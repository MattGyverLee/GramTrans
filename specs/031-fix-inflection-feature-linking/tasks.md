---

description: "Task list for 031-fix-inflection-feature-linking"
---

# Tasks: Fix Inflection-Feature Linking to Grammatical Categories

**Input**: Design documents from `specs/031-fix-inflection-feature-linking/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED. The quickstart names specific offline test files and the
constitution's quality gates require a verification run; this feature is implemented
test-first.

**Organization**: Grouped by user story. US1 and US2 are both P1 (co-required for a
usable fix); US3 (P2) is the read-only diagnosis.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3
- Exact file paths included. Work happens on a feature worktree per the git protocol;
  spec artifacts stay on `main`.

## Path Conventions

- Module source: `src/gramtrans/Lib/`
- Offline tests: `tests/unit/`
- Read-only diagnosis: `debug/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Work environment and test scaffolds

- [X] T001 Create the implementation worktree `../GramTrans-031-fix-inflection-feature-linking` on branch `031-fix-inflection-feature-linking` from `main` (per CLAUDE.md git protocol; code changes land here, not on `main`).
- [X] T002 [P] Create failing test scaffold file `tests/unit/test_031_infl_feature_linking.py` with the test class skeleton and `pytest` imports (no assertions yet).
- [X] T003 [P] Create read-only diagnosis scaffold `debug/diag_infl_features.py` with a `main()` that opens a target project read-only and prints an empty report dict (no target writes).

**Checkpoint**: Worktree ready; empty scaffolds compile.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Resolve the two `confirm-live` items from research.md and add the shared
plan binding — both US1 and US2 depend on these.

**⚠️ CRITICAL**: No user-story implementation begins until this phase is complete.

- [X] T004 Live-probe via FLExToolsMCP against `Ejagham Mini`: confirm whether the flexicon `InflectionFeature` Operations surface exposes `GetSyncableProperties`/`ApplySyncableProperties` for `IFsClosedFeature` and `IFsSymFeatVal`; capture the source-vs-target writing-system handle divergence for a known WS Id; confirm the `IPartOfSpeech.InflectableFeatsRC` accessor and `.Add` idiom. Record answers in `specs/031-fix-inflection-feature-linking/research.md` (R2/R5 open items). **DONE** — see research.md "T004 — Live-probe results": syncable surface confirmed for features (`{Name,Abbreviation,Description}`); WS-handle divergence CONFIRMED (source `etu=999000003` vs target `etu=999000002`); `InflectableFeatsRC` = `ILcmReferenceCollection[IFsFeatDefn]` with `Add` and requires `IPartOfSpeech(p)` cast; 13 source links. Value-case caveat: no `IFsSymFeatVal` in the Ejagham pair — keep C3 explicit-handle fallback.
- [X] T005 Add the `FeatureCategoryLink` plan binding to the run-plan model in `src/gramtrans/Lib/models.py` (shape `{target_pos_guid: [feature_guid, ...]}`, mirroring `lexentry_ref_bindings`); default empty; per data-model.md. **DONE** — added `RunPlan.feature_category_links: dict` (field name resolves the second Phase-0 open item).

**Checkpoint**: API surface confirmed; plan can carry feature→POS links.

---

## Phase 3: User Story 1 - Transferred features are usable on lexical entries (Priority: P1) 🎯 MVP

**Goal**: Populate each target category's `InflectableFeatsRC` so transferred inflection
features are selectable on lexical entries — via preview-visible Link rows and a Move
wiring post-pass.

**Independent Test**: Transfer categories + features into a clean target; in FieldWorks
the transferred features are selectable on a lexical entry of the correct category, and
the Preview listed one Link row per association (quickstart Steps 2–3).

### Tests for User Story 1 ⚠️ (write first, must FAIL before implementation)

- [X] T006 [P] [US1] In `tests/unit/test_031_infl_feature_linking.py`: test that plan-building gathers one `(target_pos_guid, feature_guid)` link per source `POS.InflectableFeatsRC` member in scope (contract C1 COUNT).
- [X] T007 [P] [US1] In `tests/unit/test_031_infl_feature_linking.py`: test the wiring post-pass adds the feature to a mocked target `InflectableFeatsRC` exactly once, is idempotent on a second run, and is order-independent (contract C2 IDEMPOTENT/ORDER-INDEPENDENT).
- [X] T008 [P] [US1] In `tests/unit/test_031_infl_feature_linking.py`: test that a missing feature OR missing POS endpoint yields a reported `Skip(DEPENDENCY_UNRESOLVED)` and performs NO `.Add` (contract C2 DEFERRED-NOT-DANGLING / VR-4).

