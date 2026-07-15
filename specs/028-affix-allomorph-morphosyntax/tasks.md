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

- [x] T001 Create the implementation worktree `../GramTrans-028-affix-allomorph-morphosyntax`
      on new branch `028-affix-allomorph-morphosyntax` from `main`; confirm
      `pip install -e D:/Github/_Projects/_LEX/flexlibs2` resolves and
      `python -m pytest tests/unit -q` is green modulo the known
      `test_wizard_pos_grammar_wiring` baseline fail.
      **Note (this environment):** flexicon is NOT pip-installed here, so the offline
      baseline is **7 failures** = 6 `test_013_apply_syncable_signature` (assert against the
      absent flexicon source tree `D:/Github/_Projects/_LEX/flexicon/...`) + 1 documented
      `test_wizard_pos_grammar_wiring`. 028's tests use fakes and do not depend on the
      flexicon tree; regression is measured against this 7-fail environment baseline.
- [x] T002 [P] Add import-smoke scaffold `tests/unit/test_028_affix_msenv_reproduction.py`
      (collects clean; covers the POS-ref, inflection-class, and position families).
- [x] T003 [P] Add import-smoke scaffold `tests/unit/test_028_msenv_feature_struct.py`
      (collects clean; covers the `MsEnvFeaturesOA` deep-copy family).

## Phase 2: Foundational (blocking prerequisites)

**⚠️ CRITICAL**: No user-story leg can begin until T004–T005 are complete.

- [x] T004 Gate task — confirm the reuse surface is present on the branch:
      `categories._resolve_target_pos` (+ the POS create-with-ancestors path /
      `transfer._create_pos_with_guid`), `categories._create_inflection_class` +
      `IMoInflClassFactory` create-with-GUID, `owned._target_phonological_environments`,
      `owned._reproduce_phone_env_rc` / `owned._plan_phone_env_rc_decisions`, the feature-031
      closed-feature resolution entry point, and `models.DroppedItemRecord` /
      `ReferenceDecisionRecord`. Record a one-line PASS per item in task notes; if any is
      absent, STOP and escalate (design assumption R1/R3/R4/R5 broken).
      **PASS** — all present: `categories._resolve_target_pos` (categories.py:3064);
      `transfer._create_pos_with_guid` (transfer.py:762); `owned._target_phonological_environments`
      (owned.py:1098); `owned._reproduce_phone_env_rc` (1109) / `_plan_phone_env_rc_decisions`
      (1508); `models.DroppedItemRecord` (974) / `ReferenceDecisionRecord` (1100).
      **Refinement:** inflection-class and closed-feature creation are **action-based**, not
      standalone helpers — reuse `IMoInflClassFactory.Create(Guid)` via
      `categories.inflection_classes_execute_action` (categories.py:1228) for US2, and
      `IFsClosedFeatureFactory.Create(Guid, featureSystem)` via
      `categories.inflection_features_execute_action` (categories.py:623) for US3. Non-blocking
      for the seam; US2/US3 GREEN tasks reuse those factory idioms.
- [x] T005 In `src/gramtrans/Lib/owned.py`, add the dispatch skeletons
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

- [x] T006 [P] [US1] RED: in `tests/unit/test_028_affix_msenv_reproduction.py`, failing tests
      for the POS-ref leg over duck-typed fakes — CREATE (POS absent, ancestor chain
      resolvable → created with GUID preserved, allomorph references it), LINK (present &
      identical → referenced, no write), REPORT_DROPPED (unresolvable → `DroppedItemRecord`
      `field_name="MsEnvPartOfSpeechRA"`), empty-source no-op (populated target field not
      blanked), and Preview/Move parity (plan decision == move outcome).
- [x] T007 [US1] GREEN: implement the `MsEnvPartOfSpeechRA` leg in both
      `reproduce_moaffix_msenv_data` (Move) and `_plan_moaffix_msenv_decisions` (Preview) in
      `src/gramtrans/Lib/owned.py`, reading via the `IMoAffixAllomorph(obj)` cast and
      routing through `categories._resolve_target_pos` + the POS create-with-ancestors path
      (R1). Remove `MsEnvPartOfSpeechRA` from the T005 report-drop fallback. Confirm T006
      goes GREEN and the targeted suite passes.
      **DONE** (worktree 65ec040): `owned._reproduce_msenv_pos_ra`/`_plan_msenv_pos_ra`;
      new R1-faithful single POS path `categories.resolve_or_create_target_pos`
      (reuses `_resolve_target_pos` for identity + the `gram_categories_execute_action`
      `IPartOfSpeechFactory` create idiom — GUID preserved, props synced, ancestor chain,
      Carrier B residue; fake-tolerant) + `target_has_pos_create_infra` for parity.
      `MsEnvPartOfSpeechRA` added to `owned._MSENV_REPRODUCED_FIELDS`. 8/8 targeted GREEN;
      full offline suite at the 7-fail environment baseline. The cycle-16 all-four
      never-silent test was made rollout-aware (landed field now reported by its leg).

