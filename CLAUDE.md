# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

zm-py is a lightweight Python API client for ZoneMinder, built specifically for the Home Assistant ZoneMinder integration. It is in **maintenance mode** — bug fixes and compatibility updates are accepted; new features are not planned. Published as `zm-py` on PyPI (v0.5.4). Only runtime dependency is `requests>=2.0`.

## Commands

### Run all QA checks (what CI runs)
```bash
tox
```

### Run only unit tests
```bash
tox -e py314
```

### Run a single test file or test
```bash
pytest tests/test_zm.py
pytest tests/test_ptz.py::test_control_type_from_move_valid
```

### Individual linting/formatting checks
```bash
tox -e pylint   # pylint on zoneminder/
tox -e lint     # flake8 + pydocstyle + black + isort
tox -e typing   # mypy on zoneminder/*.py
```

### E2E tests (requires a live ZoneMinder server)
```bash
# E2E tests are excluded from `tox` — run them directly with pytest.
# They auto-skip when ZM_HOST is unset.
# Set env vars or create tests/.env.zm_e2e with ZM_HOST, ZM_USER, ZM_PASSWORD
pytest tests/e2e/
ZM_E2E_WRITE=1 pytest tests/e2e/ -m zm_e2e_write  # write-tier tests
```

### Install dependencies
```bash
poetry install
```

## Architecture

### Package structure (4 modules)

- **`zoneminder/zm.py`** — `ZoneMinder` client class. Main entry point. Handles auth (JWT with legacy cookie fallback), HTTP requests with retry, and high-level operations (get_monitors, get_run_states, move_monitor).
- **`zoneminder/monitor.py`** — `Monitor` class plus `MonitorState`, `ControlType`, `TimePeriod` enums. Each Monitor holds a reference to the client and makes API calls lazily through properties (`is_recording`, `is_available`, `function`).
- **`zoneminder/run_state.py`** — `RunState` class wrapping ZM preset configurations. The `active` property fetches all states from the API on every call (not cached).
- **`zoneminder/exceptions.py`** — Exception hierarchy rooted at `ZoneminderError`. Exception messages are auto-generated from class docstrings with an optional dynamic value appended.

### Key design patterns

- **Client-based construction**: `Monitor` and `RunState` hold a client reference so they can make API calls on demand.
- **Defensive error handling**: Most API errors return empty dict/None rather than raising exceptions. Callers must check for falsy values.
- **Dual auth**: JWT (ZM 1.30+) with automatic fallback to legacy session cookies.

## Code Style

- **Black** with 100-char line length
- **isort** with Black profile
- Flake8 ignores: E501, W503, E203, D202, W504
- Pylint ignores `tests/` directory
- mypy strict mode (no `ignore_errors`)
- Python 3.13+ supported (3.14 is primary; 3.13 for legacy HA compatibility)

## Testing

- **Unit tests** (`tests/test_*.py`): Use `StubClient` for isolation, no external dependencies. Run via `tox`.
- **E2E tests** (`tests/e2e/`): Require live ZoneMinder server. **Not run by `tox`** — run directly via `pytest tests/e2e/`. Auto-skip when `ZM_HOST` is unset. Write tests gated behind `ZM_E2E_WRITE=1`.
- CI runs unit tests, linters, and typing on Python 3.14.
- **Always run `tox` and confirm it passes before offering to commit.** Do not commit with failing checks.
- **Run `pytest tests/e2e/` locally before committing** to verify against a live ZoneMinder server.
