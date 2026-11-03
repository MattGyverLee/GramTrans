"""Issue #132: key-matched PhNCSegments SegmentsRC.Add must not fail silently."""
from __future__ import annotations

from gramtrans.Lib import categories
from gramtrans.Lib.models import DroppedItemRecord


class _AddList(list):
    def Add(self, item):  # noqa: N802 -- mirrors LCM
        self.append(item)


class _RaisingSegmentsRC:
    def __init__(self, items=()):
        self._items = list(items)

    def Add(self, member):
        raise TypeError("No method matches given arguments")

    def __iter__(self):
        return iter(self._items)


class _Phoneme:
    def __init__(self, guid):
        self.Guid = guid


def test_try_add_nc_segments_rc_member_records_drop():
    segs = _RaisingSegmentsRC()
    phon = _Phoneme("phon-1")
    dropped = []
    ok = categories._try_add_nc_segments_rc_member(
        segs, phon, owner_guid="nc-1", dropped=dropped)
    assert ok is False
    assert len(dropped) == 1
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.field_name == "SegmentsRC"
    assert rec.owner_guid == "nc-1"
    assert rec.item_guid == "phon-1"
    assert "SegmentsRC.Add failed" in rec.reason


def test_try_add_nc_segments_rc_member_success():
    segs = _AddList()
    phon = _Phoneme("phon-2")
    dropped = []
    ok = categories._try_add_nc_segments_rc_member(
        segs, phon, owner_guid="nc-2", dropped=dropped)
    assert ok is True
    assert dropped == []
    assert len(segs) == 1
