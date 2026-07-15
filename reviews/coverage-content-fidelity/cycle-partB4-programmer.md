# Coverage Content-Fidelity Part B sub-part 4 (FINAL): PHON_FEAT_TYPES

Commit(s): see final commit SHA(s) on worktree `GramTrans-coverage-content-fidelity-v2`
(branch `coverage-content-fidelity-v2`).

## Change

New content category `GrammarCategory.PHON_FEAT_TYPES` = `"phon_feat_types"`
is structurally IDENTICAL to sub-part 2's `FEATURE_STRUCT_TYPES`, but under
the **phonological** feature system: deep-copies each `IFsFeatStrucType` from
source `LangProject.PhFeatureSystemOA.TypesOC` into the target's
`PhFeatureSystemOA.TypesOC`, GUID-preserved, then wires each type's
`FeaturesRS` by resolving each source member `IFsFeatDefn` GUID against the
target's `PhFeatureSystemOA.FeaturesOC` (populated earlier in the same run by
`PHONOLOGICAL_FEATURES`) and calling `FeaturesRS.Add()` -- guarded per-member,
so an unresolvable member is logged and skipped without aborting the whole
type's transfer.

`src/gramtrans/Lib/categories.py` gains five functions
(`phon_feat_types_{enumerate_source,dependencies,required_writing_systems,
plan_action,execute_action}`), inserted immediately after
`feature_struct_types_execute_action` (and immediately before the
`pos_inflectable_feats` banner), registered in `LEAF_CATEGORIES`. Cloned
(not cherry-picked) from this branch's own `feature_struct_types_*` functions
per the brief's guidance, substituting `PhFeatureSystemOA` for
`MsFeatureSystemOA` throughout. Shape confirmed for API-surface parity only
against stale-branch commit `ec9891ae`'s `phon_feat_types_*` reference
(`IFsFeatStrucTypeFactory.Create(Guid)` 1-arg-only, Add-to-owner before
writing multistrings, guarded per-member `FeaturesRS.Add()`) -- the actual
implementation reuses this branch's live helpers
(`_copy_multistrings_ws_mapped(..., ws_map=...)`, `_safe_add_to_owner`,
`_find_target_obj_by_guid`, `_guid_str_from`), exactly as sub-part 2 does,
not `ec9891ae`'s stale unmapped multistring-copy path.

### The GOLD_RESERVED vs MULTI_INSTANCE tension (flagged, not silently resolved)

Per the STATUS handoff and `ec9891ae`'s `GrammarCategory` docstring/enum
comment (`PHON_FEAT_TYPES = "phon_feat_types" # G7: PhFeatureSystemOA.TypesOC
(GOLD_RESERVED)`), `PHON_FEAT_TYPES` is classified **GOLD_RESERVED** in
`models.py`'s `_build_default_conflict_modes` -- **not** `multi_instance`,
even though it is structurally identical to `FEATURE_STRUCT_TYPES`
(which sub-part 2 placed in `multi_instance`). Under v7.0.0's GOLD unlock
both buckets resolve to `ConflictMode.UPDATE`, so **runtime behavior is
identical either way** -- this is a categorical-label difference only, not a
behavioral one. I followed the handoff + port reference (GOLD_RESERVED) as
instructed rather than deviating to match sub-part 2's precedent, and am
flagging this explicitly here for the domain reviewer to adjudicate: should
`FEATURE_STRUCT_TYPES` (Part B.2, already merged) be reclassified to
GOLD_RESERVED for consistency with its sibling, or should `PHON_FEAT_TYPES`
be reclassified to MULTI_INSTANCE to match `FEATURE_STRUCT_TYPES`? Both are
internally consistent (each fully registered per its own bucket in every
site below); nothing in the current test suite forces one over the other.

