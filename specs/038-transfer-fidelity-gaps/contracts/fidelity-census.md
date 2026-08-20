# Contract: Per-Class Object Census (the fidelity gate)

**Feature**: `038-transfer-fidelity-gaps` | **Date**: 2026-08-19

Source: spec.md FR-009..FR-013 (primary), plus FR-006 and FR-012; SC-005, SC-009,
SC-010 (primary), plus SC-002 and SC-004.
Evidence this contract is written against: [`census-evidence.md`](../census-evidence.md)
section 0 (the two measured runs `GT-20260819-030049` and `GT-20260819-024027`).

> **This instrument does not exist yet.** This document is the contract for what
> Phase 0 of this feature will build. The measurements in `census-evidence.md`
> were produced ad-hoc; `debug/audit_object_census.py` is NOT in the repository.
> Every command in [`../quickstart.md`](../quickstart.md) that depends on it is
> marked `PLANNED`.

---

## 0. What this is, and the two things it is NOT

This is an **object-count census**: for every object class the engine can create,
how many instances the source project holds, how many the destination project
holds, and what the difference means. It compares two live `.fwdata` projects
after a transfer and produces one human-readable table plus one machine-readable
artifact ([`census-artifact.schema.json`](census-artifact.schema.json)).

Two nearby things carry confusingly similar names. Neither is this.

| Not this | What it actually is | Why it is different |
|---|---|---|
| `tests/verification/fidelity_census.py` (feature 024, 1394 lines) | A **field-level** census. For each copied object pair it enumerates the populated owning/reference *fields* and classifies every field into one of four buckets (COPIED / DROP_REPORTED / OUT_OF_SCOPE_EXCLUDED / HANDLED_ELSEWHERE) against an in-code LCM model snapshot. Offline; no project opened. | Its unit is a **field on an object**. This contract's unit is a **count of objects of a class**. A project can pass 024's census with every field classified and still lose 1,949 objects, which is exactly what happened. |
| `specs/024-lexicon-reference-fidelity/contracts/fidelity-census.md` | The contract for the file above. Same filename as this document, different feature folder. | Cite the folder, never the bare filename. |

The two instruments are complementary and both are kept. 024 answers "is any
*field* silently unclassified?"; this one answers "did any *object* fail to
arrive, arrive twice, or arrive as a different class?" Neither subsumes the
other, and a reader who conflates them will mis-scope the gate.

---

## 1. Requirements this satisfies

| Id | Obligation | Where discharged here |
|---|---|---|
| FR-009 | Per-class source count, destination count, difference | Section 4 |
| FR-010 | Exclude what a newly created FLEx project ships | Section 5 |
| FR-011 | Machine-readable form as well as readable | `census-artifact.schema.json` |
| FR-012 | Cover every class the engine can create | Section 3 |
| FR-013 | Anything not reproduced appears with a reason | Section 7 |
| FR-006 | Natural-key matches distinguishable from identity matches | Section 8 |
| SC-005 | Every difference is zero or accounted for by a report line | Sections 7, 9 |
| SC-009 | Obtainable without hand-written scripting | `../quickstart.md` |
| SC-010 | No success reported over a silent discard or class change | Sections 6, 9 |
| SC-002 | No duplicate-named phoneme where the source had one | Section 6 |
| SC-004 | Templates and slots arrive at 100% | Section 9.1, Phase 2 predicate |

Constitution v8.0.0 anchors: **Principle I** (fail loudly, never silently drop) is
what the gate mechanises; **Principle III** (Preview-before-Mutate) is why the
census is a pure observer and neither a preview nor a move (Section 2);
**Principle IV**'s "reports MUST NOT claim more certainty than the baseline
supports" is why a missing baseline downgrades the verdict instead of being
assumed zero (Section 5.3).

---

## 2. READ-ONLY, without exception

The census MUST NOT write to either project, and MUST NOT be capable of writing.

- Both projects are opened **read-only**. The destination is opened read-only too,
  even though it is the project being judged, and even on a run that immediately
  follows a transfer.
- No residue tag, no `[GT-Tag]` line, no `CmAgent`, no evaluation object, no
  temporary list item. The census leaves no trace in either `.fwdata`.
- No restore is required before or after a census, because nothing it does needs
  undoing. A census is therefore safe to run against a project a person is
  actively using, and safe to run repeatedly.
- The census records `fwdata_sha256_before` for each project prior to counting and
  asserts it equal to `fwdata_sha256_after`. A changed digest is `CENSUS_ERROR`
  (Section 9), never a quiet warning: it means either the census wrote, or
  something else did while it was reading, and in both cases the counts are not
  evidence.
- The artifact carries `opened_read_only` per project, pinned to `const: true` in
  the schema, so an artifact produced through a write-enabled handle cannot
  validate.

