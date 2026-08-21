# T067 -- the registration that took three tries

**Date**: 2026-08-21
**Predecessors**: `T065-T067-the-audit-that-said-no.md`, `T088-the-cast-that-was-missing.md`
**Commits**: see the end of this file

---

## What T067 asked for, and why it needed three attempts

> "Audit and register `affixes_dependencies`: confirm the edge is correct
> against a live pair, add it to `CLOSURE_EDGES_VERIFIED` with `verified_by`
> naming the audit, then run a census."

One sentence, three separate refusals before a row landed. Each refusal was a
different kind of wrong, and none of them was visible from the unit suite.

**Attempt 1 (`73a8b73`) -- the producer did not read.** `AFFIX_TO_POS` measured
0 edges uncast against 296 cast on `Mbugwe LizzieHC practice`, 0 against 245 on
`Ejagham Mini`. `MorphoSyntaxAnalysesOC` is polymorphic and typed
`IMoMorphSynAnalysis`; `PartOfSpeechRA` is not declared there. Registration
refused; filed as T088.

**Attempt 2 (`955267e`) -- T088 supplied the cast** and deliberately registered
nothing, because "the producer works" is not "the edge is verified".

**Attempt 3 (this task) -- the composite-producer problem, then a third,
different refusal.**

## The composite-producer problem, and why `dependency_category` is the fix

`affixes_dependencies` returns a MIXED edge set from one call:
`_entry_pos_deps` gives GRAM_CATEGORIES, and `_entry_feat_struc_deps` gives
FEATURE_STRUCT_TYPES **and** INFLECTION_FEATURES. `CLOSURE_EDGES_VERIFIED` is
keyed by one `DependencyKind` per row and dict keys are unique, so the composite
cannot be registered honestly: under `AFFIX_TO_POS` with
`dependency_category: None`, `preview._closure_kind_lookup` stores it at the key
`(AFFIXES, None)` and `_materialise_closure_edges` matches every edge on that
wildcard, stamping all three relationships `AFFIX_TO_POS` and filing two
unaudited relationships under a third's `verified_by`.

The fix the task named -- narrow per-relationship producers -- turns out to have
a second half that matters as much as the narrowing itself. `_closure_kind_lookup`
keys on the PAIR `(category, dependency_category)`. So three rows all with
`category=AFFIXES` are legal *provided each declares an EXPLICIT
`dependency_category`*; the keys are then `(AFFIXES, GRAM_CATEGORIES)`,
`(AFFIXES, FEATURE_STRUCT_TYPES)`, `(AFFIXES, INFLECTION_FEATURES)` and cannot
collide. A `None` in any of them re-opens the wildcard. Both halves are asserted
(`test_every_registered_row_names_a_narrow_producer`,
`test_the_registered_rows_do_not_collide_in_the_kind_lookup`).

`affixes_dependencies` itself is UNCHANGED. It has non-closure callers, and
narrowing it would have been a live-behaviour change smuggled into a
registration commit.

The narrowing filter is STRICT (`is`, on the far category) for a reason beyond
tidiness. `_feat_struc_deps` classifies a `TypeRA` by OWNERSHIP via
`_feat_struc_type_categories`, which walks BOTH feature systems -- so an MSA
whose structure pointed into `PhFeatureSystemOA` would yield PHON_FEAT_TYPES /
PHONOLOGICAL_FEATURES edges, and `_materialise_closure_edges` RAISES on an edge
no registry row authorises. Dropping them is the correct behaviour for an
unregistered relationship, and the driver counts what was dropped
(`foreign_edges`) rather than discarding it silently. Measured 0 on both corpora
-- so the guard is live but currently unexercised, which is worth knowing rather
than assuming.

## The third refusal: an edge that names something no category can enumerate

This is the part the previous audit could not have found, because it was
measuring a composite.

`MSA_TO_INFL_FEATURE`'s producer is narrow and its edges are live: **206** edges
over 34 distinct far GUIDs on Mbugwe, **34** over 10 on Ejagham Mini,
`foreign_edges` 0 on both. By the standard T088 established -- does the producer
read anything? -- it passes.

It is still not registrable. The extended driver resolves every far GUID against
the far category's **own** `enumerate_source`, and:

| corpus | distinct far GUIDs | enumerable pieces | owned symbolic values |
|---|---|---|---|
| Mbugwe LizzieHC practice | 34 | **4** | **30** |
| Ejagham Mini | 10 | **2** | **8** |

