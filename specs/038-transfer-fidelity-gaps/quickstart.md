# Quickstart: Running the Per-Class Object Census Gate

**Feature**: `038-transfer-fidelity-gaps` | **Date**: 2026-08-19

How a maintainer captures a starter baseline, runs a census over a source ->
destination pair, reads the artifact, and uses it as a phase acceptance gate.

Contract: [`contracts/fidelity-census.md`](contracts/fidelity-census.md).
Artifact schema: [`contracts/census-artifact.schema.json`](contracts/census-artifact.schema.json).

> **The instrument ships.** It is `python -m gramtrans.census_cli`, implemented in
> `src/gramtrans/census_cli.py` over `src/gramtrans/Lib/census.py` (T021), with the
> four subcommands `capture-baseline` / `run` / `gate` / `diff`. Every command below
> runs today; the `PLANNED` markers this file used to carry are gone.
>
> There is **no** `debug/audit_object_census.py` and there will not be one. R2
> (`research.md`) rejected a `debug/` home outright -- "a release gate cannot live in
> unsupported scratch" (SC-009) -- so earlier drafts of this quickstart named a path
> that was never going to exist. The flag is `--destination` everywhere, never
> `--target`: "destination" is the vocabulary of the schema and the contracts, and
> `build_parser`'s own docstring records that absence as load-bearing.
>
> The figures in [`census-evidence.md`](census-evidence.md) were produced ad-hoc,
> before the instrument existed, and several are under correction -- see section 6.
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
- **flexicon installed editable, at or above the `pyflexicon>=4.5.2` floor**:

  ```powershell
  pip install -e D:/Github/_Projects/_LEX/flexicon
  python -c "import flexicon; print(flexicon.__file__)"
  ```

  The second command MUST NOT print a `site-packages` path. If it does, a stale
  copy is shadowing the working tree and everything below measures the wrong code.

  ```powershell
  pip show pyflexicon | Select-String '^Version:'
  ```

  **T002 verification, recorded 2026-08-19 (this feature's Phase 1).** The
  editable install was found STALE: the flexicon working tree already declared
  `version = "4.5.2"` (`flexicon/__init__.py:15`) while the installed
  distribution metadata still reported `4.4.1`, so a naive `pip show` check
  passed the *wrong* number. `pip install -e D:/Github/_Projects/_LEX/flexicon`
  reinstalled it (`Uninstalling pyflexicon-4.4.1 ... Successfully installed
  pyflexicon-4.5.2`). Both commands then agreed:

  ```text
  python -c "import flexicon; print(flexicon.__file__)"
  D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py      # not site-packages: OK

  python -c "import importlib.metadata as m; print(m.version('pyflexicon'))"
  4.5.2
  ```

  `NaturalClassOperations.GetSyncableProperties` (line 1039) and
  `ApplySyncableProperties` (line 1169) are both present, which is the 037
  surface this feature builds on.

  **The floor is `>=4.5.2`, and three documents disagreed about it.**
  `pyproject.toml:47` (authoritative) says `pyflexicon>=4.5.2`; `tasks.md` T002
  says `>=4.5.0`; this file said `>=4.4.1`. Only this file is owned by feature
  038, so only this line is corrected here -- `pyproject.toml` and `CLAUDE.md`
  are claimed by 037 and are deliberately left untouched. The reason the exact
  patch number matters is recorded in `CLAUDE.md`'s Install section: **4.5.0**
  gated the natural-class `FeaturesOA` wiring behind `hasattr(nc, "FeaturesOA")`,
  which is unconditionally False under pythonnet (attributes resolve against the
  STATIC wrapper type, and `NaturalClasses.GetAll()` yields base-`IPhNaturalClass`
  proxies), so the feature was 100% dead while every test passed; **4.5.1** fixed
  that by discriminating on `.ClassName` and casting, but gated the apply on
  `if features:`, so a genuinely empty feature structure reports a phantom loss;
  **4.5.2** gates on key presence instead. Do not lower the floor to 4.5.0 or
  4.5.1.

  **Why the floor matters, and why a lower one is worse than a hard failure.**
  4.4.1 was the first release carrying the GUID-preserving create surface
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
3. Capture:

   ```powershell
   python -m gramtrans.census_cli capture-baseline `
     --project "GT Starter Baseline" `
     --out specs/038-transfer-fidelity-gaps/contracts/starter-baseline.json
   ```

   Add `--projects-root PATH` if the projects do not live under the default
   `C:\ProgramData\SIL\FieldWorks\Projects`.

4. Confirm the capture records what it actually holds:

   ```powershell
   python -c "import json; d=json.load(open('specs/038-transfer-fidelity-gaps/contracts/starter-baseline.json')); print(d['kind'], d['carries_natural_keys'], d['flex_version'], d['data_model_version'], d['class_count'])"
   ```

   The captured artifact reads `starter_capture False 9.3.10 7000072 72`.

   **`carries_natural_keys` is `False`, and that is correct -- not a failed
   capture.** An earlier draft of this step demanded `True`. That demand is
   unsatisfiable for a whole-project baseline: a genuinely blank FieldWorks project
   holds objects in 36 classes, **11 of which carry no name at all** (`CmDomainQ`
   7938, `StTxtPara` 86, `PhCode` 25, `CmRow`, `CmCell`, `CmAgentEvaluation`,
   `DsDiscourseData`, `LangProject`, `MoMorphData`, `PhPhonData`, `StText`), so no
   such baseline can record a natural key for every starter object. Per
   `contracts/census-artifact.schema.json` a count-only baseline is a **legal,
   designed state**. What matters is that the flag is recorded *truthfully*: it must
   report `False` when keys are absent, and never claim a `True` it cannot back.

   The consequence is real, and you have to plan for it: a count-only baseline forces
   every row onto the `baseline_gross` subtraction basis, and on that basis the
   verdict is **capped at `CENSUS_ACCOUNTED`** and can never be
   `UNEXPLAINED_SHORTFALL` / `UNEXPLAINED_SURPLUS` (`contracts/fidelity-census.md`
   5.2, implemented in `recompute_verdict`). Without that cap a *correct* transfer
   reports a shortfall -- the contract's own 43-23=20 example. Read section 3's note
   on the cap before treating an exit 0 as a clean run.

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

```powershell
python -m gramtrans.census_cli run `
  --destination "Ejagham W Target" `
  --pre-transfer `
  --out scratchpad/038_census/pre.json
```

This produces a baseline of kind `pre_transfer_census` that the post-transfer run
consumes. It also gives you the destination's honest starting point before anything
touches it.

`--pre-transfer` censuses the **destination only**, so it takes no `--source`:
`_dispatch` routes it straight to `capture_baseline(args.destination, ...)`, and a
`--source` given on this path is ignored. Passing `--baseline` here warns, for the
same reason -- this run *is* the baseline. On every other `run` path `--source` is
required.

### Step 2 -- run the transfer

Run GramTrans as you normally would (FlexTools, or the standalone app). Note the
run id it prints -- format `GT-YYYYMMDD-HHMMSS`, e.g. `GT-20260819-030049` -- and
keep the run report. Supply it: an `accounted_for[]` line needs a `report_ref` to
prove the run report actually explains a difference, so without the report nothing
can be accounted for at all.

**Supplying it does not lift the 5.2 cap, though.** An earlier draft of this section
implied the cap was the price of omitting the report. It is not:
`starter_subtraction_basis` is emitted as `baseline_gross` on **every** path that has
a baseline (`census_cli.py`, `_row_for_entry`), whether or not a run report was
given, so the verdict is capped at `CENSUS_ACCOUNTED` either way. Section 4's note on
`starter_subtraction_basis` explains why, and points at the open work.

### Step 3 -- run the census

```powershell
python -m gramtrans.census_cli run `
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

**Read the `[WARN] census note(s)` block printed immediately above the verdict.**
That placement is deliberate (T023c): 5.2's cap can turn a large shortfall into
`CENSUS_ACCOUNTED` / exit 0, and the sentence that says so has to be the last thing
you read before the exit code, not something scrolled off the top. Notes are
**reportage only** -- the verdict is computed from counts, bases and accounting
lines, never from a note, so a hand-written note cannot buy a cap. When a *more*
severe verdict decided the run, the console says the cap did not apply.

Counts are **per exact class, not per polymorphic subtree** (T023b). LCM's
`AllInstances()` includes subclasses, so an unfiltered count puts one `PartOfSpeech`
object in both its own row and `CmPossibility`'s. The census filters on class
identity instead, so every object lands in exactly one row and each row's
`difference` is unambiguous.

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

> **Open, and load-bearing for anyone using exit 0 as a release gate (T024b).** On
> the gross basis the *design* above and the *shipped default* pull apart: both live
> sanity pairs reported `CENSUS_ACCOUNTED` / **exit 0** / `passed=True` while
> carrying 44-47 failing rows and 74,157 units of unexplained shortfall. That is
> 5.2's cap behaving exactly as specified, and it is still an unsafe default for a
> release gate -- the headline says success over a catastrophically incomplete
> transfer. The failing evidence does exist and is reachable today via
> `gate --phase N`, which fails correctly and names the classes. Until T024b is
> decided, **do not read a bare exit 0 on the gross basis as "nothing was lost" --
> always pass `--phase`.**

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
6. **`starter_subtraction_basis`** -- `no_baseline` means the run cannot pass at
   all. `baseline_matched` is the trustworthy basis; `baseline_gross` makes the row
   advisory for shortfall purposes and caps the whole verdict at
   `CENSUS_ACCOUNTED`.

   **In shipped behaviour you will only ever see `baseline_gross` (T024d).**
   `Lib/census.py` supports `baseline_matched` end to end -- it is in
   `SUBTRACTION_BASES`, `unmatched_starter()` computes from
   `starter_matched_to_source`, invariant checking special-cases it, 5.2's cap skips
   rows carrying it, and phase evaluation treats its shortfalls as trustworthy --
   but **nothing emits it**: the only emitter hardcodes `baseline_gross` on every
   path that has a baseline. This is not a matter of passing the right flag.
   Emitting it needs per-**object-class** matched tallies, and `RunReport`'s
   substitution counts are keyed by `GrammarCategory`, which is not a 1:1 mapping
   for the affix and MSA categories. That is T024d's work, split into a `report.py`
   half that tallies per class and a `census_cli.py` half that wires it in.

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

Or, equivalently and preferably, with the shipped subcommand -- which recomputes the
verdict from the artifact's own evidence and never trusts its stored `verdict` /
`exit_code`, so a document claiming `CENSUS_CLEAN` over an absent baseline is still
refused:

```powershell
python -m gramtrans.census_cli gate `
  --artifact scratchpad/038_census/GT-20260819-030049-census.json `
  --phase 1
```

### Idempotency (SC-008)

Run the transfer a second time into the same destination, take a third census, and
compare: the second run must add no objects.

```powershell
python -m gramtrans.census_cli diff `
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

> **Several figures in the paragraph above are under correction -- do not pin a test
> to them yet (T024, T024c).** Measured live 2026-08-19: the `MoStemMsa` 1949 -> 0
> source is **`Ngoreme FLEx`**, not `Ngoreme`; the `MoInflAffixTemplate` 8 -> 0 /
> `MoInflAffixSlot` 11 -> 0 pair is **Ejagham**, while the Ngoreme pair loses 13 and
> 19; and **`MoAffixAllomorph` +13 is not reproducible** on this machine -- the
> conversion signature that *is* reproducible is `MoAffixProcess` 1 -> 0 beside
> `MoAffixAllomorph` 146 -> 147 on the Ngoreme pair. `PhPhoneme` 41 -> 64 verified
> exactly. Separately, T024's live half censuses two projects **as they sit on
> disk** and never runs a transfer, so it cannot yet sanity-check one; T024c rebuilds
> it as restore -> pre-transfer census -> full transfer -> post census. Owned by
> T024/T024c, not by this file.

The two measured targets are disposable test projects and will be re-created rather
than repaired (spec Assumptions), so they are safe to census repeatedly.

**Do not** run any of this against the FLEx project named `Target` while another
session holds a live write on it.
