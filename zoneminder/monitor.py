import logging
from urllib.parse import urlencode

_LOGGER = logging.getLogger(__name__)


class Monitor:

    def __init__(self, raw_monitor, zms_url, username, password):
        self._monitor_id = int(raw_monitor['Id'])
        self._name = raw_monitor['Name']
        self._monitor_function = raw_monitor['Function']
        self._controllable = bool(raw_monitor['Controllable'])
        self._mjpeg_image_url = Monitor._build_image_url(
            raw_monitor, zms_url, 'jpeg', username, password)
        self._still_image_url = Monitor._build_image_url(
            raw_monitor, zms_url, 'single', username, password)

    @property
    def id(self):
        return self._monitor_id

    @property
    def name(self):
        return self._name

    @property
    def function(self):
        return self._monitor_function

    @property
    def controllable(self):
        return self._controllable

    @property
    def mjpeg_image_url(self):
        """Get a motion jpeg (mjpeg) image url"""
        return self._mjpeg_image_url

    @property
    def still_image_url(self):
        """Get a still jpeg image url"""
        return self._still_image_url

    @staticmethod
    def _build_image_url(monitor, zms_url, mode,
                         username, password) -> str:
        """Build and return a Zoneminder camera image url"""
        query = urlencode({
            'mode': mode,
            'buffer': monitor['StreamReplayBuffer'],
            'monitor': monitor['Id'],
        })
        url = '{zms_url}?{query}'.format(zms_url=zms_url, query=query)
        _LOGGER.debug('Monitor %s %s URL (without auth): %s',
                      monitor['Id'], mode, url)

        if not username:
            return url

        url += '&user={:s}'.format(username)

        if not password:
            return url

        return url + '&pass={:s}'.format(password)