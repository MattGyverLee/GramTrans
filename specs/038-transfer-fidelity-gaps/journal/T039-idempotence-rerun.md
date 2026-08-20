# T039 -- idempotence re-measured, now that enrichment exists

**Date**: 2026-08-20
**Source**: `Ejagham Mini` (read-only)
**Destination**: `GT038 T039c Target` -- restored pristine from
`backups/Ejagham W Target 2026-08-19 0830.fwbackup` (starter digest
`ab37b1cd60dd`, identical to the T038/T048 runs). **`Target`, `Esperanto`,
`GT038 Phase4 Target`, `GT038 Phase5 Target` and `GT038 T048b Target` were
never opened.**
**Censuses**: `CENSUS-20260820-133634` (run 1), `CENSUS-20260820-133834` (run 2)
**Code**: `tests/integration/test_object_census.py` (+13 tests),
`tests/integration/_snapshots/idempotence-038-t039.json` (new). **No source
file changed.**

The first T039 measurement
([T039-idempotence.md](T039-idempotence.md)) could evaluate only two of three
criteria: *"criterion 3 -- NOT EVALUABLE -- enrichment is US4 (T042-T047) and
has not landed. To be re-run when it does."* It has landed (`e6bdb6e`), so this
is that re-run.

**Substantively SC-008 still holds, and more strongly than before.** A second
run creates nothing, changes no count, and adds no child to any collection. But
criterion 3 splits in two, and only its first half is evaluable -- for a reason
that is itself a finding.

---

## The four things measured

| # | criterion | result |
|---|---|---|
| 1 | run 2 plans no `PlannedAction` whose `match_basis.basis is MatchBasis.NONE` for a class run 1 created | **PASS** -- run 2 plans **0 actions of any kind** (run 1: 329) |
| 2 | every class's `destination_count_total` unchanged | **PASS** -- identical across all **75** census entries |
| 3a | every `EnrichedCollection.added == 0` on run 2 | **PASS**, strictly -- all 10 collections across run 2's 4 records read 0, and `dropped` is 0 throughout |
| 3b | `already_present` equal to run 1's `added` | **NOT EVALUABLE** -- the two runs enrich **disjoint object sets**; see below |

Run 2's shape beside run 1's:

```
                run 1     run 2
actions           329         0
overwrites         26        38
skips            1808      2125
enrichments         3         4
dropped_items     399         0
```

---

## Criterion 3b is not evaluable, and that is the finding

The two runs enrich **no object in common**:

| run | enriched | why those |
|---|---|---|
| 1 | Noun, Pronoun, Verb | the three starter POSes it filled |
| 2 | Adjective, Demonstrative, Numeral, Interrogative | POSes run 1 **created**, now matched and found complete |

The intersection is empty, so there is no object on which to compare run 2's
`already_present` against run 1's `added`.

**The totals coincide at 16 and this must not be read as a pass.** Run 1 added
16 children; run 2 reports 16 already present. They are different 16, belonging
to different objects, and the per-collection distributions differ
(`AffixSlotsOC` 6 vs 3, `AffixTemplatesOS` 3 vs 4, `InflectableFeatsRC` 4 vs 9,
and run 1's `ReferenceFormsOC` 2 / `SubPossibilitiesOS` 1 have no run-2 row at
all). `test_the_totals_coincide_but_that_is_not_criterion_3b` pins the
coincidence precisely so nobody promotes it.

### Where the three objects went, and why the skip is CORRECT

All three are among run 2's eleven `GRAM_CATEGORIES`
`ALREADY_PRESENT_BY_GUID` skips, detail *"GUID a8e41fd3... present in target;
all WS slots equal."*

**T043 is working and this skip is constitutionally sound.** The first reading
of that detail -- that the skip rests on writing-system equality alone and so
reprises defect G3 -- is wrong, and worth recording as wrong because it is the
tempting reading. `_plan_gold_reserved_edit` computes
`_compare_pos_owned_collections` at `categories.py:788-790`, *before* either
early skip, and the skip at `:831` fires only on
`not all_gaps and not all_conflicts and not collection_delta`. The comment
there says so: *"Fully identical across every WS slot AND every owned
collection -> nothing to write. This is the one SKIP the clause still allows,
and T043 must not make it unreachable."* So data-model.md 9's requirement --
every scalar field **and all seven owned collections** compared -- is met.

