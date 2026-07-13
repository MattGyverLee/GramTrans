"""Unit tests for inflection_features leaf-category functions.

Covers:
- dependencies() returns empty tuple (values co-created in execute_action)
- plan_action() GOLD-aware skip (CatalogSourceId non-empty)
- plan_action() ALREADY_PRESENT_BY_GUID skip
- plan_action() PlannedAction for non-GOLD new feature
- execute_action() is LCM-bound — integration only
"""
from __future__ import annotations

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

