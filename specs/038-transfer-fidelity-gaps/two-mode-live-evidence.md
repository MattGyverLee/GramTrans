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

## Remaining in-scope gaps -- carried to T024h

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
