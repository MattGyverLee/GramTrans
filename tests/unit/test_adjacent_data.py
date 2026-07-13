"""US4 (Feature 026, T029) — adjacent human-curated data rides along.

Word-level glosses (under the same human-evaluation gate, FR-008), wordform
spelling status (FR-013), and analysis grammatical category (resolve-or-report,
FR-011) transfer with the analyses. Machine/parser-only glosses are excluded;
a category absent from the target POS list is left unset + reported, never
fabricated.
"""
from __future__ import annotations

from gramtrans.Lib import wordforms
from gramtrans.Lib.models import ReferenceAction
from _fakes_texts import (
    FakeWS,
    FakeEvaluation,
    FakeAnalysis,
    FakeGloss,
    FakeWordform,
    FakeSegment,
    FakeProject,
    FakeLangProject,
    FakePossibility,
    FakePossibilityList,
    FakeCtx,
)

WS_VERN = FakeWS("vern", 1, is_vernacular=True)
WS_EN = FakeWS("en", 2)


def _target(pos_items=()):
    lp = FakeLangProject(pos_list=FakePossibilityList(pos_items))
    return FakeProject(ws_list=[WS_VERN, WS_EN], lang_project=lp)


def _run(analyses, source, target):
    """Plan + apply one segment's analyses; return the ctx and dropped list."""
    wf = FakeWordform(guid="wf-1", form_by_handle={2: "dogs"},
                      analyses=analyses, spelling="CORRECT")
    seg = FakeSegment(guid="seg-1", wordforms=(wf,))
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []
    plans = wordforms.plan_analyses(seg, source, target, ctx, {}, dropped)
    wordforms.apply_agent(wordforms.plan_agent(target, ctx), target, ctx)
    wordforms.apply_analyses(plans, source, target, ctx, tag=object(),
                             resolver_cache={}, dropped=dropped)
    return plans, ctx, dropped


# ---------------------------------------------------------------------------
# FR-008 — word-level gloss human-evaluation gate
# ---------------------------------------------------------------------------

def test_human_gloss_reproduced_parser_gloss_excluded():
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    target = _target()
    human_gloss = FakeGloss("g-human", forms={2: "dog.n"},
                            human_eval=FakeEvaluation(approves=True))
    parser_gloss = FakeGloss("g-parser", forms={2: "dog.parser"}, human_eval=None)
    analysis = FakeAnalysis("an-1", human_eval=FakeEvaluation(approves=True),
                            glosses=[human_gloss, parser_gloss])

    plans, ctx, dropped = _run([analysis], source, target)

    # Plan keeps only the human-evaluated gloss (FR-008).
    assert len(plans) == 1
    kept = {g.source_guid for g in plans[0].glosses}
    assert kept == {"g-human"}, kept

    # Apply reproduces exactly the human gloss + its WS-gated form.
    created = target.WfiGlosses.created
    assert len(created) == 1
    assert created[0].set_form.get(2) == "dog.n"


def test_zero_human_glosses_reproduces_no_gloss():
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    target = _target()
    analysis = FakeAnalysis("an-1", human_eval=FakeEvaluation(approves=True),
                            glosses=[FakeGloss("g-parser", forms={2: "x"},
                                               human_eval=None)])
    plans, ctx, dropped = _run([analysis], source, target)
    assert plans[0].glosses == ()
    assert target.WfiGlosses.created == []


# ---------------------------------------------------------------------------
# FR-013 — wordform spelling status
# ---------------------------------------------------------------------------

def test_spelling_status_reproduced_onto_target_wordform():
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    target = _target()
    analysis = FakeAnalysis("an-1", human_eval=FakeEvaluation(approves=True))

    plans, ctx, dropped = _run([analysis], source, target)

    assert plans[0].spelling_status == "CORRECT"
    # The freshly-created target wordform carries the reproduced status.
    tgt_wf = target.Wordforms._wf[-1]
    assert tgt_wf.spelling == "CORRECT"


def test_absent_spelling_status_not_written():
    # Non-destructive: a None source spelling status writes nothing.
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    target = _target()
    wf = FakeWordform(guid="wf-1", form_by_handle={2: "dogs"},
                      analyses=[FakeAnalysis("an-1",
                                             human_eval=FakeEvaluation(approves=True))],
                      spelling=None)
    seg = FakeSegment(guid="seg-1", wordforms=(wf,))
    ctx = FakeCtx(source_handle=source, ws_map={})
    plans = wordforms.plan_analyses(seg, source, target, ctx, {}, [])
    wordforms.apply_agent(wordforms.plan_agent(target, ctx), target, ctx)
    wordforms.apply_analyses(plans, source, target, ctx, tag=object(),
                             resolver_cache={}, dropped=[])
    assert plans[0].spelling_status is None
    assert target.Wordforms._wf[-1].spelling is None


# ---------------------------------------------------------------------------
# FR-011 — category resolve-or-report (never fabricated)
# ---------------------------------------------------------------------------

def test_category_absent_left_unset_and_reported_never_created():
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    target = _target(pos_items=())  # empty target POS list
    pos = FakePossibility(guid="pos-noun", name="Noun")
    analysis = FakeAnalysis("an-1", human_eval=FakeEvaluation(approves=True),
                            category=pos)

    plans, ctx, dropped = _run([analysis], source, target)

    # Resolve-or-report: a CREATE is downgraded to REPORT_DROPPED (FR-011).
    decision = plans[0].category_decision
    assert decision is not None
    assert decision.action == ReferenceAction.REPORT_DROPPED
    cat_drops = [d for d in dropped if d.field_name == "CategoryRA"]
    assert len(cat_drops) == 1
    assert cat_drops[0].owner_kind == "WfiAnalysis"

    # Never fabricated: the target POS list stayed empty …
    assert len(target.Cache.LangProject.PartsOfSpeechOA.PossibilitiesOS) == 0
    # … and the created analysis has no category set.
    assert target.WfiAnalyses.created[0].CategoryRA is None


def test_category_present_resolved_and_set():
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    tgt_pos = FakePossibility(guid="pos-noun", name="Noun")
    target = _target(pos_items=(tgt_pos,))
    src_pos = FakePossibility(guid="pos-noun", name="Noun")
    analysis = FakeAnalysis("an-1", human_eval=FakeEvaluation(approves=True),
                            category=src_pos)

    plans, ctx, dropped = _run([analysis], source, target)

    decision = plans[0].category_decision
    # A matched POS resolves (LINK/UPDATE — source-preferring), never dropped.
    assert decision.action in (ReferenceAction.LINK, ReferenceAction.UPDATE)
    assert decision.action != ReferenceAction.REPORT_DROPPED
    assert [d for d in dropped if d.field_name == "CategoryRA"] == []
    # The resolved POS is wired onto the target analysis.
    assert target.WfiAnalyses.created[0].CategoryRA is tgt_pos
