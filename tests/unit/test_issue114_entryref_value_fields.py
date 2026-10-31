"""Issue #114 -- LexEntryRef `HideMinorEntry` (Int32) and `Summary`
(IMultiString) were never stashed or written by any entry-ref pass, and had no
census row, so the loss was silent.

Covers:
- `_stash_entry_bindings` records both fields as plain data
  (`hide_minor_entry`: int, `summary`: {source_ws_id: text}).
- `_run_entryref_create_pass` CREATE arm writes them onto the fresh ref, at
  the ws_map-translated TARGET handle, with read-back.
- the INV-1 (re-run) arm merges them per issue #22 Part 1
  (`conflict._merge_delta`): fill empty, update diverged, never blank, never
  touch a target-only alternative, and write NOTHING when values already match.
- never-silent: an unmapped Summary WS and a write the read-back does not show
  are `DroppedItemRecord`s on the ref.

Host-free: SIL.LCModel / System are stubbed as in
`test_027_entryref_reproduction.py`.
"""
from __future__ import annotations

import sys
import types

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.categories import (
    _merge_entryref_value_fields,
    _run_entryref_create_pass,
    _stash_entry_bindings,
)

from _fakes_entryref import (
    FakeRefSeq,
    ctx_create_and_wire,
    make_ctx,
    ref_record,
)


# ============================================================================
# Fakes
# ============================================================================

class _Ts:
    def __init__(self, text):
        self.Text = text


class _MultiString:
    """Handle-keyed fake IMultiString (plain-text values) that logs every
    set_String."""

    def __init__(self, by_handle=None, *, drop_writes=False):
        self._data = dict(by_handle or {})
        self.set_log = []
        self._drop_writes = drop_writes

    def get_String(self, handle):
        return _Ts(self._data.get(handle, ""))

    def set_String(self, handle, value):
        self.set_log.append((handle, value))
        if not self._drop_writes:
            self._data[handle] = value


class _WS:
    def __init__(self, ws_id, handle):
        self.Id = ws_id
        self.Handle = handle


class _WritingSystems:
    def __init__(self, pairs):
        self._ws = [_WS(i, h) for i, h in pairs]

    def GetAll(self):
        return list(self._ws)


class _Ref:
    """A LexEntryRef fake whose HideMinorEntry setter is counted."""

    def __init__(self, guid, hide=0, summary=None, ref_type=0):
        self.guid = guid
        self.RefType = ref_type
        self._hide = hide
        self.hide_sets = 0
        self.Summary = summary if summary is not None else _MultiString()
        self.ComponentLexemesRS = FakeRefSeq()
        self.PrimaryLexemesRS = FakeRefSeq()
        self.ShowComplexFormsInRS = FakeRefSeq()
        self.VariantEntryTypesRS = []
        self.ComplexEntryTypesRS = []

    @property
    def HideMinorEntry(self):
        return self._hide

    @HideMinorEntry.setter
    def HideMinorEntry(self, value):
        self.hide_sets += 1
        self._hide = value


class _Factory:
    def __init__(self):
        self.created = []

    def Create(self, guid):
        ref = _Ref(guid)
        self.created.append(ref)
        return ref


class _Entry:
    def __init__(self, guid, refs=()):
        self.guid = guid
        self.EntryRefsOS = FakeRefSeq(initial=refs)


class _Target:
    """Target handle: GUID registry, factory, writing systems."""

    def __init__(self, objects, ws_pairs=(("en", 10), ("fr", 11))):
        self._objs = dict(objects)
        self.factory = _Factory()
        self.WritingSystems = _WritingSystems(ws_pairs)

    def get_object_by_guid(self, guid):
        return self._objs.get(guid)

    def GetFactory(self, _token):
        return self.factory


def _install(name, module):
    original = sys.modules.get(name)
    sys.modules[name] = module
    return original


def _uninstall(name, original):
    if original is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = original


@pytest.fixture
def _stub_lcm():
    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.ILexEntryRefFactory = lambda raw: raw
    fake_lcm.ICmObjectRepository = object()
    for iface in ("ILexEntry", "ILexEntryRef"):
        setattr(fake_lcm, iface, lambda obj: obj)
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    orig_lcm = _install("SIL.LCModel", fake_lcm)
    fake_system = types.ModuleType("System")
    fake_system.Guid = type("FakeGuid", (), {"Parse": staticmethod(lambda s: s)})
    orig_sys = _install("System", fake_system)
    yield
    _uninstall("SIL.LCModel", orig_lcm)
    _uninstall("System", orig_sys)


def _rec(ref_guid, hide=None, summary=None, ref_type=0):
    return ref_record(ref_guid, ref_type=ref_type,
                      hide_minor_entry=hide, summary=summary)


