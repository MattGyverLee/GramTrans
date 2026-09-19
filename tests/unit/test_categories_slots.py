"""Unit tests for Phase 3c US2 slots leaf-category functions (T032-T033).

Slots are IMoInflAffixSlot owned by IPartOfSpeech.AffixSlotsOC. Covers:
- T032 enumerate_source + plan_action: one PlannedAction per source slot,
  GUID preserved (intended_target_guid == source GUID), owner POS resolvable.
- T033 plan_action collision guard: slot GUID already in target →
  Skip(ALREADY_PRESENT_BY_GUID) per FR-334.

execute_action is LCM-bound (IMoInflAffixSlotFactory); the live creation +
owner-attach is exercised by the integration suite (T041 / Scenario A).
"""
from __future__ import annotations

import sys
import types

import pytest

# THE MODULE-LEVEL `xfail` MARK IS GONE (feature 038, T069).
#
# It was added when Phase 3c T029 slots leaf-dispatch was still a
# `raise NotImplementedError` stub. T029 landed; the mark did not. All four
# tests in this file were XPASSING, and a non-strict xfail that xpasses is a
# test that cannot fail: pytest reports XPASS, the run stays green, and no gate
# notices. Found while mutation-verifying T068/T069, where breaking
# `slots_dependencies` outright left `tests/unit` at "3426 passed" with no
# failures. Removed rather than re-pointed; all four tests pass on their own
# merits.

from gramtrans.Lib import categories
import gramtrans.Lib.categories as _cat_mod
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
# Fakes (duck-typed POS / slot surfaces)
# ============================================================================

class _FakeSlot:
    def __init__(self, guid: str) -> None:
        self.guid = guid


class _FakePOS:
    def __init__(self, guid: str, slots=()) -> None:
        self.guid = guid
        self.AffixSlotsOC = list(slots)

    @property
    def concrete(self):
        return self


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
        source_project_name="Src",
        source_project_path="/src",
        target_handle=target,
        target_project_name="Tgt",
        target_project_path="/tgt",
        run_id="GT-20260628-010000",
        started_at="2026-06-28T01:00:00",
    )


_BUNDLE = categories.for_category(GrammarCategory.SLOTS)


@pytest.fixture(autouse=True)
def _patch_lcm_cast(monkeypatch):
    """Identity-cast IPartOfSpeech + guid-from-attr so fakes work host-free."""
    monkeypatch.setattr(
        _cat_mod, "_guid_str_from",
        lambda obj: str(getattr(obj, "guid", "")).lower(),
    )

    class _Identity:
        def __new__(cls, obj):
            return obj

    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.IPartOfSpeech = _Identity
    fake_lcm.ICmObject = _Identity
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    original = sys.modules.get("SIL.LCModel")
    sys.modules["SIL.LCModel"] = fake_lcm
    yield
    if original is None:
        sys.modules.pop("SIL.LCModel", None)
    else:
        sys.modules["SIL.LCModel"] = original


# ============================================================================
# Tests
# ============================================================================

def test_dependencies_are_empty_only_when_the_owner_is_unavailable() -> None:
    """RE-POINTED by feature 038 T068, which falsified this test's premise.

    It used to be called `test_dependencies_returns_empty_tuple` and asserted
    `()` for a slot -- true of `_FakeSlot`, which has no `Owner`, and false of
    the producer: `slots_dependencies` yields
    `(GRAM_CATEGORIES, owning_pos_guid)`, and T068 registered exactly that edge
    as `DependencyKind.SLOT_TO_POS` after measuring it live (19 edges over 5
    POSes on `Mbugwe LizzieHC practice`, 9 over 6 on `Ejagham Mini`).

    Both branches are asserted now, because the empty case is a real one that
    the docstring promises ("empty when the owner is unavailable") and asserting
    only it made a passing test out of an incomplete fake.
    """
    assert tuple(_BUNDLE["dependencies"](piece=_FakeSlot("s-1"))) == ()

    class _OwnedSlot:
        def __init__(self, guid, owner_guid):
            self.guid = guid
            self.Owner = _FakePOS(owner_guid)

    deps = tuple(_BUNDLE["dependencies"](
        piece=_OwnedSlot("s-2", "pos-verb")))
    assert deps == ((GrammarCategory.GRAM_CATEGORIES, "pos-verb"),)

    # And the NARROW producer the registry row actually names must agree with
    # the composite -- a row whose producer diverged from the composite it
    # wraps would be verified against evidence about a different function.
    assert tuple(categories.slots_pos_dependencies(
        _OwnedSlot("s-3", "pos-noun"))) == (
            (GrammarCategory.GRAM_CATEGORIES, "pos-noun"),)


def test_enumerate_source_yields_all_slots_across_poses() -> None:
    s1 = _FakeSlot("slot-1")
    s2 = _FakeSlot("slot-2")
    pos_a = _FakePOS("pos-verb", slots=(s1,))
    pos_b = _FakePOS("pos-noun", slots=(s2,))
    src = _FakeProject(poses=(pos_a, pos_b))
    ctx = _ctx(src, _FakeProject())

    items = list(_BUNDLE["enumerate_source"](ctx, None))
    assert {i.guid for i in items} == {"slot-1", "slot-2"}


def test_slot_creation_under_pos() -> None:
    """T032: 1 source slot under Verb POS, target has Verb POS already →
    plan_action emits a GUID-preserving PlannedAction (intended == source)."""
    slot = _FakeSlot("slot-verb-1")
    src_pos = _FakePOS("pos-verb", slots=(slot,))
    src = _FakeProject(poses=(src_pos,))
    # Target already has the owner POS but NOT the slot.
    tgt = _FakeProject(poses=(_FakePOS("pos-verb", slots=()),))
    ctx = _ctx(src, tgt)

    result = _BUNDLE["plan_action"](piece=slot, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, PlannedAction)
    assert result.category == GrammarCategory.SLOTS
    assert result.source_guid == "slot-verb-1"
    # GUID preserved (E8: slots created via Create(Guid)).
    assert result.intended_target_guid == "slot-verb-1"


def test_slot_collision_already_present_by_guid() -> None:
    """T033: slot GUID already under a target POS → Skip(ALREADY_PRESENT_BY_GUID)."""
    slot = _FakeSlot("slot-dup")
    src_pos = _FakePOS("pos-verb", slots=(slot,))
    src = _FakeProject(poses=(src_pos,))
    tgt = _FakeProject(poses=(_FakePOS("pos-verb", slots=(_FakeSlot("slot-dup"),)),))
    ctx = _ctx(src, tgt)

    result = _BUNDLE["plan_action"](piece=slot, context=ctx, ws_mapping=WSMapping())

    assert isinstance(result, Skip)
    assert result.reason == SkipReason.ALREADY_PRESENT_BY_GUID
    assert result.source_guid == "slot-dup"


@pytest.mark.integration
def test_slot_execute_requires_lcm() -> None:
    pytest.skip("LCM required; live slot creation covered by integration suite.")
