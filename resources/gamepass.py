import urllib
import os
import sys

import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
import StorageServer
import xmltodict

from game_common import *
from game_xbmc import *

addon = xbmcaddon.Addon(id='plugin.video.nfl.gamepass')
addon_path = xbmc.translatePath(addon.getAddonInfo('path'))
addon_profile = xbmc.translatePath(addon.getAddonInfo('profile'))
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


def get_publishpoint_url(game_id):
    set_cookies = get_current_week()
    url = "http://gamepass.nfl.com/nflgp/servlets/publishpoint"
    nt = '1'
    if (game_id == 'nfl_network' or game_id == 'rz'):
        type = 'channel'
        if game_id == 'rz':
            id = '2'
        else:
            id = '1'
        post_data = {
            'id': id,
            'type': type,
            'nt': nt 
            }
    else:
        post_data = {
            'id' : game_id,
            'type' : 'game',
            'nt' : nt,
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
        add_dir('NFL RedZone - Live', 'rz', 4, icon, discription="NFL RedZone - Live", duration=None, isfolder=False)


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
        dialog.ok("Error", "Could not access Game Pass.")
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
    week_code = re.sub('".*', '', week_code)
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
        resolved_url = get_publishpoint_url(game_id)
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
    show_name = params['name'].split(' - ')[0]
    season = params['url']
    cid = show_archives[show_name][season]
    display_archive(show_name, season, cid)
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
