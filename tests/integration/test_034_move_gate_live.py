"""T032 / FR-024, SC-003 — the gate sits on the Move path and only there.

Two claims, and the second matters as much as the first:

* a **Move** reaches `gt_api.execute_move` only after `confirm()` returned
  `True`;
* a **Preview** reaches `gt_api.compute_preview` with `confirm()` **never
  called** — a Preview that prompted would train users to dismiss the prompt,
  which is exactly how a click-through habit forms before the one time it
  matters.

Driven against the **real** `_PageFinish`, because the ordering being asserted
is a property of that method's body, not of a description of it. `execute_move`
and `compute_preview` are monkeypatched to record their calls: this test is
about call order and must never write to a project to find it out. Nothing here
opens LCM.

Marked `integration` per the task list even though it does not touch a live
project — it constructs the real wizard page against the real `gt_api`, so it
belongs with the tests that are excluded from the hosted-runner gate.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytestmark = pytest.mark.integration

pytest.importorskip("PyQt6")

from PyQt6 import QtWidgets  # noqa: E402

TARGET = "Ejagham Full GT-Test"


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


class _RecordingGate:
    """A gate that records every consultation, and answers as told."""

    def __init__(self, answer: bool):
        self.answer = answer
        self.calls = []

    def confirm(self, target_project_name):
        self.calls.append(target_project_name)
        return self.answer

    def finish_page_subtitle(self):
        return "recording gate"


class _Context:
    def __init__(self):
        self.target_project_name = TARGET
        self.target_handle = object()
        self.source_handle = object()


class _ProjectWSPage:
    def __init__(self, context):
        self._context = context

    def context(self):
        return self._context


class _FakeWizard:
    """The minimum `_PageFinish._on_move` reads.

    `page_skeleton()` is called unguarded; the phonology and entry-types
    helpers are `hasattr`-guarded, so their absence here makes them return
    empty lists — i.e. no EXCLUDED-LOSSY dialog, which is what we want: this
    test is about the gate, not about that dialog.
    """

    def __init__(self, context):
        self._page_project_ws = _ProjectWSPage(context)

    def page_project_ws(self):
        return self._page_project_ws

    def page_skeleton(self):
        return None


class _Plan:
    def excluded_lossy_count(self):
        return 0


@pytest.fixture()
def wired(qapp, monkeypatch):
    """A real `_PageFinish` with `execute_move` and `compute_preview` recorded."""
    from gramtrans.Lib import api as gt_api
    from gramtrans.Lib.ui import selection_wizard as sw

    calls = []

    def _fake_execute_move(context, plan):
        calls.append("execute_move")

        class _Report:
            pass

        return _Report()

    def _fake_compute_preview(context, selection, ws_mapping):
        calls.append("compute_preview")
        return (gt_api.PreviewState.PREVIEW_READY, _Plan())

    monkeypatch.setattr(sw.gt_api, "execute_move", _fake_execute_move)
    monkeypatch.setattr(sw.gt_api, "compute_preview", _fake_compute_preview)
    # StatsPanel.set_report would try to render a fake report object.
    monkeypatch.setattr(sw.StatsPanel, "set_report", lambda self, report: None)

    return sw, calls


def _page_ready_to_move(sw, gate):
    """A `_PageFinish` in the state a user reaches after a successful dry run."""
    page = sw._PageFinish(None, True, confirmation_gate=gate)
    context = _Context()
    wizard = _FakeWizard(context)
    page.wizard = lambda: wizard          # QWizardPage.wizard() is None standalone
    page._cached_plan = _Plan()           # what the dry run leaves behind
    return page


# ---------------------------------------------------------------------------
# FR-024 — Move consults the gate; Preview does not
# ---------------------------------------------------------------------------

def test_a_confirmed_move_reaches_execute_move(wired):
    sw, calls = wired
    gate = _RecordingGate(answer=True)

    _page_ready_to_move(sw, gate)._on_move()

    assert gate.calls == [TARGET], "the gate was not consulted exactly once"
    assert calls == ["execute_move"]


def test_the_gate_is_consulted_before_the_write_not_after(wired):
    """Ordering, stated as an ordering rather than inferred from two facts."""
    sw, calls = wired
    order = []
    gate = _RecordingGate(answer=True)

    original_confirm = gate.confirm

    def _tracking_confirm(name):
        order.append("confirm")
        return original_confirm(name)

    gate.confirm = _tracking_confirm
    monkeypatched = sw.gt_api.execute_move

    def _tracking_move(context, plan):
        order.append("execute_move")
        return monkeypatched(context, plan)

    sw.gt_api.execute_move = _tracking_move
    try:
        _page_ready_to_move(sw, gate)._on_move()
    finally:
        sw.gt_api.execute_move = monkeypatched

    assert order == ["confirm", "execute_move"]


def test_a_refused_move_writes_nothing_and_leaves_the_page_intact(wired):
    """FR-025: `False` aborts with no write, and the wizard survives it."""
    sw, calls = wired
    gate = _RecordingGate(answer=False)
    page = _page_ready_to_move(sw, gate)

    page._on_move()

    assert gate.calls == [TARGET]
    assert calls == [], "a refused gate still wrote to the target"
    assert page._move_done is False
    assert page._cached_plan is not None, (
        "the cached plan was discarded — the user would have to re-run the dry "
        "run after merely changing their mind"
    )


def test_a_preview_never_consults_the_gate(wired):
    """FR-024, the half that is easy to get wrong by being helpful."""
    sw, calls = wired
    gate = _RecordingGate(answer=True)
    page = sw._PageFinish(None, True, confirmation_gate=gate)
    context = _Context()
    wizard = _FakeWizard(context)
    page.wizard = lambda: wizard

    monkeypatch_target = sw._compute_wizard_plan
    sw._compute_wizard_plan = lambda w: (_Plan(), object())
    try:
        page._on_dry_run()
    finally:
        sw._compute_wizard_plan = monkeypatch_target

    assert gate.calls == [], "the Preview path consulted the confirmation gate"
    assert "execute_move" not in calls


def test_the_flextools_default_gate_does_not_add_a_step(wired):
    """SC-013: with no gate supplied, a Move proceeds exactly as before."""
    sw, calls = wired
    page = _page_ready_to_move(sw, None)

    page._on_move()

    assert calls == ["execute_move"]
    assert page._move_done is True
