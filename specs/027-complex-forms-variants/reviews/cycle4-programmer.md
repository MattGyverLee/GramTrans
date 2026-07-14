# Cycle 4 — Programmer Report: US3 spurt (T016-T018)

**Worktree:** `../GramTrans-027-complex-forms-variants` (branch `027-complex-forms-variants`)
**Starting commit:** `da06a5c`
**Ending commit:** `ec40a32`

## Summary

T016 and T017 add regression coverage for the RefType=1 (complex-form)
container path — component/primary wiring order+subset (T016) and the
ComplexEntryTypesRS three-way disposition matrix (T017) — mirroring the
existing RefType=0 (variant) tests test-for-test. **T018 required no
production code change**: investigation of the existing implementation
showed the parametric parity the task asked for was already landed as part
of US2's cycle-3 commit (`da06a5c`), just not yet locked by a dedicated test.
This is documented below as a deviation from the expected RED-before-GREEN
shape, along with the tripwire-genuineness proof I ran to compensate.

## Files touched

- `tests/unit/test_027_entryref_reproduction.py` — T016. Added:
  - `_FakeLexeme` (guid-addressable stand-in for a component/primary lexeme)
  - `_ctx_create_and_wire(...)` (ctx builder carrying both
    `entryref_create_bindings` and `lexentry_ref_bindings` so C1
    (`_run_entryref_create_pass`) and C2 (`_run_post_pass_a`) can run in
    sequence over the same ctx/target, mirroring
    `test_phase3c_post_pass_a.py`'s `_ctx_create_and_wire`/
    `_run_create_then_wire` create-then-wire section)
  - `test_entryref_create_pass_complex_form_primary_subset_order_preserved`
    (new test, inserted after the existing
    `test_entryref_create_pass_multi_component_complex_form` at line ~317)
- `tests/unit/test_027_entry_type_resolve.py` — T017. Added a new section
  ("T017 -- three-way disposition over ComplexEntryTypesRS (RefType==1)")
  inserted between the existing T013 VariantEntryTypesRS block and the
  "RefType routing" section (before line 399's
  `test_complex_form_ref_resolves_complex_types_not_variant_types`):
  - `test_absent_complex_type_creates_with_guid_preserved`
  - `test_diverged_custom_complex_type_updates_and_links_same_object`
  - `test_diverged_shared_gold_complex_type_links_and_reports`
  - `test_identical_complex_type_links_only_no_create_no_report`
- `src/gramtrans/Lib/categories.py` — **untouched** (no diff; confirmed via
  `git diff --stat` after commit). See "T018 finding" below.

## T016 — RED-before-GREEN status

`test_entryref_create_pass_complex_form_primary_subset_order_preserved`
passed on first run (immediately GREEN, no code change), because
`_run_post_pass_a` (C2) has always wired `ComponentLexemesRS`/
`PrimaryLexemesRS` generically per-`field_name` in a loop, independent of
`RefType` — that generic behavior predates this spurt (confirmed present
already in the T009/create-then-wire tests in `test_phase3c_post_pass_a.py`).
The combination tested here (RefType=1 + a strict M=2-of-N=3 primary subset,
in a different relative order than the components, exercised via the real
create-then-wire order) had simply never been exercised together before.

**Tripwire-genuineness proof (RED substitute):** since the test didn't fail
naturally, I manually disabled the C2 wiring loop
(`for field_name in ("ComponentLexemesRS", "PrimaryLexemesRS")` ->
`for field_name in ("ComponentLexemesRS",)`) in `categories.py`, reran the
targeted test, confirmed it failed:

```
assert list(new_ref.PrimaryLexemesRS) == [lex_c, lex_a]
E       assert [] == [<...FakeLexeme...>]
```

then reverted via `git checkout -- src/gramtrans/Lib/categories.py` (clean
revert, confirmed via `git diff --stat` showing 0 changes to that file
afterward). GREEN confirmed again in the full targeted run below.

## T017 — RED-before-GREEN status

All 5 affected tests (the new 4 three-way tests plus the pre-existing
`test_complex_form_ref_resolves_complex_types_not_variant_types` routing
test) passed on first run — no code change, for the same reason: `categories.
_run_entryref_create_pass` already computes `type_skip` from `ref_type`
(`ref_type != 1` -> skip `ComplexEntryTypesRS`) and dispatches
`ComplexEntryTypesRS` through the exact same `_apply_reference_fields` call
already used for `VariantEntryTypesRS`, and `references.py`'s
`REFERENCE_FIELD_MAP` already carries a `ComplexEntryTypesRS` field spec
(`target_list_path=lambda target: _lp(target).LexDbOA.ComplexEntryTypesOA`,
same `ItemClsid=5118` `LexEntryType` list as `VariantEntryTypesOA`, so the
CREATE arm's typed-factory lookup — `5118: ILexEntryTypeFactory` — resolves
identically for both). This was landed with US2's cycle-3 commit `da06a5c`
even though that commit's own summary emphasized only `variant_entry_types`/
`show_complex_forms_in`.

