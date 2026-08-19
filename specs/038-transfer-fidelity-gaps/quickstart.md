# Quickstart: Running the Per-Class Object Census Gate

**Feature**: `038-transfer-fidelity-gaps` | **Date**: 2026-08-19

How a maintainer captures a starter baseline, runs a census over a source ->
destination pair, reads the artifact, and uses it as a phase acceptance gate.

Contract: [`contracts/fidelity-census.md`](contracts/fidelity-census.md).
Artifact schema: [`contracts/census-artifact.schema.json`](contracts/census-artifact.schema.json).

> **The instrument does not exist yet.** `debug/audit_object_census.py` is NOT in
> the repository; the figures in [`census-evidence.md`](census-evidence.md) were
> produced ad-hoc. Every command below whose invocation depends on unwritten code
> is marked **`PLANNED`**. Commands not so marked run today.
>
> Do not confuse this with `tests/verification/fidelity_census.py` (feature 024),
> which is a **field-level** census over an in-code LCM model snapshot and never
> opens a project. Both are kept; neither replaces the other. See
> `contracts/fidelity-census.md` section 0.

---

## 1. Prerequisites

- **Windows** with **FieldWorks / FLEx** installed. The census reads live
  `.fwdata` projects through flexicon, so there is no Linux or macOS path.
- Python from the repo's supported range (`requires-python >= 3.8`). The repo's own
  docs and commands use `python`; `python3` also resolves on this machine.
- **flexicon installed editable, at or above the `pyflexicon>=4.4.1` floor**:

  ```powershell
  pip install -e D:/Github/_Projects/_LEX/flexicon
  python -c "import flexicon; print(flexicon.__file__)"
  ```

  The second command MUST NOT print a `site-packages` path. If it does, a stale
  copy is shadowing the working tree and everything below measures the wrong code.

  ```powershell
  pip show pyflexicon | Select-String '^Version:'
  ```

  **Why the floor matters, and why a lower one is worse than a hard failure.**
  4.4.1 is the first release carrying the GUID-preserving create surface
  (`BaseOperations._CreateWithGuid`, plus the optional `guid=` kwarg on
  `Texts.Create` / `Paragraphs.Create` / `Segments.AppendSentence` /
  `Wordforms.Create` / `WfiAnalyses.Create` / `WfiGlosses.Create` /
  `WfiMorphBundles.Create`). On an older flexicon every `guid=` kwarg raises
  `TypeError` -- and the engine's `_safe` / `except Exception` wrappers swallow that
  into a generic "create failed" drop. The transfer therefore **silently
  regenerates identities** instead of failing loudly: the objects arrive with fresh
  GUIDs, a re-run cannot match them, and the census sees a class that looks
  populated while identity has quietly been destroyed. A too-low floor does not
  break the census; it invalidates it.

- **Do not run any of this against a project another session is writing.** The
  census is read-only and safe on a live project (it takes an `fwdata_sha256`
  before and after and fails `CENSUS_ERROR` if the digest moved), but a project
  being written mid-transfer yields counts that are evidence of nothing.

Optional, for validating an artifact locally:

```powershell
pip install jsonschema
```

---

## 2. Capture the starter baseline (once per FieldWorks version)

FR-010: the census must exclude what a newly created FLEx project ships, or the
23 starter phonemes read as a surplus the transfer created.

1. In FLEx, create a **brand-new, empty project** -- e.g. `GT Starter Baseline`.
   Choose the vernacular writing system and then touch nothing else: do not import,
   do not add an entry, do not edit the starter phoneme or part-of-speech lists.
   An edited starter inventory is no longer a baseline.
2. Close FLEx so the `.fwdata` is flushed and unlocked.
3. Capture: **`PLANNED`**

   ```powershell
   python debug/audit_object_census.py capture-baseline `
     --project "GT Starter Baseline" `
     --out specs/038-transfer-fidelity-gaps/contracts/starter-baseline.json
   ```

4. Confirm the capture carries **keys, not only counts**:

   ```powershell
   python -c "import json; d=json.load(open('specs/038-transfer-fidelity-gaps/contracts/starter-baseline.json')); print(d['carries_natural_keys'], d['flex_version'], d['data_model_version'], d['class_count'])"
   ```

   `carries_natural_keys` must be `True`. Counts alone force every census row onto
   the `baseline_gross` subtraction basis, which cannot distinguish a correct
   natural-key match from a shortfall (`contracts/fidelity-census.md` 5.2).

5. Commit the baseline. It lives under `specs/`, so it commits to `main` per the
   Git Workflow Protocol.

**Re-capture when FieldWorks is upgraded.** The baseline records `flex_version` and
`data_model_version`; a census against a destination with a newer data model exits
`BASELINE_STALE` (5) rather than mis-subtracting. That is intentional -- FLEx
changes what a new project ships between versions.

**When the destination is NOT a freshly created project**, skip the starter capture
entirely and take a **pre-transfer census** of the destination instead (Section 3,
step 1). That is exact by construction, and it is the only correct option for a
destination that already holds real work.

