# Domain Expert Review — coverage-content-fidelity Part B

**Date:** 2026-07-15
**Domain:** FLEx/LCM grammar model (inflection feature system)
**Status:** APPROVED WITH ONE MUST-FIX (tracked as follow-up, not a merge blocker)

> FLExToolsMCP was not available as a callable tool this session; fell back to the
> ec9891ae MCP-verified LCM findings cited in all four programmer reports,
> cross-checked against `src/gramtrans/Lib/models.py` (Layer-1 conflict-mode sets,
> read directly) and domain knowledge of the LCM
> `FsFeatureSystem`/`FsFeatDefn`/`FsFeatStrucType` model.

## Per-sub-part ownership

- **B.1** (FsComplexFeature create + TypeRA-by-guid; FsOpenFeature -> clean
  Skip(NEEDS_MANUAL); FsClosedFeature unchanged) -- PASS. Matches LCM's
  feature-system model: `FsComplexFeature.TypeRA` is the atomic reference to the
  `IFsFeatStrucType` describing the shape of the feature's value; leaving it unset
  degrades gracefully rather than corrupting the object. Open features
  (free-text-valued) have no fixed value set to transfer, so a NEEDS_MANUAL skip is
  the domain-correct conservative choice.
- **B.2** (`IFsFeatStrucType` under `MsFeatureSystemOA.TypesOC`; `FeaturesRS` ->
  `MsFeatureSystemOA.FeaturesOC`) -- PASS. Correct owning collection and correct
  reference target (struct-type members are feature *definitions*, not values).
- **B.3** (`IPartOfSpeech.InflectableFeatsRC` referencing
  `MsFeatureSystemOA.FeaturesOC`) -- PASS. `RC` naming is LCM's reference-collection
  convention; correctly mirrors FLEx's per-POS "Inflection Features" tab, where
  applicability is scoped per POS, not global. No new object created, no owning
  semantics implied -- correct as pure wiring.
- **B.4** (`IFsFeatStrucType` under `PhFeatureSystemOA.TypesOC`; `FeaturesRS` ->
  `PhFeatureSystemOA.FeaturesOC`) -- PASS. Phonological and MSA feature systems are
  correctly kept separate (distinct owner objects, zero cross-references confirmed
  in the sweep audit); matches FLEx's model where phonological features (voice,
  nasality) and inflectional features (Number, Gender) are separate namespaces.

## CONCERN #1 (dispatch order) — MUST-FIX (follow-up, not blocking this merge)

A user's mental model of "Transfer" is a single, complete operation: run it once,
get a correctly-typed target model. Leaving an `FsComplexFeature` without its
`TypeRA` after a "completed" run is a real content-fidelity gap, not cosmetic -- in
FLEx's Feature editor a complex feature is defined by its struct type; an unset
`TypeRA` leaves the feature incompletely specified, with no user-visible signal a
second run is required (no re-run prompt, no doc). "It converges on run 2" is not an
acceptable permanent design for a transfer tool, even though it degrades safely (no
crash, no orphan) meanwhile. (Verification confirms it does NOT even converge on
run 2 without an explicit repair pass -- the idempotent GOLD-skip path never
revisits an already-present complex feature's TypeRA.)

This is genuinely a two-way ordering constraint, not a simple reorder:
`FEATURE_STRUCT_TYPES.FeaturesRS` wiring needs `INFLECTION_FEATURES` to have
already populated `FeaturesOC` (satisfied today), while `INFLECTION_FEATURES`'s
complex-feature `TypeRA` wiring needs `FEATURE_STRUCT_TYPES` to have already
populated `TypesOC` (not satisfied on first run). A flat reorder of the dispatch
tuple only flips which side breaks. The correct fix is a two-phase pattern within
the same run: create type/feature *shells* by GUID in one pass (both directions),
then wire the cross-references (`TypeRA`, `FeaturesRS`) in a tail pass once both
owning collections are populated -- a comparable tail-pass shape already exists in
the codebase (e.g. for `InflectableFeatsRC`/`SlotsRC` 17.1 sub-pass). Recommend a
scoped follow-up ticket implementing that tail-wiring pass before this is
considered fully closed for content fidelity; complex features are rare in practice
so this does not block merging Part B as-is.

## CONCERN #2 — GOLD classification split

### (a) FEATURE_STRUCT_TYPES (MULTI_INSTANCE) vs PHON_FEAT_TYPES (GOLD_RESERVED) — CORRECT (reclassify PHON_FEAT_TYPES down to MULTI_INSTANCE)

The two categories are structurally identical (create-by-guid struct types with a
guarded `FeaturesRS` wiring pass, no GOLD field-merge shape), and neither's
`plan_action` calls `_plan_gold_reserved_edit`. The true GOLD_RESERVED set
represents FLEx-shipped, user-facing terminology/classification sets subject to
field-level gap-fill/merge on conflict. Feature *struct types* are structural
scaffolding (shape definitions), not shared vocabulary -- conceptually closer to
`INFLECTION_CLASSES`/`EXCEPTION_FEATURES`, which already sit in MULTI_INSTANCE.
Recommend reclassifying `PHON_FEAT_TYPES` to MULTI_INSTANCE to match its sibling,
rather than promoting `FEATURE_STRUCT_TYPES` to GOLD_RESERVED. Low-risk relabel:
v7.0.0 makes both buckets resolve to `ConflictMode.UPDATE` today, so no runtime
behavior changes -- purely a model-consistency correction. Not a merge blocker;
safe to land as a same-cycle or immediate follow-up fix.

### (b) PHON_FEAT_TYPES absent from `_GOLD_RESERVED_CATS`/`_iterators` — BLESS

Correct and consistent with the existing `POS` precedent: `POS` is also
GOLD_RESERVED at Layer 1 yet absent from this map, because its `plan_action`
likewise never emits a `write_mode="merge"` `PlannedOverwrite` via
`_plan_gold_reserved_edit`. The map is opt-in machinery for categories that
actually perform field-level GOLD merge, not a mechanical mirror of the Layer-1
label set -- including `PHON_FEAT_TYPES` there would be dead code. Bless as-is; if
2(a)'s reclassification is applied, this becomes moot (the category simply moves
buckets with no map change needed either way).

## Recommendations
1. File a follow-up ticket for the B.1/B.2 intra-run `TypeRA` ordering gap
   (two-phase shell/wire pass); do not block Part B merge on it.
2. Reclassify `GrammarCategory.PHON_FEAT_TYPES` from `gold_reserved` to
   `multi_instance` in `models.py` for consistency with `FEATURE_STRUCT_TYPES`;
   update the corresponding lock-in list in `tests/unit/test_conflict_mode_model.py`.
   No behavior change expected under v7.0.0.

---
**Reviewed By:** Domain Expert Agent
*Persisted by main session from lex-domain's returned body (lex-domain has no Write tool).*
