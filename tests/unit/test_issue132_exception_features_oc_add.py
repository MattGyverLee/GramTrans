"""Issue #132: ExceptionFeaturesOC.Add must not fail silently (#111 audit)."""
from __future__ import annotations

from gramtrans.Lib import categories
from gramtrans.Lib.models import DroppedItemRecord


class _FakeVal:
    def __init__(self, guid: str) -> None:
        self.guid = guid


class _RaisingExcOC:
    def __init__(self) -> None:
        self._items = []

    def Add(self, _obj) -> None:
        raise TypeError("binding gap")

    def __iter__(self):
        return iter(self._items)


def test_try_add_exception_features_oc_member_records_drop_on_add_failure():
    val = _FakeVal("v-1")
    coll = _RaisingExcOC()
    dropped = []
    ok = categories._try_add_exception_features_oc_member(
        coll, val, pos_guid="p-1", val_guid="v-1", dropped=dropped)
    assert ok is False
    assert len(dropped) == 1
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.field_name == "ExceptionFeaturesOC"
    assert rec.owner_guid == "p-1"
    assert rec.item_guid == "v-1"
    assert "WRITE_FAILED" in rec.reason


def test_try_add_exception_features_oc_member_idempotent_when_already_present():
    val = _FakeVal("v-2")

    class _Coll(list):
        def Add(self, obj) -> None:
            self.append(obj)

    coll = _Coll([val])
    dropped = []
    ok = categories._try_add_exception_features_oc_member(
        coll, val, pos_guid="p-2", val_guid="v-2", dropped=dropped)
    assert ok is True
    assert dropped == []
    assert len(coll) == 1
