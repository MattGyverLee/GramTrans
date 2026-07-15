# Cycle-1 Verification Report -- inflection_classes per-POS fix

**Worktree:** d:\Github\_Projects\_LEX\GramTrans-coverage-content-fidelity-v2
**Branch:** coverage-content-fidelity-v2
**Commit under test:** bf70c0a (fix(gram): rewire inflection_classes to IPartOfSpeech.InflectionClassesOC)
**Interpreter:** D:\Apps\anaconda3\python.exe (Python 3.12.7, pytest 9.0.2)
**Invocation:** python -m pytest ... run from worktree root. conftest.py prepends
worktree\src to sys.path at position 0 -- confirmed this resolves gramtrans.__file__
to the worktree copy, not the main-repo editable install that this interpreter has
registered via its _editable_impl_gramtrans.pth (which points at
D:\Github\_Projects\_LEX\GramTrans\src). Verified with a manual sys.path check
before running any suite.
**Date:** 2026-07-15
**Status:** PASS (one minor discrepancy noted below -- non-blocking)

## Executive Summary

All four verification steps requested were executed. The fix is confirmed to turn
a genuinely-red baseline green, the full unit suite matches the claimed counts
exactly, the single pre-existing failure is confirmed pre-existing (fails
identically on the unmodified baseline), and categories.py compiles clean.

One approximate claim ("~5/9 fail" on baseline) does not match exactly -- the
baseline actually shows 4/9 failing, 5/9 passing (not 5 failing). This is a minor
discrepancy in an approximate figure, not a correctness issue with the fix itself;
flagging per instructions since any count divergence is to be stated plainly.

**Recommendation:** APPROVE (fix verified; note the ~5 to 4 approximation
correction in the record).

## Step 1 -- Targeted test file (fixed code)

Command: tests/unit/test_categories_inflection_classes.py -v

Result: 9 passed, 0 failed (9/9). Exact list, all PASSED:
- test_dependencies_yields_owner_pos_edge
- test_dependencies_empty_when_no_owner
- test_enumerate_source_yields_all_classes_across_poses
- test_enumerate_source_empty_when_no_pos
- test_plan_action_new_guid_yields_planned_action
- test_plan_action_already_present_yields_skip
- test_plan_action_different_guid_not_present
- test_execute_action_adds_new_class_to_owner_pos_inflection_classes_oc
- test_execute_action_returns_none_when_owner_pos_unresolved

Status: CONFIRMED -- matches the claim of 9/9 pass.

## Step 2 -- RED baseline reproduction

Method: git checkout HEAD~1 -- src/gramtrans/Lib/categories.py (isolates the
categories.py change only, equivalent to a scoped stash of just that file;
verified git status --short showed only "M src/gramtrans/Lib/categories.py" while
reverted). HEAD~1 is 95cfb81, the commit immediately prior to the fix commit
bf70c0a on this branch, i.e. genuinely pre-fix code.

Result with reverted categories.py:

4 failed, 5 passed in 0.53s

Failing tests (baseline/RED):
- test_dependencies_yields_owner_pos_edge
- test_enumerate_source_yields_all_classes_across_poses
- test_plan_action_already_present_yields_skip
- test_execute_action_adds_new_class_to_owner_pos_inflection_classes_oc

Passing on baseline (not sensitive to the bug -- e.g. empty/no-POS and
different-guid edge cases that do not depend on which collection is walked):
- test_dependencies_empty_when_no_owner
- test_enumerate_source_empty_when_no_pos
- test_plan_action_new_guid_yields_planned_action
- test_plan_action_different_guid_not_present
- test_execute_action_returns_none_when_owner_pos_unresolved

