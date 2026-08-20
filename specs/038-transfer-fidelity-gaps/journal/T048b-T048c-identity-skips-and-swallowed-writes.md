# T048b / T048c -- the two defects the last gate run found, closed and re-measured

**Date**: 2026-08-20
**Branch** `038-transfer-fidelity-gaps`, commits `1219fea` (T048b), `e8e6d4a` (T048c)
**Source**: `Ejagham Mini` (read-only, `etu`)
**Destination**: `GT038 T048b Target` -- restored fresh from
`backups/Ejagham W Target 2026-08-19 0830.fwbackup` into a **new** project name,
so nothing on disk was overwritten. **`Esperanto`, `Target`,
`GT038 Phase4 Target` and `GT038 Phase5 Target` were never opened.**
**Census**: `CENSUS-20260820-114752` -- artifacts under `scratchpad/038_census/`
(`t048b-starter.json`, `t048b-run-report.json`, `t048b-census.json`;
git-ignored per T003)

The previous gate run measured T038 and did not pass it, filing two defects.
Both are now closed, and the gate was re-run end to end against a fresh pair.
**P1 (T038) and P2 (T075) predicates are satisfied. P3 (T048) is blocked on one
row, and that row's loss is proven not to exist.**

---

## T048b -- an identity skip is a match, and the strongest kind

### The mechanism, stated exactly

`report.build_from_plan` calls `_count_matched` on the actions loop and on the
overwrites loop. It does **not** call it on the skips loop. So a destination
object the run found by GUID and left alone -- `Skip(ALREADY_PRESENT_BY_GUID)`
-- entered no tally at all.

Measured on the previous run and reproduced exactly on this one: the
destination starter held 5 parts of speech and the run matched all five, by two
different mechanisms.

| how it was matched | where it lands | counted before T048b |
|---|---|---|
| 3 matched by natural key, then **enriched** | `enrichments[]`, and thence `matched_to_source.by_object_class` | yes |
| 2 matched by GUID, then **skipped** | `skips[]` as `ALREADY_PRESENT_BY_GUID` | **no** |

`starter_matched_to_source` therefore read 3, `unmatched_starter` read
5 - 3 = 2, and two starter objects the run had positively identified by GUID
were subtracted from the destination as though they were surplus.

Nothing was written because nothing needed to be. That is a statement about the
**disposition**, not about whether the object was found.

### Three guards, because each one prevents a worse defect

The fix lives in `census_cli.py` -- the arithmetic is the census's, and
`Skip` carries no `object_class`, so making the *producer* count these would
mean growing one on ~12 emit sites in `Lib/categories.py` (a claimed file) and
changing what the ENGINE records rather than what the instrument reads.

1. **Attribution is never guessed.** The class comes from
   `preview._LCM_CLASS_FOR_CATEGORY` -- the one one-to-one table, reached by
   the same lazy import `categories._lcm_class_for_category` already uses, not
   a copy. A skip whose category is not one-to-one is counted for **no** class.
2. **Withholding is bounded.** An unattributed identity skip takes the
   `baseline_matched` basis away from the classes it *could* have been
   (`_AMBIGUOUS_IDENTITY_SKIP_CLASSES`, every entry copied from the reasons
   `_LCM_CLASS_FOR_CATEGORY` states for its own omissions) rather than from all
   of them. A `VARIANT_TYPES` match cannot have been a `PartOfSpeech`, and
   withholding the stronger basis from a row that was never in doubt is its own
   mis-report. A category **neither** table knows is unbounded and withholds
   from everything -- the pre-T048b behaviour, and the honest answer when the
   damage cannot be located.
3. **The tally is capped at the starter baseline.** `census.unmatched_starter`
   does not clamp. T039's run 2 matched 164 `MoStemMsa` against a starter
   baseline of 0; uncapped, that subtracts **-164**, inflates
   `destination_count_net` by 164 and **hides a real shortfall** -- the one
   direction this instrument must never be wrong in. Capping errs the other
   way and says so in `notes` (the T023c rule: a capped number is never
   silent).

The dedup is by GUID against the enrichments the report already counted. It is
possible from the artifact alone only because an identity skip's `source_guid`
**is** its target GUID -- that is what matching by GUID means, and `models.Skip`
has no `target_guid` field.

### Measured

1794 of 1808 identity skips attributed; the 14 that were not are
`VARIANT_TYPES` (7) and `COMPLEX_FORM_TYPES` (7), which withhold the basis from
`LexEntryType` and `LexEntryInflType` alone.

