# T109 — the line P5 was built around, and who is allowed on it

**Closed** 2026-08-26. Filed by T081, which walked the route, measured it, and
refused to wire it because deciding *who* is on it is a gate-consequential
decision that needs its own task and its own locks.

Worktree commit `f985ee6`. Code: `src/gramtrans/Lib/models.py`,
`src/gramtrans/Lib/census.py`, `src/gramtrans/census_cli.py`. Tests:
`tests/integration/test_object_census.py` (+61).

---

## The field T079 was right about, and the field P5 reads

`GOVERNED_BY_OTHER_FEATURE` is a member of **three** vocabularies, and the two
readings are not the same claim:

| as | what it does to the row | what it does to the totals |
|---|---|---|
| `not_evaluated_reason` (`CENSUS_NOT_EVALUATED_REASONS`) | flips `verdict_class` to `NOT_EVALUATED` | **deletes** the measured shortfall from `total_shortfall` and from the gate |
| `accounted_for` line reason (`REASON_TOKENS` + `REASONS_NOT_REQUIRING_REPORT_REF`) | nothing — `verdict_class` is a function of `difference` alone | nothing — `build_totals`' `total_shortfall` is `sum(max(0, -difference))`; only which *bucket* the objects sit in moves |

T079 refused the first and its refusal stands. T081 established that the second
is the one `contracts/fidelity-census.md:373` asks for by name and that
validator invariant 5 exempts from `report_ref` precisely so it can be emitted.
Confirmed here on all three corpora: **every stamped row stays `SHORTFALL`,
carries no `not_evaluated_reason`, and keeps its objects in
`total_shortfall`.**

## Measured, per corpus

`census_cli.accounted_for_governed_class` applied to T078's three committed
artifacts, with every derivation the real one (`census.unexplained_counts`,
`census.build_totals`, `census.stamp_verdict`). Nothing on disk was edited.

| | ejagham | ngoreme | mbugwe |
|---|---|---|---|
| P5 failures before → after | **19 → 10** | **27 → 16** | **23 → 14** |
| rows stamped | 9 | 11 | 9 |
| objects claimed | 1885 | 64,618 | 5841 |
| `verdict_class` on every stamped row | `SHORTFALL` | `SHORTFALL` | `SHORTFALL` |
| `totals.total_shortfall` before → after | 4781 → **4781** | 70,646 → **70,646** | 10,243 → **10,243** |
| `totals.unexplained_shortfall` | 3063 → 1178 | 68,928 → 4310 | 9384 → 3543 |
| `totals.accounted_shortfall` | 0 → 1885 | 0 → 64,618 | 0 → 5841 |
| `totals.total_surplus` | 0 → 0 | 0 → 0 | 0 → 0 |
| recomputed run verdict / exit | `DUPLICATE_IDENTITY` / 3 → **unchanged** | unchanged | unchanged |
| `validate_artifact` failures | 0 → 0 | 0 → 0 | 0 → 0 |

`unexplained_shortfall` and `accounted_shortfall` move by the **same** integer
on all three. If they had not, objects would have gone somewhere neither bucket
names, which is the laundering this instrument exists to make visible.

The run verdict was **re-derived, not copied from T081**, because T110 changed
what the recompute returns. On these three it returns the same answer: T082's
remaining `038-NK-P3` (`PhNCFeatures`, 3 / 21 / 66 extra objects) outranks
everything a P5 line can reach.

## Where T081 was wrong, and by exactly how much

T081 predicted 9 / 13 / 11 stampable rows carrying 1885 / **64,621** / **8017**
objects. Ejagham reproduces to the object. The other two do not, and the entire
delta is two rows:

| | ejagham | ngoreme | mbugwe |
|---|---|---|---|
| `CmFile` difference | 0 (MATCHED) | −2 | **−2173** |
| `CmFolder` difference | 0 (MATCHED) | −1 | −3 |
| adding both back | 9 / 1885 | **13 / 64,621** | **11 / 8017** |

which is T081's figure exactly, on both pairs. So this is a **scope ruling**,
not a measurement disagreement, and the test file reproduces the arithmetic in
both directions so it cannot later be blurred.

The orientation this task was handed said `CmFile` "was NOT in T081's stampable
nine". That is a misreading of T081's own table rather than a fact about its
probe: on ejagham `CmFile` is `0 → 0`, `MATCHED`, so it could not appear in
*ejagham's* nine. It is in mbugwe's eleven and ngoreme's thirteen, and those two
figures are unreachable without it.

