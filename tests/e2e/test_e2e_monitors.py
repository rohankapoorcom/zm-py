"""E2E tests for ZoneMinder monitor operations.

Covers get_monitors(), Monitor properties, update_monitor(), function
get/set, is_recording, is_available, get_events(), and image URL building.
"""

from __future__ import annotations

import pytest

from zoneminder.monitor import Monitor, MonitorState, TimePeriod


pytestmark = pytest.mark.zm_e2e


class TestGetMonitors:
    """ZoneMinder.get_monitors() -- list all monitors."""

    def test_returns_list(self, zm_client):
        monitors = zm_client.get_monitors()
        assert isinstance(monitors, list)

    def test_has_at_least_one_monitor(self, monitors):
        assert len(monitors) > 0, "Expected at least one monitor on the ZM server"

    def test_elements_are_monitor_instances(self, monitors):
        for mon in monitors:
            assert isinstance(mon, Monitor)

    def test_each_monitor_has_positive_id(self, monitors):
        for mon in monitors:
            assert isinstance(mon.id, int)
            assert mon.id > 0

    def test_each_monitor_has_name(self, monitors):
        for mon in monitors:
            assert isinstance(mon.name, str)
            assert len(mon.name) > 0

    def test_controllable_is_bool(self, monitors):
        for mon in monitors:
            assert isinstance(mon.controllable, bool)


class TestMonitorProperties:
    """Individual Monitor property accessors."""

    def test_id_is_int(self, any_monitor):
        assert isinstance(any_monitor.id, int)
        assert any_monitor.id > 0

    def test_name_is_str(self, any_monitor):
        assert isinstance(any_monitor.name, str)
        assert len(any_monitor.name) > 0

    def test_repr_contains_id(self, any_monitor):
        r = repr(any_monitor)
        assert str(any_monitor.id) in r

    def test_str_matches_repr(self, any_monitor):
        assert str(any_monitor) == repr(any_monitor)


class TestUpdateMonitor:
    """Monitor.update_monitor() -- refresh from API."""

    def test_update_does_not_raise(self, any_monitor):
        """update_monitor() should fetch fresh data without errors."""
        any_monitor.update_monitor()

    def test_raw_result_has_monitor_key(self, any_monitor):
        """After update, _raw_result should contain Monitor dict."""
        any_monitor.update_monitor()
        assert "Monitor" in any_monitor._raw_result


class TestMonitorFunction:
    """Monitor.function property -- get the current MonitorState."""

    def test_function_returns_monitor_state(self, any_monitor):
        """function should return a valid MonitorState enum value."""
        func = any_monitor.function
        assert isinstance(func, MonitorState)

    def test_function_is_known_value(self, any_monitor):
        """The function value should be one of the known states."""
        func = any_monitor.function
        assert func in list(MonitorState)


@pytest.mark.zm_e2e_write
class TestMonitorFunctionSet:
    """Monitor.function setter -- change monitor state (write test)."""

    def test_set_function_roundtrip(self, any_monitor):
        """Setting function and reading it back should match."""
        original = any_monitor.function
        try:
            target = MonitorState.MONITOR
            any_monitor.function = target
            result = any_monitor.function
            assert result == target
        finally:
            any_monitor.function = original


class TestMonitorIsRecording:
    """Monitor.is_recording property -- alarm status check."""

    def test_is_recording_returns_bool_or_none(self, any_monitor):
        """is_recording should return bool or None (if status unavailable)."""
        result = any_monitor.is_recording
        assert result is None or isinstance(result, bool)


class TestMonitorIsAvailable:
    """Monitor.is_available property -- daemon status check."""

    def test_is_available_returns_bool(self, any_monitor):
        """is_available should return a boolean."""
        result = any_monitor.is_available
        assert isinstance(result, bool)


class TestMonitorGetEvents:
    """Monitor.get_events() -- consoleEvents endpoint."""

    def test_get_events_all_returns_int_or_none(self, any_monitor):
        """get_events(ALL) should return an int count or None."""
        result = any_monitor.get_events(TimePeriod.ALL)
        assert result is None or isinstance(result, int)

    def test_get_events_hour_returns_int_or_none(self, any_monitor):
        result = any_monitor.get_events(TimePeriod.HOUR)
        assert result is None or isinstance(result, int)

    def test_get_events_day_returns_int_or_none(self, any_monitor):
        result = any_monitor.get_events(TimePeriod.DAY)
        assert result is None or isinstance(result, int)

    def test_get_events_week_returns_int_or_none(self, any_monitor):
        result = any_monitor.get_events(TimePeriod.WEEK)
        assert result is None or isinstance(result, int)

    def test_get_events_month_returns_int_or_none(self, any_monitor):
        result = any_monitor.get_events(TimePeriod.MONTH)
        assert result is None or isinstance(result, int)

    def test_get_events_all_gte_zero(self, any_monitor):
        """Event counts should be non-negative when returned."""
        result = any_monitor.get_events(TimePeriod.ALL)
        if result is not None:
            assert result >= 0

    def test_get_events_include_archived(self, any_monitor):
        """include_archived=True should not raise."""
        result = any_monitor.get_events(TimePeriod.ALL, include_archived=True)
        assert result is None or isinstance(result, int)


class TestMonitorImageUrls:
    """Monitor MJPEG and still image URL building."""

    def test_mjpeg_url_is_string(self, any_monitor):
        url = any_monitor.mjpeg_image_url
        assert isinstance(url, str)
        assert len(url) > 0

    def test_still_url_is_string(self, any_monitor):
        url = any_monitor.still_image_url
        assert isinstance(url, str)
        assert len(url) > 0

    def test_mjpeg_url_contains_mode_jpeg(self, any_monitor):
        """MJPEG URL should contain mode=jpeg."""
        assert "mode=jpeg" in any_monitor.mjpeg_image_url

    def test_still_url_contains_mode_single(self, any_monitor):
        """Still URL should contain mode=single."""
        assert "mode=single" in any_monitor.still_image_url

    def test_urls_contain_monitor_id(self, any_monitor):
        """Both URLs should reference the monitor's ID."""
        mid = str(any_monitor.id)
        assert mid in any_monitor.mjpeg_image_url
        assert mid in any_monitor.still_image_url

    def test_urls_contain_auth_params(self, zm_client, any_monitor):
        """If credentials are set, URLs should contain user= parameter."""
        if not zm_client._username:
            pytest.skip("No username configured")
        assert "user=" in any_monitor.mjpeg_image_url
        assert "user=" in any_monitor.still_image_url
