# T099 - null is not a smaller zero

**Date**: 2026-08-21
**Task**: T099 (US2), the most serious of the four T096's sweep filed.
**Branch**: `038-transfer-fidelity-gaps`, worktree
`D:\Github\_Projects\_LEX\GramTrans-038-transfer-fidelity-gaps`, commit
`2fce617` on `da5975f`.
**Filings**: the `T099` line in `tasks.md`; raised by
`journal/T096-the-contract-that-arrived-and-was-not-read.md`.
**New filings out of this one**: **T100** (the reason vocabulary has no member
for an unresolved accessor) and **T101** (the gate accepts an uncorroborated
null count on a required row).
**Artifacts**: `tests/integration/_snapshots/census-038-t099-ngoreme-before.json`
and `census-038-t099-ngoreme-after.json` - two runs of the same pair, eight
minutes apart, with the fix as the only difference between them.

## The one-line version

The acceptance instrument emitted a count it had itself flagged as untrue, and
on a neighbouring path refused to emit anything at all - both because
`models.ClassCensusRow` declared `source_count: int` while the schema it serves
had typed the field `["integer", "null"]` from the start.

## What the two halves actually were

`contracts/census-artifact.schema.json:389-395` types `source_count` and
`destination_count_total` as `["integer", "null"]`, and the `$comment` draws the
distinction in as many words:

> null only on a NOT_EVALUATED row where the class could not be counted at all;
> a genuine zero is 0, never null.

So the contract requires *uncountable* and *genuinely empty* to be
distinguishable. The model could express only one of them, and the two call
sites resolved that in opposite directions.

**The false zero.** `census_cli.py:126-136` said it outright at `:130` - "the
schema's honest value here is null and the in-memory model cannot express it" -
and then emitted the value anyway at `:1591-1593`. Every
`excluded_not_measurable` row went out as `0 / 0` carrying a note that called
its own numbers placeholders. Two rows per artifact, `MoForm` and
`MoMorphSynAnalysis`, in every census this feature has ever taken.

**The abort.** `census_cli.py:518-533` is the same root cause with the opposite
failure mode: at `:523`, "`models.ClassCensusRow` cannot carry a null count, so
there is no honest row to write" - and it raised, ending the run. That abort was
loud in the console and *silent in the record*: no artifact was written, so the
one document that could have named which class went uncounted, in which project,
and for what reason did not exist.

The interesting thing about the pair is that the note was honest and the data
was not. A reader who read the note knew the zeroes were false. A phase gate
reads the data.

## The measurement

Two `census_cli run` invocations against `Ngoreme FLEx` -> `GT038 Ngoreme
After`, identical baseline (`contracts/starter-baseline.json`) and identical run
report (`_run_reports/038-t096-ngoreme-report.json`), taken at 23:24 and 23:32
with the code change as the only thing in between.

**Both projects held still, and that is asserted rather than assumed.** Both
artifacts record source digest `2b80aadf...` and destination `416b8a0e...`
before *and* after each read-only open, with identical `object_count_total` -
so the delta is the instrument's and nothing else's. This matters here more than
usual: `Ngoreme FLEx` is a live project and it HAS drifted during this feature.
Re-running the census today against T096's committed snapshot shows 10 rows
moved and `total_shortfall` 70638 -> 70659, which is why the pair was measured
back to back rather than diffed against the committed artifact.

| quantity | before | after |
|---|---|---|
| rows changed | - | **2** (`MoForm`, `MoMorphSynAnalysis`) |
| `MoForm.source_count` | `0` | `null` |
| `MoForm.destination_count_total` | `0` | `null` |
| `MoForm.destination_count_net` | `0` | `null` |
| `MoForm.difference` | `0` | `null` |
| `MoForm.difference_raw` | `0` | `null` |
| `MoMorphSynAnalysis`, same five | `0` | `null` |
| `totals.total_shortfall` | 70659 | **70659** |
| `totals.unexplained_shortfall` | 68941 | **68941** |
| `totals.classes_not_evaluated` | 3 | **3** |
| `totals.classes_matched` | 41 | **41** |
| verdict / exit | DUPLICATE_IDENTITY / 3 | DUPLICATE_IDENTITY / 3 |
| schema errors | 0 | **0** |
| section-11 invariant failures | 0 | **0** |
| whole-document remainder | - | identical but for `instrument.gramtrans_dirty` |

