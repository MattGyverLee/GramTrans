# T023b -- the census counts the exact class, not the LCM subtree

- Code: **`3973fa0`** on `038-transfer-fidelity-gaps` -- `Lib/census.py` + 16 tests
  appended to the existing `tests/integration/test_object_census.py`.
- Recaptured baseline: **`69f4097`** on `main` --
  `specs/038-transfer-fidelity-gaps/contracts/starter-baseline.json`.

## The arithmetic: DIRECT subclasses, not all

`exact(C) = cumulative(C) - sum(cumulative(D) for D in DIRECT subclasses of C)`

**Direct, not all.** Each direct subclass's cumulative count already contains its own
descendants, so subtracting every subclass double-subtracts each grandchild and
reports `CmPossibility` as **299** instead of 302. There is a test pinning that
off-by-three.

Subclass names come from LCM's metadata cache at run time, never a local table.
`CmPossibility` is clid 7 with **12 direct subclasses**, while `GetAllSubclasses`
returns 14 including `LexEntryInflType` -- which is exactly why direct-only is
required.

## The pythonnet trap, hit and handled

`IFwMetaDataCacheManaged` (in `SIL.LCModel.Infrastructure`) exposes `GetClassIds()`,
`GetClassId(name)`, `GetClassName(clid)`, `GetDirectSubclasses(clid)` and
`GetAllSubclasses(clid)` -- all plain returns, **no `out` params**, so usable from
pythonnet directly.

But `LcmCache.MetaDataCacheAccessor` is typed **`IFwMetaDataCache`**, whose interface
does **not** declare `GetDirectSubclasses`; only the managed subinterface does. The
raw proxy *happens* to answer it on liblcm 11.0.0 -- **precisely the coincidence
CLAUDE.md's flexicon 4.5.0 `FeaturesOA` note records going the other way**, where
pythonnet resolved against the static wrapper type and `hasattr` was unconditionally
False, killing a feature while 1467 tests passed. So `metadata_cache()` attempts
`IFwMetaDataCacheManaged(accessor)` **first** and uses the raw accessor only if it can
be shown to answer.

`ICmObject` declares both `ClassID: Int32` and `ClassName: String`; being on the root
interface they resolve on every proxy regardless of which repository interface
produced it, and they report the **runtime** class. `ClassName` is used for the
enumeration filter -- readable in error messages, no id/name round-trip.
(`ServiceLocator.GetInstance[...]` is **not** available: `ILcmServiceLocator` has no
`GetInstance` attribute under pythonnet.)

## T017's efficiency contract survives -- and the fix is FASTER

One `repository.Count` per class plus one per direct subclass, **memoised across the
whole pass**, so a class that is several classes' subclass is read once. No
per-object re-query and **no object enumerated at all** on the healthy path.

Timed over all 74 rows of the starter: **0.26 s** (0.22 s counts + 0.04 s metadata)
against **0.37 s** for the enumerate-and-filter alternative.

The O(n) fallback (enumerate the subtree once, filter on `ClassName`) exists only for
an unreachable metadata cache, and is **recorded, never silent**:
`ClassCounts.count_basis` per class plus `ClassCounts.enumerated_classes`. On the live
run it was empty -- all 74 classes used `repository_subtraction`.

## Instrument vs `.fwdata`: 74/74 agree

| class | cumulative | exact | `.fwdata` | |
|---|---|---|---|---|
| `CmSemanticDomain` | 1792 | 1792 | 1792 | agree |
| `CmAnthroItem` | 859 | 859 | 859 | agree |
| **`CmPossibility`** | **3014** | **302** | **302** | **was wrong** |
| `StTxtPara` | 86 | 86 | 86 | agree |
| `PhCode` | 25 | 25 | 25 | agree |
| `PhPhoneme` | 23 | 23 | 23 | agree |
| `MoMorphType` | 19 | 19 | 19 | agree |
| `StText` | 12 | 12 | 12 | agree |
| **`LexEntryType`** | **14** | **11** | **11** | **was wrong** |
| `LexRefType` | 7 | 7 | 7 | agree |
| `PartOfSpeech` | 5 | 5 | 5 | agree |
| `CmAgent` | 4 | 4 | 4 | agree |
| `LexEntryInflType` | 3 | 3 | 3 | agree |
| `PhBdryMarker` | 2 | 2 | 2 | agree |
| `PhNCSegments` | 2 | 2 | 2 | agree |
| `CmFolder` | 1 | 1 | 1 | agree |
| `ReversalIndex` | 1 | 1 | 1 | agree |

The other 57 in-list classes hold 0 and read 0. **Exact counts sum to 3154 against
cumulative 5885 -- the old instrument double-counted 2731 objects.**

`ReversalIndex` is a 17th populated in-list class the earlier ground-truth list
omitted. Nine populated classes are **not in the 74-class list at all** and so are not
measured: `CmDomainQ` 7938, `StStyle` 54, `CmPossibilityList` 34, `CmRow` 30,
`CmCell` 29, `CmFilter` 26, `CmAnnotationDefn` 15, `CmAgentEvaluation` 8,
`FsFeatureSystem` 2. Two of those matter to the defect: `CmAnnotationDefn` and
`CmPerson` were being counted **inside the `CmPossibility` row** despite having no row
of their own.

