"""Classes that allow interacting with specific ZoneMinder monitors."""

from __future__ import annotations

from enum import Enum
import logging
import time
from urllib.parse import urlencode

import requests

from .exceptions import ControlTypeError, MonitorControlTypeError

_LOGGER = logging.getLogger(__name__)

# Alarm state values as returned by the ZM API alarm status endpoint.
#
# The API endpoint /api/monitors/alarm/id:{id}/command:status.json shells out
# to `zmu -s` and returns the numeric state from the C++ Monitor::State enum.
# However, in ZM 1.36.26 a backwards-compatibility hack was added that
# subtracts 1 from the value before returning it (MonitorsController.php).
# This hack was never removed even though the C++ enum was later reverted.
#
# See: docs/api/state-alarm-analysis.md
# Tracking: https://github.com/rohankapoorcom/zm-py/issues/60
#
# Version ranges and their API return values for alarm status:
#   < 1.36.16  : C++ enum had UNKNOWN=-1, so ALARM=2.  No API offset.
#   1.36.16-25 : C++ enum shifted UNKNOWN=0, so ALARM=3. No API offset.
#   >= 1.36.26 : C++ enum has ALARM=3, but API subtracts 1, so returns 2.

# API alarm status values for most ZM versions (< 1.36.16 and >= 1.36.26).
# Before 1.36.16: C++ enum had UNKNOWN=-1, giving these values natively.
# From 1.36.26+: C++ enum has UNKNOWN=0, but the API subtracts 1 (hack).
API_STATES_WITH_OFFSET = {
    "UNKNOWN": -1,
    "IDLE": 0,
    "PREALARM": 1,
    "ALARM": 2,
    "ALERT": 3,
}

# API alarm status values for ZM 1.36.16 through 1.36.25 (no -1 hack)
API_STATES_NO_OFFSET = {
    "UNKNOWN": 0,
    "IDLE": 1,
    "PREALARM": 2,
    "ALARM": 3,
    "ALERT": 4,
}


def _parse_version(version_string):
    """Parse a ZM version string like '1.36.26' into a comparable tuple."""
    try:
        return tuple(int(x) for x in version_string.split("."))
    except (ValueError, AttributeError):
        return None


def get_api_alarm_states(zm_version):
    """Return the correct alarm state table for the given ZM version string.

    The API alarm status endpoint returns different numeric values depending
    on whether MonitorsController applies a -1 offset. Only ZM 1.36.16
    through 1.36.25 lack this offset.
    """
    parsed = _parse_version(zm_version)
    if parsed and (1, 36, 16) <= parsed <= (1, 36, 25):
        return API_STATES_NO_OFFSET
    return API_STATES_WITH_OFFSET


class ControlType(Enum):
    """Represents the possibles movements types of the Monitor."""

    RIGHT = "moveConRight"
    LEFT = "moveConLeft"
    UP = "moveConUp"
    DOWN = "moveConDown"
    UP_LEFT = "moveConUpLeft"
    UP_RIGHT = "moveConUpRight"
    DOWN_LEFT = "moveConDownLeft"
    DOWN_RIGHT = "moveConDownRight"

    @classmethod
    def from_move(cls, move: str) -> ControlType:
        """Get the corresponding direction from the move.

        Example values: 'right', 'UP-RIGHT', 'down', 'down-left', or 'up_left'.
        """
        try:
            return cls[move.upper().replace("-", "_")]
        except KeyError:
            raise ControlTypeError() from None


class MonitorState(Enum):
    """Represents the current state of the Monitor."""

    NONE = "None"
    MONITOR = "Monitor"
    MODECT = "Modect"
    RECORD = "Record"
    MOCORD = "Mocord"
    NODECT = "Nodect"


class TimePeriod(Enum):
    """Represents a period of time to check for events."""

    @property
    def period(self) -> str:
        """Get the period of time."""
        return self.value[0]

    @property
    def title(self) -> str:
        """Explains what is measured in this period."""
        return self.value[1]

    @classmethod
    def get_time_period(cls, value):
        """Get the corresponding TimePeriod from the value.

        Example values: 'all', 'hour', 'day', 'week', or 'month'.
        """
        try:
            return cls._period_map()[value]
        except KeyError:
            raise ValueError(f"{value} is not a valid TimePeriod") from None

    @classmethod
    def _period_map(cls) -> dict[str, TimePeriod]:
        """Lazily build and cache a {period_string: TimePeriod} lookup."""
        try:
            return cls.__period_map  # type: ignore[attr-defined]
        except AttributeError:
            cls.__period_map = {tp.period: tp for tp in cls}  # type: ignore[attr-defined]
            return cls.__period_map  # type: ignore[attr-defined]

    ALL = ("all", "Events")
    HOUR = ("hour", "Events Last Hour")
    DAY = ("day", "Events Last Day")
    WEEK = ("week", "Events Last Week")
    MONTH = ("month", "Events Last Month")


