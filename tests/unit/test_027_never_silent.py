"""Unit tests for feature 027 (Complex Forms & Variants) cross-cutting
concerns: the never-silent drop-policy flip (contract C4), Preview/Move
parity (C5), and the empty-source regression (C7).

Resolves GitHub #30; unblocks the LexEntryRef leg of #28. See:
- specs/027-complex-forms-variants/contracts/entryref-reproduction.md (C4, C5, C7)
- specs/027-complex-forms-variants/research.md (Decision 5)

T019 (RED-before-GREEN): proves the C4 policy flip -- BEFORE the flip,
`_report_dropped_entry_refs` reports every `LexEntryRef` unconditionally,
so an in-closure ref (all its ComponentLexemesRS/PrimaryLexemesRS members
themselves eligible for STEMS/AFFIXES transfer -- reproducible by C1-C3)
is WRONGLY reported as dropped. This test fails against today's
report-all behavior and passes once T020 flips the policy.

"In closure" signal (this cycle's design choice, since the full
create-then-wire tail runs strictly AFTER every source entry's closure
walk -- see `stems_execute_action`'s `_run_tail_once` ordering -- so
`_report_dropped_entry_refs`, called mid-walk, cannot check "was this
already created on target" without an order-dependent false positive):
a component/primary lexeme is "in closure" iff it is itself ELIGIBLE for
STEMS/AFFIXES transfer, i.e. `categories._affix_type_of(entry)[0]` is
True (has `LexemeFormOA` + its `MorphTypeRA`) -- the SAME eligibility
test that classifies every `LexEntry` into STEMS/AFFIXES elsewhere in
this module. A ref with zero components/primaries is trivially in-closure
(nothing external for it to depend on). Entry-type/publication (C3)
resolution failures are NOT this function's concern any more -- C3's own
`_decide_reference_fields`/`_apply_reference_fields` dispatch already
reports those independently (this is exactly the P2 double-bookkeeping
fix: a reproduced ref must not ALSO show up here).
"""
from __future__ import annotations

import sys
import types

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.models import DroppedItemRecord, RunContext


WS_EN = 100


# ============================================================================
# Fakes
# ============================================================================

class _FakeMultiString:
    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})


class _FakeGuidObj:
    def __init__(self, guid) -> None:
        self.Guid = guid
        self.guid = guid


class _FakeMorphType(_FakeGuidObj):
    def __init__(self, guid="mt-1") -> None:
        super().__init__(guid)
        self.IsAffixType = False


class _FakeLexemeForm(_FakeGuidObj):
    """Enough surface for `_affix_type_of` to classify an entry as
    eligible: `.MorphTypeRA` present."""

    def __init__(self, guid="lf-1", morph_type=None) -> None:
        super().__init__(guid)
        self.MorphTypeRA = morph_type if morph_type is not None else _FakeMorphType()


class _FakeEligibleEntry(_FakeGuidObj):
    """An "in closure" component/primary lexeme -- has LexemeFormOA +
    MorphTypeRA, so `_affix_type_of` classifies it as STEMS/AFFIXES
    eligible (WILL be created by this transfer)."""

    def __init__(self, guid, citation_form="") -> None:
        super().__init__(guid)
        self.CitationForm = _FakeMultiString(
            {WS_EN: citation_form} if citation_form else {})
        self.LexemeFormOA = _FakeLexemeForm()


class _FakeIneligibleEntry(_FakeGuidObj):
    """An "out of closure" component/primary lexeme -- NO LexemeFormOA at
    all, so `_affix_type_of` returns (False, False): this entry is
    excluded from BOTH STEMS and AFFIXES transfer and can never be
    created on the target -- permanently unresolvable, out-of-closure."""

    def __init__(self, guid, citation_form="") -> None:
        super().__init__(guid)
        self.CitationForm = _FakeMultiString(
            {WS_EN: citation_form} if citation_form else {})
        # Deliberately no LexemeFormOA attribute at all.


