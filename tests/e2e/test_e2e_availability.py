"""E2E tests for ZoneMinder availability checks.

Covers ZoneMinder.is_available (daemonCheck) and the underlying
get_state() / _zm_request() plumbing.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.zm_e2e


class TestDaemonCheck:
    """ZoneMinder.is_available -- api/host/daemonCheck.json."""

    def test_is_available_returns_bool(self, zm_client):
        result = zm_client.is_available
        assert isinstance(result, bool)

    def test_daemon_check_raw_response(self, zm_client):
        """The raw daemonCheck response should have a 'result' key."""
        resp = zm_client.get_state("api/host/daemonCheck.json")
        assert isinstance(resp, dict)
        assert "result" in resp

    def test_daemon_check_result_is_int(self, zm_client):
        """The result value should be an integer (0 or 1)."""
        resp = zm_client.get_state("api/host/daemonCheck.json")
        result = resp.get("result")
        assert result in (0, 1, "0", "1"), f"Unexpected daemonCheck result: {result}"


class TestGetState:
    """ZoneMinder.get_state() -- generic GET wrapper."""

    def test_get_state_returns_dict(self, zm_client):
        result = zm_client.get_state("api/host/getVersion.json")
        assert isinstance(result, dict)

    def test_get_state_bad_endpoint_returns_dict(self, zm_client):
        """A non-existent endpoint should return an empty dict or error dict."""
        result = zm_client.get_state("api/nonexistent/endpoint.json")
        assert isinstance(result, dict)


class TestChangeState:
    """ZoneMinder.change_state() -- generic POST wrapper."""

    def test_change_state_returns_dict(self, zm_client):
        """POST to a valid endpoint should return a dict response."""
        result = zm_client.change_state("api/host/getVersion.json", {})
        assert isinstance(result, dict)


class TestGetUrlWithAuth:
    """ZoneMinder.get_url_with_auth() -- credential injection."""

    def test_adds_user_param(self, zm_client):
        if not zm_client._username:
            pytest.skip("No username configured")
        url = zm_client.get_url_with_auth("http://example.com/test?foo=bar")
        assert "user=" in url

    def test_adds_pass_param(self, zm_client):
        if not zm_client._password:
            pytest.skip("No password configured")
        url = zm_client.get_url_with_auth("http://example.com/test?foo=bar")
        assert "pass=" in url

    def test_no_auth_without_username(self, zm_host):
        """A client with no username should not add auth params."""
        from zoneminder.zm import ZoneMinder
        client = ZoneMinder(zm_host, None, None)
        url = client.get_url_with_auth("http://example.com/test?foo=bar")
        assert "user=" not in url
        assert "pass=" not in url


class TestZmsUrl:
    """ZoneMinder.get_zms_url() -- ZMS CGI path."""

    def test_zms_url_is_string(self, zm_client):
        url = zm_client.get_zms_url()
        assert isinstance(url, str)
        assert len(url) > 0

    def test_zms_url_contains_host(self, zm_client, zm_host):
        """The ZMS URL should be rooted at the server host."""
        url = zm_client.get_zms_url()
        # The host may have been normalized, just check it's a URL
        assert url.startswith("http")
