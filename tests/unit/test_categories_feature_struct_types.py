"""Unit tests for feature_struct_types leaf-category functions
(coverage-content-fidelity-v2 Part B sub-part 2).

Covers:
- enumerate_source() walks source MsFeatureSystemOA.TypesOC.
- dependencies() returns empty tuple (no closure of its own).
- plan_action() ALREADY_PRESENT_BY_GUID skip vs PlannedAction for new GUID.
- execute_action():
  (a) absent-in-target IFsFeatStrucType -> CREATE, GUID-preserved, landed
      in TypesOC; Name/Abbreviation/Description ws-mapped-copied.
  (b) already-present-by-GUID handled at plan_action (no duplicate CREATE
      attempted for a GUID already in target TypesOC).
  (c) FeaturesRS member whose GUID resolves in target FeaturesOC ->
      FeaturesRS.Add() called; a member with NO target counterpart is
      skipped + logged, no crash, partial wiring tolerated.
- registry test (test_category_registry.py) passes with FEATURE_STRUCT_TYPES
  present -- exercised indirectly via `categories.for_category`.
"""
from __future__ import annotations

import sys
import types
import uuid

import pytest

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


# ============================================================================
# Fakes (enumerate_source / plan_action -- no live LCM)
# ============================================================================

class _FakeFeatStrucType:
    def __init__(self, guid: str) -> None:
        self.guid = guid.lower()
        self.Guid = guid


class _FakeFeatureSystem:
    def __init__(self, types_oc=()) -> None:
        self.TypesOC = list(types_oc)


class _FakeLangProject:
    def __init__(self, feature_system) -> None:
        self.MsFeatureSystemOA = feature_system


class _FakeCache:
    def __init__(self, feature_system) -> None:
        self.LangProject = _FakeLangProject(feature_system)


class _FakeProject:
    def __init__(self, types_oc=()) -> None:
        self._feature_system = _FakeFeatureSystem(types_oc)
        self._cache = _FakeCache(self._feature_system)

    @property
    def Cache(self):
        return self._cache


def _ctx(source, target) -> RunContext:
    return RunContext(
        source_handle=source,
        source_project_name="SrcProj",
        source_project_path="/src",
        target_handle=target,
        target_project_name="TgtProj",
        target_project_path="/tgt",
        run_id="GT-20260715-020000",
        started_at="2026-07-15T02:00:00",
    )


_BUNDLE = categories.for_category(GrammarCategory.FEATURE_STRUCT_TYPES)


# ============================================================================
# enumerate_source / dependencies / required_writing_systems
# ============================================================================

def test_enumerate_source_returns_all_types() -> None:
    t1 = _FakeFeatStrucType(str(uuid.uuid4()))
    t2 = _FakeFeatStrucType(str(uuid.uuid4()))
    src = _FakeProject(types_oc=(t1, t2))
    tgt = _FakeProject()
    ctx = _ctx(src, tgt)
    sel = Selection(categories={GrammarCategory.FEATURE_STRUCT_TYPES: True})

    items = list(_BUNDLE["enumerate_source"](context=ctx, selection=sel))
    assert t1 in items
    assert t2 in items


def test_enumerate_source_no_cache_returns_empty() -> None:
    """A source object with no Cache attribute degrades to empty, not crash."""
    class _NoCacheProject:
        pass

    ctx = _ctx(_NoCacheProject(), _FakeProject())
    sel = Selection(categories={GrammarCategory.FEATURE_STRUCT_TYPES: True})
    assert list(_BUNDLE["enumerate_source"](context=ctx, selection=sel)) == []


def test_dependencies_returns_empty_tuple() -> None:
    piece = _FakeFeatStrucType(str(uuid.uuid4()))
    assert tuple(_BUNDLE["dependencies"](piece=piece)) == ()


def test_required_writing_systems_returns_empty_tuple() -> None:
    piece = _FakeFeatStrucType(str(uuid.uuid4()))
    assert tuple(_BUNDLE["required_writing_systems"](piece=piece)) == ()


# ============================================================================
# plan_action()
# ============================================================================

def test_plan_action_new_guid_yields_planned_action() -> None:
    type_guid = str(uuid.uuid4())
    piece = _FakeFeatStrucType(type_guid)
    src = _FakeProject(types_oc=(piece,))
    tgt = _FakeProject()
    ctx = _ctx(src, tgt)

    result = _BUNDLE["plan_action"](piece=piece, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, PlannedAction)
    assert result.category == GrammarCategory.FEATURE_STRUCT_TYPES
    assert result.source_guid == type_guid.lower()