class _FakePossibilityType(_FakeGuidObj):
    def __init__(self, guid, name="") -> None:
        super().__init__(guid)
        self.Name = _FakeMultiString({WS_EN: name} if name else {})


class _FakeLexEntryRef(_FakeGuidObj):
    def __init__(self, guid, ref_type, components=(), primaries=(),
                 variant_types=()) -> None:
        super().__init__(guid)
        self.RefType = ref_type
        self.ComponentLexemesRS = list(components)
        self.PrimaryLexemesRS = list(primaries)
        self.VariantEntryTypesRS = list(variant_types)
        self.ComplexEntryTypesRS = []
        self.ShowComplexFormsInRS = []


class _FakeSourceEntry(_FakeGuidObj):
    def __init__(self, guid, entry_refs=()) -> None:
        super().__init__(guid)
        self.CitationForm = _FakeMultiString()
        self.EntryRefsOS = list(entry_refs)


# ============================================================================
# T019 -- C4 policy flip
# ============================================================================

def test_in_closure_ref_yields_zero_dropped_records():
    """A variant ref whose component lexeme IS itself STEMS/AFFIXES-eligible
    (in closure -- C1-C3 will reproduce it) -> 0 DroppedItemRecord.

    RED proof (pre-T020): today's report-all `_report_dropped_entry_refs`
    emits exactly 1 record here regardless of the component's eligibility
    -- this assertion (`dropped == []`) fails against that code
    (`AssertionError: assert [<DroppedItemRecord ...>] == []`)."""
    comp = _FakeEligibleEntry("comp-in-closure-1", citation_form="root-word")
    vtype = _FakePossibilityType("vtype-1", name="Dialectal Variant")
    ref = _FakeLexEntryRef("ref-in-closure-1", ref_type=0, components=[comp],
                            variant_types=[vtype])
    entry = _FakeSourceEntry("entry-in-closure-1", entry_refs=[ref])

    dropped: list = []
    categories._report_dropped_entry_refs(entry, dropped)

    assert dropped == []


def test_out_of_closure_component_yields_exactly_one_dropped_record():
    """A variant ref whose component lexeme is NOT STEMS/AFFIXES-eligible
    (out of closure -- can never be created on target, permanently
    unresolvable) -> exactly 1 DroppedItemRecord, naming the relationship.

    RED proof (pre-T020): today's report-all behavior also emits exactly 1
    record here, so this half of the flip does NOT distinguish pre/post
    on its own -- see the paired in-closure test above and the parity test
    below for the half that actually flips."""
    comp = _FakeIneligibleEntry("comp-out-of-closure-1", citation_form="orphan-word")
    vtype = _FakePossibilityType("vtype-2", name="Dialectal Variant")
    ref = _FakeLexEntryRef("ref-out-of-closure-1", ref_type=0, components=[comp],
                            variant_types=[vtype])
    entry = _FakeSourceEntry("entry-out-of-closure-1", entry_refs=[ref])

    dropped: list = []
    categories._report_dropped_entry_refs(entry, dropped)

    assert len(dropped) == 1
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.owner_kind == "LexEntry"
    assert rec.owner_guid == "entry-out-of-closure-1"
    assert rec.field_name == "EntryRefsOS"
    assert rec.item_guid == "ref-out-of-closure-1"
    assert "variant" in rec.item_name


def test_mixed_refs_report_only_the_out_of_closure_one():
    """An entry with TWO refs, one in-closure and one out-of-closure ->
    exactly 1 DroppedItemRecord (only the out-of-closure ref's), proving
    the flip is per-ref, not per-entry.

    RED proof (pre-T020): today's report-all emits 2 records here (one per
    ref regardless of closure) -- `len(dropped) == 1` fails
    (`assert 2 == 1`)."""
    in_comp = _FakeEligibleEntry("comp-mixed-in", citation_form="in-word")
    ref_in = _FakeLexEntryRef("ref-mixed-in", ref_type=0, components=[in_comp])
    out_comp = _FakeIneligibleEntry("comp-mixed-out", citation_form="out-word")
    ref_out = _FakeLexEntryRef("ref-mixed-out", ref_type=1, components=[out_comp])
    entry = _FakeSourceEntry("entry-mixed", entry_refs=[ref_in, ref_out])

    dropped: list = []
    categories._report_dropped_entry_refs(entry, dropped)

    assert len(dropped) == 1
    assert dropped[0].item_guid == "ref-mixed-out"


