"""
An XBMC plugin agnostic library for NFL Game Pass and Game Rewind support.
"""
import cookielib
import hashlib
import random
import requests2 as requests
from traceback import format_exc
from urlparse import urlsplit
from uuid import getnode as get_mac
import xmltodict

class pigskin:
    def __init__(self, subscription, cookiefile, debug=False):
        self.subscription = subscription
        self.debug = debug

        if subscription == 'gamepass':
            self.base_url = 'https://gamepass.nfl.com/nflgp'
            self.seasonal_shows = {
                'NFL Gameday': {'2014': '212', '2013': '179', '2012': '146'},
                'Playbook': {'2014': '213', '2013': '180', '2012': '147'},
                'NFL Total Access': {'2014': '214', '2013': '181', '2012': '148'},
                'NFL RedZone Archives': {'2014': '221', '2013': '182', '2012': '149'},
                'Sound FX': {'2014': '215', '2013': '183', '2012': '150'},
                'Coaches Show': {'2014': '216', '2013': '184', '2012': '151'},
                'Top 100 Players': {'2014': '217', '2013': '185', '2012': '153'},
                'A Football Life': {'2014': '218', '2013': '186', '2012': '154'},
                'NFL Films Presents': {'2014': '219', '2013': '187'},
                'Hard Knocks': {'2014': '220'}
            }
        elif subscription == 'gamerewind':
            self.base_url = 'https://gamerewind.nfl.com/nflgr'
            self.seasonal_shows = {
                'NFL Gameday': {'2014': '212', '2013': '179', '2012': '146'},
                'Top 100 Players': {'2014': '217', '2013': '185', '2012': '153'}
            }
        else:
            raise ValueError('"%s" is not a supported subscription.' %subscription)

        self.non_seasonal_shows = { 'Super Bowl Archives': '117' }
        self.servlets_url = self.base_url.replace('https', 'http')

        self.http_session = requests.Session()
        self.cookie_jar = cookielib.LWPCookieJar(cookiefile)
        try:
            self.cookie_jar.load(ignore_discard=True, ignore_expires=True)
        except IOError:
            pass
        self.http_session.cookies = self.cookie_jar

    class LoginFailure(Exception):
        def __init__(self, value):
            self.value = value
        def __str__(self):
            return repr(self.value)

    def log(self, string):
        if self.debug:
            print '[pigskin]: %s' %string

    def check_for_subscription(self):
        sc_url = self.servlets_url + '/servlets/simpleconsole'
        sc_data = self.make_request(sc_url, {'isFlex': 'true'})

        if '</subscription>' in sc_data:
            self.log('Subscription detected.')
            return True
        else:
            self.log('No subscription was detected.')
            return False

    # The plid parameter used when requesting the video path appears to be an MD5 of... something.
    # I don't know what it is an "id" of, since the value seems to change constantly.
    # Reusing a plid doesn't work, so I'm guessing it's a unique id for the /instance/ of the player.
    # This pseudorandom approach seems to work.
    def gen_plid(self):
        rand = random.getrandbits(10)
        mac_address = str(get_mac())
        m = hashlib.md5(str(rand) + mac_address)
        return m.hexdigest()

    # the XML manifest of all available streams for a game
    def get_manifest(self, video_path):
        parsed_url = urlsplit(video_path)
        url = 'http://' + parsed_url.netloc + '/play?url=' + parsed_url.path + '&' + parsed_url.query
        manifest_data = self.make_request(url)
        return manifest_data

    # Returns the current season and week_code in a dict
    # e.g. {'2014': '210'}
    def get_current_season_and_week(self):
        sc_url = self.servlets_url + '/servlets/simpleconsole'
        sc_data = self.make_request(sc_url, {'isFlex': 'true'})

        sc_dict = xmltodict.parse(sc_data)['result']
        current_s_w = {sc_dict['currentSeason']: sc_dict['currentWeek']}
        return current_s_w

    def get_episode_manifest(self, url):
        xml_manifest = self.get_manifest(url)
        stream_manifest = self.parse_manifest(xml_manifest)
        return stream_manifest

    def get_game_manifest(self, game_id):
        set_cookies = self.get_current_season_and_week()
        video_path = self.get_video_path(game_id)
        xml_manifest = self.get_manifest(video_path)
        stream_manifest = self.parse_manifest(xml_manifest)
        return stream_manifest

    def get_live_url(self, game_id, bitrate):
        set_cookies = self.get_current_season_and_week()
        url = "http://gamepass.nfl.com/nflgp/servlets/publishpoint"

        if game_id == 'nfl_network':
            post_data = {'id': '1', 'type': 'channel', 'nt': '1'}
        elif game_id == 'rz':
            post_data = {'id': '2', 'type': 'channel', 'nt': '1'}
        else:
            post_data = {'id': game_id, 'type': 'game', 'nt': '1', 'gt': 'live'}

        headers = {'User-Agent': 'Android'}
        m3u8_data = self.make_request(url, post_data, headers)
        m3u8_dict = xmltodict.parse(m3u8_data)['result']
        self.log('NFL Dict %s' %m3u8_dict)
        m3u8_url = m3u8_dict['path'].replace('adaptive://', 'http://')
        return m3u8_url.replace('androidtab', bitrate)

    def get_shows(self, season):
        seasons_shows = self.non_seasonal_shows.keys()
        for show_name, show_codes in self.seasonal_shows.items():
            if season in show_codes:
                seasons_shows.append(show_name)

        return sorted(seasons_shows)

    # get episodes of archived NFL Network and RedZone shows
    # returns an empty list if no episodes are found or the showname/season are invalid
    def get_shows_episodes(self, show_name, season=None):
        url = 'http://gamepass.nfl.com/nflgp/servlets/browse'
        try:
            cid = self.seasonal_shows[show_name][season]
        except KeyError:
            try:
                cid = self.non_seasonal_shows[show_name]
            except KeyError:
                return []

        if show_name == 'NFL RedZone Archives':
            ps = 17
        else:
            ps = 50

        post_data = {
            'isFlex': 'true',
            'cid': cid,
            'pm': 0,
            'ps': ps,
            'pn': 1
        }

        archive_data = self.make_request(url, post_data)
        archive_dict = xmltodict.parse(archive_data)['result']

        count = int(archive_dict['paging']['count'])
        if count >= 1:
            items = archive_dict['programs']['program']
            # if only one episode is returned, we explicitly put it into a list
            if isinstance(items, dict):
                items = [items]
            return items
        else:
            return []

    def get_seasons_and_weeks(self):
        seasons_and_weeks = {}

        try:
            url = 'http://smb.cdnak.neulion.com/fs/nfl/nfl/mobile/weeks_v2.xml'
            s_w_data = self.make_request(url)
            s_w_data_dict = xmltodict.parse(s_w_data)
        except:
            self.log('Acquiring season and week data failed.')
            raise

        try:
            for season in s_w_data_dict['seasons']['season']:
                year = season['@season']
                season_dict = {}

                for week in season['week']:
                    if week['@section'] == "pre": # preseason
                        week_code = '1' + week['@value'].zfill(2)
                        season_dict[week_code] = week
                    else: # regular season and post season
                        week_code = '2' + week['@value'].zfill(2)
                        season_dict[week_code] = week

                seasons_and_weeks[year] = season_dict
        except KeyError:
            self.log('Parsing season and week data failed.')
            raise

        return seasons_and_weeks

    # the "video path" provides the info necessary to request the stream's manifest
    def get_video_path(self, game_id):
        url = self.servlets_url + '/servlets/encryptvideopath'
        plid = self.gen_plid()
        post_data = {
            'path': game_id,
            'plid': plid,
            'type': 'fgpa',
            'isFlex': 'true'
        }
        video_path_data = self.make_request(url, post_data)

        try:
            video_path_dict = xmltodict.parse(video_path_data)['result']
            self.log('Video Path Acquired Successfully.')
            return video_path_dict['path']
        except:
            self.log('Video Path Acquisition Failed.')
            return False

    # season is in format: YYYY
    # week is in format 101 (1st week preseason) or 213 (13th week of regular season)
    def get_weeks_games(self, season, week):
        url = self.servlets_url + '/servlets/games'
        post_data = {
            'isFlex': 'true',
            'season': season,
            'week': week
        }

        game_data = self.make_request(url, post_data)
        game_data_dict = xmltodict.parse(game_data)['result']
        games = game_data_dict['games']['game']
        # if only one game is returned, we explicitly put it into a list
        if isinstance(games, dict):
            games = [games]

        return games

    # Handles neccesary steps and checks to login to Game Pass/Rewind
    def login(self, username=None, password=None):
        if self.check_for_subscription():
            self.log('Already logged into %s' %self.subscription)
        else:
            if username and password:
                self.log('Not (yet) logged into %s' %self.subscription)
                self.login_to_account(username, password)
                if not self.check_for_subscription():
                    raise self.LoginFailure('%s login failed' %self.subscription)
                elif self.subscription == 'gamerewind' and self.service_blackout():
                    raise LoginFailure('Game Rewind Blackout')
            else:
                # might need sans-login check here for gamepass, though I hope the intial
                # subscription check works for sans-login regions. Also, as of 2014, there
                # may no longer be any sans-login regions, so it all could be moot.
                self.log('No username and password supplied.')
                raise self.LoginFailure('No username and password supplied.')

    # NFL Game Pass/Rewind "helpfully" does not give any indication whether the
    # login was successful or not. Thus, check_for_subscription() should be used
    # afterwards to determine success or failure.
    def login_to_account(self, username, password):
        url = 'https://id.s.nfl.com/login'
        post_data = {
            'username': username,
            'password': password,
            'vendor_id': 'nflptnrnln',
            'error_url': self.base_url + '/secure/login?redirect=loginform&redirectnosub=packages&redirectsub=schedule',
            'success_url': self.base_url + '/secure/login?redirect=loginform&redirectnosub=packages&redirectsub=schedule'
        }
        login_data = self.make_request(url, post_data)

    def make_request(self, url, payload=None, headers=None):
        self.log('Request URL: %s' %url)
        self.log('Headers: %s' %headers)

        try:
            r = self.http_session.post(url, data=payload, headers=headers, allow_redirects=False)
            self.log('Response code: %s' %r.status_code)
            self.log('Response: %s' %r.text)
            self.cookie_jar.save(ignore_discard=True, ignore_expires=False)
            return r.text
        except requests.exceptions.RequestException as e:
            self.log('Error: - %s' %e)

    def parse_manifest(self, manifest):
        streams = {}
        manifest_dict = xmltodict.parse(manifest)

        for stream in manifest_dict['channel']['streamDatas']['streamData']:
            try:
                url_path = stream['@url']
                bitrate = url_path[(url_path.rindex('_') + 1):url_path.rindex('.')]
                stream['full_url'] = 'http://%s%s.m3u8' %(stream['httpservers']['httpserver']['@name'], url_path)
                streams[bitrate] = stream
            except KeyError:
                self.log(format_exc())

        return streams

    # Check whether RedZone is on Air
    def redzone_on_air(self):
        sc_url = self.servlets_url + '/servlets/simpleconsole'
        sc_data = self.make_request(sc_url, {'isFlex': 'true'})

        sc_dict = xmltodict.parse(sc_data)['result']
        if sc_dict['rzPhase'] == 'in':
            self.log('RedZone is on air.')
            return True
        else:
            self.log('RedZone is not on air.')
            return False

    # Check if Game Rewind service is blacked-out due to live games in progress
    def service_blackout(self):
        url = self.base_url + '/secure/schedule'
        blackout_message = ('Due to broadcast restrictions, the NFL Game Rewind service is currently unavailable.'
                            ' Please check back later.')
        service_data = self.make_request(url)

        if blackout_message in service_data:
            return True
        else:
            return False
