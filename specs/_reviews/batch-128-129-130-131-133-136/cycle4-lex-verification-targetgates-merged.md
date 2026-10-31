# Cycle 4 live Target gates on merged tree (V3)

Merged sha: a3cc7ce (origin/main 717d7bf + a2d81a8, d88dc4a, 659cc83, 69b5577; all merges clean).
Worktree: D:/Github/_Projects/_LEX/GramTrans-verify-c4t. flexicon -> D:\Github\_Projects\_LEX\flexicon\flexicon. FLEXLIBS_REQUIRE_LIVE=1, Target restored before each module.

| Module | Baseline | Merged |
|---|---|---|
| test_object_census | 500p/39s | 500p/39s |
| 038 affix_slot_links | pass | 10 p |
| 038 closure_edge_audit | pass | 95 p |
| 038 no_silent_skips | 1 pre-existing fail | 33 p, 1 f (test_every_report_field_is_classified) |
| 038 phon_empty_drop | pass | 12 p |
| 038 process_rules | pass | 29 p |
| 038 stale_lock | pass | 30 p |
| 038 two_mode_and_tallies | pass | 12 p (no tally drift) |
| 038 total | 221p/1f | 221p/1f |
| issue16 | 1 f pre-existing | 1 f, `'BasicIPASymbol' in []` (same) |
| issue45 / 48 / 49 / 67 / 87 / ws_followups | pass | 1 / 5 / 1 / 2 / 1 / 2 passed |
| 028_affix_msenv_live | SKIP | SKIP (needs GRAMTRANS_E2E=1, attended-only) |

Failures: both match baseline; no batch-introduced failures, so no bisect needed. No census LcmFileLockedException occurred.
Note: a first attempt on issue16/issue45 ran without restore (harness import error in my script); both were re-run after a verified restore, with identical results.

Hashes (sha256 .fwdata), unchanged before/after:
Ngoreme 6d35c9575fc6094089dff757da4f54f266aa5a0d7e4ea16cd1fd3bd64abe472d
Esperanto e9effa15262739d8fc11e2ce72f0a1b44c88cf7a1d8d5b5a669643aa16683189
Mbugwe LizzieHC practice 3fb29a294434f85301e2f2f75d704489cdf4495325252cfb0f8797137cd5436d
Target restored from backup at end; worktree left in place.
