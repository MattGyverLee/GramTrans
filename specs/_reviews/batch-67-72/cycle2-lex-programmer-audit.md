# Cycle 2: feature-038 audit test failures

Tests: `test_every_link_in_the_chain_declares_whether_it_is_reproducible` (tests/integration/test_038_closure_edge_audit.py, "link"),
`test_every_report_field_is_classified` (tests/integration/test_038_no_silent_skips.py, "field").

| commit | link | field |
|---|---|---|
| 44ed51d (merge base) | FAIL | pass |
| 09f9619 | FAIL | FAIL |
| caaf000 | FAIL | FAIL |
| e0375ff | FAIL | FAIL |
| HEAD (pre-fix) | FAIL | FAIL |

## Verdicts
- field: REGRESSION from this batch. 09f9619 added `RunReport.outcome_counted` (#68) without classifying it in `REPORT_FIELD_ROLES`. The diff was `{'outcome_counted'}`. The #49 agent's "pre-existing" claim is wrong for this test.
- link: PRE-EXISTING at 44ed51d. It is census drift: `census-038-mbugwe-phase6.json` reports `('drifted','drifted')` where the test expects `('match','drifted')`. It is not caused by this batch and is out of scope, so it is not fixed. It needs a Mbugwe census refresh or re-baseline under feature 038. Do that in its own change and do not fold it into this batch.

## Fix
Commit 436558a (only tests/integration/test_038_no_silent_skips.py). It classifies `outcome_counted` as `NOT_AN_ITEM`, a provenance flag on a counter. The test is not weakened. The 34 tests in that file pass.

## Suite
`python -m pytest tests/unit -q`: 5051 passed, 81 skipped, 14 xfailed, 0 failed (prior 5051/81/14/0, unchanged). The integration "link" test still fails, as at the base.

Throwaway worktrees removed. Nothing pushed. No .github/ files touched.
