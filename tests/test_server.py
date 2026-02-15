"""Unit tests for the Server class.

Tests construction, properties, and URL building using raw server dicts
matching the ZM API shape -- no live ZoneMinder server needed.
"""

from __future__ import annotations

from zoneminder.server import Server

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw(
    sid=1,
    name="Server1",
    hostname="zm1.example.com",
    protocol="https",
    port=None,
    path_to_zms="/zm/cgi-bin/nph-zms",
    path_to_index="/zm/index.php",
    status="Online",
):
    """Build a raw server dict matching the inner 'Server' dict from ZM API."""
    raw = {
        "Id": str(sid),
        "Name": name,
        "Hostname": hostname,
        "Protocol": protocol,
        "PathToZMS": path_to_zms,
        "PathToIndex": path_to_index,
        "Status": status,
    }
    if port is not None:
        raw["Port"] = port
    return raw


# ---------------------------------------------------------------------------
# Construction & properties
# ---------------------------------------------------------------------------


class TestServerConstruction:
    def test_creates_from_raw(self):
        srv = Server(_make_raw())
        assert srv.id == 1
        assert srv.name == "Server1"

    def test_id_is_int(self):
        srv = Server(_make_raw(sid=42))
        assert isinstance(srv.id, int)
        assert srv.id == 42

    def test_name_from_raw(self):
        srv = Server(_make_raw(name="BackupServer"))
        assert srv.name == "BackupServer"

    def test_hostname_from_raw(self):
        srv = Server(_make_raw(hostname="cam.local"))
        assert srv.hostname == "cam.local"

    def test_protocol_from_raw(self):
        srv = Server(_make_raw(protocol="http"))
        assert srv.protocol == "http"

    def test_protocol_defaults_to_http(self):
        raw = _make_raw()
        del raw["Protocol"]
        srv = Server(raw)
        assert srv.protocol == "http"

    def test_port_from_raw(self):
        srv = Server(_make_raw(port="8443"))
        assert srv.port == "8443"

    def test_port_none_when_absent(self):
        srv = Server(_make_raw())
        assert srv.port is None

    def test_path_to_zms_from_raw(self):
        srv = Server(_make_raw(path_to_zms="/cgi-bin/nph-zms"))
        assert srv.path_to_zms == "/cgi-bin/nph-zms"

    def test_path_to_zms_defaults(self):
        raw = _make_raw()
        del raw["PathToZMS"]
        srv = Server(raw)
        assert srv.path_to_zms == "/zm/cgi-bin/nph-zms"

    def test_path_to_index_from_raw(self):
        srv = Server(_make_raw(path_to_index="/zoneminder/index.php"))
        assert srv.path_to_index == "/zoneminder/index.php"

    def test_path_to_index_defaults(self):
        raw = _make_raw()
        del raw["PathToIndex"]
        srv = Server(raw)
        assert srv.path_to_index == "/zm/index.php"

    def test_status_from_raw(self):
        srv = Server(_make_raw(status="Online"))
        assert srv.status == "Online"

    def test_status_defaults_to_empty(self):
        raw = _make_raw()
        del raw["Status"]
        srv = Server(raw)
        assert srv.status == ""

    def test_repr_contains_class_name(self):
        srv = Server(_make_raw(sid=5, name="Garage"))
        assert "Server" in repr(srv)

    def test_repr_contains_id(self):
        srv = Server(_make_raw(sid=5))
        assert "5" in repr(srv)

    def test_repr_contains_name(self):
        srv = Server(_make_raw(name="Garage"))
        assert "Garage" in repr(srv)

    def test_str_matches_repr(self):
        srv = Server(_make_raw())
        assert str(srv) == repr(srv)


# ---------------------------------------------------------------------------
# ZMS URL building
# ---------------------------------------------------------------------------


class TestServerZmsUrl:
    def test_basic_zms_url(self):
        srv = Server(_make_raw(protocol="https", hostname="zm1.example.com"))
        assert srv.zms_url == "https://zm1.example.com/zm/cgi-bin/nph-zms"

    def test_http_protocol(self):
        srv = Server(_make_raw(protocol="http", hostname="zm.local"))
        assert srv.zms_url == "http://zm.local/zm/cgi-bin/nph-zms"

    def test_with_port(self):
        srv = Server(_make_raw(protocol="https", hostname="zm1.example.com", port="8443"))
        assert srv.zms_url == "https://zm1.example.com:8443/zm/cgi-bin/nph-zms"

    def test_without_port(self):
        srv = Server(_make_raw(protocol="https", hostname="zm1.example.com"))
        assert ":" not in srv.zms_url.split("://")[1].split("/")[0]

    def test_custom_zms_path(self):
        srv = Server(_make_raw(hostname="cam.local", path_to_zms="/cgi-bin/nph-zms"))
        assert srv.zms_url == "https://cam.local/cgi-bin/nph-zms"


# ---------------------------------------------------------------------------
# Base URL building
# ---------------------------------------------------------------------------


class TestServerBaseUrl:
    def test_basic_base_url(self):
        srv = Server(_make_raw(protocol="https", hostname="zm1.example.com"))
        assert srv.base_url == "https://zm1.example.com/zm/"

    def test_with_port(self):
        srv = Server(_make_raw(protocol="https", hostname="zm1.example.com", port="8443"))
        assert srv.base_url == "https://zm1.example.com:8443/zm/"

    def test_trailing_slash(self):
        """base_url should always end with a trailing slash."""
        srv = Server(_make_raw())
        assert srv.base_url.endswith("/")

    def test_custom_path_to_index(self):
        srv = Server(_make_raw(hostname="cam.local", path_to_index="/zoneminder/index.php"))
        assert srv.base_url == "https://cam.local/zoneminder/"

    def test_root_path_to_index(self):
        srv = Server(_make_raw(hostname="cam.local", path_to_index="/index.php"))
        assert srv.base_url == "https://cam.local/"

    def test_without_port(self):
        srv = Server(_make_raw(protocol="http", hostname="zm.local"))
        assert srv.base_url == "http://zm.local/zm/"
