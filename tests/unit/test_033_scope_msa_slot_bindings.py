"""Issue #33 -- scope `plan.msa_slot_bindings` to the run.

`preview._populate_msa_slot_bindings` reports every bound MSA in the SOURCE.
Before #33 that whole-source dict went straight onto the plan, so on a partial
selection the 17.1 sub-pass (`categories._run_171_subpass`) also saw bindings
for affixes the user never picked. Any such affix already sitting in the
destination (an earlier run, a shared ancestor) with its slot missing came
back as a `Skip(DEPENDENCY_UNRESOLVED)` -- noise about an affix the run never
touched.

The fix narrows the dict at plan time (`preview._scope_msa_slot_bindings`):
a link is kept if its affix entry is in the run's scope (whole), or if any of
its slots are (trimmed to those slots); otherwise it is dropped.

Asserted here:
  (a) a partial selection yields no out-of-scope bindings and no spurious
      DEPENDENCY_UNRESOLVED from the consumer;
  (b) a full selection yields exactly the producer's whole-source bindings;
  (c) an in-scope binding whose slot is genuinely missing still reports
      DEPENDENCY_UNRESOLVED.

Host-free: every source/target here is a duck-typed fake. Branching between
live and duck modes is decided by the OBJECT (`_resolve_slot_binding_casts`
probes the first entry), not by whether SIL imports succeed -- issue #55.
"""
from __future__ import annotations

import types
from types import SimpleNamespace

from gramtrans.Lib import categories
from gramtrans.Lib import preview as preview_mod
from gramtrans.Lib.models import (
    GrammarCategory,
    PlannedAction,
    RunContext,
    Selection,
    Skip,
    SkipReason,
    WSMapping,
)
from gramtrans.Lib.preview import build_run_plan


# ============================================================================
# Fakes
# ============================================================================

class _MorphType:
    def __init__(self, is_affix: bool = True) -> None:
        self.IsAffixType = is_affix


class _LexForm:
    def __init__(self, is_affix: bool = True) -> None:
        self.MorphTypeRA = _MorphType(is_affix)


class _Obj:
    """Anything that only needs a `.guid` (slot, target entry)."""

    def __init__(self, guid: str) -> None:
        self.guid = guid


class _MSA:
    def __init__(self, guid: str, slots=()) -> None:
        self.guid = guid
        self.ClassName = "MoInflAffMsa"
        self.SlotsRC = list(slots)
        self.PartOfSpeechRA = None
        self.FromPartOfSpeechRA = None
        self.ToPartOfSpeechRA = None


class _Entry:
    def __init__(self, guid: str, msas=()) -> None:
        self.guid = guid
        self.LexemeFormOA = _LexForm(True)
        self.MorphoSyntaxAnalysesOC = list(msas)
        self.EntryRefsOS = []
        self.SensesOS = []


class _POS:
    def __init__(self, guid: str, slots=()) -> None:
        self.guid = guid
        self.AffixSlotsOC = list(slots)


class _FakeProject:
    def __init__(self, name: str, entries=(), poses=()) -> None:
        self.name = name
        self.LangProject = SimpleNamespace(
            LexDbOA=SimpleNamespace(EntriesOC=list(entries)))
        poses = list(poses)
        self.POS = SimpleNamespace(
            GetAll=lambda recursive=True: list(poses),
            GetSyncableProperties=lambda pos: {},
            GetAffixSlots=lambda pos: [],
        )
        self.MorphRules = SimpleNamespace(
            GetAllAffixTemplatesForPOS=lambda pos: [],
            GetSyncableProperties=lambda tpl: {},
        )

    def ProjectName(self) -> str:
        return self.name


class _RefColl:
    def __init__(self) -> None:
        self._items = []

    def Add(self, obj) -> None:
        self._items.append(obj)

    def __iter__(self):
        return iter(self._items)


class _TargetMSA:
    def __init__(self, guid: str) -> None:
        self.guid = guid
        self.SlotsRC = _RefColl()


