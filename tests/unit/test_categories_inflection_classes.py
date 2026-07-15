"""Unit tests for inflection_classes leaf-category functions.

Regression coverage for the mis-owned-collection bug (coverage-content-
fidelity Part A): IMoInflClass is owned PER-POS via
IPartOfSpeech.InflectionClassesOC, not the flat/wrong
MorphologicalDataOA.ProdRestrictOA.PossibilitiesOS list. The fakes below
mirror test_categories_stem_names.py's POS-owned shape (no
`InflectionFeatures` flat accessor at all) so a reversion to the old flat
walk shows up as zero enumeration / no ALREADY_PRESENT detection --
exactly the reported live symptom (arz-flex 0/1, Aweti 0/3,
French-FLExTrans-Demo2025 0/5).

Covers:
- dependencies() yields the owner POS as a GRAM_CATEGORIES edge (not empty --
  inflection classes now declare a real POS dependency for the closure walker)
- enumerate_source() walks all POS InflectionClassesOC (not a flat accessor)
- plan_action() ALREADY_PRESENT_BY_GUID skip via per-POS walk
- plan_action() PlannedAction for new GUID
- execute_action() adds the created IMoInflClass to the OWNER POS's
  InflectionClassesOC, never to ProdRestrictOA.PossibilitiesOS (fully
  mocked -- no live LCM host required, mirrors
  test_categories_phonology.py's ServiceLocator/factory mocking pattern)
- execute_action() returns None (dependency-unresolved) when the owner POS
  cannot be resolved on the target
"""
from __future__ import annotations

import sys
import types

import pytest
from unittest.mock import MagicMock

from gramtrans.Lib import categories
from gramtrans.Lib.models import (
    GrammarCategory,
    PlannedAction,
    RunContext,
    Selection,
    Skip,
    SkipReason,
    WSMapping,
)
from gramtrans.Lib.residue import ImportResidueTag

_TAG = ImportResidueTag(
    run_id="GT-20260620-010000",
    source_project_name="SrcProj",
    timestamp="2026-06-20T01:00:00",
)


# ============================================================================
# Fake objects (POS-owned shape -- mirrors test_categories_stem_names.py)
# ============================================================================

class _FakeInflClass:
    def __init__(self, guid: str, owner=None) -> None:
        self.guid = guid
        self.Owner = owner


class _FakePOS:
    def __init__(self, guid: str, infl_classes=()) -> None:
        self.guid = guid
        # Mimic IPartOfSpeech.InflectionClassesOC as a simple list.
        self.InflectionClassesOC = list(infl_classes)
        for ic in self.InflectionClassesOC:
            ic.Owner = self

    @property
    def concrete(self):
        return self


class _FakePOSOps:
    def __init__(self, poses=()) -> None:
        self._poses = list(poses)

    def GetAll(self, recursive=True):
        return list(self._poses)


class _FakeProject:
    def __init__(self, name: str, poses=()) -> None:
        self.name = name
        self.POS = _FakePOSOps(poses)

    def ProjectName(self):
        return self.name


def _ctx(source, target) -> RunContext:
    return RunContext(
        source_handle=source,
        source_project_name="SrcProj",
        source_project_path="/src",
        target_handle=target,
        target_project_name="TgtProj",
        target_project_path="/tgt",
        run_id="GT-20260620-010000",
        started_at="2026-06-20T01:00:00",
    )


_BUNDLE = categories.for_category(GrammarCategory.INFLECTION_CLASSES)


# ============================================================================
# Monkeypatch: functions cast via IPartOfSpeech(concrete)/ICmObject(concrete) --
# in unit tests without LCM we patch SIL.LCModel with identity casts (same
# fixture as test_categories_stem_names.py).
# ============================================================================

@pytest.fixture(autouse=True)
def _patch_lcm_cast(monkeypatch):
    monkeypatch.setattr(
        categories, "_guid_str_from",
        lambda obj: str(getattr(obj, "guid", "")).lower(),
    )

    class _FakeIPartOfSpeech:
        def __new__(cls, obj):
            return obj

    class _FakeICmObject:
        def __new__(cls, obj):
            return obj

    class _FakeIMoInflClass:
        """Identity cast -- returns the object as-is (execute_action tests
        mock the factory return value directly, no real LCM type needed)."""
        def __new__(cls, obj):
            return obj

    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.IPartOfSpeech = _FakeIPartOfSpeech
    fake_lcm.ICmObject = _FakeICmObject
    fake_lcm.IMoInflClass = _FakeIMoInflClass
    fake_lcm.IMoInflClassFactory = object()  # opaque key; sl.GetService(...) is mocked
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    original = sys.modules.get("SIL.LCModel")
    sys.modules["SIL.LCModel"] = fake_lcm
    yield
    if original is None:
        sys.modules.pop("SIL.LCModel", None)
    else:
        sys.modules["SIL.LCModel"] = original


