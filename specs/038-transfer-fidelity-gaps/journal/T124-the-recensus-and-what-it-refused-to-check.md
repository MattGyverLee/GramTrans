# T124 -- the re-census, and the four tasks it refused to check

**Date:** 2026-08-27
**Instrument:** `debug/run038_t124_recensus.py` (new), which drives
`harness.restore.restore_target` -> `harness.full_run.run_full_transfer` ->
`gramtrans.census_cli run` -> `census.evaluate_phase(artifact, 5)` and then
re-uses the Wave 1 owner probe (`debug/run038_phase10_owner_probe.py`) plus two
supplements it does not carry.
**Artifacts:**
`tests/integration/_snapshots/census-038-t124-{ejagham,ngoreme,mbugwe}.json`,
`tests/integration/_snapshots/recensus-038-t124-{ejagham,ngoreme,mbugwe}.json`,
`specs/038-transfer-fidelity-gaps/probes/t124/owner-probe-GT038-T124-*.json`,
`specs/038-transfer-fidelity-gaps/probes/t124/t124-supplements-*.json`,
`scratchpad/038_t124/ejagham-full.log` (3,206 lines, full stderr).

---

## 0. The one-line answer

All four of T124's obligations are discharged. **P5 is not satisfied on any
pair** (9 / 16 / 13 failures), so T081 stays open for a third time. Of the five
Wave 2 tasks T124 gates, exactly **one** (T122) earns its check; the other four
are measured and fail their own acceptance lines, each for a different and
newly-located reason.

---

## 1. Obligation 1 -- the comparand. T081's premise was false.

T081 said "the sources have moved off their pinned digests -- the T078 trio is
not reproducible as measured". Measured against
`$.projects.{source,destination}.fwdata_sha256_after` in the three committed
T078 artifacts:

| project | role | recorded | now | status |
|---|---|---|---|---|
| `Ejagham W Mini` | source | `5ad15c10...c2c5c3ea` | same | **MATCH** |
| `Ngoreme FLEx` | source | `838b7635...b23b607f` | same | **MATCH** |
| `Mbugwe LizzieHC practice` | source | `fb6aadab...226c3161` | same | **MATCH** |
| `GT038 Ejagham After` | destination | `f3f99837...02b5aaeb` | `56283578...1bae0660` | DRIFTED |
| `GT038 Ngoreme After` | destination | `979fbdf6...e5b61bb7` | same | **MATCH** |
| `GT038 Phase6 Target` | destination | `28c89140...33003a4ab` | `276dca27...ba6de66e` | DRIFTED |

**Every source is on its pin.** The drift is entirely destination-side and on
two of three, and the repo's own `T078_FWDATA_STATUS_TODAY`
(`test_object_census.py:6396`) already records exactly this table --
`TestT078ThePost037Baseline` passes 20/20. So no source needed re-pinning and
no fresh sanctioned pair needed naming; T081's sentence was describing a
problem that measurement does not support.

**What was re-pinned instead: the destination half, into three fresh
throwaways** -- `GT038 T124 Ejagham` / `GT038 T124 Ngoreme` /
`GT038 T124 Mbugwe`, each restored from `backups/Target 2026-07-06 0218.fwbackup`.
The T078 trio's figures are **historical by being kept, not overwritten**, and
that was verified after all three transfers: all three T078 destinations still
hash to the values in the table above.

**Why not `run038_before_after_pairs.py --tag t124`.** That driver writes into
`GT038 Ejagham After` / `GT038 Ngoreme After`. Two things break:
`T078_FWDATA_STATUS_TODAY` asserts the digest-status table and a
`drifted` -> `match` flip is as red as the reverse, with no backup of any of
the three as they now stand; and its `_EVIDENCE_TARGETS` guard covers only two
of the three and fires only on `--no-census`. **`GT038 Ngoreme After` -- the
only destination still byte-identical to its T078 pin, and so the single most
load-bearing comparand in the feature -- is guarded by nothing.** The new
driver refuses all six protected names unconditionally.

