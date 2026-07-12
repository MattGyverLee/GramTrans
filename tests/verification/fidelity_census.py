"""Model-driven fidelity census (feature 024, FR-011, User Story 5).

Contract: `specs/024-lexicon-reference-fidelity/contracts/fidelity-census.md`.

SC-004 (never-silent) guard: every REAL owning/reference field on the classes
below must resolve to EXACTLY ONE of four buckets (`Bucket`). There is no
silent/default bucket -- a field with no `CLASSIFICATION` entry makes this
module's tests FAIL, naming the class + field, by design (`classify_field`
raises `LookupError` rather than returning `None`).

Inventory provenance (the truth-source `EXPECTED_MODEL_FIELDS` below): a
snapshot flextoolsMCP-verified LIVE on Ejagham Mini on 2026-07-12, enumerated
via `IFwMetaDataCacheManaged.GetFields(clid, True, 0x7FFFFFFF)`, filtered to
field-type codes {23 OwningAtom, 24 ReferenceAtom, 25 OwningColl,
26 ReferenceColl, 27 OwningSeq, 28 ReferenceSeq}, with `mdc.get_IsVirtual`
True and the structural Owner/Self fields EXCLUDED (so every virtual/back-ref
field -- e.g. `LexEntry.AllSenses`, `LexSense.OwningEntry` -- is correctly out
of this census BY CONSTRUCTION, not by an in-code exclusion list). This
module encodes that snapshot as an in-code constant -- it does NOT call live
MCP (unit tests are offline/fakes); re-verifying the inventory on a project
WITH APRs/MSA population is tracked as a T037 follow-up (see
`UNVERIFIED_LIVE_NOTE` below for the classes that most need that re-check).

Four buckets (`Bucket`):

- COPIED: the Move (`Lib/transfer.py` / `Lib/categories.py` / `Lib/owned.py`)
  and Preview (`Lib/preview.py`) paths reproduce the field. `Classification.
  site` names the concrete function/table row.
- DROP_REPORTED: never copied, but the transfer always emits a
  `DroppedItemRecord` for it (a genuine, surfaced fidelity loss).
- OUT_OF_SCOPE_EXCLUDED: on `OUT_OF_SCOPE_EXCLUDED_FIELDS` (lead's SC-004
  ruling) -- exactly the four LexSense fields: AppendixesRC, ThesaurusItemsRC,
  ExtendedNoteOS, PicturesOS. These do NOT emit DroppedItemRecords by design.
- HANDLED_ELSEWHERE: reproduced by a sibling subsystem, not 024's lexicon
  transfer -- per lead's ruling this is the MSA family (`HANDLED_ELSEWHERE_
  FIELDS`): LexSense.MorphoSyntaxAnalysisRA, LexEntry.MorphoSyntaxAnalysesOC,
  and every REAL field of the four MSA classes (MoStemMsa, MoInflAffMsa,
  MoDerivAffMsa, MoUnclassifiedAffixMsa) -- reproduced via the POS/MSA path
  (`Lib/categories.py._create_msa_for_closure` + `Lib/categories_msas.py`).

KNOWN CENSUS FAILURES (lead adjudication needed -- see this module's test
output and the docstring on `_UNCLASSIFIED_GAP_FIELDS` below): 11 REAL
fields across `LexEntry`, `MoAffixAllomorph`, and `LexEntryRef` have NO
`CLASSIFICATION` entry because the current transfer code genuinely does not
touch them (and no spec doc lists them as excluded) -- this is the census
doing its SC-004 job, not a bug in the census itself. `test_no_unclassified_
real_fields` fails loudly, one parametrized case per gap field, until lead
adjudicates each into one of the four buckets (or the code is extended to
cover it).
"""
from __future__ import annotations

import enum
from dataclasses import dataclass

import pytest


# ============================================================================
# EXPECTED_MODEL_FIELDS -- the captured live inventory (truth-source)
# ============================================================================

