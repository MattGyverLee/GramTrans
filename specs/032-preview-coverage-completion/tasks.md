---
description: "Task list for Preview Coverage Completion for Grammar Categories"
---

# Tasks: Preview Coverage Completion for Grammar Categories

**Input**: Design documents from `/specs/032-preview-coverage-completion/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (preview-props.md, ws-mapping-default.md, adhoc-loss-probe.md)

**Tests**: INCLUDED. The spec's Definition of Done (SC-008) mandates offline unit tests plus a read-only live-render proof for US1-US4 and a read-only probe for US5. Test tasks are therefore first-class here and, where a fix must be load-bearing (US3 regression, SC-003), the failing test is written before the fix.

**Organization**: Tasks are grouped by user story (US1-US5). All preview work is read-only (FR-010); no destructive Move is required, so no attended `needs_human` gate applies.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1-US5 mapping to spec.md user stories
- All paths are repo-relative; source lives under `src/gramtrans/`, tests under `tests/`

## Path Conventions

- Preview core: `src/gramtrans/Lib/merge_preview.py` (Stage-1 readers only; Stage-2 diff/render unchanged)
- WS mapping: `src/gramtrans/Lib/ws_mapping.py`
- Reused read helpers: `src/gramtrans/Lib/texts.py`, `src/gramtrans/Lib/references.py`
- Never-silent report surface: `src/gramtrans/Lib/report.py`
- US5 probe: `debug/probe_adhoc_loss.py`
- Unit tests: `tests/unit/`; live integration: `tests/integration/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the worktree and test scaffolding for read-only preview-coverage work.

- [X] T001 Create the feature worktree `../GramTrans-032-preview-coverage-completion` on branch `032-preview-coverage-completion` per the Git Workflow Protocol (implementation/code changes live on the worktree; spec artifacts stay on `main`)
- [X] T002 [P] Scaffold the new offline test module `tests/unit/test_032_preview_coverage.py` with empty test stubs for the eight-category non-blank matrix and the Natural Class before/after regression (bodies filled per-story below)
- [X] T003 [P] Confirm the live test pair `Ejagham Mini` (source) -> `Ejagham Full GT-Test` (target) plus read-only cross-checks (`Esperanto`, `Mbugwe Lizzie HCPractice`) are reachable via FLExToolsMCP; record which projects populate each of the eight categories

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Verify live data shapes (FR-019) and establish the shared bounding helper before any reader is written. No user story reader may be built on assumed LCM shapes.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] Live-verify LCM property names and casts via FLExToolsMCP `get_object_api` for all eight categories (FR-019): `IText`/`IStText` baseline traversal; `WritingSystem` identity/role/rank; `ILexEntryType` pattern detail; `IMoMorphAdhocProhib`/`IMoAlloAdhocProhib`/compound-rule reference members; `IFsClosedFeature.ValuesOC`; `IPhRegularRule` StrucDesc/RHS/environment; `IMoInflAffixSlot` occupying affixes; `IPhNaturalClass` members/features — record confirmed shapes in research.md notes
- [X] T005 Add/confirm a shared bounded-excerpt + truncation-indicator helper in `src/gramtrans/Lib/merge_preview.py` (FR-018) reused by Text baseline, Slot affix list, and Natural Class member list, emitting a `Truncated` companion field only when content is cut
- [X] T006 Document the exact dispatch-table insertion points in `src/gramtrans/Lib/merge_preview.py` — `_CATEGORY_VALUE_TO_KEY` (~1148-1160) and `_PROPS_TABLE` (~1087-1119) — and the `_grammar_scalar_meta`/`_GRAMMAR_FIELD_ORDER` (~1661-1686) order entries required for the new fields, so all readers render deterministically

**Checkpoint**: Live shapes confirmed and shared helpers ready — user stories can begin.

---

## Phase 3: User Story 1 - See what blank-pane categories will transfer (Priority: P1) 🎯 MVP