# ============================================================================
# Tests -- planning surface (enumerate_source / dependencies / plan_action)
# ============================================================================

def test_dependencies_yields_owner_pos_edge() -> None:
    """RED under the old flat/leaf implementation: it returned () unconditionally,
    with no POS dependency at all. GREEN: yields (GRAM_CATEGORIES, owner_guid)."""
    pos = _FakePOS("pos-A")
    ic = _FakeInflClass("ic-001", owner=pos)

    result = tuple(_BUNDLE["dependencies"](piece=ic))

    assert result == ((GrammarCategory.GRAM_CATEGORIES, "pos-a"),)


def test_dependencies_empty_when_no_owner() -> None:
    ic = _FakeInflClass("ic-001b", owner=None)
    assert tuple(_BUNDLE["dependencies"](piece=ic)) == ()


def test_enumerate_source_yields_all_classes_across_poses() -> None:
    """RED under the old implementation: it read `source.InflectionFeatures
    .InflectionClassGetAll()`, which does not exist on this POS-owned fake
    (no `InflectionFeatures` attribute at all) -> old code returned ().
    GREEN: walks POS.InflectionClassesOC and finds both classes."""
    ic1 = _FakeInflClass("ic-100")
    ic2 = _FakeInflClass("ic-101")
    pos_a = _FakePOS("pos-X", infl_classes=(ic1,))
    pos_b = _FakePOS("pos-Y", infl_classes=(ic2,))
    src = _FakeProject("src", poses=(pos_a, pos_b))
    tgt = _FakeProject("tgt")
    ctx = _ctx(src, tgt)
    sel = Selection(categories={GrammarCategory.INFLECTION_CLASSES: True})

    items = list(_BUNDLE["enumerate_source"](context=ctx, selection=sel))

    assert ic1 in items
    assert ic2 in items
    assert len(items) == 2


def test_enumerate_source_empty_when_no_pos() -> None:
    src = _FakeProject("src", poses=())
    tgt = _FakeProject("tgt")
    ctx = _ctx(src, tgt)
    sel = Selection(categories={GrammarCategory.INFLECTION_CLASSES: True})

    items = list(_BUNDLE["enumerate_source"](context=ctx, selection=sel))
    assert items == []


def test_plan_action_new_guid_yields_planned_action() -> None:
    ic = _FakeInflClass("ic-003")
    src_pos = _FakePOS("pos-A", infl_classes=(ic,))
    src = _FakeProject("src", poses=(src_pos,))
    tgt = _FakeProject("tgt", poses=())
    ctx = _ctx(src, tgt)

    result = _BUNDLE["plan_action"](piece=ic, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, PlannedAction)
    assert result.category == GrammarCategory.INFLECTION_CLASSES
    assert result.source_guid == "ic-003"


def test_plan_action_already_present_yields_skip() -> None:
    """RED under the old implementation: presence was checked via the flat
    `InflectionFeatures.InflectionClassGetAll()` accessor, absent on this
    fake -> old code never detected the collision. GREEN: per-POS walk
    finds the GUID on the target POS and skips."""
    ic = _FakeInflClass("ic-002")
    src_pos = _FakePOS("pos-A", infl_classes=(ic,))
    src = _FakeProject("src", poses=(src_pos,))
    tgt_ic = _FakeInflClass("ic-002")
    tgt_pos = _FakePOS("pos-A", infl_classes=(tgt_ic,))
    tgt = _FakeProject("tgt", poses=(tgt_pos,))
    ctx = _ctx(src, tgt)

    result = _BUNDLE["plan_action"](piece=ic, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, Skip)
    assert result.reason == SkipReason.ALREADY_PRESENT_BY_GUID
    assert result.source_guid == "ic-002"


def test_plan_action_different_guid_not_present() -> None:
    ic_a = _FakeInflClass("ic-010")
    ic_b = _FakeInflClass("ic-011")
    src_pos = _FakePOS("pos-A", infl_classes=(ic_a,))
    src = _FakeProject("src", poses=(src_pos,))
    tgt_pos = _FakePOS("pos-A", infl_classes=(ic_b,))
    tgt = _FakeProject("tgt", poses=(tgt_pos,))
    ctx = _ctx(src, tgt)

    result = _BUNDLE["plan_action"](piece=ic_a, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, PlannedAction)
    assert result.source_guid == "ic-010"


# ============================================================================
# execute_action -- fully mocked LCM (no live host), mirrors
# test_categories_phonology.py's ServiceLocator/factory mocking pattern.
# ============================================================================

def _fake_sys_guid():
    fake_guid_class = MagicMock()
    fake_guid_class.Parse.side_effect = lambda s: s
    fake_system = MagicMock()
    fake_system.Guid = fake_guid_class
    original = sys.modules.get("System")
    sys.modules["System"] = fake_system
    return original


