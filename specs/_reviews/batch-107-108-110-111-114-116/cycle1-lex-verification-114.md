# Cycle 1 live verification - PR #124 (closes #114)
Worktree GramTrans-fix-114 @ bb06edb. FLEXLIBS_REQUIRE_LIVE=1.

Imports: gramtrans from D:\Github\_Projects\_LEX\GramTrans-fix-114\src (PYTHONPATH; traceback paths confirm), flexicon from D:\Github\_Projects\_LEX\flexicon\flexicon (editable, not site-packages).
Projects written: GT-Src-114 (seeded from file-copy of Korean-GIAL), GT-Sandbox-114 (restored from Target backup). Korean-GIAL never opened.

1. PASS - Korean-GIAL SHA before = 9ea5a4a4...e594775c (expected).
2. PASS - test_issue114_entryref_value_fields_live.py: 2 passed (27s). Create matched seeded values; re-run A: Move 2 had 1 action (stem create/ref only) and refs unchanged; re-run B: value drops=[], diverged target (HideMinorEntry 0, Summary 'TARGET EDIT', etc.) merged back to source values incl. ko-fonipa Summary ('114 summary two-ws (ko-fonipa)'); target-only ws/entries preserved.
3. PASS - Mutation (`return []` at top of _merge_entryref_value_fields): 2 failed. Reverted via git checkout; git status --short clean.
4. PASS - Korean-GIAL SHA after = 9ea5a4a4...e594775c (unchanged); no *.lock in Korean-GIAL, GT-Src-114, GT-Sandbox-114.

Notes: the printed "re-run A actions=1" is not literal 0; the claim "0 actions" was not read from that line - I did not independently audit that assertion beyond the test passing. One extra unmutated run printed a faulthandler stack (FLExInitialize) in grep output; it was a diagnostic dump during a repeat run, not a test failure observed in the verdict runs.

Verdict: PASS (live, mutation-sensitive). Recommendation: APPROVE.
