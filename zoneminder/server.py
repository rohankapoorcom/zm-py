"""Classes that allow interacting with ZoneMinder servers."""


class Server:
    """Represents a Server from ZoneMinder's multi-server configuration."""

    def __init__(self, raw_server):
        """Create a new Server from the inner 'Server' dict of the API response."""
        self._server_id = int(raw_server["Id"])
        self._name = raw_server["Name"]
        self._hostname = raw_server["Hostname"]
        self._protocol = raw_server.get("Protocol", "http")
        self._port = raw_server.get("Port")
        self._path_to_zms = raw_server.get("PathToZMS", "/zm/cgi-bin/nph-zms")
        self._path_to_index = raw_server.get("PathToIndex", "/zm/index.php")
        self._status = raw_server.get("Status", "")
        self._zms_url = self._build_zms_url()
        self._base_url = self._build_base_url()
        self._fmt = "{}(id={}, name={}, hostname={})"

    def __repr__(self) -> str:
        """Representation of a Server."""
        return self._fmt.format(self.__class__.__name__, self.id, self.name, self.hostname)

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
    def hostname(self) -> str:
        """Get the hostname of this Server."""
        return self._hostname

    @property
    def protocol(self) -> str:
        """Get the URL scheme (http/https) of this Server."""
        return self._protocol

    @property
    def port(self):
        """Get the port of this Server, or None if not set."""
        return self._port

    @property
    def path_to_zms(self) -> str:
        """Get the path to ZMS on this Server."""
        return self._path_to_zms

    @property
    def path_to_index(self) -> str:
        """Get the path to index.php on this Server."""
        return self._path_to_index

    @property
    def status(self) -> str:
        """Get the status of this Server."""
        return self._status

    @property
    def zms_url(self) -> str:
        """Get the full ZMS URL for this server."""
        return self._zms_url

    @property
    def base_url(self) -> str:
        """Get the base URL for this server."""
        return self._base_url

    def _build_zms_url(self) -> str:
        """Build the full ZMS URL for this server.

        Format: {protocol}://{hostname}[:{port}]{path_to_zms}
        Port is only included when non-None.
        """
        host = self._hostname
        if self._port is not None:
            host = f"{host}:{self._port}"
        return f"{self._protocol}://{host}{self._path_to_zms}"

    def _build_base_url(self) -> str:
        """Build the base URL for this server from PathToIndex.

        Returns the directory portion of PathToIndex with a trailing slash,
        suitable for constructing PTZ and other control URLs.
        """
        # Extract directory from PathToIndex (e.g. "/zm/index.php" -> "/zm/")
        path = self._path_to_index
        last_slash = path.rfind("/")
        if last_slash >= 0:
            directory = path[: last_slash + 1]
        else:
            directory = "/"

        host = self._hostname
        if self._port is not None:
            host = f"{host}:{self._port}"
        return f"{self._protocol}://{host}{directory}"
