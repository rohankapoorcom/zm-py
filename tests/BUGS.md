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

## BUG-002: Stale JWT token used after re-login in retry loop

**File:** `zoneminder/zm.py:108-129`
**Verified:** Code review (token expiry not safely triggerable in e2e)

`_zm_request()` computes `token_url_suffix` once before the retry loop
(line 110-112). After `self.login()` refreshes `self._auth_token` (line 127),
the next iteration still uses the old pre-computed suffix.

**Expected:** Recompute token suffix inside the loop after re-login.

**Impact:** JWT retry is broken -- second attempt reuses the expired token.

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

## BUG-005: `_zm_request` returns error response on retry exhaustion

**File:** `zoneminder/zm.py:131-135`
**Verified:** Code review (retry exhaustion not safely triggerable in e2e)

When all retries fail (for/else on line 131), execution falls through to
`req.json()` on line 135, returning the last failed response's JSON body
as if it were success data.

**Expected:** Return `{}` or raise, consistent with the `ConnectionError`
handler on line 143.

**Impact:** Callers silently process error responses as valid data.

---

## BUG-006: `login()` does not catch `ConnectionError`

**File:** `zoneminder/zm.py:53-67`
**Verified:** Code review -- `login()` calls `requests.post()` with no
try/except, while `_zm_request()` catches `ConnectionError` on line 142.

**Expected:** Catch `ConnectionError` and return `False`.

**Impact:** Uncaught exception crashes HA integration setup when ZM is down.

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
