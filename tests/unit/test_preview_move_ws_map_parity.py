"""T037 Finding 2 (Preview/Move parity) -- `Lib/preview.py.build_run_plan`
never set `context._ws_map`, so `reversals.plan_reversals`
(`reversals.py:443`, ``getattr(ctx, "_ws_map", None) or {}``) always ran
under IDENTITY WS mapping in Preview, even when the caller supplied a
NON-identity `WSMapping`. Move mode (`Lib/transfer.py.execute:353`) DOES set
it (`object.__setattr__(exec_ctx, '_ws_map', ws_map)` where
``ws_map = to_ws_map_dict(plan.ws_mapping)``, `transfer.py:182`), so Preview
could never correctly predict Move's reversal-index target WS under a
non-identity mapping.

Fixture style: STEMS entry/sense fakes mirror `test_categories_stems.py`'s
`_FakeEntry`/`_FakeSense`/`_FakeHandle` family (minimal shape needed for the
STEMS leaf-dispatch category to register a copied sense into
`context._copy_set`); reversal-index fakes mirror `test_reversal_walk.py`'s
`_FakeReversalEntry`/`_FakeReversalIndex`/`_FakeWS`/`_FakeWSRepo` family. Both
sets are duplicated locally per this codebase's established per-file fixture
convention (see e.g. `test_lexrel_final_pass.py`'s own docstring on this).
"""
from __future__ import annotations

from gramtrans.Lib import categories as categories_mod
from gramtrans.Lib import reversals as reversals_mod
from gramtrans.Lib.models import (
    GrammarCategory,
    RunContext,
    Selection,
    WSKind,
    WSMapping,
    WSMappingEntry,
)
from gramtrans.Lib.preview import build_run_plan
from gramtrans.Lib.ws_mapping import to_ws_map_dict


# ============================================================================
# Fakes -- STEMS entry/sense (mirrors test_categories_stems.py)
# ============================================================================

class _FakeMorphType:
    def __init__(self, is_affix: bool) -> None:
        self.IsAffixType = is_affix


class _FakeLexemeForm:
    def __init__(self, morphtype) -> None:
        self.MorphTypeRA = morphtype


class _FakeSense:
    def __init__(self, guid: str, domains=()) -> None:
        self.guid = guid
        self.SemanticDomainsRC = list(domains)


class _FakeEntry:
    """A stem `ILexEntry` stand-in -- same minimal shape
    `test_categories_stems.py` uses for STEMS leaf-dispatch."""

    def __init__(self, guid, *, senses=()) -> None:
        self.guid = guid
        self.LexemeFormOA = _FakeLexemeForm(_FakeMorphType(is_affix=False))
        self.MorphoSyntaxAnalysesOC = []
        self.SensesOS = list(senses)
        self.EntryRefsOS = []


class _FakeLexDb:
    def __init__(self, entries) -> None:
        self.EntriesOC = list(entries)


class _FakeLangProject:
    def __init__(self, entries) -> None:
        self.LexDbOA = _FakeLexDb(entries)


# ============================================================================
# Fakes -- reversal index / WS repo (mirrors test_reversal_walk.py)
# ============================================================================

class _FakeTsString:
    def __init__(self, text):
        self.Text = text or None


class _FakeMultiString:
    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})

    def get_String(self, ws_handle):
        return _FakeTsString(self._data.get(ws_handle))


class _FakeWS:
    def __init__(self, ws_id: str, handle: int) -> None:
        self.Id = ws_id
        self.Handle = handle


class _FakeWSRepo:
    def __init__(self, ws_list) -> None:
        self._ws_list = list(ws_list)

    def GetAll(self):
        return list(self._ws_list)


class _FakeReversalIndexesOps:
    def __init__(self, indexes=()) -> None:
        self._indexes = list(indexes)

    def GetAll(self):
        return list(self._indexes)


class _FakeReversalEntry:
    def __init__(self, guid, senses=(), form_alts=None) -> None:
        self.Guid = guid
        self.guid = guid
        self.SensesRS = list(senses)
        self.ReversalForm = _FakeMultiString(form_alts or {})
        self.PartOfSpeechRA = None
        self.SubentriesOS = []


class _FakeReversalIndex:
    def __init__(self, guid, writing_system, entries=()) -> None:
        self.Guid = guid
        self.guid = guid
        self.WritingSystem = writing_system
        self.EntriesOC = list(entries)
        self.PartsOfSpeechOA = None


# ============================================================================
# Fakes -- source/target project handles (both roles: STEMS closure walk +
# reversal walk read the SAME source/target handle objects).
# ============================================================================

class _FakeSourceProject:
    def __init__(self, entries, ws_list, indexes) -> None:
        self.LangProject = _FakeLangProject(entries)
        self.WritingSystems = _FakeWSRepo(ws_list)
        self.ReversalIndexes = _FakeReversalIndexesOps(indexes)


class _FakeTargetProject:
    def __init__(self, entries, ws_list) -> None:
        self.LangProject = _FakeLangProject(entries)
        self.WritingSystems = _FakeWSRepo(ws_list)


