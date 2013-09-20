"""
An XBMC agnostic library for NFL Game Pass and Game Rewind support.
"""
import urllib
import urllib2
import re
import os
import cookielib
import hashlib
import random
from operator import itemgetter
from uuid import getnode as get_mac
from traceback import format_exc

import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon
import StorageServer
import xmltodict

addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo('id')
addon_path = xbmc.translatePath(addon.getAddonInfo('path'))
addon_profile = xbmc.translatePath(addon.getAddonInfo('profile'))
debug = addon.getSetting('debug')
addon_version = addon.getAddonInfo('version')
subscription = addon.getSetting('subscription')

if subscription == '0': # game pass
    username = addon.getSetting('email')
    password = addon.getSetting('password')
    cache = StorageServer.StorageServer("nfl_game_pass", 2)
    cookie_file = os.path.join(addon_profile, 'gp_cookie_file')
    base_url = 'https://gamepass.nfl.com/nflgp'
    servlets_url = base_url
    icon = os.path.join(addon_path, 'resources', 'gp_icon.png')
    fanart = os.path.join(addon_path, 'resources', 'gp_fanart.jpg')
else: # game rewind
    username = addon.getSetting('gr_email')
    password = addon.getSetting('gr_password')
    cache = StorageServer.StorageServer("nfl_game_rewind", 2)
    cookie_file = os.path.join(addon_profile, 'gr_cookie_file')
    base_url = 'https://gamerewind.nfl.com/nflgr'
    servlets_url = base_url.replace('https', 'http')
    icon = os.path.join(addon_path, 'resources', 'gr_icon.png')
    fanart = os.path.join(addon_path, 'resources', 'gr_fanart.jpg')
cookie_jar = cookielib.LWPCookieJar(cookie_file)


def addon_log(string):
    if debug == 'true':
        xbmc.log("[%s-%s]: %s" %(addon_id, addon_version, string))


def make_request(url, data=None, headers=None):
    addon_log('Request URL: %s' %url)
    if not xbmcvfs.exists(cookie_file):
        addon_log('Creating cookie_file!')
        cookie_jar.save()
    cookie_jar.load(cookie_file, ignore_discard=True, ignore_expires=True)
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie_jar))
    urllib2.install_opener(opener)
    try:
        if headers is None:
            req = urllib2.Request(url, data)
        else:
            req = urllib2.Request(url, data, headers)
        response = urllib2.urlopen(req)
        cookie_jar.save(cookie_file, ignore_discard=True, ignore_expires=False)
        data = response.read()
        addon_log(str(response.info()))
        redirect_url = response.geturl()
        response.close()
        if redirect_url != url:
                addon_log('Redirect URL: %s' %redirect_url)
        return data
    except urllib2.URLError, e:
        addon_log('We failed to open "%s".' %url)
        if hasattr(e, 'reason'):
            addon_log('We failed to reach a server.')
            addon_log('Reason: %s' %e.reason)
        if hasattr(e, 'code'):
            addon_log('We failed with error code - %s.' %e.code)


def check_login():
    if not xbmcvfs.exists(addon_profile):
        xbmcvfs.mkdir(addon_profile)

    if username and password:
        if not xbmcvfs.exists(cookie_file):
            return gamepass_login()
        else:
            cookie_jar.load(cookie_file, ignore_discard=True, ignore_expires=True)
            cookies = {}
            for i in cookie_jar:
                cookies[i.name] = i.value
            login_ok = False
            if cookies.has_key('userId'):
                already_logged_in = check_for_subscription()

                if already_logged_in:
                    addon_log('Already logged in')
                    return True
                else:
                    addon_log('Not yet logged in')
                    return gamepass_login()
            else:
                return gamepass_login()
    elif subscription == '0':
        if addon.getSetting('sans_login') == 'true':
            return True
    else:
        dialog = xbmcgui.Dialog()
        dialog.ok("Account Info Not Set", "Please set your Game Pass username and password", "in Add-on Settings.")
        addon_log('No account settings detected.')
        return False

def check_for_subscription():
    sc_url = servlets_url + '/servlets/simpleconsole'
    sc_post_data = { 'isFlex': 'true' }
    sc_data = make_request(sc_url, urllib.urlencode(sc_post_data))

    try:
        sc_dict = xmltodict.parse(sc_data)['result']

        if sc_dict.has_key('subscription'):
            addon_log('Game Pass subscription detected.')
            return True
        else:
            addon_log('No Game Pass subscription was detected.')
            return False
    except:
        dialog = xbmcgui.Dialog()
        addon_log('Subscription detection failed gloriously.')
        return False


