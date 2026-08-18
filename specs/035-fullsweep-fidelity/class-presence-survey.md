# Class-presence survey -- the coverage floor's measured input (T044)

**Run**: 2026-08-19, read-only, no LCM
**Method**: `debug/fullsweep/coverage.py::scan_class_presence` -- each project's
`.fwdata` read as a binary text stream, counting `<rt class="X">` rows. No
project was opened through LCM, no lock was taken, nothing was written.
**Root**: `C:\ProgramData\SIL\FieldWorks\Projects`
**Scanned**: 90 projects. `Target` was skipped -- the disposable target pool is
this harness's own writes, not corpus evidence (same FR-002 refusal
`corpus.py` applies to sources).
**Roster**: the 69 in-scope classes of
[contracts/coverage-floor.json](./contracts/coverage-floor.json) -- the union of
[object-inventory.md](./object-inventory.md) TABLE 1 (65 primary classes the
engine creates) and TABLE 2's referenced-only classes, minus the two abstract
bases.

---

## 1. What this measurement was for

Research [D-07](./research.md) records the coverage limit as "appendix, stratum,
and one phonological-rule subclass exist in no project on this machine" -- but
names only two of the three. T044 has to pin all three, because FR-137 requires
each to report `NOT-EVALUATED` and never clean. Pinning by inference was not an
option: the floor is the only thing standing between a never-attempted class and
a silent zero, so a wrong name there would leave a real gap invisible while
loudly reporting a fictional one.

So the absence was measured rather than inferred.

## 2. Result -- the three corpus-wide absences

| Class | D-07's wording | Instances | Projects |
|---|---|---|---|
| `LexAppendix` | "appendix" | **0** | 0 |
| `MoStratum` | "stratum" | **0** | 0 |
| `PhSegmentRule` | "one phonological-rule subclass" | **0** | 0 |

**This corrects a guess that would have been wrong.** The obvious candidate for
the unnamed phonological-rule subclass is `PhMetathesisRule` -- the exotic one,
and one of the two [object-inventory.md:278](./object-inventory.md) records as
absent from Ejagham Mini. It is **present**: 4 instances across 4 projects. The
class absent corpus-wide is `PhSegmentRule`, which is concrete
(`IPhSegmentRuleFactory` exists in liblcm 11.0.0) and is dispatched by
`Lib/categories.py:8544`, yet no project on this machine owns one. Its siblings
are both present: `PhRegularRule` 398/33, `PhMetathesisRule` 4/4.

## 3. Two classes deliberately kept OFF the roster

`MoForm` and `MoMorphSynAnalysis` also scan to zero, for a categorically
different reason: they are **abstract LCM base classes**. Neither
`IMoFormFactory` nor `IMoMorphSynAnalysisFactory` exists in liblcm 11.0.0
(verified via FLExToolsMCP), so no `.fwdata` can ever carry a row for either --
every instance is serialized under a concrete subclass (`MoStemAllomorph` /
`MoAffixAllomorph`; `MoStemMsa` / `MoInflAffMsa` / `MoDerivAffMsa` /
`MoUnclassifiedAffixMsa`), and all six of those are present.

They are recorded in the floor's `excluded_not_measurable` block **with the
reason**, not silently omitted. Conflating "absent by construction" with
"absent from this corpus" would put two permanent `NOT-EVALUATED` rows on every
artifact forever, which teaches a reader to skim past the bucket -- the exact
habit FR-136 exists to prevent.

## 4. The thin tail worth knowing about

Absence is the loud case; near-absence is the quiet one. These classes are
present but so thinly that a corpus subset can easily contain none of them, and
a subset run that skips them must report `NOT-EVALUATED`, not clean:

| Class | Instances | Projects |
|---|---|---|
| `LexExtendedNote` | 2 | 2 |
| `TextTag` | 2 | 2 |
| `MoAdhocProhibGr` | 99 | 4 |
| `MoExoCompound` | 12 | 4 |
| `PhMetathesisRule` | 4 | 4 |
| `MoAlloAdhocProhib` | 326 | 5 |
| `CmPicture` | 31 | 7 |
| `MoEndoCompound` | 20 | 13 |

`LexExtendedNote` and `TextTag` at 2 instances / 2 projects each are the
sharpest constraint the three-axis corpus selection of FR-190/T049 has to
respect: drop those two projects and two in-scope classes silently stop being
covered.

