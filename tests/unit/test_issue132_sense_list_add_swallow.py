"""Issue #132 batch: never-silent `.Add()` on sense-list reference fields."""
from __future__ import annotations

from gramtrans.Lib import categories
from gramtrans.Lib.models import DroppedItemRecord

WS_EN = 100


class _FakeMultiString:
    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})


class _FakeColl:
    def __init__(self, items=(), fail: Exception | None = None):
        self._items = list(items)
        self._fail = fail

    def Add(self, item):
        if self._fail is not None:
            raise self._fail
        self._items.append(item)

    def __iter__(self):
        return iter(self._items)


class _FakeAppendix:
    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid


class _FakeTarget:
    def __init__(self, appendixes=()):
        self.appendixes = list(appendixes)


class _FakeSourceSense:
    def __init__(self, guid, appendixes=()):
        self.Guid = guid
        self.guid = guid
        self.ClassName = "LexSense"
        self.Gloss = _FakeMultiString({WS_EN: "gloss"})
        self.AppendixesRC = list(appendixes)


def test_appendix_add_failure_records_drop():
    tgt_ap = _FakeAppendix("ap-g")
    target = _FakeTarget(appendixes=[tgt_ap])
    sense = _FakeSourceSense("s-g", appendixes=[_FakeAppendix("ap-g")])
    new_sense = type("Sense", (), {
        "AppendixesRC": _FakeColl(fail=RuntimeError("boom")),
    })()
    dropped: list = []
    categories._resolve_sense_appendixes(sense, new_sense, target, dropped)
    assert len(dropped) == 1
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.field_name == "AppendixesRC"
    assert "could not be added" in rec.reason
    assert "RuntimeError" in rec.reason


def test_appendix_missing_collection_records_drop():
    tgt_ap = _FakeAppendix("ap-g")
    target = _FakeTarget(appendixes=[tgt_ap])
    sense = _FakeSourceSense("s-g", appendixes=[_FakeAppendix("ap-g")])
    new_sense = object()
    dropped: list = []
    categories._resolve_sense_appendixes(sense, new_sense, target, dropped)
    assert len(dropped) == 1
    assert dropped[0].field_name == "AppendixesRC"
    assert "collection missing" in dropped[0].reason
