"""Unit tests for the Monitor class.

Tests construction, properties, URL building, and response parsing logic
using a stub client -- no live ZoneMinder server needed.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from zoneminder.exceptions import ControlTypeError, MonitorControlTypeError
from zoneminder.monitor import Monitor, MonitorState, TimePeriod


# ---------------------------------------------------------------------------
# Stub client
# ---------------------------------------------------------------------------


class StubClient:
    """Minimal client stub for Monitor construction and method calls."""

    def __init__(self, get_state_return=None, zms_url="http://zm.test/zm/cgi-bin/nph-zms"):
        self._zms_url = zms_url
        self._username = "admin"
        self._password = "secret"
        self._verify_ssl = False
        self._get_state_return = get_state_return or {}
        self._change_state_calls = []

    @property
    def verify_ssl(self):
        return self._verify_ssl

    def get_zms_url(self):
        return self._zms_url

    def get_url_with_auth(self, url):
        return url + "&user=admin&pass=secret"

    def get_state(self, api_url):
        return self._get_state_return

    def change_state(self, api_url, post_data):
        self._change_state_calls.append((api_url, post_data))
        return {}


def _make_raw(
    mid=1,
    name="Front Door",
    controllable="0",
    function="Monitor",
    buffer="0",
):
    """Build a raw monitor result dict matching the ZM API shape."""
    return {
        "Monitor": {
            "Id": str(mid),
            "Name": name,
            "Controllable": controllable,
            "Function": function,
            "StreamReplayBuffer": buffer,
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
    def test_alarm_status_true(self):
        """Alarm status 3 (STATE_ALARM) means recording."""
        client = StubClient(get_state_return={"status": 3})
        mon = Monitor(client, _make_raw())
        assert mon.is_recording is True

    def test_alarm_status_false(self):
        """Alarm status 0 means not recording."""
        client = StubClient(get_state_return={"status": 0})
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
        """Status as string '3' should still match STATE_ALARM."""
        client = StubClient(get_state_return={"status": "3"})
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
