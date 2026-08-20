# Tasks: Transfer Fidelity Gaps

**Feature**: `specs/038-transfer-fidelity-gaps` | **Branch (code)**: `038-transfer-fidelity-gaps`
| **Size**: normal (unrecorded in `.spec-context.json`, treated as `normal`)

**Input**: [spec.md](spec.md) (US1..US5, FR-001..FR-025, SC-001..SC-010),
[plan.md](plan.md), [research.md](research.md) (R1..R7), [data-model.md](data-model.md),
[contracts/](contracts/), [census-evidence.md](census-evidence.md)

**Line format**: `- [ ] **T###** [P?] [US#] Description - exact/file/path`
`[P]` = independent of the others in its wave (different file, no incomplete dependency).

> **Do not hand-edit the `- [ ]` checkboxes.** `write-context.py --materialize` owns them.

---

## Phase ordering: why US2 runs before US1

The story phases below are **not** in bare priority order, and that is deliberate.
plan.md states the sequence is "set by verifiability rather than by user value": the
per-class census (US2, P2) is the acceptance instrument for every other slice --
"a phase is not done when its unit tests pass; it is done when the census run for its
predicate exits 0 with the predicate satisfied"
([contracts/fidelity-census.md](contracts/fidelity-census.md):486-487). US1 cannot be
accepted before the instrument that measures it exists.

Story phase order follows research.md:278 exactly:

```text
Phase 3 (US2 census) -> Phase 4 (US1 natural key) -> Phase 5 (US4 enrich) || Phase 6 (US5a)
                     -> Phase 7 (US3 closure) -> Phase 8 (US5b) -> Phase 9 (Polish)
```

US5 is split across two phases because R5 found a fourth blocking condition: 6 of 18 live
rules reference `PhSimpleContext*` objects owned by `PhPhonData.ContextsOS`, which is a
closure problem. **4a** (wholly-owned graphs) needs only US1; **4b** needs US3.

---

## Coordination and external gates

These are blocking facts, not advice. Each has a task that owns it.

| Gate | Owner task | Status |
|---|---|---|
| Land order `037-phon-nc-features` -> `038-affix-fidelity` -> this feature -> re-census (R6, non-negotiable) | T005 | both branches unmerged |
| 035 must append the six roster entries to `main` before **any** Phase 4 matching code | T028 | **CLEARED** `d8635d9` -- entries 3 -> 9, all six admitted, none rejected |
| `038-affix-fidelity` (`18c0ece`) must merge before US5 begins (spec.md:403) | T005 | unmerged |
| Post-037 re-census gates Phase 9 scoping and the phonology part of SC-005 (R7) | T078 | blocked on 037 |
| T038's P1 gate: `PhPhoneme` duplicates **0 (PASS)**; `PartOfSpeech` -5 is a `baseline_gross` phantom cleared by T043; `MoStemMsa` -2 is REAL and unexplained; exit 0 blocked by `carries_natural_keys:false` (fidelity-census.md 5.2, not Phase 4 work) | T038 | run 2026-08-20, `GT-20260820-002806` -- see journal |
| `CLAUDE.md` SPECKIT pointer still names `specs/029-sense-pictures/plan.md`; `CLAUDE.md` is claimed by 037 | T083 | deferred |

**037 has no spec artifacts.** There is no `specs/037*` on any branch or worktree, and 037's
`.specify/feature.json` still points at `specs/035-fullsweep-fidelity`. The only coordination
surface with 037 is its branch diff plus [census-evidence.md](census-evidence.md) section 4.
No task below may be phrased as "check 037's tasks.md".

**Two hazards plan.md:280-290 does not list:**

1. `Lib/models.py` (+56) and `Lib/report.py` (+30) are modified by 037 but **claimed by
   nobody**, and this feature names both as primary surfaces (plan.md:174,176). 037 adds
   `LeafExecutionFailure`, `RunReport.leaf_execution_failures` and the `leaf_failed`
   property to exactly those files. They belong on the rebase-first and claim list.
