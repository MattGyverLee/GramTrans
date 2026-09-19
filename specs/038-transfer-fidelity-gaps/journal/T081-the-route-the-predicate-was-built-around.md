# T081 -- the route the predicate was built around, and nobody had walked it

**Date**: 2026-08-25
**Task**: T081 (P5, residual) -- gate run only; no code changed
**Artifacts gated**: `census-038-t078-ejagham.json`,
`census-038-t078-ngoreme.json`, `census-038-t078-mbugwe.json`
(T078's read-only 2026-08-25 runs, the current post-037 baseline)
**Outcome**: **P5 is NOT satisfied on any corpus. T081 stays unchecked.**

---

## The gate run

`census_cli gate --artifact <a> --phase 5` on each of T078's three artifacts:

| corpus | P5 failures | exit | run verdict |
|---|---|---|---|
| ejagham | 19 | 3 | `DUPLICATE_IDENTITY` |
| ngoreme | 27 | 3 | `DUPLICATE_IDENTITY` |
| mbugwe  | 23 | 3 | `DUPLICATE_IDENTITY` |

The exit code is **not** P5's; `DUPLICATE_IDENTITY` outranks everything the
phase could say, and its cause is `PhNCFeatures` (3 / 21 / 66 extra objects) --
which is **T082's remaining `038-NK-P3`**, exactly where T078 left it. P5's own
answer is the failure list, and it is red on all three.

Every one of the 69 failures is one of two shapes:

* *"is SHORTFALL (difference -N) and carries NO accounting line"* -- 66 of them;
* *"PhNCFeatures is MATCHED but carries N unaccounted duplicate objects"* -- 3.

## Finding 1 -- P5's admissible route was never wired, and the reason it was refused was about a different field

T079 (Wave 1, same phase) considered `GOVERNED_BY_OTHER_FEATURE` for exactly
these rows and **refused it**, on this stated ground:

> ALSO REFUSED: an 18th `CENSUS_REASON_TOKENS` member and reusing
> `GOVERNED_BY_OTHER_FEATURE`. Both live in `CENSUS_NOT_EVALUATED_REASONS`, so
> stamping either on these rows flips `verdict_class` to NOT_EVALUATED and
> DELETES the measured shortfall from `total_shortfall` and from the gate --
> laundering a red run, not reporting it.

That is **true of the field T079 was looking at and false of the field P5
reads.** `GOVERNED_BY_OTHER_FEATURE` is a member of *two disjoint vocabularies*:

```
GOVERNED_BY_OTHER_FEATURE in census.CENSUS_NOT_EVALUATED_REASONS   -> True
GOVERNED_BY_OTHER_FEATURE in census.REASON_TOKENS                  -> True
GOVERNED_BY_OTHER_FEATURE in census.REASONS_NOT_REQUIRING_REPORT_REF -> True
```

* as a **not-evaluated reason** (`row.reasons` -> `not_evaluated_reason`) it does
  flip `verdict_class` to `NOT_EVALUATED` and remove the row from the shortfall
  totals. T079's refusal is correct here.
* as an **`accounted_for` line reason** it does neither. `_phase_5` skips
  `MATCHED`/`NOT_EVALUATED` and then reads `row["accounted_for"]`; a line
  reduces `unexplained_shortfall` and leaves `verdict_class` alone.

The contract asks for the second one by name --
`contracts/fidelity-census.md:373`:

> `GOVERNED_BY_OTHER_FEATURE` | either | Texts/wordforms, reversals, and sense
> pictures are governed by their own features; this feature reports their
> figures and does not fix them (spec Assumptions). **Needs no `report_ref`.**

and validator invariant 5 exempts it from `report_ref` precisely so it can be
emitted without a run-report line behind it.

**Measured, not argued.** Stamping the governed classes on a copy of the
ejagham artifact (probe only, nothing written):

| | before | after |
|---|---|---|
| P5 failures | 19 | **10** |
| `verdict_class` on stamped rows | `SHORTFALL` | **`SHORTFALL`** (unchanged) |
| `totals.total_shortfall` | 4781 | **4781** (unchanged) |
| recomputed run verdict | `DUPLICATE_IDENTITY` | **`DUPLICATE_IDENTITY`** |

Nothing was laundered: the rows stay red, the objects stay counted, the verdict
stays where it was. The route P5 was designed around is open, and the only
reason it is unused is that T079's refusal -- correct for the reason-stamp --
was read as covering the accounting line too.

Across the three corpora the route accounts for **33 of the 66 line-less rows**
(1885 / 64,621 / 8017 objects):

| corpus | P5 fails | governed-stampable | would remain |
|---|---|---|---|
| ejagham | 19 | 9 (1885 objs) | 10 |
| ngoreme | 27 | 13 (64,621 objs) | 14 |
| mbugwe  | 23 | 11 (8017 objs) | 12 |

What remains after it is the honest residue and is **not** stampable: the
feature-structure family (`FsClosedValue`, `FsFeatStruc`), `CmPossibility`, the
phonological-context family (`PhSequenceContext`, `PhSimpleContext{Bdry,NC,Seg}`
-- T079 calls these "037's or another feature's territory", which is a claim
someone must own before it can be an accounting line), `PhCode`, `MoAffixProcess`
(Phase 4's own defect), and `PhNCFeatures` (T082).

**This is deliberately NOT implemented here.** Deciding *which* classes are
governed by another feature is a gate-consequential roster decision, and
`GOVERNED_BY_OTHER_FEATURE` is by construction a way to turn a red row green.
T079 built two locks against exactly that (import-time disjointness from
`CENSUS_PHASE_GATED_CLASSES`, and gate-inertness proved by emptying the roster).
A line that *is* load-bearing on the gate needs its own equivalent, and its own
task. Filed as **T109**.

## Finding 2 -- 5.2's cap fires on rows where its own arithmetic never happened

Latent, in the direction that **excuses** loss, and independent of Finding 1.

`fidelity-census.md` 5.2 caps the run verdict at `CENSUS_ACCOUNTED` for rows on
`starter_subtraction_basis: baseline_gross`, because gross subtraction
"also subtracts the starter objects the transfer correctly matched" and so
"reports a shortfall on a correct run". The cap turns on one predicate,
`census.is_gross_basis_row`, which reads the label and nothing else.

**On a row whose `starter_baseline_count` is 0 that rationale cannot apply.**
There are no starter objects of the class to over-subtract; `starter_excluded`
is 0, `destination_count_net == destination_count_total`, and the gross and
matched bases compute the *identical* number -- `total - 0` versus
`total - (0 - 0)`. The gross figure on such a row is not an upper bound, it is
the exact difference. `census_cli`'s own T048d comment already states the
principle -- *"A class the baseline counts as ZERO cannot carry a phantom
shortfall: gross subtraction subtracts nothing from it, so the two bases
already agree"* -- but it is used only to skip the identity audit, never to
decide the basis label, so those rows keep the `baseline_gross` label and 5.2
suppresses them.

Measured on T078's three artifacts, among the required non-MATCHED rows:

| corpus | P5 fails | of which `starter_baseline_count == 0` | objects suppressed as "advisory" |
|---|---|---|---|
| ejagham | 18 | 13 | 2,602 |
| ngoreme | 26 | 19 | 57,955 |
| mbugwe  | 22 | 15 | 8,849 |

all with `starter_baseline_source: baseline_document` (a real baseline that
counts zero, not a missing one). Worst single row: mbugwe `CmFile`
source 2173 -> destination 0, baseline 0 -- 2173 objects gone, reported as
`unexplained_shortfall 2173 suppressed (basis baseline_gross)`.

**It changes no answer on these three artifacts** -- `DUPLICATE_IDENTITY`
outranks the cap, so the exit code is 3 either way, and P5 is not relaxed by the
cap in the first place (5.2 is explicit: *"`row_passes` and the section 9.1
phase predicates are deliberately NOT relaxed"*). It is latent: on a
duplicate-free artifact a run that lost 69,406 objects would read
`CENSUS_ACCOUNTED`. Filed as **T110**.

This is the fourth appearance of the bounding rule T048b first stated and T086
last applied -- *a global signal must be bounded to what it could actually
concern* -- and the first one in the excusing direction. T086's three were all
denials of rows never in doubt; this one is an excuse for rows that are.

## Why T081 stays unchecked

P5's predicate is "every remaining `required` row MATCHED or carrying a valid
`GOVERNED_BY_OTHER_FEATURE` / `NO_CREATE_PATH` line, with no unexplained
difference remaining". It is red on all three corpora and the gate says so.
Neither finding makes it green: T109 would take it from 66 line-less rows to 33,
and T110 makes the run verdict stricter, not looser. The clause is not
mis-stated the way T038/T048/T075's third clause was, so there is nothing here
for a T086-style amendment to fix -- the work is simply not done.