## The defect was not only miscounting

**`objects_in_class` shared it, and that is worse than a wrong total.** It fed T018's
duplicate grouping 3014 objects across nine classes for `CmPossibility`, so a
natural-key collision between a `PartOfSpeech` and a `CmSemanticDomain` would have
been reported as a duplicate **`CmPossibility`** -- a fabricated cross-class
duplicate. Now exact-filtered. `census_cli.natural_keys_for` (`census_cli.py:470`)
picks this up through the same call with **no edit to that file**.

Other polymorphism dependencies checked:

- `split_counts` / `count_by_feature_system` count through
  `LangProject.<system>OA.TypesOC`, not a repository -- already exact, untouched.
- `object_count_total` is `ICmObjectRepository.Count`, whose subtree *is* the project
  (11300, matching the `.fwdata`'s 11300 `<rt>` rows), so it is correct as-is and is
  now a genuine cross-check.
- Nothing wanted subtree counts, but the raw reading is kept under an unmistakable
  name rather than discarded: `counts` / `count_for()` are **exact** and drive every
  row, difference and total; `cumulative_counts` / `cumulative_count_for()` are the
  polymorphic subtree and are read by nothing in the accounting. A 45-line block at
  the counting site documents them as non-interchangeable and carries the measured
  3014/302 evidence, so a future "simplification" back to `ObjectsIn` has to argue
  with the numbers.

New failure modes are named rather than approximated: a subclass whose count cannot be
read makes the **parent** unmeasurable (publishing the subtree total is the defect),
and a negative subtraction is recorded unmeasurable rather than emitted as a negative
count. Both tested.

## Baseline before/after -- 2 of 72 entries changed

- `CmPossibility` **3014 -> 302** (-2712)
- `LexEntryType` **14 -> 11** (-3)
- baseline object total **5869 -> 3154**

70 entries byte-identical. `class_count` (72), the class set, `data_model_version`
(7000072), `flex_version` (9.3.10) and `fwdata_sha256` (`bc91a75b...`) all unchanged
-- same starter, measured correctly. `carries_natural_keys` stays `false`, not forced.

**`instrument.gramtrans_dirty` is now `false`** (was `true`), `gramtrans_sha`
`3973fa0`. To achieve that, the capture ran from a **temporary detached git worktree
at `3973fa0`** with `git status --porcelain` empty, because the shared feature
worktree was dirty with concurrent T023c work. That temp worktree was removed.
`project_name` is `GT038 T023b Scratch`, not hand-edited.

## Tests

`test_object_census.py` **136 passed / 0 failed** (112 at briefing, +8 from T023c,
+16 mine). `tests/unit` **27 failed / 2624 passed** -- byte-identical to baseline.

**No test had encoded the polymorphic counts** -- nothing in `tests/` referenced
`count_classes`, `ClassCounts`, `objects_in_class`, `ObjectCountFor` or `ObjectsIn` at
all, so there was no conflict and nothing was rewritten to match the new code.

The 16 new tests use fakes whose `ObjectCountFor` is deliberately polymorphic and
reproduces the measured **3014/302** and **14/11** exactly, so a regression fails with
the same numbers that found the defect. They cover exact partitioning, the
grandchild-subtracted-once case, leaf classes unaffected, cumulative retained
separately, one-read-per-class with zero enumerations (T017), the recorded fallback,
unreadable-subclass to unmeasurable, negative subtraction refused, `objects_in_class`
filtering and single enumeration, an object refusing to name its class, and a
source-level check that the polymorphism stays documented.

Ruff: rule-for-rule identical before and after (1 `I001`, 6 `SIM102`, 1 `SIM105`, all
pre-existing); only delta is `UP045` on new `Optional[...]` annotations, matching the
module convention.

## Safety

**`Ngoreme Target` was never opened, never write-enabled, never restored** -- mtime
still `Aug 19 09:30`, predating this session's work, so T024's evidence is intact.

Throwaway `GT038 T023b Scratch` was extracted from
`backups/Ngoreme Target 2026-08-19 0831.fwbackup` into a **new** folder, opened
read-only, and **deleted**. All four digests identical:
`bc91a75bfb4bbcd078f947480766ccfb59ddf87c18633212fb808e0683b20e73` at extraction,
before open, after close, at teardown; `read_project` independently reported
`digest_unchanged: True`.

## Concurrency, again

T023c committed while T023b's changes were staged, and its commit initially swallowed
the entire `census.py` change under its own message. It rewrote that commit
(`f1995e0` -> `4d3de35`), releasing the work back into the tree, and T023b committed
cleanly as `3973fa0` on top. Final history is correct and the tasks are properly
separated -- but **T023b's test additions were clobbered once** by the other agent
overwriting the shared test file from its own buffer, and had to be re-appended.

`tests/integration/test_object_census.py` is a genuine contention point. Serialize, or
give each agent its own worktree.
