---
description: "Dependency-ordered tasks for Texts & Wordforms (026)"
---

# Tasks: Texts & Wordforms

**Input**: Design documents from `specs/026-texts-wordforms/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓ (5 contracts)

**Tests**: INCLUDED — the plan (`plan.md` Testing + Project Structure) explicitly enumerates a
7-file unit suite under `tests/unit/` plus the extended offline fidelity census as feature
deliverables, so test tasks are generated per the design artifacts.

**Organization**: Tasks are grouped by user story (P1→P3) so each story is independently
implementable and testable. US1 is the MVP.

**Work location** (CLAUDE.md Git Workflow): all source/test work happens on a dedicated worktree
`../GramTrans-026-texts-wordforms` on branch `026-texts-wordforms`. Spec files (this folder) stay
on `main`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US5 for user-story tasks; Setup/Foundational/Polish have no story label

## Path Conventions

Single-project FlexTools module. Source under `src/gramtrans/Lib/` (UI under
`src/gramtrans/Lib/ui/`), tests under `tests/unit/` and `tests/verification/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the worktree and confirm the hard dependency before any code lands.

- [ ] T001 Create the feature worktree `../GramTrans-026-texts-wordforms` on branch `026-texts-wordforms` (CLAUDE.md Git Workflow); all Phase 2+ edits happen there, not on `main`.
- [ ] T002 Verify prerequisites: 024-lexicon-reference-fidelity is merged to `main` (resolver `Lib/references.py`, `Lib/owned.py`, `Lib/protection.py`, `DroppedItemRecord`/`FidelityStatus` in `Lib/report.py`+`Lib/models.py`, `Lib/ws_mapping.py` all present) and flexicon installed editable (`pip install -e D:/Github/_Projects/_LEX/flexlibs2`, `pyflexicon>=4.1`). Record confirmation in `specs/026-texts-wordforms/quickstart.md` prerequisites.
- [ ] T003 [P] Create module stub `src/gramtrans/Lib/texts.py` with the four contract signatures (`plan_texts`, `apply_texts`) from `contracts/text-structure-walk.md` and a module docstring citing FR-001..005/017.
- [ ] T004 [P] Create module stub `src/gramtrans/Lib/wordforms.py` with the contract signatures (`plan_analyses`, `resolve_or_report_category`, `apply_analyses`, `plan_morph_bundles`, `apply_morph_bundles`, `plan_alignment`, `apply_alignment`, `plan_agent`, `apply_agent`) from the four wordform contracts, docstring citing FR-006..016.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Model types, selection surface, residue registration, and the plan/apply dispatch hook
that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T005 Add the 026 enums to `src/gramtrans/Lib/models.py`: `EvalVerdict` (`HUMAN_APPROVED`/`HUMAN_DENIED`/`NEEDS_REVIEW`) and `AlignmentTokenKind` (`ANALYSIS`/`WORDFORM`/`PUNCTUATION`) per data-model.md Enums.
- [ ] T006 Add the 026 dataclasses to `src/gramtrans/Lib/models.py` (depends on T005): `TextTransferPlan`, `ParagraphPlan`, `SegmentPlan`, `AnalysisPlan`, `MorphBundlePlan`, `IdentityRef`, `GlossPlan`, `ProvisionedAgent` per data-model.md Dataclasses; reuse (do not redefine) `DroppedItemRecord`/`FidelityStatus`/`ReferenceDecision`/`PlannedAction` from 024.
- [ ] T007 Add **Texts** as a Model-A selectable category in `src/gramtrans/Lib/selection.py` (per-text pick, not all-or-nothing; wordforms ride along as closure, FR-001/FR-001a).
- [ ] T008 Add the Texts item-picker page to `src/gramtrans/Lib/ui/selection_wizard.py`, riding the existing wizard, populated from `TextOperations.GetAll()` (SC-004 deselect-per-text).
- [ ] T009 Register residue carriers in `src/gramtrans/Lib/residue.py`: `Text` (+ `StText`/`StTxtPara`) and `WfiWordform`/`WfiAnalysis` using the Description-append `[GT-Tag]` fallback (R8, constitution residue clause).
- [ ] T010 Wire the text-transfer dispatch hook into `src/gramtrans/Lib/preview.py` (build TextTransferPlans when Texts selected) and `src/gramtrans/Lib/transfer.py` (execute them in Move mode, after 024+025 in import order per R8); reuse the `Lib/conflict.py` UPDATE (source-preferring, never-blank) semantic for re-run (FR-021).

