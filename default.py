import urllib
import urllib2
import re
import os
import cookielib
import time
import xbmcplugin
import xbmcgui
import xbmcvfs
import xbmcaddon
import StorageServer
import random
import md5
from uuid import getnode as get_mac
from datetime import datetime, timedelta
from traceback import format_exc
from urlparse import urlparse, parse_qs
import xmltodict
from operator import itemgetter

addon = xbmcaddon.Addon(id='plugin.video.nfl.gamepass')
addon_path = xbmc.translatePath(addon.getAddonInfo('path'))
addon_profile = xbmc.translatePath(addon.getAddonInfo('profile'))
cookie_file = os.path.join(addon_profile, 'cookie_file')
cookie_jar = cookielib.LWPCookieJar(cookie_file)
icon = os.path.join(addon_path, 'icon.png')
fanart = os.path.join(addon_path, 'fanart.jpg')
debug = addon.getSetting('debug')
addon_version = addon.getAddonInfo('version')
cache = StorageServer.StorageServer("nfl_game_pass", 2)
username = addon.getSetting('email')
password = addon.getSetting('password')
language = addon.getLocalizedString

show_archives = {
    'NFL Gameday': {'2013': '179', '2012': '146'},
    'Playbook': {'2013': '180', '2012': '147'},
    'NFL Total Access': {'2013': '181', '2012': '148'},
    'NFL RedZone': {'2013': '182', '2012': '149'},
    'Sound FX': {'2013': '183', '2012': '150'},
    'Coaches Show': {'2013': '184', '2012': '151'},
    'Top 100 Players': {'2013': '185', '2012': '153'},
    'A Football Life': {'2013': '186', '2012': '154'},
    'Superbowl Archives': {'2013': '117'},
    'NFL Films Presents': {'2013': '187'}
    }


def addon_log(string):
    if debug == 'true':
        xbmc.log("[addon.nfl.gamepass-%s]: %s" %(addon_version, string))

def cache_seasons_and_weeks(login_data):
    for i in ['\r', '\t', '\n']:
        login_data = login_data.replace(i, '')
    try:
        season_str = re.findall(
            '<select id="seasonSelect" class="select" onchange="getGameSchedule\(\)">(.+?)</select>', login_data)[0]
        seasons = re.findall('value="(.+?)"', season_str)
        cache.set('seasons', repr(seasons))
        addon_log('Seasons cached')
    except:
        addon_log('Season cache failed')
        return False

    try:
        week_str = re.findall(
            '<select id="weekSelect" class="select" onchange="getGameSchedule\(\)">(.+?)</select>', login_data)[0]
        weeks = {}
        for i in re.findall('<option value="(.+?)">(.+?)</option>', week_str):
            weeks[i[0]] = i[1]
        cache.set('weeks', repr(weeks))
        addon_log('Weeks cached')
    except:
        addon_log('Week cache failed')
        return False

    return True

def display_games(season, week_code):
    games = get_weeks_games(season, week_code)
    preferred_version = int(addon.getSetting('preferred_game_version'))
    # super bowl week has only one game, which thus isn't put into a list
    if isinstance(games, dict):
        games_list = [games]
        games = games_list

    if games:
        for game in games:
            duration = None
            mode = 4
            date_time_format = '%Y-%m-%dT%H:%M:%S.000'
            home_team = game['homeTeam']
            # sometimes the first item is empty
            if home_team['name'] is None:
                continue
            away_team = game['awayTeam']
            game_name = '%s %s at %s %s' %(away_team['city'], away_team['name'], home_team['city'], home_team['name'])

            game_ids = {}
            for i in ['condensedId', 'programId', 'id']:
                if game.has_key(i):
                    if 'condensed' in i:
                        label = language(30015)
                    elif 'program' in i:
                        label = language(30014)
                    else:
                        label = 'Live'
                    game_ids[label] = game[i]
                
            if not game.has_key('hasProgram'):
                # may want to change this to game['gameTimeGMT'] or do a setting maybe
                game_datetime = datetime(*(time.strptime(game['date'], date_time_format)[0:6]))
                game_date_string = game_datetime.strftime('%A, %b %d - %I:%M %p')
                game_name += ' - ' + game_date_string + ' ET'
                mode = 8
            if game.has_key('isLive'):
                # sometimes isLive lies
                if not game.has_key('gameEndTimeGMT'):
                    game_name += ' - Live'
            if game.has_key('gameEndTimeGMT'):
                try:
                    start_time = datetime(*(time.strptime(game['gameTimeGMT'], date_time_format)[0:6]))
                    end_time = datetime(*(time.strptime(game['gameEndTimeGMT'], date_time_format)[0:6]))
                    duration = (end_time - start_time).seconds / 60
                except:
                    addon_log(format_exc())

            add_dir(game_name, game_ids, mode, icon, '', duration, False)
    else:
        dialog = xbmcgui.Dialog()
        dialog.ok("Fetching Games Failed", "Fetching Game Data Failed.")
        addon_log('Fetching games failed.')

