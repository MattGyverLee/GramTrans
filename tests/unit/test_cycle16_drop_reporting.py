"""Write-first unit tests for the cycle-16 lead adjudication (fidelity census
cycle-16 -- 11 previously-unclassified fields moved to terminal buckets).

Covers the two DROP_REPORTED emission sites the census gap identified:

1. `LexEntry.EntryRefsOS` (`Lib/categories.py._report_dropped_entry_refs`,
   called identically from `_walk_lex_entry_closure` (Move) and
   `_plan_entry_reference_decisions` (Preview)) -- one `DroppedItemRecord`
   per un-reproduced `LexEntryRef`, naming the relationship kind (variant
   vs complex-form, from `RefType`) and identifying the ref by its
   component + variant/complex type. This SUBSUMES
   `LexEntryRef.{ComponentLexemesRS, PrimaryLexemesRS, VariantEntryTypesRS,
   ComplexEntryTypesRS, ShowComplexFormsInRS}` -- no separate records for
   those 5 fields.

   SUPERSEDED (027 cycle-3, contract C4): originally report-ALL (no
   `ILexEntryRefFactory` create site existed at cycle-16 time). 027 added
   C1-C3 (`_run_entryref_create_pass`/`_run_post_pass_a`), which actually
   reproduce a ref whose components/primaries are all in-closure -- so the
   policy flipped to report-only-un-reproduced
   (`categories._entry_ref_is_reproducible`); see
   `tests/unit/test_027_never_silent.py` for the flip's own dedicated
   coverage. The tests below still use fakes shaped to be "out of closure"
   (no `LexemeFormOA`) so they continue to exercise the reported half of
   that split unchanged.

2. `MoAffixAllomorph.{InflectionClassesRC, MsEnvFeaturesOA,
   MsEnvPartOfSpeechRA, PositionRS}` -- feature 028 REPRODUCED all four
   (US1-US4); the cycle-16 field-level report stub they originally routed to
   (`Lib/owned.py._report_dropped_moaffix_msenv_fields`) is now RETIRED (028
   T016). Each field's own reproduce leg (dispatched via
   `owned.reproduce_moaffix_msenv_data` (Move) /
   `_plan_moaffix_msenv_decisions` (Preview), called from
   `reproduce_allomorph_hung_data` / `plan_allomorph_hung_data_decisions`)
   reports a `DroppedItemRecord` only when a value cannot be reproduced
   (partial fidelity, never-silent). The tests below stay GREEN because those
   report paths preserve the same never-silent guarantee against a bare
   target: vacuous (zero records) for a `MoStemAllomorph` and for a
   `MoAffixAllomorph` populating none of the 4.

Both drop sites are, by construction, the SAME function called from both
Move and Preview call sites (no separate CREATE/LINK decision exists for
either -- nothing is ever created either way this cycle) -- the parity
tests below prove that construction holds, not just that each function in
isolation behaves.
"""
from __future__ import annotations

from gramtrans.Lib import categories, owned
from gramtrans.Lib.models import DroppedItemRecord


WS_EN = 100


# ============================================================================
# Small shared fakes
# ============================================================================

class _FakeMultiString:
    """Fake ICmMultiString -- `_multistring_dict`'s `_data`-dict fallback."""

    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})


class _FakeGuidObj:
    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid


class _FakePossibilityType(_FakeGuidObj):
    """Fake ICmPossibility -- a variant/complex-form TYPE item (has a Name)."""

    def __init__(self, guid, name=""):
        super().__init__(guid)
        self.Name = _FakeMultiString({WS_EN: name} if name else {})


class _FakeComponentEntry(_FakeGuidObj):
    """Fake ILexEntry used as a LexEntryRef's component (has CitationForm)."""

    def __init__(self, guid, citation_form=""):
        super().__init__(guid)
        self.CitationForm = _FakeMultiString(
            {WS_EN: citation_form} if citation_form else {})


class _FakeLexEntryRef(_FakeGuidObj):
    """Fake ILexEntryRef -- `RefType` (0=variant, 1=complex-form) +
    ComponentLexemesRS/VariantEntryTypesRS/ComplexEntryTypesRS."""

    def __init__(self, guid, ref_type, components=(), variant_types=(),
                 complex_types=()):
        super().__init__(guid)
        self.RefType = ref_type
        self.ComponentLexemesRS = list(components)
        self.PrimaryLexemesRS = []
        self.VariantEntryTypesRS = list(variant_types)
        self.ComplexEntryTypesRS = list(complex_types)
        self.ShowComplexFormsInRS = []


