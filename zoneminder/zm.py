"""Provides an API to interact with ZoneMinder"""
import logging
from typing import Optional, List
from urllib.parse import urljoin

import requests
from requests import Response

from zoneminder.monitor import Monitor

_LOGGER = logging.getLogger(__name__)


class ZoneMinder:

    DEFAULT_SERVER_PATH = '/zm/'
    DEFAULT_ZMS_PATH = '/zm/cgi-bin/nph-zms'
    DEFAULT_TIMEOUT = 10
    LOGIN_RETRIES = 2
    # From ZoneMinder's web/includes/config.php.in
    ZM_STATE_ALARM = 2
    MONITOR_URL = 'api/monitors.json'

    def __init__(self, server_host, username, password,
                 server_path = DEFAULT_SERVER_PATH,
                 zms_path=DEFAULT_ZMS_PATH, verify_ssl=True) -> None:
        self._server_url = urljoin(server_host, server_path)
        self._username = username
        self._password = password
        self._zms_path = zms_path
        self._verify_ssl = verify_ssl
        self._cookies = None

    def login(self):
        """Login to the ZoneMinder API."""
        _LOGGER.debug("Attempting to login to ZoneMinder")

        login_post = {'view': 'console', 'action': 'login'}
        if self._username:
            login_post['username'] = self._username
        if self._password:
            login_post['password'] = self._password

        req: Response = requests.post(urljoin(self._server_url, '/index.php'),
                                      data=login_post, verify=self._verify_ssl)
        self._cookies = req.cookies

        # Login calls returns a 200 response on both failure and success.
        # The only way to tell if you logged in correctly is to issue an api
        # call.
        req = requests.get(
            urljoin(self._server_url, 'api/host/getVersion.json'),
            cookies=self._cookies,
            timeout=ZoneMinder.DEFAULT_TIMEOUT,
            verify=self._verify_ssl)

        if not req.ok:
            _LOGGER.error("Connection error logging into ZoneMinder")
            return False

        return True

    def _zm_request(self, method: str, api_url: str, data: dict=None):
        """Perform a request to the Zoneminder API."""
        # Since the API uses sessions that expire, sometimes we need to re-auth
        # if the call fails.
        _: int
        for _ in range(ZoneMinder.LOGIN_RETRIES):
            req: Response = requests.request(
                method, urljoin(self._server_url, api_url), data=data,
                cookies=self._cookies, timeout=ZoneMinder.DEFAULT_TIMEOUT,
                verify=self._verify_ssl)

            if not req.ok:
                self.login()
            else:
                break

        else:
            _LOGGER.error("Unable to get API response from ZoneMinder")

        try:
            return req.json()
        except ValueError:
            _LOGGER.exception('JSON decode exception caught while attempting '
                              'to decode "%s"', req.text)

    def is_recording(self, monitor_id) -> Optional[bool]:
        """Indicates if the requested monitor is currently recording"""
        status_response = self._zm_request(
            'get',
            'api/monitors/alarm/id:{}/command:status.json'.format(monitor_id)
        )

        if not status_response:
            _LOGGER.warning('Could not get status for monitor {}'.format(
                monitor_id))
            return None

        return int(status_response.get('status')) == ZoneMinder.ZM_STATE_ALARM

    def get_monitors(self) -> List[Monitor]:
        raw_monitors = self._zm_request('get', ZoneMinder.MONITOR_URL)
        if not raw_monitors:
            _LOGGER.warning("Could not fetch monitors from ZoneMinder")
            return []

        zms_url = urljoin(self._server_url, self._zms_path)
        monitors = []
        for i in raw_monitors['monitors']:
            m = i['Monitor']

            if m['Function'] == 'None':
                _LOGGER.info("Skipping camera %s", m['Id'])
                continue

            _LOGGER.info("Initializing camera %s", m['Id'])
            monitors.append(
                Monitor(m, zms_url, self._username, self._password))

        return monitors