def _run(target, records, ws_map=None, dropped=None):
    ctx = ctx_create_and_wire({"entry-1": records}, dropped=dropped)
    object.__setattr__(ctx, "_ws_map", ws_map)
    return _run_entryref_create_pass(ctx, target), ctx


# ============================================================================
# Stash
# ============================================================================

def test_stash_records_hide_minor_entry_and_summary_by_ws_id() -> None:
    src_ref = _Ref("ref-1", hide=1,
                   summary=_MultiString({1: "a summary", 2: ""}))
    src_entry = types.SimpleNamespace(guid="entry-1", EntryRefsOS=[src_ref])
    ctx = make_ctx()
    object.__setattr__(ctx, "source_handle", types.SimpleNamespace(
        WritingSystems=_WritingSystems((("en", 1), ("fr", 2)))))
    object.__setattr__(ctx, "_entryref_create_bindings", {})

    _stash_entry_bindings(src_entry, ctx)

    (rec,) = ctx._entryref_create_bindings["entry-1"]
    assert rec["hide_minor_entry"] == 1
    assert rec["summary"] == {"en": "a summary"}  # empty fr alt not stashed


def test_stash_tolerates_a_ref_without_the_value_fields() -> None:
    bare = types.SimpleNamespace(guid="ref-1", RefType=0)
    src_entry = types.SimpleNamespace(guid="entry-1", EntryRefsOS=[bare])
    ctx = make_ctx()  # object() source handle: no writing systems
    object.__setattr__(ctx, "_entryref_create_bindings", {})

    _stash_entry_bindings(src_entry, ctx)

    (rec,) = ctx._entryref_create_bindings["entry-1"]
    assert rec["hide_minor_entry"] is None
    assert rec["summary"] == {}


# ============================================================================
# CREATE arm
# ============================================================================

def test_create_writes_hide_minor_entry_and_summary(_stub_lcm) -> None:
    target = _Target({"entry-1": _Entry("entry-1")})
    _run(target, [_rec("ref-1", hide=1, summary={"en": "S-en", "fr": "S-fr"})])

    (new_ref,) = target.factory.created
    assert new_ref.HideMinorEntry == 1
    assert new_ref.Summary.get_String(10).Text == "S-en"
    assert new_ref.Summary.get_String(11).Text == "S-fr"


def test_create_writes_summary_at_the_mapped_target_handle(_stub_lcm) -> None:
    target = _Target({"entry-1": _Entry("entry-1")},
                     ws_pairs=(("en", 10), ("en-GB", 12)))
    _run(target, [_rec("ref-1", summary={"en": "mapped"})],
         ws_map={"en": "en-GB"})

    (new_ref,) = target.factory.created
    assert new_ref.Summary.set_log == [(12, "mapped")]


def test_create_with_default_values_writes_nothing(_stub_lcm) -> None:
    target = _Target({"entry-1": _Entry("entry-1")})
    _run(target, [_rec("ref-1", hide=0, summary={})])

    (new_ref,) = target.factory.created
    assert new_ref.hide_sets == 0  # fresh ref is already 0
    assert new_ref.Summary.set_log == []


def test_create_unmapped_summary_ws_is_a_drop_not_silent(_stub_lcm) -> None:
    dropped = []
    target = _Target({"entry-1": _Entry("entry-1")}, ws_pairs=(("en", 10),))
    _run(target, [_rec("ref-1", summary={"en": "ok", "ko": "lost"})],
         dropped=dropped)

    (new_ref,) = target.factory.created
    assert new_ref.Summary.get_String(10).Text == "ok"
    assert [(d.owner_kind, d.owner_guid, d.field_name, d.item_name)
            for d in dropped] == [("LexEntryRef", "ref-1", "Summary", "ko")]


# ============================================================================
# INV-1 (re-run) arm -- #22 Part 1 merge
# ============================================================================

def test_rerun_with_matching_values_writes_nothing(_stub_lcm) -> None:
    existing = _Ref("ref-1", hide=1, summary=_MultiString({10: "same"}))
    target = _Target({"entry-1": _Entry("entry-1", refs=[existing])})
    dropped = []
    _run(target, [_rec("ref-1", hide=1, summary={"en": "same"})],
         dropped=dropped)

    assert target.factory.created == []  # INV-1: nothing created
    assert existing.hide_sets == 0
    assert existing.Summary.set_log == []
    assert dropped == []


