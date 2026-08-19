# Data Model: Transfer Fidelity Gaps (038)

New types are pure-Python `frozen=True` dataclasses/enums in
`src/gramtrans/Lib/models.py`, no LCM import (Principle II), populated by
`src/gramtrans/Lib/preview.py:114` and only *read* by
`src/gramtrans/Lib/transfer.py:157` (Principle III).

## 1. Existing types this feature EXTENDS

038 adds no parallel identity, plan, or report mechanism.

| Type | Location | 038 extension | FR/SC |
|---|---|---|---|
| `PlannedAction` | `Lib/models.py:609` | `match_basis: MatchBasisRecord \| None = None` (None => brand-new ADD) | FR-006 |
| `PlannedOverwrite` | `Lib/models.py:666` | `match_via` gains `"natural_key"`; adds `match_basis` and `enrichment: EnrichmentRecord \| None` | FR-001, FR-002, FR-020, FR-022 |
| `Skip` | `Lib/models.py:704` | shape unchanged; new reasons only | FR-013, FR-025 |
| `SkipReason` | `Lib/models.py:208` | adds `NOT_REPRODUCIBLE`, `DEPENDENCY_DESELECTED`; `ALREADY_PRESENT_BY_GUID` narrows to post-field-identity-comparison only (defect G3) | FR-017, FR-020, FR-025 |
| `RunPlan` | `Lib/models.py:716` | adds `closure_edges`, `incompleteness`, `enrichments`, `process_rules`, all `tuple = ()` so existing snapshots stay valid | FR-014..FR-019, FR-023 |
| `CategoryReport` | `Lib/models.py:1382` | adds `identity_substitution`, `enriched`, `not_reproducible` (`int = 0`); existing `closure_pulled_in` is now actually fed | FR-006, FR-022, SC-005 |
| `RunReport` | `Lib/models.py` (after `:1382`) | adds the four `RunPlan` tuples plus `census: FidelityCensus \| None` | FR-009..FR-013 |
| `DroppedItemRecord` | `Lib/models.py:1023` | new `owner_kind` values `MoAffixProcess`, `MoInflAffixSlot`, `MoInflAffixTemplate` (free-form by contract) | FR-013, SC-010 |
| `FidelityStatus` | `Lib/models.py:1003` | reused for enriched objects: `FULL` when every source child arrived, else `PARTIAL` | SC-007 |
| `OwnedObjectSpec` | `Lib/models.py:1345` | reused to describe the seven POS owned collections | FR-020 |
| `ReferenceFieldSpec` | `Lib/models.py:1081` | reused for process-rule phoneme / natural-class references | FR-024 |
| `closure.walk` / `topological` | `Lib/closure.py` | algorithm unchanged; `(visit_order, pulled_in_by)` materialised as `ClosureEdge` and consumed by `build_run_plan`. Its only importer today is its unit test (defect G2) | FR-014, FR-015 |
| Roster JSON | `specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json` | 6 entries appended in place; owned by 035, coordinated not forked | FR-003..FR-005 |

## 2. MatchBasis / MatchBasisRecord (new)

`MatchBasis` enum: `IDENTITY` (GUID or existing `identity_remap`; always tried
first), `NATURAL_KEY` (roster-admitted key, only after identity finds nothing),
`NONE` (no match; create or report).

`MatchBasisRecord` is the per-item accounting unit carried on `PlannedAction` /
`PlannedOverwrite`, aggregated into the report.

| Field | Type | Opt | Notes |
|---|---|---|---|
| `basis` | `MatchBasis` | no | |
| `object_class` | `str` | no | LCM class; must be a roster entry when `NATURAL_KEY` |
| `key_expression` | `str` | yes `""` | roster `natural_key` text; empty for `IDENTITY` |
| `key_value` | `str` | yes `""` | the key that matched, e.g. a phoneme name |
| `source_guid` | `str` | no | |
| `target_guid` | `str` | yes `""` | empty iff `basis is NONE` |
| `candidate_count` | `int` | no | destination candidates the key hit |

