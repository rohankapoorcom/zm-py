"""Classes that allow interacting with specific ZoneMinder monitors."""

from enum import Enum
import json
import logging
from typing import Optional
from urllib.parse import urlencode

from requests import post

from .exceptions import ControlTypeError, MonitorControlTypeError

_LOGGER = logging.getLogger(__name__)

# From ZoneMinder's web/includes/config.php.in
STATE_ALARM = 3


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
    def from_move(cls, move) -> Enum:
        """Get the corresponding direction from the move.

        Example values: 'right', 'UP-RIGHT', 'down', 'down-left', or 'up_left'.
        """
        for move_key, move_obj in ControlType.__members__.items():
            if move_key == move.upper().replace("-", "_"):
                return move_obj
        raise ControlTypeError()


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
        # pylint: disable=unsubscriptable-object
        return self.value[0]

    @property
    def title(self) -> str:
        """Explains what is measured in this period."""
        # pylint: disable=unsubscriptable-object
        return self.value[1]

    @staticmethod
    def get_time_period(value):
        """Get the corresponding TimePeriod from the value.

        Example values: 'all', 'hour', 'day', 'week', or 'month'.
        """
        for time_period in TimePeriod:
            if time_period.period == value:
                return time_period
        raise ValueError(f"{value} is not a valid TimePeriod")

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

    def update_monitor(self):
        """Update the monitor and monitor status from the ZM server."""
        result = self._client.get_state(self._monitor_url)
        try:
            self._raw_result = result["monitor"]
        except KeyError:
            return False

    @property
    def function(self) -> MonitorState:
        """Get the MonitorState of this Monitor."""
        if self.update_monitor():
            return MonitorState(self._raw_result["Monitor"]["Function"])
        return "None"

    @function.setter
    def function(self, new_function):
        """Set the MonitorState of this Monitor."""
        self._client.change_state(self._monitor_url, {"Monitor[Function]": new_function.value})

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
    def is_recording(self) -> Optional[bool]:
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
            return int(status) == STATE_ALARM
        except ValueError:
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

        # Monitor_Status was only added in ZM 1.32.3
        monitor_status = self._raw_result.get("Monitor_Status", None)
        capture_fps = monitor_status and monitor_status["CaptureFPS"]
        monitor_state = monitor_status and monitor_status["Status"]

        return monitor_state == "Connected" and capture_fps != "0.00"

    def get_events(self, time_period, include_archived=False) -> Optional[int]:
        """Get the number of events that have occurred on this Monitor.

        Specifically only gets events that have occurred within the TimePeriod
        provided.
        """
        date_filter = f"1%20{time_period.period}"
        if time_period == TimePeriod.ALL:
            # The consoleEvents API uses DATE_SUB, so give it
            # something large
            date_filter = "100%20year"

        archived_filter = "/Archived=:0"
        if include_archived:
            archived_filter = ""

        event = self._client.get_state(
            f"api/events/consoleEvents/{date_filter}{archived_filter}.json"
        )

        try:
            events_by_monitor = event["results"]
            if isinstance(events_by_monitor, list):
                return 0
            return events_by_monitor.get(str(self._monitor_id), 0)
        except (TypeError, KeyError, AttributeError):
            return None

    def _build_image_url(self, monitor, mode) -> str:
        """Build and return a ZoneMinder camera image url."""
        query = urlencode(
            {
                "mode": mode,
                "buffer": monitor["StreamReplayBuffer"],
                "monitor": monitor["Id"],
            }
        )
        _LOGGER.debug(
            "_build_image_url for monitor %s.", json.dumps(monitor, sort_keys=False, indent=4)
        )
        if int(monitor["ServerId"]) > 0:
            server = self._client.servers_by_id[int(monitor["ServerId"])]
            server_hostname = f"{server.protocol}://{server.hostname}{server.pathtozms}"
        else:
            server_hostname = self._client.get_zms_url()
        _LOGGER.debug("_build_image_url server_hostname %s", server_hostname)

        url = f"{server_hostname}?{query}"
        _LOGGER.debug("Monitor %s %s URL (without auth): %s", monitor["Id"], mode, url)
        return self._client.get_url_with_auth(url)

    def ptz_control_command(self, direction, token, base_url) -> bool:
        """Move camera."""
        if not self.controllable:
            raise MonitorControlTypeError()

        ptz_url = f"{base_url}index.php"

        params = {
            "view": "request",
            "request": "control",
            "id": self.id,
            "control": ControlType.from_move(direction).value,
            "xge": 43,
            "token": token,
        }

        req = post(url=ptz_url, params=params, timeout=10)
        return bool(req.ok)
