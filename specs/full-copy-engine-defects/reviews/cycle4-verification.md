# Cycle 4 Verification — full-copy-engine-defects (offline)

**Status:** PASS

**Scope:** commit `0ad9cf4` (worktree `fullcopy-defects`) — `fix(reversals): dedup
ReversalIndexEntry create sites (no pre-create existence check)`, adding
`_find_existing_entry_by_form` to `src/gramtrans/Lib/reversals.py` and two new
regression tests to `tests/unit/test_reversal_category_resolve.py`.

## 1. New reversals regression test is a real guard

Ran `tests/unit/test_reversal_category_resolve.py` at HEAD (fix present):
**13 passed** (11 pre-existing + 2 new: `test_repeat_apply_reversals_top_level_does_not_duplicate`,
`test_repeat_apply_reversals_sub_entry_does_not_duplicate`).

Reverted ONLY the `src/gramtrans/Lib/reversals.py` hunk of commit `0ad9cf4`
(`git show 0ad9cf4 -- src/gramtrans/Lib/reversals.py | git apply -R`, leaving the
test file at HEAD untouched) and re-ran just the two new tests:

```
FAILED tests/unit/test_reversal_category_resolve.py::test_repeat_apply_reversals_top_level_does_not_duplicate
  AssertionError: second apply_reversals run duplicated the top-level entry
  assert 2 == 1
FAILED tests/unit/test_reversal_category_resolve.py::test_repeat_apply_reversals_sub_entry_does_not_duplicate
  AssertionError: second apply_reversals run duplicated the top-level entry
  assert 2 == 1
2 failed, 11 deselected
```

Both new tests fail without the fix (top-level entry duplicated on the second
`apply_reversals` run over the same decisions/target; sub-entry test fails at
the same top-level-duplication assertion before it can even reach the
sub-entry check). `git checkout -- src/gramtrans/Lib/reversals.py` restored the
fix; re-ran the full test file: **13 passed**. Guard confirmed genuine —
**Status: PASS**.

## 2. Prior cycle-3 targeted set (148 tests) still passes

```
pytest tests/unit/test_texts_fullcopy_defects.py tests/unit/test_text_structure_walk.py \
       tests/unit/test_text_markup_tags.py tests/unit/test_owned_object_walk.py \
       tests/verification/fidelity_census.py -q
```
→ **148 passed, 0 failed** (worktree `fullcopy-defects`, at commit `0ad9cf4`) —
identical to cycle 3's result. **Status: PASS**.

## 3. Full offline suite — zero new regressions

`pytest tests/ -q`:
- Worktree (`fullcopy-defects`, commit `0ad9cf4`): **27 failed, 1972 passed**,
  72 skipped, 14 xfailed, 14 xpassed.
- `main` (`0cd6c07`, same command): **27 failed, 1961 passed**, identical
  skip/xfail/xpass counts.
- The +11 pass delta (1972 vs 1961) is exactly the 9 new/rewritten tests from
  cycle 3 (`test_texts_fullcopy_defects.py` + `test_owned_object_walk.py`) plus
  the 2 new reversals regression tests added this cycle.
- The 27 failing test IDs are **byte-identical** between worktree and main
  (diffed the two `FAILED` line lists directly — both runs list the same 27
  IDs across `test_029_picture_asset_copy.py` (3), `test_029_sense_picture_reproduction.py`
  (2), `test_adjacent_data.py` (6), `test_analysis_idempotency.py` (3),
  `test_analysis_verdict.py` (1), `test_human_eval_gate.py` (5),
  `test_morph_bundle_wiring.py` (4), `test_residue_tagging_026.py` (1),
  `test_segment_alignment.py` (1), `test_wizard_pos_grammar_wiring.py` (1) =
  27). None of these touch `reversals.py` or the reversal test file.
- **Zero new failures.** Note: cycle 3's write-up bucketed
  `test_residue_tagging_026.py` as "×2" in its prose summary — this cycle's
  direct byte-for-byte diff against main (rather than trusting the prior
  cycle's prose bucket count) confirms the actual count is 1 on both branches;
  cosmetic discrepancy in cycle 3's doc, not a discrepancy in the underlying
  27-failure set itself.

## Fix-guard confirmed (via revert/restore of commit `0ad9cf4`'s src hunk)

`_find_existing_entry_by_form` (new helper) is called from both
`_create_top_level_entry` (scans `target_index.EntriesOC`) and
`_create_sub_entry` (scans `parent_entry.SubentriesOS`) before falling through
to `ReversalEntries.Create(...)` / the raw `IReversalIndexEntryFactory` path.
Without it, a second `apply_reversals` run over the same decisions
unconditionally re-creates every top-level entry and every sub-entry — exactly
the duplication bug commit `0ad9cf4`'s message describes. Confirmed empirically
above, not just by code reading.

## Recommendation

**APPROVE.** No blockers. No regressions. The fix is a genuine, tested guard
against re-Move duplication of `ReversalIndexEntry` objects, and offline test
health is unchanged from cycle 3's baseline (same 27 pre-existing failures on
`main`, none touching reversals).
