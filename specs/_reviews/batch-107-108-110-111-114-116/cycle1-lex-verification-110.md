# Live verification - PR #121 (closes #110), HEAD ce672ad

Imports (printed): gramtrans=D:\Github\_Projects\_LEX\GramTrans-fix-110\src\gramtrans\__init__.py ; flexicon=D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py (not site-packages).
Projects: source "Mbugwe LizzieHC practice 2026" (read-only); written: GT-Sandbox-110 only. Env: FLEXLIBS_REQUIRE_LIVE=1.
Note: sandbox restores used the worktree's backups/Target 2026-07-06 0218.fwbackup (same-named backup).

1. PASS - Source SHA before: d1b7eb78dd4802a99fa098ca01ab92cbb02bb57d5ec8fc07580b3fc29189eea5 (matches expected).
2. PASS - test_issue110_type_ra_single_writer_live.py: 2 passed. Run 2: 2 "TypeRA wired" logs (49eaca04.. -> 2b491f35.., df4a248b.. -> 0a6c2f79..), leaf-dispatch 10/10; run 3: 0 actions attempted.
3. PASS - Mutation (old c088d16 categories.py copied in): run2 printed wire_rows=2 reported_writes=0 wired_log=0, i.e. the 0 == 2 equality the test guards. (The pytest FAILED summary line was cut off by my output filter; failure inferred from those printed counts, not from the summary line.) Reverted via git checkout; git status --short clean.
4. PASS - Source SHA after identical to before. Final test run left GT-Sandbox-110 restored from the backup.

Verdict: [PASS] live, real LCM, mutation-sensitive. APPROVE.
