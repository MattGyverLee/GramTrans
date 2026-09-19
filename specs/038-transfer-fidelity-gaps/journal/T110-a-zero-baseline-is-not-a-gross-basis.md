# T110 — a zero baseline is not a gross basis

**Closed** 2026-08-26. Filed by T081, whose Finding 2 measured the defect and
could not fix it inside T081's own scope.

## What T110 asked

5.2's gross-basis cap suppresses a row's `unexplained_shortfall` /
`unexplained_surplus` and holds the run verdict at `CENSUS_ACCOUNTED`. Its
rationale is one arithmetic error and no other: gross subtraction removes the
**whole** baseline, so a starter object the transfer correctly **matched** is
subtracted twice — once as a starter object and once as the source object it now
stands in for. 5.2's worked example is source 41, destination 43, starter 23:
`43 - 23 = 20`, `difference -21`, a shortfall on a lossless run.

On a row whose `starter_baseline_count` is **0** there is nothing to subtract
twice. `starter_excluded` is 0, `destination_count_net ==
destination_count_total`, and the two bases compute the identical integer —
`total - 0` against `total - (0 - 0)`. The gross figure is not an upper bound on
that row; it *is* the difference. `census_cli`'s own T048d comment already says
so — *"A class the baseline counts as ZERO cannot carry a phantom shortfall:
gross subtraction subtracts nothing from it, so the two bases already agree"* —
and spends it only on skipping the identity audit, never on deciding whether the
cap applies. `census.is_gross_basis_row`, the one predicate the cap, its notes
and the exit code all turn on, still said gross.

## The predicate, before and after

```
before:  basis == "baseline_gross"

after:   basis == "baseline_gross"
         AND NOT (starter_baseline_source == "baseline_document"
                  AND starter_baseline_count is an int equal to 0)
```

Three states, kept apart by the **corroboration** rather than by the
arithmetic — because two of them subtract 0 and only one of them knows it:

| row | `starter_baseline_source` | `starter_baseline_count` | capped? | why |
|---|---|---|---|---|
| exact | `baseline_document` | `0` | **no** | a baseline was read and it said none. Both bases give the same integer, so there is no over-subtraction to compensate for. |
| unmeasured | `absent_from_baseline` (or key/source missing) | absent, or `null` | **yes** | nobody counted. The true starter population is unknown, so the arithmetic is not exact. Absent is not zero — the refusal `census.unmatched_starter` already makes. |
| over-subtractable | `baseline_document` | `> 0` | **yes** | unchanged. This is 5.2's case and the cap is correct on it. |

The `null` row is not a hypothetical: `$defs.classRow` types
`starter_baseline_count` as `["integer", "null"]`, so a *present* key can carry
a missing measurement. Key presence would therefore have been the wrong test,
and `_int_or_none` is what makes the check discriminate.

The **declared basis string is not rewritten**, here or in `census_cli`. It stays
`baseline_gross` on a de-capped row: that is the subtraction the census actually
performed, the artifact's arithmetic has to stay reproducible from what it
published, and the validator's invariant 4 plus `SUBTRACTION_BASES` are written
against that vocabulary. What changed is only whether that subtraction was
*capable* of the error the cap exists for.

The fix is at the one predicate, not at its three call sites
(`gross_basis_suppressions`, `gross_basis_cap_notes`, `recompute_verdict`) —
T024b's rule that the cap, the notes and the exit code must not be able to
disagree about which rows are capped.

## The five numbers T110 predicted, measured

Against `_snapshots/census-038-t078-{ejagham,ngoreme,mbugwe}.json`:

| corpus | required non-MATCHED | rows carrying a suppression, before | de-capped rows carrying a tally | objects that stop being advisory | recomputed verdict before → after |
|---|---|---|---|---|---|
| ejagham | 19 | 18 | **13** | **2,602** | `DUPLICATE_IDENTITY` → `DUPLICATE_IDENTITY` |
| ngoreme | 27 | 26 | **19** | **57,955** | `DUPLICATE_IDENTITY` → `DUPLICATE_IDENTITY` |
| mbugwe | 23 | 22 | **15** | **8,849** | `DUPLICATE_IDENTITY` → `DUPLICATE_IDENTITY` |