Invariants: identity is authoritative, natural key is the fallback and never the
reverse (FR-001; roster `governs` FR-186). A `NATURAL_KEY` record for a class not
on the roster is a harness error naming the class (roster `enforcement`).
`candidate_count > 1` with `key_unique_by_construction=false` is a harness error,
never a pick (FR-004, Edge Cases). Every `NATURAL_KEY` record increments
`CategoryReport.identity_substitution` - the roster's existing
IDENTITY-SUBSTITUTION bucket (FR-187) - so the report distinguishes it from an
identity match (FR-006).

## 3. NaturalKeyRosterEntry (new)

Read-only projection of one roster `entries[]` object, so code validates against
the file, not a second hand-written list (FR-003).

| Field | Type | Opt | Notes |
|---|---|---|---|
| `object_class` | `str` | no | JSON `class` |
| `natural_key` | `str` | no | |
| `key_unique_by_construction` | `bool` | no | false => ambiguity is an error |
| `on_ambiguous_key` | `str` | no | currently always `harness_error` |
| `reason` | `str` | no | admission evidence (FR-004) |
| `key_scoping_note` | `str \| None` | yes | e.g. default-vernacular-WS-only |
| `uniqueness_caveat` | `str \| None` | yes | |
| `live_confirmation` | `dict \| None` | yes | read-only FLExToolsMCP verdict + per-op ids; same standard as the 3 existing entries |
| `key_fn_id` | `str` | no | **038 adds**: names the pure key-extraction function, making the row executable |
| `scope_fn_id` | `str \| None` | yes | **038 adds**: names the destination candidate scope, so a list-scoped key is never matched project-wide |

038 admits `PhPhoneme`, `PhNCSegments`, `PhNCFeatures`, `PartOfSpeech`,
`MoMorphType`, `LexEntryInflType`; FR-005 mandates at least phonemes, natural
classes, parts of speech, morph types. Writing systems stay
`deliberately_excluded`.

## 4. StarterBaseline (new)

The blank-new-FLEx-project inventory subtracted by FR-010.

| Field | Type | Opt | Notes |
|---|---|---|---|
| `schema_version` | `int` | no | |
| `flex_version` | `str` | no | FieldWorks version the blank project came from |
| `captured_at` | `str` | no | ISO timestamp |
| `captured_from` | `str` | no | the throwaway blank project |
| `entries` | `tuple[StarterBaselineEntry, ...]` | no | |
| `content_hash` | `str` | no | hash over sorted entries; the staleness detector |

`StarterBaselineEntry`: `object_class: str`, `count: int`,
`names: tuple[str, ...]` (optional, only where the roster admits a name key).

Keyed by `(flex_version, object_class)`. A census whose destination
`flex_version` differs from the baseline's, or whose `content_hash` fails to
verify, MUST refuse the gate - a stale baseline passing silently is what FR-010
exists to prevent. Subtraction is by count per class, never by deletion: starter
content the linguist has since edited is no longer identical and must not be
treated as disposable (Edge Cases).

## 5. ClassCensusRow / FidelityCensus (new)

| Field (`ClassCensusRow`) | Type | Opt | Notes |
|---|---|---|---|
| `object_class` | `str` | no | from `specs/035-fullsweep-fidelity/object-inventory.md` |
| `source_count` | `int` | no | |
| `destination_count` | `int` | no | |
| `starter_excluded` | `int` | no | from `StarterBaselineEntry.count` |
| `difference` | `int` | no | `destination_count - starter_excluded - source_count` |
| `explained` | `bool` | no | |
| `reasons` | `tuple[str, ...]` | yes `()` | run-report lines; MUST be non-empty when `difference != 0 and explained` |
| `engine_can_create` | `bool` | no | false => report-only, no gate |
| `out_of_scope` | `bool` | no | `CmAnthroItem`, texts/reversals classes |

`FidelityCensus`: `run_id`, `source_project`, `destination_project`,
`baseline: StarterBaseline`, `rows: tuple[ClassCensusRow, ...]`, `taken_at`,
`gate_pass: bool`.

`gate_pass` is true iff every row with `engine_can_create and not out_of_scope`
has `difference == 0`, or `explained` with non-empty `reasons` (FR-013, SC-005).
Coverage spans every class the engine can create (FR-012). Rendering is
human-readable alongside `Lib/report.py:258` and machine-readable alongside
`Lib/report.py:248` (FR-011), from a supported surface, not a `debug/` script
(SC-009).

