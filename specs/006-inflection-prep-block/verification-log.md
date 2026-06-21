# Phase 3b Live MCP Verification Log

**Date**: 2026-06-21 (afternoon)
**Source**: `C:\ProgramData\SIL\FieldWorks\Projects\Ejagham Mini`
**Target**: `C:\ProgramData\SIL\FieldWorks\Projects\Ejagham Full GT-Test`
**flexlibs2 fork**: `D:/Github/_Projects/_LEX/flexlibs2` (editable install)
**GramTrans commit at run time**: `194438a` (post-`InflectionFeature` accessor fix)

## Pre-flight (target baseline)

| Category | Count | Notes |
|---|---|---|
| POS (IPartOfSpeech, recursive) | 20 | From Phase 0/3a era runs |
| Inflection features (IFsClosedFeature) | 3 | Mix of GOLD + custom |
| VariantEntryTypes (top-level) | 6 | |
| ComplexEntryTypes (top-level) | 8 | |
| SemanticDomains (top-level) | 9 | |
| Custom fields (LexEntry/Sense/MoForm/Example) | 11 | |
| IFsFeatStrucType (project.GramCat) | 2 | `Noun agreement` (GOLD), `Infl` (GOLD) |

## Bug discovered + fixed before live run

`src/gramtrans/Lib/categories.py` referenced `project.InflectionFeature` (singular) but the flexlibs2 fork exposes `project.InflectionFeatures` (plural). 6 occurrences + 2 hasattr checks fixed in commit `194438a`. Test fakes in `test_categories_inflection_features.py` + `test_categories_inflection_classes.py` updated to mirror. The Phase 0 unit tests passed under the wrong name only because the fakes mirrored it.

## Scenario A.1 — US1 POS family Preview (read-only)

Selection: `GRAM_CATEGORIES`, `INFLECTION_FEATURES`, `INFLECTION_CLASSES`, `STEM_NAMES`, `EXCEPTION_FEATURES`. `enable_overwrite=False`.

```
=== US1 PREVIEW (no writes) ===
  Actions: 3  Skips: 5  Overwrites: 0
  gram_categories     added=1  skipped=2
  inflection_features added=2  skipped=3
  TOTAL               added=3  skipped=5
  [skip] no items in source for exception_features
  [skip] no items in source for inflection_classes
  [skip] no items in source for stem_names
  Skips:
    - [gram_categories] 135f8aa2-...  gold_inviolable  CatalogSourceId='tNounAgr'
    - [gram_categories] adf5fa01-...  gold_inviolable  CatalogSourceId='Infl'
    - [inflection_features] a45b03d4-...  gold_inviolable  CatalogSourceId='cNounAgr'
    - [inflection_features] cbbef348-...  gold_inviolable  CatalogSourceId='fNum'
    - [inflection_features] f7e8a2b6-...  gold_inviolable  CatalogSourceId='fBantuClass'
  Wall clock: 0.000s
```

**Verdict**: PASS for the categories as currently wired. GOLD respect honored. FR-308 empty-source UX renders correctly for 3 of 5 categories. Leaf-dispatch loop fires without errors.

## Scenario A.1 — US1 POS family Move (write_enabled=True)

```
=== US1 MOVE DONE: wall_clock=0.077s ===
  gram_categories     added=1  skipped=2
  inflection_features added=2  skipped=3
  TOTAL               added=3  skipped=5
  Wall clock: 0.077s
Target CloseProject() called -- changes saved.
```

**Post-state verification**:

| Category | Pre | Post | Δ | Expected |
|---|---|---|---|---|
| IFsFeatStrucType (project.GramCat) | 2 | 3 | +1 | +1 (`BantuNounClass`) |
| Inflection features | 3 | 5 | +2 | +2 |
| POS (IPartOfSpeech) | 20 | 20 | **0** | (see below) |

**Verdict**: PARTIAL — the 3 actions reported in the run did land in target, and the report numbers match the post-state delta. The 2 inflection features and 1 feature-struct type persisted with source GUIDs and survived target CloseProject.

## Significant finding — `gram_categories` callback target mismatch

The Phase 3b US1 spec text and the ordering-memo step 6 both equate "Gram Categories" with **Parts of Speech**:

> 6.  Parts of Speech *(= "Gram Categories")* | `LangProject.PartsOfSpeechOA.PossibilitiesOS`

But the GramTrans `gram_categories_*` callbacks walk `project.GramCat.GetAll(recursive=True)`, which the flexlibs2 fork resolves to **`IFsFeatStrucType`** items owned by `LangProject.MsFeatureSystemOA.TypesOC` — these are the **feature-struct types** (`BantuNounClass`, `Noun agreement`, `Infl` in this project), not parts of speech.

Source has 20 POSes (7 non-GOLD: `Verb Stative`, `Adverb Ideophone`, `mod`, `Exclamation`, `Auxiliary`, `Conjunction`, `400c5e75` empty-name). Source has 3 `GramCat` items (1 non-GOLD: `BantuNounClass`). The US1 Move processed the 3 IFsFeatStrucType items and **never touched POSes**. That's why POS count in target stayed at 20.

Why this was invisible until now:
- Unit-test fakes use `.GramCat` as a duck-typed attribute that returns whatever the test wires up; they don't distinguish between IFsFeatStrucType and IPartOfSpeech.
- The verb-vertical closure path in `_select_source_poses` / `_plan_pos_closure` handles real POSes during Phase 0/1/2 runs — that path is responsible for the 6 non-GOLD POSes that DID make it into target (`Adverb Ideophone`, `Verb Stative`, `mod`, `Exclamation`, `Adjective`, `Auxiliary`).
- Phase 3a/3b didn't run a Selection that activated POS through verb-vertical; only the leaf-dispatch `GRAM_CATEGORIES` fired, which targeted the feature-struct type list.

**Implication**: Phase 3b US1 has a contract bug. The five COMPLETE callbacks were said to handle "POS family transfer," but the `gram_categories` callback specifically targets the IFsFeatStrucType list, not POS. The other four (`inflection_features`, `inflection_classes`, `stem_names`, `exception_features`) hit the correct LCM types per the original design.

**Recommended next step**: Surface this to the LEX crew (lex-domain ruling — does "Gram Categories" mean POS or IFsFeatStrucType per the FLEx UI?). If the answer is "POS" (which the ordering memo says), then the gram_categories callback needs to be re-pointed at `source.POS.GetAll(recursive=True)` and the execute_action needs to create IPartOfSpeech objects in `LangProject.PartsOfSpeechOA.PossibilitiesOS`. If the answer is "IFsFeatStrucType," then the spec narrative + memo step 6 need a correction.

## Scenarios A.3 + C — deferred

US3 (variant_types + complex_form_types + semantic_domains) Preview/Move and Scenario C (variant-type dependency closure) are deferred pending resolution of the `gram_categories` semantic question above. Re-running US3 against a target whose `gram_categories` is in an ambiguous state would only add noise.

## Summary

| Scenario | Status |
|---|---|
| A.1 Preview | PASS (for wired categories) |
| A.1 Move | PARTIAL — 3 actions landed; gram_categories semantic mismatch surfaced |
| A.3 Preview/Move | DEFERRED |
| C | DEFERRED |
| Accessor bug fix (`InflectionFeatures` plural) | LANDED in 194438a |
| `gram_categories` semantic mismatch | OPEN — needs lex-domain ruling |
