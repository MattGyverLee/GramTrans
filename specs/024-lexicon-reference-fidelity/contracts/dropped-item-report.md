# Contract: Dropped-Item Report Channel (`Lib/report.py`, `Lib/models.py`)

Covers FR-010, FR-013, and the "No silent skips" governance gate. This is the backstop that
makes the whole fidelity guarantee trustworthy.

## Collection

- A per-run `dropped: list[DroppedItemRecord]` collector is threaded through the closure
  walk (entry → sense → sub-sense → allomorph → example) alongside the existing plan/context.
- The resolver and owned-walk append to it; no other code path may swallow a non-reproduced
  item.

## Surfacing

- `report.RunReport` gains:
  - `dropped_items: list[DroppedItemRecord]`
  - per-object `fidelity: FidelityStatus` (FULL / PARTIAL with count)
- `render_text_summary(report)` MUST include a "Dropped references / owned items" section
  listing each record as: `<owner_label> [<owner_kind> <owner_guid[:8]>] . <field_name> →
  "<item_name>" (<item_guid[:8]>) — <reason>`.
- Records appear in **Preview** (so the linguist sees them before writing) and in the
  **post-run statistics panel** (Move mode).

## Invariants

- **SC-003**: count of non-reproduced items that are *absent* from `dropped_items` is zero.
- **SC-006**: for a transfer with no customized lists, `dropped_items` is empty and all other
  report output is byte-identical to today (regression guard).
- A record is emitted exactly once per (owner, field, item) triple (no duplicates on re-walk).

## Snapshot compatibility

- `to_snapshot_json` / `_to_snapshot_json` extend additively (new keys) so older snapshots
  still load; absence of `dropped_items` reads as empty.
