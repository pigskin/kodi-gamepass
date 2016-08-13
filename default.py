"""
A Kodi addon/skin for NFL Game Pass and Game Rewind.
"""
import calendar
from datetime import datetime
import os
import sys
import time
from traceback import format_exc

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from resources.lib.pigskin import pigskin

addon = xbmcaddon.Addon()
language = addon.getLocalizedString
addon_path = xbmc.translatePath(addon.getAddonInfo('path'))
addon_profile = xbmc.translatePath(addon.getAddonInfo('profile'))
logging_prefix = '[%s-%s]' %(addon.getAddonInfo('id'), addon.getAddonInfo('version'))

if not xbmcvfs.exists(addon_profile):
    xbmcvfs.mkdir(addon_profile)

if addon.getSetting('subscription') == '0': # Game Pass
    cookie_file = os.path.join(addon_profile, 'gp_cookie_file')
    username = addon.getSetting('email')
    password = addon.getSetting('password')
    sub_name = 'gamepass'
else: # Game Rewind
    cookie_file = os.path.join(addon_profile, 'gr_cookie_file')
    username = addon.getSetting('gr_email')
    password = addon.getSetting('gr_password')
    sub_name = 'gamerewind'
if addon.getSetting('debug') == 'false':
    debug = False
else:
    debug = True

proxy_config = None
if addon.getSetting('proxy_enabled') == 'true':
    proxy_config = {
        'scheme': addon.getSetting('proxy_scheme'),
        'host': addon.getSetting('proxy_host'),
        'port': addon.getSetting('proxy_port'),
        'auth': {
            'username': addon.getSetting('proxy_username'),
            'password': addon.getSetting('proxy_password'),
        },
    }
    if proxy_config['auth']['username'] == '' and proxy_config['auth']['password'] == '':
        proxy_config['auth'] = None

gpr = pigskin(sub_name, proxy_config, cookiefile=cookie_file, debug=debug)

def addon_log(string):
    if debug:
        xbmc.log("%s: %s" %(logging_prefix, string))