| class | before | after |
|---|---|---|
| `PartOfSpeech` | matched 3, basis `baseline_gross`... then `baseline_matched` with `difference -2`, **SHORTFALL** | matched **5**, basis `baseline_matched`, `difference 0`, **MATCHED** |
| `CmSemanticDomain` | basis `baseline_gross`, all 1792 starters subtracted as surplus | matched **1792**, basis `baseline_matched`, `difference 0`, **MATCHED** |
| `LexEntryType` / `LexEntryInflType` | gross | gross, **and now says why** (the withheld note names T048b) |

---

## T048c -- three writes failed and the artifact said nothing

Feature 037 built the record (`LeafExecutionFailure`), `transfer.py` appends one
per swallowed exception, and `render_text_summary` renders them. Every link was
in place except the one that matters most: **`to_snapshot_json` never emitted
them.** So the surface that survives after the console scrolls away -- and the
surface the census reads -- carried no key at all, and every reader doing
`.get()` saw `None`, unable to tell "three writes failed" from "this build does
not report write failures". Meanwhile `disposition.add_created` read 329,
because it is counted from the PLAN.

Three changes, all in `report.py`:

* the artifact emits `leaf_execution_failures` **in full** (never truncated --
  a swallowed write is the least truncatable record this report holds), plus
  `leaf_failed` and a note saying in as many words that these writes did not
  happen;
