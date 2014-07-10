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
import xml.etree.ElementTree as ET
import random
import md5
from uuid import getnode as get_mac
from datetime import datetime, timedelta
from traceback import format_exc
from urlparse import urlparse, parse_qs

from resources.lib.game_xbmc import *
    
class myPlayer(xbmc.Player):

   def __init__(self, parent, *args, **kwargs):
      xbmc.Player.__init__(self)
      self.dawindow = parent

   def onPlayBackStarted(self):
      self.dawindow.close()

   def onPlayBackStopped(self):
      self.onPlayBackEnded()

   def onPlayBackEnded(self):
      self.dawindow.doModal()

class GamepassGUI(xbmcgui.WindowXMLDialog):
    season_list = ''
    weeks_list = ''
    games_list = ''
    selectedSeason = ''
    selectedWeek = ''
    main_selection = ''


    def __init__( self, *args, **kwargs ):
        xbmcgui.WindowXMLDialog.__init__(self)
        self.action_previous_menu = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)

    def onInit(self):
        self.window = xbmcgui.Window(xbmcgui.getCurrentWindowDialogId())
        self.season_list = self.window.getControl(210)
        self.weeks_list = self.window.getControl(220)
        self.games_list = self.window.getControl(230)
        self.setFocus(self.window.getControl(100))

    def display_seasons(self):
        seasons = get_seasons()
        for season in seasons:
           listitem = xbmcgui.ListItem(season)
           self.season_list.addItem(listitem)

    def display_nfl_network_archive(self):
        if subscription == '0': # gamepass
           listitem = xbmcgui.ListItem('NFL Network - Live', 'NFL Network - Live')
           self.weeks_list.addItem(listitem)
        for i in show_archives.keys():
           listitem = xbmcgui.ListItem(i)
           self.weeks_list.addItem(listitem)

    def display_weeks_games(self):
        self.games_list.reset()
        games = get_weeks_games(self.selected_season, self.selected_week)
	addon_log('Game: %s' %games)
	# super bowl week has only one game, which thus isn't put into a list
	if isinstance(games, dict):
	   games_tmp = [games]
	   games = games_tmp

	if games:
	   date_time_format = '%Y-%m-%dT%H:%M:%S.000'
	   for game in games:
	      home_team = game['homeTeam']
	      # sometimes the first item is empty
	      if home_team['name'] is None:
		 continue

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

	      away_team = game['awayTeam']
	      game_name_shrt = '[B]%s[/B] at [B]%s[/B]' %(away_team['id'], home_team['id'])
              game_name_full = '[B]%s %s[/B] at [B]%s %s[/B]' %(away_team['city'], away_team['name'], home_team['city'], home_team['name'])
	      game_datetime = datetime(*(time.strptime(game['date'], date_time_format)[0:6]))
              game_date_string = game_datetime.strftime('%A, %b %d [CR] %I:%M %p')
              listitem = xbmcgui.ListItem(game_name_shrt,game_name_full)
              listitem.setProperty('away_thumb', 'http://i.nflcdn.com/static/site/5.31/img/logos/teams-matte-80x53/%s.png' %away_team['id'])
	      listitem.setProperty('home_thumb', 'http://i.nflcdn.com/static/site/5.31/img/logos/teams-matte-80x53/%s.png' %home_team['id'])
              listitem.setProperty('game_info', game_date_string)
              listitem.setProperty('is_game', 'true')
              listitem.setProperty('is_show', 'false')
	      params = {'name': game_name_full, 'url': game_ids}
	      url = '%s?%s' %(sys.argv[0], urllib.urlencode(params))
	      listitem.setProperty('url', url)
	      self.games_list.addItem(listitem)

    def display_archive(self, show_name, season, cid):
       cur_season = get_current_season()
    
       #No valid CID passed
       if cid > 0:
          items = parse_archive(cid, show_name)
       else:
          items = ''
       
       image_path = 'http://smb.cdn.neulion.com/u/nfl/nfl/thumbs/'
       if items:
          for i in items:
             try:
                listitem = xbmcgui.ListItem('[B]%s[/B]' %show_name)
                listitem.setProperty('game_info', i['name'])
                listitem.setProperty('away_thumb', image_path + i['image'])
                listitem.setProperty('url', i['publishPoint'])
                listitem.setProperty('is_game', 'false')
                listitem.setProperty('is_show', 'true') 
                self.games_list.addItem(listitem)
             except:
                addon_log('Exception adding archive directory: %s' %format_exc())
                addon_log('Directory name: %s' %i['name'])

    def onClick(self, controlId):
        #if Gamepass is selected
        if controlId == 110:
           self.main_selection = 'GP'
           self.games_list.reset()
           self.weeks_list.reset()
           self.season_list.reset()
           self.display_seasons()
        
        #if Nfl Network is selected
        if controlId == 130:
           self.main_selection = 'NW'
           self.games_list.reset()
           self.weeks_list.reset()
           self.season_list.reset()
           self.display_seasons()

        #if a season is selected
        if controlId == 210:
           self.weeks_list.reset()
           self.games_list.reset()              
           self.selected_season = self.season_list.getSelectedItem().getLabel()
           if self.main_selection == 'GP':
              weeks = get_seasons_weeks(self.selected_season)
              for week_code, week_name in sorted(weeks.iteritems()):
                 listitem = xbmcgui.ListItem(week_name)
                 listitem.setProperty('week_code', week_code)
                 self.weeks_list.addItem(listitem)
           elif self.main_selection == 'NW':
               self.display_nfl_network_archive()

        #if a week/show is selected
        if controlId == 220:
            self.games_list.reset()
            if self.main_selection == 'GP':
               self.selected_week = self.weeks_list.getSelectedItem().getProperty('week_code')
               self.display_weeks_games()
            elif self.main_selection == 'NW' and self.weeks_list.getSelectedItem().getLabel() == 'NFL Network - Live':
               resolvedItem = set_resolved_url(self.weeks_list.getSelectedItem().getLabel(), 'nfl_network_url') 
               player = myPlayer(parent=window)
               player.play(resolvedItem.getLabel())

               while player.isPlaying():
                  xbmc.sleep(1000)  
            elif self.main_selection == 'NW':
               show_name = self.weeks_list.getSelectedItem().getLabel()
               self.display_archive(show_name, self.selected_season, show_archives[show_name][self.selected_season])

        #if a game/show is selected
        if controlId == 230:
            if self.main_selection == 'GP':
               selectedGame = self.games_list.getSelectedItem() 
               url = selectedGame.getProperty('url')
               params = parse_qs(urlparse(url).query)
               for i in params.keys():
                  params[i] = params[i][0]
               url = params['url']
               resolvedItem = set_resolved_url(selectedGame.getLabel2(), url)
               
               player = myPlayer(parent=window)
               player.play(resolvedItem.getLabel())

               while player.isPlaying():
                  xbmc.sleep(1000)
            
            if self.main_selection == 'NW':
               url = self.games_list.getSelectedItem().getProperty('url')
               resolvedItem = resolve_show_archive_url(url)
               player = myPlayer(parent=window)
               player.play(resolvedItem.getLabel())

               while player.isPlaying():
                  xbmc.sleep(1000)
            

if not xbmcvfs.exists(addon_profile):
    xbmcvfs.mkdir(addon_profile)
    
if (__name__ == "__main__"):
    addon_log('script starting')
    start_addon()
    window = GamepassGUI('script-gamepass.xml', addon_path)
    window.doModal()

addon_log('script finished')