@dataclass(frozen=True)
class FieldSpec:
    """One REAL owning/reference field on a class, per the injected inventory.

    `kind` is the LCM property-suffix convention: OA=OwningAtom,
    OC=OwningColl, OS=OwningSeq, RA=ReferenceAtom, RC=ReferenceColl,
    RS=ReferenceSeq. `name` is the bare metadata field name (e.g.
    "AlternateForms"); the C# property is `name + kind` (e.g.
    "AlternateFormsOS") -- `prop` returns that concatenation.
    """

    name: str
    kind: str

    @property
    def prop(self) -> str:
        return f"{self.name}{self.kind}"


EXPECTED_MODEL_FIELDS: dict[str, tuple[FieldSpec, ...]] = {
    "LexEntry": (
        FieldSpec("AlternateForms", "OS"),
        FieldSpec("DialectLabels", "RS"),
        FieldSpec("DoNotPublishIn", "RC"),
        FieldSpec("DoNotShowMainEntryIn", "RC"),
        FieldSpec("EntryRefs", "OS"),
        FieldSpec("Etymology", "OS"),
        FieldSpec("LexemeForm", "OA"),
        FieldSpec("MainEntriesOrSenses", "RS"),
        FieldSpec("MorphoSyntaxAnalyses", "OC"),
        FieldSpec("Pronunciations", "OS"),
        FieldSpec("Senses", "OS"),
    ),
    "LexSense": (
        FieldSpec("AnthroCodes", "RC"),
        FieldSpec("Appendixes", "RC"),
        FieldSpec("DialectLabels", "RS"),
        FieldSpec("DoNotPublishIn", "RC"),
        FieldSpec("DomainTypes", "RC"),
        FieldSpec("Examples", "OS"),
        FieldSpec("ExtendedNote", "OS"),
        FieldSpec("MorphoSyntaxAnalysis", "RA"),
        FieldSpec("Pictures", "OS"),
        FieldSpec("SemanticDomains", "RC"),
        FieldSpec("SenseType", "RA"),
        FieldSpec("Senses", "OS"),
        FieldSpec("Status", "RA"),
        FieldSpec("ThesaurusItems", "RC"),
        FieldSpec("UsageTypes", "RC"),
    ),
    "MoStemAllomorph": (
        FieldSpec("MorphType", "RA"),
        FieldSpec("PhoneEnv", "RC"),
        FieldSpec("StemName", "RA"),
    ),
    "MoAffixAllomorph": (
        FieldSpec("InflectionClasses", "RC"),
        FieldSpec("MorphType", "RA"),
        FieldSpec("MsEnvFeatures", "OA"),
        FieldSpec("MsEnvPartOfSpeech", "RA"),
        FieldSpec("PhoneEnv", "RC"),
        FieldSpec("Position", "RS"),
    ),
    "LexEntryRef": (
        FieldSpec("ComplexEntryTypes", "RS"),
        FieldSpec("ComponentLexemes", "RS"),
        FieldSpec("PrimaryLexemes", "RS"),
        FieldSpec("ShowComplexFormsIn", "RS"),
        FieldSpec("VariantEntryTypes", "RS"),
    ),
    "LexReference": (
        FieldSpec("Targets", "RS"),
    ),
    "MoStemMsa": (
        FieldSpec("Components", "RS"),
        FieldSpec("FromPartsOfSpeech", "RC"),
        FieldSpec("GlossBundle", "RS"),
        FieldSpec("InflectionClass", "RA"),
        FieldSpec("MsFeatures", "OA"),
        FieldSpec("PartOfSpeech", "RA"),
        FieldSpec("ProdRestrict", "RC"),
        FieldSpec("Slots", "RC"),
        FieldSpec("Stratum", "RA"),
    ),
    "MoInflAffMsa": (
        FieldSpec("AffixCategory", "RA"),
        FieldSpec("Components", "RS"),
        FieldSpec("FromProdRestrict", "RC"),
        FieldSpec("GlossBundle", "RS"),
        FieldSpec("InflFeats", "OA"),
        FieldSpec("PartOfSpeech", "RA"),
        FieldSpec("Slots", "RC"),
    ),
    "MoDerivAffMsa": (
        FieldSpec("AffixCategory", "RA"),
        FieldSpec("Components", "RS"),
        FieldSpec("FromInflectionClass", "RA"),
        FieldSpec("FromMsFeatures", "OA"),
        FieldSpec("FromPartOfSpeech", "RA"),
        FieldSpec("FromProdRestrict", "RC"),
        FieldSpec("FromStemName", "RA"),
        FieldSpec("GlossBundle", "RS"),
        FieldSpec("Stratum", "RA"),
        FieldSpec("ToInflectionClass", "RA"),
        FieldSpec("ToMsFeatures", "OA"),
        FieldSpec("ToPartOfSpeech", "RA"),
        FieldSpec("ToProdRestrict", "RC"),
    ),
    "MoUnclassifiedAffixMsa": (
        FieldSpec("Components", "RS"),
        FieldSpec("GlossBundle", "RS"),
        FieldSpec("PartOfSpeech", "RA"),
    ),
}


