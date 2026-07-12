# Phase 1 Data Model: Lexicon Reference & Owned-Object Fidelity

Entities are Python-side dataclasses/enums in `Lib/models.py` plus the reference-field map
that drives the resolver. LCM objects themselves are unchanged; this feature adds transfer-
time bookkeeping, not model schema.

## Enums

### ReferenceAction

Outcome of resolving one referenced possibility item against the target.

| Value | Meaning |
|---|---|
| `LINK` | Target already has an identical item (by GUID); reference it, write nothing. |
| `CREATE` | Item absent from target; create it (+ ancestor chain), preserving GUID. |
| `UPDATE` | Item present, diverged, and **custom** (`not _is_protected`); non-destructive update per the update semantic. |
| `REPORT_DROPPED` | Item present, diverged, and **shared/default** (`_is_protected`) → LINK the existing item + emit a divergence record; OR item unresolvable → emit a dropped record. |

### FidelityStatus

Per copied object, for the report (FR-013).

| Value | Meaning |
|---|---|
| `FULL` | Every populated reference/owned field reproduced. |
| `PARTIAL` | Reproduced with ≥1 dropped item (count carried alongside). |

## Dataclasses

### DroppedItemRecord (FR-010)

The never-silent report unit.

| Field | Type | Notes |
|---|---|---|
| `owner_kind` | str | e.g. `"LexSense"`, `"LexEntry"`, `"MoStemAllomorph"`, `"LexExampleSentence"`. |
| `owner_guid` | str | Source GUID of the owning object. |
| `owner_label` | str | Human headword/gloss for the report line. |
| `field_name` | str | The reference/owned field that could not be reproduced. |
| `item_name` | str | Source item's name/abbreviation (best analysis alt). |
| `item_guid` | str | Source item GUID. |
| `reason` | str | e.g. `"shared-default diverged"`, `"target list absent"`, `"member not in copy set"`. |

### ReferenceFieldSpec (drives the resolver — the closed field map)

One row per reference field the resolver walks. This is the *hand-curated dispatch table*;
the **census (FR-011) is the independent check that it is complete**.

| Field | Type | Notes |
|---|---|---|
| `owner_class` | str | Class the field lives on. |
| `field_name` | str | LCM property (e.g. `SenseTypeRA`, `UsageTypesRC`). |
| `cardinality` | enum | `ATOMIC` \| `COLLECTION` \| `SEQUENCE`. |
| `target_list_path` | callable | `target -> ICmPossibilityList` (e.g. `lp.LexDbOA.SenseTypesOA`). |
| `hierarchical` | bool | Whether ancestor-chain creation applies. |

**Initial field map** (source of FR-001 coverage; completeness verified by census):

- Sense: `SenseTypeRA`(atomic, SenseTypesOA, tree), `UsageTypesRC`(coll, UsageTypesOA),
  `DomainTypesRC`(coll, DomainTypesOA, tree), `AnthroCodesRC`(coll, AnthroListOA, tree),
  `DialectLabelsRS`(seq, DialectLabelsOA), `StatusRA`(atomic, StatusOA)*,
  `SemanticDomainsRC`(coll, SemanticDomainListOA, tree)*, `PublishIn`/`DoNotPublishInRC`
  (coll/set, PublicationTypesOA), `DoNotShowMainEntryInRC`(coll, PublicationTypesOA).
- Entry: `DialectLabelsRS`(seq, DialectLabelsOA), `PublishIn`/`DoNotPublishInRC`/
  `DoNotShowMainEntryInRC`(PublicationTypesOA), allomorph `MorphTypeRA`(atomic, MorphTypesOA)*.
- Example → `CmTranslation.TypeRA`(atomic, TranslationTagsOA).
- Allomorph → `PhoneEnvRC`(coll, phonological environments — resolved via existing
  `PH_ENVIRONMENT` category target); `StemNameRA`(atomic, POS stem-names — existing
  `STEM_NAMES` category target).
- Etymology → `LanguageRS`(seq, LexDb.LanguagesOA).

All confirmed present on the live LCM surface via FLExTools MCP (2026-07-11):
`ICmPossibility.IsProtected`/`.SubPossibilitiesOS`, `ICmTranslation.TypeRA`,
`IMoStemAllomorph.PhoneEnvRC`/`.StemNameRA`, `ILexRefType.MembersOC`/`.MappingType`,
`IMoAlloAdhocProhib.FirstAllomorphRA`/`.RestOfAllosRS`/`.AllomorphsRS`,
`ILexEtymology.LanguageRS`/`.LiftResidue`.

`*` = already re-wired today; folded into the generic resolver for uniformity.

### OwnedObjectSpec (drives the owned-object walk — FR-009/009a)

| Field | Type | Notes |
|---|---|---|
| `owner_class` | str | `LexEntry` \| `LexSense` \| `MoForm`. |
| `owning_field` | str | e.g. `ExamplesOS`, `PronunciationsOS`, `EtymologyOS`, `SensesOS` (sub-senses). |
| `factory` | interface | LCM factory for the child. |
| `child_refs` | list | Reference fields on the child routed back through the resolver. |
| `recurse` | bool | True for sub-senses. |

Owned specs: Sense.`ExamplesOS` (child_refs: translation `TypeRA`), Entry.`PronunciationsOS`,
Entry.`EtymologyOS`, Sense.`SensesOS` (recurse), plus APR reproduction keyed off copied
allomorphs (`MorphologicalDataOA.AdhocCoProhibitionsOC`).

## Relationships & Invariants

- A `ReferenceFieldSpec` resolution yields a `ReferenceAction`; `CREATE`/`UPDATE` writes only
  in Move mode; all four appear in Preview (Principle III).
- Every `REPORT_DROPPED` (and every skipped owned member) produces exactly one
  `DroppedItemRecord` (SC-003: zero silent losses).
- A referenced item resolved once is cached by GUID for the run → reused, not re-created
  (FR-012 / SC-005).
- `FidelityStatus` for an object = `FULL` iff it produced zero `DroppedItemRecord`s.
- Non-destructive invariant: an empty/unset source reference never overwrites a populated
  target field (FR-007), independent of `ReferenceAction`.
