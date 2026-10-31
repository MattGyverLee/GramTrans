# Team Lead Final Report: batch 141-142-144-145-146-147 (cycle 2 synthesis)

**Decision:** APPROVED for PR #160 scope (fix-146 + planned-link render). No cycle 3. Two pre-existing problems go to new issues (one P1 data bug).

## Basis
- QC: fix-146 91/100, render 88/100, no P0/P1 (cycle2-lex-qc.md).
- Live (FLEXLIBS_REQUIRE_LIVE=1) on both tips incl. 24f85b2 (the landing tree): all modules pass; planned label shows in real Preview; read-only hashes unchanged (cycle2-lex-verification.md = Gate 2 evidence).
- Units 5479 passed / 80 skipped / 14 xfailed / 0 failed on 24f85b2 (test_034 excluded).
- Wordforms P1 closed on the Preview side: 3 drops for 3 analyses (RED: 1); absent POS not created; categories unset.

## Finding A -- Move RunReport omits Preview-planned drops (NOT merge-blocking, pre-existing)
The "Move report carries a drop for each" claim came from the lead's cycle-2 brief, not the programmer. Text-family drops
(texts, analyses, glosses, alignment, segment tags, genres, wordform categories) are decided at Preview time and live only in
`plan.dropped_items`; `transfer.execute`, `api.execute_move` (api.py:1096-1097) and the GUI path (gramtrans.py:624-625) build
the Move report from Move-time drops + WS failures only. RED run also shows 0, so it predates #146. Design question: a naive
fold reports false drops where Move resolves a projected drop, and census_cli credits on `dropped_items`. -> new issue.

## Finding B -- wordform category LINK silently fails (P1, pre-existing)
`wordforms._apply_category` calls `wa_ops.SetCategory(analysis_obj, target_item)` inside `_texts._safe` without an
IPartOfSpeech cast; flexicon raises `FP_ParameterError: Category must be an IPartOfSpeech object`, swallowed. Analyses on a
shared POS end with CategoryRA None, unreported. Untouched by #160. Recommendation: new P1 issue + separate write-path PR (full
crew + live gate; audit sibling `_safe(lambda: ops.SetX(obj, resolved))` sites). Blocks #166. User may instead choose a cycle 3.

## What lands on #160
Fast-forward `fix-146-preview-cache-picture-dedup` e5ea12e -> 24f85b2 (e5ea12e, 1888dee, origin/main 91faad5 are ancestors).
Diff vs main: 17 files, +1598/-56. Render judgment calls 1-4 accepted; call 4 (planned suffix also on #144 reversal Link
rows) is an extension of the approved wording -- one-line revert if rejected.

## Merge steps (each needs user OK)
1. Commit cycle-2 reports to main. 2. `git merge --ff-only 24f85b2` in GramTrans-fix-146, push (not force).
3. Confirm origin/main == 91faad5, else re-run units on the merge result. 4. Update PR #160 body (scope, Closes #146,
wording note for #144/#147, calls 1-4, Findings A/B linked). 5. `gh pr merge 160 --merge`; confirm #146 closed.
6. File issues A and B; comment QC P2s on #164 and the strict-xfail note on #161. 7. Ask before removing worktrees/branches
fix-141/144/145/146/147, fix-146-render, integ-141-147, integ-141-147-stack.

## Outstanding
- P1 Finding B; P1 Finding A (both new issues). QC P2s -> #164 comment; strict xfail -> #161 comment. User to review call 4.
