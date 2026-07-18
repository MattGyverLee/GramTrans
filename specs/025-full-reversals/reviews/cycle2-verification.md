# P0 reversal-category CREATE fix -- Cycle 2 Verification

Worktree: `D:/Github/_Projects/_LEX/GramTrans-025-fix-reversal-pos-create`
Branch: `025-fix-reversal-pos-create`, fix commit `752a60c`.

## 1. Offline suite: GREEN

`python -m pytest tests/unit -q` on the worktree:
**1719 passed, 22 failed, 8 skipped, 14 xfailed, 14 xpassed.**

- Target test `test_create_path_reversal_category_hierarchical_owner_taking_factory`
  (in `tests/unit/test_reference_create_paths.py`): **PASSED** (isolated run also green).
- The 22 failures are the SAME pre-existing set the programmer's report names
  (test_adjacent_data.py x6, test_analysis_idempotency.py x3, test_analysis_verdict.py x1,
  test_human_eval_gate.py x5, test_morph_bundle_wiring.py x4, test_residue_tagging_026.py x1,
  test_segment_alignment.py x1, test_wizard_pos_grammar_wiring.py x1 = 22). No new regressions.

## 2. Revert tripwire: RED-on-revert CONFIRMED (y)

`git checkout c617790 -- src/gramtrans/Lib/references.py` (reverting only the CREATE-arm
fix, keeping the RED-test commit's test file) then re-running the target test:

```
E   gramtrans.Lib.references.UnmappedItemClassError: unmapped item class 5049 for CREATE
```
Exactly the expected error. Confirms the fix is load-bearing, not a no-op.
Restored via `git checkout HEAD -- src/gramtrans/Lib/references.py`; re-ran target test:
PASSED. `git status` clean, no revert left uncommitted or committed.

## 3. Live Preview re-validation: NOT EXECUTED (tool unavailable to this agent)

This verification sub-agent's toolset does not include FLExToolsMCP / `run_module`
(only Read/Grep/Glob/Bash were available), so I could not drive
`scratchpad/run025_s2s3_live.py` (or a worktree-pointed copy) against the live
`Ejagham025Src` project myself. I prepared but then removed a worktree-path variant
rather than fabricate a run I could not execute.

**Static/code-level substitute check** (read-only, `src/gramtrans/Lib/references.py`
lines ~1007-1099 in the worktree): confirms `factory_by_item_clsid` now maps
`5049 -> IPartOfSpeechFactory`, and the ancestor loop's `item_clsid == 5049` branch
calls `factory.Create(parsed_guid, owner)` directly (owner = `target_list` cast to
`ICmPossibilityList` at the root, else the just-created parent `IPartOfSpeech`),
never `_add_to_owner`. This is the exact code path the now-green unit test exercises
end-to-end with a fake LCM stub, so the create is planned rather than dropped in the
same code that Preview calls.

**Action needed:** the orchestrator (or an agent with FLExToolsMCP access) must run
the live read-only Preview step directly -- point a copy of `run025_s2s3_live.py`'s
`_ROOT` at the worktree path and confirm S2's `pos_action == "create"` for the person
entry, with target = the reversal index's own `PartsOfSpeechOA` (R5 untouched). I did
NOT run any write/Move.
