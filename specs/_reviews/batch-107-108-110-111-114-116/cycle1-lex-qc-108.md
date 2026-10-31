# QC cycle1 #108 (PR #122, c61105f) - 80/100, APPROVE-WITH-FIXES

> Saved by the main session: lex-qc has no Write tool and returned this text verbatim.

Static review only. No unit tests, no live runs.

**Q1. Transaction and failure handling**
- There is no per-rewrite transaction or undo wrapper. `transfer.py` (header, line 5) relies on the FlexTools UndoableUnitOfWork, and `api.py` ~171-271 relies on the ambient NonUndoableTask. The new pass runs inside that same envelope as every other write, so it is no worse than the rest of execute().
- There is no atomicity, though. In `_rewrite_features_rs` (categories.py:3359-3375), a failure after `RemoveAt` and before `Insert` loses a member. A second failure mode is the sequence ending half-reordered.
- Failure is never raised. `categories.py:3449` converts it to Skip(DEPENDENCY_UNRESOLVED), and `transfer.py:396-399` swallows anything else.

**Q2. Preview/Move parity**
- Both use `_classify_struct_type_features_rs`, so Repair rows equal Move writes in the common branches.
- Closure-pulled case: Preview says "Wire at create" because the type is planned. Move reclassifies after create, and the type is COMPLETE if every member resolves. This is consistent as long as feature defns are created before struct-types.
  - That ordering is true for ms, from the #37 comment.
  - I did not verify it for the ph pair PHONOLOGICAL_FEATURES vs PHON_FEAT_TYPES. A planned member that lands after the type makes Preview say "Wire at create" while Move writes a repair.

**Q3. Drop-record labels**
- `_item_label` goes through `_multistring_dict` (references.py:324-395), which reads `StringCount` and `GetStringFromIndex` and handles the tuple return. This is the path that live IMultiUnicode already uses elsewhere (the #42 sense-scope drops).
- It returns "" only when every alt is empty. The fallback is a bare GUID in the report line, which is cosmetic.

**Q4. Conflict with #110 (ce672ad)**
- Conflict-free by inspection.
- #110's `transfer.py` ends the call block with `_ensure_complex_feature_type_ra(...)` followed by a blank line and the "# Issue #49" comment (line 874). #108 inserts between those two. #110 shifts line numbers only in categories.py, in the TypeRA block, which #108 does not touch.

**Q5. Noise from target-only members**
- Acceptable but noisy. It is one Skip per target-only member, per type, per in-scope run, and it is never cleared.
- Nothing from Preview feeds the report totals, so Preview and Move counts can diverge.

## P0
None.

## P1
- **categories.py:3359-3375 and :3455-3457: a failed rewrite can lose a member, and the skip text is wrong.**
  - The skip detail says "sequence left as it was". That is false after a RemoveAt that succeeded before a failed Insert.
  - Snapshot `list(seq)` first. On exception, best-effort restore (clear the sequence and re-add the snapshot), and say so in the detail. Alternatively, do the Insert before the RemoveAt and handle the shifted index, so a failure can only duplicate, never lose.
  - Add a unit test with an Insert that raises.
- **categories.py:3438-3441 and transfer.py:396: `_classify...` is called outside the per-type try.**
  - An exception on one type aborts the whole pass.
  - It also discards the skips and drops already gathered and leaves `_struct_type_features_rs_writes` unset.
  - Wrap each type's iteration in a try.

## P2
- categories.py:3469-3476: aggregate target-only members to one Skip per type, or de-dupe across runs.
- categories.py:3462: if `context._dropped` is None, drops vanish with only a log line. Preview can show them while the Move report does not.
- categories.py:3338: `g in current_set` counts a member as resolvable even if its defn is not in `FeaturesOC`. In the repair path with a nonresident g, the exact outcome depends on `list(seq)` objects. This is harmless today.
- Live gate asserts GUIDs only. Add a non-empty `owner_label` / `item_name` assertion.
- preview.py:2019: for COMPLETE, "-> list(desired)" prints the current sequence, not the source order. This can mislead.

Pattern-audit gate: PASS (present in PR body per impl report). I did not spot-check a HIGH sibling.
Live-evidence gate: the impl report cites a live run with run_mode live and pre/post GUID lists, plus mutation checks. I did not verify the evidence artifact exists at specs/<feature>/evidence/live-*.md.