* `disposition_totals` splits planned from written: `add_write_failed` and
  `add_created_written`. **`add_created` is not silently reduced** -- it is the
  honest answer to "how many creates were planned" and three invariants are
  checked against it. When failures exceed planned creates the counters
  disagree, so `add_created_written` yields `None` and
  `create_split_reconciles` is False (the `update_overwritten_not_enriched`
  precedent, and T039's lesson);
* `_has_038_data` now counts a swallowed write as data worth a disposition
  block, because a run whose only anomaly is a failed write is exactly the run
  that needs `add_created_written`. Byte-identity is not weakened: such a
  report already emits the failure list. A **zero**-failure report is
  untouched.

### Measured live, on this run's report

```text
leaf_failed: 3            leaf_execution_failures: 3 records
disposition: add_created 329, add_write_failed 3,
             add_created_written 326, create_split_reconciles true
```

The same 329 / 326 / 3 the executor logged and the previous report could not
say. The measured **zero** also has a home now: wherever the disposition block
appears it states `add_write_failed: 0` positively, so "no writes failed" and
"this build does not measure write failures" are different artifacts -- the
omit-when-empty trap `matched_to_source.by_natural_key` already records.

---

## The re-run gate

```text
phase 1 predicate satisfied      <- T038's P1
phase 2 predicate satisfied      <- T075's P2
phase 3 predicate NOT satisfied  <- T048's P3
    - P3: MoMorphType is SHORTFALL (difference -19), not MATCHED
overall: verdict CENSUS_ACCOUNTED, exit 8 [CAPPED -- advisory, not a pass]
```

### P1 -- all four rows and the duplicate half now hold

| class | measured | |
|---|---|---|
| `MoStemMsa` | 164 -> 164 **MATCHED** | |
| `MoInflAffMsa` | 83 -> 83 **MATCHED** | |
| `MoDerivAffMsa` | 0 -> 0 **MATCHED** | |
| `MoUnclassifiedAffixMsa` | 0 -> 0 **MATCHED** | |
| `PartOfSpeech` | 20 -> 20 **MATCHED**, basis `baseline_matched`, matched 5 | was SHORTFALL -2 |
| `PhPhoneme` duplicates | `extra_objects: 0`, project-wide `duplicate_extra_objects: 0` | |

### P2 (T075) passes in passing

`MoInflAffixSlot` 9 -> 9 MATCHED, `MoInflAffixTemplate` 7 -> 7 MATCHED.

### P3 -- one row, and its loss does not exist

`PartOfSpeech.match_basis.enriched == 3`, so P3's enrichment half holds. The
predicate fails on a single owned-child class, and it is **not** the one T048
predicted. Counted straight out of the two `.fwdata` files, with no instrument
in the way:

```text
MoMorphType:  source=19  destination=19
  source GUIDs missing from destination: 0
  destination-only GUIDs:                0
  identical GUID sets: True
PartOfSpeech: source=20  destination=20   identical GUID sets: True
```

**The two projects hold the same 19 morph types, by GUID.** The `-19` is
arithmetic, exactly as the `-2` was -- but it is **not** the same defect, and
T048b cannot reach it. `PartOfSpeech`'s two starters were matched and the run
*recorded* the match as a skip; T048b's whole job was to read that record.
`MoMorphType` has **no record of any kind** -- no action, no overwrite, no
skip -- because the morph-types list is project-independent fixed content that
needs no transfer. `categories.py` says so in as many words at the site that
refuses to create one: *"the morph-types list is project-independent fixed
content, all 19 GUIDs byte-identical across the three projects measured"*.

So the class arrives correct, nothing happens, nothing is recorded, and the
gross basis subtracts all 19 starters as surplus. Closing it needs evidence the
census does not currently hold -- either a GUID-level comparison (the starter
baseline records `class`, `count`, `names` and **no GUIDs**) or a declared
"fixed canonical content, matched by construction" accounting line. Inventing
an attribution with no evidence is precisely what this module forbids, so it is
**filed as T048d** rather than fixed here.

### Why the overall exit is 8 and not 0

18 rows sit on `baseline_gross` with their unexplained tallies suppressed by
the 5.2 cap, totalling 1681 advisory objects: `PunctuationForm` (586),
`WfiMorphBundle` (219), `WfiAnalysis` (136), `WfiGloss` (135), `StTxtPara`
(91), `WfiWordform` (49), `PhCode` (34), `CmPossibility` (304), `FsClosedValue`
(46), `FsFeatStruc` (23), `StText` (17), `MoMorphType` (19), `LexEntryType`
(11), `CmAgent` (4), `LexEntryInflType` (3), `ReversalIndex` (2), `CmFolder`
(1), `ReversalIndexEntry` (1).

Texts and wordforms are governed by their own feature and `CmPossibility` /
`FsFeatStruc` / `FsClosedValue` are R7 report-only residue (T079); the
remainder is T081's scope. **None of them is P1's, and none is evidence of a
loss on this evidence** -- but the verdict is capped, so T038's third clause
("exit code 0") is not met even though its predicate is.

---

## Verdict

**T048b and T048c are closed and verified live.** T038's predicate is
satisfied and its exit-code clause is not; T075's predicate is satisfied on the
same run. T048 is blocked on T048d alone. Consistent with the previous
journal's own rule -- *a gate that has not returned its own green is not a gate
that passed* -- **T038, T048 and T075 stay unchecked**, and the reason each
stays unchecked is written above rather than argued away.

Test state: `tests/unit` **3286 passed, 0 failed** (79 skipped, 14 xfailed,
14 xpassed), including 21 new T048b tests and 15 new T048c tests.
`tests/integration/test_object_census.py -m "not integration"`: 209 passed,
1 failed -- `test_t028_has_not_yet_admitted_phphoneme_to_the_roster`, which
fails identically at `201d9cd` with these changes stashed and is a roster
tripwire, not a regression.

## Reproducing this

```powershell
$env:PYTHONPATH = "D:/Github/_Projects/_LEX/GramTrans-038-transfer-fidelity-gaps/src"

# 1. a pristine starter destination under a NEW name -- overwrites nothing
python -c "import sys; sys.path.insert(0,'tests/integration'); from harness.restore import restore_target; restore_target('GT038 T048b Target', backup_path='backups/Ejagham W Target 2026-08-19 0830.fwbackup')"

# 2. its OWN baseline
python -m gramtrans.census_cli capture-baseline `
  --project "GT038 T048b Target" --out scratchpad/038_census/t048b-starter.json

# 3. full copy, ws_mapping_mode="full", stems included
#    harness.full_run.run_full_transfer("Ejagham Mini", "GT038 T048b Target",
#        path, exclude=frozenset(), ws_mapping_mode="full", report_path=...)

# 4. the gate, then each phase predicate
python -m gramtrans.census_cli run `
  --source "Ejagham Mini" --destination "GT038 T048b Target" `
  --baseline scratchpad/038_census/t048b-starter.json `
  --destination-freshly-created `
  --run-report scratchpad/038_census/t048b-run-report.json `
  --out scratchpad/038_census/t048b-census.json
python -m gramtrans.census_cli gate --artifact scratchpad/038_census/t048b-census.json --phase 1
```

The census opens both projects read-only and writes to neither.