def test_plan_action_already_present_yields_skip() -> None:
    type_guid = str(uuid.uuid4())
    piece = _FakeFeatStrucType(type_guid)
    tgt_piece = _FakeFeatStrucType(type_guid)  # same GUID, already in target
    src = _FakeProject(types_oc=(piece,))
    tgt = _FakeProject(types_oc=(tgt_piece,))
    ctx = _ctx(src, tgt)

    result = _BUNDLE["plan_action"](piece=piece, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, Skip)
    assert result.reason == SkipReason.ALREADY_PRESENT_BY_GUID


def test_plan_action_no_guid_yields_unsupported_skip() -> None:
    class _NoGuidPiece:
        pass

    ctx = _ctx(_FakeProject(), _FakeProject())
    result = _BUNDLE["plan_action"](piece=_NoGuidPiece(), context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, Skip)
    assert result.reason == SkipReason.UNSUPPORTED_LCM_TYPE


# ============================================================================
# execute_action() -- fake SIL.LCModel / System injection, no live LCM host.
# ============================================================================

_TYPE_GUID = str(uuid.uuid4()).lower()
_DEFN_GUID_RESOLVED = str(uuid.uuid4()).lower()
_DEFN_GUID_UNRESOLVED = str(uuid.uuid4()).lower()


class _FakeTsString:
    def __init__(self, text: str) -> None:
        self.Text = text


class _FakeMultiString:
    """Minimal duck-typed ITsMultiString: read/write are no-ops that never
    raise, so the WS-mapped copy path can run without touching real SIL
    types."""

    def get_String(self, ws_handle):
        return _FakeTsString("")

    def set_String(self, ws_handle, ts_string):
        pass


class _FakeSrcFeatStrucType:
    def __init__(self, guid: str, members=()) -> None:
        self.guid = guid
        self.Name = _FakeMultiString()
        self.Abbreviation = _FakeMultiString()
        self.Description = _FakeMultiString()
        self.FeaturesRS = list(members)


class _FakeDefn:
    """Stand-in for an IFsFeatDefn member (source or target)."""

    def __init__(self, guid: str) -> None:
        self.guid = guid


class _FakeNewFeatStrucType:
    def __init__(self) -> None:
        self.Name = _FakeMultiString()
        self.Abbreviation = _FakeMultiString()
        self.Description = _FakeMultiString()
        self.FeaturesRS = _FakeAddTrackingList()


class _FakeAddTrackingList(list):
    def Add(self, obj) -> None:
        self.append(obj)


class _FakeOwnerOC(list):
    def Add(self, obj) -> None:
        self.append(obj)


class _FakeFeatureSystemExec:
    def __init__(self, types_oc=None, features_oc=()) -> None:
        self.TypesOC = _FakeOwnerOC() if types_oc is None else types_oc
        self.FeaturesOC = list(features_oc)


class _FakeFactory:
    """Tracks every Create(*args) call and always returns the same object."""

    def __init__(self, obj_to_return) -> None:
        self._obj = obj_to_return
        self.create_calls: list = []

    def Create(self, *args):
        self.create_calls.append(args)
        return self._obj


class _FakeServiceLocator:
    def __init__(self, factory_map: dict) -> None:
        self._factory_map = factory_map

    def GetService(self, factory_type):
        return self._factory_map[id(factory_type)]


class _FakeLangProjectExec:
    def __init__(self, feature_system) -> None:
        self.MsFeatureSystemOA = feature_system


class _FakeCacheExec:
    def __init__(self, feature_system, service_locator) -> None:
        self.DefaultAnalWs = 1
        self.LangProject = _FakeLangProjectExec(feature_system)
        self.ServiceLocator = service_locator


class _FakeWSObj:
    def __init__(self, ws_id: str, handle: int) -> None:
        self.Id = ws_id
        self.Handle = handle


class _FakeWSOps:
    def __init__(self, ws_list=()) -> None:
        self._ws_list = list(ws_list)

    def GetAll(self):
        return list(self._ws_list)


class _FakeTgtProject:
    def __init__(self, feature_system, service_locator, ws_list=()) -> None:
        self._cache = _FakeCacheExec(feature_system, service_locator)
        self.WritingSystems = _FakeWSOps(ws_list)

    @property
    def Cache(self):
        return self._cache