def gamepass_login():
    url = 'https://id.s.nfl.com/login'
    post_data = {
        'username': username,
        'password': password,
        'vendor_id': 'nflptnrnln',
        'error_url': base_url + '/secure/login?redirect=loginform&redirectnosub=packages&redirectsub=schedule',
        'success_url': base_url + '/secure/login?redirect=loginform&redirectnosub=packages&redirectsub=schedule'
    }
    login_data = make_request(url, urllib.urlencode(post_data))

    login_success = check_for_subscription()

    if login_success:
        return True
    else:
        dialog = xbmcgui.Dialog()
        dialog.ok("Login Failed", "Logging into NFL Game Pass failed.", "Make sure your account information is correct.")
        addon_log('Game Pass login failure')


# The plid parameter used when requesting the video path appears to be an MD5 of... something.
# However, I don't know what it is an "id" of, since the value seems to change constantly.
# Reusing a plid doesn't work, so I assume it's a unique id for the instance of the player.
# This, pseudorandom approach seems to work for now.
def gen_plid():
    rand = random.getrandbits(10)
    mac_address = str(get_mac())
    m = hashlib.md5(str(rand) + mac_address)
    return m.hexdigest()


# the XML manifest of all available streams for a game
def get_manifest(video_path):
    url, port, path = video_path.partition(':443')
    path = path.replace('?', '&')
    url = url.replace('adaptive://', 'http://') + port + '/play?' + urllib.quote_plus('url=' + path, ':&=')
    manifest_data = make_request(url)
    return manifest_data


def get_seasons():
    try:
        seasons = eval(cache.get('seasons'))
        return seasons
    except:
        pass

    try:
        cache_seasons_and_weeks()
        seasons = eval(cache.get('seasons'))
        return seasons
    except:
        raise


def get_seasons_weeks(season):
    try:
        weeks = eval(cache.get('weeks'))
        return weeks[season]
    except:
        pass

    try:
        cache_seasons_and_weeks()
        weeks = eval(cache.get('weeks'))
        return weeks[season]
    except:
        raise


def parse_manifest(manifest):
    try:
        manifest_dict = xmltodict.parse(manifest)
        if isinstance(manifest_dict['channel']['streamDatas']['streamData'][0]['httpservers']['httpserver'], list):
            items = [{'servers': [{'name': x['@name'], 'port': x['@port']} for x in i['httpservers']['httpserver']],
                      'url': i['@url'], 'bitrate': int(i['@bitrate']),
                      'info': '%sx%s Bitrate: %s' %(i['video']['@height'], i['video']['@width'], i['video']['@bitrate'])}
                     for i in manifest_dict['channel']['streamDatas']['streamData']]
        else:
            items = [{'servers': [{'name': x['@name'], 'port': x['@port']} for x in [i['httpservers']['httpserver']]],
                      'url': i['@url'], 'bitrate': int(i['@bitrate']),
                      'info': '%sx%s Bitrate: %s' %(i['video']['@height'], i['video']['@width'], i['video']['@bitrate'])}
                     for i in manifest_dict['channel']['streamDatas']['streamData']]

        ret = select_bitrate(items)

        if ret >= 0:
            addon_log('Selected: %s' %items[ret])
            stream_url = 'http://%s%s.m3u8' %(items[ret]['servers'][0]['name'], items[ret]['url'])
            addon_log('Stream URL: %s' %stream_url)
            return stream_url
        else: raise
    except:
        addon_log(format_exc())
        return False


def select_bitrate(streams):
    preferred_bitrate = addon.getSetting('preferred_bitrate')
    bitrate_values = ['4500', '3000', '2400', '1600', '1200', '800', '400']
    if streams == 'live_stream':
        if preferred_bitrate == '0' or preferred_bitrate == '1':
            ret = bitrate_values[0]
        elif preferred_bitrate != '8':
            ret = bitrate_values[int(preferred_bitrate) -1]
        else:
            dialog = xbmcgui.Dialog()
            ret = bitrate_values[dialog.select('Choose a bitrate', [i for i in bitrate_values])]

    else:
        streams.sort(key=itemgetter('bitrate'), reverse=True)
        if preferred_bitrate == '0':
            ret = 0
        elif len(streams) == 7 and preferred_bitrate != '8':
            ret = int(preferred_bitrate) - 1
        else:
            dialog = xbmcgui.Dialog()
            ret = dialog.select('Choose a stream', [i['info'] for i in streams])
    addon_log('ret: %s' %ret)
    return ret


