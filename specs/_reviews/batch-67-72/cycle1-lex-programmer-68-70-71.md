# Cycle 1 - lex-programmer - #68 / #70 / #71

Worktree D:/Github/_Projects/_LEX/GramTrans-batch-67-72, branch fix-batch-67-72. Commit 09f9619 (not pushed).
Note: `import gramtrans` from the worktree resolved to the MAIN checkout; I ran everything with PYTHONPATH=<worktree>/src. flexicon resolves to D:/Github/_Projects/_LEX/flexicon.

## Files changed
- src/gramtrans/Lib/models.py ~3886-3945 (ActionOutcome), RunReport.outcome_counted field (~4560)
- src/gramtrans/Lib/transfer.py ~315-335, ~655-700 (dispatch loop), ~835 (log text), report call
- src/gramtrans/Lib/report.py `_build_from_plan` (`not_added`), `disposition_totals`
- src/gramtrans/Lib/categories.py: ~35 decline sites; `_create_entryref_container` ~11530; `_run_entryref_create_pass` ~11660; `_create_guid_failure` ~13320; variant/complex-form/semantic-domain create sites ~3776/3951/4109
- tests: new tests/unit/test_issue68_action_outcomes.py; additions to test_027_entryref_reproduction.py and test_issue48_create_guid_errors.py; 7 legacy "returns None" assertions updated; tests/integration/test_issue48_create_guid_live.py

## Outcome contract
`models.ActionOutcome(status: str, reason: str, skip_reason: SkipReason|None, recorded: bool)`, frozen. Constants OUTCOME_ADDED/SKIPPED/FAILED. Constructors `.added()`, `.skipped(reason, skip_reason=DEPENDENCY_UNRESOLVED, recorded=False)`, `.failed(reason)`. Skipped/failed require a reason.
- A skipped/failed return is honoured. Any other return (None, created object) counts as added.
- skipped: the engine appends a Skip, unless `recorded=True` (the handler already put one on `_exec_skips`, e.g. `_report_owner_pos_unresolved`).
- failed: a `LeafExecutionFailure` with exception_type "ActionFailed".
- Raised exceptions are also excluded from `added` now.
- `RunReport.build_from_plan(..., not_added=[(category, guid)])` subtracts them but keeps the category bucket. `RunReport.outcome_counted=True` makes `disposition_totals` use add_created = written + failed, so failures are not subtracted twice.

## Decline sites converted
gram_categories (source missing, owner POS), inflection_features (4), inflection_classes (2), feature_struct_types (3; 2 failed), phon_feat_types (3; 2 failed), pos_inflectable_feats (3), stem_names (2), exception_features (3), variant_types, complex_form_types, semantic_domains, affixes, slots (2), phonological_features, phonemes (2), natural_classes, ph_environment, strata, phonological_rules.
Deliberately left as None: gram_categories "already present" (the verb-vertical or prior run created it); custom_fields stub; affix_templates tail.

## texts.py
`_added` (texts.py ~777) counts real creates in `_resolve_or_create_text_ex` and is only logged. It does not feed `per_category`, so it is compatible. If texts ever need per-category reporting, it should return an `ActionOutcome`-style result. Not edited.

## Tests
Baseline 5023 passed / 81 skipped / 14 xfailed. After: 5039 passed / 81 skipped / 14 xfailed (+16, 0 failures).
Covered: a missing owner POS is skipped, never added (real stem_names handler); engine-level skipped/failed/raised/recorded cases; the entryref failing factory gives a DroppedItemRecord with exception type and text.

## #71 complex-feature decision
Feasible. The live test now creates an IFsComplexFeature on the restored Target in its setup and collides with its GUID. The backup is untouched. Written, NOT run live. It also asserts the message is a single line.

## Faulthandler
Known pythonnet/CLR artifact: first-chance access violation inside flexicon `FLExInitialize` (FLExInit.py:64), reproducible with a bare `python -c` and no GramTrans code (specs/034 probe-results, T087). Tests pass and exit is 0. No GramTrans cause, so no fix.

## Not done
Live verification (per instructions). #68 live regression is still owed.
Unrelated modified file tests/unit/test_texts_untitled_collision.py (another agent) was left uncommitted.