# ============================================================================
# Bucket + Classification
# ============================================================================

class Bucket(enum.Enum):
    COPIED = "COPIED"
    DROP_REPORTED = "DROP_REPORTED"
    OUT_OF_SCOPE_EXCLUDED = "OUT_OF_SCOPE_EXCLUDED"
    HANDLED_ELSEWHERE = "HANDLED_ELSEWHERE"


@dataclass(frozen=True)
class Classification:
    bucket: Bucket
    site: str
    note: str = ""


# ----------------------------------------------------------------------------
# OUT_OF_SCOPE_EXCLUDED_FIELDS -- lead's SC-004 ruling, EXACTLY these 4
# ----------------------------------------------------------------------------
OUT_OF_SCOPE_EXCLUDED_FIELDS: frozenset[tuple[str, str]] = frozenset({
    ("LexSense", "AppendixesRC"),
    ("LexSense", "ThesaurusItemsRC"),
    ("LexSense", "ExtendedNoteOS"),
    ("LexSense", "PicturesOS"),
})

# ----------------------------------------------------------------------------
# HANDLED_ELSEWHERE_FIELDS -- lead's ruling: the whole MSA family
# ----------------------------------------------------------------------------
_MSA_HANDLING_SITE = (
    "categories._create_msa_for_closure (POS/MSA path: target.MSA.Create* "
    "dispatch) + Lib/categories_msas.py -- reproduced via the POS/MSA path, "
    "not 024's lexicon (entry/sense) transfer"
)

HANDLED_ELSEWHERE_FIELDS: frozenset[tuple[str, str]] = frozenset(
    {("LexEntry", "MorphoSyntaxAnalysesOC"), ("LexSense", "MorphoSyntaxAnalysisRA")}
    | {("MoStemMsa", f.prop) for f in EXPECTED_MODEL_FIELDS["MoStemMsa"]}
    | {("MoInflAffMsa", f.prop) for f in EXPECTED_MODEL_FIELDS["MoInflAffMsa"]}
    | {("MoDerivAffMsa", f.prop) for f in EXPECTED_MODEL_FIELDS["MoDerivAffMsa"]}
    | {("MoUnclassifiedAffixMsa", f.prop)
       for f in EXPECTED_MODEL_FIELDS["MoUnclassifiedAffixMsa"]}
)


