# T086 -- a phase has a scope, and its gate was ignoring it

**Date**: 2026-08-20
**Commit (code)**: `856b105` on `038-transfer-fidelity-gaps`
**Closes**: T038 (P1), T075 (P2), T048 (P3), and T086 itself
**Artifact**: `CENSUS-20260820-150540`, committed as
`tests/integration/_snapshots/census-038-t039d-run1.json`

---

## The finding

Three gate tasks were stuck on the same clause, and none of them was stuck on
anything it owned.

T038 (P1), T075 (P2) and T048 (P3) each state three clauses: the classes the
phase names are MATCHED, the phase-specific extra condition holds, and the gate
"exits 0". Re-gating the measured artifacts confirms the first two on all three:

| phase | task | predicate | in-scope capped rows |
|---|---|---|---|
| P1 | T038 | satisfied | none |
| P2 | T075 | satisfied | none |
| P3 | T048 | satisfied | none |
| P4 | T064 | satisfied | none |
| P5 | T081 | NOT satisfied | all 13 |

The gate nevertheless exits 8, because `census_cli._print_gate` computes

```python
capped = census.gross_basis_suppressions(artifact) if code == 0 else ()
```

**project-wide, even when `--phase` was named.** Any 5.2 suppression anywhere
forces `CAPPED_PASS_EXIT_CODE`. The 13 suppressions on this run are
`CmPossibility` 304, `FsClosedValue` 46, `FsFeatStruc` 23, `PunctuationForm`
586, `ReversalIndex` 2, `ReversalIndexEntry` 1, `StText` 17, `StTxtPara` 91,
`WfiAnalysis` 136, `WfiGloss` 135, `WfiMorphBundle` 219, `WfiWordform` 49 and
`PhCode` 34 -- 1643 objects of texts and wordforms (governed by their own
feature), R7 report-only residue (T079) and T081's scope.

So P1's gate could not go green until **T079** gave the residual classes their
`GOVERNED_BY_OTHER_FEATURE` lines. T079 is Phase 9. Phase 1's acceptance was
gated on Phase 9's work, which inverts the ordering the whole plan is built on
-- and the phase gate stopped being usable as a sequencing tool at all, which
is the one job 9.1 gives it.

## The fix that was REJECTED

Bound `census_cli`'s capped-pass exit code to the named phase. It is a
four-line change, it needs no new test, and it closes all three tasks
instantly. It was rejected.

`gate --phase 1` would then exit **0** on a run that lost 1643 objects. Section
9 says, in as many words, that there is "deliberately no verdict meaning 'loss
reported, review advisable, exit success'". T024b was filed precisely to remove
one of those: both live sanity pairs were reporting `CENSUS_ACCOUNTED` / exit 0
/ `passed=True` while carrying 44-47 failing rows and 74,157 units of
unexplained shortfall, and T024b's own text records that it considered
"require `--phase` for a passing gate" and chose the distinct exit code
instead. Making `--phase` the way to get exit 0 back is that rejected option
arriving through the side door.

**The gate is therefore unchanged.** `gate` and `gate --phase N` both still
exit 8 while anything at all is capped.

## What actually changed

The **clause**, not the gate:

> exits 0 -- **or** exits 8 with every capped row provably outside the classes
> this phase names.

And the proof moved out of the tasks' prose into tests. "None of them is P1's"
had been asserted in three task descriptions since 2026-08-20 and checked by
nothing.

Three pieces of code, all in `Lib/census.py`:

1. **`PhasePredicate.classes`** -- each phase declares its scope. Required with
   no default, so a phase added later cannot silently inherit another's. Built
   from the constants the predicate already iterates (`PHASE_1_CLASSES =
   PHASE_1_MATCHED_CLASSES + ("PhPhoneme",)`, `PHASE_3_CLASSES =
   ("PartOfSpeech",) + PHASE_3_OWNED_CHILD_CLASSES`) rather than a second
   hand-maintained list that can drift from the one `evaluate_phase` enforces.

   A phase's scope is every class it **names**, not only the ones it counts. P1
   names `PhPhoneme` on the duplicates condition and never requires it MATCHED;
   P3 names `PartOfSpeech` on `match_basis.enriched > 0`. Leaving either out
   would let a phase pass its amended clause while its own row was capped --
   the one direction this must not be wrong in, which is
   `_AMBIGUOUS_IDENTITY_SKIP_CLASSES`'s rule from T048g restated.

2. **`phase_classes(phase)`** -- reads the scope off the predicate. `None` for
   P5.

3. **`phase_scoped_suppressions(artifact, phase)`** -- the suppressions inside
   the phase's scope. On an **unbounded** phase it returns every suppression,
   so P5 can never call a capped row somebody else's problem and **T081 gets no
   escape hatch**. An empty tuple is refused at construction, because "no row
   is in scope" would make the phase-scoped reading unfalsifiable.

`gross_basis_suppressions` gained an optional `classes=` bound rather than a
second implementation: T024b's comment requires the cap, its notes and the exit
code to be unable to disagree about which rows are capped, and one
implementation is how that stays true. The bound is matched against the row's
label **and** its bare `class`, so an Amendment A1 split row -- whose label
carries the owning feature system -- is still recognised by a caller naming the
plain class.

## Why the new clause is not a rubber stamp

Falsifiability, on real data rather than on fixtures. The two pre-fix snapshots
`census-038-ejagham` and `census-038-ngoreme` **are** T024b's 44/46-capped
measurements, and on both of them the capped rows land inside *every* bounded
phase's scope:

| snapshot | P1 in-scope capped | P2 | P4 |
|---|---|---|---|
| ejagham | `MoInflAffMsa`, `MoStemMsa`, `PartOfSpeech` | both | both |
| ngoreme | all four MSA classes + `PartOfSpeech` | both | both |

`test_the_amended_clause_refuses_the_pre_fix_runs` pins that the clause refuses
them. Both mutation directions were verified to fail:

- bound ignored (the old project-wide reading) -- **4 tests fail**
- bound matches nothing (the escape hatch) -- **3 tests fail**, including both
  falsifiability tests

21 tests. Census integration 252 passed / 29 skipped; `tests/unit` 3352 passed,
unchanged.

## The snapshot

`census-038-t039d-run1.json` is the **raw** 75 KB artifact, not a distillation
like `idempotence-038-t039.json`. Every assertion is recomputed from the
measurement rather than read out of a summary of it, and whole census artifacts
of this size are already committed repo data (`census-038-ejagham.json` 67 KB,
`census-038-ngoreme.json` 70 KB). It is the run1 half of T039's live pair --
`Ejagham Mini` -> `GT038 T039d Target`, one restore, one transfer, one census
-- so no new live run was needed: gating is a pure function over the artifact,
and re-measuring would have destroyed the record without proving anything.

## Two things noticed and deliberately not acted on

1. **P4 is satisfied on this artifact too, with an empty in-scope capped set.**
   That is **T064**'s gate, and its text carries clauses beyond the predicate
   ("either alone can be satisfied by the defect itself"). Left for whoever
   owns T064 rather than closed in passing.
2. **`test_ngoreme_flex_holds_1949_and_ngoreme_holds_1945`
   (`test_object_census.py:3943`) prints `Windows fatal exception: access
   violation`** from `flexicon/code/FLExInit.py:64` via
   `census.py:794 _ensure_flex_initialized`. The suite still completes and the
   test is skipped/passing, and nothing in this change touches the FLEx init
   path. Unrelated, pre-existing, and worth a look on its own.
