"""Tests to verify the zm module."""

import unittest

from zoneminder import zm


class TestZoneMinder(unittest.TestCase):
    """Tests to verify the ZoneMinder class."""

    def test_build_server_url_no_trailing_slash(self):
        """Verifies that server_url is correct with no trailing slashes."""
        host = 'http://zoneminder.com'
        server_path = "zm"
        self.assertEqual(
            'http://zoneminder.com/zm/'.format(host, server_path),
            zm.ZoneMinder._build_server_url(host, server_path)
        )

    def test_build_server_url_with_trailing_slash_path(self):
        """Verifies that server_url is correct with trailing slash in path."""
        host = 'http://zoneminder.com'
        server_path = "/zm/"
        self.assertEqual(
            'http://zoneminder.com/zm/'.format(host, server_path),
            zm.ZoneMinder._build_server_url(host, server_path)
        )

    def test_build_server_url_with_trailing_slash_host(self):
        """Verifies that server_url is correct with trailing slash in host."""
        host = 'http://zoneminder.com/'
        server_path = "zm/"
        self.assertEqual(
            'http://zoneminder.com/zm/'.format(host, server_path),
            zm.ZoneMinder._build_server_url(host, server_path)
        )

    def test_build_server_url_with_both_trailing_slash(self):
        """Verifies that server_url is correct with trailing slash in both."""
        host = 'http://zoneminder.com/'
        server_path = "/zm/"
        self.assertEqual(
            'http://zoneminder.com/zm/'.format(host, server_path),
            zm.ZoneMinder._build_server_url(host, server_path)
        )
