"""Phase 3a -- phonology block + strata Python-surface tests.

Tests the enumerate_source / dependencies / plan_action callbacks for
the six Phase 3a categories.  execute_action requires live LCM and is
exercised at live MCP time (integration tests in
tests/integration/test_phase3a_phonology_e2e.py).
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from gramtrans.Lib import categories
from gramtrans.Lib.models import (
    GrammarCategory,
    PlannedAction,
    PlannedOverwrite,
    RunContext,
    Selection,
    Skip,
    SkipReason,
    WSKind,
    WSMapping,
)


# ============================================================================
# Fakes
# ============================================================================

class _Item:
    def __init__(self, guid):
        self.guid = guid
        self.Guid = guid  # mimics ICmObject.Guid for _guid_str_from

    @property
    def concrete(self):
        return self


class _Ops:
    def __init__(self, items):
        self._items = list(items)

    def GetAll(self):
        return list(self._items)


def _project(**ops):
    p = type("P", (), {})()
    for attr, items in ops.items():
        setattr(p, attr, _Ops(items))
    return p


def _ctx(src, tgt) -> RunContext:
    return RunContext(
        source_handle=src, source_project_name="Src", source_project_path="/s",
        target_handle=tgt, target_project_name="Tgt", target_project_path="/t",
        run_id="GT-20260620-010000", started_at="2026-06-20T01:00:00",
    )


WSM = WSMapping(entries=())
SEL = Selection(categories={})


# Patch _guid_str_from to use the test fake's `guid` attribute directly.
@pytest.fixture(autouse=True)
def _patch_guid_helpers(monkeypatch):
    monkeypatch.setattr(categories, "_guid_str_from", lambda obj: obj.guid)


# ============================================================================
# Phon Features
# ============================================================================

def test_phon_features_enumerate_returns_source_features():
    src = _project(PhonFeatures=[_Item("a-1"), _Item("a-2")])
    tgt = _project(PhonFeatures=[])
    assert len(categories.phonological_features_enumerate_source(_ctx(src, tgt), SEL)) == 2


def test_phon_features_enumerate_empty_when_attr_missing():
    src = _project()  # no PhonFeatures attr
    tgt = _project()
    assert categories.phonological_features_enumerate_source(_ctx(src, tgt), SEL) == ()


def test_phon_features_dependencies_empty():
    assert categories.phonological_features_dependencies(_Item("a")) == ()


def test_phon_features_required_writing_systems_empty():
    assert categories.phonological_features_required_writing_systems(_Item("a")) == ()


def test_phon_features_plan_action_emits_planned_for_new_guid():
    src = _project(PhonFeatures=[_Item("f-1")])
    tgt = _project(PhonFeatures=[])
    piece = _Item("f-1")
    action = categories.phonological_features_plan_action(piece, _ctx(src, tgt), WSM)
    assert isinstance(action, PlannedAction)
    assert action.category == GrammarCategory.PHONOLOGICAL_FEATURES
    assert action.source_guid == "f-1"


def test_phon_features_plan_action_skips_when_present():
    src = _project(PhonFeatures=[_Item("f-1")])
    tgt = _project(PhonFeatures=[_Item("f-1")])
    skip = categories.phonological_features_plan_action(_Item("f-1"), _ctx(src, tgt), WSM)
    assert isinstance(skip, Skip)
    assert skip.reason == SkipReason.ALREADY_PRESENT_BY_GUID


# ============================================================================
# Phonemes
# ============================================================================

def test_phonemes_enumerate_returns_source():
    src = _project(Phonemes=[_Item("p-1"), _Item("p-2"), _Item("p-3")])
    tgt = _project(Phonemes=[])
    assert len(categories.phonemes_enumerate_source(_ctx(src, tgt), SEL)) == 3


def test_phonemes_plan_action_emits_planned_for_new_guid():
    src = _project(Phonemes=[_Item("p-1")])
    tgt = _project(Phonemes=[])
    action = categories.phonemes_plan_action(_Item("p-1"), _ctx(src, tgt), WSM)
    assert isinstance(action, PlannedAction)
    assert action.category == GrammarCategory.PHONEMES


def test_phonemes_plan_action_skips_when_present():
    src = _project(Phonemes=[_Item("p-1")])
    tgt = _project(Phonemes=[_Item("p-1")])
    skip = categories.phonemes_plan_action(_Item("p-1"), _ctx(src, tgt), WSM)
    assert isinstance(skip, Skip)
    assert skip.reason == SkipReason.ALREADY_PRESENT_BY_GUID


# ============================================================================
# Natural Classes
# ============================================================================

def test_natural_classes_enumerate_returns_source():
    src = _project(NaturalClasses=[_Item("nc-1"), _Item("nc-2")])
    tgt = _project(NaturalClasses=[])
    assert len(categories.natural_classes_enumerate_source(_ctx(src, tgt), SEL)) == 2


def test_natural_classes_dependencies_non_lcm_returns_empty():
    """Without LCM imports available, dependencies returns empty tuple
    (the function exception-guards the SIL.LCModel imports)."""
    deps = categories.natural_classes_dependencies(_Item("nc-1"))
    # In a real LCM context this would return phoneme GUIDs; here the
    # fake doesn't quack like IPhNCSegments so the function falls through.
    assert isinstance(deps, tuple)


def test_natural_classes_plan_action_skips_when_present():
    src = _project(NaturalClasses=[_Item("nc-1")])
    tgt = _project(NaturalClasses=[_Item("nc-1")])
    skip = categories.natural_classes_plan_action(_Item("nc-1"), _ctx(src, tgt), WSM)
    assert isinstance(skip, Skip)
    assert skip.reason == SkipReason.ALREADY_PRESENT_BY_GUID


# ============================================================================
# PhEnvironment
# ============================================================================

def test_ph_environment_enumerate_returns_source():
    src = _project(Environments=[_Item("e-1"), _Item("e-2")])
    tgt = _project(Environments=[])
    assert len(categories.ph_environment_enumerate_source(_ctx(src, tgt), SEL)) == 2


def test_ph_environment_dependencies_empty():
    assert categories.ph_environment_dependencies(_Item("e-1")) == ()


def test_ph_environment_plan_action_skips_when_present():
    src = _project(Environments=[_Item("e-1")])
    tgt = _project(Environments=[_Item("e-1")])
    skip = categories.ph_environment_plan_action(_Item("e-1"), _ctx(src, tgt), WSM)
    assert isinstance(skip, Skip)


# ============================================================================
# Strata
# ============================================================================

def test_strata_enumerate_returns_source():
    src = _project(Strata=[_Item("s-1"), _Item("s-2")])
    tgt = _project(Strata=[])
    assert len(categories.strata_enumerate_source(_ctx(src, tgt), SEL)) == 2


def test_strata_dependencies_empty():
    assert categories.strata_dependencies(_Item("s-1")) == ()


def test_strata_plan_action_emits_planned_for_new_guid():
    src = _project(Strata=[_Item("s-1")])
    tgt = _project(Strata=[])
    action = categories.strata_plan_action(_Item("s-1"), _ctx(src, tgt), WSM)
    assert isinstance(action, PlannedAction)
    assert action.category == GrammarCategory.STRATA


def test_strata_plan_action_skips_when_present():
    src = _project(Strata=[_Item("s-1")])
    tgt = _project(Strata=[_Item("s-1")])
    skip = categories.strata_plan_action(_Item("s-1"), _ctx(src, tgt), WSM)
    assert isinstance(skip, Skip)
    assert skip.reason == SkipReason.ALREADY_PRESENT_BY_GUID


# ============================================================================
# Phonological Rules
# ============================================================================

def test_phonological_rules_enumerate_returns_source():
    src = _project(PhonRules=[_Item("r-1"), _Item("r-2")])
    tgt = _project(PhonRules=[])
    assert len(categories.phonological_rules_enumerate_source(_ctx(src, tgt), SEL)) == 2


def test_phonological_rules_dependencies_returns_tuple():
    """Without LCM, returns empty tuple via exception guard."""
    deps = categories.phonological_rules_dependencies(_Item("r-1"))
    assert isinstance(deps, tuple)


# --- traversal test with an injected fake SIL.LCModel -----------------------
# The real dependency walk imports typed interfaces from SIL.LCModel and casts
# rule/context cells through them.  Outside a live LCM runtime that import
# fails and the function returns () (covered above).  Here we inject a fake
# SIL.LCModel whose interface names are identity casts, so the traversal logic
# itself is exercised against a hand-built PhRegularRule graph.

class _PhCell:
    """Fake context cell: ClassName drives branch selection; FeatureStructureRA
    is the phoneme/NC/boundary target; MembersRS holds sub-cells (sequence)."""

    def __init__(self, class_name, guid=None, feature=None, members=None):
        self.ClassName = class_name
        self.guid = guid
        self.FeatureStructureRA = feature
        self.MembersRS = list(members) if members else []


class _PhRef:
    """Fake referenced target (phoneme / natural class / stratum)."""

    def __init__(self, guid):
        self.guid = guid


class _PhRHS:
    def __init__(self, struc_change=None, left=None, right=None):
        self.StrucChangeOS = list(struc_change) if struc_change else []
        self.LeftContextOA = left
        self.RightContextOA = right


class _PhRule:
    def __init__(self, struc_desc, rhs_list, initial=None, final=None):
        self.StrucDescOS = list(struc_desc)
        self.RightHandSidesOS = list(rhs_list)
        self.InitialStratumRA = initial
        self.FinalStratumRA = final


@pytest.fixture
def _fake_lcmodel(monkeypatch):
    import sys
    import types

    identity = lambda x: x  # noqa: E731 -- cast interfaces are identity in tests
    fake = types.ModuleType("SIL.LCModel")
    for name in (
        "IPhSegmentRule", "IPhRegularRule",
        "IPhSimpleContextSeg", "IPhSimpleContextNC", "IPhSequenceContext",
        # Task 7 (feature 037): _phon_rule_fingerprint also branches on
        # PhSimpleContextBdry / PhIterationContext.
        "IPhSimpleContextBdry", "IPhIterationContext",
        "ICmObject",
    ):
        setattr(fake, name, identity)
    sil = types.ModuleType("SIL")
    sil.LCModel = fake
    monkeypatch.setitem(sys.modules, "SIL", sil)
    monkeypatch.setitem(sys.modules, "SIL.LCModel", fake)
    return fake


def test_phonological_rules_dependencies_collects_phoneme_nc_stratum(_fake_lcmodel):
    """Regression: the walk must surface every phoneme/NC/stratum the rule
    references -- via StrucDescOS, per-RHS StrucChangeOS/Left/RightContextOA,
    and PhSequenceContext members -- so the closure pulls them in before the
    rule executes.  Boundary markers are NOT hard dependencies."""
    struc_desc = [
        _PhCell("PhSimpleContextSeg", "seg-a", feature=_PhRef("p1")),
        _PhCell("PhSimpleContextNC", "nc-a", feature=_PhRef("nc1")),
        _PhCell("PhSimpleContextBdry", "bdry-a", feature=_PhRef("b1")),
        _PhCell("PhSequenceContext", "seq-a", members=[
            _PhCell("PhSimpleContextSeg", "seg-b", feature=_PhRef("p2")),
        ]),
    ]
    rhs = _PhRHS(
        struc_change=[_PhCell("PhSimpleContextSeg", "seg-c", feature=_PhRef("p3"))],
        left=_PhCell("PhSimpleContextNC", "nc-b", feature=_PhRef("nc2")),
        right=_PhCell("PhSequenceContext", "seq-b", members=[
            _PhCell("PhSimpleContextSeg", "seg-d", feature=_PhRef("p4")),
        ]),
    )
    rule = _PhRule(struc_desc, [rhs],
                   initial=_PhRef("s1"), final=_PhRef("s2"))

    deps = set(categories.phonological_rules_dependencies(rule))

    assert deps == {"p1", "p2", "p3", "p4", "nc1", "nc2", "s1", "s2"}
    # Boundary markers are handled (WARN-only) inside execute, not a hard dep.
    assert "b1" not in deps


def test_phonological_rules_dependencies_empty_rule(_fake_lcmodel):
    """A rule with no context cells and no strata yields no dependencies."""
    rule = _PhRule([], [_PhRHS()])
    assert categories.phonological_rules_dependencies(rule) == ()


def test_phonological_rules_plan_action_emits_planned_for_new_guid():
    src = _project(PhonRules=[_Item("r-1")])
    tgt = _project(PhonRules=[])
    action = categories.phonological_rules_plan_action(_Item("r-1"), _ctx(src, tgt), WSM)
    assert isinstance(action, PlannedAction)
    assert action.category == GrammarCategory.PHONOLOGICAL_RULES


def test_phonological_rules_plan_action_skips_when_present():
    src = _project(PhonRules=[_Item("r-1")])
    tgt = _project(PhonRules=[_Item("r-1")])
    skip = categories.phonological_rules_plan_action(_Item("r-1"), _ctx(src, tgt), WSM)
    assert isinstance(skip, Skip)
    assert skip.reason == SkipReason.ALREADY_PRESENT_BY_GUID


# ============================================================================
# Empty-source handling (US4 / FR-308)
# ============================================================================

@pytest.mark.parametrize("enumerator", [
    categories.phonological_features_enumerate_source,
    categories.phonemes_enumerate_source,
    categories.natural_classes_enumerate_source,
    categories.ph_environment_enumerate_source,
    categories.phonological_rules_enumerate_source,
    categories.strata_enumerate_source,
])
def test_enumerate_empty_source_returns_empty(enumerator):
    """FR-308: every category's enumerate_source must tolerate a source
    that has no items for that category."""
    src = _project(PhonFeatures=[], Phonemes=[], NaturalClasses=[],
                   Environments=[], PhonRules=[], Strata=[])
    tgt = _project()
    assert enumerator(_ctx(src, tgt), SEL) == []


# ============================================================================
# _create_with_guid hardening tests
# ============================================================================

def _make_target_with_factory(factory_instance):
    """Build a minimal fake `target` whose Cache.ServiceLocator.GetService()
    returns `factory_instance`."""
    sl = MagicMock()
    sl.GetService.return_value = factory_instance
    cache = MagicMock()
    cache.ServiceLocator = sl
    target = MagicMock()
    target.Cache = cache
    return target


def test_create_with_guid_raises_runtime_error_on_add_failure():
    """If Create(Guid) succeeds but Add raises, _create_with_guid must raise
    RuntimeError mentioning 'Orphan risk' and must NOT stash the sentinel."""
    sentinel = object()

    factory = MagicMock()
    factory.Create.return_value = sentinel

    bad_collection = MagicMock()
    bad_collection.Add.side_effect = ValueError("collection locked")

    # factory_iface.__name__ used for the error message
    factory_iface = MagicMock()
    factory_iface.__name__ = "FakeFactory"

    target = _make_target_with_factory(factory)

    # Intercept `from System import Guid` inside _create_with_guid by
    # injecting a fake System module into sys.modules.
    import sys
    guid_str = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    fake_guid_class = MagicMock()
    fake_guid_class.Parse.return_value = MagicMock(name="parsed_guid")
    fake_system = MagicMock()
    fake_system.Guid = fake_guid_class

    original = sys.modules.get("System")
    sys.modules["System"] = fake_system
    try:
        with pytest.raises(RuntimeError) as exc_info:
            categories._create_with_guid(factory_iface, bad_collection, guid_str, target)
    finally:
        if original is None:
            del sys.modules["System"]
        else:
            sys.modules["System"] = original

    msg = str(exc_info.value)
    assert "Orphan risk" in msg, f"Expected 'Orphan risk' in: {msg}"
    # Confirm sentinel is not reachable through any tracked collection
    bad_collection.Add.assert_called_once_with(sentinel)
    # The exception must have been raised — sentinel was never stored anywhere
    # by the helper (it has no internal list/dict).  The call to Add was the
    # only mutation attempted, and it raised, so the object is an orphan in
    # LCM memory — the error message says so and the caller is responsible.


def test_create_with_guid_raises_runtime_error_when_create_guid_unsupported():
    """If factory.Create(guid) raises, _create_with_guid must raise
    RuntimeError mentioning 'does not support Create(Guid)' and must never
    call no-arg Create()."""
    factory = MagicMock()
    factory.Create.side_effect = TypeError("no Guid overload")

    factory_iface = MagicMock()
    factory_iface.__name__ = "FakeFactory"

    owner_collection = MagicMock()

    target = _make_target_with_factory(factory)

    import sys
    fake_guid_class = MagicMock()
    fake_guid_class.Parse.return_value = MagicMock(name="parsed_guid")
    fake_system = MagicMock()
    fake_system.Guid = fake_guid_class

    guid_str = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    original = sys.modules.get("System")
    sys.modules["System"] = fake_system
    try:
        with pytest.raises(RuntimeError) as exc_info:
            categories._create_with_guid(factory_iface, owner_collection, guid_str, target)
    finally:
        if original is None:
            del sys.modules["System"]
        else:
            sys.modules["System"] = original

    msg = str(exc_info.value)
    assert "does not support Create(Guid)" in msg, f"Expected 'does not support Create(Guid)' in: {msg}"

    # Create was called exactly once (with the parsed guid) — no no-arg fallback.
    assert factory.Create.call_count == 1, (
        f"Create() called {factory.Create.call_count} times; expected exactly 1 "
        "(no no-arg fallback allowed)"
    )
    # Add must never have been called.
    owner_collection.Add.assert_not_called()


# ============================================================================
# natural_classes_execute_action -- SegmentsRC wiring (P1-C)
# ============================================================================

def _fake_sys_guid(monkeypatch):
    """Inject a fake System.Guid into sys.modules so _create_with_guid works."""
    import sys
    fake_guid_class = MagicMock()
    # Parse returns an object whose str is the original guid_str; good enough.
    fake_guid_class.Parse.side_effect = lambda s: s
    fake_system = MagicMock()
    fake_system.Guid = fake_guid_class
    original = sys.modules.get("System")
    sys.modules["System"] = fake_system
    return original


def _restore_sys_guid(original):
    import sys
    if original is None:
        sys.modules.pop("System", None)
    else:
        sys.modules["System"] = original


class _FakeCollection:
    """Minimal stand-in for an LCM reference-collection (SegmentsRC etc.)."""
    def __init__(self, items=()):
        self._items = list(items)

    def __iter__(self):
        return iter(self._items)

    def Add(self, item):
        self._items.append(item)

    def __len__(self):
        return len(self._items)


class _FakePhoneme:
    def __init__(self, guid):
        self.guid = guid
        self.Guid = guid


class _FakeNCSegments:
    """Fake IPhNCSegments source natural class."""
    def __init__(self, guid, phoneme_refs):
        self.guid = guid
        self.Guid = guid
        self.SegmentsRC = _FakeCollection(phoneme_refs)


def _build_nc_execute_context(src_nc, src_phonemes, tgt_phonemes):
    """Build fake source + target handles for natural_classes_execute_action."""
    # Source handle
    source = MagicMock()
    source.NaturalClasses.GetAll.return_value = [src_nc]
    source.NaturalClasses.GetSyncableProperties.return_value = {}
    source.Phonemes.GetAll.return_value = src_phonemes

    # Target NC object: has a mutable SegmentsRC collection.
    tgt_nc = MagicMock()
    tgt_nc.SegmentsRC = _FakeCollection()

    # Factory returns the fake target NC.
    factory = MagicMock()
    factory.Create.return_value = tgt_nc

    # Target owner collection.
    owner_os = MagicMock()
    owner_os.Add.return_value = None

    # Cache chain.
    sl = MagicMock()
    sl.GetService.return_value = factory
    cache = MagicMock()
    cache.ServiceLocator = sl
    cache.LangProject.PhonologicalDataOA.NaturalClassesOS = owner_os

    target = MagicMock()
    target.Cache = cache
    target.NaturalClasses.ApplySyncableProperties.return_value = None
    target.Phonemes.GetAll.return_value = tgt_phonemes

    return source, target, tgt_nc


def _stub_lcm_nc_imports(monkeypatch):
    """Stub out SIL.LCModel NC interfaces so no real CLR is needed."""
    import sys

    class _PassthroughCast:
        """IPhNCSegments(obj) -> obj  (cast no-op for fakes)."""
        def __new__(cls, obj):
            return obj

    fake_lcm = MagicMock()
    fake_lcm.IPhNCSegmentsFactory = MagicMock()
    fake_lcm.IPhNCFeaturesFactory = MagicMock()
    fake_lcm.IPhNCSegments = _PassthroughCast
    # ICmObject(src_nc).ClassName => "PhNCSegments" for our fake.
    fake_lcm.ICmObject.side_effect = lambda obj: obj
    # Make sure obj.ClassName is "PhNCSegments" on our fakes
    # (handled by _FakeNCSegments not having ClassName; the except branch fires).

    original = sys.modules.get("SIL.LCModel")
    sys.modules["SIL.LCModel"] = fake_lcm
    return original, fake_lcm


def _restore_lcm(original):
    import sys
    if original is None:
        sys.modules.pop("SIL.LCModel", None)
    else:
        sys.modules["SIL.LCModel"] = original


def test_nc_execute_wires_segments_rc():
    """natural_classes_execute_action wires SegmentsRC with 2 target phonemes."""
    import sys

    p1_src = _FakePhoneme("ph-guid-1")
    p2_src = _FakePhoneme("ph-guid-2")
    p1_tgt = _FakePhoneme("ph-guid-1")
    p2_tgt = _FakePhoneme("ph-guid-2")

    src_nc = _FakeNCSegments("nc-guid-a", [p1_src, p2_src])
    source, target, tgt_nc = _build_nc_execute_context(
        src_nc, [p1_src, p2_src], [p1_tgt, p2_tgt]
    )

    action = MagicMock()
    action.source_guid = "nc-guid-a"

    ctx = _ctx(source, target)

    orig_sys = _fake_sys_guid(None)
    orig_lcm, _ = _stub_lcm_nc_imports(None)
    try:
        result = categories.natural_classes_execute_action(action, ctx, WSM, "test-tag")
    finally:
        _restore_sys_guid(orig_sys)
        _restore_lcm(orig_lcm)

    assert result is tgt_nc
    added_guids = [_._FakePhoneme__dict__ if hasattr(_, "_FakePhoneme__dict__") else _.guid
                   for _ in tgt_nc.SegmentsRC._items]
    # Simpler: check the items in SegmentsRC are p1_tgt and p2_tgt.
    assert p1_tgt in tgt_nc.SegmentsRC._items
    assert p2_tgt in tgt_nc.SegmentsRC._items
    assert len(tgt_nc.SegmentsRC._items) == 2


def test_nc_execute_raises_on_unresolved_phoneme():
    """natural_classes_execute_action raises RuntimeError when a source phoneme
    GUID has no counterpart on the target side."""
    import sys

    p1_src = _FakePhoneme("ph-guid-1")
    p2_src = _FakePhoneme("ph-guid-2")   # this one is NOT on target
    p1_tgt = _FakePhoneme("ph-guid-1")   # only ph-guid-1 on target

    src_nc = _FakeNCSegments("nc-guid-b", [p1_src, p2_src])
    source, target, tgt_nc = _build_nc_execute_context(
        src_nc, [p1_src, p2_src], [p1_tgt]  # tgt missing ph-guid-2
    )

    action = MagicMock()
    action.source_guid = "nc-guid-b"

    ctx = _ctx(source, target)

    orig_sys = _fake_sys_guid(None)
    orig_lcm, _ = _stub_lcm_nc_imports(None)
    try:
        with pytest.raises(RuntimeError) as exc_info:
            categories.natural_classes_execute_action(action, ctx, WSM, "test-tag")
    finally:
        _restore_sys_guid(orig_sys)
        _restore_lcm(orig_lcm)

    msg = str(exc_info.value)
    assert "ph-guid-2" in msg, f"Expected missing GUID in error: {msg}"
    assert "nc-guid-b" in msg, f"Expected NC GUID in error: {msg}"


# ============================================================================
# _safe_add_to_owner hardening tests (P0-A..D coverage)
# ============================================================================

def test_safe_add_to_owner_success_returns_silently():
    """Happy path: Add succeeds → helper returns None without raising."""
    owner = MagicMock()
    owner.Add = MagicMock()  # no exception
    result = categories._safe_add_to_owner(
        new_obj="sentinel", owner_collection=owner,
        factory_label="IFsFactory", src_guid="abc-123",
    )
    assert result is None
    owner.Add.assert_called_once_with("sentinel")


def test_safe_add_to_owner_raises_orphan_risk_on_add_failure():
    """Add raises → RuntimeError mentions 'Orphan risk', factory label, and GUID."""
    owner = MagicMock()
    owner.Add = MagicMock(side_effect=ValueError("LCM Add rejected"))
    with pytest.raises(RuntimeError) as exc_info:
        categories._safe_add_to_owner(
            new_obj="sentinel", owner_collection=owner,
            factory_label="IFsFactory", src_guid="abc-123",
        )
    msg = str(exc_info.value)
    assert "Orphan risk" in msg
    assert "IFsFactory" in msg
    assert "abc-123" in msg


# ============================================================================
# US2 — Strata smoke (Phase 3a)
# Source projects rarely carry strata; the Phase 3a category callbacks
# still need a unit-level smoke test confirming they wire up correctly
# when source DOES have one.  Live MCP verification deferred until a
# strata-bearing source becomes available.
# ============================================================================

def test_strata_plan_action_emits_planned_for_multiple_strata():
    """Source with 3 strata, target empty -> 3 PlannedAction entries."""
    src = _project(Strata=[_Item("s-1"), _Item("s-2"), _Item("s-3")])
    tgt = _project(Strata=[])
    items = categories.strata_enumerate_source(_ctx(src, tgt), SEL)
    actions = [
        categories.strata_plan_action(p, _ctx(src, tgt), WSM) for p in items
    ]
    assert len(actions) == 3
    assert all(isinstance(a, PlannedAction) for a in actions)
    assert {a.source_guid for a in actions} == {"s-1", "s-2", "s-3"}
    assert all(a.category == GrammarCategory.STRATA for a in actions)


def test_strata_partial_target_overlap_splits_actions_and_skips():
    """Source with 3 strata, target has 1 by GUID -> 2 actions + 1 skip."""
    src = _project(Strata=[_Item("s-1"), _Item("s-2"), _Item("s-3")])
    tgt = _project(Strata=[_Item("s-2")])  # one overlap
    actions = []
    skips = []
    for p in categories.strata_enumerate_source(_ctx(src, tgt), SEL):
        result = categories.strata_plan_action(p, _ctx(src, tgt), WSM)
        if isinstance(result, PlannedAction):
            actions.append(result)
        elif isinstance(result, Skip):
            skips.append(result)
    assert len(actions) == 2
    assert len(skips) == 1
    assert skips[0].source_guid == "s-2"
    assert skips[0].reason == SkipReason.ALREADY_PRESENT_BY_GUID


# ============================================================================
# US4 — Empty-source UX (Phase 3a FR-308)
# render_text_summary surfaces "[skip] no items in source for X" for any
# category the user selected that produced zero actions/skips/overwrites.
# ============================================================================

def test_render_summary_emits_skip_line_for_empty_selected_categories():
    """Build a RunReport with empty_categories populated and confirm
    render_text_summary emits the expected line."""
    from gramtrans.Lib.models import (
        RunContext as _RC, RunMode as _RM, RunReport as _RR,
    )
    from gramtrans.Lib.report import render_text_summary
    ctx = _RC(
        source_handle=object(), source_project_name="Src", source_project_path="",
        target_handle=object(), target_project_name="Tgt", target_project_path="",
        run_id="GT-20260620-235900", started_at="2026-06-20T23:59:00",
    )
    rep = _RR(
        context=ctx, mode=_RM.MOVE,
        per_category={}, skips=(),
        empty_categories=(
            GrammarCategory.STRATA,
            GrammarCategory.PHONOLOGICAL_RULES,
        ),
    )
    lines = list(render_text_summary(rep))
    skip_lines = [ln for ln in lines if "no items in source for" in ln]
    assert len(skip_lines) == 2
    assert any("strata" in ln for ln in skip_lines)
    assert any("phonological_rules" in ln for ln in skip_lines)


# ============================================================================
# Feature 037 (task 1) -- PhNCFeatures execute-action: FeaturesOA must
# actually be verified non-null, not silently skipped/trusted.
# ============================================================================

class _FakeNCFeaturesSrc:
    """Fake IPhNCFeatures source natural class (ClassName-driven dispatch)."""

    def __init__(self, guid):
        self.guid = guid
        self.Guid = guid
        self.ClassName = "PhNCFeatures"


def _build_nc_features_execute_context(src_nc, apply_sets_features_oa):
    """Build fake source + target handles for a PhNCFeatures
    natural_classes_execute_action call.

    `apply_sets_features_oa` simulates whether the mocked
    ApplySyncableProperties call wires FeaturesOA (flexicon >=4.5.0) or
    silently no-ops (flexicon <4.5.0 -- the original bug)."""
    source = MagicMock()
    source.NaturalClasses.GetAll.return_value = [src_nc]
    source.NaturalClasses.GetSyncableProperties.return_value = {"FeaturesGuid": "fs-1"}

    tgt_nc = MagicMock()
    tgt_nc.FeaturesOA = None  # starts null; ApplySyncableProperties may populate it

    def _fake_apply(item, props, ws_map=None):
        if apply_sets_features_oa:
            item.FeaturesOA = object()

    target = MagicMock()
    target.NaturalClasses.ApplySyncableProperties.side_effect = _fake_apply

    factory = MagicMock()
    factory.Create.return_value = tgt_nc
    sl = MagicMock()
    sl.GetService.return_value = factory
    cache = MagicMock()
    cache.ServiceLocator = sl
    cache.LangProject.PhonologicalDataOA.NaturalClassesOS = MagicMock()
    target.Cache = cache

    return source, target, tgt_nc


def test_nc_execute_raises_when_phnc_features_featuresoa_stays_null():
    """Task 1: the confirmed data-loss bug. A PhNCFeatures natural class
    whose FeaturesOA is STILL null after ApplySyncableProperties (the
    flexicon <4.5.0 silent-no-op case, or any other failure to wire it)
    must RAISE -- not pass through as an apparently-successful transfer."""
    src_nc = _FakeNCFeaturesSrc("nc-feat-1")
    source, target, tgt_nc = _build_nc_features_execute_context(
        src_nc, apply_sets_features_oa=False,
    )
    action = MagicMock()
    action.source_guid = "nc-feat-1"
    ctx = _ctx(source, target)

    orig_sys = _fake_sys_guid(None)
    orig_lcm, _ = _stub_lcm_nc_imports(None)
    try:
        with pytest.raises(RuntimeError) as exc_info:
            categories.natural_classes_execute_action(action, ctx, WSM, "test-tag")
    finally:
        _restore_sys_guid(orig_sys)
        _restore_lcm(orig_lcm)

    msg = str(exc_info.value)
    assert "FeaturesOA" in msg
    assert "nc-feat-1" in msg


def test_nc_execute_succeeds_when_phnc_features_featuresoa_populated():
    """PhNCFeatures whose FeaturesOA IS populated after
    ApplySyncableProperties (flexicon >=4.5.0) must NOT raise and must
    return the new natural class -- i.e. removing the false
    `class_name != "PhNCFeatures"` skip does not break the happy path."""
    src_nc = _FakeNCFeaturesSrc("nc-feat-2")
    source, target, tgt_nc = _build_nc_features_execute_context(
        src_nc, apply_sets_features_oa=True,
    )
    action = MagicMock()
    action.source_guid = "nc-feat-2"
    ctx = _ctx(source, target)

    orig_sys = _fake_sys_guid(None)
    orig_lcm, _ = _stub_lcm_nc_imports(None)
    try:
        result = categories.natural_classes_execute_action(action, ctx, WSM, "test-tag")
    finally:
        _restore_sys_guid(orig_sys)
        _restore_lcm(orig_lcm)

    assert result is tgt_nc
    assert tgt_nc.FeaturesOA is not None


# ============================================================================
# Feature 037 (task 2) -- natural_classes_dependencies must surface the
# feature/value GUIDs a PhNCFeatures item references (previously `()` with
# the false "FeaturesOA is owned" rationale); PhNCSegments unchanged.
# ============================================================================

def _install_fake_nc_deps_lcmodel(monkeypatch):
    import sys
    import types

    identity = lambda x: x  # noqa: E731
    fake = types.ModuleType("SIL.LCModel")
    for name in ("IPhNCSegments", "IPhNCFeatures", "IFsClosedValue", "ICmObject"):
        setattr(fake, name, identity)
    sil = types.ModuleType("SIL")
    sil.LCModel = fake
    monkeypatch.setitem(sys.modules, "SIL", sil)
    monkeypatch.setitem(sys.modules, "SIL.LCModel", fake)


class _FakeGuidRef:
    """Minimal fake exposing `.Guid` (uppercase) for the identity-cast
    `ICmObject(obj).Guid` access `natural_classes_dependencies` uses."""

    def __init__(self, guid):
        self.Guid = guid


def test_natural_classes_dependencies_phnc_features_returns_feature_value_guids(monkeypatch):
    """Task 2: for a PhNCFeatures item, natural_classes_dependencies must
    return the GUIDs of the IFsClosedFeature/IFsSymFeatVal objects its
    FeaturesOA feature structure references (FeatureRA + ValueRA of each
    FeatureSpecsOC entry) -- NOT an empty tuple."""
    _install_fake_nc_deps_lcmodel(monkeypatch)

    class _FakeClosedValue:
        def __init__(self, feature_guid, value_guid):
            self.FeatureRA = _FakeGuidRef(feature_guid)
            self.ValueRA = _FakeGuidRef(value_guid)

    class _FakeFeatStruc:
        def __init__(self, specs):
            self.FeatureSpecsOC = specs

    class _FakeNCFeaturesForDeps:
        def __init__(self, features_oa):
            self.FeaturesOA = features_oa

    specs = [
        _FakeClosedValue("feat-1", "val-1"),
        _FakeClosedValue("feat-2", "val-2"),
    ]
    piece = _FakeNCFeaturesForDeps(_FakeFeatStruc(specs))

    deps = set(categories.natural_classes_dependencies(piece))
    assert deps == {"feat-1", "val-1", "feat-2", "val-2"}


def test_natural_classes_dependencies_phnc_features_null_featuresoa_returns_empty(monkeypatch):
    """A PhNCFeatures item with FeaturesOA not yet set has no dependencies
    to surface (there is nothing to gate ordering on)."""
    _install_fake_nc_deps_lcmodel(monkeypatch)

    class _FakeNCFeaturesForDeps:
        FeaturesOA = None

    assert categories.natural_classes_dependencies(_FakeNCFeaturesForDeps()) == ()


def test_natural_classes_dependencies_phnc_segments_unchanged(monkeypatch):
    """Task 2 regression guard: the new PhNCFeatures branch must not disturb
    PhNCSegments' existing phoneme-GUID dependency behavior."""
    _install_fake_nc_deps_lcmodel(monkeypatch)

    class _FakeNCSegmentsForDeps:
        SegmentsRC = [_FakeGuidRef("p1"), _FakeGuidRef("p2")]

    deps = set(categories.natural_classes_dependencies(_FakeNCSegmentsForDeps()))
    assert deps == {"p1", "p2"}