class _FakeSrcProject:
    def __init__(self, feature_system, ws_list=()) -> None:
        self._cache = _FakeCache(feature_system)
        self.WritingSystems = _FakeWSOps(ws_list)

    @property
    def Cache(self):
        return self._cache


def _action(guid: str) -> PlannedAction:
    return PlannedAction(
        category=GrammarCategory.FEATURE_STRUCT_TYPES,
        source_guid=guid,
        intended_target_guid=guid,
        summary="test",
    )


def _ctx_exec(source, target) -> RunContext:
    ctx = RunContext(
        source_handle=source,
        source_project_name="SrcProj",
        source_project_path="/src",
        target_handle=target,
        target_project_name="TgtProj",
        target_project_path="/tgt",
        run_id="GT-20260715-030000",
        started_at="2026-07-15T03:00:00",
    )
    object.__setattr__(ctx, "_exec_skips", [])
    return ctx


@pytest.fixture()
def _patch_lcm(monkeypatch):
    """Inject a fake SIL.LCModel/System so the function's internal
    `from SIL.LCModel import ...` succeeds offline (no pythonnet host), and
    no-op apply_carrier_b so residue logic doesn't need a real WS handle."""
    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.IFsFeatStrucTypeFactory = object()
    fake_lcm.IFsFeatStrucType = lambda x: x

    fake_system = types.ModuleType("System")
    fake_system.Guid = type("Guid", (), {"Parse": staticmethod(lambda s: s)})

    injected = {
        "SIL": types.ModuleType("SIL"),
        "SIL.LCModel": fake_lcm,
        "System": fake_system,
    }
    originals = {key: sys.modules.get(key) for key in injected}
    sys.modules.update(injected)

    try:
        import gramtrans.Lib.residue as _res_mod
        monkeypatch.setattr(_res_mod, "apply_carrier_b", lambda obj, ws, tag: None)
    except Exception:
        pass

    yield fake_lcm

    for key, orig in originals.items():
        if orig is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = orig


def test_execute_action_creates_type_lands_in_types_oc(_patch_lcm) -> None:
    """(a) absent-in-target -> CREATE, GUID-preserved, landed in TypesOC."""
    fake_lcm = _patch_lcm
    src_type = _FakeSrcFeatStrucType(guid=_TYPE_GUID)
    src_proj = _FakeSrcProject(_FakeFeatureSystem(types_oc=(src_type,)))

    new_type = _FakeNewFeatStrucType()
    factory = _FakeFactory(new_type)
    sl = _FakeServiceLocator({id(fake_lcm.IFsFeatStrucTypeFactory): factory})
    feat_sys = _FakeFeatureSystemExec()
    tgt_proj = _FakeTgtProject(feat_sys, sl)

    ctx = _ctx_exec(src_proj, tgt_proj)

    result = categories.feature_struct_types_execute_action(
        _action(_TYPE_GUID), ctx, WSMapping(), tag=None,
    )

    assert result is new_type
    assert factory.create_calls, "IFsFeatStrucTypeFactory.Create was not called"
    assert new_type in feat_sys.TypesOC, "new type was not landed in TypesOC"


def test_execute_action_source_type_absent_returns_none(_patch_lcm) -> None:
    """Source type GUID not found in source TypesOC -> None, no crash."""
    fake_lcm = _patch_lcm
    src_proj = _FakeSrcProject(_FakeFeatureSystem(types_oc=()))
    feat_sys = _FakeFeatureSystemExec()
    sl = _FakeServiceLocator({})
    tgt_proj = _FakeTgtProject(feat_sys, sl)
    ctx = _ctx_exec(src_proj, tgt_proj)

    result = categories.feature_struct_types_execute_action(
        _action(_TYPE_GUID), ctx, WSMapping(), tag=None,
    )

    assert result is None


