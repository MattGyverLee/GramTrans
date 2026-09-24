# T079 — the word that was already taken, and the risk that arrived inverted

**Closed** 2026-08-25. Consumes T078's re-scoping. **No successor filed** — the
roster IS the successor list, and every entry on it names one.

## What T079 asked

R7 scoped Phase 5 as report-only: "every residual class is measured by the R2
census and, where counts differ, gets a run-report line with a reason." It
recorded its own residual risk in the same breath: "a report-only class can
stay broken indefinitely once it has a report line, because the gate goes
green. Mitigated by `status: 'unmeasurable'` being a distinct census value from
`'match'`, so a follow-up feature can count what is still merely explained, not
fixed."

**Neither half existed.** T078's three post-037 censuses measured every one of
these classes as a bare row with `accounted_for: []` — the number was there and
nothing said who owns the class — and the row's console state came straight off
`verdict_class`, so a report-only class at difference 0 printed the same word as
a class this feature gates on.

## The risk arrived INVERTED, and bigger than R7's list

R7 anticipated a report-only class staying *red* behind an explanation. What
T078 measured is the opposite: on the ejagham pair **nine** rostered classes
read `MATCHED`.

| Class | ejagham | ngoreme | mbugwe |
| --- | --- | --- | --- |
| `FsComplexFeature` | 1/1 | 2/2 | 1/1 |
| `FsSymFeatVal` | 51/51 | 90/90 | 70/70 |
| `FsClosedFeature` | 20/20 | 24/24 | 21/21 |
| `LexEntryInflType` | diff 0 | diff 0 | diff 0 |
| `PhFeatureConstraint` | 0 (holds none) | **-47** | **-32** |
| `LexReference` | 0 (holds none) | **-5** | 0 |
| `CmFile` | 0 (holds none) | **-2** | **-2173** |
| `Segment` | 198/198 | **-26666** | **-2** |
| `CmTranslation` | 68/68 | **-7923** | 0 |

Five earned the green; four are **vacuous** — that corpus simply holds none of
the class — and `Segment` reads 198/198 on one pair while losing 26,666 objects
on the next. `census._phase_5` passes a MATCHED required row with a bare
`continue`, so one word covered all nine. That word was a claim this feature
never made.

## The vocabulary decision, and the three things rejected

- **REJECTED: R7's literal spelling `unmeasurable`.** The word is *already
  taken*, for a different and load-bearing meaning:
  `census.ClassCounts.unmeasurable` is the per-**project** set of classes whose
  repository accessor did not resolve, `census.unmeasurable_errors` turns each
  into a `CENSUS_ERROR`, and `ClassCensusRow._check_null_counts` reasons about
  it by name. Reusing it would make one word mean both "we could not count
  this" and "we counted it, it agrees, and nobody here owns it". It would also
  be **false**: every class on the roster was measured, to the object. `PhCode`
  -43 / -89 / -79 is a measurement, not the absence of one.
- **REJECTED: three tokens for T078's three situations.** Only one of them
  collapsed into `matched`. Measured-and-differing already carries `SHORTFALL`
  plus an `unexplained` state; excluded-from-the-delta already carries
  `NOT_EVALUATED` with `OUT_OF_SCOPE_CLASS` / `GOVERNED_BY_OTHER_FEATURE`.
  Minting a token for either would be a second name for a state the artifact
  already states correctly.
- **REJECTED: an 18th `CENSUS_REASON_TOKENS` member, and reusing
  `GOVERNED_BY_OTHER_FEATURE` on these rows.** Both are in
  `CENSUS_NOT_EVALUATED_REASONS`, so putting one into `ClassCensusRow.reasons`
  flips `verdict_class` to `NOT_EVALUATED` and **deletes the measured shortfall
  from `total_shortfall` and from the gate**. That is laundering a red run, not
  reporting it.
- **CHOSEN:** one new member of the **console row-state** vocabulary,
  `report_only`, distinct from `matched`. That vocabulary is the "state" column
  and the "Rows by state:" tally in `report._render_census_lines`; it is **not**
  a property of `census-artifact.schema.json`. So `schema_version` stays 1, no
  enum in the contract moves, and the census artifact is byte-identical. The
  *report* is what changed — which is exactly what R7 asked for.

## What landed

`models.py`

- `CENSUS_ROW_STATES` — the console state vocabulary, **moved** out of
  `report.py` (not forked) so the one place a state value is written down is the
  module every other census vocabulary is written down in, per
  `Lib/census.py:20`, "THE VOCABULARIES ARE RE-EXPORTS, NEVER RE-DECLARATIONS".
  `report._CENSUS_ROW_TIERS` is now that tuple by **identity**, pinned by test.
  `report_only` sits below `unexplained` and above `not_evaluated`/`matched`.
- `CENSUS_REPORT_ONLY_STATE` — the string, spelled once.
- `CENSUS_REPORT_ONLY_RESIDUE` — 23 classes → `(owner, reason)`, each reason
  carrying T078's three measured numbers. Gate-inert by construction.
- `CENSUS_PHASE_GATED_CLASSES` — every class a 038 phase predicate names.

`report.py`

