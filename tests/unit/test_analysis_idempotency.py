"""SC-005 — a re-Move is a no-op at the analysis/gloss/morph-bundle level.

`Wordforms.Find` deduped wordforms already; analyses/glosses/morph bundles did
not, so a second Move against an already-populated target grew WfiAnalyses and
WfiGlosses (live proof 2026-07-15: 179→329 analyses, 282→522 glosses). The fix
dedupes an analysis by:
  - its source GUID within a run (the same analysis referenced from several
    segments is created once), and
  - its STRUCTURE (morph-bundle forms + gloss forms) across runs (the target
    carries no source GUID, so structural identity is the only durable key).

These tests drive `plan_analyses` + `apply_analyses` twice against the SAME
target with fresh run contexts and assert no duplication — while a genuinely
distinct analysis is still created (the dedup is not over-broad).
"""
from __future__ import annotations

from gramtrans.Lib import wordforms
from _fakes_texts import (
    FakeWS,
    FakeEvaluation,
    FakeAnalysis,
    FakeGloss,
    FakeMorphBundle,
    FakeWordform,
    FakeSegment,
    FakeProject,
    FakeCtx,
)

WS_VERN = FakeWS("vern", 1, is_vernacular=True)
WS_EN = FakeWS("en", 2)


def _source_with(analyses):
    """A source project whose one segment holds `analyses` on one wordform."""
    return FakeProject(ws_list=[WS_VERN, WS_EN])


def _segment(analyses, wf_form="dogs"):
    wf = FakeWordform(guid="wf-1", form_by_handle={1: wf_form},
                      analyses=list(analyses), spelling="CORRECT")
    return FakeSegment(guid="seg-1", wordforms=(wf,))


def _move(segment, source, target, run_id):
    """One full Move run (fresh ctx) of a single segment's analyses."""
    ctx = FakeCtx(source_handle=source, ws_map={})
    ctx.run_id = run_id
    dropped = []
    plans = wordforms.plan_analyses(segment, source, target, ctx, {}, dropped)
    wordforms.apply_agent(wordforms.plan_agent(target, ctx), target, ctx)
    wordforms.apply_analyses(plans, source, target, ctx, tag=object(),
                             resolver_cache={}, dropped=dropped)
    return plans, ctx, dropped


def _one_analysis():
    """A human-approved analysis: 1 morph bundle (form) + 1 human gloss."""
    mb = FakeMorphBundle(guid="mb-1", form={1: "dog"})
    gloss = FakeGloss("g-1", forms={2: "dog.n"},
                      human_eval=FakeEvaluation(approves=True))
    return FakeAnalysis("an-1", human_eval=FakeEvaluation(approves=True),
                        morph_bundles=[mb], glosses=[gloss])


# ---------------------------------------------------------------------------
# SC-005 — re-Move is a no-op
# ---------------------------------------------------------------------------

def test_reapply_analyses_is_idempotent():
    source = _source_with(None)
    target = FakeProject(ws_list=[WS_VERN, WS_EN])

    # Run 1 — creates exactly one analysis, one morph bundle, one gloss.
    _move(_segment([_one_analysis()]), source, target, "GT-20260715-000001")
    assert len(target.WfiAnalyses.created) == 1
    assert len(target.WfiMorphBundles.created) == 1
    assert len(target.WfiGlosses.created) == 1
    assert len(target.Wordforms._wf) == 1

    # Run 2 — same source content, SAME target, fresh run context. A re-Move
    # must add nothing (SC-005).
    _move(_segment([_one_analysis()]), source, target, "GT-20260715-000002")
    assert len(target.WfiAnalyses.created) == 1, \
        "re-Move duplicated the analysis (SC-005)"
    assert len(target.WfiMorphBundles.created) == 1, \
        "re-Move duplicated the morph bundle (SC-005)"
    assert len(target.WfiGlosses.created) == 1, \
        "re-Move duplicated the gloss (SC-005)"
    assert len(target.Wordforms._wf) == 1


def test_same_analysis_across_two_segments_created_once_within_run():
    # The same source analysis GUID referenced from two segments is reproduced
    # once (within-run source-GUID fast-path).
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    target = FakeProject(ws_list=[WS_VERN, WS_EN])
    an = _one_analysis()
    seg_a = _segment([an])
    seg_b = _segment([an])
    ctx = FakeCtx(source_handle=source, ws_map={})
    ctx.run_id = "GT-20260715-000003"
    dropped = []
    plans_a = wordforms.plan_analyses(seg_a, source, target, ctx, {}, dropped)
    plans_b = wordforms.plan_analyses(seg_b, source, target, ctx, {}, dropped)
    wordforms.apply_agent(wordforms.plan_agent(target, ctx), target, ctx)
    wordforms.apply_analyses(plans_a, source, target, ctx, object(), {}, dropped)
    wordforms.apply_analyses(plans_b, source, target, ctx, object(), {}, dropped)
    assert len(target.WfiAnalyses.created) == 1


def test_distinct_analysis_is_still_created_on_reapply():
    # Idempotency must not suppress a genuinely NEW analysis on a re-Move.
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    target = FakeProject(ws_list=[WS_VERN, WS_EN])

    _move(_segment([_one_analysis()]), source, target, "GT-20260715-000004")
    assert len(target.WfiAnalyses.created) == 1

    # Run 2: same wordform, but a structurally-different analysis (different
    # gloss + morpheme) — must be created (net 2 analyses on the wordform).
    mb2 = FakeMorphBundle(guid="mb-2", form={1: "dog+PL"})
    gloss2 = FakeGloss("g-2", forms={2: "dog.pl"},
                       human_eval=FakeEvaluation(approves=True))
    an2 = FakeAnalysis("an-2", human_eval=FakeEvaluation(approves=True),
                       morph_bundles=[mb2], glosses=[gloss2])
    _move(_segment([_one_analysis(), an2]), source, target, "GT-20260715-000005")

    # The re-run's duplicate `an-1` is skipped; the new `an-2` is created.
    assert len(target.WfiAnalyses.created) == 2
    tgt_wf = target.Wordforms._wf[0]
    assert len(tgt_wf.analyses) == 2