def _restore_sys_guid(original):
    if original is None:
        sys.modules.pop("System", None)
    else:
        sys.modules["System"] = original


class _FakeOwningCollection:
    """Minimal stand-in for an LCM owning-collection (InflectionClassesOC /
    ProdRestrictOA.PossibilitiesOS)."""
    def __init__(self):
        self._items = []

    def Add(self, item):
        self._items.append(item)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)


def _build_execute_context(src_ic, src_owner_pos, tgt_owner_pos_guid, wrong_collection):
    """Build fake source/target handles for inflection_classes_execute_action.

    `tgt_owner_pos_guid`: guid of the POS on the TARGET side that should
    receive the new inflection class (or None to simulate an unresolvable
    owner -- dependency-unresolved path).
    `wrong_collection`: the (mis-owned) ProdRestrictOA.PossibilitiesOS stand-in
    that the OLD buggy code wrote to -- asserted empty after the fix.
    """
    source = MagicMock()
    source.POS.GetAll.return_value = [src_owner_pos]
    source.InflectionFeatures.GetSyncableProperties.return_value = {
        "Name": {"en": "First Declension"},
    }

    new_ic = MagicMock()
    factory = MagicMock()
    factory.Create.return_value = new_ic

    target_owner_collection = _FakeOwningCollection()

    tgt_pos = None
    if tgt_owner_pos_guid is not None:
        # Not a MagicMock: MagicMock auto-vivifies `.concrete` as a fresh
        # mock attribute (not `self`), which breaks `_as_pos`'s
        # `pos.concrete if hasattr(pos, "concrete") else pos` identity chain.
        tgt_pos = _FakePOS(tgt_owner_pos_guid, infl_classes=())
        tgt_pos.InflectionClassesOC = target_owner_collection

    sl = MagicMock()
    sl.GetService.return_value = factory
    cache = MagicMock()
    cache.ServiceLocator = sl
    cache.LangProject.MorphologicalDataOA.ProdRestrictOA.PossibilitiesOS = wrong_collection

    target = MagicMock()
    target.Cache = cache
    target.POS.GetAll.return_value = [tgt_pos] if tgt_pos is not None else []
    target.InflectionFeatures.ApplySyncableProperties.return_value = None

    return source, target, new_ic, target_owner_collection


def test_execute_action_adds_new_class_to_owner_pos_inflection_classes_oc() -> None:
    """The created IMoInflClass must land in the OWNER POS's
    InflectionClassesOC -- NOT in ProdRestrictOA.PossibilitiesOS."""
    src_pos = _FakePOS("pos-guid-owner", infl_classes=())
    src_ic = _FakeInflClass("ic-guid-exec", owner=src_pos)
    src_pos.InflectionClassesOC = [src_ic]

    wrong_collection = _FakeOwningCollection()
    source, target, new_ic, owner_oc = _build_execute_context(
        src_ic, src_pos, tgt_owner_pos_guid="pos-guid-owner",
        wrong_collection=wrong_collection,
    )

    action = MagicMock()
    action.source_guid = "ic-guid-exec"
    ctx = _ctx(source, target)

    orig_sys = _fake_sys_guid()
    try:
        result = categories.inflection_classes_execute_action(
            action, ctx, WSMapping(), _TAG,
        )
    finally:
        _restore_sys_guid(orig_sys)

    assert result is new_ic
    assert new_ic in owner_oc._items, (
        "Expected the new IMoInflClass in the OWNER POS's InflectionClassesOC"
    )
    assert len(wrong_collection._items) == 0, (
        "Regression: IMoInflClass must never be added to "
        "ProdRestrictOA.PossibilitiesOS (the mis-owned collection)."
    )


def test_execute_action_returns_none_when_owner_pos_unresolved() -> None:
    """When the owner POS cannot be found on the target, execute_action
    must return None (dependency-unresolved) rather than falling back to
    the wrong collection or crashing."""
    src_pos = _FakePOS("pos-guid-missing", infl_classes=())
    src_ic = _FakeInflClass("ic-guid-orphan", owner=src_pos)
    src_pos.InflectionClassesOC = [src_ic]

    wrong_collection = _FakeOwningCollection()
    source, target, new_ic, owner_oc = _build_execute_context(
        src_ic, src_pos, tgt_owner_pos_guid=None,
        wrong_collection=wrong_collection,
    )

    action = MagicMock()
    action.source_guid = "ic-guid-orphan"
    ctx = _ctx(source, target)

    orig_sys = _fake_sys_guid()
    try:
        result = categories.inflection_classes_execute_action(
            action, ctx, WSMapping(), _TAG,
        )
    finally:
        _restore_sys_guid(orig_sys)

    assert result is None
    assert len(wrong_collection._items) == 0
