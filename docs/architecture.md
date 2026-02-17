# zm-py Architecture

Companion document to the [drawio diagrams](architecture.drawio) with Mermaid diagrams
that render directly on GitHub.

## Package Structure

zm-py is organized into 5 modules under the `zoneminder/` package:

```mermaid
graph TD
    ZM["zoneminder/zm.py<br/><b>ZoneMinder</b> (client)"]
    MON["zoneminder/monitor.py<br/><b>Monitor</b> + enums"]
    SRV["zoneminder/server.py<br/><b>Server</b>"]
    RS["zoneminder/run_state.py<br/><b>RunState</b>"]
    EXC["zoneminder/exceptions.py<br/><b>ZoneminderError</b> hierarchy"]
    REQ["requests.Session<br/><i>(external)</i>"]

    ZM -->|"imports Monitor,<br/>TimePeriod,<br/>get_api_alarm_states"| MON
    ZM -->|"imports Server"| SRV
    ZM -->|"imports RunState"| RS
    MON -->|"imports ControlTypeError,<br/>MonitorControlTypeError"| EXC
    ZM -.->|"uses"| REQ

    style ZM fill:#dae8fc,stroke:#6c8ebf
    style MON fill:#d5e8d4,stroke:#82b366
    style SRV fill:#fff2cc,stroke:#d6b656
    style RS fill:#e1d5e7,stroke:#9673a6
    style EXC fill:#f8cecc,stroke:#b85450
    style REQ fill:#f5f5f5,stroke:#666,stroke-dasharray: 5 5
```

## Key Design Patterns

### Client-based construction

`Monitor` and `RunState` hold a reference to the `ZoneMinder` client so they can make
API calls on demand (lazy properties like `is_recording`, `active`). `Server` objects
are standalone but are fetched and cached through the client.

```mermaid
graph LR
    ZM["ZoneMinder"]
    ZM -->|"creates"| M["Monitor"]
    ZM -->|"creates"| RS["RunState"]
    ZM -->|"creates"| S["Server"]
    M -.->|"_client ref"| ZM
    RS -.->|"_client ref"| ZM
```

### Defensive error handling

Most API errors return empty dict (`{}`) or `None` rather than raising exceptions.
Callers must check for falsy values. Exceptions are reserved for programming errors
(e.g. `ControlTypeError` for invalid PTZ directions, `MonitorControlTypeError` for
PTZ on non-controllable monitors).

### Dual auth

JWT authentication (ZM 1.30+) with automatic fallback to legacy session cookies:

```mermaid
flowchart TD
    A["login()"] --> B["Clear stale JWT token"]
    B --> C["POST api/host/login.json"]
    C --> D{"access_token<br/>in response?"}
    D -->|Yes| E["Store JWT token<br/>return True"]
    D -->|No| F["_legacy_auth()"]
    F --> G["POST index.php<br/>(cookies stored in Session)"]
    G --> H["GET api/host/getVersion.json<br/>(verify cookies work)"]
    H --> I["return True/False"]
```

Stale JWT tokens are cleared before re-auth to prevent 401s when falling back
to cookie auth (the session would send both the stale `?token=` and valid cookies,
and ZM rejects the stale token).

### Version-aware monitor fields

On ZM >= 1.37, the single `Function` column was decomposed into three independent
columns: `Capturing`, `Analysing`, `Recording`. zm-py detects the server version
and reads/writes the appropriate fields:

```mermaid
flowchart TD
    A["Monitor.function (getter)"] --> B{"ZM >= 1.37?"}
    B -->|Yes| C["Read Capturing/Analysing/Recording"]
    C --> D{"All three present?"}
    D -->|Yes| E["_derive_function() → MonitorState"]
    D -->|No| F["Fall back to Function column"]
    E --> G{"Mapped successfully?"}
    G -->|Yes| H["Return derived MonitorState"]
    G -->|No| F
    B -->|No| F
    F --> I["Return MonitorState(Function)"]
```

### Request retry with re-auth

```mermaid
flowchart TD
    A["_zm_request(method, url, data)"] --> B["Send request<br/>with token or cookies"]
    B --> C{"req.ok?"}
    C -->|Yes| D["return req.json()"]
    C -->|No| E{"Last attempt?"}
    E -->|No| F["login() — re-authenticate"]
    F --> B
    E -->|Yes| G["log error, return {}"]
```

## Caching Strategy

zm-py uses time-based caching (`time.monotonic()`) to reduce API calls within
Home Assistant's polling cycle:

| What | TTL | Invalidation | Location |
|------|-----|-------------|----------|
| `Monitor.update_monitor()` | 1 second | `function` setter sets `_last_update = 0.0` | `monitor.py` |
| `ZoneMinder.get_event_counts()` | 1 second | Natural expiry | `zm.py` |
| `RunState.active` | 1 second | Natural expiry | `run_state.py` |
| `ZoneMinder._alarm_states` | Login lifetime | Recalculated on each `login()` | `zm.py` |
| `ZoneMinder._servers` | Client lifetime | Lazy-fetched once, never refreshed | `zm.py` |

The 1-second TTL is designed for Home Assistant's typical 10-30 second polling
interval. Within a single poll cycle, HA accesses each monitor's properties
multiple times (function, is_available, events, etc.) across sensor, switch, and
camera entities. The cache ensures each API endpoint is hit at most once per cycle.

## Detailed Diagrams

For detailed visual diagrams, open the drawio files in [draw.io](https://app.diagrams.net/):

- **[architecture.drawio](architecture.drawio)** — Package architecture, class relationships, auth flow, multi-server URL routing (4 pages)
- **[api-overview.drawio](api-overview.drawio)** — API endpoints grid, monitor state model (2 pages)
