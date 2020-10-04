"""This module contains the set of zoneminder exceptions."""


class ZoneminderError(Exception):
    """General Zoneminder error occurred."""

    def __init__(self, value=None):
        """Create a generic exception."""
        super().__init__(value)
        self.value = value

    def __str__(self):
        """Get exception message based in docstring."""
        msg = self.__class__.__doc__
        if self.value is not None:
            msg = msg.rstrip(".")
            msg += ": " + repr(self.value) + "."
        return msg


class CommError(ZoneminderError):
    """A communication error occurred."""


class LoginError(ZoneminderError):
    """A login error occurred."""


class ControlTypeError(ZoneminderError):
    """Unexpected move direction."""


class MonitorControlTypeError(ZoneminderError):
    """Unexpected command to monitor."""


class PtzError(ZoneminderError):
    """A control error occurred."""
