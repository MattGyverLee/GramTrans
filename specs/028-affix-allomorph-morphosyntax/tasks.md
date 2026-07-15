# Tasks: Affix-Allomorph Morphosyntax Fidelity (028)

**Feature**: reproduce the four un-reproduced `MoAffixAllomorph`/`MoAffixForm`
morphosyntactic-environment fields (`MsEnvPartOfSpeechRA`, `InflectionClassesRC`,
`MsEnvFeaturesOA`, `PositionRS`) on cross-project Move transfer, carrying over 024's
never-silent guarantee. Closes the 024-census DROP_REPORTED gap for affix allomorphs.

**Inputs**: [plan.md](plan.md) · [spec.md](spec.md) · [research.md](research.md) ·
[data-model.md](data-model.md) ·
[contracts/affix-msenv-reproduction.md](contracts/affix-msenv-reproduction.md) ·
[quickstart.md](quickstart.md)

**Discipline**: TDD, RED-before-GREEN — author the failing test in the same unit as its
implementation and confirm it fails first. All code work on the worktree
`../GramTrans-028-affix-allomorph-morphosyntax` (branch `028-affix-allomorph-morphosyntax`);
spec artifacts stay on `main`. Behavioral change is localized to `src/gramtrans/Lib/owned.py`
(replacing the report-only `_report_dropped_moaffix_msenv_fields` stub with a reproduce leg +
Preview twin); the only change outside `Lib/` is the `tests/verification/fidelity_census.py`
flip. Reuse — do NOT reinvent: `categories._resolve_target_pos` + POS create-with-ancestors
(R1), `categories._create_inflection_class`/`IMoInflClassFactory` (R5),
`owned._target_phonological_environments` + `_reproduce_phone_env_rc`/`_plan_phone_env_rc_decisions`
(R4), feature 031's closed-feature resolution (R3), `models.DroppedItemRecord` /
`ReferenceDecisionRecord`.

**MVP** = User Story 1 (Phase 3): `MsEnvPartOfSpeechRA` reproduced end-to-end. Delivered
alone it proves the reproduce-leg + Preview-twin pattern that US2–US4 replicate per field.

**⚠️ Note on parallelism**: all four field legs edit the SAME two dispatch functions in the
SAME file (`owned.py`). Their RED test-authoring tasks are `[P]` (distinct test files /
distinct test functions), but their GREEN implementation tasks are **sequential** — they are
NOT `[P]` because they touch the same functions.

---

## Phase 1: Setup

- [ ] T001 Create the implementation worktree `../GramTrans-028-affix-allomorph-morphosyntax`
      on new branch `028-affix-allomorph-morphosyntax` from `main`; confirm
      `pip install -e D:/Github/_Projects/_LEX/flexlibs2` resolves and
      `python -m pytest tests/unit -q` is green modulo the known
      `test_wizard_pos_grammar_wiring` baseline fail.
- [ ] T002 [P] Add import-smoke scaffold `tests/unit/test_028_affix_msenv_reproduction.py`
      (collects clean; covers the POS-ref, inflection-class, and position families).
- [ ] T003 [P] Add import-smoke scaffold `tests/unit/test_028_msenv_feature_struct.py`
      (collects clean; covers the `MsEnvFeaturesOA` deep-copy family).

## Phase 2: Foundational (blocking prerequisites)

**⚠️ CRITICAL**: No user-story leg can begin until T004–T005 are complete.

- [ ] T004 Gate task — confirm the reuse surface is present on the branch:
      `categories._resolve_target_pos` (+ the POS create-with-ancestors path /
      `transfer._create_pos_with_guid`), `categories._create_inflection_class` +
      `IMoInflClassFactory` create-with-GUID, `owned._target_phonological_environments`,
      `owned._reproduce_phone_env_rc` / `owned._plan_phone_env_rc_decisions`, the feature-031
      closed-feature resolution entry point, and `models.DroppedItemRecord` /
      `ReferenceDecisionRecord`. Record a one-line PASS per item in task notes; if any is
      absent, STOP and escalate (design assumption R1/R3/R4/R5 broken).
