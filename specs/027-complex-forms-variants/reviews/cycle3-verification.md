# Verification Report -- cycle 3

**Date:** 2026-07-13
**Feature:** 027-complex-forms-variants
**Commit under gate:** da06a5c (spurt 3: US2 entry-type resolution (C3) + C4 drop-policy
flip + P1 fold)
**Worktree:** d:/Github/_Projects/_LEX/GramTrans-027-complex-forms-variants
**Status:** PASS

## Executive Summary

All four requested checks were run. The full offline suite is green modulo the
documented pre-existing `test_wizard_pos_grammar_wiring` baseline fail. The targeted
027 suite is exactly 52 passed as claimed. All three tripwire test groups (T013/T014
for C3, T019 for C4) are genuine -- reverting the corresponding GREEN implementation
hunk in the working tree turns every one of the 8 (T013/T014) + 3 discriminating
(T019) tests RED, with zero collateral damage to the rest of the 027 suite, and the
worktree was fully restored afterward (verified byte-identical to da06a5c via
`git diff` / `git status`). The MCP-deviation scrutiny surfaced a genuine, material
gap: the read-only probe script the commit cites by name (`scratchpad/probe_c3_lists.py`)
does not exist anywhere on disk in either the main repo or this worktree, and the
"cycle-3 report" the commit message points to for the deviation note was never
written (confirmed by `.crew-handoff.json`'s own reconciliation note). This does not
block the gate -- the commit's C3/C4 code-level claims are independently verified by
the offline test suite and by direct reading of `research.md`/`tasks.md`/
`entryref-reproduction.md`, and the actual live 0->N proof is correctly tracked as the
separate, not-yet-started, attended-only T025 -- but it is a documentation-trail
finding that should be closed out (or at least acknowledged) before T025 is treated
as ready.

**Recommendation:** APPROVE (no fixes required to pass this gate). Flag the missing
probe artifact / missing cycle-3 report as a bookkeeping item for whoever picks up
T025, so the live-shape claims (ItemClsid=5118/Depth=127 for Variant-/
ComplexEntryTypesOA, ItemClsid=7/Depth=1 for PublicationTypesOA) get re-confirmed via
FLExToolsMCP (per repo rule) rather than resting solely on prose.

---

## 1. Full offline suite

Command: `python -m pytest tests/unit -q` (run from the worktree root).

```
1 failed, 1570 passed, 9 skipped, 14 xfailed, 14 xpassed in 8.50s
```

The single failure is exactly the documented baseline:

```
FAILED tests/unit/test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos
  assert len(pos_actions) == 1
  AssertionError: assert 0 == 1
```

This matches the pre-existing baseline recorded in `STATUS.md` (multiple entries,
e.g. lines 18, 57, 136, 155, 178, 341, 379, 495, 538) and in the cycle-2 verification
report (`specs/027-complex-forms-variants/reviews/cycle2-verification.md:41`) --
confirmed non-regression, unrelated to 027.

**No unexpected failures.** Status: GREEN (modulo documented baseline).

## 2. Targeted 027 suite

Command:
```
python -m pytest tests/unit/test_027_entry_type_resolve.py tests/unit/test_027_entryref_reproduction.py tests/unit/test_027_never_silent.py tests/unit/test_cycle16_drop_reporting.py tests/unit/test_reference_create_paths.py tests/unit/test_reversal_category_resolve.py -q
```

Result: **`52 passed in 0.67s`** -- matches the commit's claimed 52 exactly.

## 3. Red-before-green genuineness (tripwire proof)

Methodology: edited `src/gramtrans/Lib/categories.py` in the working tree only (never
staged/committed), re-ran the affected test file(s), then restored the file from a
byte-for-byte backup and confirmed `git status`/`git diff da06a5c` were both empty
before moving to the next revert.

### 3a. T013/T014 (C3 three-way entry-type resolution) -- revert of T015's GREEN hunk

Reverted the newly-added block in `_run_entryref_create_pass` (the `type_skip`/
`type_src`/`_apply_reference_fields(...)` call that resolves `VariantEntryTypesRS`/
`ComplexEntryTypesRS`/`ShowComplexFormsInRS`), leaving only the pre-existing
`RefType` assignment. Re-ran `tests/unit/test_027_entry_type_resolve.py`:

```
FAILED test_absent_variant_type_creates_with_guid_preserved
FAILED test_diverged_custom_variant_type_updates_and_links_same_object
FAILED test_diverged_shared_gold_variant_type_links_and_reports
FAILED test_identical_variant_type_links_only_no_create_no_report
FAILED test_complex_form_ref_resolves_complex_types_not_variant_types
FAILED test_show_complex_forms_in_always_resolves_regardless_of_ref_type
FAILED test_gold_reserved_entry_type_guid_remapped_at_creation
FAILED test_gold_reserved_existing_target_item_linked_never_overwritten
8 failed in 0.74s
```

**All 8/8 tests in the file go RED** -- every one of the three-way-disposition cases
(absent->create, diverged-custom->update, diverged-shared/GOLD->link+report,
identical->link) and both Principle-I GOLD GUID-remap tests are genuine tripwires;
none of them passes vacuously.

Collateral-damage check: re-ran the other 5 targeted files with the same revert in
place -- `tests/unit/test_027_entryref_reproduction.py`, `test_027_never_silent.py`,
`test_cycle16_drop_reporting.py`, `test_reference_create_paths.py`,
`test_reversal_category_resolve.py` together still show **44 passed**, i.e. the
revert affects only the file it targets, no spillover.

### 3b. T019 (C4 policy flip) -- revert of T020's GREEN hunk

Reverted the reproducibility skip in `_report_dropped_entry_refs` (removed the
`if _entry_ref_is_reproducible(ref): continue` guard, restoring pre-027
report-all-refs behavior). Re-ran `tests/unit/test_027_never_silent.py`:

```
FAILED test_in_closure_ref_yields_zero_dropped_records
FAILED test_mixed_refs_report_only_the_out_of_closure_one
FAILED test_ref_with_zero_components_is_trivially_in_closure
3 failed, 3 passed in 0.52s
```

**Genuine tripwires (3):** `test_in_closure_ref_yields_zero_dropped_records`,
`test_mixed_refs_report_only_the_out_of_closure_one`,
`test_ref_with_zero_components_is_trivially_in_closure` -- these are exactly the
assertions that require the new "skip if reproducible" behavior (0 records for an
in-closure ref, 1-not-2 for a mixed in/out pair, 0 for a zero-component ref), and all
three correctly break when the flip is reverted.

**Pass-even-when-reverted (3, expected, not a genuineness concern):**
`test_out_of_closure_component_yields_exactly_one_dropped_record`,
`test_entry_with_no_entry_refs_still_emits_nothing`,
`test_move_and_preview_drop_sets_identical_under_new_policy`. These three do not
discriminate between the old (report-all) and new (report-only-un-reproduced)
policy because their expected outcome is identical under both: an out-of-closure ref
is reported under both policies; an entry with zero `EntryRefsOS` returns immediately
under both (the `if not refs: return` guard predates this cycle); and the
Preview/Move parity test calls the same function from both paths regardless of which
policy is active, so parity holds either way. This is correct test design (they cover
different concerns -- C4 shape/never-silent parity, not the flip itself) and does not
weaken the tripwire proof for the 3 discriminating tests above.

Also re-ran `tests/unit/test_cycle16_drop_reporting.py` with the same C4 revert in
place: **11 passed** unchanged. This is expected and matches the commit message's own
note -- that file's fakes were deliberately updated
(`test_entry_with_multiple_entry_refs_emits_one_record_per_ref`) to give both refs an
out-of-closure component (no `LexemeFormOA`), so they remain "reported" under both
the old and new policy and are not meant to discriminate the flip;
`test_027_never_silent.py` is the flip's dedicated coverage, per the commit message
and the file's own docstring.

### Restoration confirmation

After both reverts, `src/gramtrans/Lib/categories.py` was restored from a backup
taken before any edit (copied to the session scratchpad before the first revert).
Verified:

```
git status --porcelain      -> (empty)
git diff da06a5c -- src/gramtrans/Lib/categories.py -> (empty)
```

and the full targeted 027 suite was re-run one final time post-restore:
**`52 passed in 0.76s`** (same as step 2). The worktree is clean; no revert was ever
staged or committed.

**Status: ALL CLAIMED TRIPWIRES GENUINE.** T013/T014 (8/8) and T019 (3/3
discriminating tests, +3 non-discriminating-by-design) all behave exactly as a
red-before-green discipline requires.

## 4. MCP-deviation scrutiny (no live run performed)

Per instruction, no FLExToolsMCP call and no live-LCM script was executed for this
check -- this section is a documentary audit only.

**What was read:**
- `d:/Github/_Projects/_LEX/GramTrans/scratchpad/run28_live.py` (only `run28_live.py`
  and `run031_live.py` exist under either repo's `scratchpad/`; there is no
  `probe_c3_lists.py` anywhere on disk, in the worktree or the main repo).
- `research.md` Decision 4 / Decision 8 (`specs/027-complex-forms-variants/research.md`).
- `tasks.md` Phase 4 (T013-T015) and Phase 7 (T023-T027), notably T025.
- `.crew-handoff.json` (`open_items.mcp_deviation`, `reconcile_note`).
- The da06a5c commit message body itself.

**Finding 1 -- `run28_live.py` is not the C3 probe.** `run28_live.py` is an attended,
destructive driver for issue #28 (MSA->slot wiring and `LexEntryRef`
Component/PrimaryLexemesRS membership after a real Move + reopen). It does a full
restore-from-backup -> Move -> reopen -> re-resolve cycle against a live `Target`
project. It says nothing about `VariantEntryTypesRS`/`ComplexEntryTypesRS`/
`ShowComplexFormsInRS`/`PublicationTypesRS` resolution (C3) at all -- it doesn't touch
entry-type/publication lists. It is unrelated to the C3 claims in the da06a5c commit
message and was not run as part of this gate (no live write was attempted, per
instruction).

