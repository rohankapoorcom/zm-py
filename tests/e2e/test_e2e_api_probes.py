"""Probing tests that inspect raw ZM API responses.

These tests document what ZoneMinder 1.38.x actually returns, so we can
verify whether zm-py's assumptions and parsing are correct.  Failures here
mean our code disagrees with reality.

Each test logs the actual raw value so we can see it in pytest -v --tb=long.

ZM 1.38.0 API Response Types (verified via E2E):
  host/login.json        access_token         str   JWT eyJ...
  host/login.json        refresh_token        str   JWT eyJ... (zm-py ignores)
  host/login.json        access_token_expires int   7200
  host/login.json        credentials          str   auth=258e... (zm-py ignores)
  host/login.json        append_password      int   0 (zm-py ignores)
  host/daemonCheck.json  result               int   1
  host/getVersion.json   version              str   '1.38.0'
  host/getVersion.json   apiversion           str   '2.0'
  monitors.json          item keys            --    Monitor, Manufacturer, CameraModel,
                                                    Monitor_Status, Event_Summary
  monitors/{id}.json     envelope             --    {"monitor": {"Monitor": {...}, ...}}
  Monitor_Status         CaptureFPS           str   '10.00'
  monitors/alarm/...     status               int   0
  monitors/daemonStatus  status               bool  True
  events/consoleEvents   results              dict  {'1': 133, '3': 39, ...}
  states.json            IsActive             int   1 or 0
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin

import pytest
import requests

pytestmark = pytest.mark.zm_e2e

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Raw API helpers (bypass zm-py, hit the API directly)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def raw_session(zm_client):
    """A requests.Session with the JWT token from zm_client."""
    s = requests.Session()
    s.verify = zm_client._verify_ssl
    if zm_client._auth_token:
        s.params = {"token": zm_client._auth_token}
    elif zm_client._cookies:
        s.cookies = zm_client._cookies
    return s


@pytest.fixture(scope="session")
def api_base(zm_client):
    """The base API URL (server_url)."""
    return zm_client._server_url


# ---------------------------------------------------------------------------
# BUG-002: daemonCheck result type
# ---------------------------------------------------------------------------

class TestDaemonCheckResultType:
    """Probe the actual type of daemonCheck 'result' field.

    BUG-002 claims zm-py compares `result == 1` (int) but the API may
    return the string "1".  Let's see what 1.38.x actually returns.
    """

    def test_daemon_check_result_actual_type(self, raw_session, api_base):
        """What type does the live ZM API return for daemonCheck result?"""
        r = raw_session.get(urljoin(api_base, "api/host/daemonCheck.json"))
        body = r.json()
        result = body["result"]
        logger.info("daemonCheck result = %r  (type=%s)", result, type(result).__name__)

        # Document what we got
        assert "result" in body
        # If this is an int, zm-py's `== 1` works. If str, BUG-002 is confirmed.
        if isinstance(result, str):
            pytest.fail(
                f"BUG-002 CONFIRMED: daemonCheck returns result={result!r} (str), "
                f"but zm.py:222 compares with `== 1` (int)"
            )

    def test_is_available_matches_raw(self, zm_client, raw_session, api_base):
        """Compare zm-py's is_available with what the raw API says."""
        r = raw_session.get(urljoin(api_base, "api/host/daemonCheck.json"))
        raw_result = r.json()["result"]
        raw_running = (raw_result == 1 or raw_result == "1")

        zmpy_result = zm_client.is_available
        logger.info(
            "Raw result=%r raw_running=%s zm-py.is_available=%s",
            raw_result, raw_running, zmpy_result,
        )
        if raw_running != zmpy_result:
            pytest.fail(
                f"BUG-002: raw API says running={raw_running} (result={raw_result!r}) "
                f"but zm-py says is_available={zmpy_result}"
            )


# ---------------------------------------------------------------------------
# BUG-001: Stale token in retry loop (hard to trigger in e2e, but we can
# verify the token_url_suffix is built correctly)
# ---------------------------------------------------------------------------

class TestTokenHandling:
    """Verify JWT token is used correctly in requests."""

    def test_auth_token_present_after_login(self, zm_client):
        """After login, the auth token should be set."""
        if zm_client._auth_token is None:
            pytest.skip("Server uses legacy auth")
        assert isinstance(zm_client._auth_token, str)
        assert len(zm_client._auth_token) > 10, "Token looks suspiciously short"

    def test_token_in_request_url(self, zm_client, raw_session, api_base):
        """Verify token= appears in the actual request URL zm-py builds."""
        if zm_client._auth_token is None:
            pytest.skip("Server uses legacy auth")
        # Reconstruct what _zm_request does
        token_suffix = "?token=" + zm_client._auth_token
        url = urljoin(zm_client._server_url, "api/monitors.json") + token_suffix
        r = raw_session.get(url, params={})  # clear session params to use raw URL
        logger.info("Token URL request status: %s", r.status_code)
        assert r.ok, f"Request with token URL failed: {r.status_code}"


# ---------------------------------------------------------------------------
# BUG-003: PTZ token=None
# ---------------------------------------------------------------------------