`inflection_features_enumerate_source` walks `FeatureGetAll()` -- the feature
DEFNS. The other 30 (8) GUIDs are `IFsSymFeatVal` symbolic values, which
`inflection_features_dependencies` itself records are "co-created in
execute_action, not separately planned". So most of what this relationship
points at is not a piece any category yields. A pulled-in ref naming such a
thing cannot be planned, cannot be marked pulled-in (T070), and cannot be
deselected (T072) -- FR-016's whole promise fails on it silently.

Registering it would have produced a plan containing items nobody can act on,
under a `verified_by`. Refused, and **filed as T089** rather than fixed: making
a value edge point at its owning feature changes `affixes_dependencies`' live
output, which is a behaviour change with its own census.

That the two other relationships resolved 6/6 and 2/2 with zero owned values is
what makes this a real difference rather than an instrument that cannot see
anything.

## What was registered

| relationship | producer | far category | edges (Mbugwe / Ejagham) |
|---|---|---|---|
| `AFFIX_TO_POS` | `affixes_pos_dependencies` | GRAM_CATEGORIES | 144 / 88 |
| `MSA_TO_FEAT_STRUC_TYPE` | `affixes_feat_struc_type_dependencies` | FEATURE_STRUCT_TYPES | 73 / 17 |

Two rows. Both `category=AFFIXES`, distinct `dependency_category`, each
`verified_by` naming the driver, the two corpora, the committed snapshot key and
the integration test that asserts it.

**STEMS is deliberately absent.** `stems_dependencies` shares both helpers and
would very likely audit identically -- and "would very likely audit
identically" is the exact reasoning FR-018 refuses. It would need its own
`DependencyKind` member anyway, and therefore its own audit.

The narrow-producer counts do NOT sum to `affixes_dependencies`' 1063 / 405,
and that gap is itself the argument for the extension: the composite was
measured over EVERY LexEntry, while these are measured over
`affixes_enumerate_source`'s output -- the pieces the registry actually hands
them. The composite count could not have earned these rows anything.

## The instrument, extended a second time

T088's journal records that the driver's first version measured only the read
PATTERN and was therefore useless for checking T088's own fix. The same
criticism applied to its second version and this task: `producer_output` counts
what a COMPOSITE returns, and an audit that cannot distinguish three
relationships cannot earn three `verified_by` values.

So the driver now carries a third signal, `relationships`, deliberately not
merged with the other two. Per candidate relationship it calls the narrow
producer over `affixes_enumerate_source`'s pieces and records `foreign_edges`
(is it narrow?), `resolved_as_piece` / `resolved_as_owned_value` /
`unresolved` (does the far endpoint name something plannable?) and a verdict
that is CONFIRMED only when all three answer correctly, on both corpora.

## Mutation verification -- three directions

