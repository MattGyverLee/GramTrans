# Cycle 1 — Programmer report (spurt 0): Phase 1 (Setup, T001-T003) + Phase 2 (Foundational, T004-T008)

**Worktree**: `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals` (branch `025-full-reversals`,
created off `main` @ `d58fd6b`)
**Commit**: `241dbeb` — "feat(025): Phase 1+2 scaffold -- reversals/config_views modules,
dataclasses, owner_kinds, REVERSAL_FIELD_MAP (T001-T008)"

Scope discipline honored: scaffolding + shared-infra only. No `plan_reversals`/`apply_reversals`
bodies, no config-view logic beyond imports. All new dataclasses are decision-shape only (no LCM
objects held except opaque `Any` handles mirroring 024's existing `ReferenceDecision.target_item`
pattern).

## T001 — `src/gramtrans/Lib/reversals.py` — DONE

File: `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\src\gramtrans\Lib\reversals.py`

Module docstring (Part A — reversal closure walk) + dual-import idiom
(`if __package__: from . import X else: import X`) of `owned`, `protection`, `report`,
`references`, `ws_mapping`, plus `ReferenceCardinality`/`ReferenceFieldSpec` from `models`. No
function bodies beyond `REVERSAL_FIELD_MAP` (T008, see below — the only content the task list
authorized in this file for this phase).

## T002 — `src/gramtrans/Lib/config_views.py` — DONE

File: `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\src\gramtrans\Lib\config_views.py`

Module docstring (Part B — `.fwdictconfig` file copy) + `import os, shutil, filecmp`. No logic.

## T003 — three scaffold test files — DONE

