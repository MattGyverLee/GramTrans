# Cycle 1 - integration build of #153/#157/#159/#160/#155

## Verified PR heads (after git fetch; all match)
- #153 fix-147-sense-list-row-cap: bd8047d
- #157 fix-145-module-preview-extra-lines: e7c7d8f
- #159 fix-144-preview-pos-text-decisions: 04c2998
- #160 fix-146-preview-cache-picture-dedup: e5ea12e
- #155 fix-141-142-preview-lexrel-records: 5ffd503

Merge order 147, 145, 144, 146, 141-142, `--no-ff`, one merge commit each. No PR branch touched, nothing pushed, no stash.

## Integration branches (local only)
- A: `integ-141-147` at a986e6a, worktree D:/Github/_Projects/_LEX/GramTrans-integ-141-147 (from origin/main 0a3c190)
- B: `integ-141-147-stack` at fb25f0f, worktree D:/Github/_Projects/_LEX/GramTrans-integ-141-147-stack (from f7f7213)

## Conflicts
Base A: the first four merges were clean (preview.py auto-merged for 144 and 146). Merging 141-142 conflicted in `src/gramtrans/Lib/preview.py` only, in two hunks.
1. Both #144 and #141 append after `render_sense_list_reference_decisions`. I kept both: #144's section (`_ref_decision_*`, `render_reversal_and_text_decisions`) first, then #141's `render_lexical_relation_decisions`. Each keeps its own `return tuple(lines)`.
2. Both add one line to `render_preview_extra_lines`. I kept both, in the order `render_reversal_and_text_decisions` then `render_lexical_relation_decisions`.

Base B: the same single preview.py conflict, with the same two hunks and the same resolution. These merged with no conflict (git "Auto-merging" messages):
- #147 into preview.py.
- #146 into references.py, preview.py and categories.py.
- #141 into models.py and categories.py.
- models.py: `RunPlan.lexical_relation_decisions` is appended at the tail and is intact.
- #146 vs #152 in categories.py and transfer.py: no textual conflicts. The unit suite is green on B, which is the semantic check.
- Not run: the live-LCM gate. This task was unit-only.

## Cap and helper consolidation
- One constant remains: `SENSE_LIST_REF_ROW_CAP = 25` (#147's; public, and imported by #147's tests and the live test).
- `_REF_DECISION_ROW_CAP` is removed. Its only importer was `tests/unit/test_issue144_preview_pos_text_decisions.py`, which I updated in the same commit.
- I kept #144's inline cap and did NOT unify it onto `_capped_rows`. Reason: `_capped_rows` emits `"... and N more X not shown here (T total)"`, while #144 emits `"    +N more"`. Unifying would change the rendered strings. The task says behaviour must not change. A code comment records this.
- Strings and counts are unchanged.

## Cross-PR test
`tests/unit/test_integ_141_147_planned_link_render.py` (2 tests, present on both branches).
- It builds a cache with `references.mark_planning_cache({})` and calls `decide_reference` twice on the same source-only thesaurus item. The results are CREATE, then LINK with `target_item=None` and `source_item` set.
- (a) The two decisions go in as reversal `pos_decision`s into #144's `render_reversal_and_text_decisions`.
- (b) The decisions are flattened via `categories._reference_decision_record` and fed to #147's `render_sense_list_reference_decisions`.
- Both tests pass. Neither renderer raises, and the name 'lonely item' and GUID {n-guid} come from the source item.
- Wording is NOT locked: assertions check only name and GUID.

Verbatim current output (source item name "lonely item", GUID "n-guid"):
```
  Reversal categories (each reversal index's own category list):
    Create  'lonely item' {n-guid}  (1 reversal entry)
    Link  'lonely item' {n-guid}  (1 reversal entry)

  Sense appendix / thesaurus references:
    Create  ThesaurusItemsRC 'lonely item' {n-guid}  (1 sense)
    Link  ThesaurusItemsRC 'lonely item' {n-guid}  (1 sense)
    (Later references to an item created earlier in this run show as create; Move links them.)
```
(The blank line is only the boundary between two separate renderers' output.)

Observation for the domain ruling: both renderers show the planned Link row exactly like a Link to an item already in the target. Nothing marks it as "linking to an item this run will create". Name and GUID are right.

## Unit results
Run from each worktree with PYTHONPATH=<worktree>/src. gramtrans resolves to the worktree and flexicon to D:/Github/_Projects/_LEX/flexicon/flexicon/__init__.py (verified on A).

| Base | Result | Expected | Delta |
|---|---|---|---|
| A | 5474 passed, 80 skipped, 14 xfailed | 5472 + new | +2 = my 2 new tests; exact |
| B | 5523 passed, 80 skipped, 14 xfailed | 5521 + new | +2 = my 2 new tests; exact |

- Zero failures on either base. The pre-existing `test_034_gate_default` PyQt6 gate did not fail in this environment, so there is nothing to explain.
- Skipped and xfailed counts match the baseline.

## Patch
`C:/Users/thoua/AppData/Local/Temp/claude/d--Github--Projects--LEX-GramTrans/9d0ddb47-dadb-4191-886a-347021a07731/scratchpad/141-142-resolution-and-cap-consolidation.patch`
- It is `git diff HEAD^2 HEAD` on base A, limited to preview.py and the #144 test. Applied on top of #155 it reproduces the integrated state of those two files.
- The same scratchpad directory holds `resolve.py`, the script that applied the resolution and the cap consolidation. It reproduces the edit from the conflicted state.
