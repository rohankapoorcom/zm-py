"""E2E tests for ZoneMinder run state operations.

Covers get_run_states(), get_active_state(), set_active_state(),
and the RunState model properties.
"""

from __future__ import annotations

import pytest

from zoneminder.run_state import RunState


pytestmark = pytest.mark.zm_e2e


class TestGetRunStates:
    """ZoneMinder.get_run_states() -- list all run states."""

    def test_returns_list(self, zm_client):
        states = zm_client.get_run_states()
        assert isinstance(states, list)

    def test_elements_are_run_state_instances(self, zm_client):
        states = zm_client.get_run_states()
        for state in states:
            assert isinstance(state, RunState)

    def test_each_state_has_positive_id(self, zm_client):
        states = zm_client.get_run_states()
        for state in states:
            assert isinstance(state.id, int)
            assert state.id > 0

    def test_each_state_has_name(self, zm_client):
        states = zm_client.get_run_states()
        for state in states:
            assert isinstance(state.name, str)
            assert len(state.name) > 0


class TestRunStateActive:
    """RunState.active property -- check if state is currently active."""

    def test_active_returns_bool(self, zm_client):
        """Each state's .active should return a bool."""
        states = zm_client.get_run_states()
        if not states:
            pytest.skip("No run states on ZM server")
        for state in states:
            assert isinstance(state.active, bool)

    def test_at_most_one_active(self, zm_client):
        """At most one run state should be active at any time."""
        states = zm_client.get_run_states()
        active_count = sum(1 for s in states if s.active)
        assert active_count <= 1, f"Expected 0 or 1 active states, got {active_count}"


class TestGetActiveState:
    """ZoneMinder.get_active_state() -- get the name of the active run state."""

    def test_returns_string_or_none(self, zm_client):
        result = zm_client.get_active_state()
        assert result is None or isinstance(result, str)

    def test_active_state_matches_run_states(self, zm_client):
        """If an active state is returned, it should match one of the run states."""
        active = zm_client.get_active_state()
        if active is None:
            pytest.skip("No active run state")
        states = zm_client.get_run_states()
        state_names = [s.name for s in states]
        assert active in state_names


@pytest.mark.zm_e2e_write
class TestSetActiveState:
    """ZoneMinder.set_active_state() -- change the active run state."""

    def test_set_active_state_roundtrip(self, zm_client):
        """Setting a state and reading it back should match."""
        states = zm_client.get_run_states()
        if len(states) < 2:
            pytest.skip("Need at least 2 run states for roundtrip test")

        original = zm_client.get_active_state()
        target = None
        for s in states:
            if s.name != original:
                target = s
                break

        if target is None:
            pytest.skip("Could not find an alternative state")

        try:
            zm_client.set_active_state(target.name)
            result = zm_client.get_active_state()
            assert result == target.name
        finally:
            if original:
                zm_client.set_active_state(original)


class TestRunStateActivate:
    """RunState.activate() method."""

    @pytest.mark.zm_e2e_write
    def test_activate_changes_active_state(self, zm_client):
        """Calling activate() on a state should make it the active one."""
        states = zm_client.get_run_states()
        if len(states) < 2:
            pytest.skip("Need at least 2 run states")

        original = zm_client.get_active_state()
        target = None
        for s in states:
            if s.name != original:
                target = s
                break

        if target is None:
            pytest.skip("Could not find an alternative state")

        try:
            target.activate()
            result = zm_client.get_active_state()
            assert result == target.name
        finally:
            if original:
                zm_client.set_active_state(original)