def test_rerun_fills_empty_updates_diverged_never_touches_target_only(
        _stub_lcm) -> None:
    # target: en diverged, fr empty, de target-only
    existing = _Ref("ref-1", hide=0, summary=_MultiString(
        {10: "old", 13: "target only"}))
    target = _Target({"entry-1": _Entry("entry-1", refs=[existing])},
                     ws_pairs=(("en", 10), ("fr", 11), ("de", 13)))
    _run(target, [_rec("ref-1", hide=1, summary={"en": "new", "fr": "filled"})])

    assert existing.HideMinorEntry == 1
    ms = existing.Summary
    assert ms.get_String(10).Text == "new"
    assert ms.get_String(11).Text == "filled"
    assert ms.get_String(13).Text == "target only"
    assert sorted(h for h, _v in ms.set_log) == [10, 11]


def test_rerun_empty_source_summary_never_blanks_target(_stub_lcm) -> None:
    existing = _Ref("ref-1", hide=0,
                    summary=_MultiString({10: "keep me"}))
    target = _Target({"entry-1": _Entry("entry-1", refs=[existing])})
    _run(target, [_rec("ref-1", hide=0, summary={})])

    assert existing.Summary.set_log == []
    assert existing.Summary.get_String(10).Text == "keep me"


def test_rerun_hide_minor_entry_source_zero_is_unset_target_one_stays(
        _stub_lcm) -> None:
    """Domain policy Q2: on the overwrite-existing path a source
    HideMinorEntry 0 is UNSET -- target 1 / source 0 stays 1, no write, no
    drop. Only a source 1 may overwrite a target 0."""
    existing = _Ref("ref-1", hide=1)
    target = _Target({"entry-1": _Entry("entry-1", refs=[existing])})
    _run(target, [_rec("ref-1", hide=0)])

    assert existing.HideMinorEntry == 1
    assert existing.hide_sets == 0


def test_rerun_hide_minor_entry_source_one_overwrites_target_zero(
        _stub_lcm) -> None:
    existing = _Ref("ref-1", hide=0)
    target = _Target({"entry-1": _Entry("entry-1", refs=[existing])})
    _run(target, [_rec("ref-1", hide=1)])

    assert existing.HideMinorEntry == 1
    assert existing.hide_sets == 1


def test_non_numeric_hide_minor_entry_is_a_drop_not_an_exception() -> None:
    class _Weird(_Ref):
        @property
        def HideMinorEntry(self):
            return "n/a"

        @HideMinorEntry.setter
        def HideMinorEntry(self, value):
            self.hide_sets += 1

    dropped = []
    written = _merge_entryref_value_fields(
        _rec("ref-1", hide=1), _Weird("ref-1"), types.SimpleNamespace(),
        None, dropped)

    assert written == []
    assert [d.field_name for d in dropped] == ["HideMinorEntry"]


def test_rerun_target_only_ref_is_untouched(_stub_lcm) -> None:
    other = _Ref("ref-target-only", hide=1,
                 summary=_MultiString({10: "mine"}))
    target = _Target({"entry-1": _Entry("entry-1", refs=[other])})
    _run(target, [_rec("ref-1", hide=0, summary={"en": "src"})])

    assert other.hide_sets == 0 and other.Summary.set_log == []


# ============================================================================
# Read-back
# ============================================================================

def test_summary_write_missing_on_read_back_is_a_drop() -> None:
    ref = _Ref("ref-1", summary=_MultiString(drop_writes=True))
    target = types.SimpleNamespace(WritingSystems=_WritingSystems((("en", 10),)))
    dropped = []
    written = _merge_entryref_value_fields(
        _rec("ref-1", summary={"en": "x"}), ref, target, None, dropped)

    assert written == []
    assert [(d.field_name, d.item_name) for d in dropped] == [("Summary", "en")]
    assert "read-back" in dropped[0].reason


def test_hide_minor_entry_write_missing_on_read_back_is_a_drop() -> None:
    class _Stuck(_Ref):
        @property
        def HideMinorEntry(self):
            return 0

        @HideMinorEntry.setter
        def HideMinorEntry(self, value):
            self.hide_sets += 1  # accepted but never lands

    ref = _Stuck("ref-1")
    dropped = []
    written = _merge_entryref_value_fields(
        _rec("ref-1", hide=1), ref, types.SimpleNamespace(), None, dropped)

    assert written == []
    assert [(d.field_name, d.item_name) for d in dropped] == [
        ("HideMinorEntry", "1")]


def test_merge_returns_the_written_fields() -> None:
    ref = _Ref("ref-1")
    target = types.SimpleNamespace(WritingSystems=_WritingSystems((("en", 10),)))
    written = _merge_entryref_value_fields(
        _rec("ref-1", hide=1, summary={"en": "x"}), ref, target, None, [])
    assert written == ["HideMinorEntry", "Summary@en"]


def test_value_merge_helper_is_the_one_create_pass_uses() -> None:
    """Both arms route through the one helper (no forked merge logic)."""
    import inspect
    src = inspect.getsource(categories._run_entryref_create_pass)
    assert src.count("_merge_entryref_value_fields(") == 2
