"""US2 (Feature 026, T018) — segment AnalysesRS alignment (FR-012, SC-006).

The target segment's `AnalysesRS` is reproduced in source token order, with
ANALYSIS / WORDFORM / PUNCTUATION slots classified. Copied analyses attach to
the correct baseline token; punctuation / bare-wordform slots keep their
position; no token silently disappears.
"""
from __future__ import annotations

from gramtrans.Lib import wordforms
from gramtrans.Lib.models import AlignmentTokenKind
from _fakes_texts import (
    FakeWS,
    FakeAnalysis,
    FakeWordform,
    FakeSegment,
    FakeProject,
    FakeCtx,
)

WS_VERN = FakeWS("vern", 1, is_vernacular=True)


class FakePunctuation:
    def __init__(self, guid):
        self.guid = guid
        self.Guid = guid
        self.ClassName = "PunctuationForm"


def _seg_with_tokens(tokens):
    seg = FakeSegment(guid="seg-1")
    seg.analyses_rs = list(tokens)
    return seg


def test_plan_alignment_preserves_order_and_kinds():
    analysis = FakeAnalysis("an-1")            # ClassName WfiAnalysis
    wf = FakeWordform("wf-1")                  # ClassName WfiWordform
    punct = FakePunctuation("pn-1")
    seg = _seg_with_tokens([analysis, punct, wf])
    source = FakeProject(ws_list=[WS_VERN])
    ctx = FakeCtx(source_handle=source)

    tokens = wordforms.plan_alignment(seg, ctx, [])
    assert [t.kind for t in tokens] == [
        AlignmentTokenKind.ANALYSIS,
        AlignmentTokenKind.PUNCTUATION,
        AlignmentTokenKind.WORDFORM,
    ]
    assert [t.source_guid for t in tokens] == ["an-1", "pn-1", "wf-1"]


def test_apply_alignment_rebuilds_analyses_rs_in_source_order():
    analysis = FakeAnalysis("an-1")
    wf = FakeWordform("wf-1")
    punct = FakePunctuation("pn-1")
    seg = _seg_with_tokens([analysis, punct, wf])
    source = FakeProject(ws_list=[WS_VERN])
    ctx = FakeCtx(source_handle=source)
    tokens = wordforms.plan_alignment(seg, ctx, [])

    # Source->target maps as apply_analyses would have populated them.
    tgt_analysis = object()
    tgt_wf = object()
    ctx._wf_analysis_map = {"an-1": tgt_analysis}
    ctx._wf_wordform_map = {"wf-1": tgt_wf}

    target_seg = FakeSegment(guid="tgt-seg")
    wordforms.apply_alignment(target_seg, tokens, ctx, [])

    # Resolved analysis + wordform appended in source order; punctuation slot
    # (no target referent) does not break the order.
    assert target_seg.AnalysesRS.items == [tgt_analysis, tgt_wf]


def test_apply_alignment_non_destructive_on_rerun():
    analysis = FakeAnalysis("an-1")
    seg = _seg_with_tokens([analysis])
    source = FakeProject(ws_list=[WS_VERN])
    ctx = FakeCtx(source_handle=source)
    tokens = wordforms.plan_alignment(seg, ctx, [])
    ctx._wf_analysis_map = {"an-1": object()}

    target_seg = FakeSegment(guid="tgt-seg")
    target_seg.AnalysesRS.items.append("existing")  # already aligned
    wordforms.apply_alignment(target_seg, tokens, ctx, [])
    # Non-destructive: existing alignment untouched, nothing appended.
    assert target_seg.AnalysesRS.items == ["existing"]


class FakeGlossToken:
    """A segment AnalysesRS token that is a gloss (ClassName WfiGloss) whose
    chosen content is its owning analysis. 2026-07-15 live-proof shape: real
    interlinear segments reference gloss tokens far more than bare analyses."""

    def __init__(self, guid, owning_analysis):
        self.guid = guid
        self.Guid = guid
        self.ClassName = "WfiGloss"
        self.owning_analysis = owning_analysis


def test_gloss_token_alignment_keyed_by_owning_analysis_and_wires():
    an = FakeAnalysis("an-1")
    seg = _seg_with_tokens([FakeGlossToken("gloss-9", an)])
    source = FakeProject(ws_list=[WS_VERN])
    ctx = FakeCtx(source_handle=source)

    tokens = wordforms.plan_alignment(seg, ctx, [])
    # Gloss token classified ANALYSIS, keyed by the OWNING analysis guid (an-1),
    # NOT the gloss token guid (gloss-9) -- so it matches _wf_analysis_map.
    assert tokens[0].kind == AlignmentTokenKind.ANALYSIS
    assert tokens[0].source_guid == "an-1"

    tgt_analysis = object()
    ctx._wf_analysis_map = {"an-1": tgt_analysis}
    target_seg = FakeSegment(guid="tgt-seg")
    dropped = []
    wordforms.apply_alignment(target_seg, tokens, ctx, dropped)
    # Wired (was dropped as "no referent" before the fix).
    assert target_seg.AnalysesRS.items == [tgt_analysis]
    assert dropped == []


def test_missing_target_analysis_reported_not_silent():
    analysis = FakeAnalysis("an-1")
    seg = _seg_with_tokens([analysis])
    source = FakeProject(ws_list=[WS_VERN])
    ctx = FakeCtx(source_handle=source)
    tokens = wordforms.plan_alignment(seg, ctx, [])
    # No map entry for an-1 -> unresolved analysis token.
    target_seg = FakeSegment(guid="tgt-seg")
    dropped = []
    wordforms.apply_alignment(target_seg, tokens, ctx, dropped)
    assert any(d.field_name == "AnalysesRS" for d in dropped)
    assert target_seg.AnalysesRS.items == []
