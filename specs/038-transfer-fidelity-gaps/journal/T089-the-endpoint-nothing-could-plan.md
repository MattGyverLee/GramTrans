# T089 -- the endpoint nothing could plan

**Date**: 2026-08-22
**Raised by**: T067's per-relationship audit (see
`T065-T067-the-audit-that-said-no.md`)
**Files**: `src/gramtrans/Lib/categories.py`,
`debug/run038_t089_census.py`,
`tests/integration/test_038_closure_edge_audit.py`,
`tests/unit/test_038_feat_struc_type_closure.py`,
`tests/unit/test_categories_phase3b_us3.py`

---

## The defect

`_feat_struc_deps` emitted `(INFLECTION_FEATURES, guid)` for **both** halves of
each `FeatureSpecsOC` entry: the `FeatureRA` (an `IFsFeatDefn`, owned by
`MsFeatureSystemOA.FeaturesOC`) **and** the `ValueRA` (an `IFsSymFeatVal`,
owned by the feature's own `ValuesOC`).

Only the first is a piece anything can enumerate.
`inflection_features_enumerate_source` walks
`source.InflectionFeatures.FeatureGetAll()` -- the **defns** -- and
`inflection_features_dependencies` records the reason in its own docstring: the
values are "co-created in execute_action, not separately planned."

So most of this relationship's far endpoints named an object that has no
`PlannedAction`, and therefore no FR-015 row to mark and no FR-016 checkbox to
clear. The closure promise would have failed on them **silently**, which is the
one direction constitution Principle I forbids -- and they would additionally
have been counted as pulled-in dependencies the plan claimed to have satisfied.

Measured live over `affixes_enumerate_source`'s pieces, two corpora agreeing
(`debug/audit038_closure_edges.py`, `relationships.MSA_TO_INFL_FEATURE`):

| corpus | edges | distinct far GUIDs | enumerable | owned values |
|---|---|---|---|---|
| `Mbugwe LizzieHC practice` | 206 | 34 | 4 | **30** |
| `Ejagham Mini` | 34 | 10 | 2 | **8** |

~88% and ~80% of the far endpoints named something no category could
enumerate. This is the **sixth** appearance of the feature's recurring shape --
a signal that exists and is read at a level where it cannot do its job -- and
the first where the defect is in an edge's *far endpoint* rather than in the
read that produced it.

## The fix

Direction (a), as the filing recorded, in one shared helper:
`categories._value_defn_ref(value, declared_feature)`.

- `ICmObject.Owner` **first**, not as a fallback. LCM owns an `IFsSymFeatVal`
  through `FsClosedFeature.ValuesOC`, so the owner IS the spec's `FeatureRA` in
  well-formed data and the caller's de-duplication makes the second `_add` a
  no-op. Reading `Owner` first is what covers the one case a `FeatureRA`
  fallback cannot: a spec with a `ValueRA` and a null `FeatureRA`.
- The spec's `FeatureRA` as the fallback when the owner is unreadable.
- **No edge** when neither is readable. That is the absence of a plannable
  endpoint, not the dropping of one -- measured 0 occurrences on both corpora
  -- and emitting the value guid there would put the defect back.

`Owner` is read **without a cast**, and that is checkable rather than lucky: it
is declared on `ICmObject`, so T088's polymorphic-member defect cannot apply to
it. This is the same argument that made `slots_dependencies` audit clean the
first time it was measured.

## What the fix measured

Re-run on both corpora, read-only:

| corpus | edges | distinct | enumerable | owned | verdict |
|---|---|---|---|---|---|
| `Mbugwe LizzieHC practice` | 206 -> **99** | 34 -> **4** | 4 | 30 -> **0** | REFUSED -> **CONFIRMED** |
| `Ejagham Mini` | 34 -> **17** | 10 -> **2** | 2 | 8 -> **0** | REFUSED -> **CONFIRMED** |

**The direction is the point.** The edge set got *smaller*, and the distinct
far GUIDs collapsed onto the ones that already existed, because many values of
one feature are one feature. A correction that had *added* endpoints would have
been the suspicious outcome. The composite `affixes_dependencies` fell 1063 ->
756 and 405 -> 345 with it, entirely in its `inflection_features` half (606 ->
299 and 120 -> 60).

## The sweep, and the one deliberate non-fix

The shape lived at three sites, and the fix is global **by construction**
rather than by sweeping -- the first time in this feature that has been true.

1. **`_feat_struc_deps`** serves the MSA side (AFFIXES / STEMS), the POS side
   (`IPartOfSpeech.DefaultFeaturesOA`) and the **phonological twin**
   (`phonemes_dependencies`, whose values `phonological_features_execute_action`
   co-creates exactly the way the inflectional ones are). One helper, three
   sites, one change.
2. **`variant_types_dependencies`** carried the defect independently and is
   fixed here too, using the same helper. De-duplication had to be added
   alongside it: the collapse makes duplicates the norm (a `+sg`/`-pl`
   constraint used to be two value guids and is now one feature guid), and
   without it the closure walk would count the feature twice and inflate
   `pulled_in_by`. It is unregistered, so this changes no plan -- what it
   changes is that registering VARIANT_TYPES -> INFLECTION_FEATURES later will
   not hit T089's refusal.
3. **`natural_classes_dependencies`** is deliberately **not** changed. It
   returns BARE guids by contract, and its registration is separately blocked
   on splitting the producer per far category -- which is where that fix
   belongs. Recorded rather than left silent.

## The census, and why it is not the registration's

T089's task text is explicit: the fix "is a live-behaviour change and **must
not be folded into a registration** ... it changes `affixes_dependencies`'
output for every caller, so it needs its own census."

`run038_closure_census.py` cannot supply that. Its two plans differ only in
whether `CLOSURE_EDGES_VERIFIED` is populated, so it answers *what did
registering this row change?* -- about a registry T089 does not touch. So
`debug/run038_t089_census.py` inverts the axis: the registry is held **fixed**
at its 7 rows and `categories._value_defn_ref` is monkeypatched back to the
pre-T089 identity. Patching the helper rather than restating the old code is
deliberate -- a hand-copied "before" could drift from what was actually
replaced, and then the census would be measuring a third behaviour that never
shipped.

The expected answer was zero plan difference, on a structural argument: of the
producers the fix reaches, only `affixes_feat_struc_type_dependencies` is
registered at all, and it is narrowed to FEATURE_STRUCT_TYPES -- the far
category the `TypeRA` arrow lands in, which the fix does not touch.
`MSA_TO_INFL_FEATURE` is unregistered, so `closure_dependencies_for` never
calls its producer.

**A structural argument is exactly what T088 and flexicon 4.5.0 both refuted on
live data**, so it was measured. Against `Mbugwe LizzieHC practice` into a
target restored from `Target 2026-07-06 0218.fwbackup`:

- **full copy**: 0 closure edges either way, compositions identical;
- **AFFIXES-only**: 259 closure edges either way, compositions identical;
- the resulting census reproduces `census-038-t076-registered.json`
  **row for row**, same verdict (`DUPLICATE_IDENTITY`), same exit code (3).

Artifacts: `_snapshots/closure-producer-038-t089.json`,
`_snapshots/census-038-t089-fixed.json`.

## The test was edited deliberately, and the new assertion is stricter

`test_the_refused_relationship_is_refused_for_the_recorded_reason` asserted
`resolved_as_owned_value > 0` and the `REFUSED_FAR_ENDPOINT_NOT_ENUMERABLE`
verdict, and said in its own docstring: "if that ever stops being true, this
test fails and the registration decision gets made again on new evidence, which
is the correct way for it to change." That is what happened -- it was *made* to
stop being true.

It became
`test_the_formerly_refused_relationship_now_names_only_enumerable_defns`, and
what it asserts is **stronger** than what it replaced: not "few owned values"
but `resolved_as_owned_value == 0`, `unresolved == 0`, and
`resolved_as_piece == distinct_far_guids > 0`. That is the difference between
relaxing a test and inverting it.

## The row is still not registered

The audit now says registrable and the registry says no. That third state did
not exist before and is indistinguishable from an oversight if it is not
written down, so `test_038_closure_edge_audit.py` grew the vocabulary for it:
`_CONFIRMED_NOT_REGISTERED`, asserted in **both** directions on every corpus --
CONFIRMED by the audit, and absent from `CLOSURE_EDGES_VERIFIED`. Either half
alone is satisfied by the mistake the other catches.

Registering it is **T104**. It needs the other axis --
`run038_closure_census.py` with a new `_TASKS` entry, holding the producer
fixed and varying the registry, under the AFFIXES-only selection -- and its
`expect_kinds` must name all five AFFIXES rows, because the same pieces carry
all of them.

## Lessons

1. **A fix that makes a signal smaller is more trustworthy than one that adds
   to it.** 34 far GUIDs collapsing onto 4 is a correction; 34 becoming 64
   would have needed explaining.
2. **Putting the fix in the shared helper made the sweep unnecessary for three
   of four sites.** The sweep still had to run -- it found the independent
   sibling and the deliberate non-fix -- but this is the first recurring-shape
   fix in feature 038 that was global by construction.
3. **Two censuses can look alike and answer different questions.** Holding the
   registry fixed and varying the producer is not the same measurement as
   holding the producer fixed and varying the registry, and neither substitutes
   for the other. Naming the axis in the artifact (`"axis"`) is what keeps a
   later reader from mistaking one for the other.
4. **A test that names the condition under which it should be rewritten is
   worth more than one that only asserts.** The old refusal test said exactly
   how to change it, and that sentence is why this closure is an inversion with
   evidence rather than a deletion.