class Monitor:
    """Represents a Monitor from ZoneMinder."""

    def __init__(self, client, raw_result):
        """Create a new Monitor."""
        self._client = client
        self._raw_result = raw_result
        self._last_update = time.monotonic()
        raw_monitor = raw_result["Monitor"]
        self._monitor_id = int(raw_monitor["Id"])
        self._monitor_url = f"api/monitors/{self._monitor_id}.json"
        self._name = raw_monitor["Name"]
        self._controllable = bool(int(raw_monitor["Controllable"]))
        self._mjpeg_image_url = self._build_image_url(raw_monitor, "jpeg")
        self._still_image_url = self._build_image_url(raw_monitor, "single")
        self._fmt = "{}(id={}, name={}, controllable={})"

    def __repr__(self) -> str:
        """Representation of a Monitor."""
        return self._fmt.format(self.__class__.__name__, self.id, self.name, self.controllable)

    def __str__(self) -> str:
        """Representation of a Monitor."""
        return self.__repr__()

    @property
    def id(self) -> int:
        """Get the ZoneMinder id number of this Monitor."""
        # pylint: disable=invalid-name
        return self._monitor_id

    @property
    def name(self) -> str:
        """Get the name of this Monitor."""
        return self._name

    @property
    def raw_monitor(self) -> dict:
        """Get the inner 'Monitor' dict from the raw API result."""
        return self._raw_result["Monitor"]

    def update_monitor(self):
        """Update the monitor and monitor status from the ZM server."""
        now = time.monotonic()
        if now - self._last_update < 1.0:
            return
        result = self._client.get_state(self._monitor_url)
        if not result or "monitor" not in result:
            _LOGGER.warning("Could not refresh monitor %s from API", self._monitor_id)
            return
        self._raw_result = result["monitor"]
        self._last_update = now

    @property
    def function(self) -> MonitorState:
        """Get the MonitorState of this Monitor."""
        return MonitorState(self._raw_result["Monitor"]["Function"])

    @function.setter
    def function(self, new_function):
        """Set the MonitorState of this Monitor."""
        self._client.change_state(self._monitor_url, {"Monitor[Function]": new_function.value})
        self._last_update = 0.0

    @property
    def controllable(self) -> bool:
        """Indicate whether this Monitor is movable."""
        return self._controllable

    @property
    def mjpeg_image_url(self) -> str:
        """Get the motion jpeg (mjpeg) image url of this Monitor."""
        return self._mjpeg_image_url

    @property
    def still_image_url(self) -> str:
        """Get the still jpeg image url of this Monitor."""
        return self._still_image_url

    @property
    def is_recording(self) -> bool | None:
        """Indicate if this Monitor is currently recording."""
        status_response = self._client.get_state(
            f"api/monitors/alarm/id:{self._monitor_id}/command:status.json"
        )

        if not status_response:
            _LOGGER.warning("Could not get status for monitor %s.", self._monitor_id)
            return None

        status = status_response.get("status")
        # ZoneMinder API returns an empty string to indicate that this monitor
        # cannot record right now
        try:
            states = self._client.get_alarm_states()
            return int(status) >= states["ALARM"]
        except (ValueError, TypeError):
            return False

    @property
    def is_available(self) -> bool:
        """Indicate if this Monitor is currently available."""
        status_response = self._client.get_state(
            f"api/monitors/daemonStatus/id:{self._monitor_id}/daemon:zmc.json"
        )

        if not status_response:
            _LOGGER.warning("Could not get availability for monitor %s.", self._monitor_id)
            return False

        self.update_monitor()

        # Monitor_Status was only added in ZM 1.32.3
        monitor_status = self._raw_result.get("Monitor_Status", None)
        if not monitor_status:
            return False
        capture_fps = monitor_status.get("CaptureFPS", "0.00")

        return status_response.get("status", False) and capture_fps != "0.00"

    def get_events(self, time_period, include_archived=False) -> int | None:
        """Get the number of events that have occurred on this Monitor.

        Specifically only gets events that have occurred within the TimePeriod
        provided. Delegates to the client's cached bulk fetch so that multiple
        monitors in the same polling cycle share a single API call.
        """
        events_by_monitor = self._client.get_event_counts(time_period, include_archived)
        if events_by_monitor is None:
            return None
        return events_by_monitor.get(str(self._monitor_id), 0)

    def _build_image_url(self, monitor, mode) -> str:
        """Build and return a ZoneMinder camera image url."""
        query = urlencode(
            {
                "mode": mode,
                "buffer": monitor["StreamReplayBuffer"],
                "monitor": monitor["Id"],
            }
        )
        zms_url = self._client.get_zms_url_for_monitor(monitor)
        url = f"{zms_url}?{query}"
        _LOGGER.debug("Monitor %s %s URL (without auth): %s", monitor["Id"], mode, url)
        return self._client.get_url_with_auth(url)

    def ptz_control_command(self, direction, token, base_url, cookies=None) -> bool:
        """Move camera."""
        if not self.controllable:
            raise MonitorControlTypeError()

        ptz_url = f"{base_url}index.php"

        params: dict[str, str | int] = {
            "view": "request",
            "request": "control",
            "id": self.id,
            "control": ControlType.from_move(direction).value,
            "xge": 43,
        }
        if token:
            params["token"] = token

        try:
            req = self._client._session.post(  # pylint: disable=protected-access
                url=ptz_url,
                params=params,
                cookies=cookies,
                timeout=10,
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _LOGGER.exception("Unable to connect to ZoneMinder for PTZ control")
            return False
        return bool(req.ok)
