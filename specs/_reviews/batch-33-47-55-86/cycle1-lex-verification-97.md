# Live verification -- PR #97 (closes #47)

**Verdict: [PASS]** | run_mode: live (FLEXLIBS_REQUIRE_LIVE=1) | date 2026-10-30
**Source:** Ngoreme FLEx (read-only). **Projects written (only):** `GT047 Review Main`, `GT047 Review Fix`, both restored from `backups/Ngoreme Target 2026-08-19 0831.fwbackup`. Left in place.
**Import paths:** flexicon = `D:\Github\_Projects\_LEX\flexicon\flexicon` (pyflexicon 4.13.0 >= 4.8.0). Main runs: gramtrans from `D:\Github\_Projects\_LEX\GramTrans\src` (aa0d36f). Fix runs: `D:\Github\_Projects\_LEX\GramTrans-fix-47\src` (d8b436c). Both confirmed by printed `gramtrans.__file__`.
Scripts: `...scratchpad\v97\` (run.py, seq.sh, clash.py, sdiff.py, sub.py; reuses PR agent's dangle47.py, probe47.py).

## Steps
- A [PASS] fix-worktree `tests/unit`: 5105 passed, 81 skipped, 14 xfailed (exact match).
- B [PASS] clean target, ADD then overwrite re-runs (fix: 3 runs). Every PR number reproduced.
- C [PASS] incompatible clash (see below).
- D [PASS] see below.
- E [PASS] `git status --short` in fix worktree is empty.

## B: main vs fix (measured from .fwdata)
| Metric | Main run1 -> run2 | Fix run1 -> run2 -> run3 |
|---|---|---|
| dangling objsur | 0 -> **7** | 0 -> 0 -> 0 |
| duplicate GUIDs | 0 -> 0 | 0 / 0 / 0 |
| owner/owned inconsistencies | 0 -> 0 | 0 / 0 / 0 |
| contexts correctly owned (of 89) | 87 -> **75** | 87 -> 87 -> 87 |
| rt object count | 12614 -> 12602 (-12) | 12614 constant |
| fwdata byte delta | +506,942 / +16,197 | +506,942 / +17,280 / +36,866 |
| structural diff of 129 rule/context objects | 12 objects differ | run1 vs run2: 0; **run2 vs run3: 0** |

Structural diff ignores DateModified and the `[GT-Tag]` run, which is the only text that changes (GT-Tag count 119 -> 138 -> 157; known #87 residue). Raw bytes differ only in the 8 rule objects, by that tag. Main's 7 dangling: RHS RightContext -> 09ab1138, 569f5e02, 28efff56; sequence 59138948 members x3; sequence 9384ec66 member x1.
Note: the run3 byte delta (+36.9 KB) is larger than run2's. It is not structural (0 diff) and I did not chase it.

## C: clash on GT047 Review Fix
Nulled NC `a86c10a2` in RHS 0b8e9171 (rule 4bc56951), then created a PhSimpleContextSeg with that GUID in the pool (separate sessions). The overwrite re-run:
- emitted "structural_rebuild: rule guid=4bc56951 left unchanged -- GUID collision ... (issue #47): ... already exists as a PhSimpleContextSeg, but the source object is a PhSimpleContextNC";
- wrote a DroppedItemRecord and a Warning (both present);
- left the rule's raw XML byte-identical (3-object subtree, before == after). No dangling refs, 0 duplicate GUIDs.

## D: UPDATE-path failures (identical set on main and fix, runs 2 and 3)
All six rules fail with "RuntimeError ... references phoneme/NC guid ... absent from target".

| Rule | Main (run2) | Fix |
|---|---|---|
| 33978942 | destroyed (5 -> 4 objects; dangling RightContext 09ab1138) | preserved, identical |
| 32a37f0d | destroyed (4 -> 3; dangling 28efff56) | preserved, identical |
| 1b8c0e7a | destroyed (5 -> 4; dangling 569f5e02) | preserved, identical |
| b4625d2e | subtree identical | preserved |
| 8ec67b0b | subtree identical | preserved |
| 7aa53db3 | own subtree identical, but sequence 59138948 left with 3 dangling members | preserved (only trailing-whitespace XML difference) |

Fix emits "contexts ... restored to their previous position" warnings for 1b8c0e7a, 33978942, 32a37f0d.
The root cause (UPDATE path with `context=None`) is unfixed by design; it deserves its own issue.

State C (stale-pool reconstruction): not run (optional).
