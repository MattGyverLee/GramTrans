# T023 -- the real starter baseline, captured from a blank project

`specs/038-transfer-fidelity-gaps/contracts/starter-baseline.json`, 441 lines,
commit **`8189da2`** on `main`. Captured by the shipped instrument, not by hand.

## Non-destructive route -- nothing existing was touched

`backups\Ngoreme Target 2026-08-19 0831.fwbackup` (12 zip entries) was extracted
into a brand-new `C:\ProgramData\SIL\FieldWorks\Projects\GT Starter Capture 038`,
inner `.fwdata` renamed to match the folder. It opened through flexicon read-only
on the first attempt, so the authorised `Ejagham W Target` restore was **never
needed**.

**`Ngoreme Target` was never opened, read-only or otherwise, and never restored.**
Only its `.fwbackup` zip was read. Its `.fwdata` is unchanged at mtime
`Aug 19 09:30`, 10,319,152 bytes -- so T024's post-transfer evidence is intact.
`Ejagham W Target` was also untouched; it currently holds a `.fwdata.lock`, i.e.
something else has it open.

Temp project **deleted** after capture; no `GT*` project remains.

```
PYTHONPATH=src python -m gramtrans.census_cli capture-baseline \
    --project "GT Starter Capture 038" --out <scratchpad>/starter-baseline.json
```

## What was captured

`classes 72  objects 5869  flex_version 9.3.10  data_model_version 7000072`

- **`flex_version` matches the host**: stamped `9.3.10`; host
  `FieldWorks.exe` FileVersion `9.3.10.1448` -> short `9.3.10`;
  `fwglobals.short_version()` independently returns `9.3.10`.
- **`carries_natural_keys` is `false`, recorded truthfully and not forced.** 12
  measured classes hold objects the 035 roster gives no name key for: `CmAgent`,
  `CmAnthroItem`, `CmFolder`, `CmPossibility`, `CmSemanticDomain`, `LexEntryType`,
  `LexRefType`, `PhBdryMarker`, `PhCode`, `ReversalIndex`, `StText`, `StTxtPara`.
  Consequence verified **in code**, not merely asserted: `census_cli._row_for_entry`
  (`:716`/`:722`) stamps `starter_subtraction_basis: "baseline_gross"` on every row
  whenever a baseline is present. Round-tripping through
  `load_baseline_document` **recomputes** `carries_natural_keys=False` from
  `entries`, so a document cannot talk itself up.
- `class_count` **72** is the census's derived class list (CP-1), of which **17
  hold objects**. That does not conflict with the 36 populated classes in the whole
  `.fwdata`: the other 19 (`CmDomainQ` 7938, `StStyle` 54, `CmPossibilityList` 34,
  `FsFeatureSystem` 2, `LangProject` 1, ...) are simply not in the class list.
- **`PhPhoneme` 23 and `PartOfSpeech` 5 agree exactly** with the independent
  `.fwdata` read, confirming T024's `PhPhoneme` 41->64 as 23 starter + 41 source.
  15 of 17 non-zero classes match to the object.

Read-only proof: `.fwdata` sha256
`bc91a75bfb4bbcd078f947480766ccfb59ddf87c18633212fb808e0683b20e73`, identical at
extraction, as recorded in `fwdata_sha256`, and immediately before deletion; 5,763,628
bytes unchanged. No `.bak`, `.lock` or `.fwstub` created.

## THE FINDING -- LCM repositories are polymorphic, so class rows are NOT disjoint

The 2 of 17 classes that disagreed with the direct read identify the cause exactly.
`census.objects_in_class` counts via `handle.ObjectsIn(I<Class>Repository)`, and
LCM's `AllInstances()` **includes subclasses**:

| class | instrument | own objects | difference |
|---|---|---|---|
| `CmPossibility` | **3014** | 302 | +2712 = the entire subtree |
| `LexEntryType` | **14** | 11 | +3 `LexEntryInflType` |

3014 = 302 own + 1792 `CmSemanticDomain` + 859 `CmAnthroItem` + 19 `MoMorphType`
+ 5 `PartOfSpeech` + 11 `LexEntryType` + 3 `LexEntryInflType` + 7 `LexRefType`
+ 15 `CmAnnotationDefn` + 1 `CmPerson` -- to the object.

This is inherent LCM behaviour applied **consistently**, so the subtraction between
two projects measured by the same instrument is not corrupted. But the consequences
for the census's own claims are real:

- **The 74 rows overlap.** One `PartOfSpeech` object is counted in the
  `PartOfSpeech` row *and* the `CmPossibility` row.
- **The emitted object total double-counts** (`objects 5869`).
- **A per-class `difference` is ambiguous** for any class with subclasses.
- **The match-basis invariant**
  `identity + natural_key + created_new + unmatched_reported == source_count`
  runs against a polymorphic `source_count`.
- The "no cross-class netting, ever" guarantee -- enforced by signature in T019 --
  is undermined not by netting logic but by the counts themselves overlapping.

`census.py` documents this nowhere. **Queued as T023b**: filter to exact class so
each object lands in exactly one row, document the polymorphism at the counting
site, and **recapture this baseline**, whose `CmPossibility`/`LexEntryType` counts
are inflated.

**T024's sanity pairs are unaffected** -- `MoStemMsa`, `PhPhoneme` and
`MoAffixAllomorph` are leaf classes.

## Two caveats on this artifact

1. `instrument.gramtrans_dirty` is **`true`**, which is honest rather than a
   defect: T023a had `census.py` modified at capture time. `gramtrans_sha` is
   `73b80c3`. A reproducibly-stamped baseline wants a re-run after T023a and T023b
   land -- and T023b **changes the counts**, so a recapture is required anyway.
2. `project_name` is `"GT Starter Capture 038"`, a project that no longer exists.
   Truthful provenance, deliberately not hand-edited; the commit message records
   that it derives from `backups\Ngoreme Target 2026-08-19 0831.fwbackup`. The
   schema has no field for resolving the originating project, so one would have to
   be added if a consumer needs it.
