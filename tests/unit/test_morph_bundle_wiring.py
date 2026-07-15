"""US2 (Feature 026, T017) — morph-bundle identity wiring (FR-010).

Resolvable morph-bundle references are wired to the target lexical objects by
source-GUID identity lookup (against the per-run copy-set / target GUID index).
The needs-review-approve, retained-deny, and report-context cases (FR-014/015/016)
are extended in US3 (T028); the never-silent unresolved-ref report is asserted
here too since the wiring emits it at plan time (Principle I).
"""
from __future__ import annotations

from gramtrans.Lib import wordforms
from gramtrans.Lib.models import EvalVerdict
from _fakes_texts import (
    FakeWS,
    FakeCmObject,
    FakeEvaluation,
    FakeAnalysis,
    FakeMorphBundle,
    FakeWordform,
    FakeSegment,
    FakeProject,
    FakeLangProject,
    FakeCtx,
)

WS_VERN = FakeWS("vern", 1, is_vernacular=True)
WS_EN = FakeWS("en", 2)


def _target():
    return FakeProject(ws_list=[WS_VERN, WS_EN], lang_project=FakeLangProject())


def test_resolvable_sense_ref_wired_by_guid_identity():
    target = _target()
    target_sense = object()
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    ctx = FakeCtx(source_handle=source, ws_map={},
                  copy_set={"sense-src": target_sense})

    bundle = FakeMorphBundle(guid="mb-1", form={2: "dog"},
                             sense=FakeCmObject("sense-src"))
    analysis = FakeAnalysis("an-1", morph_bundles=[bundle])
    dropped = []

    plans = wordforms.plan_morph_bundles(analysis, target, ctx, dropped)
    assert len(plans) == 1
    mbp = plans[0]
    assert mbp.sense_ref is not None
    assert mbp.sense_ref.resolved is True
    assert mbp.sense_ref.target_obj is target_sense
    assert mbp.unresolved_refs() == ()
    assert dropped == []  # fully resolvable -> nothing dropped

    # Apply wires the resolved sense onto a freshly-created target bundle.
    target_analysis = object()
    wordforms.apply_morph_bundles(target_analysis, plans, target, ctx, [])
    created = target.WfiMorphBundles.created
    assert len(created) == 1
    assert created[0].wired.get("sense") is target_sense
    assert created[0].set_form.get(2) == "dog"


def test_bundle_form_always_written_even_without_refs():
    target = _target()
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    ctx = FakeCtx(source_handle=source, ws_map={}, copy_set={})
    bundle = FakeMorphBundle(guid="mb-1", form={2: "dog"})  # no refs at all
    analysis = FakeAnalysis("an-1", morph_bundles=[bundle])

    plans = wordforms.plan_morph_bundles(analysis, target, ctx, [])
    wordforms.apply_morph_bundles(object(), plans, target, ctx, [])
    assert target.WfiMorphBundles.created[0].set_form.get(2) == "dog"


def test_unresolved_ref_reported_and_left_unlinked():
    # Sense referent absent from the copy-set + live target -> unresolved.
    target = _target()
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    ctx = FakeCtx(source_handle=source, ws_map={}, copy_set={})
    bundle = FakeMorphBundle(guid="mb-1", form={2: "dog"},
                             sense=FakeCmObject("sense-missing"))
    analysis = FakeAnalysis("an-1", morph_bundles=[bundle])
    dropped = []

    plans = wordforms.plan_morph_bundles(analysis, target, ctx, dropped)
    assert plans[0].sense_ref.resolved is False
    assert plans[0].unresolved_refs()  # non-empty
    # Never-silent: exactly one dropped record for the unresolved SenseRA.
    sense_drops = [d for d in dropped if d.field_name == "SenseRA"]
    assert len(sense_drops) == 1
    assert sense_drops[0].reason == "referent not copied to target"

    # Apply leaves the sense unset on the target bundle.
    wordforms.apply_morph_bundles(object(), plans, target, ctx, [])
    assert "sense" not in target.WfiMorphBundles.created[0].wired


