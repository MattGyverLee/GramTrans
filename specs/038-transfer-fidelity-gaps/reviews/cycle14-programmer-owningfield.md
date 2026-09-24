# Cycle 14 -- Programmer: the PER-OWNING-FIELD dimension for FsFeatStruc/FsClosedValue

TREE: `D:/Github/_Projects/_LEX/GramTrans-038-transfer-fidelity-gaps`
BRANCH: `038-transfer-fidelity-gaps`, HEAD at start = `6811894276d9558f489e8aa44b8afdadae2e601f`
(verified via `git rev-parse HEAD`; `src/gramtrans/Lib/categories.py` is 16,022 lines here).

## STEP 0 -- confirming/refuting the gap, both halves

**Half A (the requested check): CONFIRMED, the gap is real.** `_owning_field_label`
at `census.py:2529` existed and was called only from the owning-LIST walk
(`census.py:2571`, `owning_list_label`). `census_cli.py` had
`accounted_for_owning_lists` and no field analogue; `grep -n owning_field
census_cli.py` returned nothing before this change. No pre-existing second
emitter was found, so nothing was duplicated.

**Half B (found while gathering the source to transcribe): the two documents
the task named as the ruling source DO NOT CONTAIN a T119 entry.**
`specs/038-transfer-fidelity-gaps/tasks.md` tops out at T095's out-of-band
notes (`grep -n "T119\|T12[0-9]" tasks.md` -> no matches at all), and
`contracts/fidelity-census.md` has no T119 section either. This is reported
rather than silently substituted for, per the same "report it either way"
standard Step 0 asks for the main gap. The actual committed sources for
T119's partition are `tests/unit/test_038_t119_feat_struc_owners.py` (the fix
and its docstring table), `debug/run038_t124_recensus.py`'s
`_T119_OWNER_FIELDS` / `t119_rows`, and
`tests/integration/test_object_census.py::TestT124T119PerOwningField` (the
pinned per-pair measurements) -- all three are unchanged and used as the
evidence base instead.

## The finding that follows from Half B: the roster is EMPTY, on purpose

Unlike `CmPossibility`'s lists (Scripture note categories, discourse-chart
furniture -- non-grammatical content another feature owns or nobody claims),
none of the ten owning fields `_T119_OWNER_FIELDS` names belongs to another
feature. `MoStemMsa`, `MoInflAffMsa`, `MoDerivAffMsa`, `MoAffixAllomorph`,
`PartOfSpeech`, `PhPhoneme` are exactly the classes Phase 1's own predicate
gates on -- this feature's own grammar, not a bucket over someone else's. So
`models.CENSUS_OWNING_FIELD_RULINGS = {}` today, and the header comment above
it records the measured per-field table and names the three OPEN rows
explicitly (mirroring `MoMorphData.ProdRestrict`'s deliberate absence from
`CENSUS_OWNING_LIST_RULINGS`):

