"""Issue #146 cycle 2 -- a Preview-planned LINK (target_item None) must never
be applied silently, and wordforms (which never creates a POS) must not leave
Preview PlannedCreate placeholders behind."""
from __future__ import annotations

import logging
from types import SimpleNamespace

import test_issue146_preview_cache_picture_dedup as t146

from gramtrans.Lib import categories, references, texts, wordforms
from gramtrans.Lib.models import ReferenceAction, ReferenceDecision


def _setup(monkeypatch):
    fx = t146._thes_fixture()
    spec = t146._spec(fx)
    monkeypatch.setattr(wordforms, "_pos_spec", lambda: spec)
    return fx, spec


def _analysis(guid, pos):
    return SimpleNamespace(Guid=guid, guid=guid, CategoryRA=pos)


def test_decide_reference_sets_planned_on_placeholder_link():
    fx = t146._thes_fixture()
    spec = t146._spec(fx)
    cache = t146._planning()
    d1 = references.decide_reference(fx["C"], fx["target"], spec, cache)
    d2 = references.decide_reference(fx["C"], fx["target"], spec, cache)
    assert d1.planned is False
    assert d2.action == ReferenceAction.LINK and d2.planned is True
    rec = categories._reference_decision_record("LexSense", "o", spec, d2)
    assert rec.planned is True
    # Move's unmarked cache with a real object is not "planned".
    real = references.decide_reference(fx["C"], fx["target"], spec, {"c": object()})
    assert real.action == ReferenceAction.LINK and real.planned is False


def test_two_analyses_same_absent_pos_give_two_drops_and_clean_cache(monkeypatch):
    fx, _ = _setup(monkeypatch)
    cache = t146._planning()
    dropped: list = []
    decisions = [wordforms.resolve_or_report_category(
        _analysis("a%d" % i, fx["C"]), fx["target"], cache, dropped) for i in (1, 2)]
    assert [d.action for d in decisions] == [ReferenceAction.REPORT_DROPPED] * 2
    assert len(dropped) == 2
    assert not any(references.is_planned_create(v) for v in cache.values())


def test_planned_link_from_foreign_leg_is_downgraded_to_drop(monkeypatch):
    """Another consumer already planned this POS: the resulting planned LINK
    must still be a drop for wordforms (which never links to a planned item)."""
    fx, spec = _setup(monkeypatch)
    cache = t146._planning()
    references.decide_reference(fx["C"], fx["target"], spec, cache)  # foreign plan
    dropped: list = []
    d = wordforms.resolve_or_report_category(
        _analysis("a1", fx["C"]), fx["target"], cache, dropped)
    assert d.action == ReferenceAction.REPORT_DROPPED and len(dropped) == 1
    # The foreign plan's placeholders are left alone.
    assert references.is_planned_create(cache["c"])


def test_apply_category_guard_emits_drop_and_warns(monkeypatch, caplog):
    fx, _ = _setup(monkeypatch)
    plan = SimpleNamespace(source_guid="a1", category_decision=ReferenceDecision(
        action=ReferenceAction.LINK, target_item=None, source_item=fx["C"], planned=True))
    dropped: list = []
    with caplog.at_level(logging.WARNING):
        wordforms._apply_category(plan, fx["target"], object(), object(), {}, None, {}, dropped)
    assert len(dropped) == 1 and dropped[0].field_name == "CategoryRA"
    assert any("no target_item" in r.getMessage() for r in caplog.records)


def test_apply_reference_link_without_target_warns(caplog):
    fx = t146._thes_fixture()
    spec = t146._spec(fx)
    d = ReferenceDecision(action=ReferenceAction.LINK, target_item=None,
                          source_item=fx["C"], planned=True)
    with caplog.at_level(logging.WARNING):
        out = references.apply_reference(d, fx["target"], object(), spec, {}, None)
    assert out is None
    assert any("no target_item" in r.getMessage() for r in caplog.records)


def test_raising_rebind_in_texts_emits_drop(monkeypatch):
    fx = t146._thes_fixture()
    spec = t146._spec(fx)
    monkeypatch.setattr(texts, "_genre_spec", lambda: spec)
    planned = ReferenceDecision(action=ReferenceAction.LINK, target_item=None,
                                source_item=fx["C"], planned=True)

    def boom(*a, **k):
        raise RuntimeError("rebind failed")

    monkeypatch.setattr(texts._references, "rebind_planned_link", boom)
    applied = []
    monkeypatch.setattr(texts._references, "apply_reference",
                        lambda *a, **k: applied.append(a))
    dropped: list = []
    plan = SimpleNamespace(genre_decisions=(planned,), source_guid="t1")
    texts._apply_genres(plan, fx["target"], "text", {}, None, None, None, dropped)
    assert len(dropped) == 1 and applied == []
