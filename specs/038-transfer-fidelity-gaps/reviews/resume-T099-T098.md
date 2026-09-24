# Resume report - T099 then T098

**Date**: 2026-08-21 into 2026-08-22
**Feature**: 038-transfer-fidelity-gaps
**Worktree (code)**: `D:\Github\_Projects\_LEX\GramTrans-038-transfer-fidelity-gaps`,
branch `038-transfer-fidelity-gaps`, `da5975f` -> `2fce617` (T099) -> `044d644` (T098)
**Root (`main`, specs)**: `7011b5b` -> `bbbbb9b` (T099) -> `46921e6` (T098)

---

## Headline

| task | status | measurement |
|---|---|---|
| **T099** | **CLOSED** | Two live census runs of `Ngoreme FLEx` -> `GT038 Ngoreme After`, 8 minutes apart, projects asserted byte-identical by digest. Exactly **2 rows changed**, 5 fields each `0` -> `null`. Every gate quantity unchanged: `total_shortfall` **70659** both sides, verdict DUPLICATE_IDENTITY / exit 3 both sides. 0 schema errors, 0 section-11 invariant failures on both. Second corpus confirms (`Ejagham W Mini` pair). |
| **T098** | **CLOSED** | The new provenance check run over the **old** values reports exactly **6** disagreements; over the corrected values, **0**. Live confirmation on `Ejagham W Mini` -> `GT038 Ejagham After` with the pre-flight check in the run path: all **7** natural-key classes `roster_admitted: true`, `PhNCFeatures` (one of the six 038 proposed) taking the run to DUPLICATE_IDENTITY exit 3 on 3 extra objects over a difference of 0. |

Both live censuses were run and are committed. Nothing is claimed without a
measurement.

---

## T099 - the census emitted a count it had flagged as false

### What was wrong

`contracts/census-artifact.schema.json` types `$defs.classRow.source_count` and
`destination_count_total` as `["integer", "null"]`, with the meaning written
out: *"null only on a NOT_EVALUATED row where the class could not be counted at
all; a genuine zero is 0, never null"*. `models.ClassCensusRow` declared
`source_count: int`. One narrowing, two failures in opposite directions:

* `census_cli._row_for_entry` emitted `0/0` for every `excluded_not_measurable`
  class with a note calling its own numbers placeholders. Two rows per artifact,
  every census this feature has taken.
* `census_cli._report_unmeasurable` **aborted the whole run** for a class whose
  repository accessor did not resolve - loud in the console, silent in the
  record, because no artifact was written.

### Measurement

`_snapshots/census-038-t099-ngoreme-before.json` / `-after.json`. Same baseline,
same run report, source digest `2b80aadf...` and destination `416b8a0e...`
before *and* after on both. This matters: `Ngoreme FLEx` has drifted since T096
(a diff against the committed T096 artifact would have shown 10 moved rows and
`total_shortfall` 70638 -> 70659 as if the fix had done it), which is why the
pair was measured back to back rather than diffed against history.

Delta: `MoForm` and `MoMorphSynAnalysis`, five fields each (`source_count`,
`destination_count_total`, `destination_count_net`, `difference`,
`difference_raw`) `0` -> `null`. `totals` byte-identical
(`total_shortfall` 70659, `unexplained_shortfall` 68941,
`classes_not_evaluated` 3, `classes_matched` 41). Whole-document remainder
identical but for `instrument.gramtrans_dirty`.

### The three places the `int` was load-bearing, none predicted by the filing

