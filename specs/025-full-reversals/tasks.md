# Tasks: Full Reversals

**Input**: Design documents from `specs/025-full-reversals/`
**Prerequisites**: plan.md (required), spec.md (stub), research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED. The plan enumerates three unit test files
(`test_reversal_walk.py`, `test_reversal_category_resolve.py`, `test_config_view_copy.py`)
plus a fidelity-census extension, and the repo follows TDD (see CLAUDE.md / STATUS.md).
Test tasks are therefore generated and MUST fail before their implementation tasks.

**Organization**: Tasks are grouped by user story (derived from the quickstart scenarios and
the plan's Part A / Part B split, since the 025 spec is a stub with no formal FR/story block).
Each story is independently implementable and testable.

## Story derivation (spec stub → stories)

| Story | Priority | Source | Delivers |
|---|---|---|---|
| US1 | P1 (MVP) | Quickstart S1, S3; Part A walk | Reversal entries ride along with copied senses: closure discovery, per-WS index create/reuse, WS gate, ReversalForm copy, SensesRS linking (copied-only + partial report), SubentriesOS recursion |
| US2 | P2 | Quickstart S2; Part A category | `PartOfSpeechRA` resolved against the **per-index** `PartsOfSpeechOA` via the 024 resolver (create+ancestors / update / link+report / link) |
| US3 | P3 | Quickstart S4; Part B | `.fwdictconfig` dictionary + reversal configuration-view file copy with Add/Overwrite/Skip planning and absent-reference reporting |

Never-silent unification (Quickstart S5) and the fidelity census (S6) are cross-cutting —
handled within each story's dropped-item wiring and finalized in Polish.

## Path Conventions

Single project (FlexTools module). Source under `src/gramtrans/Lib/`, tests under
`tests/unit/` and `tests/verification/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the new module files and test scaffolding referenced by the plan.

- [ ] T001 Create empty module `src/gramtrans/Lib/reversals.py` with module docstring (Part A — reversal closure walk) and imports of the 024 reuse surface (`references`, `owned`, `report`, `protection`, `ws_mapping`).
- [x] T002 [P] Create empty module `src/gramtrans/Lib/config_views.py` with module docstring (Part B — `.fwdictconfig` file copy) and `import os`, `shutil`, `filecmp` for the file-I/O path.
- [ ] T003 [P] Create empty test files `tests/unit/test_reversal_walk.py`, `tests/unit/test_reversal_category_resolve.py`, and `tests/unit/test_config_view_copy.py` with pytest imports and a skipped placeholder each.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core prerequisites that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 **024 dependency gate**: verify feature 024-lexicon-reference-fidelity has landed on this worktree — confirm `src/gramtrans/Lib/references.py` exposes `decide_reference`/`apply_reference` and `ReferenceFieldSpec`, `src/gramtrans/Lib/owned.py` exposes the recursive owned-child walk, and `src/gramtrans/Lib/report.py` exposes `DroppedItemRecord` + `FidelityStatus`. If any are absent, STOP: 025 cannot proceed until 024 is merged (plan.md "Hard dependency").
- [x] T005 [P] Add `ReversalFieldSpec` / `ReversalDecision` dataclasses to `src/gramtrans/Lib/models.py` per data-model.md (target index ref, `PartOfSpeechRA` ReferenceDecision, senses-to-link + dropped members, reversal-form alternatives, recursive sub-entry decisions).
- [x] T006 [P] Add `ConfigViewRecord` dataclass to `src/gramtrans/Lib/models.py` per data-model.md (`kind`, `filename`, `src_path`, `tgt_path`, `action` enum ADD|OVERWRITE|SKIP, `missing_refs: list[DroppedItemRecord]`).
- [x] T007 Register the new dropped-item `owner_kind` values (`"ReversalIndexEntry"`, `"ReversalIndex"`, `"ConfigView"`) wherever owner_kinds are enumerated/validated in `src/gramtrans/Lib/report.py` (extend existing 024 enumeration; do not fork the report channel).
- [ ] T008 Define `REVERSAL_FIELD_MAP` in `src/gramtrans/Lib/reversals.py` per data-model.md: `PartOfSpeechRA` (atomic ref, hierarchical, `target_list_path = lambda tgt_index: tgt_index.PartsOfSpeechOA`), `SensesRS` (ref seq, re-wire to copied senses), `ReversalForm` (IMultiUnicode value copy), `SubentriesOS` (owned recurse). This is the completeness contract the census (T033) verifies.

**Checkpoint**: 024 reuse surface confirmed, shared dataclasses + owner_kinds + field map in place — user stories can begin.

---

## Phase 3: User Story 1 - Reversal entries ride along with copied senses (Priority: P1) 🎯 MVP

**Goal**: For every sense the transfer copies, reproduce the source reversal-index entries that
link it onto the target's matching per-WS index — with reversal form, sense links (copied only),
and recursive sub-entries — gated by writing-system mapping and never-silent on drops.

**Independent Test**: Run quickstart Scenario 1 (entries ride along) and Scenario 3 (WS gate):
transfer senses referenced by reversal entries; Preview lists each linked entry under its per-WS
index with an Add/Link action; Move reproduces the entries linking only copied senses, with forms
and sub-entries; an unmappable-WS index yields a `ReversalIndex` dropped record and is skipped.

### Tests for User Story 1 ⚠️ (write first, must FAIL before implementation)

- [x] T009 [P] [US1] In `tests/unit/test_reversal_walk.py`: test entry discovery — `plan_reversals` gathers only entries whose `SensesRS` intersects the copied-sense set; an index with no such entries is excluded from the plan (closure scope R3).
- [x] T010 [P] [US1] In `tests/unit/test_reversal_walk.py`: test WS gate — a source index whose `WritingSystem` cannot be mapped to a target analysis WS produces exactly one `DroppedItemRecord` (owner_kind `ReversalIndex`, reason `writing system not mapped`) and is skipped (R4).
- [x] T011 [P] [US1] In `tests/unit/test_reversal_walk.py`: test partial `SensesRS` — an entry linking both copied and non-copied senses is planned with only the copied links, and each omitted member yields one `DroppedItemRecord` (owner_kind `ReversalIndexEntry`, reason `member not in copy set`) (R3 / 024 FR-008).
- [x] T012 [P] [US1] In `tests/unit/test_reversal_walk.py`: test `ReversalForm` non-destructive copy — populated source alternatives are written per mapped WS; an empty source alt never blanks a populated target alt (R6 / 024 FR-007).
- [ ] T013 [P] [US1] In `tests/unit/test_reversal_walk.py`: test `SubentriesOS` recursion — a source entry with nested sub-entries produces a recursive `ReversalDecision` tree; each sub-entry carries its own form and links (R6).

### Implementation for User Story 1

- [ ] T014 [US1] Implement `plan_reversals(copied_senses, src_project, target, ctx, resolver_cache, dropped)` in `src/gramtrans/Lib/reversals.py`: enumerate `ReversalIndexOperations.GetAll()`, gather in-scope entries via `IReversalIndex.EntriesForSense(copied_senses)` (or `SensesRS` membership scan), skip empty indexes, map index WS via `ws_mapping` (drop+skip if unmappable), and build one `ReversalDecision` per in-scope entry (target index existing/to-create, copied-only sense links + dropped members, reversal-form alternatives, recursive sub-entry decisions). Decision-only; no writes; never throws. (Contract: reversal-walk.md)
- [ ] T015 [US1] Implement the recursive sub-entry decision builder in `src/gramtrans/Lib/reversals.py` reusing the `owned.py` walk pattern for `SubentriesOS` (each sub-entry gets form copy + recursion; category resolution stubbed to LINK-if-present here, completed in US2).
- [ ] T016 [US1] Implement `apply_reversals(decisions, target, ctx, resolver_cache, dropped)` in `src/gramtrans/Lib/reversals.py` (Move-mode only): create target index via `ReversalIndexOperations.Create(name, target_ws)` when the decision says so; create each entry via `ReversalIndexEntryOperations.Create(index, form, sense)` preserving source GUID where the create path allows; write `ReversalForm` per mapped WS (non-destructive); link `SensesRS` to copied target senses; recurse `SubentriesOS`. (Contract: reversal-walk.md)
- [ ] T017 [US1] Register `ReversalIndexEntry` (and `ReversalIndex` where a carrier applies) as residue carriers in `src/gramtrans/Lib/residue.py`; call `apply_residue` on created entries/indexes in `apply_reversals`. Fall back to the run-report creation record where no residue field exists (R7).
- [ ] T018 [US1] Hook the reversal walk into the sense-copy path: in `src/gramtrans/Lib/categories.py`, after the sense closure is established, invoke `plan_reversals` (decision) so reversal decisions join the plan.
- [ ] T019 [US1] Surface reversal decisions in Preview: in `src/gramtrans/Lib/preview.py`, render each `ReversalDecision` under its per-WS index with an Add/Link action, and list each reversal `DroppedItemRecord` in the unified dropped-items section (Principle III — before any write).
- [ ] T020 [US1] Wire `apply_reversals` into the Move execution path in `src/gramtrans/Lib/transfer.py` so reversal entries are written only in Move mode, after the plan is shown.

**Checkpoint**: Reversal entries reproduce end-to-end with forms, sense links, sub-entries, and the WS gate — quickstart S1 + S3 pass. Category resolution is LINK-if-present (US2 completes the three-way).

---

## Phase 4: User Story 2 - Reversal categories resolve against the per-index list (Priority: P2)

**Goal**: Resolve each entry's `PartOfSpeechRA` against the **target index's own**
`PartsOfSpeechOA` (never `LangProject.PartsOfSpeechOA`) via the 024 resolver, with the full
three-way disposition and shared per-run caching.

**Independent Test**: Run quickstart Scenario 2: with a fixture where an entry's
`PartOfSpeechRA` is (a) a custom category absent from the target index and (b) a renamed default
present-but-diverged, Preview shows CREATE (+ ancestor chain) for the custom in the target
index's `PartsOfSpeechOA` and LINK + divergence record for the shared default; Move creates the
custom (same GUID), links it, leaves the shared default unmutated, and never touches
`LangProject.PartsOfSpeechOA`.

### Tests for User Story 2 ⚠️ (write first, must FAIL before implementation)

- [ ] T021 [P] [US2] In `tests/unit/test_reversal_category_resolve.py`: test target-list binding — the `PartOfSpeechRA` `ReferenceFieldSpec.target_list_path` resolves to the target reversal **index's** `PartsOfSpeechOA`, and `LangProject.PartsOfSpeechOA` is never read/written (R5).
- [ ] T022 [P] [US2] In `tests/unit/test_reversal_category_resolve.py`: test CREATE path — a custom category absent from the target index resolves to `CREATE` with the ancestor chain created top-down under `SubPossibilitiesOS`, GUIDs preserved (hierarchical=True).
- [ ] T023 [P] [US2] In `tests/unit/test_reversal_category_resolve.py`: test diverged dispositions — same-GUID diverged + `not _is_protected` → `UPDATE` (non-destructive); same-GUID diverged + `_is_protected` → `REPORT_DROPPED` + LINK existing (owner_kind `ReversalIndexEntry`, field `PartOfSpeechRA`).
- [ ] T024 [P] [US2] In `tests/unit/test_reversal_category_resolve.py`: test absent-list + caching — no `PartsOfSpeechOA` on the target index → `REPORT_DROPPED` (reason `target reversal category list absent`); a category used by K entries is created at most once via the shared 024 resolver cache.

### Implementation for User Story 2

- [ ] T025 [US2] Build the `PartOfSpeechRA` `ReferenceFieldSpec` in `src/gramtrans/Lib/reversals.py` exactly per the reversal-category-resolution.md contract (owner_class `ReversalIndexEntry`, ATOMIC, `target_list_path = lambda tgt_index: tgt_index.PartsOfSpeechOA`, hierarchical=True) and route the entry's category through `references.decide_reference` in `plan_reversals`, replacing the US1 LINK-if-present stub (T015).
- [ ] T026 [US2] In `apply_reversals` (`src/gramtrans/Lib/reversals.py`), apply the `PartOfSpeechRA` `ReferenceDecision` via `references.apply_reference` against the target index `PartsOfSpeechOA`, passing the shared `resolver_cache` so a shared reversal category is created at most once; use `protection._is_protected` for custom-vs-shared classification.
- [ ] T027 [US2] Ensure the category `DroppedItemRecord`s (shared-default divergence, absent list) flow into the same unified report and appear in Preview (extend the T019 rendering; no separate reversal report section).

**Checkpoint**: US1 + US2 together fully reproduce reversal entries with correctly resolved
per-index categories — quickstart S1, S2, S3 pass.

---

## Phase 5: User Story 3 - Configuration views copied (Priority: P3)

**Goal**: Copy the source project's dictionary and reversal `.fwdictconfig` configuration-view
files into the target project's parallel `ConfigurationSettings` subdirs, planned as
Add/Overwrite/Skip, reporting any WS/custom-field/style reference the target lacks — never
silent, never destructive.

**Independent Test**: Run quickstart Scenario 4: with a source having
`ConfigurationSettings/ReversalIndex/*.fwdictconfig` (and/or `Dictionary/*.fwdictconfig`),
Preview lists each file as ADD/OVERWRITE/SKIP plus any `ConfigView` missing-reference records;
Move places the files in the target's parallel subdirs, backs up any overwritten file to
`*.gtbak`, and the target opens in FLEx with the view available (missing refs degrade gracefully).

### Tests for User Story 3 ⚠️ (write first, must FAIL before implementation) — use temp dirs

- [ ] T028 [P] [US3] In `tests/unit/test_config_view_copy.py`: test enumerate + plan — `plan_config_views` over temp source/target dirs yields `ADD` for absent, `SKIP` for byte-identical, `OVERWRITE` for differing `.fwdictconfig` files (R8).
- [ ] T029 [P] [US3] In `tests/unit/test_config_view_copy.py`: test absent-reference scan — a `.fwdictconfig` referencing a custom field / WS / style the target lacks yields `ConfigViewRecord.missing_refs` with `DroppedItemRecord`s (owner_kind `ConfigView`, `field_name` = reference kind, reason naming the referenced label) (R9).
- [ ] T030 [P] [US3] In `tests/unit/test_config_view_copy.py`: test apply — `apply_config_views` copies ADD/OVERWRITE files, writes a `*.gtbak` backup before OVERWRITE, does nothing for SKIP, and no file is written by the plan pass (Principle III); appends every `missing_ref` to the run `dropped` collector.

### Implementation for User Story 3

- [ ] T031 [US3] Implement `resolve_config_dirs(project)` and `plan_config_views(src_project, tgt_project)` in `src/gramtrans/Lib/config_views.py`: derive on-disk project dirs from the LCM cache path, enumerate `*.fwdictconfig` under `ConfigurationSettings/{Dictionary,ReversalIndex}/`, compute Add/Overwrite/Skip via `filecmp`, and scan each file's `writingSystem=`/`Option id`/custom-field/`style=` references against the target (via `ws_mapping` + target custom-field/style lists), collecting `missing_refs`. Decision-only; create target subdirs if missing. (Contract: config-view-copy.md)
- [ ] T032 [US3] Implement `apply_config_views(records, dropped)` in `src/gramtrans/Lib/config_views.py` (Move-mode only): copy ADD/OVERWRITE (`shutil.copy2`), back up the existing target to `*.fwdictconfig.gtbak` before OVERWRITE, skip SKIP, and append each record's `missing_refs` to `dropped`.
- [ ] T033 [US3] Wire config-view planning into Preview and apply into Move: surface each `ConfigViewRecord` action + missing-ref records in `src/gramtrans/Lib/preview.py`, and call `apply_config_views` from the Move path in `src/gramtrans/Lib/transfer.py` (after the plan is shown).

**Checkpoint**: All three stories functional — the target opens with working dictionary/reversal
views and reproduced reversal content; quickstart S1–S4 pass.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Unified never-silent verification, census coverage, and regression safety.

- [ ] T034 Extend the fidelity census: create/extend `tests/verification/fidelity_census.py` model map with reversal classes (`ReversalIndexEntry`: `SensesRS`, `PartOfSpeechRA`, `ReversalForm`, `SubentriesOS`) so an unhandled reversal field on a model upgrade is caught offline (R10). (Depends on 024's census harness existing.)
- [ ] T035 [P] Verify the unified never-silent report (quickstart Scenario 5): add a cross-cutting assertion (in `tests/unit/test_reversal_walk.py` or a small integration test) that reversal drops (Part A) and config `missing_refs` (Part B) land in the **one** 024 dropped-items report, each naming owner/field/item name+GUID (or config reference) and reason.
- [ ] T036 [P] Regression gate (quickstart): confirm a transfer of a project with no reversal content and no `.fwdictconfig` files plans no reversal entries, copies no config files, leaves the dropped-items report empty, and produces output identical to a 024-only run.
- [ ] T037 [P] Run `quickstart.md` end-to-end against the Ejagham Mini → disposable `*-GT-Test` pair (Scenarios 1–5) and record pre/post evidence per STATUS.md conventions.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **T004 (024 gate) BLOCKS everything** — 025 reuses 024's `references.py`/`owned.py`/`report.py`. Do not proceed past T004 until 024 has landed on the worktree.
- **User Stories (Phase 3–5)**: All depend on Foundational completion.
  - US1 (P1) is the MVP and should be built first.
  - US2 (P2) depends on US1 (it replaces the US1 category stub at T015/T025) — sequential after US1.
  - US3 (P3) is independent of US1/US2 (separate file `config_views.py`, file-I/O path) — can run in parallel with US1/US2 once Foundational is done.
- **Polish (Phase 6)**: Depends on the stories it verifies (T034 needs the walk + census harness; T035–T037 need all in-scope stories complete).

### User Story Dependencies

- **US1 (P1)**: Foundational only. No dependency on other stories.
- **US2 (P2)**: Depends on US1 (completes the `PartOfSpeechRA` resolution the US1 walk stubbed).
- **US3 (P3)**: Foundational only. Independent of US1/US2 — different file, no shared state beyond the `dropped` collector and Preview/transfer wiring.

### Within Each User Story

- Tests (T009–T013, T021–T024, T028–T030) MUST be written and FAIL before their implementation.
- In `reversals.py`: `plan_reversals`/sub-entry builder before `apply_reversals`; both before Preview/transfer wiring.
- Preview wiring before transfer (Move) wiring (Principle III — plan shown before writes).

### Parallel Opportunities

- Setup: T002, T003 parallel with T001.
- Foundational: T005, T006 parallel (same file `models.py` — coordinate the single edit or sequence them; T007/T008 are separate files and parallel).
- US1 tests T009–T013 all [P] (same test file, independent test functions — safe to author together).
- US2 tests T021–T024 all [P]; US3 tests T028–T030 all [P].
- **US3 can be developed in parallel with US1+US2** by a second implementer (separate `config_views.py`).
- Polish T035–T037 all [P].

---

## Parallel Example: User Story 1 tests

```bash
# Author all US1 reversal-walk tests together (they FAIL until T014–T020 land):
Task: "Test entry discovery / closure scoping in tests/unit/test_reversal_walk.py"
Task: "Test WS gate drop in tests/unit/test_reversal_walk.py"
Task: "Test partial SensesRS reporting in tests/unit/test_reversal_walk.py"
Task: "Test ReversalForm non-destructive copy in tests/unit/test_reversal_walk.py"
Task: "Test SubentriesOS recursion in tests/unit/test_reversal_walk.py"
```

## Parallel Example: cross-story staffing

```bash
# Once Foundational (T004–T008) is complete, two tracks proceed concurrently:
Developer A: US1 (T009–T020) -> US2 (T021–T027)      # Part A, sequential
Developer B: US3 (T028–T033)                          # Part B, independent
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1 (Setup) + Phase 2 (Foundational) — **T004 024 gate is mandatory**.
2. Complete Phase 3 (US1): reversal entries ride along with copied senses (forms, sense links, sub-entries, WS gate).
3. **STOP and VALIDATE**: run quickstart Scenario 1 + Scenario 3 against Ejagham Mini → GT-Test.
4. This is a shippable increment — the target now carries reversal entries even if category
   resolution is only LINK-if-present.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → validate (S1, S3) → the lexicon's reversal entries come along. **MVP.**
3. US2 → validate (S2) → categories resolve correctly against the per-index list.
4. US3 → validate (S4) → dictionary/reversal views copied; target opens with working views.
5. Polish → census + never-silent + regression gate (S5, S6).

### Parallel Team Strategy

- Everyone lands Foundational together (especially the 024 gate).
- Developer A takes Part A (US1 → US2); Developer B takes Part B (US3) — different files, no
  blocking dependency. They converge at Preview/transfer wiring and the Polish never-silent check.

---

## Notes

- **024 is a hard dependency.** `references.py` and `owned.py` were not present on this worktree
  at task-generation time; T004 is a real gate, not a formality.
- flexicon-direct only (Principle II) for Part A; Part B is plain file I/O (outside the LCM
  surface — the only file path in the module).
- Reversal categories target the **per-index** `PartsOfSpeechOA`, never
  `LangProject.PartsOfSpeechOA` — do not reuse the transferred grammar-POS objects.
- Every non-reproduced item (Part A or B) produces exactly one `DroppedItemRecord` in the one
  unified 024 report — the never-silent backstop.
- Validate live via FLExTools MCP against Ejagham Mini / Ejagham Full GT-Test (CLAUDE.md Rules).
- Commit after each task or logical group; stop at any checkpoint to validate a story.
