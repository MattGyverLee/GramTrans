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

from gramtrans.Lib import categories
from gramtrans.Lib.models import DroppedItemRecord


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