**Goal**: Writing System, Complex Form Type, Ad hoc/Compound rule, and Text render a populated, item-specific preview instead of a blank pane.

**Independent Test**: Open each of the four category pages against a populated source/target pair, select an item, confirm the pane shows category-appropriate detail (not blank, not error).

### Tests for User Story 1 (write first, ensure FAIL before implementation) ⚠️

- [X] T007 [P] [US1] Add props-shape tests for Text, Writing System, Complex Form Type, and Ad hoc/Compound rule in `tests/unit/test_merge_preview_props.py` asserting a non-empty dict with the contracted fields (Text: Title/Baseline/Truncated; WS: Name/Code/Kind/Rank/MapsTo; CFT: Name/Abbreviation/Type; Ad hoc: Name/ReferencedElements)
- [X] T008 [P] [US1] Add non-blank-HTML tests for the four blank categories in `tests/unit/test_merge_preview_html.py` (populated fixture -> non-blank HTML)
- [X] T009 [P] [US1] Add the four blank categories to the eight-category non-blank matrix in `tests/unit/test_032_preview_coverage.py`, including the create-case (source-only) and graceful-degradation (read-failure -> label-level, not blank) edge cases per FR-011

### Implementation for User Story 1

- [X] T010 [US1] Register `texts`, `writing_systems_check`, `complex_form_types`, `adhoc_compound_rules` in `_CATEGORY_VALUE_TO_KEY` and `_PROPS_TABLE` in `src/gramtrans/Lib/merge_preview.py` so each resolves to a non-`None` reader (per contracts/preview-props.md dispatch contract)
- [X] T011 [P] [US1] Implement the Text reader in `src/gramtrans/Lib/merge_preview.py` producing `{Title (multistring), Baseline (bounded excerpt), Truncated}`, reusing `capture_vernacular`/`_walk_paragraphs` from `src/gramtrans/Lib/texts.py`; empty/non-vernacular baseline shows what exists without asserting absent content (FR-004, FR-018)
- [X] T012 [P] [US1] Implement the Writing System reader in `src/gramtrans/Lib/merge_preview.py` producing `{Name, Code, Kind (vernacular/analysis), Rank (primary/sub), MapsTo}`, with MapsTo sourced from the US4 mapping or "unresolved" (FR-001)
- [X] T013 [P] [US1] Implement the Complex Form Type reader (`ILexEntryType`) in `src/gramtrans/Lib/merge_preview.py` producing `{Name, Abbreviation, Type/pattern detail}` via `src/gramtrans/Lib/references.py` possibility-list resolvers, diff-compatible so a matching target type diffs (FR-002, FR-009)
- [X] T014 [P] [US1] Implement the Ad hoc/Compound rule reader in `src/gramtrans/Lib/merge_preview.py` producing `{Name/identity, ReferencedElements}` via `src/gramtrans/Lib/references.py` reference resolvers; referenced targets outside the current closure are described as resolvable-only, never crash (FR-003, FR-011)
- [X] T015 [US1] Wrap each new US1 reader's enrichment read with graceful degradation (FR-011): read/cast failure falls back to the label-level dict and logs via `debuglog`, never returns `None` or a blank pane

**Checkpoint**: All four blank categories render populated previews; T007-T009 pass.

---

## Phase 4: User Story 2 - See enough detail on thin-pane categories (Priority: P1)

**Goal**: Phonological Feature, Phonological Rule, and Slot show substantive content, not just Name/Abbreviation/Description.

**Independent Test**: Select an item in each of the three categories against a populated pair and confirm the pane shows the substantive detail (values, structure, affixes).

### Tests for User Story 2 (write first, ensure FAIL before implementation) ⚠️

