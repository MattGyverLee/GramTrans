"""Unit tests for inflection_features leaf-category functions.

Covers:
- dependencies() returns empty tuple (values co-created in execute_action)
- plan_action() GOLD-aware skip (CatalogSourceId non-empty)
- plan_action() ALREADY_PRESENT_BY_GUID skip
- plan_action() PlannedAction for non-GOLD new feature
- execute_action() ClassName dispatch: FsComplexFeature is created (not
  skipped), FsClosedFeature regression guard, FsOpenFeature clean skip
  (coverage-content-fidelity-v2 Part B sub-part 1).
- execute_action() closed-feature Path A/B create is LCM-bound — integration
  only.
"""
from __future__ import annotations

import sys
import types
import uuid

import pytest

import gramtrans.Lib.categories as _cat_mod
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
# Fake objects
# ============================================================================

class _FakeFeature:
    def __init__(self, guid: str, catalog_source_id: str = "") -> None:
        self.guid = guid
        self.CatalogSourceId = catalog_source_id


class _FakeInflFeatureOps:
    def __init__(self, features=()) -> None:
        self._features = list(features)

    def FeatureGetAll(self):
        return list(self._features)


class _FakeProject:
    def __init__(self, name: str, features=()) -> None:
        self.name = name
        self.InflectionFeatures = _FakeInflFeatureOps(features)

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


_BUNDLE = categories.for_category(GrammarCategory.INFLECTION_FEATURES)


# ============================================================================
# Tests
# ============================================================================

def test_dependencies_returns_empty_tuple() -> None:
    feat = _FakeFeature("f-001")
    assert tuple(_BUNDLE["dependencies"](piece=feat)) == ()


def test_plan_action_gold_feature_absent_yields_planned_action() -> None:
    """v7.0.0 GOLD unlock: a GOLD inflection feature is an ordinary item. When
    absent from the target it transfers (PlannedAction), not a GOLD_INVIOLABLE
    skip."""
    gold_feat = _FakeFeature("f-001", catalog_source_id="fDeg")
    src = _FakeProject("src", features=(gold_feat,))
    tgt = _FakeProject("tgt")
    ctx = _ctx(src, tgt)

    result = _BUNDLE["plan_action"](piece=gold_feat, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, PlannedAction)
    assert result.category == GrammarCategory.INFLECTION_FEATURES


def test_plan_action_none_catalog_source_id_is_not_gold() -> None:
    """CatalogSourceId=None should NOT trigger GOLD skip."""
    feat = _FakeFeature("f-002", catalog_source_id="")
    feat.CatalogSourceId = None  # explicitly None
    src = _FakeProject("src", features=(feat,))
    tgt = _FakeProject("tgt")
    ctx = _ctx(src, tgt)

    result = _BUNDLE["plan_action"](piece=feat, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, PlannedAction)


def test_plan_action_already_present_yields_skip() -> None:
    feat = _FakeFeature("f-003")
    src = _FakeProject("src", features=(feat,))
    tgt_feat = _FakeFeature("f-003")
    tgt = _FakeProject("tgt", features=(tgt_feat,))
    ctx = _ctx(src, tgt)

    result = _BUNDLE["plan_action"](piece=feat, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, Skip)
    assert result.reason == SkipReason.ALREADY_PRESENT_BY_GUID


def test_plan_action_new_guid_yields_planned_action() -> None:
    feat = _FakeFeature("f-004")
    src = _FakeProject("src", features=(feat,))
    tgt = _FakeProject("tgt")
    ctx = _ctx(src, tgt)

    result = _BUNDLE["plan_action"](piece=feat, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, PlannedAction)
    assert result.source_guid == "f-004"


def test_enumerate_source_returns_all_features() -> None:
    f1 = _FakeFeature("f-100")
    f2 = _FakeFeature("f-101")
    src = _FakeProject("src", features=(f1, f2))
    tgt = _FakeProject("tgt")
    ctx = _ctx(src, tgt)
    sel = Selection(categories={GrammarCategory.INFLECTION_FEATURES: True})

    items = list(_BUNDLE["enumerate_source"](context=ctx, selection=sel))
    assert f1 in items
    assert f2 in items


