"""An API Client to interact with ZoneMinder."""

from __future__ import annotations

import logging
import time
from urllib.parse import quote, urljoin

import requests

from zoneminder.monitor import Monitor, TimePeriod, get_api_alarm_states
from zoneminder.run_state import RunState
from zoneminder.server import Server

_LOGGER = logging.getLogger(__name__)


class ZoneMinder:
    """The ZoneMinder API client itself. Create one of these to begin."""

    DEFAULT_SERVER_PATH = "/zm/"
    DEFAULT_ZMS_PATH = "/zm/cgi-bin/nph-zms"
    DEFAULT_TIMEOUT = 10
    LOGIN_RETRIES = 2
    MONITOR_URL = "api/monitors.json"
    SERVERS_URL = "api/servers.json"

    def __init__(
        self,
        server_host,
        username,
        password,
        server_path=DEFAULT_SERVER_PATH,
        zms_path=DEFAULT_ZMS_PATH,
        verify_ssl=True,
        stream_scale=None,
        stream_maxfps=None,
    ) -> None:
        """Create a ZoneMinder API Client."""
        self._server_url = ZoneMinder._build_server_url(server_host, server_path)
        self._zms_url = ZoneMinder._build_zms_url(server_host, zms_path)
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._stream_scale: int | None = stream_scale
        self._stream_maxfps: float | None = stream_maxfps
        self._session = requests.Session()
        self._session.verify = verify_ssl
        self._auth_token: str | None = None
        self._zm_version: str | None = None
        self._alarm_states: dict | None = None
        self._servers: dict[int, Server] | None = None
        self._event_cache: dict[tuple, tuple[float, dict | None]] = {}

    def login(self) -> bool:
        """Login to the ZoneMinder API."""
        _LOGGER.debug("Attempting to login to ZoneMinder")
        # Clear any stale token before re-auth.  If JWT auth fails and we
        # fall back to legacy session cookies, a leftover token would be
        # sent as ?token=… on every subsequent request, causing ZM to reject
        # the stale JWT with 401 even though the session cookie is valid.
        self._auth_token = None

        login_post = {}
        if self._username:
            login_post["user"] = self._username
        if self._password:
            login_post["pass"] = self._password

        try:
            req = self._session.post(
                urljoin(self._server_url, "api/host/login.json"),
                data=login_post,
                timeout=ZoneMinder.DEFAULT_TIMEOUT,
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _LOGGER.exception("Unable to connect to ZoneMinder during login")
            return False

        if req.ok:
            try:
                login_data = req.json()
                self._auth_token = login_data["access_token"]
                self._zm_version = login_data.get("version")
                self._alarm_states = get_api_alarm_states(self._zm_version)
                return True
            except KeyError:
                # Try legacy auth below
                pass

        return self._legacy_auth()

    def _legacy_auth(self) -> bool:
        login_post = {"view": "console", "action": "login"}
        if self._username:
            login_post["username"] = self._username
        if self._password:
            login_post["password"] = self._password

        try:
            req = self._session.post(
                urljoin(self._server_url, "index.php"),
                data=login_post,
                timeout=ZoneMinder.DEFAULT_TIMEOUT,
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _LOGGER.exception("Unable to connect to ZoneMinder during legacy login")
            return False

        # Session stores cookies automatically from the login response.

        # Login calls returns a 200 response on both failure and success.
        # The only way to tell if you logged in correctly is to issue an api
        # call.
        try:
            req = self._session.get(
                urljoin(self._server_url, "api/host/getVersion.json"),
                timeout=ZoneMinder.DEFAULT_TIMEOUT,
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _LOGGER.exception("Unable to connect to ZoneMinder during legacy login verification")
            return False

        if not req.ok:
            _LOGGER.error("Connection error logging into ZoneMinder")
            return False

        try:
            self._zm_version = req.json().get("version")
        except (ValueError, KeyError):
            pass

        self._alarm_states = get_api_alarm_states(self._zm_version)
        return True

    def get_state(self, api_url) -> dict:
        """Perform a GET request on the specified ZoneMinder API URL."""
        return self._zm_request("get", api_url)

    def change_state(self, api_url, post_data) -> dict:
        """Perform a POST request on the specific ZoneMinder API Url."""
        return self._zm_request("post", api_url, post_data)

    def _zm_request(self, method, api_url, data=None, timeout=DEFAULT_TIMEOUT) -> dict:
        """Perform a request to the ZoneMinder API."""
        try:
            # Since the API uses sessions that expire, sometimes we need to
            # re-auth if the call fails.
            url = urljoin(self._server_url, api_url)
            for attempt in range(ZoneMinder.LOGIN_RETRIES):
                params = {"token": self._auth_token} if self._auth_token else None

                req = self._session.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    timeout=timeout,
                )

                if req.ok:
                    break
                if attempt < ZoneMinder.LOGIN_RETRIES - 1:
                    _LOGGER.debug(
                        "API call %s %s returned HTTP %s, re-authenticating",
                        method.upper(),
                        api_url,
                        req.status_code,
                    )
                    login_ok = self.login()
                    _LOGGER.debug("Re-login succeeded: %s", login_ok)

            else:
                _LOGGER.error(
                    "Unable to get API response from ZoneMinder: %s %s → HTTP %s",
                    method.upper(),
                    api_url,
                    req.status_code,
                )
                return {}

            try:
                return req.json()
            except ValueError:
                _LOGGER.exception(
                    'JSON decode exception caught while attempting to decode "%s"',
                    req.text,
                )
                return {}
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _LOGGER.exception("Unable to connect to ZoneMinder")
            return {}

    def update_all_monitors(self, monitors: list[Monitor]) -> None:
        """Bulk-refresh monitors via api/monitors.json (1 call instead of M)."""
        raw_monitors = self._zm_request("get", ZoneMinder.MONITOR_URL)
        if not raw_monitors or "monitors" not in raw_monitors:
            _LOGGER.warning("Could not bulk-fetch monitors from ZoneMinder")
            return

        by_id: dict[int, dict] = {}
        for raw_result in raw_monitors["monitors"]:
            try:
                mid = int(raw_result["Monitor"]["Id"])
                by_id[mid] = raw_result
            except (KeyError, ValueError, TypeError):
                continue

        for monitor in monitors:
            if monitor.id in by_id:
                monitor._apply_raw_result(by_id[monitor.id])  # pylint: disable=protected-access

    def get_monitors(self) -> list[Monitor]:
        """Get a list of Monitors from the ZoneMinder API."""
        raw_monitors = self._zm_request("get", ZoneMinder.MONITOR_URL)
        if not raw_monitors:
            _LOGGER.warning("Could not fetch monitors from ZoneMinder")
            return []

        if "monitors" not in raw_monitors:
            _LOGGER.warning("Could not parse list of monitors from ZoneMinder")
            return []

        monitors = []
        for raw_result in raw_monitors["monitors"]:
            # ZoneMinder >= 1.37/1.38 may retain deleted monitors
            # as soft-deleted database records. Older releases do not
            # expose the Deleted field.
            if str(raw_result["Monitor"].get("Deleted", "0")).lower() in ("1", "true"):
                continue

            _LOGGER.debug("Initializing camera %s", raw_result["Monitor"]["Id"])
            monitors.append(
                Monitor(
                    self,
                    raw_result,
                    scale=self._stream_scale,
                    maxfps=self._stream_maxfps,
                )
            )

        return monitors

    def get_run_states(self) -> list[RunState]:
        """Get a list of RunStates from the ZoneMinder API."""
        raw_states = self.get_state("api/states.json")
        if not raw_states:
            _LOGGER.warning("Could not fetch runstates from ZoneMinder")
            return []

        if "states" not in raw_states:
            _LOGGER.warning("Could not parse list of runstates from ZoneMinder")
            return []

        run_states = []
        for i in raw_states["states"]:
            raw_state = i["State"]
            _LOGGER.info("Initializing runstate %s", raw_state["Id"])
            run_states.append(RunState(self, raw_state))

        return run_states

    def get_servers(self) -> list[Server]:
        """Get a list of Servers from the ZoneMinder API."""
        raw_servers = self.get_state(ZoneMinder.SERVERS_URL)
        if not raw_servers:
            _LOGGER.warning("Could not fetch servers from ZoneMinder")
            return []

        if "servers" not in raw_servers:
            _LOGGER.warning("Could not parse list of servers from ZoneMinder")
            return []

        servers = []
        for i in raw_servers["servers"]:
            raw_server = i["Server"]
            _LOGGER.info("Initializing server %s", raw_server["Id"])
            servers.append(Server(raw_server))

        return servers

    def _ensure_servers(self) -> dict[int, Server]:
        """Lazy-fetch and cache the server map as {server_id: Server}."""
        if self._servers is None:
            self._servers = {s.id: s for s in self.get_servers()}
        return self._servers

    def get_zms_url_for_monitor(self, raw_monitor) -> str:
        """Resolve the correct ZMS URL for a monitor based on its ServerId.

        Falls back to the main client ZMS URL when ServerId is missing, "0",
        or refers to an unknown server.
        """
        server_id_str = raw_monitor.get("ServerId", "0")
        try:
            server_id = int(server_id_str)
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Monitor %s has invalid ServerId %r, using main ZMS URL",
                raw_monitor.get("Id"),
                server_id_str,
            )
            return self._zms_url

        if server_id == 0:
            return self._zms_url

        servers = self._ensure_servers()
        server = servers.get(server_id)
        if server is None:
            _LOGGER.warning(
                "Monitor %s references unknown ServerId %d, using main ZMS URL",
                raw_monitor.get("Id"),
                server_id,
            )
            return self._zms_url

        return server.zms_url

    def get_server_url_for_monitor(self, raw_monitor) -> str:
        """Resolve the correct base URL for a monitor based on its ServerId.

        Used for PTZ commands and other control requests. Falls back to the
        main client server URL when ServerId is missing, "0", or unknown.
        """
        server_id_str = raw_monitor.get("ServerId", "0")
        try:
            server_id = int(server_id_str)
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Monitor %s has invalid ServerId %r, using main server URL",
                raw_monitor.get("Id"),
                server_id_str,
            )
            return self._server_url

        if server_id == 0:
            return self._server_url

        servers = self._ensure_servers()
        server = servers.get(server_id)
        if server is None:
            _LOGGER.warning(
                "Monitor %s references unknown ServerId %d, using main server URL",
                raw_monitor.get("Id"),
                server_id,
            )
            return self._server_url

        return server.base_url

    def get_active_state(self) -> str | None:
        """Get the name of the active run state from the ZoneMinder API."""
        raw_states = self.get_state("api/states.json")
        if not raw_states or "states" not in raw_states:
            return None
        for i in raw_states["states"]:
            state = i["State"]
            try:
                if int(state["IsActive"]) == 1:
                    return state["Name"]
            except (ValueError, TypeError, KeyError):
                continue
        return None

    def set_active_state(self, state_name) -> dict:
        """Set the ZoneMinder run state to the given state name, via ZM API.

        Note that this is a long-running API call; ZoneMinder changes the state
        of each camera in turn, and this GET does not receive a response until
        all cameras have been updated. Even on a reasonably powerful machine,
        this call can take ten (10) or more seconds **per camera**. This method
        sets a timeout of 120, which should be adequate for most users.
        """
        _LOGGER.info("Setting ZoneMinder run state to state %s", state_name)
        return self._zm_request(
            "get", f"api/states/change/{quote(state_name, safe='')}.json", timeout=120
        )

    def get_event_counts(self, time_period, include_archived=False) -> dict | None:
        """Fetch console event counts for all monitors.

        Results are cached for 1 second to avoid duplicate API calls when
        multiple monitors request events in the same polling cycle.
        """
        cache_key = (time_period.period, include_archived)
        now = time.monotonic()
        cached = self._event_cache.get(cache_key)
        if cached is not None:
            cached_time, cached_result = cached
            if now - cached_time < 1.0:
                return cached_result

        date_filter = quote(f"1 {time_period.period}")
        if time_period == TimePeriod.ALL:
            date_filter = quote("100 year")

        archived_filter = "/Archived=:0"
        if include_archived:
            archived_filter = ""

        response = self.get_state(f"api/events/consoleEvents/{date_filter}{archived_filter}.json")

        try:
            result = response["results"]
            if isinstance(result, list):
                result = {}
        except (TypeError, KeyError):
            result = None

        self._event_cache[cache_key] = (now, result)
        return result

    def get_zms_url(self) -> str:
        """Get the url to the current ZMS instance."""
        return self._zms_url

    def get_url_with_auth(self, url) -> str:
        """Add the auth credentials to a url (if needed)."""
        if not self._username:
            return url

        url += f"&user={quote(self._username)}"

        if not self._password:
            return url
        return url + f"&pass={quote(self._password)}"

    @property
    def is_available(self) -> bool:
        """Indicate if this ZoneMinder service is currently available."""
        status_response = self.get_state("api/host/daemonCheck.json")

        if not status_response:
            return False

        result = status_response.get("result")
        if result is None:
            return False
        try:
            return int(result) == 1
        except (ValueError, TypeError):
            return False

    @property
    def zm_version(self) -> str | None:
        """Get the ZoneMinder server version string, e.g. '1.38.0'."""
        return self._zm_version

    def get_alarm_states(self) -> dict:
        """Return the alarm state value table for this server's version."""
        if self._alarm_states is None:
            self._alarm_states = get_api_alarm_states(self._zm_version)
        return self._alarm_states

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
        return f"{server_url}/"

    def move_monitor(self, monitor: Monitor, direction: str) -> bool:
        """Call Zoneminder to move."""
        base_url = self.get_server_url_for_monitor(monitor.raw_monitor)
        result = monitor.ptz_control_command(direction, self._auth_token, base_url)
        if result:
            _LOGGER.info("Successfully moved camera to %s", direction)
        else:
            _LOGGER.error("Failed to move camera to %s", direction)
        return result

    def goto_preset(self, monitor: Monitor, preset: int) -> bool:
        """Move camera to a numbered preset position."""
        base_url = self.get_server_url_for_monitor(monitor.raw_monitor)
        result = monitor.preset_command(preset, self._auth_token, base_url)
        if result:
            _LOGGER.info("Successfully moved camera to preset %d", preset)
        else:
            _LOGGER.error("Failed to move camera to preset %d", preset)
        return result

    def goto_home(self, monitor: Monitor) -> bool:
        """Move camera to the home position."""
        base_url = self.get_server_url_for_monitor(monitor.raw_monitor)
        result = monitor.home_command(self._auth_token, base_url)
        if result:
            _LOGGER.info("Successfully moved camera to home position")
        else:
            _LOGGER.error("Failed to move camera to home position")
        return result
