"""Unit tests for TimePeriod, MonitorState, and ControlType enums."""

from __future__ import annotations

import pytest

from zoneminder.exceptions import ControlTypeError
from zoneminder.monitor import ControlType, MonitorState, TimePeriod


# ---------------------------------------------------------------------------
# TimePeriod
# ---------------------------------------------------------------------------


class TestTimePeriod:
    def test_all_period(self):
        assert TimePeriod.ALL.period == "all"

    def test_hour_period(self):
        assert TimePeriod.HOUR.period == "hour"

    def test_day_period(self):
        assert TimePeriod.DAY.period == "day"

    def test_week_period(self):
        assert TimePeriod.WEEK.period == "week"

    def test_month_period(self):
        assert TimePeriod.MONTH.period == "month"

    def test_all_title(self):
        assert TimePeriod.ALL.title == "Events"

    def test_hour_title(self):
        assert TimePeriod.HOUR.title == "Events Last Hour"

    def test_day_title(self):
        assert TimePeriod.DAY.title == "Events Last Day"

    def test_week_title(self):
        assert TimePeriod.WEEK.title == "Events Last Week"

    def test_month_title(self):
        assert TimePeriod.MONTH.title == "Events Last Month"

    def test_get_time_period_all(self):
        assert TimePeriod.get_time_period("all") is TimePeriod.ALL

    def test_get_time_period_hour(self):
        assert TimePeriod.get_time_period("hour") is TimePeriod.HOUR

    def test_get_time_period_each(self):
        for tp in TimePeriod:
            assert TimePeriod.get_time_period(tp.period) is tp

    def test_get_time_period_invalid(self):
        with pytest.raises(ValueError, match="not a valid TimePeriod"):
            TimePeriod.get_time_period("decade")

    def test_five_members(self):
        assert len(TimePeriod) == 5


# ---------------------------------------------------------------------------
# MonitorState
# ---------------------------------------------------------------------------

class TestMonitorState:
    def test_none_value(self):
        assert MonitorState.NONE.value == "None"

    def test_monitor_value(self):
        assert MonitorState.MONITOR.value == "Monitor"

    def test_modect_value(self):
        assert MonitorState.MODECT.value == "Modect"

    def test_record_value(self):
        assert MonitorState.RECORD.value == "Record"

    def test_mocord_value(self):
        assert MonitorState.MOCORD.value == "Mocord"

    def test_nodect_value(self):
        assert MonitorState.NODECT.value == "Nodect"

    def test_six_members(self):
        assert len(MonitorState) == 6

    def test_roundtrip_from_string(self):
        """Constructing from the string value (as the API returns) works."""
        for state in MonitorState:
            assert MonitorState(state.value) is state


# ---------------------------------------------------------------------------
# ControlType
# ---------------------------------------------------------------------------

class TestControlType:
    def test_right_value(self):
        assert ControlType.RIGHT.value == "moveConRight"

    def test_left_value(self):
        assert ControlType.LEFT.value == "moveConLeft"

    def test_up_value(self):
        assert ControlType.UP.value == "moveConUp"

    def test_down_value(self):
        assert ControlType.DOWN.value == "moveConDown"

    def test_diagonal_values(self):
        assert ControlType.UP_LEFT.value == "moveConUpLeft"
        assert ControlType.UP_RIGHT.value == "moveConUpRight"
        assert ControlType.DOWN_LEFT.value == "moveConDownLeft"
        assert ControlType.DOWN_RIGHT.value == "moveConDownRight"

    def test_eight_members(self):
        assert len(ControlType) == 8

    def test_from_move_case_insensitive(self):
        assert ControlType.from_move("right") == ControlType.RIGHT
        assert ControlType.from_move("RIGHT") == ControlType.RIGHT
        assert ControlType.from_move("Right") == ControlType.RIGHT

    def test_from_move_hyphen_to_underscore(self):
        assert ControlType.from_move("up-left") == ControlType.UP_LEFT
        assert ControlType.from_move("DOWN-RIGHT") == ControlType.DOWN_RIGHT

    def test_from_move_underscore(self):
        assert ControlType.from_move("up_left") == ControlType.UP_LEFT

    def test_from_move_all_directions(self):
        directions = {
            "right": ControlType.RIGHT,
            "left": ControlType.LEFT,
            "up": ControlType.UP,
            "down": ControlType.DOWN,
            "up-left": ControlType.UP_LEFT,
            "up-right": ControlType.UP_RIGHT,
            "down-left": ControlType.DOWN_LEFT,
            "down-right": ControlType.DOWN_RIGHT,
        }
        for move, expected in directions.items():
            assert ControlType.from_move(move) == expected

    def test_from_move_invalid_raises(self):
        with pytest.raises(ControlTypeError):
            ControlType.from_move("diagonal")

    def test_from_move_empty_raises(self):
        with pytest.raises(ControlTypeError):
            ControlType.from_move("")
