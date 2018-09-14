import logging
from urllib.parse import urlencode

_LOGGER = logging.getLogger(__name__)


class Monitor:

    def __init__(self, client, raw_monitor):
        self._client = client
        self._monitor_id = int(raw_monitor['Id'])
        self._name = raw_monitor['Name']
        self._monitor_function = raw_monitor['Function']
        self._controllable = bool(raw_monitor['Controllable'])
        self._mjpeg_image_url = self._build_image_url(
            raw_monitor, 'jpeg')
        self._still_image_url = self._build_image_url(
            raw_monitor, 'single')

    @property
    def id(self) -> int:
        return self._monitor_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def function(self) -> str:
        return self._monitor_function

    @property
    def controllable(self) -> bool:
        return self._controllable

    @property
    def mjpeg_image_url(self) -> str:
        """Get a motion jpeg (mjpeg) image url"""
        return self._mjpeg_image_url

    @property
    def still_image_url(self) -> str:
        """Get a still jpeg image url"""
        return self._still_image_url

    @property
    def is_recording(self) -> bool:
        """Indicates where the camera is currently recording"""

    def _build_image_url(self, monitor, mode) -> str:
        """Build and return a ZoneMinder camera image url"""
        query = urlencode({
            'mode': mode,
            'buffer': monitor['StreamReplayBuffer'],
            'monitor': monitor['Id'],
        })
        url = '{zms_url}?{query}'.format(
            zms_url=self._client.get_zms_url(), query=query)
        _LOGGER.debug('Monitor %s %s URL (without auth): %s',
                      monitor['Id'], mode, url)
        return self._client.get_url_with_auth(url)