**Checkpoint**: Foundation ready — user stories can begin.

---

## Phase 3: User Story 1 - Interlinear texts come across with structure and translations (Priority: P1) 🎯 MVP

**Goal**: Move selected texts with title/abbreviation/source/translation-complete flag,
paragraph/segment structure, baseline, free/literal translations, notes, and genres.

**Independent Test**: Select N texts, Preview then Move against a fresh target; confirm each text's
title, paragraph/segment count, baseline, translations, notes, and genre labels match source;
missing genres are created via the resolver, WS-unmappable strings reported (spec US1 Independent Test).

### Tests for User Story 1

- [ ] T011 [P] [US1] Write `tests/unit/test_text_structure_walk.py` — text/para/segment reproduction, free/literal translations + notes, genre create-via-resolver (FR-005 sc.2), WS-mapping gate skip+report (FR-020 sc.3), non-destructive re-run (FR-021). Must fail before T012–T014.

### Implementation for User Story 1

- [ ] T012 [US1] Implement `plan_texts(...)` in `src/gramtrans/Lib/texts.py` per `contracts/text-structure-walk.md`: identity disposition (GUID → `TextOperations.Find(title)` → ADD/UPDATE/SKIP, FR-021), `GenresRC` via `references.decide_reference` against `LangProject.GenreListOA` (create-allowed, resolver_cache, FR-005), owned walk `ContentsOA.ParagraphsOS → SegmentOperations.GetAll` building `ParagraphPlan`/`SegmentPlan` with WS-gated baseline/`GetFreeTranslation`/`GetLiteralTranslation`/`GetNotes` (unmapped WS → `DroppedItemRecord`, FR-020, FR-002/003/004). Zero-analysis text still yields a full plan (edge case). No writes.
- [ ] T013 [US1] Implement `apply_texts(...)` in `src/gramtrans/Lib/texts.py`: `TextOperations.Create(name, genre)` (preserve source GUID where permitted else record mapping, FR-022), set abbreviation/source/`SetIsTranslated` (FR-002); `ParagraphOperations.Create(text, content, wsHandle)` + segments; write baseline/`SetFreeTranslation`/`SetLiteralTranslation`/notes non-destructively (FR-021); apply genre `ReferenceDecision`s (`references.apply_reference`); `apply_residue` (R8).
- [ ] T014 [US1] Surface each `TextTransferPlan` as Add/Update/Skip/Report lines in `src/gramtrans/Lib/preview.py` and execute via `apply_texts` in `src/gramtrans/Lib/transfer.py` (FR-019); route dropped genres/WS through the 024 unified report channel (FR-023).

**Checkpoint**: US1 fully functional — a corpus of texts moves with structure + translations, MVP demoable.

---

## Phase 4: User Story 2 - Human-evaluated analyses ride along with their texts (Priority: P1)

**Goal**: Reproduce human-approved and human-denied analyses on the target's wordforms, wired to
target lexical objects by identity, re-aligned to segments, with a provisioned human agent owning
every evaluation. Parser-only/un-evaluated analyses never copied.

**Independent Test**: On a source wordform with human-approved + human-denied + two parser-only
analyses, transfer and confirm exactly the two human analyses appear (verdicts preserved), morph
bundles wired by identity, zero parser-only created (spec US2 Independent Test, SC-001/002).

### Tests for User Story 2

- [ ] T015 [P] [US2] Write `tests/unit/test_human_eval_gate.py` — copy iff `GetHumanEvaluation` non-null; parser-only/un-evaluated excluded and counted (FR-006, SC-001). Fail-first.
- [ ] T016 [P] [US2] Write `tests/unit/test_analysis_verdict.py` — approve/deny verdict preserved (FR-007); agent provisioned once and reused, not duplicated (FR-009). Fail-first.
- [ ] T017 [P] [US2] Write `tests/unit/test_morph_bundle_wiring.py` — resolvable morph-bundle refs wired by GUID identity (FR-010) (needs-review/deny cases added in US3 T028). Fail-first.
- [ ] T018 [P] [US2] Write `tests/unit/test_segment_alignment.py` — `AnalysesRS` reproduced in source token order incl. `WORDFORM`/`PUNCTUATION` slots (FR-012, SC-006). Fail-first.