class GamepassGUI(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        self.season_list = None
        self.season_items = []
        self.clicked_season = -1
        self.weeks_list = None
        self.weeks_items = []
        self.clicked_week = -1
        self.games_list = None
        self.games_items = []
        self.clicked_game = -1
        self.live_list = None
        self.live_items = []
        self.selected_season = ''
        self.selected_week = ''
        self.main_selection = None
        self.player = None
        self.list_refill = False
        self.focusId = 100
        self.seasons_and_weeks = gpr.get_seasons_and_weeks()

        xbmcgui.WindowXML.__init__(self, *args, **kwargs)
        self.action_previous_menu = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)

    def onInit(self):
        self.window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
        self.season_list = self.window.getControl(210)
        self.weeks_list = self.window.getControl(220)
        self.games_list = self.window.getControl(230)
        self.live_list = self.window.getControl(240)

        if gpr.subscription == 'gamepass':
            self.window.setProperty('gamepass', 'true')

        if self.list_refill:
            self.season_list.reset()
            self.season_list.addItems(self.season_items)
            self.weeks_list.reset()
            self.weeks_list.addItems(self.weeks_items)
            self.games_list.reset()
            self.games_list.addItems(self.games_items)
            self.live_list.reset()
            self.live_list.addItems(self.live_items)
        else:
            self.window.setProperty('NW_clicked', 'false')
            self.window.setProperty('GP_clicked', 'false')

        xbmc.executebuiltin("Dialog.Close(busydialog)")

        try:
            self.setFocus(self.window.getControl(self.focusId))
        except:
            addon_log('Focus not possible: %s' %self.focusId)

    def coloring(self, text, meaning):
        """Return the text wrapped in appropriate color markup."""
        if meaning == "disabled":
            color = "FF000000"
        elif meaning == "disabled-info":
            color = "FF111111"
        colored_text = "[COLOR=%s]%s[/COLOR]" %(color, text)
        return colored_text

    def display_seasons(self):
        """List seasons"""
        self.season_items = []
        for season in sorted(self.seasons_and_weeks.keys(), reverse=True):
            listitem = xbmcgui.ListItem(season)

            self.season_items.append(listitem)
        self.season_list.addItems(self.season_items)

    def display_nfl_network_archive(self):
        """List shows for a given season"""
        self.weeks_items = []
        shows = gpr.get_shows(self.selected_season)
        for show_name in shows:
            listitem = xbmcgui.ListItem(show_name)
            self.weeks_items.append(listitem)

        self.weeks_list.addItems(self.weeks_items)

    def display_weeks_games(self):
        """Show games for a given season/week"""
        self.games_items = []
        games = gpr.get_weeks_games(self.selected_season, self.selected_week)

        date_time_format = '%Y-%m-%dT%H:%M:%S.000'
        for game in games:
            if game['homeTeam']['id'] is None: # sometimes the first item is empty
                continue
            
            game_info = ''
            game_id = game['id']
            game_versions = []
            isPlayable = 'true'
            home_team = game['homeTeam']
            away_team = game['awayTeam']

            # Pro-bowl doesn't have a team "name" only a team city, which is the
            # team name... wtf
            if game['homeTeam']['name'] is None:
                game_name_shrt = '[B]%s[/B] at [B]%s[/B]' %(away_team['city'], home_team['city'])
                game_name_full = game_name_shrt
            else:
                game_name_shrt = '[B]%s[/B] at [B]%s[/B]' %(away_team['name'], home_team['name'])
                game_name_full = '[B]%s %s[/B] at [B]%s %s[/B]' %(away_team['city'], away_team['name'], home_team['city'], home_team['name'])

            for key, value in {'Condensed': 'condensedId', 'Full': 'programId'}.items():
                if game.has_key(value):
                    game_versions.append(key)

            if game.has_key('isLive'):
                game_versions.append('Live')

            if game.has_key('gameEndTimeGMT'):
                # Show game duration only if user wants to see it
                if addon.getSetting('hide_game_length') == 'false':
                    try:
                        start_time = datetime(*(time.strptime(game['gameTimeGMT'], date_time_format)[0:6]))
                        end_time = datetime(*(time.strptime(game['gameEndTimeGMT'], date_time_format)[0:6]))
                        game_info = 'Final [CR] Duration: %s' %time.strftime('%H:%M:%S', time.gmtime((end_time - start_time).seconds))
                    except:
                        addon_log(format_exc())
                        if game.has_key('result'):
                            game_info = 'Final'
                else:
                    game_info = 'Final'
            else:
                if game.has_key('isLive'):
                    game_info = 'Live'

                try:
                    if addon.getSetting('local_tz') == '1': # Localize and use 12-hour clock
                        game_gmt = time.strptime(game['gameTimeGMT'], date_time_format)
                        secs = calendar.timegm(game_gmt)
                        game_local = time.localtime(secs)
                        game_info = time.strftime('%A, %b %d - %I:%M %p', game_local)
                    elif addon.getSetting('local_tz') == '2': # Localize and use 24-hour clock
                        game_gmt = time.strptime(game['gameTimeGMT'], date_time_format)
                        secs = calendar.timegm(game_gmt)
                        game_local = time.localtime(secs)
                        game_info = time.strftime('%A, %b %d - %H:%M', game_local)
                    else: # don't localize
                        game_datetime = datetime(*(time.strptime(game['date'], date_time_format)[0:6]))
                        game_info = game_datetime.strftime('%A, %b %d - %I:%M %p')
                    if datetime.utcnow() < datetime(*(time.strptime(game['gameTimeGMT'], date_time_format)[0:6])):
                        isPlayable = 'false'
                        game_name_full = self.coloring(game_name_full, "disabled")
                        game_name_shrt = self.coloring(game_name_shrt, "disabled")
                        game_info = self.coloring(game_info, "disabled-info")
                except:
                    game_datetime = game['date'].split('T')
                    game_info = game_datetime[0] + '[CR]' + game_datetime[1].split('.')[0] + ' ET'

            listitem = xbmcgui.ListItem(game_name_shrt, game_name_full)
            listitem.setProperty('away_thumb', 'http://i.nflcdn.com/static/site/6.11/img/logos/teams-matte-80x53/%s.png' %away_team['id'])
            listitem.setProperty('home_thumb', 'http://i.nflcdn.com/static/site/6.11/img/logos/teams-matte-80x53/%s.png' %home_team['id'])
            listitem.setProperty('game_info', game_info)
            listitem.setProperty('is_game', 'true')
            listitem.setProperty('is_show', 'false')
            listitem.setProperty('isPlayable', isPlayable)
            listitem.setProperty('game_id', game_id)
            listitem.setProperty('game_date', game['date'].split('T')[0])
            listitem.setProperty('game_versions', ' '.join(game_versions))
            self.games_items.append(listitem)

        self.games_list.addItems(self.games_items)

    def display_seasons_weeks(self):
        """List weeks for a given season"""
        weeks = self.seasons_and_weeks[self.selected_season]

        for week_code, week in sorted(weeks.iteritems()):
            future = 'false'
            try:
                # convert EST to GMT by adding 6 hours
                week_date = week['@start'] + ' 06:00'
                # avoid super annoying bug http://forum.kodi.tv/showthread.php?tid=112916
                week_datetime = datetime(*(time.strptime(week_date, '%Y%m%d %H:%M')[0:6]))
                now_datetime = datetime.utcnow()

                if week_datetime > now_datetime:
                    future = 'true'
            except KeyError: # some old seasons don't provide week dates
                pass

            listitem = xbmcgui.ListItem(week['@label'].title())
            listitem.setProperty('week_code', week_code)
            listitem.setProperty('future', future)
            self.weeks_items.append(listitem)
        self.weeks_list.addItems(self.weeks_items)

    def display_shows_episodes(self, show_name, season):
        """Show episodes for a given season/show"""
        self.games_items = []
        items = gpr.get_shows_episodes(show_name, season)

        image_path = 'http://smb.cdn.neulion.com/u/nfl/nfl/thumbs/'
        for i in items:
            try:
                listitem = xbmcgui.ListItem('[B]%s[/B]' %show_name)
                listitem.setProperty('game_info', i['name'])
                listitem.setProperty('away_thumb', image_path + i['image'])
                listitem.setProperty('url', i['publishPoint'])
                listitem.setProperty('id', i['id'])
                listitem.setProperty('type', i['type'])
                listitem.setProperty('is_game', 'false')
                listitem.setProperty('is_show', 'true')
                listitem.setProperty('isPlayable', 'true')
                self.games_items.append(listitem)
            except:
                addon_log('Exception adding archive directory: %s' %format_exc())
                addon_log('Directory name: %s' %i['name'])
        self.games_list.addItems(self.games_items)

    def playUrl(self, url):
        xbmc.executebuiltin("Dialog.Close(busydialog)")
        self.list_refill = True
        xbmc.Player().play(url)

    def init(self, level):
        if level == 'season':
            self.weeks_items = []
            self.weeks_list.reset()
            self.games_list.reset()
            self.clicked_week = -1
            self.clicked_game = -1

            if self.clicked_season > -1: # unset previously selected season
                self.season_list.getListItem(self.clicked_season).setProperty('clicked', 'false')

            self.season_list.getSelectedItem().setProperty('clicked', 'true')
            self.clicked_season = self.season_list.getSelectedPosition()
        elif level == 'week/show':
            self.games_list.reset()
            self.clicked_game = -1

            if self.clicked_week > -1: # unset previously selected week/show
                self.weeks_list.getListItem(self.clicked_week).setProperty('clicked', 'false')

            self.weeks_list.getSelectedItem().setProperty('clicked', 'true')
            self.clicked_week = self.weeks_list.getSelectedPosition()
        elif level == 'game/episode':
            if self.clicked_game > -1: # unset previously selected game/episode
                self.games_list.getListItem(self.clicked_game).setProperty('clicked', 'false')

            self.games_list.getSelectedItem().setProperty('clicked', 'true')
            self.clicked_game = self.games_list.getSelectedPosition()

    def ask_bitrate(self, bitrates):
        """Presents a dialog for user to select from a list of bitrates.
        Returns the value of the selected bitrate.
        """
        options = []
        for bitrate in bitrates:
            options.append(bitrate + ' Kbps')
        dialog = xbmcgui.Dialog()
        xbmc.executebuiltin("Dialog.Close(busydialog)")
        ret = dialog.select(language(30003), options)
        return bitrates[ret]

    def select_bitrate(self, manifest_bitrates=None):
        """Returns a bitrate, while honoring the user's /preference/."""
        bitrate_setting = int(addon.getSetting('preferred_bitrate'))
        bitrate_values = ['4500', '3000', '2400', '1600', '1200', '800', '400']
        if bitrate_setting == 0:
            preferred_bitrate = 'highest'
        elif bitrate_setting < 7: # specific bitrate
            preferred_bitrate = bitrate_values[bitrate_setting -1]
        else:
            preferred_bitrate = 'ask'

        if manifest_bitrates:
            manifest_bitrates.sort(key=int, reverse=True)
            if preferred_bitrate == 'highest':
                return manifest_bitrates[0]
            elif preferred_bitrate in manifest_bitrates:
                return preferred_bitrate
            else:
                return self.ask_bitrate(manifest_bitrates)
        else:
            if preferred_bitrate == 'highest':
                return bitrate_values[0]
            elif preferred_bitrate != 'ask':
                return preferred_bitrate
            else:
                return self.ask_bitrate(bitrate_values)

    def select_version(self, game_versions):
        """Returns a game version, while honoring the user's /preference/.
        Note: the full version is always be available, but not always the
        condensed.
        """
        preferred_version = int(addon.getSetting('preferred_game_version'))

        # user wants to be asked to select version
        if preferred_version == 2:
            versions = [language(30014)]
            if 'Condensed' in game_versions:
                versions.append(language(30015))
            if 'Coach' in game_versions:
                versions.append(language(30032))
            dialog = xbmcgui.Dialog()
            xbmc.executebuiltin("Dialog.Close(busydialog)")
            preferred_version = dialog.select(language(30016), versions)

        if preferred_version == 1 and 'Condensed' in game_versions:
            game_version = 'condensed'
        elif preferred_version == 2 and 'Coach' in game_versions:
            game_version = 'coach'
        else:
            game_version = 'archive'

        return game_version

    def onFocus(self, controlId):
        #save currently focused list
        if controlId in [210, 220, 230, 240]:
            self.focusId = controlId

    def onClick(self, controlId):
        try:
            xbmc.executebuiltin("ActivateWindow(busydialog)")
            if controlId in [110, 120, 130]:
                self.games_list.reset()
                self.weeks_list.reset()
                self.season_list.reset()
                self.live_list.reset()
                self.games_items = []
                self.weeks_items = []
                self.live_items = []
                self.clicked_game = -1
                self.clicked_week = -1
                self.clicked_season = -1

                if controlId in [110, 120]:
                    self.main_selection = 'GamePass/Rewind'
                    self.window.setProperty('NW_clicked', 'false')
                    self.window.setProperty('GP_clicked', 'true')

                    #display games of current week for usability purposes
                    cur_s_w = gpr.get_current_season_and_week()
                    self.selected_season = cur_s_w.keys()[0]
                    self.selected_week = cur_s_w.values()[0]

                    self.display_seasons_weeks()
                    self.display_weeks_games()
                elif controlId == 130:
                    self.main_selection = 'NFL Network'
                    self.window.setProperty('NW_clicked', 'true')
                    self.window.setProperty('GP_clicked', 'false')
                    if gpr.subscription == 'gamepass':
                        listitem = xbmcgui.ListItem('NFL Network - Live', 'NFL Network - Live')
                        self.live_items.append(listitem)
                        if gpr.redzone_on_air():
                            listitem = xbmcgui.ListItem('NFL RedZone - Live', 'NFL RedZone - Live')
                            self.live_items.append(listitem)

                    self.live_list.addItems(self.live_items)

                self.display_seasons()
                xbmc.executebuiltin("Dialog.Close(busydialog)")
                return

            if self.main_selection == 'GamePass/Rewind':
                if controlId == 210: # season is clicked
                    self.init('season')
                    self.selected_season = self.season_list.getSelectedItem().getLabel()

                    self.display_seasons_weeks()
                elif controlId == 220: # week is clicked
                    self.init('week/show')
                    self.selected_week = self.weeks_list.getSelectedItem().getProperty('week_code')

                    self.display_weeks_games()
                elif controlId == 230: # game is clicked
                    selectedGame = self.games_list.getSelectedItem()
                    if selectedGame.getProperty('isPlayable') == 'true':
                        self.init('game/episode')
                        game_id = selectedGame.getProperty('game_id')
                        game_versions = selectedGame.getProperty('game_versions')

                        if 'Live' in game_versions:
                            if 'Final' in selectedGame.getProperty('game_info'):
                                game_version = self.select_version(game_versions)
                                if game_version == 'archive':
                                    game_version = 'dvr'
                            else:
                                game_version = 'live'
                        else:
                            # Check for coaches film availability
                            if gpr.check_for_coachestape(game_id, self.selected_season):
                                game_versions = game_versions + ' Coach'

                            game_version = self.select_version(game_versions)

                        if game_version == 'coach':
                            xbmc.executebuiltin("ActivateWindow(busydialog)")
                            coachesItems = []
                            game_date = selectedGame.getProperty('game_date').replace('-', '/')
                            self.playBackStop = False

                            play_stream = gpr.get_coaches_url(game_id, game_date, 'dummy')
                            plays = gpr.get_coaches_playIDs(game_id, self.selected_season)
                            for playID in sorted(plays, key=int):
                                cf_url = str(play_stream).replace('dummy', playID)
                                item = xbmcgui.ListItem(plays[playID])
                                item.setProperty('url', cf_url)
                                coachesItems.append(item)

                            self.list_refill = True
                            coachGui = CoachesFilmGUI('script-gamepass-coach.xml', addon_path, plays=coachesItems)
                            coachGui.doModal()
                            del coachGui
                        else:
                            game_streams = gpr.get_publishpoint_streams(game_id, 'game', game_version)
                            bitrate = self.select_bitrate(game_streams.keys())
                            game_url = game_streams[bitrate]
                            self.playUrl(game_url)

            elif self.main_selection == 'NFL Network':
                if controlId == 210: # season is clicked
                    self.init('season')
                    self.selected_season = self.season_list.getSelectedItem().getLabel()

                    self.display_nfl_network_archive()
                elif controlId == 220: # show is clicked
                    self.init('week/show')
                    show_name = self.weeks_list.getSelectedItem().getLabel()

                    self.display_shows_episodes(show_name, self.selected_season)
                elif controlId == 230: # episode is clicked
                    self.init('game/episode')
                    if self.weeks_list.getSelectedItem().getLabel() in ('Super Bowl Archives', 'Top 100 Players', 'Hard Knocks'):
                        video_id = self.games_list.getSelectedItem().getProperty('id')
                        video_streams = gpr.get_publishpoint_streams(video_id, 'video')
                        addon_log('Video-Streams: %s' %video_streams)
                        bitrate = self.select_bitrate(video_streams.keys())
                        video_url = video_streams[bitrate]
                        self.playUrl(video_url)
                    else:
                        url = self.games_list.getSelectedItem().getProperty('url')
                        vtype = self.games_list.getSelectedItem().getProperty('type')
                        episode_manifest = gpr.get_stream_manifest(vpath=url, vtype=vtype)
                        bitrate = self.select_bitrate(episode_manifest.keys())
                        episode_url = episode_manifest[bitrate]['full_url']
                        self.playUrl(episode_url)
                elif controlId == 240: # Live content (though not games)
                    show_name = self.live_list.getSelectedItem().getLabel()
                    if show_name == 'NFL RedZone - Live':
                        rz_live_streams = gpr.get_publishpoint_streams('redzone')
                        bitrate = self.select_bitrate(rz_live_streams.keys())
                        rz_live_url = rz_live_streams[bitrate]
                        self.playUrl(rz_live_url)
                    elif show_name == 'NFL Network - Live':
                        nw_live_streams = gpr.get_publishpoint_streams('nfl_network')
                        bitrate = self.select_bitrate(nw_live_streams.keys())
                        nw_live_url = nw_live_streams[bitrate]
                        self.playUrl(nw_live_url)
            xbmc.executebuiltin("Dialog.Close(busydialog)")
        except Exception: # catch anything that might fail
            xbmc.executebuiltin("Dialog.Close(busydialog)")
            addon_log(format_exc())
            dialog = xbmcgui.Dialog()
            dialog.ok(language(30021),
                      language(30024))

