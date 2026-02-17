# zm-py API Reference

Public API reference for zm-py v0.5.5. All classes, methods, properties, and enums
documented below are part of the public interface.

## ZoneMinder

**Module:** `zoneminder.zm`

The main API client. Create one instance per ZoneMinder server.

### Constructor

```python
ZoneMinder(
    server_host: str,       # e.g. "http://192.168.1.10:8080"
    username: str,
    password: str,
    server_path: str = "/zm/",
    zms_path: str = "/zm/cgi-bin/nph-zms",
    verify_ssl: bool = True,
    stream_scale: int | None = None,     # e.g. 50 for 50% scale
    stream_maxfps: float | None = None,  # e.g. 5.0 for 5 FPS cap
)
```

- `stream_scale` — injected as `&scale=` into all monitor image URLs.
- `stream_maxfps` — injected as `&maxfps=` into MJPEG stream URLs (not still images).

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `login()` | `bool` | Authenticate via JWT; falls back to legacy session cookies. Clears stale tokens before re-auth. |
| `get_monitors()` | `list[Monitor]` | Fetch all monitors from `api/monitors.json`. |
| `get_run_states()` | `list[RunState]` | Fetch all run states from `api/states.json`. |
| `get_servers()` | `list[Server]` | Fetch all servers from `api/servers.json`. |
| `update_all_monitors(monitors)` | `None` | Bulk-refresh a list of monitors in a single API call instead of one per monitor. |
| `get_event_counts(time_period, include_archived=False)` | `dict \| None` | Fetch console event counts for all monitors. Cached for 1 second. |
| `move_monitor(monitor, direction)` | `bool` | Send a PTZ command. Routes to the correct server for multi-server setups. |
| `get_active_state()` | `str \| None` | Get the name of the currently active run state. |
| `set_active_state(state_name)` | `dict` | Activate a run state by name. Long-running call (120s timeout). |
| `get_state(api_url)` | `dict` | Low-level GET against any ZM API endpoint. |
| `change_state(api_url, post_data)` | `dict` | Low-level POST against any ZM API endpoint. |
| `get_zms_url()` | `str` | Get the main ZMS streaming URL. |
| `get_url_with_auth(url)` | `str` | Append `&user=` and `&pass=` query params to a URL. |
| `get_zms_url_for_monitor(raw_monitor)` | `str` | Resolve the correct ZMS URL for a monitor based on its `ServerId`. |
| `get_server_url_for_monitor(raw_monitor)` | `str` | Resolve the correct base URL for a monitor based on its `ServerId`. |
| `get_alarm_states()` | `dict` | Return the alarm state value table for this server's ZM version. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_available` | `bool` | Whether the ZM daemon is running (`api/host/daemonCheck.json`). |
| `zm_version` | `str \| None` | Server version string (e.g. `"1.38.0"`), populated after `login()`. |
| `verify_ssl` | `bool` | Whether HTTPS certificate verification is enabled. |

---

## Monitor

**Module:** `zoneminder.monitor`

Represents a single ZoneMinder camera monitor. Created by `ZoneMinder.get_monitors()`.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | `int` | ZoneMinder monitor ID. |
| `name` | `str` | Monitor name. |
| `controllable` | `bool` | Whether PTZ control is enabled. |
| `function` | `MonitorState` | Current monitor function. On ZM >= 1.37, derived from `Capturing`/`Analysing`/`Recording`. Settable. |
| `capturing` | `str \| None` | The `Capturing` field (ZM 1.37+). `None` on older versions. Settable. |
| `analysing` | `str \| None` | The `Analysing` field (ZM 1.37+). `None` on older versions. Settable. |
| `recording` | `str \| None` | The `Recording` field (ZM 1.37+). `None` on older versions. Settable. |
| `mjpeg_image_url` | `str` | MJPEG stream URL (includes auth, scale, maxfps). |
| `still_image_url` | `str` | Single-frame JPEG URL (includes auth, scale). |
| `is_recording` | `bool \| None` | Whether the monitor is in ALARM or ALERT state. `None` if status unavailable. |
| `is_available` | `bool` | Whether the capture daemon is running and producing frames. |
| `raw_monitor` | `dict` | The inner `"Monitor"` dict from the raw API response. |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `update_monitor()` | `None` | Refresh monitor data from the API. Cached for 1 second. |
| `get_events(time_period, include_archived=False)` | `int \| None` | Event count for this monitor in the given period. Delegates to the client's cached bulk fetch. |
| `set_force_alarm_state(state: bool)` | `None` | Force alarm on (`True`) or cancel forced alarm (`False`). |
| `ptz_control_command(direction, token, base_url, cookies=None)` | `bool` | Send a PTZ movement command. Raises `MonitorControlTypeError` if not controllable. |

---

## Server

**Module:** `zoneminder.server`