### Implementation for User Story 2

- [ ] T019 [US2] Build the per-run **target GUID index** on the run context (once, from the 024/025 copy-set + live target) in `src/gramtrans/Lib/wordforms.py`, providing O(1) source-GUID → target lexical-object lookup for morph-bundle wiring (R4, plan.md Performance Goals). NOT the 024 possibility resolver.
- [ ] T020 [US2] Implement `plan_agent(...)` + `apply_agent(...)` in `src/gramtrans/Lib/wordforms.py` per `contracts/human-agent-provisioning.md`: prefer `AgentOperations.GetHumanAgents()`/`FindByType` (reuse → Link), else `Create(name)`+`SetHuman` (Add); cache the single agent on ctx for every evaluation this run (FR-009, R3).
- [ ] T021 [US2] Implement `plan_analyses(...)` + `resolve_or_report_category(...)` in `src/gramtrans/Lib/wordforms.py` per `contracts/analysis-human-eval-walk.md`: keep only analyses with non-null `GetHumanEvaluation` (FR-006), set `verdict` from `Approves` (FR-007), resolve `CategoryRA` via the resolve-or-report variant against `LangProject.PartsOfSpeechOA` (CREATE→REPORT_DROPPED, FR-011), capture WS-gated wordform form + `spelling_status`. No writes.
- [ ] T022 [US2] Implement `apply_analyses(...)` in `src/gramtrans/Lib/wordforms.py`: find-or-create target wordform by form+WS (global identity, R7), set spelling status (`WordformOperations.ApproveSpelling`/status setter, non-destructive), `WfiAnalysisOperations.Create(wordform)` (preserve GUID where permitted, FR-022), apply category decision (`SetCategory` when resolved), and write verdict — `HUMAN_APPROVED` (not needs-review) → `ApproveAnalysis` owned by the provisioned agent; `HUMAN_DENIED` → `RejectAnalysis`; `apply_residue` (R8). (NEEDS_REVIEW no-verdict path completed in US3 T027.)
- [ ] T023 [US2] Implement `plan_morph_bundles(...)` + `apply_morph_bundles(...)` in `src/gramtrans/Lib/wordforms.py` per `contracts/morph-bundle-identity-wiring.md`: build four `IdentityRef`s (`MorphRA`/`MsaRA`/`SenseRA`/`InflTypeRA`) via the T019 GUID index; `WfiMorphBundleOperations.Create` in source order, always `SetForm`, wire each resolved ref (`SetMSA`/`SetSense`/`SetMorphType`/`SetInflType`/`SetInflectionClass`). Unresolved-ref reporting/downgrade completed in US3.
- [ ] T024 [US2] Implement `plan_alignment(...)` + `apply_alignment(...)` in `src/gramtrans/Lib/wordforms.py` per `contracts/segment-alignment.md`: read `SegmentOperations.GetAnalyses`, classify tokens (`AlignmentTokenKind`), rebuild target `AnalysesRS` in source order via the raw LCM surface (`project.GetService(...)` + `CastingOperations.cast_to_concrete`, Principle II fallback, R5); preserve punctuation/bare-wordform slots (FR-012, SC-006). Carry the R5 `[PROBE]` note.
- [ ] T025 [US2] Delegate from `plan_texts`/`apply_texts` (T012/T013) into the wordform walk per segment, and surface analysis/agent/morph-bundle/alignment decisions in `preview.py` + execute in `transfer.py` (FR-019); route through the unified report (FR-023).

**Checkpoint**: US1 + US2 both work — human analyses reproduce and align for the fully-resolvable case.

---

## Phase 5: User Story 3 - Partial analyses preserved, never silently dropped or falsely approved (Priority: P2)

**Goal**: An approved analysis with an unresolvable morpheme is copied with that morpheme unlinked
and downgraded to needs-review (no human-approve written); a denied analysis keeps its deny; every
gap is reported. Builds on US2.

**Independent Test**: Source approved analysis with 3 morph bundles (2 senses present, 1 absent) →
2 wired, 1 unlinked, analysis needs-review, missing sense reported; denied analysis with
unresolvable morpheme → deny retained, morpheme reported, not downgraded (spec US3 Independent Test).

### Implementation for User Story 3

