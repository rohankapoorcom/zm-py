"""Provides an API to interact with ZoneMinder"""
from http.cookiejar import CookieJar
from urllib.parse import urljoin, urlencode

import requests
import logging

from requests import Response
from typing import Optional

_LOGGER = logging.getLogger(__name__)


class ZoneMinder:

    DEFAULT_SERVER_PATH: str = '/zm/'
    DEFAULT_ZMS_PATH: str = '/zm/cgi-bin/nph-zms'
    DEFAULT_TIMEOUT: int = 10
    LOGIN_RETRIES: int = 2
    # From ZoneMinder's web/includes/config.php.in
    ZM_STATE_ALARM: int = "2"

    def __init__(self, server_host: str, username: str, password: str, server_path: str = DEFAULT_SERVER_PATH,
                 zms_path: str = DEFAULT_ZMS_PATH, verify_ssl: bool = True) -> None:
        self._server_url: str = urljoin(server_host, server_path)
        self._username: str = username
        self._password: str = password
        self._zms_path: str = zms_path
        self._verify_ssl: bool = verify_ssl
        self._cookies: CookieJar = None

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
        # The only way to tell if you logged in correctly is to issue an api call.
        req = requests.get(
            urljoin(self._server_url, 'api/host/getVersion.json'), cookies=self._cookies,
            timeout=ZoneMinder.DEFAULT_TIMEOUT, verify=self._verify_ssl)

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
                cookies=self._cookies, timeout=ZoneMinder.DEFAULT_TIMEOUT, verify=self._verify_ssl)

            if not req.ok:
                self.login()
            else:
                break

        else:
            _LOGGER.error("Unable to get API response from ZoneMinder")

        try:
            return req.json()
        except ValueError:
            _LOGGER.exception('JSON decode exception caught while attempting to '
                              'decode "%s"', req.text)

    def _get_image_url(self, monitor, mode):
        """Build and return a Zoneminder camera image url"""
        query = urlencode({
            'mode': mode,
            'buffer': monitor['StreamReplayBuffer'],
            'monitor': monitor['Id'],
        })
        url = '{zms_url}?{query}'.format(
            zms_url=urljoin(self._server_url, self._zms_path),
            query=query,
        )
        _LOGGER.debug('Monitor %s %s URL (without auth): %s',
                      monitor['Id'], mode, url)

        if not self._username:
            return url

        url += '&user={:s}'.format(self._username)

        if not self._password:
            return url

        return url + '&pass={:s}'.format(self._password)

    def get_mjpeg_image_url(self, monitor):
        """Get a motion jpeg (mjpeg) image url"""
        return self._get_image_url(monitor, 'jpeg')

    def get_still_image_url(self, monitor):
        """Get a still jpeg image url"""
        return self._get_image_url(monitor, 'single')

    def is_recording(self, monitor_id: int) -> Optional[bool]:
        """Indicates if the requested monitor is currently recording"""
        status_response = self._zm_request(
            'get',
            'api/monitors/alarm/id:{}/command:status.json'.format(monitor_id)
        )

        if not status_response:
            _LOGGER.warning('Could not get status for monitor {}'.format(monitor_id))
            return None

        return status_response.get('status') == ZoneMinder.ZM_STATE_ALARM