### Implementation for User Story 1

- [X] T009 [US1] In `src/gramtrans/Lib/categories.py` (or the plan-builder path in `src/gramtrans/Lib/preview.py`): during plan-building, for each in-scope POS read source `InflectableFeatsRC` and record `(target_pos_guid, feature_guid)` links into the `FeatureCategoryLink` binding (contract C1).
- [X] T010 [US1] In `src/gramtrans/Lib/preview.py`: surface each link binding as a distinct Preview row with proposed action **Link** (already-present pairs shown as SKIP/already-linked) so preview count == committed count (contract C1 / VR-5 / SC-004).
- [X] T011 [US1] In `src/gramtrans/Lib/categories.py`: implement `_run_infl_feature_link_pass(context, target, tag=None) -> list[Skip]` modeled on `_run_post_pass_a` — resolve endpoints (in-plan then `get_object_by_guid`), cast POS to `IPartOfSpeech`, membership-guard, `InflectableFeatsRC.Add`, emit Skips for unresolved endpoints (contract C2).
- [X] T012 [US1] In `src/gramtrans/Lib/categories.py` / `src/gramtrans/Lib/transfer.py`: register the post-pass via `_run_tail_once` so it runs exactly once in Move after both `GRAM_CATEGORIES` and `INFLECTION_FEATURES` actions execute; fold its Skips into `context._exec_skips` (no silent skips).
- [X] T013 [US1] Ensure emitted Skips appear in the post-run statistics panel (verify wiring to the existing skip-reporting path; add coverage in `tests/unit/test_031_infl_feature_linking.py`).

**Checkpoint**: Features become selectable on lexical entries; links are preview-visible and Move-only.

---

## Phase 4: User Story 2 - Re-runs create no duplicate or nameless features (Priority: P1)

**Goal**: Fix the writing-system-mapped name copy and the feature-level dedup so
transferred features/values are always named and re-runs are fully idempotent.

**Independent Test**: Transfer into a clean target, snapshot the feature/value/link
inventory, re-run the identical transfer; inventory is unchanged and no nameless records
exist (quickstart Step 4 / SC-002 / SC-003).

### Tests for User Story 2 ⚠️ (write first, must FAIL before implementation)

- [X] T014 [P] [US2] In `tests/unit/test_categories_inflection_features.py`: test that feature and value `Name`/`Abbreviation`/`Description` are written using the TARGET writing-system handle (via `ws_map`), asserting a source string in WS X lands in target WS X and the name is non-empty in the target default analysis WS (contract C3 NON-NULL-NAME / WS-FIDELITY / VR-2).
- [X] T015 [P] [US2] In `tests/unit/test_categories_inflection_features.py`: test that a feature present in the target by feature-level GUID is classified `in_target` (not `new`) and is NOT re-created on re-run (contract C4 / VR-1).

### Implementation for User Story 2

- [X] T016 [US2] In `src/gramtrans/Lib/categories.py` `inflection_features_execute_action`: replace the raw source-handle string copy (currently `all_ws` built from `source.WritingSystems` written directly) with a WS-mapped copy — prefer `InflectionFeature.ApplySyncableProperties(..., ws_map=ws_mapping)` per T004; else translate source→target handles via `ws_mapping`. Apply to both the feature and each `IFsSymFeatVal` value (contract C3).
- [X] T017 [US2] In `src/gramtrans/Lib/selection.py`: split `_gather_target_infl_feat_guids` (or its callers) into a feature-level GUID set and a value-level GUID set; classify feature rows (`depth=0`) against the feature-level set and value rows (`depth=1`) against the value-level set (contract C4 / data-model dedup sets).
- [X] T018 [US2] In `src/gramtrans/Lib/categories.py`: verify `inflection_features_plan_action` / `_plan_gold_reserved_edit` emit `ADD` only when the feature-level GUID is absent from the target, and that `inflection_features_execute_action` does not create a fresh-GUID twin when `factory.Create(parsed_guid, ...)` is unavailable (fail-loud, not silent duplicate) — add regression coverage in `tests/unit/test_categories_inflection_features.py`.

**Checkpoint**: Features/values always named; re-run adds nothing new.

---

## Phase 5: User Story 3 - Read-only diagnosis of existing broken features (Priority: P2)

**Goal**: Characterize a target's inflection features (nameless, orphaned, WS-handle
evidence) without writing to it.

