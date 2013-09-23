import urllib
import os
import re
import sys

import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
import StorageServer
import xmltodict

from game_common import *
from game_xbmc import *

addon = xbmcaddon.Addon()
addon_path = xbmc.translatePath(addon.getAddonInfo('path'))
addon_profile = xbmc.translatePath(addon.getAddonInfo('profile'))
debug = addon.getSetting('debug')
cache = StorageServer.StorageServer("nfl_game_rewind", 2)
language = addon.getLocalizedString

show_archives = {
    'NFL Gameday': {'2013': '179', '2012': '146'},
    'Superbowl Archives': {'2013': '117'},
    'Top 100 Players': {'2013': '185', '2012': '153'}}


def get_nfl_network():
    for i in show_archives.keys():
        add_dir(i, '2013', 6, icon)


def no_service_check():
    no_service = ('Due to broadcast restrictions, the NFL Game Rewind service is currently unavailable.'
                  '  Please check back later.')
    service_data = make_request('https://gamerewind.nfl.com/nflgr/secure/schedule')
    if len(re.findall(no_service, service_data)) > 0:
        lines = no_service.replace('.', ',').split(',')
        dialog = xbmcgui.Dialog()
        dialog.ok(language(30018), lines[0], lines[1], lines[2])
        return True


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
        if no_service_check():
            pass
        else:
            display_seasons()
            add_dir('NFL Network', 'nfl_network_url', 5, icon)
    else:
        dialog = xbmcgui.Dialog()
        dialog.ok("Error", "Could not acquire Game Rewind metadata.")
        addon_log('Auth failed.')
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 1:
    # unused for the time being
    # will be used later when/if NFL Network and NFL RedZone support is added
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 2:
    weeks = eval(cache.get('weeks'))
    season = params['name']
    display_weeks(season)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 3:
    season, week_code = params['url'].split(';', 1)
    display_games(season, week_code)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 4:
    preferred_version = int(addon.getSetting('preferred_game_version'))
    try:
        if isinstance(eval(params['url']), dict):
            game_ids = eval(params['url'])
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
    except NameError:
        game_id = params['url']
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