**The one place comparability is lost, stated rather than smoothed over.**
T078's ejagham and ngoreme artifacts were measured against
`contracts/starter-baseline.json`, and this run uses the same document, so
their NET columns are comparable. T078's **mbugwe** artifact used
`scratchpad/038_census/phase6-starter.json` as it stood at
`captured_at 2026-08-22T08:38:06`; that file has since been re-captured in
place (now `2026-08-25T14:35:56`) and the 08-22 capture is committed nowhere.
The mbugwe NET column is therefore **not** comparable to T078's mbugwe NET
column, and the driver prints that warning on every mbugwe run.

---

## 2. Obligation 2 -- P5. Unsatisfied on all three, and not by the outranked route.

Read via `census.evaluate_phase(artifact, 5)`, **not** the exit code:
`gate_artifact` returns `exit_code_for(verdict)` and `DUPLICATE_IDENTITY`
outranks anything a phase can say, so the process exits 3 whether or not P5
holds. The phase answer exists only in-process.

| pair | `p5.satisfied` | failures | run verdict |
|---|---|---|---|
| ejagham | **False** | 9 | `DUPLICATE_IDENTITY` (exit 3) |
| ngoreme | **False** | 16 | `DUPLICATE_IDENTITY` (exit 3) |
| mbugwe | **False** | 13 | `DUPLICATE_IDENTITY` (exit 3) |

T124's text allowed for "if `PhNCFeatures` is still driving
`DUPLICATE_IDENTITY` then P5 is satisfied with the run verdict outranked, which
this task must state rather than paper over". **That clause does not apply.**
`PhNCFeatures` duplicates (3 / 21 / 112-class-matched-with-duplicates) do still
drive the verdict -- that is T082's `038-NK-P3` -- but P5 fails on its own
merits, on 38 row failures across three pairs, every one of the shape
"SHORTFALL carrying NO accounting line".

---

## 3. Obligation 3 -- `LexReference`. Discharged on ngoreme alone, and the
## MappingType rulings were never reached.

Stated on ngoreme only: ejagham and mbugwe carry `LexReference` source_count 0
on both sides, so their rows cannot corroborate anything.

**Source enumeration now works.** T123's `ILexRefType` cast recovers what was
0: the source reads 5 relations, and they distribute exactly as T123/T124
predicted --

| owning type | `MappingType` | kind | source refs | targets | destination |
|---|---|---|---|---|---|
| `Specific` | 3 | TREE | 3 | 2, 2, 2 | **0** |
| `Synonyms` | 0 | COLLECTION | 1 | 2 | **0** |
| `Calendar` | 4 | SEQUENCE | 1 | 13 | **0** |

**Not one of the 5 survives.** Census row: `LexReference` SHORTFALL -5.

**And the failure is one hop earlier than the question T124 was written to
ask.** The run report carries 5 `dropped_items` with
`owner_kind="LexRefType"`, `field_name="MembersOC"`, reason
**"lexical relation type not found in target"** -- one per relation. So the
per-`MappingType` structural rulings (a TREE relation survives only if
`TargetsRS[0]` was copied) were never consulted: every relation died because
its owning `LexRefType` is absent from the destination. The right next question
is not "do the tree rulings hold" but "why is the Lexical Relations type list
not in the destination".

**A reporting defect in those 5 records, found while reading them.** Each has
`item_guid` equal to its own `owner_guid`, and `owner_label` / `item_name`
empty. The record names the relation TYPE twice and never names the relation it
dropped, so five distinct losses are indistinguishable from five copies of one.

---

## 4. Obligation 4 -- the nesting assertion. Discharged per GUID, and 5
## demotions are silent.

Count buckets cannot answer this: the destination is restored from a backup
that already carries `LexEntryInflType` of its own, so "2 nested / 5
top-level" mixes starter items with transferred ones. The supplement therefore
matches **source GUID -> destination GUID** and classifies each object.

| pair | source shape | destination shape | same | **demoted nested -> top** | absent |
|---|---|---|---|---|---|
| ejagham | 6 nested / 1 top | 2 nested / 5 top | 3 | **4** -- `Perfective`, `Hortative`, `Conditional`, `Retrospective` | 0 |
| ngoreme | 2 nested / 1 top | 2 nested / 2 top | 3 | **0** | 0 |
| mbugwe | 3 nested / 1 top | 2 nested / 3 top | 3 | **1** -- `Class 10` | 0 |

