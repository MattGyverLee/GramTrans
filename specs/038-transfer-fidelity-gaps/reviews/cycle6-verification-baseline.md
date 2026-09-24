# Cycle 6 -- Verification Baseline (read-only measurement)

**Tree:** worktree `D:\Github\_Projects\_LEX\GramTrans-038-transfer-fidelity-gaps`
(branch `038-transfer-fidelity-gaps`, HEAD `5cf155c`), uncommitted token edits in
place throughout except during the stash probe noted below.

## Part 1 -- Authoritative baseline

**Command (i):**
`python -m pytest tests/unit/ -q`
**Result:** `3881 passed, 79 skipped, 14 xfailed` -- matches the ~3881/79/14 comparand
exactly. (A `Windows fatal exception: access violation` traceback prints during
`test_034_prereq_report.py::test_every_failing_check_in_a_real_report_has_a_remedy`
via `flexicon/FLExInit.py`; process exits 0 and the test is counted passed both
runs -- a known-noisy pythonnet/.NET artifact, unrelated to this task's files,
not a regression signal.)

**Command (ii):**
`python -m pytest tests/integration/test_object_census.py tests/unit/test_038_t079_report_only_residue.py tests/unit/test_038_null_counts.py tests/unit/test_038_census_report_evidence.py -q`
(Note: `test_038_census_report_evidence.py` lives under `tests/unit/`, not
`tests/integration/` as given in the task brief -- verified by directory
listing before running.)
**Result:** `5 failed, 635 passed, 29 skipped` -- matches the 635/5/29 comparand
exactly. The inherited "521 passed, 2 pre-existing failures" figure is confirmed
stale for this selection.

Five failures, each named:
1. `TestT101TheCommittedCorpusIsUnmovedByInvariant12::test_every_committed_null_row_is_advisory` -- artifact-corpus count pin (17) now sees 21 committed census artifacts (T123b/T124x3/T126x3 landed since the pin).
2. `TestT078ThePost037Baseline::test_each_baseline_is_reproducible_against_the_live_projects[mbugwe]` -- `mbugwe.source` now `drifted`, expected `match`.
3. `TestT078ThePost037Baseline::...[ngoreme]` -- `ngoreme.source` now `drifted`.
4. `TestT107TheBoundaryContextCreatePath::test_these_artifacts_are_the_ones_that_now_reproduce[census-038-t107-mbugwe-phase6.json]` -- `.source` `drifted`.
5. `TestT108TheSharedRouteAttribution::test_t107s_own_censuses_still_hash_to_their_projects` -- same mbugwe-phase6 `.source` `drifted`.

**Confirmed pre-existing:** re-ran the identical `-k` selection
(`TestT101TheCommittedCorpusIsUnmovedByInvariant12 or TestT078ThePost037Baseline
or TestT107TheBoundaryContextCreatePath or TestT108TheSharedRouteAttribution`)
against the worktree with the token edits **stashed out** (`git stash push -u`)
-- identical `5 failed, 49 passed, 476 deselected`, byte-identical failure set
and error text. Stash restored via `git stash pop`; `git status --porcelain`
before stash and after pop are identical (both list the same 7 modified paths,
no untracked residue). The T078/T107/T108 failures are live-`.fwdata` drift on
committed corpus files (as claimed); T101 is corpus-count drift from
intervening spurts (T123/T124/T126), not fwdata hash drift per se, but equally
pre-existing and unrelated to today's edits. Claim **confirmed** for all 5.

## Part 2 -- Pyright diagnostics triage

Command: `python -m pyright src/gramtrans/Lib/models.py src/gramtrans/Lib/census.py tests/integration/test_object_census.py`
Changed-hunk ranges (new-file line numbers, from `git diff -U0`):
- models.py: 777, 805-812, 831, 834, 836-838, 844, 934-951, 1915
- census.py: 85, 88, 2590, 3349, 3680
- test_object_census.py: 35-36, 43-44, 147-150, 160, 1940, 1944-1952, 2000, 2006-2065, 6148, 6154-6162, 6177-6187

The brief's claimed touch points ("models.py ~805/855/914/1884") only partly
match the real hunks: 805 and 1884(->1915) are real; **855 and 914 do not fall
inside any changed hunk** -- verified rather than trusted, per instructions.

| Diagnostic | Verdict | Evidence |
|---|---|---|
| models.py:559 `ConflictMode` return type | PRE-EXISTING | 559 is before the first changed hunk (777) |
| census.py:3644/3648/3651/3655/3663 `int\|None -` | PRE-EXISTING | nearest hunks are 2590 and 3680; 3644-3663 is inside neither |
| census.py unresolved imports (SIL.LCModel@1074/1283, SIL.LCModel.Infrastructure@1103, flexicon@1473) | PRE-EXISTING | all outside every hunk; environment/pythonpath, not edit-related |
| test_object_census.py typing complaints (474, 791, 2115, 2356-2460, 2759, 4739-4785, 5408-5493, 7856) | PRE-EXISTING | none fall inside any of the file's 7 changed hunks (35-2065, 6148-6187) |

No diagnostic landed inside a changed hunk, so the `git stash`/`pop` confirmation
step was not required for Part 2 (Part 1's stash probe, done for a different
reason, incidentally shows the tree round-trips cleanly). `git status
--porcelain` before/after both Part-1 stash and the full session: identical,
7 modified paths, no untracked leftovers, no source edited by this agent.

## GO/NO-GO

**GO** -- the uncommitted token edits introduce zero new test failures (3881/79/14
and 635/5/29 both match comparand exactly, and the 5 failures reproduce
byte-for-byte with the edits stashed out) and zero new pyright diagnostics (every
flagged line sits outside every changed hunk in models.py, census.py, and
test_object_census.py).