---

## 3. Run a census over a source -> destination pair

### Step 1 (strongly recommended) -- pre-transfer census of the destination

**`PLANNED`**

```powershell
python debug/audit_object_census.py run `
  --source "Ejagham W Mini" `
  --destination "Ejagham W Target" `
  --pre-transfer `
  --out scratchpad/038_census/pre.json
```

This produces a baseline of kind `pre_transfer_census` that the post-transfer run
consumes. It also gives you the destination's honest starting point before anything
touches it.

### Step 2 -- run the transfer

Run GramTrans as you normally would (FlexTools, or the standalone app). Note the
run id it prints -- format `GT-YYYYMMDD-HHMMSS`, e.g. `GT-20260819-030049` -- and
keep the run report. The census can run without the report, but then it cannot know
how many starter objects were matched, so it drops to the `baseline_gross` basis and
the verdict is capped at `CENSUS_ACCOUNTED` (`contracts/fidelity-census.md` 5.2).

### Step 3 -- run the census

**`PLANNED`**

```powershell
python debug/audit_object_census.py run `
  --source "Ejagham W Mini" `
  --destination "Ejagham W Target" `
  --baseline scratchpad/038_census/pre.json `
  --run-report scratchpad/038_census/GT-20260819-030049-report.json `
  --out scratchpad/038_census/GT-20260819-030049-census.json
  # add --destination-freshly-created ONLY with a starter_capture baseline
