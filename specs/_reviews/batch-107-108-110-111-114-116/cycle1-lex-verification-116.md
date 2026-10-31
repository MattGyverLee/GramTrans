# Verification #116 (PR #123) - cycle 1
Worktree GramTrans-fix-116 @ 68db9b1. run FLEXLIBS_REQUIRE_LIVE=1, GT42_TARGET_NAME=GT-Sandbox-116.
Imports: gramtrans=D:\...\GramTrans-fix-116\src\gramtrans\__init__.py ; flexicon=D:\...\_LEX\flexicon\flexicon\__init__.py
Projects written: GT-Src-42 (fixture authoring, by design), GT-Sandbox-116. No others touched.

1. PASS - snapshot copied pre-run; .fwdata SHA 13c5a96f...74c7f (matches expected).
2. PASS - 8 passed, 1 xfailed; target=GT-Sandbox-116; pane rows show Create (ThesaurusItemsRC x3), Link (AppendixesRC, ThesaurusItemsRC 'anatomy'), Not transferred (Appendix 42-ABSENT).
3. PASS - mutation (two records.extend -> bare calls): 2 failed (test_preview_create_link_decisions_match_move, test_preview_pane_renders_create_and_link_rows), 6 passed, 1 xfailed. Reverted via git checkout; git status --short clean.
4. PASS - GT-Src-42 had drifted (test restores it from backup; diff showed difference), restored from snapshot: `diff -r` snapshot vs project = no output (byte-identical); .fwdata SHA 13c5a96f...74c7f.

Verdict: PASS (live, real LCM; tests are discriminating).
