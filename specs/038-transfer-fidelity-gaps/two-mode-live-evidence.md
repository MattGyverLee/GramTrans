# T024c/T024e -- live two-mode full-copy evidence

Captured 2026-08-19 by `debug/two_mode_delta.py` against a target restored blank
from `backups/Ngoreme Target 2026-08-19 0831.fwbackup` (0 LexEntry, 23 PhPhoneme,
5 PartOfSpeech -- a genuine starter). Source `Ngoreme FLEx`: **119 classes,
205,979 objects**. Every write went to the allowlisted throwaway `Ngoreme Target`;
the source was opened read-only.

## Headline: the transfer persists NOTHING, and reports success

Three runs, all identical in outcome:

| run | WS mapping | before | after | added (report) | persisted |
|---|---|---|---|---|---|
| forceall | default-vernacular only | 11,300 | 11,300 | 2,243 | **0** |
| filtered | default-vernacular only | 11,300 | 11,300 | 2,243 | **0** |
| forceall | COMPLETE (en/swh/ngq) | 11,300 | 11,300 | 2,243 | **0** |

`RunReport` carried `error: None`, `leaf_failed: 0` (forceall), and non-zero
`added` across **19 of 20 categories** -- 41 phonemes, 48 natural classes, 21
phonological rules, 26 gram categories, 19 phonological features, and so on --
while the destination `.fwdata` was left byte-for-byte unchanged.

### Cause

`CloseProject()` -- which `gramtrans.py:282` documents as *"the ONLY disk-write on
this path"* -- throws, so LCM discards the entire unit of work:

```
ArgumentOutOfRangeException: Specified argument was out of the range of valid values.
Parameter name: handle
   at SIL.LCModel.Core.WritingSystems.WritingSystemManager.Get(Int32 handle)
   at SIL.LCModel.DomainImpl.MultiUnicodeAccessor.ToXml(...)
   at SIL.LCModel.DomainImpl.MoInflAffixSlot.ToXMLStringInternal(XmlWriter writer)
   at SIL.LCModel.Infrastructure.Impl.XMLBackendProvider.Commit(...)
   at SIL.LCModel.Infrastructure.Impl.UnitOfWorkService.Save()
```

One `MoInflAffixSlot` multistring holds a writing-system handle the target's
`WritingSystemManager` cannot resolve. Because it fails inside `Commit`, **all
2,243 adds roll back together** -- a single bad WS handle on a single object
discards the whole transfer.

### It is swallowed in production too

`gramtrans.py:302-313` wraps the same call:

```python
try:
    target.CloseProject()
    report.Info("[GramTrans] Target project closed.")
except Exception as exc:  # noqa: BLE001
    report.Warning(f"[GramTrans] Could not close target project: {exc}")
```

A total rollback is downgraded to a warning line beside a RunReport claiming
2,243 additions. This is not a harness artifact -- the harness reproduces
production's own handling.

### It is NOT an incomplete-mapping artifact

Run 3 supplied a complete mapping -- `en->en`, `swh->swh` (`create_in_target=True`),
`ngq->ngq` -- covering every source writing system. **Identical failure.**

Measured writing systems, which also show why handles cannot be copied across
projects:

| project | handles |
|---|---|
| `Ngoreme FLEx` | `en`=999000002, `swh`=999000012, `ngq`=999000008 |
| `Ngoreme Target` | `en`=999000001, `ngq`=999000002 |

**Handles are per-project and not portable**: `999000002` is `en` in the source
and `ngq` in the target. A handle carried across unchanged is therefore either
unresolvable (throws, as here) or silently resolves to the WRONG writing system.

## The mode contrast (T024e) behaved as designed

The preselection heuristic fired exactly where predicted -- orphan natural
classes, and only those:

| mode | NATURAL_CLASSES added | unchecked by preselection | leaf_failed |
|---|---|---|---|
| forceall | 48 | 0 (heuristic bypassed) | 0 |
| filtered | 36 | 11 | 1 |

`36 + 11 + 1 == 48` reconciles the two modes exactly, confirming that empty
pick-sets do mean transfer-all and that `collapse_phonology` trims only the
non-preselected rows. **The one `leaf_failed` in filtered mode is unexplained
and needs its own investigation** -- it is not accounted for by the heuristic.

The `after_forceall - after_filtered` assertion could NOT be evaluated: both
runs persisted zero objects, so both after-sets are the untouched starter.

## Also observed, not yet investigated

- **`dropped_items: 10,749`** in every run -- the never-silent channel is
  carrying a very large payload. Against 205,979 source objects this needs a
  breakdown by `owner_kind`/reason before any of it is read as expected.
