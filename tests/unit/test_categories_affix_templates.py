"""Unit tests for Phase 3c US2 affix-template functions + 17.1 sub-pass.

Covers:
- T034 template slot-ref wiring (via dependencies in source order) + collision.
- T035 17.1 basic wiring — 1 MSA / 1 slot → 1 SlotsRC write.
- T036 17.1 multi-slot per MSA — 3 bindings → 3 Adds in source order.
- T037 17.1 unresolved slot — 1 Add + 1 Skip(DEPENDENCY_UNRESOLVED).
- T038 17.1 unresolved MSA — 1 Skip with msa_guid detail.
- T039 17.1 idempotent rerun — pre-wired target → 0 net writes, 0 new skips.
- T040 17.1 unbound affix — empty source SlotsRC → no binding stashed.

The 17.1 sub-pass (`_run_171_subpass`) is pure-Python over `plan.msa_slot_bindings`
+ `plan.identity_remap`, resolving target objects through the `get_object_by_guid`
hook — so it runs host-free with duck-typed fakes.
"""
from __future__ import annotations

import types

import pytest

# THE MODULE-LEVEL `xfail` MARK IS GONE (feature 038, T069).
#
# It was added when Phase 3c T051 template leaf-dispatch and the 17.1 sub-pass
# were still `raise NotImplementedError` stubs, and it said so in its own
# comment: "they auto-flip to xpass once implemented, at which point this mark
# should be removed." T051 landed; the mark did not. Every one of the 10 tests
# in this file was XPASSING, and a non-strict xfail that xpasses is a test that
# CANNOT FAIL -- pytest reports XPASS, the run stays green, and no gate
# notices.
#
# That was measured, not inferred. T069 registers a `CLOSURE_EDGES_VERIFIED`
# row on `affix_templates_dependencies`, so its mutation verification broke the
# producer on purpose: with the five `*SlotsRS` sequences unread,
# `test_template_dependencies_cover_all_five_ref_seqs` and
# `test_template_dependencies_yield_slot_refs_in_source_order` flipped from
# XPASS to XFAIL -- and `tests/unit` still reported "3426 passed" with zero
# failures. The only signal was two counters moving in a summary line.
#
# A registry row whose producer's entire unit coverage cannot fail is the
# hollow-assertion pattern this feature keeps finding elsewhere, so the mark is
# removed rather than re-pointed at a newer excuse. All 10 tests pass on their
# own merits.

from gramtrans.Lib import categories
from gramtrans.Lib.models import (
    AffixSlotLinkOutcome,
    GrammarCategory,
    PlannedAction,
    RunContext,
    Skip,
    SkipReason,
    WSMapping,
)


# ============================================================================
# Fakes
# ============================================================================

class _FakeRefColl:
    """LCM reference-collection stand-in: records Add calls in order."""

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


class _FakeSlotObj:
    def __init__(self, guid: str) -> None:
        self.guid = guid


class _FakeTargetMSA:
    def __init__(self, guid: str, prewired=()) -> None:
        self.guid = guid
        self.SlotsRC = _FakeRefColl(initial=prewired)


class _FakeTemplateSrc:
    """Source affix template carrying slot ref sequences + owner."""

    def __init__(self, guid, owner_guid, prefix=(), suffix=(), enclitic=(),
                 proclitic=(), slots=()) -> None:
        self.guid = guid
        self.Owner = _FakeSlotObj(owner_guid)  # any object exposing .guid
        self.PrefixSlotsRS = list(prefix)
        self.SuffixSlotsRS = list(suffix)
        self.EncliticSlotsRS = list(enclitic)
        self.ProcliticSlotsRS = list(proclitic)
        self.SlotsRS = list(slots)


class _FakeTarget171:
    """Target exposing get_object_by_guid over a fixed registry."""

    def __init__(self, objects_by_guid) -> None:
        self._objs = dict(objects_by_guid)

    def get_object_by_guid(self, guid):
        return self._objs.get(guid)


def _ctx_with_plan(msa_slot_bindings, identity_remap=None,
                   msa_owner_entry=None) -> RunContext:
    ctx = RunContext(
        source_handle=object(),
        source_project_name="Src",
        source_project_path="/src",
        target_handle=object(),
        target_project_name="Tgt",
        target_project_path="/tgt",
        run_id="GT-20260628-020000",
        started_at="2026-06-28T02:00:00",
    )
    plan = types.SimpleNamespace(
        msa_slot_bindings=dict(msa_slot_bindings),
        identity_remap=dict(identity_remap or {}),
        # T074 (FR-019): owner map, absent by default -- see the docstring on
        # `test_171_unresolved_msa_is_only_a_failure_when_the_affix_is_here`.
        msa_owner_entry=dict(msa_owner_entry or {}),
    )
    object.__setattr__(ctx, "_run_plan", plan)
    return ctx


_BUNDLE = categories.for_category(GrammarCategory.AFFIX_TEMPLATES)


# ============================================================================
# T034 — template slot-ref wiring (dependencies in source order) + collision
# ============================================================================