@pytest.mark.integration
def test_execute_action_requires_lcm() -> None:
    pytest.skip("LCM required; run as integration test with FlexTools host.")


# ============================================================================
# Feature 031 US2 -- WS-mapped name copy (C3) + feature-level dedup (C4)
# ============================================================================

from gramtrans.Lib import selection as _selection


class _FakeWS:
    def __init__(self, ws_id: str, handle: int) -> None:
        self.Id = ws_id
        self.Handle = handle


class _FakeWSColl:
    def __init__(self, ws=()) -> None:
        self._ws = list(ws)

    def GetAll(self):
        return list(self._ws)


class _FakeTsString:
    def __init__(self, text: str) -> None:
        self.Text = text


class _FakeMultiString:
    """Duck-typed ITsMultiString: text keyed by WS handle."""

    def __init__(self, by_handle=None) -> None:
        self._by_handle = dict(by_handle or {})

    def get_String(self, handle):  # noqa: N802 -- mirrors LCM PascalCase
        return _FakeTsString(self._by_handle.get(handle, ""))

    def set_String(self, handle, tss):  # noqa: N802
        self._by_handle[handle] = tss.Text if hasattr(tss, "Text") else tss


class _FakeStrObj:
    """A feature / value stand-in exposing Name/Abbreviation/Description."""

    def __init__(self) -> None:
        self.Name = _FakeMultiString()
        self.Abbreviation = _FakeMultiString()
        self.Description = _FakeMultiString()


class _WSFakeProject:
    def __init__(self, ws) -> None:
        self.WritingSystems = _FakeWSColl(ws)


# Inject explicit read/make callables so the copy helper never touches SIL --
# a sibling test may leave a partial fake `SIL.LCModel` in sys.modules whose
# ITsString rejects our duck-typed strings.
def _copy_fakes(**kw):
    kw.setdefault("read_text", lambda tss: tss.Text)
    kw.setdefault("make_string", lambda text, handle: _FakeTsString(text))
    return kw


# --- C3: WS-mapped multistring copy (T014) ---------------------------------
#
# Reproduces the Ejagham pair's smoking gun (research.md T004-B): source `etu`
# handle 999000003 vs target `etu` handle 999000002. The pre-fix code wrote the
# name with the SOURCE handle, landing it on a wrong/absent target WS (bare-GUID
# feature). The fix must translate source->target handle by WS Id.

def test_ws_mapped_copy_lands_name_on_target_handle() -> None:
    # source: en=1, etu=999000003 ; target: en=1, etu=999000002
    source = _WSFakeProject([_FakeWS("en", 1), _FakeWS("etu", 999000003)])
    target = _WSFakeProject([_FakeWS("en", 1), _FakeWS("etu", 999000002)])
    src = _FakeStrObj()
    src.Name = _FakeMultiString({1: "Number", 999000003: "Nomba"})
    new = _FakeStrObj()

    categories._copy_multistrings_ws_mapped(
        src, new, ("Name", "Abbreviation", "Description"),
        **_copy_fakes(source=source, target=target, ws_map={}),  # identity map
    )

    # WS-FIDELITY: etu string lands on the TARGET etu handle, not the source one.
    assert new.Name.get_String(999000002).Text == "Nomba"
    assert new.Name.get_String(999000003).Text == ""  # never the source handle
    # NON-NULL-NAME: analysis WS (en, coincident handle) preserved.
    assert new.Name.get_String(1).Text == "Number"


def test_ws_mapped_copy_honors_nonidentity_map() -> None:
    # source vernacular `mgz` (handle 7) -> target `etu` (handle 5) via ws_map.
    source = _WSFakeProject([_FakeWS("mgz", 7)])
    target = _WSFakeProject([_FakeWS("etu", 5)])
    src = _FakeStrObj()
    src.Abbreviation = _FakeMultiString({7: "num"})
    new = _FakeStrObj()

    categories._copy_multistrings_ws_mapped(
        src, new, ("Name", "Abbreviation", "Description"),
        **_copy_fakes(source=source, target=target, ws_map={"mgz": "etu"}),
    )
    assert new.Abbreviation.get_String(5).Text == "num"