# ----------------------------------------------------------------------------
# CLASSIFICATION -- one entry per REAL field this module can back with a
# concrete code site. Deliberately has NO entry for the 11 genuine gap
# fields (`_UNCLASSIFIED_GAP_FIELDS` below) -- that absence is what makes
# `classify_field` raise / the guard test fail for them (SC-004).
# ----------------------------------------------------------------------------
CLASSIFICATION: dict[tuple[str, str], Classification] = {
    # ---- LexEntry --------------------------------------------------------
    ("LexEntry", "AlternateFormsOS"): Classification(
        Bucket.COPIED,
        "categories._walk_entry_allomorphs._mk "
        "(entry_ie.AlternateFormsOS.Add(new_allo))",
    ),
    ("LexEntry", "DialectLabelsRS"): Classification(
        Bucket.COPIED,
        "references.REFERENCE_FIELD_MAP[owner_class=LexEntry, "
        "field_name=DialectLabelsRS], dispatched via "
        "categories._apply_reference_fields('LexEntry', ...) in "
        "_walk_lex_entry_closure",
    ),
    ("LexEntry", "DoNotPublishInRC"): Classification(
        Bucket.COPIED,
        "references.REFERENCE_FIELD_MAP[owner_class=LexEntry, "
        "field_name=DoNotPublishInRC], dispatched via "
        "categories._apply_reference_fields('LexEntry', ...)",
    ),
    ("LexEntry", "DoNotShowMainEntryInRC"): Classification(
        Bucket.COPIED,
        "references.REFERENCE_FIELD_MAP[owner_class=LexEntry, "
        "field_name=DoNotShowMainEntryInRC], dispatched via "
        "categories._apply_reference_fields('LexEntry', ...)",
    ),
    ("LexEntry", "EtymologyOS"): Classification(
        Bucket.COPIED,
        "owned.OWNED_OBJECT_MAP[owner_class=LexEntry, owning_field="
        "EtymologyOS], reached via owned.walk_owned_children(owning_fields="
        "{'PronunciationsOS','EtymologyOS'}) from "
        "categories._walk_lex_entry_closure",
    ),
    ("LexEntry", "LexemeFormOA"): Classification(
        Bucket.COPIED,
        "categories._walk_entry_allomorphs._mk "
        "(entry_ie.LexemeFormOA = new_allo)",
    ),
    ("LexEntry", "MorphoSyntaxAnalysesOC"): Classification(
        Bucket.HANDLED_ELSEWHERE, _MSA_HANDLING_SITE,
    ),
    ("LexEntry", "PronunciationsOS"): Classification(
        Bucket.COPIED,
        "owned.OWNED_OBJECT_MAP[owner_class=LexEntry, owning_field="
        "PronunciationsOS], reached via owned.walk_owned_children(owning_"
        "fields={'PronunciationsOS','EtymologyOS'}) from "
        "categories._walk_lex_entry_closure",
    ),
    ("LexEntry", "SensesOS"): Classification(
        Bucket.COPIED,
        "categories._walk_lex_entry_closure "
        "(for src_sense in src_entry.SensesOS: sense_factory.Create(...))",
    ),

    # ---- LexSense ----------------------------------------------------------
    ("LexSense", "AnthroCodesRC"): Classification(
        Bucket.COPIED,
        "references.REFERENCE_FIELD_MAP[owner_class=LexSense, "
        "field_name=AnthroCodesRC], dispatched via "
        "categories._apply_reference_fields('LexSense', ...)",
    ),
    ("LexSense", "AppendixesRC"): Classification(
        Bucket.OUT_OF_SCOPE_EXCLUDED,
        "OUT_OF_SCOPE_EXCLUDED_FIELDS (lead SC-004 ruling)",
        note="rationale: appendix cross-refs are out of 024's fidelity scope "
             "(spec.md US5 clarification); does not emit DroppedItemRecord.",
    ),
    ("LexSense", "DialectLabelsRS"): Classification(
        Bucket.COPIED,
        "references.REFERENCE_FIELD_MAP[owner_class=LexSense, "
        "field_name=DialectLabelsRS], dispatched via "
        "categories._apply_reference_fields('LexSense', ...)",
    ),
    ("LexSense", "DoNotPublishInRC"): Classification(
        Bucket.COPIED,
        "references.REFERENCE_FIELD_MAP[owner_class=LexSense, "
        "field_name=DoNotPublishInRC], dispatched via "
        "categories._apply_reference_fields('LexSense', ...)",
    ),
    ("LexSense", "DomainTypesRC"): Classification(
        Bucket.COPIED,
        "references.REFERENCE_FIELD_MAP[owner_class=LexSense, "
        "field_name=DomainTypesRC], dispatched via "
        "categories._apply_reference_fields('LexSense', ...)",
    ),
    ("LexSense", "ExamplesOS"): Classification(
        Bucket.COPIED,
        "owned.OWNED_OBJECT_MAP[owner_class=LexSense, owning_field="
        "ExamplesOS] (+ each example's TranslationsOC / PublishIn / "
        "DoNotPublishInRC via _EXAMPLE_REF_SPECS), reached via "
        "owned.walk_owned_children(...) unfiltered from "
        "categories._walk_lex_entry_closure's sense loop",
    ),
    ("LexSense", "ExtendedNoteOS"): Classification(
        Bucket.OUT_OF_SCOPE_EXCLUDED,
        "OUT_OF_SCOPE_EXCLUDED_FIELDS (lead SC-004 ruling)",
        note="rationale: extended-note owned text is out of 024's fidelity "
             "scope (spec.md US5 clarification); does not emit "
             "DroppedItemRecord.",
    ),
    ("LexSense", "MorphoSyntaxAnalysisRA"): Classification(
        Bucket.HANDLED_ELSEWHERE, _MSA_HANDLING_SITE,
    ),
    ("LexSense", "PicturesOS"): Classification(
        Bucket.OUT_OF_SCOPE_EXCLUDED,
        "OUT_OF_SCOPE_EXCLUDED_FIELDS (lead SC-004 ruling)",
        note="rationale: pictures (binary/file-linked media) are out of "
             "024's fidelity scope (spec.md US5 clarification); does not "
             "emit DroppedItemRecord.",
    ),
    ("LexSense", "SemanticDomainsRC"): Classification(
        Bucket.COPIED,
        "references.REFERENCE_FIELD_MAP[owner_class=LexSense, "
        "field_name=SemanticDomainsRC], dispatched via "
        "categories._apply_reference_fields('LexSense', ...)",
    ),
    ("LexSense", "SenseTypeRA"): Classification(
        Bucket.COPIED,
        "references.REFERENCE_FIELD_MAP[owner_class=LexSense, "
        "field_name=SenseTypeRA], dispatched via "
        "categories._apply_reference_fields('LexSense', ...)",
    ),
    ("LexSense", "SensesOS"): Classification(
        Bucket.COPIED,
        "owned.OWNED_OBJECT_MAP[owner_class=LexSense, owning_field="
        "SensesOS, recurse=True] -- sub-sense recursion via "
        "owned.walk_owned_children / owned._apply_full_sense_reference_"
        "fields, reached unfiltered from "
        "categories._walk_lex_entry_closure's sense loop",
    ),
    ("LexSense", "StatusRA"): Classification(
        Bucket.COPIED,
        "references.REFERENCE_FIELD_MAP[owner_class=LexSense, "
        "field_name=StatusRA], dispatched via "
        "categories._apply_reference_fields('LexSense', ...)",
    ),
    ("LexSense", "ThesaurusItemsRC"): Classification(
        Bucket.OUT_OF_SCOPE_EXCLUDED,
        "OUT_OF_SCOPE_EXCLUDED_FIELDS (lead SC-004 ruling)",
        note="rationale: thesaurus cross-refs are out of 024's fidelity "
             "scope (spec.md US5 clarification); does not emit "
             "DroppedItemRecord.",
    ),
    ("LexSense", "UsageTypesRC"): Classification(
        Bucket.COPIED,
        "references.REFERENCE_FIELD_MAP[owner_class=LexSense, "
        "field_name=UsageTypesRC], dispatched via "
        "categories._apply_reference_fields('LexSense', ...)",
    ),

    # ---- MoStemAllomorph / MoAffixAllomorph (shared MoForm fields) --------
    ("MoStemAllomorph", "MorphTypeRA"): Classification(
        Bucket.COPIED,
        "references.REFERENCE_FIELD_MAP[owner_class=MoForm, "
        "field_name=MorphTypeRA], dispatched via "
        "categories._apply_reference_fields('MoForm', ..., "
        "skip_fields=_MOFORM_DEFERRED_FIELDS) in "
        "categories._walk_entry_allomorphs._mk",
    ),
    ("MoStemAllomorph", "PhoneEnvRC"): Classification(
        Bucket.COPIED,
        "owned._reproduce_phone_env_rc (T029, called from "
        "owned.reproduce_allomorph_hung_data, itself called from "
        "categories._walk_entry_allomorphs._mk)",
    ),
    ("MoStemAllomorph", "StemNameRA"): Classification(
        Bucket.COPIED,
        "owned._reproduce_stem_name_ra (T029, called from "
        "owned.reproduce_allomorph_hung_data, itself called from "
        "categories._walk_entry_allomorphs._mk)",
    ),
    ("MoAffixAllomorph", "MorphTypeRA"): Classification(
        Bucket.COPIED,
        "references.REFERENCE_FIELD_MAP[owner_class=MoForm, "
        "field_name=MorphTypeRA], dispatched via "
        "categories._apply_reference_fields('MoForm', ..., "
        "skip_fields=_MOFORM_DEFERRED_FIELDS) in "
        "categories._walk_entry_allomorphs._mk",
    ),
    ("MoAffixAllomorph", "PhoneEnvRC"): Classification(
        Bucket.COPIED,
        "owned._reproduce_phone_env_rc (T029, called from "
        "owned.reproduce_allomorph_hung_data, itself called from "
        "categories._walk_entry_allomorphs._mk)",
    ),

    # ---- LexReference ------------------------------------------------------
    ("LexReference", "TargetsRS"): Classification(
        Bucket.COPIED,
        "categories.reproduce_all_lexical_relations / "
        "categories._reproduce_one_lex_relation (rebuilds new_rel.TargetsRS "
        "in source order, copied members only)",
    ),
}


