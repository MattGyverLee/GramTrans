"""Unit tests for feature 027 (Complex Forms & Variants), US1/US3: `LexEntryRef`
container creation (`categories._run_entryref_create_pass`, contract C1) and
the extended create-then-wire flow reachable via `_run_post_pass_a` (C2).

Resolves GitHub #30; unblocks the LexEntryRef leg of #28. See:
- specs/027-complex-forms-variants/contracts/entryref-reproduction.md (C1, C2)
- specs/027-complex-forms-variants/research.md (Decisions 1-3, 6-7)
- specs/027-complex-forms-variants/data-model.md (per-ref binding shape)

`_run_entryref_create_pass` reads `context._run_plan.entryref_create_bindings`
(`{src_entry_guid: [ref_record, ...]}`, data-model.md's extension) and
`plan.identity_remap`. For each source entry, it resolves the owning target
entry via `_resolve_target_by_guid` + `_cast_lcm(..., "ILexEntry")` (issue #28
layers 1+2), then for each not-yet-reproduced ref (GUID guard, INV-1) creates
a `LexEntryRef` via the raw `ILexEntryRefFactory` (research.md Decision 1 --
flexicon has no wrapper for this factory), sets `RefType`, and owns it into
`EntryRefsOS`.

T007-T009 (RED-before-GREEN): these tests are authored BEFORE
`_run_entryref_create_pass` exists in `categories.py` and MUST fail first
(AttributeError: module has no attribute '_run_entryref_create_pass') --
confirmed in the programmer's cycle-1 report.
"""
from __future__ import annotations

import sys
import types

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.models import (
    GrammarCategory,
    RunContext,
    Skip,
    SkipReason,
)


# ============================================================================
# Fakes (inline, lowercase .guid so _guid_str_from resolves host-free)
# ============================================================================

class _FakeRefSeq:
    """LCM owning/reference sequence stand-in: records Add calls in order."""

    def __init__(self, initial=()) -> None:
        self._items = list(initial)
        self.add_log = []

    def Add(self, obj):
        self._items.append(obj)
        self.add_log.append(obj)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    @property
    def Count(self):
        return len(self._items)


class _FakeCreatedRef:
    """What `factory.Create(guid)` returns: a fresh, unowned LexEntryRef."""

    def __init__(self, guid) -> None:
        self.guid = guid
        self.RefType = None
        self.ComponentLexemesRS = _FakeRefSeq()
        self.PrimaryLexemesRS = _FakeRefSeq()


class _FakeEntryRefFactory:
    """Duck-typed stand-in for the raw ILexEntryRefFactory: records every
    guid passed to Create so tests can assert GUID-preservation (INV-1)."""

    def __init__(self) -> None:
        self.create_log = []

    def Create(self, guid):
        self.create_log.append(guid)
        return _FakeCreatedRef(guid)


class _FailingEntryRefFactory:
    """Simulates an absent/broken factory: Create always raises."""

    def Create(self, guid):
        raise RuntimeError("factory unavailable")


class _FakeTargetEntry:
    def __init__(self, guid: str, entry_refs=()) -> None:
        self.guid = guid
        self.EntryRefsOS = _FakeRefSeq(initial=entry_refs)


class _FakeTarget:
    """Target project handle: get_object_by_guid registry + GetFactory."""

    def __init__(self, objects_by_guid=None, factory=None) -> None:
        self._objs = dict(objects_by_guid or {})
        self._factory = factory if factory is not None else _FakeEntryRefFactory()

    def get_object_by_guid(self, guid):
        return self._objs.get(guid)

    def GetFactory(self, iface_token):
        return self._factory


def _make_ctx() -> RunContext:
    return RunContext(
        source_handle=object(),
        source_project_name="Src",
        source_project_path="/src",
        target_handle=object(),
        target_project_name="Tgt",
        target_project_path="/tgt",
        run_id="GT-20260713-000000",
        started_at="2026-07-13T00:00:00",
    )


def _ref_record(ref_guid, ref_type=0, components=(), primaries=(),
                variant_entry_types=(), complex_entry_types=(),
                show_complex_forms_in=()):
    return {
        "ref_guid": ref_guid,
        "ref_type": ref_type,
        "components": list(components),
        "primaries": list(primaries),
        "variant_entry_types": list(variant_entry_types),
        "complex_entry_types": list(complex_entry_types),
        "show_complex_forms_in": list(show_complex_forms_in),
    }


