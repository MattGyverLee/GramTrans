# Merge check, batch 107-108-110-111-114-116 (cycle 1)

Worktree: D:/Github/_Projects/_LEX/GramTrans-review-batch-107-116, branch review/batch-107-116 from origin/main 3985150. Nothing pushed; PR branches untouched; no FLEx project opened.

## SHA check
All six origin/<branch> equal their local worktree HEAD: ce672ad, c61105f, 8394e4a, f0bd7bb, bb06edb, 68db9b1. No mismatch.

## Merges (--no-ff, required order)
- PR#121 fix-110: clean
- PR#122 fix-108: clean
- PR#120 fix-111: clean
- PR#125 fix-107: auto-merged (transfer.py)
- PR#124 fix-114: clean
- PR#123 fix-116: CONFLICT, src/gramtrans/Lib/preview.py (add/add, purely textual); categories.py and models.py auto-merged.

Resolution (keep both sides):
1. Hunk at ~L1982: kept #108's `render_struct_type_features_rs` in full, then the shared `return tuple(lines)`, two blank lines, then #116's block (sense-field constant + `render_sense_list_reference_decisions`), which ends with the shared tail `return tuple(lines)`.
2. Hunk at ~L2117, the render tuple: both lines kept, in this order:
   `+ tuple(render_struct_type_features_rs(plan))`
   `+ tuple(render_sense_list_reference_decisions(plan))`
Merge commit 10eef63; preview.py parses.

## Survival checks (merged tree)
- test_issue31_msa_slot_live.py: GT_ISSUE31_SANDBOX override (L54), `TARGET_NAME.startswith("GT-Sandbox-")` guard (L143) and test_move2_creates_no_slot_or_template_objects (L273) are all present.
- transfer.py execute(): `_ensure_struct_type_features_rs` (L938) sits directly after `_ensure_complex_feature_type_ra` (L934), separated only by a comment. #107's `_fill_created_pos_collections` is intact (call at L846 in the leaf loop; def at L3405).
- categories.py: touched by #110, #111 and #116 (+657/-68 net). I did not read these hunks line by line. All merged without textual conflict, no unit test regressed, and I saw no sign of a semantic interaction. Live verification should cover it.

## Tests (PYTHONPATH=<review worktree>/src)
- gramtrans.__file__ = ...GramTrans-review-batch-107-116\src\gramtrans\__init__.py
- flexicon.__file__ = D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py (not site-packages)
- tests/unit: 5368 passed, 80 skipped, 14 xfailed. This matches the expected totals exactly; no delta.
- fidelity_census.py: 118 passed.