This is also why the census is *not* subject to the Preview/Move split of
Principle III: it is an observer of both projects, not a plan builder and not an
executor. It has no `Lib/preview.py` twin because it has nothing to preview.

---

## 3. The class list, and how FR-012 coverage is PROVEN

FR-012 requires the comparison to cover **every object class the transfer engine is
capable of creating**. A hand-maintained list inside the census's own source would
make that an assertion. It is instead derived, and re-derived at run time.

### 3.1 Truth source

The engine's create surface is enumerated in
`specs/035-fullsweep-fidelity/object-inventory.md` (441 lines): TABLE 1 is the 65
distinct classes the engine CREATES (70 create rows), TABLE 2 the 24 it LINKS to,
TABLE 3 the ride-along owned children, TABLE 4 the writing-system and
configuration artifacts.

Feature 035 already publishes the machine-readable projection of that document as
`specs/035-fullsweep-fidelity/contracts/coverage-floor.json` -- `in_scope_classes`,
currently **69** entries (TABLE 1 union TABLE 2's referenced-only classes, minus
`excluded_not_measurable`).

**038 reads that file. 038 does not fork it.** The floor and the natural-key roster
are owned by 035, and edits to either must be coordinated with that live session.

### 3.2 The proof obligation (not an assertion)

Four checks, all executable, each failing by class name.

- **CP-1 -- derivation, at run time.** The census re-derives the class set by
  parsing TABLE 1 and TABLE 2 of `object-inventory.md` and asserts set equality
  against `in_scope_classes` union `excluded_not_measurable`. A class added to the
  inventory and not to the floor, or the reverse, fails the run and names the class.
  The derivation runs on every census invocation rather than being pinned to a
  stored digest, so drift in the truth source cannot pass unnoticed. The digests
  are still recorded, as provenance for the reader.
- **CP-2 -- one row per class, always.** The artifact carries exactly one `classes`
  row per required class. A class with no instances in either project is reported
  `NOT_EVALUATED` with a reason; it is **never** omitted. `len(classes) ==
  required_class_count` is a validator invariant (Section 11).
- **CP-3 -- gate scope is explicit per row.** Rows with `engine_can_create: true`
  are `gate_scope: "required"`. The three classes the inventory records as never
  created by any path -- `LexRefType`, `LexAppendix`, `PhBdryMarker` -- are
  `gate_scope: "advisory"` and cannot by themselves fail the gate. SC-005's scope is
  exactly the `required` set.
- **CP-4 -- the additions ledger.** Three classes measured in `census-evidence.md`
  section 0 are absent from the 035 floor. They are carried in
  `class_list_provenance.census_additions`, each with a rationale and
  `owed_to_035: true`:

  | Addition | Measured | Why the floor omits it |
  |---|---|---|
  | `MoAffixProcess` | Ejagham 13 -> 0, Ngoreme 1 -> 0 | Absent from `object-inventory.md` entirely, because the engine has **no create path** for it -- the class the transfer silently downgraded. A truth-source gap, not a corpus gap. |
  | `PhCode` | 43 -> 25, 89 -> 25 | `object-inventory.md` TABLE 3 (ride-along): flexicon's phoneme `GetSyncableProperties` explicitly does not include `CodesOS`, so nothing carries it and nothing reports the drop. Measurable, and measured. |
  | `CmTranslation` | Ngoreme 7925 -> 2 | Reached through the texts path; never projected into the floor. |

  Required class count is therefore **72** until 035 absorbs the additions. A class
  appearing in BOTH `in_scope_classes` and `census_additions` is
  `COVERAGE_INCOMPLETE`: the addition must be dropped in the same change that adds
  it to the floor, so the ledger cannot rot into a second truth source.

Classes 035 marks `excluded_not_measurable` (`MoForm`, `MoMorphSynAnalysis` -- both
abstract LCM bases with no factory) get a `NOT_EVALUATED` row with reason
`ABSENT_BY_CONSTRUCTION`. `CmAnthroItem` is in the floor but out of this feature's
scope: it gets a `NOT_EVALUATED` row with reason `OUT_OF_SCOPE_CLASS`, so its
859 -> 0 on Ejagham stays visible and is explicitly not counted against the gate.

---

## 4. The three counts, and the sign convention

Per class, per run:

| Field | Meaning |
|---|---|
| `source_count` | instances of the class in the source project |
| `destination_count_total` | instances in the destination project, counted as found |
| `destination_count_net` | `destination_count_total` minus the destination's pre-existing instances (Section 5) |
| `difference` | `destination_count_net - source_count` -- **the gate quantity** |
| `difference_raw` | `destination_count_total - source_count` -- what a naive reader would compute |

**Sign convention, fixed and not negotiable:**