Represents a server in ZoneMinder's multi-server configuration. Created by `ZoneMinder.get_servers()`.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | `int` | ZoneMinder server ID. |
| `name` | `str` | Server name. |
| `hostname` | `str` | Server hostname. |
| `protocol` | `str` | URL scheme (`"http"` or `"https"`). Defaults to `"http"`. |
| `port` | `str \| None` | Server port, or `None` if not set. |
| `path_to_zms` | `str` | Path to the ZMS CGI binary. Defaults to `"/zm/cgi-bin/nph-zms"`. |
| `path_to_index` | `str` | Path to index.php. Defaults to `"/zm/index.php"`. |
| `status` | `str` | Server status string. |
| `zms_url` | `str` | Full ZMS URL: `{protocol}://{hostname}[:{port}]{path_to_zms}`. |
| `base_url` | `str` | Base URL for control requests: `{protocol}://{hostname}[:{port}]{dir(path_to_index)}/`. |

---

## RunState

**Module:** `zoneminder.run_state`

Represents a ZoneMinder run state (preset camera configurations). Created by `ZoneMinder.get_run_states()`.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | `int` | ZoneMinder state ID. |
| `name` | `str` | State name. |
| `active` | `bool` | Whether this state is currently active. Cached for 1 second via `time.monotonic()`. |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `activate()` | `None` | Activate this run state (calls `ZoneMinder.set_active_state()`). |

---

## Enums

**Module:** `zoneminder.monitor`

### MonitorState

```python
class MonitorState(Enum):
    NONE = "None"
    MONITOR = "Monitor"
    MODECT = "Modect"       # Motion detection
    RECORD = "Record"       # Continuous recording
    MOCORD = "Mocord"       # Motion detection + continuous recording
    NODECT = "Nodect"       # No detection, record on external triggers
```

### ControlType

```python
class ControlType(Enum):
    RIGHT = "moveConRight"
    LEFT = "moveConLeft"
    UP = "moveConUp"
    DOWN = "moveConDown"
    UP_LEFT = "moveConUpLeft"
    UP_RIGHT = "moveConUpRight"
    DOWN_LEFT = "moveConDownLeft"
    DOWN_RIGHT = "moveConDownRight"
```

| Method | Returns | Description |
|--------|---------|-------------|
| `ControlType.from_move(move: str)` | `ControlType` | Parse a direction string (e.g. `"right"`, `"UP-RIGHT"`, `"down_left"`). Raises `ControlTypeError` on invalid input. |

### TimePeriod

```python
class TimePeriod(Enum):
    ALL = ("all", "Events")
    HOUR = ("hour", "Events Last Hour")
    DAY = ("day", "Events Last Day")
    WEEK = ("week", "Events Last Week")
    MONTH = ("month", "Events Last Month")
```

| Property/Method | Returns | Description |
|----------------|---------|-------------|
| `.period` | `str` | The period string (e.g. `"hour"`). |
| `.title` | `str` | Human-readable label (e.g. `"Events Last Hour"`). |
| `TimePeriod.get_time_period(value: str)` | `TimePeriod` | Look up by period string. Raises `ValueError` on invalid input. |

---

## Exceptions

**Module:** `zoneminder.exceptions`

All exceptions inherit from `ZoneminderError`. The `__str__` method auto-generates
messages from each class's docstring, with an optional dynamic value appended.

```
ZoneminderError          — "General Zoneminder error occurred."
├── CommError            — "A communication error occurred."
├── LoginError           — "A login error occurred."
├── ControlTypeError     — "Unexpected move direction."
├── MonitorControlTypeError — "Unexpected command to monitor."
└── PtzError             — "A control error occurred."
```

```python
# Example:
>>> str(ControlTypeError("diagonal-spin"))
"Unexpected move direction: 'diagonal-spin'."
```

---

## Usage Examples

### Basic setup

```python
from zoneminder.zm import ZoneMinder

zm = ZoneMinder(
    server_host="http://192.168.1.10",
    username="admin",
    password="secret",
    server_path="/zm/",
    verify_ssl=False,
    stream_scale=50,      # 50% resolution for streams
    stream_maxfps=5.0,    # cap MJPEG at 5 FPS
)
zm.login()

for monitor in zm.get_monitors():
    print(f"{monitor.name}: {monitor.function.value}")
```

### PTZ control

```python
controllable = [m for m in zm.get_monitors() if m.controllable]
for monitor in controllable:
    zm.move_monitor(monitor, "right")
```

### Run states

```python
states = zm.get_run_states()
for state in states:
    print(f"{state.name}: active={state.active}")

# Activate a state by name
zm.set_active_state("Home")
```

### Force alarm

```python
monitor = zm.get_monitors()[0]
monitor.set_force_alarm_state(True)   # force alarm on
monitor.set_force_alarm_state(False)  # cancel forced alarm
```

### Stream parameters

```python
# stream_scale and stream_maxfps are set at client construction
# and automatically injected into monitor image URLs:
monitor = zm.get_monitors()[0]
print(monitor.mjpeg_image_url)
# ...?mode=jpeg&buffer=0&monitor=1&scale=50&maxfps=5.0&user=admin&pass=secret
print(monitor.still_image_url)
# ...?mode=single&buffer=0&monitor=1&scale=50&user=admin&pass=secret
```

### Multi-server

```python
# In multi-server setups, monitors route to the correct server automatically.
# The servers API is fetched lazily on first access.
servers = zm.get_servers()
for server in servers:
    print(f"{server.name}: {server.hostname} ({server.zms_url})")
```
