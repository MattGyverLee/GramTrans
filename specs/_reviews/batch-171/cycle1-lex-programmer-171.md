# impl-171 -- InflectableFeats mid-pass raise keeps tallies (issue #171, P2)

Branch `fix-171-infl-midpass`, worktree `/workspace/worktrees/GramTrans-fix-171`.

## Diagnosis

Issue #133 added `_infl_pairs_settled` before the link loop so reconciliation still
reports unsettled pairs when `_run_infl_feature_link_pass` raises mid-pass
(`test_a_pass_that_raises_midway_keeps_the_pairs_it_settled`). Two tallies still
lived only in function locals:

1. **`_infl_feature_link_writes`** -- incremented in a local `writes` counter and
   flushed only at normal return (`categories.py` end of pass). A mid-pass exception
   discarded confirmed links already on the target.
2. **`Skip` list** -- `_ensure_infl_feature_links` only extends `exec_skips` from the
   return value; on exception `late_skips` stayed `None` even when the pass had
   already appended POS-unresolved or WRITE_FAILED skips.

## Fix

- `_run_infl_feature_link_pass`: wrap the binding loop in `try`/`finally`.
  `_flush_infl_link_pass_progress()` always merges `writes` into
  `context._infl_feature_link_writes`. On exceptional exit, stash partial `skips`
  on `context._infl_feature_link_skips_stash`.
- `transfer._ensure_infl_feature_links`: on pass exception, recover stashed skips into
  `late_skips` before reconciliation (then clear the stash).

## Tests

- Extended `test_a_pass_that_raises_midway_keeps_the_pairs_it_settled` to assert
  `_infl_feature_link_writes == 1`.
- New `tests/unit/test_issue171_infl_midpass_tally.py`: mid-pass raise after an
  earlier POS-unresolved skip and one confirmed link.

## Verification

```
PYTHONPATH=src python3 -m pytest tests/unit -q
```
(Full unit suite green in cloud agent environment; no live gate -- flexicon/LCM not
available here.)
