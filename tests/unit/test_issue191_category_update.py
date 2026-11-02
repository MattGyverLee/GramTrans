"""Issue #191 -- a CategoryRA UPDATE decision applies the field update to the
target POS (not just the link), and a failed update is reported.

Live proof: tests/integration/test_issue191_category_update_live.py.
"""
from __future__ import annotations

from types import SimpleNamespace

from gramtrans.Lib import wordforms
from gramtrans.Lib.models import (
    DroppedItemRecord,
    ReferenceAction,
    ReferenceDecision,
)


class _Ops:
    def __init__(self):
        self.calls = []

    def SetCategory(self, analysis, category):
        self.calls.append((analysis, category))
        analysis.CategoryRA = category


def _plan(action=ReferenceAction.UPDATE):
    src = SimpleNamespace(guid="src-pos", Name="Noun")
    tgt = SimpleNamespace(guid="tgt-pos")
    decision = ReferenceDecision(action=action, target_item=tgt, source_item=src)
    return SimpleNamespace(category_decision=decision, source_guid="an-guid"), tgt


def _run(plan, monkeypatch, apply_fn, source="SRC"):
    monkeypatch.setattr(wordforms._references, "apply_reference", apply_fn)
    analysis = SimpleNamespace(CategoryRA=None)
    ops, dropped = _Ops(), []
    wordforms._apply_category(plan, "TGT", analysis, ops, {}, None, {"a": "b"},
                              dropped, source=source)
    return analysis, ops, dropped


def test_update_applies_field_update_then_links(monkeypatch):
    plan, tgt = _plan()
    seen = []

    def fake_apply(decision, target, owner, spec, cache, tag, **kw):
        seen.append((decision, target, owner, spec.field_name, kw))
        return decision.target_item

    analysis, ops, dropped = _run(plan, monkeypatch, fake_apply)
    assert len(seen) == 1
    decision, target, owner, field, kw = seen[0]
    assert decision.action == ReferenceAction.UPDATE
    assert target == "TGT" and owner is None and field == "CategoryRA"
    assert kw["source"] == "SRC" and kw["ws_map"] == {"a": "b"}
    assert analysis.CategoryRA is tgt and dropped == []


def test_link_does_not_invoke_update_path(monkeypatch):
    plan, tgt = _plan(ReferenceAction.LINK)

    def boom(*a, **k):
        raise AssertionError("apply_reference must not run for LINK")

    analysis, _, dropped = _run(plan, monkeypatch, boom)
    assert analysis.CategoryRA is tgt and dropped == []


def test_update_failure_is_reported_and_link_still_made(monkeypatch):
    plan, tgt = _plan()

    def fail(*a, **k):
        raise RuntimeError("merge exploded")

    analysis, _, dropped = _run(plan, monkeypatch, fail)
    assert analysis.CategoryRA is tgt
    assert len(dropped) == 1
    d = dropped[0]
    assert isinstance(d, DroppedItemRecord)
    assert (d.owner_kind, d.owner_guid, d.field_name) == (
        "WfiAnalysis", "an-guid", "CategoryRA")
    assert d.reason == wordforms.CATEGORY_UPDATE_FAILED_REASON
    assert d.item_guid == "src-pos"
