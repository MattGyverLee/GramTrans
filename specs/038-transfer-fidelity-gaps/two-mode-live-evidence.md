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