def test_ref_with_zero_components_is_trivially_in_closure():
    """A ref with NO components/primaries at all (C1 still creates its
    empty container unconditionally) has nothing external to fail on ->
    0 DroppedItemRecord.

    RED proof (pre-T020): today's report-all emits 1 record for this ref
    even though it depends on nothing -- `dropped == []` fails."""
    ref = _FakeLexEntryRef("ref-empty-1", ref_type=0)
    entry = _FakeSourceEntry("entry-empty-1", entry_refs=[ref])

    dropped: list = []
    categories._report_dropped_entry_refs(entry, dropped)

    assert dropped == []


def test_entry_with_no_entry_refs_still_emits_nothing():
    entry = _FakeSourceEntry("entry-none", entry_refs=[])

    dropped: list = []
    categories._report_dropped_entry_refs(entry, dropped)

    assert dropped == []


# ----------------------------------------------------------------------------
# C5 -- Move/Preview drop-set parity, re-proven under the new policy.
# ----------------------------------------------------------------------------

class _FakeRunContext:
    def __init__(self, source_handle) -> None:
        self.source_handle = source_handle
        self.target_handle = object()


def test_move_and_preview_drop_sets_identical_under_new_policy():
    """`_report_dropped_entry_refs` (Move's call site) and
    `_plan_entry_reference_decisions` (Preview's entrypoint, which calls
    the SAME function internally) must still produce the identical
    EntryRefsOS drop set under the flipped policy."""
    out_comp = _FakeIneligibleEntry("comp-parity-out", citation_form="orphan")
    ref = _FakeLexEntryRef("ref-parity-1", ref_type=0, components=[out_comp])
    entry = _FakeSourceEntry("entry-parity-1", entry_refs=[ref])

    move_dropped: list = []
    categories._report_dropped_entry_refs(entry, move_dropped)

    preview_dropped: list = []
    ctx = _FakeRunContext(source_handle=object())
    ctx._dropped = preview_dropped
    categories._plan_entry_reference_decisions(entry, ctx, target=object())

    def _entry_refs_only(records):
        return sorted(
            (r.owner_guid, r.field_name, r.item_guid, r.item_name, r.reason)
            for r in records if r.field_name == "EntryRefsOS"
        )

    assert _entry_refs_only(move_dropped) == _entry_refs_only(preview_dropped)
    assert len(move_dropped) == 1


# ============================================================================
# T021 -- C5 full Preview/Move parity: created-ref SET + dropped-record SET,
# Preview writes nothing (Principle III, byte-unchanged).
#
# The existing parity test above proves the DROP set matches for a single
# out-of-closure ref. T021 completes C5: over an `Ejagham Mini`-shaped
# selection (6 all-in-closure variant refs, echoing the corpus's 6 variant
# refs -- SC-001) it proves BOTH halves of the contract's promise ("the same
# set of created refs AND the same set of dropped records") plus the
# read-only guarantee.
#
# The shared-plan story (`stems_plan_action` -> `stems_execute_action`):
#   * PLAN/PREVIEW time -- `_stash_entry_bindings` gathers
#     `entryref_create_bindings` (the "will create" set) read-only, and
#     `_plan_entry_reference_decisions` computes Preview's drop set.
#   * MOVE time -- `_run_entryref_create_pass` creates from those SAME
#     bindings (the "did create" set), and `_walk_lex_entry_closure` calls
#     `_report_dropped_entry_refs` for Move's drop set.
# Parity is therefore between the plan-gathered create set and the Move-created
# set, and between the two call sites of the one report function.
#
# Entry-type resolution (C3) is deliberately out of scope here (refs carry no
# variant/complex types) -- it is covered by test_027_entry_type_resolve.py;
# C5 is about the container SET + drop SET, not type disposition.
# ============================================================================

