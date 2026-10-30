# Cycle 1 live verification: PR #93 (closes #33)
Verdict: PASS. run_mode live, FLEXLIBS_REQUIRE_LIVE=1.
Written: only `GT033 Review Target` (restored from Target 2026-07-06 0218.fwbackup via harness/restore.py). Source `Mbugwe LizzieHC practice` opened read-only.
Imports: fix = D:\Github\_Projects\_LEX\GramTrans-fix-33\src\gramtrans (@58bb118); main = D:\Github\_Projects\_LEX\GramTrans\src\gramtrans (aa0d36f); flexicon = D:\Github\_Projects\_LEX\flexicon (pyflexicon 4.13.0, >= 4.8.0).
Driver: scratchpad v93/drv.py (my own, not the author's); logs and JSON in scratchpad v93/.

| Step | Result | Numbers (main / fix) |
|---|---|---|
| A unit suite, worktree | PASS | 5098 passed, 81 skipped, 14 xfailed |
| B full-selection preview, bindings | PASS | 203 / 203 |
| B 3-affix preview (after move 1), bindings | PASS | 203 (198 outside picks) / 5 (0 outside) |
| B DEPENDENCY_UNRESOLVED, 3 picks (executed) | PASS | 2 real + 96 spurious / 2 real + 0 spurious |
| B the 2 real | PASS | Both belong to affix 12d4bab5, slots fc50f37f and 4306d08f, "not in target after slot transfer". Neither slot is in the target after move 1, so both are genuine. |
| C 3-affix execute | PASS | Link outcomes 105 LINKED + 98 SLOT_MISSING / 3 LINKED + 2 SLOT_MISSING. Target MSA->slot pairs 105 before and after on both (new pairs 0), so nothing was lost. The 3 picks were already linked by move 1, and the 2 missing slots cannot link. |
| D slots+templates-only run, after C | PASS | Bindings 203 / 159. LINKED 203 / 159. Skips 0 / 0. Target pairs 105 -> 203 on both (98 new each). |
| E worktree `git status --short` | PASS | Empty |

Step B note: DEPENDENCY_UNRESOLVED only arises at execute, not preview. So B was measured on the real move 1 -> move 2 sequence (move 1 = AFFIXES-only: 98 real skips, 0 spurious on both).

Step D: the fix still binds in-run slots to affix MSAs already in the target (98 new links, same as main). It drops 44 bindings, those whose slot is not in the run. All 44 were already linked in the target from move 1, so the final target state is identical: 203 pairs on both.

Caveat: the D run also pulled in slots through the template closure (9 slot actions for 5 picked slots). Behaviour is identical on both code versions.