Ejagham's arithmetic closes exactly: 6 - 4 = 2 nested, 1 + 4 = 5 top-level,
with `absent=0` and `dest_only=0`, so there is no starter contamination in the
reading at all. **The 2/5 shape the ruling called wrong is still exactly what
arrives**, and it is 4 named objects, not a rounding artifact.

**The nesting fix is NOT uniformly broken** -- ngoreme demotes nothing, and 3
of 4 nestings hold on mbugwe. It fails on ejagham, on 4 of 7.

**The demotion is silent, and this is a separate defect from the nesting one.**
`straggler-rulings.md` section 1 promises "a reported demotion to top level"
via `_log_possibility_demoted` (`categories.py:11891`). That function logs to
`logging.getLogger("gramtrans.Lib.categories").warning(...)` -- not to the run
report -- so the run-report JSON was the wrong place to look. Re-run with full
stderr captured (`scratchpad/038_t124/ejagham-full.log`, 3,206 lines): the log
**does** carry 9 `WARNING` lines from `gramtrans.Lib.wordforms`, proving the
stream is captured and warnings do reach it, and it carries **zero** occurrences
of `TOP LEVEL` or `should nest under` while the same run demotes the same 4
objects. `_log_possibility_demoted` is never called on the path that actually
demotes these four.

**Also found, by GUID, on the `LexEntryType` row:** two objects are absent
outright rather than demoted -- ngoreme's `Perfective` (source nested) and
mbugwe's `Periphrastic Form` (source top-level). That is the -1 / -1 that
`straggler-rulings.md` section 3 predicted against the census's gross -12 /
-12, now confirmed by identity and with both objects named.

---

## 5. T119, per pair AND per owning field -- the acceptance it was owed

`$.classes.FsFeatStruc.owners` in the Wave 1 probe is already keyed
`OwningClass.Field (flid=N)`, so no census schema bump was needed. Source
column from the committed Wave 1 probes (valid: all three sources are on their
pinned digests); destination column measured fresh.

| owning field | ejagham | ngoreme | mbugwe |
|---|---|---|---|
| `MoStemMsa.MsFeatures` (5001001) | 117 -> **0** | 782 -> **0** | 104 -> **0** |
| `FsComplexValue.Value` (53001) | -- | 825 -> 20 | -- |
| `PartOfSpeech.ReferenceForms` (5049010) | 10 -> 10 | 44 -> **0** | 19 -> 18 |
| `PhPhoneme.Features` (5092002) | 41 -> 20 | 41 -> 21 | 42 -> 23 |
| `PhNCFeatures.Features` (5094001) | 15 -> 15 | 41 -> 41 | 112 -> 112 |
| `MoInflAffMsa.InflFeats` (5038001) | 86 -> 86 | 38 -> **38** | 78 -> 78 |
| `CmAnnotation.Features` (34008) | -- | -- | 39 -> **0** |
| `MoDerivAffMsa.FromMsFeatures` (5031001) | -- | -- | 17 -> **17** |
| `MoDerivAffMsa.ToMsFeatures` (5031002) | -- | -- | 17 -> **17** |
| `MoAffixAllomorph.MsEnvFeatures` (5027001) | -- | -- | 1 -> **1** |

**The class-level gain, and it attributes exactly to those fields:**

* ejagham `FsFeatStruc` net **131 -> 131 (+0)**. The destination's 131 are
  86 + 20 + 15 + 10 -- precisely the four owners that already worked. T119's
  eight-owner pass contributed nothing measurable on this pair.
* ngoreme net **80 -> 120 (+40)** = `InflFeats` 18 -> 38 (+20, T119's open
  question, now answered: the complex-value reader fixed it) + the 20 nested
  `FsComplexValue` structures. `FsClosedValue` 495 -> 515 (+20) rides it.
* mbugwe net **231 -> 266 (+35)** = From 17 + To 17 + MsEnvFeatures 1, exactly.
  `FsClosedValue` 722 -> 758 (+36).