def test_ws_mapped_copy_skips_absent_target_ws() -> None:
    # A source WS with no target counterpart is skipped -- never written to a
    # wrong handle (WS-FIDELITY); the field simply stays empty.
    source = _WSFakeProject([_FakeWS("zz", 9)])
    target = _WSFakeProject([_FakeWS("en", 1)])
    src = _FakeStrObj()
    src.Name = _FakeMultiString({9: "orphan"})
    new = _FakeStrObj()

    categories._copy_multistrings_ws_mapped(
        src, new, ("Name",), **_copy_fakes(source=source, target=target, ws_map={}),
    )
    assert new.Name.get_String(1).Text == ""
    assert new.Name.get_String(9).Text == ""


# --- C4: feature-level vs value-level dedup sets (T015) ---------------------

class _FakeClosedFeature031:
    def __init__(self, guid, values=()) -> None:
        self.guid = guid.lower()
        self.Guid = guid
        self.ValuesOC = list(values)


class _FakeValue031:
    def __init__(self, guid) -> None:
        self.guid = guid.lower()
        self.Guid = guid


class _FakeInflOps031:
    def __init__(self, feats) -> None:
        self._feats = list(feats)

    def FeatureGetAll(self):
        return list(self._feats)


class _FakeDedupTarget:
    def __init__(self, feats) -> None:
        self.InflectionFeatures = _FakeInflOps031(feats)


def test_feature_and_value_guid_sets_are_distinct() -> None:
    # C4: a present feature by feature-level GUID classifies via the FEATURE set,
    # not the value set. Pre-fix, both used the value-level set, so a present
    # feature read as `new` and was re-created (duplicate) on re-run.
    val = _FakeValue031("V-1")
    feat = _FakeClosedFeature031("F-1", values=(val,))
    target = _FakeDedupTarget([feat])

    feat_guids = _selection._gather_target_infl_feature_guids(target)
    value_guids = _selection._gather_target_infl_feat_guids(target)

    assert "f-1" in feat_guids
    assert "f-1" not in value_guids  # feature GUID is NOT in the value set
    assert "v-1" in value_guids
    assert "v-1" not in feat_guids


# ============================================================================
# execute_action() ClassName dispatch -- complex/open inflection features
# (coverage-content-fidelity-v2 Part B sub-part 1)
#
# Prior main behavior: any non-IFsClosedFeature source (FsComplexFeature /
# FsOpenFeature) failed the `IFsClosedFeature(src_feat)` cast and was
# reported as Skip(UNSUPPORTED_LCM_TYPE) -- a silent content-fidelity drop.
# These tests lock the fixed dispatch: FsComplexFeature is now CREATED (not
# skipped); FsClosedFeature keeps working (regression guard); FsOpenFeature
# is a clean, documented skip with no orphan LCM object.
# ============================================================================

_FEAT_GUID_B1 = str(uuid.uuid4()).lower()
_TYPE_GUID_B1 = str(uuid.uuid4()).lower()


class _FakeTsStringB1:
    def __init__(self, text: str) -> None:
        self.Text = text


class _FakeMultiStringB1:
    """Minimal duck-typed ITsMultiString: read/write are no-ops that never
    raise, so the WS-mapped copy path (or its GetSyncableProperties-first
    attempt) can run without touching real SIL types."""

    def get_String(self, ws_handle):
        return _FakeTsStringB1("")

    def set_String(self, ws_handle, ts_string):
        pass


class _FakeComplexFeatureB1:
    ClassName = "FsComplexFeature"

    def __init__(self, guid: str, type_ra=None) -> None:
        self.guid = guid
        self.Name = _FakeMultiStringB1()
        self.Abbreviation = _FakeMultiStringB1()
        self.Description = _FakeMultiStringB1()
        self.TypeRA = type_ra


class _FakeOpenFeatureB1:
    ClassName = "FsOpenFeature"

    def __init__(self, guid: str) -> None:
        self.guid = guid


class _FakeValueB1:
    def __init__(self, guid: str) -> None:
        self.guid = guid
        self.Name = _FakeMultiStringB1()
        self.Abbreviation = _FakeMultiStringB1()
        self.Description = _FakeMultiStringB1()


