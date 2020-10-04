"""Tests to verify the zm module."""

import unittest

from zoneminder import zm


class TestZoneMinder(unittest.TestCase):
    """Tests to verify the ZoneMinder class."""

    def test_build_server_url_no_trailing_slash(self):
        """Verifies that server_url is correct with no trailing slashes."""
        host = "http://zoneminder.com"
        server_path = "zm"
        self.assertEqual(
            "http://zoneminder.com/zm/".format(host, server_path),
            zm.ZoneMinder._build_server_url(host, server_path),
        )

    def test_build_server_url_with_trailing_slash_path(self):
        """Verifies that server_url is correct with trailing slash in path."""
        host = "http://zoneminder.com"
        server_path = "/zm/"
        self.assertEqual(
            "http://zoneminder.com/zm/".format(host, server_path),
            zm.ZoneMinder._build_server_url(host, server_path),
        )

    def test_build_server_url_with_trailing_slash_host(self):
        """Verifies that server_url is correct with trailing slash in host."""
        host = "http://zoneminder.com/"
        server_path = "zm/"
        self.assertEqual(
            "http://zoneminder.com/zm/".format(host, server_path),
            zm.ZoneMinder._build_server_url(host, server_path),
        )

    def test_build_server_url_with_both_trailing_slash(self):
        """Verifies that server_url is correct with trailing slash in both."""
        host = "http://zoneminder.com/"
        server_path = "/zm/"
        self.assertEqual(
            "http://zoneminder.com/zm/".format(host, server_path),
            zm.ZoneMinder._build_server_url(host, server_path),
        )

    def test_get_zms_url_no_trailing_slash(self):
        """Verifies that zms_url is correct with no trailing slashes."""
        client = zm.ZoneMinder(
            "http://zoneminder.com",
            None,
            None,
            server_path="zm",
            zms_path="cgi-bin/npm-zms",
        )
        self.assertEqual("http://zoneminder.com/cgi-bin/npm-zms", client.get_zms_url())

    def test_get_zms_url_with_leading_slash_zms_path(self):
        """Verifies that zms_url is correct with leading slash in zms_path."""
        client = zm.ZoneMinder(
            "http://zoneminder.com",
            None,
            None,
            server_path="zm",
            zms_path="/cgi-bin/npm-zms",
        )
        self.assertEqual("http://zoneminder.com/cgi-bin/npm-zms", client.get_zms_url())

    def test_get_url_with_auth_username_special(self):
        """Verifies handing of username with special characters is encoded."""
        client = zm.ZoneMinder(None, "@dmin", None, server_path="zm", zms_path="/cgi-bin/npm-zms")
        self.assertEqual(
            "/cgi-bin/npm-zms&user=%40dmin", client.get_url_with_auth(client.get_zms_url())
        )

    def test_get_url_with_auth_password_special(self):
        """Verifies handing of password with special characters is encoded."""
        client = zm.ZoneMinder(
            None, "@dmin", "p@ssword", server_path="zm", zms_path="/cgi-bin/npm-zms"
        )
        self.assertEqual(
            "/cgi-bin/npm-zms&user=%40dmin&pass=p%40ssword",
            client.get_url_with_auth(client.get_zms_url()),
        )