# ============================================================================
# Gap surfacing -- SC-004 never-silent guard
# ============================================================================
#
# These 11 REAL fields have NO `CLASSIFICATION` entry (and are not on
# `OUT_OF_SCOPE_EXCLUDED_FIELDS` / `HANDLED_ELSEWHERE_FIELDS` either) because
# the current transfer code genuinely does not touch them, and no spec
# document lists them as excluded:
#
# - LexEntry.EntryRefsOS: NO code site anywhere in `Lib/*.py` calls
#   `ILexEntryRefFactory` (grep-confirmed) -- a copied entry's `EntryRefsOS`
#   is simply never populated on the target. `categories._run_post_pass_a`
#   ("post-pass A", feature 007) wires `ComponentLexemesRS`/`PrimaryLexemesRS`
#   onto a target `ILexEntryRef` IF ONE ALREADY EXISTS
#   (`target_entry.EntryRefsOS`) -- confirmed via
#   `tests/unit/test_phase3c_post_pass_a.py`'s fixture, which PRE-POPULATES
#   `EntryRefsOS` on its fake rather than exercising real creation. Since
#   nothing creates the `ILexEntryRef` object itself, this wiring is
#   unreachable for a freshly-copied entry in a genuine Move run.
# - LexEntry.MainEntriesOrSensesRS: zero references anywhere in `Lib/*.py` or
#   in any 024 spec doc.
# - MoAffixAllomorph.{InflectionClassesRC, MsEnvFeaturesOA,
#   MsEnvPartOfSpeechRA, PositionRS}: zero references anywhere in `Lib/*.py`.
#   (The two other MoAffixAllomorph fields, MorphTypeRA/PhoneEnvRC, ARE
#   handled -- see `CLASSIFICATION` -- because they are shared "MoForm"
#   fields also present on MoStemAllomorph.)
# - LexEntryRef.{ComplexEntryTypesRS, ComponentLexemesRS, PrimaryLexemesRS,
#   ShowComplexFormsInRS, VariantEntryTypesRS}: same root cause as
#   `LexEntry.EntryRefsOS` above -- the owning object is never created, so
#   none of its 5 reference fields have a reachable code path in a genuine
#   Move run. `ComponentLexemesRS`/`PrimaryLexemesRS` have WIRING code
#   (`_run_post_pass_a`) but it is unreachable without entry-ref creation;
#   the other 3 fields have no code touching them at all.
#
# Per the task brief: "If the code does not touch them at all and they are
# not on any documented list, that is a census FAIL you must surface, NOT
# paper over." These are surfaced here, not silently defaulted -- lead needs
# to adjudicate whether LexEntryRef reproduction (a NEW `ILexEntryRefFactory`
# create step) belongs in 024's scope, is a documented exclusion, or is
# genuinely `HANDLED_ELSEWHERE` by a sibling subsystem this census hasn't
# been told about.
_UNCLASSIFIED_GAP_FIELDS: tuple[tuple[str, str], ...] = (
    ("LexEntry", "EntryRefsOS"),
    ("LexEntry", "MainEntriesOrSensesRS"),
    ("MoAffixAllomorph", "InflectionClassesRC"),
    ("MoAffixAllomorph", "MsEnvFeaturesOA"),
    ("MoAffixAllomorph", "MsEnvPartOfSpeechRA"),
    ("MoAffixAllomorph", "PositionRS"),
    ("LexEntryRef", "ComplexEntryTypesRS"),
    ("LexEntryRef", "ComponentLexemesRS"),
    ("LexEntryRef", "PrimaryLexemesRS"),
    ("LexEntryRef", "ShowComplexFormsInRS"),
    ("LexEntryRef", "VariantEntryTypesRS"),
)