class _FakeClosedFeatureB1:
    ClassName = "FsClosedFeature"

    def __init__(self, guid: str, values=()) -> None:
        self.guid = guid
        self.Name = _FakeMultiStringB1()
        self.Abbreviation = _FakeMultiStringB1()
        self.Description = _FakeMultiStringB1()
        self.ValuesOC = list(values)


class _FakeFeatStrucTypeB1:
    def __init__(self, guid: str) -> None:
        self.guid = guid


class _FakeOCB1(list):
    def Add(self, obj) -> None:
        self.append(obj)


class _FakeFeatureSystemB1:
    def __init__(self, types_oc=(), features_oc=None) -> None:
        self.TypesOC = list(types_oc)
        self.FeaturesOC = _FakeOCB1() if features_oc is None else features_oc


class _FakeNewComplexFeatB1:
    def __init__(self) -> None:
        self.Name = _FakeMultiStringB1()
        self.Abbreviation = _FakeMultiStringB1()
        self.Description = _FakeMultiStringB1()
        self.TypeRA = None


class _FakeNewClosedFeatB1:
    def __init__(self) -> None:
        self.Name = _FakeMultiStringB1()
        self.Abbreviation = _FakeMultiStringB1()
        self.Description = _FakeMultiStringB1()
        self.ValuesOC = _FakeOCB1()


class _FakeNewValueB1:
    def __init__(self) -> None:
        self.Name = _FakeMultiStringB1()
        self.Abbreviation = _FakeMultiStringB1()
        self.Description = _FakeMultiStringB1()


class _FakeWSObjB1:
    def __init__(self, ws_id: str, handle: int) -> None:
        self.Id = ws_id
        self.Handle = handle


class _FakeWSOpsB1:
    def __init__(self, ws_list=()) -> None:
        self._ws_list = list(ws_list)

    def GetAll(self):
        return list(self._ws_list)


class _FakeFactoryB1:
    """Tracks every Create(*args) call and always returns the same object --
    mirrors the live 2-arg-then-1-arg factory idiom without a real LCM host."""

    def __init__(self, obj_to_return) -> None:
        self._obj = obj_to_return
        self.create_calls: list = []

    def Create(self, *args):
        self.create_calls.append(args)
        return self._obj


class _FakeServiceLocatorB1:
    """Maps a factory-interface sentinel to its fake factory. A branch that
    requests a factory NOT registered here raises KeyError -- catching any
    accidental cross-branch dispatch (e.g. a closed feature erroneously
    asking for IFsComplexFeatureFactory) as a loud test failure."""

    def __init__(self, factory_map: dict) -> None:
        self._factory_map = factory_map

    def GetService(self, factory_type):
        return self._factory_map[id(factory_type)]


class _FakeCacheB1:
    def __init__(self, feature_system, service_locator) -> None:
        self.DefaultAnalWs = 1
        self.LangProject = _FakeLangProjectB1(feature_system)
        self.ServiceLocator = service_locator


class _FakeLangProjectB1:
    def __init__(self, feature_system) -> None:
        self.MsFeatureSystemOA = feature_system


class _FakeTgtProjectB1:
    def __init__(self, feature_system, service_locator, ws_list=()) -> None:
        self._cache = _FakeCacheB1(feature_system, service_locator)
        self.WritingSystems = _FakeWSOpsB1(ws_list)

    @property
    def Cache(self):
        return self._cache


class _FakeInflFeatureOpsB1:
    def __init__(self, feature) -> None:
        self._feature = feature

    def FeatureGetAll(self):
        return [self._feature]


class _FakeSrcProjectB1:
    def __init__(self, feature, ws_list=()) -> None:
        self.InflectionFeatures = _FakeInflFeatureOpsB1(feature)
        self.WritingSystems = _FakeWSOpsB1(ws_list)


def _ctx_b1(source, target) -> RunContext:
    ctx = RunContext(
        source_handle=source,
        source_project_name="SrcProj",
        source_project_path="/src",
        target_handle=target,
        target_project_name="TgtProj",
        target_project_path="/tgt",
        run_id="GT-20260715-010000",
        started_at="2026-07-15T01:00:00",
    )
    object.__setattr__(ctx, "_exec_skips", [])
    return ctx


