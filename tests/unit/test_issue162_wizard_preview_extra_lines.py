"""Issue #162 -- the SelectionWizard's Preview paths render the extra lines.

`render_preview_extra_lines(plan)` composes the Preview-only lines (reversal
Add/Link plan, config views, sense appendix/thesaurus/picture references,
lexical-relation creates, ...). Its only GUI caller was `MainWindow._on_preview`,
which no production path constructs. The wizard that `_run_gui` actually
launches -- `_PageFinish._on_dry_run` (the real Preview; it is in `flow()`) and
`_PagePreview._on_preview` (retained, out of the flow) -- called
`self._stats.set_report(report)` with no `extra_lines`, so none of those lines
ever reached the operator before Move wrote them (Principle III).

* wiring -- `render_preview_extra_lines` is replaced with a recording sentinel;
  each handler must call it with the very plan it computed and hand the result
  to the panel.
* end to end -- the REAL render function on a REAL `RunPlan` that carries a
  reversal decision and a config-view record; the text must land in the
  StatsPanel's extra pane.
* negative controls -- a plan with no extras leaves the pane hidden, and a
  failed plan assembly never renders anything.
"""
from __future__ import annotations

import os

# House convention: offscreen platform chosen before Qt is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

PyQt6 = pytest.importorskip("PyQt6")

from PyQt6 import QtWidgets  # noqa: E402

from gramtrans.Lib.models import (  # noqa: E402
    ConfigViewAction,
    ConfigViewRecord,
    ReversalDecision,
    RunContext,
    RunMode,
    RunPlan,
    RunReport,
    Selection,
    WSMapping,
)
from gramtrans.Lib.ui import selection_wizard as sw  # noqa: E402


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

    def page_skeleton(self):
        return None


def _ctx() -> RunContext:
    return RunContext(
        source_handle=object(),
        source_project_name="Src",
        source_project_path="/fake/src",
        target_handle=object(),
        target_project_name="Tgt",
        target_project_path="/fake/tgt",
        run_id="GT-20261101-120000",
        started_at="2026-11-01T12:00:00",
    )


def _report() -> RunReport:
    # Empty per_category + no skips satisfies the FR-018 __post_init__ invariant.
    return RunReport(context=_ctx(), mode=RunMode.PREVIEW)


def _plan(reversal_decisions=(), config_view_records=()) -> RunPlan:
    return RunPlan(
        context=_ctx(),
        selection=Selection(),
        ws_mapping=WSMapping(entries=()),
        reversal_decisions=reversal_decisions,
        config_view_records=config_view_records,
    )


def _plan_with_extras() -> RunPlan:
    decision = ReversalDecision(
        source_entry_guid="entry-guid-1",
        target_index_ref=None,  # None -> to-create -> "Add"
        target_ws_id="en",
        linked_sense_guids=("sense-guid-1",),
        reversal_form_alts={"en": "person"},
    )
    cv = ConfigViewRecord(
        kind="ReversalIndex",
        filename="en.fwdictconfig",
        src_path="/x",
        tgt_path="/y",
        action=ConfigViewAction.ADD,
        missing_refs=[],
    )
    return _plan(reversal_decisions=(decision,), config_view_records=(cv,))


def _finish_page(wizard):
    if not _built_on_real_qt(sw._PageFinish):
        pytest.skip("_PageFinish was built on a PyQt6 QWizardPage double")
    page = sw._PageFinish(_Sink(), True)
    page.wizard = lambda: wizard  # type: ignore[method-assign]
    page.initializePage()
    return page


def _preview_page(wizard):
    if not _built_on_real_qt(sw._PagePreview):
        pytest.skip("_PagePreview was built on a PyQt6 QWizardPage double")
    page = sw._PagePreview()
    page.wizard = lambda: wizard  # type: ignore[method-assign]
    return page


# Both wizard Preview paths, as (page factory, slot name).
_PATHS = [
    pytest.param(_finish_page, "_on_dry_run", id="finish-dry-run"),
    pytest.param(_preview_page, "_on_preview", id="preview-page"),
]


def _extra_text(page) -> str:
    return page._stats._extra_view.toPlainText()


# ---------------------------------------------------------------------------
# Wiring -- the plan the handler computed is the plan that gets rendered
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("make_page, slot", _PATHS)
def test_handler_renders_extra_lines_of_its_own_plan(qapp, monkeypatch,
                                                     make_page, slot):
    plan, report = object(), _report()
    seen = []

    def _render(p):
        seen.append(p)
        return ("SENTINEL-162 line one", "SENTINEL-162 line two")

    monkeypatch.setattr(sw, "_safe_compute_wizard_plan",
                        lambda wizard: (plan, report))
    monkeypatch.setattr(sw, "render_preview_extra_lines", _render)

    page = make_page(_Wizard(context=_ctx()))
    getattr(page, slot)()

    assert seen == [plan], "render_preview_extra_lines not called with the plan"
    shown = _extra_text(page)
    assert "SENTINEL-162 line one" in shown
    assert "SENTINEL-162 line two" in shown
    assert not page._stats._extra_view.isHidden()


# ---------------------------------------------------------------------------
# End to end -- real render, real RunPlan, real StatsPanel
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("make_page, slot", _PATHS)
def test_real_plan_extra_lines_reach_the_stats_panel(qapp, monkeypatch,
                                                     make_page, slot):
    plan = _plan_with_extras()
    monkeypatch.setattr(sw, "_safe_compute_wizard_plan",
                        lambda wizard: (plan, _report()))

    page = make_page(_Wizard(context=_ctx()))
    getattr(page, slot)()

    shown = _extra_text(page)
    assert not page._stats._extra_view.isHidden(), "extra pane not revealed"
    assert "Reversal index [en] (Add):" in shown
    assert "person" in shown
    assert "Configuration views:" in shown
    assert "en.fwdictconfig" in shown


# ---------------------------------------------------------------------------
# Negative controls
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("make_page, slot", _PATHS)
def test_plan_without_extras_leaves_the_pane_hidden(qapp, monkeypatch,
                                                    make_page, slot):
    monkeypatch.setattr(sw, "_safe_compute_wizard_plan",
                        lambda wizard: (_plan(), _report()))

    page = make_page(_Wizard(context=_ctx()))
    getattr(page, slot)()

    assert page._stats._extra_view.isHidden()
    assert _extra_text(page) == ""


@pytest.mark.parametrize("make_page, slot", _PATHS)
def test_failed_plan_assembly_renders_nothing(qapp, monkeypatch,
                                              make_page, slot):
    calls = []
    monkeypatch.setattr(sw, "_safe_compute_wizard_plan",
                        lambda wizard: (None, None))
    monkeypatch.setattr(sw, "render_preview_extra_lines",
                        lambda p: calls.append(p) or ("SHOULD-NOT-APPEAR",))
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "warning",
        staticmethod(lambda *a, **k: QtWidgets.QMessageBox.StandardButton.Ok))

    page = make_page(_Wizard(context=_ctx()))
    getattr(page, slot)()

    assert calls == []
    assert "SHOULD-NOT-APPEAR" not in _extra_text(page)
