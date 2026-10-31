# Cycle 2 programmer report: #108 (PR #122)

Branch fix-108-featuresrs-repair. New HEAD **6acb166** (fix commit 1e84e4a + merge of origin/main 7c721b9, which includes #110 and #111; merged cleanly, no conflicts). Pushed. PR #122 body updated via REST API (`gh pr edit` failed on token scopes).

## Diff summary
- categories.py (`_classify_struct_type_features_rs`, `_rewrite_features_rs`, `_run_struct_type_features_rs_pass`, banner):
  - New outcome `FEATURES_RS_REORDERED`. REPAIR now means "a resolvable member is missing", and `desired` is the list of members to insert.
  - `_rewrite_features_rs` is insert-only: it inserts after the nearest present source predecessor, else before the nearest successor, else at 0. It never calls RemoveAt and records `inserted` as it goes.
  - Reordered gives a Skip(NEEDS_MANUAL, "reordered in target, left as-is") in Move. The classifier is shared, so Preview rows match.
  - Each struct-type's classify, write, drops and target-only skips sit in their own try. Failures give a Skip(DEPENDENCY_UNRESOLVED) saying "inserted before the failure: [..]/nothing". Drops, other skips and the writes counter survive.
- transfer.py: unchanged. The outer swallow was already last-resort, and per-type isolation now sits inside the pass.
- preview.py `render_struct_type_features_rs`: Repair rows print "insert [...]"; Wire at create shows source order; new row "SKIP (reordered in target, left as-is)". No misleading target sequence is printed.
- Live test: worktree-agnostic provenance assert (`gramtrans.__file__` under `parents[2]/src`). Added non-empty owner_label/item_name asserts on all FeaturesRS drops. Run 4 is now reordered -> 0 writes, 1 Skip row, 1 Skip, order left swapped.
- Unit tests: 3 existing tests updated and 10 new ones (class `TestInsertOnly`):
  - missing inserted without moving existing members
  - missing inserted beside reordered shared members
  - never RemoveAt
  - reordered -> Skip with zero writes
  - Preview reordered row, Preview Repair row lists inserts only
  - Insert fails mid-repair: nothing lost, detail accurate
  - Insert fails on first insert
  - one bad type does not abort others or lose drops
  - classifier raising on one type does not abort others

## Tests
- Unit, after merging main: **5340 passed, 80 skipped, 14 xfailed** (before the merge: 5327, i.e. 5317 + 10). The census tests are included in the full run.
- flexicon resolves to D:\Github\_Projects\_LEX\flexicon (not site-packages). gramtrans resolves to the fix-108 worktree.
- Live, `FLEXLIBS_REQUIRE_LIVE=1`, run sequentially:
  - `test_issue108_features_rs_repair_live`: 1 passed. Run 2 had 6 repairs, run 3 had 0, run 4 had 0 repairs and kept the swapped order.
  - `test_issue37_complex_type_ra_live`: 3 passed.
  - `test_issue110_type_ra_single_writer_live`: 2 passed. Source was Mbugwe LizzieHC practice 2026, target GT-Sandbox-110. It reported 2 wire rows, 2 writes, 0 on re-run.
- Mbugwe Lizzie .fwdata SHA-256 before and after: `db195e04e8963ab4ab2d849f3ff955932fbe9ed52c90fb568da033ce60a7ff0c` (identical).
- Mutation check: I changed the classifier so reordered returns REPAIR. 3 new/updated tests failed:
  - test_complete_but_reordered_is_reordered_not_repair
  - test_complete_but_reordered_is_skip_with_zero_writes
  - test_preview_row_for_reordered_matches_move
  I then restored the code (confirmed by a clean git status).

## Item 6 finding (QC-108 Q2)
PHONOLOGICAL_FEATURES dispatches BEFORE PHON_FEAT_TYPES: transfer.py:602-607 (`_LEAF_DISPATCH_CATEGORIES`, with a comment stating the ordering requirement). So at create the phon defns have landed when the type is wired. Preview's "Wire at create" is consistent with Move, and no parity gap was found. I did not change anything. I did not check the equivalent ms pair, INFLECTION_FEATURES before FEATURE_STRUCT_TYPES, which the task did not ask about.