def cache_seasons_and_weeks():
    seasons = []
    weeks = {}

    try:
        url = 'http://smb.cdnak.neulion.com/fs/nfl/nfl/mobile/weeks_v2.xml'
        s_w_data = make_request(url)
        s_w_data_dict = xmltodict.parse(s_w_data)
    except:
        addon_log('Acquiring season and week data failed.')
        raise

    try:
        for season in s_w_data_dict['seasons']['season']:
            year = season['@season']
            seasons.append(year)
            weeks[year] = {}

            for week in season['week']:
                if week['@section'] == "pre":
                    week_code = '1' + week['@value'].zfill(2)
                    weeks[year][week_code] = 'Preseason Week ' + week['@value']
                elif week['@section'] == "reg":
                    week_code = '2' + week['@value'].zfill(2)
                    weeks[year][week_code] = 'Week ' + week['@value']
                elif week['@section'] == "post":
                    week_code = '2' + week['@value'].zfill(2)
                    weeks[year][week_code] = week['@label']
                else:
                    addon_log('Unknown week type: %' %week['@section'])
    except:
        addon_log('Parsing season and week data failed.')
        raise

    cache.set('seasons', repr(seasons))
    addon_log('Seasons cached')
    cache.set('weeks', repr(weeks))
    addon_log('Weeks cached')

    addon_log('seasons: %s' %seasons)
    addon_log('weeks: %s' %weeks)
    return True


def get_current_week():
    url = servlets_url + '/servlets/simpleconsole'
    data = make_request(url, urllib.urlencode({'isFlex':'true'}))
    if data:
        return data
    return 'False'


# season is in format: YYYY
# week is in format 101 (1st week preseason) or 213 (13th week of regular season)
def get_weeks_games(season, week):
    cache.set('current_schedule', repr((season, week)))
    url = servlets_url + '/servlets/games'
    post_data = {
        'isFlex': 'true',
        'season': season,
        'week': week
    }

    game_data = make_request(url, urllib.urlencode(post_data))
    #addon_log('game data: %s' %game_data)

    game_data_dict = xmltodict.parse(game_data)['result']
    #addon_log('game data dict: %s' %game_data_dict)
    games = game_data_dict['games']['game']

    return games


def get_stream_url(game_id, post_data=None):
    set_cookies = get_current_week()
    if cache.get('mode') == '4':
        set_cookies = get_weeks_games(*eval(cache.get('current_schedule')))
    video_path = get_video_path(game_id, post_data)
    manifest = get_manifest(video_path)
    stream_url = parse_manifest(manifest)
    return stream_url


# the "video path" provides the info neccesary to request the stream's manifest
def get_video_path(game_id, post_data):
    url = servlets_url + '/servlets/encryptvideopath'
    plid = gen_plid()
    if post_data is None:
        type = 'fgpa'
    elif post_data == 'NFL Network':
        type = 'channel'
    elif post_data == 'NFL RedZone':
        type = 'frz'
    post_data = {
        'path': game_id,
        'plid': plid,
        'type': type,
        'isFlex': 'true'
    }

    video_path_data = make_request(url, urllib.urlencode(post_data))

    try:
        video_path_dict = xmltodict.parse(video_path_data)['result']
        addon_log('Video Path Acquired Successfully.')
        return video_path_dict['path']
    except:
        addon_log('Video Path Acquisition Failed.')
        return False


# parse archives for NFL Network, RedZone
def parse_archive(cid, show_name):
    url = 'http://gamepass.nfl.com/nflgp/servlets/browse'
    if show_name == 'NFL RedZone':
        ps = 17
    else:
        ps = 50
    post_data = {
        'isFlex':'true',
        'cid': cid,
        'pm': 0,
        'ps': ps,
        'pn': 1
        }
    archive_data = make_request(url, urllib.urlencode(post_data))
    archive_dict = xmltodict.parse(archive_data)['result']
    addon_log('Archive Dict: %s' %archive_dict)

    count = int(archive_dict['paging']['count'])
    if count < 1:
        return
    else:
        items = archive_dict['programs']['program']
        if isinstance(items, dict):
            items_list = [items]
            items = items_list
        return items