## The `CmFile` ruling — measured, not argued

The task line's `SCOPE` clause says **"texts/wordforms/reversals only — the
classes the spec Assumptions already hand to another feature"**. Both halves of
that sentence are in tension with each other:

- `spec.md:372-374` hands over **three** paths: *"**Sense pictures, reversal
  indexes, and the texts/wordforms path** are governed by their own
  features."*
- `contracts/fidelity-census.md:373`, cited by the task line as its authority,
  says the same: *"Texts/wordforms, reversals, **and sense pictures** are
  governed by their own features."*

**FINDING.** The task line's own scope clause is narrower than both its cited
authority and its own stated justification. Recorded here and pinned as a test
(`test_the_task_lines_own_scope_clause_is_narrower_than_its_authority`) against
the contract table's literal text, so the discrepancy cannot be closed later by
quietly editing the table.

**RULING: the sense-pictures path is rostered; `CmFile` and `CmFolder` are
not.** The reasoning is a measurement, and it is what makes the ruling
defensible in both directions at once:

| class | ejagham | ngoreme | mbugwe |
|---|---|---|---|
| `CmPicture` source → destination | 0 → 0 | 0 → 0 | 0 → 0 |
| `CmFile` | 0 → 0 | 2 → 0 | 2173 → 0 |
| `CmFolder` | 1 → 1 | 1 → 0 | 3 → 0 |

`CmPicture` **is** sense pictures, and it holds nothing on any of the three
pairs. So the 2176 objects `CmFile` and `CmFolder` lose between them cannot be
sense-picture content — there is no picture anywhere to refer to them. They are
the project's **media folder**, a path the Assumptions name nowhere and for
which no successor feature exists. An accounting line for them would be exactly
the unowned claim T081 refused for the phonological contexts, and the fact that
T110 just de-capped mbugwe's `CmFile` row — making it load-bearing on the run
verdict rather than advisory — is a reason to be *more* careful here, not less.

`CENSUS_REPORT_ONLY_RESIDUE` already carries `CmFile` under *"the media/pictures
path — not 038"*. That is the right home for a **display word** on a class
nobody owns and the wrong one for a **gate-bearing line**, which is the whole
distinction between the two rosters.

`CmPicture` is rostered anyway, as an **admitted promise**, so the roster covers
all three of the spec's named paths and the derivation stays falsifiable. Its
own reason string carries the measurement that keeps `CmFile` out.

## The reversals ruling

Both reversal classes **are** carried in the census, and one of them is the only
governed class that is a required non-`MATCHED` row on all three pairs:

| class | gate scope | ejagham | ngoreme | mbugwe |
|---|---|---|---|---|
| `ReversalIndex` | required | −2 | −2 | −2 |
| `ReversalIndexEntry` | required | −14 (144 → 130) | 0 (holds none) | 0 (holds none) |

So: **accounting lines, not promises.** Neither class appears in
`CENSUS_REPORT_ONLY_RESIDUE`, although the Assumptions name the path — the
second gap in that roster (see the defect below).

## The roster as written — 14 entries, two of them promises

Declared as `models.CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES`, `(owner, reason)`,
re-exported as `census.GOVERNED_BY_OTHER_FEATURE_CLASSES` and read through the
single lookup `census.governed_by_other_feature`.

**texts/wordforms (11)** — `Text`, `TextTag`\*, `StText`, `StTxtPara`,
`Segment`, `CmTranslation`, `PunctuationForm`, `WfiWordform`, `WfiAnalysis`,
`WfiGloss`, `WfiMorphBundle`
**reversal indexes (2)** — `ReversalIndex`, `ReversalIndexEntry`
**sense pictures (1)** — `CmPicture`\*

\* the two promises: `source_count` 0 on all three pairs, so no committed census
can stamp them. Each says so in its own reason string, in those words, and a
test asserts the promise set is exactly `{TextTag, CmPicture}` **and** that the
admission is true.

Every other entry's reason string begins `measured a, b, c` in
(ejagham, ngoreme, mbugwe) order, and a test parses all twelve back out and
checks them against T078's censuses. A roster whose evidence can drift from the
artifacts is a roster that will.

