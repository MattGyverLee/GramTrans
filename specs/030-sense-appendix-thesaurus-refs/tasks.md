# Tasks: Sense Appendix & Thesaurus References (030)

**Feature dir**: `specs/030-sense-appendix-thesaurus-refs/`
**Inputs**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Tests**: requested (fakes/unit offline + MCP live-fixture proof — see quickstart.md)

**Implementation location**: dedicated worktree
`../GramTrans-030-sense-appendix-thesaurus-refs` on branch
`030-sense-appendix-thesaurus-refs` (repo Git protocol — spec artifacts stay on `main`,
code on the worktree). All `src/`/`tests/` paths below are relative to the worktree root.

---

## Phase 1: Setup

- [ ] T001 Create the implementation worktree `../GramTrans-030-sense-appendix-thesaurus-refs` on branch `030-sense-appendix-thesaurus-refs` from `main`, and confirm flexicon is importable (`pip install -e D:/Github/_Projects/_LEX/flexlibs2` if needed)
- [ ] T002 Establish the offline baseline: run `pytest tests/unit/test_cycle16c_sense_scope_gaps.py tests/verification/fidelity_census.py -q` and record the green/failing baseline before any edit

---

## Phase 2: Foundational (blocking prerequisites)

- [ ] T003 In `src/gramtrans/Lib/categories.py`, split `_SENSE_SCOPE_GAP_FIELDS` so `PicturesOS` remains the only drop-only sense-scope-gap row; keep `_report_dropped_sense_scope_gaps` emitting for whatever rows remain (this isolates the drop-only reporter from the two fields 030 promotes, without yet adding reproduction legs)
- [ ] T004 [P] In `src/gramtrans/Lib/categories.py`, add a private helper `_target_appendix_by_guid(target, guid)` that linear-scans `ILexDb(ILangProject(target.Cache.LangProject).LexDbOA).AppendixesOC` and returns the matching `ILexAppendix` or `None` (never raises; casts per research.md Finding 2)
- [ ] T005 [P] In `src/gramtrans/Lib/references.py`, add a private helper `discover_owning_possibility_list(item)` that walks `item.Owner` (depth-capped) casting each hop to `ICmPossibilityList`, returning the owning list or `None` (never raises; research.md Finding 4)
- [ ] T006 In `src/gramtrans/Lib/references.py`, add `mirror_possibility_list_to_target(src_list, target)` that finds the equivalent target `ICmPossibilityList` by owner-class + `OwningFlid` (model-stable), falling back to Name match, returning the target list or `None` (research.md Finding 3; NEVER match by list GUID)

---

## Phase 3: User Story 1 — Appendix reference link-by-GUID (Priority: P1)

**Goal**: A sense's `AppendixesRC` reference is linked to a target-owned `LexAppendix`
by GUID; absent → DROP_REPORT (never create). Contract: `contracts/appendix-link-by-guid.md`.

**Independent test**: construct source appendix *G* + referencing sense; transfer into a
target that owns *G* (linked, 0 drops) and one that does not (0 created, 1 drop).

- [ ] T007 [P] [US1] Add fakes/unit tests in `tests/unit/test_cycle16c_sense_scope_gaps.py` for cases A-link, A-absent, A-partial, A-empty, A-shared (contracts/appendix-link-by-guid.md); assert link-or-drop and no creation
- [ ] T008 [US1] Implement the appendix link-by-GUID leg in `src/gramtrans/Lib/categories.py`: a function `_resolve_sense_appendixes(src_sense, copied_sense_or_None, target, dropped, mode)` that, per referenced source appendix, links via `_target_appendix_by_guid` (Move: add to `copied_sense.AppendixesRC` idempotently; Preview: record LINK decision) or emits a `DroppedItemRecord` when absent (reason per data-model.md), and never blanks a populated target field (G-A3)
- [ ] T009 [US1] Wire `_resolve_sense_appendixes` into BOTH sense-loop call sites — Move (`_walk_lex_entry_closure`) and Preview (`_plan_entry_reference_decisions`) — replacing the appendix half of the old drop-only `_report_dropped_sense_scope_gaps` call, so decisions and drop sets stay identical by construction (FR-008, G-A5)
- [ ] T010 [US1] Run `pytest tests/unit/test_cycle16c_sense_scope_gaps.py -q` and confirm all A-cases pass

**Checkpoint**: Section A complete and offline-proven independently of US2/US3.

---

## Phase 4: User Story 2 — Thesaurus dynamic-owner resolver (Priority: P1)

**Goal**: A sense's `ThesaurusItemsRC` reference is reproduced by discovering its owning
list dynamically and delegating item create/link to 024's resolver; unresolvable →
DROP_REPORT. Contract: `contracts/thesaurus-dynamic-owner.md`.

**Independent test**: construct source item in list *L* + referencing sense; transfer
into a target with equiv list lacking the item (created) and re-run (linked, no dup);
synthetic no-list / no-mirror cases DROP_REPORT without throwing.