- [ ] T005 In `src/gramtrans/Lib/owned.py`, add the dispatch skeletons
      `reproduce_moaffix_msenv_data(src_allo, new_allo, ctx, tag, resolver_cache, dropped)`
      (Move) and `_plan_moaffix_msenv_decisions(src_allo, ctx, dropped)` (Preview twin), and
      wire them into `reproduce_allomorph_hung_data` and `plan_allomorph_hung_data_decisions`
      **in place of** the `_report_dropped_moaffix_msenv_fields` call. Until each field leg
      lands, the skeleton MUST fall back to `_report_dropped_moaffix_msenv_fields` for the
      not-yet-implemented fields so the never-silent guarantee and the full suite stay green
      throughout the transition (no silent regression). Reuse `_is_moaffix_allomorph` /
      `_moaffix_msenv_populated_fields` for gating; vacuous for `MoStemAllomorph` and
      unpopulated `MoAffixAllomorph`.

**Checkpoint**: dispatch seam exists; behavior byte-identical to pre-028 (all fields still
report-dropped, but now through the new seam).

---

## Phase 3: User Story 1 — Affix POS environment survives (Priority: P1) 🎯 MVP

**Goal**: reproduce `MsEnvPartOfSpeechRA` — resolve/create the target POS and reference it.
**Independent test**: quickstart Tier 1 CREATE/LINK/REPORT for POS ref + Tier 2 step 4.

- [ ] T006 [P] [US1] RED: in `tests/unit/test_028_affix_msenv_reproduction.py`, failing tests
      for the POS-ref leg over duck-typed fakes — CREATE (POS absent, ancestor chain
      resolvable → created with GUID preserved, allomorph references it), LINK (present &
      identical → referenced, no write), REPORT_DROPPED (unresolvable → `DroppedItemRecord`
      `field_name="MsEnvPartOfSpeechRA"`), empty-source no-op (populated target field not
      blanked), and Preview/Move parity (plan decision == move outcome).
- [ ] T007 [US1] GREEN: implement the `MsEnvPartOfSpeechRA` leg in both
      `reproduce_moaffix_msenv_data` (Move) and `_plan_moaffix_msenv_decisions` (Preview) in
      `src/gramtrans/Lib/owned.py`, reading via the `IMoAffixAllomorph(obj)` cast and
      routing through `categories._resolve_target_pos` + the POS create-with-ancestors path
      (R1). Remove `MsEnvPartOfSpeechRA` from the T005 report-drop fallback. Confirm T006
      goes GREEN and the targeted suite passes.

**Checkpoint**: US1 fully functional and independently testable — MVP reproduce-leg +
Preview-twin pattern proven.

---

## Phase 4: User Story 2 — Inflection-class references survive (Priority: P1)

**Goal**: reproduce `InflectionClassesRC` (read from the `IMoAffixForm` parent), scoped to the
owning POS. **Independent test**: quickstart Tier 1 class LINK/CREATE/REPORT + dedup.

- [ ] T008 [P] [US2] RED: in `tests/unit/test_028_affix_msenv_reproduction.py`, failing tests
      for the inflection-class leg — read via `IMoAffixForm(obj)` cast; LINK (class present by
      GUID), CREATE (absent, owning POS in-closure → created under that POS, GUID preserved,
      added to target `InflectionClassesRC`), REPORT_DROPPED (owning POS neither present nor
      in-closure → `field_name="InflectionClassesRC"`, per class), and dedup (two allomorphs
      sharing a class → one create via `resolver_cache`).
- [ ] T009 [US2] GREEN: implement the `InflectionClassesRC` leg in both dispatch functions in
      `src/gramtrans/Lib/owned.py`, reusing `categories._create_inflection_class` /
      `IMoInflClassFactory` (R5) and the grammar POS resolution for the owning POS (R1),
      closure-scoped (Principle V). Remove `InflectionClassesRC` from the T005 fallback.
      Confirm T008 GREEN.

