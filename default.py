﻿import urllib
import time
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
import xmltodict
from datetime import datetime, timedelta, date
from traceback import format_exc
from urlparse import urlparse, parse_qs

from resources.lib.game_common import *

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


    def __init__(self, *args, **kwargs):
        xbmcgui.WindowXMLDialog.__init__(self)
        self.action_previous_menu = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)

    def onInit(self):
        self.window = xbmcgui.Window(xbmcgui.getCurrentWindowDialogId())
        self.season_list = self.window.getControl(210)
        self.weeks_list = self.window.getControl(220)
        self.games_list = self.window.getControl(230)
        self.setFocus(self.window.getControl(100))

    def coloring(self, text, meaning):
        if meaning == "disabled":
            color = "FF000000"
        elif meaning == "disabled-info":
            color = "FF111111"
        colored_text = "[COLOR=%s]%s[/COLOR]" %(color, text)
        return colored_text

    def display_seasons(self):
        seasons = get_seasons()
        for season in seasons:
            listitem = xbmcgui.ListItem(season)
            self.season_list.addItem(listitem)

    def display_nfl_network_archive(self):
        if subscription == '0': # GamePass
            listitem = xbmcgui.ListItem('NFL Network - Live', 'NFL Network - Live')
            self.weeks_list.addItem(listitem)
        for i in show_archives.keys():
            if not(i == 'NFL RedZone'):
                listitem = xbmcgui.ListItem(i)
                self.weeks_list.addItem(listitem)

    def display_redzone(self):
        url = 'http://gamepass.nfl.com/nflgp/servlets/simpleconsole'
        simple_data = make_request(url, {'isFlex':'true'})
        simple_dict = xmltodict.parse(simple_data)['result']
        if simple_dict['rzPhase'] == 'in':
            listitem = xbmcgui.ListItem('NFL RedZone - Live', 'NFL RedZone - Live')
            self.weeks_list.addItem(listitem)
        listitem = xbmcgui.ListItem('NFL RedZone - Archive', 'NFL RedZone - Archive')
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
                isLive = 'false'
                isPlayable = 'true'
                home_team = game['homeTeam']
                # sometimes the first item is empty
                if home_team['name'] is None:
                    continue

                game_version_ids = {}
                for key, value in {'Condensed': 'condensedId', 'Full': 'programId', 'Live': 'id'}.items():
                    try:
                        game_version_ids[key] = game[value]
                    except KeyError:
                        pass

                away_team = game['awayTeam']
                game_name_shrt = '[B]%s[/B] at [B]%s[/B]' %(away_team['name'], home_team['name'])
                game_name_full = '[B]%s %s[/B] at [B]%s %s[/B]' %(away_team['city'], away_team['name'], home_team['city'], home_team['name'])

                if game.has_key('isLive') and not game.has_key('gameEndTimeGMT'): # sometimes isLive lies
                    game_name_full += ' - Live'
                    isLive = 'true'
                elif game.has_key('gameEndTimeGMT'):
                    try:
                        start_time = datetime(*(time.strptime(game['gameTimeGMT'], date_time_format)[0:6]))
                        end_time = datetime(*(time.strptime(game['gameEndTimeGMT'], date_time_format)[0:6]))
                        game_info = 'Final [CR] Duration: %s' %time.strftime('%H:%M:%S', time.gmtime((end_time - start_time).seconds))
                    except:
                        addon_log(format_exc())
                        if game.has_key('result'):
                            game_info = ' - Final'
                else:
                    try:
                        # may want to change this to game['gameTimeGMT'] or do a setting maybe
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
                listitem.setProperty('away_thumb', 'http://i.nflcdn.com/static/site/5.31/img/logos/teams-matte-80x53/%s.png' %away_team['id'])
                listitem.setProperty('home_thumb', 'http://i.nflcdn.com/static/site/5.31/img/logos/teams-matte-80x53/%s.png' %home_team['id'])
                listitem.setProperty('game_info', game_info)
                listitem.setProperty('is_game', 'true')
                listitem.setProperty('is_show', 'false')
                listitem.setProperty('isPlayable', isPlayable)
                listitem.setProperty('isLive', isLive)
                params = {'name': game_name_full, 'url': game_version_ids}
                url = '%s?%s' %(sys.argv[0], urllib.urlencode(params))
                listitem.setProperty('url', url)
                self.games_list.addItem(listitem)

    def display_archive(self, show_name, season, cid):
        cur_season = get_current_season()

        # No valid CID passed
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
                    listitem.setProperty('isPlayable', 'true')
                    self.games_list.addItem(listitem)
                except:
                    addon_log('Exception adding archive directory: %s' %format_exc())
                    addon_log('Directory name: %s' %i['name'])

    def playUrl(self, url):
        player = myPlayer(parent=window)
        player.play(url)

        while player.isPlaying():
            xbmc.sleep(2000)

    def select_bitrate(self):
        preferred_bitrate = int(addon.getSetting('preferred_bitrate'))
        bitrate_values = ['4500', '3000', '2400', '1600', '1200', '800', '400']

        if preferred_bitrate == 0: # "highest"
            bitrate = bitrate_values[0]
        elif preferred_bitrate < 7: # specific bitrate
            bitrate = bitrate_values[preferred_bitrate -1]
        else: # ask
            options = []
            for i in range(len(bitrate_values)):
                options.append(language(30005 + i))
            dialog = xbmcgui.Dialog()
            ret = dialog.select(language(30003), options)
            bitrate = bitrate_values[ret]

        return ret

    # returns a gameid, while honoring user preference when applicable
    def select_version(self, game_version_ids):
        preferred_version = int(addon.getSetting('preferred_game_version'))

        # the full version is always available, but not always the condensed
        game_id = game_version_ids['Full']
        versions = [language(30014)]

        if game_version_ids.has_key('Condensed'):
            versions.append(language(30015))
            if preferred_version == 1:
                game_id = game_version_ids['Condensed']

        # user wants to be asked to select version
        if preferred_version == 2:
            dialog = xbmcgui.Dialog()
            ret = dialog.select(language(30016), versions)
            if ret == 1:
                game_id = game_version_ids['Condensed']

        return game_id

    def onClick(self, controlId):
        if controlId in[110, 120, 130]:
            self.games_list.reset()
            self.weeks_list.reset()
            self.season_list.reset()

            if controlId == 110:
                self.main_selection = 'GamePass'
            elif controlId == 120:
                self.main_selection = 'RedZone'
            elif controlId == 130:
                self.main_selection = 'NFL Network'

            self.display_seasons()
            return

        if self.main_selection == 'GamePass':
            if controlId == 210: # season is clicked
                self.weeks_list.reset()
                self.games_list.reset()
                self.selected_season = self.season_list.getSelectedItem().getLabel()
                weeks = get_seasons_weeks(self.selected_season)

                for week_code, week_name in sorted(weeks['weeks'].iteritems()):
                    week_date = weeks['dates'][week_code]+' 06:00'
                    future = 'false'

                    week_time = int(time.mktime(time.strptime(week_date, '%Y%m%d %H:%M')))
                    time_utc = str(datetime.utcnow())[:-7]
                    time_now = int(time.mktime(time.strptime(time_utc, '%Y-%m-%d %H:%M:%S')))

                    if week_time > time_now:
                        future = 'true'

                    listitem = xbmcgui.ListItem(week_name)
                    listitem.setProperty('week_code', week_code)
                    listitem.setProperty('future', future)
                    self.weeks_list.addItem(listitem)
            elif controlId == 220: # week is clicked
                self.games_list.reset()
                self.selected_week = self.weeks_list.getSelectedItem().getProperty('week_code')
                self.display_weeks_games()
            elif controlId == 230: # game is clicked
                if self.games_list.getSelectedItem().getProperty('isPlayable') == 'true':
                    selectedGame = self.games_list.getSelectedItem()
                    url = selectedGame.getProperty('url')
                    params = parse_qs(urlparse(url).query)
                    for i in params.keys():
                        params[i] = params[i][0]
                    game_version_ids = eval(params['url'])

                    if selectedGame.getLabel2().endswith('- Live'):
                        game_live_url = get_live_url(game_version_ids['Live'], self.select_bitrate())
                        self.playUrl(game_live_url)
                    else:
                        game_id = self.select_version(game_version_ids)
                        game_url = get_stream_url(game_id)
                        self.playUrl(game_url)
        elif self.main_selection == 'RedZone':
            if controlId == 210: # season is clicked
                self.weeks_list.reset()
                self.games_list.reset()
                self.selected_season = self.season_list.getSelectedItem().getLabel()
                self.display_redzone()
            elif controlId == 220: # show is clicked
                self.games_list.reset()
                show_name = self.weeks_list.getSelectedItem().getLabel()
                if show_name == 'RedZone - Live':
                    redzone_live_url = get_live_url('rz', self.select_bitrate())
                    self.playUrl(redzone_live_url)
                elif show_name == 'NFL RedZone - Archive':
                    self.display_archive('NFL RedZone', self.selected_season, show_archives['NFL RedZone'][self.selected_season])
            elif controlId == 230: # episode is clicked
                url = self.games_list.getSelectedItem().getProperty('url')
                stream_url = resolve_show_archive_url(url)
                self.playUrl(stream_url)
        elif self.main_selection == 'NFL Network':
            if controlId == 210: # season is clicked
                self.weeks_list.reset()
                self.games_list.reset()
                self.selected_season = self.season_list.getSelectedItem().getLabel()
                self.display_nfl_network_archive()
            elif controlId == 220: # show is clicked
                self.games_list.reset()
                show_name = self.weeks_list.getSelectedItem().getLabel()
                if show_name == 'NFL Network - Live':
                    nfl_network_url = get_live_url('nfl_network', self.select_bitrate())
                    self.playUrl(nfl_network_url)
                else:
                    self.display_archive(show_name, self.selected_season, show_archives[show_name][self.selected_season])
            elif controlId == 230: # episode is clicked
                url = self.games_list.getSelectedItem().getProperty('url')
                stream_url = resolve_show_archive_url(url)
                self.playUrl(stream_url)