- [ ] T026 [US3] In `plan_analyses` (`src/gramtrans/Lib/wordforms.py`), compute `needs_review = (verdict == HUMAN_APPROVED and any unresolved IdentityRef)` (FR-014); a `HUMAN_DENIED` analysis is **never** downgraded (FR-015).
- [ ] T027 [US3] Complete the NEEDS_REVIEW apply path in `apply_analyses` (`src/gramtrans/Lib/wordforms.py`): create the analysis and write **no** human evaluation (natural no-verdict state, R2/FR-014) — no in-FLEx marker, no proxy-deny; leave unresolved morph-bundle fields unset in `apply_morph_bundles`.
- [ ] T028 [US3] Emit one `DroppedItemRecord` per unresolved `IdentityRef` (owner_kind `WfiMorphBundle`, field = ref name, reason "referent not copied to target") and per needs-review downgrade, with text/segment/wordform/morpheme context (FR-016), through the unified report (FR-023); extend `tests/unit/test_morph_bundle_wiring.py` with the needs-review-approve, retained-deny, and report-context cases (FR-014/015/016, SC-002/003).

**Checkpoint**: Referential completeness holds — no false approvals, no silent drops.

---

## Phase 6: User Story 4 - Adjacent human-curated data transfers with the analyses (Priority: P2)

**Goal**: Word-level glosses (under the human-eval gate), wordform spelling status, and analysis
grammatical category ride along with the analyses.

**Independent Test**: Source with human-evaluated glosses, approved-spelling wordforms, and
category-bearing analyses → target reproduces the human glosses only, the spelling statuses, and
categories resolved against target POS (unresolved reported) (spec US4 Independent Test).

### Tests for User Story 4

- [ ] T029 [P] [US4] Write `tests/unit/test_adjacent_data.py` — human-approved `WfiGloss` reproduced but parser-only gloss excluded (FR-008 sc.1); spelling status reproduced (FR-013 sc.2); category resolve-or-report, absent POS left unset + reported, never created (FR-011 sc.3). Fail-first.

### Implementation for User Story 4

- [ ] T030 [US4] In `plan_analyses`/`apply_analyses` (`src/gramtrans/Lib/wordforms.py`), gate `WfiGloss` by human evaluation (`GetGlosses` filtered, FR-008) into `GlossPlan`s and copy only human-evaluated glosses (`WfiGlossOperations` set/`SetGloss`).
- [ ] T031 [US4] Confirm/finalize spelling-status reproduction onto the target wordform in `apply_analyses` (`WordformOperations.ApproveSpelling`/status setter, non-destructive, FR-013).
- [ ] T032 [US4] Finalize category resolve-or-report in `apply_analyses` (`SetCategory` when resolved; unset + `DroppedItemRecord` when absent, FR-011) and confirm it flows to the unified report (FR-023).

**Checkpoint**: Copied interlinear is visibly complete — glosses, spelling, categories present.

---

## Phase 7: User Story 5 - Text tagging comes across (Priority: P3)

**Goal**: The text-markup tag possibility list and the per-segment tag references are reproduced
(tags absent from target created via the resolver; unresolvable tags reported).

**Independent Test**: Source text carrying markup tags → target holds the tag possibilities and
per-segment tag references, unresolvable tags reported (spec US5 Independent Test).

### Tests for User Story 5

- [ ] T033 [P] [US5] Write `tests/unit/test_text_markup_tags.py` — tag list + per-segment tag refs reproduced; tag absent from target created via resolver; unresolvable tag reported (FR-017). Fail-first.

### Implementation for User Story 5

- [ ] T034 [US5] In `plan_texts` (`src/gramtrans/Lib/texts.py`), resolve per-segment text-markup tag references via `references.decide_reference` against the text-markup tag list (create-allowed, GUID-preserving, resolver_cache) into `SegmentPlan.tag_decisions` (FR-017, R6).
- [ ] T035 [US5] In `apply_texts`, apply the tag `ReferenceDecision`s (`references.apply_reference`) — referenced tag possibilities + per-segment refs; route any unresolvable tag to the unified report (FR-017/023).

**Checkpoint**: All five user stories independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Fidelity verification, validation runs, and the deferred live [PROBE] confirmations.