**Finding 2 -- the actual C3 probe script does not exist.** The commit message and
the `test_027_entry_type_resolve.py` module docstring both name
`scratchpad/probe_c3_lists.py` as the read-only probe that confirmed, live against
Ejagham Mini: `LexDbOA.VariantEntryTypesOA` / `.ComplexEntryTypesOA` are
`ICmPossibilityList` with `ItemClsid=5118` (`LexEntryType`, `Depth=127`), and
`.PublicationTypesOA` is `ItemClsid=7` (generic `CmPossibility`, `Depth=1`). A
filesystem search of both the main repo and this worktree found no file by that
name, and no output/log artifact under any similar name (`*c3*`) anywhere in either
tree. The only two scratchpad scripts present are `run28_live.py` and
`run031_live.py`, both for different issues.

**Finding 3 -- the "cycle-3 report" the commit points to was never written.** The
commit message says "see the cycle-3 report's deviation note," but no
`specs/027-complex-forms-variants/reviews/cycle3-programmer.md` (or equivalent) exists
in either the main repo or the worktree -- only `cycle1-programmer.md`,
`cycle2-qc.md`, and `cycle2-verification.md` exist. `.crew-handoff.json`'s own
`reconcile_note` confirms this directly: "Prior agent committed spurt 3 ... as
da06a5c but died before ticking checkboxes / running the cycle-3 gate / updating
STATUS.md + this handoff. Bookkeeping reconciled 2026-07-13; cycle-3 gate now
dispatched." The only place the deviation is actually recorded in writing is
`.crew-handoff.json`'s `open_items.mcp_deviation` field ("da06a5c C3 live claims
(Ejagham Mini) rest on a read-only probe, NOT FLExTools MCP (not exposed to that
session). Cycle-3 verification must scrutinize this.") and the commit message body
itself -- i.e. this gate is that scrutiny, and it is happening without a primary
source artifact to check against.