```
difference <  0   SHORTFALL   the destination has FEWER than the source   (loss)
difference == 0   MATCHED     the destination has as many as the source
difference >  0   SURPLUS     the destination has MORE than the source    (excess)
```

`verdict_class` carries the token (`MATCHED` / `SHORTFALL` / `SURPLUS` /
`NOT_EVALUATED`) so a reader never has to infer intent from a sign. The
human-readable table prints source count, destination count, and the signed
difference, and marks MATCHED rows so a class that agrees is distinguishable at a
glance (spec US2 acceptance scenario 3).

**No cross-class netting, ever.** Ejagham's `MoAffixProcess` 13 -> 0 (SHORTFALL
-13) and `MoAffixAllomorph` 130 -> 143 (SURPLUS +13) are the *same defect* seen
twice: a process rule silently downgraded into an ordinary allomorph. Summing them
to zero would report the run clean while a whole class changed kind, which is
precisely the SC-010 failure this feature exists to end. Totals are reported as
`total_shortfall` and `total_surplus` separately and are never summed into a single
net figure.

---

## 5. The starter baseline (FR-010)

A newly created FLEx project is not empty. It ships example phonemes, two example
natural classes, a starter part-of-speech list, morph types, and more. None of it
shares identity with any source project's equivalents. Counted naively it looks
like a surplus the transfer created.

### 5.1 The three admissible baseline kinds

`starter_baseline.kind` is one of:

- **`pre_transfer_census`** (preferred, and the only kind valid for a destination
  that is not a fresh project). A census of the destination taken *before* the
  transfer ran, keyed by class. Exact by construction: it is the destination's own
  prior state, not a model of it.
- **`starter_capture`**. A per-class census of a genuinely freshly created empty
  FLEx project, captured once and tracked as
  `specs/038-transfer-fidelity-gaps/contracts/starter-baseline.json`. Valid only
  for a destination the operator declares was freshly created.
- **`none`**. Legal to *record*, never legal to *pass* -- see 5.3.

A `starter_capture` baseline records, per class, both the count and the **natural
keys** of the starter objects (phoneme names, POS names and abbreviations,
morph-type names). Those keys are what make 5.2 and Section 6 possible; a count
alone is not enough.

### 5.2 Gross subtraction is wrong once natural-key matching exists

Subtracting the whole baseline count is only correct while nothing matches it. Take
the measured phoneme row: source 41, destination 64, starter 23.

- Broken run (measured): 0 of the 23 starter phonemes matched, 41 created beside
  them. 64 - 23 = 41, so `difference` 0.
- Fixed run (the FR-002 goal): 21 starter phonemes matched by name, 20 new created,
  destination total 43. Gross subtraction gives 43 - 23 = 20, so `difference`
  **-21** -- a shortfall reported on a *correct* run.

So the subtrahend is the starter objects that were **not** matched to a source
object:

```
unmatched_starter     = starter_baseline_count - starter_matched_to_source
destination_count_net = destination_count_total - unmatched_starter
```

Fixed run: 23 - 21 = 2 unmatched, 43 - 2 = 41, `difference` 0. Correct.
Broken run: 23 - 0 = 23 unmatched, 64 - 23 = 41, `difference` 0. **Also zero** --
and that run was catastrophically wrong. Baseline arithmetic alone cannot see a
duplicate. Section 6 is what does, and it is not optional.

