"""An API Client to interact with ZoneMinder."""
import logging
from typing import List, Optional
from urllib.parse import urljoin
from urllib.parse import quote

import requests

from zoneminder.monitor import Monitor
from zoneminder.run_state import RunState
from zoneminder.exceptions import ControlTypeError, MonitorControlTypeError

_LOGGER = logging.getLogger(__name__)


class ZoneMinder:
    """The ZoneMinder API client itself. Create one of these to begin."""

    DEFAULT_SERVER_PATH = "/zm/"
    DEFAULT_ZMS_PATH = "/zm/cgi-bin/nph-zms"
    DEFAULT_TIMEOUT = 10
    LOGIN_RETRIES = 2
    MONITOR_URL = "api/monitors.json"

    def __init__(
        self,
        server_host,
        username,
        password,
        server_path=DEFAULT_SERVER_PATH,
        zms_path=DEFAULT_ZMS_PATH,
        verify_ssl=True,
    ) -> None:
        """Create a ZoneMinder API Client."""
        self._server_url = ZoneMinder._build_server_url(server_host, server_path)
        self._zms_url = ZoneMinder._build_zms_url(server_host, zms_path)
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._cookies = None
        self._auth_token = None

    def login(self):
        """Login to the ZoneMinder API."""
        _LOGGER.debug("Attempting to login to ZoneMinder")

        login_post = {}
        if self._username:
            login_post["user"] = self._username
        if self._password:
            login_post["pass"] = self._password

        req = requests.post(
            urljoin(self._server_url, "api/host/login.json"),
            data=login_post,
            verify=self._verify_ssl,
        )
        if req.ok:
            try:
                self._auth_token = req.json()["access_token"]
                return True
            except KeyError:
                # Try legacy auth below
                pass

        return self._legacy_auth()

    def _legacy_auth(self):
        login_post = {"view": "console", "action": "login"}
        if self._username:
            login_post["username"] = self._username
        if self._password:
            login_post["password"] = self._password

        req = requests.post(
            urljoin(self._server_url, "index.php"),
            data=login_post,
            verify=self._verify_ssl,
        )
        self._cookies = req.cookies

        # Login calls returns a 200 response on both failure and success.
        # The only way to tell if you logged in correctly is to issue an api
        # call.
        req = requests.get(
            urljoin(self._server_url, "api/host/getVersion.json"),
            cookies=self._cookies,
            timeout=ZoneMinder.DEFAULT_TIMEOUT,
            verify=self._verify_ssl,
        )

        if not req.ok:
            _LOGGER.error("Connection error logging into ZoneMinder")
            return False

        return True

    def get_state(self, api_url) -> dict:
        """Perform a GET request on the specified ZoneMinder API URL."""
        return self._zm_request("get", api_url)

    def change_state(self, api_url, post_data) -> dict:
        """Perform a POST request on the specific ZoneMinder API Url."""
        return self._zm_request("post", api_url, post_data)

    def _zm_request(self, method, api_url, data=None, timeout=DEFAULT_TIMEOUT) -> dict:
        """Perform a request to the ZoneMinder API."""
        token_url_suffix = ""
        if self._auth_token:
            token_url_suffix = "?token=" + self._auth_token
        try:
            # Since the API uses sessions that expire, sometimes we need to
            # re-auth if the call fails.
            for _ in range(ZoneMinder.LOGIN_RETRIES):
                req = requests.request(
                    method,
                    urljoin(self._server_url, api_url) + token_url_suffix,
                    data=data,
                    cookies=self._cookies,
                    timeout=timeout,
                    verify=self._verify_ssl,
                )

                if not req.ok:
                    self.login()
                else:
                    break

            else:
                _LOGGER.error("Unable to get API response from ZoneMinder")

            try:
                return req.json()
            except ValueError:
                _LOGGER.exception(
                    "JSON decode exception caught while" 'attempting to decode "%s"',
                    req.text,
                )
                return {}
        except requests.exceptions.ConnectionError:
            _LOGGER.exception("Unable to connect to ZoneMinder")
            return {}

    def get_monitors(self) -> List[Monitor]:
        """Get a list of Monitors from the ZoneMinder API."""
        raw_monitors = self._zm_request("get", ZoneMinder.MONITOR_URL)
        if not raw_monitors:
            _LOGGER.warning("Could not fetch monitors from ZoneMinder")
            return []

        monitors = []
        for raw_result in raw_monitors["monitors"]:
            _LOGGER.debug("Initializing camera %s", raw_result["Monitor"]["Id"])
            monitors.append(Monitor(self, raw_result))

        return monitors

    def get_run_states(self) -> List[RunState]:
        """Get a list of RunStates from the ZoneMinder API."""
        raw_states = self.get_state("api/states.json")
        if not raw_states:
            _LOGGER.warning("Could not fetch runstates from ZoneMinder")
            return []

        run_states = []
        for i in raw_states["states"]:
            raw_state = i["State"]
            _LOGGER.info("Initializing runstate %s", raw_state["Id"])
            run_states.append(RunState(self, raw_state))

        return run_states

    def get_active_state(self) -> Optional[str]:
        """Get the name of the active run state from the ZoneMinder API."""
        for state in self.get_run_states():
            if state.active:
                return state.name
        return None

    def set_active_state(self, state_name):
        """
        Set the ZoneMinder run state to the given state name, via ZM API.

        Note that this is a long-running API call; ZoneMinder changes the state
        of each camera in turn, and this GET does not receive a response until
        all cameras have been updated. Even on a reasonably powerful machine,
        this call can take ten (10) or more seconds **per camera**. This method
        sets a timeout of 120, which should be adequate for most users.
        """
        _LOGGER.info("Setting ZoneMinder run state to state %s", state_name)
        return self._zm_request("GET", "api/states/change/{}.json".format(state_name), timeout=120)

    def get_zms_url(self) -> str:
        """Get the url to the current ZMS instance."""
        return self._zms_url

    def get_url_with_auth(self, url) -> str:
        """Add the auth credentials to a url (if needed)."""
        if not self._username:
            return url

        url += "&user={:s}".format(quote(self._username))

        if not self._password:
            return url
        return url + "&pass={:s}".format(quote(self._password))

    @property
    def is_available(self) -> bool:
        """Indicate if this ZoneMinder service is currently available."""
        status_response = self.get_state("api/host/daemonCheck.json")

        if not status_response:
            return False

        return status_response.get("result") == 1

    @property
    def verify_ssl(self) -> bool:
        """Indicate whether urls with http(s) should verify the certificate."""
        return self._verify_ssl

    @staticmethod
    def _build_zms_url(server_host, zms_path) -> str:
        """Build the ZMS url to the current ZMS instance."""
        return urljoin(server_host, zms_path)

    @staticmethod
    def _build_server_url(server_host, server_path) -> str:
        """Build the server url making sure it ends in a trailing slash."""
        server_url = urljoin(server_host, server_path)
        if server_url[-1] == "/":
            return server_url
        return "{}/".format(server_url)

    def move_monitor(self, monitor: Monitor, direction: str):
        """Call Zoneminder to move."""
        try:
            result = monitor.ptz_control_command(direction, self._auth_token, self._server_url)
            if result:
                _LOGGER.info("Success to move camera to %s", direction)
            else:
                _LOGGER.error("Impossible to move camera to %s", direction)
        except ControlTypeError:
            _LOGGER.exception("Impossible move monitor")
        except MonitorControlTypeError:
            _LOGGER.exception("Impossible to use direction")