def display_seasons(seasons):
    for season in seasons:
        add_dir(season, season, 2, icon)

def display_weeks(season, weeks):
    for week_code, week_name in sorted(weeks.iteritems()):
        add_dir(week_name, season + ';' + week_code, 3, icon)

def check_login():
    if not xbmcvfs.exists(addon_profile):
        xbmcvfs.mkdir(addon_profile)

    if addon.getSetting('sans_login') == 'true':
        data = make_request('https://gamepass.nfl.com/nflgp/secure/schedule')
        return cache_seasons_and_weeks(data)

    elif username and password:
        if not xbmcvfs.exists(cookie_file):
            return gamepass_login()
        else:
            cookie_jar.load(cookie_file, ignore_discard=True, ignore_expires=True)
            cookies = {}
            for i in cookie_jar:
                cookies[i.name] = i.value
            login_ok = False
            if cookies.has_key('userId'):
                data = make_request('https://gamepass.nfl.com/nflgp/secure/myaccount')
                try:
                    login_ok = re.findall('Update Account Information / Change Password', data)[0]
                except IndexError:
                    addon_log('Not Logged In')
                if not login_ok:
                    return gamepass_login()
                else:
                    addon_log('Logged In')
                    data = make_request('https://gamepass.nfl.com/nflgp/secure/schedule')
                    return cache_seasons_and_weeks(data)
            else:
                return gamepass_login()
    else:
        dialog = xbmcgui.Dialog()
        dialog.ok("Account Info Not Set", "Please set your Game Pass username and password", "in Add-on Settings.")
        addon_log('No account settings detected.')

def gamepass_login():
    url = 'https://id.s.nfl.com/login'
    post_data = {
        'username': username,
        'password': password,
        'vendor_id': 'nflptnrnln',
        'error_url': 'https://gamepass.nfl.com/nflgp/secure/login?redirect=loginform&redirectnosub=packages&redirectsub=schedule',
        'success_url': 'https://gamepass.nfl.com/nflgp/secure/login?redirect=loginform&redirectnosub=packages&redirectsub=schedule'
    }
    login_data = make_request(url, urllib.urlencode(post_data))

    cache_success = cache_seasons_and_weeks(login_data)

    if cache_success:
        addon_log('login success')
        return True
    else: # if cache failed, then login failed or the login page's HTML changed
        dialog = xbmcgui.Dialog()
        dialog.ok("Login Failed", "Logging into NFL Game Pass failed.", "Make sure your account information is correct.")
        addon_log('login failed')
        return False

# The plid parameter used when requesting the video path appears to be an MD5 of... something.
# However, I don't know what it is an "id" of, since the value seems to change constantly.
# Reusing a plid doesn't work, so I assume it's a unique id for the instance of the player.
# This, pseudorandom approach seems to work for now.
def gen_plid():
    rand = random.getrandbits(10)
    mac_address = str(get_mac())
    m = md5.new(str(rand) + mac_address)
    return m.hexdigest()

# the XML manifest of all available streams for a game
def get_manifest(video_path):
    url, port, path = video_path.partition(':443')
    path = path.replace('?', '&')
    url = url.replace('adaptive://', 'http://') + port + '/play?' + urllib.quote_plus('url=' + path, ':&=')

    manifest_data = make_request(url)

    return manifest_data

def get_publishpoint_url(game_id):
    set_cookies = get_current_week()
    url = "http://gamepass.nfl.com/nflgp/servlets/publishpoint"
    if game_id == 'nfl_network':
        post_data = {
            'id': '1',
            'type': 'channel',
            'nt': '1'
            }
    else:
        post_data = {
            'id' : game_id,
            'type' : 'game',
            'nt' : '1',
            'gt' : 'live'
            }
    headers = {'User-Agent' : 'Android'}
    m3u8_data = make_request(url, urllib.urlencode(post_data), headers)
    m3u8_dict = xmltodict.parse(m3u8_data)['result']
    addon_log('NFL Dict %s.' %m3u8_dict)
    m3u8_url = m3u8_dict['path'].replace('adaptive://', 'http://')
    return m3u8_url.replace('androidtab', select_bitrate('live_stream'))

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
    url = 'https://gamepass.nfl.com/nflgp/servlets/encryptvideopath'
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

# season is in format: YYYY
# week is in format 101 (1st week preseason) or 213 (13th week of regular season)
def get_weeks_games(season, week):
    cache.set('current_schedule', repr((season, week)))
    url = 'https://gamepass.nfl.com/nflgp/servlets/games'
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

def get_nfl_network():
    add_dir('NFL Network - Live', 'nfl_network_url', 4, icon, discription="NFL Network", duration=None, isfolder=False)
    for i in show_archives.keys():
        add_dir(i, '2013', 6, icon)

