# Cycle 4 -- integration verification of merged PRs #154 #158 #156 #152

Worktree: D:/Github/_Projects/_LEX/GramTrans-verify-c4 (detached, left in place; nothing committed)
Base 717d7bf. **Merged HEAD: f7f7213ad6b9d9542d39105818be7961232a1c59**
Merges (--no-ff, in order a2d81a8, d88dc4a, 659cc83, 69b5577): **all 4 clean, zero textual conflicts.**
gramtrans.__file__ = worktree/src/gramtrans/__init__.py ; flexicon.__file__ = D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py (not site-packages).

## Per-step results
| Step | Result |
|------|--------|
| 1 unit | 5468 passed / 80 skipped / 14 xfailed in 120s -- EXACT match, 0 failures |
| 2 semantic clash | PASS (see below) |
| 3a 128 entryref_postpass + affixes_only | 2 passed |
| 3b 42 appendix (GT42_TARGET_NAME=GT-Sandbox-129) | 9 passed, no xfail |
| 3c 130 overwrite_slots | 4 passed |
| 3c 31 msa_slot (GT_ISSUE31_SANDBOX=GT-Sandbox-130) | 8 passed |
| 3c 038 affix_slot_links | 10 passed (offline: reads committed snapshot, writes nothing) |
| 3d 133 pos_inflfeats | 3 passed |
| 3e 136 subsense_refs | 5 passed |
| 3e 131 semdomain_create | 1 passed |
| TypeError count ("Apply syncable properties: exception TypeError") | 0 in every log (positive control: the same logs contain 6-445 "apply syncable" lines, so logging was captured) |

Live runs used FLEXLIBS_REQUIRE_LIVE=1, sequential; every module restores its own sandbox(es) from Target 2026-07-06 0218.fwbackup via harness.restore (verified in source), so no extra restore was run. Note: adding `-m requires_live_project` deselects all of these modules (they are not marked), so they were run without -m, by file path only. tests/live_status.json is not produced by these modules; liveness evidence is the passes under REQUIRE_LIVE=1 (a skip/mock would not pass these).
`Target` was never touched.

## Unit count reconciliation
5419 main + 2 (#154) + 6 (#158) + 15 (#156) + 26 (#152) = 5468. Observed 5468. No per-PR discrepancy.

## Step 2 detail
- #152's only new `_unwrap` call sites are preview.py (pos_typed=_unwrap(pos), _guid_str(_unwrap(feat))); preview.py `_unwrap` (line 4317) = `return _shared_unwrap(obj)`. transfer.py `_unwrap` (2360) and conflict.py/merge_preview.py `_unwrap` likewise delegate to lcm_unwrap.unwrap. #152 added no new transfer.py `_unwrap` calls.
- One definition of `_unwrap` per module (preview, transfer, conflict, merge_preview); no duplicates.
- Observation (not a clash, pre-existing on main, not from #152): categories.py:4913 has a nested closure `def _unwrap` (`_cast_rule_concrete(getattr(obj,"concrete",obj))`) and `_unwrap_lcm` (`._obj` only) at :268. They do not use lcm_unwrap; out of scope of #156 but a candidate follow-up for the same AffixSlot-style `.concrete`-only blind spot.

## Negative controls (src checked out at pre-fix sha, then restored)
| Test file | src at | Result |
|-----------|--------|--------|
| test_issue130b_unwrap_root.py | f8096a3 | 11 failed, 2 passed (new tests fail pre-fix) |
| test_133_deferred_reconciliation.py | 971c3b3 | 12 failed, 1 passed |
| test_issue129_create_arm_multistring.py | f8096a3 | 6 failed, 5 passed (the 6 new tests all fail: all_dropped_analysis_text, vernacular_best_alt, unresolvable_default_analysis, unknown_vernacular_set, wrap_plain_text, apply_failure_record_carries_owner) |
`git status --short` clean after restore (verified; no diff vs HEAD).

## sha256 of read-only projects (.fwdata), before == after (SAME)
- Mbugwe LizzieHC practice: 3fb29a294434f85301e2f2f75d704489cdf4495325252cfb0f8797137cd5436d
- Ngoreme: 6d35c9575fc6094089dff757da4f54f266aa5a0d7e4ea16cd1fd3bd64abe472d
- Esperanto: e9effa15262739d8fc11e2ce72f0a1b44c88cf7a1d8d5b5a669643aa16683189

## Verdict: [PASS] -- the four heads coexist; APPROVE merge in stated order.