**So T119 is neither ineffective nor done.** Three of its eight new owners are
demonstrably built and working -- `MoDerivAffMsa.FromMsFeatures`,
`.ToMsFeatures`, `MoAffixAllomorph.MsEnvFeatures`, all on mbugwe, the only
sanctioned pair that holds them, all measured 0 by Wave 1 and 17/17/1 now. And
its **headline owner is still a total loss on 3 of 3 pairs**:
`MoStemMsa.MsFeatures` 117 / 782 / 104 -> 0 / 0 / 0, **1,003 objects, the
single largest block in the P5 residue**, with `MoStemMsa` itself count-MATCHED
(so no counts-only gate can see it) and the destination probe's
`feature_structure` reading `{"(none)": 153}` -- every MSA arrives hollow.

**It fails silently, which is the part that matters.** The pass IS wired
(`categories.py:9561`) and the producer IS called (`preview.py:1462`), yet the
ejagham and ngoreme run reports contain **zero** occurrences of `MsFeatures`,
and their `skips[]` hold nothing but `ALREADY_PRESENT_BY_GUID`. Mbugwe's report
does carry 2 `MsEnvFeaturesOA` `dropped_items`, which proves
`_wire_owner_feat_strucs` runs and can report -- so for `MsFeaturesOA`
specifically there is neither a write nor a failure record. Whether the
producer yields no binding or the applier never consults it is one preview-only
read away and belongs to T119, not here.

**Two more per-field facts the class row hides.** `PhPhoneme.Features` loses
21 / 20 / 19 structures on the three pairs -- the starter-matched phonemes are
never enriched, which `_populate_msa_feat_struc_bindings`'s docstring assigns
to T121 rather than to this pass. And `PartOfSpeech.ReferenceForms` is
**inconsistent across pairs**: 10 -> 10 on ejagham but 44 -> **0** on ngoreme,
which no single ruling about T045's depth limit explains.

---

## 6. T120 -- the rules arrive whole and their contents leave silently

| row | ejagham | ngoreme | mbugwe |
|---|---|---|---|
| `PhRegularRule` | 6 -> 6 **MATCHED** | 21 -> 21 **MATCHED** | 39 -> 39 **MATCHED** |
| `PhSegRuleRHS` | 6 -> 6 | 21 -> 18 (**-3**) | 39 -> 28 (**-11**) |
| `PhFeatureConstraint` | 0 -> 0 | 70 -> 23 (**-47**) | 89 -> 57 (**-32**) |
| `RightHandSidesOS` drop records | **0** | **0** | **0** |

Every phonological rule arrives. **14 of their right-hand sides do not, and
`_report_dropped_rhs` (`categories.py:13430`) recorded not one of them.** T120's
acceptance was "which right-hand sides actually raise, on which pairs"; the
measured answer is that none raise and the losses stay silent -- which is the
exact defect class T120 was written to convert into a reported one. The shared
constraint pool (`PhPhonData.FeatConstraints`) is unchanged from T078 on both
pairs that have one (23 -> 23, 57 -> 57) against 79 missing constraints, with
one `ExclRuleFeatsRC` and one `ReqRuleFeatsRC` drop between them.

---

## 7. T121 -- the phoneme half passes on 3 of 3; the boundary half cannot be
## shown either way, and the clause is at fault

The starter baseline carries `PhCode` 25 = 23 phoneme codes + 2
boundary-marker codes. `PhCode`'s owning field is `PhTerminalUnit.Codes` for
**both** halves, so the `[runtime=...]` suffix the Wave 1 probe appends is the
only thing that separates them -- normalising it away (which the
`FsFeatStruc` table does on purpose) collapses exactly the distinction the
acceptance is about.

| pair | phoneme codes: starter -> dest (source) | boundary codes: starter -> dest (source) |
|---|---|---|
| ejagham | 23 -> **64** (41) | 2 -> **2** (2) |
| ngoreme | 23 -> **110** (87) | 2 -> **2** (2) |
| mbugwe | 23 -> **100** (77) | 2 -> **2** (2) |

The phoneme half is exact on every pair -- 23 + 41 = 64, 23 + 87 = 110,
23 + 77 = 100 -- and `PhCode` net moves 0 -> 41 / 0 -> 87 / 0 -> 79 against
T078. T121's route works.