class _FakeSourceEntry(_FakeGuidObj):
    """Fake ILexEntry -- just enough surface for `_report_dropped_entry_refs`
    / `_plan_entry_reference_decisions` to run without a live LCM host."""

    def __init__(self, guid, citation_form="", entry_refs=()):
        super().__init__(guid)
        self.CitationForm = _FakeMultiString(
            {WS_EN: citation_form} if citation_form else {})
        self.EntryRefsOS = list(entry_refs)


# ============================================================================
# (1) LexEntry.EntryRefsOS -- DROP_REPORTED
# ============================================================================

def test_entry_ref_variant_type_emits_one_dropped_record_naming_variant_and_component():
    """Mirrors the 6 Ejagham variant entries: RefType=0 (variant), 1
    component, 1 variantType."""
    comp = _FakeComponentEntry("comp-guid-1", citation_form="root-word")
    vtype = _FakePossibilityType("vtype-guid-1", name="Dialectal Variant")
    ref = _FakeLexEntryRef("ref-guid-1", ref_type=0, components=[comp],
                            variant_types=[vtype])
    entry = _FakeSourceEntry("entry-guid-1", citation_form="variant-word",
                              entry_refs=[ref])

    dropped: list = []
    categories._report_dropped_entry_refs(entry, dropped)

    assert len(dropped) == 1
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.owner_kind == "LexEntry"
    assert rec.owner_guid == "entry-guid-1"
    assert rec.field_name == "EntryRefsOS"
    assert rec.item_guid == "ref-guid-1"
    assert "variant" in rec.item_name
    assert "root-word" in rec.item_name
    assert "Dialectal Variant" in rec.item_name
    assert "variant" in rec.reason
    assert "027-complex-forms-variants" in rec.reason


def test_entry_ref_complex_form_type_emits_one_dropped_record_naming_complex_form():
    comp = _FakeComponentEntry("comp-guid-2", citation_form="base-word")
    ctype = _FakePossibilityType("ctype-guid-2", name="Compound")
    ref = _FakeLexEntryRef("ref-guid-2", ref_type=1, components=[comp],
                            complex_types=[ctype])
    entry = _FakeSourceEntry("entry-guid-2", entry_refs=[ref])

    dropped: list = []
    categories._report_dropped_entry_refs(entry, dropped)

    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.item_guid == "ref-guid-2"
    assert "complex-form" in rec.item_name
    assert "base-word" in rec.item_name
    assert "Compound" in rec.item_name
    assert "complex-form" in rec.reason


def test_entry_with_multiple_entry_refs_emits_one_record_per_ref():
    """027 C4 policy flip: a ref with 0 components/primaries is trivially
    "in closure" (nothing external to fail on) and is no longer reported --
    so both refs here are given an out-of-closure `_FakeComponentEntry`
    component (it lacks `LexemeFormOA`, hence `_affix_type_of` -> ineligible
    -- see `_entry_ref_is_reproducible`) to keep proving the per-ref (not
    per-entry) multiplicity this test targets."""
    comp_a = _FakeComponentEntry("comp-a", citation_form="word-a")
    comp_b = _FakeComponentEntry("comp-b", citation_form="word-b")
    ref_a = _FakeLexEntryRef("ref-a", ref_type=0, components=[comp_a])
    ref_b = _FakeLexEntryRef("ref-b", ref_type=1, components=[comp_b])
    entry = _FakeSourceEntry("entry-guid-3", entry_refs=[ref_a, ref_b])

    dropped: list = []
    categories._report_dropped_entry_refs(entry, dropped)

    assert {r.item_guid for r in dropped} == {"ref-a", "ref-b"}
    assert len(dropped) == 2


def test_entry_with_no_entry_refs_emits_nothing():
    entry = _FakeSourceEntry("entry-guid-4", entry_refs=[])

    dropped: list = []
    categories._report_dropped_entry_refs(entry, dropped)

    assert dropped == []


# ----------------------------------------------------------------------------
# Move + Preview parity: same drop set for EntryRefsOS.
# ----------------------------------------------------------------------------

class _FakeRunContext:
    """Minimal ctx surface `_plan_entry_reference_decisions` needs: no live
    LCM host required (every internal call it makes is fail-soft/duck-typed
    against an object this bare)."""

    def __init__(self, source_handle):
        self.source_handle = source_handle
        self.target_handle = object()