# Create-pass fakes (mirror test_027_entryref_reproduction.py; self-contained
# so this cross-cutting file has no cross-test-module import).


class _FakeRefSeq:
    """LCM owning/reference sequence stand-in: records Add calls in order."""

    def __init__(self, initial=()) -> None:
        self._items = list(initial)
        self.add_log = []

    def Add(self, obj):
        self._items.append(obj)
        self.add_log.append(obj)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)


class _FakeCreatedRef:
    """What `factory.Create(guid)` returns: a fresh, unowned LexEntryRef."""

    def __init__(self, guid) -> None:
        self.guid = guid
        self.RefType = None
        self.ComponentLexemesRS = _FakeRefSeq()
        self.PrimaryLexemesRS = _FakeRefSeq()


class _FakeEntryRefFactory:
    """Records every guid passed to Create (GUID-preservation, INV-1)."""

    def __init__(self) -> None:
        self.create_log = []

    def Create(self, guid):
        self.create_log.append(guid)
        return _FakeCreatedRef(guid)


class _FakeTargetEntry027:
    def __init__(self, guid: str, entry_refs=()) -> None:
        self.guid = guid
        self.EntryRefsOS = _FakeRefSeq(initial=entry_refs)


class _FakeCreateTarget:
    """Target handle for the create pass: get_object_by_guid + GetFactory."""

    def __init__(self, objects_by_guid=None, factory=None) -> None:
        self._objs = dict(objects_by_guid or {})
        self._factory = factory if factory is not None else _FakeEntryRefFactory()

    def get_object_by_guid(self, guid):
        return self._objs.get(guid)

    def GetFactory(self, iface_token):
        return self._factory


def _install_module(name, module):
    original = sys.modules.get(name)
    sys.modules[name] = module
    return original


def _restore_module(name, original):
    if original is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = original


def _iface_cast(name):
    """A stub SIL.LCModel interface: `IFoo(bare)` -> bare._views['IFoo']."""
    def cast(obj):
        return getattr(obj, "_views", {}).get(name, obj)
    return cast


@pytest.fixture
def _stub_lcm_full():
    """Stub SIL.LCModel + System with `ILexEntryRefFactory` PLUS the
    `ILexEntry`/`ILexEntryRef` casts `_run_entryref_create_pass` depends on
    (same fixture shape as test_027_entryref_reproduction.py)."""
    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.ILexEntryRefFactory = lambda raw: raw  # identity cast
    fake_lcm.ICmObjectRepository = object()
    for iface in ("ILexEntry", "ILexEntryRef"):
        setattr(fake_lcm, iface, _iface_cast(iface))
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    original_lcm = _install_module("SIL.LCModel", fake_lcm)

    fake_system = types.ModuleType("System")
    fake_system.Guid = type(
        "FakeGuid", (), {"Parse": staticmethod(lambda s: s)}
    )
    original_system = _install_module("System", fake_system)

    yield

    _restore_module("SIL.LCModel", original_lcm)
    _restore_module("System", original_system)


def _make_ctx() -> RunContext:
    return RunContext(
        source_handle=object(),
        source_project_name="Src",
        source_project_path="/src",
        target_handle=object(),
        target_project_name="Tgt",
        target_project_path="/tgt",
        run_id="GT-20260713-000000",
        started_at="2026-07-13T00:00:00",
    )


def _ctx_from_bindings(entryref_create_bindings, dropped) -> RunContext:
    """RunContext carrying an already-gathered `entryref_create_bindings`
    plan (the Move-time consumer's input)."""
    ctx = _make_ctx()
    plan = types.SimpleNamespace(
        entryref_create_bindings={
            k: list(v) for k, v in entryref_create_bindings.items()
        },
        identity_remap={},
    )
    object.__setattr__(ctx, "_run_plan", plan)
    object.__setattr__(ctx, "_dropped", dropped)
    return ctx