- **`identity_substituted: 0`** on every run. Against a starter target holding
  23 phonemes and 5 POS that share names with source objects, zero substitutions
  means the natural-key match path did not engage at all.

## Reproduce

```
python debug/two_mode_delta.py \
  --source "Ngoreme FLEx" --destination "Ngoreme Target" \
  --backup "backups/Ngoreme Target 2026-08-19 0831.fwbackup" \
  --repo <worktree> --out result.json \
  --allowlist "Ngoreme Target" --modes forceall filtered
```

`GT_WS_FULL=1` selects the complete writing-system mapping.


---

# RESOLVED (T024g) -- root cause and post-fix measurement

## Root cause: source writing-system handles written into the target

Three sites enumerated the SOURCE writing systems and passed those handles
straight to `set_String` on a TARGET multistring:

| site | function | object |
|---|---|---|
| `categories.py:7521` | `slots_execute_action` | `IMoInflAffixSlot` |
| `categories.py:2225` | `stem_names_execute_action` | `IMoStemName` |
| `transfer.py:2561` | `_execute_gold_reserved_merge` | OW-MERGE fill |

Because handles are per-project, this has two failure modes. A handle with no
target counterpart (`swh`=999000012) reaches `MultiUnicodeAccessor.ToXml`,
`WritingSystemManager.Get` throws, and LCM discards the whole unit of work --
the observed total rollback. A handle that *does* exist but means something
else (`999000002` = `en` in source, `ngq` in target) resolves **silently to the
wrong writing system**, which raises nothing at all.

The correct helper already existed and was in use at six other call sites:
`_copy_multistrings_ws_mapped` (`categories.py:579`) translates source handle ->
target handle by (mapped) WS Id and skips a source WS with no target
counterpart -- *"so a string is never written to a wrong/absent handle"*. The
three sites above had simply never adopted it.

## Post-fix measurement (same pair, same blank restore, force-all)

| | before fix | after fix |
|---|---|---|
| destination objects | 11,300 (unchanged) | **28,354** |
| destination classes | 36 | **74** |
| persist error | ArgumentOutOfRangeException | **none** |

### Grammar-scope classes, by GUID set

| class | source | arrived | missing | invented |
|---|---|---|---|---|
| MoStemMsa | 1949 | 1939 | 10 | 0 |
| MoInflAffMsa | 134 | 134 | 0 | 0 |
| MoInflAffixSlot | 19 | 19 | 0 | 0 |
| MoInflAffixTemplate | 13 | 13 | 0 | 0 |
| PartOfSpeech | 26 | 26 | 0 | 0 |
| PhPhoneme | 41 | 41 | 0 | 0 |
| PhNCFeatures | 41 | 41 | 0 | 0 |
| PhNCSegments | 7 | 7 | 0 | 0 |
| PhRegularRule | 21 | 21 | 0 | 0 |
| PhEnvironment | 9 | 9 | 0 | 0 |
| FsSymFeatVal | 90 | 90 | 0 | 0 |
| MoAffixAllomorph | 146 | 146 | 0 | 0 |
| MoStemAllomorph | 2136 | 2136 | 0 | 0 |
| **PhCode** | 89 | **0** | 89 | 0 |
| **FsClosedValue** | 2540 | 20 | 2520 | **855** |
| **FsFeatStruc** | 1771 | 59 | 1712 | **41** |
| **FsComplexValue** | 825 | **0** | 825 | 0 |
| MoAffixProcess | 1 | 0 | 1 | 0 |
| PhSequenceContext | 13 | 12 | 1 | 0 |
| PhSimpleContextNC | 47 | 46 | 1 | 0 |

**This invalidates T024's premise.** `MoStemMsa` 1949->0, `MoInflAffixTemplate`
13->0 and `MoInflAffixSlot` 19->0 -- the "catastrophic" losses T024 was built to
prove the census could see, and which it read as *"the lexicon arrived STRIPPED
OF ITS MORPHO-SYNTACTIC ANALYSES"* -- were **entirely an artifact of this
rollback**, not evidence of missing transfer logic. All three now arrive
complete and GUID-preserved.

The whole-database totals (arrived 18,105 / missing 187,874) are dominated by
classes GramTrans does not claim -- `ChkRef` 86,611, `Segment` 28,926,
`WfiWordform` 8,181, `CmDomainQ` 7,939, `ScrTxtPara` 7,923, `ChkTerm` 6,428 and
the rest of the text/scripture/discourse layer. Those are out of scope, not
lost; separating them is still what a run report would buy (T024d).

## Remaining in-scope gaps -- carried to T024h (ANSWERED below)

