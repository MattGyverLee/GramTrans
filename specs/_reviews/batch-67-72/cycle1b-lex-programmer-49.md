# Cycle 1b - lex-programmer - #49 (e0375ff, not pushed)

Worktree GramTrans-batch-67-72. PYTHONPATH=<worktree>/src; flexicon resolves to D:/Github/_Projects/_LEX/flexicon.

## Files
- src/gramtrans/Lib/preview.py ~1311-1365 (planner visibility)
- src/gramtrans/Lib/categories.py affix_templates_execute_action (~12598-12690)
- src/gramtrans/Lib/transfer.py: `_verify_candidates` collection (~338, ~703), reconcile call after `_ensure_owner_feat_strucs` (~770), `_lookup_target_guid` / `reconcile_added_actions` (before `planned_destination_for`)
- tests: new tests/unit/test_issue49_reconciliation.py (6), tests/integration/test_issue49_default_set_live.py; adjusted test_phase3b_leaf_dispatch.py (fake FeatureGetAll) and test_preview_no_writes.py (now expects the explicit POS-no-picks skip).

## (1) Planner: visible-drop decision, NOT un-gating
Evidence the gate is deliberate: preview.py ~1129 "SUPERSEDE DECISION (2026-07-06)": the verb-vertical path double-transferred and collided on identical GUIDs; leaf-dispatch (AFFIXES/STEMS) is the single path (commit 88b81554). Re-enabling is feature-sized and reintroduces the collision. So:
- every ON category outside the dispatch set (ENTRY/SENSE/MSA/ALLOMORPH) gets a Skip "not dispatched: ... select AFFIXES and/or STEMS";
- missing handler (old `except KeyError: continue`) and enumeration exceptions (old `pieces = []`) now emit Skips;
- POS with empty picks (and no GRAM_CATEGORIES) emits a Skip. POS with picks already planned correctly (21 actions live).
**Lexicon transfer via the default category set remains unimplemented.** lex-lead should decide whether to split a new issue (map ENTRY/SENSE/MSA/ALLOMORPH to AFFIXES+STEMS in build_run_plan).

## (2) Template/slot outcomes
Slots already returned skipped outcomes (#68). Templates now return skipped for source-not-found and owner-POS-unresolved (recorded=True); the 17.1 tail still runs.

## (3) Reconciliation hook
`reconcile_added_actions(target, [(action, expected_guid)])`: for each action the handler reported written (None or created object; expected GUID = resolved planned destination else source GUID), looks up the GUID via the LCM ObjectRepository; a miss becomes LeafExecutionFailure("UnverifiedWrite") plus `not_added`, so `added` and `leaf_failed` are truthful. Exempt: CUSTOM_FIELDS; targets with no GUID lookup (offline fakes) are unverifiable and skipped, not failed.

## Live (FLEXLIBS_REQUIRE_LIVE=1, Ngoreme FLEx -> restored Target, all 26 POS picks, default set)
.fwdata sha256 before 13c5a96f...ad74c7f, after f3cb256d...a859e8 (changed). Reported added vs new objects in Target by GUID:
- affix_templates 13 / 13; slots 19 / 19; pos 21 / 21 (5 pre-existing, 26 after); ph_environment 9 / 9
- entry, sense, msa, allomorph: 0 reported, 0 landed, each with a "not dispatched" skip
- leaf_failed 0; every planned added object verified present.
Target restored afterwards. Bounded: lexicon not run since not dispatched.

## Suites
Unit: 5051 passed / 81 skipped / 14 xfailed (prior 5039; +6 new, +6 from other agents' commits). 038 audit tests: 139 passed, 2 failed; the same 2 fail without my changes (test_every_link_in_the_chain_declares_whether_it_is_reproducible, test_every_report_field_is_classified) - pre-existing.

## Note
Plan shows 9 gram_categories actions alongside 21 POS (closure); Target gained only 21 PartOfSpeech in total, so reported POS added matches landed objects.

SHA: e0375ff (fix-batch-67-72).