def test_move_and_preview_drop_sets_identical_for_entry_refs():
    """`_report_dropped_entry_refs` (the Move call site's function) and
    `_plan_entry_reference_decisions` (the actual Preview entrypoint, which
    calls the SAME function internally) must produce the identical
    EntryRefsOS drop set for the same source entry."""
    comp = _FakeComponentEntry("comp-guid-5", citation_form="root-word-5")
    vtype = _FakePossibilityType("vtype-guid-5", name="Free Variant")
    ref = _FakeLexEntryRef("ref-guid-5", ref_type=0, components=[comp],
                            variant_types=[vtype])
    entry = _FakeSourceEntry("entry-guid-5", citation_form="var-5",
                              entry_refs=[ref])

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
# (2) MoAffixAllomorph MsEnv/inflection-class/position fields -- DROP_REPORTED
# ============================================================================

class _FakeMoAffixAllomorph(_FakeGuidObj):
    def __init__(self, guid, inflection_classes=(), msenv_features=None,
                 msenv_pos=None, position=()):
        super().__init__(guid)
        self.ClassName = "MoAffixAllomorph"
        self.PhoneEnvRC = []
        self.StemNameRA = None
        self.InflectionClassesRC = list(inflection_classes)
        self.MsEnvFeaturesOA = msenv_features
        self.MsEnvPartOfSpeechRA = msenv_pos
        self.PositionRS = list(position)


class _FakeMoStemAllomorph(_FakeGuidObj):
    def __init__(self, guid):
        super().__init__(guid)
        self.ClassName = "MoStemAllomorph"
        self.PhoneEnvRC = []
        self.StemNameRA = None


class _FakeNewAllomorph(_FakeGuidObj):
    def __init__(self, guid):
        super().__init__(guid)
        self.PhoneEnvRC = []
        self.StemNameRA = None


class _FakeHungDataContext:
    """Minimal ctx surface for `reproduce_allomorph_hung_data`/
    `plan_allomorph_hung_data_decisions` when PhoneEnvRC/StemNameRA/APRs are
    all empty (every guard clause short-circuits before touching
    source_handle/target_handle's internals)."""

    def __init__(self):
        self.source_handle = object()
        self.target_handle = object()
        self._copy_set = {}


def test_moaffix_allomorph_none_populated_emits_nothing():
    src = _FakeMoAffixAllomorph("allo-none")
    new = _FakeNewAllomorph("allo-none")
    ctx = _FakeHungDataContext()

    move_dropped: list = []
    owned.reproduce_allomorph_hung_data(
        src, new, ctx, "tag", {}, move_dropped)
    assert move_dropped == []

    preview_dropped: list = []
    owned.plan_allomorph_hung_data_decisions(src, ctx, {}, preview_dropped)
    assert preview_dropped == []


def test_mostemallomorph_never_reports_msenv_fields():
    """Vacuous for MoStemAllomorph -- the 4 fields don't exist on that
    subclass at all."""
    src = _FakeMoStemAllomorph("stem-allo-1")
    new = _FakeNewAllomorph("stem-allo-1")
    ctx = _FakeHungDataContext()

    dropped: list = []
    owned.reproduce_allomorph_hung_data(src, new, ctx, "tag", {}, dropped)
    assert dropped == []


def test_moaffix_allomorph_all_four_fields_populated_move_reports_one_record_each():
    """Never-silent backstop across all four fields, ROLLOUT-AWARE (028
    incremental delivery): against a bare-`object()` target -- no POS/env/
    feature infra -- NONE of the four fields can be reproduced, so every
    populated field still yields exactly one `DroppedItemRecord` (the
    never-silent guarantee holds throughout US1-US4). A field whose 028
    reproduce leg has NOT yet landed (`owned._msenv_unreproduced_fields()`)
    is reported by the cycle-16 report-only stub (its reason names the
    028 feature); a field whose leg HAS landed
    (`owned._MSENV_REPRODUCED_FIELDS`, e.g. US1's MsEnvPartOfSpeechRA) is
    reported by that leg's own resolve-or-create-failed path."""
    src = _FakeMoAffixAllomorph(
        "allo-full",
        inflection_classes=[_FakeGuidObj("iclass-1")],
        msenv_features=_FakeGuidObj("msenv-feat-1"),
        msenv_pos=_FakeGuidObj("msenv-pos-1"),
        position=[_FakeGuidObj("pos-1")],
    )
    new = _FakeNewAllomorph("allo-full")
    ctx = _FakeHungDataContext()

    dropped: list = []
    owned.reproduce_allomorph_hung_data(src, new, ctx, "tag", {}, dropped)

    field_names = {r.field_name for r in dropped}
    assert field_names == {
        "InflectionClassesRC", "MsEnvFeaturesOA", "MsEnvPartOfSpeechRA",
        "PositionRS",
    }
    assert len(dropped) == 4
    stub_fields = owned._msenv_unreproduced_fields()
    for rec in dropped:
        assert rec.owner_kind == "MoAffixAllomorph"
        assert rec.owner_guid == "allo-full"
        assert rec.reason  # never-silent: a non-empty reason is always present
        if rec.field_name in stub_fields:
            assert "028-affix-allomorph-morphosyntax" in rec.reason


