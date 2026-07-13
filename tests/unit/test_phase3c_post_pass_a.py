"""Unit tests for Phase 3c post-pass A (LexEntryRef wiring) + the 17.1
MSA-slot sub-pass — the two pure-Python tail sub-passes of feature 007.

Both helpers are module-level in categories.py and run host-free over a
duck-typed target exposing `get_object_by_guid(guid)`:

- ``categories._run_post_pass_a(context, target, tag=None)`` — reads
  ``context._run_plan.lexentry_ref_bindings`` (``{src_entry_guid:
  {"ComponentLexemesRS": [...], "PrimaryLexemesRS": [...]}}``) plus
  ``plan.in_plan_entries``, then wires each target entry-ref's
  ComponentLexemesRS / PrimaryLexemesRS in source order. Idempotent via a
  membership guard; emits one Skip(DEPENDENCY_UNRESOLVED) per unresolved
  target entry (detail ``entry_guid=<g>``) and per unresolved lexeme
  (detail ``<field> component <guid> unresolved``). See
  contracts/post-pass-a.md.

- ``categories._run_171_subpass(context, target, tag=None)`` — reads
  ``context._run_plan.msa_slot_bindings`` (``{src_msa_guid: [src_slot_guid,
  ...]}``) plus ``plan.identity_remap``, then wires each MSA's SlotsRC in
  source order. See contracts/msa-slot-wiring.md.

Fakes expose the LOWERCASE ``.guid`` attribute that ``categories._guid_str_from``
reads host-free, and record every RS/RC ``Add`` so ordering can be asserted.
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
    """LCM reference sequence/collection stand-in: records Add calls in order."""

    def __init__(self, initial=()) -> None:
        self._items = list(initial)
        self.add_log = []  # ordered list of added objects

    def Add(self, obj):
        self._items.append(obj)
        self.add_log.append(obj)

    def __iter__(self):
        return iter(self._items)

    @property
    def Count(self):
        return len(self._items)


class _FakeObj:
    """Anything addressed by GUID (lexeme entry, slot, MSA target)."""

    def __init__(self, guid: str) -> None:
        self.guid = guid


class _FakeEntryRef:
    def __init__(self, components=(), primaries=()) -> None:
        self.ComponentLexemesRS = _FakeRefSeq(initial=components)
        self.PrimaryLexemesRS = _FakeRefSeq(initial=primaries)


class _FakeTargetEntry:
    def __init__(self, guid: str, entry_refs=()) -> None:
        self.guid = guid
        self.EntryRefsOS = list(entry_refs)


class _FakeTargetMSA:
    def __init__(self, guid: str, prewired=()) -> None:
        self.guid = guid
        self.SlotsRC = _FakeRefSeq(initial=prewired)


class _FakeTarget:
    """Target project handle exposing get_object_by_guid over a registry."""

    def __init__(self, objects_by_guid=None) -> None:
        self._objs = dict(objects_by_guid or {})

    def get_object_by_guid(self, guid):
        return self._objs.get(guid)


def _make_ctx() -> RunContext:
    return RunContext(
        source_handle=object(),
        source_project_name="Src",
        source_project_path="/src",
        target_handle=object(),
        target_project_name="Tgt",
        target_project_path="/tgt",
        run_id="GT-20260706-000000",
        started_at="2026-07-06T00:00:00",
    )


def _ctx_post_pass_a(lexentry_ref_bindings, in_plan_entries=None) -> RunContext:
    ctx = _make_ctx()
    plan = types.SimpleNamespace(
        lexentry_ref_bindings=dict(lexentry_ref_bindings),
        in_plan_entries=dict(in_plan_entries or {}),
    )
    object.__setattr__(ctx, "_run_plan", plan)
    return ctx


def _ctx_171(msa_slot_bindings, identity_remap=None) -> RunContext:
    ctx = _make_ctx()
    plan = types.SimpleNamespace(
        msa_slot_bindings=dict(msa_slot_bindings),
        identity_remap=dict(identity_remap or {}),
    )
    object.__setattr__(ctx, "_run_plan", plan)
    return ctx


# ============================================================================
# post-pass A — LexEntryRef component/primary lexeme wiring
# ============================================================================

def test_post_pass_a_wires_component_lexemes_in_order() -> None:
    """Two component lexemes → 2 ComponentLexemesRS.Add in source order."""
    ref = _FakeEntryRef()
    entry = _FakeTargetEntry("entry-1", entry_refs=[ref])
    lex_a, lex_b = _FakeObj("lex-a"), _FakeObj("lex-b")
    target = _FakeTarget({"entry-1": entry, "lex-a": lex_a, "lex-b": lex_b})
    ctx = _ctx_post_pass_a(
        {"entry-1": {"ComponentLexemesRS": ["lex-a", "lex-b"]}}
    )

    skips = categories._run_post_pass_a(ctx, target, tag=None)

    assert skips == []
    assert ref.ComponentLexemesRS.add_log == [lex_a, lex_b]
    assert ref.PrimaryLexemesRS.add_log == []


def test_post_pass_a_wires_both_fields() -> None:
    """ComponentLexemesRS and PrimaryLexemesRS both wired from the binding."""
    ref = _FakeEntryRef()
    entry = _FakeTargetEntry("entry-1", entry_refs=[ref])
    comp, prim = _FakeObj("comp"), _FakeObj("prim")
    target = _FakeTarget({"entry-1": entry, "comp": comp, "prim": prim})
    ctx = _ctx_post_pass_a({
        "entry-1": {
            "ComponentLexemesRS": ["comp"],
            "PrimaryLexemesRS": ["prim"],
        }
    })

    skips = categories._run_post_pass_a(ctx, target, tag=None)

    assert skips == []
    assert ref.ComponentLexemesRS.add_log == [comp]
    assert ref.PrimaryLexemesRS.add_log == [prim]


def test_post_pass_a_resolves_via_in_plan_entries_first() -> None:
    """A lexeme in the in-plan creation list is used before target lookup."""
    ref = _FakeEntryRef()
    entry = _FakeTargetEntry("entry-1", entry_refs=[ref])
    in_plan_lex = _FakeObj("lex-x")
    # Deliberately absent from the target registry: must resolve via in_plan.
    target = _FakeTarget({"entry-1": entry})
    ctx = _ctx_post_pass_a(
        {"entry-1": {"ComponentLexemesRS": ["lex-x"]}},
        in_plan_entries={"lex-x": in_plan_lex},
    )

    skips = categories._run_post_pass_a(ctx, target, tag=None)

    assert skips == []
    assert ref.ComponentLexemesRS.add_log == [in_plan_lex]


def test_post_pass_a_unresolved_target_entry() -> None:
    """Target entry missing → 1 Skip with entry_guid=<g> detail, no writes."""
    target = _FakeTarget({})  # entry-missing absent
    ctx = _ctx_post_pass_a(
        {"entry-missing": {"ComponentLexemesRS": ["lex-a"]}}
    )

    skips = categories._run_post_pass_a(ctx, target, tag=None)

    assert len(skips) == 1
    assert skips[0].reason == SkipReason.DEPENDENCY_UNRESOLVED
    assert "entry_guid=entry-missing" in skips[0].detail


def test_post_pass_a_unresolved_component_lexeme() -> None:
    """One component missing → 1 Add + 1 Skip('<field> component <guid> unresolved')."""
    ref = _FakeEntryRef()
    entry = _FakeTargetEntry("entry-1", entry_refs=[ref])
    present = _FakeObj("present")
    target = _FakeTarget({"entry-1": entry, "present": present})  # "gone" absent
    ctx = _ctx_post_pass_a(
        {"entry-1": {"ComponentLexemesRS": ["present", "gone"]}}
    )

    skips = categories._run_post_pass_a(ctx, target, tag=None)

    assert ref.ComponentLexemesRS.add_log == [present]
    assert len(skips) == 1
    assert skips[0].reason == SkipReason.DEPENDENCY_UNRESOLVED
    assert skips[0].detail == "ComponentLexemesRS component gone unresolved"


def test_post_pass_a_idempotent_rerun() -> None:
    """Pre-wired ref + same binding → 0 net writes, 0 skips (membership guard)."""
    lex_a = _FakeObj("lex-a")
    ref = _FakeEntryRef(components=[lex_a])  # already wired
    entry = _FakeTargetEntry("entry-1", entry_refs=[ref])
    target = _FakeTarget({"entry-1": entry, "lex-a": lex_a})
    ctx = _ctx_post_pass_a(
        {"entry-1": {"ComponentLexemesRS": ["lex-a"]}}
    )

    skips = categories._run_post_pass_a(ctx, target, tag=None)

    assert skips == []
    assert ref.ComponentLexemesRS.add_log == []  # no re-Add
    assert ref.ComponentLexemesRS.Count == 1


def test_post_pass_a_empty_bindings_noop() -> None:
    """Empty plan bindings → no work, empty skip list."""
    ctx = _ctx_post_pass_a({})
    assert categories._run_post_pass_a(ctx, _FakeTarget({}), tag=None) == []


def test_post_pass_a_falls_back_to_context_attrs_without_run_plan() -> None:
    """No _run_plan → reads context._lexentry_ref_bindings + _in_plan_entries."""
    ref = _FakeEntryRef()
    entry = _FakeTargetEntry("entry-1", entry_refs=[ref])
    lex_a = _FakeObj("lex-a")
    target = _FakeTarget({"entry-1": entry, "lex-a": lex_a})
    ctx = _make_ctx()  # no _run_plan attached
    object.__setattr__(
        ctx, "_lexentry_ref_bindings",
        {"entry-1": {"ComponentLexemesRS": ["lex-a"]}},
    )

    skips = categories._run_post_pass_a(ctx, target, tag=None)

    assert skips == []
    assert ref.ComponentLexemesRS.add_log == [lex_a]


def test_post_pass_a_preserves_source_order_across_fields() -> None:
    """Multiple components in a field keep source order."""
    ref = _FakeEntryRef()
    entry = _FakeTargetEntry("entry-1", entry_refs=[ref])
    l1, l2, l3 = _FakeObj("l1"), _FakeObj("l2"), _FakeObj("l3")
    target = _FakeTarget(
        {"entry-1": entry, "l1": l1, "l2": l2, "l3": l3}
    )
    ctx = _ctx_post_pass_a(
        {"entry-1": {"ComponentLexemesRS": ["l3", "l1", "l2"]}}
    )

    categories._run_post_pass_a(ctx, target, tag=None)

    assert ref.ComponentLexemesRS.add_log == [l3, l1, l2]


# ============================================================================
# 17.1 MSA-slot sub-pass
# ============================================================================

def test_171_wires_slots_in_order() -> None:
    """MSA with 3 slot bindings → 3 SlotsRC.Add in source order."""
    msa = _FakeTargetMSA("msa-1")
    s1, s2, s3 = _FakeObj("a"), _FakeObj("b"), _FakeObj("c")
    target = _FakeTarget({"msa-1": msa, "a": s1, "b": s2, "c": s3})
    ctx = _ctx_171({"msa-1": ["a", "b", "c"]})

    skips = categories._run_171_subpass(ctx, target, tag=None)

    assert skips == []
    assert msa.SlotsRC.add_log == [s1, s2, s3]


def test_171_resolves_msa_via_identity_remap() -> None:
    """Source MSA guid remapped to the created target MSA guid."""
    msa = _FakeTargetMSA("msa-new")
    slot = _FakeObj("slot-1")
    target = _FakeTarget({"msa-new": msa, "slot-1": slot})
    ctx = _ctx_171({"msa-src": ["slot-1"]}, identity_remap={"msa-src": "msa-new"})

    skips = categories._run_171_subpass(ctx, target, tag=None)

    assert skips == []
    assert msa.SlotsRC.add_log == [slot]


def test_171_unresolved_msa() -> None:
    """MSA absent from target → 1 Skip carrying msa_guid=<g> detail."""
    slot = _FakeObj("slot-1")
    target = _FakeTarget({"slot-1": slot})  # msa absent
    ctx = _ctx_171({"msa-missing": ["slot-1"]})

    skips = categories._run_171_subpass(ctx, target, tag=None)

    assert len(skips) == 1
    assert skips[0].reason == SkipReason.DEPENDENCY_UNRESOLVED
    assert "msa_guid=msa-missing" in skips[0].detail


def test_171_unresolved_slot() -> None:
    """One slot missing → 1 Add + 1 Skip carrying the slot guid."""
    msa = _FakeTargetMSA("msa-1")
    present = _FakeObj("present")
    target = _FakeTarget({"msa-1": msa, "present": present})  # "missing" absent
    ctx = _ctx_171({"msa-1": ["present", "missing"]})

    skips = categories._run_171_subpass(ctx, target, tag=None)

    assert msa.SlotsRC.add_log == [present]
    assert len(skips) == 1
    assert skips[0].reason == SkipReason.DEPENDENCY_UNRESOLVED
    assert "missing" in skips[0].detail


def test_171_idempotent_rerun() -> None:
    """Pre-wired MSA + same plan → 0 net writes, 0 skips."""
    slot = _FakeObj("slot-1")
    msa = _FakeTargetMSA("msa-1", prewired=[slot])
    target = _FakeTarget({"msa-1": msa, "slot-1": slot})
    ctx = _ctx_171({"msa-1": ["slot-1"]})

    skips = categories._run_171_subpass(ctx, target, tag=None)

    assert skips == []
    assert msa.SlotsRC.add_log == []
    assert msa.SlotsRC.Count == 1


def test_171_empty_bindings_noop() -> None:
    """Empty plan bindings → no work, empty skip list."""
    ctx = _ctx_171({})
    assert categories._run_171_subpass(ctx, _FakeTarget({}), tag=None) == []


def test_171_skips_are_skip_instances() -> None:
    """Returned skips are model Skip objects (not tuples/strings)."""
    ctx = _ctx_171({"msa-missing": ["slot-1"]})
    skips = categories._run_171_subpass(ctx, _FakeTarget({}), tag=None)
    assert skips and all(isinstance(s, Skip) for s in skips)


# ============================================================================
# Live-repo fallback (issue #28) — both passes must resolve GUIDs through
# `_resolve_target_by_guid`, which falls back to the LCM object repository on
# a live flexicon FLExProject (which has NO `get_object_by_guid`). These tests
# drive each pass end-to-end against a live-style target so the fallback branch
# is exercised THROUGH the pass, not just via the resolver in isolation — the
# coverage gap that let the 031-shaped bug ship in these two passes.
# ============================================================================

class _FakeRepo:
    """LCM ICmObjectRepository stand-in: IsValidObjectId + GetObject over a map."""

    def __init__(self, objects_by_guid=None) -> None:
        self._objs = dict(objects_by_guid or {})

    def IsValidObjectId(self, guid):
        # guid arrives as the ("parsed", <str>) tuple from the stub Guid.Parse.
        return self._key(guid) in self._objs

    def GetObject(self, guid):
        return self._objs.get(self._key(guid))

    @staticmethod
    def _key(guid):
        return guid[1] if isinstance(guid, tuple) else guid


class _FakeLiveTarget:
    """Mirrors the live flexicon FLExProject: exposes ObjectRepository() but
    NO get_object_by_guid, so `_resolve_target_by_guid` must take the live
    LCM-repo fallback branch."""

    def __init__(self, objects_by_guid=None) -> None:
        self._repo = _FakeRepo(objects_by_guid)

    def ObjectRepository(self, iface):
        return self._repo


@pytest.fixture
def _stub_lcm_and_system():
    """Stub SIL.LCModel + System so `_resolve_target_by_guid`'s live branch
    imports resolve offline (mirrors test_031_infl_feature_linking)."""
    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.ICmObjectRepository = object()
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    original_lcm = sys.modules.get("SIL.LCModel")
    sys.modules["SIL.LCModel"] = fake_lcm

    fake_system = types.ModuleType("System")
    fake_system.Guid = type(
        "FakeGuid", (), {"Parse": staticmethod(lambda s: ("parsed", s))}
    )
    original_system = sys.modules.get("System")
    sys.modules["System"] = fake_system

    yield

    if original_lcm is None:
        sys.modules.pop("SIL.LCModel", None)
    else:
        sys.modules["SIL.LCModel"] = original_lcm
    if original_system is None:
        sys.modules.pop("System", None)
    else:
        sys.modules["System"] = original_system


def test_171_wires_via_live_repo_fallback(_stub_lcm_and_system) -> None:
    """_run_171_subpass wires MSA->slot on a live-style target (no getter),
    proving it routes through the LCM-repo fallback (issue #28)."""
    msa = _FakeTargetMSA("msa-1")
    slot = _FakeObj("slot-1")
    target = _FakeLiveTarget({"msa-1": msa, "slot-1": slot})
    ctx = _ctx_171({"msa-1": ["slot-1"]})

    skips = categories._run_171_subpass(ctx, target, tag=None)

    assert skips == []
    assert msa.SlotsRC.add_log == [slot]


def test_post_pass_a_wires_via_live_repo_fallback(_stub_lcm_and_system) -> None:
    """_run_post_pass_a wires LexEntryRef component/primary on a live-style
    target (no getter), proving the LCM-repo fallback path (issue #28)."""
    ref = _FakeEntryRef()
    entry = _FakeTargetEntry("entry-1", entry_refs=[ref])
    comp, prim = _FakeObj("comp"), _FakeObj("prim")
    target = _FakeLiveTarget({"entry-1": entry, "comp": comp, "prim": prim})
    ctx = _ctx_post_pass_a({
        "entry-1": {
            "ComponentLexemesRS": ["comp"],
            "PrimaryLexemesRS": ["prim"],
        }
    })

    skips = categories._run_post_pass_a(ctx, target, tag=None)

    assert skips == []
    assert ref.ComponentLexemesRS.add_log == [comp]
    assert ref.PrimaryLexemesRS.add_log == [prim]


# ============================================================================
# Live-object CAST path (issue #28 layer 2) — `_resolve_target_by_guid` returns
# a bare ICmObject on the live target, whose typed members (.SlotsRC,
# .EntryRefsOS, .ComponentLexemesRS/.PrimaryLexemesRS) are invisible until the
# object is cast to the declaring interface. MCP-confirmed: uncast
# `.EntryRefsOS` -> None; `ILexEntry(obj).EntryRefsOS` -> the sequence. These
# fakes reproduce that: a `_Bare` object hides typed members (attribute access
# raises / getattr -> None, exactly like live pythonnet) and only the stubbed
# interface cast surfaces the typed `_view`. Without the cast fix both passes
# silently no-op (171 raises AttributeError -> swallowed; post-pass A wires 0).
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


def _iface_cast(name):
    """A stub SIL.LCModel interface: `IFoo(bare)` -> bare._views['IFoo']."""
    def cast(obj):
        return getattr(obj, "_views", {}).get(name, obj)
    return cast


@pytest.fixture
def _stub_lcm_with_interfaces():
    """Stub SIL.LCModel + System with the interface casts the passes use, so
    `_cast_lcm` surfaces the typed view of a bare live object offline."""
    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.ICmObjectRepository = object()
    for iface in ("IMoInflAffMsa", "IMoInflAffixSlot", "ILexEntry", "ILexEntryRef"):
        setattr(fake_lcm, iface, _iface_cast(iface))
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    original_lcm = sys.modules.get("SIL.LCModel")
    sys.modules["SIL.LCModel"] = fake_lcm

    fake_system = types.ModuleType("System")
    fake_system.Guid = type(
        "FakeGuid", (), {"Parse": staticmethod(lambda s: ("parsed", s))}
    )
    original_system = sys.modules.get("System")
    sys.modules["System"] = fake_system

    yield

    if original_lcm is None:
        sys.modules.pop("SIL.LCModel", None)
    else:
        sys.modules["SIL.LCModel"] = original_lcm
    if original_system is None:
        sys.modules.pop("System", None)
    else:
        sys.modules["System"] = original_system


def test_171_casts_bare_msa_and_slot(_stub_lcm_with_interfaces) -> None:
    """171 sub-pass casts the bare resolved MSA/slot so SlotsRC is reachable;
    without the cast, `bare.SlotsRC` would raise (silently swallowed live)."""
    slot_view = _Typed("slot-1")
    slot_bare = _Bare("slot-1", views={"IMoInflAffixSlot": slot_view})
    msa_slots = _FakeRefSeq()
    msa_view = _Typed("msa-1", SlotsRC=msa_slots)
    msa_bare = _Bare("msa-1", views={"IMoInflAffMsa": msa_view})
    target = _FakeLiveTarget({"msa-1": msa_bare, "slot-1": slot_bare})
    ctx = _ctx_171({"msa-1": ["slot-1"]})

    skips = categories._run_171_subpass(ctx, target, tag=None)

    assert skips == []
    assert msa_slots.add_log == [slot_view]  # the CAST slot was wired


def test_post_pass_a_casts_bare_entry_and_ref(_stub_lcm_with_interfaces) -> None:
    """post-pass A casts the bare resolved entry (-> EntryRefsOS) and each ref
    (-> ComponentLexemesRS/PrimaryLexemesRS); without the casts getattr yields
    None and the pass wires 0 (the live #28 layer-2 no-op)."""
    comp_seq = _FakeRefSeq()
    ref_view = _Typed("ref-1", ComponentLexemesRS=comp_seq,
                      PrimaryLexemesRS=_FakeRefSeq())
    ref_bare = _Bare("ref-1", views={"ILexEntryRef": ref_view})
    entry_view = _Typed("entry-1", EntryRefsOS=[ref_bare])
    entry_bare = _Bare("entry-1", views={"ILexEntry": entry_view})
    comp = _FakeObj("comp")
    target = _FakeLiveTarget({"entry-1": entry_bare, "comp": comp})
    ctx = _ctx_post_pass_a({"entry-1": {"ComponentLexemesRS": ["comp"]}})

    skips = categories._run_post_pass_a(ctx, target, tag=None)

    assert skips == []
    assert comp_seq.add_log == [comp]  # wired into the CAST ref's sequence


# ---- _cast_lcm unit coverage ------------------------------------------------

def test_cast_lcm_none_returns_none() -> None:
    assert categories._cast_lcm(None, "ILexEntry") is None


def test_cast_lcm_passthrough_when_interface_absent() -> None:
    """No SIL.LCModel (or no such interface) -> object returned unchanged
    (the offline duck-typed fake path)."""
    fake = _FakeObj("x")
    sys.modules.pop("SIL.LCModel", None)  # ensure import fails
    assert categories._cast_lcm(fake, "ILexEntry") is fake


def test_cast_lcm_invokes_interface_when_present(_stub_lcm_with_interfaces) -> None:
    view = _Typed("v")
    bare = _Bare("v", views={"ILexEntry": view})
    assert categories._cast_lcm(bare, "ILexEntry") is view


def test_cast_lcm_falls_back_when_cast_raises() -> None:
    """A cast that raises (already-correct type / uncastable) -> return obj."""
    fake_lcm = types.ModuleType("SIL.LCModel")

    def _boom(_obj):
        raise TypeError("cannot cast")

    fake_lcm.ILexEntry = _boom
    original = sys.modules.get("SIL.LCModel")
    sys.modules["SIL.LCModel"] = fake_lcm
    try:
        obj = _FakeObj("y")
        assert categories._cast_lcm(obj, "ILexEntry") is obj
    finally:
        if original is None:
            sys.modules.pop("SIL.LCModel", None)
        else:
            sys.modules["SIL.LCModel"] = original
