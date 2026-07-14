# Tasks: Complex Forms & Variants (027)

**Feature**: reproduce `LexEntryRef` complex-form / variant relationships on cross-project
Move transfer. Resolves GitHub **#30**; unblocks the LexEntryRef leg of **#28**.

**Inputs**: [plan.md](plan.md) · [spec.md](spec.md) · [research.md](research.md) ·
[data-model.md](data-model.md) · [contracts/entryref-reproduction.md](contracts/entryref-reproduction.md) ·
[quickstart.md](quickstart.md)

**Discipline**: TDD, RED-before-GREEN — author the failing test in the same unit as its
implementation and confirm it fails first. All code work on the worktree
`../GramTrans-027-complex-forms-variants` (branch `027-complex-forms-variants`); spec
artifacts stay on `main`. All resolution via `_resolve_target_by_guid`; all
`LexEntry`/`LexEntryRef` member access via `_cast_lcm` (issue #28 layers 1+2).

**MVP** = User Story 1 (Phase 3). Delivered alone it reproduces variant relationships and
satisfies the issue #28/#30 live `0 → N` acceptance.

---

## Phase 1: Setup

- [x] T001 Create the implementation worktree `../GramTrans-027-complex-forms-variants` on
      new branch `027-complex-forms-variants` from `main` (carries #28 layer-1/2 fixes);
      confirm `pip install -e D:/Github/_Projects/_LEX/flexlibs2` resolves and
      `python -m pytest tests/unit -q` is green modulo the known
      `test_wizard_pos_grammar_wiring` baseline fail.
- [x] T002 [P] Add skip-collecting scaffolds for the three new unit files
      `tests/unit/test_027_entryref_reproduction.py`,
      `tests/unit/test_027_entry_type_resolve.py`,
      `tests/unit/test_027_never_silent.py` (import smoke only; collect clean).
- [x] T003 [P] Add `@pytest.mark.integration` skip-by-default scaffold
      `tests/integration/test_027_complex_forms_live.py` (collects → 1 skipped, exit 0).

## Phase 2: Foundational (blocking prerequisites)

- [x] T004 Confirm the 024 reuse surface is present on the branch:
      `references.decide_reference`/`apply_reference`, `owned.walk_owned_children`,
      `report.DroppedItemRecord`, and the on-`main` `categories._resolve_target_by_guid` +
      `_cast_lcm`. Gate task — record a one-line PASS in the task notes; if any is absent,
      STOP and escalate.
- [x] T005 Extend the plan binding shape in `src/gramtrans/Lib/models.py` per data-model.md:
      per-source-entry list of per-ref records `{ref_guid, ref_type, components, primaries,
      variant_entry_types, complex_entry_types, show_complex_forms_in}`, keeping the existing
      `_run_post_pass_a` consumption working (extend or add a parallel
      `entryref_create_bindings`; keep Preview gatherer + Move consumer in lockstep).
- [x] T006 Populate the extended bindings at plan time in `src/gramtrans/Lib/preview.py` /
      the STEMS gather path (`stems_execute_action`): walk source `EntryRefsOS`, record each
      ref's guid/RefType/components/primaries/type-refs, closure-scoped. Read-only (no writes).

## Phase 3: User Story 1 — Variant relationships survive transfer (P1) — MVP

**Goal**: create target `LexEntryRef` containers (RefType=variant) and wire their component
lexemes, so `Ejagham Mini`'s 6 variant refs land on the target (`0 → 6`).
**Independent test**: quickstart §1 (offline) + §3 (attended live `0 → 6`).

- [x] T007 [P] [US1] RED: in `tests/unit/test_027_entryref_reproduction.py`, failing tests
      for C1 container creation over duck-typed fakes — variant ref created, GUID preserved,
      `RefType=0` set, owned into `EntryRefsOS`; unresolved target entry → `Skip`.
- [x] T008 [P] [US1] RED: fake `ICmObjectRepository` fallback-branch test (no
      `get_object_by_guid` getter) proving C1 resolves via the live-repo path — closes the
      offline gap that let #28 ship.
- [x] T009 [P] [US1] RED: `_Bare` vs `_Typed` cast tripwire — an uncast `LexEntry`/
      `LexEntryRef` reproduces 0 (reproducing the #28 layer-2 live no-op), the cast path
      reproduces N. Same shape as the existing #28 regression tests.
- [x] T010 [US1] GREEN: implement `_run_entryref_create_pass` (C1) in
      `src/gramtrans/Lib/categories.py` — resolve+cast entry, GUID-idempotency guard,
      `ILexEntryRefFactory(target.GetFactory(ILexEntryRefFactory))` create (confirm the exact
      `Create` signature live per research Decision 1), set `RefType`, own into `EntryRefsOS`.
      Degrade to report-only if factory/interface absent.
- [x] T011 [US1] GREEN: make `_run_post_pass_a` (C2) reachable — invoke create-then-wire in
      the STEMS tail (front: create; then existing component/primary wiring) under
      `_run_tail_once`. Extend `tests/unit/test_phase3c_post_pass_a.py` for create-then-wire,
      order preservation, and membership-guard idempotency.
- [x] T012 [US1] Wire the pass into the Move executor in `src/gramtrans/Lib/transfer.py`
      (STEMS-tail placement alongside the existing post-passes); confirm ordering after all
      closure entries exist.

**Checkpoint US1**: offline C1+C2 green; `Ejagham Mini` Preview shows 6 variant Add rows.

## Phase 4: User Story 2 — Entry-type / publication references resolve (P2)

**Goal**: each reproduced variant ref carries its resolved `VariantEntryTypesRS` (and
`ShowComplexFormsInRS`) via 024's three-way disposition, concept↔GUID preserved.
**Independent test**: quickstart §1 (C3 tests) + live SC-002.

- [x] T013 [P] [US2] RED: in `tests/unit/test_027_entry_type_resolve.py`, three-way
      disposition tests over the entry-type list — absent → create incl. ancestor chain;
      diverged custom → update; diverged shared/GOLD → link + report; identical → link.
- [x] T014 [P] [US2] RED: Principle-I test — a GOLD/reserved entry-type is GUID-remapped at
      creation and an existing target GOLD item is linked, never overwritten.
- [x] T015 [US2] GREEN: implement C3 resolution in `src/gramtrans/Lib/categories.py` —
      route `variant_entry_types` / `show_complex_forms_in` through
      `references.decide_reference`/`apply_reference` against the target lists; unresolved →
      `DroppedItemRecord`.

**Checkpoint US2**: reproduced variant refs carry a resolved variant-type; no ref left with
an empty entry-type where the source had one.

## Phase 5: User Story 3 — Complex-form relationships (P3, offline only)

**Goal**: same reproduction for `RefType=complex-form` (multi-component + primary subset +
`ComplexEntryTypesRS`). Live proof deferred (no complex-form corpus).
**Independent test**: quickstart §1 (US3 tests); live proof tracked follow-up.

- [x] T016 [P] [US3] RED: complex-form tests in `tests/unit/test_027_entryref_reproduction.py`
      — `RefType=1`, N components with M-primary subset, source order preserved.
- [x] T017 [P] [US3] RED: `ComplexEntryTypesRS` three-way resolution test in
      `tests/unit/test_027_entry_type_resolve.py`.
- [x] T018 [US3] GREEN: extend C1/C3 to handle `RefType=1` (complex_entry_types →
      `ComplexEntryTypesRS`; primaries subset) in `src/gramtrans/Lib/categories.py` — should
      be parametric parity with US1/US2, no new create path. **[DONE — parity already existed;
      T018 confirmed no new production code needed, verified genuine by cycle-5 QC.]**

## Phase 6: Cross-cutting — drop policy & Preview parity

- [x] T019 RED: in `tests/unit/test_027_never_silent.py`, prove the C4 policy flip — an
      in-closure ref yields **0** `DroppedItemRecord` (reproduced); an out-of-closure
      component/type yields exactly **1** `DroppedItemRecord` (reported).
- [x] T020 GREEN: flip `_report_dropped_entry_refs` (C4) in `src/gramtrans/Lib/categories.py`
      from report-all to report-only-un-reproduced; keep it called identically from
      `_walk_lex_entry_closure` (Move) and `_plan_entry_reference_decisions` (Preview).
- [x] T021 [P] Preview-parity test (C5): a Preview run followed by a Move run over the same
      `Ejagham Mini` selection produces the same created-ref set and the same dropped-record
      set; Preview writes nothing (byte-unchanged; Principle III). **[DONE — 2 tests in
      `tests/unit/test_027_never_silent.py`: `test_c5_preview_move_created_and_dropped_set_parity`
      (6 all-in-closure variant refs → 6 created == planned, 0 dropped, Preview mutates
      neither source nor target) + `test_c5_created_ref_set_is_disjoint_from_dropped_set`
      (mixed in/out-of-closure → same partition both modes). Green.]**
- [x] T022 [P] Empty-source regression (C7): a source with 0 `LexEntryRef` yields 0 new
      objects and 0 new dropped records vs. a 024-only baseline (FR-011, SC-005). **[DONE — 2
      tests in `tests/unit/test_027_never_silent.py`: `test_c7_empty_source_gathers_no_create_bindings`
      (no binding keys added — byte-identical plan) + `test_c7_empty_source_creates_nothing_and_reports_nothing`
      (0 created, 0 skips, 0 drops both modes). Green.]**

## Phase 7: Polish & Live Validation

- [x] T023 Run the full offline suite (`python -m pytest tests/unit -q`); confirm green
      modulo the documented `test_wizard_pos_grammar_wiring` baseline fail; confirm each new
      RED test is a genuine tripwire (breaks when its fix is reverted). **[DONE — 1579 passed,
      only the documented baseline fail. Tripwires confirmed by temporary revert: reverting the
      C4 flip (`_entry_ref_is_reproducible` → False) fails T019 + both T021 C5 tests; reverting
      C1 (`_create_entryref_container` → None) fails T007-T009 + T021 created-set parity. Source
      tree restored clean after each revert.]**
- [x] T024 [P] Author `scratchpad/run27_live.py` (restore → diagnose → Move → re-Move →
      diagnose), modeled on `run031_live.py` + the `run28_live.py` FLExToolsMCP
      re-resolution probe; keep it attended-only (no unattended Move). **[DONE — worktree
      34be1ad. Full Move (STEMS incl.) → reopen target RO → re-resolve every planned ref
      binding, counting containers (SC-001 0→6), RefType (C1), VariantEntryTypesRS (C3), +
      idempotent re-Move (SC-003). Casts via `_cast_lcm` (#28 layer 2). Compiles clean;
      ATTENDED-ONLY, execution deferred to T025.]**
- [ ] T025 **[ATTENDED / needs_human]** [US1][US2] Live `0 → N` proof (SC-001/002/003/004):
      restored target, attended Move `Ejagham Mini → Target`, FLExToolsMCP re-resolution
      confirms `LexEntryRef 0 → 6`, variant-type wired, re-Move 0-duplicate, out-of-closure
      refs reported. Write evidence to
      `specs/027-complex-forms-variants/verification-log.md`. **Never under an unattended
      loop.**
- [ ] T026 File the **US3 complex-form live-proof** follow-up issue (needs a constructed
      complex-form fixture; parallel to #31's MSA→slot live source) and record it in
      `STATUS.md`. Update issue #28 (LexEntryRef leg now proven) and close #30 after T025.
- [ ] T027 Merge `027-complex-forms-variants` → `main` (`--no-ff`) after LEX-crew review
      gates are green and T025 passes; remove the worktree; update `STATUS.md` handoff.

---

## Dependencies & ordering

- Phase 1 → Phase 2 → Phase 3 (US1) is the critical path to the MVP + issue #28/#30 fix.
- US2 (Phase 4) depends on US1's created containers (needs a ref to attach types to).
- US3 (Phase 5) depends on US1/US2 (parametric extension; no new path).
- Cross-cutting C4/C5 (Phase 6) depends on US1 (drop policy only meaningful once creation
  exists).
- T025 (attended live) depends on the full offline suite (T023) + the driver (T024).
- T027 (merge) depends on T025 + crew approval.

## Parallel opportunities

- T002/T003 (scaffolds) in parallel.
- Within each story, the RED test tasks marked `[P]` (T007/T008/T009; T013/T014;
  T016/T017) are parallelizable — different test files / independent assertions — before
  their GREEN implementation task.
- T021/T022 parallel (independent test files).

## Independent test criteria

- **US1**: target holds 6 variant `LexEntryRef` (0 → 6), each with 1 component wired;
  re-Move 0-duplicate. (SC-001, SC-003)
- **US2**: every reproduced variant ref carries a resolved variant-type. (SC-002)
- **US3**: offline — RefType=1 multi-component + primary subset + `ComplexEntryTypesRS`
  reproduced; live proof deferred.
- **Cross-cutting**: 0 silent drops; Preview/Move drop-set parity; empty-source parity.
  (SC-004, SC-005, SC-006)

## Notes on live safety (repo protocol)

T025 is a destructive-capable live-LCM write and is marked **attended / needs_human**. It
MUST run against a freshly-restored disposable target with FLExToolsMCP active, attended,
never under an unattended Ralph loop. If a restored target is unavailable when the loop
reaches T025, emit `needs_human` and stop.