class TestPtzTokenParam:
    """Verify what happens when token is None in PTZ params."""

    def test_token_none_serializes_as_string(self):
        """Demonstrate BUG-003: requests serializes None as 'None' string."""
        req = requests.Request("POST", "http://example.com", params={"token": None})
        prepared = req.prepare()
        logger.info("Prepared URL with token=None: %s", prepared.url)
        # requests drops None params (since requests 2.x)
        # or serializes as "None" string depending on version
        if "token=None" in (prepared.url or ""):
            logger.warning("BUG-003 CONFIRMED: token=None serialized as literal 'None'")
        elif "token" not in (prepared.url or ""):
            logger.info("BUG-003 NOT an issue on this requests version (None params dropped)")


# ---------------------------------------------------------------------------
# Monitor response shape probes
# ---------------------------------------------------------------------------

class TestMonitorResponseShape:
    """Probe the actual shape of monitor API responses."""

    def test_monitors_list_envelope(self, raw_session, api_base):
        """Check the top-level keys of api/monitors.json response."""
        r = raw_session.get(urljoin(api_base, "api/monitors.json"))
        body = r.json()
        logger.info("monitors.json top-level keys: %s", list(body.keys()))
        assert "monitors" in body

    def test_monitor_item_shape(self, raw_session, api_base):
        """Check the shape of each monitor item."""
        r = raw_session.get(urljoin(api_base, "api/monitors.json"))
        monitors = r.json()["monitors"]
        assert len(monitors) > 0
        item = monitors[0]
        logger.info("Monitor item keys: %s", list(item.keys()))
        assert "Monitor" in item
        monitor = item["Monitor"]
        logger.info("Monitor dict keys: %s", sorted(monitor.keys()))
        # Keys zm-py relies on
        for key in ("Id", "Name", "Controllable", "Function", "StreamReplayBuffer"):
            assert key in monitor, f"Missing expected key: {key}"

    def test_single_monitor_envelope(self, raw_session, api_base, any_monitor):
        """Check api/monitors/{id}.json response shape.

        zm-py accesses result['monitor'] (lowercase) in update_monitor().
        """
        r = raw_session.get(urljoin(api_base, f"api/monitors/{any_monitor.id}.json"))
        body = r.json()
        logger.info("Single monitor response keys: %s", list(body.keys()))
        assert "monitor" in body, (
            f"Expected 'monitor' key (lowercase) in single monitor response, "
            f"got keys: {list(body.keys())}"
        )
        inner = body["monitor"]
        assert "Monitor" in inner
        # BUG-008: is_available reads Monitor_Status from _raw_result
        has_status = "Monitor_Status" in inner
        logger.info("Has Monitor_Status: %s", has_status)
        if has_status:
            status = inner["Monitor_Status"]
            logger.info("Monitor_Status keys: %s", list(status.keys()) if status else "None")
            if status:
                fps = status.get("CaptureFPS")
                logger.info("CaptureFPS = %r (type=%s)", fps, type(fps).__name__)

    def test_monitor_status_in_list_vs_single(self, raw_session, api_base, any_monitor):
        """Compare Monitor_Status presence in list vs single endpoints.

        BUG-008: is_available uses _raw_result from get_monitors() which may
        not include Monitor_Status, vs update_monitor() which fetches single.
        """
        # List endpoint
        r_list = raw_session.get(urljoin(api_base, "api/monitors.json"))
        list_item = None
        for m in r_list.json()["monitors"]:
            if int(m["Monitor"]["Id"]) == any_monitor.id:
                list_item = m
                break
        assert list_item is not None

        # Single endpoint
        r_single = raw_session.get(urljoin(api_base, f"api/monitors/{any_monitor.id}.json"))
        single_item = r_single.json()["monitor"]

        list_has = "Monitor_Status" in list_item
        single_has = "Monitor_Status" in single_item
        logger.info(
            "Monitor_Status present - list endpoint: %s, single endpoint: %s",
            list_has, single_has,
        )
        list_fps = None
        single_fps = None
        if list_has and list_item["Monitor_Status"]:
            list_fps = list_item["Monitor_Status"].get("CaptureFPS")
        if single_has and single_item["Monitor_Status"]:
            single_fps = single_item["Monitor_Status"].get("CaptureFPS")
        logger.info("CaptureFPS - list: %r, single: %r", list_fps, single_fps)


# ---------------------------------------------------------------------------
# Monitor alarm/daemon status probes
# ---------------------------------------------------------------------------

