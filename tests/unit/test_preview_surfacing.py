"""P0-2 (feature 025 cycle-6 remediation): the reversal Add/Link plan and
the config-view Add/Overwrite/Skip list MUST reach the Preview surface
before Move ever writes (Principle III).

`Lib/preview.py.render_reversal_decisions` and `.render_config_view_records`
were fully implemented (US1 T019 / US3 T033) but had NO call site anywhere
in the codebase -- `Lib/ui/main_window.py._on_preview` built a `RunReport`
and called `self._stats.set_report(report)`, which surfaces `dropped_items`
only. This test proves a pure composition helper
(`Lib/preview.py.render_preview_extra_lines`) wires both render functions
onto a `RunPlan` and is what `_on_preview` now calls -- see that module's
own docstring/call site for the UI wiring half of this fix (not exercised
here without a live QApplication).
"""
from __future__ import annotations

from gramtrans.Lib.models import (
    ConfigViewAction,
    ConfigViewRecord,
    ReversalDecision,
    RunContext,
    RunPlan,
    Selection,
    WSMapping,
)
from gramtrans.Lib.preview import render_preview_extra_lines


def _ctx() -> RunContext:
    return RunContext(
        source_handle=object(),
        source_project_name="Src",
        source_project_path="/fake/src",
        target_handle=object(),
        target_project_name="Tgt",
        target_project_path="/fake/tgt",
        run_id="GT-20260712-100000",
        started_at="2026-07-12T10:00:00",
    )


def _plan(reversal_decisions=(), config_view_records=()) -> RunPlan:
    return RunPlan(
        context=_ctx(),
        selection=Selection(),
        ws_mapping=WSMapping(entries=()),
        reversal_decisions=reversal_decisions,
        config_view_records=config_view_records,
    )


def test_render_preview_extra_lines_empty_plan_yields_nothing():
    """An empty plan (no reversal decisions, no config-view records)
    contributes zero extra Preview lines -- clean no-op."""
    assert render_preview_extra_lines(_plan()) == ()


def test_render_preview_extra_lines_surfaces_reversal_add_and_config_view_dispositions():
    """The exact bug this test guards: before P0-2, NOTHING called
    `render_reversal_decisions`/`render_config_view_records`, so a plan
    carrying a real reversal Add decision and a real config-view
    Add/Overwrite/Skip list produced NO Preview-visible trace of either.
    `render_preview_extra_lines` must surface both."""
    decision = ReversalDecision(
        source_entry_guid="entry-guid-1",
        target_index_ref=None,  # None -> to-create -> "Add"
        target_ws_id="en",
        linked_sense_guids=("sense-guid-1",),
        reversal_form_alts={"en": "run"},
    )
    cv_add = ConfigViewRecord(
        kind="ReversalIndex",
        filename="en.fwdictconfig",
        src_path="/fake/src/ConfigurationSettings/ReversalIndex/en.fwdictconfig",
        tgt_path="/fake/tgt/ConfigurationSettings/ReversalIndex/en.fwdictconfig",
        action=ConfigViewAction.ADD,
        missing_refs=[],
    )
    cv_skip = ConfigViewRecord(
        kind="Dictionary",
        filename="Lexeme.fwdictconfig",
        src_path="/fake/src/ConfigurationSettings/Dictionary/Lexeme.fwdictconfig",
        tgt_path="/fake/tgt/ConfigurationSettings/Dictionary/Lexeme.fwdictconfig",
        action=ConfigViewAction.SKIP,
        missing_refs=[],
    )

    plan = _plan(
        reversal_decisions=(decision,),
        config_view_records=(cv_add, cv_skip),
    )

    lines = render_preview_extra_lines(plan)
    text = "\n".join(lines)

    # Reversal Add/Link plan (render_reversal_decisions).
    assert "Reversal index [en] (Add):" in text
    assert "Add entry 'run' -- links 1 sense(s)" in text

    # Config-view Add/Overwrite/Skip list (render_config_view_records).
    assert "Configuration views:" in text
    assert "ReversalIndex:" in text
    assert "Add 'en.fwdictconfig'" in text
    assert "Dictionary:" in text
    assert "Skip (already up to date) 'Lexeme.fwdictconfig'" in text


def test_render_preview_extra_lines_is_reversal_lines_then_config_view_lines():
    """Composition order: reversal decisions first, config-view records
    second (mirrors the order both sections are computed in `build_run_
    plan`)."""
    decision = ReversalDecision(
        source_entry_guid="entry-guid-1",
        target_index_ref=None,
        target_ws_id="en",
        linked_sense_guids=(),
        reversal_form_alts={"en": "run"},
    )
    cv = ConfigViewRecord(
        kind="Dictionary",
        filename="Lexeme.fwdictconfig",
        src_path="/fake/src/x",
        tgt_path="/fake/tgt/x",
        action=ConfigViewAction.ADD,
        missing_refs=[],
    )
    plan = _plan(reversal_decisions=(decision,), config_view_records=(cv,))
    lines = render_preview_extra_lines(plan)
    reversal_idx = next(i for i, l in enumerate(lines) if "Reversal index" in l)
    config_idx = next(i for i, l in enumerate(lines) if "Configuration views:" in l)
    assert reversal_idx < config_idx
