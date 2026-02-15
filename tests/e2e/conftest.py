"""Fixtures and skip logic for live ZoneMinder E2E tests.

These tests hit a real ZoneMinder server.  Configuration is loaded from
environment variables or a ``.env.zm_e2e`` file placed in the ha-zm-py
project root.

Required env vars
-----------------
    ZM_HOST          ZoneMinder base URL, e.g. http://192.168.1.10
    ZM_USER          ZoneMinder username  (default: admin)
    ZM_PASSWORD      ZoneMinder password  (default: admin)

Optional env vars
-----------------
    ZM_SERVER_PATH   Server path           (default: /zm/)
    ZM_ZMS_PATH      ZMS CGI path          (default: /zm/cgi-bin/nph-zms)
    ZM_VERIFY_SSL    Verify SSL certs      (default: false)
    ZM_E2E_WRITE     Set to "1" to enable write-tier tests (state changes, etc.)

Run conventions
---------------
    # readonly (default) -- skips automatically if ZM_HOST is unset
    pytest tests/e2e/ -v

    # include write-tier tests (monitor function changes, state switching)
    ZM_E2E_WRITE=1 pytest tests/e2e/ -v

    # normal dev -- e2e tests auto-skip when no server configured
    pytest tests/
"""

from __future__ import annotations

from collections import OrderedDict
import logging
import os
from pathlib import Path
import time

import pytest
import requests

from zoneminder.zm import ZoneMinder


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Env-file loading
# ---------------------------------------------------------------------------

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env.zm_e2e"


def _load_env_file() -> dict[str, str]:
    """Parse .env.zm_e2e (KEY=VALUE lines).  Ignores comments and blanks."""
    if not _ENV_FILE.is_file():
        return {}
    values: dict[str, str] = {}
    for line in _ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, val = line.partition("=")
        if key:
            values[key.strip()] = val.strip()
    return values


_file_values = _load_env_file()


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, _file_values.get(name, default))


# ---------------------------------------------------------------------------
# Skip logic
# ---------------------------------------------------------------------------

_ZM_HOST = _get("ZM_HOST")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-skip e2e tests when the ZM server isn't configured."""
    skip_no_server = pytest.mark.skip(reason="ZM_HOST not set (no .env.zm_e2e)")
    skip_no_write = pytest.mark.skip(reason="ZM_E2E_WRITE != 1 (write tests disabled)")
    write_enabled = _get("ZM_E2E_WRITE") == "1"

    for item in items:
        markers = {m.name for m in item.iter_markers()}
        if "zm_e2e" not in markers and "zm_e2e_write" not in markers:
            continue
        if not _ZM_HOST:
            item.add_marker(skip_no_server)
        elif "zm_e2e_write" in markers and not write_enabled:
            item.add_marker(skip_no_write)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def wait_for_zm(
    server_url: str,
    timeout: int = 90,
    verify_ssl: bool = False,
) -> bool:
    """Poll the ZM API until it responds or timeout expires."""
    from urllib.parse import urljoin

    version_url = urljoin(server_url, "api/host/getVersion.json")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(version_url, timeout=5, verify=verify_ssl)
            if r.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(2)
    return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def zm_host() -> str:
    """ZoneMinder server host URL."""
    if not _ZM_HOST:
        pytest.skip("ZM_HOST not set")
    return _ZM_HOST


@pytest.fixture(scope="session")
def zm_client(zm_host: str) -> ZoneMinder:
    """Session-scoped ZoneMinder client, logged in once."""
    verify_ssl = _get("ZM_VERIFY_SSL", "false").lower() in ("1", "true", "yes")
    server_path = _get("ZM_SERVER_PATH", "/zm/")
    zms_path = _get("ZM_ZMS_PATH", "/zm/cgi-bin/nph-zms")
    user = _get("ZM_USER", "admin")
    password = _get("ZM_PASSWORD", "admin")

    client = ZoneMinder(
        server_host=zm_host,
        username=user,
        password=password,
        server_path=server_path,
        zms_path=zms_path,
        verify_ssl=verify_ssl,
    )
    logged_in = client.login()
    assert logged_in, f"Failed to login to ZoneMinder at {zm_host}"

    _record("Server", "Host", zm_host)
    return client


@pytest.fixture
def zm_client_fresh(zm_host: str) -> ZoneMinder:
    """Fresh ZoneMinder client per test -- for testing login/auth behaviour."""
    verify_ssl = _get("ZM_VERIFY_SSL", "false").lower() in ("1", "true", "yes")
    server_path = _get("ZM_SERVER_PATH", "/zm/")
    zms_path = _get("ZM_ZMS_PATH", "/zm/cgi-bin/nph-zms")
    user = _get("ZM_USER", "admin")
    password = _get("ZM_PASSWORD", "admin")

    return ZoneMinder(
        server_host=zm_host,
        username=user,
        password=password,
        server_path=server_path,
        zms_path=zms_path,
        verify_ssl=verify_ssl,
    )


@pytest.fixture(scope="session")
def any_monitor(zm_client: ZoneMinder):
    """First available Monitor.  Skips if none exist."""
    monitors = zm_client.get_monitors()
    if not monitors:
        pytest.skip("No monitors on ZM server")
    mon = monitors[0]
    _record("Test targets", "Monitor", f"id={mon.id}  name={mon.name!r}")
    return mon


@pytest.fixture(scope="session")
def monitors(zm_client: ZoneMinder):
    """All monitors from the ZM server."""
    result = zm_client.get_monitors()
    _record("Test targets", "Monitor count", str(len(result)))
    return result


# ---------------------------------------------------------------------------
# E2E summary report
# ---------------------------------------------------------------------------

_summary: OrderedDict[str, list[tuple[str, str]]] = OrderedDict()


@pytest.fixture(scope="session")
def e2e_summary() -> OrderedDict[str, list[tuple[str, str]]]:
    """Shared summary dict.  Tests append (label, detail) tuples."""
    return _summary


def _record(section: str, label: str, detail: str) -> None:
    """Helper for fixtures to record summary lines."""
    _summary.setdefault(section, []).append((label, detail))


def pytest_terminal_summary(
    terminalreporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Print a ZM E2E results summary after the test run."""
    skipped = terminalreporter.stats.get("skipped", [])
    skip_reasons: dict[str, list[str]] = {}
    for report in skipped:
        if "e2e" not in str(report.fspath):
            continue
        reason = report.longrepr[-1] if isinstance(report.longrepr, tuple) else str(report.longrepr)
        reason = reason.removeprefix("Skipped: ")
        skip_reasons.setdefault(reason, []).append(report.nodeid.split("::")[-1])

    if not _summary and not skip_reasons:
        return
    tw = terminalreporter._tw
    tw.sep("=", "ZM E2E Summary")
    for section, items in _summary.items():
        tw.line(f"\n  {section}:", bold=True)
        for label, detail in items:
            tw.line(f"    {label}: {detail}")
    if skip_reasons:
        tw.line(f"\n  Skipped ({sum(len(v) for v in skip_reasons.values())} tests):", bold=True)
        for reason, tests in skip_reasons.items():
            tw.line(f"    {reason}  ({len(tests)} tests)")
