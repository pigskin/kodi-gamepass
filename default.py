import urllib
import os
import sys

import xbmcplugin
import xbmcgui
import xmltodict

from resources.lib.game_xbmc import *
    
    
if debug == 'true':
    cache.dbg = True

params = get_params()
addon_log("params: %s" %params)

try:
    mode = int(params['mode'])
except:
    mode = None
    
if mode == None:
    if start_addon():
        display_plugin_root()
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
    item = set_resolved_url(params['name'], params['url'])
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)

elif mode == 5:
    get_nfl_network()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 6:
    cid = get_show_archive(params['name'], params['url'])
    display_archive(params['name'], params['url'], cid)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 7:
    item = resolve_show_archive_url(params['url'])
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)

elif mode == 8:
    # for a do nothing list item
    pass

cache.set('mode', str(mode))
