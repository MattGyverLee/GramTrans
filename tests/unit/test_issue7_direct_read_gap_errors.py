"""Issue #7 item 1: _direct_read_gap catches only LCM-read errors."""
import pytest

from gramtrans.Lib.merge_preview import _direct_read_gap, _lcm_read_errors


class _Boom:
    def __init__(self, exc):
        self._exc = exc

    @property
    def Name(self):
        raise self._exc


@pytest.mark.parametrize("exc", [AttributeError("x"), TypeError("x"), ValueError("x"), KeyError("x")])
def test_read_errors_return_none(exc):
    assert _direct_read_gap(_Boom(exc)) is None


def test_programming_error_propagates():
    with pytest.raises(NameError):
        _direct_read_gap(_Boom(NameError("bug")))


def test_read_errors_tuple_has_core_types():
    errs = _lcm_read_errors()
    assert AttributeError in errs and TypeError in errs
    assert NameError not in errs