- [X] T016 [P] [US2] Add enrichment tests in `tests/unit/test_merge_preview_enrichment.py` asserting Phon Feature surfaces `{Type, Values}`, Phon Rule surfaces `{Structure}`, and Slot surfaces `{Affixes}` beyond the label fields
- [X] T017 [P] [US2] Add the three thin categories to the non-blank matrix in `tests/unit/test_032_preview_coverage.py` and add the bounded-Slot-affix-list truncation assertion (FR-018)

### Implementation for User Story 2

- [X] T018 [P] [US2] Add the Phonological Feature enrich hook in `src/gramtrans/Lib/merge_preview.py` surfacing `{Type, Values}` from `IFsClosedFeature.ValuesOC` on top of the existing gap fields (FR-005)
- [X] T019 [P] [US2] Add the Phonological Rule enrich hook in `src/gramtrans/Lib/merge_preview.py` (mirroring `_enrich_natural_class`) surfacing `{Structure}` (StrucDesc/RHS/environment/ordering) so same-named rules are distinguishable (FR-006)
- [X] T020 [P] [US2] Add the Slot enrich hook in `src/gramtrans/Lib/merge_preview.py` surfacing `{Affixes}` (occupying affixes via MSA/affix references), bounded per FR-018, beyond Name/Optional (FR-007)
- [X] T021 [US2] Apply graceful degradation (FR-011) to all three US2 enrich hooks: failed cast/attribute logs via `debuglog` and falls back to label-level detail, never blank

**Checkpoint**: All three thin categories render substantive content; T016-T017 pass.

---

## Phase 5: User Story 3 - Natural Class values/features actually appear (Priority: P1)

**Goal**: The Natural Class preview shows resolved member segments and/or feature=value specs — fixing the regression where they are resolved but never reach render.

**Independent Test**: Select a segment-based and a feature-based natural class; confirm members and/or feature=value are visible. Establish the empty state first, then confirm the fix restores content (SC-003).

### Tests for User Story 3 (write the FAILING regression test FIRST) ⚠️

- [X] T022 [US3] Write the load-bearing regression test in `tests/unit/test_032_preview_coverage.py`: on identical fixture data assert Members/Features are ABSENT before the fix (reproduce the empty state) and PRESENT after (SC-003, FR-008) — this test must fail before T024
- [X] T023 [P] [US3] Live-pin the exact drop point via FLExToolsMCP (research.md R1): confirm the resolvers `_natural_class_members`/`_natural_class_features`/`_enrich_natural_class` produce content in isolation, then determine whether content vanishes at the finder/ops-resolution step (~1268-1294) or downstream in render; record the finding

### Implementation for User Story 3

- [X] T024 [US3] Fix the Natural Class drop point in `src/gramtrans/Lib/merge_preview.py` at the location pinned in T023 so `Members`/`Features` reach `diff_props`/`to_html` (no shape change — order entries already exist); make T022's "after" assertion pass (FR-008)

**Checkpoint**: Natural Class members/features are visible; the T022 regression test is green.

---

## Phase 6: User Story 4 - Writing-system mapping defaults for related languages (Priority: P2)

**Goal**: The WS mapping step pre-fills source primary -> target primary vernacular and source sub -> target sub by subtag suffix, using real mappings only, leaving ambiguous rows unresolved with confirm gated.

**Independent Test**: Trigger the mapping step for a multi-WS selection against a target with a known primary-vernacular + sub-WS config; confirm rows pre-populate (primary->primary, sub->sub) and confirm without manual edits when correspondence is clean; ambiguous rows stay unresolved.

### Tests for User Story 4 (write first, ensure FAIL before implementation) ⚠️

- [ ] T025 [P] [US4] Add the clean-correspondence test in `tests/unit/test_ws_mapping.py`: a related-languages pair pre-fills primary->primary and every sub->sub (incl. `eja-fonipa`->`abc-fonipa`) and confirms with no manual edits (SC-004, FR-012/FR-013)
- [ ] T026 [P] [US4] Add the ambiguity/no-correspondence tests in `tests/unit/test_ws_mapping_detect.py`: target with no primary vernacular, no target sub sharing the suffix, and >1 target sub sharing the suffix each leave the row unresolved with confirm gated; verify default is never "create"/"skip" (FR-014, FR-015)

