# T023a + T023c -- the gross-basis verdict cap, and making it audible

- **T023a `ca64629`** -- the cap, in `recompute_verdict` (one verdict source).
  `Lib/census.py` +200/-2, plus a `TestGrossBasisVerdictCap` class in the existing
  `tests/integration/test_object_census.py` (deliberately not a new file, so
  `tests/unit`'s file-globbing discipline tests cannot drift).
- **T023c `4d3de35`** -- rendering `notes`. `Lib/report.py`
  (`_census_cap_was_overruled` :659, `_census_notes` :684, block at :1559-1590),
  `census_cli.py` (`_artifact_notes` :959, `_print_notes` :987, one call in
  `_print_gate` :1086 -- the single surface both `run` and `gate` print through).

## The contract wording implemented against

`fidelity-census.md:251`, the `starter_subtraction_basis` table:

> `baseline_gross | baseline present, run report absent | starter_matched_to_source:
> null; gross subtraction used; every row is advisory for SHORTFALL purposes and the
> run verdict cannot exceed CENSUS_ACCOUNTED`

and the worked example at `:34-36`: 21 starter phonemes matched by name, 20 new
created, destination total 43; gross subtraction gives 43 - 23 = 20, so `difference`
**-21** -- "a shortfall reported on a *correct* run."

## Before / after on that example

```
PhPhoneme: source=41 total=43 baseline=23 matched=None basis=baseline_gross
           net=43-23=20  difference=-21  unexplained_shortfall=21

BEFORE                                     AFTER
recompute_verdict = UNEXPLAINED_SHORTFALL    CENSUS_ACCOUNTED
exit_code         = 1                        0
gate passed       = False                    True
```

The five behaviour-pinning tests were confirmed to **fail** with the cap neutralised
(monkeypatched `is_gross_basis_row` / `gross_basis_suppressions`), so they pin the cap
rather than merely passing alongside it.

## A ceiling on unexplained tallies, NOT on severity

Over the same capped artifact:

| added condition | verdict | exit |
|---|---|---|
| (none) | `CENSUS_ACCOUNTED` | 0 |
| `errors[]` present | `CENSUS_ERROR` | 7 |
| derivation mismatch | `COVERAGE_INCOMPLETE` | 6 |
| `starter_baseline.kind: none` | `BASELINE_MISSING` | 4 |
| `starter_baseline` block absent | `BASELINE_MISSING` | 4 |
| baseline `data_model` older | `BASELINE_STALE` | 5 |
| 21 duplicate phonemes | `DUPLICATE_IDENTITY` | 3 |
| one `baseline_matched` shortfall row | `UNEXPLAINED_SHORTFALL` | 1 |
| forged stored `CENSUS_CLEAN`/0, no baseline | `BASELINE_MISSING` | 4 |

T014's adaptive bypass sweep was re-run over a gross-basis, baseline-less artifact
across every `--phase` and every candidate flag the parser actually has: **no
invocation exits 0.**

**The cap is the RUN verdict only.** `row_passes` on the capped row is still `False`,
`evaluate_phase(artifact, 5)` still unsatisfied naming PhPhoneme, and
`gate_artifact(artifact, phase=5).passed` is `False` -- a phase cannot declare itself
done on gross-basis arithmetic.

A genuinely clean gross-basis run still reports `CENSUS_CLEAN`, suppressions `()`,
notes `[]`.

## Granularity: per row, conservatively

`starter_subtraction_basis` is per row (`census-artifact.schema.json:405`,
`$defs.classRow`); it does not exist at artifact level, while the cap sentence speaks
of "the **run** verdict". The contract is **silent on a mixed artifact**, so the
suppression is applied per row: one gross-basis row caps only its own contribution,
and a `baseline_matched` row's shortfall remains trustworthy evidence yielding
`UNEXPLAINED_SHORTFALL` / exit 1 in the same artifact.

The two readings coincide in the case the contract actually describes, because
`census-artifact.schema.json:139` says an absent `transfer_run.report_path` "forces
starter_subtraction_basis 'baseline_gross' on **every** row", and
`census_cli.py:711/720` sets exactly that on the live `run` path today.

## The cap is now audible, and cannot lie

`stamp_verdict` appends the cap notes; T023c renders them beside `report.py`'s
existing `[INFO] ... FLOOR` line and above the CLI's verdict headline.

**The contradiction T023c caught:** `stamp_verdict` writes a cap note whenever the
gross basis suppressed a tally, *including on a run a more severe verdict then
decides* -- so unqualified rendering printed "verdict CAPPED at CENSUS_ACCOUNTED"
beside `[FAIL] ... exit 4`. `_census_cap_was_overruled` compares the **already
computed** gate verdict against the published `GROSS_BASIS_VERDICT_CAP` via
`most_severe_verdict`; it does **not** re-ask whether the artifact is on the gross
basis, so it cannot drift from the cap. Output gains:

```
[INFO] the cap those notes describe did NOT decide this run: BASELINE_MISSING is
       more severe than the CENSUS_ACCOUNTED ceiling, so it stands (exit 4)
```

**Rendering reads BOTH the stored `notes` array and `gross_basis_cap_notes()`**, in
that order, deduplicated. Not belt-and-braces: `gate` reads a file another producer
wrote and `gate_artifact` **recomputes** the verdict, so an artifact that never went
through `stamp_verdict` can be gated to a capped `CENSUS_ACCOUNTED` carrying no note
at all -- array-only rendering would leave exactly the silence this task removes.
Same on `report.py`'s path, where a `dict` handed straight to `RunReport.census` is
never stamped. Neither surface re-derives "is this capped"; that stays in
`census.is_gross_basis_row`.

## Notes remain non-load-bearing (invariant 9)

```
with notes       : CENSUS_ACCOUNTED  exit 0  (2 notes)
notes = []       : CENSUS_ACCOUNTED  exit 0  (0 notes)
notes key absent : CENSUS_ACCOUNTED  exit 0
fabricated cap note on a NON-gross artifact: UNEXPLAINED_SHORTFALL exit 1
```

`census gate` on the notes-stripped artifact still exits 0 **and still prints the
cap**, because the sentence is regenerated from the basis rather than read back.
A fabricated note is displayed but explicitly qualified, and cannot buy a cap.
T023a's `test_no_verdict_depends_on_a_note` passes unchanged and unweakened.

## The 5.2 wording had to be clarified (`8501f23` on `main`)

"cannot exceed `CENSUS_ACCOUNTED`", read literally against the published severity
ordering (`:459-469`), would also suppress `DUPLICATE_IDENTITY`, `BASELINE_MISSING`,
`BASELINE_STALE`, `COVERAGE_INCOMPLETE` and `CENSUS_ERROR` -- contradicting 5.3
("Staleness and absence are **verdicts**, not warnings. There is no path on which a
missing baseline yields exit 0", `:80-81`) and 5.2's own closing line ("Section 6 is
what does, and it is not optional", `:49`). The governing clause is the local one in
the same sentence: advisory *for SHORTFALL purposes*. Wording clarified in place; no
semantics changed.

Separately noted, unresolved and harmless: `fidelity-census.md:22-25` says a
`starter_capture` baseline records "both the count and the **natural keys**",
presuming `carries_natural_keys: true`, while `schema:337` makes it a boolean whose
false value forces the gross basis -- and T023 measured that false is what a
whole-project capture actually is. The schema was followed; nothing depends on the
resolution.

## Tests

`test_object_census.py` **112 passed** after T023a (was 91; +21 new, no pre-existing
test changed or removed -- nothing had encoded the uncapped behaviour), then **136**
once T023c's 8 and T023b's 16 landed in the same file.
`tests/unit` **27 failed / 2624 passed** throughout -- byte-identical to baseline.
`test_report.py` + `test_dropped_item_report.py` + `test_cycle16_drop_reporting.py` +
`test_038_foundational.py`: 73 passed.

## Process hazard worth remembering

T023b and T023c ran **concurrently in the same git worktree** and therefore shared
one index. T023c's first two commit attempts swept in T023b's uncommitted `census.py`
(+392/-42) and its appended 306-line test block; it detected this, rebuilt the commit
with `reset --soft` plus explicit staging, and restored T023b's block byte-for-byte.
`4d3de35` contains only its own three files.

**Parallel agents editing disjoint FILES still collide on a shared INDEX.** Use
separate worktrees or serialize. Also: the checkout is CRLF while both agents' tooling
wrote LF, so `census.py` and `test_object_census.py` are LF in the working tree; git
normalises on add, so it is cosmetic.