- `_census_row_tier` returns `report_only` for a rostered class, **after** the
  `unexplained` and `not_evaluated` tests. `unexplained` still wins: a
  report-only class with an unaccounted loss keeps its `[FAIL] UNEXPLAINED`
  line and its place at the top of the table. The state exists to stop a *green*
  row reading as a promise, never to soften a red one.
- `(report-only)` mark on every rostered row, including the red ones — the mark
  and the state answer different questions, and the mark is the one that names
  the owner.
- `report_only_residue_lines()` — the machine-readable surface, so a follow-up
  feature counts "what is still merely explained, not fixed" by calling a
  function rather than parsing console text. **Agreeing rows lead it**, which is
  deliberately not the table's order: 23 rostered classes against
  `_CONSOLE_MAX_ROWS` 20 means the table's urgency order truncates away exactly
  the rows this block exists for (measured on ngoreme: 19 differing rows left
  one of the four agreeing rows visible).
- `census_report_only_residue` — a **run-report** key beside `census`, not
  inside it: every object in `census-artifact.schema.json` is
  `additionalProperties: false`, so a new key on the artifact would be a hard
  validation failure and would force a `schema_version` bump on a format that
  has not shipped. Omitted when empty, so a census-free run report stays
  byte-identical to the pre-038 build.
- `report_only_roster_defects()` — four checks, returned as strings rather than
  raised so a live run can never die inside a renderer.

## Direction 2: a class this feature owns cannot be reclassified to dodge a gate

Two locks, because a roster is exactly the kind of list that grows by accident.

1. **Import-time disjointness.** `_REPORT_ONLY_OVERREACH` raises if any
   rostered class is named by a phase predicate.
2. **Gate-inertness, tested by emptying the roster.** With the roster and with
   `{}`, `_census_gate` and `_census_json` return byte-identical results —
   verdict, exit code, failures, `gate_scope`, `verdict_class`, every tally. So
   putting a class *on* the roster cannot buy a pass. The only things that move
   are one word in the state column and the contents of one report block.

`report_only_roster_defects` also asserts `CENSUS_PHASE_GATED_CLASSES` still
equals the union of `PHASE_1_CLASSES`, `PHASE_2_MATCHED_CLASSES`,
`PHASE_3_CLASSES` and `PHASE_4_CLASSES`. `models.py` cannot import `census.py`
(the dependency direction is census → models), so the set is spelled there as
names; this is what stops the copy drifting from the predicates it mirrors.
`PHASE_5_CLASSES` is deliberately excluded — it is `None`, meaning "every
required row", and folding it in would make every class phase-gated and the
roster empty.

## `MoInflClass` is why direction 2 is not theoretical

R7's prose lists `MoInflClass` as report-only — "5 → 0, expected to close as a
side effect of Phases 1/3". But `census.PHASE_3_OWNED_CHILD_CLASSES` names it
and `_phase_1`…`_phase_4` require it MATCHED, so this feature has an
**executable gate** on it. Where the prose and the gate disagree, the gate
wins, and the class stays **off** the roster — rostering a class a phase
predicate gates on is precisely the dodge direction 2 forbids.

`CmAnthroItem` is off it too, for the opposite reason: 859 → 0,
`NOT_EVALUATED` with `OUT_OF_SCOPE_CLASS` on all three pairs, a state already
distinct from `matched`. T078 ruled it excluded, not report-only.

## The three test defects fixed on the way through, and what each was

The T079 implementation was already on disk when this session picked it up, with
three of its 31 tests red. All three were **test-side**, and none of the three
was a disagreement about behaviour:

1. `2609 objects short` — arithmetic. `FsClosedValue` -2045 plus `PhCode` -64 is
   **2109**, and the renderer said 2109. The literal was wrong, not the sum.
2. `models.RunReport(run_id=…)` — `RunReport` is frozen and has no `run_id`; the
   run id lives on the `RunContext` it is built around. Replaced with a
   `_run_report()` builder that constructs the real thing and passes `census=`
   at construction.
3. `assert verdict == "UNEXPLAINED_SHORTFALL"` reading `CENSUS_ERROR` — the
   `_artifact` fixture omitted `projects.*.opened_read_only` and
   `class_list_provenance.derivation_check`, and `census.recompute_verdict`
   tests both **before** it ever looks at a row. An artifact without them
   recomputes to exit 7 no matter what its counts say, so the test would have
   been asserting gate-inertness across a census error rather than across the
   shortfall it is about. The fixture now carries both blocks (with
   `fwdata_sha256_before == after`, i.e. the census moved nothing) and takes
   `**over`, and the gate-inertness test stamps the verdict its own rows
   support — invariant 8 refuses a document whose stored verdict disagrees with
   its recomputed evidence. The test now also asserts `failures == ()`: a roster
   that could not move a verdict but silently added a gate failure would still
   be a way in.

## Suite

`tests/unit` 3693 → **3724 passed** / 79 skipped / 14 xfailed (the 31 new T079
tests; nothing else moved). `tests/integration` **577 passed / 0 failed / 75
skipped**, reproducing T078's baseline exactly — as it must, since nothing T079
touches can move a census row.
