# T045d implementation report -- the live field_source(cls, guid) reader

Branch: `035-fullsweep-fidelity`, worktree `GramTrans-035-fullsweep`, commit
`00627d6783b01fc67bf16f6656a2002875d82dcd` (pushed to origin).

## Files

- Added `debug/fullsweep/field_dispatch.py` -- `build_field_source(proj)`
  (the live `field_source(cls, guid)`), `CLASS_TO_ACCESSOR` dispatch table,
  `POSSIBILITY_GENERIC_CLASSES`, `MANDATORY_UNREACHABLE_CLASSES` /
  `DISCOVERED_UNREACHABLE_CLASSES` / `UNREACHABLE_CLASSES`,
  `UnreachableClassError`, `model_fields_for_class` (the generic MDC route),
  `is_dispatchable` / `partition_dispatchable`.
- Added `debug/probe_field_dispatch_t045d.py` -- the live, read-only smoke
  script (mirrors `probe_field_census_api.py`'s pattern; no `^Target` name
  refusal, per the task's explicit trap warning).
- Added `tests/unit/test_035_field_dispatch.py` -- 28 offline unit tests (no
  LCM), all passing.
- Modified `debug/fullsweep/__init__.py` -- registered the new module.

## Dispatch coverage

Against `coverage-floor.json`'s 66 present in-scope classes: **49
dispatchable** (45 via a named `FLExProject` accessor + 6 via a
directly-imported generic `PossibilityItemOperations` — actually 6 distinct
classes route through it, table total is 45+6=51 minus overlap none, net 49
dispatchable computed live), **6 unreachable** (3 mandated +
`ReversalIndex`/`ReversalIndexEntry`/`TextTag`, discovered), **11 genuinely
unmapped** and honestly reported as such by `partition_dispatchable` rather
than guessed (`CmFolder`, `CmPicture`, five `Fs*` structural-nested classes,
`LexExtendedNote`, `MoInflAffixSlot`, `PhBdryMarker`, `PunctuationForm`).

## The three mandated classes

`MoAdhocProhibGr` / `MoAlloAdhocProhib` / `MoMorphAdhocProhib` are refused
**before** any accessor lookup via `UnreachableClassError` (a
`CensusContractError` subclass) -- never an empty dict, never a bare crash.
Live-verified: calling `field_source` with each raises cleanly. Confirmed via
`lcm_casting.py:158-175` that `MorphRuleOperations.py:469` and
`adhoc_prohibition.py` branch on the wrong (never-existed-in-LCM) names
`MoAdhocProhibMorph`/`MoAdhocProhibAllomorph` for two of the three -- an
upstream flexicon defect, not fixed here, reported in the commit body.

## Live smoke run (Ejagham Mini, read-only, pyflexicon 4.8.0)

`PartOfSpeech` (model=69, syncable=4, compared=4, 5 objects), `LexEntry`
(model=46, syncable=9, compared=7), `PhPhoneme` (model=10, syncable=2) all
census cleanly. `LexSense` and `PhEnvironment` correctly **raise**
`CensusContractError` against two newly-discovered live flexicon defects
(a phantom `DoNotShowMainEntryInRC` key with no backing field, and
per-object syncable-surface disagreement caused by conditional key omission)
-- the census catching real defects, not a bug in this reader. `WfiWordform`
raises against the `GetMultiStringDict`-missing defect (see below). All 3
mandated classes raise `UnreachableClassError` as designed.

## Tests / regressions

28 new tests, all passing. Full `tests/unit` suite: 31 pre-existing failures
reproduce identically with these changes stashed out (confirmed via
`git stash`), so nothing here regressed anything.

## Findings beyond the brief (see commit body for full detail)

`self.project.GetMultiStringDict` is called by 7 `GetSyncableProperties`
overrides but is defined nowhere on `FLExProject` -- breaks
Text/CmFile/Segment/WfiGloss/WfiMorphBundle/WfiWordform unconditionally.
`FLExProject.Object(guid)` returns an `ICmObject`-typed proxy (same
static-wrapper-type class of bug as CLAUDE.md's `FeaturesOA` note); fixed
defensively here via an explicit `I<ClassName>(obj)` cast before every
dispatch call, verified live. `census_fields`' own "coverage locked to first
object" rule is in real tension with how `GetSyncableProperties` overrides
conditionally omit unset-field keys -- surfaced for the first time now that
a live `field_source` exists to exercise it; not this task's fix.