A second, related consequence of the GOLD_RESERVED classification: this
category's `plan_action` does **not** call the shared
`_plan_gold_reserved_edit` helper that the other 6 GOLD_RESERVED categories
(`gram_categories`, `inflection_features`, `variant_types`,
`complex_form_types`, `semantic_domains`, `phonological_features`) all use
for their own `plan_action`. Those six perform a per-WS
Name/Abbreviation/Description gap-fill/diverged-field comparison and emit a
`PlannedOverwrite(write_mode="merge")` when the target already has the GUID
but some field differs. `PHON_FEAT_TYPES` instead follows
`FEATURE_STRUCT_TYPES`'s simpler create-by-guid shape: an already-present
type is `Skip(ALREADY_PRESENT_BY_GUID)` outright, with no field-level merge
comparison. This is a deliberate choice (cloning sub-part 2's tested,
working shape rather than inventing a GOLD-merge variant not requested by
the brief) but means `PHON_FEAT_TYPES` never actually exercises the
GOLD_RESERVED merge-overwrite machinery in `transfer.py` -- see registration
site 6 below.

### Registration sites touched (found via `grep -rn "FEATURE_STRUCT_TYPES" src/ tests/`)

1. `src/gramtrans/Lib/models.py:35` -- `PHON_FEAT_TYPES = "phon_feat_types"`
   enum member (inserted directly after `POS_INFLECTABLE_FEATS`).
2. `src/gramtrans/Lib/models.py` `gold_reserved` set (~137-150) -- added
   `GrammarCategory.PHON_FEAT_TYPES` with an inline comment explaining the
   GOLD-vs-MULTI_INSTANCE tension above (**not** added to `multi_instance`,
   per the brief).
3. `src/gramtrans/Lib/categories.py` -- new `phon_feat_types_*` block
   (banner + 5 functions), inserted between `feature_struct_types_
   execute_action` and the `pos_inflectable_feats` banner.
4. `src/gramtrans/Lib/categories.py` `LEAF_CATEGORIES` dict (~7810) -- new
   entry mapping to the 5 functions above, inserted between
   `POS_INFLECTABLE_FEATS` and `STEM_NAMES`.
5. `src/gramtrans/Lib/preview.py` `_LEAF_DISPATCH_CATEGORIES` tuple (~226) --
   added immediately **after** `PHONOLOGICAL_FEATURES` (ordering guarantee:
   `PHON_FEAT_TYPES` must dispatch after `PHONOLOGICAL_FEATURES` so its
   `FeaturesRS` resolution finds defns already landed in target
   `PhFeatureSystemOA.FeaturesOC`).
6. `src/gramtrans/Lib/transfer.py` `_LEAF_DISPATCH_CATEGORIES` tuple (~300) --
   same position/order as preview.py.
7. `src/gramtrans/Lib/transfer.py` `_OPS_ACCESSOR_FOR_CATEGORY` (~1757) --
   added `PHON_FEAT_TYPES: "PhonFeatStructTypes"` as a speculative
   future-UPDATE-mode accessor entry, mirroring `FEATURE_STRUCT_TYPES:
   "FeatureStructTypes"`'s precedent exactly (degrades to a no-op today
   since flexicon has no such ops accessor yet; same posture as its
   sibling).
8. `src/gramtrans/Lib/transfer.py` `_GOLD_RESERVED_CATS` (~2271) /
   `_iterators` (~2355) -- **deliberately NOT added**, despite
   `PHON_FEAT_TYPES` being GOLD_RESERVED at Layer 1. Verified against how
   the other GOLD_RESERVED categories actually appear here: all six that
   ARE present (`GRAM_CATEGORIES`, `INFLECTION_FEATURES`, `VARIANT_TYPES`,
   `COMPLEX_FORM_TYPES`, `SEMANTIC_DOMAINS`, `PHONOLOGICAL_FEATURES`) opt in
   via their own `plan_action` calling `_plan_gold_reserved_edit`
   (confirmed by grepping every `_plan_gold_reserved_edit` call site's
   enclosing function). `POS` is the seventh GOLD_RESERVED category and is
   ALSO absent from this map/set, for the identical structural reason (its
   own overwrite path is handled elsewhere, not through this merge
   shortcut). Since `phon_feat_types_plan_action` (cloned from
   `feature_struct_types_plan_action`) never calls
   `_plan_gold_reserved_edit` and never emits a `write_mode="merge"`
   `PlannedOverwrite`, adding an entry to `_GOLD_RESERVED_CATS`/`_iterators`
   would be dead code -- `_execute_gold_reserved_merge` would never be
   invoked for this category's actions. Added an explanatory comment at the
   `_GOLD_RESERVED_CATS` definition site documenting this precisely so a
   future reader doesn't assume a missed registration.
