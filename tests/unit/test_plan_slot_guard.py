"""A clicked button must never let an exception cross into Qt.

`_on_dry_run` and `_on_preview` are slots, called from C++. An exception raised
in one has no Python frame above it to catch, so PyQt6 answers it with
`sys.excepthook` and then `qFatal()`/`abort()` -- a window that vanishes, or a
button that appears to do nothing at all. Both have shipped.

The live failure: a non-1:1 writing-system mapping raised `ValueError` out of
step 6 of `_compute_wizard_plan`, so Dry run did nothing, showed no dialog, and
wrote nothing to the log. `_compute_wizard_plan` had documented "(None, None) on
any failure" the whole time; it simply was not true.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sw = pytest.importorskip("gramtrans.Lib.ui.selection_wizard")


class FakeWizard:
    """Enough of a wizard to reach -- and fail -- plan assembly."""

    def __init__(self, boom: BaseException | None = None) -> None:
        self._boom = boom

    def page_project_ws(self):
        if self._boom is not None:
            raise self._boom
        return None  # unreachable in these tests


def test_a_raising_assembly_becomes_none_none_not_an_exception():
    wizard = FakeWizard(boom=ValueError("WS mapping not 1:1: 'en' and 'swh'"))
    plan, report = sw._safe_compute_wizard_plan(wizard)   # must not raise
    assert plan is None and report is None


def test_the_reason_survives_for_the_dialog():
    wizard = FakeWizard(boom=ValueError("WS mapping not 1:1: 'en' and 'swh'"))
    sw._safe_compute_wizard_plan(wizard)
    reason = sw._take_plan_failure_reason(wizard)
    assert reason, "the operator would have got a dead button again"
    assert "ValueError" in reason
    assert "not 1:1" in reason


def test_the_reason_is_cleared_once_taken():
    """A stale reason must not be reported against a later, different run."""
    wizard = FakeWizard(boom=RuntimeError("first"))
    sw._safe_compute_wizard_plan(wizard)
    assert sw._take_plan_failure_reason(wizard)
    assert sw._take_plan_failure_reason(wizard) == ""


def test_a_specific_reason_is_not_overwritten_by_the_generic_one():
    """Step 6 sets a plain-language reason; the guard must defer to it."""
    wizard = FakeWizard()
    sw._set_plan_failure_reason(wizard, "go back to Writing Systems")

    def _raise(_w):
        raise ValueError("raw internal detail")

    original = sw._compute_wizard_plan
    try:
        sw._compute_wizard_plan = _raise
        sw._safe_compute_wizard_plan(wizard)
    finally:
        sw._compute_wizard_plan = original
    assert sw._take_plan_failure_reason(wizard) == "go back to Writing Systems"


def test_a_wizard_that_rejects_attributes_does_not_break_the_guard():
    """Fake wizards in the suite use __slots__; the guard must still return."""

    class Slotted:
        __slots__ = ()

        def page_project_ws(self):
            raise ValueError("boom")

    plan, report = sw._safe_compute_wizard_plan(Slotted())
    assert plan is None and report is None
    assert sw._take_plan_failure_reason(Slotted()) == ""
