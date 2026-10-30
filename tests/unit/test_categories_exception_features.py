"""Unit tests for exception_features leaf-category functions.

Covers:
- dependencies() returns empty tuple
- plan_action() with malformed piece yields UNSUPPORTED_LCM_TYPE skip
- plan_action() already-wired yields ALREADY_PRESENT_BY_GUID skip
- plan_action() new wiring yields PlannedAction with compound guid
- enumerate_source() yields (pos_guid, val_obj) pairs
- execute_action() wires the value / skips when absent (fakes; #58)

Exception features in FLEx are IFsSymFeatVal references wired into
IPartOfSpeech.ExceptionFeaturesOC.  The piece here is a
(pos_guid_str, sym_feat_val_obj) tuple.

CAVEAT (#58, verified live): IPartOfSpeech has NO `ExceptionFeaturesOC` on
LCM 9 (FLExToolsMCP lists no such property; a live read raises
AttributeError). These are FAKE-CONTRACT tests of the category's code paths
only -- they do not prove the category transfers anything live. Follow-up
pending to re-model the category on the real LCM surface.
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

class _FakeVal:
    def __init__(self, guid: str) -> None:
        self.guid = guid


class _FakePOS:
    def __init__(self, guid: str, exception_vals=()) -> None:
        self.guid = guid
        self.ExceptionFeaturesOC = list(exception_vals)

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


_BUNDLE = categories.for_category(GrammarCategory.EXCEPTION_FEATURES)


# ============================================================================
# Real-host guard (issue #58) -- no SIL stub, no cast monkeypatch.
# ============================================================================

from _sil_guard import force_sil_loaded


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
# Tests
# ============================================================================

def test_dependencies_returns_owner_pos_edge() -> None:
    piece = ("pos-aaa", _FakeVal("val-bbb"))
    assert tuple(_BUNDLE["dependencies"](piece=piece)) == (
        (GrammarCategory.GRAM_CATEGORIES, "pos-aaa"),
    )


def test_dependencies_none_owner_returns_empty_tuple() -> None:
    assert tuple(_BUNDLE["dependencies"](piece=(None, _FakeVal("v")))) == ()


def test_dependencies_non_tuple_piece_returns_empty_tuple() -> None:
    assert tuple(_BUNDLE["dependencies"](piece="not-a-tuple")) == ()


def test_plan_action_malformed_piece_yields_unsupported_lcm_type_skip() -> None:
    """Non-tuple piece → UNSUPPORTED_LCM_TYPE skip (robust error path)."""
    result = _BUNDLE["plan_action"](piece="not-a-tuple", context=object(), ws_mapping=WSMapping())

    assert isinstance(result, Skip)
    assert result.reason == SkipReason.UNSUPPORTED_LCM_TYPE


def test_plan_action_new_wiring_yields_planned_action() -> None:
    val = _FakeVal("v-001")
    pos = _FakePOS("p-001", exception_vals=())
    src = _FakeProject("src", poses=(pos,))
    tgt = _FakeProject("tgt", poses=())
    ctx = _ctx(src, tgt)

    piece = ("p-001", val)
    result = _BUNDLE["plan_action"](piece=piece, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, PlannedAction)
    assert result.category == GrammarCategory.EXCEPTION_FEATURES
    # compound guid encodes both pos and val
    assert "p-001" in result.source_guid
    assert "v-001" in result.source_guid
    assert "::" in result.source_guid


def test_plan_action_already_wired_yields_already_present_skip() -> None:
    val = _FakeVal("v-002")
    pos_src = _FakePOS("p-002", exception_vals=(val,))
    src = _FakeProject("src", poses=(pos_src,))
    tgt_val = _FakeVal("v-002")
    tgt_pos = _FakePOS("p-002", exception_vals=(tgt_val,))
    tgt = _FakeProject("tgt", poses=(tgt_pos,))
    ctx = _ctx(src, tgt)

    piece = ("p-002", val)
    result = _BUNDLE["plan_action"](piece=piece, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, Skip)
    assert result.reason == SkipReason.ALREADY_PRESENT_BY_GUID


def test_enumerate_source_yields_pos_guid_val_tuples() -> None:
    v1 = _FakeVal("v-100")
    v2 = _FakeVal("v-101")
    pos = _FakePOS("p-010", exception_vals=(v1, v2))
    src = _FakeProject("src", poses=(pos,))
    tgt = _FakeProject("tgt")
    ctx = _ctx(src, tgt)
    sel = Selection(categories={GrammarCategory.EXCEPTION_FEATURES: True})

    items = list(_BUNDLE["enumerate_source"](context=ctx, selection=sel))
    assert len(items) == 2
    pos_guids = [t[0] for t in items]
    val_objs = [t[1] for t in items]
    assert all(g == "p-010" for g in pos_guids)
    assert v1 in val_objs
    assert v2 in val_objs


def test_enumerate_source_empty_when_no_poses() -> None:
    src = _FakeProject("src", poses=())
    tgt = _FakeProject("tgt")
    ctx = _ctx(src, tgt)
    sel = Selection(categories={GrammarCategory.EXCEPTION_FEATURES: True})

    items = list(_BUNDLE["enumerate_source"](context=ctx, selection=sel))
    assert items == []


# execute_action(): reference wiring only (no factory, no Guid parse), so it
# is fake-drivable. Issue #58: the IFsSymFeatVal cast used to sit inside the
# compare's try, so with SIL loaded a fake value was reported absent.

class _FakeAddList(list):
    def Add(self, obj) -> None:
        self.append(obj)


class _FakeClosedFeature:
    def __init__(self, guid: str, values=()) -> None:
        self.guid = guid
        self.ValuesOC = list(values)


class _FakeTgtProject(_FakeProject):
    def __init__(self, poses=(), features=()) -> None:
        super().__init__("tgt", poses=poses)
        fs = type("FS", (), {"FeaturesOC": list(features)})()
        lp = type("LP", (), {"MsFeatureSystemOA": fs})()
        self.Cache = type("Cache", (), {"LangProject": lp})()


def _exec_action(pos_guid: str, val_guid: str) -> PlannedAction:
    compound = f"{pos_guid}::{val_guid}"
    return PlannedAction(
        category=GrammarCategory.EXCEPTION_FEATURES,
        source_guid=compound, intended_target_guid=compound, summary="test",
    )


def test_execute_action_wires_value_into_target_pos() -> None:
    val = _FakeVal("v-300")
    tgt_pos = _FakePOS("p-300")
    tgt_pos.ExceptionFeaturesOC = _FakeAddList()
    tgt = _FakeTgtProject(poses=(tgt_pos,),
                          features=(_FakeClosedFeature("f-1", (val,)),))
    ctx = _ctx(_FakeProject("src"), tgt)

    result = _BUNDLE["execute_action"](
        _exec_action("p-300", "v-300"), ctx, WSMapping(), tag=None)

    assert result is val
    assert list(tgt_pos.ExceptionFeaturesOC) == [val]


def test_execute_action_value_absent_is_skipped_no_add() -> None:
    tgt_pos = _FakePOS("p-301")
    tgt_pos.ExceptionFeaturesOC = _FakeAddList()
    tgt = _FakeTgtProject(poses=(tgt_pos,),
                          features=(_FakeClosedFeature("f-1", ()),))
    ctx = _ctx(_FakeProject("src"), tgt)

    result = _BUNDLE["execute_action"](
        _exec_action("p-301", "v-missing"), ctx, WSMapping(), tag=None)

    assert result is not None and result.status == "skipped"
    assert list(tgt_pos.ExceptionFeaturesOC) == []
