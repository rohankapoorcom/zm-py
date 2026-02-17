"""Classes that allow interacting with ZoneMinder RunStates."""

import time


class RunState:
    """Represents a Run State from ZoneMinder."""

    def __init__(self, client, raw_state):
        """Create a new RunState."""
        self._client = client
        self._state_id = int(raw_state["Id"])
        self._state_url = "api/states.json"
        self._name = raw_state["Name"]
        if "IsActive" in raw_state:
            self._is_active = int(raw_state["IsActive"]) == 1
            self._last_update = time.monotonic()
        else:
            self._is_active = False
            self._last_update = 0.0

    @property
    def id(self) -> int:
        """Get the ZoneMinder id number of this RunState."""
        # pylint: disable=invalid-name
        return self._state_id

    @property
    def name(self) -> str:
        """Get the name of this RunState."""
        return self._name

    @property
    def active(self) -> bool:
        """Indicate if this RunState is currently active."""
        now = time.monotonic()
        if now - self._last_update < 1.0:
            return self._is_active
        response = self._client.get_state(self._state_url)
        self._last_update = now
        if not response or "states" not in response:
            return self._is_active
        for state in response["states"]:
            state = state["State"]
            if int(state["Id"]) == self._state_id:
                # yes, the ZM API uses the *string* "1" for this...
                # Since ZM 1.36 this is now an *int*, provides support for legacy versions
                self._is_active = int(state["IsActive"]) == 1
                return self._is_active
        self._is_active = False
        return self._is_active

    def activate(self):
        """Activate this RunState."""
        self._client.set_active_state(self._name)