**Declared, not derived from `CENSUS_REPORT_ONLY_RESIDUE`**, and the two sets
are provably different: the residue roster carries the phonology family under an
owner that names no existing feature; this one carries `Text`, `TextTag`,
`ReversalIndex`, `ReversalIndexEntry` and `CmPicture`, which the residue roster
does not. `governed - residue` and `residue - governed` are both asserted
non-empty, so a later hand that tries to collapse them into one list fails.

**Out, and asserted class by class**: `PhSequenceContext`,
`PhSimpleContext{Bdry,NC,Seg}`, `PhCode`, `PhFeatureConstraint`, `FsFeatStruc`,
`FsClosedValue`, `CmPossibility`, `MoAffixProcess`, `PhNCFeatures`, `CmFile`,
`CmFolder`. Every one is a required row with a real loss on at least one pair,
which is exactly what makes rostering them tempting.

## The three locks — where they live and what breaks without them

**Lock 1 — import-time disjointness.** `Lib/census.py`, at module scope
immediately after `PHASE_5_CLASSES`. Two raises: a rostered class named by a
phase predicate, and an entry that is not a two-string `(owner, reason)` pair.

*Stronger than T079's*, in one specific way. `report.py` checks the roster
against `models.CENSUS_PHASE_GATED_CLASSES` — a hand-spelled **mirror** of the
predicate scopes, because `models.py` cannot import `census.py` (the dependency
direction is census → models) — and therefore needs a second check to prove the
mirror still matches. This lock reads `PHASE_1_CLASSES`,
`PHASE_2_MATCHED_CLASSES`, `PHASE_3_CLASSES` and `PHASE_4_CLASSES` **themselves,
three lines above**, so there is no mirror to drift. `PHASE_5_CLASSES` is
excluded for the reason its own comment gives: it is `None`, meaning "every
required row", and folding it in would make every class phase-gated and the
roster necessarily empty.

*Remove it and*: `models.CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES["MoStemMsa"] =
(...)` gives P1's own required-`MATCHED` class an admissible P5 line and a zero
`unexplained_shortfall`. Exercised in a **subprocess**, because the lock is
import-time by design and an assertion a `-k` selection can deselect is not a
lock — the artifact would still get written.

**Lock 2 — the cap**, `census_cli.accounted_for_governed_class`. `count =
max(0, -difference) − sum(existing shortfall lines)`.

This is not only R-2. `census.unexplained_counts` computes `max(0, -difference)
− sum(shortfall lines)` and `census._phase_5` fails a row whose
`unexplained_shortfall` is nonzero **after** accounting, so the cap is also the
exact figure that makes a stamped row **pass**. There is one right number:
overshoot is `CENSUS_ERROR` at `census.over_accounted_directions`; undershoot
leaves the row red behind a line that looks like progress. Pinned both ways
(`test_the_cap_is_what_makes_a_stamped_row_pass_not_merely_safe` forges a line
one short and shows the residue of 1).

Unlike `accounted_for_drops`, the count is derived from the row's **own**
difference rather than from a run-report tally, which is what makes the cap
airtight rather than best-effort: there is no external number to outrun and no
shared tally two rows could both spend.

The two non-shortfall directions, ruled on explicitly rather than falling out of
an inequality:

- **`difference is None` → nothing.** T099: a null difference is not a zero.
  `row_verdict_class` makes such a row `NOT_EVALUATED`, `_phase_5` skips it, and
  `class_row_artifact` zeroes both residues for it — a line would claim objects
  nobody counted against a row the gate does not read. The schema's `count` has
  `minimum: 1`, so there is not even a zero-count line to express it with.
- **`difference >= 0` → nothing.** The contract's table gives this token
  direction "either", so the token *would* permit a surplus line; the refusal is
  a judgment. A destination holding *more* objects of a governed class is not
  something another feature failed to do, it is something that happened, and
  naming an owner would excuse an over-creation nobody has attributed. Every
  governed non-`MATCHED` row on all three pairs is `SHORTFALL`, so the refusal
  was made before it was needed.

Ordering: a **reported drop takes the room first**, because it is the more
specific claim — it names run-report content invariant 5 can resolve — and the
governance line takes what is left. The other order would let the residual claim
swallow the difference and starve the evidenced line. When the room runs out
entirely, the refusal goes in `notes` rather than being an absence a reader has
to notice (T023c: a capped number is never silent).

*Remove it and*: a class with a reported drop covering the whole shortfall gets
a second line for the same objects, R-2 fires as `CENSUS_ERROR`, and the
artifact stops validating. Remove only the *existing-lines* term and the same
happens on every row that carries both.