## 6. ClosureEdge / IncompletenessRecord (new)

`ClosureEdge` materialises one `(dependency, dependent)` pair of `pulled_in_by`.

| Field | Type | Opt | Notes |
|---|---|---|---|
| `dependent` | `tuple[GrammarCategory, str]` | no | the item that needs |
| `dependency` | `tuple[GrammarCategory, str]` | no | the item needed |
| `kind` | `DependencyKind` | no | `AFFIX_TO_POS`, `AFFIX_TO_SLOT`, `SLOT_TO_TEMPLATE`, `TEMPLATE_TO_POS`, `MSA_TO_INFL_FEATURE`, `PROCESS_RULE_TO_PHONEME`, `PROCESS_RULE_TO_NATURAL_CLASS` |
| `verified` | `bool` | no | FR-018 |
| `verified_by` | `str` | yes `""` | test/probe id that verified it |
| `origin` | `str` | no | `"chosen"` (seed) or `"pulled_in"` (FR-015) |
| `deselected` | `bool` | no | FR-016, per item |

`build_run_plan` MUST raise on any edge with `verified is False` rather than plan
from it (FR-018). `closure.walk`'s seed semantics hold: a directly selected item
is never `pulled_in`.

`IncompletenessRecord` is raised when a dependency is deselected (FR-016) or
unsatisfiable (FR-017): `incomplete_item`, `incomplete_label`,
`missing_dependency`, `missing_label` (the two refs are
`tuple[GrammarCategory, str]`), `cause: str` (`deselected` | `unsatisfiable` |
`cycle`), `consequence: str`. Every record reaches the post-run statistics panel;
the item is reported, not transferred silently broken (FR-017, SC-010).
Affix-to-column link failures emit one too (FR-019, SC-003).

## 7. EnrichmentRecord (new)

What a matched-and-enriched destination object gained (FR-020..FR-022, SC-007).

| Field | Type | Opt | Notes |
|---|---|---|---|
| `object_class` | `str` | no | |
| `source_guid`, `target_guid` | `str` | no | |
| `label` | `str` | no | |
| `collections` | `tuple[EnrichedCollection, ...]` | no | one per owned collection touched |
| `fields_updated` | `tuple[str, ...]` | yes `()` | scalar/multistring fields filled where empty |
| `was_created` | `bool` | no | always False here; the created-vs-enriched flag (FR-022) |

`EnrichedCollection`: `field_name: str`, `added: int`, `already_present: int`,
`dropped: int`. `field_name` is one of the seven POS owned collections:
`AffixSlotsOC`, `AffixTemplatesOS`, `InflectableFeatsRC`, `SubPossibilitiesOS`,
`StemNamesOC`, `InflectionClassesOC`, `ReferenceFormsOS`.

Enrichment never removes, blanks, or overwrites existing destination content
(FR-021): write mode is `PlannedOverwrite.write_mode == "merge"`, Principle IV's
"write source where non-empty, keep target where source empty, never blank from
empty". An enrichment with every `added == 0` and no `fields_updated` is the only
case that may degrade to a `Skip`.

## 8. ProcessRuleTransferRecord (new)

FR-023..FR-025, SC-006.

| Field | Type | Opt | Notes |
|---|---|---|---|
| `source_guid` | `str` | no | source `MoAffixProcess` |
| `target_guid` | `str` | yes `""` | empty when not reproduced |
| `input_contexts` | `tuple[ProcessContextSpec, ...]` | no | `PhSimpleContextSeg` / `PhSimpleContextNC` / `PhSimpleContextBdry` rows |
| `output_steps` | `tuple[ProcessOutputSpec, ...]` | no | `MoCopyFromInput`, `MoInsertPhones`, `MoModifyFromInput` |
| `reproduced` | `bool` | no | |
| `not_reproducible_reason` | `str` | yes `""` | MUST be non-empty when `reproduced is False` |
| `reference_decisions` | `tuple` | yes `()` | reuses `ReferenceDecisionRecord`; phoneme / natural-class refs resolve to the FR-001/FR-002 matched items, never duplicates (FR-024) |

