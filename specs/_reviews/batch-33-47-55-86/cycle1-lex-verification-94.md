# Verification PR #94 (fix-86-census-rebaseline @ 70bc997), read-only

Verdict: PASS (all steps). FLEXLIBS_REQUIRE_LIVE=1. Read-only: no project opened writeEnabled; no write transfers run.

Import paths (PYTHONPATH, confirmed by `gramtrans.__file__`): main = D:\...\GramTrans\src; worktree = D:\...\GramTrans-fix-86\src.

## A. Source sha256 (repo `census.sha256_of`), before == after: PASS
- Ngoreme FLEx: d0ab2c6600a427b3e0192e88b8247b85970f54a6ff2ede78083a3e5089c149db
- Mbugwe LizzieHC practice: 3fb29a294434f85301e2f2f75d704489cdf4495325252cfb0f8797137cd5436d
- Ejagham W Mini: 5ad15c10ee10d5463564397681b4d59bbafeda476f3febb5190b2003c2c5c3ea
- Ejagham Mini: d5bb4d32c0f412cbc0f2599065bd4b4d55cbd6e5097c193619cdec21a30ed9e4
(All four unchanged at end.)

## B. PASS
- main: 30 failed, 573 passed, 29 skipped (as expected).
- worktree: 595 passed, 39 skipped, 0 failed.
- 39 skips: 11 + 11 + 1 + 1... precisely: 10 (T024 Ngoreme, line 2689) + 1 (2694) + 11 (T024 Ejagham W Mini, 2689) + 1 (2694) = 23 digest-drift; 6 GRAMTRANS_E2E opt-in (5 + 1); 10 T081 ejagham t126-report absent (line 8753, message names `_run_reports\038-t126-ejagham-report.json`). 23+6+10 = 39. Exactly 10 are the named T081 skips; the other 29 are pre-existing.

## C. PASS
Current digests equal both KNOWN_SOURCE_MOVES "to" values (Ngoreme d0ab2c66..., Mbugwe 3fb29a29...). "From" values (838b7635..., fb6aadab...) equal the committed t078 baselines, via test_each_known_source_move_ends_at_a_committed_measurement (passes unmutated; t135 pins "to" and matches on disk).

## D. PASS (mutation, via scratch pytest plugin in scratchpad/mut; worktree untouched)
- Perturbed Mbugwe "to": 2 failed (reproducible[mbugwe], known_source_move[mbugwe]).
- Removed Ngoreme declaration (unlisted drift): 2 failed (the [ngoreme] counterparts). 51 others passed in each.

## E. PASS
T101 counts committed census-038-*.json artifacts that contain any null count row. Independent scan of all census-038-*.json files: 37 artifacts, null classes exactly {MoForm, MoMorphSynAnalysis}; 37 x 2 = 74 advisory nulls. It counts committed artifacts, not live source content, so no source read is involved.

## F. PASS
`git status --short` in the worktree: empty (only a commit-graph warning).
