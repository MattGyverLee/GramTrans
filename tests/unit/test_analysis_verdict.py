"""US2 (Feature 026, T016) — verdict preserved + human-agent provisioning.

approve/deny verdict is reproduced on the target analysis (FR-007); the human
agent is provisioned once per run and reused, never duplicated (FR-009).
"""
from __future__ import annotations

from gramtrans.Lib import wordforms
from _fakes_texts import (
    FakeWS,
    FakeEvaluation,
    FakeAnalysis,
    FakeWordform,
    FakeSegment,
    FakeProject,
    FakeLangProject,
    FakeAgent,
    FakeCtx,
)

WS_VERN = FakeWS("vern", 1, is_vernacular=True)
WS_EN = FakeWS("en", 2)


def _plans_for(analyses, source, target):
    wf = FakeWordform(guid="wf-1", form_by_handle={2: "dogs"}, analyses=analyses)
    seg = FakeSegment(guid="seg-1", wordforms=(wf,))
    ctx = FakeCtx(source_handle=source, ws_map={})
    return wordforms.plan_analyses(seg, source, target, ctx, {}, []), ctx


def test_approve_and_deny_verdicts_reproduced():
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    target = FakeProject(ws_list=[WS_VERN, WS_EN], lang_project=FakeLangProject())
    analyses = [
        FakeAnalysis("an-approved", human_eval=FakeEvaluation(approves=True)),
        FakeAnalysis("an-denied", human_eval=FakeEvaluation(approves=False)),
    ]
    plans, ctx = _plans_for(analyses, source, target)

    # Provision the agent (as apply_texts does before the loop).
    decision = wordforms.plan_agent(target, ctx)
    wordforms.apply_agent(decision, target, ctx)

    dropped = []
    wordforms.apply_analyses(plans, source, target, ctx, tag=object(),
                             resolver_cache={}, dropped=dropped)

    created = target.WfiAnalyses.created
    assert len(created) == 2
    approved = [a for a in created if a.approved is True]
    denied = [a for a in created if a.approved is False]
    assert len(approved) == 1
    assert len(denied) == 1


def test_agent_provisioned_once_when_absent():
    target = FakeProject(ws_list=[WS_VERN, WS_EN])  # no human agents
    ctx = FakeCtx(ws_map={})
    d1 = wordforms.plan_agent(target, ctx)
    assert d1.created is True
    a1 = wordforms.apply_agent(d1, target, ctx)
    a2 = wordforms.apply_agent(d1, target, ctx)  # second call reuses cache
    assert a1 is a2
    assert len(target.Agents.created) == 1


def test_existing_human_agent_reused_not_created():
    existing = FakeAgent("Linguist", is_human=True)
    target = FakeProject(ws_list=[WS_VERN, WS_EN], agents=[existing])
    ctx = FakeCtx(ws_map={})
    decision = wordforms.plan_agent(target, ctx)
    assert decision.created is False
    agent = wordforms.apply_agent(decision, target, ctx)
    assert agent is existing
    assert target.Agents.created == []


def test_agent_reused_across_two_analyses():
    source = FakeProject(ws_list=[WS_VERN, WS_EN])
    target = FakeProject(ws_list=[WS_VERN, WS_EN], lang_project=FakeLangProject())
    analyses = [
        FakeAnalysis("a1", human_eval=FakeEvaluation(approves=True)),
        FakeAnalysis("a2", human_eval=FakeEvaluation(approves=True)),
    ]
    plans, ctx = _plans_for(analyses, source, target)
    wordforms.apply_agent(wordforms.plan_agent(target, ctx), target, ctx)
    wordforms.apply_analyses(plans, source, target, ctx, tag=object(),
                             resolver_cache={}, dropped=[])
    # Still exactly one agent for two evaluations.
    assert len(target.Agents.created) == 1
