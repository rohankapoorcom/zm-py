"""Unit tests for the Monitor class.

Tests construction, properties, URL building, and response parsing logic
using a stub client -- no live ZoneMinder server needed.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from zoneminder.exceptions import ControlTypeError, MonitorControlTypeError
from zoneminder.monitor import (
    API_STATES_NO_OFFSET,
    API_STATES_WITH_OFFSET,
    Monitor,
    MonitorState,
    TimePeriod,
    _parse_version,
    get_api_alarm_states,
)

# ---------------------------------------------------------------------------
# Stub client
# ---------------------------------------------------------------------------


class StubClient:
    """Minimal client stub for Monitor construction and method calls."""

    def __init__(
        self,
        get_state_return=None,
        zms_url="http://zm.test/zm/cgi-bin/nph-zms",
        zm_version="1.38.0",
    ):
        self._zms_url = zms_url
        self._username = "admin"
        self._password = "secret"
        self._verify_ssl = False
        self._zm_version = zm_version
        self._get_state_return = get_state_return or {}
        self._get_state_call_count = 0
        self._change_state_calls = []

    @property
    def verify_ssl(self):
        return self._verify_ssl

    def get_zms_url(self):
        return self._zms_url

    def get_zms_url_for_monitor(self, raw_monitor):
        return self._zms_url

    def get_url_with_auth(self, url):
        return url + "&user=admin&pass=secret"

    def get_state(self, api_url):
        self._get_state_call_count += 1
        return self._get_state_return

    def change_state(self, api_url, post_data):
        self._change_state_calls.append((api_url, post_data))
        return {}

    def get_alarm_states(self):
        return get_api_alarm_states(self._zm_version)


def _make_raw(
    mid=1,
    name="Front Door",
    controllable="0",
    function="Monitor",
    buffer="0",
    server_id="0",
):
    """Build a raw monitor result dict matching the ZM API shape."""
    return {
        "Monitor": {
            "Id": str(mid),
            "Name": name,
            "Controllable": controllable,
            "Function": function,
            "StreamReplayBuffer": buffer,
            "ServerId": server_id,
        },
        "Monitor_Status": {
            "CaptureFPS": "10.00",
        },
    }


# ---------------------------------------------------------------------------
# Construction & properties
# ---------------------------------------------------------------------------

class TestMonitorConstruction:
    def test_creates_from_raw(self):
        mon = Monitor(StubClient(), _make_raw())
        assert mon.id == 1
        assert mon.name == "Front Door"

    def test_id_is_int(self):
        mon = Monitor(StubClient(), _make_raw(mid=42))
        assert isinstance(mon.id, int)
        assert mon.id == 42

    def test_name_from_raw(self):
        mon = Monitor(StubClient(), _make_raw(name="Back Yard"))
        assert mon.name == "Back Yard"

    def test_controllable_false(self):
        mon = Monitor(StubClient(), _make_raw(controllable="0"))
        assert mon.controllable is False

    def test_controllable_true(self):
        mon = Monitor(StubClient(), _make_raw(controllable="1"))
        assert mon.controllable is True

    def test_controllable_is_bool(self):
        mon = Monitor(StubClient(), _make_raw(controllable="1"))
        assert isinstance(mon.controllable, bool)


class TestMonitorRepr:
    def test_repr_contains_class_name(self):
        mon = Monitor(StubClient(), _make_raw(mid=5, name="Garage"))
        assert "Monitor" in repr(mon)

    def test_repr_contains_id(self):
        mon = Monitor(StubClient(), _make_raw(mid=5))
        assert "5" in repr(mon)

    def test_repr_contains_name(self):
        mon = Monitor(StubClient(), _make_raw(name="Garage"))
        assert "Garage" in repr(mon)

    def test_str_matches_repr(self):
        mon = Monitor(StubClient(), _make_raw())
        assert str(mon) == repr(mon)


# ---------------------------------------------------------------------------
# Image URL building
# ---------------------------------------------------------------------------

class TestMonitorImageUrls:
    def test_mjpeg_url_contains_mode_jpeg(self):
        mon = Monitor(StubClient(), _make_raw())
        assert "mode=jpeg" in mon.mjpeg_image_url

    def test_still_url_contains_mode_single(self):
        mon = Monitor(StubClient(), _make_raw())
        assert "mode=single" in mon.still_image_url

    def test_urls_contain_monitor_id(self):
        mon = Monitor(StubClient(), _make_raw(mid=7))
        assert "monitor=7" in mon.mjpeg_image_url
        assert "monitor=7" in mon.still_image_url

    def test_urls_contain_buffer(self):
        mon = Monitor(StubClient(), _make_raw(buffer="1000"))
        assert "buffer=1000" in mon.mjpeg_image_url

    def test_urls_contain_auth(self):
        mon = Monitor(StubClient(), _make_raw())
        assert "user=admin" in mon.mjpeg_image_url
        assert "pass=secret" in mon.mjpeg_image_url

    def test_urls_rooted_at_zms(self):
        client = StubClient(zms_url="http://cam.local/zm/cgi-bin/nph-zms")
        mon = Monitor(client, _make_raw())
        assert mon.mjpeg_image_url.startswith("http://cam.local/zm/cgi-bin/nph-zms?")

    def test_no_auth_without_username(self):
        """Client without credentials should not inject auth params."""
        client = StubClient()
        client._username = None

        def no_auth(url):
            return url

        client.get_url_with_auth = no_auth
        mon = Monitor(client, _make_raw())
        assert "user=" not in mon.mjpeg_image_url


# ---------------------------------------------------------------------------
# is_recording
# ---------------------------------------------------------------------------

class TestMonitorIsRecording:
    """Test is_recording with version-aware alarm state values.

    Default StubClient uses version 1.38.0 (with -1 offset), so ALARM=2.
    """

    def test_alarm_status_true(self):
        """Alarm status 2 means recording on ZM >= 1.36.26."""
        client = StubClient(get_state_return={"status": 2})
        mon = Monitor(client, _make_raw())
        assert mon.is_recording is True

    def test_alert_status_also_recording(self):
        """Alert status 3 also means recording (post-alarm frames)."""
        client = StubClient(get_state_return={"status": 3})
        mon = Monitor(client, _make_raw())
        assert mon.is_recording is True

    def test_idle_status_false(self):
        """Idle status 0 means not recording."""
        client = StubClient(get_state_return={"status": 0})
        mon = Monitor(client, _make_raw())
        assert mon.is_recording is False

    def test_prealarm_status_false(self):
        """Prealarm status 1 means not yet recording."""
        client = StubClient(get_state_return={"status": 1})
        mon = Monitor(client, _make_raw())
        assert mon.is_recording is False

    def test_alarm_status_empty_string(self):
        """Empty string means monitor cannot record right now."""
        client = StubClient(get_state_return={"status": ""})
        mon = Monitor(client, _make_raw())
        assert mon.is_recording is False

    def test_alarm_no_response(self):
        """Empty response returns None."""
        client = StubClient(get_state_return={})
        mon = Monitor(client, _make_raw())
        assert mon.is_recording is None

    def test_alarm_status_int_cast(self):
        """Status as string '2' should still match ALARM."""
        client = StubClient(get_state_return={"status": "2"})
        mon = Monitor(client, _make_raw())
        assert mon.is_recording is True

    def test_alarm_status_none(self):
        """None status (missing key) should return False, not crash."""
        client = StubClient(get_state_return={"other": "data"})
        mon = Monitor(client, _make_raw())
        assert mon.is_recording is False

    def test_no_offset_version_alarm_at_3(self):
        """ZM 1.36.20 (no -1 hack) has ALARM=3."""
        client = StubClient(get_state_return={"status": 3}, zm_version="1.36.20")
        mon = Monitor(client, _make_raw())
        assert mon.is_recording is True

    def test_no_offset_version_2_not_recording(self):
        """ZM 1.36.20 (no -1 hack): status 2 is PREALARM, not recording."""
        client = StubClient(get_state_return={"status": 2}, zm_version="1.36.20")
        mon = Monitor(client, _make_raw())
        assert mon.is_recording is False

    def test_unknown_version_uses_offset(self):
        """Unknown version string defaults to the offset table."""
        client = StubClient(get_state_return={"status": 2}, zm_version=None)
        mon = Monitor(client, _make_raw())
        assert mon.is_recording is True


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------

class TestMonitorIsAvailable:
    def _make_available_monitor(self, daemon_status, capture_fps="10.00", has_monitor_status=True):
        """Build a monitor with patched update_monitor for is_available tests."""
        client = StubClient(get_state_return=daemon_status)
        raw = _make_raw()
        if has_monitor_status:
            raw["Monitor_Status"] = {"CaptureFPS": capture_fps}
        else:
            del raw["Monitor_Status"]
        mon = Monitor(client, raw)
        # Patch update_monitor to be a no-op since _raw_result is already set
        # and StubClient can only return one response shape
        mon.update_monitor = lambda: None
        return mon

    def test_available_when_daemon_running_and_fps_nonzero(self):
        mon = self._make_available_monitor({"status": True}, capture_fps="10.00")
        assert mon.is_available is True

    def test_unavailable_when_daemon_not_running(self):
        mon = self._make_available_monitor({"status": False}, capture_fps="10.00")
        assert mon.is_available is False

    def test_unavailable_when_fps_zero(self):
        mon = self._make_available_monitor({"status": True}, capture_fps="0.00")
        assert mon.is_available is False

    def test_unavailable_when_no_monitor_status(self):
        """Without Monitor_Status, should be unavailable."""
        mon = self._make_available_monitor({"status": True}, has_monitor_status=False)
        assert mon.is_available is False

    def test_unavailable_when_no_response(self):
        client = StubClient(get_state_return={})
        mon = Monitor(client, _make_raw())
        assert mon.is_available is False

    def test_fetches_fresh_data(self):
        """is_available should call update_monitor to get fresh Monitor_Status."""
        client = StubClient(get_state_return={"status": True})
        raw = _make_raw()
        raw["Monitor_Status"] = {"CaptureFPS": "0.00"}
        mon = Monitor(client, raw)
        # Simulate update_monitor refreshing _raw_result with new FPS
        fresh_raw = _make_raw()
        fresh_raw["Monitor_Status"] = {"CaptureFPS": "15.00"}
        mon.update_monitor = lambda: setattr(mon, "_raw_result", fresh_raw)
        assert mon.is_available is True


# ---------------------------------------------------------------------------
# get_events
# ---------------------------------------------------------------------------

class TestMonitorGetEvents:
    def test_returns_count_from_dict(self):
        client = StubClient(get_state_return={"results": {"1": 42, "2": 10}})
        mon = Monitor(client, _make_raw(mid=1))
        assert mon.get_events(TimePeriod.ALL) == 42

    def test_returns_zero_for_missing_monitor(self):
        client = StubClient(get_state_return={"results": {"2": 10}})
        mon = Monitor(client, _make_raw(mid=1))
        assert mon.get_events(TimePeriod.ALL) == 0

    def test_returns_zero_for_empty_list(self):
        """ZM returns [] when no events exist."""
        client = StubClient(get_state_return={"results": []})
        mon = Monitor(client, _make_raw(mid=1))
        assert mon.get_events(TimePeriod.ALL) == 0

    def test_returns_none_on_error(self):
        client = StubClient(get_state_return={})
        mon = Monitor(client, _make_raw(mid=1))
        assert mon.get_events(TimePeriod.ALL) is None

    def test_all_time_periods(self):
        """Each TimePeriod should produce a valid get_events call."""
        client = StubClient(get_state_return={"results": {"1": 5}})
        mon = Monitor(client, _make_raw(mid=1))
        for tp in TimePeriod:
            assert mon.get_events(tp) == 5

    def test_include_archived(self):
        """include_archived=True should still work (different URL)."""
        client = StubClient(get_state_return={"results": {"1": 3}})
        mon = Monitor(client, _make_raw(mid=1))
        assert mon.get_events(TimePeriod.ALL, include_archived=True) == 3


# ---------------------------------------------------------------------------
# function property
# ---------------------------------------------------------------------------

class TestMonitorFunction:
    def test_getter_returns_monitor_state(self):
        """function getter calls update_monitor() then reads Function."""
        get_return = {
            "monitor": {
                "Monitor": {"Function": "Modect"},
                "Monitor_Status": {"CaptureFPS": "10.00"},
            }
        }
        client = StubClient(get_state_return=get_return)
        mon = Monitor(client, _make_raw(function="Monitor"))
        assert mon.function == MonitorState.MODECT

    def test_setter_posts_new_function(self):
        client = StubClient()
        mon = Monitor(client, _make_raw())
        mon.function = MonitorState.RECORD
        assert len(client._change_state_calls) == 1
        url, data = client._change_state_calls[0]
        assert "monitors/1.json" in url
        assert data == {"Monitor[Function]": "Record"}


# ---------------------------------------------------------------------------
# update_monitor
# ---------------------------------------------------------------------------

class TestUpdateMonitor:
    def test_refreshes_raw_result(self):
        updated = {
            "monitor": {
                "Monitor": {"Function": "Mocord"},
                "Monitor_Status": {"CaptureFPS": "15.00"},
            }
        }
        client = StubClient(get_state_return=updated)
        mon = Monitor(client, _make_raw())
        mon.update_monitor()
        assert mon._raw_result["Monitor"]["Function"] == "Mocord"

    def test_second_call_within_ttl_does_not_refetch(self):
        """Within 1s TTL, update_monitor should use cached data."""
        updated = {
            "monitor": {
                "Monitor": {"Function": "Mocord"},
                "Monitor_Status": {"CaptureFPS": "15.00"},
            }
        }
        client = StubClient(get_state_return=updated)
        mon = Monitor(client, _make_raw())
        mon.update_monitor()
        mon.update_monitor()
        mon.update_monitor()
        assert client._get_state_call_count == 1

    @patch("zoneminder.monitor.time.monotonic")
    def test_cache_expires_after_ttl(self, mock_monotonic):
        """After TTL expires, update_monitor should re-fetch."""
        updated = {
            "monitor": {
                "Monitor": {"Function": "Mocord"},
                "Monitor_Status": {"CaptureFPS": "15.00"},
            }
        }
        client = StubClient(get_state_return=updated)
        mon = Monitor(client, _make_raw())

        mock_monotonic.return_value = 100.0
        mon.update_monitor()
        assert client._get_state_call_count == 1

        # Still within TTL
        mock_monotonic.return_value = 100.5
        mon.update_monitor()
        assert client._get_state_call_count == 1

        # TTL expired
        mock_monotonic.return_value = 101.1
        mon.update_monitor()
        assert client._get_state_call_count == 2

    def test_function_setter_invalidates_cache(self):
        """After setting function, next read should re-fetch."""
        updated = {
            "monitor": {
                "Monitor": {"Function": "Record"},
                "Monitor_Status": {"CaptureFPS": "10.00"},
            }
        }
        client = StubClient(get_state_return=updated)
        mon = Monitor(client, _make_raw())

        # First read fetches
        _ = mon.function
        assert client._get_state_call_count == 1

        # Set function (invalidates cache)
        mon.function = MonitorState.RECORD

        # Next read should re-fetch despite being within 1s
        _ = mon.function
        assert client._get_state_call_count == 2


# ---------------------------------------------------------------------------
# PTZ control
# ---------------------------------------------------------------------------

class TestPtzControlCommand:
    """PTZ tests using mocked requests.post -- no live server needed."""

    def test_raises_on_non_controllable(self):
        mon = Monitor(StubClient(), _make_raw(controllable="0"))
        with pytest.raises(MonitorControlTypeError):
            mon.ptz_control_command("right", "fake-token", "http://zm.test/zm/")

    def test_raises_on_invalid_direction(self):
        mon = Monitor(StubClient(), _make_raw(controllable="1"))
        with pytest.raises(ControlTypeError):
            mon.ptz_control_command("invalid-dir", "fake-token", "http://zm.test/zm/")

    @patch("zoneminder.monitor.post")
    def test_sends_post_request(self, mock_post):
        mock_post.return_value.ok = True
        mon = Monitor(StubClient(), _make_raw(controllable="1"))
        result = mon.ptz_control_command("right", "test-token", "http://zm.test/zm/")
        assert result is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["url"] == "http://zm.test/zm/index.php"

    @patch("zoneminder.monitor.post")
    def test_params_contain_control_value(self, mock_post):
        mock_post.return_value.ok = True
        mon = Monitor(StubClient(), _make_raw(controllable="1"))
        mon.ptz_control_command("up", "tok", "http://zm.test/zm/")
        params = mock_post.call_args.kwargs["params"]
        assert params["control"] == "moveConUp"
        assert params["id"] == 1
        assert params["token"] == "tok"
        assert params["view"] == "request"
        assert params["request"] == "control"

    @patch("zoneminder.monitor.post")
    def test_all_directions(self, mock_post):
        """All 8 directions should succeed."""
        mock_post.return_value.ok = True
        mon = Monitor(StubClient(), _make_raw(controllable="1"))
        for direction in ("right", "left", "up", "down",
                          "up-left", "up-right", "down-left", "down-right"):
            result = mon.ptz_control_command(direction, "tok", "http://zm.test/zm/")
            assert result is True

    @patch("zoneminder.monitor.post")
    def test_returns_false_on_http_error(self, mock_post):
        mock_post.return_value.ok = False
        mon = Monitor(StubClient(), _make_raw(controllable="1"))
        result = mon.ptz_control_command("right", "tok", "http://zm.test/zm/")
        assert result is False

    @patch("zoneminder.monitor.post")
    def test_ptz_passes_verify_ssl(self, mock_post):
        """PTZ should pass verify= kwarg to requests.post."""
        mock_post.return_value.ok = True
        client = StubClient()
        client._verify_ssl = False
        mon = Monitor(client, _make_raw(controllable="1"))
        mon.ptz_control_command("right", "tok", "http://zm.test/zm/")
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["verify"] is False

    @patch("zoneminder.monitor.post")
    def test_returns_false_on_connection_error(self, mock_post):
        """ConnectionError should return False, not crash."""
        import requests as _req

        mock_post.side_effect = _req.exceptions.ConnectionError("refused")
        mon = Monitor(StubClient(), _make_raw(controllable="1"))
        result = mon.ptz_control_command("right", "tok", "http://zm.test/zm/")
        assert result is False

    @patch("zoneminder.monitor.post")
    def test_no_token_param_when_token_is_none(self, mock_post):
        """Legacy auth: token=None should not appear in params."""
        mock_post.return_value.ok = True
        mon = Monitor(StubClient(), _make_raw(controllable="1"))
        mon.ptz_control_command("right", None, "http://zm.test/zm/")
        params = mock_post.call_args.kwargs["params"]
        assert "token" not in params

    @patch("zoneminder.monitor.post")
    def test_cookies_passed_through(self, mock_post):
        """Cookies should be forwarded to requests.post."""
        mock_post.return_value.ok = True
        mon = Monitor(StubClient(), _make_raw(controllable="1"))
        cookies = {"ZMSESSID": "abc123"}
        mon.ptz_control_command("right", None, "http://zm.test/zm/", cookies=cookies)
        assert mock_post.call_args.kwargs["cookies"] == cookies


# ---------------------------------------------------------------------------
# Multi-server URL routing
# ---------------------------------------------------------------------------


class TestMonitorMultiServerUrls:
    """Verify that Monitor delegates ZMS URL resolution to the client."""

    def test_raw_monitor_property(self):
        mon = Monitor(StubClient(), _make_raw())
        assert mon.raw_monitor["Id"] == "1"
        assert mon.raw_monitor["Name"] == "Front Door"

    def test_raw_monitor_contains_server_id(self):
        mon = Monitor(StubClient(), _make_raw(server_id="2"))
        assert mon.raw_monitor["ServerId"] == "2"

    def test_image_url_uses_get_zms_url_for_monitor(self):
        """_build_image_url should call get_zms_url_for_monitor, not get_zms_url."""
        client = StubClient(zms_url="http://main.test/zm/cgi-bin/nph-zms")

        # Override to return a per-server URL
        client.get_zms_url_for_monitor = lambda raw: "http://server2.test/zm/cgi-bin/nph-zms"

        mon = Monitor(client, _make_raw(server_id="2"))
        assert mon.mjpeg_image_url.startswith("http://server2.test/zm/cgi-bin/nph-zms?")
        assert mon.still_image_url.startswith("http://server2.test/zm/cgi-bin/nph-zms?")

    def test_image_url_falls_back_to_main(self):
        """ServerId=0 should use the main ZMS URL."""
        client = StubClient(zms_url="http://main.test/zm/cgi-bin/nph-zms")
        mon = Monitor(client, _make_raw(server_id="0"))
        assert mon.mjpeg_image_url.startswith("http://main.test/zm/cgi-bin/nph-zms?")


# ---------------------------------------------------------------------------
# Version parsing and alarm state table selection
# ---------------------------------------------------------------------------


class TestParseVersion:
    def test_standard_version(self):
        assert _parse_version("1.36.26") == (1, 36, 26)

    def test_two_part_version(self):
        assert _parse_version("1.38") == (1, 38)

    def test_four_part_version(self):
        assert _parse_version("1.36.26.1") == (1, 36, 26, 1)

    def test_none_returns_none(self):
        assert _parse_version(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_version("") is None

    def test_garbage_returns_none(self):
        assert _parse_version("not-a-version") is None


class TestGetApiAlarmStates:
    """Verify the version-to-state-table mapping."""

    def test_pre_1_36_16_uses_offset(self):
        """Versions before 1.36.16 had UNKNOWN=-1 in C++ enum, so ALARM=2."""
        states = get_api_alarm_states("1.36.0")
        assert states["ALARM"] == 2

    def test_1_36_15_uses_offset(self):
        states = get_api_alarm_states("1.36.15")
        assert states["ALARM"] == 2

    def test_1_36_16_no_offset(self):
        """1.36.16 shifted UNKNOWN to 0 but no -1 hack yet, so ALARM=3."""
        states = get_api_alarm_states("1.36.16")
        assert states["ALARM"] == 3

    def test_1_36_20_no_offset(self):
        states = get_api_alarm_states("1.36.20")
        assert states["ALARM"] == 3

    def test_1_36_25_no_offset(self):
        """Last version without the -1 hack."""
        states = get_api_alarm_states("1.36.25")
        assert states["ALARM"] == 3

    def test_1_36_26_uses_offset(self):
        """1.36.26 introduced the -1 hack, so ALARM=2 again."""
        states = get_api_alarm_states("1.36.26")
        assert states["ALARM"] == 2

    def test_1_36_33_uses_offset(self):
        states = get_api_alarm_states("1.36.33")
        assert states["ALARM"] == 2

    def test_1_36_two_part_uses_offset(self):
        """'1.36' (no patch) is effectively 1.36.0, before the no-offset window."""
        states = get_api_alarm_states("1.36")
        assert states["ALARM"] == 2

    def test_1_37_uses_offset(self):
        states = get_api_alarm_states("1.37.61")
        assert states["ALARM"] == 2

    def test_1_38_uses_offset(self):
        states = get_api_alarm_states("1.38.0")
        assert states["ALARM"] == 2

    def test_none_version_defaults_to_offset(self):
        """Unknown version falls back to the offset table (most common)."""
        states = get_api_alarm_states(None)
        assert states["ALARM"] == 2

    def test_all_states_present(self):
        """Both tables should contain all 5 state keys."""
        expected_keys = {"UNKNOWN", "IDLE", "PREALARM", "ALARM", "ALERT"}
        assert set(API_STATES_WITH_OFFSET.keys()) == expected_keys
        assert set(API_STATES_NO_OFFSET.keys()) == expected_keys

    def test_tables_differ_by_one(self):
        """The offset table values should each be 1 less than the no-offset table."""
        for key in API_STATES_WITH_OFFSET:
            assert API_STATES_WITH_OFFSET[key] == API_STATES_NO_OFFSET[key] - 1