def _ctx(source, target) -> RunContext:
    return RunContext(
        source_handle=source,
        source_project_name="Src",
        source_project_path="/src",
        target_handle=target,
        target_project_name="Tgt",
        target_project_path="/tgt",
        run_id="GT-20260712-000000",
        started_at="2026-07-12T00:00:00",
    )


def _build_fixture():
    """One copied stem entry/sense ('entry-1'/'sense-1'), one source reversal
    index keyed by 'koh' whose sole entry links 'sense-1', a NON-identity
    WSMapping 'koh' -> 'gez', and a target that registers 'gez' (but not
    'koh') as a writing system."""
    sense = _FakeSense("sense-1")
    stem_entry = _FakeEntry("entry-1", senses=[sense])

    rev_sense = _FakeSense("sense-1")  # matched by GUID only
    rev_entry = _FakeReversalEntry("rev-e1", senses=[rev_sense], form_alts={1: "run"})
    rev_index = _FakeReversalIndex("idx1", "koh", entries=[rev_entry])

    source = _FakeSourceProject(
        entries=[stem_entry],
        ws_list=[_FakeWS("koh", 1)],
        indexes=[rev_index],
    )
    target = _FakeTargetProject(entries=[], ws_list=[_FakeWS("gez", 10)])

    ws_mapping = WSMapping(entries=(
        WSMappingEntry(
            source_ws_id="koh", source_ws_kind=WSKind.ANALYSIS,
            target_ws_id="gez",
        ),
    ))
    selection = Selection(categories={GrammarCategory.STEMS: True})
    return source, target, ws_mapping, selection


# ============================================================================
# Test A -- Preview sees the MAPPED target WS, not identity.
# ============================================================================

def test_build_run_plan_populates_ws_map_and_reversal_walk_resolves_mapped_ws():
    """Before the fix, `build_run_plan` never set `context._ws_map`, so
    `plan_reversals` ran under identity WS mapping: 'koh' (absent from the
    target) would fail the R4 WS gate and the whole index would be DROPPED
    rather than mapped to 'gez'. After the fix, `context._ws_map` carries
    the caller's real mapping and the reversal decision's `target_ws_id` is
    the MAPPED id ('gez'), not the source id ('koh')."""
    source, target, ws_mapping, selection = _build_fixture()
    context = _ctx(source, target)

    plan = build_run_plan(context, selection, ws_mapping, source, target)

    assert getattr(context, "_ws_map", None) == {"koh": "gez"}, (
        "build_run_plan must thread the caller's WSMapping into "
        "context._ws_map (mirrors transfer.execute's convention) so the "
        "reversal walk resolves through it, not identity."
    )
    assert len(plan.reversal_decisions) == 1, (
        f"expected exactly one reversal decision (index 'koh' maps to a "
        f"target WS the target actually has); got {plan.reversal_decisions!r} "
        f"-- dropped={plan.dropped_items!r}"
    )
    decision = plan.reversal_decisions[0]
    assert decision.target_ws_id == "gez"
    assert decision.source_entry_guid == "rev-e1"
    # No "writing system not mapped" drop for this index -- the mapping
    # resolved successfully.
    ws_drops = [
        r for r in plan.dropped_items
        if r.owner_kind == "ReversalIndex" and r.reason == "writing system not mapped"
    ]
    assert ws_drops == []


# ============================================================================
# Test B -- Preview/Move parity: both resolve the SAME target WS for the
# SAME reversal index under the SAME non-identity WSMapping.
# ============================================================================

def test_preview_and_move_resolve_same_target_ws_for_reversal_index():
    """Move mode's own convention (`transfer.py:182`/`:353`) is
    ``object.__setattr__(exec_ctx, '_ws_map', to_ws_map_dict(plan.ws_mapping))``
    ahead of `reproduce_reversal_entries` -> `reversals.plan_reversals`. This
    test re-derives a Move-style context the SAME way (reusing the SAME
    `to_ws_map_dict` helper and the SAME fully-settled `copy_set` Preview's
    STEMS leaf-dispatch loop just assembled) and asserts `plan_reversals`
    resolves the IDENTICAL `target_ws_id` Preview's `build_run_plan` reported
    -- proving Preview no longer diverges from what Move will actually do.
    """
    source, target, ws_mapping, selection = _build_fixture()
    context = _ctx(source, target)

    plan = build_run_plan(context, selection, ws_mapping, source, target)
    assert len(plan.reversal_decisions) == 1
    preview_target_ws_id = plan.reversal_decisions[0].target_ws_id

    # Re-derive a Move-style context the SAME way transfer.execute does,
    # over the SAME copy_set Preview's leaf-dispatch loop already settled
    # (context._copy_set is mutated in place by build_run_plan).
    move_ctx = _ctx(source, target)
    object.__setattr__(move_ctx, "_ws_map", to_ws_map_dict(ws_mapping))
    move_copy_set = dict(getattr(context, "_copy_set", None) or {})
    assert move_copy_set, "Preview's STEMS leaf-dispatch loop must have copied 'sense-1'"

    move_decisions = list(reversals_mod.plan_reversals(
        move_copy_set, source, target, move_ctx, {}, [],
    ))
    assert len(move_decisions) == 1
    move_target_ws_id = move_decisions[0].target_ws_id

    assert preview_target_ws_id == move_target_ws_id == "gez"
