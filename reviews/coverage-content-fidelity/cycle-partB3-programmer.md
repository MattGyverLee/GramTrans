# Coverage Content-Fidelity Part B sub-part 3: POS_INFLECTABLE_FEATS

Commit(s): see final commit SHA(s) on worktree `GramTrans-coverage-content-fidelity-v2`
(branch `coverage-content-fidelity-v2`).

## Change

New content category `GrammarCategory.POS_INFLECTABLE_FEATS` =
`"pos_inflectable_feats"` is a **pure reference-wiring** category (NOT a
create-by-GUID category like sub-parts 1/2). For every POS in the source,
each `IFsFeatDefn` in `IPartOfSpeech.InflectableFeatsRC` (a reference
collection) is wired into the corresponding target POS's `InflectableFeatsRC`.
The feature definition itself is already created in the target by
`INFLECTION_FEATURES` (Part B.1), so this category creates **no new LCM
object**, copies **no multistrings**, applies **no residue tag**, and has
**no GOLD check**.

`src/gramtrans/Lib/categories.py` gains five functions
(`pos_inflectable_feats_{enumerate_source,dependencies,
required_writing_systems,plan_action,execute_action}`), inserted immediately
after `feature_struct_types_execute_action` (and immediately before
`stem_names`), registered in `LEAF_CATEGORIES`. Re-implemented (shape only,
not cherry-picked) from stale-branch commit `ec9891ae`'s
`pos_inflectable_feats_*` functions, adapted to this branch's live idiom:

- Piece shape: `(pos_guid_str, feat_defn_obj)` tuple; compound
  `source_guid = f"{pos_guid}::{feat_guid}"` (encodes both POS and feat).
- `enumerate_source` reuses this branch's `_iter_pos(source)` helper
  (`handle.POS.GetAll(recursive=True)`, tolerant of a missing `POS`
  accessor) instead of `ec9891ae`'s inline `hasattr(source, "POS")` /
  direct-`GetAll` duplication.
- `plan_action` validates the piece is a 2-tuple (`Skip(UNSUPPORTED_LCM_TYPE)`
  otherwise), then walks every target POS's `InflectableFeatsRC` (via
  `_iter_pos(target)` + `IPartOfSpeech(concrete)` cast) looking for the
  feat GUID already wired -> `Skip(ALREADY_PRESENT_BY_GUID)`; else
  `PlannedAction`.
