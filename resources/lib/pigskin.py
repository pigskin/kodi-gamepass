"""
A Kodi-agnostic library for NFL Game Pass
"""
import codecs
import uuid
import m3u8
import re
import sys
import json
import urllib
from traceback import format_exc
from urlparse import urlsplit

import requests
import xmltodict


class pigskin(object):
    def __init__(self, proxy_config, debug=False):
        self.debug = debug
        self.base_url = 'https://www.nflgamepass.com'
        self.http_session = requests.Session()
        self.access_token = None
        self.refresh_token = None
        self.config = self.make_request(self.base_url + '/api/en/content/v1/web/config', 'get')
        self.client_id = self.config["modules"]["API"]["CLIENT_ID"]
        self.nflnShows = {}
        self.nflnSeasons = []

        if proxy_config is not None:
            proxy_url = self.build_proxy_url(proxy_config)
            if proxy_url != '':
                self.http_session.proxies = {
                    'http': proxy_url,
                    'https': proxy_url,
                }

        self.log('Debugging enabled.')
        self.log('Python Version: %s' % sys.version)

    class GamePassError(Exception):
        def __init__(self, value):
            self.value = value

        def __str__(self):
            return repr(self.value)

    def log(self, string):
        if self.debug:
            try:
                print '[pigskin]: %s' % string
            except UnicodeEncodeError:
                # we can't anticipate everything in unicode they might throw at
                # us, but we can handle a simple BOM
                bom = unicode(codecs.BOM_UTF8, 'utf8')
                print '[pigskin]: %s' % string.replace(bom, '')
            except:
                pass

    def make_request(self, url, method, params=None, payload=None, headers=None):
        """Make an HTTP request. Return the response."""
        self.log('Request URL: %s' % url)
        self.log('Method: %s' % method)
        if params:
            self.log('Params: %s' % params)
        if payload:
            self.log('Payload: %s' % payload)
        if headers:
            self.log('Headers: %s' % headers)

        if method == 'get':
            req = self.http_session.get(url, params=params, headers=headers)
        elif method == 'put':
            req = self.http_session.put(url, params=params, data=payload, headers=headers)
        else:  # post
            req = self.http_session.post(url, params=params, data=payload, headers=headers)
        self.log('Response code: %s' % req.status_code)
        self.log('Response: %s' % req.content)

        return self.parse_response(req)

    def parse_response(self, req):
        """Try to load JSON data into dict and raise potential errors."""
        try:
            response = json.loads(req.content)
        except ValueError:  # if response is not json
            response = req.content

        if isinstance(response, dict):
            for key in response.keys():
                if key.lower() == 'message':
                    if response[key]: # raise all messages as GamePassError if message is not empty
                        raise self.GamePassError(response[key])

        return response

    def build_proxy_url(self, config):
        proxy_url = ''

        if 'scheme' in config:
            scheme = config['scheme'].lower().strip()
            if scheme != 'http' and scheme != 'https':
                return ''
            proxy_url += scheme + '://'

        if 'auth' in config and config['auth'] is not None:
            try:
                username = config['auth']['username']
                password = config['auth']['password']
                if username == '' or password == '':
                    return ''
                proxy_url += '%s:%s@' % (urllib.quote(username), urllib.quote(password))
            except KeyError:
                return ''

        if 'host' not in config or config['host'].strip() == '':
            return ''
        proxy_url += config['host'].strip()

        if 'port' in config:
            try:
                port = int(config['port'])
                if port <= 0 or port > 65535:
                    return ''
                proxy_url += ':' + str(port)
            except ValueError:
                return ''

        return proxy_url

    def login(self, username, password):
        """Blindly authenticate to Game Pass. Use has_subscription() to
        determine success.
        """
        url = self.config["modules"]["API"]["LOGIN"]
        post_data = {
            'username': username,
            'password': password,
            'client_id': self.client_id,
            'grant_type': 'password'
        }
        data = self.make_request(url, 'post', payload=post_data)
        self.access_token = data['access_token']
        self.refresh_token = data['refresh_token']
        self.check_for_subscription()

        return True

    def check_for_subscription(self):
        """Returns True if a subscription is detected. Raises error_unauthorised on failure."""
        url = self.config["modules"]["API"]["USER_PROFILE"]
        headers = {'Authorization': 'Bearer {0}'.format(self.access_token)}
        self.make_request(url, 'get', headers=headers)

        return True

    def refresh_tokens(self):
        """Refreshes authorization tokens."""
        url = self.config["modules"]["API"]["LOGIN"]
        post_data = {
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'grant_type': 'refresh_token'
        }
        data = self.make_request(url, 'post', payload=post_data)
        self.access_token = data['access_token']
        self.refresh_token = data['refresh_token']

        return True

    def get_seasons_and_weeks(self):
        """Return a multidimensional array of all seasons and weeks."""
        seasons_and_weeks = {}

        try:
            url = self.config["modules"]["ROUTES_DATA_PROVIDERS"]["games"]
            seasons = self.make_request(url, 'get')
        except:
            self.log('Acquiring season and week data failed.')
            raise

        try:
            for season in seasons['modules']['mainMenu']['seasonStructureList']:
                year = str(season['season'])
                season_dict = {}

                for season_week_types in season['seasonTypes']:
                    if season_week_types['seasonType'] == "pre":  # preseason
                        for week in season_week_types['weeks']:
                            week_code = '1' + str(week['number']).zfill(2)
                            if week['weekNameAbbr'] == 'hof':
                                season_dict[week_code] = 'Hall of Fame'
                            else:
                                season_dict[week_code] = 'Week ' + str(week['number'])
                    if season_week_types['seasonType'] == "reg":
                        for week in season_week_types['weeks']:
                            week_code = '2' + str(week['number']).zfill(2)
                            season_dict[week_code] = 'Week ' + str(week['number']+4)
                    else:  # regular season and post season
                        for week in season_week_types['weeks']:
                            week_code = '3' + str(week['number']).zfill(2)
                            if week['weekNameAbbr'] == 'wc':
                                season_dict[week_code] = 'WILD CARD ROUND'
                            if week['weekNameAbbr'] == 'div':
                                season_dict[week_code] = 'DIVISIONAL ROUND'
                            if week['weekNameAbbr'] == 'conf':
                                season_dict[week_code] = 'CHAMPIONSHIP ROUND'
                            if week['weekNameAbbr'] == 'pro':
                                season_dict[week_code] = 'PRO BOWL'
                            if week['weekNameAbbr'] == 'sb':
                                season_dict[week_code] = 'SUPER BOWL'

                seasons_and_weeks[year] = season_dict
        except KeyError:
            self.log('Parsing season and week data failed.')
            raise

        return seasons_and_weeks

    def get_current_season_and_week(self):
        """Return the current season and week_code (e.g. 210) in a dict."""
        try:
            url = self.config["modules"]["ROUTES_DATA_PROVIDERS"]["games"]
            seasons = self.make_request(url, 'get')
        except:
            self.log('Acquiring season and week data failed.')
            raise

        if seasons['modules']['meta']['currentContext']['currentSeasonType'] == 'pre':
            current_s_w = {seasons['modules']['meta']['currentContext']['currentSeason']: '1' + str(seasons['modules']['meta']['currentContext']['currentWeek']).zfill(2)}
        if seasons['modules']['meta']['currentContext']['currentSeasonType'] == 'reg':
            current_s_w = {seasons['modules']['meta']['currentContext']['currentSeason']: '2' + str(seasons['modules']['meta']['currentContext']['currentWeek']).zfill(2)}
        if seasons['modules']['meta']['currentContext']['currentSeasonType'] == 'post':
            current_s_w = {seasons['modules']['meta']['currentContext']['currentSeason']: '3' + str(seasons['modules']['meta']['currentContext']['currentWeek']).zfill(2)}

        return current_s_w

    def get_weeks_games(self, season, week_code):
        if week_code[:1] == '1':
            week_code = week_code[1:].lstrip('0')
            if week_code == '':
                week_code = '0'
            seasonType = 'pre'
        else:
            if week_code[:1] == '2':
                week_code = week_code[1:].lstrip('0')
                seasonType = 'reg'
            else:
                if week_code[:1] == '3':
                    week_code = week_code[1:].lstrip('0')
                    seasonType = 'post'
        try:
            url = self.config['modules']['ROUTES_DATA_PROVIDERS']['games_detail'].replace(':seasonType', seasonType).replace(':season', season).replace(':week', week_code)
            games = self.make_request(url, 'get')
        except:
            self.log('Acquiring games data failed.')
            raise

        return games

    def get_team_games(self, season, team=None):
        try:
            url = self.config['modules']['ROUTES_DATA_PROVIDERS']['teams']
            teams = self.make_request(url, 'get')
            if team is None:
                return teams
            else:
                for conference in teams['modules']:
                    for teamname in teams['modules'][conference]['content']:
                        if team == teamname['fullName']:
                            team = teamname['seoname']

                url = self.config['modules']['ROUTES_DATA_PROVIDERS']['team_detail'].replace(':team', team)
                team_detail = self.make_request(url, 'get')

                return team_detail

        except:
            self.log('Acquiring games data failed.')
            raise
        return False

    def has_coachestape(self, game_id, season):
        """Return whether coaches tape is available for a given game."""
        url = self.config['modules']['ROUTES_DATA_PROVIDERS']['game_page'].replace(':season', season).replace(':gameslug', game_id)
        response = self.make_request(url, 'get')
        coachfilmVideo = response['modules']['singlegame']['content'][0]['coachfilmVideo']
        if coachfilmVideo is None:
            print 'No coaches Tape available'
            return False
        else:
            print 'Coaches Tape available'
            return coachfilmVideo['videoId']

    def has_condensedGame(self, game_id, season):
        """Return whether coaches tape is available for a given game."""
        url = self.config['modules']['ROUTES_DATA_PROVIDERS']['game_page'].replace(':season', season).replace(':gameslug', game_id)
        response = self.make_request(url, 'get')
        condensedVideo = response['modules']['singlegame']['content'][0]['condensedVideo']
        if condensedVideo is None:
            print 'No Condensed Game available'
            return False
        else:
            print 'Condensed Game available'
            return condensedVideo['videoId']

    def get_publishpoint_streams(self, video_id, stream_type=None, game_type=None, username=None, full = None):
        """Return the URL for a stream."""
        streams = {}
        self.get_current_season_and_week()  # set cookies

        if video_id == 'nfl_network':
            divaconfig = self.config['modules']['DIVA']['HTML5']['SETTINGS']['Live24x7']
            url = self.config['modules']['ROUTES_DATA_PROVIDERS']['network']
            response = self.make_request(url, 'get')
            video_id = response['modules']['networkLiveVideo']['content'][0]['videoId']
        else:
            if game_type == 'live':
                divaconfig = self.config['modules']['DIVA']['HTML5']['SETTINGS']['LiveNoData']
            else:
                divaconfig = self.config['modules']['DIVA']['HTML5']['SETTINGS']['VodNoData']

        url = divaconfig.replace('device', 'html5')
        request = self.make_request(url, 'get')
        divaconfig = xmltodict.parse(request)
        for parameter in divaconfig['settings']['videoData']['parameter']:
            if parameter['@name']== 'videoDataPath':
                videoDataPath = parameter['@value'].replace('{V.ID}',video_id)
        for parameter in divaconfig['settings']['entitlementCheck']['parameter']:
            if parameter['@name']== 'processingUrlCallPath':
                processingUrlCallPath = parameter['@value']
        request = self.make_request(videoDataPath, 'get')
        akamai_url = xmltodict.parse(request)
        for videoSource in akamai_url['video']['videoSources']['videoSource']:
            if videoSource['@format']== 'HLS':
                m3u8_url = videoSource['uri']
        self.refresh_tokens()

        post_data = {
            'Type': '1',
            'User': '',
            'VideoId': video_id,
            'VideoSource': m3u8_url,
            'VideoKind': 'Video',
            'AssetState': '3',
            'PlayerType': 'HTML5',
            'other': str(uuid.uuid4()) + '|' + self.access_token + '|web|Mozilla%2F5.0%20(Windows%20NT%2010.0%3B%20WOW64%3B%20rv%3A54.0)%20Gecko%2F20100101%20Firefox%2F54.0|undefined|' +  username
        }

        response = self.make_request(processingUrlCallPath, 'post', payload=json.dumps(post_data))
        m3u8_url = response['ContentUrl']

        m3u8_manifest = self.make_request(m3u8_url, 'get')
        if full:
            return m3u8_url
        m3u8_header = {'User-Agent': 'Safari/537.36 Mozilla/5.0 AppleWebKit/537.36 Chrome/31.0.1650.57',
                       'Connection': 'keep-alive'}

        if m3u8_manifest:
            m3u8_obj = m3u8.loads(m3u8_manifest)
            if m3u8_obj.is_variant:  # if this m3u8 contains links to other m3u8s
                for playlist in m3u8_obj.playlists:
                    bitrate = int(playlist.stream_info.bandwidth)
                    streams[bitrate] = m3u8_url[:m3u8_url.rfind('/manifest') + 1] + playlist.uri + '?' + m3u8_url.split('?')[1] + '|' + urllib.urlencode(m3u8_header)
            else:
                streams['sole available'] = m3u8_url

        return streams

    def redzone_on_air(self):
        """Return whether RedZone Live is currently broadcasting."""
        url = self.config['modules']['ROUTES_DATA_PROVIDERS']['redzone']
        response = self.make_request(url, 'get')
        # Dynamically parse NFL-Network shows
        self.parse_shows()

        # Check if RedZone is Live
        #if sc_dict['rzPhase'] in ('pre', 'in'):
        #    self.log('RedZone is on air.')
        #    return True
        #else:
        #    self.log('RedZone is not on air.')
        #    return False
        if not response['modules']['redZoneLive']['content']:
            return False
        else:
            return True

    def parse_shows(self):
        url = self.config['modules']['API']['NETWORK_PROGRAMS']
        response = self.make_request(url, 'get')
        show_dict = {}

        for show in response['modules']['programs']:
            name = show['title']
            slug = show['slug']
            season_dict = {}
            for season in show['seasons']:
                slug_dict = {}
                season_name = season['value']
                season_id = season['slug']
                season_dict[season_name] = season_id
                if season_name not in self.nflnSeasons:
                        self.nflnSeasons.append(season_name)
            show_dict[name] = season_dict
        self.nflnShows.update(show_dict)

    def get_shows(self, season):
        """Return a list of all shows for a season."""
        #seasons_shows = self.nflnShows.keys()
        seasons_shows = []

        for show_name, show_codes in self.nflnShows.items():
            if season in show_codes:
                seasons_shows.append(show_name)

        return sorted(seasons_shows)

    def get_shows_episodes(self, show_name, season=None):
        """Return a list of episodes for a show. Return empty list if none are
        found or if an error occurs.
        """
        url = self.config['modules']['API']['NETWORK_PROGRAMS']
        response = self.make_request(url, 'get')
        season_id = ''
        slug = ''
        for show in response['modules']['programs']:
            name = show['title']
            if show_name == name:
                slug = show['slug']
                for seasons in show['seasons']:
                    season_name = seasons['value']
                    if season == season_name:
                        season_id = seasons['slug']
        url = self.config['modules']['API']['NETWORK_EPISODES']
        url = url.replace(':seasonSlug', season_id).replace(':tvShowSlug', slug)
        response = self.make_request(url, 'get')

        return response