class _Target171:
    def __init__(self, objects) -> None:
        self._objs = {o.guid: o for o in objects}

    def get_object_by_guid(self, guid):
        return self._objs.get(guid)


def _ctx(source, target) -> RunContext:
    return RunContext(
        source_handle=source,
        source_project_name="Src",
        source_project_path="/src",
        target_handle=target,
        target_project_name="Tgt",
        target_project_path="/tgt",
        run_id="GT-20261030-120000",
        started_at="2026-10-30T12:00:00",
    )


# Two bound affixes, each in its own slot, both slots under one POS.
_SLOT_A, _SLOT_B = _Obj("slot-a"), _Obj("slot-b")
_ENTRY_A = _Entry("entry-a", [_MSA("msa-a", [_SLOT_A])])
_ENTRY_B = _Entry("entry-b", [_MSA("msa-b", [_SLOT_B])])


def _source():
    return _FakeProject("src", entries=[_ENTRY_A, _ENTRY_B],
                        poses=[_POS("pos-1", [_SLOT_A, _SLOT_B])])


def _plan(selection):
    src, tgt = _source(), _FakeProject("tgt")
    return build_run_plan(_ctx(src, tgt), selection, WSMapping(entries=()),
                          src, tgt)


def _partial_selection() -> Selection:
    """AFFIXES on, only entry-a picked; SLOTS off."""
    return Selection(
        categories={GrammarCategory.AFFIXES: True},
        leaf_item_picks={GrammarCategory.AFFIXES: frozenset({"entry-a"})},
    )


def _run_consumer(plan, target):
    ctx = _ctx(object(), target)
    object.__setattr__(ctx, "_run_plan", plan)
    return categories._run_171_subpass(ctx, target, tag=None)


# ============================================================================
# _run_scope_guids
# ============================================================================

def test_run_scope_reads_actions_overwrites_and_skips_of_the_category() -> None:
    action = PlannedAction(category=GrammarCategory.AFFIXES,
                           source_guid="E1", intended_target_guid="e1",
                           summary="")
    present = Skip(category=GrammarCategory.AFFIXES, source_guid="{e2}",
                   reason=SkipReason.ALREADY_PRESENT_BY_GUID, detail="present")
    other = PlannedAction(category=GrammarCategory.SLOTS, source_guid="s1",
                          intended_target_guid="s1", summary="")
    scope = preview_mod._run_scope_guids(
        (GrammarCategory.AFFIXES,), [action, other], [], [present])
    assert scope == frozenset({"e1", "e2"})


def test_a_deselected_dependency_is_not_in_the_run_scope() -> None:
    """T093's presence probe and the pull-in both see deselected pieces; the
    DEPENDENCY_DESELECTED skip is the plan saying "not this run"."""
    refused = Skip(category=GrammarCategory.SLOTS, source_guid="s1",
                   reason=SkipReason.DEPENDENCY_DESELECTED, detail="refused")
    assert preview_mod._run_scope_guids(
        (GrammarCategory.SLOTS,), [], [], [refused]) == frozenset()


# ============================================================================
# _scope_msa_slot_bindings
# ============================================================================

def test_an_in_scope_affix_keeps_every_column_it_occupied() -> None:
    bindings = {"msa-1": ["slot-x", "slot-y"]}
    preview_mod._scope_msa_slot_bindings(
        bindings, {"msa-1": "entry-1"}, frozenset({"entry-1"}), frozenset())
    assert bindings == {"msa-1": ["slot-x", "slot-y"]}


def test_an_out_of_scope_affix_keeps_only_the_in_scope_slots() -> None:
    """FR-020 enrichment: an affix the destination already holds may be linked
    to a slot this run transfers -- but only to that slot."""
    bindings = {"msa-1": ["slot-x", "slot-y"]}
    preview_mod._scope_msa_slot_bindings(
        bindings, {"msa-1": "entry-1"}, frozenset(), frozenset({"slot-y"}))
    assert bindings == {"msa-1": ["slot-y"]}