def test_approve_with_unresolved_ref_downgrades_to_needs_review():
    # FR-014: an APPROVE that lost a morpheme referent -> needs_review.
    target = _target()
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    ctx = FakeCtx(source_handle=source, ws_map={}, copy_set={})
    bundle = FakeMorphBundle(guid="mb-1", form={2: "dog"},
                             sense=FakeCmObject("sense-missing"))
    wf = FakeWordform(guid="wf-1", form_by_handle={2: "dogs"}, analyses=[
        FakeAnalysis("an-approved", human_eval=FakeEvaluation(approves=True),
                     morph_bundles=[bundle]),
    ])
    seg = FakeSegment(guid="seg-1", wordforms=(wf,))
    plans = wordforms.plan_analyses(seg, source, target, ctx, {}, [])
    assert len(plans) == 1
    assert plans[0].verdict == EvalVerdict.HUMAN_APPROVED
    assert plans[0].needs_review is True


def test_deny_with_unresolved_ref_keeps_deny():
    # FR-015: a DENY is never downgraded, even with an unresolved morpheme.
    target = _target()
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    ctx = FakeCtx(source_handle=source, ws_map={}, copy_set={})
    bundle = FakeMorphBundle(guid="mb-1", form={2: "dog"},
                             sense=FakeCmObject("sense-missing"))
    wf = FakeWordform(guid="wf-1", form_by_handle={2: "dogs"}, analyses=[
        FakeAnalysis("an-denied", human_eval=FakeEvaluation(approves=False),
                     morph_bundles=[bundle]),
    ])
    seg = FakeSegment(guid="seg-1", wordforms=(wf,))
    dropped = []
    plans = wordforms.plan_analyses(seg, source, target, ctx, {}, dropped)
    assert plans[0].verdict == EvalVerdict.HUMAN_DENIED
    assert plans[0].needs_review is False
    # FR-015: no needs-review downgrade record for a retained deny …
    assert [d for d in dropped if d.field_name == "verdict"] == []
    # … but the unresolved morpheme is still reported (FR-016).
    assert [d for d in dropped if d.field_name == "SenseRA"]


def test_needs_review_downgrade_is_reported():
    # T028/FR-016: the approve→needs-review downgrade itself is a report record,
    # since the analysis is written no-verdict (T027) — the report is the only
    # signal the linguist gets to re-approve it once the morpheme lands.
    target = _target()
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    ctx = FakeCtx(source_handle=source, ws_map={}, copy_set={})
    bundle = FakeMorphBundle(guid="mb-1", form={2: "dog"},
                             sense=FakeCmObject("sense-missing"))
    wf = FakeWordform(guid="wf-1", form_by_handle={2: "dogs"}, analyses=[
        FakeAnalysis("an-approved", human_eval=FakeEvaluation(approves=True),
                     morph_bundles=[bundle]),
    ])
    seg = FakeSegment(guid="seg-1", wordforms=(wf,))
    dropped = []
    wordforms.plan_analyses(seg, source, target, ctx, {}, dropped)
    verdict_drops = [d for d in dropped if d.field_name == "verdict"]
    assert len(verdict_drops) == 1
    assert verdict_drops[0].owner_kind == "WfiAnalysis"
    assert verdict_drops[0].item_name == "needs-review"
    assert verdict_drops[0].owner_guid == "an-approved"


def test_unresolved_ref_report_carries_locate_context():
    # FR-016: the dropped record must carry enough context to finish it by hand —
    # the owning wordform form and the morpheme form.
    target = _target()
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    ctx = FakeCtx(source_handle=source, ws_map={}, copy_set={})
    bundle = FakeMorphBundle(guid="mb-1", form={2: "dog"},
                             sense=FakeCmObject("sense-missing"))
    wf = FakeWordform(guid="wf-1", form_by_handle={2: "dogs"}, analyses=[
        FakeAnalysis("an-approved", human_eval=FakeEvaluation(approves=True),
                     morph_bundles=[bundle]),
    ])
    seg = FakeSegment(guid="seg-1", wordforms=(wf,))
    dropped = []
    wordforms.plan_analyses(seg, source, target, ctx, {}, dropped)
    sense_drop = next(d for d in dropped if d.field_name == "SenseRA")
    assert sense_drop.owner_label == "dogs"   # owning wordform form
    assert sense_drop.item_name == "dog"      # morpheme form
    assert sense_drop.item_guid == "sense-missing"
