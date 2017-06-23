"""
A Kodi-agnostic library for NFL Game Pass
"""
import codecs
import hashlib
import random
import m3u8
import re
import sys
import json
import urllib
from traceback import format_exc
from uuid import getnode as get_mac
from urlparse import urlsplit

import requests
import xmltodict


class pigskin(object):
    def __init__(self, proxy_config, debug=False):
        self.debug = debug
        self.base_url = 'https://www.nflgamepass.com'
        self.http_session = requests.Session()
        self.access_token = ''
        self.refresh_token = ''
        #################
        url = self.base_url + '/api/en/content/v1/web/config'
        jsonconfig = requests.get(url, verify=False)
        self.config = jsonconfig.json()
        self.client_id = self.config["modules"]["API"]["CLIENT_ID"]
        #self.config["modules"]["API"]["LOGIN"]

        #################
        
        
        
        self.servlets_url = 'http://gamepass.nfl.leutner.ch/nflgp/servlets'
        self.simpleconsole_url = self.servlets_url + '/simpleconsole'
        self.boxscore_url = ''
        self.image_url = ''
        self.locEDLBaseUrl = ''
        self.non_seasonal_shows = {}
        self.seasonal_shows = {}
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

    class LoginFailure(Exception):
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

    def check_for_subscription(self):
        """Return whether a subscription and user name are detected. Determines
        whether a login was successful."""
        url = self.config["modules"]["API"]["USER_PROFILE"]
        BearerHeaders = {"Authorization":"Bearer " + self.access_token}
        request=requests.get(url, headers=BearerHeaders, verify=False)
        if request.status_code == 401:
            self.log('Subscription not detected in Game Pass response.')
            return False
        else:
            self.log('Subscription detected.')
            return True

    def login(self, username=None, password=None):
        """Complete login process for Game Pass. Errors (auth issues, blackout,
        etc) are raised as LoginFailure.
        """
        if self.check_for_subscription():
            self.log('Already logged into Game Pass ')
        else:
            if username and password:
                self.log('Not (yet) logged into ')
                self.login_to_account(username, password)
                if not self.check_for_subscription():
                    raise self.LoginFailure('login failed')
            else:
                self.log('No username and password supplied.')
                raise self.LoginFailure('No username and password supplied.')

    def login_to_account(self, username, password):
        """Blindly authenticate to Game Pass. Use check_for_subscription() to
        determine success.
        """
        url = self.config["modules"]["API"]["LOGIN"]
        post_data = {
            'username': username,
            'password': password,
            'client_id': self.client_id,
            'grant_type': 'password'
        }
        request = requests.post(url, data=post_data, verify=False)
        if request.status_code == 200:
            result = request.json()
            self.access_token = result["access_token"]
            self.refresh_token = result["refresh_token"]
            return True
        return False
    
    def get_refresh_token(self, refresh_token):
        """Blindly authenticate to Game Pass. Use check_for_subscription() to
        determine success.
        """
        url = self.config["modules"]["API"]["LOGIN"]
        post_data = {
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'grant_type': 'refresh_token'
        }
        request = requests.post(url, data=post_data, verify=False)
        if request.status_code == 200:
            result = request.json()
            self.access_token = result["access_token"]
            self.refresh_token = result["refresh_token"]
            return True
        return False
        
    def get_seasons_and_weeks(self):
        """Return a multidimensional array of all seasons and weeks."""
        seasons_and_weeks = {}

        try:
            url = self.config["modules"]["ROUTES_DATA_PROVIDERS"]["games"]
            request = requests.get(url, verify=False)
            seasons = request.json()
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
            request = requests.get(url, verify=False)
            seasons = request.json()
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
            url = self.config['modules']['ROUTES_DATA_PROVIDERS']['games_detail']
            url = url.replace(':seasonType', seasonType).replace(':season', season).replace(':week', week_code)
            request = requests.get(url, verify=False)
            games = request.json()
        except:
            self.log('Acquiring games data failed.')
            raise
        return games
        
    def check_for_coachestape(self, game_id, season):
        """Return whether coaches tape is available for a given game."""
        url = self.config['modules']['ROUTES_DATA_PROVIDERS']['game_page']
        url = url.replace(':season', season).replace(':gameslug', game_id)
        request = requests.get(url, verify=False)
        response = request.json()
        coachfilmVideo = response['modules']['singlegame']['content'][0]['coachfilmVideo']
        if coachfilmVideo is None:
            print 'No coaches Tape available'
            return False
        else:
            print 'Coaches Tape available'
            return coachfilmVideo['videoId'] 
    
    def check_for_condensedGame(self, game_id, season):
        """Return whether coaches tape is available for a given game."""
        url = self.config['modules']['ROUTES_DATA_PROVIDERS']['game_page']
        url = url.replace(':season', season).replace(':gameslug', game_id)
        request = requests.get(url, verify=False)
        response = request.json()
        condensedVideo = response['modules']['singlegame']['content'][0]['condensedVideo']
        if condensedVideo is None:
            print 'No condensed Game available'
            return False
        else:
            print 'Condensed Game available'
            return condensedVideo['videoId']

    def gen_plid(self):
        """Return a "unique" MD5 hash. Getting the video path requires a plid,
        which looks like MD5 and always changes. Reusing a plid does not work,
        so our guess is that it's a id for each instance of the player.
        """
        rand = random.getrandbits(10)
        mac_address = str(get_mac())
        md5 = hashlib.md5(str(rand) + mac_address)
        return md5.hexdigest()
        
    def get_publishpoint_streams(self, video_id, stream_type=None, game_type=None, username=None, full = None):
        """Return the URL for a stream."""
        streams = {}
        self.get_current_season_and_week()  # set cookies
        divaconfig = self.config['modules']['DIVA']['HTML5']['SETTINGS']['VodNoData']
        url = divaconfig.replace('device', 'html5')
        request = requests.get(url, verify=False)
        divaconfig = xmltodict.parse(request.text)
        for parameter in divaconfig['settings']['videoData']['parameter']:
            if parameter['@name']== 'videoDataPath':
                videoDataPath = parameter['@value'].replace('{V.ID}',video_id)
        for parameter in divaconfig['settings']['entitlementCheck']['parameter']:
            if parameter['@name']== 'processingUrlCallPath':
                processingUrlCallPath = parameter['@value']
        request = requests.get(videoDataPath, verify=False)
        akamai_url = xmltodict.parse(request.text)
        for videoSource in akamai_url['video']['videoSources']['videoSource']:
            if videoSource['@format']== 'HLS':
                m3u8_url = videoSource['uri']
        self.get_refresh_token(self.refresh_token)
        
        
        
        
        post_data = {
            'Type': '1',
            'User': '',
            'VideoId': video_id,
            'VideoSource': m3u8_url,
            'VideoKind': 'Video',
            'AssetState': '3',
            'PlayerType': 'HTML5',
            'other': self.gen_plid() + '|' + self.access_token + '|web|Mozilla%2F5.0%20(Windows%20NT%2010.0%3B%20WOW64%3B%20rv%3A54.0)%20Gecko%2F20100101%20Firefox%2F54.0|undefined|' +  username
        }
        
        request = requests.post(processingUrlCallPath, json=post_data, verify=False)
        response = request.json()
        m3u8_url = response['ContentUrl']
        
        m3u8_request = requests.get(m3u8_url, verify=False)
        m3u8_manifest = m3u8_request.text
        if full:
            return m3u8_url
        m3u8_header = {'User-Agent': 'Safari/537.36 Mozilla/5.0 AppleWebKit/537.36 Chrome/31.0.1650.57',
                       'Connection': 'keep-alive'}

        if m3u8_manifest:
            m3u8_obj = m3u8.loads(m3u8_manifest)
            if m3u8_obj.is_variant:  # if this m3u8 contains links to other m3u8s
                for playlist in m3u8_obj.playlists:
                    bitrate = int(playlist.stream_info.bandwidth)
                    print bitrate
                    streams[bitrate] = m3u8_url[:m3u8_url.rfind('/manifest') + 1] + playlist.uri + '?' + m3u8_url.split('?')[1] + '|' + urllib.urlencode(m3u8_header)
            else:
                streams['sole available'] = m3u8_url

        return streams
    