### Implementation for User Story 4

- [ ] T027 [US4] Introduce the primary-vernacular concept and `subtag_suffix` in `_enumerate_ws` (~158) in `src/gramtrans/Lib/ws_mapping.py`: identify each side's primary vernacular WS and compute each sub WS's suffix relative to its side's primary base subtag
- [ ] T028 [US4] Implement the suffix-correspondence defaulting in `detect_ws_mismatches` (~213) / `fold_choices` (~245) in `src/gramtrans/Lib/ws_mapping.py`: primary->primary (FR-012); sub->sub by matching suffix across differing base subtags (FR-013); default is always a real target Id, never CREATE/SKIP (FR-014)
- [ ] T029 [US4] Enforce unresolved-row gating in `src/gramtrans/Lib/ws_mapping.py`: zero/ambiguous suffix match or missing target primary vernacular leaves the row unresolved and keeps `is_complete`/`validate` failing until the user resolves it (FR-015)

**Checkpoint**: WS defaults pre-fill on clean pairs and refuse to guess on ambiguity; T025-T026 pass.

---

## Phase 7: User Story 5 - Characterize Ad hoc rule transfer loss (Priority: P2)

**Goal**: A read-only probe characterizes the Ad hoc rule transfer loss, produces a root cause + scope decision, and any in-scope residual loss becomes never-silent reporting. Reproduction is out of scope (FR-016).

**Independent Test**: Run the read-only probe on a source/target pair with ad hoc rules and all stems/affixes present; produce evidence of what is/isn't reproduced plus a written root cause and scope decision.

### Implementation for User Story 5

- [ ] T030 [US5] Implement the read-only probe `debug/probe_adhoc_loss.py`: enumerate source ad hoc/compound rules and, on a target that already received all stems/affixes, characterize per-rule which portion is present vs absent; writes nothing to either project (SC-008, FR-016)
- [ ] T031 [US5] Confirm or refute the leading hypothesis in the probe output — `to_ws_map_dict` (`src/gramtrans/Lib/ws_mapping.py` ~66-85) silently dropping source WSs whose mapped target Id is absent — as it applies to the ad-hoc transfer path (research.md R5)
- [ ] T032 [US5] Produce the evidence + root-cause + scope-decision artifact under `specs/032-preview-coverage-completion/` (reproduction warranted -> follow-up-feature recommendation, OR loss unavoidable -> documented known limitation) per contracts/adhoc-loss-probe.md (FR-016, SC-006)
- [ ] T033 [US5] If in-scope loss is confirmed, wire never-silent reporting through `src/gramtrans/Lib/report.py` so the loss surfaces on the post-run statistics/report surface, consistent with the never-silent contract (FR-017)

**Checkpoint**: US5 yields a root cause + scope decision; any in-scope loss is never-silent.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Guard invariants, run the read-only live proof, and validate quickstart.

- [X] T034 Confirm the Qt-free guard `tests/unit/test_merge_preview_qt_free.py` still passes — no PyQt import leaked into the render core (SC-007)
- [X] T035 Confirm the read-only guard `tests/unit/test_preview_no_writes.py` still passes — no preview writes to any project and no Move-plan change (SC-005, FR-010)
- [ ] T036 Run the read-only live-render proof (SC-008): extend `tests/integration/test_e2e_all_categories.py` (non-blank pane per category) and `tests/integration/test_phase2_us2_ws_wizard.py` (WS default pre-fill) with `GRAMTRANS_E2E=1` against `Ejagham Mini` -> `Ejagham Full GT-Test`; no Move executed
- [X] T037 [P] Run the full offline unit suite from quickstart.md and confirm SC-001/SC-003/SC-004/SC-005/SC-007 pass; walk the quickstart Definition of Done checklist

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (readers must not be built on unverified shapes, FR-019).
- **User Stories (Phase 3-7)**: All depend on Foundational.
  - US1, US2, US3 (all P1) and US5 are largely independent and can run in parallel once Foundational is done.
  - US4 (P2) is independent but the US1 Writing System reader's `MapsTo` field reads the US4 mapping — if both are in flight, T012 can emit "unresolved" until US4 lands, so no hard ordering is required.