**Tripwire-genuineness proof:** manually forced `ComplexEntryTypesRS` into
`type_skip` unconditionally (`if ref_type != 1: type_skip.add(...)` ->
`if True: type_skip.add(...)`), reran the 5 affected tests, confirmed all 5
failed (e.g. `assert len(linked) == 1` -> `assert 0 == 1`, empty
`ComplexEntryTypesRS`), then reverted (`git checkout --`, confirmed 0 diff).
GREEN confirmed again below.

## T018 finding: no new production code needed

Given both tripwire proofs above, the "extend the EXISTING C1/C3 path to
handle RefType=1" instruction is satisfied by **already-shipped code** from
the cycle-3 commit, not new code this cycle:

- `categories.py:5152-5166` (`_run_entryref_create_pass`) already builds
  `type_skip` from `ref_type` and calls the shared
  `_apply_reference_fields("LexEntryRef", type_src, new_ref_typed, ...)`
  dispatch for `VariantEntryTypesRS`/`ComplexEntryTypesRS`/
  `ShowComplexFormsInRS` uniformly.
- `references.py:196-202` already declares the `ComplexEntryTypesRS`
  `ReferenceFieldSpec` alongside `VariantEntryTypesRS` (196) and
  `ShowComplexFormsInRS` (203), same `hierarchical=True`, same
  `ItemClsid=5118` target list shape.
- `categories.py:5215` (`_run_post_pass_a`) has always looped
  `("ComponentLexemesRS", "PrimaryLexemesRS")` generically per target ref,
  with no `RefType` branch at all.

I made **no edits to `src/gramtrans/Lib/categories.py` or
`src/gramtrans/Lib/references.py`** this cycle — confirmed by
`git diff --stat` showing only the two test files changed, and by the
committed diffstat (`2 files changed, 194 insertions(+)`, both test files).
This is a genuine "parametric parity already exists" finding, not an
oversight: the two tripwire experiments above independently proved that (a)
disabling the RefType=1 dispatch and (b) disabling the primary-subset wiring
loop each break exactly the tests meant to catch that class of regression,
and nothing else broke in the reverts.

## Test-run results

Targeted 027 suite (the three `test_027_*.py` files + `test_phase3c_post_pass_a.py`):

```
tests/unit/test_027_entryref_reproduction.py tests/unit/test_027_entry_type_resolve.py tests/unit/test_phase3c_post_pass_a.py
50 passed in 0.48s
```

(45 pre-existing + 5 new: 1 from T016, 4 from T017's own new tests — the 5th
T017-affected test, the routing test, was pre-existing and is included in
the 45 baseline.)

Full `tests/unit` suite:

```
1575 passed, 9 skipped, 14 xfailed, 14 xpassed, 1 failed in 6.76s
```

The 1 failure is `test_wizard_pos_grammar_wiring.py::
TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos` —
this matches the briefing's documented known/pre-existing failure and was
left untouched per instructions.

## Worktree commit

`ec40a32` — `test(027): US3 spurt -- T016/T017 lock RefType=1 parametric
parity, T018 confirms no new code needed` (2 files changed: the two test
files; `src/` untouched).

## Deviations from the brief

1. **RED-before-GREEN literal discipline**: T016 and T017's new tests passed
   immediately on first run (no genuine RED state ever existed against
   unmodified `categories.py`/`references.py`), because the RefType=1 dispatch
   path (C1/C3) and the RefType-agnostic wiring loop (C2) were already fully
   parametric before this spurt started (landed with cycle-3's `da06a5c`,
   just not yet covered by a dedicated four-way/subset-order test). I
   substituted the required RED proof with an explicit tripwire-genuineness
   experiment for each test group (temporarily disabling the exact code path
   each test exercises, confirming failure, then cleanly reverting via `git
   checkout --`) — see the "Tripwire-genuineness proof" notes above for the
   literal failure output. No task scope was skipped; T018 is simply a
   "confirm, don't rebuild" outcome rather than a "build" outcome.
2. Out-of-scope items (Phase 6 T021/T022, P1a/P1b/c, live/FLExToolsMCP Move)
   were left untouched as instructed.

## Relevant paths

- `d:/Github/_Projects/_LEX/GramTrans-027-complex-forms-variants/tests/unit/test_027_entryref_reproduction.py`
- `d:/Github/_Projects/_LEX/GramTrans-027-complex-forms-variants/tests/unit/test_027_entry_type_resolve.py`
- `d:/Github/_Projects/_LEX/GramTrans-027-complex-forms-variants/src/gramtrans/Lib/categories.py` (read-only this cycle; relevant existing code at lines 5026-5168 `_run_entryref_create_pass`, 5174-5240 `_run_post_pass_a`, 4999-5023 `_create_entryref_container`)
- `d:/Github/_Projects/_LEX/GramTrans-027-complex-forms-variants/src/gramtrans/Lib/references.py` (read-only this cycle; relevant existing code at lines 68-209 `REFERENCE_FIELD_MAP`, 1030-1048 typed-factory-by-ItemClsid lookup)