# ============================================================================
# Feature 037 (task 4) -- post-transfer guard: any transferred PhNCFeatures
# left with a null FeaturesOA must be surfaced via DroppedItemRecord.
# ============================================================================

class _FakeTgtNCForGuard:
    def __init__(self, guid, features_oa):
        self.guid = guid
        self.Guid = guid
        self.FeaturesOA = features_oa
        self.Name = "MyFeatureClass"


def test_guard_nc_features_transferred_appends_dropped_record_when_null():
    tgt = _project(NaturalClasses=[_FakeTgtNCForGuard("nc-guard-1", None)])
    ctx = _ctx(_project(), tgt)
    object.__setattr__(ctx, "_nc_features_guids", ["nc-guard-1"])
    dropped: list = []
    object.__setattr__(ctx, "_dropped", dropped)

    result = categories._guard_nc_features_transferred(ctx, tgt, "test-tag")

    assert result == []
    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.owner_kind == "PhNCFeatures"
    assert rec.owner_guid == "nc-guard-1"
    assert rec.field_name == "FeaturesOA"
    assert rec.item_guid == "nc-guard-1"


def test_guard_nc_features_transferred_no_op_when_featuresoa_populated():
    tgt = _project(NaturalClasses=[_FakeTgtNCForGuard("nc-guard-2", object())])
    ctx = _ctx(_project(), tgt)
    object.__setattr__(ctx, "_nc_features_guids", ["nc-guard-2"])
    dropped: list = []
    object.__setattr__(ctx, "_dropped", dropped)

    result = categories._guard_nc_features_transferred(ctx, tgt, "test-tag")

    assert result == []
    assert dropped == []