9. `tests/unit/test_category_registry.py:29` -- added
   `GrammarCategory.PHON_FEAT_TYPES` to the `LEAF_CATEGORIES` EXPECTED set
   (the half-registration tripwire), inserted between
   `POS_INFLECTABLE_FEATS` and `STEM_NAMES`.
10. `tests/unit/test_conflict_mode_model.py`
    `TestLayer1DefaultTable.test_gold_reserved_default_update`'s explicit
    `gold` list -- added `GrammarCategory.PHON_FEAT_TYPES` (the
    GOLD_RESERVED lock-in list, **not** the `test_multi_instance_default_
    update`'s `multi` list, per the brief).
11. `src/gramtrans/Lib/merge_preview.py` `_CATEGORY_VALUE_TO_KEY` dict
    (~1130-1159) -- added `"phon_feat_types": None`, mirroring
    `"feature_struct_types": None`'s entry (no standalone per-item preview
    pane; explicit `None` rather than an accidental table-miss
    fallthrough).

No UI wizard file (`main_window.py`, `selection_wizard.py`) change was made.
`ui/selection_wizard.py` has its own, separate `_GOLD_RESERVED` set
(distinct from `models.py`'s `gold_reserved`) that gates the wizard's
`_allowed_modes()` toggle behavior; it currently mirrors `models.py`'s
7-member set exactly. I deliberately left it untouched, following sub-part
2/3's precedent that `PHON_FEAT_TYPES` (like `FEATURE_STRUCT_TYPES` and
`POS_INFLECTABLE_FEATS` before it) is a co-created dependency category with
no independent user-visible pick-list in `_CATEGORY_TOGGLES` -- since it is
never user-toggled, whether it additionally appears in the wizard's
`_GOLD_RESERVED` set has no observable effect. Flagging this alongside the
main GOLD-vs-MULTI_INSTANCE tension in case domain review wants the wizard
set kept in lockstep with `models.py`'s for future-proofing.

## Tests (TDD, RED first)

New file `tests/unit/test_categories_phon_feat_types.py` (15 tests, cloned
from `test_categories_feature_struct_types.py`'s structure with
`PhFeatureSystemOA` substituted for `MsFeatureSystemOA` throughout the fakes,
plus one additional GOLD_RESERVED-specific test):

- `enumerate_source`: yields all `IFsFeatStrucType` objects from
  `PhFeatureSystemOA.TypesOC`; no-`Cache` source degrades to empty, no crash.
- `dependencies` / `required_writing_systems`: empty tuples.
- `plan_action`: new GUID -> `PlannedAction`; already-present-by-GUID in
  target `PhFeatureSystemOA.TypesOC` -> `Skip(ALREADY_PRESENT_BY_GUID)`;
  no-GUID piece -> `Skip(UNSUPPORTED_LCM_TYPE)`.
- `execute_action` (fake `SIL.LCModel`/`System` injection, no live LCM host):
  (a) absent-in-target -> `Factory.Create` called, new type landed in
      `PhFeatureSystemOA.TypesOC` (asserted via `_FakeAddTrackingList`
      identity check, not merely a count).
  (b) source type GUID not found in source -> `None`, no crash.
  (c) `FeaturesRS` member resolvable in target `PhFeatureSystemOA.FeaturesOC`
      -> `FeaturesRS.Add()` called with the TARGET defn object;
      unresolvable member -> skipped + logged, no crash, partial wiring
      tolerated (both single-member and mixed resolved/unresolved cases
      covered).
- (e) `test_conflict_mode_for_phon_feat_types_is_update_via_gold_reserved`:
  asserts `Selection().conflict_mode_for(GrammarCategory.PHON_FEAT_TYPES)
  == ConflictMode.UPDATE`, through the same `Selection.conflict_mode_for`
  API `test_conflict_mode_model.py` uses -- locks the OBSERVABLE UPDATE
  behavior regardless of which internal bucket (GOLD_RESERVED vs
  MULTI_INSTANCE) produces it.
- Registry sanity: bundle has exactly the 5 required keys;
  `categories.for_category(PHON_FEAT_TYPES)` returns the same bundle object
  (identity check).

