"""E2E tests for PTZ (Pan-Tilt-Zoom) camera control.

These tests require at least one controllable monitor on the ZM server.
Non-controllable monitors are expected to raise MonitorControlTypeError.

Note: ControlType enum mapping tests live in tests/test_ptz.py (unit tests).
"""

from __future__ import annotations

import pytest

from zoneminder.exceptions import MonitorControlTypeError

pytestmark = pytest.mark.zm_e2e


@pytest.fixture
def controllable_monitor(monitors):
    """Find a controllable monitor, skip if none exist."""
    for mon in monitors:
        if mon.controllable:
            return mon
    pytest.skip("No controllable monitors on ZM server")


@pytest.fixture
def non_controllable_monitor(monitors):
    """Find a non-controllable monitor, skip if all are controllable."""
    for mon in monitors:
        if not mon.controllable:
            return mon
    pytest.skip("All monitors are controllable")


class TestPtzNonControllable:
    """PTZ on non-controllable monitors should raise."""

    def test_ptz_command_raises_on_non_controllable(self, zm_client, non_controllable_monitor):
        """ptz_control_command() should raise MonitorControlTypeError directly."""
        with pytest.raises(MonitorControlTypeError):
            non_controllable_monitor.ptz_control_command(
                "right", zm_client._auth_token, zm_client._server_url
            )

    @pytest.mark.xfail(reason="BUG-001: move_monitor swallows MonitorControlTypeError")
    def test_move_monitor_raises_on_non_controllable(self, zm_client, non_controllable_monitor):
        """move_monitor() should propagate MonitorControlTypeError to callers."""
        with pytest.raises(MonitorControlTypeError):
            zm_client.move_monitor(non_controllable_monitor, "right")


@pytest.mark.zm_e2e_write
class TestPtzControllable:
    """PTZ commands on controllable monitors (write test)."""

    def test_move_right(self, zm_client, controllable_monitor):
        """Sending a move command should not raise."""
        zm_client.move_monitor(controllable_monitor, "right")

    def test_move_left(self, zm_client, controllable_monitor):
        zm_client.move_monitor(controllable_monitor, "left")

    def test_move_up(self, zm_client, controllable_monitor):
        zm_client.move_monitor(controllable_monitor, "up")

    def test_move_down(self, zm_client, controllable_monitor):
        zm_client.move_monitor(controllable_monitor, "down")