**No gate quantity moved, and that is the finding, not a disappointment.**
`census.build_totals` filters `difference is not None` before summing, so a
null-difference row contributes to no total. The two affected rows were also
already `verdict_class: NOT_EVALUATED` and `gate_scope: advisory` before the
change - which is exactly why the defect survived: the verdict was right and
the numbers under it were false, so nobody reading verdicts would ever have
found it.

## The three places the `int` was load-bearing

None of them is visible from the field declaration, and this is the part the
filing did not predict.

**1. The emitter would have DROPPED the fix.** `census.class_row_artifact` ran
`if value is None: continue` over every mapped field, with a comment asserting
"No REQUIRED mapped field can be None (the row's own invariants reject that),
so this cannot silently drop one". True - *because* the model lied. The moment
the model told the truth, that branch would have omitted `source_count`,
`destination_count_total` and `difference`, all three of which are in
`$defs.classRow.required`, turning an honest row into an invalid artifact. The
guard is now on the field NAME (`models.CLASS_ROW_REQUIRED_NULLABLE_FIELDS`),
because "optional, omit it" and "required and nullable, emit the null" are
indistinguishable by looking at the value.

**2. `verdict_class` compared `difference == 0` before checking None.** That is
the exact line where a placeholder zero became the word MATCHED. It is now
checked in the other order, and `census.row_verdict_class` - which had the
`difference is None` branch all along - makes the same call on the same input.

**3. `counts_pass` did the same, and would have failed in the other
direction.** `None == 0` is False, so without a guard an uncounted
gate-relevant row would have reported *not matched and not explained* - a loss
nobody measured.

Points 1 and 3 are the same lesson from opposite ends: an `int`-typed field
whose only null-handling lives in a *comment* has silent behaviour on both sides
of the change.

## The abort became a row without becoming quiet

`_report_unmeasurable` split in two.

