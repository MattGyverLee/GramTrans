# Coverage Content-Fidelity Part B sub-part 2: FEATURE_STRUCT_TYPES

Commit(s): see final commit SHA(s) on worktree `GramTrans-coverage-content-fidelity-v2`
(branch `coverage-content-fidelity-v2`).

## Change

New content category `GrammarCategory.FEATURE_STRUCT_TYPES` = `"feature_struct_types"`
deep-copies each `IFsFeatStrucType` from source `LangProject.MsFeatureSystemOA.TypesOC`
into the target's `MsFeatureSystemOA.TypesOC`, GUID-preserved, then wires each type's
`FeaturesRS` by resolving each source member `IFsFeatDefn` GUID against the target's
`MsFeatureSystemOA.FeaturesOC` (populated earlier in the same run by
`INFLECTION_FEATURES`) and calling `new_type.FeaturesRS.Add(tgt_defn)` (guarded
per-member).

`src/gramtrans/Lib/categories.py` gains five functions
(`feature_struct_types_{enumerate_source,dependencies,required_writing_systems,
plan_action,execute_action}`), inserted immediately after
`inflection_classes_execute_action` and registered in `LEAF_CATEGORIES`. The
implementation was **re-implemented from the stale `ec9891ae` reference** (LCM API
shape only: `IFsFeatStrucTypeFactory.Create(Guid)` 1-arg-only, `TypesOC.Add()`
BEFORE writing multistrings, `FeaturesRS.Add()` bindability) but adapted to this
branch's live idiom:
- Multistring copy uses main's `_copy_multistrings_ws_mapped(..., source=, target=,
  ws_map=...)` (categories.py:577), NOT ec9891ae's stale unmapped
  `_build_ws_pairs`/`_copy_multistring` helpers (which do not exist on this branch).
- Owner-Add uses main's `_safe_add_to_owner(new_obj, owner_collection,
  factory_label, src_guid)` (categories.py:6469), matching the
  `inflection_classes_execute_action` / `inflection_features_execute_action`
  (complex-feature branch) idiom exactly.
- `plan_action` follows the `inflection_classes_plan_action` shape (no GOLD
  check, `_target_has_guid` presence check, `ALREADY_PRESENT_BY_GUID` skip).

### Registration sites touched (found via `grep -rn "INFLECTION_CLASSES" src/ tests/`)

1. `src/gramtrans/Lib/models.py:32` -- `FEATURE_STRUCT_TYPES = "feature_struct_types"` enum member.
2. `src/gramtrans/Lib/models.py:118` -- added to the `multi_instance` conflict-mode set
   (default `ConflictMode.UPDATE`), **not** `gold_reserved` -- confirmed by the
   `ec9891ae` reference diff, which placed `FEATURE_STRUCT_TYPES` in the
   MULTI_INSTANCE set and reserved GOLD_RESERVED for the separate, later
   `PHON_FEAT_TYPES` (`PhFeatureSystemOA.TypesOC`) category.
3. `src/gramtrans/Lib/categories.py` (~line 1755 area, `LEAF_CATEGORIES` dict) --
   new entry mapping to the 5 functions above.
4. `src/gramtrans/Lib/preview.py:239` -- added to `_LEAF_DISPATCH_CATEGORIES`
   tuple, immediately after `INFLECTION_CLASSES`.
5. `src/gramtrans/Lib/transfer.py:313` -- added to the execute-side
   `_LEAF_DISPATCH_CATEGORIES` tuple, same position, matching preview.py order.
6. `src/gramtrans/Lib/transfer.py:1759` -- added to `_OPS_ACCESSOR_FOR_CATEGORY`
   (`GrammarCategory.FEATURE_STRUCT_TYPES: "FeatureStructTypes"`) for future
   UPDATE-mode field-merge support; degrades gracefully (logged no-op) today
   since flexicon does not yet expose a `project.FeatureStructTypes` ops
   accessor with `GetSyncableProperties`/`ApplySyncableProperties` -- same
   posture as the pre-existing `INFLECTION_CLASSES: "InflectionClasses"` /
   `STEM_NAMES: "StemNames"` / `EXCEPTION_FEATURES: "ExceptionFeatures"` entries,
   none of which resolve to a live accessor on the installed flexicon 4.1.1 either.
7. `src/gramtrans/Lib/transfer.py` `_GOLD_RESERVED_CATS` (~2268) / `_iterators`
   (~2352) -- **deliberately NOT added.** `INFLECTION_CLASSES` is absent from
   both (they are GOLD_RESERVED-merge-only machinery for the 6 GOLD categories);
   since `FEATURE_STRUCT_TYPES` is likewise not GOLD_RESERVED, it is absent too,
   matching `INFLECTION_CLASSES`'s presence/absence exactly per the brief.
8. `tests/unit/test_category_registry.py:27` -- added to the `LEAF_CATEGORIES`
   EXPECTED set (the half-registration tripwire).
9. (Bonus, not in the original 8-site list but same shape) `tests/unit/
   test_conflict_mode_model.py:148` -- added to the `TestLayer1DefaultTable
   .test_multi_instance_default_update` explicit list, locking the Layer-1
   default assignment made in site 2.

UI wizard files (`src/gramtrans/Lib/ui/main_window.py`,
`src/gramtrans/Lib/ui/selection_wizard.py`) were **deliberately left untouched**:
their `_SCHEMA_CATEGORIES` / `_CATEGORY_TOGGLES` lists are a curated legacy
subset that already excludes several existing leaf categories (all of Phase 3a's
phonology block: `PHONOLOGICAL_FEATURES`, `PHONEMES`, `NATURAL_CLASSES`,
`PHONOLOGICAL_RULES`, `STRATA`; plus `SEMANTIC_DOMAINS`, `STEMS`) -- confirmed by
grep before editing. `FEATURE_STRUCT_TYPES` is a create-by-guid dependency
category with no independent user-visible pick-list (mirrors how
`INFLECTION_FEATURES` values are co-created, not separately toggled), so it
follows the same non-UI-exposed precedent. Flagging this as a scope decision
rather than an oversight; a future UI sub-part can decide whether any of these
categories need their own wizard row.

`test_phase3b_leaf_dispatch.py`'s `_PHASE3B_CATS` tuple (a historical fixed
9-category milestone list) was intentionally left alone -- it pins a
Phase-3b-era snapshot, not a live registry-completeness contract.

## Tests

New file `tests/unit/test_categories_feature_struct_types.py` (14 tests, all
offline, no live LCM host):
- `enumerate_source`: returns all source types; degrades to `[]` (not a crash)
  when the source object has no `Cache`.
- `dependencies` / `required_writing_systems`: empty tuples.
- `plan_action`: new-GUID -> `PlannedAction`; already-present-by-GUID ->
  `Skip(ALREADY_PRESENT_BY_GUID)`; no-GUID piece -> `Skip(UNSUPPORTED_LCM_TYPE)`.
- `execute_action` (fake `SIL.LCModel`/`System` module injection, matching the
  `_patch_lcm_b1` idiom from sub-part 1's test file):
  (a) absent-in-target -> type CREATED, landed in `TypesOC` (verified via
      membership check on the fake owner-collection), factory `Create` called
      with the parsed GUID.
  (b) source-type-absent-in-source -> `None`, no crash (defensive path;
      already-present-in-target is covered at the `plan_action` layer per the
      brief, since `execute_action` is only ever invoked for a `PlannedAction`,
      never for an `ALREADY_PRESENT_BY_GUID` skip).
  (c) `FeaturesRS` member GUID resolved in target `FeaturesOC` ->
      `FeaturesRS.Add()` called with the **target** defn object (not the
      source one); member GUID unresolved -> skipped, type creation still
      succeeds (`result is new_type`, `FeaturesRS` stays empty for that
      member); mixed resolved+unresolved members -> only the resolved one is
      wired (partial-wiring tolerance).
- Registry sanity: bundle has exactly the 5 required keys;
  `categories.for_category(FEATURE_STRUCT_TYPES)` returns the same bundle
  object (identity check, mirrors `test_category_registry.py`).

## RED proof

`git stash push -- src/gramtrans/Lib/{categories,models,preview,transfer}.py
tests/unit/{test_category_registry,test_conflict_mode_model}.py` (leaving the
new test file untouched, since it is untracked) reproduced the pre-change
state. Collecting `tests/unit/test_categories_feature_struct_types.py` then
failed at **collection time** with `AttributeError: type object
'GrammarCategory' has no attribute 'FEATURE_STRUCT_TYPES'` -- confirming the
new tests fail for the right reason (the category genuinely does not exist
pre-change). `git stash pop` restored the fix; the same file then passed
14/14.

## Verify

- Targeted: `test_categories_feature_struct_types.py` +
  `test_category_registry.py` -> 20 passed.
- Widened targeted (+ `test_conflict_mode_model.py`) -> 61 passed.
- `python -m py_compile` on every edited/created file -> clean.
- Full suite `python -m pytest tests/unit -q`: **1612 passed**, 8 skipped, 14
  xfailed, 14 xpassed, **exactly 1 failure**:
  `test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos
  ::test_plan_emits_pos_action_for_picked_pos` -- confirmed (re-ran in
  isolation) to be the same pre-existing baseline failure documented at the
  1598-passed baseline; not a regression. 1612 = 1598 baseline + 14 new tests
  (the new file contributes all 14; the two touched pre-existing test files
  (`test_category_registry.py`, `test_conflict_mode_model.py`) added 0 new
  test functions, only widened existing set-membership assertions).

## Sweep audit

Shape: "single-subtype cast / owner-collection mis-write" (per brief). Grepped
every `TypesOC` / `FeaturesOC` reference in `categories.py`:
- `FEATURE_STRUCT_TYPES` (this change) writes to `MsFeatureSystemOA.TypesOC`
  only -- confirmed at the `_safe_add_to_owner` call site.
- `INFLECTION_FEATURES` writes to `MsFeatureSystemOA.FeaturesOC` only (separate
  owner collection, correct -- feature *definitions*, not struct *types*).
- `exception_features` writes to `IPartOfSpeech.ExceptionFeaturesOC` (a third,
  unrelated collection -- correct, per its own header note).
- A phonology-block category (~line 6573) writes to `PhFeatureSystemOA
  .FeaturesOC` -- a **different top-level owner** (`PhFeatureSystemOA`, not
  `MsFeatureSystemOA`) for phonological feature *values*; correctly distinct
  from both of the above and out of scope here (belongs to the future
  `PHON_FEAT_TYPES` sub-part, which targets `PhFeatureSystemOA.TypesOC`).
- The module-header comment at categories.py:322 (pre-existing, from the
  `GRAM_CATEGORIES` GOLD-fix era) already documents the `GramCat` vs `POS`
  disambiguation and explicitly flags `IFsFeatStrucType` /
  `MsFeatureSystemOA.TypesOC` as "new FEATURE_STRUC_TYPES category" -- this
  change is exactly that promised follow-up; no further sibling mis-write
  found.

No sibling site was found writing `IFsFeatStrucType` to the wrong owner
collection.

## Cross-sub-part notes

- This lands the target-side half of the `TypeRA` wiring dependency flagged in
  sub-part 1's report: `inflection_features_execute_action`'s complex-feature
  branch resolves `TypeRA` by GUID lookup in
  `MsFeatureSystemOA.TypesOC`. Once both sub-parts run in the same pass (in
  `_LEAF_DISPATCH_CATEGORIES` order: `INFLECTION_FEATURES` runs before
  `INFLECTION_CLASSES`/`FEATURE_STRUCT_TYPES`), a source complex feature whose
  `TypeRA` struct-type transfers in the *same run* will still see an empty
  target `TypesOC` at the moment the feature is created, because
  `FEATURE_STRUCT_TYPES` is dispatched *after* `INFLECTION_FEATURES` in both
  `preview.py` and `transfer.py`'s `_LEAF_DISPATCH_CATEGORIES` tuples (order:
  ... GRAM_CATEGORIES, INFLECTION_FEATURES, CUSTOM_FIELDS, INFLECTION_CLASSES,
  FEATURE_STRUCT_TYPES, STEM_NAMES, ...). This means `TypeRA` wiring will
  continue to degrade gracefully (left unset) for a *first* transfer run in a
  target that has never seen the struct-type before, and will only resolve on
  a **second** run (once `FEATURE_STRUCT_TYPES` has landed the type). This
  ordering constraint was called out in the ec9891ae reference comment
  ("Must run AFTER inflection_features ... and BEFORE G1's MSA InflFeatsOA
  copy") but that reference did not resolve the intra-run TypeRA ordering
  either -- flagging for a future ordering fix (e.g. running
  `FEATURE_STRUCT_TYPES` before `INFLECTION_FEATURES`, or a post-pass similar
  to the `InflectableFeatsRC` tail-pass already used by `INFLECTION_FEATURES`)
  rather than silently declaring it solved here, since re-ordering has its own
  ripple risk (`INFLECTION_CLASSES`'s `GRAM_CATEGORIES` dependency edge, the
  `CUSTOM_FIELDS` position, etc.) that is out of this sub-part's scope.
- `FEATURE_STRUCT_TYPES`'s own `FeaturesRS` wiring has the *inverse* ordering
  requirement (needs `INFLECTION_FEATURES` to have already landed target
  `FeaturesOC` entries) and **is** satisfied by the current dispatch order,
  since `INFLECTION_FEATURES` precedes `FEATURE_STRUCT_TYPES` in both tuples.

## Note

FLExToolsMCP was not available as a callable tool in this session (offline
implementation only, per brief). LCM API shape
(`IFsFeatStrucTypeFactory.Create(Guid)` 1-arg, `FeaturesRS.Add()` bindability)
was taken from stale-branch commit `ec9891ae`'s already-MCP-verified findings
(2026-07-11, cited in its own code comments) rather than re-probed live. No
live FLEx transfer was run in this session.