**Checkpoint**: US1 fully functional and independently testable — MVP reproduce-leg +
Preview-twin pattern proven.

---

## Phase 4: User Story 2 — Inflection-class references survive (Priority: P1)

**Goal**: reproduce `InflectionClassesRC` (read from the `IMoAffixForm` parent), scoped to the
owning POS. **Independent test**: quickstart Tier 1 class LINK/CREATE/REPORT + dedup.

- [x] T008 [P] [US2] RED: in `tests/unit/test_028_affix_msenv_reproduction.py`, failing tests
      for the inflection-class leg — read via `IMoAffixForm(obj)` cast; LINK (class present by
      GUID), CREATE (absent, owning POS in-closure → created under that POS, GUID preserved,
      added to target `InflectionClassesRC`), REPORT_DROPPED (owning POS neither present nor
      in-closure → `field_name="InflectionClassesRC"`, per class), and dedup (two allomorphs
      sharing a class → one create via `resolver_cache`).
- [x] T009 [US2] GREEN: implement the `InflectionClassesRC` leg in both dispatch functions in
      `src/gramtrans/Lib/owned.py`, reusing `categories._create_inflection_class` /
      `IMoInflClassFactory` (R5) and the grammar POS resolution for the owning POS (R1),
      closure-scoped (Principle V). Remove `InflectionClassesRC` from the T005 fallback.
      Confirm T008 GREEN.
      **DONE** (worktree e5125ad): `owned._reproduce_inflection_classes_rc`/
      `_plan_inflection_classes_rc`; new `categories.resolve_or_create_inflection_class`
      (R5) — resolve by GUID under the owning POS's `InflectionClassesOC` (or a parent
      class's `SubclassesOC`), create via `IMoInflClassFactory.Create` GUID-preserved; the
      owning POS is **resolved, never invented** (G8/Principle V) — plus
      `resolve_target_inflection_class` + `can_create_inflection_class` for parity.
      `InflectionClassesRC` added to `owned._MSENV_REPRODUCED_FIELDS`. LCM-direct `.Add` into
      the read-only-through-wrapper collection. 14/14 targeted GREEN; full offline suite at
      the 7-fail environment baseline.
      **Reuse note (R5 refinement):** the existing `inflection_classes_execute_action`
      creates classes under `MorphologicalDataOA.ProdRestrictOA` (a different owner); 028
      creates the affix-`InflectionClassesRC` member under its **owning POS's
      `InflectionClassesOC`** per data-model.md, using the same `IMoInflClassFactory.Create`
      idiom.

**Checkpoint**: US1 + US2 both independently functional.

---

## Phase 5: User Story 3 — Owned MsEnv feature structure comes along (Priority: P1)

**Goal**: deep-copy `MsEnvFeaturesOA` (owned `IFsFeatStruc`), resolving feature values.
**Independent test**: quickstart Tier 1 deep-copy + feature-value resolution/report.

- [x] T010 [P] [US3] RED: in `tests/unit/test_028_msenv_feature_struct.py`, failing tests —
      deep-copy of a feature structure with a resolvable closed-feature value (target allomorph
      owns an equivalent structure with matching values), REPORT_DROPPED for an unresolvable /
      complex-feature value with the resolvable remainder still reproduced (partial fidelity,
      never silent, `field_name="MsEnvFeaturesOA"`), and empty-source no-op (no empty structure
      created; populated target not blanked).
- [x] T011 [US3] GREEN: implement the `MsEnvFeaturesOA` leg in both dispatch functions in
      `src/gramtrans/Lib/owned.py` — deep-copy the owned `IFsFeatStruc` (owned-child discipline)
      reading via `IMoAffixAllomorph(obj)` cast, resolving feature-value references through
      feature 031's closed-feature machinery (R3); complex/open features → REPORT_DROPPED
      (spec Out of Scope). Remove `MsEnvFeaturesOA` from the T005 fallback. Confirm T010 GREEN.
      **DONE** (worktree c72d254): `owned._reproduce_msenv_features_oa`/`_plan_msenv_features_oa`;
      deep-copies the owned `IFsFeatStruc` via `IFsFeatStrucFactory`/`IFsClosedValueFactory`
      (GUID preserved), resolving each `IFsClosedValue` spec's `FeatureRA`/`ValueRA` BY GUID
      against `Cache.LangProject.MsFeatureSystemOA.FeaturesOC` (feature-031 machinery, the same
      iteration `categories.exception_features_execute_action` uses — resolve/LINK only, never
      creates a feature). Partial fidelity: resolvable specs reproduced, unresolvable/complex
      (non-closed) values per-spec REPORT_DROPPED; nothing resolves → no empty structure created.
      `MsEnvFeaturesOA` added to `owned._MSENV_REPRODUCED_FIELDS`. Present-but-unreadable vs
      genuinely-empty `FeatureSpecsOC` distinguished (field-level drop vs no-op) to keep the
      cycle-16 rollout backstop green. 7/7 targeted GREEN; full offline suite at the 7-fail
      environment baseline.

