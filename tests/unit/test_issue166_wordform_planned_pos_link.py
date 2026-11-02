"""Issue #166 -- a wordform analysis whose POS this run creates plans a LINK
(rebound at Move), not a drop."""
from __future__ import annotations

from types import SimpleNamespace

import test_issue146_preview_cache_picture_dedup as t146

from gramtrans.Lib import references, wordforms
from gramtrans.Lib.models import ReferenceAction


def _setup(monkeypatch):
    fx = t146._thes_fixture()
    spec = t146._spec(fx)
    monkeypatch.setattr(wordforms, "_pos_spec", lambda: spec)
    return fx, spec


def _analysis(pos):
    return SimpleNamespace(Guid="a1", guid="a1", CategoryRA=pos)


def test_pos_created_in_run_plans_planned_link_not_drop(monkeypatch):
    fx, _ = _setup(monkeypatch)
    cache = t146._planning()
    dropped: list = []
    d = wordforms.resolve_or_report_category(
        _analysis(fx["C"]), fx["target"], cache, dropped,
        planned_pos_guids={"c"})
    assert d.action == ReferenceAction.LINK and d.planned is True
    assert d.target_item is None and dropped == []
    assert not any(references.is_planned_create(v) for v in cache.values())


def test_pos_not_created_in_run_still_dropped(monkeypatch):
    fx, _ = _setup(monkeypatch)
    dropped: list = []
    d = wordforms.resolve_or_report_category(
        _analysis(fx["C"]), fx["target"], t146._planning(), dropped,
        planned_pos_guids={"zzz"})
    assert d.action == ReferenceAction.REPORT_DROPPED and len(dropped) == 1


def test_apply_category_rebinds_planned_link(monkeypatch):
    fx, spec = _setup(monkeypatch)
    sentinel = object()
    monkeypatch.setattr(wordforms, "_as_part_of_speech", lambda x: x)
    monkeypatch.setattr(references, "rebind_planned_link",
                        lambda dec, *a, **k: SimpleNamespace(
                            action=ReferenceAction.LINK, target_item=sentinel,
                            source_item=dec.source_item, planned=False))
    plan = SimpleNamespace(source_guid="a1", category_decision=SimpleNamespace(
        action=ReferenceAction.LINK, target_item=None, source_item=fx["C"],
        planned=True))
    set_calls = []
    wa_ops = SimpleNamespace(SetCategory=lambda a, c: set_calls.append(c))
    dropped: list = []
    wordforms._apply_category(plan, fx["target"], object(), wa_ops, {}, None, {}, dropped)
    assert dropped == [] and set_calls == [sentinel]