**Checkpoint**: US1 + US2 both independently functional.

---

## Phase 5: User Story 3 — Owned MsEnv feature structure comes along (Priority: P1)

**Goal**: deep-copy `MsEnvFeaturesOA` (owned `IFsFeatStruc`), resolving feature values.
**Independent test**: quickstart Tier 1 deep-copy + feature-value resolution/report.

- [ ] T010 [P] [US3] RED: in `tests/unit/test_028_msenv_feature_struct.py`, failing tests —
      deep-copy of a feature structure with a resolvable closed-feature value (target allomorph
      owns an equivalent structure with matching values), REPORT_DROPPED for an unresolvable /
      complex-feature value with the resolvable remainder still reproduced (partial fidelity,
      never silent, `field_name="MsEnvFeaturesOA"`), and empty-source no-op (no empty structure
      created; populated target not blanked).
- [ ] T011 [US3] GREEN: implement the `MsEnvFeaturesOA` leg in both dispatch functions in
      `src/gramtrans/Lib/owned.py` — deep-copy the owned `IFsFeatStruc` (owned-child discipline)
      reading via `IMoAffixAllomorph(obj)` cast, resolving feature-value references through
      feature 031's closed-feature machinery (R3); complex/open features → REPORT_DROPPED
      (spec Out of Scope). Remove `MsEnvFeaturesOA` from the T005 fallback. Confirm T010 GREEN.

**Checkpoint**: US1–US3 independently functional.

---

## Phase 6: User Story 4 — Infix position references survive (Priority: P2)

**Goal**: reproduce `PositionRS` (ordered `IPhEnvironment` references), reusing the 024
environment path. **Independent test**: quickstart Tier 1 order + LINK/REPORT + never-create.

- [ ] T012 [P] [US4] RED: in `tests/unit/test_028_affix_msenv_reproduction.py`, failing tests
      for the position leg — LINK each position to the target env (present), order preserved
      for ≥2 positions, a middle unresolvable position REPORT_DROPPED
      (`field_name="PositionRS"`) **without reordering** the rest, and never-create-environment
      (absent env is reported, never created).
- [ ] T013 [US4] GREEN: implement the `PositionRS` leg in both dispatch functions in
      `src/gramtrans/Lib/owned.py`, iterating source order and reusing
      `owned._target_phonological_environments` + the `_reproduce_phone_env_rc` link-or-report
      logic (R4), appending to the target `PositionRS` in order. Remove `PositionRS` from the
      T005 fallback — the fallback is now empty and `_report_dropped_moaffix_msenv_fields`
      is dead for the four fields. Confirm T012 GREEN.

**Checkpoint**: all four fields reproduced; the T005 report-drop fallback covers nothing.

---

## Phase 7: User Story 5 — Never-silent backstop + census (Priority: P1)

**Goal**: prove nothing is silently lost across all four fields, and reflect reproduction in
the model-driven census. **Independent test**: quickstart Tier 1 census flip + unified
never-silent.

- [ ] T014 [P] [US5] RED: unified never-silent + no-regression test (in
      `tests/unit/test_028_affix_msenv_reproduction.py`) — drive all four field families into
      ONE shared `dropped` list and assert every unreproduced item yields a `DroppedItemRecord`
      with owner/field/source identity; plus a **vacuous** assertion (a `MoStemAllomorph` and an
      unpopulated `MoAffixAllomorph` emit zero records in BOTH the Move and Preview legs, SC-006).
- [ ] T015 [US5] Flip the four `("MoAffixAllomorph", …)` rows in
      `tests/verification/fidelity_census.py` from DROP_REPORTED to COPIED (each pointing at
      its concrete new `owned.py` code site), update the module header comment block and the
      `"MoAffixAllomorph": 6` count assertion (field set unchanged — only the bucket changes),
      and confirm the never-silent `classify_field` guard still raises on any unclassified
      field. Run `python -m pytest tests/verification/ -q` → GREEN (FR-009).