- [ ] T011 [P] [US2] Add fakes/unit tests in `tests/unit/test_cycle16c_sense_scope_gaps.py` for cases B-create, B-link, B-nested, B-nolist, B-nomirror, B-empty, B-shared (contracts/thesaurus-dynamic-owner.md)
- [ ] T012 [US2] Implement `resolve_thesaurus_item(src_item, target, cache, source)` in `src/gramtrans/Lib/references.py`: discover source owning list (T005) → mirror to target (T006) → build a synthetic `ReferenceFieldSpec("LexSense","ThesaurusItemsRC", COLLECTION, target_list_path=lambda _: tgt_list, hierarchical=True)` → return a `decide_reference` decision; return a drop-signal when list discovery/mirroring fails (G-B3, never raises)
- [ ] T013 [US2] Implement `_resolve_sense_thesaurus_items(src_sense, copied_sense_or_None, target, cache, dropped, tag, mode)` in `src/gramtrans/Lib/categories.py`: per referenced item call `references.resolve_thesaurus_item`; Move → `apply_reference` onto `copied_sense.ThesaurusItemsRC`; Preview → record decision; drop-signal → `DroppedItemRecord` (reason per data-model.md); dedupe shared items via the resolver cache (G-B6) and never blank a populated target field (G-B5)
- [ ] T014 [US2] Wire `_resolve_sense_thesaurus_items` into BOTH sense-loop call sites (Move + Preview), replacing the thesaurus half of the old drop-only call; retire the now-empty appendix+thesaurus rows from `_SENSE_SCOPE_GAP_FIELDS` leaving only `PicturesOS` (FR-008, G-B7)
- [ ] T015 [US2] Run `pytest tests/unit/test_cycle16c_sense_scope_gaps.py -q` and confirm all B-cases pass

**Checkpoint**: Section B complete and offline-proven.

---

## Phase 5: User Story 3 — Census reflects promotion, never-silent intact (Priority: P2)

**Goal**: both fields classify COPIED; never-silent guard and `OUT_OF_SCOPE_EXCLUDED`
unchanged. Contract: FR-009; data-model.md classification table.

- [ ] T016 [US3] In `tests/verification/fidelity_census.py`, move `("LexSense","AppendixesRC")` and `("LexSense","ThesaurusItemsRC")` `Classification` rows from `Bucket.DROP_REPORTED` to `Bucket.COPIED` (cite the responsible 030 functions in each `Classification` string); leave `PicturesOS` DROP_REPORTED
- [ ] T017 [US3] Update the cycle-17 CENSUS CORRECTION docstring/comments in `tests/verification/fidelity_census.py` to record the 030 promotion (AppendixesRC/ThesaurusItemsRC now COPIED), keeping the never-silent classifier guard and the single-member `OUT_OF_SCOPE_EXCLUDED` assertion test intact
- [ ] T018 [US3] Run `pytest tests/verification/fidelity_census.py -q` and confirm both fields report COPIED and the classifier never-silent regression test is green

**Checkpoint**: All three user stories independently green offline.

---

## Phase 6: Polish, Live Proof & Cross-Cutting

- [ ] T019 Run the full offline suite `pytest -q` from the worktree; confirm no regression beyond the known pre-existing wizard/POS failure noted in 024
- [ ] T020 [P] Live fixture proof — Section A: via write-enabled FLExTools MCP on the disposable `Ejagham Full GT-Test`, construct a `LexAppendix` (GUID G) + referencing sense fixture, transfer, and capture pre/post evidence for A-present (linked) and A-absent (dropped, not created); clean up temp objects
- [ ] T021 [P] Live fixture proof — Section B: construct a source sense referencing a `CmPossibility` in a list the target also has; transfer and capture pre/post evidence for B-create then B-link (no dup); confirm DROP_REPORT on a no-mirror case; clean up temp objects
- [ ] T022 Update `specs/024-lexicon-reference-fidelity/validation-status.md` (or a 030 validation-status.md) to move `LexAppendix` / `ThesaurusItems` off the vacuous-live list, recording the constructed-fixture live proof from T020/T021 (commit to `main`)
- [ ] T023 Run `/speckit-analyze` for cross-artifact consistency, then merge the worktree branch to `main` after the crew review gates are green

---

## Dependencies & Execution Order

- **Setup (T001–T002)** → **Foundational (T003–T006)** → user stories.
- **US1 (T007–T010)** and **US2 (T011–T015)** are independent of each other once
  Foundational is done; both are P1. US1 depends on T003+T004; US2 depends on
  T003+T005+T006.
- **US3 (T016–T018)** depends on US1 + US2 (the census asserts the reproduction the two
  legs deliver).
- **Polish (T019–T023)** last; T020/T021 require US1/US2 code.

## Parallel Opportunities

- T004 ‖ T005 (different modules, no interdep).
- T007 ‖ T011 (test authoring in the same file — coordinate insert points; treat as
  sequential if edit-conflict risk).
- T020 ‖ T021 (independent live fixtures).

## MVP Scope

**US1 alone** (T001–T004, T007–T010) is a shippable MVP: it closes a real never-silent
appendix drop with the lowest-risk mechanism (link, never create). US2 and US3 layer on
top.

## Format validation

All tasks use `- [ ] Tnnn [P?] [US?] description + file path`. Setup/Foundational/Polish
carry no story label; US phases carry `[US1]`/`[US2]`/`[US3]`.
