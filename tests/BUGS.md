# zm-py Known Bugs

Verified against ZoneMinder **1.38.0**, API version **2.0**.

**Policy:** Do not fix yet -- document here to guide refactoring.

---

## BUG-001: ~~`move_monitor()` swallows exceptions silently~~ FIXED

**File:** `zoneminder/zm.py` — `move_monitor()`
**Status:** Fixed. Exceptions now propagate to callers; method returns `bool`.
**Test:** `tests/test_client.py::TestMoveMonitor`

---

## BUG-002: ~~Stale JWT token used after re-login in retry loop~~ FIXED

**File:** `zoneminder/zm.py` — `_zm_request()`
**Status:** Fixed. `token_url_suffix` is now recomputed inside the retry loop
after `self.login()` refreshes `self._auth_token`.
**Test:** `tests/test_client.py::TestStaleTokenRetry`

---

## BUG-003: ~~`Monitor.is_available` uses stale `_raw_result`~~ FIXED

**File:** `zoneminder/monitor.py` — `is_available`
**Status:** Fixed. Now calls `update_monitor()` before reading `Monitor_Status`.
Also returns `False` when `Monitor_Status` is missing (pre-1.32.3 ZM).
**Test:** `tests/test_monitor.py::TestMonitorIsAvailable`

---

## BUG-004: ~~PTZ ignores `verify_ssl` setting~~ FIXED

**File:** `zoneminder/monitor.py` — `ptz_control_command()`
**Status:** Fixed. Now passes `verify=self._client._verify_ssl` to `requests.post()`.
**Test:** `tests/test_monitor.py::TestPtzControlCommand::test_ptz_passes_verify_ssl`

---

## BUG-005: ~~`_zm_request` returns error response on retry exhaustion~~ FIXED

**File:** `zoneminder/zm.py` — `_zm_request()`
**Status:** Fixed. The `for/else` clause now returns `{}` when all retries
are exhausted, consistent with the `ConnectionError` handler.
**Test:** `tests/test_client.py::TestRetryExhaustion`

---

## BUG-006: ~~`login()` does not catch `ConnectionError`~~ FIXED

**File:** `zoneminder/zm.py` — `login()` and `_legacy_auth()`
**Status:** Fixed. Both `login()` and `_legacy_auth()` now catch
`requests.exceptions.ConnectionError` and return `False`.
**Test:** `tests/test_client.py::TestLoginConnectionError`

---

## ZM 1.38.0 API Response Types

Reference from E2E probe tests (`test_e2e_api_probes.py`):

| Endpoint | Field | Type | Example |
|----------|-------|------|---------|
| `host/login.json` | `access_token` | str | JWT eyJ... |
| `host/login.json` | `refresh_token` | str | JWT eyJ... (zm-py ignores) |
| `host/login.json` | `access_token_expires` | int | 7200 |
| `host/login.json` | `credentials` | str | `auth=258e...` (zm-py ignores) |
| `host/login.json` | `append_password` | int | 0 (zm-py ignores) |
| `host/daemonCheck.json` | `result` | int | 1 |
| `host/getVersion.json` | `version` | str | `1.38.0` |
| `host/getVersion.json` | `apiversion` | str | `2.0` |
| `monitors.json` | item keys | -- | `Monitor`, `Manufacturer`, `CameraModel`, `Monitor_Status`, `Event_Summary` |
| `monitors/{id}.json` | envelope | -- | `{"monitor": {"Monitor": {...}, "Monitor_Status": {...}}}` |
| `Monitor_Status` | `CaptureFPS` | str | `'10.00'` |
| `monitors/alarm/...` | `status` | int | 0 |
| `monitors/daemonStatus/...` | `status` | bool | `True` |
| `events/consoleEvents/...` | `results` | dict | `{'1': 133, '3': 39, ...}` |
| `states.json` | `IsActive` | int | 1 or 0 |
