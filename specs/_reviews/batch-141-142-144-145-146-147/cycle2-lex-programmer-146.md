# Cycle 2 - lex-programmer - #146 (PR #160, worktree GramTrans-fix-146)

Commit: 1888dee (local, not pushed; parent e5ea12e). PYTHONPATH verified: gramtrans from the worktree src, flexicon from D:/Github/_Projects/_LEX/flexicon/flexicon/__init__.py.

## Task 1 - can another Preview consumer plant a PlannedCreate for a POS under the same cache key?
Short answer: not today, but the cache is not scoped to protect against it.
- The cache is `context._resolver_cache` (preview.py:1311-1319), keyed by bare source GUID. It has no list scoping.
- decide_reference callers: categories.py:6813 and :6941 (generic, via `field_specs_for(owner_class)`), owned.py:420/605/936, reversals.py:344, texts.py:386/518, wordforms.py:521.
- No `REFERENCE_FIELD_MAP` spec (references.py:70-290) targets `LangProject.PartsOfSpeechOA`. The only decide_reference call against that list is wordforms `_pos_spec()` (wordforms.py:215-224).
- The reversals spec targets the index's own `PartsOfSpeechOA` (reversals.py:106). It uses reversal-category GUIDs, which are different objects from list POSes.
- The categories/lexical POS leg creates POSes directly (categories.py:1332-1461) and does not use decide_reference.
- The MsEnv POS twin (owned.py:1575+) uses its own keyed dicts (`_MSENV_POS_*_KEY`), not GUID entries.
- The real hazard was the reverse direction. wordforms primed PlannedCreate placeholders for POS GUIDs it never creates. A later lookup of the same POS, in wordforms or in any future consumer, then returned a phantom LINK. A GUID collision would also have let a foreign planned entry through.
- Task 3 handles both directions.

## Changes (files and lines, relative to e5ea12e)
- models.py:4185-4188 `ReferenceDecision.planned: bool = False`. models.py:4236 `ReferenceDecisionRecord.planned: bool = False`. Both are defaulted.
- references.py:807 decide_reference sets `planned=is_planned_create(cached)`.
- references.py:1032-1041 apply_reference LINK arm logs a WARNING when `target_item` is None. It does not raise.
- categories.py:6568 `_reference_decision_record` carries `planned`.
- wordforms.py:520-532 `resolve_or_report_category` records which chain GUIDs were absent before the call, using `_ancestor_chain`. Only the chain is touched; there is no cache copy. A `finally` block then deletes any PlannedCreate it added itself. A foreign pre-existing planned entry is left alone.
- wordforms.py:537-540 `planned` or LINK with `target_item` None is now REPORT_DROPPED with a DroppedItemRecord, the same as CREATE. N analyses sharing an absent POS give N drops.
- wordforms.py:1082-1099 `_apply_category`: LINK with `target_item` None logs a warning and appends a DroppedItemRecord. It does not raise.
- texts.py:923-949 new helper `_rebind_or_drop`. It runs `rebind_planned_link` and, on an exception or a None result, logs a warning and appends a DroppedItemRecord. It is used at texts.py:954-960 (genres) and texts.py:1007-1012 (segment tags). Both callers `continue` when it returns None.
- Live test `test_issue146_preview_cache_picture_dedup_live.py`: the imperative `pytest.xfail` helper is replaced by `@pytest.mark.xfail(strict=True, reason="#161 ...")` on the two genre tests.
- Copied `tests/integration/test_integ_146_segment_tag_rebind_live.py` from the integ-141-147-stack worktree. The original is left in place.
- New `tests/unit/test_issue146_planned_link_guards.py` with 6 tests.

## Unit counts
- Baseline, same tree minus the new file: 5436 passed, 80 skipped, 14 xfailed.
- With the new tests: 5442 passed, 80 skipped, 14 xfailed.
- No regressions.

## RED evidence
Each src change was reverse-applied alone, the new tests were run, then the change was re-applied.
- Revert wordforms.py: 3 failed.
  - `test_two_analyses_same_absent_pos_give_two_drops_and_clean_cache`
  - `test_planned_link_from_foreign_leg_is_downgraded_to_drop`
  - `test_apply_category_guard_emits_drop_and_warns`
- Revert texts.py: 1 failed, `test_raising_rebind_in_texts_emits_drop`.
- Revert references.py: 2 failed.
  - `test_decide_reference_sets_planned_on_placeholder_link`
  - `test_apply_reference_link_without_target_warns`
- With all changes applied: 6 passed.
- The two-analyses test's negative control is that same revert of wordforms.py. Without the fix, the second analysis gets a phantom LINK or a missing drop, and the leftover PlannedCreate in the cache is caught.

## Live results (FLEXLIBS_REQUIRE_LIVE=1, own GT-Src-146/GT-Sandbox-146 sandbox pairs restored by fixtures)
- `test_issue146_preview_cache_picture_dedup_live.py` plus `test_integ_146_segment_tag_rebind_live.py`: 9 passed, 2 xfailed (the strict #161 genre tests). 15s.
- There was a faulthandler traceback dump at interpreter shutdown, which looks like pythonnet teardown. The exit result was still 9 passed and 2 xfailed.
- No writes to Esperanto, Ejagham Mini or Mbugwe LizzieHC practice.

## Notes
- The strict xfail is unconditional. Once #161 is fixed on the flexicon side, both genre tests will XPASS-fail and need revisiting.
- I did not make wordforms link to a POS created by another leg. That is the deferred follow-up.
- The report is not committed.