- `execute_action` splits the compound `source_guid` on `"::"`, resolves the
  target POS via this branch's existing `_resolve_target_pos(target,
  pos_guid)` helper (shared with `inflection_classes`/`stem_names`; walks
  `_iter_pos` + GUID match, already casts to `IPartOfSpeech`), then resolves
  the target feature defn by `feat_guid` in `cache.LangProject
  .MsFeatureSystemOA.FeaturesOC` (linear GUID scan via `_guid_str_from`,
  mirroring `feature_struct_types_execute_action`'s `FeaturesRS` member
  resolution). If either resolution fails, logs a warning and returns
  `None` -- no crash, no partial/orphan wiring. On success:
  `target_pos.InflectableFeatsRC.Add(target_feat)`, returns `target_feat`.
- `dependencies` returns `()` (Part B.1 `INFLECTION_FEATURES` already runs
  earlier in the same pass and lands the feature defns this category
  resolves against -- no additional closure edge needed, matching
  `ec9891ae`'s `return ()`).
- `required_writing_systems` returns `()`.

`ec9891ae`'s `exception_features` naming/rework was explicitly ignored per
the brief (this branch's `EXCEPTION_FEATURES` was already reworked to the
`ProdRestrictOA` `CmPossibility` model in a separate change and is untouched
here); only the `InflectableFeatsRC` logic was ported, under the
`POS_INFLECTABLE_FEATS` name.

### Registration sites touched (found via `grep -rn "FEATURE_STRUCT_TYPES" src/ tests/`)

1. `src/gramtrans/Lib/models.py:33` -- `POS_INFLECTABLE_FEATS =
   "pos_inflectable_feats"` enum member (inserted directly after
   `FEATURE_STRUCT_TYPES`).
2. `src/gramtrans/Lib/models.py:123` -- added to the `multi_instance`
   conflict-mode set (default `ConflictMode.UPDATE`), **not**
   `gold_reserved`. See "Conflict-set choice" below for rationale.
3. `src/gramtrans/Lib/categories.py:7810` (`LEAF_CATEGORIES` dict) -- new
   entry mapping to the 5 functions above, inserted between
   `FEATURE_STRUCT_TYPES` and `STEM_NAMES`.
4. `src/gramtrans/Lib/preview.py:240` -- added to `_LEAF_DISPATCH_CATEGORIES`
   tuple, immediately after `FEATURE_STRUCT_TYPES`.
5. `src/gramtrans/Lib/transfer.py:314` -- added to the execute-side
   `_LEAF_DISPATCH_CATEGORIES` tuple, same position, matching preview.py
   order.
6. `src/gramtrans/Lib/transfer.py` `_OPS_ACCESSOR_FOR_CATEGORY` (~1757) --
   **deliberately NOT added.** Every existing entry in this map (e.g.
   `INFLECTION_CLASSES: "InflectionClasses"`, `FEATURE_STRUCT_TYPES:
   "FeatureStructTypes"`) is keyed to a project-level ops accessor exposing
   `GetSyncableProperties`/`ApplySyncableProperties` for a **single-GUID**
   object lookup (`_find_obj_by_guid(ops, guid_str)`, called from the
   UPDATE-mode `_execute_update_semantic` path). `POS_INFLECTABLE_FEATS`
   has no such ops accessor (there is nothing to "sync" on a reference-
   collection entry -- it either is wired or is not) and its `source_guid`
   is a **compound** `"pos::feat"` string that `_find_obj_by_guid` cannot
   parse. Adding an entry here would silently misroute an UPDATE-mode
   overwrite attempt into a crash or false no-op. Absence here matches the
   documented precedent for categories with no field-level update semantic
   (the comment above the map: "Others (ENTRY, AFFIXES, STEMS, etc.) use
   identity_remap paths"); `POS_INFLECTABLE_FEATS`'s "update" is fully
   captured by the `ALREADY_PRESENT_BY_GUID` idempotent-add at plan time,
   with no separate field-merge to perform.
7. `src/gramtrans/Lib/transfer.py` `_GOLD_RESERVED_CATS` (~2268) /
   `_iterators` (~2352) -- **deliberately NOT added**, matching
   `INFLECTION_CLASSES`/`FEATURE_STRUCT_TYPES`'s absence from both exactly
   (this machinery is GOLD_RESERVED-merge-only for the 6 GOLD categories;
   `POS_INFLECTABLE_FEATS` is not GOLD_RESERVED).
8. `tests/unit/test_category_registry.py:28` -- added to the
   `LEAF_CATEGORIES` EXPECTED set (the half-registration tripwire),
   inserted between `FEATURE_STRUCT_TYPES` and `STEM_NAMES`.
9. `tests/unit/test_conflict_mode_model.py:149` -- added to
   `TestLayer1DefaultTable.test_multi_instance_default_update`'s explicit
   list, locking the Layer-1 default assignment made in site 2.

No UI wizard file (`main_window.py`, `selection_wizard.py`) change was made,
for the same reason documented in sub-part 2's report: `POS_INFLECTABLE_FEATS`
is a co-created dependency-wiring category with no independent user-visible
pick-list, following the same non-UI-exposed precedent as
`INFLECTION_FEATURES`/`FEATURE_STRUCT_TYPES`.

### Conflict-set choice + rationale

Placed in the **MULTI_INSTANCE** set (default `ConflictMode.UPDATE`),
matching `FEATURE_STRUCT_TYPES` and `EXCEPTION_FEATURES` (both other
reference/wiring-flavored siblings already in that set) rather than
`GOLD_RESERVED`. Rationale:
- It is not one of the 6 constitutionally-designated GOLD_RESERVED
  categories (`GRAM_CATEGORIES`, `INFLECTION_FEATURES`, `VARIANT_TYPES`,
  `COMPLEX_FORM_TYPES`, `POS`, `PHONOLOGICAL_FEATURES`, `SEMANTIC_DOMAINS`).
- There is no dedicated "reference/wiring" `ConflictMode` set distinct from
  MULTI_INSTANCE in this codebase (checked `models.py`'s
  `_build_default_conflict_modes`) -- MULTI_INSTANCE is the closest existing
  bucket and already hosts other GUID-idempotent-add categories.
- The `ALREADY_PRESENT_BY_GUID`-skip-else-add semantics are idempotent by
  construction regardless of which `ConflictMode` label the category
  carries; UPDATE here simply means "add the wiring if missing," never a
  destructive rewrite -- there are no fields to blank or overwrite on a
  reference-collection entry, so UPDATE and ADD_NEW are behaviorally
  identical for this category. LINK's semantics ("link if present, else
  add, no field-level update") would also work but MULTI_INSTANCE/UPDATE
  keeps this category's Layer-1 classification consistent with its closest
  siblings and avoids introducing a one-off exception for no engine-level
  reason.

## Tests

New file `tests/unit/test_categories_pos_inflectable_feats.py` (15 tests,
all offline, no live LCM host, fakes mirror
`test_categories_inflection_classes.py`'s POS-owned shape +
`test_categories_feature_struct_types.py`'s Add-tracking-list idiom):

- `enumerate_source`: yields `(pos_guid, feat_obj)` tuples across multiple
  POSes; empty when no POS.
- `dependencies` / `required_writing_systems`: empty tuples.
- `plan_action`:
  (d) piece not a 2-tuple, and a wrong-length tuple -> both
      `Skip(UNSUPPORTED_LCM_TYPE)`.
  (c) already-wired-by-GUID in target POS -> `Skip(ALREADY_PRESENT_BY_GUID)`,
      no duplicate `Add`.
  new compound guid -> `PlannedAction` with `source_guid ==
  "pos-a::feat-200"`.
- `execute_action`:
  (a) feat defn GUID present in target `FeaturesOC` ->
      `InflectableFeatsRC.Add()` called on the matching target POS; returns
      the target feat object (verified by identity, not the source object).
  (b) feat defn GUID absent in target `FeaturesOC` -> `None`, warning
      logged (`caplog` assertion), no `Add` call, no crash.
  (e) target POS absent -> `None`.
  Malformed compound guid (no `"::"` separator) -> `None`, no crash
      (defensive path beyond the brief's explicit list, added because the
      split-on-`"::"` logic has an unguarded failure mode otherwise).
- Registry sanity: bundle has exactly the 5 required keys;
  `categories.for_category(POS_INFLECTABLE_FEATS)` returns the same bundle
  object (identity check); `POS_INFLECTABLE_FEATS` present in
  `categories.LEAF_CATEGORIES` (local double-check of the registry
  tripwire).

## RED proof

`git stash push -- src/gramtrans/Lib/{categories,models,preview,transfer}.py
tests/unit/{test_category_registry,test_conflict_mode_model}.py` (leaving the
new test file untouched, since it is untracked) reproduced the pre-change
state. Collecting `tests/unit/test_categories_pos_inflectable_feats.py`
then failed at **collection time** with `AttributeError: type object
'GrammarCategory' has no attribute 'POS_INFLECTABLE_FEATS'` -- confirming
the new tests fail for the right reason (the category genuinely does not
exist pre-change). `git stash pop` restored the fix; the same file then
passed 15/15.

## Verify

- Targeted: `test_categories_pos_inflectable_feats.py` +
  `test_category_registry.py` + `test_conflict_mode_model.py` -> 62 passed.
- `python -m py_compile` on every edited/created file -> clean.
- Full suite `python -m pytest tests/unit -q`: **1627 passed**, 8 skipped,
  14 xfailed, 14 xpassed, **exactly 1 failure**:
  `test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos
  ::test_plan_emits_pos_action_for_picked_pos` -- confirmed to be the same
  documented pre-existing baseline failure (unchanged from sub-part 2's
  report); not a regression. 1627 = 1612 (sub-part 2 baseline) + 15 new
  tests (the new file contributes all 15; the two touched pre-existing
  test files added 0 new test functions, only widened existing
  set-membership assertions).

## Sweep audit

Shape: "reference-collection wiring resolved by GUID." Confirmed:
- The `Add` call targets `IPartOfSpeech.InflectableFeatsRC` (a per-POS
  reference collection resolved via `_resolve_target_pos` -- the same
  helper `inflection_classes`/`stem_names` use to locate the owning POS by
  source GUID), **not** the feature system and **not** a wrong owner.
  `_FakeAddTrackingList` in the test file asserts the exact object landed
  in the exact POS's `InflectableFeatsRC`, not some other collection.
- The feature-defn resolution reads `MsFeatureSystemOA.FeaturesOC` (defn
  level -- `IFsClosedFeature`/`IFsComplexFeature` objects), **not**
  `ValuesOC` (which holds `IFsSymFeatVal` value objects, a different LCM
  interface entirely -- confirmed this is the same `FeaturesOC` collection
  `feature_struct_types_execute_action`'s `FeaturesRS` wiring already
  resolves against, so both sub-parts share one correct resolution target).
- No new LCM object created; no multistring copy; no residue-tag
  application -- confirmed by the absence of any `Factory.Create`,
  `_copy_multistrings_ws_mapped`, or `apply_carrier_b` call anywhere in
  `pos_inflectable_feats_execute_action`.

No sibling site was found wiring `InflectableFeatsRC` to the wrong
collection, and no other category resolves a feat-defn GUID against
`ValuesOC` instead of `FeaturesOC`.

## Note

FLExToolsMCP was not available as a callable tool in this session (offline
implementation only, per brief). LCM API shape (`IPartOfSpeech
.InflectableFeatsRC` as an `ILcmReferenceCollection<IFsFeatDefn>` supporting
`.Add()`) was taken from stale-branch commit `ec9891ae`'s reference
implementation (which itself cited an earlier MCP-verified finding for the
sibling `FeaturesRS.Add()` bindability) rather than re-probed live. No live
FLEx transfer was run in this session.
