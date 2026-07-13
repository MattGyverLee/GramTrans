"""US5 (Feature 026, T033) — text-markup tagging comes across.

Covers `Lib/texts.py` US5 additions: the text-markup tag possibility list and
the per-segment tag references are reproduced — tags absent from the target are
created via the 024 resolver (CREATE decision), present tags are LINKed, and an
unresolvable tag (target list absent) is reported, never silently dropped
(FR-017, R6).

Offline: exercised with the shared `_fakes_texts` doubles (no flexicon host).
The exact live ITextTag write path (StText.TagsOC + ITextTagFactory) is a
[PROBE] deferred to T039; here the duck-typed `FakeTextTagOps` stands in.
"""
from __future__ import annotations

from gramtrans.Lib import texts
from gramtrans.Lib.models import (
    ReferenceAction,
    Selection,
    GrammarCategory,
)
from _fakes_texts import (
    FakeWS,
    FakePossibility,
    FakePossibilityList,
    FakeLangProject,
    FakeText,
    FakeTextTag,
    FakeParagraph,
    FakeSegment,
    FakeProject,
    FakeCtx,
)


WS_VERN = FakeWS("vern", 1, is_vernacular=True)
WS_EN = FakeWS("en", 2)


def _source_with_tag(tag_poss):
    seg = FakeSegment(
        guid="seg-1", baseline=" abc def .",
        free={2: "the dog runs"}, literal={},
        wordforms=(), analyses_rs=(),
    )
    para = FakeParagraph(guid="para-1", text_by_handle={1: "abc def."}, segments=(seg,))
    tag = FakeTextTag(guid="tt-1", tag_ra=tag_poss, begin_seg=seg, end_seg=seg)
    text = FakeText(guid="txt-1", name="Story One", paragraphs=(para,), tags=(tag,))
    return FakeProject(ws_list=[WS_VERN, WS_EN], texts=[text])


def _target(tag_items=(), tag_list_present=True):
    tag_list = FakePossibilityList(tag_items) if tag_list_present else None
    lp = FakeLangProject(tag_list=tag_list)
    return FakeProject(ws_list=[WS_VERN, WS_EN], texts=(), lang_project=lp)


def _selection():
    return Selection(categories={GrammarCategory.TEXTS: True},
                     text_picks=frozenset({"txt-1"}))


def _seg_plan(plans):
    return plans[0].paragraphs[0].segments[0]


# ---------------------------------------------------------------------------
# Tag possibility resolution into SegmentPlan.tag_decisions (T034, FR-017)
# ---------------------------------------------------------------------------

def test_absent_tag_yields_create_decision():
    poss = FakePossibility(guid="tag-poss-1", name="Topic")
    source = _source_with_tag(poss)
    target = _target(tag_items=())  # empty tag list -> CREATE
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []

    plans = texts.plan_texts(_selection(), source, target, ctx, {}, dropped)
    decisions = _seg_plan(plans).tag_decisions
    assert len(decisions) == 1
    assert decisions[0].action == ReferenceAction.CREATE


def test_present_tag_links_not_recreated():
    poss = FakePossibility(guid="tag-poss-1", name="Topic")
    tgt_poss = FakePossibility(guid="tag-poss-1", name="Topic")
    source = _source_with_tag(poss)
    target = _target(tag_items=(tgt_poss,))
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []

    plans = texts.plan_texts(_selection(), source, target, ctx, {}, dropped)
    decisions = _seg_plan(plans).tag_decisions
    assert len(decisions) == 1
    assert decisions[0].action == ReferenceAction.LINK


def test_unresolvable_tag_reported():
    poss = FakePossibility(guid="tag-poss-1", name="Topic")
    source = _source_with_tag(poss)
    target = _target(tag_list_present=False)  # no TextMarkupTagsOA -> REPORT_DROPPED
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []

    plans = texts.plan_texts(_selection(), source, target, ctx, {}, dropped)
    decisions = _seg_plan(plans).tag_decisions
    assert len(decisions) == 1
    assert decisions[0].action == ReferenceAction.REPORT_DROPPED
    tag_drops = [d for d in dropped if d.field_name == "TagRA"]
    assert tag_drops, "an unresolvable tag must be reported (never silently dropped)"


def test_plan_does_not_create_target_tags():
    poss = FakePossibility(guid="tag-poss-1", name="Topic")
    source = _source_with_tag(poss)
    target = _target(tag_items=())
    ctx = FakeCtx(source_handle=source, ws_map={})
    texts.plan_texts(_selection(), source, target, ctx, {}, [])
    # No text-markup tag was created on the target during Preview (Principle III).
    assert target.TextTags.created == []


# ---------------------------------------------------------------------------
# apply_texts — per-segment tag reference reproduced (T035, FR-017)
# ---------------------------------------------------------------------------

class _Sink:
    def __init__(self):
        self.msgs = []

    def Info(self, m):
        self.msgs.append(m)


def test_apply_creates_per_segment_tag_reference():
    poss = FakePossibility(guid="tag-poss-1", name="Topic")
    tgt_poss = FakePossibility(guid="tag-poss-1", name="Topic")
    source = _source_with_tag(poss)
    target = _target(tag_items=(tgt_poss,))
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []
    plans = texts.plan_texts(_selection(), source, target, ctx, {}, dropped)

    texts.apply_texts(plans, source, target, ctx, tag=object(),
                      report_sink=_Sink(), resolver_cache={}, dropped=dropped)

    # A per-segment text-markup tag reference was created, wired to the linked
    # (not re-created) target possibility.
    assert len(target.TextTags.created) == 1
    created = target.TextTags.created[0]
    assert created.TagRA is tgt_poss