def get_nfl_redzone():
    url = 'http://gamepass.nfl.com/nflgp/servlets/simpleconsole'
    simple_data = make_request(url, urllib.urlencode({'isFlex':'true'}))
    simple_dict = xmltodict.parse(simple_data)['result']
    if simple_dict['rzPhase'] == 'in':
        add_dir('NFL RedZone - Live', 'frz', 4, icon, discription="NFL RedZone - Live", duration=None, isfolder=False)

# parse archives for NFL Network, RedZone, Fantasy
def parse_archive(show_name, season):
    cid = show_archives[show_name][season]
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
    image_path = 'http://smb.cdn.neulion.com/u/nfl/nfl/thumbs/'
    archive_data = make_request(url, urllib.urlencode(post_data))
    archive_dict = xmltodict.parse(archive_data)['result']
    addon_log('Archive Dict: %s' %archive_dict)

    count = int(archive_dict['paging']['count'])
    if count < 1:
        if season == '2013':
            return parse_archive(show_name, '2012')
    else:
        items = archive_dict['programs']['program']
        if isinstance(items, dict):
            items_list = [items]
            items = items_list
        for i in items:
            add_dir(i['name'], i['publishPoint'], 7, image_path + i['image'], '%s\n%s' %(i['description'], i['releaseDate']), i['runtime'], False)
    if season == '2013':
        if not (show_name == 'Superbowl Archives' or show_name == 'NFL Films Presents'):
            add_dir('%s - Season 2012' %show_name, '2012', 6, icon)

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

def parse_manifest(manifest):
    try:
        manifest_dict = xmltodict.parse(manifest)
        items = [{'servers': [{'name': x['@name'], 'port': x['@port']} for x in i['httpservers']['httpserver']],
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

def add_dir(name, url, mode, iconimage, discription="", duration=None, isfolder=True):
    params = {'name': name, 'url': url, 'mode': mode}
    url = '%s?%s' %(sys.argv[0], urllib.urlencode(params))
    listitem = xbmcgui.ListItem(name, iconImage=iconimage, thumbnailImage=iconimage)
    listitem.setProperty("Fanart_Image", fanart)
    if not isfolder:
        if not mode == 8:
            # IsPlayable tells xbmc that there is more work to be done to resolve a playable url
            listitem.setProperty('IsPlayable', 'true')
        listitem.setInfo(type="Video", infoLabels={"Title": name, "Plot": discription, "Duration": duration})
    xbmcplugin.addDirectoryItem(int(sys.argv[1]), url, listitem, isfolder)

def get_current_week():
    url = 'http://gamepass.nfl.com/nflgp/servlets/simpleconsole'
    data = make_request(url, urllib.urlencode({'isFlex':'true'}))
    if data:
        return data
    return 'False'

def get_params():
    p = parse_qs(sys.argv[2][1:])
    for i in p.keys():
        p[i] = p[i][0]
    return p


if debug == 'true':
    cache.dbg = True

params = get_params()
addon_log("params: %s" %params)

try:
    mode = int(params['mode'])
except:
    mode = None
    

if mode == None:
    auth = check_login()
    if auth:
        seasons = eval(cache.get('seasons'))
        display_seasons(seasons)
        add_dir('NFL Network', 'nfl_network_url', 5, icon)
        get_nfl_redzone()
    else:
        dialog = xbmcgui.Dialog()
        dialog.ok("Error", "Could not acquire Game Pass metadata.")
        addon_log('Auth failed.')
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 1:
    # unused for the time being
    # will be used later when/if NFL Network and NFL RedZone support is added
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 2:
    weeks = eval(cache.get('weeks'))
    season = params['name']
    display_weeks(season, weeks)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 3:
    season, week_code = params['url'].split(';', 1)
    display_games(season, week_code)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 4:
    try:
        if isinstance(eval(params['url']), dict):
            game_ids = eval(params['url'])
    except NameError:
        game_id = params['url']
    if params['name'] == 'NFL Network - Live':
        resolved_url = get_publishpoint_url('nfl_network')
    elif params['name'] == 'NFL RedZone - Live':
        resolved_url = get_stream_url(game_id, 'NFL RedZone')
    elif params['name'].endswith('- Live'):
        resolved_url = get_publishpoint_url(game_ids['Live'])
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
    item = xbmcgui.ListItem(path=resolved_url)
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)

elif mode == 5:
    get_nfl_network()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 6:
    parse_archive(params['name'].split(' - ')[0], params['url'])
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 7:
    manifest = get_manifest(params['url'])
    stream_url = parse_manifest(manifest)
    item = xbmcgui.ListItem(path=stream_url)
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)

elif mode == 8:
    # for a do nothing list item
    pass

cache.set('mode', str(mode))