- **Polish (Phase 8)**: Depends on all targeted stories being complete.

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational only (dispatch registration T010 gates T011-T015).
- **US2 (P1)**: Depends on Foundational only; independent of US1.
- **US3 (P1)**: Depends on Foundational only; T022 (failing test) + T023 (drop-point pin) gate T024.
- **US4 (P2)**: Depends on Foundational only; T027 gates T028/T029.
- **US5 (P2)**: Depends on Foundational only; T030->T031->T032, and T033 only if T032 confirms in-scope loss.

### Within Each User Story

- Tests written and FAILING before implementation (especially T022 for the US3 regression, SC-003).
- Dispatch registration (T010) before US1 readers.
- `_enumerate_ws` primary-vernacular (T027) before suffix defaulting (T028) before gating (T029).

### Parallel Opportunities

- Setup: T002, T003 in parallel.
- Foundational: T004 runs in parallel with T005/T006 prep.
- US1 readers T011-T014 are different reader functions and can be written in parallel after T010; their tests T007-T009 are parallel.
- US2 enrich hooks T018-T020 are parallel; tests T016-T017 parallel.
- Across stories: US1, US2, US3, US5 can proceed in parallel once Foundational completes.

---

## Parallel Example: User Story 1

```text
# After T010 (dispatch registration), launch the four readers in parallel:
Task: "Implement Text reader in src/gramtrans/Lib/merge_preview.py"           # T011
Task: "Implement Writing System reader in src/gramtrans/Lib/merge_preview.py"  # T012
Task: "Implement Complex Form Type reader in src/gramtrans/Lib/merge_preview.py" # T013
Task: "Implement Ad hoc/Compound rule reader in src/gramtrans/Lib/merge_preview.py" # T014

# Launch the US1 test tasks in parallel (write first, expect FAIL):
Task: "Props-shape tests in tests/unit/test_merge_preview_props.py"   # T007
Task: "Non-blank HTML tests in tests/unit/test_merge_preview_html.py" # T008
Task: "Non-blank matrix + edge cases in tests/unit/test_032_preview_coverage.py" # T009
```

---

## Implementation Strategy

### MVP First (User Stories 1-3, all P1)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (live-verify shapes — CRITICAL, blocks all stories).
3. Complete Phase 3 (US1), Phase 4 (US2), Phase 5 (US3) — the three P1 decision-blindness fixes.
4. **STOP and VALIDATE**: eight-category non-blank matrix green; US3 regression load-bearing (SC-001, SC-003).
5. Read-only live-render proof for the covered categories (SC-008).

### Incremental Delivery

1. Setup + Foundational -> foundation ready.
2. US1 -> four blank panes populated -> validate (MVP increment).
3. US2 -> three thin panes enriched -> validate.
4. US3 -> Natural Class regression fixed -> validate (before/after proof).
5. US4 -> WS mapping defaults -> validate (P2 usability).
6. US5 -> ad hoc loss characterized + never-silent reporting -> validate (P2 investigation).

### Notes

- [P] tasks touch different files/functions with no incomplete dependencies.
- All preview work is read-only (FR-010); no attended `needs_human` Move gate applies (SC-008).
- The Qt-free render core and the write paths (`Lib/preview.py`, `Lib/transfer.py`) are NOT modified.
- Commit after each task or logical group; keep spec artifacts on `main`, code on the worktree.
