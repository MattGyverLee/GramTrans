# T034 / T035 / T036 -- Phase 4's implementation is complete

**Date**: 2026-08-19
**Branch (code)**: `038-transfer-fidelity-gaps`
**Commits**: `cb25b4e` (T036), `b4f50a7` (T031 producer fix), `3834de3` (T034/T035)
**Unit suite**: 2897 passing, 27 pre-existing failures, **zero net-new**

Phase 4 now has every implementation task done (T028-T037). What remains is
**T038/T039**, the census gates, which need a live pair and are blocked on the
merge described at the end.

---

## T036 -- the executor stopped asking a question the plan had answered

The executor had two opposite failure modes and no way to tell them apart. The
create-anyway half (`_idempotency_guard` and the `_create_*_with_guid` family)
looked the object up by GUID only, so a destination the plan had matched **by
name** was invisible and starter content duplicated. The resolve-only half (the
`_find_target_*_by_guid` family) looked up the same GUID, warned on `None`, and
returned -- dropping the analysis.

Now: `IDENTITY` or `NATURAL_KEY` resolves the destination the plan named, with
no re-scan and no re-derivation; `NONE` creates only where the plan licenses it
and otherwise reports; a missing record is pre-038 behaviour untouched. A
**promised-but-absent GUID raises** rather than falling back to either a create
or a drop -- the plan promised an object, so its absence is a harness defect,
not a data condition. `PlannedDestination` is deliberately executor-internal
rather than added to `models.py`: it is a resolution outcome, not a plan fact.

### The clean-degradation proof, and why it had to be that strong

This mattered more than usual, because T036 discovered that **nothing produced
a `match_basis` in production at all**. Three ways of showing the None path is
unchanged:

1. `resolve_planned_destination(None, ...)` returns before touching the
   project -- and its test uses a target whose `Object()` **raises**, asserting
   `target.asked == []`. That is the strongest available statement that nothing
   was asked, rather than that nothing went wrong.
2. Every wired site is gated on `dest.resolved`, which is False for the
   undetermined outcome, so the branch is dead without a record.
3. An A/B run of the new `transfer.py` against `git show HEAD:...transfer.py`,
   every other file identical, produced **byte-identical FAILED sets**.

### The gap it found in T031

`_emit_present_outcome` had an `object_class=` parameter and attached a record
only when a caller passed it. **None of its three callers did.** The wiring was
inert, and the T031 journal entry claiming the record now travels on the plan
was wrong until `b4f50a7`.

An opt-in that every caller must remember is the wrong shape for an accounting
record, so the class is now derived from the category through
`lcm_class_for_category`, with `object_class=` kept as an override.

The map contains **only one-to-one categories**, and the omissions carry the
reasoning: `object_class` is the field `report.py` groups by, so a guessed name
is worse than no record -- it files the match under another class's row.
`ALLOMORPH` spans two allomorph classes, `MSA` spans four, `INFLECTION_FEATURES`
spans two. The two sharp ones are `NATURAL_CLASSES`
(`PhNCSegments`/`PhNCFeatures`) and `VARIANT_TYPES`
(`LexEntryType`/`LexEntryInflType`): **038's own roster forbids both pairs from
matching each other**, so collapsing either to one name would undo that at the
report layer.

It is worth recording *how* this was found -- T036 went looking system-wide to
prove its own degradation argument, rather than checking branch by branch, and
the absence of any producer turned out to be load-bearing evidence for a
different task.

### Two recon corrections, so they are not re-derived

- `_find_target_morph_type_by_guid` is **not** a resolve-only drop site. Its
  only consumer is reference wiring that warns and continues, over the source
  allomorph's `MorphTypeRA`, for which no plan item exists.
- Two of `_find_target_env_by_guid`'s consumers are likewise unwireable: they
  build their map from `Skip`s and `PlannedOverwrite.target_guid`, and `Skip`
  has no `match_basis` field at all.

The `transfer.py:477` defect -- the ignored `execute_action` return value plus
the unconditional `leaf_succeeded` increment, which lets a silent abandon count
as a success -- was left **alone on purpose**, because fixing it changes
`match_basis is None` behaviour. T033 addressed the same defect from the
producer side instead, by making the four abandoning sites report.

---

## T034 -- the edge goes on the OWNING side, and tasks.md points the wrong way

This is the design question of the task, and the answer is the opposite of what
the task text suggests.

`feature_struct_types_dependencies` is handed an `IFsFeatStrucType` straight out
of `TypesOC`. But the `TypeRA` arrow points **at** such a piece, **from** an
`IFsFeatStruc` owned by an MSA / POS / phoneme / natural class. `closure.walk`
walks **outward** from what the user selected -- so emitting the arrow from the
type's own producer would reverse it, and an MSA selected for transfer would
never pull in the type it needs.