Hard invariant (FR-025, SC-010): when `reproduced is False` the item is reported
via `DroppedItemRecord` plus `Skip(NOT_REPRODUCIBLE)` and skipped. It MUST NEVER
be written as a different, simpler class - the historic
`MoAffixProcess -> MoAffixAllomorph` downgrade is prohibited by construction: no
`PlannedAction` may name a target class differing from its source class.

## 9. Alignment with the constitution's disposition vocabulary

| Situation | Basis | Disposition | Mode | Carrier |
|---|---|---|---|---|
| No match, class creatable | `NONE` | ADD | ADD_NEW | `PlannedAction` + `MatchBasisRecord(NONE)` |
| Identity match, delta found | `IDENTITY` | UPDATE | UPDATE | `PlannedOverwrite(write_mode="merge")` + `EnrichmentRecord` |
| Natural-key match, delta found | `NATURAL_KEY` | UPDATE | LINK then UPDATE | same, `match_via="natural_key"`, counted IDENTITY-SUBSTITUTION |
| Match, no delta, proven by field-identity comparison | either | SKIP | LINK | `Skip(ALREADY_PRESENT_BY_GUID \| ALREADY_PRESENT_BY_IDENTITY)` |
| Out-of-scope class (`CmAnthroItem`) | n/a | IGNORE | n/a | `ClassCensusRow(out_of_scope=True)` |
| Not reproducible | any | SKIP | n/a | `Skip(NOT_REPRODUCIBLE)` + `ProcessRuleTransferRecord` |
| Conflict, user took source | either | OVERWRITE | OVERWRITE | `PlannedOverwrite(write_mode="overwrite")` |

**SKIP is defined by field-identity comparison, not by mere GUID presence.** A
matched GUID alone is a LINK, not a SKIP. Emitting SKIP requires that every
scalar field and all seven owned collections were compared and needed no write;
otherwise it is UPDATE. Defect G3 is exactly the whole-object
`ALREADY_PRESENT_BY_GUID` skip taken without that comparison.

## 10. State transitions

```
selected (seed)  |  pulled_in (ClosureEdge.origin)
        -> match attempt, identity first (FR-001)
             -> matched-by-identity     (MatchBasis.IDENTITY)
             -> matched-by-natural-key  (MatchBasis.NATURAL_KEY, roster only)
             -> unmatched               (MatchBasis.NONE)
        -> disposition
             ADD    <- unmatched, class creatable
             UPDATE <- matched, delta found -> enriched (EnrichmentRecord)
             SKIP   <- matched, field-identity comparison found no delta
             dropped-with-reason <- not creatable, dependency deselected or
                 unsatisfiable, or not reproducible (DroppedItemRecord +
                 Skip + IncompletenessRecord)
```

Every selected item reaches exactly one of ADD, UPDATE (enriched), SKIP, or
dropped-with-reason, and each appears in the post-run statistics panel. There is
no fifth, unreported outcome (SC-010) - the existing `RunReport.__post_init__`
accounting invariant, extended to the new buckets.

## 11. Idempotence

FR-008 / SC-008, in terms of these entities:

1. Run 1 records `MatchBasisRecord(basis=NONE)` for a new item, writing it with
   the source GUID preserved.
2. Run 2 therefore finds it by `MatchBasis.IDENTITY`, yielding a
   `PlannedOverwrite` or a `Skip`, never a `PlannedAction`.
3. For a run-1 `NATURAL_KEY` match, run 2 reaches the SAME destination object:
   the key function is pure and run 1 did not alter the key value (enrichment
   never blanks or renames, FR-021).
4. So run 2's census repeats run 1's `destination_count` per class, every
   `ClassCensusRow.difference` is unchanged, and every `EnrichedCollection.added`
   is 0 with `already_present` equal to run 1's `added`.

Mechanical check: run 2's `RunPlan.actions` must contain zero `PlannedAction`
whose `match_basis.basis is MatchBasis.NONE` for a class run 1 created. Any such
action is an idempotence violation and fails the gate.