2. **`lockout` claims are worktree-path-scoped.** All seven of 037's live claims name
   `...\GramTrans-037-phon-nc-features\...` paths, so a claim taken from
   `..\GramTrans-038-transfer-fidelity-gaps\` on its own copy of `categories.py` can never
   register as a conflict. Claim the **main-worktree path** and verify with
   `lockout status --file` against 037's absolute path, or the claim is theatre.

**The flexicon floor moved under this plan.** 037 has raised `pyproject.toml` to
`pyflexicon>=4.5.0` (flexicon issue #222 - `NaturalClassOperations` `FeaturesOA` wiring);
plan.md and quickstart.md still say `>=4.4.1`. T002 verifies 4.5.0 and records the
discrepancy rather than editing `pyproject.toml` or `CLAUDE.md`, both of which 037 claims.
A related 037 change is worth knowing here: `natural_classes_execute_action` now **raises**
`RuntimeError` rather than reporting a defective transfer as successful, which is the same
no-silent-skip posture FR-013 and SC-010 require - build on it, do not re-litigate it.

**Textual conflict to expect:** 037's `transfer.py` hunk at `@@ -439` and
`038-affix-fidelity`'s at `@@ -442` are ~3 lines apart, both inside `execute()`. In
`categories.py` the two are cleanly separated (037 is entirely `>= L8009`; 038-affix is
L4851-6483), so that file is only a two-way concern.

**Git split (CLAUDE.md protocol):** everything under `specs/` commits to `main`; all code
commits on the `038-transfer-fidelity-gaps` worktree.

---

## Phase 1: Setup

**Wave 1 - independent (different targets):**

- [x] **T001** [P] Create the code worktree `../GramTrans-038-transfer-fidelity-gaps` on a new branch `038-transfer-fidelity-gaps` cut from `main` - `git worktree add ../GramTrans-038-transfer-fidelity-gaps -b 038-transfer-fidelity-gaps main`
- [x] **T002** [P] Verify the flexicon floor and that `flexicon` resolves to the working tree, not site-packages. **The effective floor is `pyflexicon>=4.5.0`, not the `>=4.4.1` plan.md and quickstart.md document** - 037 raised it for `NaturalClassOperations.GetSyncableProperties` / `ApplySyncableProperties` `FeaturesOA` wiring (flexicon issue #222), and that bump arrives with the T005 rebase. Verify against 4.5.0 and note the discrepancy; do not edit `pyproject.toml` or `CLAUDE.md` to reconcile it - both are claimed by 037. A too-low floor makes every `guid=` raise `TypeError`, which `_safe` swallows into a generic drop. Record both command outputs in the task journal - `specs/038-transfer-fidelity-gaps/quickstart.md` (prerequisites block)
- [x] **T003** [P] Create the census output directory and confirm it is git-ignored so artifacts never land in a commit - `scratchpad/038_census/`

**--> Wait for Wave 1 to finish, then:**

- [x] **T004** Acquire `lockout` claims for team `transfer-fidelity-gaps-038` on the **main-worktree** paths of `src/gramtrans/Lib/{categories.py,transfer.py,models.py,report.py,preview.py}`, and run `lockout status --file` against 037's absolute worktree paths to confirm no live conflict. Record that 037's claims are path-scoped to its own worktree and therefore cannot collide by path - `~/.claude/skills/lockout/lockout.py`

**--> Wait for T004 (never rebase an unclaimed hazard file), then:**

- [x] **T005** Land-order rebase (R6): merge `037-phon-nc-features`, then `038-affix-fidelity`, into `038-transfer-fidelity-gaps`, resolving the `transfer.py` collision between 037's `@@ -439` and 038-affix's `@@ -442` inside `execute()`. Confirm afterwards that `RunReport.leaf_execution_failures` / `leaf_failed` and 038-affix's `_strip_ref_fields` are both present - `src/gramtrans/Lib/transfer.py`, `src/gramtrans/Lib/models.py`, `src/gramtrans/Lib/report.py`

**--> Wait for T005, then:**

- [x] **T006** Run the existing suite on the rebased branch to establish a green baseline before any 038 edit; record the pass count - `tests/`

---

## Phase 2: Foundational (BLOCKS every user story)

Shared types, the single roster accessor, and the closure registry landing empty. No story
work begins until this phase is done. Every new dataclass is `frozen=True` and imports no
LCM type (Principle II, data-model.md:3-6).

**Wave 1 - single task (`models.py`, identity types):**

- [x] **T007** [US1] Add `MatchBasis` enum (`IDENTITY`, `NATURAL_KEY`, `NONE`), `MatchBasisRecord` (`basis`, `object_class`, `key_expression`, `key_value`, `source_guid`, `target_guid` empty iff `NONE`, `candidate_count`), and `NaturalKeyRosterEntry` as a read-only projection of one roster `entries[]` object plus 038's `key_fn_id` / `scope_fn_id`. Extend `SkipReason` (:208) with `NOT_REPRODUCIBLE` and `DEPENDENCY_DESELECTED`, and narrow `ALREADY_PRESENT_BY_GUID` to post-field-identity-comparison only (defect G3) - `src/gramtrans/Lib/models.py`

**--> Wait for T007 (same file), then:**

- [x] **T008** Extend the plan/report carriers: `PlannedAction.match_basis` (:609); `PlannedOverwrite.match_via` gains `"natural_key"` (:689) plus `match_basis` and `enrichment` (:666); `RunPlan` (:716) gains `closure_edges`, `incompleteness`, `enrichments`, `process_rules`, all `tuple = ()` so existing snapshots stay valid; `CategoryReport` (:1382) gains `identity_substitution`, `enriched`, `not_reproducible` as `int = 0`; `RunReport` gains the four tuples plus `census`. Follow 037's additive-tuple + derived-`@property` pattern (`dropped_items`, `leaf_execution_failures`, `leaf_failed`) rather than a parallel channel. Extend the `__post_init__` accounting invariant to the new buckets - `src/gramtrans/Lib/models.py`

**--> Wait for Wave 2, then (different files, no shared state):**

- [x] **T009** [P] [US1] Add the **single** roster accessor (R1): load `specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json`, project each entry to `NaturalKeyRosterEntry`, and return "no natural-key basis" for any class absent from the file, so the engine degrades to GUID-only and this feature lands green before 035's append. An off-roster class that nonetheless reaches the natural-key step is a **harness error naming the class**. Never hard-code a key - `src/gramtrans/Lib/matcher.py`
- [x] **T010** [P] [US3] Add the `CLOSURE_EDGES_VERIFIED` registry, **landing empty**, and the callable handed to `closure.walk` that consults only registered producers and returns `()` for every unregistered one (R3 - one global flag cannot satisfy FR-018). While here, reconcile the producer-count drift: research.md says 24 `*_dependencies(piece)` producers, the file has 23 - correct whichever is wrong and say which - `src/gramtrans/Lib/categories.py`
- [x] **T011** [P] Add the report surfaces for the new buckets: machine-readable alongside `to_snapshot_json` (:248), human-readable alongside `render_text_summary` (:258). Console truncation is legal only if it states how many items it omitted; the artifact is never truncated - `src/gramtrans/Lib/report.py`

**--> Wait for Wave 3, then:**

- [x] **T012** [US3] Wire `build_run_plan` (:114) to `closure.walk` then `closure.topological`, materialising `(visit_order, pulled_in_by)` into `ClosureEdge`. With the registry empty this is a **no-op by construction** - assert that in the test. `build_run_plan` MUST **raise** on any edge whose `verified is False` rather than plan from it (FR-018, data-model.md:142-144) - `src/gramtrans/Lib/preview.py`

**--> Wait for T012, then:**

- [x] **T013** Unit tests for the foundational layer: every new dataclass rejects its invalid states; the roster accessor returns no-basis for an absent class and raises for an off-roster class reaching step 2; `build_run_plan` raises on an unverified edge; the empty registry changes no existing plan - `tests/unit/test_038_foundational.py`

**Checkpoint**: shared types exist, the roster accessor degrades safely, closure is wired but inert. No behaviour has changed yet and the suite is green.

---

## Phase 3: US2 - The run report tells the truth about what moved (P2, runs first)

**Goal**: a per-class source/destination comparison with a machine-readable gate artifact, so every later slice is accepted by a census diff rather than by a unit test.

**Independent Test**: run the comparison against a completed transfer and confirm the reported per-class figures match the projects. Delivers value alone - a person can see what a transfer lost with no other fix in place.

### Tests

- [x] **T014** [US2] Write the gate test first, failing: validate the artifact against `contracts/census-artifact.schema.json`, assert phase predicates P1..P5, and assert that a **missing or stale baseline is a failing verdict, not a warning** - there must be no path on which an absent baseline yields exit 0 - `tests/integration/test_object_census.py`

### Implementation

**Wave 1 - single task (`models.py`):**

- [x] **T015** [US2] Add `StarterBaseline` (`schema_version`, `flex_version`, `captured_at`, `captured_from`, `entries`, `content_hash`), `StarterBaselineEntry` (`object_class`, `count`, `names`), `ClassCensusRow` (`object_class`, `source_count`, `destination_count`, `starter_excluded`, `difference`, `explained`, `reasons`, `engine_can_create`, `out_of_scope`) and `FidelityCensus` (`run_id`, `source_project`, `destination_project`, `baseline`, `rows`, `taken_at`, `gate_pass`) - `src/gramtrans/Lib/models.py`

**--> Wait for T015, then (T016-T020 all touch `census.py`, so each is its own wave):**

- [x] **T016** [US2] Create the census engine's class-list loader: parse `specs/035-fullsweep-fidelity/object-inventory.md` TABLE 1 + TABLE 2 **at run time** and assert set equality against `coverage-floor.json` `in_scope_classes` (69) union `excluded_not_measurable` (2: `MoForm`, `MoMorphSynAnalysis`) = **71** (CP-1 as the contract states it, `fidelity-census.md:118-121`; mismatch is `COVERAGE_INCOMPLETE` naming the classes). **AMENDED 2026-08-19:** this clause previously read "plus `class_list_provenance.census_additions` (3) = 72", which is unsatisfiable -- all three additions are provably absent from TABLE 1 and TABLE 2 (`MoAffixProcess` zero matches in the document, `PhCode` only in TABLE 3 at :202, `CmTranslation` in TABLE 2 only as the column-3 owning field `CmTranslation.TypeRA` at :150), and their absence is precisely why the additions ledger exists. The 72 remains asserted, separately, as the **cardinality** check `required_count == 72` per `fidelity-census.md:145` -- so no class can go silently unmeasured. Emit exactly one row per class with `len(classes) == required_class_count` (CP-2); mark `LexRefType`, `LexAppendix`, `PhBdryMarker` as `gate_scope: advisory` (CP-3); a class appearing in both floor and additions is `COVERAGE_INCOMPLETE` (CP-4). `MoForm` / `MoMorphSynAnalysis` are `NOT_EVALUATED` / `ABSENT_BY_CONSTRUCTION`; `CmAnthroItem` is `NOT_EVALUATED` / `OUT_OF_SCOPE_CLASS` - `src/gramtrans/Lib/census.py`
- [x] **T017** [US2] Add the read-only counting pass: open both projects read-only, enumerate each class **once** (no per-object re-query), and assert `opened_read_only` is `const: true` and `fwdata_sha256_before == fwdata_sha256_after` for both projects, else `CENSUS_ERROR`. `unmeasurable` / `unresolved_accessors` must exist as real outcomes because `tests/integration/harness/full_run.py:230` silently swallows a missing accessor - `src/gramtrans/Lib/census.py`
- [x] **T018** [US2] Add per-class duplicate-natural-key grouping producing `duplicates.extra_objects`, and split the `FsFeatStrucType` row **by owning feature system** (`LangProject.MsFeatureSystemOA` vs `LangProject.PhFeatureSystemOA`), each part evaluated independently (Amendment A1, fidelity-census.md:650-673). A single summed count is ambiguous. Accounting change only - the 72-class count is unaffected - `src/gramtrans/Lib/census.py`
- [x] **T019** [US2] Add the accounting arithmetic: `unmatched_starter = starter_baseline_count - starter_matched_to_source`; `destination_count_net = destination_count_total - unmatched_starter`; `difference = destination_count_net - source_count` (negative SHORTFALL, zero MATCHED, positive SURPLUS). **No cross-class netting, ever.** Add the match-basis invariant `identity + natural_key + created_new + unmatched_reported == source_count` with `enriched` excluded - a mismatch is a FAIL - `src/gramtrans/Lib/census.py`
- [x] **T020** [US2] Add the closed **16-token** reason vocabulary (no `UNEXPLAINED`, no `OTHER`; only `STARTER_CONTENT`, `ABSENT_BY_CONSTRUCTION`, `OUT_OF_SCOPE_CLASS`, `GOVERNED_BY_OTHER_FEATURE` need no `report_ref`), the nine verdict tokens with their exit codes, and the **published severity ordering**, which is not derived from the exit integer: `CENSUS_ERROR > COVERAGE_INCOMPLETE > BASELINE_MISSING > BASELINE_STALE > DUPLICATE_IDENTITY > UNEXPLAINED_SHORTFALL > UNEXPLAINED_SURPLUS > CENSUS_ACCOUNTED > CENSUS_CLEAN`. Implement fail triggers R-1..R-5 and the 11 validator invariants. PASS iff the verdict is `CENSUS_CLEAN` or `CENSUS_ACCOUNTED`; a row passes only when **both** `difference == 0` (or every unit accounted) **and** `duplicates.extra_objects == 0` (or each group accounted) - `src/gramtrans/Lib/census.py`

**--> Wait for the census engine, then (different files):**

- [x] **T021** [P] [US2] Add the CLI with the four subcommands `capture-baseline` / `run` / `gate` / `diff` and the quickstart flag surface, invoked as `python -m gramtrans.census_cli`. **Resolve the recorded artifact conflict in favour of R2 for location and quickstart for surface**: R2 (binding, research.md:76-83) puts the instrument in `Lib/census.py` + `census_cli.py` and explicitly rejects `debug/audit_object_census.py` because "a release gate cannot live in unsupported scratch" (SC-009), while quickstart still names the `debug/` script. Use `--destination`, not R2's `--target`, because "destination" is the schema and contract vocabulary throughout. **No `pyproject.toml` change** - that file is claimed by 037 - `src/gramtrans/census_cli.py`
- [x] **T022** [P] [US2] Attach the census to the run report: machine-readable next to `to_snapshot_json`, human-readable table next to `render_text_summary` - `src/gramtrans/Lib/report.py`

**--> Wait for T021, then:**

- [x] **T023a** [US2] Implement `fidelity-census.md` 5.2's **gross-basis verdict cap**: when `starter_subtraction_basis` is `baseline_gross` (which a count-only baseline forces, per `census-artifact.schema.json:337`), the verdict is capped at `CENSUS_ACCOUNTED` and can never be `UNEXPLAINED_SHORTFALL`/`UNEXPLAINED_SURPLUS`. **Without this a CORRECT transfer reports `UNEXPLAINED_SHORTFALL`** -- the contract's own 43-23=20 example -- so every real starter baseline produces a false failure. Added 2026-08-19 from T021's finding 3; the cap belongs in `recompute_verdict` (one verdict source), never in the CLI - `src/gramtrans/Lib/census.py`

- [x] **T023** [US2] Capture `starter-baseline.json` from a **genuinely blank** FieldWorks project - it cannot be authored by inspection. Assert the stamped `flex_version` matches the running host and the class count is present. **AMENDED 2026-08-19:** this task previously asserted `carries_natural_keys` is `true`. That is unsatisfiable and the assertion is wrong: a genuinely blank FieldWorks project holds objects in 36 classes, **11 of which carry no name at all** (`CmDomainQ` 7938, `StTxtPara` 86, `PhCode` 25, `CmRow`, `CmCell`, `CmAgentEvaluation`, `DsDiscourseData`, `LangProject`, `MoMorphData`, `PhPhonData`, `StText`), so no whole-project baseline can record a natural key for every starter object. Per `census-artifact.schema.json:337` a count-only baseline is a **legal, designed state** that forces `starter_subtraction_basis: baseline_gross`. Assert instead that `carries_natural_keys` is recorded **truthfully** and that the artifact declares the gross basis whenever it is `false`. This makes the 5.2 gross-basis verdict cap load-bearing -- see T023a **Commits to `main`**, not the worktree - `specs/038-transfer-fidelity-gaps/contracts/starter-baseline.json`
- [x] **T023b** [US2] **Count the EXACT class, not the polymorphic subtree.** `census.objects_in_class` counts via `handle.ObjectsIn(I<Class>Repository)`, and LCM's `AllInstances()` includes subclasses, so the 74 rows are **not disjoint**: measured on the blank starter, `CmPossibility` reports 3014 against 302 own objects (3014 = 302 + 1792 `CmSemanticDomain` + 859 `CmAnthroItem` + 19 `MoMorphType` + 5 `PartOfSpeech` + 11 `LexEntryType` + 3 `LexEntryInflType` + 7 `LexRefType` + 15 `CmAnnotationDefn` + 1 `CmPerson`, i.e. the whole subtree to the object), and `LexEntryType` reports 14 against 11 own (+3 `LexEntryInflType`). A single `PartOfSpeech` object is therefore counted in both its own row and `CmPossibility`'s, the emitted object total double-counts, and a per-class `difference` is ambiguous for any class with subclasses -- which also makes the match-basis invariant `identity + natural_key + created_new + unmatched_reported == source_count` run against a polymorphic `source_count`. Filter to exact class (`ClassName`/`ClassID` equality) so each object lands in exactly one row, document the polymorphism where the counting happens, and **recapture `starter-baseline.json`** because its `CmPossibility`/`LexEntryType` counts are inflated. Leaf classes (`MoStemMsa`, `PhPhoneme`, `MoAffixAllomorph`) are unaffected, so T024's sanity pairs still hold. Added 2026-08-19 from T023's live capture - `src/gramtrans/Lib/census.py`

- [x] **T023c** [US2] **Render artifact `notes` to the console.** T023a made the 5.2 verdict cap visible in the JSON artifact (`notes`, plus the public `gross_basis_cap_notes()`), but neither `Lib/report.py` nor `census_cli.py` renders `notes` at all -- so in the printed summary a capped `CENSUS_ACCOUNTED`/exit 0 is indistinguishable from a genuinely clean run, which is exactly the silence the cap's `[WARN]` text exists to prevent. Surface them beside `report.py`'s existing `[INFO] ... FLOOR` line (`report.py:1481-1487`) and in the CLI's `run`/`gate` output. `notes` stays **non-load-bearing** (invariant 9): the cap keys off `starter_subtraction_basis`, never off a note, and a hand-written note must not be able to buy a cap - `src/gramtrans/Lib/report.py`, `src/gramtrans/census_cli.py`

- [x] **T024** [US2] **REOPENED 2026-08-19 -- see T024c: the live half of this task does not measure a transfer.** The hermetic assertions stand; the two live pairs do not. Sanity-check the instrument before trusting any green result: it must reproduce the known-bad pairs; a census that reports them clean is itself broken. **PREMISES CORRECTED 2026-08-19 against live measurement:** (a) the `MoStemMsa` 1949->0 source is **`Ngoreme FLEx`**, NOT `Ngoreme` -- `Ngoreme` holds 1945 / `PhPhoneme` 37, while `Ngoreme FLEx` holds exactly 1949 / 41; (b) `MoInflAffixTemplate` 8->0 / `MoInflAffixSlot` 11->0 is the **Ejagham** pair (`Ejagham W Mini` -> `Ejagham W Target`), while the Ngoreme pair loses 13 and 19; (c) **`MoAffixAllomorph` +13 is NOT REPRODUCIBLE** -- no project on this machine holds 143 allomorphs, and `Ejagham W Target` lost both classes outright (130->0 and 13->0). The conversion signature IS reproducible at scale 1 on the Ngoreme pair: `MoAffixProcess` 1->0 beside `MoAffixAllomorph` 146->147 (surplus +1, baseline 0), both halves in one artifact and not netted -- assert that instead, and do not manufacture the +13; (d) `PhPhoneme` 41->64 verified exactly (dest_total 64, baseline 23, net 41, difference 0, `MATCHED`, `difference_raw` +23); (e) the duplicate assertion must be **phase-1 unsatisfied, NOT `DUPLICATE_IDENTITY`** -- see T024a - `tests/integration/test_object_census.py`
- [x] **T024a** [US2] **Duplicate detection is inert for `PhPhoneme` until T028 lands.** Measured live: a destination holding 21 duplicate phoneme names reports `totals.duplicate_extra_objects` **0** and never raises `DUPLICATE_IDENTITY`. This is by design, not a bug -- `PhPhoneme` is absent from 035's roster (admitted: `WfiWordform`, `ReversalIndex`, `ReversalIndexEntry`), so `duplicates.roster_admitted` is `False` and `duplicates_unaccounted()` returns 0; `contracts/natural-key-roster-extension.json` still holds **zero entries** because T028 has not populated it. The loss is caught instead by `_phase_1`'s dedicated PhPhoneme check (`census.py:3582`) with the SC-002 wording "baseline arithmetic alone would have passed this row". Record this dependency explicitly so nobody reads a 0 as absence of duplicates, and re-run T024's duplicate assertions once T028 appends the six roster entries - `tests/integration/test_object_census.py`

- [x] **T024b** [US2] **DONE 2026-08-19 (worktree `fe16eea`). The user chose "distinct non-zero exit code".** A capped pass now exits `census_cli.CAPPED_PASS_EXIT_CODE` and prints `[CAPPED -- advisory, not a pass]`, so exit 0 means "nothing was lost" and nothing else. Two corrections to the sketch: (a) the code is **8, not 3** -- codes 0-7 are all spoken for by section 9's verdict table (3 is `DUPLICATE_IDENTITY`) and a non-verdict outcome must never borrow a verdict's code; (b) it keys off `census.gross_basis_suppressions`, NOT off the basis -- a gross-basis run that suppressed nothing hid nothing, and flipping it to non-zero would cry wolf on every honest run. The verdict TOKEN is unchanged (the artifact is `additionalProperties: false`; inventing a tenth token is forbidden), so this is a property of the process outcome, not of the document. Two T023c tests asserted the old exit 0 and were updated; `test_the_capped_exit_code_is_not_a_verdict_code` pins the no-collision rule. ORIGINAL FINDING: **`census gate` must not return a bare exit 0 on the gross basis.** Measured live: both sanity pairs reported `CENSUS_ACCOUNTED` / **exit 0** / `passed=True` while carrying **44-47 failing rows and 74,157 units of unexplained shortfall**. That is the 5.2 cap behaving as specified, and it is still an unsafe default for a release gate -- the headline says success on a catastrophically incomplete transfer, and the failing evidence surfaces only via `--phase`. Either require `--phase` for a passing gate, or make a gross-basis pass a distinct non-success outcome, so no caller can read exit 0 as "nothing was lost". `evaluate_phase(1)`/`(5)` already fail correctly and name `MoStemMsa` and `MoAffixProcess`, so the information exists; the default is what is wrong - `src/gramtrans/census_cli.py`

- [x] **T024c** [US2] **T024's live pairs never run a transfer -- so they cannot sanity-check one.** Raised by the user 2026-08-19. `_t024_census` (`test_object_census.py:2297`) censuses two projects **as they happen to sit on disk**: it invokes `cli_exit(["run", "--source", ..., "--destination", ..., "--baseline", <starter>, "--destination-freshly-created"])` and nothing anywhere in the 3702-line file restores a target or executes a transfer (`transfer_run` appears only inside the synthetic `make_artifact` fixtures). **CORRECTED against measurement, 2026-08-19:** an earlier draft of this task claimed the `--destination-freshly-created` declaration was false for `Ngoreme Target` and therefore `CENSUS_ERROR` per 5.1. **It is not.** `backups/Ngoreme Target 2026-08-19 0831.fwbackup` (main worktree; `backups/` is not shared across worktrees, which is why the first sweep missed it) holds LexEntry 0, LexSense 0, MoStemMsa 0, **PhPhoneme 23**, PartOfSpeech 5 -- a genuinely blank starter. The target WAS restored fresh at 08:31 and the live 10.3 MB `.fwdata` at 09:30 IS the result of a real transfer run this morning. `census.baseline_misdeclared` (`census.py:2910`) tests only whether the operator *declared* freshness, not whether the destination is empty at census time, so the declaration was truthful and the check correctly passes. What remains wrong is narrower and still disqualifying:
  1. **The pairing is an uncaptured convention, not an enforced one.** The test asserts fixed numbers against a destination whose provenance lives only in a session log. Nothing binds `Ngoreme Target`'s 09:30 state to `Ngoreme FLEx`; touch either project and the suite measures a different, equally unattributable delta while still claiming to be a sanity check. A sanity check for an instrument that gates transfers must itself produce the transfer.
  2. **A `pre_transfer_census` is still the right baseline, but it does NOT lift the 5.2 cap -- see T024d.** An earlier draft of this task claimed it did. It does not: `starter_subtraction_basis` is emitted as `baseline_gross` unconditionally (`census_cli.py:688`), independent of baseline kind. The exact baseline is worth having anyway -- it makes `starter_baseline_count` measured rather than modelled -- but the cap survives it.
  3. **`--run-report` does not currently account for scope either -- see T024d.** GramTrans transfers GRAMMAR; `LexEntry`, `LexSense`, `Text` and `Segment` are out of scope by design, and an earlier draft claimed passing the run report moves them into `accounted_for`. It does not: `transfer_run_block` (`census_cli.py:661`) reads only `run_id`, `mode`, `started_at` and `selected_categories` into a provenance block. No per-class tally is read, so the out-of-scope lexicon classes stay in `unexplained_shortfall`.

  **The corrected shape, which the code already supports end to end:** `harness/restore.py::restore_target("Ngoreme Target", <0831 backup>)` -> `census run --pre-transfer --destination "Ngoreme Target" --out pre.json` (`census_cli.py:1281`) -> `harness/full_run.py::run_full_transfer` with `build_full_selection(exclude=frozenset())` (the default excludes `STEMS`; a FULL copy must not) -> persist the `RunReport` -> `census run --source "Ngoreme FLEx" --destination "Ngoreme Target" --baseline pre.json --run-report report.json --out post.json`. The meaningful delta is then the rows with `difference != 0` that the run report does NOT account for. Reproducible from a backup, attributable to one named run, and exact. Keep the starter-capture baseline work (T023/T023b): knowing what ships with a blank project stays independently useful and is the right basis for a genuinely fresh destination -- it is just not a substitute for measuring the destination you are about to write to - `tests/integration/test_object_census.py`, `tests/integration/harness/`

- [x] **T024d** [US2] **DONE 2026-08-19 (worktree `fe16eea`), both halves.** **T024d-a** (`Lib/models.py`, `Lib/report.py`): `RunReport.matched_by_class` (keyed by LCM object class) + `matches_unattributed` (keyed by category) + `matched_to_source_total` / `matched_class_is_complete`, produced in `build_from_plan` and surfaced additively as `matched_to_source` in the snapshot (omit-when-empty, so a run with no matches is byte-identical). Attribution reads ONLY the two authoritative class names -- `MatchBasisRecord.object_class` and `EnrichmentRecord.object_class` -- and routes everything else to the unattributed bucket rather than guessing through the non-1:1 category->class mapping. **T024d-b** (`census_cli.py`): `matched_by_class_from_report` + `_row_for_entry` now earns `baseline_matched` per row when there is a baseline count, a tally for THAT class, and complete attribution; `starter_excluded` then becomes `unmatched_starter`. Verified on 5.2's own worked example: a blank target shipping 23 starter phonemes with the destination at 41 reported `difference` **-23** on the gross basis and reports **0** on the matched basis. Conservative by design -- an absent class is no evidence (never a zero), any unattributed match spoils completeness for every class, and A1 split rows never reach the matched basis. Note the sequencing premise below still holds for T024c, which remains open. ORIGINAL FINDING: Found 2026-08-19 while designing T024c's live rebuild; this is the root cause behind T024b and the reason a "meaningful delta" is not obtainable today. `census.py` supports the basis completely -- it is in `SUBTRACTION_BASES` (`census.py:2022`), `unmatched_starter()` computes from `starter_matched_to_source` (`census.py:2142`), invariant checking special-cases it (`census.py:3018`), the 5.2 cap skips rows carrying it (`gross_basis_suppressions`, `census.py:3240`), and phase evaluation treats its shortfalls as trustworthy (`census.py:3402`). But the only emitter, `_row_for_entry`, hardcodes `basis = "baseline_gross"` on every path that has a baseline, and its own docstring concedes it: *"THE SUBTRACTION BASIS IS NEVER `baseline_matched` HERE ... reading per-class matched tallies out of a run report is T022's seam, not this one's"* (`census_cli.py:688`). **T022 is marked `[x]` and did not do this** -- it attached the census to the run report, not the run report to the census. Consequences:
  1. **Every census on this instrument is advisory, always.** The run verdict is structurally incapable of exceeding `CENSUS_ACCOUNTED`, regardless of baseline kind, run report, or how correct the transfer was. `CENSUS_CLEAN` is unreachable on any real pair.
  2. **The cap's own remediation advice is unfollowable.** `gross_basis_cap_notes` prints *"supply the run report to get a baseline_matched basis and a trustworthy answer"* (`census.py:3297`). Supplying the run report does not produce that basis. The instrument tells the operator to do the one thing that cannot help.
  3. **It mis-reports CORRECT runs, which is the failure mode 5.2 exists to name.** On a target restored blank (`PhPhoneme` starter 23), a transfer that correctly matches all 23 starter phonemes to source phonemes lands the destination at 41. Gross subtraction gives 41 - 23 = 18 and reports `difference` **-23** -- a 23-unit shortfall on a lossless run. Until the matched tally is read, "meaningful delta" cannot be separated from baseline arithmetic.

  **The work:** read per-class identity-substitution / matched counts out of the `RunReport` snapshot in `transfer_run_block`, thread them into `_row_for_entry` as `starter_matched_to_source`, and emit `basis = "baseline_matched"` for rows the report covers. Everything downstream already handles it. **CONFIRMED 2026-08-19: it splits.** `RunReport` does carry substitution tallies -- `CategoryReport.identity_substitution` (`models.py:2651`), summed by `RunReport.identity_substituted` (`models.py:2759`) -- but they are keyed by **`GrammarCategory`**, while every census row is keyed by **LCM object class**. `per_category[PHONEMES].identity_substitution` cannot be attributed to `PhPhoneme` without a category->class mapping, and the mapping is not 1:1 for the affix and MSA categories. So T024d-a is a `report.py` change (tally substitutions per object class, not merely per category) and T024d-b is the `census_cli.py` wiring that consumes it. Do NOT attempt the wiring first: without per-class tallies there is nothing to wire. Sequence T024d BEFORE T024c's live rebuild: running the full-copy simulation without it produces the same capped, uninterpretable exit 0 the rebuild exists to eliminate - `src/gramtrans/census_cli.py`, `src/gramtrans/Lib/report.py`

- [x] **T024e** [US2] **Test the two selection modes -- default PRESELECTION vs force-all -- and pin their difference exactly.** Raised by the user 2026-08-19: with everything selected, some items are deliberately NOT preselected on the assumption they are not needed, and both modes need programmatic testing. **CORRECTED: an earlier draft of this task answered the wrong question** -- it described `_phon_is_empty`, the inventory-level blank drop, and proposed adding a `Selection` switch and a `DroppedItemRecord` channel before the two-mode test could run. That is a different, smaller mechanism (see T024f) and **none of that work is required here.** Both modes are constructible today from existing public functions:
  * **Force-all** is `build_full_selection(exclude=frozenset())`. `collapse_phonology` (`selection.py:2848`) records `leaf_item_picks[cat]` *"ONLY when the category is trimmed ... omitted when all rows are checked (=> transfer-all)"*, so leaving every pick-set empty means transfer-all and the preselection heuristics are bypassed entirely. This is what `debug/run_fullcopy_sweep.py` already runs.
  * **Default/filtered** is what the GUI produces: build the inventory, take `checked = {r.guid for r in group.rows if r.preselected}` per category, and fold it through `collapse_phonology(inventory, checked)` into the Selection. No new API.

  **The two heuristics that leave enumerated items unchecked:**
  1. **Orphan natural classes** (`selection.py:2687`, applied at `:2832` as `replace(r, preselected=(r.guid not in orphan_nc_guids))`). FLEx auto-creates a fresh *"Created automatically for rule X"* NC every time a rule's context is re-saved and strands the previous copy, so a source accumulates dozens nothing references. Orphan-hood is authoritative LCM `ReferringObjects.Count == 0` via `compute_orphan_nc_guids` -- explicitly NOT a re-walk of rule structure, which misses NC contexts nested in `PhSequenceContext`/`StrucChange` and mislabels every used NC an orphan (live-proven on `Mbugwe LizzieHC practice`).
  2. **AS-NEEDED dependency closure** for slots, templates and POS (`selection.py:1174-1197`, `:1510`, `:1560-1586`). A slot is preselected iff a picked affix fills it, a template iff any referenced slot is filled, a POS iff a picked affix attaches to it. With all affixes picked these preselect transitively; anything no pick reaches opens unchecked.

  **Why this is cheap to test:** a non-preselected item is still ENUMERATED -- `preselected` is a field on the row, not a removal -- so the expected difference between the modes is computable from the inventory BEFORE either run, with no run report and no baseline. `orphan_nc_guids` is also an injectable parameter (`None` = compute from source; tests inject a set), so the heuristic can be disabled without touching production defaults. **The assertion:** run both modes against the same restored-blank target and require `after_forceall - after_filtered` to equal EXACTLY the non-preselected GUID set -- larger means the filtered run dropped something the heuristic never claimed, smaller means force-all is not actually forcing. Both directions are real defects and neither is visible in a count-based census - `tests/integration/`, `src/gramtrans/Lib/selection.py`

- [x] **T024f** [US2] **Separately: the inventory-level blank drop is unconditional and unobservable.** NOT the filter T024e tests -- this one removes items from the inventory entirely rather than leaving them unchecked, so it is invisible to the T024e mode contrast and needs its own handling. `_phon_is_empty` (`selection.py:2436`) is applied at `selection.py:2587` and `:2725`, both a bare `continue` guarded by nothing, and `Selection` carries no field that switches it -- so even force-all drops these. Neither site emits a `DroppedItemRecord`, increments a counter, or appends to any tally; the comments say *"silently skipped from the inventory"* and *"silently skip (FR: dangling)"*. The drop happens BEFORE the plan exists, so the items never reach `RunReport.dropped_items`, the channel 024 built so that nothing drops silently. In a `source - after` comparison a filtered blank is therefore indistinguishable from a real loss. **Not cosmetic:** this predicate decides what transfers and has been wrong twice on `fullcopy-defects` -- `a5772f4` ("content-aware `_phon_is_empty` -- keep items with fields OR children") and `f4e1b83`, which per the predicate's own docstring *"wrongly dropped every unnamed rule -- making it un-previewable AND silently excluding it from transfer"*. Make the two sites record what they skip through the existing `DroppedItemRecord` channel with a distinct reason token. Scope note: the docstring says the motivating case (~32 dangling Ejagham phonemes) is *"no longer reproducible in current live data"*, so on today's corpus this set is probably EMPTY and the T024c comparison is unaffected in practice -- verify that empirically rather than assuming it - `src/gramtrans/Lib/selection.py`

- [x] **T024g** [US2] **FIXED 2026-08-19 (worktree `796640c`); see the RESOLVED section of `two-mode-live-evidence.md`. Root cause: three sites wrote SOURCE writing-system handles into TARGET multistrings (`categories.py:7521`, `categories.py:2225`, `transfer.py:2561`), now routed through the pre-existing `_copy_multistrings_ws_mapped`; a failed CloseProject is no longer a warning. Post-fix the destination goes 11,300 -> 28,354 objects and MoStemMsa/slots/templates arrive complete, which INVALIDATES T024's premise that those were transfer-logic losses.** Original finding: **BLOCKER, highest severity: the full transfer PERSISTS NOTHING and reports success.** Measured live 2026-08-19 -- full evidence in `specs/038-transfer-fidelity-gaps/two-mode-live-evidence.md`, driver `debug/two_mode_delta.py`. Against `Ngoreme FLEx` (119 classes / 205,979 objects) into `Ngoreme Target` restored blank from `backups/Ngoreme Target 2026-08-19 0831.fwbackup`, **three runs** -- forceall, filtered, and forceall with a COMPLETE writing-system mapping -- each left the destination at exactly **11,300 objects, unchanged**, while `RunReport` carried `error: None`, `leaf_failed: 0`, and **2,243 `added` across 19 of 20 categories**. Cause, from the .NET stack: `CloseProject()` -- which `gramtrans.py:282` documents as *"the ONLY disk-write on this path"* -- raises `ArgumentOutOfRangeException` in `WritingSystemManager.Get(Int32 handle)` under `MoInflAffixSlot.ToXMLStringInternal` -> `MultiUnicodeAccessor.ToXml`, inside `XMLBackendProvider.Commit`. One unresolvable WS handle on one slot discards the ENTIRE unit of work. **Production swallows it identically** (`gramtrans.py:302-313`: `except Exception as exc: report.Warning(...)`), so a user sees a warning line beside a report claiming 2,243 additions and a target that did not change. Sub-findings:
  1. **Not an incomplete-mapping artifact.** Run 3 mapped every source WS (`en->en`, `swh->swh` with `create_in_target=True`, `ngq->ngq`) and failed identically.
  2. **WS handles are per-project and NOT portable.** Measured: `999000002` is `en` in `Ngoreme FLEx` and `ngq` in `Ngoreme Target`; `swh` is absent from the target entirely. A handle carried across unchanged either throws (as here) or silently resolves to the WRONG writing system -- the latter is the more dangerous outcome because nothing raises.
  3. **Wrong layer.** Per constitution v5.1.0 Principle III, an unmappable/unresolvable writing system is a PREVIEW-time refusal, not a commit-time throw. Preview returned `PREVIEW_READY`.
  4. **A total rollback must never be a warning.** Whatever the trigger, `execute_move` reporting 2,243 adds over a byte-identical destination is the silent-loss class 038 exists to eliminate. Fix the swallow first -- it is small and it converts every other defect here from silent to loud - `src/gramtrans/gramtrans.py`, `src/gramtrans/Lib/api.py`, `src/gramtrans/Lib/preview.py`

- [x] **T024h** [US2] **Two unexplained tallies from the same live runs**, both needing a breakdown before anything is read as expected: (a) **`dropped_items: 10,749`** on every run -- the never-silent channel is carrying a very large payload against 205,979 source objects and has never been broken down by `owner_kind`/reason; (b) **`identity_substituted: 0`** on every run, against a starter target holding 23 phonemes and 5 POS whose names collide with source objects -- zero substitutions means the natural-key match path did not engage AT ALL, which is either a defect or evidence that FR-006 is unreachable on this pair. Also: the filtered mode reported **`leaf_failed: 1`** where forceall reported 0, unaccounted for by the preselection heuristic (`36 added + 11 unchecked + 1 leaf_failed == 48 forceall added`) - `specs/038-transfer-fidelity-gaps/two-mode-live-evidence.md`

- [x] **T024i** [US2] **DONE 2026-08-19 (worktree `c8a1d7f`). Out-of-band: the census instrument was CORRUPTING the projects it measured.** Reported by the user as an intermittent "Can't add EN writing system". `flexicon.FLExInitialize()` initialises the SLDR via `Sldr.Initialize(True)`; `flexicon.FLExCleanup()` calls `Sldr.Cleanup()` and takes it down again -- both process-global. Every standalone entry point guarded initialisation with a once-per-process boolean latch, which records that we CALLED FLExInitialize, not whether the SLDR is still up. So within one process: init (SLDR up, latch True) -> any `HostSession.release()`/teardown (SLDR **down**, latch still True) -> the next `OpenProject` short-circuits the latch and opens with the SLDR down. LibLCM's LDML-in-folder repository then fails to parse EVERY file in `WritingSystemStore/`, declares each bad, and RENAMES it to `*.ldml.bad` (`Exception: The SLDR has not been initialized.`); once `en.ldml` is gone the project has no English writing system. **A READ-ONLY open is enough** -- `writeEnabled=False` protects the `.fwdata`, not the writing-system store -- and the census opens BOTH projects read-only, so it was one of the paths doing the damage. Measured fallout in one day: **8 files quarantined in `Esperanto`** (documented read-only in the strong sense) and **2 in `Ejagham Full GT-Test`**, leaving neither project a single valid `.ldml`. Verified live: `after ensure_flex_initialized True / after FLExCleanup False / after re-ensure True`. Fix: new `Lib/flexinit.py` owns the discipline -- FLExInitialize stays once-per-process (registry/ICU) but `Sldr.IsInitialized` is re-checked on EVERY call and re-initialised when down, fail-soft throughout -- wired into `Lib/census.py`, `standalone/app.py` (itself the `FLExCleanup` caller), both `gramtrans.py` opens, and `tests/integration/harness/full_run.py`. The quarantined LDML was restored by rename with the user's explicit authorisation, preserving Esperanto's fr/hbo/id tailoring a FieldWorks regeneration would have replaced with defaults; `Esperanto.fwdata` was not touched. `tests/unit/test_flexinit_sldr_guard.py` (6 tests) pins the rule hermetically. **Bearing on this feature:** any census artifact captured before this fix may have been measured against a project whose writing systems were being quarantined mid-run - `src/gramtrans/Lib/flexinit.py`, `src/gramtrans/Lib/census.py`, `src/gramtrans/standalone/app.py`, `src/gramtrans/gramtrans.py`, `tests/integration/harness/full_run.py`

- [x] **T025** [US2] **DONE 2026-08-19.** Update the quickstart to name `python -m gramtrans.census_cli <subcommand>` throughout, drop the `debug/audit_object_census.py` invocations, and clear the `PLANNED` markers T021/T023 have now satisfied. **Commits to `main`**. All five invocations were verified to parse against the shipped `build_parser()` (`capture-baseline`, `run --pre-transfer`, `run`, `gate --phase`, `diff`); no `--target` was reintroduced. Four corrections beyond the rename, each forced by shipped behaviour rather than by preference: (a) step 2.4 demanded `carries_natural_keys == True`, which T023's amendment makes unsatisfiable -- the captured artifact reads `starter_capture False 9.3.10 7000072 72` and a count-only baseline is a legal designed state; (b) section 3 step 2 implied the 5.2 cap was the price of omitting `--run-report`, but `_row_for_entry` hardcodes `baseline_gross` on every baseline path, so the cap applies either way; (c) section 4's `starter_subtraction_basis` entry described `baseline_matched` as reachable when nothing emits it -- now points at T024d; (d) step 1's `--pre-transfer` example passed a `--source` that `_dispatch` ignores. Also documented T023c's notes-above-the-verdict block and T023b's exact-class counting, and added pointers -- NOT fixes -- for T024b (bare exit 0 on the gross basis) and T024/T024c (section 6's sanity figures are under correction) - `specs/038-transfer-fidelity-gaps/quickstart.md`

**Checkpoint**: US2 is independently functional. A person can obtain the per-class comparison for a completed transfer without hand-written scripting (SC-009), the artifact validates against its schema, and the four measured defect pairs are reproduced. Every later phase now has its acceptance instrument.

---

## Phase 4: US1 - Entries keep their grammatical analysis (P1)

**Goal**: identity-first matching with a governed natural-key fallback, so 2,088 MSAs stop vanishing and the starter phoneme inventory stops being duplicated 21 times over.

**Independent Test**: transfer a project containing entries with parts of speech into a freshly created empty FLEx project; count entries with a grammatical analysis in source and target. Delivers value alone - the receiving project has a usable lexicon even if nothing else ships.

**Verify against `Ejagham Mini` -> a freshly created disposable target. Never open `Target`** - 037 holds a live restore-bounded Move on `Projects\Target\Target.fwdata`.

### Tests

- [x] **T026** [US1] Write failing unit tests for the matching order: GUID found -> `IDENTITY`, key never computed, then **enrich rather than whole-object skip**; not found -> compute key; ineligible or not computable -> report, no match, **no create-by-key**; 0 candidates -> FR-007 create GUID-preserving or report; exactly 1 -> reuse plus an IDENTITY-SUBSTITUTION record; more than 1 -> `harness_error` naming class, scope and key. Ambiguity is **never a pick and never an IDENTITY-SUBSTITUTION record** - `tests/unit/test_038_natural_key.py`
- [x] **T027** [US1] Write failing tests for comparison strictness: exact, case-sensitive, **no** Unicode normalisation, **no** case folding, **no** whitespace trimming, for all six classes (`Nasals` / `nasals` / `Nasal Consonants` were measured distinct). An object with no name in the scoped writing system has **no key** and must never match - including empty-key against empty-key - `tests/unit/test_038_natural_key.py`

### Implementation

**Wave 1 - single blocking gate:**

- [x] **T028** [US1] Execute the roster coordination protocol (roster-extension.md:411-481). 038 has already committed the proposal; the remaining steps are 035's: claim the roster file as team `fullsweep-fidelity-035`, pull `main`, **APPEND** the six `proposed_entries` objects verbatim and in order to the **end** of `entries`, record the seven op ids under a `live_confirmation_038` sibling key, re-run 035's roster checks, commit to `main`, release the claim. `schema_version` stays 1 and the original three entries stay byte-identical. **Expect one breakage: any 035 test pinning the roster to exactly three entries.** 038 must **not** begin the matching code below until the six entries are visible on `main` (`coordination.step_6`). If 035 rejects an entry, 038 implements no natural-key matching for that class and falls back to FR-007/FR-013 - `specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json`

**--> Wait for T028 (hard gate), then (different files):**

- [x] **T029** [P] [US1] Implement the six key functions and scope predicates behind `key_fn_id` / `scope_fn_id`, each naming **its own writing system**, because the WS differs by class in opposite directions: `PhPhoneme` -> exact `Name` in the **default vernacular** (97/97; analysis only 44/97), never a secondary WS, and the key is not computable unless the pre-run WS mapping mapped source->target default vernacular; `PhNCSegments`, `PhNCFeatures`, `PartOfSpeech`, `MoMorphType`, `LexEntryInflType` -> exact `Name` in the **default analysis** WS. `PhCode` is explicitly not the phoneme key - `src/gramtrans/Lib/matcher.py`
- [x] **T030** [P] [US1] Implement the per-class eligibility rules: `PhNCSegments` and `PhNCFeatures` are **subclass-restricted** (never match segment-based to feature-based); `PhNCFeatures` names matching `Created automatically for rule "<rule name>"` are **ineligible, decided before candidate counting** so it is not even an ambiguity - report them under a named, counted outcome and leave them to the owning rule's transfer (66/113 collisions, 47 distinct auto-labels that would otherwise slip through the ambiguity rule); `PartOfSpeech` keys project-wide over the recursive hierarchy with the **owning parent not part of the key** (`093264d7-...` "Demonstrative" is depth-1 in one project, depth-2 in another) - record the parent, report divergence, and **never re-parent the destination**; `MoMorphType` **must not create** on an unmatched key - report and skip, never mint, and treat any nonzero IDENTITY-SUBSTITUTION count as a review signal; `LexEntryInflType` is subclass-restricted against `LexEntryType`, its parent divergence is a reportable anomaly (14/15 under `Irregularly Inflected Form`), and here **creating a missing type IS correct** (FR-007, GUID-preserving) - `src/gramtrans/Lib/matcher.py`

**--> Wait for Wave 2, then (plan-time first - Principle III):**

- [x] **T031** [US1] Compute the whole match decision in the plan builder so Preview and Move agree by construction: both step 1 (GUID) and step 2 (key) run here, each producing a `MatchBasisRecord` on the `PlannedAction` / `PlannedOverwrite`. Nothing about matching may be computed only in the executor - `src/gramtrans/Lib/preview.py`

**--> Wait for T031, then (T032-T035 all touch `categories.py` - the file every branch touches - so they run serially):**

- [x] **T032** [US1] Give `_resolve_target_pos` (:3864) the FR-002 natural-key fallback after identity. This is the `None`-returns-and-caller-abandons path that lost all 2,088 MSAs - `src/gramtrans/Lib/categories.py`
- [x] **T033** [US1] Sweep all eight `_resolve_target_pos` call sites (:1452, :2060, :3994, :4141, :4195, :6397, :7406, :7553) and convert every silent abandon into report-or-match. FR-007 forbids dropping the item's analysis silently; an unmatchable category is created or reported, never dropped - `src/gramtrans/Lib/categories.py`
- [x] **T034** [US1] Register the **`FsFeatStrucType` closure edge** - a hard Phase 1 prerequisite, not report-only (R7). `feature_struct_types_dependencies` currently returns `()` at :1522-1525; make it return the edge MSA/POS -> the `FsFeatStrucType` named by `FsFeatStruc.TypeRA`, plus MSA/POS -> the `FsClosedFeature` / `FsSymFeatVal` its `FeatureSpecsOC` references. Do the same for the `phon_feat_types_*` twin, and **walk both feature systems** (`MsFeatureSystemOA` and `PhFeatureSystemOA`), since `IFsFeatStrucType` is owned only by `IFsFeatureSystem.TypesOC`. **No new create code**: `feature_struct_types_*` (:1507-1735), `phon_feat_types_*` (:1738-1900) and `inflection_features_*` (:488-946) already create GUID-preserved at :1631, :1864 and :719, and all 13 `Fs*` factories report `Create(Guid guid)`. Without the types present, the ~2,083 restored MSAs each carry an unsatisfiable `TypeRA`, which Principle I forbids - `src/gramtrans/Lib/categories.py`
- [x] **T035** [US1] Honour the pythonnet trap wherever an `Fs*` object is created: the **interfaces** declare `Create(Guid, owner)`, which pythonnet cannot bind. Call the **concrete** factory's 1-arg `Create(Guid)` and **then** `Add()` to the owning collection, in that order. flexicon's `InflectionFeatureOperations.TypeCreate` (:621) and `FeatureCreate` (:1062) are unusable here - they mint fresh GUIDs - `src/gramtrans/Lib/categories.py`

**--> Wait for the `categories.py` chain, then (different files):**

- [x] **T036** [P] [US1] Make the executor a resolve-or-create path consuming the plan's `match_basis` - one path, not the two opposite failure modes (create-anyway duplicating starter content, resolve-only dropping the analysis). The executor adds no matching logic of its own - `src/gramtrans/Lib/transfer.py`
- [x] **T037** [P] [US1] Report every natural-key match as such, distinguishable from an identity match (FR-006), and feed `CategoryReport.identity_substitution` - `src/gramtrans/Lib/report.py`

**--> Wait for Wave 5, then:**

- [ ] **T038** [US1] Run the census gate for **predicate P1**: `MoStemMsa`, `MoInflAffMsa`, `MoDerivAffMsa`, `MoUnclassifiedAffixMsa` and `PartOfSpeech` all MATCHED **and** `PhPhoneme.duplicates.extra_objects == 0`, exit code 0. Both halves are required - counts alone would pass the single worst measured outcome, since `PhPhoneme` 41->64 against a 23-phoneme starter baseline nets to zero - `tests/integration/test_object_census.py`
- [ ] **T039** [US1] Verify SC-008 idempotence mechanically: on run 2, `RunPlan.actions` contains **zero** `PlannedAction` whose `match_basis.basis is MatchBasis.NONE` for any class run 1 created, every class's `destination_count_total` is unchanged, and every `EnrichedCollection.added == 0` with `already_present` equal to run 1's `added`. Any increase is a duplicate-creation defect **regardless of what either census's own verdict says** - `tests/integration/test_object_census.py`

**Checkpoint**: US1 is independently functional. SC-001 (analyses 0% -> 100%), SC-002 (no duplicate phoneme names) and SC-008 (a re-run adds nothing) hold on the measured pair, proven by a census exit 0 rather than by unit tests alone.

---

## Phase 5: US4 - Existing destination items gain what they lack (P4)

**Goal**: an object matched by identity is enriched with the child collections its source counterpart has and it lacks, instead of being skipped whole.

**Independent Test**: transfer into a destination that already contains a part of speech which, in the source, owns slots, templates, features and sub-categories; confirm the destination's copy gains them.

**Depends on Phase 4.** Holds the `categories.py` claim for its duration (plan.md:289-290).

### Tests

- [ ] **T040** [US4] Write failing tests that **SKIP is defined by field-identity comparison, not by mere GUID presence**: a matched GUID alone is a LINK, not a SKIP, and emitting SKIP requires that every scalar field **and all seven owned collections** were compared and needed no write (data-model.md:209-213). This is the constitutional clause defect G3 currently violates - `tests/unit/test_038_enrichment.py`
- [ ] **T041** [US4] Write failing tests that enrichment is non-destructive: never remove, blank, overwrite or destructively reorder existing destination content, and never blank a target field from an empty source (FR-021, Principle IV `update`) - `tests/unit/test_038_enrichment.py`

### Implementation

**Wave 1 - single task (`models.py`):**

- [ ] **T042** [US4] Add `EnrichmentRecord` (`object_class`, `source_guid`, `target_guid`, `label`, `collections`, `fields_updated`, `was_created` always `False`) and `EnrichedCollection` (`field_name`, `added`, `already_present`, `dropped`), with `field_name` constrained to the seven POS collections: `AffixSlotsOC`, `AffixTemplatesOS`, `InflectableFeatsRC`, `SubPossibilitiesOS`, `StemNamesOC`, `InflectionClassesOC`, `ReferenceFormsOC`. Reuse `FidelityStatus` for enriched objects (FULL when every source child arrived, else PARTIAL) and `OwnedObjectSpec` to describe the seven collections - duplicate neither - `src/gramtrans/Lib/models.py`

**--> Wait for T042, then (both touch `categories.py`, serially):**

- [ ] **T043** [US4] Widen `_plan_gold_reserved_edit` (**:423**) with an owned-collection pass beside the existing `("Name","Abbreviation","Description")` loop, covering the seven collections. Its two early `Skip(ALREADY_PRESENT_BY_GUID)` returns at **:471** (the "no WS info for comparison" conservative skip) and **:495** (the "all WS slots equal" skip) may fire **only** when that pass also finds nothing; otherwise fall through to the existing `PlannedOverwrite(write_mode="merge")` at **:524**. This widens the existing path rather than adding a parallel enrich path (recorded decision). Extend the helper docstring at **:424-450** to state the collection pass - `src/gramtrans/Lib/categories.py`

  > **Line numbers corrected (T040/T041 measurement).** The `:194`/`:246`/`:269`/`:298` offsets this task shipped with were stale by **+229**; the four sites above are the live ones. The sentence "Owned collections are outside its scope" that this task said to strike from the `:219` docstring **does not exist in the tree** - it is `census-evidence.md:155` describing the helper, not a docstring. There is nothing to strike; the docstring simply never mentions owned collections.
  >
  > **The helper is shared by six categories, not just POS** - `gram_categories`, `inflection_features`, `variant_types`, `complex_form_types`, `semantic_domains`, `phonological_features`, with further callers at :2778, :2913, :3024 and :8468. The seven collections are POS-only, so the new pass **must** be keyed off the category (or off attribute presence) or the other five pay for a comparison that can never apply. The `test_017_gold_reserved_edit_copy.py` cases must stay green.
  >
  > **Open reading on the :471 skip, decide before implementing.** T040 encodes the reading that collections need no writing-system information to compare, so the collection pass runs even when `ws_list` is empty and only a clean pass lets the conservative skip stand. The stricter reading is that `ALREADY_PRESENT_BY_GUID` is illegal there outright, since the scalar comparison provably did not run - which would need a distinct `SkipReason`. Resolve this rather than letting the implementation pick silently.
- [ ] **T043a** [US1+US4] Give `_phonology_simple_plan`'s present-object path the same `match_basis` record `_emit_present_outcome` already emits, instead of a bare `Skip`. **Same root cause as T043**, filed from the T039 live run (`c65579a`): a bare `Skip` carries no `match_basis`, so the census cannot attribute the objects, the row falls back to `baseline_gross`, and gross subtraction removes starter objects the transfer correctly matched. Measured: run 2 flipped `PhPhoneme` MATCHED -> SHORTFALL (unexplained 21) and `PhNCSegments` MATCHED -> SHORTFALL (2) with **identical destination counts in both runs** - both phantoms. Stated plainly: the better the transfer gets, the worse the census reports it, because working matches turn creates into identity skips and every identity skip degrades its row's subtraction basis. **Giving `Skip` a `match_basis` field is recorded as considered and NOT recommended** - `Skip` means "nothing will be written", and a skip carrying a match is really a LINK, which is exactly the boundary US4 exists to sharpen - `src/gramtrans/Lib/categories.py`
- [ ] **T044** [US4] Give collection children their own identity rule - GUID first, then the R1 roster key - since a collection child is matched, not blindly appended. Sequenced after Phase 4 by construction and guarded by the SC-008 re-run check - `src/gramtrans/Lib/categories.py`

**--> Wait for the `categories.py` chain, then (different files):**

- [ ] **T045** [P] [US4] Extend `_execute_update_semantic` (:268, and the :1674 / :2340 sites) to **add-only** collection semantics: never remove, never destructively reorder. It already routes `write_mode="merge"`; this widens what merge means for a collection. Report the outcome as `disposition=UPDATE` with per-collection counts - `src/gramtrans/Lib/transfer.py`
- [ ] **T046** [P] [US4] Distinguish an enriched item from a created one in the run report (FR-022), and honour the certainty clause: never claim "identical now" on a first transfer, and claim "untouched since last run" only where a residue baseline exists - `src/gramtrans/Lib/report.py`
- [ ] **T047** [P] [US4] Mirror the enrich-vs-skip decision in the plan builder so Preview shows it (Principle III) - `src/gramtrans/Lib/preview.py`

**--> Wait for Wave 3, then:**

- [ ] **T048** [US4] Run the census gate for **predicate P3**: `PartOfSpeech.match_basis.enriched > 0` **and** the owned-child classes MATCHED (SC-007). Measured baseline: 3 matched categories, each missing between 3 and 4 whole collections - `tests/integration/test_object_census.py`

**Checkpoint**: US4 is independently functional. A matched destination item gains 100% of the child items its source counterpart holds and it lacked, and loses none of its own.

---

## Phase 6: US5a - Affix process rules survive the transfer, wholly-owned graphs (P5)

**Goal**: a `MoAffixProcess` is reproduced with its input and output content, or reported and skipped - never downgraded into a plain allomorph.

**Independent Test**: transfer a project containing affix process rules and confirm each arrives with its input and output content intact.

**Depends on Phase 4 and on `038-affix-fidelity` having merged (T005).** Runs in parallel with Phase 5 except for `models.py` (T042 / T052) and the `categories.py` claim, which must be serialised between the two phases.

**Live corpus**: `Mbugwe LizzieHC practice` is the only project with rules - 18 `MoAffixProcess`, 124 `MoAffixAllomorph`, 137 `MoStemAllomorph`, `ContextsOS=93`, `FeatConstraintsOS=89`.

### Tests

- [ ] **T049** [US5] Layer (a) - class-identity assertion on `_walk_entry_allomorphs` with a fake whose `ClassName == "MoAffixProcess"`: assert **neither** allomorph factory was invoked and that exactly one `DroppedItemRecord` with `item_name == "MoAffixProcess"` was appended - `tests/unit/test_038_process_rules.py`
- [ ] **T050** [US5] Layer (b) - the **negative-whitelist invariant**, which tests the FR-025 shape rather than one instance: for every `ClassName` where `_dispatch_allomorph_subclass(...) is None`, the path returns without calling any allomorph factory. This is what makes the downgrade unable to recur for a class nobody thought of - `tests/unit/test_038_process_rules.py`
- [ ] **T051** [US5] Write the failing invariant that **no `PlannedAction` may name a target class differing from its source class** (data-model.md:191-196) - under no circumstance is an object created as a simpler kind - `tests/unit/test_038_process_rules.py`

### Implementation

**Wave 1 - single task (`models.py`):**

- [ ] **T052** [US5] Add `ProcessRuleTransferRecord` (`source_guid`, `target_guid`, `input_contexts`, `output_steps`, `reproduced`, `not_reproducible_reason` non-empty when not reproduced, `reference_decisions` reusing `ReferenceDecisionRecord`), plus `ProcessContextSpec` and `ProcessOutputSpec` rows for `PhSimpleContextSeg`/`NC`/`Bdry` and `MoCopyFromInput`/`MoInsertPhones`/`MoModifyFromInput`. Reuse `ReferenceFieldSpec` for the phoneme and natural-class references. Extend `DroppedItemRecord`'s `owner_kind` values with `MoAffixProcess`, `MoInflAffixSlot`, `MoInflAffixTemplate` - `src/gramtrans/Lib/models.py`

**--> Wait for T052, then (T053-T058 all touch `categories.py`, serially):**

- [ ] **T053** [US5] Implement the create sequence the probe validated: `ServiceLocator.GetService(IMoAffixProcessFactory)` -> `Create(Guid)` -> `Add` to the owning sequence -> set references, attaching the rule exactly as an allomorph (`entry.LexemeFormOA` or `entry.AlternateFormsOS.Add(obj)`; all 18 live instances are owned by `LexEntry.flid5002030`). There is **no flexicon wrapper** - `find_wrappers_for_lcm` returns `found: false` for `IMoAffixProcess` and its factory, `MorphRuleOperations` disclaims the class, and `AllomorphOperations.Create` knows only the stem and affix allomorph factories and has **no `guid=` kwarg at all** (calling it that way raises `TypeError`, swallowed into a generic drop). Route every create through `create_with_guid` (:6248) - never a bare `Create()`. All 12 concrete factories in the graph report `Create(Guid guid)`, so nothing here regenerates identity; note that reflection over the **interface** returns `[]`, so only the concrete implementation carries the overloads - `src/gramtrans/Lib/categories.py`
- [ ] **T054** [US5] Plan and write `InputOS` **before** `OutputOS`, carrying a source-GUID -> new-object map into the `OutputOS` pass, because `OutputOS` members' `ContentRA` point back at `InputOS` members of the same rule. The map must be **many-to-one tolerant**, and `OutputOS` order is significant. Cover `MoCopyFromInput.ContentRA`, `MoInsertPhones.ContentRS`, `PhSimpleContextSeg`/`NC.FeatureStructureRA`, `PhIterationContext.MemberRA`/`Minimum`/`Maximum`, `PhSequenceContext.MembersRS`, and `PhVariable` - `src/gramtrans/Lib/categories.py`
- [ ] **T055** [US5] Implement the R5 condition-4 detector: a `PhSequenceContext` in `InputOS` is owned by the rule, but its `MembersRS` reference `PhSimpleContext*` objects owned by the shared, project-level `PhPhonData.ContextsOS` - true for **6 of the 18** live rules. Until Phase 7's closure pulls them, those rules are **reported and skipped** with the reason naming the missing context. A partially populated `MembersRS` is not an acceptable outcome, and an empty one is exactly the silent content loss FR-023 and SC-006 forbid. Ship `MoModifyFromInput`, `MoInsertNC`, `PhSimpleContextBdry`, `PhIterationContext` and non-empty `PlusConstrRS`/`MinusConstrRS` behind the same skip (zero live instances), matching the `NEEDS_MANUAL` posture at :5480 - `src/gramtrans/Lib/categories.py`
- [ ] **T056** [US5] Implement the FR-025 skip contract: create **nothing** in the item's place - no allomorph, no partially populated `MoAffixProcess` - and roll back or delete any shell created before failure was detected; append exactly one `DroppedItemRecord` with `owner_kind="LexEntry"`, `owner_guid` = source entry GUID, `field_name` = `"LexemeFormOA"` or `"AlternateFormsOS"`, `item_name="MoAffixProcess"`, `item_guid` = the rule's source GUID, and a `reason` naming the specific blocker, deduped on `(owner_guid, field_name, item_guid)`; mark the owning entry `FidelityStatus.PARTIAL` and surface it in the post-run statistics panel - `src/gramtrans/Lib/categories.py`
- [ ] **T057** [US5] Add `MoAffixProcess` to `_dispatch_allomorph_subclass`'s `known` set (:5485-5490, today `{"MoAffixAllomorph","MoStemAllomorph"}`) **in this same change and never earlier** - the whitelist entry and the real executor must land together, or the downgrade returns - `src/gramtrans/Lib/categories.py`
- [ ] **T058** [US5] Replace the downgrade at `_walk_entry_allomorphs._mk` (:6184-6187, the `else IMoAffixAllomorphFactory` ternary) with the real create path, keeping `038-affix-fidelity`'s skip (`18c0ece`) as the fallback rather than removing it - `src/gramtrans/Lib/categories.py`

**--> Wait for the `categories.py` chain, then (different files):**

- [ ] **T059** [P] [US5] Mirror the FR-025 skip decision in the plan builder, not only in the executor, and plan `InputOS` before `OutputOS` there too - `src/gramtrans/Lib/preview.py`
- [ ] **T060** [P] [US5] Add the process-rule executor consuming `RunPlan.process_rules`, resolving every phoneme and natural-class reference to the destination objects matched under FR-001/FR-002 (FR-024) - `src/gramtrans/Lib/transfer.py`
- [ ] **T061** [P] [US5] Confirm residue tagging needs no new work: `MoAffixProcess` is already in `CARRIER_A_CLASSES` (:43). Record the confirmation rather than adding a carrier - `src/gramtrans/Lib/residue.py`
- [ ] **T062** [P] [US5] File an issue for the stale comment at `matcher.py:262` claiming `IMoAffixAllomorph`'s LCM factory "do[es] not accept a GUID override" - `MoAffixAllomorphFactory` reports `Create(Guid guid)` live. Out of scope for this phase; do not fix it here - `src/gramtrans/Lib/matcher.py`

**--> Wait for Wave 3, then:**

- [ ] **T063** [US5] Layer (c) corpus acceptance: transfer `Mbugwe LizzieHC practice` into a restored blank target and require `count(MoAffixProcess) == 18` **and** `delta(MoAffixAllomorph) == +124 exactly`, plus per-member counts `MoInsertPhones` 63, `MoCopyFromInput` 38, `PhVariable` 21, `PhSimpleContextSeg` 12, `PhSequenceContext` 6, `PhSimpleContextNC` 5 - so an empty-`OutputOS` shell also fails - `tests/integration/test_038_process_rules.py`
- [ ] **T064** [US5] Run the census gate for **predicate P4**: `MoAffixProcess` MATCHED **and** `MoAffixAllomorph.difference == 0`. Both, because either alone can be satisfied by the defect itself - the downgrade produces a correct allomorph count while destroying every rule (SC-006; measured baseline 14 of 14 destroyed while the run reported success) - `tests/integration/test_object_census.py`

**Checkpoint**: US5a is independently functional for wholly-owned rule graphs. The 6 rules with shared contexts are reported and skipped with a named reason - loudly incomplete, never silently downgraded.

---

## Phase 7: US3 - Selecting a piece brings what it needs (P3)

**Goal**: `Lib/closure.py` stops being code with no caller, and a selected affix actually pulls the categories, slots and templates it needs.

**Independent Test**: select only affixes, run a preview, and confirm the dependent categories, slots and templates appear in the plan and are individually deselectable.

**Depends on Phase 2's registry.** Holds the `categories.py` claim for its duration. Defect G2 verified: `closure.py`'s only importer today is `tests/unit/test_closure.py:12`.

**Audit-then-enable, one relationship at a time, with a census run after each (R3).** A global flag cannot satisfy FR-018. 037's rewritten `natural_classes_dependencies` is deliberately **not** among the first three.

### Tests

- [ ] **T065** [US3] Write failing tests that an edge may influence a plan only after it is registered in `CLOSURE_EDGES_VERIFIED`, and that `build_run_plan` raises on `verified is False` (FR-018) - `tests/unit/test_038_closure.py`

### Implementation

**Wave 1 - single task (`models.py`):**

- [ ] **T066** [US3] Add `ClosureEdge` (`dependent`, `dependency`, `kind`, `verified`, `verified_by`, `origin` in `{"chosen","pulled_in"}`, `deselected`), the `DependencyKind` enum (`AFFIX_TO_POS`, `AFFIX_TO_SLOT`, `SLOT_TO_TEMPLATE`, `TEMPLATE_TO_POS`, `MSA_TO_INFL_FEATURE`, `PROCESS_RULE_TO_PHONEME`, `PROCESS_RULE_TO_NATURAL_CLASS`) and `IncompletenessRecord` (`incomplete_item`, `incomplete_label`, `missing_dependency`, `missing_label`, `cause` in `{deselected, unsatisfiable, cycle}`, `consequence`) - `src/gramtrans/Lib/models.py`

**--> Wait for T066, then (one edge at a time - each gated by its own census run, and all three touch `categories.py`):**

- [ ] **T067** [US3] Audit and register `affixes_dependencies` (:7261): confirm the edge is correct against a live pair, add it to `CLOSURE_EDGES_VERIFIED` with `verified_by` naming the audit, then run a census - `src/gramtrans/Lib/categories.py`
- [ ] **T068** [US3] Audit and register `slots_dependencies` (:7337), then run a census - `src/gramtrans/Lib/categories.py`
- [ ] **T069** [US3] Audit and register `affix_templates_dependencies` (:7475), then run a census. These three are what close SC-003 and SC-004 - `src/gramtrans/Lib/categories.py`

**--> Wait for the three edges, then (different files):**

- [ ] **T070** [P] [US3] Mark pulled-in items in the plan and surface them through the existing pulled-in surfaces at :1348, :1380 and :1427 rather than adding a new one; set `ClosureEdge.origin` to `"pulled_in"` (FR-015) - `src/gramtrans/Lib/preview.py`
- [ ] **T071** [P] [US3] Reuse `Selection.excluded_deps`, `is_dep_excluded`, `Selection.scope_for`'s `CategoryScope` mapping and the existing `SkipReason.EXCLUDED_LOSSY` / `BARE_BONES_MISSING_CLOSURE` for deselection rather than adding new machinery - `src/gramtrans/Lib/selection.py`
- [ ] **T072** [P] [US3] Make each pulled-in item individually deselectable in the wizard (FR-016) - **re-pointed by feature 039:** `selection_wizard.py` no longer holds the page classes. The tree to edit is in the module that owns it - `src/gramtrans/Lib/ui/wizard_pages_skeleton.py` (`_PageGramDeps`, for grammar dependencies pulled in by an affix pick) or `src/gramtrans/Lib/ui/wizard_pages_pickers.py` (`_PageItemPicker` / `_PageStemPicker`). If the deselection needs whole-block tristate behaviour, put it on `_BlockPage` in `src/gramtrans/Lib/ui/wizard_page_base.py` rather than in one page

**--> Wait for Wave 3, then:**

- [ ] **T073** [US3] Emit an `IncompletenessRecord` for every item left incomplete because a dependency was deselected or could not be satisfied (FR-017), including the cycle case - `src/gramtrans/Lib/preview.py`
- [ ] **T074** [US3] Link each transferred affix to the template column it occupied in the source, or report the failure to link (FR-019). Measured baseline: 0 of 110 linked and 0 reported - `src/gramtrans/Lib/categories.py`

**--> Wait for Wave 4, then:**

- [ ] **T075** [US3] Run the census gate for **predicate P2**: `MoInflAffixTemplate` and `MoInflAffixSlot` MATCHED (SC-004; measured baseline 0 of 8 and 0 of 11 on one pair, 0 of 13 and 0 of 19 on the other) - `tests/integration/test_object_census.py`

**Checkpoint**: US3 is independently functional. Transfers stop arriving structurally incomplete, pulled-in items are visible and deselectable, and every deselection consequence is reported.

---

## Phase 8: US5b - Rules whose input references shared project-level contexts

**Depends on Phase 7.** Until now these 6 rules were reported and skipped by T055.

- [ ] **T076** [US5] Extend closure to pull the `PhSimpleContext*` objects owned by `PhPhonData.ContextsOS` that a rule's `PhSequenceContext.MembersRS` references, register that edge under `CLOSURE_EDGES_VERIFIED`, and flip the 6 affected rules from report-and-skip to full transfer - `src/gramtrans/Lib/categories.py`

**--> Wait for T076, then:**

- [ ] **T077** [US5] Re-run the `Mbugwe LizzieHC practice` corpus acceptance from T063 and confirm all 18 rules now transfer with complete `MembersRS`, with no rule left on the skip path for condition 4 - `tests/integration/test_038_process_rules.py`

**Checkpoint**: US5 is complete. Every affix process rule in the live corpus either transfers with its input and output content intact or is reported with a reason - none is downgraded.

---

## Phase 9: Polish

Report-only residuals, the cross-cutting audits, and validation against the Success Criteria.

**Wave 1 - blocked on 037, independent of each other:**

- [ ] **T078** [P] Re-run the census after 037 lands to obtain the post-037 baseline, then re-scope the report-only residual set. If 037 stalls, this blocks nothing in US1-US4 - the residual work is report-only (R7) - `tests/integration/test_object_census.py`
- [ ] **T079** [P] Give the residual classes report lines rather than fixes (R7): `FsComplexFeature` stays report-only, and `status: "unmeasurable"` must be a value **distinct** from `"match"` so a report-only class cannot rot behind a green gate. The phonological-context family is 037's or another feature's territory; texts and wordforms are governed by their own feature - `src/gramtrans/Lib/report.py`

**--> Wait for Wave 1, then (different files):**

- [ ] **T080** [P] Audit SC-010 end to end: every selected item reaches exactly one of ADD, UPDATE (enriched), SKIP, or dropped-with-reason, and each appears in the post-run statistics panel - **there is no fifth, unreported outcome** (data-model.md:232-235). Assert the extended `RunReport.__post_init__` accounting invariant covers all four buckets - `tests/integration/test_038_no_silent_skips.py`
- [ ] **T081** [P] Run the census gate for **predicate P5**: every remaining `required` row MATCHED or carrying a valid `GOVERNED_BY_OTHER_FEATURE` / `NO_CREATE_PATH` line, with no unexplained difference remaining (SC-005) - `tests/integration/test_object_census.py`
- [ ] **T082** [P] Resolve the two roster pending items: `038-NK-P2` (uniqueness enforcement was never located - the confirming test **must run in a throwaway project only**) and `038-NK-P3` (recovery verified by re-census). Re-check `PhNCSegments` (8) and `LexEntryInflType` (15) first if a new read-only project is sanctioned. **Commits to `main`** - `specs/038-transfer-fidelity-gaps/contracts/natural-key-roster-extension.md`

**--> Wait for Wave 2, then:**

- [ ] **T083** Refresh the `<!-- SPECKIT -->` pointer in `CLAUDE.md`, which still names `specs/029-sense-pictures/plan.md`. **Blocked until 037 releases its `CLAUDE.md` claim** - if the claim is still live, leave this unchecked and say so rather than forcing it - `CLAUDE.md`
- [ ] **T084** Release every `lockout` claim taken in T004 - `~/.claude/skills/lockout/lockout.py`
- [ ] **T085** Merge the validated `038-transfer-fidelity-gaps` branch to `main` and remove the worktree. Spec artifacts (T023, T025, T082) commit to `main` directly and are already there - `git`

---

## Dependencies & Execution Order

**Phase dependencies**

```text
Phase 1 Setup
   -> Phase 2 Foundational          (blocks every story)
        -> Phase 3 US2 census       (the acceptance instrument for everything below)
             -> Phase 4 US1 natural key   [external gate: T028, 035's roster append]
                  -> Phase 5 US4 enrichment  ||  Phase 6 US5a process rules
                       -> Phase 7 US3 closure
                            -> Phase 8 US5b shared contexts
                                 -> Phase 9 Polish  [external gate: T078, 037 landing]
```

Phases 5 and 6 are genuinely parallel except for `models.py` (T042 and T052) and the
`categories.py` claim, which must be serialised between them.

**Wave restatement per phase**

- **Phase 1**: W1 T001/T002/T003 [P] -> W2 T004 (claims) -> W3 T005 (rebase) -> W4 T006 (green baseline).
- **Phase 2**: W1 T007 -> W2 T008 (same file) -> W3 T009/T010/T011 [P] -> W4 T012 (needs T008 + T010) -> W5 T013.
- **Phase 3**: T014 (failing test) -> W1 T015 -> W2..W6 T016-T020 (all `census.py`, serial) -> W7 T021/T022 [P] -> W8 T023, T024, T025.
- **Phase 4**: T026/T027 (failing tests) -> W1 T028 (**hard external gate**) -> W2 T029/T030 [P] -> W3 T031 (plan-time first) -> W4 T032-T035 (`categories.py`, serial) -> W5 T036/T037 [P] -> W6 T038, T039.
- **Phase 5**: T040/T041 -> W1 T042 -> W2 T043, T044 (`categories.py`, serial) -> W3 T045/T046/T047 [P] -> W4 T048.
- **Phase 6**: T049/T050/T051 -> W1 T052 -> W2 T053-T058 (`categories.py`, serial) -> W3 T059/T060/T061/T062 [P] -> W4 T063, T064.
- **Phase 7**: T065 -> W1 T066 -> W2 T067, T068, T069 (one edge at a time, census after each) -> W3 T070/T071/T072 [P] -> W4 T073, T074 -> W5 T075.
- **Phase 8**: T076 -> T077.
- **Phase 9**: W1 T078/T079 [P] -> W2 T080/T081/T082 [P] -> W3 T083, T084, T085.

**The bottleneck is `categories.py`**, at 9,157 lines the primary surface for Phases 4, 5, 6, 7 and 8. Its tasks are serial by necessity, not by oversight, and Phases 5 and 7 must hold the claim for their duration (plan.md:289-290).

**Acceptance rule governing every phase gate above**: a phase is not done when its unit tests pass; it is done when the census run for its predicate exits 0 with the predicate satisfied.
