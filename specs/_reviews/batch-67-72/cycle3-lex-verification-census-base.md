# Census failures: base 44ed51d vs branch fix-batch-67-72 (HEAD 8138a7f)
Cmd: FLEXLIBS_REQUIRE_LIVE=1 PYTHONPATH=<wt>/src python -m pytest tests/integration/test_object_census.py -q -p no:cacheprovider
flexicon -> D:\Github\_Projects\_LEX\flexicon (editable, not site-packages); base gramtrans imported from base worktree src. Read-only; no writes.
Results: base 31 failed/477 passed/29 skipped; HEAD 29 failed/479 passed/29 skipped.

| Test (class::test[param]) | base | HEAD |
|---|---|---|
| T078::reproducible_against_live_projects[mbugwe], [ngoreme] (2) | FAIL | FAIL |
| T081 EachRosteredClassEmitsItsLine::cmfile_and_cmfolder, moaffixprocess, phcode (3) | FAIL | FAIL |
| T081 ::expected_reason_token_lands_on_every_shortfall_row[ejagham,mbugwe,ngoreme] (3) | FAIL | FAIL |
| T081 GateStops::no_closed_row_still_unexplained, no_kind_one_residue_row_is_touched, p5_still_unsatisfied, p5_failure_count_drops, stamped_artifact_validates_schema, total_shortfall_does_not_move [x3 projects] (18) | FAIL | FAIL |
| T101::every_committed_null_row_is_advisory | FAIL | FAIL |
| T107::artifacts_now_reproduce[census-038-t107-mbugwe-phase6.json] | FAIL | FAIL |
| T108::t107s_own_censuses_still_hash_to_their_projects | FAIL | FAIL |
| MeasuredCensusSnapshots::snapshots_are_committed_repo_data[ejagham] | FAIL | pass |
| MeasuredCensusSnapshots::snapshots_are_committed_repo_data[ngoreme] | FAIL | pass |

(29 HEAD failures = 29 base failures; identical IDs. Base has 2 extra, fixed by the branch.)

Causes seen on HEAD: 3x `assert 'drifted' == 'match'` (T078 x2, T107 x1; per-counter names not printed
by the assertion); 24x CensusError "no run report" for _run_reports/038-t126-{ejagham,ngoreme,mbugwe}-report.json
(untracked run-report fixtures absent from the worktree -- environmental); 1x T101 corpus-list mismatch.

VERDICT: all 29 pre-existing at 44ed51d. 0 introduced by fix-batch-67-72 (branch fixes 2 more).
Worktree removed.
