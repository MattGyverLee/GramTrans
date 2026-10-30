# Cycle 3 programmer report -- issue #87

Commit f5bff14 (single commit on d9f55c9, branch fix-87-residue-idempotent, UNPUSHED). Target sha256 after final restore: 13c5a96fba560ae86b29893798f5bcf1cd0d631d19d36f50bef9a1ecfad74c7f (= baseline).

## Root cause (lead's hypothesis confirmed, plus one more site)
- Run-2 POS writes come from the UPDATE executor, not a PlannedAction: transfer.py `_execute_update_semantic` L3372-3418 (src vs tgt GetSyncableProperties; tgt Description holds our own `[GT-Tag]` line -> UPDATE every run -> source write replaces the line -> apply_residue appends a new line with `snap=` nesting the old tag).
- The PLANNER also created those overwrites (why plan.actions==0 still had work): categories.py `_compare_multistring_per_ws` (L527, used by `_plan_gold_reserved_edit` L1016) saw the tag as a "conflict".

## Comparison sites (all target-side stripped)
Fixed: transfer.py L3372 (disposition+apply+snapshot), categories.py L527 planner, conflict.py `collect_overwrite_conflicts` L400, merge_preview.py `_fetch_props` (target side; diff engine), transfer.py `tgt_pre_props` reads in OVERWRITE executors (entry x2, POS, template, sense, allomorph, env). `with_snapshot` itself strips, so no snap nests tags.
Safe: references.py:1003 (possibility lists, stamps only created ancestors); owned.py (stamps only new children); `compute_disposition` itself (callers now pass clean props).
Helpers (residue.py): `strip_residue_text/props`, `residue_lines`, `restore_residue_history`; line-start matching also in `apply_carrier_b` (QC P2 L283).

## Tag-history decision
Genuine UPDATE keeps earlier tag lines (captured before the source write, re-appended before the new line). OVERWRITE mode still replaces Description wholesale (history lost), unchanged behaviour. `snap=` baseline now holds the stripped props (a change from before: it no longer nests earlier tags). Known edge: a source Description ending in a lone trailing newline compares unequal to the stripped target (trailing newline trimmed after strip).

## P1 trace
(a) conflict.py L464 `ImportResidueTag.parse` uses `rfind` of the marker, so the LAST line wins; history is appended, newest is last (unit test `test_history_survives_update_and_last_line_parses`). (b) Every non-snap stamp site (categories/transfer/owned/references/reversals/wordforms `apply_*` on `new_*`) is on a freshly created object; snap-bearing stamps are only on matched objects (transfer.py L2257, 3418, 3601...); the two sets are disjoint, and create-then-update in one run yields a create stamp (baseline absent) -- correct. Production consumers of `snap=`: none (decode_snapshot used only by tests; report.py baseline is unwired); `load_prior_log` has no production caller.

## QC P2 texts.py
`_apply_paragraphs` now returns `(already, created_count)`; stamp when `_created or created>0`. Tests: matched empty text gains paragraphs -> stamped once, rerun none; all creates fail -> not stamped.

## Regression evidence
New live test `tests/integration/test_issue87_residue_idempotent_live.py` (POS+GRAM_CATEGORIES+4 Texts, "Mbugwe LizzieHC practice", restore-first). Run on main src (d9f55c9; test copied into the main tree because the root conftest forces its own src first -- a worktree pytest run silently tests the worktree): FAIL, 15 objects re-stamped (11 PartOfSpeech, 4 Text). On fix: PASS. Excluded by explicit list: new MoInflAffixSlot (10) / MoInflAffixTemplate (7) / FsFeatStruc (47), POS owner links, MoInflAffMsa/FsFeatStruc changes.
"18-line diff" claim: WITHDRAWN. The issue45 untitled-text test gives a 0-line run1/run2 diff on main (re-verified), so I cannot reproduce it; it was likely 3 Texts x 6 diff lines from a different state. Not claimed in the commit.

## Tests
Unit: 5083 passed, 0 failed (81 skipped, 14 xfailed). Integration (FLEXLIBS_REQUIRE_LIVE=1, -rf): 30 failed / 768 passed; failing IDs identical to the main baseline's 30 (comm: 0 new failures, 0 fixed). New passes: the new live test.
Not live-verified: the genuine-UPDATE history-keeping path (unit-tested only).

## Notes
Commit trailer is `Co-Authored-By: Claude Sonnet 5.5` (one, unindented) -- my session attribution rule; you asked for "Opus 5.5", amend if you want that. Draft issue: cycle3-draft-issue-slot-template-idempotency.md (this folder).