def test_template_dependencies_yield_slot_refs_in_source_order() -> None:
    """2 prefix slots + 1 suffix slot → SLOTS deps in source order (+ owner POS)."""
    tpl = _FakeTemplateSrc(
        "tpl-1", owner_guid="pos-verb",
        prefix=[_FakeSlotObj("slot-p1"), _FakeSlotObj("slot-p2")],
        suffix=[_FakeSlotObj("slot-s1")],
    )
    deps = list(_BUNDLE["dependencies"](piece=tpl))

    assert (GrammarCategory.GRAM_CATEGORIES, "pos-verb") in deps
    slot_deps = [g for (c, g) in deps if c == GrammarCategory.SLOTS]
    # Prefix slots precede suffix slot, both in source order.
    assert slot_deps == ["slot-p1", "slot-p2", "slot-s1"]


def test_template_dependencies_cover_all_five_ref_seqs() -> None:
    tpl = _FakeTemplateSrc(
        "tpl-2", owner_guid="pos-verb",
        prefix=[_FakeSlotObj("p")],
        suffix=[_FakeSlotObj("s")],
        enclitic=[_FakeSlotObj("e")],
        proclitic=[_FakeSlotObj("c")],
        slots=[_FakeSlotObj("x")],
    )
    slot_deps = [g for (c, g) in _BUNDLE["dependencies"](piece=tpl)
                 if c == GrammarCategory.SLOTS]
    assert slot_deps == ["p", "s", "e", "c", "x"]


def test_template_plan_action_collision_already_present() -> None:
    """Template GUID already under a target POS → Skip(ALREADY_PRESENT_BY_GUID)."""
    src_tpl = _FakeTemplateSrc("tpl-dup", owner_guid="pos-verb")

    class _POS:
        def __init__(self, tpls):
            self.AffixTemplatesOS = list(tpls)

        @property
        def concrete(self):
            return self

    class _POSOps:
        def __init__(self, poses):
            self._p = poses

        def GetAll(self, recursive=True):
            return self._p

    class _Proj:
        def __init__(self, poses):
            self.POS = _POSOps(poses)

    tgt = _Proj([_POS([_FakeTemplateSrc("tpl-dup", owner_guid="pos-verb")])])
    ctx = RunContext(
        source_handle=_Proj([]), source_project_name="s", source_project_path="/s",
        target_handle=tgt, target_project_name="t", target_project_path="/t",
        run_id="GT-1", started_at="t",
    )
    result = _BUNDLE["plan_action"](piece=src_tpl, context=ctx, ws_mapping=WSMapping())
    assert isinstance(result, Skip)
    assert result.reason == SkipReason.ALREADY_PRESENT_BY_GUID


# ============================================================================
# T035-T039 — 17.1 MSA-slot wiring sub-pass
# ============================================================================

def test_171_basic_wiring() -> None:
    """T035: 1 MSA with 1 slot binding → 1 SlotsRC.Add."""
    msa = _FakeTargetMSA("msa-1")
    slot = _FakeSlotObj("slot-1")
    target = _FakeTarget171({"msa-1": msa, "slot-1": slot})
    ctx = _ctx_with_plan({"msa-1": ["slot-1"]})

    skips = categories._run_171_subpass(ctx, target, tag=None)

    assert skips == []
    assert msa.SlotsRC.add_log == [slot]


def test_171_multi_slot_per_msa() -> None:
    """T036: 1 MSA with 3 slot bindings → 3 Adds in source order."""
    msa = _FakeTargetMSA("msa-1")
    s1, s2, s3 = _FakeSlotObj("a"), _FakeSlotObj("b"), _FakeSlotObj("c")
    target = _FakeTarget171({"msa-1": msa, "a": s1, "b": s2, "c": s3})
    ctx = _ctx_with_plan({"msa-1": ["a", "b", "c"]})

    skips = categories._run_171_subpass(ctx, target, tag=None)

    assert skips == []
    assert msa.SlotsRC.add_log == [s1, s2, s3]


def test_171_unresolved_slot() -> None:
    """T037: 2 slots stashed, 1 missing → 1 Add + 1 Skip(DEPENDENCY_UNRESOLVED)."""
    msa = _FakeTargetMSA("msa-1")
    s1 = _FakeSlotObj("present")
    target = _FakeTarget171({"msa-1": msa, "present": s1})  # "missing" absent
    ctx = _ctx_with_plan({"msa-1": ["present", "missing"]})

    skips = categories._run_171_subpass(ctx, target, tag=None)

    assert msa.SlotsRC.add_log == [s1]
    assert len(skips) == 1
    assert skips[0].reason == SkipReason.DEPENDENCY_UNRESOLVED
    assert "missing" in skips[0].detail