- [ ] T016 [US5] Retire `_report_dropped_moaffix_msenv_fields` from `owned.py` (now dead for
      the four fields) — delete it, or keep it ONLY as the explicitly-documented fallback for
      complex/open feature values that are out of scope (R3). Update the cycle-16 comment block
      to reflect that the four fields are now reproduced, not report-only.

**Checkpoint**: never-silent proven across all fields; census reflects COPIED.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T017 Run the full offline suite `python -m pytest tests/unit tests/verification -q`;
      confirm no new failures beyond the documented `test_wizard_pos_grammar_wiring` baseline.
- [ ] T018 Run quickstart Tier 1 offline validation end-to-end (unit + census + full
      regression) and record results in the task notes.
- [ ] T019 [needs_human] Attended live proof (quickstart Tier 2) — build the **constructed**
      non-Ejagham fixture (affix allomorph populating all four fields), `-restore` a disposable
      target, run Preview → Move → re-Move (idempotency) → forced-drop, verify the `0 → N`
      reproduction and order/dedup/never-silent per quickstart, and write evidence to
      `specs/028-affix-allomorph-morphosyntax/verification-log.md`. **Never under an unattended
      loop** (Ejagham corpora are vacuous for these fields; mirrors 027's constructed-fixture
      proof). Reaching this task under a loop → emit `needs_human` and stop.
- [ ] T020 Merge `028-affix-allomorph-morphosyntax` → `main` (`--no-ff`) after T019 passes and
      any crew review is green; remove the worktree; update STATUS.md. Confirm the merged-tree
      offline suite matches (modulo the baseline fail). File any deferred follow-ups
      (e.g. complex/open feature-value reproduction, tracked against #29-class scope).

---

## Dependencies & Execution Order

### Phase dependencies
- **Setup (P1)**: no dependencies.
- **Foundational (P2)**: depends on Setup; **BLOCKS all user stories** (T005 creates the seam).
- **US1–US4 (P3–P6)**: each depends on Foundational. They are **sequential, not parallel** —
  all edit `reproduce_moaffix_msenv_data` / `_plan_moaffix_msenv_decisions` in the same file.
  Priority order P1(US1) → P1(US2) → P1(US3) → P2(US4).
- **US5 (P7)**: depends on US1–US4 (the census flip and dead-code retirement require all four
  legs landed; the unified never-silent test exercises all four).
- **Polish (P8)**: depends on all stories. T019 (live) is `needs_human`; T020 (merge) depends
  on T019.

### Within each user story
- RED test authored and confirmed failing before the GREEN implementation (TDD).
- Move leg + Preview twin land together (parity is a hard requirement, tested in the RED task).

### Parallel opportunities
- Setup: T002, T003 (`[P]`, distinct files).
- RED test-authoring tasks T006/T008/T012 target distinct test *functions* and T010 a distinct
  *file*, so they may be drafted in parallel (`[P]`) — but each story's GREEN task is sequential.
- No cross-story parallel implementation: same-file, same-function constraint.

---

## Implementation Strategy

### MVP first (User Story 1 only)
1. Phase 1 Setup → 2. Phase 2 Foundational (seam) → 3. Phase 3 US1 (`MsEnvPartOfSpeechRA`).
4. **STOP and VALIDATE**: US1 reproduces the POS environment; the reproduce-leg + Preview-twin
   pattern is proven. Every later story replicates it for one more field.

### Incremental delivery
US1 (POS) → US2 (inflection classes) → US3 (feature structure) → US4 (positions) → US5
(never-silent + census). Each adds one field's fidelity without disturbing the prior legs;
the T005 report-drop fallback shrinks by one field per story, so never-silent holds throughout.

---

## Notes
- `[P]` = different files/functions, no dependency on incomplete tasks.
- `[Story]` label maps each task to its spec user story for traceability.
- Verify RED before GREEN; commit after each task or logical group.
- The whole feature is a targeted stub replacement + census flip — resist adding a new module
  (plan Structure Decision) or a second POS-creation path (research R1).
