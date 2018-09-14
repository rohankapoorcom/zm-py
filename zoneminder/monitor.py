import logging
from enum import Enum
from typing import Optional
from urllib.parse import urlencode

_LOGGER = logging.getLogger(__name__)

# From ZoneMinder's web/includes/config.php.in
STATE_ALARM = 2


class MonitorState(Enum):
    """Represents the current state of the Monitor"""
    NONE = 'None'
    MONITOR = 'Monitor'
    MODECT = 'Modect'
    RECORD = 'Record'
    MOCORD = 'Mocord'
    NODECT = 'Nodect'


class TimePeriod(Enum):
    """Represents a period of time to check for events"""
    @property
    def period(self) -> str:
        """The period of time"""
        return self.value[0]

    @property
    def title(self) -> str:
        """The text that explains what is measured in this period"""
        return self.value[1]

    @staticmethod
    def get_time_period(value):
        for tl in TimePeriod:
            if tl.period == value:
                return tl
        raise ValueError('{} is not a valid TimePeriod'.format(value))

    ALL = ('all', 'Events')
    HOUR = ('hour', 'Events Last Hour')
    DAY = ('day', 'Events Last Day')
    WEEK = ('week', 'Events Last Week')
    MONTH = ('month', 'Events Last Month')


class Monitor:
    """Represents a Monitor from ZoneMinder"""
    def __init__(self, client, raw_monitor):
        self._client = client
        self._monitor_id = int(raw_monitor['Id'])
        self._monitor_url = 'api/monitors/{}.json'.format(self._monitor_id)
        self._name = raw_monitor['Name']
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
        """Gets the MonitorState of a Monitor"""
        return MonitorState(self._client.get_state(
            self._monitor_url)['monitor']['Monitor']['Function'])

    @function.setter
    def function(self, new_function):
        """Sets the MonitorState of a Monitor"""
        self._client.change_state(
            self._monitor_url,
            {'Monitor[Function]': new_function.value})

    @property
    def controllable(self) -> bool:
        """Indicates whether this Monitor is movable"""
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
                self._monitor_id
            )
        )

        if not status_response:
            _LOGGER.warning('Could not get status for monitor {}'.format(
                self._monitor_id
            ))
            return None

        return int(status_response.get('status')) == STATE_ALARM

    def get_events(self, time_period, include_archived=False) -> Optional[int]:
        """
        Get the number of events that have occurred on this Monitor in the
        during the current TimePeriod
        """
        date_filter = '1%20{}'.format(time_period.period)
        if time_period == TimePeriod.ALL:
            # The consoleEvents API uses DATE_SUB, so give it
            # something large
            date_filter = '100%20year'

        archived_filter = '/Archived=:0'
        if include_archived:
            archived_filter = ''

        event = self._client.get_state(
            'api/events/consoleEvents/{}{}.json'.format(
             date_filter,
             archived_filter
            )
        )

        try:
            return event['results'][str(self._monitor_id)]
        except (TypeError, KeyError):
            return None

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
