"""Issue #84: ENTRY/SENSE/MSA/ALLOMORPH are dispatched as AFFIXES + STEMS.

The legacy verb-vertical closure that owned the four lexicon categories is
retired, so selecting them used to plan nothing. `build_run_plan` now rewrites
them onto the categories that carry lexicon entries before dispatch, and says
so in `RunPlan.category_notes` -> `RunReport.category_notes` -> [INFO] lines.
"""
from __future__ import annotations

import gramtrans.Lib.categories as categories
import gramtrans.Lib.preview as preview
from gramtrans.Lib.models import (
    GrammarCategory as GC, RunContext, RunMode, RunReport, Selection, WSMapping,
)
from gramtrans.Lib.report import render_text_summary

LEX = (GC.ENTRY, GC.SENSE, GC.MSA, GC.ALLOMORPH)


def _sel(*cats, **kw):
    return Selection(categories={c: True for c in cats}, **kw)


# ---------------------------------------------------------------------------
# expand_lexicon_categories (pure)
# ---------------------------------------------------------------------------

def test_no_lexicon_category_is_untouched():
    sel = _sel(GC.POS, GC.SLOTS, pos_picks=frozenset({"p"}))
    out, notes = preview.expand_lexicon_categories(sel)
    assert out is sel and notes == ()


def test_lexicon_only_expands_to_affixes_and_stems():
    out, notes = preview.expand_lexicon_categories(_sel(*LEX, GC.SLOTS))
    assert out.is_on(GC.AFFIXES) and out.is_on(GC.STEMS)
    assert out.is_on(GC.SLOTS)
    assert not any(out.is_on(c) for c in LEX)
    assert len(notes) == 1
    assert "entry, sense, msa, allomorph" in notes[0]
    assert "affixes + stems" in notes[0]


def test_each_lexicon_category_alone_expands_to_both_carriers():
    # MSA and ALLOMORPH belong to affix AND stem entries alike: no narrower
    # reading exists, so each one alone brings in both carriers.
    for c in LEX:
        out, notes = preview.expand_lexicon_categories(_sel(c))
        assert out.is_on(GC.AFFIXES) and out.is_on(GC.STEMS), c
        assert not out.is_on(c) and notes, c


def test_explicit_carrier_choice_is_kept():
    # The caller's explicit AFFIXES-only choice wins: STEMS stays off (the
    # full-selection harness relies on this) and the note says so.
    out, notes = preview.expand_lexicon_categories(_sel(GC.ENTRY, GC.AFFIXES))
    assert out.is_on(GC.AFFIXES) and not out.is_on(GC.STEMS)
    assert not out.is_on(GC.ENTRY)
    assert "inside the selected affixes" in notes[0]
    assert "stems is not selected" in notes[0]

    out, notes = preview.expand_lexicon_categories(
        _sel(GC.MSA, GC.AFFIXES, GC.STEMS))
    assert out.is_on(GC.AFFIXES) and out.is_on(GC.STEMS)
    assert "affixes + stems" in notes[0] and "not selected" not in notes[0]


def test_pos_picks_note_and_other_fields_preserved():
    sel = _sel(GC.POS, *LEX, pos_picks=frozenset({"p1"}), enable_overwrite=True,
               interactive_merge=True,
               leaf_item_picks={GC.STEMS: frozenset({"s1"})})
    out, notes = preview.expand_lexicon_categories(sel)
    assert "do not narrow the lexicon" in notes[0]
    assert out.pos_picks == sel.pos_picks
    assert out.enable_overwrite and out.interactive_merge
    assert out.leaf_picks_for(GC.STEMS) == frozenset({"s1"})


# ---------------------------------------------------------------------------
# build_run_plan wiring
# ---------------------------------------------------------------------------

class _FakeProj:
    def __getattr__(self, name):
        raise AttributeError(name)


def _ctx():
    return RunContext(
        source_handle=object(), source_project_name="S", source_project_path="/s",
        target_handle=object(), target_project_name="T", target_project_path="/t",
        run_id="GT-20261030-120000", started_at="2026-10-30T12:00:00",
    )


def _plan_recording(monkeypatch, sel):
    calls = []

    def _bundle(cat):
        return {"enumerate_source": lambda ctx, s: calls.append(cat) or [],
                "plan_action": lambda *a: None}

    monkeypatch.setattr(categories, "for_category", _bundle)
    plan = preview.build_run_plan(_ctx(), sel, WSMapping(entries=()),
                                  _FakeProj(), _FakeProj())
    return plan, calls


def test_default_set_dispatches_affixes_and_stems_once(monkeypatch):
    sel = _sel(GC.POS, GC.AFFIX_TEMPLATES, GC.SLOTS, *LEX, GC.PH_ENVIRONMENT,
               pos_picks=frozenset({"p1"}))
    plan, calls = _plan_recording(monkeypatch, sel)
    # Each carrier enumerated exactly once: no second (legacy) path.
    assert calls.count(GC.AFFIXES) == 1 and calls.count(GC.STEMS) == 1
    assert not any(c in LEX for c in calls)
    assert not any("not dispatched" in s.detail for s in plan.skips)
    assert plan.selection.is_on(GC.AFFIXES) and plan.selection.is_on(GC.STEMS)
    assert len(plan.category_notes) == 1


def test_full_selection_without_stems_does_not_pull_stems(monkeypatch):
    sel = Selection(categories={c: True for c in GC if c is not GC.STEMS})
    plan, calls = _plan_recording(monkeypatch, sel)
    assert GC.AFFIXES in calls and GC.STEMS not in calls
    assert "stems is not selected" in plan.category_notes[0]


def test_report_renders_info_note_and_no_empty_lexicon_lines(monkeypatch):
    plan, _ = _plan_recording(monkeypatch, _sel(GC.ENTRY))
    report = RunReport.build_from_plan(plan, RunMode.PREVIEW)
    assert report.category_notes == plan.category_notes
    lines = list(render_text_summary(report))
    assert any(l.startswith("  [INFO] entry: dispatched as affixes + stems")
               for l in lines)
    assert not any("NOT DISPATCHED" in l for l in lines)
    # ENTRY is no longer a selected-but-empty category in the report.
    assert GC.ENTRY not in report.empty_categories
