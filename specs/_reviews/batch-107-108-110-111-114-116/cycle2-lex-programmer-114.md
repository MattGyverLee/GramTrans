# Cycle 2 programmer report, #114 (PR #124)

New HEAD: 236b44f (pushed to origin/fix-114-entryref-hide-summary; Step 0 merge of origin/main = fda24a1, merge not rebase).

## Diff summary
- src/gramtrans/Lib/categories.py `_merge_entryref_value_fields` (~11949-12020): new kwarg `existing=False`; with `existing=True` a source HideMinorEntry 0 is treated as unset (`unset = existing and src_hide == 0`), so only source 1 may overwrite target 0; target 1 / source 0 stays 1, no drop. Create path unchanged (source 0 stays data). Docstring updated. INV-1 caller (~12172) passes `existing=True`; create caller unchanged.
- QC P2 (same function): the `int(tgt_hide)` read and `_merge_delta` call are inside a try catching TypeError/ValueError and recording a `HideMinorEntry` drop; the read-back `int(back)` is now inside the existing try, so a non-numeric value is a recorded drop, never an exception.
- tests/unit/test_issue114_entryref_value_fields.py (~301-350): old source-zero-updates test REWRITTEN to `..._source_zero_is_unset_target_one_stays` (target stays 1, hide_sets==0); added source-1-overwrites-target-0 and non-numeric-is-a-drop tests.
- tests/integration/test_issue114_entryref_value_fields_live.py (~357-361): REF_DEFAULT (target 1 / source 0, already seeded by the diverge step) now expects HideMinorEntry 1 and no drop. No fixture change needed.

## Validation
- Unit: 5311 passed, 80 skipped, 14 xfailed. Census (tests/verification/fidelity_census.py, pytest-driven): 118 passed. flexicon resolves to D:\Github\_Projects\_LEX\flexicon.
- Live (FLEXLIBS_REQUIRE_LIVE=1): 2 passed. Writes only GT-Src-114 and GT-Sandbox-114.
- Mutation: with the policy line changed to `unset = False and ...`, the new unit test failed (1 failed, 16 passed); restored, 17 passed. (A `git checkout` used to revert the mutation also reverted my uncommitted edit; I restored it from a backup copy and re-ran, so the committed code is the intended version.)
- Korean-GIAL .fwdata SHA-256 before and after: 9ea5a4a49711c0fdb893941f21d6ecd4b2a79f3fb847f61d054e77bde594775c (unchanged); no lock files in its folder.

## Item 3 (actions=1)
Re-run A's one action is the SPARE_1 stem entry (STEMS action, forces the STEMS tail). Re-run B is also 1 (SPARE_2; SPARE_1 already exists). The test asserts `actions >= 1` and that the spare entry exists in the target, so it checks what the PR claims. verification-114's "0" was a misreading; the pure re-run (move#2) is the 0-action case. No test or wording fix needed in the code; PR text names the spare mechanism via the limitation bullet.

## PR #124 body
Updated via REST (`gh pr edit` fails on missing read:org scope; used `gh api -X PATCH`). Residual risks now name: (a) unpreviewed INV-1 merge, Principle III gap, follow-up "TBD, to be filed before merge"; (b) >=1 STEMS action limitation, "TBD"; (c) HideMinorEntry 0-as-unset policy. Both TBD placeholders still need real issue numbers.
