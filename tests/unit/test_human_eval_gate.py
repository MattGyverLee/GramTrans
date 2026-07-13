"""US2 (Feature 026, T015) — human-evaluation gate (FR-006, SC-001).

An analysis is copy-eligible IFF it carries a non-null human evaluation.
Parser-only and un-evaluated analyses are excluded (no plan, no write) — and
countable. Exercised with the shared `_fakes_texts` doubles.
"""
from __future__ import annotations

from gramtrans.Lib import wordforms
from gramtrans.Lib.models import EvalVerdict
from _fakes_texts import (
    FakeWS,
    FakeEvaluation,
    FakeAnalysis,
    FakeWordform,
    FakeSegment,
    FakeProject,
    FakeLangProject,
    FakeCtx,
)

WS_VERN = FakeWS("vern", 1, is_vernacular=True)
WS_EN = FakeWS("en", 2)


def _source_and_target(analyses):
    wf = FakeWordform(guid="wf-1", form_by_handle={1: "dogs"}, analyses=analyses)
    seg = FakeSegment(guid="seg-1", wordforms=(wf,))
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    target = FakeProject(ws_list=[WS_VERN, WS_EN], lang_project=FakeLangProject())
    return seg, source, target


def test_only_human_evaluated_analyses_kept():
    analyses = [
        FakeAnalysis("an-approved", human_eval=FakeEvaluation(approves=True)),
        FakeAnalysis("an-denied", human_eval=FakeEvaluation(approves=False)),
        FakeAnalysis("an-parser", human_eval=None),      # parser-only
        FakeAnalysis("an-uneval", human_eval=None),       # un-evaluated
    ]
    seg, source, target = _source_and_target(analyses)
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []

    plans = wordforms.plan_analyses(seg, source, target, ctx, {}, dropped)

    kept = {p.source_guid for p in plans}
    assert kept == {"an-approved", "an-denied"}, kept
    # SC-001: exactly two human analyses; zero parser-only/un-evaluated.
    assert len(plans) == 2


def test_zero_human_analyses_yields_empty_plan_no_error():
    analyses = [FakeAnalysis("an-parser", human_eval=None)]
    seg, source, target = _source_and_target(analyses)
    ctx = FakeCtx(source_handle=source, ws_map={})
    plans = wordforms.plan_analyses(seg, source, target, ctx, {}, [])
    assert plans == []


def test_verdicts_read_from_evaluation():
    analyses = [
        FakeAnalysis("an-approved", human_eval=FakeEvaluation(approves=True)),
        FakeAnalysis("an-denied", human_eval=FakeEvaluation(approves=False)),
    ]
    seg, source, target = _source_and_target(analyses)
    ctx = FakeCtx(source_handle=source, ws_map={})
    plans = wordforms.plan_analyses(seg, source, target, ctx, {}, [])
    by_guid = {p.source_guid: p.verdict for p in plans}
    assert by_guid["an-approved"] == EvalVerdict.HUMAN_APPROVED
    assert by_guid["an-denied"] == EvalVerdict.HUMAN_DENIED
