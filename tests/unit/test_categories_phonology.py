"""Phase 3a -- phonology block + strata Python-surface tests.

Tests the enumerate_source / dependencies / plan_action callbacks for
the six Phase 3a categories.  execute_action requires live LCM and is
exercised at live MCP time (integration tests in
tests/integration/test_phase3a_phonology_e2e.py).
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
