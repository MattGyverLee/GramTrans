# Data Model: Fix Inflection-Feature Linking to Grammatical Categories

**Feature**: 031-fix-inflection-feature-linking | **Date**: 2026-07-13

This bugfix introduces no new persisted LCM object types. It (a) begins **populating an
existing LCM reference collection** that was previously left empty, and (b) adds one
**in-memory plan binding** to carry the planned links from Preview to Move.

## LCM entities (existing — behavior corrected)

### InflectionFeature (`IFsClosedFeature`)
- **Owner**: `LangProject.MsFeatureSystemOA.FeaturesOC`.
- **Fields carried on transfer**: `Guid` (preserved), `Name`, `Abbreviation`,
  `Description` (multistring — must be written with **target** WS handles via
  `ws_map`), `ValuesOC` (owned values).
- **Correction**: string fields must be written through writing-system mapping (R2), so
  no feature is left nameless.

### FeatureValue (`IFsSymFeatVal`)
- **Owner**: parent `IFsClosedFeature.ValuesOC`.
- **Fields**: `Guid` (preserved), `Name`, `Abbreviation`, `Description` (same WS-mapping
  correction as the feature).

### GrammaticalCategory / Part of Speech (`IPartOfSpeech`)
- **Owner**: `LangProject.PartsOfSpeechOA.PossibilitiesOS` (top-level) or a parent
  `IPartOfSpeech` (sub-category).
- **Relevant field**: **`InflectableFeatsRC`** — a reference collection of
  `IFsFeatDefn` (each element cast to `IFsClosedFeature`). **This is the collection the
  transfer previously never wrote.** Populating it is the Defect-1 fix.
- **Invariant**: an element of `InflectableFeatsRC` MUST resolve to a real feature
  object already present in the target (Principle I). Membership is a set — no duplicate
  entries (FR-002).

## Relationships

```
IPartOfSpeech.InflectableFeatsRC ──(reference, many)──▶ IFsClosedFeature
IFsClosedFeature.ValuesOC ──────────(ownership, many)──▶ IFsSymFeatVal
```

A feature becomes assignable on a lexical entry **iff** the entry's category (or an
ancestor per FLEx inheritance) lists it in `InflectableFeatsRC`.

## In-memory plan binding (new)

### FeatureCategoryLink binding
Recorded on the run-plan during Preview, consumed by the Move wiring post-pass.

| Field | Type | Meaning |
|---|---|---|
| `target_pos_guid` | str (GUID) | The category that will reference the feature (mirrors source `POS.InflectableFeatsRC` ownership). |
| `feature_guid` | str (GUID) | The inflection feature to add to that category. |

- **Shape** (mirrors `lexentry_ref_bindings`): `{target_pos_guid: [feature_guid, ...]}`.
- **Population**: at plan time, for each selected/created POS, read source
  `POS.InflectableFeatsRC` and record one entry per referenced feature that is in scope.
- **Consumption**: the wiring post-pass resolves `target_pos_guid` and each
  `feature_guid` against (a) the in-plan creation list, then (b)
  `target.get_object_by_guid`; on success it adds the feature to `InflectableFeatsRC`
  (membership-guarded); on failure it emits `Skip(DEPENDENCY_UNRESOLVED)`.

## Dedup / status sets (corrected)

| Set | Built from | Used to classify |
|---|---|---|
| target **feature**-GUID set | `target.InflectionFeatures.FeatureGetAll()` → feature `.Guid` | feature rows (`depth=0`) — `in_target` vs `new` |
| target **value**-GUID set | `FeatureGetAll()` → `IFsClosedFeature.ValuesOC` → value `.Guid` | value rows (`depth=1`) — `in_target` vs `new` |

**Correction (R3)**: previously a single value-level set (`_gather_target_infl_feat_guids`)
was used to classify both feature and value rows, mislabeling present features as
`new`. Feature rows must be classified against the feature-level set.

## State transitions (per feature, across a transfer)

```
source feature selected
   │
   ├─ present in target by GUID (feature-level) ──▶ SKIP create (names reconciled if diverged)
   └─ absent ──▶ ADD feature (+ values) with mapped names/abbr/desc
                     │
                     ▼
          feature exists in target
                     │  (wiring post-pass, both endpoints present)
                     ▼
   add feature to each referencing target POS.InflectableFeatsRC  (idempotent)
                     │  (endpoint missing)
                     ▼
          Skip(DEPENDENCY_UNRESOLVED) — reported, retried next run
```

## Validation rules

- **VR-1** (FR-001/005): a feature present in the target by feature-level GUID is never
  re-created.
- **VR-2** (FR-004): after transfer every feature and value has a non-empty name in at
  least the target default analysis WS.
- **VR-3** (FR-002): `InflectableFeatsRC` contains each feature at most once per POS.
- **VR-4** (FR-007): a link whose feature or POS is absent in the target is deferred and
  reported, never written as a dangling reference.
- **VR-5** (Principle III / FR-006): the set of links written in Move equals the set of
  link rows shown in Preview for the same selection state.