`starter_matched_to_source` comes from the run report's identity-substitution counts
(FR-006, and 035's FR-187). When no run report is available the census cannot know
it, and says so rather than guessing:

| `starter_subtraction_basis` | Condition | Consequence |
|---|---|---|
| `baseline_matched` | baseline present AND run report present | `difference` is fully trustworthy |
| `baseline_gross` | baseline present, run report absent | `starter_matched_to_source: null`; gross subtraction used; every row is advisory for SHORTFALL purposes and the run verdict cannot exceed `CENSUS_ACCOUNTED`. **CLARIFIED 2026-08-19:** "cannot exceed" suppresses exactly `UNEXPLAINED_SHORTFALL` and `UNEXPLAINED_SURPLUS`. It is a **ceiling on unexplained tallies, not on severity**: `CENSUS_ERROR`, `COVERAGE_INCOMPLETE`, `BASELINE_MISSING`, `BASELINE_STALE` and `DUPLICATE_IDENTITY` are unaffected and still win. Read against the published severity ordering (:459-469) the bare phrase would also suppress those, contradicting 5.3 ("Staleness and absence are **verdicts**, not warnings. There is no path on which a missing baseline yields exit 0", :80-81) and 5.2's own closing line ("Section 6 is what does, and it is not optional", :49). The governing clause is the local one in this same sentence: advisory *for SHORTFALL purposes*. The cap is also the **run** verdict only -- `row_passes` and `evaluate_phase` are untouched, so a phase cannot declare itself done on gross-basis arithmetic |
| `no_baseline` | no baseline at all | see 5.3 |

### 5.3 Missing or stale baseline

- **Missing** (`kind: "none"`): verdict `BASELINE_MISSING`, exit 4. The census still
  produces a complete artifact with every count and `difference_raw` -- the numbers
  are useful -- but it MUST NOT report a pass, and MUST NOT substitute zero for the
  baseline. A zero baseline is a claim that the destination shipped empty, and
  Principle IV forbids a report claiming more certainty than its baseline supports.
- **Stale**: the baseline records `flex_version`, `data_model_version`, and the
  `fwdata_sha256` of the project it was captured from. A baseline is stale when the
  destination's `data_model_version` exceeds the baseline's, or the recorded
  `flex_version` differs from the running FieldWorks version. Verdict
  `BASELINE_STALE`, exit 5. FLEx changes what a new project ships between versions;
  an old capture silently mis-subtracts.
- **Mis-declared**: a `starter_capture` baseline used against a destination the
  operator did not declare freshly created is `CENSUS_ERROR`. The spec's edge case
  "destination content that FLEx ships but the linguist has since edited" is handled
  the only honest way -- by requiring `pre_transfer_census` for any destination that
  is not demonstrably fresh.

Staleness and absence are **verdicts**, not warnings. There is no path on which a
missing baseline yields exit 0.

---

## 6. Duplicates: why `difference == 0` is not sufficient

A class row passes only when *both* hold:

1. `difference == 0`, or every non-zero unit is accounted for (Section 7); **and**
2. `duplicates.extra_objects == 0`, or each duplicate group is accounted for.

`duplicates` is computed for every class on the natural-key roster
(`specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json`) plus
every `census_additions` class with a stated key. It groups destination objects by
that key and counts groups of size > 1:

```
duplicates.groups        = number of keys held by more than one destination object
duplicates.extra_objects = sum(group_size - 1) over those groups
duplicates.examples[]    = { key, count, guids[] }   (never truncated)
```

The measured phoneme case: `PhPhoneme`, `difference` 0, `duplicates.groups` 21,
`duplicates.extra_objects` 21, examples `a`, `b`, `d`, `e`, `f`, `g`, `i`, `j`, `k`,
`l`, `m`, `n`, `o`, `p`, `r`, `s`, `t`, `u`, `w`, `z`, plus the eng. Only `v` and
`x` were genuinely destination-only. The row fails on rule 2 with verdict
`DUPLICATE_IDENTITY`, which is what makes the census a gate for SC-002 and not
merely for SC-005.

`duplicates` is reported for classes NOT on the roster too, as advisory: a duplicate
name on an unadmitted class is not automatically a defect (homographs are
legitimate), so it is surfaced and does not fail the gate. Admission to
gate-failing duplicate detection is by roster enumeration only, exactly as FR-003
requires for matching itself.

---

## 7. Accounted for, versus unexplained (SC-005)

SC-005: every difference is *either zero or accounted for by a line in the run
report*. The census makes that a computation, not a judgement call.

Each class row carries `accounted_for[]`, a list of lines each claiming a count
against the difference:

```jsonc
{ "reason": "NO_CREATE_PATH",
  "count": 13,
  "direction": "shortfall",
  "report_ref": { "kind": "dropped_item", "run_id": "GT-20260819-030049",
                  "record_ids": ["..."], "count_in_report": 13 },
  "detail": "MoAffixProcess reported and skipped, never downgraded (FR-025)" }
```

Then, per direction:

```
unexplained_shortfall = max(0, -difference) - sum(accounted_for where direction == "shortfall")
unexplained_surplus   = max(0,  difference) - sum(accounted_for where direction == "surplus")
```

Rules:

- **R-1.** A line is valid only if it resolves to real report content. Every reason
  except `STARTER_CONTENT`, `ABSENT_BY_CONSTRUCTION`, `OUT_OF_SCOPE_CLASS`, and
  `GOVERNED_BY_OTHER_FEATURE` MUST carry a `report_ref` whose `count_in_report >=
  count`. A line claiming 13 against a report that names 2 is `CENSUS_ERROR`, not a
  pass.
- **R-2.** Over-accounting fails. `sum(accounted_for)` exceeding the difference in
  its direction is `CENSUS_ERROR`. The census must not be able to explain away more
  than actually happened.
- **R-3.** Accounting is per class and per direction. A shortfall line never offsets
  a surplus, and a line on one class never touches another (Section 4).
- **R-4.** `unexplained_shortfall > 0` or `unexplained_surplus > 0` on any
  `gate_scope: "required"` row fails the run. That single rule is SC-005.
- **R-5.** Absence of an `accounted_for` list is not an excuse. A class with a
  non-zero difference and an empty list is fully unexplained, by definition.

### 7.1 The reason vocabulary (FR-013)

A closed enum. A reason the census cannot classify is `CENSUS_ERROR`, never a
free-text pass. Tokens are `SCREAMING_SNAKE_CASE` in the artifact; the
human-readable table prints the label.

| Token | Direction | Means |
|---|---|---|
| `MATCHED_EXISTING_IDENTITY` | shortfall | The source object matched a destination object by GUID, so no new object was created. Not a loss. |
| `MATCHED_EXISTING_NATURAL_KEY` | shortfall | Matched on the FR-002 natural-key basis (FR-006). Not a loss. |
| `ENRICHED_EXISTING` | shortfall | Matched and enriched with owned children rather than created (FR-020, FR-022). |
| `STARTER_CONTENT` | surplus | Explained by the new-project starter inventory (FR-010). Needs no `report_ref`. |
| `NO_CREATE_PATH` | shortfall | The engine has no create path for the class or subclass; reported and skipped (FR-025). `MoAffixProcess` before Phase 4; `FsFeatStrucType`. |
| `UNSUPPORTED_SUBTYPE` | shortfall | A recognised class whose specific subtype the engine cannot reproduce. Reported, never downgraded. |
| `DEPENDENCY_UNRESOLVED` | shortfall | A required referent is absent in the destination (FR-017). |
| `DEPENDENCY_DESELECTED` | shortfall | A pulled-in dependency the operator deliberately switched off (FR-016, FR-017). |
| `NOT_SELECTED` | shortfall | The class's category was not part of this run's selection. |
| `UNMAPPED_WS` | shortfall | A writing system could not be mapped, so a string-bearing object was not written. |
| `IDENTITY_COLLISION` | shortfall | The source GUID is already held by a different destination object. |
| `AMBIGUOUS_NATURAL_KEY` | shortfall | The natural key matched more than one destination object; reported, never guessed. |
| `DUPLICATE_CREATED` | surplus | The transfer created an object beside an equivalent it failed to recognise. Always a defect; admissible as accounting only while a report line names it. |
| `GOVERNED_BY_OTHER_FEATURE` | either | Texts/wordforms, reversals, and sense pictures are governed by their own features; this feature reports their figures and does not fix them (spec Assumptions). Needs no `report_ref`. |
| `OUT_OF_SCOPE_CLASS` | either | `CmAnthroItem`. Needs no `report_ref`. |
| `ABSENT_BY_CONSTRUCTION` | either | Abstract LCM base with no factory (`MoForm`, `MoMorphSynAnalysis`). Needs no `report_ref`. |
| `SOURCE_REFERENT_ABSENT` | shortfall | A referent the engine required is absent on the **source**, so the dependent object was not transferred. The source-side sibling of `DEPENDENCY_UNRESOLVED` (FR-017), which is destination-side; the two are not interchangeable. |

There is deliberately **no `UNEXPLAINED` token and no `OTHER` token.** Unexplained
is the *absence* of an accounting line, so it cannot be laundered into one.
`DUPLICATE_CREATED` and `NO_CREATE_PATH` are admissible accounting because a
reported defect is not a *silent* defect, which is the Principle I standard -- but
they are exactly the reasons a phase's exit criteria should drive to zero.

---

## 8. Match-basis tallies (FR-006)

FR-006 requires every natural-key match to be distinguishable from an identity
match. The census carries the per-class tally so that distinction survives into the
gate artifact and is not report-only prose:

```jsonc
"match_basis": {
  "identity": 5,              // GUID match (FR-001, the authoritative basis)
  "natural_key": 21,          // FR-002 fallback; 035 FR-187 IDENTITY-SUBSTITUTION
  "created_new": 20,          // no match found, created
  "enriched": 3,              // matched AND gained owned children (FR-020)
  "unmatched_reported": 0,    // no match, not created, reported (FR-007)
  "basis_source": "run_report"
}
```

`identity + natural_key + created_new + unmatched_reported` MUST equal
`source_count` on a `required` row whose `basis_source` is `run_report`; a mismatch
is `CENSUS_ERROR`. `enriched` is a subset of `identity + natural_key` and is not
part of that sum. When no run report is available, `basis_source` is
`"unavailable"`, every tally is `null`, and the row's `starter_subtraction_basis` is
at best `baseline_gross` (Section 5.2).

`match_basis.natural_key > 0` for a class absent from the 035 roster is a harness
error, matching that roster's own `enforcement` clause: the natural-key basis firing
for an unadmitted class must name the class and fail.

---

## 9. The gate: verdicts, exit codes, pass/fail

Three separate things, deliberately not conflated (house style, following
`specs/035-fullsweep-fidelity/contracts/verdict-exit-model.md`): the machine token
the artifact stores and tests assert on, the human label the console prints, and
the process exit code.

| Machine token | Human label | Exit code | Success? |
|---|---|---|---|
| `CENSUS_CLEAN` | `Census clean` | 0 | yes |
| `CENSUS_ACCOUNTED` | `Census accounted` | 0 | yes |
| `UNEXPLAINED_SHORTFALL` | `Unexplained shortfall` | 1 | no |
| `UNEXPLAINED_SURPLUS` | `Unexplained surplus` | 2 | no |
| `DUPLICATE_IDENTITY` | `Duplicate identity` | 3 | no |
| `BASELINE_MISSING` | `Baseline missing` | 4 | no |
| `BASELINE_STALE` | `Baseline stale` | 5 | no |
| `COVERAGE_INCOMPLETE` | `Coverage incomplete` | 6 | no |
| `CENSUS_ERROR` | `Census error` | 7 | no |

Assignment -- exactly one verdict per census run:

| Verdict | Assigned when |
|---|---|
| `CENSUS_CLEAN` | Every `required` row is MATCHED with zero duplicates and an empty `accounted_for`. Nothing needed explaining. |
| `CENSUS_ACCOUNTED` | As clean, except one or more rows carry differences fully accounted for by valid report lines (Section 7). |
| `UNEXPLAINED_SHORTFALL` | Any `required` row has `unexplained_shortfall > 0`. |
| `UNEXPLAINED_SURPLUS` | Any `required` row has `unexplained_surplus > 0` and no unexplained shortfall outranks it. |
| `DUPLICATE_IDENTITY` | Any roster-admitted class has unaccounted `duplicates.extra_objects > 0`. |
| `BASELINE_MISSING` | `starter_baseline.kind == "none"`. |
| `BASELINE_STALE` | Baseline present but version-mismatched against the destination (5.3). |
| `COVERAGE_INCOMPLETE` | CP-1 derivation mismatch, a missing `classes` row, or a class in both the floor and the additions ledger. |
| `CENSUS_ERROR` | An R-1/R-2 accounting violation, a Section 8 tally mismatch, an `fwdata_sha256` that changed under the census, a mis-declared baseline kind, an unclassifiable reason, or an unhandled exception. |

**Published severity ordering** (most severe first). This is NOT the exit-code
integer and MUST NOT be derived from it:

```
CENSUS_ERROR
COVERAGE_INCOMPLETE
BASELINE_MISSING
BASELINE_STALE
DUPLICATE_IDENTITY
UNEXPLAINED_SHORTFALL
UNEXPLAINED_SURPLUS
CENSUS_ACCOUNTED
CENSUS_CLEAN
```

Exactly two verdicts report success. There is deliberately no verdict meaning "loss
reported, review advisable, exit success" -- that is the shape of the bug this
feature exists to remove (SC-010).

### 9.1 Using it as a phase gate

Acceptance for Phases 1..5 of this feature is a census diff, not a unit test. A
phase declares its exit criteria as a **predicate over the artifact**, and the
predicate names classes and counts:

- **Phase 1 (identity).** `MoStemMsa`, `MoInflAffMsa`, `MoDerivAffMsa`,
  `MoUnclassifiedAffixMsa`, `PartOfSpeech` rows MATCHED;
  `PhPhoneme.duplicates.extra_objects == 0`. (SC-001, SC-002)
- **Phase 2 (closure).** `MoInflAffixTemplate` and `MoInflAffixSlot` rows MATCHED.
  (SC-004)
- **Phase 3 (enrichment).** `match_basis.enriched > 0` on `PartOfSpeech`, and the
  owned-child classes MATCHED. (SC-007)
- **Phase 4 (process rules).** `MoAffixProcess` MATCHED **and** `MoAffixAllomorph`
  `difference == 0` -- both, because either alone can be satisfied by the defect
  itself. (SC-006)
- **Phase 5 (residual).** Every remaining `required` row is either MATCHED or
  carries a valid `GOVERNED_BY_OTHER_FEATURE` / `NO_CREATE_PATH` line. (SC-005)

A phase is not done when its unit tests pass; it is done when the census run for its
predicate exits 0 with the predicate satisfied.

---

## 10. Worked example -- the measured runs

Real figures from `census-evidence.md` section 0, as the artifact would express
them. Shortened to the load-bearing fields.

**(a) A total loss with no accounting.** `MoStemMsa` on `Ngoreme FLEx` ->
`Ngoreme Target`, run `GT-20260819-024027`. All 1,949 stem MSAs gone, because
`_resolve_target_pos` returned `None` for every one of the source's 26 parts of
speech and the caller abandoned the object.

```jsonc
{ "class": "MoStemMsa", "engine_can_create": true, "gate_scope": "required",
  "source_count": 1949, "destination_count_total": 0,
  "starter_baseline_count": 0, "starter_matched_to_source": 0,
  "starter_subtraction_basis": "baseline_matched",
  "destination_count_net": 0, "difference": -1949, "difference_raw": -1949,
  "verdict_class": "SHORTFALL",
  "accounted_for": [], "unexplained_shortfall": 1949, "unexplained_surplus": 0,
  "match_basis": { "identity": 0, "natural_key": 0, "created_new": 0,
                   "enriched": 0, "unmatched_reported": 0,
                   "basis_source": "run_report" } }
```

`unexplained_shortfall` 1949 on a `required` row -> run verdict
`UNEXPLAINED_SHORTFALL`, exit 1. Note `unmatched_reported: 0`: nothing was even
reported, which is the Principle I violation. Once branch `038-affix-fidelity`'s D2
fix lands, the same loss shows `unmatched_reported: 1949` and can carry a
`DEPENDENCY_UNRESOLVED` line -- still a failure by the Phase 1 predicate, but a
*visible* one. That is the difference between D1/D2 (making loss visible) and
Phase 1 (making it stop).

**(b) A duplicate that arithmetic hides.** `PhPhoneme`, identical on both pairs: 41
source phonemes created GUID-preserved beside the destination's 23 starter phonemes.

```jsonc
{ "class": "PhPhoneme", "engine_can_create": true, "gate_scope": "required",
  "source_count": 41, "destination_count_total": 64,
  "starter_baseline_count": 23, "starter_matched_to_source": 0,
  "starter_subtraction_basis": "baseline_matched",
  "destination_count_net": 41, "difference": 0, "difference_raw": 23,
  "verdict_class": "MATCHED",
  "accounted_for": [], "unexplained_shortfall": 0, "unexplained_surplus": 0,
  "duplicates": { "key_definition": "Name (vernacular alt), case-sensitive",
                  "roster_admitted": true, "groups": 21, "extra_objects": 21,
                  "examples": [ { "key": "a", "count": 2, "guids": ["...", "..."] },
                                { "key": "z", "count": 2, "guids": ["...", "..."] } ] },
  "match_basis": { "identity": 0, "natural_key": 0, "created_new": 41,
                   "enriched": 0, "unmatched_reported": 0,
                   "basis_source": "run_report" } }
```

`difference` is **0** and `verdict_class` is **MATCHED** -- and the run still fails:
`DUPLICATE_IDENTITY`, exit 3, on rule 2 of Section 6. This row is why Section 6
exists. A gate built on counts alone would have passed the single worst phoneme
outcome available.

**(c) A class change that must not net out.** `MoAffixProcess` and
`MoAffixAllomorph` on `Ejagham W Mini` -> `Ejagham W Target`, run
`GT-20260819-030049`. Thirteen process rules were downgraded into ordinary
allomorphs -- source GUID and Form kept, `Input`/`Output` destroyed -- then stamped
with GT residue so the run reported success.

```jsonc
{ "class": "MoAffixProcess", "engine_can_create": false, "gate_scope": "required",
  "in_class_list_via": "census_additions",
  "source_count": 13, "destination_count_total": 0,
  "destination_count_net": 0, "difference": -13, "verdict_class": "SHORTFALL",
  "accounted_for": [], "unexplained_shortfall": 13 }

{ "class": "MoAffixAllomorph", "engine_can_create": true, "gate_scope": "required",
  "source_count": 130, "destination_count_total": 143,
  "starter_baseline_count": 0, "destination_count_net": 143,
  "difference": 13, "verdict_class": "SURPLUS",
  "accounted_for": [], "unexplained_surplus": 13 }
```

Two rows, two failures, one defect. `total_shortfall` and `total_surplus` are
reported separately and never summed, so the +13 cannot cancel the -13. On the
post-`18c0ece` engine the first row gains a
`{ "reason": "NO_CREATE_PATH", "count": 13, "report_ref": { ... } }` line and the
second returns to `difference: 0` -- so the pair moves from
`UNEXPLAINED_SHORTFALL` to `CENSUS_ACCOUNTED`, which is exactly the state Phase 4
then has to clear.

**(d) For contrast, a partially accounted row.** Ejagham's five destination parts of
speech happened to be GUID-identical to five of the source's, so they matched rather
than being created:

```jsonc
{ "class": "PartOfSpeech", "source_count": 20, "destination_count_total": 5,
  "starter_baseline_count": 5, "starter_matched_to_source": 5,
  "starter_subtraction_basis": "baseline_matched",
  "destination_count_net": 0, "difference": -20, "verdict_class": "SHORTFALL",
  "accounted_for": [ { "reason": "MATCHED_EXISTING_IDENTITY", "count": 5,
                       "direction": "shortfall",
                       "report_ref": { "kind": "skip", "run_id": "GT-20260819-030049",
                                       "count_in_report": 5 } } ],
  "unexplained_shortfall": 15,
  "match_basis": { "identity": 5, "natural_key": 0, "created_new": 0,
                   "enriched": 0, "unmatched_reported": 15,
                   "basis_source": "run_report" } }
```

Five of the twenty are legitimately accounted for; fifteen are not -- including the
three sub-categories (`Verb Test`, `Exclamation`, `Verb Stative`) that never arrived
because their parent `Verb` already existed and the whole-object skip never
descended into `SubPossibilitiesOS`. Partial accounting does not rescue a row: the
remaining 15 still fail the gate.

---

## 11. Invariants a validator MUST enforce

1. Exactly one `classes` row per required class; `len(classes) ==
   class_list_provenance.required_class_count`. A class is `NOT_EVALUATED`, never
   absent (CP-2).
2. No list in the artifact is truncated, ever -- `duplicates.examples`,
   `accounted_for`, and `notes` included. Truncation is legal only in the console
   summary, which MUST state how many items it omitted.
3. `difference == destination_count_net - source_count` and `difference_raw ==
   destination_count_total - source_count`, on every counted row. Both are stored,
   and a validator recomputes both.
4. `destination_count_net == destination_count_total - (starter_baseline_count -
   starter_matched_to_source)` whenever `starter_subtraction_basis ==
   "baseline_matched"`.
5. Every `accounted_for` line whose reason is not `STARTER_CONTENT`,
   `ABSENT_BY_CONSTRUCTION`, `OUT_OF_SCOPE_CLASS`, or `GOVERNED_BY_OTHER_FEATURE`
   carries a `report_ref` with `count_in_report >= count` (R-1).
6. `sum(accounted_for)` per direction never exceeds the difference in that direction
   (R-2).
7. `opened_read_only` is `true` for both projects, and each project's
   `fwdata_sha256_before` equals its `fwdata_sha256_after`.
8. `verdict` and `exit_code` agree with the table in Section 9, and `verdict` is the
   most severe applicable token by the Section 9 ordering.
9. Every datum that contributed to `verdict` also appears in this artifact. A
   verdict-bearing datum that reached its reader only through the console is a
   violation.
10. `transfer_run.run_id`, when present, matches `^GT-\d{8}-\d{6}$`; `census_id`
    matches `^CENSUS-\d{8}-\d{6}$`.
11. `match_basis` sums as specified in Section 8 on every `required` row whose
    `basis_source` is `run_report`.

---

## 12. What this contract does NOT cover

- **Field-level fidelity.** Whether an arrived object arrived *complete* is 024's
  census and the run report's `FidelityStatus` (FULL / PARTIAL). An object counted
  here can be present and impoverished.
- **The natural-key roster itself.** Owned by 035. This feature extends it in place
  with `PhPhoneme`, `PhNCSegments`, `PhNCFeatures`, `PartOfSpeech`, `MoMorphType`,
  and `LexEntryInflType` (FR-005), coordinated with that live session, and never
  forks it.
- **Repairing damaged destinations.** Forward-looking only (spec Assumptions).
- **The transfer's own reporting.** The census *consumes* run-report lines; making
  the engine emit them is FR-013's job inside the engine, not here.

---

## 13. Amendment A1 -- `FsFeatStrucType` is counted per feature system

Recorded after this contract's first draft, from the live probe in
[process-morphology-create-path.md](process-morphology-create-path.md)'s sibling,
[feature-system-create-path.md](feature-system-create-path.md) (ops `op-043616616-018`,
`op-043655215-019`, `op-043716755-020`, `op-043743387-021`, all certified read-only).

A FieldWorks project has **two** feature systems, not one:

- `LangProject.MsFeatureSystemOA` -- the morphosyntactic feature system
- `LangProject.PhFeatureSystemOA` -- the phonological feature system

Both own `FsFeatStrucType` objects. A single summed `FsFeatStrucType` row is therefore
**ambiguous**: a shortfall in one system can be masked by a surplus in the other, which is the
same masking defect Section 6 rule 2 exists to prevent for duplicate identities.

**Requirement.** The `FsFeatStrucType` row MUST be split by owning feature system, carrying the
owner in the row so the two are never summed into one gate decision. Each part is evaluated
independently against the rules in Section 9. The same requirement applies to any other class
reachable from both feature systems.

This is an accounting change only -- it adds no class to the required list and does not alter
the 72-class count in Section 4, since `FsFeatStrucType` was already required. It changes how
that one class's counts are reported and gated.