def _action_b1(guid: str) -> PlannedAction:
    return PlannedAction(
        category=GrammarCategory.INFLECTION_FEATURES,
        source_guid=guid,
        intended_target_guid=guid,
        summary="test",
    )


@pytest.fixture()
def _patch_lcm_b1(monkeypatch):
    """Inject a fake SIL.LCModel/System so the function's internal
    `from SIL.LCModel import ...` succeeds offline (no pythonnet host), and
    no-op apply_carrier_b so residue logic doesn't need a real WS handle."""
    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.IFsClosedFeatureFactory = object()
    fake_lcm.IFsClosedFeature = lambda x: x
    fake_lcm.IFsSymFeatValFactory = object()
    fake_lcm.IFsSymFeatVal = lambda x: x
    fake_lcm.IFsComplexFeatureFactory = object()
    fake_lcm.IFsComplexFeature = lambda x: x

    fake_kernel = types.ModuleType("SIL.LCModel.Core.KernelInterfaces")
    fake_kernel.ITsString = lambda x: x
    fake_text = types.ModuleType("SIL.LCModel.Core.Text")
    fake_text.TsStringUtils = type("TsStringUtils", (), {
        "MakeString": staticmethod(lambda text, ws: text)
    })
    fake_system = types.ModuleType("System")
    fake_system.Guid = type("Guid", (), {"Parse": staticmethod(lambda s: s)})

    injected = {
        "SIL": types.ModuleType("SIL"),
        "SIL.LCModel.Core": types.ModuleType("SIL.LCModel.Core"),
        "SIL.LCModel": fake_lcm,
        "SIL.LCModel.Core.KernelInterfaces": fake_kernel,
        "SIL.LCModel.Core.Text": fake_text,
        "System": fake_system,
    }
    originals = {key: sys.modules.get(key) for key in injected}
    sys.modules.update(injected)

    try:
        import gramtrans.Lib.residue as _res_mod
        monkeypatch.setattr(_res_mod, "apply_carrier_b", lambda feat, ws, tag: None)
    except Exception:
        pass

    yield fake_lcm

    for key, orig in originals.items():
        if orig is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = orig


def test_execute_action_complex_feature_creates_object_not_skipped(_patch_lcm_b1) -> None:
    """(a) FsComplexFeature -> feature IS created, not routed to the
    Skip(UNSUPPORTED_LCM_TYPE) refusal. TypeRA wired when the target
    struct-type is resolvable by GUID."""
    fake_lcm = _patch_lcm_b1
    src_type = _FakeFeatStrucTypeB1(guid=_TYPE_GUID_B1)
    src_feat = _FakeComplexFeatureB1(guid=_FEAT_GUID_B1, type_ra=src_type)

    tgt_type = _FakeFeatStrucTypeB1(guid=_TYPE_GUID_B1)
    feat_sys = _FakeFeatureSystemB1(types_oc=[tgt_type])
    new_complex_feat = _FakeNewComplexFeatB1()
    complex_factory = _FakeFactoryB1(new_complex_feat)
    sl = _FakeServiceLocatorB1({id(fake_lcm.IFsComplexFeatureFactory): complex_factory})

    tgt_proj = _FakeTgtProjectB1(feat_sys, sl)
    src_proj = _FakeSrcProjectB1(src_feat)
    ctx = _ctx_b1(src_proj, tgt_proj)

    result = categories.inflection_features_execute_action(
        _action_b1(_FEAT_GUID_B1), ctx, WSMapping(), tag=None,
    )

    assert result is new_complex_feat, "complex feature was not created"
    assert ctx._exec_skips == [], "complex feature must not be reported as a skip"
    assert complex_factory.create_calls, "IFsComplexFeatureFactory.Create was not called"
    assert result.TypeRA is tgt_type, "TypeRA not wired to matching target struct-type"


