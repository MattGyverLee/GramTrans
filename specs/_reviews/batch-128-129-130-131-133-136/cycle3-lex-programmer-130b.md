# cycle3 programmer 130b

PR #156 (Follow-up to #130 / PR #150), branch fix-130-unwrap-root, head 659cc83. Worktree D:/Github/_Projects/_LEX/GramTrans-fix-130b. Not merged; no issues filed.

## Changes
- New Lib/lcm_unwrap.py::unwrap (.concrete -> _concrete -> _obj -> self). transfer/preview/conflict/merge_preview `_unwrap` delegate. `_lcm_slot` now relies on it (_concrete ahead of _obj).
- P2: `_overwrite_msa_slots` skips Clear+Add when resolved source GUID set == target snapshot set (order-insensitive).

## Cast question (answered live, Ngoreme read-only; FLExToolsMCP not used)
pythonnet `ICmObject(wrapper)` and `IMoInflAffixSlot(wrapper)` RAISE `TypeError: object does not implement ...`. Not silent. Wrapper has `_concrete` and `_obj` (both IMoInflAffixSlot), no `.concrete`.

## Sweep verdicts (old _unwrap vs new, live + unit)
1. transfer _find_target_slot_by_guid: BROKEN before (TypeError); fixed.
2. transfer scan fallback (~4318): BROKEN before; fixed.
3. _slot_name (transfer and preview): BROKEN before; fixed.
4. preview _target_has_slot_guid (~4246): BROKEN before; fixed.
5. transfer ~1352 consumer: inherited row 1; fixed.
6. merge_preview ~1635: NOT broken (iterates raw LCM refs; _obj_guid on wrapper already worked); unchanged.
Caveat: QC's "MED/LOW" rows were all real except merge_preview. Pre-fix failures were loud TypeErrors, so they were reachable only if callers did not swallow them.

## Unit
Full suite 5434 passed / 80 skipped / 14 xfailed vs ~5411/80/14 baseline. New file tests/unit/test_issue130b_unwrap_root.py adds 12 tests (strict-cast stub raising TypeError on wrappers); the remainder of the delta is baseline drift in the approximate figure. Skips and xfails unchanged.

## Live (FLEXLIBS_REQUIRE_LIVE=1, GT-Sandbox-130 only, restored from Target 2026-07-06 0218.fwbackup by each module)
- test_issue130_overwrite_slots_live: 4 passed.
- test_issue31_msa_slot_live (GT_ISSUE31_SANDBOX=GT-Sandbox-130): 8 passed.
- test_038_affix_slot_links_live: 10 passed; offline snapshot, no writes.
All three ran against this branch. A pythonnet "access violation" dump appears at interpreter exit after the pass line (shutdown noise, exit after results). Nothing owed on Target. Target, Esperanto and Mbugwe were never written.

## Follow-up candidates (not filed)
- flexicon: public `.concrete` property on LCMObjectWrapper (removes the need for GramTrans fallbacks).
- The live 130 test still drives `_execute_overwrite` with seeded differing sets; equal-set no-op is proven only by unit test, not live.