**Checkpoint**: US1–US3 independently functional.

---

## Phase 6: User Story 4 — Infix position references survive (Priority: P2)

**Goal**: reproduce `PositionRS` (ordered `IPhEnvironment` references), reusing the 024
environment path. **Independent test**: quickstart Tier 1 order + LINK/REPORT + never-create.

- [x] T012 [P] [US4] RED: in `tests/unit/test_028_affix_msenv_reproduction.py`, failing tests
      for the position leg — LINK each position to the target env (present), order preserved
      for ≥2 positions, a middle unresolvable position REPORT_DROPPED
      (`field_name="PositionRS"`) **without reordering** the rest, and never-create-environment
      (absent env is reported, never created).
- [x] T013 [US4] GREEN: implement the `PositionRS` leg in both dispatch functions in
      `src/gramtrans/Lib/owned.py`, iterating source order and reusing
      `owned._target_phonological_environments` + the `_reproduce_phone_env_rc` link-or-report
      logic (R4), appending to the target `PositionRS` in order. Remove `PositionRS` from the
      T005 fallback — the fallback is now empty and `_report_dropped_moaffix_msenv_fields`
      is dead for the four fields. Confirm T012 GREEN.
      **DONE** (worktree 1676119): `owned._reproduce_position_rs`/`_plan_position_rs` — a faithful
      mirror of the `_reproduce_phone_env_rc`/`_plan_phone_env_rc_decisions` pair (`PositionRS`
      targets the SAME `IPhEnvironment` list, MCP-confirmed), read via `IMoAffixAllomorph(obj)`
      cast, iterating source order and `.Add()`-appending resolved target envs (order preserved,
      G5/INV-5); a middle unresolvable position is REPORT_DROPPED (`field_name="PositionRS"`,
      `owner_kind="MoAffixAllomorph"`) without reordering the rest; NEVER creates an environment
      (G7). `PositionRS` added to `owned._MSENV_REPRODUCED_FIELDS` — the T005 report-drop fallback
      is now **empty** (`_msenv_unreproduced_fields()` == ∅; all four fields reproduced). 6/6
      targeted GREEN; cycle-16 backstop still green; full offline suite at the 7-fail baseline.

**Checkpoint**: all four fields reproduced; the T005 report-drop fallback covers nothing.

---

## Phase 7: User Story 5 — Never-silent backstop + census (Priority: P1)

**Goal**: prove nothing is silently lost across all four fields, and reflect reproduction in
the model-driven census. **Independent test**: quickstart Tier 1 census flip + unified
never-silent.

- [x] T014 [P] [US5] RED: unified never-silent + no-regression test (in
      `tests/unit/test_028_affix_msenv_reproduction.py`) — drive all four field families into
      ONE shared `dropped` list and assert every unreproduced item yields a `DroppedItemRecord`
      with owner/field/source identity; plus a **vacuous** assertion (a `MoStemAllomorph` and an
      unpopulated `MoAffixAllomorph` emit zero records in BOTH the Move and Preview legs, SC-006).
      **DONE** (worktree 466cdb6): 4 unified tests over the 028 dispatch entry points directly
      (`test_unified_never_silent_all_four_fields_move` — one drop per field with owner/field/
      source identity against a bare no-infra target; `..._move_preview_parity`;
      `..._vacuous_stem_allomorph_emits_nothing`; `..._vacuous_unpopulated_affix_emits_nothing`).
      Since all four legs already landed (US1-US4), these are GREEN backstops formalizing the
      whole-object guarantee. 24/24 in the file pass.
