# T093 -- the refusal that was reported as a loss

**Date:** 2026-08-24
**Task:** T093 (US3, FR-017 / SC-010)
**Branch commit:** `4ec8fff` on `038-transfer-fidelity-gaps`
**Artifact:** `tests/integration/_snapshots/incompleteness-038-t093.json`
(`python debug/run038_incompleteness_census.py T093`, source
`Mbugwe LizzieHC practice` -> `GT038 Closure Target` restored from
`Target 2026-07-06 0218.fwbackup`, AFFIX_TEMPLATES-only, `preview_only=True`,
wrote nothing)

---

## What was wrong

`_plan_incompleteness` emitted an `IncompletenessRecord` for every dependent
whose deselected dependency was not in the plan -- including the dependencies
that were **already in the destination**, where the dependent's reference
still resolves and nothing is incomplete.

It could not tell. `_plan_pulled_in_items` (T071) refuses a deselected ref
**before** its planner runs. That is correct for the plan -- a refused
dependency must not be written -- and it is what
`test_a_deselected_dependency_is_not_planned` pins. The side effect is that no
`ALREADY_PRESENT_BY_GUID` / `_BY_IDENTITY` skip can ever exist on the
deselected path, so `_DEPENDENCY_PRESENT_SKIPS` -- the set that already
existed for exactly this question -- could not fire there.

## The measurement

| reading | T073 (before) | T093 (after) |
|---|---|---|
| P1 records (everything deselected) | 35 | **27** |
| P1 records naming an already-present dependency | 8 | **0** |
| P2 records (only the POSes deselected) | 29 | **7** |
| P1 deselection skips | `{gram_categories: 5, slots: 18}` | unchanged |
| P0 / P3 records | 0 / 0 | 0 / 0 |
| refs already in the destination | 2 | same 2 |

`35 - 27 == 8`, exactly the number of records that named one of the two POSes
the destination already had: every record that disappeared is one of the
over-reports and none of the real ones went with them.

**P2 is the reading that matters, and the filing understated it.** Deselecting
only the parts of speech -- the selection a linguist is likeliest to actually
make -- went from 29 records to 7, because those two POSes were between them
the dependency of 22 of the 29 arriving items. Three quarters of that report
was phantom. "8 of 35" was the number the census happened to headline; it was
not the size of the defect.

This is the direction CLAUDE.md records as unshippable for flexicon 4.5.1,
where a source-aware guard "reports a loss that did not happen" and 3 phantom
losses sank the release. A report that cries loss where there was none teaches
the reader to stop reading it.

## The repair, and why it is neither of the two candidates the task line named

The task filed two candidate repairs and said both needed their own evidence.
Neither is what landed.

**(a) "run the refused ref's `plan_action`, then discard everything but the
presence fact"** was rejected in the task line because it "CHANGES T071's
measured composition (an `ALREADY_PRESENT` skip appears where a
`DEPENDENCY_DESELECTED` skip stood) and breaks
`test_a_deselected_dependency_is_reported_not_dropped`". That consequence
follows only if the planner's `Skip` is appended to `skips`. It does not have
to be. The probe runs the planner, reads its verdict, and **discards the
result entirely** -- no plan member, no skip, no edge restamped. The refusal
is still a refusal and still carries `DEPENDENCY_DESELECTED`; the live
artifact confirms the deselection skips are the same `{gram_categories: 5,
slots: 18}` before and after.

**(b) "add a target-presence probe"** was rejected because a bare
`guid in target` check is **Defect G3's exact shape** -- `ALREADY_PRESENT_BY_
GUID` taken without a field-identity comparison, the premise this feature
exists to remove. That objection is right and the fix does not need the
probe it objects to. The question is answered by the category's **own
`plan_action`**, the same matcher that decides ADD-vs-OVERWRITE for every
non-deselected ref, with its full identity logic intact:

| planner verdict | reading |
|---|---|
| `PlannedOverwrite` | matched an existing target object -- **present** |
| `Skip(ALREADY_PRESENT_*)` | matched, nothing to write -- **present** |
| `PlannedAction` | an ADD -- **absent** |
| anything else, or a raise | unknown -- **absent**, so the record stands |

Unknown resolving to "report it" is deliberate: over-reporting one item is
recoverable, and Principle I's failure is the silent one.

## The part that was not about the probe

The presence test had to move **above the cause ladder**, not into the
`deselected` branch. `deselected > cycle > unsatisfiable` orders
*explanations for an incompleteness*; it cannot decide *whether there is
one*. An object already in the destination resolves the dependent's reference
whether the user refused to re-transfer it, whether it sits in a cycle, or
neither -- so presence is tested first and ends the question. The same
argument retires the `cycle` cause for an already-present dependency: a cycle
reports a write-ordering hazard, and an object that is not being written has
no ordering.

The `already_present` set therefore has two feeds now: the skip-derived one
(every path except the deselected one) and `already_present_refs` (the
deselected path's probe). They answer the same question and are unioned.

## What the artifact does NOT do

`incompleteness-038-t073.json` is **not overwritten.** T102 filed what happens
when a committed artifact is re-measured in place -- the before stops existing
and every comparison against it turns red for a reason unrelated to what it
asserts. T073's artifact stays as the before, T093 writes its own, and the
driver now **refuses** to rewrite T073's without `GT038_OVERWRITE_T073` set.
The integration block is split the same way: every test that states what the
code *does* reads the T093 artifact, and the two that state what it *used to*
do say so in their names and read T073's.

## Coverage

- `tests/unit/test_038_pull_in.py` -- 7 new end-to-end cases: an
  already-there dependency reports nothing (both `PlannedOverwrite` and
  `ALREADY_PRESENT_BY_IDENTITY`), the refusal survives unchanged, the edge
  keeps its `deselected` stamp, an absent dependency is still reported, a
  raising probe still reports, and the quiet case is untouched.
- `tests/unit/test_038_incompleteness.py` -- 5 new cases on the channel
  itself, including presence outranking the `cycle` cause (no live instance;
  the five registered relationships form a DAG, so it is constructed and said
  to be).
- `tests/integration/test_038_closure_edge_audit.py` -- the T073 block
  re-pointed to the after-artifact with its numbers restated, plus a T093
  block of 6 tests over the before/after delta.
- Full suite: 3653 unit passed / 79 skipped / 14 xfailed; 517 integration
  passed / 76 skipped.

## The shape, once more

Twelfth appearance of this feature's recurring shape, and the first where the
signal read at the wrong level was one the code **declined to compute**.
`_DEPENDENCY_PRESENT_SKIPS` existed, was correct, was consulted -- and the
path that needed it produced no skip for it to read, because an earlier and
also-correct decision short-circuited before the fact was ever generated. Not
a value read at the wrong level, and not an assumption (T095) or an artifact
(T102): an **absence manufactured upstream by a correct optimisation**.
