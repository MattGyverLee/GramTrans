"""Issue #132: LexReference.TargetsRS.Add must not fail silently (#111 audit)."""
from __future__ import annotations

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.models import DroppedItemRecord


class _FakeGuid:
    def __init__(self, guid):
        self.Guid = guid


class _RaisingTargetsRS:
    def __init__(self):
        self._items = []

    def Add(self, member):
        raise TypeError("binding gap")

    def __iter__(self):
        return iter(self._items)

    def Clear(self):
        self._items.clear()


class _FakeRel:
    def __init__(self):
        self.TargetsRS = _RaisingTargetsRS()


def test_try_add_lex_rel_targets_rs_member_records_drop():
    rel = _FakeRel()
    member = _FakeGuid("mem-1")
    dropped = []
    ok = categories._try_add_lex_rel_targets_rs_member(
        rel, member, "rel-1", dropped)
    assert ok is False
    assert len(dropped) == 1
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.field_name == "TargetsRS"
    assert rec.owner_guid == "rel-1"
    assert rec.item_guid == "mem-1"
    assert "TargetsRS.Add failed" in rec.reason


def test_rebuild_targets_rs_in_source_order_records_per_member_add_failure():
    rel = _FakeRel()
    members = [_FakeGuid("a"), _FakeGuid("b")]
    dropped = []
    categories._rebuild_targets_rs_in_source_order(
        rel, members, dropped=dropped, rel_guid="rel-2")
    assert len(dropped) == 2
    assert all(r.field_name == "TargetsRS" for r in dropped)
    assert {r.item_guid for r in dropped} == {"a", "b"}


def test_reproduce_lexical_relation_surfaces_targets_rs_add_failure(monkeypatch):
    member = _FakeGuid("e1")
    src_rel = type("R", (), {"Guid": "rel-guid", "TargetsRS": [member]})()
    target_type = type("T", (), {"MembersOC": []})()
    ctx = type("Ctx", (), {
        "target_handle": object(),
        "_copy_set": {"e1": member},
    })()
    reproduced = {}
    dropped = []

    class _Factory:
        def Create(self, parsed_guid, owner):
            return _FakeRel()

    def _eval(*_a, **_k):
        return ("rel-guid", target_type, [member])

    monkeypatch.setattr(categories, "_evaluate_lexical_relation", _eval)

    import gramtrans.Lib.owned as owned_mod

    monkeypatch.setattr(owned_mod, "_get_owned_factory", lambda *a, **k: _Factory())
    monkeypatch.setattr(owned_mod, "_guid_for_create", lambda g: g)

    out = categories.reproduce_lexical_relation(
        src_rel, ctx, "gt", reproduced, dropped)
    assert out is not None
    assert any(
        r.field_name == "TargetsRS" and "Add failed" in r.reason for r in dropped
    )