def test_execute_action_features_rs_member_resolved_is_wired(_patch_lcm) -> None:
    """(c) a FeaturesRS member whose GUID resolves in target FeaturesOC ->
    FeaturesRS.Add() called with the TARGET defn object."""
    fake_lcm = _patch_lcm
    src_defn = _FakeDefn(_DEFN_GUID_RESOLVED)
    src_type = _FakeSrcFeatStrucType(guid=_TYPE_GUID, members=(src_defn,))
    src_proj = _FakeSrcProject(_FakeFeatureSystem(types_oc=(src_type,)))

    tgt_defn = _FakeDefn(_DEFN_GUID_RESOLVED)
    new_type = _FakeNewFeatStrucType()
    factory = _FakeFactory(new_type)
    sl = _FakeServiceLocator({id(fake_lcm.IFsFeatStrucTypeFactory): factory})
    feat_sys = _FakeFeatureSystemExec(features_oc=(tgt_defn,))
    tgt_proj = _FakeTgtProject(feat_sys, sl)

    ctx = _ctx_exec(src_proj, tgt_proj)

    result = categories.feature_struct_types_execute_action(
        _action(_TYPE_GUID), ctx, WSMapping(), tag=None,
    )

    assert result is new_type
    assert list(result.FeaturesRS) == [tgt_defn], (
        "resolved member must be added to FeaturesRS via the TARGET defn object"
    )


def test_execute_action_features_rs_member_unresolved_is_skipped_no_crash(_patch_lcm) -> None:
    """(c) a FeaturesRS member whose GUID has NO target counterpart is
    skipped + logged -- no crash, partial wiring tolerated (FeaturesRS
    stays empty for that member, the type itself is still created)."""
    fake_lcm = _patch_lcm
    src_defn = _FakeDefn(_DEFN_GUID_UNRESOLVED)
    src_type = _FakeSrcFeatStrucType(guid=_TYPE_GUID, members=(src_defn,))
    src_proj = _FakeSrcProject(_FakeFeatureSystem(types_oc=(src_type,)))

    new_type = _FakeNewFeatStrucType()
    factory = _FakeFactory(new_type)
    sl = _FakeServiceLocator({id(fake_lcm.IFsFeatStrucTypeFactory): factory})
    feat_sys = _FakeFeatureSystemExec(features_oc=())  # no matching defn present
    tgt_proj = _FakeTgtProject(feat_sys, sl)

    ctx = _ctx_exec(src_proj, tgt_proj)

    result = categories.feature_struct_types_execute_action(
        _action(_TYPE_GUID), ctx, WSMapping(), tag=None,
    )

    assert result is new_type, "type creation must succeed despite unresolved member"
    assert list(result.FeaturesRS) == [], "unresolved member must not be added"


def test_execute_action_mixed_members_partial_wiring(_patch_lcm) -> None:
    """One resolved + one unresolved member -> only the resolved one is
    wired; the unresolved one is skipped without aborting the whole type."""
    fake_lcm = _patch_lcm
    resolved_defn = _FakeDefn(_DEFN_GUID_RESOLVED)
    unresolved_defn = _FakeDefn(_DEFN_GUID_UNRESOLVED)
    src_type = _FakeSrcFeatStrucType(
        guid=_TYPE_GUID, members=(resolved_defn, unresolved_defn),
    )
    src_proj = _FakeSrcProject(_FakeFeatureSystem(types_oc=(src_type,)))

    tgt_defn = _FakeDefn(_DEFN_GUID_RESOLVED)
    new_type = _FakeNewFeatStrucType()
    factory = _FakeFactory(new_type)
    sl = _FakeServiceLocator({id(fake_lcm.IFsFeatStrucTypeFactory): factory})
    feat_sys = _FakeFeatureSystemExec(features_oc=(tgt_defn,))
    tgt_proj = _FakeTgtProject(feat_sys, sl)

    ctx = _ctx_exec(src_proj, tgt_proj)

    result = categories.feature_struct_types_execute_action(
        _action(_TYPE_GUID), ctx, WSMapping(), tag=None,
    )

    assert result is new_type
    assert list(result.FeaturesRS) == [tgt_defn]


# ============================================================================
# Registry sanity (mirrors test_category_registry.py's own assertions;
# FEATURE_STRUCT_TYPES-specific double-check kept local for fast failure
# attribution when this file is run in isolation).
# ============================================================================

def test_registry_bundle_has_all_required_keys() -> None:
    required = {
        "enumerate_source", "dependencies", "required_writing_systems",
        "plan_action", "execute_action",
    }
    assert set(_BUNDLE.keys()) == required


def test_for_category_dispatch_returns_same_bundle() -> None:
    assert categories.for_category(GrammarCategory.FEATURE_STRUCT_TYPES) is _BUNDLE
