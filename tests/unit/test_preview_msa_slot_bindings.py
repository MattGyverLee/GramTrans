"""Unit tests for preview._populate_msa_slot_bindings (FR-333 fix).

Verifies that build_run_plan populates plan.msa_slot_bindings for every
inflectional affix MSA that carries at least one slot.  The root cause of
the original bug was that categories._stash_entry_bindings used getattr
duck-typing that silently returned None for base-typed IMoMorphSynAnalysis
refs from live LCM (pythonnet hides SlotsRC on the base interface).  The fix
adds an explicit IMoInflAffMsa-cast pass in preview.py that works for both
live LCM and duck-typed fakes.

All tests here are host-free (no SIL.LCModel / Windows / FLEx required).
The duck-typed path in _populate_msa_slot_bindings_duck covers the host-free
scenarios exercised below.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from gramtrans.Lib import preview as preview_mod
from gramtrans.Lib.preview import _populate_msa_slot_bindings
from gramtrans.Lib.models import (
    GrammarCategory,
    RunContext,
    Selection,
    WSMapping,
)
from gramtrans.Lib.preview import build_run_plan


# ============================================================================
# Fakes (duck-typed, lowercase .guid, matching test_categories_affixes.py)
# ============================================================================

class _MorphType:
    def __init__(self, is_affix: bool = True) -> None:
        self.IsAffixType = is_affix


class _LexForm:
    def __init__(self, is_affix: bool = True) -> None:
        self.MorphTypeRA = _MorphType(is_affix)


class _Slot:
    def __init__(self, guid: str) -> None:
        self.guid = guid


class _MSA:
    def __init__(self, guid: str, slots=(), class_name="MoInflAffMsa") -> None:
        self.guid = guid
        self.ClassName = class_name
        self.SlotsRC = list(slots)
        self.PartOfSpeechRA = None
        self.FromPartOfSpeechRA = None
        self.ToPartOfSpeechRA = None


class _Entry:
    def __init__(self, guid: str, is_affix: bool = True, msas=(),
                 refs=()) -> None:
        self.guid = guid
        self.LexemeFormOA = _LexForm(is_affix)
        self.MorphoSyntaxAnalysesOC = list(msas)
        self.EntryRefsOS = list(refs)
        self.SensesOS = []


def _lexdb_handle(entries=()):
    """Build a handle whose LexDbOA.EntriesOC is a list of _Entry fakes.
    Uses handle.LangProject.LexDbOA (second nav path in _iter_lex_entries)."""
    return SimpleNamespace(
        LangProject=SimpleNamespace(
            LexDbOA=SimpleNamespace(EntriesOC=list(entries))
        )
    )


def _ctx(source, target) -> RunContext:
    return RunContext(
        source_handle=source,
        source_project_name="Src",
        source_project_path="/src",
        target_handle=target,
        target_project_name="Tgt",
        target_project_path="/tgt",
        run_id="GT-20260706-020000",
        started_at="2026-07-06T02:00:00",
    )


# ============================================================================
# Direct tests for _populate_msa_slot_bindings helper
# ============================================================================

def test_populate_writes_slot_guids_for_infl_affix_msa() -> None:
    """Core invariant: an InflAff MSA with two slots produces a binding."""
    slot_a = _Slot("slot-a")
    slot_b = _Slot("slot-b")
    msa = _MSA("msa-1", slots=[slot_a, slot_b])
    entry = _Entry("entry-1", msas=[msa])
    src = _lexdb_handle([entry])

    bindings: dict = {}
    _populate_msa_slot_bindings(src, bindings)

    assert bindings == {"msa-1": ["slot-a", "slot-b"]}


def test_populate_skips_msa_with_empty_slots() -> None:
    """T040 invariant: an unbound MSA (empty SlotsRC) must NOT produce a
    binding entry, matching the Ejagham Mini 'ro~-' case."""
    msa = _MSA("msa-unbound", slots=[])
    entry = _Entry("entry-1", msas=[msa])
    src = _lexdb_handle([entry])

    bindings: dict = {}
    _populate_msa_slot_bindings(src, bindings)

    assert bindings == {}


def test_populate_handles_multiple_entries() -> None:
    """79 of 83 affix MSAs in Ejagham Mini carry slots: all must be captured."""
    bound_msa = _MSA("msa-bound", slots=[_Slot("slot-x")])
    unbound_msa = _MSA("msa-unbound", slots=[])
    entry_a = _Entry("entry-a", msas=[bound_msa])
    entry_b = _Entry("entry-b", msas=[unbound_msa])
    src = _lexdb_handle([entry_a, entry_b])

    bindings: dict = {}
    _populate_msa_slot_bindings(src, bindings)

    assert bindings == {"msa-bound": ["slot-x"]}


def test_populate_none_source_is_a_noop() -> None:
    bindings: dict = {}
    _populate_msa_slot_bindings(None, bindings)
    assert bindings == {}


def test_populate_source_with_no_lexdb_is_a_noop() -> None:
    """A source handle that exposes no LangProject.LexDbOA is silently skipped."""
    src = SimpleNamespace()  # no LangProject at all
    bindings: dict = {}
    _populate_msa_slot_bindings(src, bindings)
    assert bindings == {}


def test_populate_is_idempotent_when_rerun() -> None:
    """Running twice with the same source overwrites keys with identical values
    (idempotent — no duplicate slot guids)."""
    msa = _MSA("msa-1", slots=[_Slot("slot-a")])
    entry = _Entry("entry-1", msas=[msa])
    src = _lexdb_handle([entry])

    bindings: dict = {}
    _populate_msa_slot_bindings(src, bindings)
    _populate_msa_slot_bindings(src, bindings)

    assert bindings == {"msa-1": ["slot-a"]}


def test_populate_preserves_slot_order() -> None:
    """Slot order from SlotsRC must be preserved (matches source order contract)."""
    slots = [_Slot(f"slot-{i}") for i in range(4)]
    msa = _MSA("msa-ordered", slots=slots)
    entry = _Entry("entry-1", msas=[msa])
    src = _lexdb_handle([entry])

    bindings: dict = {}
    _populate_msa_slot_bindings(src, bindings)

    assert bindings["msa-ordered"] == ["slot-0", "slot-1", "slot-2", "slot-3"]


# ============================================================================
# Integration: build_run_plan populates plan.msa_slot_bindings end-to-end
# ============================================================================

class _FakeProject:
    """Minimal flexicon-style source/target handle for build_run_plan.

    Exposes enough for the leaf dispatch + _populate_msa_slot_bindings to
    traverse affix entries without triggering SIL.LCModel imports.
    """

    def __init__(self, name: str, entries=()) -> None:
        self.name = name
        # Shape walked by _iter_lex_entries AND _populate_msa_slot_bindings:
        # handle.LangProject.LexDbOA.EntriesOC
        self.LangProject = SimpleNamespace(
            LexDbOA=SimpleNamespace(EntriesOC=list(entries))
        )
        # Stubs for other accessors that build_run_plan / leaf dispatch touch
        # when selection is empty (no categories on).
        self.POS = SimpleNamespace(
            GetAll=lambda recursive=True: [],
            GetSyncableProperties=lambda pos: {},
            GetAffixSlots=lambda pos: [],
        )
        self.MorphRules = SimpleNamespace(
            GetAllAffixTemplatesForPOS=lambda pos: [],
            GetSyncableProperties=lambda tpl: {},
        )

    def ProjectName(self) -> str:
        return self.name


def _all_off_selection() -> Selection:
    """A Selection with no categories enabled — exercises only the binding
    population pass, not the leaf-dispatch planners."""
    return Selection(categories={})


def test_build_run_plan_populates_bindings_for_affix_with_slots() -> None:
    """End-to-end: build_run_plan leaves plan.msa_slot_bindings non-empty for
    a source that contains one affix entry with a slotted MSA."""
    slot = _Slot("slot-guid-1")
    msa = _MSA("msa-guid-1", slots=[slot])
    entry = _Entry("entry-guid-1", is_affix=True, msas=[msa])

    src = _FakeProject("src", entries=[entry])
    tgt = _FakeProject("tgt", entries=[])

    plan = build_run_plan(
        _ctx(src, tgt), _all_off_selection(), WSMapping(entries=()), src, tgt
    )

    assert plan.msa_slot_bindings == {"msa-guid-1": ["slot-guid-1"]}, (
        "plan.msa_slot_bindings must be populated for an affix MSA with slots"
    )


def test_build_run_plan_no_bindings_for_unbound_affix() -> None:
    """T040 invariant via build_run_plan: unbound MSA produces no binding."""
    msa = _MSA("msa-unbound", slots=[])
    entry = _Entry("entry-1", is_affix=True, msas=[msa])

    src = _FakeProject("src", entries=[entry])
    tgt = _FakeProject("tgt", entries=[])

    plan = build_run_plan(
        _ctx(src, tgt), _all_off_selection(), WSMapping(entries=()), src, tgt
    )

    assert plan.msa_slot_bindings == {}


def test_build_run_plan_bindings_empty_when_no_affix_entries() -> None:
    """No affix entries in source -> empty msa_slot_bindings dict."""
    src = _FakeProject("src", entries=[])
    tgt = _FakeProject("tgt", entries=[])

    plan = build_run_plan(
        _ctx(src, tgt), _all_off_selection(), WSMapping(entries=()), src, tgt
    )

    assert plan.msa_slot_bindings == {}