- [x] T015 [US5] Flip the four `("MoAffixAllomorph", …)` rows in
      `tests/verification/fidelity_census.py` from DROP_REPORTED to COPIED (each pointing at
      its concrete new `owned.py` code site), update the module header comment block and the
      `"MoAffixAllomorph": 6` count assertion (field set unchanged — only the bucket changes),
      and confirm the never-silent `classify_field` guard still raises on any unclassified
      field. Run `python -m pytest tests/verification/ -q` → GREEN (FR-009).
      **DONE** (worktree 466cdb6): four rows now `Bucket.COPIED`, each citing its
      `_reproduce_*`/`_plan_*` leg + partial-fidelity note; module header block rewritten.
      The `"MoAffixAllomorph": 6` assertion is a **field-inventory** count (bucket-independent) —
      correctly unchanged. `classify_field` guard + `test_every_real_field_is_classified` +
      `test_guard_fires_for_unclassified_property` all pass. 86/86 census tests GREEN.
      **Invocation note:** `pytest tests/verification/ -q` collects nothing (exit 5) — the file
      `fidelity_census.py` doesn't match pytest's default `python_files=test_*.py`, a
      pre-existing harness detail. Pass the file explicitly
      (`pytest tests/verification/fidelity_census.py -q`) → 86 passed, exit 0.
- [x] T016 [US5] Retire `_report_dropped_moaffix_msenv_fields` from `owned.py` (now dead for
      the four fields) — delete it, or keep it ONLY as the explicitly-documented fallback for
      complex/open feature values that are out of scope (R3). Update the cycle-16 comment block
      to reflect that the four fields are now reproduced, not report-only.
      **DONE** (worktree 466cdb6): DELETED the stub + its only caller
      `_moaffix_msenv_populated_fields` (both dead — the `MsEnvFeaturesOA` leg reports
      complex/open values through its OWN `_drop_msenv_spec`/`_drop_msenv_field`, not this
      stub); removed the two now-no-op dispatch calls (`_msenv_unreproduced_fields()` is ∅);
      rewrote the header + seam comment blocks and the cycle-16 backstop docstring to reflect
      "reproduced, not report-only". Kept `_MSENV_REPRODUCED_FIELDS`/`_msenv_unreproduced_fields`
      as the rollout invariant probe (used by the cycle-16 backstop test). No live refs to the
      deleted symbols remain.

**Checkpoint**: never-silent proven across all fields; census reflects COPIED.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T017 Run the full offline suite `python -m pytest tests/unit tests/verification -q`;
      confirm no new failures beyond the documented `test_wizard_pos_grammar_wiring` baseline.
      **DONE** (worktree 466cdb6): `pytest tests/unit tests/verification/fidelity_census.py -q`
      → 1625 passed, 35 skipped, 14 xfailed, 14 xpassed; **7 failed = the documented environment
      baseline** (6 `test_013_apply_syncable_signature` [flexicon tree absent] + 1
      `test_wizard_pos_grammar_wiring`). No new failures from Phase 7. (Census passed via explicit
      file path per the T015 invocation note.)
- [x] T018 Run quickstart Tier 1 offline validation end-to-end (unit + census + full
      regression) and record results in the task notes.
      **DONE** (worktree 466cdb6): all three Tier 1 commands GREEN —
      [1] `test_028_affix_msenv_reproduction.py` + `test_028_msenv_feature_struct.py` → 31 passed;
      [2] fidelity census → 86 passed (four rows COPIED, `classify_field` guard passes, no
      unclassified field); [3] full unit regression → 1539 passed at the 7-fail baseline (no new
      failures). SC-001/002/003/004/005/006 offline obligations satisfied (Tier 1 column of the
      quickstart success-criteria map).
- [ ] T019 [needs_human] Attended live proof (quickstart Tier 2) — build the **constructed**
      non-Ejagham fixture (affix allomorph populating all four fields), `-restore` a disposable
      target, run Preview → Move → re-Move (idempotency) → forced-drop, verify the `0 → N`
      reproduction and order/dedup/never-silent per quickstart, and write evidence to
      `specs/028-affix-allomorph-morphosyntax/verification-log.md`. **Never under an unattended
      loop** (Ejagham corpora are vacuous for these fields; mirrors 027's constructed-fixture
      proof). Reaching this task under a loop → emit `needs_human` and stop.
      **STAGED, attended run PENDING** (user-directed session): environment staged —
      disposable source `Ejagham028Src` restored from `backups/Ejagham Mini.fwbackup` (real
      Ejagham Mini untouched); `Target` restored clean from `backups/Target 2026-07-06
      0218.fwbackup`; FieldWorks 9 present. Added the double-gated skipping placeholder
      `tests/integration/test_028_affix_msenv_live.py` (worktree 4fc9340, mirrors 027) and the
      procedure + fixture spec + SC map in `verification-log.md`. **Not executed:** the
      constructed-fixture build (raw-LCM affix entry + form + allomorph populating all four
      fields) + the two-project engine Move must be run attended in the FLEx host where
      `flexicon` is installed (it is NOT pip-installed in the dev/CI shell, and the full engine
      run is impractical through the single-project MCP). Template driver:
      `scratchpad/run031_live.py`. Fill the RESULTS section of `verification-log.md` on the run.
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
