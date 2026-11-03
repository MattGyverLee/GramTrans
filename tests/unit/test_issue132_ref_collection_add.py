"""Issue #132 batch 2: reference-collection `.Add` failures must not be silent.

MattGyverLee comment on #132 (2026-11-01): `_apply_reference_fields` and
`owned._apply_child_refs` used to swallow Add failures like the pre-#183
GenresRC path. This batch records a `DroppedItemRecord` instead (#161 pattern).
"""
from __future__ import annotations

import types

from gramtrans.Lib import categories, owned
from gramtrans.Lib.models import DroppedItemRecord

WS_EN = 100


class _FakeTsString:
    def __init__(self, text):
        self.Text = text or None


class _FakeMultiString:
    def __init__(self, data=None):
        self._data = dict(data or {})

    def get_String(self, ws_handle):
        return _FakeTsString(self._data.get(ws_handle))


class _FakePossibility:
    def __init__(self, guid, name=""):
        self.Guid = guid
        self.guid = guid
        self.Name = _FakeMultiString({WS_EN: name} if name else {})
        self.Abbreviation = _FakeMultiString({})
        self.IsProtected = False
        self.Owner = None
        self.OwningPossibility = None


class _FakeCollection(list):
    def Add(self, item):
        super().append(item)


class _RaiseOnAddCollection(_FakeCollection):
    def Add(self, item):
        raise TypeError("collection Add binding failed")


class _RaiseOnClearCollection(_FakeCollection):
    """Simulates OVERWRITE replace: pre-populated collection, Clear raises."""

    def __init__(self, *items):
        super().__init__(list(items))

    def Clear(self):
        raise TypeError("collection Clear binding failed")


def test_add_resolved_records_drop_on_add_failure():
    item = _FakePossibility("eeeeeeee-0000-0000-0000-eeeeeeeeeeee", name="Vernacular")
    coll = _RaiseOnAddCollection()
    dropped: list = []
    categories._add_resolved_to_reference_collection(
        coll, item, dropped=dropped,
        owner_class="LexSense", owner_guid="sense-1",
        src_obj=types.SimpleNamespace(), field_name="DoNotPublishInRC",
        source_item=item,
    )
    assert list(coll) == []
    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.field_name == "DoNotPublishInRC"
    assert rec.owner_guid == "sense-1"
    assert "reference collection Add failed" in rec.reason


def test_apply_reference_fields_records_drop_when_collection_add_raises(monkeypatch):
    from gramtrans.Lib.models import ReferenceAction, ReferenceDecision

    pub = _FakePossibility("eeeeeeee-0000-0000-0000-eeeeeeeeeeee", name="Vernacular")
    src_obj = types.SimpleNamespace(DoNotPublishInRC=[pub])
    new_obj = types.SimpleNamespace(DoNotPublishInRC=_RaiseOnAddCollection())
    dropped: list = []

    def _fake_decide(*_args, **_kwargs):
        return ReferenceDecision(
            action=ReferenceAction.LINK, target_item=pub, source_item=pub,
        )

    def _fake_call(*_args, **_kwargs):
        return pub, True

    monkeypatch.setattr(categories, "_call_apply_reference", _fake_call)
    from gramtrans.Lib import references as _references

    monkeypatch.setattr(_references, "decide_reference", _fake_decide)
    categories._apply_reference_fields(
        "LexSense", src_obj, new_obj, object(), None, {}, dropped,
        skip_fields=frozenset({"SenseTypeRA"}),
        owner_guid="sense-1",
    )
    assert len(dropped) == 1
    assert dropped[0].field_name == "DoNotPublishInRC"


def test_apply_reference_fields_records_drop_when_overwrite_clear_raises(monkeypatch):
    from gramtrans.Lib.models import ReferenceAction, ReferenceDecision

    stale = _FakePossibility("aaaaaaaa-0000-0000-0000-aaaaaaaaaaaa", name="stale")
    pub = _FakePossibility("eeeeeeee-0000-0000-0000-eeeeeeeeeeee", name="Vernacular")
    src_obj = types.SimpleNamespace(DoNotPublishInRC=[pub])
    new_obj = types.SimpleNamespace(
        DoNotPublishInRC=_RaiseOnClearCollection(stale),
    )
    dropped: list = []

    def _fake_decide(*_args, **_kwargs):
        return ReferenceDecision(
            action=ReferenceAction.LINK, target_item=pub, source_item=pub,
        )

    def _fake_call(*_args, **_kwargs):
        return pub, True

    monkeypatch.setattr(categories, "_call_apply_reference", _fake_call)
    from gramtrans.Lib import references as _references

    monkeypatch.setattr(_references, "decide_reference", _fake_decide)
    categories._apply_reference_fields(
        "LexSense", src_obj, new_obj, object(), None, {}, dropped,
        skip_fields=frozenset({"SenseTypeRA"}),
        owner_guid="sense-1",
        clear_before_add=True,
    )
    assert list(new_obj.DoNotPublishInRC) == [stale]
    assert len(dropped) == 1
    assert dropped[0].field_name == "DoNotPublishInRC"
    assert "Clear failed during OVERWRITE" in dropped[0].reason


def test_owned_apply_child_refs_records_drop_when_collection_add_raises(monkeypatch):
    pub = _FakePossibility("eeeeeeee-0000-0000-0000-eeeeeeeeeeee", name="Vernacular")

    class _Example:
        ClassName = "LexExampleSentence"

    src_child = _Example()
    src_child.Guid = "ex-1"
    src_child.guid = "ex-1"
    src_child.DoNotPublishInRC = [pub]
    new_child = types.SimpleNamespace(DoNotPublishInRC=_RaiseOnAddCollection())
    ctx = types.SimpleNamespace(
        target_handle=object(), source_handle=object(), _ws_map=None,
    )
    spec = owned._EXAMPLE_REF_SPECS[1]
    dropped: list = []

    def _fake_decide(*_args, **_kwargs):
        from gramtrans.Lib.models import ReferenceAction, ReferenceDecision
        return ReferenceDecision(
            action=ReferenceAction.LINK,
            target_item=pub,
            source_item=pub,
        )

    monkeypatch.setattr(owned._references, "decide_reference", _fake_decide)
    monkeypatch.setattr(
        owned._references, "apply_reference",
        lambda *a, **k: pub,
    )
    owned._apply_child_refs(
        (spec,), src_child, new_child, ctx, None, {}, dropped,
    )
    assert len(dropped) == 1
    assert dropped[0].field_name == "DoNotPublishInRC"
    assert "reference collection Add failed" in dropped[0].reason