def test_a_link_with_neither_end_in_scope_is_dropped() -> None:
    bindings = {"msa-1": ["slot-x"]}
    preview_mod._scope_msa_slot_bindings(
        bindings, {"msa-1": "entry-1"}, frozenset({"entry-2"}),
        frozenset({"slot-z"}))
    assert bindings == {}


def test_an_msa_with_no_recorded_owner_is_not_in_entry_scope() -> None:
    bindings = {"msa-1": ["slot-x"]}
    preview_mod._scope_msa_slot_bindings(
        bindings, {}, frozenset({""}), frozenset())
    assert bindings == {}


# ============================================================================
# build_run_plan end to end
# ============================================================================

def test_a_and_partial_selection_has_no_out_of_scope_bindings() -> None:
    """(a) Only the picked affix's link reaches the plan."""
    plan = _plan(_partial_selection())
    assert plan.msa_slot_bindings == {"msa-a": ["slot-a"]}


def test_b_full_selection_keeps_the_whole_source_bindings() -> None:
    """(b) A full selection keeps exactly what the producer found."""
    whole_source = {}
    preview_mod._populate_msa_slot_bindings(_source(), whole_source)
    assert whole_source == {"msa-a": ["slot-a"], "msa-b": ["slot-b"]}

    plan = _plan(Selection(categories={GrammarCategory.AFFIXES: True,
                                       GrammarCategory.SLOTS: True}))
    assert plan.msa_slot_bindings == whole_source


def test_slots_only_keeps_links_to_the_transferred_slots() -> None:
    """No affixes picked, one slot picked: only links into that slot remain
    (so an affix already in the destination can still gain the column)."""
    plan = _plan(Selection(
        categories={GrammarCategory.SLOTS: True},
        leaf_item_picks={GrammarCategory.SLOTS: frozenset({"slot-b"})},
    ))
    assert plan.msa_slot_bindings == {"msa-b": ["slot-b"]}


def test_nothing_selected_means_no_bindings() -> None:
    assert _plan(Selection(categories={})).msa_slot_bindings == {}


# ============================================================================
# Consumer: the run report
# ============================================================================

def _target_with_both_affixes_and_no_slots():
    """Both affix entries + MSAs already in the destination (an earlier run),
    neither slot transferred."""
    return _Target171([_Obj("entry-a"), _TargetMSA("msa-a"),
                       _Obj("entry-b"), _TargetMSA("msa-b")])


def test_a_and_c_partial_run_reports_only_the_in_scope_loss() -> None:
    """(a) entry-b was not picked: no skip about it. (c) entry-a was picked
    and its slot is genuinely missing: still DEPENDENCY_UNRESOLVED."""
    plan = _plan(_partial_selection())
    skips = _run_consumer(plan, _target_with_both_affixes_and_no_slots())

    assert [s.reason for s in skips] == [SkipReason.DEPENDENCY_UNRESOLVED]
    assert skips[0].source_guid == "slot-a"
    assert "msa_guid=msa-a" in skips[0].detail
    assert not any("msa-b" in s.detail or "slot-b" in s.detail for s in skips)


def test_the_whole_source_dict_is_what_produced_the_noise() -> None:
    """Control: the pre-#33 plan (whole-source bindings) on the same target
    reports the out-of-scope affix too -- the noise this issue removes."""
    whole_source = {}
    preview_mod._populate_msa_slot_bindings(_source(), whole_source)
    plan = types.SimpleNamespace(
        msa_slot_bindings=whole_source, identity_remap={},
        msa_owner_entry={"msa-a": "entry-a", "msa-b": "entry-b"})
    skips = _run_consumer(plan, _target_with_both_affixes_and_no_slots())
    assert sorted(s.source_guid for s in skips) == ["slot-a", "slot-b"]