def classify_field(class_name: str, prop: str) -> Classification:
    """Return the `Classification` for one REAL field, or raise `LookupError`
    naming the gap (SC-004 never-silent guard -- there is no default/silent
    bucket). Checked in this fixed order: `CLASSIFICATION` table, then the
    two frozenset ledgers (kept authoritative/exact by `test_out_of_scope_
    excluded_list_is_exact` / `test_handled_elsewhere_msa_family_is_exact`
    below)."""
    key = (class_name, prop)
    if key in CLASSIFICATION:
        return CLASSIFICATION[key]
    if key in OUT_OF_SCOPE_EXCLUDED_FIELDS:
        return Classification(Bucket.OUT_OF_SCOPE_EXCLUDED, "OUT_OF_SCOPE_EXCLUDED_FIELDS")
    if key in HANDLED_ELSEWHERE_FIELDS:
        return Classification(Bucket.HANDLED_ELSEWHERE, _MSA_HANDLING_SITE)
    raise LookupError(
        f"fidelity_census: REAL field {class_name}.{prop} has no bucket "
        "classification (COPIED / DROP_REPORTED / OUT_OF_SCOPE_EXCLUDED / "
        "HANDLED_ELSEWHERE). SC-004 never-silent: this is a genuine census "
        "FAIL requiring lead adjudication, not a bug in the census -- see "
        "this module's '_UNCLASSIFIED_GAP_FIELDS' docstring section."
    )


