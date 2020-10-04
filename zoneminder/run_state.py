"""Classes that allow interacting with ZoneMinder RunStates."""


class RunState:
    """Represents a Run State from ZoneMinder."""

    def __init__(self, client, raw_state):
        """Create a new RunState."""
        self._client = client
        self._state_id = int(raw_state["Id"])
        self._state_url = "api/states.json"
        self._name = raw_state["Name"]

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
        states = self._client.get_state(self._state_url)["states"]
        for state in states:
            state = state["State"]
            if int(state["Id"]) == self._state_id:
                # yes, the ZM API uses the *string* "1" for this...
                return state["IsActive"] == "1"
        return False

    def activate(self):
        """Activate this RunState."""
        self._client.set_active_state(self._name)
