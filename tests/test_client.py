"""Unit tests for ZoneMinder client logic beyond URL building.

Tests response parsing, property behaviour, and move_monitor using
a mock _zm_request -- no live server needed.

URL building tests remain in test_zm.py (the original upstream tests).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from zoneminder.exceptions import ControlTypeError, MonitorControlTypeError
from zoneminder.monitor import Monitor
from zoneminder.run_state import RunState
from zoneminder.server import Server
from zoneminder.zm import ZoneMinder

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client(**kwargs) -> ZoneMinder:
    """Build a ZoneMinder client with sensible defaults."""
    return ZoneMinder(
        server_host=kwargs.get("host", "http://zm.test"),
        username=kwargs.get("username", "admin"),
        password=kwargs.get("password", "secret"),
        server_path=kwargs.get("server_path", "/zm/"),
        zms_path=kwargs.get("zms_path", "/zm/cgi-bin/nph-zms"),
        verify_ssl=kwargs.get("verify_ssl", False),
    )


def _monitor_raw(mid=1, name="Cam", controllable="0", function="Monitor", server_id="0"):
    return {
        "Monitor": {
            "Id": str(mid),
            "Name": name,
            "Controllable": controllable,
            "Function": function,
            "StreamReplayBuffer": "0",
            "ServerId": server_id,
        },
        "Monitor_Status": {"CaptureFPS": "10.00"},
    }


def _server_raw(sid=1, name="Server1", hostname="zm1.example.com", protocol="https"):
    return {
        "Server": {
            "Id": str(sid),
            "Name": name,
            "Hostname": hostname,
            "Protocol": protocol,
            "PathToZMS": "/zm/cgi-bin/nph-zms",
            "PathToIndex": "/zm/index.php",
            "Status": "Online",
        }
    }


# ---------------------------------------------------------------------------
# verify_ssl property
# ---------------------------------------------------------------------------

class TestVerifySsl:
    def test_default_is_true(self):
        c = ZoneMinder("http://zm.test", None, None)
        assert c.verify_ssl is True

    def test_explicit_false(self):
        c = _client(verify_ssl=False)
        assert c.verify_ssl is False

    def test_explicit_true(self):
        c = _client(verify_ssl=True)
        assert c.verify_ssl is True


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------

class TestIsAvailable:
    def test_true_when_result_is_1(self):
        c = _client()
        with patch.object(c, "get_state", return_value={"result": 1}):
            assert c.is_available is True

    def test_false_when_result_is_0(self):
        c = _client()
        with patch.object(c, "get_state", return_value={"result": 0}):
            assert c.is_available is False

    def test_false_when_empty_response(self):
        c = _client()
        with patch.object(c, "get_state", return_value={}):
            assert c.is_available is False

    def test_true_when_result_is_string(self):
        """String '1' should be coerced to int and return True."""
        c = _client()
        with patch.object(c, "get_state", return_value={"result": "1"}):
            assert c.is_available is True

    def test_false_when_result_is_non_numeric(self):
        """Non-numeric result should return False, not crash."""
        c = _client()
        with patch.object(c, "get_state", return_value={"result": "bad"}):
            assert c.is_available is False

    def test_false_when_result_is_none(self):
        """None result should return False, not crash."""
        c = _client()
        with patch.object(c, "get_state", return_value={"result": None}):
            assert c.is_available is False


# ---------------------------------------------------------------------------
# get_monitors
# ---------------------------------------------------------------------------

class TestGetMonitors:
    def test_returns_list_of_monitors(self):
        raw = {"monitors": [_monitor_raw(1, "Cam1"), _monitor_raw(2, "Cam2")]}
        c = _client()
        with patch.object(c, "_zm_request", return_value=raw):
            monitors = c.get_monitors()
        assert len(monitors) == 2
        assert all(isinstance(m, Monitor) for m in monitors)
        assert monitors[0].id == 1
        assert monitors[1].name == "Cam2"

    def test_empty_response_returns_empty_list(self):
        c = _client()
        with patch.object(c, "_zm_request", return_value={}):
            assert c.get_monitors() == []

    def test_no_monitors_key_returns_empty_list(self):
        c = _client()
        with patch.object(c, "_zm_request", return_value={"other": "data"}):
            assert c.get_monitors() == []

    def test_empty_monitors_list(self):
        c = _client()
        with patch.object(c, "_zm_request", return_value={"monitors": []}):
            assert c.get_monitors() == []


# ---------------------------------------------------------------------------
# get_run_states
# ---------------------------------------------------------------------------

class TestGetRunStates:
    def test_returns_list_of_run_states(self):
        raw = {
            "states": [
                {"State": {"Id": "1", "Name": "Default", "IsActive": 1}},
                {"State": {"Id": "2", "Name": "Away", "IsActive": 0}},
            ]
        }
        c = _client()
        with patch.object(c, "get_state", return_value=raw):
            states = c.get_run_states()
        assert len(states) == 2
        assert all(isinstance(s, RunState) for s in states)
        assert states[0].name == "Default"

    def test_empty_response_returns_empty_list(self):
        c = _client()
        with patch.object(c, "get_state", return_value={}):
            assert c.get_run_states() == []

    def test_no_states_key_returns_empty_list(self):
        c = _client()
        with patch.object(c, "get_state", return_value={"other": "data"}):
            assert c.get_run_states() == []


# ---------------------------------------------------------------------------
# get_active_state
# ---------------------------------------------------------------------------

class TestGetActiveState:
    def test_returns_active_state_name(self):
        raw = {
            "states": [
                {"State": {"Id": "1", "Name": "Default", "IsActive": 0}},
                {"State": {"Id": "2", "Name": "Away", "IsActive": 1}},
            ]
        }
        c = _client()
        with patch.object(c, "get_state", return_value=raw):
            assert c.get_active_state() == "Away"

    def test_returns_none_when_no_active(self):
        raw = {
            "states": [
                {"State": {"Id": "1", "Name": "Default", "IsActive": 0}},
            ]
        }
        c = _client()
        with patch.object(c, "get_state", return_value=raw):
            assert c.get_active_state() is None


# ---------------------------------------------------------------------------
# set_active_state
# ---------------------------------------------------------------------------


class TestSetActiveState:
    @patch.object(ZoneMinder, "_zm_request", return_value={})
    def test_url_encodes_state_name(self, mock_req):
        """State names with special chars should be percent-encoded."""
        c = _client()
        c.set_active_state("Away Mode")
        call_args = mock_req.call_args
        api_url = call_args[0][1]
        assert "Away%20Mode" in api_url
        assert "Away Mode" not in api_url

    @patch.object(ZoneMinder, "_zm_request", return_value={})
    def test_plain_state_name(self, mock_req):
        """Simple state names should pass through unchanged."""
        c = _client()
        c.set_active_state("Home")
        api_url = mock_req.call_args[0][1]
        assert "Home" in api_url


# ---------------------------------------------------------------------------
# move_monitor
# ---------------------------------------------------------------------------

class TestMoveMonitor:
    def _make_monitor(self, controllable=True):
        raw = _monitor_raw(controllable="1" if controllable else "0")
        return Monitor(_client(), raw)

    @patch("zoneminder.monitor.post")
    def test_delegates_to_ptz_control_command(self, mock_post):
        mock_post.return_value.ok = True
        c = _client()
        c._auth_token = "test-token"
        mon = self._make_monitor(controllable=True)
        c.move_monitor(mon, "right")
        mock_post.assert_called_once()

    def test_raises_on_invalid_direction(self):
        """move_monitor should propagate ControlTypeError to callers."""
        c = _client()
        c._auth_token = "tok"
        mon = self._make_monitor(controllable=True)
        with pytest.raises(ControlTypeError):
            c.move_monitor(mon, "invalid-direction")

    def test_raises_on_non_controllable(self):
        """move_monitor should propagate MonitorControlTypeError to callers."""
        c = _client()
        c._auth_token = "tok"
        mon = self._make_monitor(controllable=False)
        with pytest.raises(MonitorControlTypeError):
            c.move_monitor(mon, "right")

    @patch("zoneminder.monitor.post")
    def test_returns_bool_on_success(self, mock_post):
        """move_monitor should return True on success."""
        mock_post.return_value.ok = True
        c = _client()
        c._auth_token = "tok"
        mon = self._make_monitor(controllable=True)
        result = c.move_monitor(mon, "right")
        assert result is True

    @patch("zoneminder.monitor.post")
    def test_passes_cookies_to_ptz(self, mock_post):
        """move_monitor should forward session cookies for legacy auth."""
        mock_post.return_value.ok = True
        c = _client()
        c._cookies = {"ZMSESSID": "abc123"}
        mon = self._make_monitor(controllable=True)
        c.move_monitor(mon, "right")
        assert mock_post.call_args.kwargs["cookies"] == {"ZMSESSID": "abc123"}


class TestStaleTokenRetry:
    """Verify _zm_request recomputes token suffix after login() refreshes the token."""

    @patch("zoneminder.zm.requests.request")
    def test_uses_refreshed_token_after_relogin(self, mock_request):
        """After a 401 triggers login(), the next request should use the new token."""
        c = _client()
        c._auth_token = "old-token"

        # First call returns 401, second call returns 200
        resp_fail = MagicMock(ok=False, status_code=401)
        resp_ok = MagicMock(ok=True)
        resp_ok.json.return_value = {"result": 1}
        mock_request.side_effect = [resp_fail, resp_ok]

        # login() refreshes the token
        with patch.object(c, "login", side_effect=lambda: setattr(c, "_auth_token", "new-token")):
            result = c._zm_request("get", "api/host/daemonCheck.json")

        assert result == {"result": 1}
        # Second call should have used new-token, not old-token
        second_call_params = mock_request.call_args_list[1][1].get("params", {})
        assert second_call_params == {"token": "new-token"}


class TestRetryExhaustion:
    """Verify _zm_request returns {} when all retries fail."""

    @patch("zoneminder.zm.requests.request")
    def test_returns_empty_dict_on_exhaustion(self, mock_request):
        """When all retries fail, return {} instead of error response JSON."""
        c = _client()

        resp_fail = MagicMock(ok=False, status_code=401)
        resp_fail.json.return_value = {"error": "Unauthorized"}
        mock_request.return_value = resp_fail

        with patch.object(c, "login"):
            result = c._zm_request("get", "api/monitors.json")

        assert result == {}

    @patch("zoneminder.zm.requests.request")
    def test_no_wasted_login_on_last_attempt(self, mock_request):
        """login() should not be called after the final failed attempt."""
        c = _client()

        resp_fail = MagicMock(ok=False, status_code=401)
        mock_request.return_value = resp_fail

        with patch.object(c, "login") as mock_login:
            c._zm_request("get", "api/monitors.json")

        # LOGIN_RETRIES=2: login called once (after 1st fail), not after 2nd
        assert mock_login.call_count == 1


class TestLoginConnectionError:
    """Verify login() returns False on ConnectionError instead of crashing."""

    @patch("zoneminder.zm.requests.post")
    def test_login_returns_false_on_connection_error(self, mock_post):
        """login() should catch ConnectionError and return False."""
        mock_post.side_effect = requests.exceptions.ConnectionError("refused")
        c = _client()
        assert c.login() is False

    @patch("zoneminder.zm.requests.post")
    def test_legacy_auth_post_connection_error(self, mock_post):
        """_legacy_auth() should catch ConnectionError on the POST."""
        mock_post.side_effect = requests.exceptions.ConnectionError("refused")
        c = _client()
        assert c._legacy_auth() is False

    @patch("zoneminder.zm.requests.get")
    @patch("zoneminder.zm.requests.post")
    def test_legacy_auth_get_connection_error(self, mock_post, mock_get):
        """_legacy_auth() should catch ConnectionError on the verification GET."""
        mock_post.return_value = MagicMock(cookies={})
        mock_get.side_effect = requests.exceptions.ConnectionError("refused")
        c = _client()
        assert c._legacy_auth() is False


# ---------------------------------------------------------------------------
# get_servers
# ---------------------------------------------------------------------------


class TestGetServers:
    def test_empty_response_returns_empty_list(self):
        c = _client()
        with patch.object(c, "get_state", return_value={}):
            assert c.get_servers() == []

    def test_no_servers_key_returns_empty_list(self):
        c = _client()
        with patch.object(c, "get_state", return_value={"other": "data"}):
            assert c.get_servers() == []

    def test_valid_response_returns_servers(self):
        raw = {"servers": [_server_raw(1, "Srv1"), _server_raw(2, "Srv2", hostname="zm2.test")]}
        c = _client()
        with patch.object(c, "get_state", return_value=raw):
            servers = c.get_servers()
        assert len(servers) == 2
        assert all(isinstance(s, Server) for s in servers)
        assert servers[0].name == "Srv1"
        assert servers[1].hostname == "zm2.test"

    def test_empty_servers_list(self):
        c = _client()
        with patch.object(c, "get_state", return_value={"servers": []}):
            assert c.get_servers() == []


# ---------------------------------------------------------------------------
# Multi-server ZMS routing
# ---------------------------------------------------------------------------


class TestMultiServerZmsRouting:
    def test_server_id_zero_returns_main_zms(self):
        c = _client()
        raw_monitor = {"Id": "1", "ServerId": "0"}
        assert c.get_zms_url_for_monitor(raw_monitor) == c.get_zms_url()

    def test_missing_server_id_returns_main_zms(self):
        c = _client()
        raw_monitor = {"Id": "1"}
        assert c.get_zms_url_for_monitor(raw_monitor) == c.get_zms_url()

    def test_known_server_returns_server_zms(self):
        c = _client()
        raw = {"servers": [_server_raw(2, "Srv2", hostname="zm2.test", protocol="https")]}
        with patch.object(c, "get_state", return_value=raw):
            raw_monitor = {"Id": "1", "ServerId": "2"}
            result = c.get_zms_url_for_monitor(raw_monitor)
        assert result == "https://zm2.test/zm/cgi-bin/nph-zms"

    def test_unknown_server_falls_back_to_main(self):
        c = _client()
        raw = {"servers": [_server_raw(2, "Srv2", hostname="zm2.test")]}
        with patch.object(c, "get_state", return_value=raw):
            raw_monitor = {"Id": "1", "ServerId": "99"}
            result = c.get_zms_url_for_monitor(raw_monitor)
        assert result == c.get_zms_url()

    def test_invalid_server_id_falls_back_to_main(self):
        c = _client()
        raw_monitor = {"Id": "1", "ServerId": "abc"}
        assert c.get_zms_url_for_monitor(raw_monitor) == c.get_zms_url()

    def test_lazy_caching(self):
        """_ensure_servers should only fetch once."""
        c = _client()
        raw = {"servers": [_server_raw(2, "Srv2", hostname="zm2.test")]}
        with patch.object(c, "get_state", return_value=raw) as mock_get:
            c.get_zms_url_for_monitor({"Id": "1", "ServerId": "2"})
            c.get_zms_url_for_monitor({"Id": "2", "ServerId": "2"})
        # get_state should have been called once (lazy cache)
        mock_get.assert_called_once()


# ---------------------------------------------------------------------------
# Multi-server PTZ routing
# ---------------------------------------------------------------------------


class TestMultiServerPtzRouting:
    def test_server_id_zero_returns_main_url(self):
        c = _client()
        raw_monitor = {"Id": "1", "ServerId": "0"}
        assert c.get_server_url_for_monitor(raw_monitor) == c._server_url

    def test_known_server_returns_server_base_url(self):
        c = _client()
        raw = {"servers": [_server_raw(2, "Srv2", hostname="zm2.test", protocol="https")]}
        with patch.object(c, "get_state", return_value=raw):
            raw_monitor = {"Id": "1", "ServerId": "2"}
            result = c.get_server_url_for_monitor(raw_monitor)
        assert result == "https://zm2.test/zm/"

    @patch("zoneminder.monitor.post")
    def test_move_monitor_uses_server_url(self, mock_post):
        """move_monitor should resolve the per-server URL for PTZ."""
        mock_post.return_value.ok = True
        c = _client()
        c._auth_token = "tok"
        raw = {"servers": [_server_raw(2, "Srv2", hostname="zm2.test", protocol="https")]}
        with patch.object(c, "get_state", return_value=raw):
            mon = Monitor(c, _monitor_raw(controllable="1", server_id="2"))
            c.move_monitor(mon, "right")
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["url"] == "https://zm2.test/zm/index.php"
