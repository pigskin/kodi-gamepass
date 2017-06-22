"""
A Kodi-agnostic library for NFL Game Pass
"""
import codecs
import hashlib
import random
import m3u8
import re
import sys
import urllib
import urllib2
import json
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
        jsonconfig = urllib2.urlopen(url)
        self.config = json.loads(jsonconfig.read())
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
                proxy_url += '%s:%s@' % (urllib2.quote(username), urllib2.quote(password))
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
        request=urllib2.Request(url, headers=BearerHeaders)
        try:
            response = urllib2.urlopen(request)
        except urllib2.HTTPError as e:
            if e.code==401:
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
        request = urllib2.urlopen(url, urllib.urlencode(post_data))
        result = json.loads(request.read())
        self.access_token = result["access_token"]
        self.refresh_token = result["refresh_token"]
        print result

    def get_seasons_and_weeks(self):
        """Return a multidimensional array of all seasons and weeks."""
        seasons_and_weeks = {}

        try:
            url = self.config["modules"]["ROUTES_DATA_PROVIDERS"]["games"]
            request = urllib2.urlopen(url)
            seasons = json.loads(request.read())
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
            request = urllib2.urlopen(url)
            seasons = json.loads(request.read())
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
            type = 'pre'
        if week_code[:1] == '2':
            week_code = week_code[1:].lstrip('0')
            type = 'reg'
        if week_code[:1] == '3':
            week_code = week_code[1:].lstrip('0')
            type = 'post'
        try:
            url = self.config['modules']['ROUTES_DATA_PROVIDERS']['games_detail']
            print url
            url = url.replace(':seasonType', type).replace(':season', season).replace(':week', week_code)
            
            print type
            print week_code
            print season
            print url
        
            request = urllib2.urlopen(url)
            games = json.loads(request.read())
        except:
            self.log('Acquiring games data failed.')
            raise
        return games