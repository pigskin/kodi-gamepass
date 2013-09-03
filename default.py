import urllib
import urllib2
import re
import os
import json
import cookielib
import time
import xbmcplugin
import xbmcgui
import xbmcvfs
import xbmcaddon
import StorageServer
import xml.etree.ElementTree as ElementTree
import random
import md5
from uuid import getnode as get_mac
from datetime import datetime, timedelta
from traceback import format_exc
from urlparse import urlparse, parse_qs
from BeautifulSoup import BeautifulSoup
from BeautifulSoup import BeautifulStoneSoup
from operator import itemgetter
from XmlDict import XmlDictConfig

addon = xbmcaddon.Addon(id='plugin.video.nfl.gamepass')
addon_path = xbmc.translatePath(addon.getAddonInfo('path'))
addon_profile = xbmc.translatePath(addon.getAddonInfo('profile'))
cookie_file = os.path.join(addon_profile, 'cookie_file')
cookie_jar = cookielib.LWPCookieJar(cookie_file)
icon = os.path.join(addon_path, 'icon.png')
fanart = os.path.join(addon_path, 'fanart.jpg')
debug = addon.getSetting('debug')
addon_version = addon.getAddonInfo('version')
cache = StorageServer.StorageServer("nfl_game_pass", 24)
username = addon.getSetting('email')
password = addon.getSetting('password')

show_archives = {
    'NFL Gameday': {'2013': '179', '2012': '146'},
    'Playbook': {'2013': '180', '2012': '147'},
    'NFL Total Access': {'2013': '181', '2012': '148'},
    'Sound FX': {'2013': '183', '2012': '150'},
    'Coaches Show': {'2013': '184', '2012': '151'},
    'Top 100 Players': {'2013': '185', '2012': '153'},
    'A Football Life': {'2013': '186', '2012': '154'},
    'Superbowl Archives': {'2013': '117'}
     # {'NFL Films Presents': {'2013': '187', '2012': ''}}, isn't showing any episodes
    }
     
     
def addon_log(string):
    if debug == 'true':
        xbmc.log("[addon.nfl.gamepass-%s]: %s" %(addon_version, string))

def cache_seasons_and_weeks(login_data):
    soup = BeautifulSoup(login_data, convertEntities=BeautifulSoup.HTML_ENTITIES)

    try:
        seasons_soup = soup.find('select', id='seasonSelect').findChildren()
        seasons = []
        for season in seasons_soup:
            seasons.append(season.string)
        cache.set('seasons', repr(seasons))
        addon_log('Seasons cached')
    except:
        addon_log('Season cache failed')
        return False

    try:
        weeks_soup = soup.find('select', id='weekSelect').findChildren()
        weeks = {}
        for week in weeks_soup:
            week_code = week['value']
            weeks[week_code] = week.string
        cache.set('weeks', repr(weeks))
        addon_log('Weeks cached')
    except:
        addon_log('Week cache failed')
        return False

    return True

def display_games(season, week_code):
    games = get_weeks_games(season, week_code)

    # super bowl week has only one game, which thus isn't put into a list
    if isinstance(games, dict):
        games_list = [games]
        games = games_list
    
    if games:
        for game in games:
            home_team = game['homeTeam']
            away_team = game['awayTeam']
            game_name = '%s %s at %s %s' %(away_team['city'], away_team['name'], home_team['city'], home_team['name'])

            date_time_format = '%Y-%m-%dT%H:%M:%S.000'
            try:
                start_time = datetime(*(time.strptime(game['gameTimeGMT'], date_time_format)[0:6]))
                end_time = datetime(*(time.strptime(game['gameEndTimeGMT'], date_time_format)[0:6]))
                duration = (end_time - start_time).seconds / 60
            except:
                addon_log(format_exc())
                duration = None

            add_dir(game_name, game['programId'], 4, icon, '', duration, False)
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

def get_nfl_network_url():
    url = 'http://gamepass.nfl.com/nflgp/servlets/publishpoint'
    post_data = {
        'id': '1',
        'type': 'channel',
        'nt': '1'
    }
    headers = {'User-Agent' : 'Android'}
    m3u8_data = make_request(url, urllib.urlencode(post_data), headers)

    root = ElementTree.XML(m3u8_data)
    m3u8_dict = XmlDictConfig(root)
    addon_log('NFL Dict %s.' %m3u8_dict)
    m3u8_url = m3u8_dict['path'].replace('adaptive://', 'http://')

    return m3u8_url.replace('androidtab', select_bitrate('live_stream'))

