"""Issues #8 and #11 -- the shared plan-failure dialog and the cleared-plan hint.

#8: `_PagePreview._on_preview` and `_PageFinish._on_dry_run` route their
`plan is None` dialogs through one helper, `_warn_plan_failure`, so the two
cannot drift apart.

#11: when Finish-page re-entry discards a plan that actually existed, the
dry-run button says so; a fresh successful dry run restores the plain label.
"""
from __future__ import annotations

import inspect
import os

# House convention: offscreen platform chosen before Qt is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

PyQt6 = pytest.importorskip("PyQt6")

from PyQt6 import QtWidgets  # noqa: E402

from gramtrans.Lib.ui import selection_wizard as sw  # noqa: E402

_PLAIN = "Dry run (preview plan)"
_CLEARED = "Dry run (plan cleared - re-run)"


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _built_on_real_qt(cls) -> bool:
    """See test_036_finish_guard: sibling modules may install QWizardPage doubles."""
    return any(
        base.__name__ in ("QWizardPage", "QWizard")
        and getattr(base, "__module__", "").startswith("PyQt6")
        for base in cls.__mro__
    )


class _Sink:
    def Info(self, msg=""):  # noqa: N802
        pass

    def Warning(self, msg=""):  # noqa: N802
        pass

    def Error(self, msg=""):  # noqa: N802
        pass

    def Blank(self):  # noqa: N802
        pass


class _ProjectWS:
    def __init__(self, context) -> None:
        self._context = context

    def context(self):
        return self._context


class _Wizard:
    def __init__(self, context=None) -> None:
        self._ws = _ProjectWS(context)

    def page_project_ws(self):
        return self._ws


@pytest.fixture
def warnings(monkeypatch):
    popped = []

    def _warn(*args, **kwargs):
        popped.append(args[2] if len(args) > 2 else "")
        return QtWidgets.QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", staticmethod(_warn))
    return popped


def _finish(wizard):
    if not _built_on_real_qt(sw._PageFinish):
        pytest.skip("_PageFinish was built on a PyQt6 QWizardPage double")
    page = sw._PageFinish(_Sink(), True)
    page.wizard = lambda: wizard  # type: ignore[method-assign]
    return page


# ---------------------------------------------------------------------------
# #8 -- one helper, both callers
# ---------------------------------------------------------------------------

def test_helper_no_context_message(qapp, warnings):
    sw._warn_plan_failure(None, _Wizard(context=None))
    assert warnings == ["No target project bound. Go back to page 1."]


def test_helper_assembly_failure_default_message(qapp, warnings):
    sw._warn_plan_failure(None, _Wizard(context=object()))
    assert warnings == ["Plan assembly failed. Check project state."]


def test_helper_prefers_recorded_reason_and_consumes_it(qapp, warnings):
    wizard = _Wizard(context=object())
    sw._set_plan_failure_reason(wizard, "specific reason")
    sw._warn_plan_failure(None, wizard)
    sw._warn_plan_failure(None, wizard)
    assert warnings == ["specific reason",
                        "Plan assembly failed. Check project state."]


def test_both_callers_use_the_shared_helper():
    for fn in (sw._PagePreview._on_preview, sw._PageFinish._on_dry_run):
        src = inspect.getsource(fn)
        assert "_warn_plan_failure(self, wizard)" in src
        assert "QMessageBox.warning" not in src, f"{fn.__qualname__} pops its own dialog"


# ---------------------------------------------------------------------------
# #11 -- the cleared-plan hint
# ---------------------------------------------------------------------------

def _succeed(monkeypatch):
    monkeypatch.setattr(sw, "_safe_compute_wizard_plan",
                        lambda wizard: (object(), None))
    # StatsPanel.set_report(None) is not the subject here.
    monkeypatch.setattr(sw.StatsPanel, "set_report", lambda self, report: None)


def test_first_entry_shows_plain_label(qapp):
    page = _finish(_Wizard(context=object()))
    page.initializePage()
    assert page._dry_run_btn.text() == _PLAIN


def test_reentry_after_a_plan_shows_hint_and_dry_run_restores(qapp, monkeypatch):
    page = _finish(_Wizard(context=object()))
    _succeed(monkeypatch)
    page.initializePage()
    page._on_dry_run()
    assert page._dry_run_btn.text() == _PLAIN

    page.initializePage()          # back-navigation discarded the plan
    assert page._dry_run_btn.text() == _CLEARED

    page.initializePage()          # nothing new was discarded; hint stays
    assert page._dry_run_btn.text() == _CLEARED

    page._on_dry_run()
    assert page._dry_run_btn.text() == _PLAIN


def test_failed_dry_run_keeps_the_hint(qapp, monkeypatch, warnings):
    page = _finish(_Wizard(context=object()))
    _succeed(monkeypatch)
    page.initializePage()
    page._on_dry_run()
    page.initializePage()
    monkeypatch.setattr(sw, "_safe_compute_wizard_plan", lambda wizard: (None, None))
    page._on_dry_run()
    assert page._dry_run_btn.text() == _CLEARED
    assert warnings
