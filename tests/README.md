# zm-py Test Suite

## Overview

The test suite is organized into two tiers:

| Tier | Directory | What it tests | Dependencies |
|------|-----------|---------------|--------------|
| **Unit** | `tests/` (root) | All public API logic with stubs/mocks | None (pure logic) |
| **E2E** | `tests/e2e/` | Every API call against a live ZoneMinder instance | Running ZM server |

The E2E tests exist to validate zm-py's behavior against **the real ZoneMinder
API**, not mocked responses. This catches drift between what we *think* the API
returns and what it *actually* returns.

## Quick Start

### Unit tests (no server needed)

```bash
cd ha-zm-py
pip install -e ".[dev]"   # or: pip install pytest requests
pytest tests/test_*.py -v
```

### E2E tests (requires live ZM server)

```bash
# 1. Create config
cp .env.zm_e2e.example .env.zm_e2e
# Edit .env.zm_e2e with your ZM server details

# 2. Run read-only tests
pytest tests/e2e/ -v

# 3. Run including write tests (changes monitor states!)
ZM_E2E_WRITE=1 pytest tests/e2e/ -v
```

## E2E Configuration

Configuration is read from environment variables or a `.env.zm_e2e` file in the
ha-zm-py project root. Env vars always take precedence.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ZM_HOST` | Yes | -- | ZM server base URL, e.g. `http://192.168.1.10` |
| `ZM_USER` | No | `admin` | ZM username |
| `ZM_PASSWORD` | No | `admin` | ZM password |
| `ZM_SERVER_PATH` | No | `/zm/` | ZM web path |
| `ZM_ZMS_PATH` | No | `/zm/cgi-bin/nph-zms` | ZMS CGI path |
| `ZM_VERIFY_SSL` | No | `false` | SSL certificate verification |
| `ZM_E2E_WRITE` | No | `0` | Set to `1` to enable write-tier tests |

### Auto-skip behavior

- If `ZM_HOST` is not set, all E2E tests are **automatically skipped** with a
  clear reason message. Running `pytest tests/` during normal development will
  not fail.
- Write-tier tests (`@pytest.mark.zm_e2e_write`) are skipped unless
  `ZM_E2E_WRITE=1`.

## Test Markers

| Marker | Description |
|--------|-------------|
| `zm_e2e` | Read-only test that requires a live ZM server |
| `zm_e2e_write` | Test that **mutates** ZM state (monitor functions, run states) |

Run only E2E tests:
```bash
pytest -m zm_e2e tests/e2e/ -v
```

Run only write tests:
```bash
ZM_E2E_WRITE=1 pytest -m zm_e2e_write tests/e2e/ -v
```

## Unit Test Modules

| Module | What it covers |
|--------|----------------|
| `test_zm.py` | URL building (`_build_server_url`, `_build_zms_url`, `get_url_with_auth`) |
| `test_ptz.py` | `ControlType.from_move()` direction parsing |
| `test_monitor.py` | Monitor construction, properties, image URLs, `is_recording`/`is_available` parsing, `get_events` parsing, `function` get/set, PTZ with mocked HTTP |
| `test_run_state.py` | RunState construction, properties, `active` parsing, `activate` |
| `test_enums.py` | `TimePeriod` (period/title/get_time_period), `MonitorState`, `ControlType` values |
| `test_exceptions.py` | Exception hierarchy, `__str__` formatting |
| `test_client.py` | `verify_ssl`, `is_available` parsing, `get_monitors`/`get_run_states`/`get_active_state` response handling, `move_monitor` exception swallowing |

## E2E Test Modules

| Module | What it covers | ZM API endpoints hit |
|--------|----------------|---------------------|
| `test_e2e_auth.py` | Login (JWT + legacy), version info | `api/host/login.json`, `api/host/getVersion.json` |
| `test_e2e_monitors.py` | Monitor listing, properties, function get/set, events, image URLs | `api/monitors.json`, `api/monitors/{id}.json`, `api/monitors/alarm/...`, `api/monitors/daemonStatus/...`, `api/events/consoleEvents/...` |
| `test_e2e_states.py` | Run states listing, active state, state switching | `api/states.json`, `api/states/change/{name}.json` |
| `test_e2e_availability.py` | Daemon check, get_state/change_state plumbing, ZMS URL, auth URL helpers | `api/host/daemonCheck.json`, `api/host/getVersion.json` |
| `test_e2e_ptz.py` | PTZ control on controllable/non-controllable monitors | `index.php` (control view) |
| `test_e2e_api_probes.py` | Raw API response inspection -- documents actual types/shapes from ZM 1.38.x to validate BUGS.md | All endpoints |

## API Coverage

The E2E tests cover every endpoint that zm-py calls:

```
POST api/host/login.json           -> ZoneMinder.login()
POST index.php (legacy auth)       -> ZoneMinder._legacy_auth()
GET  api/host/getVersion.json      -> ZoneMinder._legacy_auth()
GET  api/host/daemonCheck.json     -> ZoneMinder.is_available
GET  api/monitors.json             -> ZoneMinder.get_monitors()
GET  api/monitors/{id}.json        -> Monitor.update_monitor()
POST api/monitors/{id}.json        -> Monitor.function (setter)     [write]
GET  api/states.json               -> ZoneMinder.get_run_states()
GET  api/states/change/{name}.json -> ZoneMinder.set_active_state() [write]
GET  api/monitors/alarm/...        -> Monitor.is_recording
GET  api/monitors/daemonStatus/... -> Monitor.is_available
GET  api/events/consoleEvents/...  -> Monitor.get_events()
POST index.php (PTZ control)       -> Monitor.ptz_control_command() [write]
```

## Fixtures

Session-scoped fixtures (created once per test run):

| Fixture | Description |
|---------|-------------|
| `zm_host` | The ZM server URL from config |
| `zm_client` | Logged-in `ZoneMinder` client (session-scoped) |
| `monitors` | All monitors from the server |
| `any_monitor` | First available monitor |

Per-test fixtures:

| Fixture | Description |
|---------|-------------|
| `zm_client_fresh` | Fresh `ZoneMinder` client (not logged in) |
| `controllable_monitor` | A monitor with `controllable=True` (skips if none) |
| `non_controllable_monitor` | A monitor with `controllable=False` (skips if none) |

## E2E Summary Report

After the test run, a summary section is printed showing:
- Server connection details
- Test target monitors
- Skip reasons and counts

## Known Bugs

See [BUGS.md](BUGS.md) for bugs discovered in zm-py during test development.
These are **not fixed** -- they are documented to guide future refactoring.

## Comparison with Sister Projects

This test suite follows the same E2E patterns established in:

| Project | E2E location | Config mechanism |
|---------|-------------|------------------|
| **zm-py** (this) | `tests/e2e/` | `.env.zm_e2e` + env vars |
| **pyzm2** | `tests/test_zm_e2e/` | `.env.zm_e2e` + env vars |
| **legacy/pyzm** | `tests/e2e/` | env vars |
| **zoneminder** (API contract) | `zoneminder/tests/api/` | Docker Compose |

All three Python libraries test against the same real ZM API to ensure
their behavior matches what the server actually does, not what documentation
claims.
