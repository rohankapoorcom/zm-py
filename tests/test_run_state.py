"""Unit tests for the RunState class.

Uses a stub client -- no live ZoneMinder server needed.
"""

from __future__ import annotations

from zoneminder.run_state import RunState

# ---------------------------------------------------------------------------
# Stub client
# ---------------------------------------------------------------------------


class StubClient:
    """Minimal client stub for RunState."""

    def __init__(self, states_response=None):
        self._states_response = states_response or {"states": []}
        self._set_active_calls = []

    def get_state(self, api_url):
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
