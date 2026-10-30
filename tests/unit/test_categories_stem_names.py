"""Unit tests for stem_names leaf-category functions.

Covers:
- dependencies() returns empty tuple (leaf)
- plan_action() ALREADY_PRESENT_BY_GUID skip (when target POS has same GUID)
- plan_action() PlannedAction for new GUID
- enumerate_source() walks all POS stem names
- execute_action() is LCM-bound — integration only

Stem names live in IPartOfSpeech.StemNamesOC; the unit-test fakes duck-type
that surface without importing LCM.
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

class _FakeStemName:
    def __init__(self, guid: str) -> None:
        self.guid = guid


class _FakePOS:
    def __init__(self, guid: str, stem_names=()) -> None:
        self.guid = guid
        # Mimic IPartOfSpeech.StemNamesOC as a simple list
        self.StemNamesOC = list(stem_names)

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


_BUNDLE = categories.for_category(GrammarCategory.STEM_NAMES)


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

def test_dependencies_returns_empty_tuple() -> None:
    sn = _FakeStemName("sn-001")
    assert tuple(_BUNDLE["dependencies"](piece=sn)) == ()


def test_plan_action_new_stem_name_yields_planned_action() -> None:
    sn = _FakeStemName("sn-002")
    src_pos = _FakePOS("pos-A", stem_names=(sn,))
    src = _FakeProject("src", poses=(src_pos,))
    tgt = _FakeProject("tgt", poses=())
    ctx = _ctx(src, tgt)

    result = _BUNDLE["plan_action"](piece=sn, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, PlannedAction)
    assert result.category == GrammarCategory.STEM_NAMES
    assert result.source_guid == "sn-002"


def test_plan_action_already_present_yields_skip() -> None:
    sn = _FakeStemName("sn-003")
    src_pos = _FakePOS("pos-A", stem_names=(sn,))
    src = _FakeProject("src", poses=(src_pos,))
    tgt_sn = _FakeStemName("sn-003")
    tgt_pos = _FakePOS("pos-A", stem_names=(tgt_sn,))
    tgt = _FakeProject("tgt", poses=(tgt_pos,))
    ctx = _ctx(src, tgt)

    result = _BUNDLE["plan_action"](piece=sn, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, Skip)
    assert result.reason == SkipReason.ALREADY_PRESENT_BY_GUID
    assert result.source_guid == "sn-003"


def test_enumerate_source_yields_all_stem_names_across_poses() -> None:
    sn1 = _FakeStemName("sn-100")
    sn2 = _FakeStemName("sn-101")
    pos_a = _FakePOS("pos-X", stem_names=(sn1,))
    pos_b = _FakePOS("pos-Y", stem_names=(sn2,))
    src = _FakeProject("src", poses=(pos_a, pos_b))
    tgt = _FakeProject("tgt")
    ctx = _ctx(src, tgt)
    sel = Selection(categories={GrammarCategory.STEM_NAMES: True})

    items = list(_BUNDLE["enumerate_source"](context=ctx, selection=sel))
    assert sn1 in items
    assert sn2 in items


def test_enumerate_source_empty_when_no_pos() -> None:
    src = _FakeProject("src", poses=())
    tgt = _FakeProject("tgt")
    ctx = _ctx(src, tgt)
    sel = Selection(categories={GrammarCategory.STEM_NAMES: True})

    items = list(_BUNDLE["enumerate_source"](context=ctx, selection=sel))
    assert items == []


@pytest.mark.integration
def test_execute_action_requires_lcm() -> None:
    pytest.skip("LCM required; run as integration test with FlexTools host.")
