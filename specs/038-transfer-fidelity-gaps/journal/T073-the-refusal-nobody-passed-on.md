# T073 -- the refusal nobody passed on

**Date**: 2026-08-21
**Task**: T073 (Phase 7 / US3, Wave 4) -- emit an `IncompletenessRecord` for
every item left incomplete because a dependency was deselected or could not be
satisfied (FR-017), including the cycle case
**Commits**: worktree `038-transfer-fidelity-gaps` `4cebfb2`; spec artifacts on
`main`

---

## What was owed, and what was already standing

T070/T071/T072 had just landed. T071's own measurement was that
`ClosureEdge.deselected` is set on **53 of 53** edges under a full deselection,
and that each of the 23 refused dependencies gets a `DEPENDENCY_DESELECTED`
skip naming the items that wanted it. So the plan knew, per edge, exactly what
the user had refused.

Everything needed to *tell* the user existed too, and had existed since the
Phase 2 foundational layer:

| surface | state before T073 |
|---|---|
| `models.IncompletenessRecord` | complete, with domain validation on `cause` and a non-empty `consequence` invariant |
| `RunPlan.incompleteness` | field present, never passed by `build_run_plan` |
| `RunReport.incompleteness` | field present, `build_from_plan` already forwards it |
| `RunReport.has_incomplete_items` | property present, always `False` |
| `report._incompleteness_json` | serializer present, key omitted because the bucket was empty |
| `render_text_summary`'s "Items arriving INCOMPLETE" block | rendered, never entered |

Six surfaces, wired end to end, fed by an empty tuple. **No `models.py` change
was needed** -- which matters, because Phase 5/6 serialise on that file and
Phase 7 holds only the `categories.py` claim. The whole task was one producer
in `preview.py`.

That is this feature's recurring shape for the eighth time -- *something that
exists and is read at a level where it cannot do its job* -- and it is the
purest instance of it so far, because here the signal was not merely
mis-levelled: it was written by T071 and read by nobody at all.

---

## The measurement

`debug/run038_incompleteness_census.py`, `Mbugwe LizzieHC practice` ->
throwaway target restored from `Target 2026-07-06 0218.fwbackup`, the same
AFFIX_TEMPLATES-only selection T069 and T070 used (a **full copy cannot
observe a closure edge at all**, so the acceptance selection has to be the
narrow one). Snapshot:
`tests/integration/_snapshots/incompleteness-038-t073.json`. The census exits 0
with all seven claims satisfied.

| case | edges | records | cause |
|---|---|---|---|
| nothing deselected | 53 | **0** | -- |
| everything deselected (23 GUIDs) | 53 | **35** | deselected |
| only the 5 POSes deselected | 53 | **29** | deselected |
| full copy | 0 | **0** | -- |

**The before is 0 in every one of those rows**, and it is taken from the
committed record rather than from memory: `closure-pull-in-038-t070.json`, the
artifact of the immediately preceding wave over the *same* source, target and
selection, contains **no `incompleteness` key at any depth** while carrying 53
edges marked deselected and 23 deselection skips. A test asserts that
(`test_the_pre_t073_artifact_reported_none_of_this`), so the before cannot
quietly become unfalsifiable later.

### THIS DRIVER WRITES NOTHING

Worth stating because every sibling driver in this phase writes. FR-017 is a
**plan-time** determination (Principle III -- Preview decides, Move obeys), so
the records exist before anything is written and all four cases are
`preview_only=True`. The restore is still done, for a reason that only became
visible while writing the driver: *whether the dependency is already in the
destination* is one of the facts a record depends on, so a target left in
whatever state the last driver put it in makes the measurement unrepeatable.

