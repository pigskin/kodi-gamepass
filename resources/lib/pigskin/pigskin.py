"""
A Python library for NFL Game Pass
"""
import uuid
import sys
import json
import calendar
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
try:
    from urllib.parse import urlencode
except ImportError:  # Python 2.7
    from urllib import urlencode

import requests
import m3u8


class pigskin(object):
    def __init__(
            self,
            proxy_url=None
        ):
        self.logger = logging.getLogger(__name__)
        self.ch = logging.StreamHandler()
        self.ch.setLevel(logging.INFO)
        self.logger.addHandler(self.ch)

        self.base_url = 'https://www.nflgamepass.com'
        self.user_agent = 'Firefox'
        self.http_session = requests.Session()
        self.http_session.proxies['http'] = proxy_url
        self.http_session.proxies['https'] = proxy_url

        self.access_token = None
        self.refresh_token = None
        self.config = self.populate_config()
        self.nfln_shows = {}
        self.episode_list = []

        self.logger.debug('Python Version: %s' % sys.version)

    class GamePassError(Exception):
        def __init__(self, value):
            self.value = value

        def __str__(self):
            return repr(self.value)


    def populate_config(self):
        url = self.base_url + '/api/en/content/v1/web/config'
        r = self.http_session.get(url)
        return r.json()


    def _log_request(self, r):
        """Log (at the debug level) everything about a provided HTTP request.

        Note
        ----
        TODO: optional password filtering

        Parameters
        ----------
        r : requests.models.Response
            The handle of a Requests request.

        Returns
        -------
        bool
            True if successful

        Examples
        --------
        >>> r = self.http_session.get(url)
        >>> self._log_request(r)
        """
        request_dict = {}
        response_dict = {}
        if type(r) == requests.models.Response:
            request_dict['body'] = r.request.body
            request_dict['headers'] = dict(r.request.headers)
            request_dict['method'] = r.request.method
            request_dict['uri'] = r.request.url

            try:
                response_dict['body'] = r.json()
            except ValueError:
                response_dict['body'] = str(r.content)
            response_dict['headers'] = dict(r.headers)
            response_dict['status_code'] = r.status_code

        self.logger.debug('request:')
        try:
            self.logger.debug(json.dumps(request_dict, sort_keys=True, indent=4))
        except UnicodeDecodeError:  # python 2.7
            request_dict['body'] = 'BINARY DATA'
            self.logger.debug(json.dumps(request_dict, sort_keys=True, indent=4))

        self.logger.debug('response:')
        try:
            self.logger.debug(json.dumps(response_dict, sort_keys=True, indent=4))
        except UnicodeDecodeError:  # python 2.7
            response_dict['body'] = 'BINARY DATA'
            self.logger.debug(json.dumps(response_dict, sort_keys=True, indent=4))

        return True


    def make_request(self, url, method, params=None, payload=None, headers=None):
        """Make an HTTP request. Return the response."""
        self.logger.debug('Request URL: %s' % url)
        self.logger.debug('Method: %s' % method)
        if params:
            self.logger.debug('Params: %s' % params)
        if payload:
            if 'password' in payload:
                password = payload['password']
                payload['password'] = 'xxxxxxxxxxxx'
            self.logger.debug('Payload: %s' % payload)
            if 'password' in payload:
                payload['password'] = password
        if headers:
            self.logger.debug('Headers: %s' % headers)

        # requests session implements connection pooling, after being idle for
        # some time the connection might be closed server side.
        # In case it's the servers being very slow, the timeout should fail fast
        # and retry with longer timeout.
        failed = False
        for t in [3, 22]:
            try:
                if method == 'get':
                    req = self.http_session.get(url, params=params, headers=headers, timeout=t)
                elif method == 'put':
                    req = self.http_session.put(url, params=params, data=payload, headers=headers, timeout=t)
                else:  # post
                    req = self.http_session.post(url, params=params, data=payload, headers=headers, timeout=t)
                # We made it without error, exit the loop
                break
            except requests.Timeout:
                self.logger.warning('Timeout condition occurred after %i seconds' % t)
                if failed:
                    # failed twice while sending request
                    # TODO: this should be raised so the user can be informed.
                    pass
                else:
                    failed = True
            except:
                # something else went wrong, not a timeout
                # TODO: raise this
                pass

        self.logger.debug('Response code: %s' % req.status_code)
        self.logger.debug('Response: %s' % req.content)

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
                    if response[key]:  # raise all messages as GamePassError if message is not empty
                        raise self.GamePassError(response[key])

        return response

    def login(self, username, password):
        """Login to NFL Game Pass.

        Note
        ----
        A successful login does not necessarily mean that access to content is
        granted (i.e. has a valid subscription). Use ``check_for_subscription()``
        to determine if access has been granted.

        Parameters
        ----------
        username : str
            Your NFL Game Pass username.
        password : str
            The user's password.

        Returns
        -------
        bool
            True if successful, False otherwise.
        """
        url = self.config['modules']['API']['LOGIN']
        post_data = {
            'client_id': self.config['modules']['API']['CLIENT_ID'],
            'username': username,
            'password': password,
            'grant_type': 'password'
        }

        try:
            r = self.http_session.post(url, data=post_data)
            self._log_request(r)
            data = r.json()
        except ValueError:
            self.logger.error('login: server response is invalid')
            return False
        except Exception as e:
            raise e

        try:
            # TODO: are these tokens provided for valid accounts without a subscription?
            self.access_token = data['access_token']
            self.refresh_token = data['refresh_token']
        except KeyError:
            self.logger.error('could not acquire GP tokens')
            self.logger.error('login failed')
            return False
        except Exception as e:
            raise e

        # TODO: check for status codes, just in case

        self.logger.debug('login was successful')
        return True


    def check_for_subscription(self):
        """Return True if a subscription is detected and raise 'no_subscription' on failure."""
        url = self.config['modules']['API']['USER_ACCOUNT']
        headers = {'Authorization': 'Bearer {0}'.format(self.access_token)}
        account_data = self.make_request(url, 'get', headers=headers)

        try:
            self.logger.debug('subscription: %s' % account_data['subscriptions'])
            return True
        except TypeError:
            self.logger.error('No active NFL Game Pass Europe subscription was found.')
            raise self.GamePassError('no_subscription')


    def refresh_tokens(self):
        """Refresh the ``access`` and ``refresh`` tokens to access content.

        Returns
        -------
        bool
            True if successful, False otherwise.
        """
        url = self.config['modules']['API']['REFRESH_TOKEN']
        post_data = {
            'client_id': self.config['modules']['API']['CLIENT_ID'],
            'refresh_token': self.refresh_token,
            'grant_type': 'refresh_token'
        }

        try:
            r = self.http_session.post(url, data=post_data)
            self._log_request(r)
            data = r.json()
        except ValueError:
            self.logger.error('token refresh: server response is invalid')
            return False
        except Exception as e:
            raise e

        try:
            self.access_token = data['access_token']
            self.refresh_token = data['refresh_token']
        except KeyError:
            self.logger.error('could not find GP tokens to refresh')
            return False
        except Exception as e:
            raise e

        # TODO: check for status codes, just in case

        self.logger.debug('successfully refreshed tokens')
        return True


    def get_seasons(self):
        """Get a list of available seasons.

        Returns
        -------
        list
            a list of available seasons, sorted from the most to least recent;
            empty if there was a failure.
        """
        url = self.config['modules']['ROUTES_DATA_PROVIDERS']['games']
        seasons = []

        try:
            r = self.http_session.get(url)
            self._log_request(r)
            data = r.json()
        except ValueError:
            self.logger.error('')
            return []
        except Exception as e:
            raise e

        try:
            self.logger.debug('parsing seasons')
            giga_list = data['modules']['mainMenu']['seasonStructureList']
            seasons = [str(x['season']) for x in giga_list if x.get('season') != None]
            seasons.sort(reverse=True)
        except KeyError:
            self.logger.error('unable to find the seasons list')
            return []
        except Exception as e:
            raise e

        return seasons


    def get_weeks(self, season):
        """Get the weeks of a given season.
        Parameters
        ----------
        season : int or str
            The season can be provided as either a ``str`` or ``int``.

        Returns
        -------
        dict
            with the ``pre``, ``reg``, and ``post`` fields populated with dicts
            containing the week's number (key) and the week's abbreviation
            (value). Empty if there was a failure.

        Examples
        --------
        >>> weeks = gp.get_weeks(2017)
        >>> print(weeks['pre']['0']
        'hof'
        >>> print(weeks['reg']['8']
        'weeks'
        >>> print(weeks['post']'22']
        'sb'
        """
        url = self.config['modules']['ROUTES_DATA_PROVIDERS']['games']
        weeks = {}

        try:
            r = self.http_session.get(url)
            self._log_request(r)
            data = r.json()
        except ValueError:
            self.logger.error('')
            return []
        except Exception as e:
            raise e

        try:
            self.logger.debug('parsing week list')

            giga_list = data['modules']['mainMenu']['seasonStructureList']
            season_types_list = [x['seasonTypes'] for x in giga_list if x.get('season') == int(season)][0]

            for st in season_types_list:
                if st['seasonType'] == 'pre':
                    weeks['pre'] = { str(w['number']) : w['weekNameAbbr'] for w in st['weeks'] }
                elif st['seasonType'] == 'reg':
                    weeks['reg'] = { str(w['number']) : w['weekNameAbbr'] for w in st['weeks'] }
                elif st['seasonType'] == 'post':
                    weeks['post'] = { str(w['number']) : w['weekNameAbbr'] for w in st['weeks'] }
                else:
                    self.logger.warning('found an unexpected season type')
        except KeyError:
            self.logger.error("unable to find the season's week-list")
            return {}
        except Exception as e:
            raise e

        return weeks


    def get_current_season_and_week(self):
        """Get the current season (year), season type, and week.

        Returns
        -------
        dict
            with the ``season``, ``season_type``, and ``week`` fields populated
            if successful; empty if otherwise.
        """
        url = self.config['modules']['ROUTES_DATA_PROVIDERS']['games']
        current = {}

        try:
            r = self.http_session.get(url)
            self._log_request(r)
            data = r.json()
        except ValueError:
            self.logger.error('current_season_and_week: server response is invalid')
            return {}
        except Exception as e:
            raise e

        try:
            current = {
                'season': data['modules']['meta']['currentContext']['currentSeason'],
                'season_type': data['modules']['meta']['currentContext']['currentSeasonType'],
                'week': str(data['modules']['meta']['currentContext']['currentWeek'])
            }
        except KeyError:
            self.logger.error('could not determine the current season and week')
            return {}
        except Exception as e:
            raise e

        return current


    def get_games(self, season, season_type, week):
        """Get the raw game data for a given season (year), season type, and week.

        Parameters
        ----------
        season : str or int
            The season can be provided as either a ``str`` or ``int``.
        season_type : str
            The season_type can be either ``pre``, ``reg``, or ``post``.
        week : str or int
            The week can be provided as either a ``str`` or ``int``.

        Returns
        -------
        list
            of dicts with the metadata for each game

        Note
        ----
        TODO: the data returned really should be normalized, rather than a
        (nearly) straight dump of the raw data.

        Examples
        --------
        >>> games = gp.get_games(2017, 'reg', 1)
        >>> print(games[1]['video']['title'])
        New York Jets @ Buffalo Bills
        """
        url = self.config['modules']['ROUTES_DATA_PROVIDERS']['games_detail']
        url = url.replace(':seasonType', season_type).replace(':season', str(season)).replace(':week', str(week))
        games = []

        try:
            r = self.http_session.get(url)
            self._log_request(r)
            data = r.json()
        except ValueError:
            self.logger.error('get_games: server response is invalid')
            return []
        except Exception as e:
            raise e

        try:
            games = [g for x in data['modules'] if data['modules'][x].get('content') for g in data['modules'][x]['content']]
            games = sorted(games, key=lambda x: x['gameDateTimeUtc'])
        except KeyError:
            self.logger.error('could not parse/build the games list')
            self.logger.error('')
            return []
        except Exception as e:
            raise e

        return games


    def get_team_games(self, season, team):
        """Get the raw game data for a given season (year) and team.

        Parameters
        ----------
        season : str or int
            The season can be provided as either a ``str`` or ``int``.
        team : str
            Accepts the team ``seo_name``. For a list of team seo names, see
            self.config['modules']['ROUTES_DATA_PROVIDERS']['team_detail'].

        Returns
        -------
        list
            of dicts with the metadata for each game

        Note
        ----
        TODO: the data returned really should be normalized, rather than a
              (nearly) straight dump of the raw data.
        TODO: currently only the current season is supported
        TODO: create a ``get_team_seo_name()`` helper

        See Also
        --------
        ``get_current_season_and_week()``

        Examples
        --------
        >>> games = gp.get_team_games(2018, '49ers')
        >>> print(games[2]['weekName'])
        Preseason Week 3
        """
        url = self.config['modules']['ROUTES_DATA_PROVIDERS']['team_detail']
        url = url.replace(':team', team)
        games = []

        # TODO: bail if ``season`` isn't the current season

        try:
            r = self.http_session.get(url)
            self._log_request(r)
            data = r.json()
        except ValueError:
            self.logger.error('get_team_games: server response is invalid')
            return []
        except Exception as e:
            raise e

        try:
            # currently, only data for the current season is available
            games = [x for x in data['modules']['gamesCurrentSeason']['content']]
            games = sorted(games, key=lambda x: x['gameDateTimeUtc'])
        except KeyError:
            self.logger.error('could not parse/build the team_games list')
            return []
        except Exception as e:
            raise e

        return games


    def get_game_versions(self, game_id, season):
        """Return a dict of available game versions (full, condensed, coaches,
        etc) for a game.

        Parameters
        ----------
        season : str or int
            The season can be provided as either a ``str`` or ``int``.
        game_id : str or int
            A game's ``game_id`` can be found in the metadata returned by either
            ``get_games()`` or ``get_team_games()``.

        Returns
        -------
        dict
            with the ``key`` as game version and its ``value`` being the
            ``video_id`` of the corresponding stream.

        See Also
        --------
        ``get_games()``
        ``get_team_games()``

        Examples
        --------
        >>> versions = gp.get_game_versions('2017090700', '2017')
        >>> print(versions.keys())
        dict_keys(['Coach film', 'Condensed game', 'Game video'])
        """
        url = self.config['modules']['ROUTES_DATA_PROVIDERS']['game_page']
        url = url.replace(':gameslug', str(game_id)).replace(':season', str(season))
        versions = {}

        try:
            r = self.http_session.get(url)
            self._log_request(r)
            data = r.json()
        except ValueError:
            self.logger.error('get_game_versions: server response is invalid')
            return {}
        except Exception as e:
            raise e

        try:
            game_data = data['modules']['singlegame']['content'][0]
            for key in game_data:
                try:
                    versions[game_data[key]['kind']] = game_data[key]['videoId']
                except (KeyError, TypeError):
                    pass
        except KeyError:
            self.logger.error('could not parse/build the game versions data')
            return {}
        except Exception as e:
            raise e

        self.logger.debug('Game versions found for {0}: {1}'.format(game_id, ', '.join(versions.keys())))
        return versions


    def get_streams(self, video_id, game_type=None, username=None):
        """Return a dict of available streams."""
        streams = {}
        m3u8_header = {
            'Connection': 'keep-alive',
            'User-Agent': self.user_agent
        }
        self.refresh_tokens()

        if video_id == 'nfl_network':
            diva_config_url = self.config['modules']['DIVA']['HTML5']['SETTINGS']['Live24x7']
            url = self.config['modules']['ROUTES_DATA_PROVIDERS']['network']
            response = self.make_request(url, 'get')
            video_id = response['modules']['networkLiveVideo']['content'][0]['videoId']
        elif video_id == 'redzone':
            diva_config_url = self.config['modules']['DIVA']['HTML5']['SETTINGS']['Live24x7']
            url = self.config['modules']['ROUTES_DATA_PROVIDERS']['redzone']
            response = self.make_request(url, 'get')
            video_id = response['modules']['redZoneLive']['content'][0]['videoId']
        else:
            if game_type == 'live':
                diva_config_url = self.config['modules']['DIVA']['HTML5']['SETTINGS']['LiveNoData']
            else:
                diva_config_url = self.config['modules']['DIVA']['HTML5']['SETTINGS']['VodNoData']

        diva_config_data = self.make_request(diva_config_url.replace('device', 'html5'), 'get')
        diva_config_root = ET.fromstring(diva_config_data)
        for i in diva_config_root.iter('parameter'):
            if i.attrib['name'] == 'processingUrlCallPath':
                processing_url = i.attrib['value']
            elif i.attrib['name'] == 'videoDataPath':
                stream_request_url = i.attrib['value'].replace('{V.ID}', video_id)
        akamai_xml_data = self.make_request(stream_request_url, 'get')
        akamai_xml_root = ET.fromstring(akamai_xml_data)

        for i in akamai_xml_root.iter('videoSource'):
            try:
                vs_format = i.attrib['format'].lower()
                vs_url = i.findtext('uri')

                post_data = {
                    'Type': '1',
                    'User': '',
                    'VideoId': video_id,
                    'VideoSource': vs_url,
                    'VideoKind': 'Video',
                    'AssetState': '3',
                    'PlayerType': 'HTML5',
                    'other': '{0}|{1}|web|{1}|undefined|{2}' .format(str(uuid.uuid4()), self.access_token, self.user_agent, username)
                }
                response = self.make_request(processing_url, 'post', payload=json.dumps(post_data))

                streams[vs_format] = response['ContentUrl'] + '|' + urllib.urlencode(m3u8_header)

            except:
                pass

        return streams

    def m3u8_to_dict(self, manifest_url):
        """Return a dict of available bitrates and their respective stream. This
        is especially useful if you need to pass a URL to a player that doesn't
        support adaptive streaming."""
        streams = {}
        m3u8_header = {
            'Connection': 'keep-alive',
            'User-Agent': self.user_agent
        }

        m3u8_manifest = self.make_request(manifest_url, 'get')
        m3u8_obj = m3u8.loads(m3u8_manifest)
        for playlist in m3u8_obj.playlists:
            bitrate = int(playlist.stream_info.bandwidth) / 1000
            streams[bitrate] = manifest_url[:manifest_url.rfind('/manifest') + 1] + playlist.uri + '?' + manifest_url.split('?')[1] + '|' + urlencode(m3u8_header)

        return streams

    def redzone_on_air(self):
        """Return whether RedZone Live is currently broadcasting."""
        url = self.config['modules']['ROUTES_DATA_PROVIDERS']['redzone']
        response = self.make_request(url, 'get')
        if not response['modules']['redZoneLive']['content']:
            return False
        else:
            return True

    def parse_shows(self):
        """Dynamically parse the NFL Network shows into a dict."""
        show_dict = {}

        # NFL Network shows
        url = self.config['modules']['API']['NETWORK_PROGRAMS']
        response = self.make_request(url, 'get')
        current_season = self.get_current_season_and_week()['season']

        for show in response['modules']['programs']:
            # Unfortunately, the 'seasons' list for each show cannot be trusted.
            # So we loop over every episode for every show to build the list.
            # TODO: this causes a lot of network traffic and slows down init
            #       quite a bit. Would be nice to have a better workaround.
            request_url = self.config['modules']['API']['NETWORK_EPISODES']
            episodes_url = request_url.replace(':seasonSlug/', '').replace(':tvShowSlug', show['slug'])
            episodes_data = self.make_request(episodes_url, 'get')['modules']['archive']['content']

            # 'season' is often left unset. It's impossible to know for sure,
            # but the year of the current Season seems like a sane best guess.
            season_list = set([episode['season'].replace('season-', '')
                               if episode['season'] else current_season
                               for episode in episodes_data])

            show_dict[show['title']] = season_list

            # Adding NFL-Network as a List of dictionary containing oher dictionaries.
            # episode_thumbnail = {videoId, thumbnail}
            # episode_id_dict = {episodename, episode_thumbnail{}}
            # episode_season_dict = {episode_season, episode_id_dict{}}
            # show_season_dict = {show_title, episode_season_dict{}}
            # The Function returns all Season and Episodes
            for episode in episodes_data:
                episode_thumbnail = {}
                episode_id_dict = {}
                episode_season_dict = {}
                show_season_dict = {}
                episode_name = episode['title']
                episode_id = episode['videoId']
                if episode['season']:
                    episode_season = episode['season'].replace('season-', '')
                else:
                    episode_season = current_season
                # Using Episode Thumbnail if not present use theire corresponding Show Thumbnail
                if episode['videoThumbnail']['templateUrl']:
                    episode_thumbnail[episode_id] = episode['videoThumbnail']['templateUrl']
                else:
                    episode_thumbnail[episode_id] = show['thumbnail']['templateUrl']
                episode_id_dict[episode_name] = episode_thumbnail
                episode_season_dict[episode_season] = episode_id_dict
                show_season_dict[show['title']] = episode_season_dict
                self.episode_list.append(show_season_dict)

        # Adding RedZone as a List of dictionary containing oher dictionaries.
        # episode_thumbnail = {videoId, thumbnail}
        # episode_id_dict = {episodename, episode_thumbnail{}}
        # episode_season_dict = {episode_season, episode_id_dict{}}
        # show_season_dict = {show_title, episode_season_dict{}}
        # The Function returns all Season and Episodes
        url = self.config['modules']['ROUTES_DATA_PROVIDERS']['redzone']
        response = self.make_request(url, 'get')

        season_list = []
        for episode in response['modules']['redZoneVod']['content']:
            season_name = episode['season'].replace('season-', '')
            season_list.append(season_name)
            episode_thumbnail = {}
            episode_id_dict = {}
            episode_season_dict = {}
            show_season_dict = {}
            episode_name = episode['title']
            episode_id = episode['videoId']
            if episode['season']:
                episode_season = episode['season'].replace('season-', '')
            else:
                episode_season = current_season
            # Using Episode Thumbnail if not present use theire corresponding Show Thumbnail
            if episode['videoThumbnail']['templateUrl']:
                episode_thumbnail[episode_id] = episode['videoThumbnail']['templateUrl']
            else:
                episode_thumbnail[episode_id] = ''
            episode_id_dict[episode_name] = episode_thumbnail
            episode_season_dict[episode_season] = episode_id_dict
            show_season_dict['RedZone'] = episode_season_dict
            self.episode_list.append(show_season_dict)

        show_dict['RedZone'] = season_list
        self.nfln_shows.update(show_dict)

    def get_shows(self, season):
        """Return a list of all shows for a season."""
        seasons_shows = []

        for show_name, years in self.nfln_shows.items():
            if season in years:
                seasons_shows.append(show_name)

        return sorted(seasons_shows)

    def get_shows_episodes(self, show_name, season=None):
        """Return a list of episodes for a show. Return empty list if none are
        found or if an error occurs."""
        # Create a List of all games related to a specific show_name and a season.
        # The returning List contains episode name, episode id and episode thumbnail
        episodes_data = []
        for episode in self.episode_list:
            for dict_show_name, episode_season_dict in episode.items():
                if dict_show_name == show_name:
                    for episode_season, episode_id_dict in episode_season_dict.items():
                        if episode_season == season:
                            episodes_data.append(episode_id_dict)

        return episodes_data

    def parse_datetime(self, date_string, localize=False):
        """Parse NFL Game Pass date string to datetime object."""
        date_time_format = '%Y-%m-%dT%H:%M:%S.%fZ'
        datetime_obj = datetime(*(time.strptime(date_string, date_time_format)[0:6]))

        if localize:
            return self.utc_to_local(datetime_obj)

        return datetime_obj

    @staticmethod
    def utc_to_local(utc_dt):
        """Convert UTC time to local time."""
        # get integer timestamp to avoid precision lost
        timestamp = calendar.timegm(utc_dt.timetuple())
        local_dt = datetime.fromtimestamp(timestamp)
        assert utc_dt.resolution >= timedelta(microseconds=1)
        return local_dt.replace(microsecond=utc_dt.microsecond)
