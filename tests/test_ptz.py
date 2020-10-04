"""Tests to verify ControlType."""


from pytest import mark, raises
from zoneminder.monitor import ControlType
from zoneminder.exceptions import ControlTypeError


@mark.parametrize(
    "source,want",
    [
        ("right", ControlType.RIGHT),
        ("LEFT", ControlType.LEFT),
        ("UP_LEFT", ControlType.UP_LEFT),
        ("down-LEFT", ControlType.DOWN_LEFT),
    ],
)
def test_control_type_from_move(source, want):
    """Verifies that ControlType return correct move type."""
    assert ControlType.from_move(source) == want


@mark.parametrize(
    "source,want",
    [
        ("UP-DOWN", raises(ControlTypeError)),
        ("rigth", raises(ControlTypeError)),
    ],
)
def test_control_type_from_move_wrong_move(source, want):
    """Verifies that ControlType return correct exceptions."""
    with want:
        ControlType.from_move(source)
