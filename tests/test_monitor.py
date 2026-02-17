"""Unit tests for the Monitor class.

Tests construction, properties, URL building, and response parsing logic
using a stub client -- no live ZoneMinder server needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from zoneminder.exceptions import ControlTypeError, MonitorControlTypeError
from zoneminder.monitor import (
    _FUNCTION_TO_NEW_FIELDS,
    API_STATES_NO_OFFSET,
    API_STATES_WITH_OFFSET,
    Monitor,
    MonitorState,
    TimePeriod,
    _derive_function,
    _is_zm_137_or_later,
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
        self._session = MagicMock()

    @property
    def verify_ssl(self):
        return self._verify_ssl

    @property
    def zm_version(self):
        return self._zm_version

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

    def get_event_counts(self, time_period, include_archived=False):
        """Match the ZoneMinder client's event-count interface."""
        resp = self._get_state_return
        try:
            result = resp["results"]
            if isinstance(result, list):
                return {}
            return result
        except (TypeError, KeyError):
            return None


def _make_raw(
    mid=1,
    name="Front Door",
    controllable="0",
    function="Monitor",
    buffer="0",
    server_id="0",
    capturing=None,
    analysing=None,
    recording=None,
):
    """Build a raw monitor result dict matching the ZM API shape.

    When capturing/analysing/recording are provided, include them in the
    Monitor dict to simulate ZM 1.37+ API responses.
    """
    monitor = {
        "Id": str(mid),
        "Name": name,
        "Controllable": controllable,
        "Function": function,
        "StreamReplayBuffer": buffer,
        "ServerId": server_id,
    }
    if capturing is not None:
        monitor["Capturing"] = capturing
    if analysing is not None:
        monitor["Analysing"] = analysing
    if recording is not None:
        monitor["Recording"] = recording
    return {
        "Monitor": monitor,
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
        """Build a monitor for is_available tests.

        Uses a multi-response client: first call returns daemon_status,
        second call (update_monitor) returns monitor data with the FPS.
        """
        responses = []
        responses.append(daemon_status)
        if has_monitor_status:
            responses.append({
                "monitor": {
                    "Monitor": {
                        "Id": "1", "Name": "Front Door", "Controllable": "0",
                        "Function": "Monitor", "StreamReplayBuffer": "0", "ServerId": "0",
                    },
                    "Monitor_Status": {"CaptureFPS": capture_fps},
                }
            })
        else:
            responses.append({
                "monitor": {
                    "Monitor": {
                        "Id": "1", "Name": "Front Door", "Controllable": "0",
                        "Function": "Monitor", "StreamReplayBuffer": "0", "ServerId": "0",
                    },
                }
            })

        client = StubClient()
        call_idx = 0

        def multi_get_state(api_url):
            nonlocal call_idx
            client._get_state_call_count += 1
            if call_idx < len(responses):
                resp = responses[call_idx]
                call_idx += 1
                return resp
            return {}

        client.get_state = multi_get_state

        raw = _make_raw()
        if has_monitor_status:
            raw["Monitor_Status"] = {"CaptureFPS": capture_fps}
        else:
            del raw["Monitor_Status"]
        mon = Monitor(client, raw)
        mon._last_update = 0.0  # Expire TTL to allow update_monitor to fetch
        return mon, client

    def test_available_when_daemon_running_and_fps_nonzero(self):
        mon, _ = self._make_available_monitor({"status": True}, capture_fps="10.00")
        assert mon.is_available is True

    def test_unavailable_when_daemon_not_running(self):
        mon, _ = self._make_available_monitor({"status": False}, capture_fps="10.00")
        assert mon.is_available is False

    def test_unavailable_when_fps_zero(self):
        mon, _ = self._make_available_monitor({"status": True}, capture_fps="0.00")
        assert mon.is_available is False

    def test_unavailable_when_no_monitor_status(self):
        """Without Monitor_Status, should be unavailable."""
        mon, _ = self._make_available_monitor({"status": True}, has_monitor_status=False)
        assert mon.is_available is False

    def test_unavailable_when_no_response(self):
        client = StubClient(get_state_return={})
        mon = Monitor(client, _make_raw())
        assert mon.is_available is False

    def test_refreshes_monitor_data(self):
        """is_available should call update_monitor to get fresh FPS data."""
        mon, client = self._make_available_monitor({"status": True}, capture_fps="15.00")
        assert mon.is_available is True
        assert client._get_state_call_count == 2  # daemon status + update_monitor


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

class TestMonitorFunctionLegacy:
    """Test function getter/setter on ZM < 1.37 (legacy Function column)."""

    def test_getter_returns_monitor_state(self):
        """function getter reads Function from cached raw_result."""
        client = StubClient(zm_version="1.36.33")
        mon = Monitor(client, _make_raw(function="Modect"))
        assert mon.function == MonitorState.MODECT
        assert client._get_state_call_count == 0

    def test_getter_does_not_fetch_even_when_cache_expired(self):
        """BUG-03 regression: function getter must never call update_monitor().

        Even after the 1s TTL expires, reading function should be a pure read
        from _raw_result with zero API calls.
        """
        client = StubClient(zm_version="1.36.33")
        mon = Monitor(client, _make_raw(function="Modect"))
        mon._last_update = 0.0  # Expire the TTL cache
        assert mon.function == MonitorState.MODECT
        assert client._get_state_call_count == 0

    def test_setter_posts_function_column(self):
        """On ZM < 1.37, setter writes Monitor[Function]."""
        client = StubClient(zm_version="1.36.33")
        mon = Monitor(client, _make_raw())
        mon.function = MonitorState.RECORD
        assert len(client._change_state_calls) == 1
        url, data = client._change_state_calls[0]
        assert "monitors/1.json" in url
        assert data == {"Monitor[Function]": "Record"}

    def test_getter_all_states(self):
        """Each MonitorState should parse correctly from the Function column."""
        client = StubClient(zm_version="1.36.33")
        for state in MonitorState:
            mon = Monitor(client, _make_raw(function=state.value))
            assert mon.function == state


class TestMonitorFunctionZm137:
    """Test function getter/setter on ZM >= 1.37 (new decomposed fields)."""

    def test_getter_derives_from_new_fields(self):
        """On ZM >= 1.37, getter derives state from Capturing/Analysing/Recording."""
        client = StubClient(zm_version="1.38.0")
        raw = _make_raw(
            function="Monitor",  # stale Function column
            capturing="Always",
            analysing="Always",
            recording="OnMotion",
        )
        mon = Monitor(client, raw)
        # Should derive MODECT from new fields, ignoring stale Function
        assert mon.function == MonitorState.MODECT

    @pytest.mark.parametrize(
        "state,capturing,analysing,recording",
        [
            (MonitorState.NONE, "None", "None", "None"),
            (MonitorState.MONITOR, "Always", "None", "None"),
            (MonitorState.MODECT, "Always", "Always", "OnMotion"),
            (MonitorState.RECORD, "Always", "None", "Always"),
            (MonitorState.MOCORD, "Always", "Always", "Always"),
            (MonitorState.NODECT, "Always", "None", "OnMotion"),
        ],
    )
    def test_getter_all_states(self, state, capturing, analysing, recording):
        """Each classic MonitorState should be derivable from the new fields."""
        client = StubClient(zm_version="1.38.0")
        raw = _make_raw(capturing=capturing, analysing=analysing, recording=recording)
        mon = Monitor(client, raw)
        assert mon.function == state

    def test_getter_falls_back_to_function_on_unmappable_combination(self):
        """Unmappable new-field combo falls back to Function column."""
        client = StubClient(zm_version="1.38.0")
        raw = _make_raw(
            function="Monitor",
            capturing="Ondemand",  # Not in any classic mapping
            analysing="None",
            recording="None",
        )
        mon = Monitor(client, raw)
        assert mon.function == MonitorState.MONITOR

    def test_getter_falls_back_when_new_fields_missing(self):
        """If new fields aren't in the API response, fall back to Function."""
        client = StubClient(zm_version="1.38.0")
        raw = _make_raw(function="Modect")  # No new fields
        mon = Monitor(client, raw)
        assert mon.function == MonitorState.MODECT

    def test_getter_does_not_fetch(self):
        """Getter should never make API calls, even on ZM 1.37+."""
        client = StubClient(zm_version="1.38.0")
        raw = _make_raw(capturing="Always", analysing="Always", recording="OnMotion")
        mon = Monitor(client, raw)
        mon._last_update = 0.0
        assert mon.function == MonitorState.MODECT
        assert client._get_state_call_count == 0

    @pytest.mark.parametrize(
        "state,expected_fields",
        [
            (
                MonitorState.NONE,
                {
                    "Monitor[Capturing]": "None",
                    "Monitor[Analysing]": "None",
                    "Monitor[Recording]": "None",
                },
            ),
            (
                MonitorState.MONITOR,
                {
                    "Monitor[Capturing]": "Always",
                    "Monitor[Analysing]": "None",
                    "Monitor[Recording]": "None",
                },
            ),
            (
                MonitorState.MODECT,
                {
                    "Monitor[Capturing]": "Always",
                    "Monitor[Analysing]": "Always",
                    "Monitor[Recording]": "OnMotion",
                },
            ),
            (
                MonitorState.RECORD,
                {
                    "Monitor[Capturing]": "Always",
                    "Monitor[Analysing]": "None",
                    "Monitor[Recording]": "Always",
                },
            ),
            (
                MonitorState.MOCORD,
                {
                    "Monitor[Capturing]": "Always",
                    "Monitor[Analysing]": "Always",
                    "Monitor[Recording]": "Always",
                },
            ),
            (
                MonitorState.NODECT,
                {
                    "Monitor[Capturing]": "Always",
                    "Monitor[Analysing]": "None",
                    "Monitor[Recording]": "OnMotion",
                },
            ),
        ],
    )
    def test_setter_posts_new_fields(self, state, expected_fields):
        """On ZM >= 1.37, setter writes Capturing/Analysing/Recording."""
        client = StubClient(zm_version="1.38.0")
        mon = Monitor(client, _make_raw())
        mon.function = state
        assert len(client._change_state_calls) == 1
        url, data = client._change_state_calls[0]
        assert "monitors/1.json" in url
        assert data == expected_fields

    def test_setter_does_not_post_function_column(self):
        """On ZM >= 1.37, setter must NOT write Monitor[Function]."""
        client = StubClient(zm_version="1.38.0")
        mon = Monitor(client, _make_raw())
        mon.function = MonitorState.MODECT
        _, data = client._change_state_calls[0]
        assert "Monitor[Function]" not in data

    def test_setter_invalidates_cache(self):
        """After setting function on ZM 1.37+, cache should be invalidated."""
        client = StubClient(zm_version="1.38.0")
        mon = Monitor(client, _make_raw())
        mon.function = MonitorState.RECORD
        assert mon._last_update == 0.0


class TestDeriveFunction:
    """Test the _derive_function helper directly."""

    def test_none(self):
        assert _derive_function("None", "None", "None") == MonitorState.NONE

    def test_none_ignores_analysing_recording(self):
        """When Capturing=None, result is NONE regardless of other fields."""
        assert _derive_function("None", "Always", "Always") == MonitorState.NONE

    def test_monitor(self):
        assert _derive_function("Always", "None", "None") == MonitorState.MONITOR

    def test_modect(self):
        assert _derive_function("Always", "Always", "OnMotion") == MonitorState.MODECT

    def test_record(self):
        assert _derive_function("Always", "None", "Always") == MonitorState.RECORD

    def test_mocord(self):
        assert _derive_function("Always", "Always", "Always") == MonitorState.MOCORD

    def test_nodect(self):
        assert _derive_function("Always", "None", "OnMotion") == MonitorState.NODECT

    def test_unmappable_returns_none(self):
        """Ondemand capturing doesn't map to any classic MonitorState."""
        assert _derive_function("Ondemand", "None", "None") is None


class TestIsZm137OrLater:
    """Test the version check helper."""

    def test_136(self):
        assert _is_zm_137_or_later("1.36.33") is False

    def test_137(self):
        assert _is_zm_137_or_later("1.37.0") is True

    def test_1370(self):
        assert _is_zm_137_or_later("1.37") is True

    def test_138(self):
        assert _is_zm_137_or_later("1.38.0") is True

    def test_none(self):
        assert _is_zm_137_or_later(None) is False

    def test_garbage(self):
        assert _is_zm_137_or_later("not-a-version") is False


class TestFunctionToNewFieldsMapping:
    """Verify the mapping table covers all MonitorState values."""

    def test_all_states_mapped(self):
        for state in MonitorState:
            assert state in _FUNCTION_TO_NEW_FIELDS

    def test_all_entries_have_three_fields(self):
        for state, fields in _FUNCTION_TO_NEW_FIELDS.items():
            assert set(fields.keys()) == {"Capturing", "Analysing", "Recording"}, (
                f"{state} missing fields"
            )


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
        mon._last_update = 0.0  # Expire cache to force fetch
        mon.update_monitor()
        assert mon._raw_result["Monitor"]["Function"] == "Mocord"

    def test_empty_response_preserves_existing_data(self):
        """Empty API response should log warning and keep stale data, not crash."""
        client = StubClient(get_state_return={})
        mon = Monitor(client, _make_raw(function="Modect"))
        mon._last_update = 0.0  # Expire cache to force fetch
        mon.update_monitor()
        # Original data should be preserved
        assert mon.function == MonitorState.MODECT

    def test_missing_monitor_key_preserves_existing_data(self):
        """Response without 'monitor' key should not crash."""
        client = StubClient(get_state_return={"other": "data"})
        mon = Monitor(client, _make_raw(function="Record"))
        mon._last_update = 0.0
        mon.update_monitor()
        assert mon.function == MonitorState.RECORD

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
        mon._last_update = 0.0  # Expire cache so first call fetches
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
        mock_monotonic.return_value = 99.0  # Constructor time
        client = StubClient(get_state_return=updated)
        mon = Monitor(client, _make_raw())

        mock_monotonic.return_value = 100.0  # 1.0s after constructor -> TTL expired
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
        """After setting function, explicit update_monitor() should re-fetch."""
        updated = {
            "monitor": {
                "Monitor": {"Function": "Record"},
                "Monitor_Status": {"CaptureFPS": "10.00"},
            }
        }
        client = StubClient(get_state_return=updated)
        mon = Monitor(client, _make_raw())

        # Set function (invalidates cache by setting _last_update = 0.0)
        mon.function = MonitorState.RECORD
        assert client._get_state_call_count == 0

        # Explicit update_monitor() should re-fetch since cache is invalidated
        mon.update_monitor()
        assert client._get_state_call_count == 1
        assert mon.function == MonitorState.RECORD


# ---------------------------------------------------------------------------
# _apply_raw_result
# ---------------------------------------------------------------------------

class TestApplyRawResult:
    def test_updates_raw_result(self):
        """_apply_raw_result should replace _raw_result with new data."""
        client = StubClient()
        mon = Monitor(client, _make_raw(function="Monitor"))
        assert mon.function == MonitorState.MONITOR

        new_raw = _make_raw(function="Modect")
        mon._apply_raw_result(new_raw)
        assert mon.function == MonitorState.MODECT

    def test_sets_last_update_so_ttl_prevents_refetch(self):
        """After _apply_raw_result, update_monitor() should be a TTL cache hit."""
        client = StubClient(get_state_return={
            "monitor": _make_raw(function="Record"),
        })
        mon = Monitor(client, _make_raw(function="Monitor"))
        mon._apply_raw_result(_make_raw(function="Modect"))

        # update_monitor() should skip fetch due to TTL
        mon.update_monitor()
        assert client._get_state_call_count == 0


# ---------------------------------------------------------------------------
# PTZ control
# ---------------------------------------------------------------------------

class TestPtzControlCommand:
    """PTZ tests using mocked session -- no live server needed."""

    def test_raises_on_non_controllable(self):
        mon = Monitor(StubClient(), _make_raw(controllable="0"))
        with pytest.raises(MonitorControlTypeError):
            mon.ptz_control_command("right", "fake-token", "http://zm.test/zm/")

    def test_raises_on_invalid_direction(self):
        mon = Monitor(StubClient(), _make_raw(controllable="1"))
        with pytest.raises(ControlTypeError):
            mon.ptz_control_command("invalid-dir", "fake-token", "http://zm.test/zm/")

    def test_sends_post_request(self):
        client = StubClient()
        client._session.post.return_value = MagicMock(ok=True)
        mon = Monitor(client, _make_raw(controllable="1"))
        result = mon.ptz_control_command("right", "test-token", "http://zm.test/zm/")
        assert result is True
        client._session.post.assert_called_once()
        call_kwargs = client._session.post.call_args
        assert call_kwargs.kwargs["url"] == "http://zm.test/zm/index.php"

    def test_params_contain_control_value(self):
        client = StubClient()
        client._session.post.return_value = MagicMock(ok=True)
        mon = Monitor(client, _make_raw(controllable="1"))
        mon.ptz_control_command("up", "tok", "http://zm.test/zm/")
        params = client._session.post.call_args.kwargs["params"]
        assert params["control"] == "moveConUp"
        assert params["id"] == 1
        assert params["token"] == "tok"
        assert params["view"] == "request"
        assert params["request"] == "control"

    def test_all_directions(self):
        """All 8 directions should succeed."""
        client = StubClient()
        client._session.post.return_value = MagicMock(ok=True)
        mon = Monitor(client, _make_raw(controllable="1"))
        for direction in ("right", "left", "up", "down",
                          "up-left", "up-right", "down-left", "down-right"):
            result = mon.ptz_control_command(direction, "tok", "http://zm.test/zm/")
            assert result is True

    def test_returns_false_on_http_error(self):
        client = StubClient()
        client._session.post.return_value = MagicMock(ok=False)
        mon = Monitor(client, _make_raw(controllable="1"))
        result = mon.ptz_control_command("right", "tok", "http://zm.test/zm/")
        assert result is False

    def test_ptz_uses_session(self):
        """PTZ should use the client's session for connection pooling."""
        client = StubClient()
        client._session.post.return_value = MagicMock(ok=True)
        mon = Monitor(client, _make_raw(controllable="1"))
        mon.ptz_control_command("right", "tok", "http://zm.test/zm/")
        client._session.post.assert_called_once()

    def test_returns_false_on_connection_error(self):
        """ConnectionError should return False, not crash."""
        import requests as _req

        client = StubClient()
        client._session.post.side_effect = _req.exceptions.ConnectionError("refused")
        mon = Monitor(client, _make_raw(controllable="1"))
        result = mon.ptz_control_command("right", "tok", "http://zm.test/zm/")
        assert result is False

    def test_returns_false_on_timeout(self):
        """Timeout should return False, not crash."""
        import requests as _req

        client = StubClient()
        client._session.post.side_effect = _req.exceptions.Timeout("timed out")
        mon = Monitor(client, _make_raw(controllable="1"))
        result = mon.ptz_control_command("right", "tok", "http://zm.test/zm/")
        assert result is False

    def test_no_token_param_when_token_is_none(self):
        """Legacy auth: token=None should not appear in params."""
        client = StubClient()
        client._session.post.return_value = MagicMock(ok=True)
        mon = Monitor(client, _make_raw(controllable="1"))
        mon.ptz_control_command("right", None, "http://zm.test/zm/")
        params = client._session.post.call_args.kwargs["params"]
        assert "token" not in params

    def test_cookies_passed_through(self):
        """Cookies should be forwarded to session.post."""
        client = StubClient()
        client._session.post.return_value = MagicMock(ok=True)
        mon = Monitor(client, _make_raw(controllable="1"))
        cookies = {"ZMSESSID": "abc123"}
        mon.ptz_control_command("right", None, "http://zm.test/zm/", cookies=cookies)
        assert client._session.post.call_args.kwargs["cookies"] == cookies


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