```

The census prints the human-readable per-class table to the console and writes the
machine-readable artifact to `--out`. It **never writes to either project**: both
are opened read-only, no residue tag is applied, and no restore is needed before or
after.

Check the exit code, since that is the gate:

```powershell
echo $LASTEXITCODE
```

| Exit | Verdict | Meaning |
|---|---|---|
| 0 | `CENSUS_CLEAN` | every required class matched, no duplicates, nothing needed explaining |
| 0 | `CENSUS_ACCOUNTED` | differences exist and every one is backed by a run-report line |
| 1 | `UNEXPLAINED_SHORTFALL` | objects went missing with no report line -- the SC-005 failure |
| 2 | `UNEXPLAINED_SURPLUS` | objects appeared with no report line |
| 3 | `DUPLICATE_IDENTITY` | an admitted class holds two objects for one natural key (SC-002) |
| 4 | `BASELINE_MISSING` | no baseline; the counts are still written, the run cannot pass |
| 5 | `BASELINE_STALE` | baseline captured under a different FLEx / data model version |
| 6 | `COVERAGE_INCOMPLETE` | the class list no longer matches the truth source (FR-012) |
| 7 | `CENSUS_ERROR` | over-accounting, unresolvable report ref, a project digest that moved, or an unhandled exception |

Only 0 is success. There is deliberately no verdict meaning "loss reported, review
advisable, exit success".

---

## 4. Read the artifact

Validate it first, if you have `jsonschema`:

```powershell
python -c "import json,jsonschema; s=json.load(open('specs/038-transfer-fidelity-gaps/contracts/census-artifact.schema.json')); d=json.load(open('scratchpad/038_census/GT-20260819-030049-census.json')); jsonschema.Draft202012Validator(s).validate(d); print('artifact valid')"
```

Headline:

```powershell
python -c "import json; d=json.load(open('scratchpad/038_census/GT-20260819-030049-census.json')); t=d['totals']; print(d['verdict'], d['exit_code']); print('shortfall', t['total_shortfall'], 'unexplained', t['unexplained_shortfall']); print('surplus', t['total_surplus'], 'unexplained', t['unexplained_surplus']); print('duplicates', t['duplicate_extra_objects'])"
```

Every class that failed, with its numbers:

```powershell
python -c "import json; d=json.load(open('scratchpad/038_census/GT-20260819-030049-census.json')); [print(r['class'], r['source_count'], '->', r['destination_count_total'], 'diff', r['difference'], r['verdict_class'], 'unexp', r['unexplained_shortfall'], r['unexplained_surplus']) for r in d['classes'] if r['gate_scope']=='required' and (r['unexplained_shortfall'] or r['unexplained_surplus'])]"
```

Duplicates -- the check a zero difference cannot make:

```powershell
python -c "import json; d=json.load(open('scratchpad/038_census/GT-20260819-030049-census.json')); [print(r['class'], 'groups', r['duplicates']['groups'], 'extra', r['duplicates']['extra_objects']) for r in d['classes'] if r.get('duplicates') and r['duplicates']['extra_objects']]"
```

How to read a row, in order:

1. **`verdict_class`** -- `MATCHED` / `SHORTFALL` / `SURPLUS` / `NOT_EVALUATED`. Never
   infer this from the sign yourself; the sign convention is
   `difference = destination_count_net - source_count`, so negative is a loss and
   positive is an excess.
2. **`difference` vs `difference_raw`** -- `difference` is the gate quantity, net of
   the destination's pre-existing objects; `difference_raw` is the naive
   `destination - source`. The measured `PhPhoneme` row is `difference_raw` +23,
   `difference` 0.
3. **`duplicates.extra_objects`** -- a `MATCHED` row with duplicates still fails.
   That is the measured phoneme case exactly: 41 -> 64 with 23 starter phonemes nets
   to `difference` 0 while 21 phoneme names exist twice.
4. **`accounted_for[]`** -- each line names a reason (FR-013's closed vocabulary) and
   a `report_ref` proving the run report actually says so. `unexplained_shortfall`
   and `unexplained_surplus` are what remains after those lines are subtracted; a
   non-zero value on a `required` row is the failure.
5. **`match_basis`** -- `identity` vs `natural_key` (FR-006), plus `created_new`,
   `enriched`, and `unmatched_reported`. A large `created_new` on a class whose
   starter content should have matched is the duplicate defect in the making.
6. **`starter_subtraction_basis`** -- `baseline_matched` is trustworthy;
   `baseline_gross` means no run report was supplied and the row is advisory for
   shortfall purposes; `no_baseline` means the run cannot pass at all.

Note that the artifact always carries **one row per required class**, including
classes with no instances anywhere (`verdict_class: "NOT_EVALUATED"` with a
reason). An absent row is a schema violation, not a clean class.

---

## 5. Use it as a phase acceptance gate

Acceptance for Phases 1..5 of this feature is a census diff, not a unit test. Each
phase declares a **predicate over the artifact**; the phase is done when a census
run exits 0 with its predicate satisfied.

Predicates, per `contracts/fidelity-census.md` 9.1:

| Phase | Predicate | Success criterion |
|---|---|---|
| 1 identity | `MoStemMsa`, `MoInflAffMsa`, `MoDerivAffMsa`, `MoUnclassifiedAffixMsa`, `PartOfSpeech` MATCHED; `PhPhoneme.duplicates.extra_objects == 0` | SC-001, SC-002 |
| 2 closure | `MoInflAffixTemplate`, `MoInflAffixSlot` MATCHED | SC-004 |
| 3 enrichment | `PartOfSpeech.match_basis.enriched > 0`; owned-child classes MATCHED | SC-007 |
| 4 process rules | `MoAffixProcess` MATCHED **and** `MoAffixAllomorph.difference == 0` | SC-006 |
| 5 residual | every remaining required row MATCHED or carrying a valid `GOVERNED_BY_OTHER_FEATURE` / `NO_CREATE_PATH` line | SC-005 |

Phase 4 needs both halves because either alone can be satisfied by the defect
itself: the measured run turned 13 `MoAffixProcess` into 13 extra
`MoAffixAllomorph`, so checking only the allomorph count, or only the process
count, would pass a downgrade.

Assert a predicate against an artifact:

```powershell
python -c "import json,sys; d=json.load(open('scratchpad/038_census/GT-20260819-030049-census.json')); rows={r['class']:r for r in d['classes']}; want=['MoStemMsa','MoInflAffMsa','MoDerivAffMsa','MoUnclassifiedAffixMsa','PartOfSpeech']; bad=[c for c in want if rows.get(c,{}).get('verdict_class')!='MATCHED']; dup=rows.get('PhPhoneme',{}).get('duplicates',{}).get('extra_objects',-1); print('PHASE 1', 'PASS' if not bad and dup==0 else 'FAIL'); print('not matched:', bad, 'phoneme duplicates:', dup); sys.exit(0 if not bad and dup==0 else 1)"
```

Or, once the subcommand exists: **`PLANNED`**

```powershell
python debug/audit_object_census.py gate `
  --artifact scratchpad/038_census/GT-20260819-030049-census.json `
  --phase 1
```

### Idempotency (SC-008)

Run the transfer a second time into the same destination, take a third census, and
compare: the second run must add no objects. **`PLANNED`**

```powershell
python debug/audit_object_census.py diff `
  --before scratchpad/038_census/GT-20260819-030049-census.json `
  --after  scratchpad/038_census/GT-20260819-041500-census.json
```

Every class's `destination_count_total` must be unchanged. Any increase is a
duplicate-creation defect regardless of what either census's own verdict says.

---

## 6. Sanity check on the measured baseline

Before trusting a green run, confirm the census can still see the *known* failures.
Point it at the two disposable measured targets and check it reproduces
[`census-evidence.md`](census-evidence.md) section 0 -- notably `MoStemMsa`
1949 -> 0 on the Ngoreme pair, `PhPhoneme` 41 -> 64 with 21 duplicate names on
both, `MoAffixProcess` 13 -> 0 against `MoAffixAllomorph` +13 on Ejagham, and
`MoInflAffixTemplate` 8 -> 0 / `MoInflAffixSlot` 11 -> 0. A census that reports
those pairs clean is itself broken.

The two measured targets are disposable test projects and will be re-created rather
than repaired (spec Assumptions), so they are safe to census repeatedly.

**Do not** run any of this against the FLEx project named `Target` while another
session holds a live write on it.
