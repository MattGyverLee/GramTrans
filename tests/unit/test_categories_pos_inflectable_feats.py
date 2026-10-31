"""Unit tests for pos_inflectable_feats leaf-category functions
(coverage-content-fidelity-v2 Part B sub-part 3).

POS_INFLECTABLE_FEATS is a PURE REFERENCE-WIRING category: for every POS in
the source, each IFsFeatDefn in IPartOfSpeech.InflectableFeatsRC must be
wired into the corresponding target POS's InflectableFeatsRC. The feature
definition itself is already created in the target by inflection_features
(Part B.1) -- this category creates NO new LCM object, copies NO
multistrings, and applies NO residue tag.

Piece shape: (pos_guid_str, feat_defn_obj). Compound source_guid:
"pos_guid::feat_guid".

Covers:
- enumerate_source() walks all POS InflectableFeatsRC, yielding
  (pos_guid, feat_obj) tuples.
- dependencies() / required_writing_systems() return empty tuples.
- plan_action():
  (d) piece not a 2-tuple -> Skip(UNSUPPORTED_LCM_TYPE).
  (c) already-wired-by-GUID in target POS -> Skip(ALREADY_PRESENT_BY_GUID).
  new compound guid -> PlannedAction.
- execute_action():
  (a) feat defn GUID present in target FeaturesOC -> InflectableFeatsRC.Add()
      called on the matching target POS; returns the target feat.
  (b) feat defn GUID absent in target FeaturesOC -> None, warning logged,
      no Add, no crash.
  (e) target POS absent -> None.
- registry test: POS_INFLECTABLE_FEATS present in the leaf registry.
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
from _sil_guard import force_sil_loaded


# ============================================================================
# Fakes (POS-owned shape -- mirrors test_categories_inflection_classes.py)
# ============================================================================

class _FakeFeatDefn:
    def __init__(self, guid: str) -> None:
        self.guid = guid.lower()
        self.Guid = guid


class _FakePOS:
    def __init__(self, guid: str, inflectable_feats=()) -> None:
        self.guid = guid.lower()
        self.Guid = guid
        # Mimic IPartOfSpeech.InflectableFeatsRC as a plain list; execute_action
        # tests swap this for an Add-tracking list.
        self.InflectableFeatsRC = list(inflectable_feats)

    @property
    def concrete(self):
        return self


class _FakeAddTrackingList(list):
    def Add(self, obj) -> None:
        self.append(obj)


class _FakePOSOps:
    def __init__(self, poses=()) -> None:
        self._poses = list(poses)

    def GetAll(self, recursive=True):
        return list(self._poses)


class _FakeProject:
    def __init__(self, poses=()) -> None:
        self.POS = _FakePOSOps(poses)


def _ctx(source, target) -> RunContext:
    return RunContext(
        source_handle=source,
        source_project_name="SrcProj",
        source_project_path="/src",
        target_handle=target,
        target_project_name="TgtProj",
        target_project_path="/tgt",
        run_id="GT-20260715-040000",
        started_at="2026-07-15T04:00:00",
    )


_BUNDLE = categories.for_category(GrammarCategory.POS_INFLECTABLE_FEATS)


@pytest.fixture(autouse=True)
def _real_sil_loaded():
    """Issue #58: no `sys.modules` stub. FORCE-LOAD the real SIL assemblies
    (when this machine has them) so every test below drives the duck-typed
    fakes through production code with a live `SIL.LCModel` in-process --
    the condition under which a cast-inside-try with no duck fallback used to
    silently drop the fake. Host-free, the same assertions must hold.
    (Guard shape: tests/unit/test_reversal_walk.py, 201d9cd.)"""
    force_sil_loaded()
    yield


# ============================================================================
# enumerate_source / dependencies / required_writing_systems
# ============================================================================

def test_enumerate_source_yields_pos_feat_tuples_across_poses() -> None:
    feat1 = _FakeFeatDefn("feat-100")
    feat2 = _FakeFeatDefn("feat-101")
    pos_a = _FakePOS("pos-X", inflectable_feats=(feat1,))
    pos_b = _FakePOS("pos-Y", inflectable_feats=(feat2,))
    src = _FakeProject(poses=(pos_a, pos_b))
    tgt = _FakeProject()
    ctx = _ctx(src, tgt)
    sel = Selection(categories={GrammarCategory.POS_INFLECTABLE_FEATS: True})

    items = list(_BUNDLE["enumerate_source"](context=ctx, selection=sel))

    assert ("pos-x", feat1) in items
    assert ("pos-y", feat2) in items
    assert len(items) == 2


def test_enumerate_source_empty_when_no_pos() -> None:
    src = _FakeProject(poses=())
    tgt = _FakeProject()
    ctx = _ctx(src, tgt)
    sel = Selection(categories={GrammarCategory.POS_INFLECTABLE_FEATS: True})

    assert list(_BUNDLE["enumerate_source"](context=ctx, selection=sel)) == []


def test_dependencies_returns_owner_pos_edge() -> None:
    piece = ("pos-a", _FakeFeatDefn("feat-1"))
    assert tuple(_BUNDLE["dependencies"](piece=piece)) == (
        (GrammarCategory.GRAM_CATEGORIES, "pos-a"),
    )


def test_dependencies_none_owner_returns_empty_tuple() -> None:
    piece = (None, _FakeFeatDefn("feat-1"))
    assert tuple(_BUNDLE["dependencies"](piece=piece)) == ()


def test_dependencies_non_tuple_piece_returns_empty_tuple() -> None:
    assert tuple(_BUNDLE["dependencies"](piece="not-a-tuple")) == ()


def test_required_writing_systems_returns_empty_tuple() -> None:
    piece = ("pos-a", _FakeFeatDefn("feat-1"))
    assert tuple(_BUNDLE["required_writing_systems"](piece=piece)) == ()


# ============================================================================
# plan_action()
# ============================================================================

def test_plan_action_new_guid_yields_planned_action() -> None:
    feat = _FakeFeatDefn("feat-200")
    pos_a = _FakePOS("pos-A", inflectable_feats=(feat,))
    src = _FakeProject(poses=(pos_a,))
    tgt = _FakeProject(poses=(_FakePOS("pos-A"),))
    ctx = _ctx(src, tgt)

    piece = ("pos-a", feat)
    result = _BUNDLE["plan_action"](piece=piece, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, PlannedAction)
    assert result.category == GrammarCategory.POS_INFLECTABLE_FEATS
    assert result.source_guid == "pos-a::feat-200"


def test_plan_action_already_wired_yields_skip() -> None:
    feat = _FakeFeatDefn("feat-201")
    tgt_feat = _FakeFeatDefn("feat-201")  # same GUID, already wired in target
    pos_a = _FakePOS("pos-A", inflectable_feats=(feat,))
    src = _FakeProject(poses=(pos_a,))
    tgt_pos = _FakePOS("pos-A", inflectable_feats=(tgt_feat,))
    tgt = _FakeProject(poses=(tgt_pos,))
    ctx = _ctx(src, tgt)

    piece = ("pos-a", feat)
    result = _BUNDLE["plan_action"](piece=piece, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, Skip)
    assert result.reason == SkipReason.ALREADY_PRESENT_BY_GUID


def test_plan_action_not_a_2_tuple_yields_unsupported_skip() -> None:
    ctx = _ctx(_FakeProject(), _FakeProject())
    result = _BUNDLE["plan_action"](piece="not-a-tuple", context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, Skip)
    assert result.reason == SkipReason.UNSUPPORTED_LCM_TYPE


def test_plan_action_wrong_length_tuple_yields_unsupported_skip() -> None:
    ctx = _ctx(_FakeProject(), _FakeProject())
    piece = ("only-one-element",)
    result = _BUNDLE["plan_action"](piece=piece, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, Skip)
    assert result.reason == SkipReason.UNSUPPORTED_LCM_TYPE


# ============================================================================
# execute_action()
# ============================================================================

class _FakeFeatureSystemExec:
    def __init__(self, features_oc=()) -> None:
        self.FeaturesOC = list(features_oc)


class _FakeLangProjectExec:
    def __init__(self, feature_system) -> None:
        self.MsFeatureSystemOA = feature_system


class _FakeCacheExec:
    def __init__(self, feature_system) -> None:
        self.LangProject = _FakeLangProjectExec(feature_system)


class _FakeTgtProject:
    def __init__(self, poses=(), features_oc=()) -> None:
        self.POS = _FakePOSOps(poses)
        self._cache = _FakeCacheExec(_FakeFeatureSystemExec(features_oc))

    @property
    def Cache(self):
        return self._cache


def _action(pos_guid: str, feat_guid: str) -> PlannedAction:
    compound = f"{pos_guid}::{feat_guid}"
    return PlannedAction(
        category=GrammarCategory.POS_INFLECTABLE_FEATS,
        source_guid=compound,
        intended_target_guid=compound,
        summary="test",
    )


def test_execute_action_records_intent_and_never_writes() -> None:
    """Issue #133 (single writer): the executor records the (pos, feature)
    pair as intent in `feature_category_links` and does NOT Add -- the one
    writer is `_run_infl_feature_link_pass`. It reports not-added so the leaf
    count never claims a write it did not make."""
    tgt_feat = _FakeFeatDefn("feat-300")
    tgt_pos = _FakePOS("pos-A")
    tgt_pos.InflectableFeatsRC = _FakeAddTrackingList()
    tgt = _FakeTgtProject(poses=(tgt_pos,), features_oc=(tgt_feat,))
    ctx = _ctx(_FakeProject(), tgt)
    links: dict = {}
    object.__setattr__(ctx, "_feature_category_links", links)

    result = _BUNDLE["execute_action"](
        _action("pos-a", "feat-300"), ctx, WSMapping(), tag=None,
    )

    assert result.status == "skipped" and result.recorded is True
    assert list(tgt_pos.InflectableFeatsRC) == []   # no Add from here
    assert links == {"pos-a": ["feat-300"]}


def test_execute_action_without_binding_channel_is_skipped_not_written() -> None:
    tgt_pos = _FakePOS("pos-A")
    tgt_pos.InflectableFeatsRC = _FakeAddTrackingList()
    tgt = _FakeTgtProject(poses=(tgt_pos,), features_oc=(_FakeFeatDefn("f"),))
    ctx = _ctx(_FakeProject(), tgt)

    result = _BUNDLE["execute_action"](
        _action("pos-a", "f"), ctx, WSMapping(), tag=None,
    )

    assert result.status == "skipped"
    assert list(tgt_pos.InflectableFeatsRC) == []


def test_execute_action_target_pos_absent_returns_none() -> None:
    """(e) target POS absent -> None."""
    tgt_feat = _FakeFeatDefn("feat-300")
    tgt = _FakeTgtProject(poses=(), features_oc=(tgt_feat,))
    ctx = _ctx(_FakeProject(), tgt)

    result = _BUNDLE["execute_action"](
        _action("pos-missing", "feat-300"), ctx, WSMapping(), tag=None,
    )

    # Issue #68: a decline is an explicit skipped outcome, not None.
    assert result is not None and result.status == "skipped"


def test_execute_action_malformed_compound_guid_returns_none() -> None:
    tgt = _FakeTgtProject(poses=(_FakePOS("pos-A"),), features_oc=())
    ctx = _ctx(_FakeProject(), tgt)
    action = PlannedAction(
        category=GrammarCategory.POS_INFLECTABLE_FEATS,
        source_guid="no-separator-here",
        intended_target_guid="no-separator-here",
        summary="test",
    )

    result = _BUNDLE["execute_action"](action, ctx, WSMapping(), tag=None)
    # Issue #68: a decline is an explicit skipped outcome, not None.
    assert result is not None and result.status == "skipped"


# ============================================================================
# Registry sanity
# ============================================================================

def test_registry_bundle_has_all_required_keys() -> None:
    required = {
        "enumerate_source", "dependencies", "required_writing_systems",
        "plan_action", "execute_action",
    }
    assert set(_BUNDLE.keys()) == required


def test_for_category_dispatch_returns_same_bundle() -> None:
    assert categories.for_category(GrammarCategory.POS_INFLECTABLE_FEATS) is _BUNDLE


def test_registry_test_category_registry_includes_pos_inflectable_feats() -> None:
    """Full registration tripwire (mirrors test_category_registry.py)."""
    assert GrammarCategory.POS_INFLECTABLE_FEATS in categories.LEAF_CATEGORIES
