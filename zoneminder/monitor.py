import logging
from enum import Enum
from typing import Optional
from urllib.parse import urlencode

_LOGGER = logging.getLogger(__name__)

# From ZoneMinder's web/includes/config.php.in
STATE_ALARM = 2


class MonitorState(Enum):
    NONE = None
    MONITOR = 'Monitor'
    MODECT = 'Modect'
    RECORD = 'Record'
    MOCORD = 'Mocord'
    NODECT = 'Nodect'


class Monitor:

    def __init__(self, client, raw_monitor):
        self._client = client
        self._monitor_id = int(raw_monitor['Id'])
        self._name = raw_monitor['Name']
        self._monitor_function = MonitorState(raw_monitor['Function'])
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
    def function(self) -> MonitorState:
        return self._monitor_function

    def set_function(self, new_function) -> bool:
        self._client.change_state(
            'api/monitors/{}.json'.format(self._monitor_id),
            {'Monitor[Function]': new_function.value})
        self._monitor_function = new_function
        return True

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
    def is_recording(self) -> Optional[bool]:
        """Indicates where the Monitor is currently recording"""
        status_response = self._client.get_state(
            'api/monitors/alarm/id:{}/command:status.json'.format(
                self._monitor_id)
        )

        if not status_response:
            _LOGGER.warning('Could not get status for monitor {}'.format(
                self._monitor_id))
            return None

        return int(status_response.get('status')) == STATE_ALARM

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