class CoachesFilmGUI(xbmcgui.WindowXML):
    def __init__(self, xmlFilename, scriptPath, plays, defaultSkin = "Default", defaultRes = "720p"):
        self.playsList = None
        self.playsItems = plays

        xbmcgui.WindowXML.__init__(self, xmlFilename, scriptPath, defaultSkin, defaultRes)
        self.action_previous_menu = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)

    def onInit(self):
        self.window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
        if addon.getSetting('coach_lite') == 'true':
            self.window.setProperty('coach_lite', 'true')

        self.playsList = self.window.getControl(110)
        self.window.getControl(99).setLabel(language(30032))
        self.playsList.addItems(self.playsItems)
        self.setFocus(self.playsList)
        url = self.playsList.getListItem(0).getProperty('url')
        xbmc.executebuiltin("Dialog.Close(busydialog)")
        xbmc.executebuiltin('PlayMedia(%s,False,1)' %url)

    def onClick(self, controlId):
        if controlId == 110:
            url = self.playsList.getSelectedItem().getProperty('url')
            xbmc.executebuiltin('PlayMedia(%s,False,1)' %url)

if __name__ == "__main__":
    addon_log('script starting')
    xbmc.executebuiltin("Dialog.Close(busydialog)")

    try:
        gpr.login(username, password)
    except gpr.LoginFailure as error:
        dialog = xbmcgui.Dialog()
        if error.value == 'Game Rewind Blackout':
            addon_log('Rewind is in blackout.')
            dialog.ok(language(30021),
                      language(30022))
        else:
            addon_log('login failed')
            dialog.ok(language(30021),
                      language(30023))
        sys.exit(0)
    except:
        addon_log(format_exc())
        dialog = xbmcgui.Dialog()
        dialog.ok('Epic Failure',
                  language(30024))
        sys.exit(0)

    gui = GamepassGUI('script-gamepass.xml', addon_path)
    gui.doModal()
    del gui

addon_log('script finished')