if (__name__ == "__main__"):
    addon_log('script starting')

    addon_path = xbmc.translatePath(addon.getAddonInfo('path'))

    if not xbmcvfs.exists(addon_profile):
        xbmcvfs.mkdir(addon_profile)

    try:
        if subscription == '0': # Game Pass
            login_gamepass(addon.getSetting('email'), addon.getSetting('password'))
        else: # Game Rewind
            login_rewind(addon.getSetting('gr_email'), addon.getSetting('gr_password'))
    except LoginFailure as e:
        dialog = xbmcgui.Dialog()
        if e.value == 'Game Rewind Blackout':
            addon_log('Rewind is in blackout.')
            dialog.ok(language(30018),
                      'Due to broadcast restrictions',
                      'NFL Game Rewind is currently unavailable.',
                      'Please try again later.')
        else:
            addon_log('auth failure')
            dialog.ok('Login Failed',
                      'Logging into NFL Game Pass/Rewind failed.',
                      'Make sure your account information is correct.')
    except:
        addon_log(format_exc())
        dialog = xbmcgui.Dialog()
        dialog.ok('Epic Failure',
                  'Some bad jujumagumbo just went down.',
                  'Please enable debuging, and submit a bug report.')
        sys.exit(0)

    window = GamepassGUI('script-gamepass.xml', addon_path)
    window.doModal()

addon_log('script finished')