def get_stream_url(game_id, post_data=None):
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
    post_data = {
        'path': game_id,
        'plid': plid,
        'type': type,
        'isFlex': 'true'
    }
    video_path_data = make_request(url, urllib.urlencode(post_data))

    try:
        soup = BeautifulStoneSoup(video_path_data, convertEntities=BeautifulSoup.XML_ENTITIES)
        video_path = soup.find('path')
        addon_log('Video Path Acquired Successfully.')
        return video_path.string
    except:
        addon_log('Video Path Acquisition Failed.')
        return False

# season is in format: YYYY
# week is in format 101 (1st week preseason) or 213 (13th week of regular season)
def get_weeks_games(season, week):
    url = 'https://gamepass.nfl.com/nflgp/servlets/games'
    post_data = {
        'isFlex': 'true',
        'season': season,
        'week': week
    }

    game_data = make_request(url, urllib.urlencode(post_data))
    #addon_log('game data: %s' %game_data)
    
    root = ElementTree.XML(game_data)
    game_data_dict = XmlDictConfig(root)
    #addon_log('game data dict: %s' %game_data_dict)
    games = game_data_dict['games']

    return games['game']
    
def get_nfl_network():
    add_dir('NFL Network - Live', 'nfl_network_url', 4, icon, discription="NFL Network", duration=None, isfolder=False)
    for i in show_archives.keys():
        add_dir(i, '2013', 6, icon)
             

# parse archives for NFL Network, RedZone, Fantasy
def parse_archive(show_name, season):
    cid = show_archives[show_name][season]
    url = 'http://gamepass.nfl.com/nflgp/servlets/browse'
    post_data = {
        'isFlex':'true',
        'cid': cid,
        'pm': 0,
        'ps': 50,
        'pn': 1
        }
    image_path = 'http://smb.cdn.neulion.com/u/nfl/nfl/thumbs/'
    data = make_request(url, urllib.urlencode(post_data))
    root = ElementTree.XML(data)
    archive_dict = XmlDictConfig(root)
    count = int(archive_dict['paging']['count'])
    if count < 1:
        if season == '2013':
            return parse_archive(show_name, '2012')
    else:
        items = archive_dict['programs']['program']
        for i in items:
            add_dir(i['name'], i['publishPoint'], 7, image_path + i['image'], '%s\n%s' %(i['description'], i['releaseDate']), i['runtime'], False)
        if season == '2013':
            if not show_name == 'Superbowl Archives':
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
        soup = BeautifulStoneSoup(manifest, convertEntities=BeautifulStoneSoup.XML_ENTITIES)
        items = [{'servers': [{'name': x['name'], 'port': x['port']} for x in i('httpserver')],
                  'url': i['url'], 'bitrate': int(i['bitrate']),
                  'info': '%sx%s Bitrate: %s' %(i.video['height'], i.video['width'], i['bitrate'])}
                 for i in soup('streamdata')]

        ret = select_bitrate(items)

        if ret >= 0:
            addon_log('Selected: %s' %items[ret])
            stream_url = 'http://%s%s' %(items[ret]['servers'][0]['name'], items[ret]['url'])
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
        # IsPlayable tells xbmc that there is more work to be done to resolve a playable url
        listitem.setProperty('IsPlayable', 'true')
        listitem.setInfo(type="Video", infoLabels={"Title": name, "Plot": discription, "Duration": duration})
    xbmcplugin.addDirectoryItem(int(sys.argv[1]), url, listitem, isfolder)

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
    seasons = None
    sans_login_region = addon.getSetting('sans_login')

    if sans_login_region == 'true':
        try:
            seasons = eval(cache.get('seasons'))
        except SyntaxError:
            addon_log('No season cache')
            data = make_request('https://gamepass.nfl.com/nflgp/secure/schedule')
            ok = cache_seasons_and_weeks(data)
            if ok:
                seasons = eval(cache.get('seasons'))
    else:
        if username and password:
            login_success = gamepass_login()
            if login_success:
                seasons = eval(cache.get('seasons'))
        else:
            dialog = xbmcgui.Dialog()
            dialog.ok("Account Info Not Set", "Please set your Game Pass username and password", "in Add-on Settings.")
            addon_log('No account settings detected.')
        
    if seasons:
        display_seasons(seasons)
    else:
        dialog = xbmcgui.Dialog()
        dialog.ok("Error", "Could not acquire Game Pass metadata.")
        addon_log('No seasons data.')

    add_dir('NFL Network', 'nfl_network_url', 5, icon)
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
    game_id = params['url']
    if params['name'] == 'NFL Network - Live':
        resolved_url = get_nfl_network_url()
    else:
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