def test_execute_action_complex_feature_type_ra_absent_degrades_gracefully(_patch_lcm_b1) -> None:
    """Cross-sub-part dependency: FEATURE_STRUCT_TYPES (a later coverage
    sub-part) may not have created the target struct-type yet. TypeRA must
    be left unset -- no crash -- rather than fail the whole feature create."""
    fake_lcm = _patch_lcm_b1
    src_type = _FakeFeatStrucTypeB1(guid=_TYPE_GUID_B1)
    src_feat = _FakeComplexFeatureB1(guid=_FEAT_GUID_B1, type_ra=src_type)

    feat_sys = _FakeFeatureSystemB1(types_oc=())  # target struct-type absent
    new_complex_feat = _FakeNewComplexFeatB1()
    complex_factory = _FakeFactoryB1(new_complex_feat)
    sl = _FakeServiceLocatorB1({id(fake_lcm.IFsComplexFeatureFactory): complex_factory})

    tgt_proj = _FakeTgtProjectB1(feat_sys, sl)
    src_proj = _FakeSrcProjectB1(src_feat)
    ctx = _ctx_b1(src_proj, tgt_proj)

    result = categories.inflection_features_execute_action(
        _action_b1(_FEAT_GUID_B1), ctx, WSMapping(), tag=None,
    )

    assert result is new_complex_feat
    assert result.TypeRA is None, "TypeRA must stay unset when target type absent"
    assert ctx._exec_skips == []  # graceful degrade, not a skip


def test_execute_action_closed_feature_still_works(_patch_lcm_b1) -> None:
    """(b) Regression guard: FsClosedFeature keeps using the existing GOLD
    Path A create + IFsSymFeatVal co-create -- untouched by the new
    complex/open branches. IFsComplexFeatureFactory is deliberately NOT
    registered in the service locator, so any accidental cross-branch
    dispatch raises KeyError (a loud test failure)."""
    fake_lcm = _patch_lcm_b1
    val_guid = str(uuid.uuid4()).lower()
    src_val = _FakeValueB1(guid=val_guid)
    src_feat = _FakeClosedFeatureB1(guid=_FEAT_GUID_B1, values=(src_val,))

    feat_sys = _FakeFeatureSystemB1()
    new_closed_feat = _FakeNewClosedFeatB1()
    new_val = _FakeNewValueB1()
    closed_factory = _FakeFactoryB1(new_closed_feat)
    value_factory = _FakeFactoryB1(new_val)
    sl = _FakeServiceLocatorB1({
        id(fake_lcm.IFsClosedFeatureFactory): closed_factory,
        id(fake_lcm.IFsSymFeatValFactory): value_factory,
    })

    tgt_proj = _FakeTgtProjectB1(feat_sys, sl)
    src_proj = _FakeSrcProjectB1(src_feat)
    ctx = _ctx_b1(src_proj, tgt_proj)

    result = categories.inflection_features_execute_action(
        _action_b1(_FEAT_GUID_B1), ctx, WSMapping(), tag=None,
    )

    assert result is new_closed_feat
    assert ctx._exec_skips == []
    assert closed_factory.create_calls, "IFsClosedFeatureFactory.Create was not called"
    assert value_factory.create_calls, "IFsSymFeatValFactory.Create was not called"


def test_execute_action_open_feature_clean_skip(_patch_lcm_b1) -> None:
    """(c) FsOpenFeature -> clean documented skip: returns None, attaches
    nothing to FeaturesOC (no orphan), and records a single NEEDS_MANUAL
    Skip for the category."""
    src_feat = _FakeOpenFeatureB1(guid=_FEAT_GUID_B1)
    feat_sys = _FakeFeatureSystemB1()
    sl = _FakeServiceLocatorB1({})  # no factory should be requested at all

    tgt_proj = _FakeTgtProjectB1(feat_sys, sl)
    src_proj = _FakeSrcProjectB1(src_feat)
    ctx = _ctx_b1(src_proj, tgt_proj)

    result = categories.inflection_features_execute_action(
        _action_b1(_FEAT_GUID_B1), ctx, WSMapping(), tag=None,
    )

    assert result is None, "FsOpenFeature should return None (clean skip)"
    assert len(feat_sys.FeaturesOC) == 0, "FsOpenFeature must not attach anything to FeaturesOC"
    assert len(ctx._exec_skips) == 1
    skip = ctx._exec_skips[0]
    assert skip.category == GrammarCategory.INFLECTION_FEATURES
    assert skip.source_guid == _FEAT_GUID_B1
    assert skip.reason == SkipReason.NEEDS_MANUAL