def _ctx_create(entryref_create_bindings, identity_remap=None, dropped=None) -> RunContext:
    ctx = _make_ctx()
    plan = types.SimpleNamespace(
        entryref_create_bindings={
            k: list(v) for k, v in entryref_create_bindings.items()
        },
        identity_remap=dict(identity_remap or {}),
    )
    object.__setattr__(ctx, "_run_plan", plan)
    if dropped is None:
        dropped = []
    object.__setattr__(ctx, "_dropped", dropped)
    return ctx


# ============================================================================
# SIL.LCModel / System stubs
# ============================================================================

def _install_module(name, module):
    original = sys.modules.get(name)
    sys.modules[name] = module
    return original


def _restore_module(name, original):
    if original is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = original


@pytest.fixture
def _stub_lcm_factory_only():
    """Stub SIL.LCModel + System with ONLY `ILexEntryRefFactory` present --
    NOT `ILexEntry`/`ILexEntryRef` -- so `_cast_lcm` cannot find those
    interfaces and falls back to returning the bare object unchanged (T009's
    "uncast reproduces 0" half)."""
    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.ILexEntryRefFactory = lambda raw: raw  # identity cast
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    original_lcm = _install_module("SIL.LCModel", fake_lcm)

    fake_system = types.ModuleType("System")
    fake_system.Guid = type(
        "FakeGuid", (), {"Parse": staticmethod(lambda s: s)}
    )
    original_system = _install_module("System", fake_system)

    yield

    _restore_module("SIL.LCModel", original_lcm)
    _restore_module("System", original_system)


def _iface_cast(name):
    """A stub SIL.LCModel interface: `IFoo(bare)` -> bare._views['IFoo']."""
    def cast(obj):
        return getattr(obj, "_views", {}).get(name, obj)
    return cast


@pytest.fixture
def _stub_lcm_full():
    """Stub SIL.LCModel + System with `ILexEntryRefFactory` PLUS the
    `ILexEntry`/`ILexEntryRef` casts the pass depends on (T009's "cast path
    reproduces N" half; also used by the plain create/idempotency tests)."""
    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.ILexEntryRefFactory = lambda raw: raw  # identity cast
    fake_lcm.ICmObjectRepository = object()
    for iface in ("ILexEntry", "ILexEntryRef"):
        setattr(fake_lcm, iface, _iface_cast(iface))
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    original_lcm = _install_module("SIL.LCModel", fake_lcm)

    fake_system = types.ModuleType("System")
    fake_system.Guid = type(
        "FakeGuid", (), {"Parse": staticmethod(lambda s: s)}
    )
    original_system = _install_module("System", fake_system)

    yield

    _restore_module("SIL.LCModel", original_lcm)
    _restore_module("System", original_system)


# ============================================================================
# T007 -- C1 container creation over duck-typed fakes
# ============================================================================

def test_entryref_create_pass_creates_variant_container(_stub_lcm_full) -> None:
    """A single variant ref_record -> 1 LexEntryRef created, GUID preserved,
    RefType=0 set, owned into EntryRefsOS."""
    entry = _FakeTargetEntry("entry-1")
    factory = _FakeEntryRefFactory()
    target = _FakeTarget({"entry-1": entry}, factory=factory)
    ctx = _ctx_create({"entry-1": [_ref_record("ref-1", ref_type=0)]})

    skips = categories._run_entryref_create_pass(ctx, target, tag=None)

    assert skips == []
    assert factory.create_log == ["ref-1"]  # GUID preserved
    assert len(entry.EntryRefsOS) == 1
    new_ref = list(entry.EntryRefsOS)[0]
    assert new_ref.guid == "ref-1"
    assert new_ref.RefType == 0


def test_entryref_create_pass_unresolved_target_entry_skips() -> None:
    """Target entry missing -> 1 Skip(DEPENDENCY_UNRESOLVED), no create call."""
    target = _FakeTarget({})  # entry-missing absent
    ctx = _ctx_create({"entry-missing": [_ref_record("ref-1")]})

    skips = categories._run_entryref_create_pass(ctx, target, tag=None)

    assert len(skips) == 1
    assert skips[0].reason == SkipReason.DEPENDENCY_UNRESOLVED
    assert "entry_guid=entry-missing" in skips[0].detail