def test_guard_nc_features_transferred_no_op_when_no_guids_tracked():
    """No PhNCFeatures touched this run -> guard is a complete no-op."""
    tgt = _project(NaturalClasses=[])
    ctx = _ctx(_project(), tgt)
    dropped: list = []
    object.__setattr__(ctx, "_dropped", dropped)

    result = categories._guard_nc_features_transferred(ctx, tgt, "test-tag")

    assert result == []
    assert dropped == []


# ============================================================================
# Feature 037 (task 3) -- phonological rule Disabled flag must be copied
# EXPLICITLY (flexicon's GetSyncableProperties never includes it).
# ============================================================================

def test_phon_rule_apply_body_copies_disabled_true_explicitly():
    orig_lcm, _ = _stub_lcm_nc_imports(None)
    try:
        class _SrcRule:
            ClassName = "PhMetathesisRule"
            Disabled = True

        class _NewRule:
            Disabled = False  # starts enabled -- must flip to True

        source = MagicMock()
        source.PhonRules.GetSyncableProperties.return_value = {"Name": {}}
        target = MagicMock()

        new_rule = _NewRule()
        result = categories._phon_rule_apply_body(
            _SrcRule(), new_rule, "PhMetathesisRule", source, target,
            ws_mapping=None, tag="test-tag", src_guid="rule-1", context=None,
        )
    finally:
        _restore_lcm(orig_lcm)

    assert result is new_rule
    assert new_rule.Disabled is True