**What the (now-unrecoverable) probe DID demonstrate, per the consistent prose
record (commit message + test docstrings + `research.md`):**
- The three target-list attribute names and shapes the CREATE arm needs
  (`VariantEntryTypesOA`/`ComplexEntryTypesOA`/`PublicationTypesOA` off `LexDbOA`,
  with the stated `ItemClsid`/`Depth` values) are asserted as real, live-confirmed
  identifiers on an actual Ejagham-Mini-shaped LCM cache -- i.e., the field-spec
  plumbing added to `references.py`'s `REFERENCE_FIELD_MAP` and the new
  `5118 -> ILexEntryTypeFactory` CREATE-arm entry are claimed to target real live
  attributes, not invented ones.
- This is consistent with `research.md`'s Decision 4 (drafted during Phase 0 planning
  with FLExToolsMCP access, dated 2026-07-13) -- the list-shape facts line up with
  what Decision 4 already establishes about reusing 024's resolver against
  possibility-list references, so the probe's claims are at least internally
  consistent with the planning-phase MCP research, even though the probe itself
  reportedly ran outside MCP.

**What remains UNPROVEN without a live attended Move + MCP re-resolution (T025):**
- End-to-end write-path correctness: whether `ILexEntryTypeFactory.Create(Guid)`
  actually succeeds against a live cache for the CREATE arm of C3's three-way
  disposition (the probe was read-only -- it looked at existing lists, it did not
  create anything).