def test_entryref_create_pass_idempotent_guid_guard(_stub_lcm_full) -> None:
    """A ref whose GUID already exists on the target entry is NOT re-created
    (INV-1 idempotency guard) -- 0 net creates, 0 skips."""
    existing_ref = _FakeCreatedRef("ref-1")
    entry = _FakeTargetEntry("entry-1", entry_refs=[existing_ref])
    factory = _FakeEntryRefFactory()
    target = _FakeTarget({"entry-1": entry}, factory=factory)
    ctx = _ctx_create({"entry-1": [_ref_record("ref-1", ref_type=0)]})

    skips = categories._run_entryref_create_pass(ctx, target, tag=None)

    assert skips == []
    assert factory.create_log == []  # no re-create
    assert len(entry.EntryRefsOS) == 1


def test_entryref_create_pass_empty_bindings_noop() -> None:
    """Empty plan bindings -> no work, empty skip list (FR-011/C7 parity)."""
    ctx = _ctx_create({})
    assert categories._run_entryref_create_pass(ctx, _FakeTarget({}), tag=None) == []


def test_entryref_create_pass_degrades_when_factory_unavailable() -> None:
    """No SIL.LCModel stubbed at all -> ILexEntryRefFactory import fails ->
    degrade to report-only (DroppedItemRecord), never crash (Principle II)."""
    sys.modules.pop("SIL.LCModel", None)  # ensure absent
    entry = _FakeTargetEntry("entry-1")
    target = _FakeTarget({"entry-1": entry})
    dropped = []
    ctx = _ctx_create({"entry-1": [_ref_record("ref-1", ref_type=0)]}, dropped=dropped)

    skips = categories._run_entryref_create_pass(ctx, target, tag=None)

    assert skips == []  # not a Skip -- reported, not crashed
    assert len(entry.EntryRefsOS) == 0  # nothing created
    assert len(dropped) == 1
    assert dropped[0].item_guid == "ref-1"


def test_entryref_create_pass_multi_component_complex_form(_stub_lcm_full) -> None:
    """US3 parity check (offline): RefType=1 complex-form container creates
    the same way as a variant container -- parametric, no new create path."""
    entry = _FakeTargetEntry("entry-1")
    factory = _FakeEntryRefFactory()
    target = _FakeTarget({"entry-1": entry}, factory=factory)
    ctx = _ctx_create({"entry-1": [_ref_record(
        "ref-cf1", ref_type=1,
        components=["lex-a", "lex-b"], primaries=["lex-a"],
    )]})

    skips = categories._run_entryref_create_pass(ctx, target, tag=None)

    assert skips == []
    new_ref = list(entry.EntryRefsOS)[0]
    assert new_ref.RefType == 1


# ============================================================================
# T008 -- fake ICmObjectRepository fallback branch (closes the #28 offline gap)
# ============================================================================

class _FakeRepo:
    """LCM ICmObjectRepository stand-in: IsValidObjectId + GetObject over a map."""

    def __init__(self, objects_by_guid=None) -> None:
        self._objs = dict(objects_by_guid or {})

    def IsValidObjectId(self, guid):
        return self._key(guid) in self._objs

    def GetObject(self, guid):
        return self._objs.get(self._key(guid))

    @staticmethod
    def _key(guid):
        return guid[1] if isinstance(guid, tuple) else guid


class _FakeLiveTarget:
    """Mirrors the live flexicon FLExProject: exposes ObjectRepository() AND
    GetFactory(), but NO get_object_by_guid -- so `_resolve_target_by_guid`
    must take the live LCM-repo fallback branch for entry resolution."""

    def __init__(self, objects_by_guid=None, factory=None) -> None:
        self._repo = _FakeRepo(objects_by_guid)
        self._factory = factory if factory is not None else _FakeEntryRefFactory()

    def ObjectRepository(self, iface):
        return self._repo

    def GetFactory(self, iface_token):
        return self._factory


def test_entryref_create_pass_resolves_entry_via_live_repo_fallback(_stub_lcm_full) -> None:
    """No get_object_by_guid on the target -- entry resolution MUST route
    through the ICmObjectRepository fallback branch, proving the pass closes
    the exact offline coverage gap that let #28 ship (`_run_171_subpass` /
    `_run_post_pass_a` both lacked this fallback-branch-through-the-pass
    coverage before their fix)."""
    entry = _FakeTargetEntry("entry-1")
    factory = _FakeEntryRefFactory()
    target = _FakeLiveTarget({"entry-1": entry}, factory=factory)
    ctx = _ctx_create({"entry-1": [_ref_record("ref-1", ref_type=0)]})

    skips = categories._run_entryref_create_pass(ctx, target, tag=None)

    assert skips == []
    assert factory.create_log == ["ref-1"]
    assert len(entry.EntryRefsOS) == 1