**The boundary half is unfalsifiable on these corpora, and that is a defect in
the acceptance clause, not in the code.** All three sources hold exactly 2
boundary-marker codes and the starter holds exactly 2, so "the destination
stops reading exactly the starter baseline" **cannot be true** for that half no
matter how correct the transfer is: 2 = 2 = 2 whether the codes were matched by
identity or never touched. Closing it needs an identity-level check (are the
destination's 2 the source's GUIDs or the starter's?) or a corpus whose
boundary inventory differs -- not another count. This is a T086-style
mis-stated clause and is recorded as one.

---

## 8. T122 -- the one task that earns its check

The Wave 1 probe's `$.classes.CmPossibility.possibility_lists` is the per-list
dimension T122 was waiting on.

| list | ruling | ejagham | ngoreme | mbugwe |
|---|---|---|---|---|
| `MoMorphData.ProdRestrict` | **IN SCOPE** | absent | **1 -> 1** | **3 -> 3** |
| `Scripture.NoteCategories` | out of scope | -- | 115 -> 0 | -- |
| `LexDb.Languages` | out of scope | -- | -- | 15 -> 0 |
| `LangProject.GenreList` | out of scope | 35 -> 29 | 32 -> 29 | 34 -> 29 |
| `DsDiscourseData.ChartMarkers` | out of scope | 67 -> 67 | 37 -> **67** | 77 -> 67 |
| `LangProject.CheckLists` | out of scope | -- | 5 -> 0 | -- |
| `LexDb.DialectLabels` | out of scope | -- | 2 -> 0 | -- |
| `LangProject.Status` | out of scope | 4 -> 4 | 5 -> 4 | -- |
| `DsDiscourseData.ConstChartTempl` | out of scope | 11 -> 11 | 11 -> 11 | 12 -> 11 |
| `LexDb.ExtendedNoteTypes` | out of scope | 5 -> 5 | 4 -> **5** | 4 -> **5** |

**The in-scope list is MATCHED on both pairs that hold it**, and the
class-level net delta against T078 is **exactly** those objects: `CmPossibility`
net 0 -> 1 on ngoreme, 0 -> 3 on mbugwe. Every residual per-list deficit lands
in a list `cmpossibility-list-rulings.md` puts out of scope, and the ruling's
own predicted signs reproduce independently -- `ChartMarkers` a **surplus** on
ngoreme (+30) and a shortfall on mbugwe (-10), `ExtendedNoteTypes` +1 on both
pairs that hold it. A class-level ruling could not have expressed either.

The `CmPossibility` census row stays red for the two reasons the ruling already
names: `Lib/census.py` has no per-owning-list dimension, and gross-basis
subtraction suppresses the row (`unexplained_shortfall` 308 / 397 / 332
advisory). Neither is a transfer defect. **T122's acceptance is satisfied.**

---

## 9. What this closes and what it does not

**Checked:** T122 (per-list, in-scope list matched on both pairs that hold it),
T124 (all four obligations discharged), T125 (T081's third entry written).

**Left unchecked, each with a measured reason:**

* **T119** -- `MoStemMsa.MsFeatures` 0 of 1,003 on 3 of 3 pairs, no write and
  no failure record. Three of eight new owners do work (mbugwe 17/17/1).
* **T120** -- 14 right-hand sides and 79 feature constraints lost with 0 drop
  records; the reporter it added never fires.
* **T121** -- phoneme half passes 3/3; boundary half's clause is unsatisfiable
  by construction on every sanctioned pair and needs amending.
* **T123** -- 0 of 5 `LexReference` survive (and die before any MappingType
  ruling applies); 5 nesting demotions across two pairs, none of them logged.
* **T081** -- P5 unsatisfied on all three, 38 row failures.

**Not touched:** T082 (`038-NK-P2` / `038-NK-P3`; the `PhNCFeatures`
duplicates driving `DUPLICATE_IDENTITY` are its `038-NK-P3`), T085 (merge).

**Test state.** `tests/unit`: **3810 passed, 79 skipped, 14 xfailed, 0 failed**
(30.7s) -- STATUS.md's note about 27 pre-existing failures is stale; they are
gone. `test_object_census.py`: 478 collected, 31 behind `-m integration`;
`TestT078ThePost037Baseline` 20/20 green both before and after all three live
transfers.
