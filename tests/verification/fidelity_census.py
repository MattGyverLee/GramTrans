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
- OUT_OF_SCOPE_EXCLUDED: reserved for a genuinely read-only derived
  aggregate that can never be an independent data-loss point --
  EXACTLY `LexEntry.MainEntriesOrSensesRS` (cycle-16 ruling; rationale-class
  "read-only-derived-aggregate": `can_write=false`, transitively populated
  by the LexEntryRef mechanism). This bucket does NOT emit
  DroppedItemRecords by design, and (cycle-17 correction, below) is no
  longer used as a silent parking spot for genuinely-lost fields -- see
  SC-003/FR-010 ("NOTHING is silently lost").
- HANDLED_ELSEWHERE: reproduced by a sibling subsystem, not 024's lexicon
  transfer -- per lead's ruling this is the MSA family (`HANDLED_ELSEWHERE_
  FIELDS`): LexSense.MorphoSyntaxAnalysisRA, LexEntry.MorphoSyntaxAnalysesOC,
  and every REAL field of the four MSA classes (MoStemMsa, MoInflAffMsa,
  MoDerivAffMsa, MoUnclassifiedAffixMsa) -- reproduced via the POS/MSA path
  (`Lib/categories.py._create_msa_for_closure` + `Lib/categories_msas.py`).

CYCLE-16 CENSUS RESOLUTION: the 11 fields the cycle-16 census run surfaced
as unclassified gaps (see `_UNCLASSIFIED_GAP_FIELDS`'s pre-cycle-16
docstring, retained below for provenance) have all been adjudicated into
terminal buckets by the lead and are now real `CLASSIFICATION` entries:

- `LexEntry.EntryRefsOS` -> DROP_REPORTED. The transfer now emits one
  `DroppedItemRecord` per un-reproduced `LexEntryRef` owned by a copied
  entry (`Lib/categories.py._report_dropped_entry_refs`, called from both
  `_walk_lex_entry_closure` (Move) and `_plan_entry_reference_decisions`
  (Preview) -- Move == Preview by construction, same function). Routed to
  027-complex-forms-variants for eventual reproduction.
- `LexEntryRef.{ComponentLexemesRS, PrimaryLexemesRS, VariantEntryTypesRS,
  ComplexEntryTypesRS, ShowComplexFormsInRS}` -> DROP_REPORTED, SUBSUMED by
  the parent `EntryRefsOS` record above -- no `LexEntryRef` is ever created,
  so these 5 fields cannot exist independently of that drop. Each points at
  the SAME emission site as `EntryRefsOS`; no double-counting.
- `LexEntry.MainEntriesOrSensesRS` -> OUT_OF_SCOPE_EXCLUDED
  (rationale-class "read-only-derived-aggregate"; see above).
- `MoAffixAllomorph.{InflectionClassesRC, MsEnvFeaturesOA,
  MsEnvPartOfSpeechRA, PositionRS}` -> DROP_REPORTED. One
  `DroppedItemRecord` per POPULATED field on a created `MoAffixAllomorph`
  (`Lib/owned.py._report_dropped_moaffix_msenv_fields`, called from both
  `reproduce_allomorph_hung_data` (Move) and
  `plan_allomorph_hung_data_decisions` (Preview) -- Move == Preview by
  construction, same function). Vacuous on Ejagham Mini (0/106 allomorphs
  populate these) but honest for other projects. Routed to
  028-affix-allomorph-morphosyntax for eventual reproduction.

Zero fields remain in `_UNCLASSIFIED_GAP_FIELDS` / xfail after this cycle.

CYCLE-17 CENSUS CORRECTION: a prior lead ruling wrongly parked 4 LexSense
fields (AppendixesRC, ThesaurusItemsRC, ExtendedNoteOS, PicturesOS) in the
SILENT `OUT_OF_SCOPE_EXCLUDED` bucket -- a bucket that, by definition, emits
no `DroppedItemRecord`. That violates SC-003/FR-010 ("NOTHING is silently
lost") and the spec.md US5 clarification ("all owned child objects in
v1"). MCP target-class truth (reflection against `SIL.LCModel.dll`)
refined which of the 4 are cleanly reproducible; the corrected terminal
buckets are:

- `LexSense.ExtendedNoteOS` -> COPIED. Owns `LexExtendedNote` (clid 5134,
  `ILexExtendedNoteFactory` -- base `Create()`/`Create(Guid)` only, no
  owner overload -- UNOWNED_THEN_ADD, `Lib/owned.py.OWNED_OBJECT_MAP`).
  Its `ExamplesOS` recurses through the SAME example-reproduction closure
  `LexSense.ExamplesOS` already uses (`_EXAMPLE_REF_SPECS`, NOT forked --
  a second `OWNED_OBJECT_MAP` row referencing the SAME child_refs/factory
  constants). Its `ExtendedNoteTypeRA` resolves against the newly-added
  `references.REFERENCE_FIELD_MAP` row -> `lp.LexDbOA.ExtendedNoteTypesOA`
  (generic `ICmPossibilityFactory`, ItemClsid 7 -- no new typed-factory
  mapping needed).
- `LexSense.AppendixesRC` -> DROP_REPORTED (was silently excluded).
  `LexAppendix` is a bespoke OWNED class in `LexDb.AppendixesOC` (NOT a
  possibility list -- confirmed via reflection: `ILexAppendix` has only
  `ContentsOA : IStText`) -- the generic resolver does not apply.
  `categories._report_dropped_sense_scope_gaps` emits one
  `DroppedItemRecord` per referenced appendix. Routed to
  030-sense-appendix-thesaurus-refs.
- `LexSense.ThesaurusItemsRC` -> DROP_REPORTED (was silently excluded).
  Generic `CmPossibility` (confirmed via reflection:
  `ILcmReferenceCollection<ICmPossibility>`) with no fixed home list
  (legacy, dynamic-owner) -- no dynamic-owner resolution attempted. Same
  emission function as AppendixesRC. Routed to
  030-sense-appendix-thesaurus-refs.
- `LexSense.PicturesOS` -> DROP_REPORTED (was silently excluded). Owns
  `CmPicture` -> `CmFile` -> disk file (confirmed via reflection:
  `ICmPicture.PictureFileRA : ICmFile`) -- never creates a `CmPicture`/
  `CmFile` or copies a file. Same emission function. Routed to
  029-sense-pictures.

`LexEntry.MainEntriesOrSensesRS` is UNCHANGED (cycle-16 ruling,
rationale-class "read-only-derived-aggregate") and is now the ONLY entry
remaining in `OUT_OF_SCOPE_EXCLUDED_FIELDS`. On Ejagham Mini all 4
corrected fields are vacuous (0 populated) -- this cycle's tests
(`tests/unit/test_cycle16c_sense_scope_gaps.py`,
`tests/unit/test_owned_object_walk.py`'s
`test_extended_note_reproduced_with_examples_and_type_resolved`) are
fakes-only; live proof deferred to the T037-class fixture posture already
accepted for lexrel/affix-MsEnv.
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

    Feature 025 (full reversals) T034 ADDITION: `kind == "MU"` denotes an
    IMultiUnicode/IMultiString VALUE field (e.g. `ReversalIndexEntry.
    ReversalForm`) -- a genuine census-worthy field this module chooses to
    track (see `ReversalIndexEntry`'s "(a)" decision below), but NOT an
    owning/reference field in the OA/OC/OS/RA/RC/RS sense. LCM's own naming
    convention gives such fields NO type suffix at all (the bare metadata
    name IS the C# property -- "ReversalForm", "Discussion"), so `prop`
    special-cases "MU" to return `name` unsuffixed rather than the nonsense
    "ReversalFormMU" the generic concatenation would otherwise produce --
    the ONLY change `FieldSpec`/`_all_real_fields` needed to carry a value
    field through the SAME never-silent machinery every owning/reference
    field already uses (no other module semantics touched).
    """

    name: str
    kind: str

    @property
    def prop(self) -> str:
        if self.kind == "MU":
            return self.name
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
    "LexExtendedNote": (
        FieldSpec("Examples", "OS"),
        FieldSpec("ExtendedNoteType", "RA"),
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
    # ---- ReversalIndexEntry (feature 025 full-reversals, T034) -------------
    # `IReversalIndexEntry`'s reference/owned fields (mirrors `Lib/reversals.
    # py.REVERSAL_FIELD_MAP` -- the SAME four rows, T008/T014). `SensesRS`/
    # `PartOfSpeechRA`/`SubentriesOS` are genuine owning/reference fields
    # (RS/RA/OS respectively). `ReversalForm` is IMultiUnicode -- a VALUE
    # field, not owning/reference -- carried here as `kind="MU"` (see
    # `FieldSpec`'s own docstring for the `prop` special-case) rather than
    # silently excluded the way 024's `LexExtendedNote.Discussion` (also an
    # IMultiString value field) is: T034 named `ReversalForm` explicitly, so
    # silently excluding it here would be a FRESH SC-003/FR-010 violation on
    # a field the task called out by name. `Discussion` itself is left
    # UNCHANGED (still excluded) -- 024 never named it as needing coverage,
    # so retrofitting it is a separate, unprompted scope change.
    "ReversalIndexEntry": (
        FieldSpec("Senses", "RS"),
        FieldSpec("PartOfSpeech", "RA"),
        FieldSpec("Subentries", "OS"),
        FieldSpec("ReversalForm", "MU"),
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
# OUT_OF_SCOPE_EXCLUDED_FIELDS -- cycle-17 correction: EXACTLY ONE field,
# `LexEntry.MainEntriesOrSensesRS` (cycle-16 ruling, rationale-class
# "read-only-derived-aggregate" -- a read-only derived aggregate
# transitively populated by the LexEntryRef mechanism, not an independent
# data-loss point). The 4 LexSense fields formerly parked here
# (AppendixesRC, ThesaurusItemsRC, ExtendedNoteOS, PicturesOS) violated
# SC-003/FR-010 (silent exclusion) -- they are now real terminal buckets
# (ExtendedNoteOS -> COPIED; the other 3 -> DROP_REPORTED). See this
# module's "CYCLE-17 CENSUS CORRECTION" docstring section.
# ----------------------------------------------------------------------------
OUT_OF_SCOPE_EXCLUDED_FIELDS: frozenset[tuple[str, str]] = frozenset({
    ("LexEntry", "MainEntriesOrSensesRS"),
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
    ("LexEntry", "EntryRefsOS"): Classification(
        Bucket.DROP_REPORTED,
        "categories._report_dropped_entry_refs (categories.py:4060), called "
        "from _walk_lex_entry_closure (Move, categories.py:4089+) and "
        "_plan_entry_reference_decisions (Preview) -- one DroppedItemRecord "
        "per un-reproduced LexEntryRef owned by the entry",
        note="cycle-16 lead adjudication: no ILexEntryRefFactory create "
             "site exists anywhere in Lib/*.py; routed to "
             "027-complex-forms-variants for eventual reproduction. "
             "Subsumes LexEntryRef.{ComponentLexemesRS, PrimaryLexemesRS, "
             "VariantEntryTypesRS, ComplexEntryTypesRS, "
             "ShowComplexFormsInRS} -- see those rows.",
    ),
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
    ("LexEntry", "MainEntriesOrSensesRS"): Classification(
        Bucket.OUT_OF_SCOPE_EXCLUDED,
        "OUT_OF_SCOPE_EXCLUDED_FIELDS (cycle-16 lead ruling)",
        note="rationale-class: read-only-derived-aggregate -- can_write="
             "false; a read-only derived aggregate transitively populated "
             "by the LexEntryRef mechanism (see LexEntry.EntryRefsOS), not "
             "an independent data-loss point. This is the ONLY "
             "OUT_OF_SCOPE_EXCLUDED entry as of cycle-17 -- the 4 LexSense "
             "fields that used to sit alongside it under a decorative "
             "'out-of-024-scope' label were a SILENT-exclusion violation "
             "(SC-003/FR-010) and are now real COPIED/DROP_REPORTED "
             "terminal buckets (see the module docstring's 'CYCLE-17 "
             "CENSUS CORRECTION' section).",
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
        Bucket.DROP_REPORTED,
        "categories._report_dropped_sense_scope_gaps (categories.py), "
        "called from _walk_lex_entry_closure's sense loop (Move) and "
        "_plan_entry_reference_decisions's sense loop (Preview) -- one "
        "DroppedItemRecord per referenced LexAppendix",
        note="cycle-17 lead correction (was wrongly OUT_OF_SCOPE_EXCLUDED, "
             "a SILENT bucket -- violated SC-003/FR-010): LexAppendix is a "
             "bespoke owned class (LexDb.AppendixesOC), not a possibility "
             "list -- the generic resolver does not apply. Routed to "
             "030-sense-appendix-thesaurus-refs for eventual reproduction.",
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
        Bucket.COPIED,
        "owned.OWNED_OBJECT_MAP[owner_class=LexSense, owning_field="
        "ExtendedNoteOS] (UNOWNED_THEN_ADD via ILexExtendedNoteFactory."
        "Create(Guid)+Add), reached via owned.walk_owned_children(...) "
        "unfiltered from categories._walk_lex_entry_closure's sense loop",
        note="cycle-17 lead correction (was wrongly OUT_OF_SCOPE_EXCLUDED, "
             "a SILENT bucket -- violated SC-003/FR-010): "
             "ILexExtendedNoteFactory has only the base Create()/"
             "Create(Guid) overloads (reflection-confirmed against "
             "SIL.LCModel.dll) -- no owner overload, matching Pronunciation/"
             "Etymology's UNOWNED_THEN_ADD shape.",
    ),
    ("LexSense", "MorphoSyntaxAnalysisRA"): Classification(
        Bucket.HANDLED_ELSEWHERE, _MSA_HANDLING_SITE,
    ),
    ("LexSense", "PicturesOS"): Classification(
        Bucket.DROP_REPORTED,
        "categories._report_dropped_sense_scope_gaps (categories.py), "
        "called from _walk_lex_entry_closure's sense loop (Move) and "
        "_plan_entry_reference_decisions's sense loop (Preview) -- one "
        "DroppedItemRecord per picture",
        note="cycle-17 lead correction (was wrongly OUT_OF_SCOPE_EXCLUDED, "
             "a SILENT bucket -- violated SC-003/FR-010): CmPicture -> "
             "CmFile -> disk file is never created/copied. Routed to "
             "029-sense-pictures for eventual reproduction.",
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
        Bucket.DROP_REPORTED,
        "categories._report_dropped_sense_scope_gaps (categories.py), "
        "called from _walk_lex_entry_closure's sense loop (Move) and "
        "_plan_entry_reference_decisions's sense loop (Preview) -- one "
        "DroppedItemRecord per referenced thesaurus item",
        note="cycle-17 lead correction (was wrongly OUT_OF_SCOPE_EXCLUDED, "
             "a SILENT bucket -- violated SC-003/FR-010): generic "
             "CmPossibility with no fixed home list (legacy, dynamic-owner) "
             "-- no dynamic-owner resolution attempted. Routed to "
             "030-sense-appendix-thesaurus-refs for eventual reproduction.",
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
    ("MoAffixAllomorph", "InflectionClassesRC"): Classification(
        Bucket.DROP_REPORTED,
        "owned._report_dropped_moaffix_msenv_fields (owned.py:1395), "
        "called from reproduce_allomorph_hung_data (Move, owned.py:1419+) "
        "and plan_allomorph_hung_data_decisions (Preview, owned.py:1563+), "
        "themselves called from categories._walk_entry_allomorphs._mk "
        "(Move) / categories._plan_entry_reference_decisions (Preview) -- "
        "one DroppedItemRecord per populated MsEnv/inflection-class/"
        "position field on a created MoAffixAllomorph",
        note="cycle-16 lead adjudication: routed to "
             "028-affix-allomorph-morphosyntax for eventual reproduction. "
             "Vacuous on Ejagham Mini (0/106 allomorphs populate this).",
    ),
    ("MoAffixAllomorph", "MsEnvFeaturesOA"): Classification(
        Bucket.DROP_REPORTED,
        "owned._report_dropped_moaffix_msenv_fields (owned.py:1395), "
        "called from reproduce_allomorph_hung_data (Move) and "
        "plan_allomorph_hung_data_decisions (Preview)",
        note="cycle-16 lead adjudication: routed to "
             "028-affix-allomorph-morphosyntax for eventual reproduction. "
             "Vacuous on Ejagham Mini (0/106 allomorphs populate this).",
    ),
    ("MoAffixAllomorph", "MsEnvPartOfSpeechRA"): Classification(
        Bucket.DROP_REPORTED,
        "owned._report_dropped_moaffix_msenv_fields (owned.py:1395), "
        "called from reproduce_allomorph_hung_data (Move) and "
        "plan_allomorph_hung_data_decisions (Preview)",
        note="cycle-16 lead adjudication: routed to "
             "028-affix-allomorph-morphosyntax for eventual reproduction. "
             "Vacuous on Ejagham Mini (0/106 allomorphs populate this).",
    ),
    ("MoAffixAllomorph", "PositionRS"): Classification(
        Bucket.DROP_REPORTED,
        "owned._report_dropped_moaffix_msenv_fields (owned.py:1395), "
        "called from reproduce_allomorph_hung_data (Move) and "
        "plan_allomorph_hung_data_decisions (Preview)",
        note="cycle-16 lead adjudication: routed to "
             "028-affix-allomorph-morphosyntax for eventual reproduction. "
             "Vacuous on Ejagham Mini (0/106 allomorphs populate this).",
    ),

    # ---- LexEntryRef (SUBSUMED by parent LexEntry.EntryRefsOS drop) -------
    ("LexEntryRef", "ComponentLexemesRS"): Classification(
        Bucket.DROP_REPORTED,
        "SAME emission site as LexEntry.EntryRefsOS: "
        "categories._report_dropped_entry_refs (categories.py:4060)",
        note="subsumed by parent EntryRefsOS drop record -- no LexEntryRef "
             "is ever created, so this field cannot exist independently of "
             "that drop; no separate DroppedItemRecord is emitted for it.",
    ),
    ("LexEntryRef", "PrimaryLexemesRS"): Classification(
        Bucket.DROP_REPORTED,
        "SAME emission site as LexEntry.EntryRefsOS: "
        "categories._report_dropped_entry_refs (categories.py:4060)",
        note="subsumed by parent EntryRefsOS drop record -- no LexEntryRef "
             "is ever created, so this field cannot exist independently of "
             "that drop; no separate DroppedItemRecord is emitted for it.",
    ),
    ("LexEntryRef", "VariantEntryTypesRS"): Classification(
        Bucket.DROP_REPORTED,
        "SAME emission site as LexEntry.EntryRefsOS: "
        "categories._report_dropped_entry_refs (categories.py:4060)",
        note="subsumed by parent EntryRefsOS drop record -- no LexEntryRef "
             "is ever created, so this field cannot exist independently of "
             "that drop; no separate DroppedItemRecord is emitted for it.",
    ),
    ("LexEntryRef", "ComplexEntryTypesRS"): Classification(
        Bucket.DROP_REPORTED,
        "SAME emission site as LexEntry.EntryRefsOS: "
        "categories._report_dropped_entry_refs (categories.py:4060)",
        note="subsumed by parent EntryRefsOS drop record -- no LexEntryRef "
             "is ever created, so this field cannot exist independently of "
             "that drop; no separate DroppedItemRecord is emitted for it.",
    ),
    ("LexEntryRef", "ShowComplexFormsInRS"): Classification(
        Bucket.DROP_REPORTED,
        "SAME emission site as LexEntry.EntryRefsOS: "
        "categories._report_dropped_entry_refs (categories.py:4060)",
        note="subsumed by parent EntryRefsOS drop record -- no LexEntryRef "
             "is ever created, so this field cannot exist independently of "
             "that drop; no separate DroppedItemRecord is emitted for it.",
    ),

    # ---- LexReference ------------------------------------------------------
    ("LexReference", "TargetsRS"): Classification(
        Bucket.COPIED,
        "categories.reproduce_all_lexical_relations / "
        "categories._reproduce_one_lex_relation (rebuilds new_rel.TargetsRS "
        "in source order, copied members only)",
    ),

    # ---- LexExtendedNote (cycle-17 correction) -----------------------------
    ("LexExtendedNote", "ExamplesOS"): Classification(
        Bucket.COPIED,
        "owned.OWNED_OBJECT_MAP[owner_class=LexExtendedNote, owning_field="
        "ExamplesOS] -- SAME `_EXAMPLE_REF_SPECS`/`ILexExampleSentenceFactory` "
        "table LexSense.ExamplesOS uses (not forked), reached via "
        "owned.walk_owned_children's unconditional re-walk of a newly-"
        "created LexExtendedNote's own owned collections",
        note="ILexExampleSentenceFactory has no (Guid, ILexExtendedNote) "
             "owner overload (reflection-confirmed) -- this row uses "
             "UNOWNED_THEN_ADD (the factory's base Create(Guid) overload) "
             "rather than the LexSense.ExamplesOS row's OWNER_TAKING "
             "Create(Guid, owner) overload.",
    ),
    ("LexExtendedNote", "ExtendedNoteTypeRA"): Classification(
        Bucket.COPIED,
        "references.REFERENCE_FIELD_MAP[owner_class=LexExtendedNote, "
        "field_name=ExtendedNoteTypeRA] -> lp.LexDbOA.ExtendedNoteTypesOA "
        "(generic ICmPossibilityFactory, ItemClsid 7), dispatched via "
        "owned._apply_child_refs as ExtendedNoteOS's own child_refs",
    ),

    # ---- ReversalIndexEntry (feature 025 full-reversals, T034) -------------
    ("ReversalIndexEntry", "SensesRS"): Classification(
        Bucket.COPIED,
        "reversals._resolve_sense_links (reversals.py), called from "
        "reversals._build_entry_decision -- re-wires SensesRS to the "
        "copied-sense set only; every non-copied member is DROP_REPORTED "
        "individually (owner_kind 'ReversalIndexEntry', field_name "
        "'SensesRS', reason 'member not in copy set')",
        note="US1 T014 (feature 025-full-reversals, R3/024 FR-008 partial-"
             "member policy): the FIELD itself is COPIED (re-wired to "
             "whatever subset was actually copied); only individual omitted "
             "MEMBERS are DROP_REPORTED -- same posture as 024's COLLECTION/"
             "SEQUENCE lexical-relation kinds (LexReference.TargetsRS).",
    ),
    ("ReversalIndexEntry", "PartOfSpeechRA"): Classification(
        Bucket.COPIED,
        "reversals._decide_reversal_category (US2 T025), applied by "
        "reversals._apply_pos_decision (T026) -- routes through the SAME "
        "024 three-way resolver (references.decide_reference/"
        "apply_reference) against the TARGET REVERSAL INDEX's OWN "
        "PartsOfSpeechOA (never LangProject.PartsOfSpeechOA, per R5)",
        note="REPORT_DROPPED sub-cases (to-create index / list absent -- "
             "reason 'target reversal category list absent'; shared-default "
             "divergence -- resolver's own REPORT_DROPPED arm) each emit a "
             "DroppedItemRecord (owner_kind 'ReversalIndexEntry', field_name "
             "'PartOfSpeechRA') the same way every other referenced-"
             "possibility field in this codebase does.",
    ),
    ("ReversalIndexEntry", "SubentriesOS"): Classification(
        Bucket.COPIED,
        "reversals._build_entry_decision's unconditional SubentriesOS "
        "recursion (US1 T014, applied by reversals._apply_one_entry's own "
        "recursion, T016/T027 sub-entry create path) -- mirrors "
        "owned.walk_owned_children's recursive owned-child pattern; every "
        "sub-entry gets its own ReversalDecision (and target sub-entry) at "
        "every depth, never truncated.",
    ),
    ("ReversalIndexEntry", "ReversalForm"): Classification(
        Bucket.COPIED,
        "reversals._reversal_form_alts (US1 T014, plan-time snapshot) + "
        "reversals._set_reversal_form_alt (T016, apply-time per-WS write) "
        "-- non-destructive alt copy (R6/024 FR-007): an empty/absent "
        "source alt is never a key in reversal_form_alts, so a later write "
        "pass can never blank an existing populated target alt for that WS",
        note="(a)/(b) DECISION (T034, documented per task instruction): "
             "ReversalForm is IMultiUnicode -- a VALUE field, not an owning/"
             "reference field -- so it does not naturally fit this module's "
             "OA/OC/OS/RA/RC/RS-suffix FieldSpec shape, and 024's own "
             "precedent (LexExtendedNote.Discussion, also IMultiString) is "
             "to EXCLUDE such fields from EXPECTED_MODEL_FIELDS entirely. "
             "Chose (a) -- a new FieldSpec kind ('MU', see FieldSpec's own "
             "docstring for the minimal `prop` special-case this required) "
             "carrying a real COPIED CLASSIFICATION entry pointing at the "
             "non-destructive alt-copy site above -- over (b) mirroring "
             "Discussion's silent exclusion, because T034's own task text "
             "explicitly named ReversalForm as a field requiring a "
             "'defensible, DOCUMENTED choice': silently excluding a field "
             "the task called out by name would itself be a fresh SC-003/"
             "FR-010 violation, the exact defect cycle-17 corrected for the "
             "4 LexSense fields above. Discussion is deliberately left "
             "UNCHANGED (still excluded) -- retrofitting it now would be an "
             "unprompted scope change; only ReversalForm was named.",
    ),
}


# ============================================================================
# Gap surfacing -- SC-004 never-silent guard
# ============================================================================
#
# Cycle-16 RESOLUTION: the 11 fields formerly listed here as unclassified
# gaps (LexEntry.EntryRefsOS; LexEntry.MainEntriesOrSensesRS;
# MoAffixAllomorph.{InflectionClassesRC, MsEnvFeaturesOA,
# MsEnvPartOfSpeechRA, PositionRS}; LexEntryRef.{ComplexEntryTypesRS,
# ComponentLexemesRS, PrimaryLexemesRS, ShowComplexFormsInRS,
# VariantEntryTypesRS}) have ALL been adjudicated into terminal buckets
# (see the module docstring's "CYCLE-16 CENSUS RESOLUTION" section and the
# `CLASSIFICATION` entries above) -- this tuple is now empty, and
# `test_known_gaps_need_lead_adjudication` (the xfail(strict) test that
# used to document them) has been removed accordingly. The never-silent
# guard itself (`classify_field` raising `LookupError` for anything with no
# bucket) remains fully intact and is regression-tested by
# `test_guard_fires_for_unclassified_property` below.
_UNCLASSIFIED_GAP_FIELDS: tuple[tuple[str, str], ...] = ()


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
        "FAIL requiring lead adjudication -- add a CLASSIFICATION entry (or "
        "a documented exclusion/handoff) for this field."
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


def test_no_unclassified_gap_fields_remain() -> None:
    """Cycle-16 closure: `_UNCLASSIFIED_GAP_FIELDS` must be empty -- every
    field the census surfaced as a gap has been adjudicated into a terminal
    bucket with a real `CLASSIFICATION` entry (or added to one of the two
    frozenset ledgers). If a future model change reintroduces a gap, THIS
    test (not an xfail) is what will start failing, naming the size of the
    reintroduced gap set."""
    assert _UNCLASSIFIED_GAP_FIELDS == ()


def test_out_of_scope_excluded_list_is_exact() -> None:
    """Cycle-17 correction (SC-003/FR-010, never-silent): nobody can quietly
    park an in-scope field on the exclusion list, and the list can't
    silently shrink either -- EXACTLY ONE field remains,
    `LexEntry.MainEntriesOrSensesRS` (cycle-16 ruling). The 4 LexSense
    fields formerly parked here (a SILENT bucket -- violated SC-003/FR-010)
    are now real terminal buckets: `ExtendedNoteOS` -> COPIED;
    `AppendixesRC`/`ThesaurusItemsRC`/`PicturesOS` -> DROP_REPORTED."""
    assert OUT_OF_SCOPE_EXCLUDED_FIELDS == frozenset({
        ("LexEntry", "MainEntriesOrSensesRS"),
    })
    for class_name, prop in OUT_OF_SCOPE_EXCLUDED_FIELDS:
        classification = classify_field(class_name, prop)
        assert classification.bucket == Bucket.OUT_OF_SCOPE_EXCLUDED
        assert classification.note, (
            f"{class_name}.{prop}: OUT_OF_SCOPE_EXCLUDED entries must carry "
            "a rationale string"
        )


def test_out_of_scope_excluded_rationale_class_is_read_only_derived_aggregate() -> None:
    """`LexEntry.MainEntriesOrSensesRS` must carry the
    "read-only-derived-aggregate" rationale-class (cycle-16 ruling) --
    cycle-17 renamed this test (was `..._are_distinct`, comparing it against
    the 4 now-removed LexSense exclusions) since it is now the ONLY
    OUT_OF_SCOPE_EXCLUDED entry -- nothing left to be "distinct" from."""
    lex_entry_note = classify_field("LexEntry", "MainEntriesOrSensesRS").note
    assert "rationale-class: read-only-derived-aggregate" in lex_entry_note


def test_no_field_carries_out_of_024_scope_rationale_class() -> None:
    """Cycle-17 regression guard: the "out-of-024-scope" rationale-class
    (the SILENT-exclusion label the 4 corrected LexSense fields used to
    carry) must not appear anywhere in `CLASSIFICATION` any more -- SC-003/
    FR-010 forbids silent exclusion, and this rationale-class was exactly
    that pattern."""
    for (class_name, prop), classification in CLASSIFICATION.items():
        assert "rationale-class: out-of-024-scope" not in classification.note, (
            f"{class_name}.{prop} still carries the retired silent "
            "'out-of-024-scope' rationale-class"
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
    """Sanity check on the captured inventory itself: 79 REAL fields total
    across the 12 classes (11+15+2+3+6+5+1+9+7+13+3+4), matching the injected
    flextoolsMCP-verified/reflection-confirmed snapshot exactly -- guards
    against an accidental edit silently dropping or duplicating a row in
    `EXPECTED_MODEL_FIELDS`. Cycle-17: added `LexExtendedNote` (2 REAL
    fields -- ExamplesOS, ExtendedNoteTypeRA; `Discussion` is a multistring,
    not owning/reference) as a newly-covered class. Feature 025 (full
    reversals) T034: added `ReversalIndexEntry` (4 REAL fields -- SensesRS,
    PartOfSpeechRA, SubentriesOS, and `ReversalForm` -- the last is ALSO a
    multistring/IMultiUnicode field like `Discussion`, but is deliberately
    COVERED here (kind="MU", a real COPIED classification) rather than
    excluded, per the (a)/(b) decision documented on its own CLASSIFICATION
    entry above -- `Discussion` itself remains excluded, unchanged)."""
    counts = {name: len(fields) for name, fields in EXPECTED_MODEL_FIELDS.items()}
    assert counts == {
        "LexEntry": 11,
        "LexSense": 15,
        "LexExtendedNote": 2,
        "MoStemAllomorph": 3,
        "MoAffixAllomorph": 6,
        "LexEntryRef": 5,
        "LexReference": 1,
        "MoStemMsa": 9,
        "MoInflAffMsa": 7,
        "MoDerivAffMsa": 13,
        "MoUnclassifiedAffixMsa": 3,
        "ReversalIndexEntry": 4,
    }
    assert sum(counts.values()) == 79
