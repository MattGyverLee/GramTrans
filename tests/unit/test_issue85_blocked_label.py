"""Issue #85: the run report labels BLOCKED outcomes, not plain "skipped".

A selected item that did not arrive because its owner POS is missing in the
destination, or because its source object was not found, is a
`Skip(DEPENDENCY_UNRESOLVED)`. These tests pin how the report counts and
renders it, and the report-level warning for "not dispatched" lexicon
categories. Classification only: nothing here writes.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib import report as report_module
from gramtrans.Lib.models import (
    CategoryReport,
    GrammarCategory,
    PlannedAction,
    RunContext,
    RunMode,
    RunPlan,
    RunReport,
    Selection,
    Skip,
    SkipReason,
    WSMapping,
    is_blocked_skip,
)
from gramtrans.Lib.report import render_text_summary

TPL = GrammarCategory.AFFIX_TEMPLATES
STEM_NAMES = GrammarCategory.STEM_NAMES


def _ctx() -> RunContext:
    return RunContext(
        source_handle=object(),
        source_project_name="Src",
        source_project_path="/src",
        target_handle=object(),
        target_project_name="Tgt",
        target_project_path="/tgt",
        run_id="GT-20261030-120000",
        started_at="2026-10-30T12:00:00",
    )


def _skip(cat, guid, reason, detail) -> Skip:
    return Skip(category=cat, source_guid=guid, reason=reason, detail=detail)


def _owner_pos_skip(guid="tpl-1") -> Skip:
    return _skip(TPL, guid, SkipReason.DEPENDENCY_UNRESOLVED,
                 "affix template tpl-1... was not transferred: its owning "
                 "category (guid=pos-9...) is not present in the destination")


def _source_missing_skip(guid="tpl-2") -> Skip:
    return _skip(TPL, guid, SkipReason.DEPENDENCY_UNRESOLVED,
                 "source affix template %s not found in the source project"
                 % guid)


def _not_dispatched_skip(cat) -> Skip:
    return _skip(cat, cat.value, SkipReason.UNSUPPORTED_LCM_TYPE,
                 f"not dispatched: {cat.value} has no planner in the default "
                 "path; select AFFIXES and/or STEMS")


def _report(skips=(), extra_skips=(), actions=()) -> RunReport:
    plan = RunPlan(
        context=_ctx(),
        selection=Selection(categories={TPL: True}),
        ws_mapping=WSMapping(entries=()),
        actions=tuple(actions),
        skips=tuple(skips),
    )
    return RunReport.build_from_plan(plan, RunMode.MOVE,
                                     extra_skips=tuple(extra_skips))


def _text(report) -> str:
    return "\n".join(render_text_summary(report))


def test_only_dependency_unresolved_is_blocked():
    assert is_blocked_skip(_owner_pos_skip())
    for reason in (SkipReason.ALREADY_PRESENT_BY_GUID, SkipReason.UNMAPPED_WS,
                   SkipReason.UNSUPPORTED_LCM_TYPE, SkipReason.NEEDS_MANUAL,
                   SkipReason.INTERACTIVE_SKIP):
        assert not is_blocked_skip(_skip(TPL, "x", reason, "d"))


def test_blocked_affix_templates_are_counted_and_labelled():
    """Owner-POS-unresolved (plan skip) and source-not-found (exec skip) are
    both BLOCKED; the second is called out as a source data error."""
    report = _report(skips=[_owner_pos_skip()],
                     extra_skips=[_source_missing_skip()])
    r = report.per_category[TPL]
    assert (r.skipped, r.blocked) == (2, 2)
    text = _text(report)
    assert "skipped=2  blocked=2" in text
    assert ("[BLOCKED] 2 item(s) did NOT arrive (counted within skipped): "
            "1 missing a dependency in the destination, 1 source object not "
            "found (source data error)") in text
    assert text.count("    - [BLOCKED] [affix_templates]") == 2
    assert text.isascii()


def test_stem_name_dependency_unresolved_is_blocked():
    report = _report(extra_skips=[_skip(
        STEM_NAMES, "sn-1", SkipReason.DEPENDENCY_UNRESOLVED,
        "stem name sn-1... was not transferred: its owning category is not "
        "present in the destination")])
    assert report.per_category[STEM_NAMES].blocked == 1
    assert "    - [BLOCKED] [stem_names] sn-1" in _text(report)


def test_benign_skip_renders_no_blocked_label():
    report = _report(skips=[_skip(TPL, "t", SkipReason.ALREADY_PRESENT_BY_GUID,
                                  "already present")])
    assert report.per_category[TPL].blocked == 0
    text = _text(report)
    assert "BLOCKED" not in text
    assert "blocked=" not in text


def test_disposition_panel_names_the_blocked_subset():
    report = _report(
        skips=[_owner_pos_skip()],
        actions=[PlannedAction(category=TPL, source_guid="ok",
                               intended_target_guid="ok", summary="add ok")])
    assert report_module.disposition_totals(report)["skip_blocked"] == 1
    assert "of those, BLOCKED (did not arrive)" in _text(report)


def test_not_dispatched_lexicon_categories_raise_a_top_warning():
    report = _report(skips=[_not_dispatched_skip(GrammarCategory.ENTRY),
                            _not_dispatched_skip(GrammarCategory.SENSE)])
    lines = list(render_text_summary(report))
    # Right after the Source/Target header, ahead of the per-category table.
    assert lines[3] == ("  [WARN] NOT DISPATCHED -- selected, but nothing was "
                        "planned or written for: entry, sense")
    assert lines[4].startswith("  [WARN] No lexicon entries were transferred")
    # Not a blocked item: a whole category, reported by the warning instead.
    assert "[BLOCKED]" not in "\n".join(lines)


def test_not_dispatched_non_lexicon_category_omits_the_lexicon_hint():
    report = _report(skips=[_not_dispatched_skip(GrammarCategory.SLOTS)])
    text = _text(report)
    assert "[WARN] NOT DISPATCHED" in text
    assert "No lexicon entries" not in text


def test_no_warning_when_everything_dispatched():
    assert "NOT DISPATCHED" not in _text(_report(skips=[_owner_pos_skip()]))


def test_blocked_counter_must_reconcile_with_the_skips():
    with pytest.raises(ValueError, match="Issue #85"):
        RunReport(
            context=_ctx(),
            mode=RunMode.MOVE,
            per_category={TPL: CategoryReport(skipped=1, blocked=0)},
            skips=(_owner_pos_skip(),),
        )


@pytest.fixture(scope="module")
def qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QtWidgets = pytest.importorskip("PyQt6.QtWidgets")
    # Held by the fixture: an unreferenced QApplication is collected and the
    # first widget then crashes the interpreter.
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_stats_panel_tags_blocked_skips_and_warns_not_dispatched(qapp):
    """The post-run Qt panel carries the same two signals as the console."""
    from gramtrans.Lib.ui.stats_panel import StatsPanel

    panel = StatsPanel()
    panel.set_report(_report(skips=[
        _owner_pos_skip(), _not_dispatched_skip(GrammarCategory.MSA)]))
    skips = panel._skip_view.toPlainText().splitlines()
    assert skips[0].startswith("[BLOCKED] [affix_templates] tpl-1")
    assert skips[1].startswith("[msa] msa")
    assert panel._warn_view.toPlainText().startswith(
        "[WARN] NOT DISPATCHED -- selected, but nothing was planned or "
        "written for: msa")