All three re-measured against the FINAL tree, not against whatever the suite
happened to contain when each mutation was first tried. (The first pass
recorded 3425 because the FR-018 raise guard had not been written yet; a
mutation number that was true of an earlier tree is the kind of claim this
feature keeps catching in other people's work.)

| mutation | `tests/unit` | live audit | integration guards |
|---|---|---|---|
| **M1** `_narrow_deps` -> passthrough | **3426 passed** (unchanged) | `MSA_TO_FEAT_STRUC_TYPE` and `MSA_TO_INFL_FEATURE` -> `REFUSED_NOT_NARROW`, foreign 206 / 73 | **3 fire** |
| **M2** register the composite under `AFFIX_TO_POS`, `dependency_category: None` | **3 FAIL** | not needed | -- |
| **M3** `_cast_to_concrete` -> no-op (pre-T088) | **3426 passed** (unchanged) | all three relationships -> `NO_DATA`, producers 0 edges | **7 fire** |

M1 and M3 are the asymmetry restated: a change that is invisible to 3426 unit
tests and fatal to the live audit. M2 is the interesting exception -- it is a
registry-SHAPE defect, so the unit suite catches it without a database, which
is exactly where a shape defect should be caught.

M2's third failure was not predicted and is worth recording.
`test_an_unregistered_far_category_from_a_registered_source_raises` fires under
M2, because the `(AFFIXES, None)` wildcard **absorbs** a PHON_FEAT_TYPES edge
instead of raising on it. That test was written to pin the raise; under the
mutation it demonstrates the substitution FR-018 exists to prevent, on the
exact edge the strict filter drops.

## The census -- and the third instrument error, found by running it

Driver: `debug/run038_t067_census.py`, target `GT038 T067 Target` restored from
`backups/Target 2026-07-06 0218.fwbackup` first. Source `Mbugwe LizzieHC
practice`, opened read-only.

**Its first version reported the registration as INERT, and was wrong.** It
measured a FULL COPY and found **0** closure edges with the registry live.
That is not a defect: `closure.walk`'s seed semantics say an item the user
picked directly is never "pulled in by" another, and
`_materialise_closure_edges` builds edges only out of `pulled_in_by`. In a full
copy every far endpoint is already a seed in its own right -- measured, 10
`gram_categories` actions plus 2 overwrites over 13 source POSes, and 6
`feature_struct_types` actions. There is nothing left to pull in.

So a registered closure edge is observable ONLY under a partial selection, and
the partial selection in question is Phase 7's own Independent Test, sitting in
tasks.md above these three tasks the whole time: *"select only affixes, run a
preview, and confirm the dependent categories, slots and templates appear in the
plan."* That is the third time on this task that the instrument was measuring
something adjacent to the question.

### What it measured, both selections

| | full copy | affixes only |
|---|---|---|
| closure edges, registry LIVE | **0** (correct) | **217** |
| closure edges, registry EMPTY | 0 | **0** |
| distinct pulled-in refs | 0 | **8** (6 POSes + 2 struct types) |
| `AFFIX_TO_POS` | -- | 144, all `origin="pulled_in"` |
| `MSA_TO_FEAT_STRUC_TYPE` | -- | 73, all `origin="pulled_in"` |
| plan composition vs registry-empty | **identical** | **identical** |
| `verified_by` non-empty on every edge | -- | yes |

217 edges over 8 distinct dependencies is the point of having closure at all:
many affixes share a POS. It is also why the edge count and the pulled-in ITEM
count are reported separately -- FR-015's surfaces care about the second.

The registry-empty column is load-bearing. Without it, "the plan has 217 edges"
is satisfied by any code path that produces closure edges, including one that
ignores `CLOSURE_EDGES_VERIFIED` entirely -- the fall-through FR-018 forbids.

Plan composition identical under BOTH selections is what makes this safe to
land ahead of T070 and T072: registration adds edges and changes no action, skip
or overwrite. That is measured, not asserted from the design.

### The census artifact

`census run --destination-freshly-created --run-report ...` then `gate`:
**exit 3, `DUPLICATE_IDENTITY`**, artifact committed at
`_snapshots/census-038-t067-registered.json`.

On its own that number says nothing about registration. The comparison is what
means something: against `census-038-mbugwe-phase6.json` -- T063/T064's run over
the **same** source, the **same** backup and the **same** full-copy selection,
with the registry **empty**, on a separately restored target --

- **74 classes, 0 differing rows.**
- totals identical (`total_shortfall` 10262, `unexplained_shortfall` 9403,
  `duplicate_extra_objects` 66, 49 matched / 23 shortfall / 3 not evaluated).
- same verdict, same exit code.

Registering the two rows moved **no object count**. The shared exit 3 is
`PhNCFeatures`' 23 duplicate natural-key groups over 66 extra objects -- the
FLEx-auto-generated "Created automatically for rule ..." classes the source
itself duplicates, already recorded under T064 and unrelated to US3.

## What this does NOT do

- **`MSA_TO_INFL_FEATURE` is not registered.** T089.
- **STEMS is not registered**, nor is `POS_TO_FEAT_STRUC_TYPE` /
  `PHONEME_TO_FEAT_STRUC_TYPE` (those members still do not exist, on purpose --
  an unused member invites a registration nobody verified).
- **T070/T072 are untouched**, so pulled-in items are not yet marked in the
  plan or deselectable. That is why the census's job here is to prove
  registration added EDGES and changed no decision.

## Commits

- `1556dea` -- `feat(038): T067 -- two closure edges registered, the third
  refused again` (worktree `038-transfer-fidelity-gaps`)
- spec artifacts (this journal, tasks.md, T089) on `main`

## Test runs

- `tests/unit` -- **3426 passed**, 79 skipped, 14 xfailed, 14 xpassed.
- `tests/integration` (`--ignore=tests/integration/test_034_standalone_preview_live.py`,
  per STATUS.md's note about the unconditional module-scoped `flex` fixture) --
  **367 passed, 77 skipped, 1 failed**. The failure is
  `test_object_census.py::TestCorrectedPremiseNgoremeFlexIsTheSource::test_ngoreme_flex_holds_1949_and_ngoreme_holds_1945`
  and it is **pre-existing**: reproduced with every change here stashed. The
  live `Ngoreme FLEx` project has moved since its premise was pinned
  (`MoStemMsa` measured 1952, pinned 1949; the project digest has changed too
  and the test says so in its own output). Nothing in T067 touches that class,
  that project or `Lib/census.py`.
- `categories.py` ruff findings: **176 before, 176 after**. The 4 new findings
  in `debug/audit038_closure_edges.py` are all `UP031` (`%`-formatting),
  matching the 13 already there -- that file formats with `%` throughout for
  ASCII-safe Windows output.