1. **`census.class_row_artifact` would have DROPPED the fix.** It skipped any
   mapped field whose value was None, on a comment asserting no REQUIRED field
   could be None - true only *because* the model lied. The honest fix would have
   omitted three `$defs.classRow.required` keys and produced an invalid
   artifact. The guard is now on the field NAME
   (`models.CLASS_ROW_REQUIRED_NULLABLE_FIELDS`, derived in the test from the
   schema's own `required` array).
2. **`verdict_class` compared `difference == 0` before checking None** - the
   exact line where a placeholder zero became the word MATCHED.
3. **`counts_pass` did the same**, where `None == 0` is False, so an uncounted
   gate-relevant row would have FAILED on counts and reported a loss nobody
   measured.

### The abort became a row and stayed loud

`_print_unmeasurable` keeps every `[FAIL]` line and the "may not fail QUIETLY"
summary, and now returns the entries, which become `errors[]` - CENSUS_ERROR /
exit 7 in `recompute_verdict`, which the gate recomputes rather than reads.
`capture_baseline` **keeps** its abort deliberately: a baseline is a count map a
later run SUBTRACTS, a null there would be subtracted as 0 by the arithmetic 5.2
forbids, and a baseline document has no `classes` array for a row to go into.

### The predicate re-read (T099 asked for it)

The library was already null-ready in about a dozen places -
`net_destination_count`, `signed_difference`, `unexplained_counts`,
`row_verdict_class`, `MatchBasis.sums_to`, `build_totals`, `row_passes`,
invariants 3/4/11, and `census_cli diff`'s `isinstance(old, int)` guard whose
message already read *"a null destination_count_total on one side"* - **and all
of it was dead**, because a `ClassCensusRow` could not produce the input. This
fix added no null handling; it made a feature-long accumulation of it reachable.
First appearance of this feature's recurring shape where the thing read at the
wrong level is the **handling itself**, unreachable from the type of a dataclass
field.

* `_require_matched` (P1-P4) reads `verdict_class` and FAILS on NOT_EVALUATED -
  the safe direction, now pinned.
* `_phase_5` `continue`s on NOT_EVALUATED without failing. Caught only by the
  `errors[]` entry (exit 7) that put the row there. Part of why T101 is filed.
* `census_cli diff` moves the two rows from "compared and equal" to "not
  compared" (`[INFO]`, no verdict change) - a small, correct coverage loss:
  comparing two falsehoods and finding them equal was never evidence.

### A hole the fix itself opens - closed on the producer, filed on the gate

A test written to prove the opposite failed. A null difference reads
NOT_EVALUATED and `row_passes` returns True for NOT_EVALUATED, so **nulling a
required class retires its shortfall without measuring anything** - unreachable
before only because the model refused to hold a null.
`_refuse_uncorroborated_nulls` now states the prohibition on the producer (a
required row may carry a null only if it is advisory or named in `errors[]`). The
GATE still accepts an uncorroborated null in a hand-authored artifact; that is a
property of the artifact FORMAT and changes what every committed artifact is
judged by, so it is **T101**, with current behaviour pinned by a test that fails
the day T101 lands.

### New tasks filed

* **T100** - the closed 17-token reason vocabulary has no member meaning "the
  repository accessor did not resolve", so an unresolved-accessor row cannot
  carry the `not_evaluated_reason` the schema's `$comment` asks for.
  `ABSENT_BY_CONSTRUCTION` would be a false statement. A contract amendment with
  T096's exact-match tripwire attached, not a code change.
* **T101** - the gate accepts an uncorroborated null count on a gate-required row
  and gates exit 0.

### Pins deliberately moved (both wording, neither a relaxation, both journaled)

* `_NOT_MEASURED_NOTE` no longer calls its own counts placeholders. Leaving it
  verbatim would put a false statement into every line it produces - T096's
  `SOURCE_REFERENT_ABSENT_DETAIL` lesson. Old text preserved in the constant's
  comment.
* `_report_unmeasurable` split into a reporting half and a raising half. No test
  asserted on it before; the `capture_baseline` raise is pinned now and was not.

---

## T098 - the field that recorded which document admits a natural key

### The filing's premise needed correcting first

T098 says "the designed tripwire did not fire". The sentence it quotes
(`census.py:1561-1565`) is in the docstring of **`roster_admitted_classes`**,
which reads 035's roster at run time - and that fired exactly as promised.
Measured live with the new check in place
(`_snapshots/census-038-t098-ejagham.json`, 0 schema errors, 0 invariant
failures):

| class | `roster_admitted` | groups | extra | src -> dst | diff |
|---|---|---|---|---|---|
| `PhPhoneme` | true | 0 | 0 | 41 -> 43 | 0 |
| `PhNCSegments` | true | 0 | 0 | 3 -> 4 | 0 |
| `PhNCFeatures` | true | **1** | **3** | 15 -> 15 | 0 |
| `PartOfSpeech` | true | 0 | 0 | 20 -> 20 | 0 |
| `MoMorphType` | true | 0 | 0 | 19 -> 19 | 0 |
| `LexEntryInflType` | true | 0 | 0 | 7 -> 7 | 0 |
| `WfiWordform` | true | 0 | 0 | 429 -> 132 | -297 |

All seven admitted with no edit in `NATURAL_KEY_DEFINITIONS`, and admission is
doing work: `PhNCFeatures` - one of the six 038 proposed - takes the run to
DUPLICATE_IDENTITY / exit 3 on a row whose `difference` is 0. Section 6's whole
argument, on a newly admitted class.

Getting this right matters because "the tripwire did not fire" would have sent
the fix at a mechanism that needs nothing.

### What actually had no reader

`NaturalKeyDefinition.roster_source` had a default (`"roster_extension_038"`)
that six of seven definitions inherited, and a seventh (`WfiWordform`) overrode
with the other spelling. Two writers disagreeing about the same question, with
the field read nowhere in `src/` or `tests/`. From 2026-08-19 the six inherited
values were simply false, and nothing could say so.

### The fix - the "give it a consumer" arm

Chosen over deletion because the check is worth more than the field: it is the
only thing in the tree that would notice a roster **removal**.

1. The **default is gone** - a definition cannot acquire a provenance claim by
   omission. Pinned by reading `dataclasses.fields`, not a source line.
2. The value is a **closed two-member vocabulary** validated in `__post_init__`
   (`ROSTER_SOURCE_035` / `ROSTER_SOURCE_038_PROPOSAL`). A typo here used to be
   checked against nothing.
3. `roster_source_disagreements` checks every claim against **both** documents -
   both, because 038's extension is the proposal RECORD and is not emptied on
   landing, so a class legitimately appears in both files and provenance cannot
   be inferred from presence. `verify_roster_sources` raises before
   `census_cli.run` opens a project, on the same grounds `derive_class_list`
   raises on a CP-1 mismatch.

### Measurement

| values | disagreements |
|---|---|
| pre-fix (six inheriting the proposal claim) | **6** |
| pre-fix, `WfiWordform` alone | **0** (already right) |
| post-fix | **0** |

A test rebuilds the old table and runs the check on it, so the 6 is a test and
not a sentence. It also fires in the direction nothing else can see: a claim of
035 admission for a class 035 does not admit.

### T082's two pending roster items - checked as T098 asked

* **`038-NK-P2` - NOT settled, and cannot be by a merge.** The roster still lists
  it PENDING; every appended entry sets `key_unique_by_construction: false` and
  relies on `on_ambiguous_key: harness_error`, which the roster itself calls
  "safe under either outcome". Answerable only by a live attempt to create a
  duplicate name - throwaway project only, as T082 already requires.
* **`038-NK-P3` - largely ANSWERED, mixed, and NARROWED from four claims to one
  class.** Measured on both pairs: the 2088 MSAs are recovered (Ngoreme
  `MoStemMsa` 1953 -> 1951, 2 residual, other three MSA classes matched; Ejagham
  153/153 and 111/111); the 21 duplicate PHONEME names are gone (0 groups on
  both); `PartOfSpeech` MATCHED with 0 duplicates on both; `LexEntryInflType`'s
  +1 nets to 0. **But the duplicate count did not go to zero - it moved class**:
  `PhNCFeatures` carries 12 groups / 21 extra on Ngoreme and 1 / 3 on Ejagham,
  and both re-censuses exit 3. P3's acceptance is "recovery verified by
  re-census", and a re-census that exits 3 does not verify it. T082 stays open
  with a note recording the narrowing. (The Ngoreme 21 and the original phoneme
  21 are the same number on different classes; nothing measured establishes a
  relationship, and treating the coincidence as a lead would be inventing a
  mechanism.)

---

## Suites

| suite | T096 baseline | after T099 | after T098 |
|---|---|---|---|
| `tests/unit` | 3534 / 79 skipped / 14 xfailed | 3558 | **3568 passed, 79 skipped, 14 xfailed** |
| `tests/integration` | 409 passed, **1 failed**, 75 skipped | 428 passed, 0 failed | **432 passed, 0 failed, 76 skipped** |

**The 0 failures are not a win and must not be read as one.** T096's one
pre-existing failure -
`TestCorrectedPremiseNgoremeFlexIsTheSource::test_ngoreme_flex_holds_1949_and_ngoreme_holds_1945`,
live drift to 1952 - is now a **SKIP**, because FieldWorks was opened on
`Ngoreme FLEx` at 23:43 (PID 13768, verified running - a **genuine** lock, not
T090's stale one) and the census correctly refuses a locked project. The failure
did not go away; it went out of reach. The lock was left alone.

That same lock is why the committed T099 after-artifact predates
`_refuse_uncorroborated_nulls` (written afterwards). A guard added after a
measurement is worth nothing unless the measurement is re-checked against it, so
`test_the_committed_measurement_satisfies_the_producer_guard` runs the guard over
both committed artifacts' rows. Re-running the census was not available.

Note: `pytest tests/unit tests/integration` in one invocation fails collection on
a pre-existing basename collision (`test_038_process_rules.py`). Run separately.

---

## Commits

| worktree | commit | subject |
|---|---|---|
| feature | `2fce617` | `fix(038): T099 -- the census emitted a 0 it had flagged as false, and aborted rather than emit the row the schema allows` |
| `main` | `bbbbb9b` | `docs(038): T099 closed -- null is not a smaller zero, and T100/T101 filed` |
| feature | `044d644` | `fix(038): T098 -- the field recording which document admits a natural key had no reader, so it went stale unnoticed` |
| `main` | `46921e6` | `docs(038): T098 closed -- the tripwire was not the tripwire, and T082 narrows` |

Journals: `journal/T099-null-is-not-a-smaller-zero.md`,
`journal/T098-the-tripwire-that-was-not-the-tripwire.md`.
Artifacts: `_snapshots/census-038-t099-ngoreme-before.json`,
`census-038-t099-ngoreme-after.json`, `census-038-t098-ejagham.json`.

## Live-project discipline

Every project was opened READ-ONLY by the census (`opened_read_only: true`,
`.fwdata` digest asserted equal before and after in every artifact). **Nothing
was written, nothing was restored, and no transfer was run.** `Esperanto`,
`Ngoreme Target` and `Ejagham W Target` were not opened at all. The two
destinations used (`GT038 Ngoreme After`, `GT038 Ejagham After`) are existing
throwaways from earlier tasks and were read, not rebuilt.

## Not done, deliberately

* T064 - left parked as instructed.
* T090 - not fixed; demonstrated in its adjacent form (a genuine lock turns a
  failure into a skip just as effectively as a stale one) and reported.
* T097 - not started.
* The pre-existing `Ngoreme FLEx` 1949 -> 1952 pin - still not re-pinned, still
  not decided.