* `MoStemMsa.MsFeatures` -- TOTAL LOSS on every pair (117/782/104 -> 0/0/0),
  1,003 objects, still caused by `_create_msa_for_closure` never writing
  `MsFeaturesOA` (T119's own docstring). A live, unfixed defect.
* `FsComplexValue.Value` -- 825 -> 20 on ngoreme, the one pair that holds any;
  T119 closed the sibling `MoInflAffMsa.InflFeats` row but the complex values
  underneath did not fully follow.
* `PartOfSpeech.ReferenceForms` -- inconsistent (10->10 ejagham, 44->0
  ngoreme), which falsifies the prior "T045 depth-limit" excuse rather than
  confirming it (`test_reference_forms_is_inconsistent_across_pairs`).

The other measured fields (`MoInflAffMsa.InflFeats`,
`MoDerivAffMsa.From/ToMsFeatures`, `MoAffixAllomorph.MsEnvFeatures`) are
MATCHED on every pair that holds them, so they never reach the emitter at all
(no shortfall, ruled or not) -- exactly like a matched `owning_lists` entry.

If this reading is wrong -- i.e. a future session locates or writes a
committed ruling document naming one of these fields out-of-scope -- the
roster is where that entry belongs, transcribed the same way
`CENSUS_OWNING_LIST_RULINGS` transcribes `cmpossibility-list-rulings.md`.

## What was built, mirroring 6811894's shape exactly

* `census.count_by_owning_field(handle, object_class)` / `owning_field_counts`
  -- collected by `read_project` in the SAME open as the counts and the
  per-list dimension (one open, one digest window). Keyed `OwningClass.Field`
  with NO flid, via the ALREADY-EXISTING `_owning_field_label` (no upward walk
  needed, unlike `owning_list_label`: `FsComplexValue.Value` is itself one of
  T119's ten labels, not something to resolve past).
* `census.OWNING_FIELD_RULINGS` / `owning_field_ruling` -- the fourth roster
  and lookup, read at call time (T109 lock 3).
* `models.CENSUS_OWNING_FIELD_RULINGS: dict = {}` -- empty, with the header
  comment described above.
* `census_cli._merge_owning_fields` / `accounted_for_owning_fields` --
  DOUBLE-CAPPED (own field's shortfall, and the row's remaining room),
  surpluses never netted, wired into `_row_for_entry` LAST (after the
  per-list dimension) on the unsplit path only, matching the A1 reasoning
  already given for `owning_lists`.
* `$defs.classRow.owning_fields` added to
  `contracts/census-artifact.schema.json` (`additionalProperties: false`
  preserved), shape identical to `owning_lists` (`field` /`source_count`/
  `destination_count`).

Hard constraints respected: `max_claim` / `CENSUS_RULED_RESIDUE_CLASSES`
untouched (verified: `TestT120aTheScalarCapDoesNotBindADriftedSource` still
passes, 2/2); no class-keyed roster entry added for `FsFeatStruc`/
`FsClosedValue`; no token added to `PHASE_5_ADMISSIBLE_REASONS`;
`contracts/fidelity-census.md` untouched (still the pre-existing dirty
working copy, byte-identical to what it was before this session -- confirmed
via `git diff` showing no new hunk from this session).

## Tests

New file `tests/unit/test_038_t119_owning_fields.py`, 28 tests, mirroring
`test_038_t081_owning_lists.py`'s structure with a monkeypatched roster (the
production roster being empty, a `NGOREME_LISTS`-style fixture needed a
synthetic stand-in to exercise the mechanism):

* `TestEmptyingTheProductionRosterRestoresTheArtifactByteForByte` -- the
  RULE-5-required pinning test: with the production (already-empty) roster,
  a realistic T119 shortfall shape produces zero lines.
* `TestALeakDetector::test_a_single_entry_roster_does_not_leak_to_an_unlisted_field`
  -- a one-entry roster does not produce a line for a different, unruled
  field in the same row.
* `TestTheCapCannotOutrunTheFieldsMeasuredShortfall` -- two directions: the
  row's room caps below the field's own loss, AND the field's own loss caps
  below unlimited row room.
* Plus the class/lookup disjointness, emitter, join, and artifact-shape
  tests mirroring the list-dimension suite's coverage.

**RULE 5, run both ways.** Stashed `census.py`/`models.py`/`census_cli.py`/
the schema (leaving only the new test file), ran the suite against that
pre-implementation state (= HEAD `6811894`): **all 28 tests failed**
(`AttributeError: module 'gramtrans.Lib.census' has no attribute
'OWNING_FIELD_RULINGS'`, etc.). Restored the changes: **all 28 pass**.

## Full suite

`tests/unit`: **3967 passed, 79 skipped, 14 xfailed** (baseline at 6811894
was 3939 passed; +28 is exactly the new file, 0 regressions). Ruff on the
three touched files: 161 -> 162 findings, the one new finding is `UP045`
(`Optional[dict]` style) on the new `owning_field_counts` dataclass field,
identical in kind to the 76 pre-existing `UP045` findings already in
`census.py`, including the sibling `owning_list_counts` field one line above
it -- not a new category of issue.

`tests/integration` (excluding `test_034_standalone_preview_live.py` per
STATUS.md convention): 767 passed, 75 skipped, 6 failed. **All 6 failures are
pre-existing live source drift, unrelated to this change** -- verified by
re-running the same tests with `census.py`/`models.py`/`census_cli.py`/the
schema stashed: the same 6 tests fail identically against unmodified
`6811894` (mbugwe/ngoreme `.fwdata` digests have moved off their pinned
values, matching the "mbugwe source drift found" note already recorded in
this branch's commit `02323b2`).

## Flags for the spec side

`specs/038-transfer-fidelity-gaps/contracts/census-artifact.schema.json` is a
spec artifact; its edit here (adding `$defs.classRow.owning_fields`) needs to
land on `main` per the repo's spec-vs-worktree convention. **Its main-side
copy is currently missing `owning_lists` entirely** (confirmed via `git show
main:...census-artifact.schema.json | grep owning_lists` -> no matches) --
i.e. this worktree's schema has been ahead of `main` since 6811894 landed
`owning_lists` here without a corresponding `main` commit, and this session's
`owning_fields` addition widens that same gap by one more property. Someone
needs to land the schema (and probably `fidelity-census.md`'s prose once it
is no longer deliberately dirty) on `main` before an external consumer
pinned to the committed schema can validate either dimension.

`contracts/fidelity-census.md` was left untouched, as instructed -- it is
still the pre-existing dirty working copy from before this session, and its
prose does not yet describe `owning_fields` (nor, per the flag above, does
`main`'s copy describe `owning_lists`).

## Files touched

* `src/gramtrans/Lib/census.py`
* `src/gramtrans/Lib/models.py`
* `src/gramtrans/census_cli.py`
* `specs/038-transfer-fidelity-gaps/contracts/census-artifact.schema.json`
* `tests/unit/test_038_t119_owning_fields.py` (new)
