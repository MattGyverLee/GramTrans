# Implementation Plan: Fix Inflection-Feature Linking to Grammatical Categories

**Branch**: `031-fix-inflection-feature-linking` | **Date**: 2026-07-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/031-fix-inflection-feature-linking/spec.md`

## Summary

Grammar transfer creates inflection features (`IFsClosedFeature` + `IFsSymFeatVal`
values) in the target's `MsFeatureSystemOA` and creates Parts of Speech, but never
writes the **feature ↔ category** link (`IPartOfSpeech.InflectableFeatsRC`). As a
result transferred features are orphaned — invisible on lexical entries (Defect 1).
Separately, transferred features accumulate as nameless/duplicate records on re-run
(Defect 2), whose leading hypothesis is that `inflection_features_execute_action`
copies `Name`/`Abbreviation`/`Description` using **source** writing-system handles
written directly into the **target** object, with no source→target handle mapping
(unlike the POS path, which routes through `ApplySyncableProperties(..., ws_map=...)`).

**Technical approach:**
1. **Read-only live diagnosis** (US3) confirms Defect 2's root cause and characterizes
   the polluted target — before any code write.
2. **Feature→category link** (US1) is added as a **wiring post-pass** modeled on the
   existing `_run_post_pass_a` / `_run_tail_once` pattern: plan-time gathers source
   `POS.InflectableFeatsRC` membership into plan bindings and emits preview-visible
   link rows; move-time wires target `InflectableFeatsRC` after both endpoints exist,
   idempotently, deferring (Skip `DEPENDENCY_UNRESOLVED`) when an endpoint is absent.
3. **Name copy + dedup fix** (US2) routes the feature/value string copy through
   writing-system mapping (mirroring the POS path) and reconciles the feature-level
   dedup so re-runs create nothing new.

The fix is **prevention-only** (FR-011): it does not remediate the already-polluted
`Ejagham Full GT-Test` target.

## Technical Context

**Language/Version**: Python 3 (FlexTools host runtime)

**Primary Dependencies**: flexicon (dist `pyflexicon>=4.1`) Operations-class API;
LCM interfaces via `cache.ServiceLocator` / `project.GetFactory` (`IFsClosedFeature`,
`IFsSymFeatVal`, `IPartOfSpeech`, `IPartOfSpeechFactory`, `IFsClosedFeatureFactory`,
`IFsSymFeatValFactory`); PyQt for the wizard UI.

**Storage**: FLEx project `.fwdata` (LCM object graph) — source and target projects.

**Testing**: pytest offline unit suite under `tests/unit/`; live FLExTools MCP
validation against the `Ejagham Mini` → `Ejagham Full GT-Test` project pair.

**Target Platform**: Windows, FlexTools host.

**Project Type**: Single project — FlexTools-compatible module (`src/gramtrans/`).

**Performance Goals**: N/A (interactive per-run transfer; feature counts are small —
tens to low hundreds of features).

**Constraints**: Preview-before-mutate (no writes outside Move); idempotent re-runs;
no silent skips (every deferral/omission reported); writing-system identity mapped
before any string write; GUID-preserving identity.

**Scale/Scope**: Two category engines touched (`INFLECTION_FEATURES`,
`GRAM_CATEGORIES`) plus one new wiring post-pass and a read-only diagnosis helper.
Feature inventory in the reference pair is on the order of 10s of features / 100s of
values.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. FLEx Domain Fidelity (NON-NEGOTIABLE)** — PASS / directly served. The
  feature→category link is the exact "inflection features and classes pull the
  categories they attach to" cross-reference the principle requires to "resolve to
  real objects in the target after transfer, or … fail loudly." The name-copy fix
  enforces "writing-system identity MUST be validated and explicitly mapped before any
  string-bearing field is written." GUIDs preserved; GOLD features treated as ordinary
  items (v7.0.0) — the link is written to reserved categories too (FR-008).
- **II. FlexTools-Compatible Output, flexicon-Direct** — PASS. All work stays in
  `src/gramtrans/Lib/` importing flexicon/LCM directly; no adapter, no new optional
  dependency. `InflectableFeatsRC` write uses the LCM reference-collection `.Add`
  guarded by a membership check (same idiom as `_run_post_pass_a`).
- **III. Preview-Before-Mutate (NON-NEGOTIABLE)** — PASS. Link appears as a distinct
  preview row (planned action / binding) and is written only in Move via the wiring
  post-pass. Residue tagging unaffected (link is a reference add, not a new object).
- **IV. Phased Merge Discipline** — PASS. This is a Phase 3b bugfix within an already
  shipped phase; it introduces no new merge mode. Dedup uses existing GUID-first
  identity; link honors the category's mode (LINK to existing / created features
  alike).
- **V. Referential Completeness** — PASS / directly served. Restores the closure
  edge feature→category so a transferred feature is not left "broken." Unsatisfiable
  links are **reported** (Skip `DEPENDENCY_UNRESOLVED`), never silently dropped.

**Result: PASS — no violations, Complexity Tracking not required.**

## Project Structure

### Documentation (this feature)

```text
specs/031-fix-inflection-feature-linking/
├── plan.md              # This file
├── research.md          # Phase 0 output — root-cause decisions
├── data-model.md        # Phase 1 output — entities + plan bindings
├── quickstart.md        # Phase 1 output — validation guide
├── contracts/
│   ├── feature-category-link.md   # Link planned-action + wiring post-pass contract
│   └── diagnosis-report.md        # Read-only diagnosis output contract
├── checklists/
│   └── requirements.md  # From /speckit-specify
└── tasks.md             # /speckit-tasks output (NOT created here)
```

### Source Code (repository root)

```text
src/gramtrans/
├── gramtrans.py                 # MainFunction entry (unchanged)
└── Lib/
    ├── categories.py            # EDIT: inflection_features_execute_action (name copy via ws_map);
    │                            #       gram_categories link gathering; NEW wiring post-pass +
    │                            #       _run_tail_once registration for the feature->POS link
    ├── selection.py             # EDIT: reconcile _gather_target_infl_feat_guids (feature- vs
    │                            #       value-level GUID) used for closure status classification
    ├── preview.py               # EDIT (if needed): surface link bindings as preview rows
    ├── transfer.py              # EDIT (if needed): ensure post-pass runs in Move
    └── models.py                # EDIT (if needed): plan binding field for feature->POS links

tests/unit/
├── test_categories_inflection_features.py   # EXTEND: link + name-copy + idempotency
├── test_category_registry.py                # EXTEND: post-pass registration
└── test_031_infl_feature_linking.py         # NEW: end-to-end plan/preview/execute + re-run

debug/
└── diag_infl_features.py        # NEW: read-only live diagnosis (US3)
```

**Structure Decision**: Single-project FlexTools module. All changes are localized to
the two affected category engines and one new post-pass in `Lib/categories.py`, plus a
closure-status reconciliation in `Lib/selection.py`. No new module or package is
introduced; the wiring post-pass reuses the established `_run_post_pass_a` /
`_run_tail_once` machinery. Exact touch-points (`preview.py`, `transfer.py`,
`models.py`) are confirmed in Phase 0 research before edits.

## Complexity Tracking

> No Constitution Check violations — section intentionally empty.
