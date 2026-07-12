# Contract: Referenced-Possibility Resolver (`Lib/references.py`)

Covers FR-001..005, FR-012. Split into a pure decision function (Preview) and an apply
function (Move), per Principle III.

## `decide_reference(source_item, target, spec, cache) -> ReferenceDecision`

Pure; no writes. Classifies one referenced possibility item.

**Inputs**
- `source_item`: the source `ICmPossibility` the copied object points at (or `None`).
- `target`: target project handle (divergence baseline, FR-005).
- `spec`: `ReferenceFieldSpec` (gives the target list + hierarchy flag).
- `cache`: per-run dict GUID → resolved/created target item (FR-012).

**Returns** `ReferenceDecision`:
- `action`: `ReferenceAction` (LINK | CREATE | UPDATE | REPORT_DROPPED)
- `target_item`: existing target item when LINK/UPDATE, else `None`
- `ancestors_to_create`: ordered source items (root→leaf) when CREATE and hierarchical
- `dropped`: `DroppedItemRecord | None` (set when REPORT_DROPPED)

**Decision table**

| Condition | action |
|---|---|
| `source_item is None` | (no-op, not emitted) |
| target has same GUID, fields identical (R7) | `LINK` |
| target has same GUID, diverged, `not _is_protected(target_item)` | `UPDATE` |
| target has same GUID, diverged, `_is_protected(target_item)` | `REPORT_DROPPED` (+LINK) |
| target lacks GUID, target list exists | `CREATE` (+ ancestor chain) |
| target list itself absent | `REPORT_DROPPED` (reason `target list absent`) |

**Guarantees**
- Deterministic; never writes; never throws on a missing target list (returns
  REPORT_DROPPED).
- Idempotent via `cache`: a GUID already resolved returns LINK to the cached item.

## `apply_reference(decision, target, owner_obj, spec, cache, tag) -> target_item`

Move-mode only. Executes the decision.
- `CREATE`: create ancestors top-down (preserve GUIDs) then the leaf under the correct
  parent; `apply_residue` the created items; store in `cache`.
- `UPDATE`: apply the non-destructive update semantic (`conflict.apply_update_semantic`);
  never blank from empty source (FR-007).
- `LINK`: set the owner's reference field to `target_item`.
- `REPORT_DROPPED`: set the reference to the existing target item if present (divergence
  case) and record is already collected; write nothing to the list.
- Returns the target item the owner should reference (or `None`).

**Postconditions**
- Owner field references a real target object or is left unchanged (never blanked).
- Exactly one `DroppedItemRecord` exists for a REPORT_DROPPED outcome.