# ============================================================================
# T009 -- _Bare vs _Typed cast tripwire (issue #28 layer 2)
# ============================================================================

class _Bare:
    """Bare ICmObject stand-in: exposes .guid; typed members hidden until a
    stubbed interface cast returns the matching `_view`."""

    def __init__(self, guid, views=None) -> None:
        self.guid = guid
        self._views = dict(views or {})


class _Typed:
    """A cast 'view' exposing the typed members the interface declares."""

    def __init__(self, guid, **members) -> None:
        self.guid = guid
        for k, v in members.items():
            setattr(self, k, v)


def test_entryref_create_pass_uncast_bare_entry_reproduces_zero(_stub_lcm_factory_only) -> None:
    """`ILexEntry`/`ILexEntryRef` NOT stubbed (factory-only fixture) ->
    `_cast_lcm` cannot surface `.EntryRefsOS` on the bare resolved entry ->
    the pass reproduces 0 refs and emits a Skip -- reproducing the exact
    #28 layer-2 live no-op offline."""
    bare_entry = _Bare("entry-1")  # no _views -- EntryRefsOS stays hidden
    target = _FakeTarget({"entry-1": bare_entry})
    ctx = _ctx_create({"entry-1": [_ref_record("ref-1", ref_type=0)]})

    skips = categories._run_entryref_create_pass(ctx, target, tag=None)

    assert len(skips) == 1
    assert skips[0].reason == SkipReason.DEPENDENCY_UNRESOLVED


def test_entryref_create_pass_casts_bare_entry_reproduces_n(_stub_lcm_full) -> None:
    """Same bare entry shape, but `ILexEntry` IS stubbed and this object DOES
    carry a matching `_views['ILexEntry']` -- `_cast_lcm` surfaces the typed
    view's `EntryRefsOS`, and the pass creates N (=1) refs. Without the cast
    fix, `bare.EntryRefsOS` would be `None` and this would stay at 0 (the
    same shape as `test_post_pass_a_casts_bare_entry_and_ref`)."""
    entry_refs_seq = _FakeRefSeq()
    entry_view = _Typed("entry-1", EntryRefsOS=entry_refs_seq)
    bare_entry = _Bare("entry-1", views={"ILexEntry": entry_view})
    factory = _FakeEntryRefFactory()
    target = _FakeTarget({"entry-1": bare_entry}, factory=factory)
    ctx = _ctx_create({"entry-1": [_ref_record("ref-1", ref_type=0)]})

    skips = categories._run_entryref_create_pass(ctx, target, tag=None)

    assert skips == []
    assert factory.create_log == ["ref-1"]
    assert len(entry_refs_seq) == 1  # wired into the CAST entry's sequence


# ============================================================================
# P1 (cycle-3 DRY fold) -- `_safe_add_to_owner` orphan-risk raise path
# ============================================================================

class _FailingAddRefSeq(_FakeRefSeq):
    """An owning sequence whose `.Add()` always raises -- simulates
    `Create()` succeeding but the LCM Add-to-owner call failing."""

    def Add(self, obj):
        raise RuntimeError("Add-to-owner failed (simulated LCM failure)")


def test_entryref_create_pass_add_failure_raises_orphan_risk_runtimeerror(
        _stub_lcm_full) -> None:
    """`entry_refs.Add(new_ref)` failing after a successful `Create()` must
    raise a `RuntimeError` naming the orphan risk -- this is now routed
    through the shared `_safe_add_to_owner` helper (P1 DRY fold, same one
    every other hand-rolled Create+Add category site already uses) instead
    of a bespoke inline try/except, so this branch proves the fold didn't
    silently drop the orphan-risk guard."""
    entry = _FakeTargetEntry("entry-1")
    entry.EntryRefsOS = _FailingAddRefSeq()
    factory = _FakeEntryRefFactory()
    target = _FakeTarget({"entry-1": entry}, factory=factory)
    ctx = _ctx_create({"entry-1": [_ref_record("ref-1", ref_type=0)]})

    with pytest.raises(RuntimeError, match="Orphan risk"):
        categories._run_entryref_create_pass(ctx, target, tag=None)

    # Create() DID succeed (the orphan risk is real -- an object exists
    # somewhere that never got owned) before the Add failure surfaced.
    assert factory.create_log == ["ref-1"]