- **`FsClosedValue` 855 invented / `FsFeatStruc` 41 invented.** Feature-structure
  values are being RECREATED with fresh GUIDs instead of GUID-preserved. Content
  may well be correct; identity is not.
- **`PhCode` 89 -> 0.** All 41 phonemes arrive, none of their grapheme codes do.
- **`FsComplexValue` 825 -> 0.**
- `MoStemMsa` 10, `MoAffixProcess` 1, `PhSequenceContext` 1, `PhSimpleContextNC` 1.

## Note on the test baseline

The `038-transfer-fidelity-gaps` worktree carries **27 pre-existing unit-test
failures** unrelated to this change (identical set before and after the fix).
That baseline should be repaired before it hides a real regression.


---

# RESOLVED (T024c / T024e / T024h) -- measured 2026-08-19, post-T024g

Everything below comes from runs this session PRODUCED rather than from
projects as they sat on disk. Three artifacts back it:

- `tests/integration/_snapshots/two-mode-038-ngoreme.json` -- the trimmed
  two-mode result (`debug/two_mode_delta.py`, `GT_WS_FULL=1`), asserted by
  `tests/integration/test_038_two_mode_and_tallies.py` (12 tests).
- `TestT024cTheSanityCheckProducesItsOwnTransfer` in
  `tests/integration/test_object_census.py` (6 tests, `GRAMTRANS_E2E=1`).
- `tests/integration/test_038_phon_empty_drop_live.py` (12 tests, read-only).

FieldWorks held `Ngoreme FLEx` open at the start of the session and was closed
gracefully before the write runs. Measured incidentally and worth recording: a
**read-only** flexicon open of a project FieldWorks holds open SUCCEEDS -- the
existing T024 block censuses `Ngoreme FLEx` under a live lock. Only the
DESTINATION's lock is disqualifying, because a restore cannot replace a locked
`.fwdata`. The guard in T024c is asymmetric for that reason.

## T024c -- the sanity check now produces the transfer it measures

`restore(0831 backup)` -> `census run --pre-transfer` -> full transfer
(`exclude=frozenset()`, full WS mapping, RunReport persisted) ->
`census run --baseline pre.json --run-report report.json`.

Destination **0 -> 20,202** counted objects across the census class list; the
run report claims 2,243 additions across 20 categories and the destination
grew, so T024g stays fixed.

**30 rows carry an unaccounted difference.** They split cleanly, and the split
is the point -- a count-based census could not make it:

| out of scope (text / lexicon layer GramTrans does not claim) | |
|---|---|
| `Segment` | -26,666 |
| `WfiWordform` | -8,029 |
| `CmTranslation` | -7,923 |
| `StTxtPara` | -5,568 |
| `StText` | -4,903 |
| `WfiMorphBundle` | -4,516 |
| `PunctuationForm` | -3,993 |
| `CmSemanticDomain` | -1,792 |
| `WfiAnalysis` | -1,472 |
| `WfiGloss` | -593 |
| `CmPossibility` | -398 |
| `Text` / `LexReference` / `LexRefType` / `ReversalIndex` / `CmAgent` / `CmFile` / `CmFolder` | -14 / -5 / -7 / -2 / -4 / -2 / -1 |

| IN SCOPE -- these are the feature's business | |
|---|---|
| `FsFeatStruc` | **-1,671** |
| `FsClosedValue` | **-1,665** |
| `PhCode` | **-89** |
| `PhFeatureConstraint` | **-47** |
| `MoMorphType` | -19 |
| `LexEntryType` | -12 |
| `MoStemMsa` | -10 |
| `LexEntryInflType` / `PhBdryMarker` | -2 / -2 |
| `MoAffixProcess` / `PhSequenceContext` / `PhSimpleContextNC` | -1 each |

### The verdict is structurally capped until Phase 4 lands

The run report **was** supplied and **not one row** reached the
`baseline_matched` basis. All 75 rows stayed on `baseline_gross`, 28 of them
capped, 69,399 unexplained objects turned into accounting, verdict
`CENSUS_ACCOUNTED` / exit 8.

The chain, measured end to end:

```
Phase 4 (T028-T037) unlanded
  -> no PlannedAction carries a match_basis at all   (plan: 2243x "<no match_basis>")
  -> RunReport.matched_to_source.by_object_class == {}   (total 1806, complete False)
  -> T024d-b forbids baseline_matched on every row
  -> fidelity-census.md 5.2 caps the verdict at CENSUS_ACCOUNTED
```

