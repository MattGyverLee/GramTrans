# Cycle 1 -- Domain Expert Rulings: fullsweep fidelity classification

**Date:** 2026-08-17
**Feature:** 035-fullsweep-fidelity
**Scope:** rulings only -- no code, no writes to any FLEx project.

> Provenance note: authored by the lex-domain agent, which has no Write tool in
> its definition; the main session persisted this content verbatim from the
> agent's report. Section cross-references written "SS<n>" mean section <n>.

## 1. EXPECTED_DIVERGENT roster

1. `Hvo` MUST be excluded from comparison entirely (it is the join-scope key
   candidate's runtime session id, not persisted data; already excluded from
   the interactive diff pane at `merge_preview.py:_EXCLUDED_KEYS_EXACT`).
2. `DateCreated` MUST always differ and MUST NOT be diffed. LCM stamps it at
   target-side factory `Create()` time; GramTrans has no provenance-preserving
   write path for it and none is wanted -- the tool's own provenance record is
   the `ImportResidueTag` (residue.py), not a forged `DateCreated`.
3. `DateModified` (and any key containing `DateModified`) MUST always differ
   and MUST NOT be diffed. LCM rewrites it on every save; already excluded
   in `merge_preview.py`.
4. `DateResolved` MUST be treated by the same rule as `DateModified` if any
   future in-scope class exposes it: it is not present on any class any
   GrammarCategory currently transfers (confirmed by full-repo grep of
   GramTrans and flexicon), so this is a forward guard, not an active check.
5. `Hvo`/`Guid`-suffixed handle fields (`*Guid`, `*Guids`) other than the
   object's own primary Guid MUST NOT be diffed as data; they are internal
   reference-lookup keys, already excluded via the `*Guid`/`*Guids` suffix
   pattern in `merge_preview.py`.
6. `OwnOrd` MUST NOT be diffed as a raw integer. It is LCM's own owning-
   sequence position bookkeeping; faithfulness of order is expressed by
   comparing the SEQUENCE (see SS4), not this per-item scalar.
7. The raw `OwningFlid` integer MUST NOT be diffed (it is a schema field-id,
   liable to differ across LCM builds with zero semantic content); the
   OWNER OBJECT identity (SS5) is what must be faithful, and for any object
   GramTrans preserves GUIDs for, the owner's GUID MUST match (033
   invariant) -- so a genuine owner mismatch there IS a DISTORTION, just not
   via the `OwningFlid` int.
8. `LexEntry.HomographNumber` MUST always be allowed to differ and MUST NOT
   be diffed. It is recomputed from the TARGET lexicon's own homograph
   siblings at write time, not copied user data (already excluded in
   `merge_preview.py` with this exact rationale).
9. `ImportResidue` MUST NOT be diffed as data on any class. It is a raw
   pre-existing LIFT-import artifact string, already excluded in
   `merge_preview.py`; separately, GramTrans's own `LiftResidue` (Carrier A,
   `residue.py`) and `Description`-append (Carrier B) fields are DELIBERATELY
   mutated by every run (the GT-tag is appended). The comparator MUST strip
   the trailing `[GT-Tag]: GT|...` line (per `ImportResidueTag.parse`)
   before comparing `Description`/`LiftResidue` prose, and MUST NOT report
   the appended tag segment itself as a mismatch on either carrier.
10. Any field literally named `Checksum`/`Hash`/`CRC` (none currently exposed
    on a transferred class -- confirmed by grep of flexicon) MUST be treated
    as EXPECTED_DIVERGENT if ever encountered: such values are recomputed by
    the target LCM instance, never copied.
11. A boolean/flag field MUST be judged EXPECTED_DIVERGENT only if flexicon's
    `GetSyncableProperties()` for that class OMITS it by design; if flexicon
    syncs it (most `Is*`/`DoNotPublishInRC`/`ExcludeAsHeadword`-style flags
    ARE persisted user data), it MUST be treated as ordinary content subject
    to DISTORTED/LOST, not waved through as "probably derived." No blanket
    `Is*`-name heuristic is permitted.