`_print_unmeasurable` is the run path. It prints every unresolved accessor as a
`[FAIL]` line, prints the summary line ("the census may fail to measure a class;
it may not fail QUIETLY"), and *returns* the entries, which the run puts in the
artifact's `errors[]` array. A non-empty `errors[]` is CENSUS_ERROR / exit 7 in
`census.recompute_verdict`, and the gate recomputes rather than reads - so the
run still fails, at the same exit code, with the same console output, and now
with a document that names the class. The row it leaves is null-counted and
NOT_EVALUATED.

`_report_unmeasurable` keeps the raise, for `capture_baseline` only, and the
reason is not inertia. A baseline document is a count MAP that a later run
*subtracts*, and `census.unmatched_starter` refuses to read an absent count as
zero; a null baseline count would be subtracted as 0 by exactly the arithmetic
5.2 forbids. There is also no `classes` array in a baseline document, so T099's
"the abort becomes a row" has nothing there to become.

## The hole the fix itself opens, and where it is closed

This is the thing I did not expect to find, and a test found it rather than
inspection.

A null difference reads `NOT_EVALUATED`, and `census.row_passes` returns True
for `NOT_EVALUATED`. So **nulling a required class retires its shortfall
without measuring anything.** Before T099 that was unreachable because the
model would not hold a null at all; the model no longer will not, so the
prohibition has to be stated somewhere.

It is stated on the producer: `_refuse_uncorroborated_nulls` runs over the
finished rows before anything is written and refuses a `gate_scope: required`
row with a null count unless the class is named in `errors[]`. Two
corroborations are accepted and they are the only two this CLI can produce -
`advisory` (every `excluded_not_measurable` entry is hardcoded advisory in
`census.derive_class_list`, so an abstract LCM base can neither fail nor excuse
a gate) or an `errors[]` entry, which is CENSUS_ERROR on its own.

It is **not** stated on the gate, and that is deliberate.
`census.validate_artifact` and `recompute_verdict` are null-tolerant by design
throughout - `_int_or_none` and `None not in (...)` guards everywhere - and they
have no invariant tying a null count on a required row to a corroborating
`errors[]` entry. A hand-authored artifact of that shape still gates CENSUS_CLEAN
/ exit 0. Adding the invariant changes what the gate refuses about *every*
artifact already committed, which needs its own before/after. Filed as **T101**,
and pinned as current behaviour by
`test_the_gate_alone_does_not_yet_refuse_a_forged_null`, which will fail the day
T101 lands.

## What the predicate re-read found

T099 asked for "a re-read of any predicate that compares a count against 0".
Done, and the answer is reassuring for a reason worth writing down: the engine
side was already null-ready and only the model was not.

* `census.net_destination_count`, `signed_difference`, `unexplained_counts`,
  `row_verdict_class`, `MatchBasis.sums_to`, `unmatched_starter` - every one
  already returns or short-circuits on None, with a docstring saying why.
* `census.build_totals` filters `difference is not None` on both `total_*` and
  `advisory_shortfall`.
* `census.validate_artifact` invariants 3, 4 and 11 are all guarded with
  `None not in (...)`.
* `census.row_passes` checks `verdict_class == "NOT_EVALUATED"` first, before
  any count is read.
* `_require_matched` (P1/P2/P3/P4) reads `verdict_class`, so an uncounted class
  in a phase's list reports NOT_EVALUATED and **fails** its phase. That is the
  safe direction and it is now pinned.
* `_phase_5` `continue`s on NOT_EVALUATED without failing - the one place an
  uncounted required class is not caught by the predicate itself. It is caught
  by the `errors[]` entry that put it there (exit 7), which is why T101 is a
  filing and not a shrug.
* `census_cli diff` (SC-008) uses `isinstance(old, int)` and already had a
  message reading "a null `destination_count_total` on one side". Two rows move
  from "compared and equal" to "not compared" - reported as `[INFO]`, no verdict
  change. That is a real, small loss of coverage, and it is the right loss:
  comparing two falsehoods and finding them equal was never evidence.

The pattern is that the *library* anticipated nulls in about a dozen places and
the *model* forbade them, so none of that machinery had ever run. The T099 fix
did not add null handling; it made a decade of it reachable.

## The tests, and why these

Two of them would have caught the original defect, and both are structural
rather than corpus-bound.

`test_the_model_admits_every_type_the_schema_does` reads
`typing.get_type_hints(ClassCensusRow)` and `$defs.classRow.properties[*].type`
and compares them. Nothing in the tree had ever compared the model to the schema
it serves; the gap was recorded only in a code comment, and a comment cannot
fail.

`test_a_null_count_is_emitted_as_null_not_omitted` asserts the three required
keys are present-and-null rather than absent. That is the trap in point 1 above,
and it is the one that would have turned a correct fix into an invalid artifact.

`test_the_emitter_knows_which_required_fields_may_be_null` derives the expected
set from the schema's own `required` array rather than restating it, so a schema
change that makes a fourth field nullable fails here instead of silently
diverging.

Plus 19 in `test_object_census.py` over the committed measurement pair
(including `test_neither_project_moved_between_the_two_runs`, which is what
makes the delta attributable) and the reported-not-raised accessor.

## Pins deliberately moved

Both wording, neither a relaxation.

* `_NOT_MEASURED_NOTE` no longer calls its own counts placeholders. Leaving the
  text verbatim would have put a false statement into every artifact line it
  produces - the same defect one layer down, which is the mistake T096 avoided
  with `SOURCE_REFERENT_ABSENT_DETAIL`. The old text is quoted in the constant's
  own comment so the record survives.
* `_report_unmeasurable` split into a reporting half and a raising half. No
  existing test asserted on it; the `capture_baseline` raise is now pinned by
  `test_capture_baseline_still_aborts`, which it was not before.

## Suites

| suite | before (T096) | after |
|---|---|---|
| `tests/unit` | 3534 passed, 79 skipped, 14 xfailed | **3558** passed, 79 skipped, 14 xfailed |
| `tests/integration` | 409 passed, 1 failed, 75 skipped | **427** passed, **0 failed**, 76 skipped |

**The zero failures are not a win and must not be read as one.** T096's one
remaining failure was
`TestCorrectedPremiseNgoremeFlexIsTheSource::test_ngoreme_flex_holds_1949_and_ngoreme_holds_1945`
- pre-existing live drift, `Ngoreme FLEx` now holding 1952. It is now a SKIP,
because FieldWorks was opened on `Ngoreme FLEx` at 23:43 (PID 13768, verified
running, a genuine lock and not T090's stale one) and the census correctly
refuses a locked project. The failure did not go away; it went out of reach.
The lock was left alone - a real FieldWorks session is not something to clear.

That same lock is why the committed after-artifact was measured at 23:32,
*before* `_refuse_uncorroborated_nulls` was written. A guard added after a
measurement is worth nothing unless the measurement is re-checked against it, so
`test_the_committed_measurement_satisfies_the_producer_guard` runs the guard
over both committed artifacts' rows. Re-running the census was not available.

## What this closes, and what it does not

**Closes**: the false `0` on `MoForm` and `MoMorphSynAnalysis`, measured on a
real pair; the abort that produced no artifact; the two structural tripwires
that were missing.

**Does not close**:

* **T100**, filed. The closed 17-token reason vocabulary has no member meaning
  "the repository accessor did not resolve". `ABSENT_BY_CONSTRUCTION` is the
  abstract-base case and would be a false statement about a class whose accessor
  merely drifted, and `$defs.classRow.not_evaluated_reason`'s `$comment` says a
  NOT_EVALUATED row should carry one. So an unresolved-accessor row omits it and
  states its cause in `errors[]` instead. Not settled by inventing an 18th
  token - the vocabulary being closed is load-bearing (T096).
* **T101**, filed. The gate accepts an uncorroborated null on a required row.
* **T090**, untouched and now demonstrated in its adjacent form: a genuine lock
  turns a failure into a skip just as effectively as a stale one.
* The pre-existing `Ngoreme FLEx` 1949 -> 1952 pin. Still not re-pinned, still
  not decided, and now not even reachable.

## What surprised me

That the library was ready and the model was not. `Lib/census.py` has
`Optional[int]` on every count-shaped parameter, a `difference is None` branch in
`row_verdict_class`, and a `(0, 0)` early return in `unexplained_counts`, each
with a docstring explaining the null case. All of it was dead, because a
`ClassCensusRow` could not produce the input. This is the feature's recurring
shape once more - *something that exists and is read at a level where it cannot
do its job* - except here the thing that existed was the **handling**, and the
level it could not be reached from was **the type of a dataclass field**. T094
found a sweep with no producer; this is null handling with no producer, and it
had been sitting one keyword away from working for the whole feature.

## What I refused to do

* Make the abort silent, or downgrade it to a warning. Same `[FAIL]` lines,
  same exit 7, plus a record.
* Remove the `capture_baseline` abort along with the run's, on the grounds that
  they share a function.
* Invent an 18th reason token so an unresolved-accessor row could carry a
  `not_evaluated_reason`.
* Add the missing gate invariant as a drive-by (T101).
* Re-pin the `Ngoreme FLEx` 1949 drift, or clear a live FieldWorks lock to get
  a cleaner-looking suite.
* Re-run the census to regenerate the after-artifact once the tree was dirty -
  the committed pair is the pair that was measured, and the guard added
  afterwards is checked against it rather than folded into it.
