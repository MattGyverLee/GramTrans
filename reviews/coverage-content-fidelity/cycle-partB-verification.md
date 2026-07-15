# Coverage Content-Fidelity Part B -- Verification Report (cycle 1)

**Status:** APPROVE WITH CONCERN (non-blocking, tracked)

## 1. Full offline suite

`python -m pytest tests/unit -q` (worktree, branch coverage-content-fidelity-v2 @ ed7addf):
**1642 passed, 8 skipped, 14 xfailed, 14 xpassed, 1 failed.** Matches expected
baseline exactly. The single failure is
`test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos`
(assert 0 == 1) -- confirmed to be the documented pre-existing baseline
failure, no new deviation.

## 2. RED-first spot-check (B.3, POS_INFLECTABLE_FEATS)

Checked out pre-fix state of the 4 touched source files + 2 touched test
files from `dfcc626~1` (`git checkout dfcc626~1 -- categories.py models.py
preview.py transfer.py test_category_registry.py test_conflict_mode_model.py`),
leaving the new untracked test file in place. Ran
`test_categories_pos_inflectable_feats.py` alone:
`AttributeError: type object 'GrammarCategory' has no attribute
'POS_INFLECTABLE_FEATS'` at collection time -- genuine RED, matches the
programmer report exactly. Restored with `git checkout HEAD -- <same files>`;
re-ran same file: 15 passed. `git status --short` clean afterward.

## 3. py_compile

Clean over all changed modules: categories.py, models.py, preview.py,
transfer.py, merge_preview.py, plus all 4 new/touched test files. No errors.

## 4. CONCERN #1 -- dispatch-order / cross-reference gap

Verdict: **CONCERN, not a blocker, but the programmer's "resolves on second
run" claim is incorrect and should be corrected in the record.**

First-run behavior is safe: `inflection_features_execute_action`'s complex
branch (categories.py:759-780) leaves `TypeRA` unset and logs an INFO message
when the target struct-type isn't found -- no crash, no partial/orphan write.

However, tracing the **second-run** path shows it does NOT converge as
claimed. `INFLECTION_FEATURES` is GOLD_RESERVED and its `plan_action`
(`_plan_gold_reserved_edit`, categories.py:194-260) only compares
Name/Abbreviation/Description per WS. On a second run against the same
target: the complex feature is already present by GUID with matching
Name/Abbrev/Description -> `Skip(ALREADY_PRESENT_BY_GUID)` -> `execute_action`
is **never called again** -> the TypeRA-wiring code path never re-executes.
Even in the alternate branch (some WS field diverged -> `PlannedOverwrite
(write_mode="merge")`), `_execute_gold_reserved_merge`
(transfer.py:2303-2314+) fills only empty Name/Abbrev/Description WS slots via
`set_String` -- it has no TypeRA/reference-field logic at all.

Net effect: any complex feature transferred on a run where its struct-type
did not yet exist in the target will have `TypeRA` **permanently unset**,
not merely delayed to "the next run" -- because the standard idempotent-skip
path never revisits already-present GOLD items structurally. This is a
silent (logged-only) content-fidelity gap, distinct from a crash.

Non-blocking because: fails safe (no crash/corruption); only affects the
edge case where source complex features have `TypeRA` and the target has
never received a prior `FEATURE_STRUCT_TYPES` transfer; already flagged by
the B.2 report as a known ordering gap, just with an inaccurate "second run
fixes it" resolution claim.

**Recommendation:** merge is fine; open a follow-up item to either (1)
reorder `FEATURE_STRUCT_TYPES` before `INFLECTION_FEATURES` in
`_LEAF_DISPATCH_CATEGORIES`, or (2) add a post-pass TypeRA-repair sweep
(mirroring the existing `InflectableFeatsRC` tail-pass idiom), and correct
the "converges on second run" claim in the B.2 report to "does not converge
without an explicit repair pass."

## Overall

Requirements: 4/4 sub-parts land, tests pass, RED-first genuine, py_compile
clean. **PASS**, with CONCERN #1 tracked as a non-blocking follow-up (see
above) rather than a merge blocker.