def test_171_unresolved_msa_is_only_a_failure_when_the_affix_is_here() -> None:
    """T038, re-pointed by T074 (FR-019): an absent MSA is a failure to link
    only if its OWNING AFFIX is in the destination.

    T038 asserted the skip unconditionally. That is what let the report claim
    203 link failures on a run that transferred no affixes at all (measured,
    `Mbugwe LizzieHC practice`, AFFIX_TEMPLATES-only) -- every one of them
    about a source affix the run never touched. Both branches are asserted here
    so the fix cannot decay into "emit fewer skips": the affix-absent case is
    recorded as NOT_IN_RUN and reports nothing, the affix-present case still
    reports, and now names the affix rather than the missing MSA.
    """
    slot = _FakeSlotObj("slot-1")

    # (a) the affix is NOT in the destination -- nothing was promised.
    ctx_absent = _ctx_with_plan({"msa-missing": ["slot-1"]},
                                msa_owner_entry={"msa-missing": "entry-gone"})
    skips_absent = categories._run_171_subpass(
        ctx_absent, _FakeTarget171({"slot-1": slot}), tag=None)
    assert skips_absent == []
    records = list(getattr(ctx_absent, "_affix_slot_links", []))
    assert [r.outcome for r in records] == [AffixSlotLinkOutcome.NOT_IN_RUN]

    # (b) the affix IS in the destination -- a real, uniquely-reported loss.
    entry = _FakeSlotObj("entry-here")
    ctx_present = _ctx_with_plan({"msa-missing": ["slot-1"]},
                                 msa_owner_entry={"msa-missing": "entry-here"})
    skips_present = categories._run_171_subpass(
        ctx_present,
        _FakeTarget171({"slot-1": slot, "entry-here": entry}), tag=None)
    assert len(skips_present) == 1
    assert skips_present[0].reason == SkipReason.DEPENDENCY_UNRESOLVED
    assert skips_present[0].source_guid == "entry-here"
    assert "msa_guid=msa-missing" in skips_present[0].detail
    records = list(getattr(ctx_present, "_affix_slot_links", []))
    assert [r.outcome for r in records] == [AffixSlotLinkOutcome.MSA_MISSING]


def test_171_resolves_msa_via_identity_remap() -> None:
    """MSA resolved through identity_remap (source guid != target guid)."""
    msa = _FakeTargetMSA("msa-new")
    slot = _FakeSlotObj("slot-1")
    target = _FakeTarget171({"msa-new": msa, "slot-1": slot})
    ctx = _ctx_with_plan({"msa-src": ["slot-1"]}, identity_remap={"msa-src": "msa-new"})

    skips = categories._run_171_subpass(ctx, target, tag=None)

    assert skips == []
    assert msa.SlotsRC.add_log == [slot]


def test_171_idempotent_rerun() -> None:
    """T039: pre-wired target + same plan → 0 net writes, 0 new skips."""
    slot = _FakeSlotObj("slot-1")
    msa = _FakeTargetMSA("msa-1", prewired=[slot])  # already wired
    target = _FakeTarget171({"msa-1": msa, "slot-1": slot})
    ctx = _ctx_with_plan({"msa-1": ["slot-1"]})

    skips = categories._run_171_subpass(ctx, target, tag=None)

    assert skips == []
    assert msa.SlotsRC.add_log == []  # membership guard suppressed the Add
    assert msa.SlotsRC.Count == 1     # still exactly one slot


# ============================================================================
# T040 — unbound affix (no binding stashed for empty source SlotsRC)
# ============================================================================

def test_171_unbound_affix() -> None:
    """T040: source MSA with empty SlotsRC → no entry in plan.msa_slot_bindings;
    the 17.1 pass produces no wires and no skips (matches Ejagham Mini `ro~-`)."""
    affixes = categories.for_category(GrammarCategory.AFFIXES)

    class _FakeMorphType:
        IsAffixType = True

    class _FakeForm:
        MorphTypeRA = _FakeMorphType()

    class _FakeMSA:
        def __init__(self, guid):
            self.guid = guid
            self.SlotsRC = []  # unbound

    class _FakeEntry:
        def __init__(self):
            self.guid = "entry-unbound"
            self.LexemeFormOA = _FakeForm()
            self.MorphoSyntaxAnalysesOC = [_FakeMSA("msa-ro")]
            self.EntryRefsOS = []

    class _Cache:
        LangProject = types.SimpleNamespace(
            LexDbOA=types.SimpleNamespace(EntriesOC=[])
        )

    class _Tgt:
        Cache = _Cache()

    ctx = RunContext(
        source_handle=None, source_project_name="s", source_project_path="/s",
        target_handle=_Tgt(), target_project_name="t", target_project_path="/t",
        run_id="GT-1", started_at="t",
    )
    bindings: dict = {}
    object.__setattr__(ctx, "_msa_slot_bindings", bindings)
    object.__setattr__(ctx, "_lexentry_ref_bindings", {})

    result = affixes["plan_action"](_FakeEntry(), ctx, WSMapping())
    assert isinstance(result, PlannedAction)
    assert bindings == {}  # no binding stashed for the unbound MSA

    # And a 17.1 pass over the empty bindings does nothing.
    ctx2 = _ctx_with_plan(bindings)
    assert categories._run_171_subpass(ctx2, _FakeTarget171({}), tag=None) == []