The edge is emitted by five producers instead: `affixes`, `stems`,
`gram_categories` (via `IPartOfSpeech.DefaultFeaturesOA`), `phonemes`, and
`natural_classes`.

The two type-side producers did get their own **outward** edge, `FeaturesRS` ->
`INFLECTION_FEATURES` / `PHONOLOGICAL_FEATURES`. That is a real reference
dependency -- `feature_struct_types_execute_action` already logs "no target
counterpart in FeaturesOC -- skipping member" and ships a partially wired type
-- and their previous `()` rationale had the implication backwards: **because**
the member definitions are owned elsewhere, `FeaturesRS` is a reference.

Both feature systems are walked, since `IFsFeatStrucType` is owned only by
`IFsFeatureSystem.TypesOC`, and each `TypesOC` GUID is classified by which
system owns it. `natural_classes` appends `TypeRA` as a **ref tuple**,
deliberately mixing shapes with its existing bare GUIDs: a bare GUID there is
indistinguishable from a feature/value GUID, and one `dependency_category`
would file it under `PHONOLOGICAL_FEATURES` instead of `PHON_FEAT_TYPES`.

### Not registered in `CLOSURE_EDGES_VERIFIED` -- correct, not an omission

Three independent reasons:

1. `verified_by` must name a **real audit**, and none has been run. Registering
   would mean fabricating exactly the evidence the mechanism exists to require.
2. The registry is keyed by `DependencyKind`, so the five producers **cannot
   all register under one member**. Phase 7 must decide the split as part of
   the same audit.
3. `test_038_foundational.py::TestClosureRegistryShipsEmpty` asserts the
   registry is `== {}` exactly, so registering now would be a net-new failure.

T034 is complete as "the producer emits the edge and the relationship is
named"; switch-on is a separate, evidence-gated act owned by T067-T069 -- which
is precisely the recorded project decision that the allowlist lands empty.
`MSA_TO_FEAT_STRUC_TYPE` is added; `POS_TO_FEAT_STRUC_TYPE` and
`PHONEME_TO_FEAT_STRUC_TYPE` are withheld until an audit can earn each a
`verified_by`.

---

## T035 -- a bug that survived because it produced the right answer

The three `Fs*` factory sites in `inflection_features_execute_action` tried the
2-arg `Create(Guid, owner)` overload **first**, inside a bare
`except Exception:`, and only then fell back to 1-arg + `Add`. They reached the
right end state -- which is precisely why this survived. A "did the object come
out right" test cannot distinguish the two paths. The swallowed exception was
hiding a pythonnet bind failure on **every single create**.

Path A is gone. All three now call the concrete factory's 1-arg `Create(Guid)`
and then `_safe_add_to_owner`.

**Six comments asserted the 2-arg belief, not the three the sweep expected** --
the module docstring, the `inflection_features` banner, the
`feature_struct_types` banner (which claimed "no 2-arg attach-on-create
overload confirmed for this factory, unlike `IFsComplexFeatureFactory`"), an
`execute_action` docstring bullet, a paragraph citing
`InflectionFeatureOperations._factory_create_attached`, and a value-loop
comment reading "the 2-arg Create attaches automatically". All six are
corrected, because a comment left asserting the opposite of the code is how
this belief propagated in the first place.

The T035 tests are **call-log** tests through the offline stub, asserting
`Create` is called exactly once with exactly one argument -- an assertion the
old code could not pass and an end-state test could never make.

### Reported rather than edited

- `owned.py`'s two `Fs*` creates are compliant in ordering but carry a no-arg
  `Create()` **GUID-loss fallback**, as do `categories._get_or_create_feat_struc`
  and `_add_closed_value`.
- `owned.py:663` has a real 2-arg `factory.Create(parsed_guid, new_owner)` for
  the `OWNER_TAKING` create kind. Non-`Fs*` and out of T035's scope, but **it
  is the one live claim in this repo that a 2-arg create binds**, and it is
  worth confirming against a host before anyone generalises T035's finding into
  "2-arg never binds".

---

## The gate on T038/T039

Two things must happen before the census gates can run, and neither is a code
change:

1. **Merge `main` into the branch.** The worktree is 53+ commits behind, and
   one of them is the roster (`d8635d9`). `matcher.NATURAL_KEY_ROSTER_PATH`
   resolves relative to the module, so the worktree still reads a **3-entry**
   roster -- every natural-key path there is inert at run time. The unit tests
   build the appended roster in `tmp_path` and are unaffected, which is exactly
   why this does not show up as a test failure. Re-run the unit suite
   immediately after the merge: at least two of those commits touched `src/`,
   not only `specs/`.
2. **A live pair.** Phase 4's header requires `Ejagham Mini` -> **a freshly
   created disposable target**, and explicitly: *never open `Target`* -- 037
   holds a live restore-bounded Move on `Projects\Target\Target.fwdata`.
   Creating that disposable project is a human decision, not something to do
   unattended.