All five predictions **confirmed**, with one clarification and one correction:

- **13 / 19 / 15 is right**, read as *rows whose suppression goes away*. Read
  literally as "of the required non-MATCHED rows", mbugwe is **16**, not 15: a
  sixteenth zero-baseline row, `CmAnthroItem`, is `NOT_EVALUATED` with a tally of
  0, so it changes capping status while contributing no objects. T081's table
  counted against "P5 fails" (18 / 26 / 22 rows carrying a suppression) and is
  internally consistent; T110's task line inherited the count without the
  denominator.
- **2,602 / 57,955 / 8,849 exact**, and the three sum to **69,406** — the number
  T110 names for the latent case, to the object.
- Worst single row **mbugwe `CmFile` 2173 → 0** confirmed, baseline 0 from a real
  `baseline_document`.
- **No verdict change on these three**, confirmed: `DUPLICATE_IDENTITY` outranks
  the cap, exit 3 either way.

Suppression counts after: 5 / 7 / 7 rows and 461 / 10,973 / 535 objects — the
rows with a genuine nonzero baseline, which keep their cap.

**"CHANGES NO ANSWER TODAY" is true only of those three artifacts, and the task
line does not say so.** It changes the answer on every committed
**duplicate-free** census in the repo, which is exactly the latency it names:

| artifact | verdict before | verdict after | exit before | exit after |
|---|---|---|---|---|
| `census-038-ejagham` (T024b) | `CENSUS_ACCOUNTED` | `UNEXPLAINED_SHORTFALL` | 0 | 1 |
| `census-038-ngoreme` (T024b) | `CENSUS_ACCOUNTED` | `UNEXPLAINED_SHORTFALL` | 0 | 1 |
| `census-038-t039d-run1` (T086) | `CENSUS_ACCOUNTED` | `UNEXPLAINED_SHORTFALL` | 8 | 1 |

And on the T078 trio with their duplicate evidence removed (`roster_admitted`
false, nothing else touched), all three go `CENSUS_ACCOUNTED` / exit 0 →
`UNEXPLAINED_SHORTFALL` / exit 1. The defect was never dormant; it was masked
by a *second* defect being more severe.

## Three states, all three present in real data

The `absent_from_baseline` state is not a forged edge case. Both T024b snapshots
carry an Amendment A1 `FsFeatStrucType` half with **no `starter_baseline_count`
key at all** and `unexplained_shortfall: 3`. It stays capped, which is why the
still-capped count on those artifacts is **13 = 12 + 1** rather than just the
twelve nonzero-baseline rows. Had the predicate read absence as zero, that row
would have been de-capped for the one reason T110 forbids — and it is the row
whose baseline genuinely *is* unknown, because the baseline document is not split
by owning feature system.

## What T086's finding looks like now

The T086 snapshot's suppressions drop from **13 rows / 1,643 objects** to
**5 rows / 448**. Eight rows left — `FsClosedValue` 46, `FsFeatStruc` 23,
`PunctuationForm` 586, `ReversalIndexEntry` 1, `WfiAnalysis` 136, `WfiGloss`
135, `WfiMorphBundle` 219, `WfiWordform` 49, together **1,195 of the 1,643** —
every one of them a measured-zero baseline. They were never advisory.

T086's substance survives intact and is worth stating plainly, because the exit
code moved and the finding did not. `evaluate_phase` is unchanged for P1, P2, P3
and P4; `phase_scoped_suppressions` is still `()` for all four; the capped rows
are still disjoint from every bounded phase's scope. What changed is that the
project-wide gate exits **1** instead of 8, because the de-capped rows make the
run verdict a genuine `UNEXPLAINED_SHORTFALL` and there is no pass left to cap.
`CAPPED_PASS_EXIT_CODE` 8 is untouched and still reachable — `gross_basis_rows`
over a nonzero baseline produces it, and `test_a_capped_pass_does_not_exit_zero`
still exercises it.

