"""Classes that allow interacting with specific ZoneMinder servers."""

import json
import logging

_LOGGER = logging.getLogger(__name__)


class Server:
    """Represents a Server from ZoneMinder."""

    def __init__(self, client, raw_result):
        """Create a new Server."""
        _LOGGER.debug("INIT for server %s.", json.dumps(raw_result, sort_keys=False, indent=4))
        self._client = client
        self._raw_result = raw_result
        raw_server = raw_result["Server"]
        self._server_id = int(raw_server["Id"])
        self._name = raw_server["Name"]
        self._protocol = raw_server["Protocol"]
        self._hostname = raw_server["Hostname"]
        self._pathtozms = raw_server["PathToZMS"]
        self._pathtoindex = raw_server["PathToIndex"]
        self._pathtoapi = raw_server["PathToApi"]
        self._status = raw_server["Status"]
        self._fmt = "{}(id={}, name={}, status={})"

    def __repr__(self) -> str:
        """Representation of a Server."""
        return self._fmt.format(self.__class__.__name__, self.id, self.name)

    def __str__(self) -> str:
        """Representation of a Server."""
        return self.__repr__()

    @property
    def id(self) -> int:
        """Get the ZoneMinder id number of this Server."""
        # pylint: disable=invalid-name
        return self._server_id

    @property
    def name(self) -> str:
        """Get the name of this Server."""
        return self._name

    @property
    def protocol(self) -> str:
        """Get the protocol of this Server."""
        return self._protocol

    @property
    def hostname(self) -> str:
        """Get the hostname of this Server."""
        return self._hostname

    @property
    def pathtozms(self) -> str:
        """Get the ZMS path of this Server."""
        return self._pathtozms
