"""Issue #132: never-silent RestOfAllosRS / RestOfMorphsRS Add on adhoc rules."""
from __future__ import annotations

from gramtrans.Lib import categories
from gramtrans.Lib.models import DroppedItemRecord


class _FakeColl:
    def __init__(self, fail: Exception | None = None):
        self._fail = fail
        self.items = []

    def Add(self, item):
        if self._fail is not None:
            raise self._fail
        self.items.append(item)


class _FakeRule:
    def __init__(self, field_name: str, coll):
        setattr(self, field_name, coll)


def test_rest_of_allos_add_failure_records_drop():
    coll = _FakeColl(fail=TypeError("no method matches"))
    rule = _FakeRule("RestOfAllosRS", coll)
    member = type("Allo", (), {"Guid": "a1", "guid": "a1"})()
    dropped: list = []
    ok = categories._try_add_adhoc_rest_rs_member(
        rule, "RestOfAllosRS", member, "rule-g", dropped,
        owner_kind="MoAlloAdhocProhib",
    )
    assert ok is False
    assert len(dropped) == 1
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.field_name == "RestOfAllosRS"
    assert rec.owner_kind == "MoAlloAdhocProhib"
    assert "RestOfAllosRS.Add failed" in rec.reason


def test_rest_of_morphs_missing_collection_records_drop():
    rule = object()
    member = type("Msa", (), {"Guid": "m1", "guid": "m1"})()
    dropped: list = []
    ok = categories._try_add_adhoc_rest_rs_member(
        rule, "RestOfMorphsRS", member, "rule-g2", dropped,
        owner_kind="MoMorphAdhocProhib",
    )
    assert ok is False
    assert len(dropped) == 1
    assert dropped[0].field_name == "RestOfMorphsRS"
    assert "collection missing" in dropped[0].reason