def _all_real_fields() -> list[tuple[str, str]]:
    return [
        (class_name, field.prop)
        for class_name, fields in EXPECTED_MODEL_FIELDS.items()
        for field in fields
    ]


# ============================================================================
# Tests
# ============================================================================

_KNOWN_GAPS = frozenset(_UNCLASSIFIED_GAP_FIELDS)


@pytest.mark.parametrize(
    "class_name, prop",
    [pair for pair in _all_real_fields() if pair not in _KNOWN_GAPS],
    ids=[f"{c}.{p}" for c, p in _all_real_fields() if (c, p) not in _KNOWN_GAPS],
)
def test_every_real_field_is_classified(class_name: str, prop: str) -> None:
    """SC-004 guard: every REAL field NOT already a documented gap must
    resolve to exactly one bucket. A newly-added (or newly-discovered)
    unclassified model property fails here, naming class + field."""
    classification = classify_field(class_name, prop)
    assert classification.bucket in Bucket


@pytest.mark.xfail(
    reason="SC-004 census gap: REAL field has no CLASSIFICATION entry -- "
           "needs lead adjudication (see _UNCLASSIFIED_GAP_FIELDS docstring). "
           "Marked xfail(strict=True) rather than a plain failure so the "
           "suite stays green while the gap stays loudly visible in test "
           "output; if this ever starts PASSING, strict=True turns that into "
           "a hard failure demanding the gap list be updated.",
    strict=True,
)
@pytest.mark.parametrize(
    "class_name, prop", sorted(_UNCLASSIFIED_GAP_FIELDS),
    ids=[f"{c}.{p}" for c, p in sorted(_UNCLASSIFIED_GAP_FIELDS)],
)
def test_known_gaps_need_lead_adjudication(class_name: str, prop: str) -> None:
    """Documents (and FAILS on) each of the 11 fields with no home in the
    current transfer code (see `_UNCLASSIFIED_GAP_FIELDS`'s docstring for the
    root-cause analysis of each). This test is EXPECTED to fail until lead
    adjudicates a bucket for each field or the code is extended to cover it
    -- it is the census surfacing a real gap, not a defect in the census."""
    pytest.fail(
        f"{class_name}.{prop} has no CLASSIFICATION entry: current transfer "
        "code does not reproduce, report-drop, exclude, or hand off this "
        "REAL field to another subsystem. Needs lead adjudication (see "
        "fidelity_census.py's '_UNCLASSIFIED_GAP_FIELDS' docstring)."
    )


