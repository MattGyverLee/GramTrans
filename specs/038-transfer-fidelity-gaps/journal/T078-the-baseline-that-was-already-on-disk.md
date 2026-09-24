# T078 - the baseline that was already on disk, and the corpus that was never asked

**Date**: 2026-08-25
**Task**: T078 (Phase 9 Wave 1), the post-037 re-census and the re-scoping of
R7's report-only residual set.
**Branch**: `038-transfer-fidelity-gaps`, worktree
`D:\Github\_Projects\_LEX\GramTrans-038-transfer-fidelity-gaps`, clean at
`2482a53` when this started.
**Artifacts**: `tests/integration/_snapshots/census-038-t078-ejagham.json`,
`census-038-t078-ngoreme.json`, `census-038-t078-mbugwe.json`,
`process-rules-038-t078-corpus.json`.
**Filed**: **T107** (`PhSimpleContextBdry`'s co-create path).

## The one-line version

The post-037 baseline had been sitting on disk for a day: 037 merged on
2026-08-19, so every census this feature has taken since -- T077's, T095's,
T098's, T099's -- was already post-037, and T078's fresh read-only run
reproduces the newest of them row for row, 75 rows, 0 differing, every total
equal. What the re-run bought was not a number. It was the proof that the
numbers are current, and -- because it censused all **three** sanctioned pairs
instead of the one a given task happened to need -- one finding: `Ejagham W
Mini` blocks 13 of 13 of its affix process rules on `PhSimpleContextBdry`, the
class T076 had put behind the FR-025 skip because no corpus exercised it.

## Correcting the premise, first, because that is the fifteenth time

The task line says "re-run the census **after 037 lands** to obtain the
post-037 baseline". The coordination table dates 037's landing to 2026-08-20.
The actual commit is `a824b8d`, *"Merge branch '037-phon-nc-features': stop
phonology transfer losing rule content"*, dated **2026-08-19**, and it is on
`main` **and** an ancestor of the 038 worktree's `HEAD`:

```
git merge-base --is-ancestor 7daaa3b HEAD   -> 0
git merge-base --is-ancestor a824b8d main   -> 0
```

So the gate T078 was waiting behind had opened before this feature's Phase 3
was finished. Six days and roughly thirty commits of census artifacts were
produced on the far side of it. "Re-run after 037 lands" was, by the time
anybody could act on it, a request to re-run something that had already been
run four times.

That is not the end of it, because "T098/T099 already did it" is *also* wrong,
for the opposite reason. Those two artifacts were post-037 and are **stale**:

| artifact | source digest | destination digest |
|---|---|---|
| `census-038-t098-ejagham` (2026-08-22) | match | **drifted** |
| `census-038-t099-ngoreme-after` (2026-08-21) | **drifted** | **drifted** |
| `census-038-t095-ejagham` (2026-08-24) | match | match |
| `census-038-t095-ngoreme` (2026-08-24) | match | match |
| `census-038-t077-mbugwe-phase6` (2026-08-22) | match | match |

Measured T102's way -- each artifact's own recorded `fwdata_sha256_after`
against the file on disk, no FLEx host, no project opened. T095's runs on
2026-08-24 re-transferred both destinations, and `Ngoreme FLEx` itself moved
(FieldWorks had it open on 2026-08-22 and closing it rewrote the file). So the
question "is a re-run needed?" has two true answers that point in opposite
directions, and the correct one is the third: **the baseline was already on
disk, but not in the artifacts the task brief named.**

## The baseline, and what the re-run actually proved

Three read-only `census_cli run` invocations, 2026-08-25, on the three
sanctioned pairs. No project was written; the CLI digests each `.fwdata` before
the open and after the close and refuses if it moved, and all six blocks record
`opened_read_only: true` with `before == after`.

| pair | source -> destination | verdict | exit |
|---|---|---|---|
| ejagham | `Ejagham W Mini` -> `GT038 Ejagham After` | DUPLICATE_IDENTITY | **3** |
| ngoreme | `Ngoreme FLEx` -> `GT038 Ngoreme After` | DUPLICATE_IDENTITY | **3** |
| mbugwe | `Mbugwe LizzieHC practice` -> `GT038 Phase6 Target` | DUPLICATE_IDENTITY | **3** |

**Exit 3, three times, and it is written down rather than laundered.** The
verdict is `PhNCFeatures` duplicates -- 3 extra objects on Ejagham, 21 on
Ngoreme, 66 on Mbugwe. That is T082's remaining `038-NK-P3` item, which T098
had already narrowed from four claims to that one class. It is not T078's and
it is not hidden: `test_the_recorded_exit_code_is_reported_and_not_laundered`
asserts the pair `("DUPLICATE_IDENTITY", 3)` on all three artifacts.

Each new artifact reproduces its predecessor -- `census-038-t095-*` for the
first two, `census-038-t077-mbugwe-phase6` for the third:

* **75 rows, 0 differing** on `source_count`, `destination_count_total`,
  `destination_count_net` and `difference`;
* every entry of `totals` equal;
* `verdict_class` and `unexplained_shortfall` equal too, on every row -- which
  is the *stronger* claim and is only assertable because `Lib/census.py` and
  `census_cli.py` are **untouched since `8169f6f`** (`git log 8169f6f..HEAD --
  src/gramtrans/Lib/census.py src/gramtrans/census_cli.py` is empty). T102's
  lesson is exactly that a row-for-row match proves nothing about an instrument
  that moved in between, so the instrument's stillness is the load-bearing
  fact, not the match.
* the **only** fields that differ at all are two path strings
  (`starter_baseline.path`, `transfer_run.report_path`, absolute vs relative).

Engine changes between the predecessors and now: `T106` only, for the
Ejagham/Ngoreme pair. T106's own closing note is what makes this safe to state
rather than guess -- six of its seven latent finders sit behind
`_VERB_VERTICAL_ENABLED = False`, and its one live defect was
`_execute_overwrite`'s MSA branch, whose subject is `SlotsRC`, *a reference
collection*, so **no census row can move on its account and `total_shortfall`
reads the same either way**. The Mbugwe destination is older still (T077's
engine), and re-creating it would need a live WRITE. T078 did not do that; a
census re-run is read-only by contract, and the safety rules say to report
rather than write.

## The re-scoped report-only residual set

This is the deliverable T079 consumes. Differences are
`(ejagham, ngoreme, mbugwe)`. Every class R7 names appears in exactly one
group, and
`TestT078TheRescopedReportOnlyResidualSet::test_every_class_r7_named_is_scoped_exactly_once`
asserts the two groups are disjoint and together equal R7's list -- so a class
cannot leave scope by being forgotten, which is what a prose re-scoping cannot
prevent.

### CLOSED by the post-037 measurement (5) -- MATCHED on all three corpora

| class | R7 said | now | reading |
|---|---|---|---|
| `MoInflClass` | 5 -> 0, "expected to close as a side effect of Phases 1/3" | 2/2, **5/5**, 0/0 | **closed exactly as predicted.** Ngoreme's 5 arrive. |
| `LexEntryInflType` | "+1 excess (R1's create-anyway failure mode)" | 7->7, 3->4, 4->5, **difference 0** on all three, 0 duplicate groups | **closed.** The +1 nets to zero against the starter baseline. |
| `FsSymFeatVal` | part of "the bulk of the `Fs*` cascade" | 51/51, 90/90, 70/70 | **closed.** |
| `FsClosedFeature` | part of the same cascade | 20/20, 24/24, 21/21 | **closed.** |
| `FsComplexFeature` | "stays report-only" *by decision* | 1/1, 2/2, 1/1 | **report-only and green.** R7's evidence recorded 1 -> 0 and 2 -> 0; both now arrive. This is precisely R7's own residual risk -- "a report-only class can stay broken indefinitely once it has a report line" -- inverted: it is a report-only class that is *not* broken and whose report line would say nothing. T079's `status: "unmeasurable"` is the answer, and it is T079's to write. |

### STILL OPEN and still report-only (10), with the number behind each

**The phonological-context family.** R7 deferred all six "to the post-037
re-census since 037's structural-rebuild path may already move these". The
post-037 answer is **037 moved none of them**.

| class | difference (E, N, M) | reading |
|---|---|---|
| `PhSequenceContext` | -40, -2, -11 | stays report-only. T076/T077 moved Mbugwe **-17 -> -11** and Ngoreme -3 -> -2. Moved, not closed. |
| `PhSimpleContextNC` | -38, -7, -23 | stays report-only. T076/T077 moved Mbugwe **-28 -> -23**. |
| `PhSimpleContextSeg` | -27, -3, -21 | stays report-only. T076/T077 moved Mbugwe **-23 -> -21**. |
| `PhSimpleContextBdry` | -9, -4, -15 | **RE-SCOPED.** No longer "deferred to the re-census"; it now has a measured consequence and a named owner, **T107**. See below. |
| `PhCode` | -43, -89, -79 | stays report-only. Destination is **25 on all three pairs** -- exactly the starter baseline, i.e. not one `PhCode` was created in any run. All three rows are on `baseline_gross` and advisory-capped; the T048d identity audit supplies only an upper bound on the loss. |
| `PhFeatureConstraint` | 0, -47, -32 | stays report-only. MATCHED on Ejagham because Ejagham holds none. |

**Named individually by R7 outside the phonology family.**

| class | difference (E, N, M) | reading |
|---|---|---|
| `LexReference` | 0, **-5**, 0 | stays report-only. R7's "5 -> 0" reproduces exactly, unchanged. |
| `CmFile` | 0, **-2**, **-2173** | stays report-only, **but the number does not survive re-scoping.** R7 records "`CmFile` 2 -> 0" as a property of the transfer; it is a `Ngoreme FLEx` reading. On Mbugwe it is 2173 -> 0, three orders of magnitude larger. Pinned by `test_the_two_r7_figures_that_were_a_single_corpus_all_along`. |

**The half of the `Fs*` cascade that did NOT close.**

| class | difference (E, N, M) | reading |
|---|---|---|
| `FsFeatStruc` | -138, **-1691**, -198 | stays report-only. R7's expectation that "the bulk of the `Fs*` cascade" would close as a side effect held for two of four members and failed for these two, which carry all the volume. |
| `FsClosedValue` | -562, **-2045**, -630 | stays report-only. |

### Ruled on separately by R7, and confirmed unchanged

* **`FsFeatStrucType` -- NOT report-only, a Phase 1 prerequisite. SATISFIED.**
  R7 promoted it out of report-only because ~2,083 restored MSAs would
  otherwise carry an unsatisfiable `TypeRA`. R7's evidence recorded **4 -> 0 in
  both projects**; the baseline reads **3 + 1 -> 3 + 1**, MATCHED on each half,
  on Ejagham and Ngoreme (6 + 1 on Mbugwe). R7's third finding is visible in
  the same rows: the two-feature-system amendment is live, so the class is two
  rows disambiguated by `owning_feature_system` -- `LangProject.MsFeatureSystemOA`
  and `LangProject.PhFeatureSystemOA` -- rather than one ambiguous total.
* **`CmAnthroItem` -- excluded from the delta, not reported as a shortfall.**
  859 -> 0, `NOT_EVALUATED`, `unexplained_shortfall` 0 on all three. Pinned so
  the exclusion cannot quietly become either a shortfall or a match.
* **texts / wordforms -- governed by their own feature, still report-only, and
  the magnitude is the point.** On Ngoreme alone, `WfiWordform` -8191,
  `WfiMorphBundle` -4977, `Segment` -26666, `StTxtPara` -5568, `StText` -4903,
  `WfiAnalysis` -1628, `WfiGloss` -752 -- over 50,000 objects across seven
  classes, which is why `total_shortfall` (70,646 on that pair) is unusable as
  a headline for this feature's work. `CmTranslation` -7923 and
  `PunctuationForm` -3994 sit in the same path.

## The finding: a premise falsified by a corpus nobody asked

T076 held `PhSimpleContextBdry` and `PhIterationContext` behind
`_PROCESS_UNEXERCISED_CLASSES` and said why, in the code, with a number:
`Mbugwe LizzieHC practice` holds **22** and **11** of them in
`PhPhonData.ContextsOS` and **not one is referenced by any of its 18 affix
process rules**, so admitting them "would ship a create path no corpus can
check".

**That measurement is correct and still reproduces.** Mbugwe is 18/18. What
does not survive is the inference, because it was taken on one corpus. Derived
read-only from the run reports the T078 censuses judge
(`process-rules-038-t078-corpus.json`):

| corpus | rules | reproduced | not | blocked by |
|---|---|---|---|---|
| `Mbugwe LizzieHC practice` | 18 | **18** | 0 | -- |
| `Ngoreme FLEx` | 1 | **1** | 0 | -- |
| `Ejagham W Mini` | **13** | **0** | **13** | `PhSimpleContextBdry`, 13/13 |
| **corpus-wide** | **32** | **19** | **13** | **`PhSimpleContextBdry`, and nothing else** |

Of Ejagham's 13, **8** name the boundary context as a **direct** input member
and **5** reach it through a `PhSequenceContext` in `PhPhonData.ContextsOS` --
i.e. through exactly the shared-context route T076 built and then declined to
extend to this class. The census row is `MoAffixProcess` **13 -> 0 SHORTFALL**
on Ejagham, MATCHED on both other pairs. The corpus lesson of this feature,
one more time: *a gate is only as good as the pair it ran on.* T091 taught it
about `PartOfSpeech` on Ngoreme; this is the same lesson on Ejagham.

SC-010 is **not** violated. All 13 rules are dropped **with a reason that names
the blocking class**, so the census row has an explanation to point at. This is
a report-only residual behaving exactly as R7 designed -- which is why it stays
report-only, and why what it needed was a re-scope rather than a fix.

**And the reason string is now false.** It reads *"a class with zero instances
in any sanctioned corpus"*. Every sanctioned source holds the class: **10**
(Ejagham), **13** (Ngoreme), **24** (Mbugwe). Those three numbers are pinned by
`test_the_skip_reason_the_engine_emits_is_now_factually_wrong`, and the string
was deliberately **not** changed here -- it is live run-report output for four
classes, and editing it is a reporting change with no census behind it. Same
reasoning T106 used to keep itself out of T095. Recorded as a debt, and part of
T107's scope.

## The project name, checked because it is load-bearing

The evidence comments name **`Ejagham W Mini`**, which is not `Ejagham Mini`.
It is a real, distinct project -- `C:\ProgramData\SIL\FieldWorks\Projects\
Ejagham W Mini\Ejagham W Mini.fwdata`, alongside a separate `Ejagham Mini` --
and it is the source project every prior 038 census used
(`census-038-t095-ejagham.json`, `census-038-t098-ejagham.json`, and T024's
corrected-premise note in `tasks.md`, which distinguishes the two by name for
the same reason). Not a typo, and worth writing down: T076's own docstring
names `Ejagham Mini` as holding "ZERO `MoAffixProcess` rules", which is true of
`Ejagham Mini` and false of `Ejagham W Mini`, and the two-word difference is the
whole finding above.

## What was deliberately NOT done

* **Admit `PhSimpleContextBdry` to the co-create path.** That is a create-path
  change in `categories.py`, US5's territory, and a live-behaviour change that
  needs its own restored-target census. Filed as **T107** with the acceptance
  spelled out. Doing it inside a read-only re-census task would have been the
  shape T106 refused.
* **Correct the drop-reason string.** See above. Pinned, not patched.
* **Overwrite any earlier snapshot.** T077's and T102's rule: the
  `census-038-*-phase6.json` chain is asserted pairwise by
  `test_038_closure_edge_audit.py`, and T078 writes a new `t078` suffix so
  nothing unrelated turns red.
* **Restore or write anything.** All three censuses are read-only; `Ngoreme
  Target` was not touched, `Esperanto` was not opened, and no `Target` restore
  was needed because no write was needed. Re-creating the Mbugwe destination on
  the current engine WOULD need a write; that is reported, not performed.
* **Relax the tripwire that fired.**
  `TestT101TheCommittedCorpusIsUnmovedByInvariant12::test_every_committed_null_row_is_advisory`
  pins the count of committed artifacts that null a row, and the three new
  censuses took it **9 -> 12**. Edited deliberately, with the evidence recorded
  in place: clause 1 -- the one that fails on a genuinely *new* null -- passed
  untouched, because each of the three nulls exactly `MoForm` and
  `MoMorphSynAnalysis`, and each is separately asserted to reproduce its
  predecessor row for row, so these are the same **rows** and not merely the
  same classes. Same reading T089's and T104's links earned.
* **Re-litigate T082.** Exit 3 on all three pairs is `PhNCFeatures`
  duplicates, which is T082's `038-NK-P3`. Reported, not folded in.

## The unmerged branch, since it bears on the word "baseline"

`038-affix-fidelity` (`18c0ece`) is **still unmerged**, and the land order R6
declares is `037 -> 038-affix-fidelity -> this feature -> re-census`. So this
baseline is post-037 and **pre-`038-affix-fidelity`**, and it is the baseline
for *this feature's* Phase 9 scoping, not for the release. Whatever
`038-affix-fidelity` changes in the affix path will move rows this artifact
pins, and the T078 tests are written to go red and be edited rather than to
absorb it silently. The three defects that branch carries are ones spec.md's
Assumptions already declare fixed, which is exactly why it must land before
US5's gate and not after.

## Suites

| suite | before T078 | after |
|---|---|---|
| `tests/integration` | 528 passed, 0 failed, 75 skipped | **577** passed, **0 failed**, 75 skipped |
| `tests/unit` | 3693 passed, 79 skipped, 14 xfailed | **3693** passed, 79 skipped, 14 xfailed |

+49 integration tests, all T078's. The unit count is unchanged because the two
edits there are docstring corrections, not new assertions -- which is the
honest shape for a task whose product is a measurement and a re-scoping rather
than a behaviour change.

The intermediate red is worth recording: with the three new snapshots present
and no test edits, the run was **1 failed, 527 passed, 75 skipped** -- the T101
corpus tripwire, firing exactly as designed on an artifact arriving. It was
read before it was edited.