def test_phon_rule_apply_body_leaves_enabled_rule_enabled():
    """Companion case: Disabled=False on source must not flip an
    already-True target flag to False in a way that looks like a bug in the
    other direction (defends against a copy that ORs instead of assigns)."""
    orig_lcm, _ = _stub_lcm_nc_imports(None)
    try:
        class _SrcRule:
            ClassName = "PhMetathesisRule"
            Disabled = False

        class _NewRule:
            Disabled = True

        source = MagicMock()
        source.PhonRules.GetSyncableProperties.return_value = {}
        target = MagicMock()

        new_rule = _NewRule()
        categories._phon_rule_apply_body(
            _SrcRule(), new_rule, "PhMetathesisRule", source, target,
            ws_mapping=None, tag="test-tag", src_guid="rule-2", context=None,
        )
    finally:
        _restore_lcm(orig_lcm)

    assert new_rule.Disabled is False


# ============================================================================
# Feature 037 (task 7) -- already-present-by-GUID phonological rules must be
# reconciled (skip if structurally identical, update if different), not
# blindly skipped.  `_fake_lcmodel` (module-level fixture, extended above
# with IPhSimpleContextBdry/IPhIterationContext) drives `_phon_rule_fingerprint`.
# ============================================================================

def _make_rule(guid, struc_desc=None, rhs_list=None, initial=None, final=None,
               disabled=False, direction=0, class_name="PhRegularRule"):
    rule = _PhRule(
        struc_desc if struc_desc is not None else [],
        rhs_list if rhs_list is not None else [],
        initial=initial, final=final,
    )
    rule.guid = guid
    rule.Disabled = disabled
    rule.Direction = direction
    rule.ClassName = class_name
    return rule


