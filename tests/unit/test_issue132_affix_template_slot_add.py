"""Issue #132: affix-template create path must not swallow slot-sequence Add failures."""
from __future__ import annotations

from gramtrans.Lib import categories
from gramtrans.Lib.models import DroppedItemRecord


class _FakeSlot:
    def __init__(self, guid: str) -> None:
        self.Guid = guid
        self.guid = guid


class _RaiseOnAdd(list):
    def Add(self, item):
        raise TypeError("No method matches given arguments")


def test_template_slot_add_failure_records_drop():
    coll = _RaiseOnAdd()
    slot = _FakeSlot("slot-guid")
    dropped: list = []
    categories._try_add_affix_template_slot_member(
        coll, slot, template_guid="tpl-guid", seq_name="PrefixSlotsRS",
        src_slot=slot, dropped=dropped,
    )
    assert list(coll) == []
    assert len(dropped) == 1
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.owner_kind == "MoInflAffixTemplate"
    assert rec.owner_guid == "tpl-guid"
    assert rec.field_name == "PrefixSlotsRS"
    assert rec.item_guid == "slot-guid"
    assert "Add failed on PrefixSlotsRS" in rec.reason
    assert "TypeError" in rec.reason


def test_template_slot_add_success_no_drop():
    coll: list = []
    slot = _FakeSlot("slot-guid")

    class _Coll(list):
        def Add(self, item):
            self.append(item)

    coll_obj = _Coll()
    dropped: list = []
    categories._try_add_affix_template_slot_member(
        coll_obj, slot, template_guid="tpl-guid", seq_name="SuffixSlotsRS",
        src_slot=slot, dropped=dropped,
    )
    assert len(coll_obj) == 1
    assert dropped == []