This is T024d behaving exactly as specified -- *"an absent tally is no evidence
the matcher ran, never a zero"* -- not a defect in it. But it means
**`CENSUS_CLEAN` and the phase gates T038/T039 are unreachable until Phase 4
lands**, and an operator who supplies `--run-report` and still sees a capped
verdict now has the reason written down. `test_no_row_reaches_the_matched_basis_before_phase_4`
is the tripwire: it FAILS the moment `by_object_class` becomes non-empty.

## T024e -- the two modes, and the exact difference

Both modes restored from the same blank backup and both persisted:
force-all **11,300 -> 28,354**, filtered **11,300 -> 28,322**.

The raw contrast is 917 objects, and reading that as the mode difference would
be wrong. Three classes -- `FsClosedValue` (855/842), `FsFeatStruc` (48/41),
`CmTranslation` (2/2) -- appear on **both** sides. A GUID only-in-force-all
beside a different GUID only-in-filtered is not a mode difference at all: those
objects are **re-minted with fresh GUIDs on every run**. That independently
confirms the "invented" finding above and is why the comparison excludes them.

Excluding the re-minted classes the difference is **12 objects, all natural
classes**, and:

- **11 are exactly the rows the orphan-NC heuristic left unchecked.** Nothing
  in the filtered run is missing from force-all, and nothing the heuristic
  claimed failed to appear. The heuristic honours its claim in both directions.
- **1 is not a preselection decision at all**:
  `ad5738e0-2a61-4e42-8f95-8db24e7b9881`.

## T024h -- the two bare tallies, broken down

### (a) `dropped_items: 10,749`, by (owner_kind, reason)

| owner_kind | count | dominant reason |
|---|---|---|
| `Segment` | 6,951 | alignment token had no copied target referent |
| `MoForm` | 2,193 | shared-default diverged |
| `LexSense` | 1,531 | source writing system `999000004` absent in target |
| `ConfigView` | 56 | 7 custom fields + `swh` absent in target |
| `LexEntry` | 10 | **9x `MoStemMsa.PartOfSpeechRA` empty on source** |
| `LexEntryRef` | 5 | shared-default diverged |
| `PhSegRuleRHS` | 3 | **`Req`/`ExclRuleFeatsRC` item absent from target** |

The top three are 99.4% of the total and are the out-of-scope text/lexicon
layer -- so the number is **ordinary**, which the count alone could not say.
The in-scope residue is 13 records and every one is named: nine senses lose
their part-of-speech analysis (US1 / FR-002), three phonological-rule
right-hand sides *"silently lost this conditioning feature/POS restriction"*
(consistent with `PhFeatureConstraint` -47 above), one `MoAffixProcess` is
`NEEDS_MANUAL` by design.

`LexSense` 1,531 is worth its own note: writing system `999000004` was
unmapped **even under `GT_WS_FULL=1`**, whose mapping enumerated only
`en`, `swh`, `ngq`. A fourth source writing system exists that
`WritingSystems.GetAll()` did not enumerate.

### (b) `identity_substituted: 0`

Read off the PLAN, not the report: `plan_match_basis` is
`{"<no match_basis>": 2243}` (2,231 filtered) and `plan_natural_key_by_class`
is `{}`. **Not one planned action carries a match basis at all.** So the
natural-key path did not run and find nothing -- it does not exist yet. The
opposite reading (zero substitutions beside a non-zero `NATURAL_KEY` count)
would have meant the matcher ran and had nothing to substitute, and the bare
tally distinguished neither. FR-006 is unreachable on this pair *today*; that
is sequencing, not a defect.

### (c) The filtered-only `leaf_failed: 1`

Now attributable, and it closes the loop with T024e and T024f:

```
GrammarCategory.PHONOLOGICAL_RULES  rule 33978942-cc6e-4655-afb2-b0a869b670c5
RuntimeError: PhSimpleContextNC guid=09ab1138-5ee0-49ff-8c60-d864b3bbe2ff
  references NC guid=ad5738e0-2a61-4e42-8f95-8db24e7b9881 absent from target
```

That NC is the **same** object as T024e's unexplained twelfth, and the **same**
one `_phon_is_empty` removes from the inventory (T024f) -- a Name-less,
`SegmentsRC`-less, `FeaturesOA`-less natural class. Force-all transfers it
anyway because empty pick-sets mean transfer-all; filtered does not, because a
dropped item is in no pick set. So the silent inventory-level drop is not
merely unobservable in a `source - after` comparison: **it breaks a
phonological-rule transfer**, and the `DroppedItemRecord` T024f added is what
names the object.

Measured breadth for that drop (T024f, read-only, 8 free projects / 921
enumerated phonology items): the drop set is **1** -- this object.
`_phon_is_empty`'s docstring is very nearly right that the motivating case is
*"no longer reproducible in current live data"*, and the one survivor is the
one that breaks a rule.