## RED proof

`git stash push -- src/gramtrans/Lib/{categories,merge_preview,models,
preview,transfer}.py tests/unit/{test_category_registry,
test_conflict_mode_model}.py` (leaving the new test file untouched, since it
is untracked) reproduced the pre-change state. Collecting
`tests/unit/test_categories_phon_feat_types.py` then failed at
**collection time** with `AttributeError: type object 'GrammarCategory' has
no attribute 'PHON_FEAT_TYPES'` -- confirming the new tests fail for the
right reason (the category genuinely does not exist pre-change).
`git stash pop` restored the fix; the same file then passed 15/15.

## Verify

- Targeted: `test_categories_phon_feat_types.py` + `test_category_registry.py`
  + `test_conflict_mode_model.py` -> **62 passed**.
- `python -m py_compile` on every edited/created file -> clean.
- Full suite `python -m pytest tests/unit -q`: **1642 passed**, 8 skipped,
  14 xfailed, 14 xpassed, **exactly 1 failure**:
  `test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos
  ::test_plan_emits_pos_action_for_picked_pos` -- confirmed to be the same
  documented pre-existing baseline failure (unchanged from sub-parts
  1/2/3's reports); not a regression. 1642 = 1627 (sub-part 3 baseline) +
  15 new tests (the new file contributes all 15; the two touched
  pre-existing test files added 0 new test functions, only widened existing
  set-membership assertions).

## Sweep audit

Shape: "`IFsFeatStrucType` owner-collection mis-write" (the same shape
class sub-part 2 swept). Confirmed:
- `phon_feat_types_execute_action`'s `_safe_add_to_owner` call targets
  `tgt_feature_system.TypesOC` where `tgt_feature_system =
  tgt_cache.LangProject.PhFeatureSystemOA` -- **not**
  `MsFeatureSystemOA.TypesOC` (sub-part 2's owner) and **not** `FeaturesOC`
  (a sibling collection on the same feature system, holding defns rather
  than types).
- `FeaturesRS` member resolution reads `list(tgt_feature_system.FeaturesOC)`
  where `tgt_feature_system` is the SAME `PhFeatureSystemOA` object used for
  the `TypesOC` Add above -- confirmed both reads/writes in this function
  resolve against the phonological feature system, never accidentally
  crossing over to `MsFeatureSystemOA` (grepped every
  `MsFeatureSystemOA`/`PhFeatureSystemOA` occurrence added by this
  sub-part; `phon_feat_types_*` contains zero `MsFeatureSystemOA`
  references).
- Grepped every `TypesOC`/`FeaturesOC` write site across `categories.py`
  post-change: `FEATURE_STRUCT_TYPES` writes only to
  `MsFeatureSystemOA.TypesOC`, `PHON_FEAT_TYPES` writes only to
  `PhFeatureSystemOA.TypesOC`, `INFLECTION_FEATURES` writes only to
  `MsFeatureSystemOA.FeaturesOC`, `PHONOLOGICAL_FEATURES` writes only to
  `PhFeatureSystemOA.FeaturesOC`, `POS_INFLECTABLE_FEATS` reads (never
  writes) `MsFeatureSystemOA.FeaturesOC` -- no sibling mis-write to the
  wrong owner collection found across the whole Part B set.

## Part B COMPLETE

All 4 sub-parts of coverage-content-fidelity Part B are now landed on this
branch:
- Part B.1: `INFLECTION_FEATURES` complex/open features (commit `2ab8a79`).
- Part B.2: `FEATURE_STRUCT_TYPES` (`MsFeatureSystemOA.TypesOC`,
  MULTI_INSTANCE) (commit `e98f752`).
- Part B.3: `POS_INFLECTABLE_FEATS` (`IPartOfSpeech.InflectableFeatsRC`
  ref-wiring, MULTI_INSTANCE) (commit `dfcc626`).
- Part B.4 (this sub-part): `PHON_FEAT_TYPES` (`PhFeatureSystemOA.TypesOC`,
  GOLD_RESERVED per handoff -- flagged tension with B.2's sibling
  classification, above).

No live FLEx/FLExToolsMCP transfer was run in this session (offline
implementation + unit tests only, per instructions).
