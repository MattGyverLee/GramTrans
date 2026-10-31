# impl-130: OVERWRITE `SlotsRC.Clear()+Add` erased MSA slot membership silently

- Branch: `fix-130-overwrite-slotsrc-guard` (worktree `D:/Github/_Projects/_LEX/GramTrans-fix-130`, based on origin/main 23e5356, merged with origin/main before push)
- PR: https://github.com/MattGyverLee/GramTrans/pull/150 (not merged). Commit message says `closes #130`.
- Verdict: [OK] Fixed. Unit +6, 0 regressions. Live proof on `GT-Sandbox-130` passes, including both mutation checks. A second, latent live defect was found and fixed (section 3).

## 1. Env check
`gramtrans=D:\Github\_Projects\_LEX\GramTrans-fix-130\src\gramtrans\__init__.py  flexicon=D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py`

## 2. Fix (`src/gramtrans/Lib/transfer.py`, local to `_execute_overwrite` and new helpers)
New `_overwrite_msa_slots`, called from the MSA branch:
1. Snapshot `SlotsRC` before any write. If the snapshot cannot be read, nothing is written.
2. Resolve every source slot. **Decision: if ANY slot is unresolved, do not Clear.** The target keeps its membership; we do not destroy membership to write a partial set. Each unresolved GUID gets `Skip(DEPENDENCY_UNRESOLVED)` + `DroppedItemRecord` (field `SlotsRC`, `item_guid` = slot) + one `AffixSlotLinkRecord(SLOT_MISSING)` + a Warning.
3. Otherwise a guarded `Clear`, then a guarded `Add` per slot (errors collected, loop continues).
4. One read-back via PR #120's `_slots_absent_on_readback`. On any absence or raise: Clear, re-Add the snapshot, read back the restore too, then append `AffixSlotLinkRecord(WRITE_FAILED, unwritten_slot_guids, detail)`. The detail says "pre-overwrite SlotsRC membership restored" or "RESTORE FAILED ...". A Skip per unwritten slot is added, matching #120.
5. A clean overwrite appends nothing.

Record plumbing: `AffixSlotLinkRecord` does fit (it is keyed by MSA, so no fallback to the drop model alone was needed; drop records are used for the unresolved slots). `_execute_overwrite` gained an optional `affix_slot_links=None` collector. `execute()` now creates `_affix_slot_links` before the OVERWRITE loop (it was created after it) and passes the same list; the `exec_ctx` attach is unchanged. Records therefore land in `RunReport.affix_slot_links`, so report precedence and the `_affix_slot_link_block` console rendering are the unchanged PR #120 code (no report.py edit). The MSA branch now returns its Skips (it returned None).

## 3. Latent live bug found by the live proof
`target.POS.GetAffixSlots` yields flexicon `AffixSlot` wrappers. `transfer._unwrap` only honours a `.concrete` attribute they lack, so the old code put the WRAPPER into `target_slots_by_guid` and `SlotsRC.Add(wrapper)` raises `TypeError: No method matches given arguments for ICollection`1.Add` on a live LCM. (I hit the same TypeError when seeding with `_unwrap`; I did not run the pre-fix `_execute_overwrite` live.) Offline fakes hide it. With the guard alone, every live OVERWRITE would have reported WRITE_FAILED, so I added `_lcm_slot` (reaches `_obj`, casts to `IMoInflAffixSlot`) and use it when building the slot index. Unit-tested.

## 4. Tests
Unit `tests/unit/test_issue130_overwrite_slotsrc_guard.py` (6 tests): no-op Add -> WRITE_FAILED + snapshot restored; raising Add -> WRITE_FAILED + restored + both Adds attempted; unresolved slot -> snapshot kept, SLOT_MISSING + drop + skip naming the GUID; clean overwrite -> no records; failed restore is reported ("RESTORE FAILED"); `_lcm_slot`.

| | Passed | Skipped | xfailed |
|---|---|---|---|
| Baseline | 5384 | 80 | 14 |
| After | 5390 | 80 | 14 |

## 5. Live verification (`FLEXLIBS_REQUIRE_LIVE=1`)
Test: `tests/integration/test_issue130_overwrite_slots_live.py`; `TARGET_NAME = "GT-Sandbox-130"` pinned and asserted before any write. Source `Ngoreme` opened read-only; `.fwdata` SHA-256 asserted unchanged (passes). Target restored from `Target 2026-07-06 0218.fwbackup`, then a Move 1 full transfer (as #31) lands the 128 MSAs.

**How OVERWRITE is driven.** The planner cannot emit an MSA OVERWRITE with differing membership: `preview._msa_fingerprint` includes the slot-GUID set, so a differing set plans an ADD. So the test calls the real `transfer._execute_overwrite` with a real `PlannedOverwrite(category=MSA)` on live source and target handles (precedent: test_issue55). The mutation wraps the target `SlotsRC` in a proxy over the real collection at the `_overwrite_msa_slots` call; the restore phase uses the real Add.

Run: `4 passed`. Output:
```
[LIVE] seeded target MSA a1d6feda membership=['0065adc6'] (source=31dbee39)
[LIVE] clean OVERWRITE read-back=['31dbee39'] records=[]
[LIVE] MUTATION noop: records=[('WRITE_FAILED', ('31dbee39',)), ('WRITE_FAILED', ('54fabd10',))]
[LIVE] MUTATION noop: details=['slot absent on read-back; pre-overwrite SlotsRC membership restored', (same)]
[LIVE] MUTATION noop: pre={'a1d6feda': ['0065adc6'], 'fd1617dd': ['bbeedab1']} post={same}
[LIVE] MUTATION raise: records=[('WRITE_FAILED', ('31dbee39',)), ('WRITE_FAILED', ('54fabd10',))]
[LIVE] MUTATION raise: details=['Add 31dbee39-...: RuntimeError: MUTATION: Add raises; pre-overwrite SlotsRC membership restored', ...]
[LIVE] MUTATION raise: pre={'a1d6feda': ['0065adc6'], 'fd1617dd': ['bbeedab1']} post={same}
```
Two MSAs per mutation run: both get WRITE_FAILED, so the pass continues after a failure. Regression: `test_issue31_msa_slot_live.py` with `GT_ISSUE31_SANDBOX=GT-Sandbox-130`: 8 passed. No other project was written.

## 6. Residual risks / follow-ups
- A `Clear` that silently does nothing (leaving extra stale slots) is not detected on the forward write; only missing slots are. The restore check does look for extras.
- The `[NOT LINKED]` console text is proven by PR #120's unit tests, not re-rendered here; this fix only feeds the same records.
- Partial-set policy (keep target when any source slot is unresolved) differs from the old "write what resolves"; flag if the product owner prefers partial writes.
- Other `_unwrap`-then-LCM-call sites may share the wrapper defect; not swept here.
