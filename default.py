# -*- coding: utf-8 -*-
"""
A Kodi addon/skin for NFL Game Pass
"""
import calendar
import datetime
from dateutil import tz
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
ADDON_PATH = xbmc.translatePath(addon.getAddonInfo('path'))
ADDON_PROFILE = xbmc.translatePath(addon.getAddonInfo('profile'))
LOGGING_PREFIX = '[%s-%s]' % (addon.getAddonInfo('id'), addon.getAddonInfo('version'))

if not xbmcvfs.exists(ADDON_PROFILE):
    xbmcvfs.mkdir(ADDON_PROFILE)

username = addon.getSetting('email')
password = addon.getSetting('password')

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
    if addon.getSetting('proxy_auth') == 'false':
        proxy_config['auth'] = None

gp = pigskin(proxy_config, debug=True)


def addon_log(string):
    msg = '%s: %s' % (LOGGING_PREFIX, string)
    xbmc.log(msg=msg, level=xbmc.LOGDEBUG)


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
        self.seasons_and_weeks = gp.get_seasons_and_weeks()

        xbmcgui.WindowXML.__init__(self, *args, **kwargs)
        self.action_previous_menu = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)

    def onInit(self):  # pylint: disable=invalid-name
        self.window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
        self.season_list = self.window.getControl(210)
        self.weeks_list = self.window.getControl(220)
        self.games_list = self.window.getControl(230)
        self.live_list = self.window.getControl(240)

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
            addon_log('Focus not possible: %s' % self.focusId)

    def coloring(self, text, meaning):
        """Return the text wrapped in appropriate color markup."""
        if meaning == "disabled":
            color = "FF000000"
        elif meaning == "disabled-info":
            color = "FF111111"
        colored_text = "[COLOR=%s]%s[/COLOR]" % (color, text)
        return colored_text

    def display_seasons(self):
        """List seasons"""
        self.season_items = []
        for season in sorted(self.seasons_and_weeks.keys(), reverse=True):
            listitem = xbmcgui.ListItem(season)
            self.season_items.append(listitem)

        self.season_list.addItems(self.season_items)

    def display_nfln_seasons(self):
        """List seasons"""
        self.season_items = []
        # sort so that years are first (descending) followed by text
        for season in sorted(gp.nflnSeasons, key=lambda x: (x[0].isdigit(), x), reverse=True):
            listitem = xbmcgui.ListItem(season)
            self.season_items.append(listitem)

        self.season_list.addItems(self.season_items)

    def display_nfl_network_archive(self):
        """List shows for a given season"""
        self.weeks_items = []
        shows = gp.get_shows(self.selected_season)
        for show_name in shows:
            listitem = xbmcgui.ListItem(show_name)
            self.weeks_items.append(listitem)

        self.weeks_list.addItems(self.weeks_items)

    def display_weeks_games(self):
        """Show games for a given season/week"""
        self.games_items = []

        date_time_format = '%Y-%m-%dT%H:%M:%S.%fZ'
        team_name = addon.getSetting('preferred_team')
        if addon.getSetting('team_view') == 'true' and self.selected_week == '444':
            if (31002+int(team_name))== 31034:
                options = []
                for i in range (31002, 31033):
                    options.append(language(i))
                dialog = xbmcgui.Dialog()
                xbmc.executebuiltin("Dialog.Close(busydialog)")
                ret = dialog.select(language(31001), options)

                if ret > -1:
                    print 'Team ist : %s' % language(31002+ret)
                    games = gp.get_team_games(self.selected_season, language(31002+ret))
                else:
                    return None
            else:
                games = gp.get_team_games(self.selected_season, language(31002+int(team_name)))
            if games:
                slug = 'videos'+self.selected_season
                #for game in games['modules']['weekCompletedGames']['content']:
                for game in games['modules'][slug]['content']:
                    if game['gameId']:
                        game_id = game['visitorNickName'].lower() + '-' +  game['homeNickName'].lower() + '-' + str(game['gameId'])
                        home_team = game['homeTeamAbbr']
                        away_team = game['visitorTeamAbbr']
                        #game_info = ''
                        game_name_shrt = '[B]%s[/B] at [B]%s[/B]' % (game['visitorNickName'], game['homeNickName'])
                        game_name_full = '[B]%s %s[/B] at [B]%s %s[/B]' % (game['visitorCityState'], game['visitorNickName'], game['homeCityState'], game['homeNickName'])
                        listitem = xbmcgui.ListItem(game_name_shrt, game_name_full)
                        listitem.setProperty('is_game', 'true')
                        listitem.setProperty('is_show', 'false')
                        isPlayable = 'true'
                        if game['videoStatus'] == 'SCHEDULED':
                            isPlayable = 'false'
                        listitem.setProperty('isPlayable', isPlayable)
                        listitem.setProperty('game_id', game_id)
                        listitem.setProperty('away_thumb', 'http://i.nflcdn.com/static/site/7.4/img/logos/teams-matte-144x96/%s.png' % away_team)
                        listitem.setProperty('home_thumb', 'http://i.nflcdn.com/static/site/7.4/img/logos/teams-matte-144x96/%s.png' % home_team)
                        if game['phase'] == 'FINAL' or game['phase'] == 'FINAL_OVERTIME':
                        # Show game duration only if user wants to see it
                            if addon.getSetting('hide_game_length') == 'false':
                                try:
                                    game_info = 'Final [CR] Duration: %s' % str(datetime.timedelta(seconds=int(float(game['video']['videoDuration']))))
                                except:
                                    addon_log(format_exc())
                                    if 'result' in game:
                                        game_info = game['phase']
                            else:
                                game_info = 'FINAL'
                            listitem.setProperty('game_info', game_info)
                        else:
                            if 'isLive' in game:
                                game_info = '» Live «'
                        
                            try:
                                if addon.getSetting('local_tz') == '0':  # don't localize
                                    game_datetime = datetime.datetime(*(time.strptime(game['gameDateTimeUtc'], date_time_format)[0:6]))
                                    game_info = game_datetime.strftime('%A, %b %d - %I:%M %p')
                                else:
                                    from_zone = tz.tzutc()
                                    to_zone = tz.tzlocal()
                                    game_datetime = datetime.datetime(*(time.strptime(game['gameDateTimeUtc'], date_time_format)[0:6]))
                                    game_datetime = game_datetime.replace(tzinfo=from_zone)
                                    local_time = game_datetime.astimezone(to_zone)
                                    if addon.getSetting('local_tz') == '1':  # localize and use 12-hour clock
                                        game_info = local_time.strftime('%A, %b %d - %I:%M %p')
                                    else:  # localize and use 24-hour clock
                                        game_info = local_time.strftime('%A, %b %d - %H:%M')
                            except:  # all else fails, just use their raw date value
                                game_datetime = game['gameDateTimeUtc'].split('T')
                                game_info = game_datetime[0] + '[CR]' + game_datetime[1].split('.')[0] + ' ET'
                            listitem.setProperty('game_info', game_info)
                        self.games_items.append(listitem)
        else:
            games = gp.get_weeks_games(self.selected_season, self.selected_week)
            if games:
                for weekSet in games['modules']:
                    for game in games['modules'][weekSet]['content']:
                        game_id = game['visitorNickName'].lower() + '-' +  game['homeNickName'].lower() + '-' + str(game['gameId'])
                        home_team = game['homeTeamAbbr']
                        away_team = game['visitorTeamAbbr']
                        #game_info = ''
                        game_name_shrt = '[B]%s[/B] at [B]%s[/B]' % (game['visitorNickName'], game['homeNickName'])
                        game_name_full = '[B]%s %s[/B] at [B]%s %s[/B]' % (game['visitorCityState'], game['visitorNickName'], game['homeCityState'], game['homeNickName'])
                        listitem = xbmcgui.ListItem(game_name_shrt, game_name_full)

                        listitem.setProperty('is_game', 'true')
                        listitem.setProperty('is_show', 'false')

                        if game['phase'] == 'FINAL' or game['phase'] == 'FINAL_OVERTIME':
                            # show game duration only if user wants to see it
                            if addon.getSetting('hide_game_length') == 'false':
                                try:
                                    game_info = 'Final [CR] Duration: %s' % str(datetime.timedelta(seconds=int(float(game['video']['videoDuration']))))
                                except:
                                    addon_log(format_exc())
                                    if 'result' in game:
                                        game_info = game['phase']
                            else:
                                game_info = 'FINAL'
                            listitem.setProperty('game_info', game_info)
                        else:
                            if 'isLive' in game:
                                game_info = '» Live «'

                            try:
                                if addon.getSetting('local_tz') == '0':  # don't localize
                                    game_datetime = datetime.datetime(*(time.strptime(game['gameDateTimeUtc'], date_time_format)[0:6]))
                                    game_info = game_datetime.strftime('%A, %b %d - %I:%M %p')
                                else:
                                    from_zone = tz.tzutc()
                                    to_zone = tz.tzlocal()
                                    game_datetime = datetime.datetime(*(time.strptime(game['gameDateTimeUtc'], date_time_format)[0:6]))
                                    game_datetime = game_datetime.replace(tzinfo=from_zone)
                                    local_time = game_datetime.astimezone(to_zone)
                                    if addon.getSetting('local_tz') == '1':  # localize and use 12-hour clock
                                        game_info = local_time.strftime('%A, %b %d - %I:%M %p')
                                    else:  # localize and use 24-hour clock
                                        game_info = local_time.strftime('%A, %b %d - %H:%M')
                            except:  # all else fails, just use their raw date value
                                game_datetime = game['gameDateTimeUtc'].split('T')
                                game_info = game_datetime[0] + '[CR]' + game_datetime[1].split('.')[0] + ' ET'
                            listitem.setProperty('game_info', game_info)

                        if weekSet == 'weekScheduledGames':
                            isPlayable = 'false'
                            isBlackedOut = 'false'
                        else:
                            if weekSet == 'weekLiveGames':
                                if game['video']['videoId']:
                                    video_id = str(game['video']['videoId'])
                                    isPlayable = 'true'
                                    isBlackedOut = 'false'
                                    listitem.setProperty('video_id', video_id)
                                    listitem.setProperty('game_versions', 'Live')
                            else:
                                if weekSet == 'weekCompletedGames':
                                    if game['video']['videoId']:
                                        video_id = str(game['video']['videoId'])
                                        isPlayable = 'true'
                                        isBlackedOut = 'false'
                                        listitem.setProperty('video_id', video_id)

                        listitem.setProperty('isPlayable', isPlayable)
                        listitem.setProperty('isBlackedOut', isBlackedOut)
                        listitem.setProperty('game_id', game_id)
                        listitem.setProperty('away_thumb', 'http://i.nflcdn.com/static/site/7.4/img/logos/teams-matte-144x96/%s.png' % away_team)
                        listitem.setProperty('home_thumb', 'http://i.nflcdn.com/static/site/7.4/img/logos/teams-matte-144x96/%s.png' % home_team)
                        #listitem.setProperty('game_date', game['date'].split('T')[0])
                        #listitem.setProperty('game_versions', ' '.join(game_versions))
                        self.games_items.append(listitem)
        self.games_list.addItems(self.games_items)

    def display_seasons_weeks(self):
        """List weeks for a given season"""
        weeks = self.seasons_and_weeks[self.selected_season]
        if addon.getSetting('team_view') == 'true':
            listitem = xbmcgui.ListItem('Teams')
            listitem.setProperty('week_code', '444')
            listitem.setProperty('future', 'false')
            self.weeks_items.append(listitem)
        for week_code, week in sorted(weeks.iteritems()):
            future = 'false'
            #try:
                # convert EST to GMT by adding 6 hours
                #week_date = week['@start'] + ' 06:00'
                # avoid super annoying bug http://forum.kodi.tv/showthread.php?tid=112916
                #week_datetime = datetime(*(time.strptime(week_date, '%Y%m%d %H:%M')[0:6]))
                #now_datetime = datetime.utcnow()

                #if week_datetime > now_datetime:
                #    future = 'true'
            #except KeyError:  # some old seasons don't provide week dates
            #    pass
            listitem = xbmcgui.ListItem(week.title())
            listitem.setProperty('week_code', week_code)
            listitem.setProperty('future', future)
            self.weeks_items.append(listitem)
        self.weeks_list.addItems(self.weeks_items)

    def display_shows_episodes(self, show_name, season):
        """Show episodes for a given season/show"""
        self.games_items = []
        items = gp.get_shows_episodes(show_name, season)

        for i in items['modules']['archive']['content']:
            try:
                listitem = xbmcgui.ListItem('[B]%s[/B]' % show_name)
                listitem.setProperty('game_info', i['title'])
                #listitem.setProperty('away_thumb', gp.image_url + i['image'])
                #listitem.setProperty('url', i['publishPoint'])
                listitem.setProperty('id', i['videoId'])
                listitem.setProperty('is_game', 'false')
                listitem.setProperty('is_show', 'true')
                listitem.setProperty('isPlayable', 'true')
                self.games_items.append(listitem)
            except:
                addon_log('Exception adding archive directory: %s' % format_exc())
                addon_log('Directory name: %s' % i['title'])
        self.games_list.addItems(self.games_items)

    def play_url(self, url):
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

            if self.clicked_season > -1:  # unset previously selected season
                self.season_list.getListItem(self.clicked_season).setProperty('clicked', 'false')

            self.season_list.getSelectedItem().setProperty('clicked', 'true')
            self.clicked_season = self.season_list.getSelectedPosition()
        elif level == 'week/show':
            self.games_list.reset()
            self.clicked_game = -1

            if self.clicked_week > -1:  # unset previously selected week/show
                self.weeks_list.getListItem(self.clicked_week).setProperty('clicked', 'false')

            self.weeks_list.getSelectedItem().setProperty('clicked', 'true')
            self.clicked_week = self.weeks_list.getSelectedPosition()
        elif level == 'game/episode':
            if self.clicked_game > -1:  # unset previously selected game/episode
                self.games_list.getListItem(self.clicked_game).setProperty('clicked', 'false')

            self.games_list.getSelectedItem().setProperty('clicked', 'true')
            self.clicked_game = self.games_list.getSelectedPosition()

    def ask_bitrate(self, bitrates):
        """Presents a dialog for user to select from a list of bitrates.
        Returns the value of the selected bitrate.
        """
        options = []
        for bitrate in bitrates:
            options.append(str(bitrate) + ' Kbps')
        dialog = xbmcgui.Dialog()
        xbmc.executebuiltin("Dialog.Close(busydialog)")
        ret = dialog.select(language(30003), options)
        if ret > -1:
            return bitrates[ret]
        else:
            return None

    def select_bitrate(self, manifest_bitrates=None):
        """Returns a bitrate, while honoring the user's /preference/."""
        bitrate_setting = int(addon.getSetting('preferred_bitrate'))
        bitrate_values = ['3671533', '2394274', '1577316', '1117771', '760027', '555799', '402512']

        highest = False
        preferred_bitrate = None
        if bitrate_setting == 0:  # 0 === "highest"
            highest = True
        elif 0 < bitrate_setting and bitrate_setting < 8:  # a specific bitrate. '8' === "ask"
            preferred_bitrate = bitrate_values[bitrate_setting - 1]

        if manifest_bitrates:
            manifest_bitrates.sort(key=int, reverse=True)
            if highest:
                return manifest_bitrates[0]
            elif preferred_bitrate and preferred_bitrate in manifest_bitrates:
                return preferred_bitrate
            else:  # ask user
                return self.ask_bitrate(manifest_bitrates)
        else:
            if highest:
                return bitrate_values[0]
            elif preferred_bitrate:
                return preferred_bitrate
            else:  # ask user
                return self.ask_bitrate(bitrate_values)

    def select_version(self, game_versions):
        """Returns a game version, while honoring the user's /preference/.
        Note: the full version is always available but not always the condensed.
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

        if preferred_version > -1:
            return game_version
        else:
            return None

    def onFocus(self, controlId):  # pylint: disable=invalid-name
        # save currently focused list
        if controlId in [210, 220, 230, 240]:
            self.focusId = controlId

    def onClick(self, controlId):  # pylint: disable=invalid-name
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
                    self.main_selection = 'GamePass'
                    self.window.setProperty('NW_clicked', 'false')
                    self.window.setProperty('GP_clicked', 'true')

                    # display games of current week for usability purposes
                    cur_s_w = gp.get_current_season_and_week()
                    self.selected_season = cur_s_w.keys()[0]
                    self.selected_week = cur_s_w.values()[0]
                    self.display_seasons()

                    try:
                        self.display_seasons_weeks()
                        self.display_weeks_games()
                    except:
                        addon_log('Error while reading seasons weeks and games')
                elif controlId == 130:
                    self.main_selection = 'NFL Network'
                    self.window.setProperty('NW_clicked', 'true')
                    self.window.setProperty('GP_clicked', 'false')

                    listitem = xbmcgui.ListItem('NFL Network - Live', 'NFL Network - Live')
                    self.live_items.append(listitem)

                    if gp.redzone_on_air():
                        listitem = xbmcgui.ListItem('NFL RedZone - Live', 'NFL RedZone - Live')
                        self.live_items.append(listitem)

                    self.live_list.addItems(self.live_items)
                    self.display_nfln_seasons()

                xbmc.executebuiltin("Dialog.Close(busydialog)")
                return

            if self.main_selection == 'GamePass':
                if controlId == 210:  # season is clicked
                    self.init('season')
                    self.selected_season = self.season_list.getSelectedItem().getLabel()

                    self.display_seasons_weeks()
                elif controlId == 220:  # week is clicked
                    self.init('week/show')
                    self.selected_week = self.weeks_list.getSelectedItem().getProperty('week_code')

                    self.display_weeks_games()
                elif controlId == 230:  # game is clicked
                    selectedGame = self.games_list.getSelectedItem()
                    if selectedGame.getProperty('isPlayable') == 'true':
                        self.init('game/episode')
                        game_id = selectedGame.getProperty('game_id')
                        video_id = selectedGame.getProperty('video_id')
                        game_versions = selectedGame.getProperty('game_versions')

                        if 'Live' in game_versions:
                            if 'Final' in selectedGame.getProperty('game_info'):
                                game_version = self.select_version(game_versions)
                                if game_version == 'archive':
                                    game_version = 'dvr'
                            else:
                                game_version = 'live'
                        else:
                            # check for coaches film availability
                            if gp.has_coachestape(game_id, self.selected_season):
                                game_versions = game_versions + ' Coach'
                                coach_id = gp.has_coachestape(game_id, self.selected_season)
                            # check for condensed film availability
                            if gp.has_condensedGame(game_id, self.selected_season):
                                game_versions = game_versions + ' Condensed'
                                condensed_id = gp.has_condensedGame(game_id, self.selected_season)

                            game_version = self.select_version(game_versions)
                        if game_version:
                            #if game_version == 'coach':
                            #    xbmc.executebuiltin("ActivateWindow(busydialog)")
                            #    coachesItems = []
                            #    game_date = selectedGame.getProperty('game_date').replace('-', '/')
                            #    self.playBackStop = False

                                #play_stream = gp.get_coaches_url(game_id, game_date, 'dummy')
                                #play_stream = gp.get_publishpoint_streams(coach_id, 'game', game_version, username)
                                #plays = gp.get_coaches_playIDs(game_id, self.selected_season)
                                #for playID in sorted(plays, key=int):
                                #    cf_url = str(play_stream).replace('dummy', playID)
                                #    item = xbmcgui.ListItem(plays[playID])
                                #    item.setProperty('url', cf_url)
                                #    coachesItems.append(item)

                                #self.list_refill = True
                                #xbmc.executebuiltin("Dialog.Close(busydialog)")
                                #coachGui = CoachesFilmGUI('script-gamepass-coach.xml', ADDON_PATH, plays=coachesItems)
                                #coachGui.doModal()
                                #del coachGui
                            if game_version == 'condensed':
                                game_streams = gp.get_publishpoint_streams(condensed_id, 'game', game_version, username)
                            else:
                                if game_version == 'coach':
                                    game_streams = gp.get_publishpoint_streams(coach_id, 'game', game_version, username)
                                else:
                                    game_streams = gp.get_publishpoint_streams(video_id, 'game', game_version, username)
                            bitrate = self.select_bitrate(game_streams.keys())
                            if bitrate:
                                game_url = game_streams[bitrate]
                                self.play_url(game_url)

            elif self.main_selection == 'NFL Network':
                if controlId == 210:  # season is clicked
                    self.init('season')
                    self.selected_season = self.season_list.getSelectedItem().getLabel()

                    self.display_nfl_network_archive()
                elif controlId == 220:  # show is clicked
                    self.init('week/show')
                    show_name = self.weeks_list.getSelectedItem().getLabel()

                    self.display_shows_episodes(show_name, self.selected_season)
                elif controlId == 230:  # episode is clicked
                    self.init('game/episode')
                    video_id = self.games_list.getSelectedItem().getProperty('id')
                    video_streams = gp.get_publishpoint_streams(video_id, 'video', '', username)
                    if video_streams:
                        addon_log('Video-Streams: %s' % video_streams)
                        bitrate = self.select_bitrate(video_streams.keys())
                        if bitrate:
                            video_url = video_streams[bitrate]
                            self.play_url(video_url)
                    else:
                        dialog = xbmcgui.Dialog()
                        dialog.ok(language(30043), language(30045))
                elif controlId == 240:  # Live content (though not games)
                    show_name = self.live_list.getSelectedItem().getLabel()
                    if show_name == 'NFL RedZone - Live':
                        rz_live_streams = gp.get_publishpoint_streams('redzone', '', '', username)
                        if rz_live_streams:
                            bitrate = self.select_bitrate(rz_live_streams.keys())
                            if bitrate:
                                rz_live_url = rz_live_streams[bitrate]
                                self.play_url(rz_live_url)
                        else:
                            dialog = xbmcgui.Dialog()
                            dialog.ok(language(30043), language(30045))
                    elif show_name == 'NFL Network - Live':
                        nw_live_streams = gp.get_publishpoint_streams('nfl_network', '', '', username)
                        if nw_live_streams:
                            bitrate = self.select_bitrate(nw_live_streams.keys())
                            if bitrate:
                                nw_live_url = nw_live_streams[bitrate]
                                self.play_url(nw_live_url)
                        else:
                            dialog = xbmcgui.Dialog()
                            dialog.ok(language(30043), language(30045))
            xbmc.executebuiltin("Dialog.Close(busydialog)")
        except Exception:  # catch anything that might fail
            xbmc.executebuiltin("Dialog.Close(busydialog)")
            addon_log(format_exc())

            dialog = xbmcgui.Dialog()
            if self.main_selection == 'NFL Network' and controlId == 230:  # episode
                # inform that not all shows will work
                dialog.ok(language(30043), language(30044))
            else:
                # generic oops
                dialog.ok(language(30021), language(30024))


class CoachesFilmGUI(xbmcgui.WindowXML):
    def __init__(self, xmlFilename, scriptPath, plays, defaultSkin="Default", defaultRes="720p"):  # pylint: disable=invalid-name
        self.playsList = None
        self.playsItems = plays

        xbmcgui.WindowXML.__init__(self, xmlFilename, scriptPath, defaultSkin, defaultRes)
        self.action_previous_menu = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)

    def onInit(self):  # pylint: disable=invalid-name
        self.window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
        if addon.getSetting('coach_lite') == 'true':
            self.window.setProperty('coach_lite', 'true')

        self.playsList = self.window.getControl(110)
        self.window.getControl(99).setLabel(language(30032))
        self.playsList.addItems(self.playsItems)
        self.setFocus(self.playsList)
        url = self.playsList.getListItem(0).getProperty('url')
        xbmc.executebuiltin("Dialog.Close(busydialog)")
        xbmc.executebuiltin('PlayMedia(%s,False,1)' % url)

    def onClick(self, controlId):  # pylint: disable=invalid-name
        if controlId == 110:
            url = self.playsList.getSelectedItem().getProperty('url')
            xbmc.executebuiltin('PlayMedia(%s,False,1)' % url)

if __name__ == "__main__":
    addon_log('script starting')
    xbmc.executebuiltin("Dialog.Close(busydialog)")

    try:
        gp.login(username, password)
    except gp.LoginFailure as error:
        dialog = xbmcgui.Dialog()
        if error.value == 'Game Pass Domestic Blackout':
            addon_log('Game Pass Domestic is in blackout.')
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

    gui = GamepassGUI('script-gamepass.xml', ADDON_PATH)
    gui.doModal()
    del gui

addon_log('script finished')
