# zm-py Known Bugs

Verified against ZoneMinder **1.38.0**, API version **2.0**.

**Policy:** Do not fix yet -- document here to guide refactoring.

---

## BUG-001: `move_monitor()` swallows exceptions silently

**File:** `zoneminder/zm.py:242-253`
**Verified:** E2E confirmed -- `test_move_monitor_swallows_exception`

`move_monitor()` catches both `ControlTypeError` and
`MonitorControlTypeError`, logs them, and returns `None`. Callers cannot
distinguish success from failure.

**Expected:** Re-raise or return a boolean. `MonitorControlTypeError`
(non-controllable monitor) should propagate since it's a programming error.

**Impact:** HA integration silently ignores PTZ failures.

---

## BUG-002: ~~Stale JWT token used after re-login in retry loop~~ FIXED

**File:** `zoneminder/zm.py` — `_zm_request()`
**Status:** Fixed. `token_url_suffix` is now recomputed inside the retry loop
after `self.login()` refreshes `self._auth_token`.
**Test:** `tests/test_client.py::TestStaleTokenRetry`

---

## BUG-003: `Monitor.is_available` uses stale `_raw_result`

**File:** `zoneminder/monitor.py:173-187`
**Verified:** E2E confirmed `Monitor_Status` exists with `CaptureFPS='10.00'`
(str) on both list and single endpoints, but `is_available` reads from
`_raw_result` set at construction time.

`is_available` fetches fresh `daemonStatus` but reads `Monitor_Status` /
`CaptureFPS` from `self._raw_result` which was set during `get_monitors()`
or the last `update_monitor()`. No refresh before reading.

**Expected:** Call `update_monitor()` first, or read from the daemon response.

**Impact:** `is_available` returns stale results when capture state changes.

---

## BUG-004: PTZ ignores `verify_ssl` setting

**File:** `zoneminder/monitor.py:246`
**Verified:** Code review -- `requests.post()` has no `verify=` kwarg.
Every other API call passes `verify=self._verify_ssl`.

**Expected:** Pass `verify=self._client._verify_ssl`.

**Impact:** PTZ fails with SSL errors on self-signed HTTPS setups even when
`verify_ssl=False`.

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
