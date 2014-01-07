
import os
import cookielib

import xbmc
import xbmcaddon
import StorageServer
import time

addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo('id')
addon_path = xbmc.translatePath(addon.getAddonInfo('path'))
addon_profile = xbmc.translatePath(addon.getAddonInfo('profile'))
debug = addon.getSetting('debug')
addon_version = addon.getAddonInfo('version')
subscription = addon.getSetting('subscription')
language = addon.getLocalizedString
if subscription == '0': # game pass
    username = addon.getSetting('email')
    password = addon.getSetting('password')
    cache = StorageServer.StorageServer("nfl_game_pass", 2)
    cookie_file = os.path.join(addon_profile, 'gp_cookie_file')
    base_url = 'https://gamepass.nfl.com/nflgp'
    icon = os.path.join(addon_path, 'resources', 'images', 'gp_icon.png')
    fanart = os.path.join(addon_path, 'resources', 'images', 'gp_fanart.jpg')
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
    username = addon.getSetting('gr_email')
    password = addon.getSetting('gr_password')
    cache = StorageServer.StorageServer("nfl_game_rewind", 2)
    cookie_file = os.path.join(addon_profile, 'gr_cookie_file')
    base_url = 'https://gamerewind.nfl.com/nflgr'
    icon = os.path.join(addon_path, 'resources', 'images', 'gr_icon.png')
    fanart = os.path.join(addon_path, 'resources', 'images', 'gr_fanart.jpg')
    show_archives = {
        'NFL Gameday': {'2014': '212', '2013': '179', '2012': '146'},
        'Superbowl Archives': {'2013': '117'},
        'Top 100 Players': {'2014': '217', '2013': '185', '2012': '153'}
        }
    
servlets_url = base_url.replace('https', 'http')
cookie_jar = cookielib.LWPCookieJar(cookie_file)
