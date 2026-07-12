# Implementation Plan: Lexicon Reference & Owned-Object Fidelity

**Branch**: `024-lexicon-reference-fidelity` | **Date**: 2026-07-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/024-lexicon-reference-fidelity/spec.md`

## Summary

Guarantee that nothing hanging off a copied lexical entry/sense is silently lost. Extend the
existing entry/sense closure walk (`Lib/categories.py` `_walk_lex_entry_closure` and its
sense/allomorph helpers) with (1) a **generic referenced-possibility resolver** that, per
referenced list item, resolves-by-GUID / creates-with-ancestor-chain / updates-custom /
links-and-reports-shared-default; (2) **re-wiring of the object-reference fields dropped on
apply** (SenseType, DoNotPublishIn, DoNotShowMainEntryIn) to close the blanking bug; (3) an
**owned-object walk** for examples (+translations), pronunciations, etymologies, and
recursive sub-senses, plus allomorph-hung data (phonological environments, ad-hoc
prohibition rules); (4) a **dropped-item report channel** wired into the existing
`Lib/report.py` RunReport so every unreproducible item surfaces in Preview and the post-run
panel; and (5) a **model-driven fidelity census** test harness driven by the LCM
MetaDataCache. The resolver participates in the Preview plan (Principle III) rather than
writing as a hidden execute-time side effect.

## Technical Context

**Language/Version**: Python 3 (CPython + pythonnet), hosted by a stock FlexTools install.

**Primary Dependencies**: flexicon (`pyflexicon>=4.1`) Operations-class API; `SIL.LCModel`
interfaces via pythonnet (`ILexDb`, `ILangProject`, `ICmPossibilityList`, `ICmPossibility`,
`IFwMetaDataCacheManaged`, `ISilDataAccess`, factories); PyQt for the host UI/report panel.

**Storage**: FieldWorks `.fwdata` project pair accessed through the LCM cache; no external
store. Divergence baseline is the live target project (FR-005).

**Testing**: pytest under `tests/unit/`; the fidelity census is an offline verification
harness (FR-011) under `tests/verification/`, not a runtime gate.

**Target Platform**: Windows (FlexTools host); source → target between two FLEx projects.

**Project Type**: Single project — FlexTools-compatible module with helpers under
`src/gramtrans/Lib/`.

**Performance Goals**: Bounded per-reference overhead over the existing closure walk (target
corpus ~4,300 entries / ~2,500 senses / ~1,200 examples / ~2,300 pronunciations). Referenced
items are resolved once and cached per run (FR-012, SC-005) so cost is O(distinct
referenced items), not O(references).

**Constraints**: Preview-before-mutate (Principle III) — resolver decisions appear in the
plan as Add/Link/Update/Skip/Report before any write. Non-destructive: never blank a target
field from an empty source (FR-007, Principle IV update semantic). Graceful degrade: an
unresolvable item is reported, never thrown or silently dropped (Principle I "fail loudly",
"No silent skips" gate). flexicon-direct only (Principle II).

**Scale/Scope**: Lexical entry/sense/sub-sense/allomorph/example/pronunciation/etymology
closure plus the ~15 possibility lists and lexical relations they reference. Reversals (025)
and texts/wordforms (026) explicitly excluded.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| **I. FLEx Domain Fidelity** (NON-NEGOTIABLE) | **Directly served.** Principle I already requires "allomorph → environment, APR → category … MUST resolve to real objects in the target after transfer, or … fail loudly rather than silently drop." This feature *is* the implementation of that clause for the lexicon closure. GUID preservation on create (FR-002) and the GOLD-ordinary-item / concept↔GUID rule (FR-003/005 reuse `protection._is_protected`) are honored. **PASS.** |
| **II. flexicon-Direct** | All new code uses flexicon Operations + `project.GetService(IFooFactory)` fallback + `CastingOperations.cast_to_concrete` for polymorphic access. MetaDataCache/SDA reached via the LCM cache, author-side only for the census. **PASS.** |
| **III. Preview-Before-Mutate** (NON-NEGOTIABLE) | Resolver + owned-walk decisions MUST be computed in the plan-builder path and represented per item (Add/Link/Update/Skip/Report) in Preview, with writes deferred to `Lib/transfer.py`. Dropped-item records appear in Preview, not only post-run. **PASS with design obligation** (tracked in research R2). |
| **IV. Phased Merge Discipline** | Reuses existing mode vocabulary (ADD_NEW/LINK/UPDATE/OVERWRITE) and the `conflict.py` update semantic. Custom-diverged → UPDATE; shared-default-diverged → LINK + report (FR-003). No new mode introduced. **PASS.** |
| **V. Referential Completeness** | Extends closure-by-default to referenced list items and owned children; unresolved items reported, deselectability inherited from the existing per-item closure UI. **PASS.** |
| **Workflow: No silent skips** | The dropped-item report channel (FR-010/013) routes every non-reproduced item into the post-run statistics panel. **PASS** — this gate is the feature's backstop. |

No violations. Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
specs/024-lexicon-reference-fidelity/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── reference-resolver.md
│   ├── owned-object-walk.md
│   ├── dropped-item-report.md
│   └── fidelity-census.md
└── tasks.md             # /speckit-tasks output (NOT created here)
```

### Source Code (repository root)

```text
src/gramtrans/Lib/
├── categories.py        # MODIFY: entry/sense/allomorph closure walk calls the resolver +
│                        #         owned-object walk; re-wire dropped object-refs (FR-006)
├── references.py        # NEW: generic referenced-possibility resolver
│                        #      (resolve/create-ancestors/update/link+report) — FR-001..005,012
├── owned.py             # NEW: owned-object walk (examples+translations, pronunciations,
│                        #      etymologies, sub-senses, allomorph env + APR) — FR-009/009a
├── protection.py        # REUSE: _is_protected → custom-vs-shared/default classification (FR-005)
├── residue.py           # REUSE: apply_residue already covers the owned-child carrier classes
├── report.py            # MODIFY: RunReport carries dropped-item records + per-object
│                        #         fidelity status (FR-010/013)
├── conflict.py          # REUSE: update semantic for custom-item UPDATE (FR-003)
├── preview.py / transfer.py  # MODIFY: surface resolver/owned decisions in plan + execute
└── models.py            # MODIFY: DroppedItemRecord dataclass; FidelityStatus enum

tests/
├── unit/
│   ├── test_reference_resolver.py     # NEW: create/update/link+report/ancestor-chain
│   ├── test_blanking_fix.py           # NEW: FR-006/007 overwrite-does-not-blank
│   ├── test_owned_object_walk.py      # NEW: examples/pronunciations/etymology/subsense
│   ├── test_allomorph_hung_data.py    # NEW: env + APR resolution/report
│   └── test_dropped_item_report.py    # NEW: never-silent report contents
└── verification/
    └── fidelity_census.py             # NEW: MetaDataCache-driven populated-field diff (FR-011)
```

**Structure Decision**: Single-project FlexTools module. Two new focused helpers
(`references.py`, `owned.py`) keep `categories.py` from growing further and give the resolver
a clean, independently testable seam. The census lives under `tests/verification/` because it
is a dev/CI harness (Q4), not shipped runtime code. Everything else reuses existing modules
(`protection`, `residue`, `conflict`, `report`).

## Complexity Tracking

> No Constitution Check violations — table intentionally omitted.
