"""
An XBMC plugin agnostic library for NFL Game Pass and Game Rewind support.
"""
import cookielib
import hashlib
from operator import itemgetter
import os
import random
import requests2 as requests
import StorageServer
import time
from traceback import format_exc
from urlparse import urlsplit
from uuid import getnode as get_mac
import xmltodict

import xbmc
import xbmcaddon
import xbmcgui


addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo('id')
addon_profile = xbmc.translatePath(addon.getAddonInfo('profile'))
addon_version = addon.getAddonInfo('version')
debug = addon.getSetting('debug')
language = addon.getLocalizedString
subscription = addon.getSetting('subscription')

if subscription == '0': # game pass
    cache = StorageServer.StorageServer("nfl_game_pass", 2)
    cookie_file = os.path.join(addon_profile, 'gp_cookie_file')
    base_url = 'https://gamepass.nfl.com/nflgp'
    show_archives = {
        'NFL Gameday': {'2014': '212', '2013': '179', '2012': '146'},
        'Playbook': {'2014': '213', '2013': '180', '2012': '147'},
        'NFL Total Access': {'2014': '214', '2013': '181', '2012': '148'},
        'NFL RedZone': {'2014': '221', '2013': '182', '2012': '149'},
        'Sound FX': {'2014': '215', '2013': '183', '2012': '150'},
        'Coaches Show': {'2014': '216', '2013': '184', '2012': '151'},
        'Top 100 Players': {'2014': '217', '2013': '185', '2012': '153'},
        'A Football Life': {'2014': '218', '2013': '186', '2012': '154'},
        'Superbowl Archives': {'2014': '117'},
        'NFL Films Presents': {'2014': '219', '2013': '187'},
        'Hard Knocks': {'2014': '220'}
    }
else: # game rewind
    cache = StorageServer.StorageServer("nfl_game_rewind", 2)
    cookie_file = os.path.join(addon_profile, 'gr_cookie_file')
    base_url = 'https://gamerewind.nfl.com/nflgr'
    show_archives = {
        'NFL Gameday': {'2014': '212', '2013': '179', '2012': '146'},
        'Superbowl Archives': {'2013': '117'},
        'Top 100 Players': {'2014': '217', '2013': '185', '2012': '153'}
    }

servlets_url = base_url.replace('https', 'http')


cookie_jar = cookielib.LWPCookieJar(cookie_file)
try:
    cookie_jar.load(ignore_discard=True, ignore_expires=True)
except:
    pass

s = requests.Session()
s.cookies = cookie_jar