Files (all under `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\tests\unit\`):
- `test_reversal_walk.py`
- `test_reversal_category_resolve.py`
- `test_config_view_copy.py`

Each: module docstring pointing at its future US task IDs, `import pytest`, one
`@pytest.mark.skip(reason="scaffold — US1/US2/US3 tests land later")` placeholder test. Verified
collecting cleanly (see VERIFY section below) — `3 skipped in 0.28s`, zero errors.

## T004 — 024 dependency gate — PASS

Checked in the worktree (post branch-off `main`@`d58fd6b`, which contains the merged 024 feature):

- `src\gramtrans\Lib\references.py` — `def decide_reference(...)` at line 614, `def
  apply_reference(...)` at line 768. **Present.**
- `src\gramtrans\Lib\models.py` — `class ReferenceFieldSpec` at line 954 (frozen dataclass,
  `owner_class`/`field_name`/`cardinality`/`target_list_path`/`hierarchical`). **Present.**
- `src\gramtrans\Lib\owned.py` — `def walk_owned_children(src_owner, new_owner, ctx, tag,
  resolver_cache, dropped, ...)` at line 768 (the recursive owned-child walk). **Present.**
- `src\gramtrans\Lib\report.py` imports `DroppedItemRecord`, `FidelityStatus` from `models` (lines
  17-30) and uses them (e.g. `d.owner_kind` at report.py:221/313). `src\gramtrans\Lib\models.py` —
  `class FidelityStatus` at line 891, `class DroppedItemRecord` at line 911 (both present,
  confirmed by direct grep + read). **Present.**

Gate recorded **PASS** before any scaffolding was written. Confirmed by import smoke-test after
implementation (see VERIFY).

## T005 — `ReversalFieldSpec` / `ReversalDecision` dataclasses — DONE

File: `models.py`, inserted immediately after the existing `ReferenceDecisionRecord` block (was
line ~1047 pre-edit), before `OwnedCreateKind`.

Design note (flagging for QC/lex-lead review, since data-model.md does not literally name
`ReversalFieldSpec` — only `ReversalDecision` is implied by plan.md prose and tasks.md T005/T014's
description overlaps almost verbatim between the two names): I resolved the ambiguity by making
`ReversalFieldSpec` the reversal analogue of `ReferenceFieldSpec` **at the field-shape level**
(one row per reversal-entry field: `field_name`, `kind` ∈
`{reference_atomic, ref_seq_rewire, multi_unicode_value_copy, owned_recurse}`, and an optional
`reference_spec: ReferenceFieldSpec` linkage for the one true reference field, `PartOfSpeechRA`) —
mirroring how `REVERSAL_FIELD_MAP` (T008) itself is structured (one `ReferenceFieldSpec` row +
three descriptor rows). `ReversalDecision` is the actual **per-entry decision output** (mirrors
`ReferenceDecision`'s decision-only posture): `source_entry_guid`, `target_index_ref: Any` (existing
target index object or `None` = to-create, exactly mirroring
`ReferenceDecision.target_item`'s existing-vs-to-create posture — not a violation of "no LCM
objects" any more than `ReferenceDecision.target_item`/`source_item` already are), `pos_decision:
Optional[ReferenceDecision]`, `linked_sense_guids: tuple`, `dropped_sense_members: tuple`,
`reversal_form_alts: dict`, `sub_entry_decisions: tuple["ReversalDecision", ...]` (recursive
`SubentriesOS` tree). Both frozen dataclasses; no `__post_init__` validation added (kept to pure
scaffolding per this spurt's "stubs and dataclasses only" scope — US1/US2 implementation may add
validation later if the contracts call for it).

## T006 — `ConfigViewRecord` — DONE

File: `models.py`, immediately after the `ReversalDecision` block. Added `ConfigViewAction` enum
(`ADD`/`OVERWRITE`/`SKIP`) and frozen dataclass `ConfigViewRecord` with exactly the data-model.md
table's fields: `kind: str`, `filename: str`, `src_path: str`, `tgt_path: str`,
`action: ConfigViewAction`, `missing_refs: list = field(default_factory=list)`.

## T007 — owner_kind enumeration — DONE (documentation-only branch taken)

Searched `report.py`, `models.py`, `owned.py`, `references.py`, `categories.py`, `transfer.py` for
any owner_kind whitelist/enumeration/validation. Found none: `DroppedItemRecord.owner_kind` is a
free-form `str` whose only check (`__post_init__`) is non-empty (`if not self.owner_kind: raise
ValueError(...)`) — not a value whitelist. Every call site passes a literal string
(`"LexSense"`, `"LexEntry"`, `spec.owner_class`, `"MoForm"`, etc.) with no central registry.

**Branch taken: documentation-only.** Added a paragraph to `DroppedItemRecord`'s docstring in
`models.py` (immediately before the `owner_kind: str` field line) naming the three new 025
owner_kind values (`"ReversalIndexEntry"`, `"ReversalIndex"`, `"ConfigView"`) and explicitly noting
no whitelist enforcement point exists to extend. No code changes to `report.py` were needed or
made (nothing to extend there — did not fork the report channel; the channel remains the single
`DroppedItemRecord`/`RunReport.dropped_items` pipe).

## T008 — `REVERSAL_FIELD_MAP` — DONE

File: `reversals.py`. Module-level dict with exactly the four data-model.md rows:
- `"PartOfSpeechRA"` → `ReferenceFieldSpec(owner_class="ReversalIndexEntry",
  field_name="PartOfSpeechRA", cardinality=ReferenceCardinality.ATOMIC,
  target_list_path=lambda tgt_index: tgt_index.PartsOfSpeechOA, hierarchical=True)`
- `"SensesRS"` → descriptor dict (`kind="ref_seq_rewire"`, re-wire to copied senses + dropped-member
  reporting)
- `"ReversalForm"` → descriptor dict (`kind="multi_unicode_value_copy"`, non-destructive per-WS
  copy)
- `"SubentriesOS"` → descriptor dict (`kind="owned_recurse"`, owned-walk pattern not the resolver)

This is the module-level structure the census (T033) will later verify for completeness against
live MCP-confirmed `IReversalIndexEntry` members.

## VERIFY

Ran from the worktree (`D:\Github\_Projects\_LEX\GramTrans-025-full-reversals`):

```
python -m pytest tests/unit/test_reversal_walk.py tests/unit/test_reversal_category_resolve.py tests/unit/test_config_view_copy.py -q
```
→ `sss` / `3 skipped in 0.28s` — all three collect and skip cleanly, zero errors.

Import smoke-test (`python -c "..."` with `src` on `sys.path`):
```
from gramtrans.Lib import models
from gramtrans.Lib import reversals
from gramtrans.Lib import config_views
```
→ succeeded; printed `models.ReversalFieldSpec`, `models.ReversalDecision`,
`models.ConfigViewRecord`, `models.ConfigViewAction`, `reversals.REVERSAL_FIELD_MAP.keys() ==
['PartOfSpeechRA', 'SensesRS', 'ReversalForm', 'SubentriesOS']`, and `config_views.os/.shutil/
.filecmp` module refs. No import errors. Did **not** run the full suite (per instructions).

## Files touched (all absolute paths, all in the worktree except this report)

- `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\src\gramtrans\Lib\reversals.py` (new)
- `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\src\gramtrans\Lib\config_views.py` (new)
- `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\src\gramtrans\Lib\models.py` (modified)
- `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\tests\unit\test_reversal_walk.py` (new)
- `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\tests\unit\test_reversal_category_resolve.py` (new)
- `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\tests\unit\test_config_view_copy.py` (new)
- `D:\Github\_Projects\_LEX\GramTrans\specs\025-full-reversals\reviews\cycle1-programmer.md` (this
  report, main repo checkout, not committed by me per instructions)

No `specs/` files or `tasks.md` were touched, per instructions.

## Open item for lex-lead / QC

Flag the T005 `ReversalFieldSpec` vs `ReversalDecision` naming/shape ambiguity noted above for
review — data-model.md doesn't literally define `ReversalFieldSpec`; I made a reasoned design
choice (field-shape spec vs. per-entry decision output, mirroring the 024
`ReferenceFieldSpec`/`ReferenceDecision` split) and documented it in both the dataclass docstrings
and here. If US1/US2 authors want a different shape once `plan_reversals`/`apply_reversals` logic
is written, these frozen dataclasses can be adjusted before any caller depends on them (nothing
consumes them yet).