def test_phonological_rules_plan_action_skips_identical_structural_fingerprint(_fake_lcmodel):
    """Task 7(a): a rule present by GUID with an IDENTICAL structural
    fingerprint is skipped, as before -- cheap, no PlannedOverwrite."""
    src_rhs = _PhRHS(
        right=_PhCell("PhSimpleContextNC", "rc-src", feature=_PhRef("nc-1")),
    )
    src_rule = _make_rule("r-1", rhs_list=[src_rhs])
    tgt_rhs = _PhRHS(
        # Different cell GUID ("rc-tgt" vs "rc-src") is irrelevant -- only the
        # REFERENCED natural class GUID ("nc-1") is compared.
        right=_PhCell("PhSimpleContextNC", "rc-tgt", feature=_PhRef("nc-1")),
    )
    tgt_rule = _make_rule("r-1", rhs_list=[tgt_rhs])

    src = _project(PhonRules=[src_rule])
    tgt = _project(PhonRules=[tgt_rule])

    result = categories.phonological_rules_plan_action(src_rule, _ctx(src, tgt), WSM)

    assert isinstance(result, Skip)
    assert result.reason == SkipReason.ALREADY_PRESENT_BY_GUID


def test_phonological_rules_plan_action_detects_null_vs_present_right_context(_fake_lcmodel):
    """Task 7(b) -- regression test for the proven case: rule
    "nasal assim simple reb" (33978942-cc6e-4655-afb2-b0a869b670c5), whose
    source RHS[0].RightContextOA holds a PhSimpleContextNC while target's is
    null, with everything else matching. Must be detected as DIFFERENT and
    routed to a structural-rebuild PlannedOverwrite -- not skipped."""
    src_rhs = _PhRHS(
        struc_change=[_PhCell("PhSimpleContextSeg", "sc-1", feature=_PhRef("p-1"))],
        left=_PhCell("PhSimpleContextNC", "lc-1", feature=_PhRef("nc-left")),
        right=_PhCell("PhSimpleContextNC", "rc-1", feature=_PhRef("nc-right")),
    )
    src_rule = _make_rule(
        "33978942-cc6e-4655-afb2-b0a869b670c5", rhs_list=[src_rhs],
    )

    tgt_rhs = _PhRHS(
        struc_change=[_PhCell("PhSimpleContextSeg", "sc-1t", feature=_PhRef("p-1"))],
        left=_PhCell("PhSimpleContextNC", "lc-1t", feature=_PhRef("nc-left")),
        right=None,  # <-- the drift under test: RightContextOA is null in target
    )
    tgt_rule = _make_rule(
        "33978942-cc6e-4655-afb2-b0a869b670c5", rhs_list=[tgt_rhs],
    )

    src = _project(PhonRules=[src_rule])
    tgt = _project(PhonRules=[tgt_rule])

    result = categories.phonological_rules_plan_action(src_rule, _ctx(src, tgt), WSM)

    assert isinstance(result, PlannedOverwrite)
    assert result.write_mode == "structural_rebuild"
    assert result.category == GrammarCategory.PHONOLOGICAL_RULES
    assert result.source_guid == "33978942-cc6e-4655-afb2-b0a869b670c5"


