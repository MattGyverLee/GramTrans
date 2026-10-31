"""Issue #145 -- the FlexTools-module Preview paths show the Preview extra lines.

`gramtrans.py` has two module-level Preview paths: `_headless_phase0` (the
PyQt-less fallback of `MainFunction`) and `phase2_interactive_move`. Before the
fix neither called `preview.render_preview_extra_lines`, so the reversal
Add/Link plan, config views, feature/category links, complex-form and struct
types, and the #116 sense appendix / thesaurus rows never reached the module's
Preview report -- only `ui/main_window.py._on_preview` rendered them.

Two layers:

* wiring -- `render_preview_extra_lines` is replaced with a sentinel tuple and
  each path must pass every sentinel line to `report.Info`, BEFORE the Move
  (here: on a preview-only run, where no Move ever happens);
* real renderer -- `build_run_plan` returns a real `RunPlan` carrying a #116
  sense-list reference decision, and the real `render_preview_extra_lines`
  output must reach the report text.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib import flexinit
from gramtrans.Lib.models import (
    GrammarCategory,
    PlannedAction,
    ReferenceAction,
    ReferenceDecisionRecord,
    RunContext,
    RunPlan,
    Selection,
    WSMapping,
)

try:
    from gramtrans import gramtrans as _gt
except ImportError as _exc:  # pragma: no cover - host-only modules
    _gt = None
    _GT_IMPORT_ERROR = str(_exc)
else:
    _GT_IMPORT_ERROR = ""

pytestmark = pytest.mark.skipif(
    _gt is None, reason=f"gramtrans host imports unavailable: {_GT_IMPORT_ERROR}")

SENTINEL = ("  GT145 sentinel header:", "    GT145 sentinel row {g-145}")


# ============================================================================
# Doubles
# ============================================================================

class _Src:
    def OpenProject(self, **kw):  # noqa: N802
        pass

    def CloseProject(self):  # noqa: N802
        pass


class _Tgt:
    def ProjectName(self):  # noqa: N802
        return "GT-Sandbox-145"


class _Report:
    def __init__(self):
        self.lines = []

    def Info(self, msg):  # noqa: N802
        self.lines.append(("info", msg))

    def Warning(self, msg):  # noqa: N802
        self.lines.append(("warning", msg))

    def Error(self, msg):  # noqa: N802
        self.lines.append(("error", msg))

    def Blank(self):  # noqa: N802
        self.lines.append(("blank", ""))

    @property
    def text(self):
        return "\n".join(m for _, m in self.lines)


class _StubPlan:
    actions = overwrites = skips = dropped_items = category_notes = ()


def _real_plan():
    """A real RunPlan with one #116 sense-list decision (LINK appendix)."""
    ctx = RunContext(
        source_handle=object(), source_project_name="GT-Src-145",
        source_project_path="", target_handle=object(),
        target_project_name="GT-Sandbox-145", target_project_path="",
        run_id="GT-145", started_at="2026-10-31T00:00:00")
    rec = ReferenceDecisionRecord(
        owner_kind="LexSense", owner_guid="s1", field_name="AppendixesRC",
        action=ReferenceAction.LINK, item_name="Appendix 145", item_guid="ap-145")
    action = PlannedAction(
        category=GrammarCategory.STEMS, source_guid="e1",
        intended_target_guid="e1", summary="entry",
        reference_decisions=(rec,))
    return RunPlan(context=ctx, selection=Selection(),
                   ws_mapping=WSMapping(entries=()), actions=(action,))


def _patch_common(monkeypatch, plan):
    monkeypatch.setattr(flexinit, "ensure_sldr_initialized", lambda: None)
    monkeypatch.setattr(_gt, "FLExProject", _Src)
    monkeypatch.setattr(_gt, "_safe_project_path", lambda p: "")
    monkeypatch.setattr(_gt, "build_run_plan", lambda *a, **k: plan)


def _run_headless(monkeypatch, plan):
    _patch_common(monkeypatch, plan)
    report = _Report()
    _gt._headless_phase0(_Tgt(), report, False)
    assert not [m for k, m in report.lines if k == "error"], report.text
    return report


def _run_phase2(monkeypatch, plan):
    _patch_common(monkeypatch, plan)
    monkeypatch.setattr(_gt, "detect_ws_mismatches", lambda s, t: [])
    monkeypatch.setattr(_gt, "default_ws_choices", lambda s, t: ())
    monkeypatch.setattr(_gt, "collect_overwrite_conflicts", lambda *a: [])
    report = _Report()
    result = _gt.phase2_interactive_move(
        _Tgt(), report, False, source_project_name="GT-Src-145")
    assert result is None  # preview-only: no Move
    return report


def _info(report):
    return [m for k, m in report.lines if k == "info"]


# ============================================================================
# Wiring
# ============================================================================

def test_headless_preview_reports_every_extra_line(monkeypatch):
    seen = []
    monkeypatch.setattr(_gt, "render_preview_extra_lines",
                        lambda p: seen.append(p) or SENTINEL)
    plan = _StubPlan()
    report = _run_headless(monkeypatch, plan)
    assert seen == [plan]
    info = _info(report)
    for line in SENTINEL:
        assert line in info, report.text
    # Shown as part of the Preview block, before the preview-only notice.
    notice = info.index("(Preview-only run: no writes performed.)")
    assert all(info.index(line) < notice for line in SENTINEL)


def test_phase2_preview_reports_every_extra_line_before_conflicts(monkeypatch):
    seen = []
    monkeypatch.setattr(_gt, "render_preview_extra_lines",
                        lambda p: seen.append(p) or SENTINEL)
    plan = _StubPlan()
    report = _run_phase2(monkeypatch, plan)
    assert seen == [plan]
    info = _info(report)
    hits = [i for i, m in enumerate(info) for line in SENTINEL if line in m]
    assert len(hits) == len(SENTINEL), report.text
    conflicts = next(i for i, m in enumerate(info) if "No conflicts in plan" in m)
    assert max(hits) < conflicts, "extra lines must precede the conflict step"


def test_empty_extra_lines_add_nothing(monkeypatch):
    monkeypatch.setattr(_gt, "render_preview_extra_lines", lambda p: ())
    report = _run_headless(monkeypatch, _StubPlan())
    assert "GT145" not in report.text


# ============================================================================
# Real renderer: the #116 appendix row reaches the module's Preview text
# ============================================================================

@pytest.mark.parametrize("runner", [_run_headless, _run_phase2],
                         ids=["headless_phase0", "phase2_interactive_move"])
def test_real_sense_list_lines_reach_module_preview(monkeypatch, runner):
    report = runner(monkeypatch, _real_plan())
    text = report.text
    assert "Sense appendix / thesaurus references:" in text, text
    assert "Link  AppendixesRC 'Appendix 145' {ap-145}  (1 sense)" in text, text
