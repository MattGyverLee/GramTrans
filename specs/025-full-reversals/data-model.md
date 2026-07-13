# Phase 1 Data Model: Full Reversals

Reuses 024's `ReferenceAction`, `FidelityStatus`, `DroppedItemRecord`, `ReferenceFieldSpec`,
and the per-run resolver cache unchanged. 025 adds a small reversal field map, a config-view
record, and reversal `owner_kind` values for dropped records. LCM objects are unchanged; this
is transfer-time bookkeeping.

## Reused from 024 (no change)

- `ReferenceAction` (LINK | CREATE | UPDATE | REPORT_DROPPED)
- `FidelityStatus` (FULL | PARTIAL)
- `DroppedItemRecord` (owner_kind, owner_guid, owner_label, field_name, item_name, item_guid,
  reason)
- `ReferenceFieldSpec` (owner_class, field_name, cardinality, target_list_path, hierarchical)
  and `decide_reference` / `apply_reference`.

## LCM objects in scope (MCP-confirmed 2026-07-11)

### IReversalIndex (owned by `LexDb.ReversalIndexesOC`, one per analysis WS)

| Member | Kind | Role in 025 |
|---|---|---|
| `WritingSystem` | str tag | Index identity; mapped source→target via `ws_mapping` (R4). |
| `EntriesOC` / `AllEntries` | owned coll | Reversal entries; filtered to those linking copied senses. |
| `PartsOfSpeechOA` | owned atom (list) | **Per-index** reversal-category possibility list — resolver target (R5). |
| `EntriesForSense(list)` | method | Closure hook: entries referencing the copied senses. |
| `FindOrCreateReversalEntry(longName)` | method | (Available; creation goes through `ReversalIndexEntryOperations.Create`.) |

### IReversalIndexEntry (owned by an index; `SubentriesOS` recurses)

| Member | Kind | Role in 025 |
|---|---|---|
| `SensesRS` | ref seq | Back-link to senses — closure scoping + partial-member reporting (R3). |
| `PartOfSpeechRA` | ref atom | Reversal category; resolved against the owning index `PartsOfSpeechOA` (R5). |
| `ReversalForm` | IMultiUnicode | Per-WS reversal string; copied via WS-map, non-destructive (R6). |
| `SubentriesOS` | owned seq | Hierarchical sub-entries; recursed like sub-senses (R6). |
| `MainEntry` / `OwningEntry` | ref | Hierarchy pointers (set implicitly by ownership). |

## Reversal field map (drives Part A; census verifies completeness)

`REVERSAL_FIELD_MAP` — the reference fields on a reversal entry routed through the 024 resolver
or owned-walk:

- `ReversalIndexEntry.PartOfSpeechRA` — atomic ref, hierarchical, target
  `lambda tgt_index: tgt_index.PartsOfSpeechOA` (R5).
- `ReversalIndexEntry.SensesRS` — ref seq; not a possibility item — re-wired to the copied
  target senses; members not in the copy set → `DroppedItemRecord` (reason `member not in copy
  set`).
- `ReversalIndexEntry.ReversalForm` — IMultiUnicode; copied per mapped WS (value field, not a
  reference).
- `ReversalIndexEntry.SubentriesOS` — owned recurse (owned-walk spec, not the resolver).

## New dataclass: ConfigViewRecord (drives Part B)

One row per configuration-view file considered for copy.

| Field | Type | Notes |
|---|---|---|
| `kind` | str | `"Dictionary"` or `"ReversalIndex"`. |
| `filename` | str | e.g. `en.fwdictconfig`. |
| `src_path` | str | Absolute source path. |
| `tgt_path` | str | Absolute target path (parallel subdir). |
| `action` | enum | `ADD` \| `OVERWRITE` \| `SKIP` (Preview-visible; R8). |
| `missing_refs` | list[DroppedItemRecord] | WS / custom-field / style references absent in target (R9). |

## New DroppedItemRecord owner_kinds (Part A + B)

- `"ReversalIndexEntry"` — for `PartOfSpeechRA` shared-default divergence, unmapped WS,
  partial `SensesRS`.
- `"ReversalIndex"` — for a whole index dropped (WS not mapped).
- `"ConfigView"` — for a config file whose reference (WS/custom-field/style) is absent in
  target; `field_name` carries the reference kind, `item_name` the referenced label.

## Relationships & Invariants

- Reversal content is copied **only** for senses in the copy set (R3); an index with no such
  entries never enters the plan (scope decision R0.1).
- A reversal category resolved once is cached by GUID for the run → reused, not re-created
  (reuse 024 cache; created at most once).
- `PartOfSpeechRA` resolution targets the **per-index** `PartsOfSpeechOA`, never
  `LangProject.PartsOfSpeechOA` (R5).
- Non-destructive: an empty source `ReversalForm` alt never blanks a populated target alt
  (024 FR-007).
- Every dropped reversal item and every config `missing_ref` produces exactly one
  `DroppedItemRecord` in the unified report (No-silent-skips gate).
- A config view is copied as a file; its `.fwdictconfig` bytes are authoritative (not
  reconstructed from the model). OVERWRITE backs up the replaced target file first.
- `FidelityStatus` for a reversal entry = `FULL` iff it produced zero `DroppedItemRecord`s.
