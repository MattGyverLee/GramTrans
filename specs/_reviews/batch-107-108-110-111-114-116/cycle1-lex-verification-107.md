# Cycle 1 live verification -- #107 (PR #125), worktree GramTrans-fix-107 @ f0bd7bb

**Imports (confirmed in log):** gramtrans = D:\Github\_Projects\_LEX\GramTrans-fix-107\src\gramtrans; flexicon = D:\Github\_Projects\_LEX\flexicon\flexicon.
**Projects:** read: "Mbugwe LizzieHC practice" (source, read-only). Written: GT-Sandbox-107 only (GT_ISSUE87_TARGET set; shared Target untouched).
**Env:** FLEXLIBS_REQUIRE_LIVE=1, PYTHONPATH=fix-107/src.

## Checks
1. [PASS] Source SHA-256 before: 3fb29a294434f85301e2f2f75d704489cdf4495325252cfb0f8797137cd5436d
2. [PASS] test_issue87_residue_idempotent_live.py: 1 passed (43.8s); run1 actions=17, run2 actions=0.
3. [PASS] Mutation (`if False:` before _fill_created_pos_collections in leaf loop): test FAILED, "run 2 created objects (#107)": FsFeatStruc, MoInflAffixSlot, MoInflAffixTemplate ... Run 1 still 17/0 in log, but the post-run-2 object diff caught the missing fill, so the test is sensitive to the fix.
4. [PASS] Revert via git checkout; `git status --short` clean (empty).
5. [PASS] Source SHA-256 after: identical to before (3fb29a29...436d).
6. [PASS] GT-Sandbox-107 restored by the test fixture from the backup after each run (log: "Restore ... completed (11 files)").

## Verdict: APPROVE
