"""
An XBMC specific library for NFL Game Pass and Game Rewind support.
"""
import os
import sys
import urllib
import time
from datetime import datetime
import time
from urlparse import parse_qs
from traceback import format_exc

import xbmc
import xbmcplugin
import xbmcgui
import xbmcvfs
import xbmcaddon
import StorageServer

from game_common import *

language = addon.getLocalizedString

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


def display_archive(show_name, season, cid):
    items = parse_archive(cid, show_name)
    image_path = 'http://smb.cdn.neulion.com/u/nfl/nfl/thumbs/'
    if items:
        for i in items:
            try:
                name = i['name']
                add_dir(name, i['publishPoint'], 7, image_path + i['image'], '%s\n%s' %(i['description'], i['releaseDate']), i['runtime'], False)
            except:
                addon_log('Exception adding archive directory: %s' %format_exc())
                addon_log('Directory name: %s' %i['name'])

        if season == '2013':
            if not (show_name == 'Superbowl Archives' or show_name == 'NFL Films Presents'):
                add_dir('%s - Season 2012' %show_name, '2012', 6, icon)
    elif season == '2013':
        return display_archive(show_name, '2012')


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

            if game.has_key('isLive') and not game.has_key('gameEndTimeGMT'): # sometimes isLive lies
                game_name += ' - Live'
            elif game.has_key('gameEndTimeGMT'):
                try:
                    start_time = datetime(*(time.strptime(game['gameTimeGMT'], date_time_format)[0:6]))
                    end_time = datetime(*(time.strptime(game['gameEndTimeGMT'], date_time_format)[0:6]))
                    duration = (end_time - start_time).seconds / 60
                except:
                    addon_log(format_exc())
                    if game.has_key('result'):
                        game_name += ' - Final'
            else:
                try:
                    # may want to change this to game['gameTimeGMT'] or do a setting maybe
                    game_datetime = datetime(*(time.strptime(game['date'], date_time_format)[0:6]))
                    game_date_string = game_datetime.strftime('%A, %b %d - %I:%M %p')
                    game_name += ' - ' + game_date_string + ' ET'
                    if datetime.utcnow() < datetime(*(time.strptime(game['gameTimeGMT'], date_time_format)[0:6])):
                        mode = 8
                except:
                    game_datetime = game['date'].split('T')
                    game_name += ' - ' + game_datetime[0] + ', ' + game_datetime[1].split('.')[0] + ' ET'

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


def get_params():
    p = parse_qs(sys.argv[2][1:])
    for i in p.keys():
        p[i] = p[i][0]
    return p