12. Any field a FLEx save-side handler recomputes and that flexicon's own
    `GetSyncableProperties` deliberately omits (the constitution names
    flexicon's Operations surface as canonical, Principle II) MUST be
    EXPECTED_DIVERGENT; the comparator's roster of such fields is exactly
    this document plus whatever `GetSyncableProperties` omits per class --
    it MUST NOT be derived by re-scraping `merge_preview.py`'s
    `_EXCLUDED_KEYS_EXACT`, because that set conflates UI-legibility
    exclusions with true fidelity exclusions (see SS3 ranking item 6 on
    `Direction`, which is excluded from the merge-preview UI but MUST still
    be fidelity-checked).
13. The internal numeric WS `Handle` (as opposed to the WS `Id`/langtag) MUST
    NOT be diffed; handles are per-project-session integers assigned by LCM
    at open time and are never stable across two different projects even for
    "the same" writing system.

## 2. WS-mapped legitimacy

1. For an `IMultiString`/`IMultiUnicode` field, faithful MUST mean: for every
   source WS alternative that has a `WSMappingEntry`, the alternative's text
   appears byte-identical under the entry's `target_ws_id` in the target
   object. This mirrors the already-implemented rule at
   `categories._copy_multistrings_ws_mapped` (`tgt_id = ws_map.get(src_id,
   src_id)`, then a target-handle lookup) and is the correct rule because a
   FLEx user thinks in terms of "my French gloss went to French," not raw WS
   handles.
2. A source WS alternative with NO `WSMappingEntry` at all MUST be classified
   EXPECTED_DIVERGENT/out-of-scope, NEVER LOST, PROVIDED the run's own
   plan/report carries an accounting artifact for it (a `Skip(UNMAPPED_WS)`
   or equivalent, per the existing `SkipReason.UNMAPPED_WS` enum member).
   If no such accounting artifact exists for an unmapped WS's content, that
   is a PROCESS DEFECT in the fullsweep's own `WSMapping` construction, not
   a per-object fidelity failure, and the comparator MUST report it as
   "unmapped WS with no skip record" so it is never silently absorbed into
   either LOST or EXPECTED_DIVERGENT.
3. `full_run.py`'s `run_full_transfer` currently constructs a `WSMapping`
   covering ONLY the default vernacular (its own docstring: "Not
   customizable: the coverage/full-run harness always uses the default
   vernacular on both sides"). The fullsweep MUST NOT inherit this
   narrowing unmodified: per SS2's rule, every additional vernacular and
   every analysis WS present in a source project that has NO mapping entry
   is entirely out of the diff's reach, which contradicts "I want to know
   whether all of the things that hang off of the things we copied are
   faithful." The fullsweep's `WSMapping` builder MUST enumerate every
   distinct source WS (vernacular and analysis) and either map it by
   langtag identity to an existing target WS of the same langtag, or set
   `create_in_target=True`, before computing the preview.
4. A target WS lookup that resolves to `None` for a MAPPED source WS
   (`tgt_handle_by_id.get(tgt_id)` returning nothing) MUST be classified
   LOST, not EXPECTED_DIVERGENT, because the entry declared an intent to
   carry that WS's content across and the intent was not honored.

## 3. Distortion classes, ranked (most to least user-consequential)

1. **Whitespace strip inside string content -- DISTORTED.** Proven, not
   theoretical: `specs/033-guid-preservation/TODO.md` documents a real bug
   (`ParagraphOperations.Create` stripping `'ka '` to `'ka'`), now fixed
   upstream (flexicon #242). Trailing/leading whitespace in vernacular text
   can be phonologically/orthographically significant; never benign.
2. **Case folding -- DISTORTED, always.** Casing distinguishes lexical
   identity (proper nouns, citation-form conventions) in most orthographies
   GramTrans's users work in; no exception.
3. **Run-level style/WS loss inside a formatted `ITsString` -- DISTORTED.**
   A multi-run string (e.g. an embedded citation in a different WS, or a
   bolded note) that collapses to matching plain text but loses run
   boundaries/per-run WS/character style IS a real loss to a FLEx user who
   deliberately used per-run formatting. The comparator MUST compare run
   structure (WS-per-run, style-per-run), not just `.Text`, or it will
   false-pass this class.
4. **Unicode normalization (NFC vs NFD) -- DISTORTED, but bucketed
   separately.** A byte-level normalization difference MUST be flagged, not
   silently equated, because some of GramTrans's target orthographies
   (decomposed diacritic sequences, as in the Ejagham-family data this repo
   works with) are normalization-sensitive at the font/rendering layer, so
   "the codepoints differ but mean the same thing" is not a safe assumption
   the comparator is entitled to make on GramTrans's behalf. It MUST,
   however, be tagged as its own DISTORTED subtype (e.g.
   `NORMALIZATION_DIFF`) distinct from generic content mismatches, so a
   human reviewing the fullsweep report can triage a large, probably-benign
   cluster of these separately from genuine content bugs.
5. **`GenDate` precision loss -- DISTORTED when it occurs.** Precision (exact
   vs. approximate vs. before/after a year) is itself asserted data, not
   formatting; collapsing "circa 1950" to "1950" is a different claim.
   Currently unreachable: no `GrammarCategory` GramTrans transfers touches a
   `GenDate`-typed property (confirmed by repo-wide grep for `GenDate` in
   both GramTrans and flexicon -- only `flexicon`'s `Notebook`
   Person/Location operations and `CustomFieldOperations`'s
   `PropType_GenDate` constant reference it, and Notebook/People is not a
   GramTrans `GrammarCategory`). Rule stands as a forward guard.
6. **Enum/int semantics -- DISTORTED if the DECODED values differ, benign
   only for pure internal plumbing ints.** `MorphType` itself is not a raw
   int in this schema; it is `MorphTypeRA`, a reference to `IMoMorphType`,
   resolved per SS5 below. A genuinely raw enum int the fullsweep WILL
   encounter is `PhonologicalRule.Direction` (0/1/2). `merge_preview.py`
   excludes `Direction` from the interactive diff pane because it has "no
   user-meaningful label in the diff pane" for a human editing one entry --
   that is a UI-legibility call, NOT a fidelity ruling. `Direction`
   encodes real phonological content (left-to-right vs right-to-left vs
   simultaneous rule application) that a linguist absolutely cares about if
   scrambled in transfer, so the fullsweep comparator MUST diff it (by
   decoding both sides to the same enum, not comparing raw ints blindly,
   defensively against any cross-version ordinal drift) rather than
   silently reusing `merge_preview._EXCLUDED_KEYS_EXACT`.

## 4. Children (owned collections/sequences) semantics

1. Order MUST be part of faithfulness for every owned/reference field whose
   LCM accessor name ends in `OS` or `RS` -- the suffix itself IS FLEx's own
   promise of ordering (Owned/Reference Sequence vs Collection), and
   GramTrans's own model already encodes this distinction explicitly via
   `ReferenceCardinality.SEQUENCE` (ordered) vs `.COLLECTION` (unordered) in
   `models.py`. The comparator SHOULD derive order-significance from this
   suffix/enum rather than re-deriving it per class.
2. Order MUST NOT be asserted for any field ending in `OC` or `RC` -- FLEx
   itself gives no ordering guarantee there, so a positional mismatch on
   such a field is benign, not DISTORTED; only set-membership (what's
   present) matters.
3. Named exception FLEx users must know about: `WfiWordform.AnalysesOC` is a
   Collection (confirmed present as `AnalysesOC` in flexicon's
   `WordformOperations.py`), by design -- competing human analyses of one
   wordform have no author-assigned order, so re-ordering them on transfer
   is expected and benign.
4. Confirmed order-critical `OS` fields users will notice if scrambled:
   `LexEntry.SensesOS` (dictionary sense numbering), `WfiAnalysis
   .MorphBundlesOS` (left-to-right morpheme parse), `StTxtPara.SegmentsOS`
   (reading order), `LexEntry.AlternateFormsOS`.
5. Confirmed order-critical `RS` fields, per the user's own belief -- both
   CONFIRMED correct: `MoInflAffixTemplate.PrefixSlotsRS` /
   `SuffixSlotsRS` (affix template slot order defines legal affix ordering,
   confirmed present in flexicon's `affix_template.py`) and
   `LexEntryRef.ComponentLexemesRS` (complex-form component order,
   confirmed present in flexicon's `VariantOperations.py`, which also
   copies the sibling `PrimaryLexemesRS` -- order there selects which
   component displays as the complex form's "head," equally order-critical).
6. `LexDb`-level iteration order across unrelated top-level `LexEntry`
   objects (as opposed to order WITHIN one entry's owned children) MUST NOT
   be asserted, because FLEx exposes entries via a virtual/backreference
   surface with no author-assigned cross-entry order.

## 5. Links semantics (RA/RC/RS)

1. RESOLVED MUST mean: dereferencing the target field yields an object whose
   GUID equals the source referent's GUID (whether that target object was
   created THIS run, or already existed in a fresh Target from FLEx's own
   project-creation template -- see item 4). The comparator MUST perform
   this check by live GUID comparison, not by assuming the referent must be
   something the current run's plan created.
2. DANGLING MUST mean: the target field is non-null but resolves to an
   object whose GUID does NOT match the source referent under RESOLVED or
   RESOLVED-BY-EQUIVALENCE (item 4/5) -- this is always a hard failure,
   never benign, per constitution Principle I's cross-reference clause
   ("MUST resolve to real objects in the target after transfer, or...MUST
   fail loudly rather than silently drop the reference").
3. SILENTLY_UNSET MUST mean: the target field is null/empty, the source
   field had a referent, AND there is no `DroppedItemRecord`/`Skip` entry
   for that `(owner_guid, field_name, item_guid)` triple in the run's
   report. This is worse than ordinary LOST -- it is itself a Principle I
   "never silent" violation and MUST be flagged with higher severity than
   an accounted-for gap. A null/empty target field THAT DOES carry a
   matching `DroppedItemRecord`/`Skip` MUST be classified as a distinct,
   milder verdict -- LOST-BUT-ACCOUNTED -- not SILENTLY_UNSET and not a
   clean pass.
4. Legitimate re-pointing to a DIFFERENT (non-freshly-copied) target object
   EXISTS for GUID-bearing catalog/seed possibilities (e.g. `MorphTypeRA`
   onto the standard "stem"/"prefix"/"suffix" entries, or GOLD POS
   concepts): a fresh FLEx project template ships these with FIXED,
   well-known GUIDs, so the "pre-existing" target entry's GUID is the SAME
   GUID as the source's, not merely equivalent -- this collapses to
   ordinary RESOLVED (item 1) and needs no special verdict. This is also
   the ontology-GUID case constitution Principle I singles out ("closest-
   concept mapping... the mapping remains valid after transfer").
5. Genuine RESOLVED-BY-EQUIVALENCE (a THIRD verdict, distinct from
   RESOLVED) is required for exactly one class of object today: custom
   field DEFINITIONS, which have no LCM Guid at all. GramTrans's own
   dedup already defines the equivalence precisely --
   `(owner_class, field_name)` tuple identity via flexicon's `FindField`,
   recorded as `SkipReason.ALREADY_PRESENT_BY_IDENTITY` in `categories.py`.
   The fullsweep comparator MUST use exactly this same
   `(owner_class, name)` equivalence for custom-field-definition links, and
   MUST NOT fall back to bare display-name matching for any GUID-bearing
   class -- if RESOLVED-BY-EQUIVALENCE ever fires for a class that
   normally carries a GUID, the comparator MUST treat that as a bug signal
   (loud log entry), because it would mean a 033 GUID-preservation
   regression is being silently papered over by a fuzzy match.

## 6. STEMS ruling

1. The fullsweep MUST enable `GrammarCategory.STEMS` for at least one full
   pass; `build_full_selection()`'s default exclusion in
   `tests/integration/harness/full_run.py` MUST NOT be inherited unexamined,
   because it exists to serve a DIFFERENT harness's narrower goal
   (persistence/idempotency proof), not because STEMS transfer is known
   unsafe.
2. Nothing is KNOWN to break by enabling STEMS. `specs/033-guid-
   preservation/TODO.md`'s own OPEN ITEMS list `MoStemAllomorph` as
   "untested... routes through the same `_mk` helper that was fixed, so it
   *should* inherit the fix -- unproven" -- i.e. expected-to-work but never
   exercised live. The fullsweep is precisely the vehicle that should close
   this known gap, matching the user's stated goal ("EVERY project," "all
   of the things that hang off").
3. The one real cost of enabling STEMS is volume/runtime, not correctness
   risk: stem allomorphs are typically the largest per-project population
   GramTrans creates (TODO.md shows sibling categories already in the
   hundreds per project), so a fullsweep with STEMS on will run
   materially longer and emit materially more log/report volume per
   project -- call this out as a scheduling cost in the fullsweep spec, not
   a safety caveat.
4. IF a first smoke pass keeps STEMS off to time-box initial validation, the
   coverage reduction MUST be reported as an explicit, machine-checkable
   field on the run's own report/plan artifact (e.g. a
   `coverage_excluded_categories` list), NOT merely a Python default-
   parameter invisible to any consumer -- exactly the gap
   `build_full_selection()`'s current signature has today. A reader of the
   fidelity report MUST NOT be able to mistake "0 STEMS mismatches" for
   "STEMS passed"; the report must say STEMS was never attempted.

---
**Reviewed By:** Domain Expert Agent
**Domain:** FieldWorks Language Explorer / LCM transfer fidelity
