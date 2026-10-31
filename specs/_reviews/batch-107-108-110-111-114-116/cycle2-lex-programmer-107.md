# Cycle 2 programmer report -- #107 (PR #125)
HEAD: 2ea7b9a (fix commit e13bd8c + merge of origin/main 7c721b9, clean, no conflicts). Pushed.

## Diff
- src/gramtrans/Lib/transfer.py: new `_record_unfilled_pos_collections` (before `_fill_created_pos_collections`); called from the leaf-loop exception path (~817) and the source-POS-not-found path inside `_fill_created_pos_collections`. One DroppedItemRecord per POS_OWNED_COLLECTION_FIELDS entry, owner_label = action.summary (fallback guid), reason carries the exception. Warning kept as well.
- transfer.py `_check_add_only` + new `_same_lcm_member` (GUID compare, then is/==).
- tests/unit/test_issue107_created_pos_collections.py: +3 tests (unfound source drops, failing fill drops via execute -> RunReport, add-only proxy tolerance).
- test_issue31_msa_slot_live.py docstring rewritten (docstring only); test_issue87 live: GT_ISSUE87_TARGET must be "Target" (unset default) or start "GT-Sandbox-".
- PR #125 body updated (Principle III gap, "Principle III issue: TBD").

## Item 4
Benign false positive in the check itself: `after[index] is not original` (old transfer.py ~3061). pythonnet yields fresh proxy wrappers per iteration, so `is` fails for the same LCM object at index 0 (added=0 already_present=N confirms nothing moved). Fixed by GUID comparison; reorder/removal still detected (unit-tested).

## Validation
- Unit: 5323 passed, 80 skipped, 14 xfailed. flexicon -> D:\...\flexicon. (No separate census script found; debug/fullsweep/census.py not run.)
- Mutation: neutralised `_record_unfilled_pos_collections` -> 2 new tests fail; restored -> pass.
- Live (FLEXLIBS_REQUIRE_LIVE=1): #87 with GT_ISSUE87_TARGET=GT-Sandbox-107 (source Mbugwe LizzieHC practice): 1 passed (run1 17 actions, run2 0). #31 against GT-Sandbox-111 (source Ngoreme): 8 passed via scratch copy pre-merge and via GT_ISSUE31_SANDBOX after merge (the post-merge run printed an interpreter-shutdown traceback line alongside "8 passed"; not investigated).
- SHA-256 before==after: Ngoreme 6d35c957...be472d; Mbugwe LizzieHC practice 3fb29a29...5436d.
