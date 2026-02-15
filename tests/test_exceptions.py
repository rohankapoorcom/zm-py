"""Unit tests for zm-py exception classes."""

from __future__ import annotations

from zoneminder.exceptions import (
    CommError,
    ControlTypeError,
    LoginError,
    MonitorControlTypeError,
    PtzError,
    ZoneminderError,
)


class TestExceptionHierarchy:
    """All exceptions should inherit from ZoneminderError."""

    def test_comm_error(self):
        assert issubclass(CommError, ZoneminderError)

    def test_login_error(self):
        assert issubclass(LoginError, ZoneminderError)

    def test_control_type_error(self):
        assert issubclass(ControlTypeError, ZoneminderError)

    def test_monitor_control_type_error(self):
        assert issubclass(MonitorControlTypeError, ZoneminderError)

    def test_ptz_error(self):
        assert issubclass(PtzError, ZoneminderError)

    def test_base_is_exception(self):
        assert issubclass(ZoneminderError, Exception)


class TestExceptionStr:
    """Exception __str__ uses docstring as message."""

    def test_no_value(self):
        err = ZoneminderError()
        assert str(err) == "General Zoneminder error occurred."

    def test_with_value(self):
        err = ZoneminderError("oops")
        msg = str(err)
        assert "oops" in msg
        assert "General Zoneminder error" in msg

    def test_subclass_uses_own_docstring(self):
        err = CommError()
        assert "communication error" in str(err).lower()

    def test_subclass_with_value(self):
        err = LoginError("bad creds")
        msg = str(err)
        assert "login error" in msg.lower()
        assert "bad creds" in msg

    def test_control_type_error_message(self):
        assert "move direction" in str(ControlTypeError()).lower()

    def test_monitor_control_type_error_message(self):
        assert "command to monitor" in str(MonitorControlTypeError()).lower()

    def test_all_exceptions_are_catchable_as_base(self):
        for cls in (CommError, LoginError, ControlTypeError,
                    MonitorControlTypeError, PtzError):
            try:
                raise cls("test")
            except ZoneminderError:
                pass  # expected