**Lock 3 — gate-inertness, proved by emptying the roster.** The forge in
`TestT109Lock3TheRosterIsGateInert` emits a full artifact through the real path
(`_row_for_entry` → `class_row_artifact` → `build_artifact` → `stamp_verdict`)
and serialises it with the exact `json.dumps(..., indent=2, ensure_ascii=False)
+ "\n"` that `census_cli.run` writes to disk — so "byte for byte" means the
bytes of the artifact file, not a dict comparison.

Three assertions, and the third is what makes it falsifiable:

1. emptying the roster removes the token from the bytes;
2. the emptied artifact is not merely token-free but is the artifact the
   **pre-T109** emitter wrote — every row's `accounted_for` is `[]`, every
   residue is the full difference, `accounted_shortfall` is 0. That is precisely
   T081's "carries NO accounting line";
3. **the leak detector.** A roster containing only `CmAgent` — a class the
   artifact holds and does not lose — reproduces the emptied bytes *exactly*.
   The forge puts `PhCode` at the **same −140 as `Segment`** in the same
   artifact, so a line produced from anywhere but the roster lookup, or keyed on
   the difference rather than the class, shows up. A companion test asserts the
   emitter's own source contains no direct read of the roster dict, only
   `census.governed_by_other_feature(` — a second read would make the roster
   un-emptiable and this lock decorative.

*Remove it and* the roster stops being auditable: nobody could show that a
rostered class buys only the line it is visibly responsible for.

## What the task line got wrong

1. **The scope clause** is narrower than its own cited authority and its own
   stated justification (above). Ruled on, pinned as a test.
2. **`CmFile` "was NOT in T081's stampable nine"** — a misreading of T081's
   per-corpus table. It is in mbugwe's eleven and ngoreme's thirteen and both
   figures are unreachable without it. The exclusion here is a fresh ruling on
   evidence, not a continuation.
3. **T081's per-corpus figures** hold on ejagham only. 13 / 64,621 → 11 /
   64,618 and 11 / 8017 → 9 / 5841, the delta being `CmFile` + `CmFolder`.
4. **`_phase_5` line numbers** in the orientation (`census.py:4140-4180`) had
   shifted; the predicate is at `4222` pre-T109. Noted only because the next
   task will be handed the same kind of pointer.

## NEW DEFECT, named and not fixed

**`CENSUS_REPORT_ONLY_RESIDUE` under-covers two of the three paths the spec
Assumptions hand to other features.** `Text`, `TextTag`, `ReversalIndex`,
`ReversalIndexEntry` and `CmPicture` are all absent from it, while `StText`,
`StTxtPara` and the four `Wfi*` classes are present. Consequences, both
display-only and both visible:

- `report._census_row_tier` reads that roster. `StText` renders in the
  `report_only` band; `Text` — its owner via `ContentsOA`, governed by the same
  feature, and now carrying a `GOVERNED_BY_OTHER_FEATURE` line — renders as
  plain `accounted`. Two classes on one path, two different words.
- `ReversalIndex` is a required `SHORTFALL` on **all three** pairs and reads as
  a class 038 merely accounted for rather than one it does not own.
- `report_only_roster_defects()` cannot see this: its four checks all look for
  a class that should not be *on* the roster, never for one missing from it.

Not fixed here: T109's remit is the accounting line, and widening T079's roster
changes a console column on committed evidence that other tests read. Filed as a
finding, per this feature's convention that findings become numbered task lines.
The narrow version is "add the five classes to `CENSUS_REPORT_ONLY_RESIDUE`";
the load-bearing version is "give `report_only_roster_defects` a completeness
check, so the residue roster cannot be silently short of a path the Assumptions
name".

## Suites

| | before (`bc11110`) | after (`f985ee6`) |
|---|---|---|
| `tests/unit` | 3731 passed / 79 skipped / 14 xfailed | **unmoved** |
| `tests/integration` | 657 passed / 0 failed / 75 skipped | **718** passed / 0 failed / 75 skipped |

+61 integration tests, all T109's own. No existing test moved, which is the
expected result: T109 changes the **emitter**, and no committed artifact was
re-emitted — a test asserts every T078 row still carries `accounted_for: []`
and `accounted_shortfall: 0`, so none of the measurements above can be an
artifact quietly edited into agreement. No live FLEx project was opened and
nothing was written to any project.
