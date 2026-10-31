# Cycle 3 live verification A (merged tree d719a5d, worktree GramTrans-review-batch-107-116)
run_mode: live (FLEXLIBS_REQUIRE_LIVE=1). gramtrans = review worktree src; flexicon = D:/Github/_Projects/_LEX/flexicon (not site-packages).

| Test | Source -> target | Result | Exit |
|---|---|---|---|
| issue37 complex_type_ra | Mbugwe Lizzie -> GT-Sandbox-37 | 3 passed | 0 |
| issue108 features_rs_repair | Mbugwe Lizzie -> GT-Sandbox-108 | 1 passed | 0 |
| issue110 type_ra_single_writer | Mbugwe LizzieHC practice 2026 -> GT-Sandbox-110 | 2 passed (run2: 2 wire rows / 2 writes; run3: 0 writes, 2 "SKIP (already wired)") | 0 |
| issue87 residue idempotent | Mbugwe LizzieHC practice -> GT-Sandbox-107 | 1 passed (run1 17 actions, run2 0) | 0 |

#108 detail (-s output): Run 2 = 6 struct-type FeaturesRS repairs (inserts logged); Run 3 = 0 repairs, 0 actions; Run 4 (hand-swapped) repaired=0, order left swapped (e49c.., bd1d.., 5570..). The "SKIP (reordered" row count == 1 and the single reordered Skip are asserted in-test (lines 332-336, passed) but not printed in the -s output. grep RemoveAt in the log = 0 occurrences (no member moved).

SHA-256 (identical before and after):
- Mbugwe Lizzie: db195e04e8963ab4ab2d849f3ff955932fbe9ed52c90fb568da033ce60a7ff0c
- Mbugwe LizzieHC practice 2026: d1b7eb78dd4802a99fa098ca01ab92cbb02bb57d5ec8fc07580b3fc29189eea5
- Mbugwe LizzieHC practice: 3fb29a294434f85301e2f2f75d704489cdf4495325252cfb0f8797137cd5436d

Locks: none in touched projects. Pre-existing locks on Ejagham Full GT-Test, Esperanto, Hdi (not touched by this run). Worktree `git status --short`: clean.

Noise: every run prints "Windows fatal exception: access violation" (faulthandler, early in the test; stack in _open_target / test body) yet tests continue, pass and exit 0. This is a known pythonnet/CLR faulthandler artifact, not a test error (exit codes all 0, no nonzero-with-passed case).

Verdict: [PASS] - 7/7 passed, all exit 0, sources unchanged.