def _planned_ref_guids(bindings) -> set:
    return {rec["ref_guid"] for recs in bindings.values() for rec in recs}


def _entry_ref_drops(records) -> list:
    """The EntryRefsOS-only drop tuples, sorted -- the field this parity test
    owns (other fields' fail-soft decisions are not C5's concern; same filter
    as `test_move_and_preview_drop_sets_identical_under_new_policy`)."""
    return sorted(
        (r.owner_guid, r.field_name, r.item_guid, r.item_name, r.reason)
        for r in records if r.field_name == "EntryRefsOS"
    )


def test_c5_preview_move_created_and_dropped_set_parity(_stub_lcm_full) -> None:
    """`Ejagham Mini`-shaped selection: 6 all-in-closure variant refs.

    C5 end-to-end -- the created-ref set Move produces equals the set the plan
    gathered (which Preview shares), the drop set is identical between the
    Preview and Move call sites (empty here -- all in-closure, SC-001), and
    the Preview pass mutates neither the source ref collection nor the target
    (Principle III, byte-unchanged)."""
    refs = []
    for i in range(6):
        comp = _FakeEligibleEntry(f"comp-{i}", citation_form=f"root-{i}")
        refs.append(_FakeLexEntryRef(f"ref-{i}", ref_type=0, components=[comp]))
    entry = _FakeSourceEntry("entry-emini", entry_refs=refs)

    # --- PLAN time (shared by Preview + Move): gather create bindings read-only.
    plan_bindings: dict = {}
    plan_ctx = types.SimpleNamespace(
        _entryref_create_bindings=plan_bindings,
        _lexentry_ref_bindings={},
    )
    categories._stash_entry_bindings(entry, plan_ctx)
    planned = _planned_ref_guids(plan_bindings)
    assert planned == {f"ref-{i}" for i in range(6)}

    # --- PREVIEW time: read-only decision pass. Snapshot the source ref
    # collection so we can prove Preview wrote nothing to it.
    source_refs_before = list(entry.EntryRefsOS)
    preview_dropped: list = []
    preview_ctx = _FakeRunContext(source_handle=object())
    preview_ctx._dropped = preview_dropped
    categories._plan_entry_reference_decisions(entry, preview_ctx, target=object())
    assert list(entry.EntryRefsOS) == source_refs_before  # Preview wrote nothing

    # --- MOVE time: create containers from the SAME plan bindings, then the
    # closure-walk drop report.
    target_entry = _FakeTargetEntry027("entry-emini")
    factory = _FakeEntryRefFactory()
    target = _FakeCreateTarget({"entry-emini": target_entry}, factory=factory)
    move_dropped: list = []
    move_ctx = _ctx_from_bindings(plan_bindings, move_dropped)
    skips = categories._run_entryref_create_pass(move_ctx, target, tag=None)
    categories._report_dropped_entry_refs(entry, move_dropped)

    # Created-ref SET parity: Move created exactly the plan's set, GUIDs
    # preserved, all owned into the target entry.
    assert skips == []
    assert set(factory.create_log) == planned
    assert len(target_entry.EntryRefsOS) == 6

    # Dropped-record SET parity: identical between the two call sites, and
    # empty because every ref is in-closure (SC-001 -- 0 -> 6, 0 dropped).
    assert _entry_ref_drops(move_dropped) == _entry_ref_drops(preview_dropped)
    assert _entry_ref_drops(move_dropped) == []