def test_moaffix_allomorph_partial_population_move_reports_only_populated_fields():
    src = _FakeMoAffixAllomorph(
        "allo-partial",
        msenv_pos=_FakeGuidObj("msenv-pos-2"),
    )
    new = _FakeNewAllomorph("allo-partial")
    ctx = _FakeHungDataContext()

    dropped: list = []
    owned.reproduce_allomorph_hung_data(src, new, ctx, "tag", {}, dropped)

    assert len(dropped) == 1
    assert dropped[0].field_name == "MsEnvPartOfSpeechRA"


# ----------------------------------------------------------------------------
# Move + Preview parity: same drop set for the 4 MoAffixAllomorph fields.
# ----------------------------------------------------------------------------

def test_move_and_preview_drop_sets_identical_for_moaffix_msenv_fields():
    src = _FakeMoAffixAllomorph(
        "allo-parity",
        inflection_classes=[_FakeGuidObj("iclass-parity")],
        msenv_features=_FakeGuidObj("msenv-feat-parity"),
        msenv_pos=_FakeGuidObj("msenv-pos-parity"),
        position=[_FakeGuidObj("pos-parity")],
    )
    new = _FakeNewAllomorph("allo-parity")
    move_ctx = _FakeHungDataContext()
    preview_ctx = _FakeHungDataContext()

    move_dropped: list = []
    owned.reproduce_allomorph_hung_data(
        src, new, move_ctx, "tag", {}, move_dropped)

    preview_dropped: list = []
    owned.plan_allomorph_hung_data_decisions(src, preview_ctx, {}, preview_dropped)

    def _key(records):
        return sorted(
            (r.owner_kind, r.owner_guid, r.field_name, r.item_guid, r.reason)
            for r in records
        )

    assert _key(move_dropped) == _key(preview_dropped)
    assert len(move_dropped) == 4


# ============================================================================
# T037 Finding 1(b) -- `_plan_entry_reference_decisions`'s catch-all must
# EMIT a DroppedItemRecord, never silently `return ()` (Principle III /
# FR-010). Before this fix the broad `except (AttributeError, TypeError,
# KeyError)` at categories.py:3480-3488 only logged a warning and returned
# an empty tuple -- any residual reference-decision failure for an entry
# vanished with no trace in `RunPlan.dropped_items`.
# ============================================================================

def test_plan_entry_reference_decisions_catchall_emits_dropped_record(monkeypatch):
    """Force a TypeError inside the try body (the resolver-cache lookup, the
    first call `_plan_entry_reference_decisions` makes after establishing
    `dropped`) and assert the except handler appends exactly one
    `DroppedItemRecord` to the run's `dropped` sink -- never a silent `()`."""
    entry = _FakeSourceEntry("entry-guid-catchall")

    def _boom(_context):
        raise TypeError("forced failure for T037 Finding 1(b) regression")

    monkeypatch.setattr(categories, "_get_resolver_cache", _boom)

    preview_dropped: list = []
    ctx = _FakeRunContext(source_handle=object())
    ctx._dropped = preview_dropped

    result = categories._plan_entry_reference_decisions(entry, ctx, target=object())

    assert result == (), "the fail-soft return value itself is unchanged (empty tuple)"
    assert len(preview_dropped) == 1, (
        f"expected exactly one DroppedItemRecord surfacing the forced "
        f"TypeError, got {preview_dropped!r} -- a silent () violates "
        f"Principle III / FR-010"
    )
    record = preview_dropped[0]
    assert isinstance(record, DroppedItemRecord)
    assert record.owner_kind == "LexEntry"
    assert record.owner_guid == "entry-guid-catchall"
    assert record.item_guid == "entry-guid-catchall"
    assert "TypeError" in record.reason
    assert "forced failure for T037 Finding 1(b) regression" in record.reason