On the two T024b pre-fix runs, P2's clause three is now **vacuously** satisfied:
its two classes, `MoInflAffixSlot` and `MoInflAffixTemplate`, both had
measured-zero baselines, so they carry no suppression to be in or out of scope.
P2 is still refused there, by clauses one and two. The falsifiability test now
pins the per-phase in-scope sets (`{PartOfSpeech}`, `{}`,
`{MoMorphType, PartOfSpeech}`) rather than asserting each is non-empty, because
"non-empty" was measuring the cap's reach and not the clause.

## The committed artifacts, and what was and was not edited

No snapshot JSON was touched. Their stored `verdict` / `exit_code` /
`verdict_human_label` are now the **pre-T110 answer**, which invariant 8 reports
as exactly one failure apiece — and invariant 8 exists to say precisely that
("the gate recomputes it rather than trusting it"). Two tests carry it:
`test_the_stored_verdict_is_the_pre_t110_answer_and_only_that` asserts the ONE
failure and its text, so a second failure later would be a new problem rather
than absorbed into this one; and the section-11 invariant test now validates
`with_recomputed_verdict(...)`, a copy re-stamped by `census.stamp_verdict`.

That helper is the same move as the existing `with_current_roster_admission` and
rests on the same fact: `verdict` is a **derivation**, not a measurement —
`stamp_verdict` is "the ONLY sanctioned way those three fields get their values"
— so re-running the derivation over unchanged counts forges nothing. Every
measured quantity in both files is validated exactly as it sits on disk.

## What was NOT done

- **The emitted `starter_subtraction_basis` string.** Left alone, deliberately;
  see above.
- **`census_cli._row_for_entry`.** It still assigns `baseline_gross` to a
  zero-baseline row, which is true of the subtraction. No emitter change was
  needed, which is the point of fixing the predicate.
- **The 5.2 contract text and the schema `$comment`.** Both still say
  "`baseline_gross` … caps the run verdict at `CENSUS_ACCOUNTED`" with no zero
  carve-out. The code now states the bound in the predicate docstring and in the
  5.2 design block; aligning `fidelity-census.md:251` and
  `census-artifact.schema.json:408` is spec work, filed below rather than done
  here.

## New finding, filed rather than fixed

**T086's amended third clause is written in terms of an EXIT CODE that T110
retired.** The clause as it stands in T038, T048, T075 and T064's task text is
*"exits 0, **or** exits 8 with every capped row provably outside the classes this
phase names"*. After T110 the T086 artifact exits **1**: the rows that decide the
run verdict are the de-capped zero-baseline ones, which are still provably
outside all four phases' scopes, but the clause has no branch for a run that
fails outright on out-of-scope rows. Everything the clause actually *proves* is
still checked and still green (`evaluate_phase(...).satisfied`,
`phase_scoped_suppressions(...) == ()`), so the four tasks' conclusions stand —
what is stale is the integer they cite, in four places, together with the
"13 capped rows (1643 objects)" figure repeated beside it. (T038's separate
"18 rows / 1681 advisory objects" is a different census, `CENSUS-20260820-114752`,
whose artifact is not committed; it is presumably stale for the same reason but
was not measured here.)
The right fix is to restate the clause over what it demonstrates rather than over
the exit code, and to refresh the numbers; it should not be done inside T110,
because it edits four closed tasks' acceptance text.

## Evidence

- `src/gramtrans/Lib/census.py` — `is_gross_basis_row`, the
  `BASELINE_SOURCE_DOCUMENT` constant, the 5.2 design block's T110 section.
- `tests/integration/test_object_census.py` —
  `TestT110AZeroBaselineIsNotAGrossBasis` (nine tests, all three states plus the
  latent consequence and its falsifier), and the moved numbers in
  `TestMeasuredCensusSnapshots`, `TestMoStemMsaTotalLoss`,
  `TestCappedExitZeroCoexistsWithFailingRows` and
  `TestT086TheAmendedThirdClause`.
- `tests/unit` 3731 passed / 79 skipped / 14 xfailed — **unmoved**.
- `tests/integration` 641 → **657** passed / 0 failed / 75 skipped.
