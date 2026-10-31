# QC cycle 2: #130 (PR #150) and #136 (PR #148)

> Saved by the main session. The lex-qc agent had no Write or Bash tool and returned this as its final message.
> It read the main worktree at local main 7b91f71 instead of ee365b3. The main session confirmed that 7b91f71 contains both a9a2d19 (#130) and 17a2128 (#136), so the reviewed code is correct; cited line numbers may drift slightly from ee365b3.
> FLExToolsMCP was not callable, so flexicon was checked with grep only.

**Scores:** #130 = 82/100, #136 = 88/100.
**Gates:** live evidence is present for both. No sweep-pattern section was applicable to check.

## Q1: unwrap convention
- **How flexicon wraps:**
  - flexicon `LCMObjectWrapper` (Shared/wrapper_base.py:148-149) holds `_obj` (the base interface) and `_concrete` (a concrete cast). It has no public `.concrete`.
  - Only AffixTemplate (affix_template.py:506), CompoundRule and Allomorph define `.concrete`.
  - `AffixSlot` (affix_Slot.py:63) does not. `POSOperations.GetAffixSlots` returns AffixSlot wrappers (POSOperations.py:1106).
- **The gap:** `transfer._unwrap` (transfer.py:2225) falls through when `.concrete` is missing, so the wrapper is returned unchanged.
- **P1:** `_lcm_slot` (transfer.py:3947-3963) fixes only one call site. Fix the root cause once instead:
  - either `_unwrap` falls back to `_concrete`, then `_obj`,
  - or flexicon adds a public `concrete` property to `LCMObjectWrapper`.
- `_lcm_slot` also prefers `_obj` over `_concrete`. `_cast_lcm` makes this harmless, but `_concrete` is the intended field.
- `PythonicWrapper.unwrap()` belongs to a different class and does not apply.

## Q2: `_unwrap` sweep
There are 4 `_unwrap` definitions (transfer, preview, conflict, merge_preview). AffixSlot is the only wrapper class confirmed to lack `.concrete`; not every flexicon wrapper was audited.

| File:line | Use | Confidence |
|---|---|---|
| transfer.py:2202-2206 `_find_target_slot_by_guid` | Returns the wrapper; the result goes to `apply_residue` at 4282 | MED |
| transfer.py:4266-4268 | Scan fallback `_guid_str(_unwrap(s))` gives `ICmObject(wrapper)`; `tgt_slot` then goes to `apply_residue` | MED |
| transfer.py:2229-2231 `_slot_name` (callers 1292, preview.py:3371) | `IMoInflAffixSlot(wrapper)` | LOW-MED |
| preview.py:4244, 4276-4278 | `_guid_str(_unwrap(s))` and `IMoInflAffixSlot(_unwrap(slot))` | LOW-MED |
| transfer.py:1300 | Consumer of `_find_target_slot_by_guid` | LOW |
| merge_preview.py:1635 | `_unwrap(sl)` read | LOW |

Only `.Add(wrapper)` was proven to fail live. Whether a pythonnet interface cast of a wrapper raises is unverified, so these are candidates.

## Q3: reachability of #130
- **Confirmed:** `_match_msas_by_fingerprint` emits OVERWRITE only when the fingerprint matches (preview.py:3596-3609, 4022-4035). `_msa_fingerprint` (3899-3909) includes the slot GUIDs as a frozenset, so a differing slot set plans an ADD instead.
- **In production:** the guarded Clear+Add therefore always re-adds an identical set. It is reachable on every fingerprint-matched MSA overwrite, but it is a no-op rewrite; it matters only if Add or Clear fails.
- **P2:** skip the Clear+Add when the target's SlotsRC GUID set already equals the source's.
- **SLOT_MISSING:** this branch is practically reachable only when a slot sits on a different POS than the MSA's POS.
- **What the live test proves:** it calls `_execute_overwrite` directly with seeded, differing membership plus a mutation proxy, which is a state the planner cannot produce.
  - It does prove the live `_lcm_slot` unwrap and `Add`, and the snapshot/restore mechanics.
  - It does not prove a naturally occurring failure.

## Q4: `_affix_slot_links` earlier creation
**Safe.**
- It is the same list object attached to `exec_ctx` (transfer.py:739).
- `_record_affix_slot_link` (categories.py:11767) appends to it via getattr.
- `_slots_absent_on_readback` (categories.py:11590) is a pure read-back helper.
- The report concatenates plan links with the extras (report.py:443-444). Ordering is OVERWRITE records first, then 17.1 records.

**P2:** there is no dedupe by `msa_guid`. That is harmless today, because the ADD and OVERWRITE MSA sets are disjoint.

## Q5: #136
- **No double application:**
  - The entry points act only on `src_child`'s own fields.
  - The top-level sense loop (categories.py:9226-9284) and the sub-senses are disjoint.
  - `walk_owned_children` recurses through `SensesOS` once per child.
  - `_report_dropped_sense_scope_gaps` uses `_append_dropped_once` (categories.py:8637), so there are no duplicate records.
- **Preview with `new_sense=None` is safe:**
  - `_resolve_sense_thesaurus_items` returns early on `None` (categories.py:8937).
  - `_resolve_sense_appendixes` guards it (8833).
  - Preview returns the records via `records.extend` (owned.py:985-999).
- **P2:** owned.py:509-517 and 991-997 swallow an ImportError on the pictures import and skip silently. The picture pass is lost with only a `pragma: no cover`.
- **P2:** duplicate-drop behaviour for appendix/thesaurus drops across repeated plan runs depends on resolver internals that were not verified. The implementer notes #146 for pictures.

## Findings
- **P0:** none.
- **P1:**
  - Fix the `_unwrap` root cause (Q1).
  - impl-130 admits the `_unwrap` sweep was not done; the table above is that sweep.
- **P2:**
  - Skip the no-op Clear+Add when the slot sets are equal (Q3).
  - The partial-set policy (keep the target if any source slot is unresolved) changes behaviour from "write what resolves". The domain review ruled it PASS.
  - A silent no-op `Clear` is not detected on the forward write (impl-130 §6).