- Whether the ancestor-chain creation path and Principle-I GUID-remap (T014) hold up
  against a real live target's existing possibility hierarchy (as opposed to the
  offline fakes in `test_027_entry_type_resolve.py`).
- The `LexEntryRef` 0->N creation itself (SC-001), variant-type wiring after reopen
  (SC-002), 0-duplicate re-Move (SC-003), and out-of-closure drop reporting (SC-004)
  -- all four are explicitly still unchecked under T025 in `tasks.md`, marked
  ATTENDED / needs_human, and correctly NOT attempted by this gate or by da06a5c.
- Whether C4's `_entry_ref_is_reproducible` in-closure/out-of-closure boundary
  matches real closure semantics on a live Move (only exercised offline here).

**Conclusion for this section:** the commit's live-claim framing is accurate about
what kind of evidence it has (read-only probe, not MCP, not the full live proof) and
is honest that T025 is the remaining live gate. However, the specific artifact that
would let a future session or reviewer re-verify the read-only probe's factual
claims (ItemClsid=5118/Depth=127/ItemClsid=7/Depth=1) is missing from disk, and the
report that was supposed to document the deviation was never written. This is a
process/bookkeeping gap, not a code-correctness defect -- the offline test suite
(sections 1-3 above) independently and mechanically verifies the C3/C4 code behavior
regardless of the probe's fate. No live-LCM write was attempted by this gate, per
instruction.

---

## Final Assessment

**Overall Status:** PASS

**Blockers:** none for this gate.

**Non-blocking findings to carry forward (recommend surfacing to lex-lead / QC):**
1. `scratchpad/probe_c3_lists.py` (the C3 read-only live probe) does not exist on
   disk anywhere -- cannot be re-run or re-inspected. Recommend re-confirming the
   ItemClsid/Depth claims via FLExToolsMCP (per repo rule) at or before T025, rather
   than relying solely on the commit-message/docstring prose.
2. No `cycle3-programmer.md` report was ever written; the commit message's pointer
   to "the cycle-3 report's deviation note" is currently a dangling reference. The
   only durable record of the MCP deviation is `.crew-handoff.json`'s
   `open_items.mcp_deviation` field plus this verification report. Recommend either
   writing a retroactive cycle-3 programmer note or updating the commit-message
   pointer's intent in `STATUS.md`.
3. T025 (live 0->N proof, SC-001-004) remains correctly unstarted and attended-only;
   nothing in this gate should be read as license to run it unattended.

**Recommendation:** APPROVE this cycle-3 verification gate for da06a5c. Proceed to
QC per the standing cycle-3 dispatch; carry the two documentation-gap findings above
into the record for whoever executes T025.

---
**Verified By:** Verification Agent
**Date:** 2026-07-13
