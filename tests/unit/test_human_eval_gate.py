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


# ---------------------------------------------------------------------------
# 2026-07-15 live-proof regression (verification-log.md): the FR-006 gate MUST
# read a LIVE IWfiAnalysis via ApprovalStatusIcon, not only the fake
# GetHumanEvaluation() / human_evaluation hooks. Live proof caught that
# `WfiAnalyses.GetHumanEvaluation` is ABSENT on the live flexicon surface, so
# every real analysis was gated out as parser-only and 219 human-approved
# analyses were silently dropped. These fakes mimic the live shape (only
# ApprovalStatusIcon, no eval hooks) -- the exact blind spot the offline fakes
# could not previously express.
# ---------------------------------------------------------------------------

class _LiveShapedAnalysis:
    """Live `IWfiAnalysis`-shaped double: exposes ONLY `ApprovalStatusIcon`
    (1 approved / 2 disapproved / 0 no-opinion) -- NO `GetHumanEvaluation()`
    method and NO `human_evaluation` attribute (both absent on real LCM)."""

    def __init__(self, guid, icon):
        self.Guid = guid
        self.guid = guid
        self.ApprovalStatusIcon = icon


class _SourceNoHumanEvalOps:
    """Source handle whose WfiAnalyses ops lack GetHumanEvaluation (like the
    live flexicon FLExProject), forcing the gate onto the live path."""

    WfiAnalyses = None
    Wordforms = None


def test_gate_reads_live_approval_status_icon():
    src = _SourceNoHumanEvalOps()
    approved = wordforms._human_evaluation(src, _LiveShapedAnalysis("a", 1))
    denied = wordforms._human_evaluation(src, _LiveShapedAnalysis("d", 2))
    parser = wordforms._human_evaluation(src, _LiveShapedAnalysis("p", 0))
    assert approved is not None
    assert wordforms._verdict_from_eval(approved) == EvalVerdict.HUMAN_APPROVED
    assert denied is not None
    assert wordforms._verdict_from_eval(denied) == EvalVerdict.HUMAN_DENIED
    assert parser is None  # icon 0 -> excluded parser-only (FR-008), not a loss


def test_gate_live_path_survives_source_without_wfianalyses_attr():
    class _Bare:
        pass
    ev = wordforms._human_evaluation(_Bare(), _LiveShapedAnalysis("a", 1))
    assert ev is not None
    assert wordforms._verdict_from_eval(ev) == EvalVerdict.HUMAN_APPROVED


# ---------------------------------------------------------------------------
# Layer-2 regression: real interlinear Segment.AnalysesRS tokens are mostly
# IWfiGloss (the chosen gloss), not bare IWfiAnalysis. The walk must normalize a
# gloss token to its owning analysis, dedupe an analysis reached via several
# gloss tokens, and skip bare-wordform / punctuation tokens.
# ---------------------------------------------------------------------------

class _GlossToken:
    """Offline stand-in for a live IWfiGloss segment token: carries only a
    pointer to its owning analysis (mirrors `gloss.Owner` -> IWfiAnalysis)."""

    def __init__(self, owning_analysis):
        self.owning_analysis = owning_analysis


class _NonAnalysisToken:
    """Offline stand-in for a bare IWfiWordform / IPunctuationForm token."""

    is_analysis = False


def test_gloss_tokens_reproduce_owning_analysis_deduped():
    an = FakeAnalysis("an-1", human_eval=FakeEvaluation(approves=True))
    # segment references the SAME analysis via two gloss tokens + a punctuation.
    wf = FakeWordform(guid="wf-1", form_by_handle={1: "dogs"},
                      analyses=[_GlossToken(an), _GlossToken(an), _NonAnalysisToken()])
    seg = FakeSegment(guid="seg-1", wordforms=(wf,))
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    target = FakeProject(ws_list=[WS_VERN, WS_EN], lang_project=FakeLangProject())
    ctx = FakeCtx(source_handle=source, ws_map={})

    plans = wordforms.plan_analyses(seg, source, target, ctx, {}, [])

    assert [p.source_guid for p in plans] == ["an-1"]  # deduped; punctuation skipped
    assert plans[0].verdict == EvalVerdict.HUMAN_APPROVED


def test_normalize_token_maps_gloss_and_skips_non_analysis():
    an = FakeAnalysis("an-x", human_eval=FakeEvaluation(approves=True))
    assert wordforms._normalize_token_to_analysis(_GlossToken(an)) is an
    assert wordforms._normalize_token_to_analysis(_NonAnalysisToken()) is None
    assert wordforms._normalize_token_to_analysis(an) is an  # bare analysis → itself