## 5. Full presence table (66 of 69 in-scope classes)

Ascending by project count.

| Class | Instances | Projects |
|---|---|---|
| `LexExtendedNote` | 2 | 2 |
| `TextTag` | 2 | 2 |
| `MoAdhocProhibGr` | 99 | 4 |
| `MoExoCompound` | 12 | 4 |
| `PhMetathesisRule` | 4 | 4 |
| `MoAlloAdhocProhib` | 326 | 5 |
| `CmPicture` | 31 | 7 |
| `MoEndoCompound` | 20 | 13 |
| `MoMorphAdhocProhib` | 94 | 15 |
| `MoStemName` | 41 | 16 |
| `LexEtymology` | 1035 | 17 |
| `CmFile` | 13377 | 20 |
| `LexReference` | 1665 | 22 |
| `MoUnclassifiedAffixMsa` | 882 | 22 |
| `PhFeatureConstraint` | 667 | 23 |
| `MoInflClass` | 67 | 25 |
| `ReversalIndexEntry` | 76187 | 26 |
| `PhSequenceContext` | 393 | 28 |
| `PhSimpleContextSeg` | 741 | 28 |
| `PhSimpleContextBdry` | 293 | 29 |
| `PhSimpleContextNC` | 2466 | 29 |
| `LexPronunciation` | 33729 | 31 |
| `PhNCFeatures` | 1117 | 32 |
| `PhRegularRule` | 398 | 33 |
| `PhSegRuleRHS` | 400 | 33 |
| `MoDerivAffMsa` | 545 | 36 |
| `LexExampleSentence` | 29552 | 38 |
| `LexEntryRef` | 13188 | 47 |
| `FsComplexFeature` | 142 | 50 |
| `PhEnvironment` | 692 | 57 |
| `MoInflAffixSlot` | 842 | 62 |
| `MoInflAffixTemplate` | 519 | 62 |
| `WfiGloss` | 43811 | 63 |
| `FsClosedValue` | 36906 | 65 |
| `PunctuationForm` | 37783 | 65 |
| `FsFeatStruc` | 20469 | 66 |
| `FsFeatStrucType` | 250 | 66 |
| `MoInflAffMsa` | 3374 | 67 |
| `CmAnthroItem` | 59157 | 68 |
| `FsClosedFeature` | 882 | 68 |
| `FsSymFeatVal` | 2458 | 68 |
| `Segment` | 394840 | 70 |
| `WfiAnalysis` | 177364 | 70 |
| `WfiMorphBundle` | 527954 | 70 |
| `WfiWordform` | 205382 | 72 |
| `MoAffixAllomorph` | 5900 | 73 |
| `PhNCSegments` | 335 | 76 |
| `Text` | 1281 | 78 |
| `MoStemAllomorph` | 134463 | 82 |
| `MoStemMsa` | 121779 | 82 |
| `LexEntry` | 130251 | 84 |
| `LexSense` | 136864 | 84 |
| `CmSemanticDomain` | 159499 | 87 |
| `CmAgent` | 360 | 88 |
| `CmFolder` | 121 | 88 |
| `CmPossibility` | 28948 | 88 |
| `LexEntryInflType` | 367 | 88 |
| `LexEntryType` | 1099 | 88 |
| `LexRefType` | 703 | 88 |
| `MoMorphType` | 1710 | 88 |
| `PartOfSpeech` | 1544 | 88 |
| `PhBdryMarker` | 180 | 88 |
| `PhPhoneme` | 2813 | 88 |
| `ReversalIndex` | 154 | 88 |
| `StText` | 78614 | 88 |
| `StTxtPara` | 122501 | 88 |
## 6. Reproducing this

```python
from debug.fullsweep import coverage
floor = coverage.load_coverage_floor()
survey = coverage.scan_class_presence(
    r"C:\ProgramData\SIL\FieldWorks\Projects", classes=floor.in_scope_classes)
report = coverage.classify_coverage(floor, survey=survey)
print(report.counts())          # never_attempted == 3
print(report.reports_clean)     # False -- 66 clean classes do not close a gap
```

The scan is O(bytes) over ~4.6 GB of `.fwdata` and takes a few minutes. It is
line-oriented on purpose: a chunked read can split `<rt class="...` across a
buffer boundary and undercount, and an undercount here would manufacture a
corpus-wide absence out of nothing.
