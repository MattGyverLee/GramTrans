# T038 / T048 -- the live gate, re-run after T045/T046 landed

**Date**: 2026-08-20
**Source**: `Ejagham Mini` (read-only, `etu`)
**Destination**: `GT038 Phase5 Target` -- created for this run. **`Target`,
`Esperanto` and `GT038 Phase4 Target` were never opened.**
**Census**: `CENSUS-20260820-094825` - artifacts under `scratchpad/038_census/`
(`p5-starter.json`, `p5-run-report.json`, `p5-census.json`; git-ignored per T003)

This is the single run T038 asked for: *"Run it once, after T045/T046 land --
that same run also answers T048's P3 predicate."* It settles P1's two count
rows and P3 together.

---

## What unblocked it

T038 recorded two reasons not to measure. Both are gone.

1. **The tree is now coherent.** T045 (`transfer.py`) and T046 (`report.py`)
   were uncommitted mid-edit in other sessions. Those sessions ended; the
   `lockout` registry reports **no active locks**. Their work was verified and
   committed as `e6bdb6e`: 63 new unit tests pass, and the 27 pre-existing
   failures at `e4e7123` are unchanged in **both membership and count**
   (3157 -> 3220 passing; failure sets diffed, identical).
2. **The exit-code prediction was wrong, and in the informative direction.**
   T038 predicted exit 8 (`CENSUS_ACCOUNTED`, the 5.2 gross-basis ceiling).
   Measured: **exit 1, `UNEXPLAINED_SHORTFALL`**. The console says why in as
   many words -- *"UNEXPLAINED_SHORTFALL is more severe than the
   CENSUS_ACCOUNTED ceiling, so it stands."* The cap is a ceiling on how good
   a verdict can get, not a floor under how bad it can get, and the earlier
   note read it as the latter.

---

## Creating the destination without writing new code

The T038 journal created its target through
`LcmCache.CreateNewLangProj(progressDlg, [...])`, having established that
`CreateCacheWithNewBlankLangProj` is **wrong** (0 phonemes, 0 POS -- SC-002
could not fail against it). That route needs an `IThreadedProgress`; reflection
over the loaded `SIL.*` assemblies finds the interface and **no concrete
implementation**, so a headless caller has to supply one from Python.

None was needed. `backups/Ejagham W Target 2026-08-19 0830.fwbackup` is a
**pristine GUI-created starter project** -- read straight out of the zip, it
carries exactly the committed `contracts/starter-baseline.json` inventory:

| class | backup | starter baseline | |
|---|---|---|---|
| PhPhoneme | 23 | 23 | MATCH |
| PartOfSpeech | 5 | 5 | MATCH |
| MoMorphType | 19 | 19 | MATCH |
| PhNCSegments | 2 | 2 | MATCH |
| LexEntry | 0 | 0 | MATCH |

`harness/restore.py` extracts it into a **new** project name, so nothing on
disk was overwritten and no existing project was touched. The destination then
captured **its own** baseline (`p5-starter.json`), which is what the recipe
asks for and is exact by construction.

> **A trap this run had to step around first.** `pip`'s editable install points
> `gramtrans` at the **main** worktree's `src/`, not the branch's. Every command
> below therefore sets
> `PYTHONPATH=D:/Github/_Projects/_LEX/GramTrans-038-transfer-fidelity-gaps/src`.
> Without it the gate measures `main`'s engine and silently attributes the
> result to the branch -- the same shape of error as the blank-project trap,
> arriving through packaging instead of through an API name.

---

## P1 -- three of four rows pass; the fourth is an instrument defect

Predicate P1: `MoStemMsa`, `MoInflAffMsa`, `MoDerivAffMsa`,
`MoUnclassifiedAffixMsa` and `PartOfSpeech` all MATCHED **and**
`PhPhoneme.duplicates.extra_objects == 0`.

| class | prediction on record | measured | |
|---|---|---|---|
| `MoStemMsa` | 164 -> 164 MATCHED | **164 -> 164 MATCHED** | as predicted |
| `MoInflAffMsa` | -- | 83 -> 83 MATCHED | |
| `MoDerivAffMsa` | -- | 0 -> 0 MATCHED | |
| `MoUnclassifiedAffixMsa` | -- | 0 -> 0 MATCHED | |
| `PartOfSpeech` | MATCHED on `baseline_matched` | **SHORTFALL -2** on `baseline_matched` | missed |
| `PhPhoneme` duplicates | 0 | **0** (`duplicate_extra_objects: 0` project-wide) | as predicted |
| exit code | 8 | **1** | see above |

**`MoStemMsa` 164 -> 164 confirms T043b live.** The `-2` that the previous gate
run measured and the CORRECTION section explained -- two source MSAs carrying a
null `PartOfSpeechRA` -- is closed. It is not merely reported now; it is gone.

### The `PartOfSpeech -2` is a census accounting defect, and this is provable

Counted directly out of the two `.fwdata` files, with no instrument in the way:

```text
source PartOfSpeech guids: 20
dest   PartOfSpeech guids: 20
source guids MISSING from dest: []
dest-only guids (starter leftovers): 0
```

**Every source part of speech reached the destination, and the destination
holds exactly those 20 and nothing else.** The transfer is perfect for this
class. The `-2` is arithmetic inside the census.

The arithmetic: the destination's starter held **5** parts of speech. The run
matched all five to source counterparts --

* **3 by natural key, then enriched**: `Noun`, `Pronoun`, `Verb`
  (`enrichments[]`, 16 children added across `AffixSlotsOC`,
  `AffixTemplatesOS`, `InflectableFeatsRC`, `ReferenceFormsOC`,
  `SubPossibilitiesOS`);
