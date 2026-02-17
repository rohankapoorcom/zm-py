"""Unit tests for the RunState class.

Uses a stub client -- no live ZoneMinder server needed.
"""

from __future__ import annotations

from unittest.mock import patch

from zoneminder.run_state import RunState

# ---------------------------------------------------------------------------
# Stub client
# ---------------------------------------------------------------------------


class StubClient:
    """Minimal client stub for RunState."""

    def __init__(self, states_response=None):
        self._states_response = states_response or {"states": []}
        self._set_active_calls = []
        self._get_state_call_count = 0

    def get_state(self, api_url):
        self._get_state_call_count += 1
        return self._states_response

    def set_active_state(self, name):
        self._set_active_calls.append(name)


def _states_response(*states):
    """Build a states.json response from (id, name, is_active) tuples."""
    return {
        "states": [
            {"State": {"Id": str(sid), "Name": name, "IsActive": is_active}}
            for sid, name, is_active in states
        ]
    }


# ---------------------------------------------------------------------------
# Construction & properties
# ---------------------------------------------------------------------------

class TestRunStateConstruction:
    def test_creates_from_raw(self):
        raw = {"Id": "1", "Name": "Default"}
        rs = RunState(StubClient(), raw)
        assert rs.id == 1
        assert rs.name == "Default"

    def test_id_is_int(self):
        raw = {"Id": "42", "Name": "Test"}
        rs = RunState(StubClient(), raw)
        assert isinstance(rs.id, int)

    def test_name_is_str(self):
        raw = {"Id": "1", "Name": "Home"}
        rs = RunState(StubClient(), raw)
        assert isinstance(rs.name, str)

    def test_seeds_is_active_from_constructor(self):
        """When IsActive is in the raw dict, it should be cached."""
        raw = {"Id": "1", "Name": "Default", "IsActive": 1}
        client = StubClient()
        rs = RunState(client, raw)
        assert rs.active is True
        assert client._get_state_call_count == 0  # No API call, used cached

    def test_seeds_is_active_false_from_constructor(self):
        raw = {"Id": "1", "Name": "Default", "IsActive": 0}
        client = StubClient()
        rs = RunState(client, raw)
        assert rs.active is False
        assert client._get_state_call_count == 0

    def test_without_is_active_fetches_on_first_access(self):
        """When IsActive is not in constructor, active should fetch from API."""
        resp = _states_response((1, "Default", 1))
        client = StubClient(states_response=resp)
        rs = RunState(client, {"Id": "1", "Name": "Default"})
        assert rs.active is True
        assert client._get_state_call_count == 1


# ---------------------------------------------------------------------------
# active property
# ---------------------------------------------------------------------------

class TestRunStateActive:
    def test_active_when_is_active_int_1(self):
        """ZM >= 1.36 returns IsActive as int 1."""
        resp = _states_response((1, "Default", 1))
        client = StubClient(states_response=resp)
        rs = RunState(client, {"Id": "1", "Name": "Default"})
        assert rs.active is True

    def test_active_when_is_active_str_1(self):
        """Legacy ZM returns IsActive as string '1'."""
        resp = _states_response((1, "Default", "1"))
        client = StubClient(states_response=resp)
        rs = RunState(client, {"Id": "1", "Name": "Default"})
        assert rs.active is True

    def test_inactive_when_is_active_0(self):
        resp = _states_response((1, "Default", 0))
        client = StubClient(states_response=resp)
        rs = RunState(client, {"Id": "1", "Name": "Default"})
        assert rs.active is False

    def test_inactive_when_is_active_str_0(self):
        resp = _states_response((1, "Default", "0"))
        client = StubClient(states_response=resp)
        rs = RunState(client, {"Id": "1", "Name": "Default"})
        assert rs.active is False

    def test_returns_bool(self):
        resp = _states_response((1, "Default", 1))
        client = StubClient(states_response=resp)
        rs = RunState(client, {"Id": "1", "Name": "Default"})
        assert isinstance(rs.active, bool)

    def test_false_when_state_not_found(self):
        """If our state ID is not in the API response, return False."""
        resp = _states_response((2, "Other", 1))
        client = StubClient(states_response=resp)
        rs = RunState(client, {"Id": "99", "Name": "Missing"})
        assert rs.active is False

    def test_false_when_api_returns_empty(self):
        """Empty API response should return False, not crash."""
        client = StubClient(states_response={})
        rs = RunState(client, {"Id": "1", "Name": "Default"})
        assert rs.active is False

    def test_false_when_api_returns_no_states_key(self):
        """Response without 'states' key should return False, not crash."""
        client = StubClient(states_response={"other": "data"})
        rs = RunState(client, {"Id": "1", "Name": "Default"})
        assert rs.active is False

    def test_multiple_states_picks_correct_one(self):
        resp = _states_response(
            (1, "Default", 0),
            (2, "Away", 1),
            (3, "Night", 0),
        )
        client = StubClient(states_response=resp)
        rs_away = RunState(client, {"Id": "2", "Name": "Away"})
        rs_default = RunState(client, {"Id": "1", "Name": "Default"})
        assert rs_away.active is True
        assert rs_default.active is False


# ---------------------------------------------------------------------------
# TTL caching
# ---------------------------------------------------------------------------

class TestRunStateTtlCache:
    def test_cached_within_ttl(self):
        """Consecutive calls within 1s should not re-fetch."""
        resp = _states_response((1, "Default", 1))
        client = StubClient(states_response=resp)
        rs = RunState(client, {"Id": "1", "Name": "Default", "IsActive": 1})
        # First call uses cached value (seeded from constructor)
        assert rs.active is True
        assert rs.active is True
        assert rs.active is True
        assert client._get_state_call_count == 0

    @patch("zoneminder.run_state.time.monotonic")
    def test_refetches_after_ttl(self, mock_monotonic):
        """After 1s TTL expires, active should re-fetch from API."""
        resp = _states_response((1, "Default", 0))
        client = StubClient(states_response=resp)

        mock_monotonic.return_value = 100.0
        rs = RunState(client, {"Id": "1", "Name": "Default", "IsActive": 1})

        # Cached: still returns True (seeded value)
        mock_monotonic.return_value = 100.5
        assert rs.active is True
        assert client._get_state_call_count == 0

        # TTL expired: fetches from API, which returns IsActive=0
        mock_monotonic.return_value = 101.1
        assert rs.active is False
        assert client._get_state_call_count == 1

    def test_no_cache_without_is_active_in_constructor(self):
        """Without IsActive in constructor, first access should fetch."""
        resp = _states_response((1, "Default", 1))
        client = StubClient(states_response=resp)
        rs = RunState(client, {"Id": "1", "Name": "Default"})
        assert rs.active is True
        assert client._get_state_call_count == 1


# ---------------------------------------------------------------------------
# activate
# ---------------------------------------------------------------------------

class TestRunStateActivate:
    def test_calls_set_active_state(self):
        client = StubClient()
        rs = RunState(client, {"Id": "1", "Name": "Home"})
        rs.activate()
        assert client._set_active_calls == ["Home"]

    def test_passes_name_not_id(self):
        client = StubClient()
        rs = RunState(client, {"Id": "5", "Name": "Away"})
        rs.activate()
        assert client._set_active_calls == ["Away"]
