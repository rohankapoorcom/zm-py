"""E2E probes for ZoneMinder multi-server support.

Probes the raw ``api/servers.json`` response and verifies that
``get_servers()`` returns a list of Server instances.  Also checks
whether monitors include a ``ServerId`` field.

All tests gracefully handle single-server setups where the servers
list may be empty.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin

import pytest

from zoneminder.server import Server

pytestmark = pytest.mark.zm_e2e

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Raw servers.json probes
# ---------------------------------------------------------------------------


class TestServersJsonResponse:
    """Probe the raw api/servers.json endpoint."""

    def test_servers_endpoint_accessible(self, raw_session, api_base):
        """Verify that api/servers.json returns a 200 response."""
        r = raw_session.get(urljoin(api_base, "api/servers.json"))
        logger.info("servers.json status: %s", r.status_code)
        assert r.ok, f"servers.json returned {r.status_code}"

    def test_servers_response_has_servers_key(self, raw_session, api_base):
        """Response should have a 'servers' key (possibly empty list)."""
        r = raw_session.get(urljoin(api_base, "api/servers.json"))
        body = r.json()
        logger.info("servers.json top-level keys: %s", list(body.keys()))
        assert "servers" in body

    def test_server_item_shape(self, raw_session, api_base):
        """If servers exist, check the shape of each item."""
        r = raw_session.get(urljoin(api_base, "api/servers.json"))
        servers = r.json()["servers"]
        logger.info("Number of servers: %d", len(servers))
        if not servers:
            pytest.skip("No servers configured (single-server setup)")
        item = servers[0]
        logger.info("Server item keys: %s", list(item.keys()))
        assert "Server" in item
        server = item["Server"]
        logger.info("Server dict keys: %s", sorted(server.keys()))
        for key in ("Id", "Name", "Hostname"):
            assert key in server, f"Missing expected key: {key}"
        # Log optional fields zm-py uses
        for key in ("Protocol", "Port", "PathToZMS", "PathToIndex", "Status"):
            logger.info("  %s = %r", key, server.get(key))


# ---------------------------------------------------------------------------
# get_servers() integration
# ---------------------------------------------------------------------------


class TestGetServers:
    """Verify get_servers() returns Server instances from a live server."""

    def test_returns_list(self, zm_client):
        """get_servers() should return a list (possibly empty)."""
        servers = zm_client.get_servers()
        assert isinstance(servers, list)
        logger.info("get_servers() returned %d servers", len(servers))

    def test_items_are_server_instances(self, zm_client):
        """Each item should be a Server instance."""
        servers = zm_client.get_servers()
        if not servers:
            pytest.skip("No servers configured (single-server setup)")
        for srv in servers:
            assert isinstance(srv, Server)
            logger.info("  Server: id=%d name=%r hostname=%r", srv.id, srv.name, srv.hostname)

    def test_server_urls_are_valid(self, zm_client):
        """Server zms_url and base_url should be well-formed."""
        servers = zm_client.get_servers()
        if not servers:
            pytest.skip("No servers configured (single-server setup)")
        for srv in servers:
            assert "://" in srv.zms_url, f"zms_url missing scheme: {srv.zms_url}"
            assert "://" in srv.base_url, f"base_url missing scheme: {srv.base_url}"
            assert srv.base_url.endswith("/"), f"base_url missing trailing slash: {srv.base_url}"
            logger.info("  Server %d: zms_url=%s  base_url=%s", srv.id, srv.zms_url, srv.base_url)


# ---------------------------------------------------------------------------
# Monitor ServerId field probe
# ---------------------------------------------------------------------------


class TestMonitorServerId:
    """Probe whether monitors include a ServerId field."""

    def test_monitors_have_server_id(self, raw_session, api_base):
        """Check if monitors include ServerId in their data."""
        r = raw_session.get(urljoin(api_base, "api/monitors.json"))
        monitors = r.json().get("monitors", [])
        if not monitors:
            pytest.skip("No monitors on ZM server")
        for item in monitors:
            monitor = item["Monitor"]
            server_id = monitor.get("ServerId")
            logger.info(
                "Monitor %s (%s): ServerId=%r (type=%s)",
                monitor["Id"],
                monitor["Name"],
                server_id,
                type(server_id).__name__ if server_id is not None else "missing",
            )
        # Document whether the field exists (it should on ZM 1.30+)
        first = monitors[0]["Monitor"]
        has_field = "ServerId" in first
        logger.info("ServerId field present in monitors: %s", has_field)
