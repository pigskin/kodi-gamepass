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
