"""E2E tests for ZoneMinder authentication and login flows.

Validates login(), _legacy_auth(), JWT token acquisition, and the
get_state() / change_state() plumbing against a live ZM instance.
"""

from __future__ import annotations

import re

import pytest

from zoneminder.zm import ZoneMinder

pytestmark = pytest.mark.zm_e2e


class TestLogin:
    """JWT and session-based login."""

    def test_login_returns_true(self, zm_client_fresh: ZoneMinder):
        """login() should return True on success."""
        result = zm_client_fresh.login()
        assert result is True

    def test_login_populates_auth_token(self, zm_client_fresh: ZoneMinder):
        """After login(), the client should have an auth token or cookies."""
        zm_client_fresh.login()
        has_token = zm_client_fresh._auth_token is not None
        has_cookies = len(zm_client_fresh._session.cookies) > 0
        assert has_token or has_cookies, (
            "Expected either JWT token or session cookies after login"
        )

    def test_jwt_token_is_string(self, zm_client_fresh: ZoneMinder):
        """If JWT auth succeeds, the token should be a non-empty string."""
        zm_client_fresh.login()
        if zm_client_fresh._auth_token is None:
            pytest.skip("Server uses legacy auth, no JWT token")
        assert isinstance(zm_client_fresh._auth_token, str)
        assert len(zm_client_fresh._auth_token) > 0

    def test_session_client_still_works(self, zm_client: ZoneMinder):
        """The session-scoped client should still be functional."""
        monitors = zm_client.get_monitors()
        assert isinstance(monitors, list)


class TestVersion:
    """Host version endpoint used during legacy auth verification."""

    def test_get_version_returns_dict(self, zm_client: ZoneMinder):
        """api/host/getVersion.json should return a dict with version info."""
        result = zm_client.get_state("api/host/getVersion.json")
        assert isinstance(result, dict)
        assert "version" in result

    def test_version_is_semver_like(self, zm_client: ZoneMinder):
        """The ZM version should be a dotted numeric string."""
        result = zm_client.get_state("api/host/getVersion.json")
        version = result.get("version", "")
        assert re.match(r"\d+\.\d+", version), f"Unexpected version format: {version}"

    def test_api_version_present(self, zm_client: ZoneMinder):
        """The response should include an apiversion field."""
        result = zm_client.get_state("api/host/getVersion.json")
        assert "apiversion" in result
        assert re.match(r"\d+\.\d+", result["apiversion"])