**The defect is evidentiary, not decisional.** The `collections` tuple that
comparison produces holds exactly the `already_present` tallies criterion 3b
wants, and on the skip path it is **discarded**. The skip's detail names only
the WS slots, and no `EnrichmentRecord` is emitted -- even though
`EnrichmentRecord` already models this case (`is_empty`, and
`models.py:1824`'s `all(c.added == 0 and c.dropped == 0 ...)`).

So: **a correct no-op enrichment leaves no record that it happened.** Filed as
**T048e**. It is a small fix on data that already exists at the call site, and
it is what makes 3b evaluable.

---

## Criterion 1 passes, but not for the reason it names

Worth writing down because the criterion looks like a tripwire and is not one.
**No `PlannedAction` carries a `match_basis` at all.** Run 1's 329 actions are
uniformly `<unattributed>|None`; `match_basis` is populated only on
`PlannedOverwrite` (`preview.py:1588`) and on the phonology path
(`categories.py:9024`/`:9106`). `transfer.py` states it three times over --
*"With `match_basis=None` (every plan built today)"* (`:546`, `:1298`, `:3199`).

Consequence: a duplicate create on run 2 would arrive with `match_basis is
None`, and `None.basis` is not `MatchBasis.NONE`, so the criterion's literal
predicate would pass it. **The load-bearing assertion is the action count**
(0), which is why the test asserts that and pins the unfalsifiability
separately, with a tripwire that fires if `PlannedAction.match_basis` ever
starts being populated.

This does not weaken *this* measurement -- 0 actions is strictly stronger than
"0 actions with a particular basis" -- but the criterion should not be reused
elsewhere as written.

---

## The basis drift: same root cause, third appearance, now localised

Two rows still change verdict between the runs **with no count moving** --
exactly what the first T039 journal reported:

| class | run 1 | run 2 |
|---|---|---|
| `PhPhoneme` | MATCHED, `baseline_matched`, matched 21, unexplained 0 | SHORTFALL, `baseline_gross`, matched **None**, unexplained **21** |
| `PhNCSegments` | MATCHED, `baseline_matched`, matched 2, unexplained 0 | SHORTFALL, `baseline_gross`, matched **None**, unexplained **2** |

`destination_count_total` is identical for both (34 and 5). Nothing was lost.

**`PartOfSpeech` does NOT drift** -- `baseline_matched`, 5 of 5, on both runs.
That contrast is what localises the defect, and it also shows T048b and T048d
working as designed.

### Root cause: two incompleteness signals, only one of them bounded

The counts are **not missing** from run 2's report. `matched_to_source
.by_object_class` carries `PhPhoneme: 21` and `PhNCSegments: 2`, byte-identical
to run 1. They are *refused*.

`census_cli.py:1416` gates the strong basis on `matched_complete`, which
`matched_by_class_from_report` (`:734-737`) derives as a **single global
boolean**: false if the report left *any* match unattributed anywhere. Run 2
left 11 unattributed -- `GRAM_CATEGORIES: 5`, `INFLECTION_FEATURES: 5`,
`VARIANT_TYPES: 1` -- so **every one of the 75 rows** loses `baseline_matched`,
including two whose tallies are perfectly attributed and belong to categories
with no unattributed matches at all.

Twenty lines below, the same file solves the same problem correctly. T048b's
withholding is **bounded to the classes actually at risk**
(`withheld_classes`, via `_AMBIGUOUS_IDENTITY_SKIP_CLASSES`,
`census_cli.py:1414-1415`) -- *"an unattributable skip withholds the
`baseline_matched` basis from only the classes it could have been."*
`matched_to_source` already publishes `unattributed_by_category`, which is
exactly the bounding data that rule needs. Filed as **T048f**.

### Why T048d's audit cannot rescue these two

`PartOfSpeech` survives run 2 through the T048d GUID audit
(`starter_matched_lower_bound`). That audit is blind to `PhPhoneme` **by
construction**: a natural-key match links a source object to a destination
object with a *different* GUID, so `B - |D \ Q|` cannot see it. The 21 starter
phonemes matched by name in run 1 are, to a GUID-set comparison,
destination-only objects. T048f therefore needs the bounded-withholding fix,
not a third audit.

The perverse consequence the first journal named still stands, one layer up:
**the better the transfer gets, the worse the census reports it** -- and now
also, *one unattributable match anywhere degrades every class's basis*.

---

## Why T039 stays unchecked

Its substance is proven and its own text explicitly refuses to let the census
verdict decide it: *"Any increase is a duplicate-creation defect regardless of
what either census's own verdict says."* There is no increase, so nothing here
is a transfer defect, and both censuses returning `CENSUS_ACCOUNTED` / exit 8
is the documented gross-basis ceiling, not a failure.

But one of the three criteria **could not be evaluated**, and the reason is a
defect (T048e) rather than an absence of opportunity. Checking the task off
would record an evaluation that did not happen -- the same laundering the
T038/T048 journal refused. T039 is blocked on T048e exactly as T038 was blocked
on T048b.

**What closing T048e will make possible:** the three POSes will carry a record
on run 2, the intersection will stop being empty, and
`test_criterion_3b_is_not_evaluable_because_the_runs_are_disjoint` will fail --
which is its purpose. Replace it then with the real per-object, per-collection
comparison and T039 closes.

---

## Tests

`tests/integration/test_object_census.py::TestT039IdempotenceIsMeasured`, 13
tests, all hermetic over the committed snapshot -- no live project, 0.75s.
File total: **222 passed, 1 failed**; the failure is
`test_t028_has_not_yet_admitted_phphoneme_to_the_roster`, the roster tripwire
that fails identically at `e8e6d4a` (recorded in
[T048d-identity-audit.md](T048d-identity-audit.md) as verified by `git stash`)
and is untouched by this work, which changed **no source file**.

Four of the thirteen exist specifically to stop a future reader misreading this
measurement:

- `test_criterion_1_is_unfalsifiable_as_literally_written` -- the basis clause
  is not a tripwire; the action count is.
- `test_the_totals_coincide_but_that_is_not_criterion_3b` -- 16 == 16 is a
  coincidence of this corpus.
- `test_criterion_3b_is_not_evaluable_because_the_runs_are_disjoint` -- fails
  when T048e lands, by design.
- `test_partofspeech_does_NOT_drift_because_T048b_and_T048d_reach_it` -- pins
  the contrast that localises T048f, so a fix aimed at the wrong layer fails.

## Reproducing this

```powershell
$env:PYTHONPATH = "D:/Github/_Projects/_LEX/GramTrans-038-transfer-fidelity-gaps/src"

# 1. pristine destination, additive -- overwrites nothing
python -c "import sys; sys.path.insert(0,'tests/integration'); from harness.restore import restore_target; restore_target('GT038 T039c Target', backup_path='D:/Github/_Projects/_LEX/GramTrans/backups/Ejagham W Target 2026-08-19 0830.fwbackup')"

python -m gramtrans.census_cli capture-baseline `
  --project "GT038 T039c Target" --out scratchpad/038_census/t039-starter.json

# 2. run 1, census, run 2, census -- NO restore between the runs
python scratchpad/t039b_run.py run1
python -m gramtrans.census_cli run --source "Ejagham Mini" `
  --destination "GT038 T039c Target" `
  --baseline scratchpad/038_census/t039-starter.json `
  --destination-freshly-created `
  --run-report scratchpad/038_census/t039-run1-report.json `
  --out scratchpad/038_census/t039-run1-census.json

python scratchpad/t039b_run.py run2
python -m gramtrans.census_cli run --source "Ejagham Mini" `
  --destination "GT038 T039c Target" `
  --baseline scratchpad/038_census/t039-starter.json `
  --destination-freshly-created `
  --run-report scratchpad/038_census/t039-run2-report.json `
  --out scratchpad/038_census/t039-run2-census.json
```

`scratchpad/t039b_run.py` is the two-line driver over
`harness.full_run.run_full_transfer(..., exclude=frozenset(),
ws_mapping_mode="full")` that also dumps the plan/enrichment side-data the
snapshot is built from. Both censuses opened both projects read-only and
verified their digests unchanged.
