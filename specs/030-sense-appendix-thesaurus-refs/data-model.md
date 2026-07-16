# Data Model: Sense Appendix & Thesaurus References (030)

030 introduces **no new persisted entities**. It resolves two existing `LexSense`
reference fields and reuses 024's `DroppedItemRecord`. This document records the LCM
shapes involved and the in-memory resolution structures.

## LCM entities (read/linked, not defined by 030)

### `LexSense.AppendixesRC` → `LexAppendix`

| Aspect | Value |
|---|---|
| Field | `LexSense.AppendixesRC` (reference collection, `RC`) |
| Target class | `LexAppendix` (bespoke owned class) |
| Home | `LexDb.AppendixesOC` (owning collection) |
| Members | `ContentsOA : IStText` (owned atomic), `ClassID`, `ClassName`, `OwnershipStatus` |
| Identity | GUID (`.Guid`) |
| 030 action | **Link by GUID** if a matching appendix exists in target `LexDb.AppendixesOC`; else `DroppedItemRecord`. Never created; owned `IStText` never reproduced. |
| Target access | `ILexDb(ILangProject(target.Cache.LangProject).LexDbOA).AppendixesOC` |

### `LexSense.ThesaurusItemsRC` → `CmPossibility`

| Aspect | Value |
|---|---|
| Field | `LexSense.ThesaurusItemsRC` (reference collection, `RC`) |
| Target class | generic `CmPossibility` (`ICmPossibility`) |
| Home list | **not fixed** — discovered by walking `.Owner` to the owning `ICmPossibilityList` |
| Identity | GUID + name/abbreviation; optional parent (hierarchy) |
| 030 action | Discover owning list, mirror it onto the target (owner-class + owning-flid), then resolve/create/link the item via 024's resolver; else `DroppedItemRecord`. |

**Cross-project caveat**: possibility-list GUIDs differ per project (source
SemanticDomainList `c924bfce…` vs target `90aa3d0a…`), so the equivalent target list is
found by owner-class + `OwningFlid` (model-stable), never by list GUID. The *item* is
matched by GUID/fingerprint within the discovered list (024 behavior).

## In-memory resolution structures (reused from 024)

### `ReferenceFieldSpec` (existing, `Lib/references.py`)

Section B constructs a **synthetic** spec per thesaurus reference:

```text
ReferenceFieldSpec(
    owner_class    = "LexSense",
    field_name     = "ThesaurusItemsRC",
    cardinality    = ReferenceCardinality.COLLECTION,
    target_list_path = lambda _target: <discovered target ICmPossibilityList>,
    hierarchical   = True,   # safe default: create ancestor chain if nested
)
```

The lambda closes over the already-discovered target list (discovery is not pure-data
like the static `REFERENCE_FIELD_MAP` rows, so the spec is built at resolve time, not at
import time).

### `DroppedItemRecord` (existing, unchanged shape)

Emitted (never-silent) when a reference cannot be reproduced:

| Field | Section A value | Section B value |
|---|---|---|
| `owner_kind` | `"LexSense"` | `"LexSense"` |
| `owner_guid` / `owner_label` | source sense identity | source sense identity |
| `field_name` | `"AppendixesRC"` | `"ThesaurusItemsRC"` |
| `item_name` | `""` (LexAppendix has no `.Name`) | item best-WS name |
| `item_guid` | source appendix GUID | source item GUID |
| `reason` | "no LexAppendix with this GUID in target LexDb.AppendixesOC (030 link-by-GUID scope; not created)" | "owning CmPossibilityList could not be resolved in target (030 dynamic-owner)" |

## Census classification transitions (`tests/verification/fidelity_census.py`)

| Field | 024 bucket | 030 bucket |
|---|---|---|
| `("LexSense","AppendixesRC")` | `DROP_REPORTED` | **`COPIED`** |
| `("LexSense","ThesaurusItemsRC")` | `DROP_REPORTED` | **`COPIED`** |
| `("LexSense","PicturesOS")` | `DROP_REPORTED` | `DROP_REPORTED` (029) |
| `OUT_OF_SCOPE_EXCLUDED` frozenset | `{("LexEntry","MainEntriesOrSensesRS")}` | unchanged |

## Invariants

- **Never-silent**: every non-reproduced reference emits exactly one `DroppedItemRecord`
  (dedup via existing `_append_dropped_once`). No silent out-of-scope bucket for real data.
- **Non-destructive**: an empty/unset source field never blanks a populated target field.
- **At-most-once**: a shared appendix/thesaurus item resolves once per run (resolver cache
  / target scan), not per referencing sense.
- **Preview == Move**: identical decisions and residual drop sets by construction.