def test_c5_created_ref_set_is_disjoint_from_dropped_set(_stub_lcm_full) -> None:
    """A mixed selection (in-closure + out-of-closure ref): the ONE
    out-of-closure ref lands in the drop set of BOTH Preview and Move, and the
    in-closure ref is created, not dropped -- proving the reproduce-vs-report
    split is the same partition in both modes (C4/C5)."""
    in_comp = _FakeEligibleEntry("comp-in", citation_form="in-root")
    ref_in = _FakeLexEntryRef("ref-in", ref_type=0, components=[in_comp])
    out_comp = _FakeIneligibleEntry("comp-out", citation_form="orphan")
    ref_out = _FakeLexEntryRef("ref-out", ref_type=0, components=[out_comp])
    entry = _FakeSourceEntry("entry-mixed-parity", entry_refs=[ref_in, ref_out])

    plan_bindings: dict = {}
    plan_ctx = types.SimpleNamespace(
        _entryref_create_bindings=plan_bindings,
        _lexentry_ref_bindings={},
    )
    categories._stash_entry_bindings(entry, plan_ctx)

    preview_dropped: list = []
    preview_ctx = _FakeRunContext(source_handle=object())
    preview_ctx._dropped = preview_dropped
    categories._plan_entry_reference_decisions(entry, preview_ctx, target=object())

    move_dropped: list = []
    categories._report_dropped_entry_refs(entry, move_dropped)

    # Preview and Move report the identical single out-of-closure ref.
    assert _entry_ref_drops(move_dropped) == _entry_ref_drops(preview_dropped)
    move_drop_guids = {r.item_guid for r in move_dropped
                       if r.field_name == "EntryRefsOS"}
    assert move_drop_guids == {"ref-out"}


# ============================================================================
# T022 -- C7 empty-source regression: a source with 0 LexEntryRef produces 0
# new objects and 0 new dropped records vs. a 024-only baseline (FR-011,
# SC-005). The feature is prevention-only: absent any EntryRefsOS, EVERY 027
# entry point must be a no-op, so the plan and the drop set are byte-identical
# to what a 024-only run would produce.
# ============================================================================

def test_c7_empty_source_gathers_no_create_bindings() -> None:
    """`_stash_entry_bindings` over an entry with 0 EntryRefsOS adds NOTHING
    to either binding map -- not even an empty-list slot for the entry -- so
    the plan is byte-identical to a 024-only plan (the 027 create-bindings
    extension contributes zero keys)."""
    entry = _FakeSourceEntry("entry-noref", entry_refs=[])

    create_map: dict = {}
    ref_map: dict = {}
    plan_ctx = types.SimpleNamespace(
        _entryref_create_bindings=create_map,
        _lexentry_ref_bindings=ref_map,
    )
    categories._stash_entry_bindings(entry, plan_ctx)

    assert create_map == {}   # no key added, not {"entry-noref": []}
    assert ref_map == {}


def test_c7_empty_source_creates_nothing_and_reports_nothing(_stub_lcm_full) -> None:
    """End-to-end C7 over a 0-ref source: the create pass creates 0 objects
    (0 skips) and the drop report emits 0 records in BOTH modes -- the total
    delta vs. a 024-only baseline is zero new objects and zero new drops."""
    entry = _FakeSourceEntry("entry-noref", entry_refs=[])

    # Plan: nothing gathered (proven above) -> empty bindings feed the pass.
    dropped: list = []
    ctx = _ctx_from_bindings({}, dropped)
    target_entry = _FakeTargetEntry027("entry-noref")
    factory = _FakeEntryRefFactory()
    target = _FakeCreateTarget({"entry-noref": target_entry}, factory=factory)

    skips = categories._run_entryref_create_pass(ctx, target, tag=None)

    assert skips == []
    assert factory.create_log == []              # 0 objects created
    assert len(target_entry.EntryRefsOS) == 0
    assert dropped == []                          # 0 new dropped records

    # Move-path and Preview-path drop reports over the empty source: both
    # emit nothing (parity holds trivially at the zero point).
    move_dropped: list = []
    categories._report_dropped_entry_refs(entry, move_dropped)
    assert move_dropped == []

    preview_dropped: list = []
    preview_ctx = _FakeRunContext(source_handle=object())
    preview_ctx._dropped = preview_dropped
    categories._plan_entry_reference_decisions(entry, preview_ctx, target=object())
    assert [r for r in preview_dropped if r.field_name == "EntryRefsOS"] == []