class TestMonitorStatusEndpoints:
    """Probe the alarm and daemonStatus endpoints zm-py uses."""

    def test_alarm_status_response(self, raw_session, api_base, any_monitor):
        """Check api/monitors/alarm/id:{id}/command:status.json shape.

        zm-py reads response['status'] and casts to int.
        """
        url = urljoin(api_base, f"api/monitors/alarm/id:{any_monitor.id}/command:status.json")
        r = raw_session.get(url)
        logger.info("Alarm status code: %s", r.status_code)
        if r.ok:
            body = r.json()
            logger.info("Alarm response: %r", body)
            status = body.get("status")
            logger.info("status = %r (type=%s)", status, type(status).__name__)
            # zm-py does int(status) == STATE_ALARM (3)
            # Verify the cast would work
            if status != "" and status is not None:
                try:
                    int_status = int(status)
                    logger.info("int(status) = %d", int_status)
                except (ValueError, TypeError) as e:
                    pytest.fail(f"Cannot cast alarm status to int: {status!r} ({e})")
        else:
            logger.warning("Alarm status endpoint returned %s", r.status_code)

    def test_daemon_status_response(self, raw_session, api_base, any_monitor):
        """Check api/monitors/daemonStatus/id:{id}/daemon:zmc.json shape.

        zm-py reads response['status'].
        """
        url = urljoin(
            api_base,
            f"api/monitors/daemonStatus/id:{any_monitor.id}/daemon:zmc.json",
        )
        r = raw_session.get(url)
        logger.info("Daemon status code: %s", r.status_code)
        if r.ok:
            body = r.json()
            logger.info("Daemon status response: %r", body)
            status = body.get("status")
            logger.info("status = %r (type=%s)", status, type(status).__name__)


# ---------------------------------------------------------------------------
# consoleEvents probes
# ---------------------------------------------------------------------------

class TestConsoleEvents:
    """Probe the consoleEvents endpoint zm-py uses for event counts."""

    def test_console_events_response_shape(self, raw_session, api_base):
        """Check api/events/consoleEvents/{filter}.json response.

        zm-py reads response['results'] and checks if it's a list or dict.
        """
        url = urljoin(api_base, "api/events/consoleEvents/100%20year.json")
        r = raw_session.get(url)
        logger.info("consoleEvents status: %s", r.status_code)
        assert r.ok
        body = r.json()
        logger.info("consoleEvents keys: %s", list(body.keys()))
        assert "results" in body
        results = body["results"]
        logger.info("results type: %s  value: %r", type(results).__name__, results)
        # zm-py: if isinstance(results, list) => return 0 (no events)
        # else: results.get(str(monitor_id), 0)
        if isinstance(results, dict):
            for k, v in results.items():
                logger.info("  monitor_id=%s  count=%r (type=%s)", k, v, type(v).__name__)

    def test_console_events_with_archived_filter(self, raw_session, api_base):
        """Check the Archived filter works."""
        url = urljoin(api_base, "api/events/consoleEvents/100%20year/Archived=:0.json")
        r = raw_session.get(url)
        logger.info("consoleEvents (Archived=:0) status: %s", r.status_code)
        assert r.ok
        body = r.json()
        results = body.get("results")
        logger.info("Filtered results type: %s  value: %r", type(results).__name__, results)


# ---------------------------------------------------------------------------
# States response probes
# ---------------------------------------------------------------------------

class TestStatesResponse:
    """Probe the states endpoint to verify IsActive type."""

    def test_states_is_active_type(self, raw_session, api_base):
        """Check what type IsActive is on ZM 1.38.x.

        zm-py's RunState.active does int(state['IsActive']) == 1 which
        handles both str '1' and int 1.  Let's document the actual type.
        """
        r = raw_session.get(urljoin(api_base, "api/states.json"))
        assert r.ok
        body = r.json()
        assert "states" in body
        for state in body["states"]:
            s = state["State"]
            is_active = s["IsActive"]
            logger.info(
                "State %r (id=%s): IsActive=%r (type=%s)",
                s["Name"], s["Id"], is_active, type(is_active).__name__,
            )


# ---------------------------------------------------------------------------
# Login response probes
# ---------------------------------------------------------------------------

class TestLoginResponse:
    """Probe the login endpoint to document the actual response shape."""

    def test_login_response_shape(self, api_base, zm_host):
        """Check what fields the login response contains on ZM 1.38.x."""
        from tests.e2e.conftest import _get
        r = requests.post(
            urljoin(api_base, "api/host/login.json"),
            data={
                "user": _get("ZM_USER", "admin"),
                "pass": _get("ZM_PASSWORD", "admin"),
            },
            verify=_get("ZM_VERIFY_SSL", "false").lower() in ("1", "true", "yes"),
            timeout=10,
        )
        assert r.ok
        body = r.json()
        logger.info("Login response keys: %s", sorted(body.keys()))
        for k, v in body.items():
            vtype = type(v).__name__
            vpreview = repr(v)[:80]
            logger.info("  %s: %s = %s", k, vtype, vpreview)

        # zm-py only reads 'access_token'
        if "access_token" in body:
            logger.info("JWT auth available")
        else:
            logger.info("JWT auth NOT available (legacy only)")

        # Check for refresh token support (zm-py ignores this)
        if "refresh_token" in body:
            logger.info("Refresh token available (zm-py does NOT use it)")

    def test_version_response_shape(self, raw_session, api_base):
        """Check all fields in getVersion response."""
        r = raw_session.get(urljoin(api_base, "api/host/getVersion.json"))
        assert r.ok
        body = r.json()
        logger.info("getVersion keys: %s", sorted(body.keys()))
        for k, v in body.items():
            logger.info("  %s = %r (type=%s)", k, v, type(v).__name__)
