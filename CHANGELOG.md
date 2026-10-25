# Changelog

## 0.5.9 (2026-10-25)

### Behaviour change

- On ZoneMinder 1.37+, `Monitor.function` returns `None` when `Capturing`/`Analysing`/`Recording` have no classic equivalent (for example `Ondemand` capture, or analysing without recording), instead of the `Function` column. ZoneMinder no longer updates that column, so it reported a stale mode. The warning is logged once per monitor and combination instead of on every read. Read `capturing`, `analysing` and `recording` for the full state. (#88)

[Full diff](https://github.com/rohankapoorcom/zm-py/compare/v0.5.8...v0.5.9)

## 0.5.8 (2026-10-25)

### Bug fixes

- A monitor with a null `ServerId` is treated as being on the main server, without logging a warning. Single-server installs no longer log two warnings per monitor on every `get_monitors()`. (#82)

### Dependencies

- urllib3 2.8.0 (#80)

## 0.5.7 (2026-10-05)

### Behaviour change

- `login()` raises `requests.ConnectionError` or `requests.Timeout` when the server is unreachable, instead of returning `False`. `False` now only means the credentials were rejected. Requests made through `_zm_request` are unchanged. (#79)

### Bug fixes

- PTZ up and down moves now send the tilt speed, so control modules such as HikVision tilt, and diagonal moves no longer only pan. (#78)
- `get_monitors()` leaves out soft-deleted monitors. (#77)

### Dependencies

- pytest 9.0.3 (#74), black 26.3.1 (#72)

[Full diff](https://github.com/rohankapoorcom/zm-py/compare/v0.5.6...v0.5.7)

## 0.5.6 (2026-06-16)

### Features

- PTZ preset goto and home commands.

### Dependencies

- idna, urllib3, requests, pytest and black updated.

[Full diff](https://github.com/rohankapoorcom/zm-py/compare/v0.5.5...v0.5.6)

## 0.5.5 (2026-02-18)

### Breaking changes

- Python 3.13 or later is required.
- requests 2.32.2 or later is required.
- Reading `Monitor.function` no longer calls the API. It returns cached data, so call `monitor.update_monitor()` first to get the current value.

### Bug fixes

- `is_recording` uses alarm state tables that match the ZoneMinder version, instead of a fixed `STATE_ALARM=3`.
- `is_available` returns `False` when `Monitor_Status` is missing (ZoneMinder before 1.32.3), and handles a string `"1"` result.
- A stale JWT is cleared before logging in again, which stops a 401 on retry.
- `set_active_state()` URL-encodes the state name.
- PTZ `move_monitor()` raises `ControlTypeError` and `MonitorControlTypeError` instead of hiding them, and passes `verify_ssl` through.
- `_zm_request()` returns `{}` when retries run out, instead of `None`.
- Error logs include the method, URL and status code.

### Features

- On ZoneMinder 1.37 and later, `Monitor.function` reads and writes the `Capturing`, `Analysing` and `Recording` fields instead of the legacy `Function` field. Each field is also available on its own.
- Multi-server support: monitors use the URLs of the server they run on.
- `update_all_monitors()` refreshes every monitor in one API call. `update_monitor()` results are cached for one second.
- `stream_scale` and `stream_maxfps` options for stream URLs.
- `set_force_alarm_state()` forces a monitor into or out of alarm.
- HTTP connection pooling.

[Full diff](https://github.com/rohankapoorcom/zm-py/compare/v0.5.4...v0.5.5)

## 0.5.4 (2024-01-08)

[Full diff](https://github.com/rohankapoorcom/zm-py/compare/v0.5.3...v0.5.4)

## Earlier releases

See the [GitHub releases](https://github.com/rohankapoorcom/zm-py/releases).