DISCREPANCY vs claim: the task briefing stated "confirm ~5/9 fail." Actual
baseline is 4/9 failing, 5/9 passing -- one fewer failure than the approximate
figure. This does not affect the substance of the fix: the 4 failures reproduced
are exactly the ones expected from the bug description (dependency edge shape,
cross-POS enumeration, "already present" detection against the correct per-POS
collection, and execute_action landing in the correct owner collection). Given
the "~" qualifier in the original claim, this is judged NOT a P0 blocker -- the
identity of the 4 reproduced failures directly matches the bug root cause, which
is the substantive claim being verified. Flagged here plainly as instructed.

After reverting to fixed code (git checkout HEAD -- src/gramtrans/Lib/categories.py,
confirmed git status --short clean of that path again), rerunning the same file
returned 9 passed, 0 failed -- confirming the fix is what turns the 4 RED tests
green (and does not disturb the other 5, which passed on both baseline and fixed
code).

Status: CONFIRMED -- fix demonstrably turns the RED baseline tests green; count
is 4/9 failing (not ~5/9 as approximately stated), flagged above.

## Step 3 -- Full unit suite

Command: python -m pytest tests/unit -q

Result (fixed code, HEAD bf70c0a):

1 failed, 1594 passed, 8 skipped, 14 xfailed, 14 xpassed in 8.25s

This is an EXACT MATCH to the claim: 1594 passed, 8 skipped, 14 xfailed,
14 xpassed, 1 failed.

The one failure:

tests/unit/test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos
FAILED -- AssertionError: assert 0 == 1 (pos_actions list empty, expected 1 POS action)

Confirmed pre-existing: reverted categories.py to HEAD~1 (pre-fix) again and ran
this single test in isolation -- it fails identically (assert 0 == 1, same
traceback) on the unmodified baseline. Restored categories.py to the fix (HEAD)
afterward and re-ran the full suite once more to confirm counts are stable and
reproducible: 1 failed, 1594 passed, 8 skipped, 14 xfailed, 14 xpassed (identical
on rerun).

This matches the main-repo STATUS.md running record, which independently
documents this exact test as a known baseline failure across multiple recent
features (msa-slot-wiring-v2, 027-complex-forms-variants), i.e. it is not specific
to or introduced by this fix.

Status: CONFIRMED -- full-suite counts match exactly; the one failure is
confirmed pre-existing and unrelated to the inflection_classes fix.

## Step 4 -- py_compile

Command: python -m py_compile src/gramtrans/Lib/categories.py

Result: clean, no output, exit 0.

Status: CONFIRMED.

## Working-tree integrity check

After all git checkout HEAD~1 / git checkout HEAD round-trips used to reproduce
the RED baseline, git diff --stat against bf70c0a shows no diff -- the worktree
was restored to the exact fix commit. An untracked file "nul" was present in the
worktree before this verification began and was left untouched; it is unrelated
to this change.

## Final Assessment

| Check | Claimed | Observed | Status |
|---|---|---|---|
| Targeted file, fixed code | 9/9 pass | 9/9 pass | match |
| Baseline (reverted categories.py) | ~5/9 fail | 4/9 fail, 5/9 pass | off by 1 (approx claim) |
| Fix turns baseline RED tests green | yes | yes (same 4 tests) | match |
| Full unit suite | 1594 passed, 8 skipped, 14 xfailed, 14 xpassed, 1 failed | identical | exact match |
| The 1 failure is test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos | yes | yes | match |
| That failure is pre-existing (fails on baseline too) | yes | yes, identical traceback | match |
| py_compile categories.py clean | yes | yes | match |

**Overall Status:** PASS

**Blockers:** None.

**Recommendation:** APPROVE. The only deviation from the claims is the
approximate baseline fail-count ("~5/9" vs actual 4/9), which is a minor wording
imprecision, not a defect in the fix -- the substantive claim (the fix turns the
correct RED tests green, without disturbing the others) is fully confirmed.

**Next Steps:**
1. Note the 4/9 (not ~5/9) baseline-fail count correction in the feature record
   if a precise historical count is desired.
2. No code changes required from this verification pass.

---
**Verified By:** Verification Agent
**Date:** 2026-07-15