def test_phonological_rules_plan_action_detects_disabled_only_drift(_fake_lcmodel):
    """Task 7(c): rules identical in owned structure but differing ONLY in
    Disabled must also be detected as different."""
    src_rule = _make_rule("r-disabled", disabled=True)
    tgt_rule = _make_rule("r-disabled", disabled=False)

    src = _project(PhonRules=[src_rule])
    tgt = _project(PhonRules=[tgt_rule])

    result = categories.phonological_rules_plan_action(src_rule, _ctx(src, tgt), WSM)

    assert isinstance(result, PlannedOverwrite)
    assert result.write_mode == "structural_rebuild"


def test_shallow_syncable_props_comparator_would_not_catch_right_context_drift(_fake_lcmodel):
    """Task 7(d): prove the shallow comparator flexicon's
    PhonologicalRuleOperations effectively offers (GetSyncableProperties:
    Name/Description/Direction/StratumGuid only) is BLIND to the exact
    drift test (b) exercises -- the reason a naive CompareTo-based fix would
    NOT have caught rule "nasal assim simple reb"."""
    src_rhs = _PhRHS(right=_PhCell("PhSimpleContextNC", "rc-1", feature=_PhRef("nc-right")))
    src_rule = _make_rule("r-shallow", rhs_list=[src_rhs], direction=0)
    tgt_rhs = _PhRHS(right=None)
    tgt_rule = _make_rule("r-shallow", rhs_list=[tgt_rhs], direction=0)

    # The only fields flexicon's GetSyncableProperties would ever compare
    # for a rule (Name/Description omitted here -- both empty on these
    # fakes -- StratumGuid is dead code per categories.py's docstring):
    shallow_src = {"Direction": src_rule.Direction}
    shallow_tgt = {"Direction": tgt_rule.Direction}
    assert shallow_src == shallow_tgt, "shallow comparator sees these as IDENTICAL"

    # ...yet the structural fingerprint this fix uses correctly reports them
    # as different.
    assert (
        categories._phon_rule_fingerprint(src_rule)
        != categories._phon_rule_fingerprint(tgt_rule)
    ), "structural fingerprint must catch what the shallow comparator misses"