No `.fwdata.lock` was left behind (T090's trap): the three on disk afterwards
are the pre-existing ones on `Ejagham Full`, `Ejagham Full GT-Test` and `Hdi`,
neither of which this run opened. The driver prints the lock inventory itself
so a future run cannot leave one silently.

---

## The three decisions that the numbers are made of

### 1. A record is emitted only when the DEPENDENT is actually being written

This is why 53 edges become 35 records and not 53, and it is the decision I
spent longest on.

Under a full deselection the edges split `TEMPLATE_TO_POS` 11,
`TEMPLATE_TO_SLOT` 24, `SLOT_TO_POS` 18. The first two have templates as their
dependent -- templates are the seeds, they transfer, and each arrives having
lost a POS and some slots. **The 18 `SLOT_TO_POS` edges have SLOTS as their
dependent, and those slots were themselves deselected**, so they do not arrive
at all.

Reporting them would have said, of an object that never reaches the
destination, that it "arrives incomplete" -- and it would have counted one loss
twice, under two different SC-010 buckets: the slot is already
dropped-with-reason via its own `DEPENDENCY_DESELECTED` skip (18 of the 23).
SC-010's whole content is *exactly one* of ADD / UPDATE / SKIP /
dropped-with-reason per item. An item cannot be both dropped and
arriving-incomplete.

So the gate is membership in `actions` or `overwrites`. An enriched
destination object (an `overwrite`, FR-020..FR-022) counts as arriving --
reading only `actions` would have silently exempted every UPDATE, which is a
pinned test.

**The deselect-only-the-POSes case exists to prove the gate is not just a
suppression.** Refuse the 5 POSes and keep the slots: now the slots DO arrive,
and they arrive incomplete -- 29 records over 29 distinct items (11 templates +
18 slots) naming 5 distinct missing dependencies. That is the two-hop shape
T069's census warned Phase 7 to expect, and a full deselection cannot show it.

### 2. Satisfaction is read off the PLAN, not off the skip list

Three ways a dependency is satisfied: it is being written, or it is **already
in the destination** (an `ALREADY_PRESENT_BY_GUID` / `_BY_IDENTITY` skip), or
neither -- which is `unsatisfiable`.

Deriving that from plan membership rather than from the skips buys one thing I
did not expect to need: `_plan_pulled_in_items` has a **silent exit**. Its
final branch is `elif result is not None:` -- a `plan_action` that returns
`None` plans nothing *and* skips nothing. A reader keyed on
`SkipReason.DEPENDENCY_UNRESOLVED` would have inherited that hole verbatim.
Keyed on "is it in the plan", the hole reports itself. Pinned as
`test_a_dependency_that_vanished_without_any_skip_is_reported_anyway`.

The `ALREADY_PRESENT_*` exemption is the negative that keeps this honest, and
it is not hypothetical: without it, FR-017 would fire loudest on the case where
nothing was lost. That is the phantom-loss failure CLAUDE.md records at length
for flexicon 4.5.1's natural-class features -- a report that says a thing was
lost when it was not is a different failure from a silent loss, not a safer
one.

### 3. The cycle came from the edges, because `topological` throws it away

The task line names the cycle case explicitly, and the interesting part is
where the fact had to be recovered from.

`closure.walk` is cycle-**tolerant** by construction: it dedups on
`(category, guid)`, so it cannot loop, and it also cannot report. `closure
.topological` *does* detect a cycle --

```python
if len(result) != len(visit_order):
    # Cycle detected - emit remaining nodes by rank to keep output total.
```

-- and then discards the finding, emitting the survivors by rank and telling
nobody. Its callers want a total order, so changing its contract would be the
wrong repair; `_walk_verified_closure` does not even keep its return value.

So `_closure_cycle_groups` recovers the fact from the **edges**, which is where
the plan and the report both already read: an iterative Tarjan SCC over
`dependent -> dependency` arcs, with a size-one component counting only if it
carries a self-loop.

A cycle is genuinely reachable and not a thought experiment, but only at two
hops or more: `walk`'s seed semantics mean a seed never records a parent, so
`A -> B -> A` starting at seed `A` produces no cycle in the edge set. It takes
`seed -> A -> B -> A`. Both endpoints are then planned, so the cause is
`cycle` and not `unsatisfiable` -- neither object is missing; the ORDER is
impossible.

**Cause precedence is `deselected` > `cycle` > `unsatisfiable`.** The user's
own action is the most actionable explanation there is, so it names itself even
when the refused item also sits in a cycle.

Live, the cycle count is **0**: the five registered relationships form a DAG
(11 templates and 18 slots all pointing at 5 shared POSes -- a diamond, 53
edges over 23 refs). So the cycle cause is unit-tested only, and the unit
tests say so rather than implying a measurement they do not have. The
false-positive guard matters more than the positive: a detector that called
that diamond a cycle would report every live narrow transfer as broken.
`test_a_diamond_is_not_a_cycle` is that guard, and `test_the_cycle_walk_does_
not_recurse_on_depth` (3000 chained refs) is why the SCC pass is iterated --
closure depth is data, not a constant.

---

## What surprised me

**The labels were the part I nearly got wrong.** `IncompletenessRecord`
validates `consequence` but not the two labels, and the obvious source for
them -- the plan member's `summary` -- is guid-shaped by convention
(`"POS guid=a8e41fd3..."`). A record whose labels are GUID restatements tells
the reader which GUIDs are involved and nothing about which *items*.

So `_pull_in_label` reuses `references._item_label`, the same best-effort
`Name` reader `DroppedItemRecord.item_name` uses, on the source piece the
pull-in already resolved. That required extracting `_piece_for` out of
`_plan_pulled_in_items` into `_pull_in_piece_resolver` so both readers share
one enumeration cache and one answer about what a ref is *called* -- a second
resolver would enumerate every category twice and could disagree with the
first.

Live result: **63 of 70** labels in the full-deselection case are real source
names. The records read like *`"basic noun"` is missing `"Noun"`*, *`"basic
noun"` is missing `"aug"`*, *`"np"` is missing `"Noun"`*.

The **7 fallbacks are 3 affix templates whose source `Name` is genuinely
empty** -- a fact about the corpus, not a failure of the label reader, which is
precisely why the fallback is the console form of the ref rather than an empty
string. (I did not check whether they are the same 3 templates T070 measured as
never arriving without the pull-in; the T070 artifact does not carry their
GUIDs, and guessing would be worse than saying so.)

---

## What I refused to do

**I did not fix the over-report, and it is real.** 2 of the 5 pulled-in POSes
already exist in the restored destination -- T070 measured them as OVERWRITEs
rather than ADDs. When the user deselects one of those, the dependent's
reference still resolves against the object that is already there, so nothing
is incomplete. **T073 reports 8 of its 35 records anyway.**

It cannot currently tell, and the reason is a *correct* decision one task
upstream: T071 suppresses a deselected ref **before** its planner runs -- which
is what makes "a deselected dependency is not planned" true and what its own
live measurement asserts -- so no `ALREADY_PRESENT_BY_*` skip exists for this
reader to consult. Learning the fact means either running the planner for an
item the user refused (changing T071's measured composition and breaking its
tests) or adding a target-presence probe, and a bare GUID-presence probe is the
Defect G3 shape this feature exists to remove, so it needs its own audit.

Filed as **T093** with the measured evidence, and **pinned as a test asserting
the current defective behaviour** (`test_the_over_report_this_task_
deliberately_did_not_fix`, asserting `8`), on the same principle T087/T089/T090
use: closing it has to be a deliberate edit, not silent drift.

**I did not extend the records beyond the closure.** T070's other loss -- the 3
templates that never arrived because `_resolve_target_pos` returned None and
`_report_owner_pos_unresolved` abandoned them -- is a *drop*, not an
incompleteness; those items do not arrive, so by decision 1 above they belong
to `dropped_items`, where they already are.

**I did not touch `closure.topological`.** Its silent cycle-swallow is real and
is now documented in `_closure_cycle_groups`'s docstring, but its callers want
a total order and T073 does not need it to change.

**I did not fix T090.** The driver reports the lock inventory instead.

---

## Mutation verification -- seven mutations, seven specific failures

| mutation | first test to fail |
|---|---|
| M1 `_plan_incompleteness` returns `()` at once | `test_a_deselected_dependency_makes_its_dependent_report_incomplete` |
| M2 the "is it arriving" gate removed | `test_an_item_that_does_not_arrive_is_not_called_incomplete` |
| M3 already-present no longer satisfies | `test_a_dependency_already_in_the_destination_is_not_an_incompleteness` |
| M4 cycle detection disabled | `test_a_two_item_cycle_is_reported_as_a_cycle` |
| M5 cycle checked before deselection | `test_a_deselection_inside_a_cycle_names_the_deselection` |
| M6 label fallback returns `""` | `test_the_label_helper_reads_the_name_multistring` |
| M7 the plan does not carry the records | `test_the_plan_carries_the_record_for_a_deselected_dependency` |

M2 and M3 are the two worth keeping: they are the two decisions the record
COUNT is made of, and either one silently changes 35 into something else.

---

## Test runs

* `tests/unit`: **3497 passed / 79 skipped / 14 xfailed** (3471 before this
  task; +26, all in the new `tests/unit/test_038_incompleteness.py`).
* `tests/integration` (`--ignore=test_034_standalone_preview_live.py`):
  **402 passed / 75 skipped / 1 pre-existing failure** (393 + 9 new;
  `test_object_census.py::TestCorrectedPremiseNgoremeFlexIsTheSource` --
  `Ngoreme FLEx` has moved, `MoStemMsa` 1952 against a pinned 1949, recorded
  by T069 and unrelated).
* ruff: `preview.py` **79, identical to its pre-change count**; the new unit
  test module clean; `test_038_closure_edge_audit.py` clean; the driver 11
  (percent-format, matching `run038_pull_in_census.py`'s 17 in the same style).

## Artifacts

* `src/gramtrans/Lib/preview.py` -- `_plan_incompleteness`,
  `_closure_cycle_groups`, `_pull_in_piece_resolver`, `_pull_in_label`,
  `_DEPENDENCY_PRESENT_SKIPS`, and `incompleteness=` on the `RunPlan`.
* `tests/unit/test_038_incompleteness.py` -- 26 tests, cycle case included.
* `tests/integration/test_038_closure_edge_audit.py` -- 9 new tests over the
  committed measurement, including the before and the pinned T093 over-report.
* `debug/run038_incompleteness_census.py` -- the driver. Writes nothing.
* `tests/integration/_snapshots/incompleteness-038-t073.json` -- P0..P4 plus
  the label-quality and already-in-the-destination accounting.