**Independent Test**: Run the diagnosis against a target; it produces the report with 0
target modifications (quickstart Step 0 / SC-005).

### Tests for User Story 3 ⚠️

- [X] T019 [P] [US3] In `tests/unit/test_031_infl_feature_linking.py`: test the diagnosis report shape against a mocked project — `total_features`, `total_values`, `nameless_features`, `nameless_values`, `orphaned_features`, `linked_features`, `feature_name_ws_map`, `duplicate_guid_groups`; assert every feature is classified exactly one of linked/orphaned (contract diagnosis-report COMPLETE). **DONE** — 6 US3 tests over a `_FakeView`/`ProjectView` facade: shape (all 8 keys), counts+classification, COMPLETE partition (linked+orphaned==total), WS-map evidence sampling, duplicate-GUID detection. All pass (worktree @ e376b39).

### Implementation for User Story 3

- [X] T020 [US3] Implement the read-only report in `debug/diag_infl_features.py` per `contracts/diagnosis-report.md`: walk `MsFeatureSystemOA.FeaturesOC`, count nameless features/values, classify each feature as orphaned vs linked by scanning every `IPartOfSpeech.InflectableFeatsRC`, sample the WS handle carrying a named feature, and detect duplicate-GUID groups. MUST open read-only and perform zero writes (contract READ-ONLY). **DONE** — pure `build_report(view)` core + live `_LcmProjectView` (casts `ILangProject`/`IPartOfSpeech`/`IFsFeatDefn`/`IFsSymFeatVal`). Navigation validated read-only via FLExToolsMCP against `Ejagham Mini` (5 feat / 20 POS / 3 linked + 2 orphaned) and `Ejagham Full GT-Test` (clean: 0 feat; target `etu=999000002` confirms T004 divergence). Both MCP runs certified read-only.
- [X] T021 [US3] Add a guard/assertion path in `debug/diag_infl_features.py` that proves read-only (e.g. no UoW opened; pre/post object-count snapshot equal) and prints the report as plain ASCII (no emoji, per environment rules). **DONE** — `main()` opens `writeEnabled=False`, asserts `object_count()` (ServiceLocator.ObjectRepository.Count, with a feature/value/POS-count fallback) is unchanged before vs after the walk; `_print_report` emits plain-ASCII `[INFO]/[WARN]` lines only.

**Checkpoint**: Diagnosis produces before/after evidence for Defects 1 and 2.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verification, pattern audit, and documentation

- [X] T022 Run the sweep-pattern audit for the WS-handle-copy bug class (source-handle written into target object): search the other GOLD/feature execute_action paths (e.g. `exception_features`, `inflection_classes`, `variant_types`, `complex_form_types`, `phonological_features`) for the same raw-source-handle string copy; record siblings (file:line + confidence) in a "Pattern audit" section of the PR body. **DONE** — see [pattern-audit.md](pattern-audit.md). Found **3 SUSPECT siblings** (the only raw source-handle writes in `Lib/`): `stem_names_execute_action` (categories.py:1388-1400), `slots_execute_action` (categories.py:5265-5276), `_execute_gold_reserved_merge` (transfer.py:2392-2436). All OUT of 031's prevention-only scope — file a follow-up spec to apply the same `ws_map` fix globally. All other Name/Abbrev/Desc paths route through `ApplySyncableProperties(..., ws_map=...)` (SAFE).
- [X] T023 [P] Run the full offline unit suite from the worktree and confirm no regressions vs the merged-tree baseline: `python -m pytest tests/unit -q`. **DONE** — `1529 passed, 1 failed, 1 skipped, 8 deselected, 14 xfailed, 14 xpassed` (+ 6 new US3 tests all pass). The single failure (`test_wizard_pos_grammar_wiring::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos`) is a PRE-EXISTING baseline failure: reproduced at clean HEAD `c3f89bf` with the Phase 5 files stashed — NOT a Phase 5/6 regression. (Untracked flag: worth a follow-up spec, out of 031 scope.)
- [X] T024 Execute quickstart.md live validation Steps 0–4 against `Ejagham Mini` → a clean/restored `Ejagham Full GT-Test`; attach pre/post diagnosis reports and Import Residue / `[GT-Tag]` evidence. (Destructive Move — attended; restore target from clean backup first.) **DONE (attended, user-authorized 2026-07-13)** — ran `Ejagham Mini` → restored **`Target`** (clean backup) via `scratchpad/run031_live.py`. **First run FAILED and caught two real Phase 3-4 defects** the offline mocked tests missed; both fixed (worktree @ `9e41a1f`), re-run **PASS**: `linked_features 0→3` (== source), `nameless_features 1→0`, idempotent re-Move (4 feat / 35 val both runs), 0 duplicates. The 1 remaining orphaned feature is correct (orphaned in source too); the `FsComplexFeature` is cleanly skipped `UNSUPPORTED_LCM_TYPE`. Fixes: (1) `_resolve_target_by_guid` (live target has no `get_object_by_guid` — used LCM object repo, MCP-verified); (2) non-closed-feature type guard. See STATUS.md + pattern-audit.md.
- [X] T025 [P] Update `STATUS.md` with the 031 outcome and evidence links; note prevention-only scope (FR-011) and that the polluted target must be restored out of band. **DONE** — STATUS.md now leads with the 031 Phase-5 entry (worktree @ e376b39; MCP evidence; T022 sibling list; T024/T026 gate).
- [ ] T026 Merge `031-fix-inflection-feature-linking` → `main` after live validation passes; remove the worktree. **BLOCKED on T024** (attended live validation must pass first).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; **blocks US1 and US2** (T004 confirms the
  name-copy approach; T005 adds the binding US1 writes to).