* **2 by GUID identity, then skipped**: `46e4fe08-...` and `a4fc78d6-...`,
  both `skips[]` rows reading `ALREADY_PRESENT_BY_GUID` / *"present in target;
  all WS slots equal."*

`starter_matched_to_source` is derived from `enrichments[]` alone, so it saw
**3**, not 5. That gives `unmatched_starter = 5 - 3 = 2`,
`destination_count_net = 20 - 2 = 18`, and `difference = 18 - 20 = -2`.
Count the identity skips as the matches they are and
`starter_matched_to_source = 5`, `unmatched_starter = 0`,
`destination_count_net = 20`, **`difference = 0`, verdict MATCHED**.

This is T048a's shape, one field further on: T048a wired `enrichments[]` and
`dropped_items[]` into the census and stopped there. An
`ALREADY_PRESENT_BY_GUID` skip is a *match* -- the strongest kind, identity --
and the accounting drops it on the floor. **Filed as T048b.** Until it lands,
P1 cannot report green no matter how correct the transfer is.

> Worth being precise about how this relates to the earlier `PartOfSpeech -5`,
> which the previous gate journal called a PHANTOM of the gross basis. Both are
> the same family -- starter objects matched to source but not counted as
> matched -- but they are not the same bug. `-5` was every starter POS going
> uncounted because the row sat on `baseline_gross`. `-2` is the row correctly
> promoted to `baseline_matched` and *still* undercounting, because only one of
> the two ways of matching a starter object feeds the tally. Fixing the basis
> did not fix the census; it narrowed the defect from 5 to 2 and made the
> remainder legible.

---

## P3 -- passes on its enrichment half, and T045/T046 are confirmed live

Predicate P3 (T048): `PartOfSpeech.match_basis.enriched > 0` **and** the
owned-child classes MATCHED.

* `PartOfSpeech.match_basis` = `{"basis_source": "run_report", "enriched": 3}`
  -- **`enriched > 0` holds**, and 3 is exactly the "3 matched categories"
  the measured baseline predicted.
* `MoInflAffixSlot` 9 -> 9 **MATCHED**; `MoInflAffixTemplate` 7 -> 7
  **MATCHED** -- which is also **P2's** whole predicate (T075).
* `FsFeatStruc` (-23), `FsClosedValue` (-46) and `CmPossibility` (-304) are
  short, but all three sit on `baseline_gross`, so those tallies are
  **advisory, not evidence** (5.2). They cannot be read either way until the
  basis is fixed; see T048b and T082.

The report surfaces T045/T046 added are populated and internally consistent:

```text
disposition: add_created 329, update_enriched 3, update_overwritten 26,
             update_overwritten_not_enriched 23, overwrite_split_reconciles true,
             skip 1808, dropped_with_reason 399,
             enriched_full 3, enriched_gained_nothing 0,
             enriched_children_added 16, enriched_children_dropped 0,
             created_excludes_enriched true
certainty:   is_first_transfer true,
             may_claim_identical_now false,
             may_claim_untouched_since_last_run false
```

`may_claim_identical_now: false` on a first transfer is T046's certainty clause
doing exactly its job, and `enriched_children_dropped: 0` alongside
`enriched_children_added: 16` is T045's add-only guarantee holding against a
live database rather than against a fake.

---

## One thing this run surfaced that is nobody's current task

The executor logged `leaf-dispatch counts attempted=329 succeeded=326
failed=3`, and the run report's `leaf_execution_failures` / `leaf_failed` are
both **`None`**. Three writes failed and the report says nothing, while
`add_created` still reads 329 because it is built from the plan. The debug line
states the mechanism itself -- *"swallowed write failures do NOT reduce the
reported 'added' count"*. That is a Principle I shape (a loss that is real and
unreported) and it is **not** covered by any open 038 task. Recorded here
rather than fixed, because it belongs to the `execute()` failure-plumbing that
T005 merged, not to Phase 5. **Filed as T048c.**

---

## Reproducing this

```powershell
$env:PYTHONPATH = "D:/Github/_Projects/_LEX/GramTrans-038-transfer-fidelity-gaps/src"

# 1. a pristine starter destination, additive -- overwrites nothing
python -c "import sys; sys.path.insert(0,'tests/integration'); from harness.restore import restore_target; restore_target('GT038 Phase5 Target', backup_path='backups/Ejagham W Target 2026-08-19 0830.fwbackup')"

# 2. its OWN baseline
python -m gramtrans.census_cli capture-baseline `
  --project "GT038 Phase5 Target" --out scratchpad/038_census/p5-starter.json

# 3. full copy, ws_mapping_mode="full", stems included
#    harness.full_run.run_full_transfer("Ejagham Mini", "GT038 Phase5 Target",
#        path, exclude=frozenset(), ws_mapping_mode="full", report_path=...)

# 4. the gate
python -m gramtrans.census_cli run `
  --source "Ejagham Mini" --destination "GT038 Phase5 Target" `
  --baseline scratchpad/038_census/p5-starter.json `
  --destination-freshly-created `
  --run-report scratchpad/038_census/p5-run-report.json `
  --out scratchpad/038_census/p5-census.json
```

The census opens both projects read-only and writes to neither; the capture
verified its own digest (`ab37b1cd60dd...`) unchanged before and after.

---

## Verdict

**T038 is measured but not passed, and the residual is not in the transfer.**
Its MSA half and its duplicate half both hold; its `PartOfSpeech` row is
blocked on T048b, an instrument defect proven against the raw `.fwdata`.
**T048's `enriched > 0` half passes**, as does **P2 (T075)** in passing. Neither
task is checked off here: a gate that has not returned its own green is not a
gate that passed, and writing it down as passed on the strength of a hand
count is precisely the laundering the CORRECTION section of the previous
journal warned about.
