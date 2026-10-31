# Live verification, merged tree (#37 gate for #108 + #110 combined)

Worktree GramTrans-review-batch-107-116 @10eef63. FLEXLIBS_REQUIRE_LIVE=1, PYTHONPATH=<worktree>/src, run sequentially.
Each log shows gramtrans = D:\...\GramTrans-review-batch-107-116\src\gramtrans\__init__.py; flexicon = D:\...\flexicon (not site-packages).

| Test | Source -> Target | Result |
|------|------------------|--------|
| test_issue37_complex_type_ra_live.py | Mbugwe Lizzie -> GT-Sandbox-37 | PASS (3 passed) |
| test_issue108_features_rs_repair_live.py | Mbugwe Lizzie -> GT-Sandbox-108 | PASS on rerun (see note) |
| test_issue110_type_ra_single_writer_live.py | Mbugwe LizzieHC practice 2026 -> GT-Sandbox-110 | PASS (2 passed) |

Note (#108): first run FAILED in 1.6s before any transfer, on a hardcoded provenance assert
`"GramTrans-fix-108" in gramtrans.__file__` (test-scaffolding, not a product failure). I temporarily
changed the literal to the review worktree name, reran: 1 passed (27.7s), then `git checkout` reverted it.
The test file on the branch still carries the stale literal and will fail in any other worktree; fix it separately.

SHA-256 (identical before and after all runs):
- Mbugwe Lizzie.fwdata: db195e04e8963ab4ab2d849f3ff955932fbe9ed52c90fb568da033ce60a7ff0c
- Mbugwe LizzieHC practice 2026.fwdata: d1b7eb78dd4802a99fa098ca01ab92cbb02bb57d5ec8fc07580b3fc29189eea5

Cleanup: each test's fixture restores its sandbox from the Target 2026-07-06 0218 backup after the run
(logs end with "Restore ... completed (11 files)"). The backup path used was the worktree's own
backups/ copy of that file, not the GramTrans/backups path named in the brief. `git status --short` clean.
Ngoreme/GT-Sandbox-111 never touched.

Verdict: PASS. #110 (TypeRA create-path removal) and #108 (FeaturesRS pass) hold live, alone and combined.