- **US1 (Phase 3)** and **US2 (Phase 4)**: both P1, depend only on Foundational. Both
  edit `categories.py` (`inflection_features_execute_action` vs the new post-pass +
  gathering) and touch `selection.py`/`preview.py` — see conflict notes below.
- **US3 (Phase 5)**: P2; independent of US1/US2 code (read-only, separate file
  `debug/diag_infl_features.py`). **Recommended to run its diagnosis EARLY** (quickstart
  Step 0) to capture pre-fix evidence, even though it ships as P2.
- **Polish (Phase 6)**: depends on US1+US2 complete (T024 live-validates the fix).

### User Story Dependencies

- US1 and US2 are co-required for a *usable* fix (a link without idempotency multiplies
  bad records; naming without the link leaves features orphaned) but are each
  independently testable offline.
- US3 has no dependency on US1/US2 and can be built/run at any point.

### Within Each User Story

- Tests (T006–T008, T014–T015, T019) written first and FAIL before implementation.

### Parallel Opportunities & Conflict Notes

- Setup: T002, T003 in parallel.
- US1 tests T006/T007/T008 in parallel (same new file, but independent test functions —
  coordinate to avoid edit collisions; safe to author together).
- US2 tests T014/T015 in parallel.
- **Cross-story file conflict**: US1 (T009, T011, T012) and US2 (T016, T017, T018) both
  edit `src/gramtrans/Lib/categories.py`. Do NOT run T009/T011/T012 and T016/T018 in
  parallel against the same file — sequence them (US1 then US2, or coordinate hunks).
  US2's `selection.py` edit (T017) is parallel-safe vs US1.
- US3 (T019–T021) is fully parallel with US1/US2 (distinct files).

---

## Parallel Example: User Story 1 tests

```bash
# Author these together (independent test functions in the same new file):
Task: "T006 link-gathering count test"
Task: "T007 post-pass idempotency/order test"
Task: "T008 deferral (Skip DEPENDENCY_UNRESOLVED) test"
```

---

## Implementation Strategy

### MVP scope

**US1 + US2 together are the MVP** (both P1). US1 alone makes features appear but re-runs
would still pollute; US2 alone leaves features orphaned. Ship both, validated on the
clean reference pair, then merge.

### Recommended order

1. Phase 1 Setup → Phase 2 Foundational.
2. Run US3's diagnosis (T020, read-only) against the current target to capture pre-fix
   evidence (Defect 1 orphan count, Defect 2 nameless/WS-handle evidence).
3. US1 (link) → US2 (naming + dedup), sequencing the shared `categories.py` edits.
4. Phase 6: pattern audit, full suite, live quickstart validation, merge.

### Attended / needs_human gate

- T024 is a destructive live Move. Restore `Ejagham Full GT-Test` from a clean backup
  first; run attended; never let an unattended loop perform the live write.

---

## Notes

- [P] = different files, no dependencies. Watch the `categories.py` cross-story conflict.
- Prevention-only (FR-011): no task modifies existing broken records in the polluted
  target.
- Constitution gates: Preview-before-mutate (T010/T011/T012), WS identity mapping (T016),
  referential completeness + no-silent-skips (T012/T013), pattern audit for the shaped
  bug (T022).
- Commit after each task or logical group on the worktree; spec edits (e.g. T004's
  research.md update) commit to `main`.