- [ ] T036 [P] Extend `tests/verification/fidelity_census.py` with the 7 new classes (`Text`, `StTxtPara`, `Segment`, `WfiWordform`, `WfiAnalysis`, `WfiMorphBundle`, `WfiGloss`) so every populated source field is either reproduced or carries a matching `DroppedItemRecord` (SC-003).
- [ ] T037 [P] Run the offline unit gate (all 7 `tests/unit/test_*` files from quickstart.md) and the extended census; confirm all pass, zero silent losses.
- [ ] T038 Run the quickstart.md validation scenarios (US1–US5 + re-run non-destructive check) as Preview then Move against the `Ejagham Mini → Ejagham Full GT-Test` pair; confirm SC-001..SC-007 (re-run shows SKIP/UPDATE not ADD, SC-005).
- [ ] T039 Execute the deferred live [PROBE] confirmations once the MCP `run_module`/CLR-init path is restored and record results in `specs/026-texts-wordforms/probe-results.md`: R2 (needs-review renders unanalyzed-but-present, SC-006 context), R5 (exact `AnalysesRS` write path), R6 (target-list accessors `GenreListOA` / text-markup tag list owner).
- [ ] T040 Verify residue tagging (`[GT-Tag]` Description-append) is present and non-destructive on every added/overwritten text/paragraph/wordform/analysis (R8, constitution residue gate).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup; **BLOCKS all user stories** (models, selection, dispatch hook).
- **User Stories (Phase 3–7)**: all depend on Foundational.
  - US1 (P1) is the MVP and has no dependency on other stories.
  - US2 (P1) depends only on Foundational; T025 delegates from US1's `plan_texts`/`apply_texts`, so US2 apply-time integration lands cleanest after T012/T013 exist (US2 logic itself is independent).
  - US3 (P2) extends US2 (`plan_analyses`/`apply_analyses`/`apply_morph_bundles`); do after US2.
  - US4 (P2) adds independent fields to US2's analysis path; do after US2, parallelizable with US3.
  - US5 (P3) extends US1's `texts.py`; do after US1, independent of US2–US4.
- **Polish (Phase 8)**: depends on the desired stories being complete.

### Within Each User Story

- Tests written first and failing before implementation.
- Plan (`plan_*`, decision, no writes) before apply (`apply_*`, writes) — Principle III.
- `preview.py`/`transfer.py` surfacing after the plan/apply pair exists.

### Parallel Opportunities

- Setup: T003, T004 in parallel (different new files).
- US2 tests T015–T018 in parallel (different test files); US4 T029, US5 T033 in parallel with each other and with US2/US3 test-writing.
- After Foundational: US1 and US2 core logic can be built concurrently by different developers (US2's `wordforms.py` is a separate file from US1's `texts.py`); US3/US4 branch off US2, US5 off US1.
- Polish T036, T037 in parallel.
- ⚠️ Serialization points: T005→T006 (same file `models.py`); T012/T013/T034 all edit `texts.py`; T021/T022/T023/T024/T026/T027/T030/T031/T032 all edit `wordforms.py` — order within each file per task IDs.

---

## Parallel Example: User Story 2 tests

```bash
# Launch all US2 test-writing tasks together (different files):
Task: "Write tests/unit/test_human_eval_gate.py"      # T015
Task: "Write tests/unit/test_analysis_verdict.py"      # T016
Task: "Write tests/unit/test_morph_bundle_wiring.py"   # T017
Task: "Write tests/unit/test_segment_alignment.py"     # T018
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational (blocks everything).
2. Phase 3 US1 (texts + structure + translations + genres).
3. **STOP and VALIDATE**: quickstart US1 scenario against a fresh target — a corpus of texts moves standalone.
4. Demo the MVP.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → validate → demo (MVP: texts move).
3. US2 → validate → demo (human analyses ride along, fully-resolvable case).
4. US3 → validate (partial analyses preserved / needs-review).
5. US4 → validate (glosses, spelling, category).
6. US5 → validate (tags).
7. Polish: census + full validation + live [PROBE]s.

---

## Notes

- [P] = different files, no dependency on incomplete work.
- Every REUSE seam (`references.py`, `owned.py`, `protection.py`, `ws_mapping.py`, `conflict.py`, `report.py`) exists from 024 — verified present in `src/gramtrans/Lib/`. Do not re-implement.
- All new/modified source and tests are committed on the `026-texts-wordforms` worktree; this `specs/` folder stays on `main` (CLAUDE.md Git Workflow).
- Three open `[PROBE]` items (R2/R5/R6) are gated on the MCP `run_module` runtime and tracked in T039 — none blocks the offline unit gate (T037), the primary acceptance gate.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
