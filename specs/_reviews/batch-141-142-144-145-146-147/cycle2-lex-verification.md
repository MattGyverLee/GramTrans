# Cycle 2 live verification (#141/#144/#145/#146/#147 + wordforms P1 + planned label)

**Verdict: FAIL** (modules and planned-label PASS; wordforms P1 Preview PASS, Move-report claim FAIL)
**run_mode:** live (FLEXLIBS_REQUIRE_LIVE=1; no tests/live_status.json exists in this repo, so not checked). Marker is `integration`, not `requires_live_project` (the latter deselects everything).

## Env (printed from inside the runs)
- render tip 24f85b2: gramtrans = GramTrans-fix-146-render\src\gramtrans, flexicon = D:\Github\_Projects\_LEX\flexicon\flexicon
- fix-146 tip 1888dee: gramtrans = GramTrans-fix-146\src\gramtrans, same flexicon
- Both worktrees clean after runs. A pythonnet access-violation faulthandler dump appears at FLExInitialize, but summaries are clean.

## Per-module (live passed / xfailed)
| Module | Expected | render 24f85b2 | fix-146 1888dee |
|---|---|---|---|
| #141 lexrel | 5 | 5 PASS | n/a |
| #144 pos/text | 6 | 6 PASS | n/a |
| #145 module preview | 4 | 4 PASS | n/a |
| #146 dedup | 5+2 strict xfail | 5 + 2 xfailed PASS | 5 + 2 xfailed PASS |
| #146 segment-tag rebind | 4 | 4 PASS | 4 PASS |
| #147 row cap (new wording) | 2 | 2 PASS | n/a |

No strict-xfail XPASS. #147 live ran for the first time against the new wording and passed.

## Wordforms P1 (scratch script p1_live.py in scratchpad, own pair GT-Src-146P1 / GT-Sandbox-146P1)
Fixture: shared POS authored, target forked, then source got an absent POS plus 4 approved analyses on 4 wordforms in one text (3 on the absent POS, 1 on the shared POS). Pre-state re-queried: absent POS not in target; shared POS in target; 0 analyses in target.

| Claim | GREEN (render) | RED (reverted wordforms hunk) |
|---|---|---|
| Preview: one drop per analysis | 3 CategoryRA drops, guids match the 3 analyses [PASS] | 1 drop (undercount) |
| Move: category unset on each | all 3 target analyses CategoryRA None, absent POS not created [PASS] | same |
| Move report carries a drop for each | `report.dropped_items` = 0 [FAIL] (3 only in the returned plan: `plan2.dropped_items`) | 0 report, 1 plan |

RED: full copy at scratchpad\red146w, `git apply -R` of `git diff 1888dee^ 1888dee -- wordforms.py` (absent_before count 0 vs 4 in the worktree); env print shows gramtrans resolved to the copy path.

Finding A (FAIL): Move's `_apply_category` returns early on REPORT_DROPPED ("already reported"), and plan-time drops are not merged into the Move RunReport. The logic predates #146, but the stated claim does not hold live.

Finding B (out of scope, not reported by the branch): the analysis on the SHARED POS (should LINK) also ended with CategoryRA None. The log shows `texts.apply: swallowed FP_ParameterError: Category must be an IPartOfSpeech object`. `_apply_category` calls `SetCategory` without an IPartOfSpeech cast, inside `_texts._safe`, so a legitimate LINK silently fails. The line is untouched by this branch; recommend a separate issue.

## Planned label (real Preview, p2_live.py; two reversal entries on one new reversal POS)
```
  Reversal categories (each reversal index's own category list):
    Create  'GT146P2 newrevpos' {c4d8fbdb-...}  (1 reversal entry)
    Link  'GT146P2 newrevpos' {c4d8fbdb-...}  (1 reversal entry) -- links to the item created above in this run
    (New in this run: created once, and the other references link to it.)
```
PLANNED_LINK_ROW_SUFFIX and REVERSAL_TEXT_NEW_IN_RUN_NOTE both present [PASS]. Programmer deviation 4 (suffix on #144 planned Links) fires; not ruled on. The #147 collapse planned line was not captured live (unit-covered only).

## Hashes (.fwdata sha256, before = after, IDENTICAL)
- Esperanto e9effa15262739d8fc11e2ce72f0a1b44c88cf7a1d8d5b5a669643aa16683189
- Ejagham Mini d5bb4d32c0f412cbc0f2599065bd4b4d55cbd6e5097c193619cdec21a30ed9e4
- Mbugwe LizzieHC practice 3fb29a294434f85301e2f2f75d704489cdf4495325252cfb0f8797137cd5436d

## Incident
A failed `cd` made one `git apply -R` run in the render worktree instead of the copy. I restored it with `git checkout -- src/gramtrans/Lib/wordforms.py` (the file was clean beforehand); status is clean at 24f85b2. A stray `/red146` directory (copy of src/tests) and `/wf.patch` may exist under the Git-bash root; my removal was blocked, so please delete them.

## Recommendation
FIX ISSUES: decide whether Move must carry the wordform category drops (Finding A), and file Finding B.
