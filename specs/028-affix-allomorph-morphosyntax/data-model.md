# Phase 1 Data Model: Affix-Allomorph Morphosyntax Fidelity

This feature adds **no new persisted data types**. It reproduces four existing LCM fields and
reuses 024's `DroppedItemRecord` and `ReferenceDecisionRecord` (in `Lib/models.py`) unchanged.
This document records the four fields, their target objects, and their per-field disposition
logic.

## The four affix-MsEnv fields

| Field | Declaring iface (read via) | Kind | Target object | Reproduction | Never-create? |
|---|---|---|---|---|---|
| `MsEnvPartOfSpeechRA` | `IMoAffixAllomorph` | RA | `IPartOfSpeech` | resolve/create via grammar POS machinery | creates POS in-closure (allowed) |
| `InflectionClassesRC` | `IMoAffixForm` (parent) | RC | `IMoInflClass` (POS-owned) | resolve/create via `IMoInflClassFactory`, scoped to owning POS | creates class under in-closure POS (allowed) |
| `MsEnvFeaturesOA` | `IMoAffixAllomorph` | OA | `IFsFeatStruc` (owned) | deep-copy owned child; resolve feature values | n/a (owned deep copy) |
| `PositionRS` | `IMoAffixAllomorph` | RS | `IPhEnvironment` | link-or-report against target env list, ordered | **never** creates an environment |

## Per-field disposition

Each field resolves to exactly one terminal disposition per referenced item, reusing 024's
vocabulary (surfaced in Preview via `ReferenceDecisionRecord`, and in the report via
`DroppedItemRecord`):

- **LINK** — target already holds the equivalent object (by GUID); reference it, write nothing
  to the target object itself.
- **CREATE** — target lacks the object and it is creatable in-closure (POS with ancestor
  chain; inflection class under an in-closure POS; owned feature structure). Create with GUID
  preserved (Principle I) and reference it.
- **REPORT_DROPPED** — the object cannot be resolved or created (out-of-closure owning POS;
  environment absent from the target env list; unsupported/complex feature value). Emit a
  `DroppedItemRecord`.

### `MsEnvPartOfSpeechRA` (atomic)
1. Empty source → no-op (must not blank a populated target field, FR-005).
2. Resolve source POS GUID against target (`_resolve_target_pos`).
   - present → LINK.
   - absent, ancestor chain resolvable in-closure → CREATE (with ancestors) → LINK.
   - absent, not resolvable → REPORT_DROPPED (`field_name="MsEnvPartOfSpeechRA"`).

### `InflectionClassesRC` (collection, read from `IMoAffixForm`)
For each referenced `IMoInflClass` (dedup within run via `resolver_cache`):
1. Resolve by GUID in target → LINK.
2. Absent, owning POS in-closure or present in target → CREATE under that POS
   (`_create_inflection_class`, GUID preserved) → add to target `InflectionClassesRC`.
3. Absent, owning POS neither present nor in-closure → REPORT_DROPPED
   (`field_name="InflectionClassesRC"`, item = the class).
Empty source collection → no-op.

### `MsEnvFeaturesOA` (owned atomic)
1. Empty/absent source → no-op (never create an empty structure; never blank target).
2. Present → deep-copy the `IFsFeatStruc` into the target allomorph's `MsEnvFeaturesOA`:
   - each feature-value specification whose feature definition resolves against the target
     feature system (reuse feature 031's closed-feature resolution) is reproduced;
   - an unresolvable/complex-feature value is REPORT_DROPPED
     (`field_name="MsEnvFeaturesOA"`, item = the feature/value), and the resolvable remainder
     is still reproduced (partial fidelity, never silent).

### `PositionRS` (reference sequence)
For each position in **source order**:
1. Resolve the `IPhEnvironment` against the target env list
   (`_target_phonological_environments`).
   - present → append to target `PositionRS` (order preserved).
   - absent → REPORT_DROPPED (`field_name="PositionRS"`, item = the environment); **never
     create** an environment.
Empty source sequence → no-op.

## Reused entities (no change)

- **`DroppedItemRecord`** (`Lib/models.py`): `owner_kind` (`"MoAffixAllomorph"`), `owner_guid`,
  `owner_label`, `field_name`, `item_name`, `item_guid`, `reason`. Field-level drop for whole
  fields (e.g. an out-of-closure POS); item-level for enumerable members (a specific missing
  environment or inflection class).
- **`ReferenceDecisionRecord`** (`Lib/models.py`): the Preview record (LINK/CREATE) surfaced in
  `PlannedAction.reference_decisions`.
- **`resolver_cache`** (per-run dict): target-item dedup so a POS / inflection class /
  environment shared by K allomorphs is resolved once (SC-005).

## Invariants

- **INV-1 (GUID identity)**: created POS and inflection classes preserve the source GUID
  unless the target already holds that GUID (Principle I; inherited from grammar path).
- **INV-2 (non-destructive)**: an empty/unset source field never blanks a populated target
  field (FR-005), across all conflict modes.
- **INV-3 (never-silent)**: every non-reproduced field/item yields a `DroppedItemRecord`
  (FR-007); the census `classify_field` guard proves no field is unclassified.
- **INV-4 (dedup)**: a target item shared by multiple allomorphs is created at most once
  (FR-006/SC-005).
- **INV-5 (order)**: `PositionRS` reproduced positions preserve source order (RS semantics).
- **INV-6 (Preview/Move parity)**: the Preview twin emits the same LINK/CREATE/REPORT
  decisions the Move leg acts on (Principle III).