class LoginFailure(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


def addon_log(string):
    if debug == 'true':
        xbmc.log("[%s-%s]: %s" %(addon_id, addon_version, string))


def make_request(url, payload=None, headers=None):
    addon_log('Request URL: %s' %url)
    addon_log('Headers: %s' %headers)

    try:
        r = s.post(url, data=payload, headers=headers, allow_redirects=False)
        addon_log('Response code: %s' %r.status_code)
        addon_log('Response: %s' %r.text)
        cookie_jar.save(ignore_discard=True, ignore_expires=False)
        return r.text
    except requests.exceptions.RequestException as e:
        addon_log('Error: - %s.' %e)


# Check age of cache, delete and update if it is older than 7200 sec (2hr)
# TODO: This shouldn't be neccesary, as we set the cache TTL with StorageServer,
# but that cache was not expiring correctly.
def check_cache():
    # for those who already have cached data, but no cachetime set
    try:
        eval(cache.get('cachetime'))
    except:
        cache.set('cachetime', "0")

    if int(cache.get('cachetime')) > (time.time() - 7200):
        addon_log('Found "young" cache')
    else:
        addon_log('Cache too old, updating')
        cache.delete('seasons')
        cache.delete('weeks')


# Handles to neccesary steps and checks to login to NFL Game Pass.
# Some regions are free, hence why username and password are optional
def login_gamepass(username=None, password=None):
    if check_for_subscription():
        addon_log('Already logged into Game Pass.')
    else:
        if username and password:
            addon_log('Not (yet) logged into Game Pass.')
            login_to_account(username, password)
            if not check_for_subscription:
                raise LoginFailure('Game Pass login failed.')
        else:
            # might need sans-login check here, though hoping above subscription check is enough
            addon_log('No username and password supplied.')
            raise LoginFailure('No username and password supplied.')


# Handles to neccesary steps and checks to login to NFL Rewind.
def login_rewind(username, password):
    if check_for_subscription():
        addon_log('Already logged into Game Rewind.')
    else:
        addon_log('Not (yet) logged into Game Rewind.')
        login_to_account(username, password)
        if not check_for_subscription():
            raise LoginFailure('Game Rewind login failed.')
        elif service_blackout():
            raise LoginFailure('Game Rewind Blackout')


def check_for_subscription():
    sc_url = servlets_url + '/servlets/simpleconsole'
    sc_data = make_request(sc_url, {'isFlex': 'true'})

    try:
        sc_dict = xmltodict.parse(sc_data)['result']

        if sc_dict.has_key('subscription'):
            addon_log('Subscription detected.')
            return True
        else:
            addon_log('No subscription was detected.')
            return False
    except:
        addon_log('Subscription detection failed gloriously.')
        raise


# NFL Game Pass/Rewind "helpfully" does not give any indication whether the
# login was successful or not. Thus, check_for_subscription() should be used
# afterwards to determine success or failure.
def login_to_account(username, password):
    url = 'https://id.s.nfl.com/login'
    post_data = {
        'username': username,
        'password': password,
        'vendor_id': 'nflptnrnln',
        'error_url': base_url + '/secure/login?redirect=loginform&redirectnosub=packages&redirectsub=schedule',
        'success_url': base_url + '/secure/login?redirect=loginform&redirectnosub=packages&redirectsub=schedule'
    }
    login_data = make_request(url, post_data)


# The plid parameter used when requesting the video path appears to be an MD5 of... something.
# I don't know what it is an "id" of, since the value seems to change constantly.
# Reusing a plid doesn't work, so I'm guessing it's a unique id for the /instance/ of the player.
# This pseudorandom approach seems to work.
def gen_plid():
    rand = random.getrandbits(10)
    mac_address = str(get_mac())
    m = hashlib.md5(str(rand) + mac_address)
    return m.hexdigest()


# the XML manifest of all available streams for a game
def get_manifest(video_path):
    parsed_url = urlsplit(video_path)
    url = 'http://' + parsed_url.netloc + '/play?url=' + parsed_url.path + '&' + parsed_url.query
    manifest_data = make_request(url)
    return manifest_data


def get_seasons():
    check_cache()

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

def get_current_season():
    try:
        cur_season = eval(cache.get('current_season'))
        return str(cur_season)
    except:
        pass

    try:
        cache_seasons_and_weeks()
        cur_season = eval(cache.get('current_season'))
        return str(cur_season)
    except:
        raise

def get_seasons_weeks(season):
    try:
        weeks = eval(cache.get('weeks'))
        weeks_dates = eval(cache.get('weeks_dates'))
        output = {
            "weeks": weeks[season],
            "dates": weeks_dates[season]
        }
        return output
    except:
        pass

    try:
        cache_seasons_and_weeks()
        weeks = eval(cache.get('weeks'))
        weeks_dates = eval(cache.get('weeks_dates'))
        output = {
            "weeks": weeks[season],
            "dates": weeks_dates[season]
        }
        return output
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
            ret = bitrate_values[dialog.select('Choose a bitrate',
                                [language(30005 + i) for i in range(len(bitrate_values))])]

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
    weeks_dates = {}
    current_season = ''

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

            # assume that first year is current season
            if current_season == '':
               current_season = str(year)

            seasons.append(year)
            weeks[year] = {}
            weeks_dates[year] = {}

            for week in season['week']:
                # games prior to 2013 don't have dates in the xml-file, so I just
                # put a static prior date
                if int(year) >= 2013:
                    week_start = week['@start']
                else:
                    week_start = '20010203'

                if week['@section'] == "pre":
                    week_code = '1' + week['@value'].zfill(2)
                    weeks[year][week_code] = 'Preseason Week ' + week['@value']
                    weeks_dates[year][week_code] = week_start
                elif week['@section'] == "reg":
                    week_code = '2' + week['@value'].zfill(2)
                    weeks[year][week_code] = 'Week ' + week['@value']
                    weeks_dates[year][week_code] = week_start
                elif week['@section'] == "post":
                    week_code = '2' + week['@value'].zfill(2)
                    weeks[year][week_code] = week['@label']
                    weeks_dates[year][week_code] = week_start
                else:
                    addon_log('Unknown week type: %' %week['@section'])
    except:
        addon_log('Parsing season and week data failed.')
        raise

    cache.set('cachetime', str(int(time.time())))
    cache.set('seasons', repr(seasons))
    addon_log('Seasons cached')
    cache.set('current_season', current_season)
    addon_log('Current season cached')
    cache.set('weeks', repr(weeks))
    cache.set('weeks_dates', repr(weeks_dates))
    addon_log('Weeks cached')

    addon_log('seasons: %s' %seasons)
    addon_log('current season: %s' %current_season)
    addon_log('weeks: %s' %weeks)
    return True


# Returns the current season and week_code in a dict
# e.g. {'2014': '210'}
def get_current_season_and_week():
    sc_url = servlets_url + '/servlets/simpleconsole'
    sc_data = make_request(sc_url, {'isFlex':'true'})

    sc_dict = xmltodict.parse(sc_data)['result']
    current_s_w = {sc_dict['currentSeason']: sc_dict['currentWeek']}
    return current_s_w


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

    game_data = make_request(url, post_data)
    game_data_dict = xmltodict.parse(game_data)['result']
    games = game_data_dict['games']['game']

    return games


def get_stream_url(game_id):
    set_cookies = get_current_season_and_week()
    if cache.get('mode') == '4':
        set_cookies = get_weeks_games(*eval(cache.get('current_schedule')))
    video_path = get_video_path(game_id)
    manifest = get_manifest(video_path)
    stream_url = parse_manifest(manifest)
    return stream_url


# the "video path" provides the info necessary to request the stream's manifest
def get_video_path(game_id):
    url = servlets_url + '/servlets/encryptvideopath'
    plid = gen_plid()
    post_data = {
        'path': game_id,
        'plid': plid,
        'type': 'fgpa',
        'isFlex': 'true'
    }
    video_path_data = make_request(url, post_data)

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
    show_name = show_name.split('-')[0]

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

    archive_data = make_request(url, post_data)
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


def get_show_archive(name, url):
    show_name = name.split(' - ')[0]
    season = url

    try:
       cid = show_archives[show_name][season]
    except:
       # if no valid cid is found in show_archives
       cid = 0

    return cid


def resolve_show_archive_url(url):
    manifest = get_manifest(url)
    stream_url = parse_manifest(manifest)
    return stream_url


def get_live_url(game_id):
    set_cookies = get_current_season_and_week()
    url = "http://gamepass.nfl.com/nflgp/servlets/publishpoint"

    if game_id == 'nfl_network':
        post_data = {'id': '1', 'type': 'channel', 'nt': '1'}
    elif game_id == 'rz':
        post_data = {'id': '2', 'type': 'channel', 'nt': '1'}
    else:
        post_data = {'id': game_id, 'type': 'game', 'nt': '1', 'gt': 'live'}

    headers = {'User-Agent' : 'Android'}
    m3u8_data = make_request(url, post_data, headers)
    m3u8_dict = xmltodict.parse(m3u8_data)['result']
    addon_log('NFL Dict %s.' %m3u8_dict)
    m3u8_url = m3u8_dict['path'].replace('adaptive://', 'http://')
    return m3u8_url.replace('androidtab', select_bitrate('live_stream'))


# Check if Game Rewind service is blacked-out due to live games in progress
def service_blackout():
    no_service = ('Due to broadcast restrictions, the NFL Game Rewind service is currently unavailable.'
                  ' Please check back later.')
    service_data = make_request('https://gamerewind.nfl.com/nflgr/secure/schedule')

    if no_service in service_data:
        return True
    else:
        return False


def set_resolved_url(name, url):
    try:
        if isinstance(eval(url), dict):
            game_ids = eval(url)
    except NameError:
        game_id = url
    if name.endswith('- Live'):
        resolved_url = get_live_url(game_ids['Live'])
    else:
        preferred_version = int(addon.getSetting('preferred_game_version'))
        game_id = game_ids[language(30014)]
        if preferred_version > 0:
            if game_ids.has_key(language(30015)):
                if preferred_version == 1:
                    game_id = game_ids[language(30015)]
                else:
                    dialog = xbmcgui.Dialog()
                    versions = [language(30014), language(30015)]
                    ret = dialog.select(language(30016), versions)
                    game_id = game_ids[versions[ret]]
        resolved_url = get_stream_url(game_id)
    addon_log('Resolved URL: %s.' %resolved_url)
    item = xbmcgui.ListItem(label=resolved_url,path=resolved_url)
    return item