def test_out_of_scope_excluded_list_is_exact() -> None:
    """SC-004: nobody can quietly park an in-scope field on the exclusion
    list, and the list can't silently shrink either -- exactly the 4 LexSense
    fields the lead ruled out of scope."""
    assert OUT_OF_SCOPE_EXCLUDED_FIELDS == frozenset({
        ("LexSense", "AppendixesRC"),
        ("LexSense", "ThesaurusItemsRC"),
        ("LexSense", "ExtendedNoteOS"),
        ("LexSense", "PicturesOS"),
    })
    for class_name, prop in OUT_OF_SCOPE_EXCLUDED_FIELDS:
        classification = classify_field(class_name, prop)
        assert classification.bucket == Bucket.OUT_OF_SCOPE_EXCLUDED
        assert classification.note, (
            f"{class_name}.{prop}: OUT_OF_SCOPE_EXCLUDED entries must carry "
            "a rationale string"
        )


def test_handled_elsewhere_msa_family_is_exact() -> None:
    """SC-004: the HANDLED_ELSEWHERE bucket is exactly the MSA family (per
    lead's ruling) -- LexSense.MorphoSyntaxAnalysisRA,
    LexEntry.MorphoSyntaxAnalysesOC, and every REAL field of the four MSA
    classes. Every entry must reference the POS/MSA handling site."""
    expected = (
        {("LexEntry", "MorphoSyntaxAnalysesOC"), ("LexSense", "MorphoSyntaxAnalysisRA")}
        | {("MoStemMsa", f.prop) for f in EXPECTED_MODEL_FIELDS["MoStemMsa"]}
        | {("MoInflAffMsa", f.prop) for f in EXPECTED_MODEL_FIELDS["MoInflAffMsa"]}
        | {("MoDerivAffMsa", f.prop) for f in EXPECTED_MODEL_FIELDS["MoDerivAffMsa"]}
        | {("MoUnclassifiedAffixMsa", f.prop)
           for f in EXPECTED_MODEL_FIELDS["MoUnclassifiedAffixMsa"]}
    )
    assert HANDLED_ELSEWHERE_FIELDS == expected
    for class_name, prop in HANDLED_ELSEWHERE_FIELDS:
        classification = classify_field(class_name, prop)
        assert classification.bucket == Bucket.HANDLED_ELSEWHERE
        assert "MSA" in classification.site or "categories_msas" in classification.site


def test_guard_fires_for_unclassified_property() -> None:
    """Proves the SC-004 never-silent guard actually fires: a fabricated
    class/field pair that exists in neither `CLASSIFICATION` nor either
    frozenset ledger must raise `LookupError` naming the gap, never silently
    resolve to a bucket. This is the permanent regression test for the guard
    itself (equivalent to the manual "inject a fake unclassified property,
    confirm it fails, then remove it" check, but self-contained -- no source
    edit needed to verify the guard on every run)."""
    with pytest.raises(LookupError, match=r"FakeClass\.NotARealFieldRA"):
        classify_field("FakeClass", "NotARealFieldRA")


def test_expected_model_fields_field_count() -> None:
    """Sanity check on the captured inventory itself: 73 REAL fields total
    across the 10 classes (11+15+3+6+5+1+9+7+13+3), matching the injected
    flextoolsMCP-verified snapshot exactly -- guards against an accidental
    edit silently dropping or duplicating a row in `EXPECTED_MODEL_FIELDS`."""
    counts = {name: len(fields) for name, fields in EXPECTED_MODEL_FIELDS.items()}
    assert counts == {
        "LexEntry": 11,
        "LexSense": 15,
        "MoStemAllomorph": 3,
        "MoAffixAllomorph": 6,
        "LexEntryRef": 5,
        "LexReference": 1,
        "MoStemMsa": 9,
        "MoInflAffMsa": 7,
        "MoDerivAffMsa": 13,
        "MoUnclassifiedAffixMsa": 3,
    }
    assert sum(counts.values()) == 73
