import urllib
import os
import time
import sys
from datetime import datetime, timedelta
from traceback import format_exc
from urlparse import urlparse, parse_qs

import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
import StorageServer
import xmltodict

from game_common import *

addon = xbmcaddon.Addon(id='plugin.video.nfl.gamepass')
addon_path = xbmc.translatePath(addon.getAddonInfo('path'))
addon_profile = xbmc.translatePath(addon.getAddonInfo('profile'))
icon = os.path.join(addon_path, 'icon.png')
fanart = os.path.join(addon_path, 'fanart.jpg')
debug = addon.getSetting('debug')
cache = StorageServer.StorageServer("nfl_game_pass", 2)
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

def display_seasons():
    seasons = get_seasons()
    for season in seasons:
        add_dir(season, season, 2, icon)

def display_weeks(season):
    weeks = get_seasons_weeks(season)
    for week_code, week_name in sorted(weeks.iteritems()):
        add_dir(week_name, season + ';' + week_code, 3, icon)

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

def display_archive(show_name, season):
    cid = show_archives[show_name][season]
    items = parse_archive(cid, show_name)
    image_path = 'http://smb.cdn.neulion.com/u/nfl/nfl/thumbs/'
    if items:
        for i in items:
            add_dir(i['name'], i['publishPoint'], 7, image_path + i['image'], '%s\n%s' %(i['description'], i['releaseDate']), i['runtime'], False)

        if season == '2013':
            if not (show_name == 'Superbowl Archives' or show_name == 'NFL Films Presents'):
                add_dir('%s - Season 2012' %show_name, '2012', 6, icon)
    elif season == '2013':
        return display_archive(show_name, '2012')

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
        display_seasons()
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
    season = params['name']
    display_weeks(season)
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
    display_archive(params['name'].split(' - ')[0], params['url'])
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