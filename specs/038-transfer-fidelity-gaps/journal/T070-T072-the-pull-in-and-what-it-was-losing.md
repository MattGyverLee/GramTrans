# T070/T071/T072 -- the pull-in, and the three templates nobody knew were missing

**Date**: 2026-08-21
**Tasks**: T070 (mark pulled-in items in the plan), T071 (deselection through
the machinery that already existed), T072 (make each pulled-in item
individually deselectable in the wizard)
**Commits**: worktree `038-transfer-fidelity-gaps`; spec artifacts on `main`

---

## What was owed

Phase 7 Wave 3, all three tasks marked `[P]`. T067-T069 had registered five
closure edges and measured every one of them against two live corpora, and
T069's census asserted -- deliberately, as the thing that made two-hop closure
safe to land ahead of this wave -- that **the pulled-in items were not in the
plan**. Under an AFFIX_TEMPLATES-only selection `plan.closure_edges` carried 53
edges naming 23 distinct pulled-in refs while `plan.actions` held
`{affix_templates: 11}` and nothing else.

So the closure knew exactly which parts of speech and slots the templates
needed, wrote it down in a first-class record, and transferred none of them.
That is FR-014 unmet, and it is this feature's recurring shape for the seventh
time: a signal that exists and is read at a level where it cannot do its job.

---

## 1. What the defect actually cost, measured rather than reasoned about

The plan-shape numbers below are the mechanism. This is the outcome, and it is
the only measurement stated the way a linguist would ask it: **after
transferring templates alone, is what they need actually in the target?**

Two real transfers into the same throwaway target, each restored from
`Target 2026-07-06 0218.fwbackup` first, same source (`Mbugwe LizzieHC
practice`), same AFFIX_TEMPLATES-only selection, differing in nothing but
whether `CLOSURE_EDGES_VERIFIED` was live:

| class | baseline | with the pull-in | without |
|---|---|---|---|
| `PartOfSpeech` | 5 | **8** | 5 |
| `MoInflAffixSlot` | 0 | **19** | **0** |
| `MoInflAffixTemplate` | 0 | **11** | **8** |

**Three of eleven templates never arrived.** Their owning POS was absent from
the destination, `_resolve_target_pos` returned None, and
`_report_owner_pos_unresolved` abandoned the item. The run reported no closure
failure, because the plan had never claimed to transfer a POS -- the loss was
invisible at every surface a user reads. The 19 slots are the cleaner half:
not one of them arrived.

The `without` column is not a deduction from the `with` column; it is a second
restore and a second transfer, because "objects arrived" is satisfied by any
code path that creates them, including one that ignores the registry.

### The 19th slot, named rather than rounded off

18 slots are pulled in by the closure and 19 arrive. The extra one comes from
the ENRICHMENT pass (FR-020..FR-022) on a pulled-in POS, whose `AffixSlotsOC`
is add-only merged -- so it is a slot owned by an enriched POS that no template
references. The arrival column is the union of two mechanisms, not a
restatement of the pull-in count. What isolates T070's own contribution is the
registry-live/registry-empty pair (A) and the deselection pair (B), not the
arrival table.

---

## 2. T070 -- `preview._plan_pulled_in_items`

One new helper in `Lib/preview.py`, called from `build_run_plan` immediately
after `_walk_verified_closure`. It mutates `actions`/`overwrites`/`skips` in
place and returns the edge tuple re-stamped, so the plan and the edge set
cannot disagree about what happened.

**No new surface** (research.md R3). The mark is `pulled_in_by` on the plan
member -- the field `report.build_from_plan` already counts into
`CategoryReport.closure_pulled_in` (report.py:233) and
`Lib/ui/stats_panel.py:149` already renders. Measured end to end: the run
report shows `{gram_categories: 5, slots: 18}`, the same numbers the plan
carries.

**The pull-in routes through the category's own `plan_action`.** Of the 5
POSes, **3 are ADDs and 2 are OVERWRITEs** onto destination objects that
already existed. A pull-in that hand-rolled its own create would have minted
two duplicate `Verb`/`Noun` POSes here -- the create-anyway defect 038 exists
to remove.

**Order is dispatch order, not walk order.** `transfer.execute` walks
`plan.actions` in order (transfer.py:516), so a dependency appended at the end
is created after the item that wires to it -- the same "arrives wired to
nothing" failure one layer down. `_insert_in_dispatch_order` puts each member
before the first member of a later `_LEAF_DISPATCH_CATEGORIES` entry, which
leaves every existing member's relative position untouched. Measured: all 23
pulled-in members at indices 0..20, first template at 21.

**Two pieces of never-silent plumbing.** A ref whose own category cannot
enumerate a source piece for it -- T089's live shape -- becomes a
`DEPENDENCY_UNRESOLVED` skip rather than a quiet omission; so does a
`plan_action` that raises.

**One deliberate difference from `closure_dependencies_for._pieces_for`**: the
piece lookup falls back to enumerating with `selection=None`. A pulled-in item
is by definition one the user did not select, so a category whose
`enumerate_source` narrows to the picks (`pos_enumerate_source`, every
`leaf_picks_for` filter) would hide exactly the piece the closure needs.

---

## 3. T071 -- the deselection machinery was already there, with no reader

`Selection.excluded_deps` + `is_dep_excluded` and `Selection.scope_for`'s
`CategoryScope` mapping both predate this feature. `excluded_deps` had exactly
one consumer in the whole engine (`preview.py:2269`, the verb-vertical POS
check). `SkipReason.DEPENDENCY_DESELECTED` was defined by the Phase 2
foundational work with a docstring naming this precise case -- "an object the
closure walk would have pulled in was deliberately DESELECTED by the user" --
and **had no emitter at all**.

So T071 added no machinery, which is what its task line asked for. It added the
reader: `_pull_in_is_deselected` consults both knobs, and a deselected
dependency is not planned, emits a `DEPENDENCY_DESELECTED` skip naming the
items that needed it, and marks `ClosureEdge.deselected` -- another T066 field
that nothing had ever written, and the one T073 will build its
`IncompletenessRecord`s from.

Measured live, with all 23 pulled-in GUIDs in `excluded_deps`: the plan returns
to **exactly** the registry-emptied composition (`{affix_templates: 11}`), 23
`DEPENDENCY_DESELECTED` skips, and **53 of 53** edges marked deselected.

`include_closure=False` resolves to `CategoryScope.NONE` for every category, so
the back-compatible spelling of "no closure" suppresses the pull-in too. That
matters more than it reads: without it, adding a registry row would have
started pulling items into plans built by callers that had asked for no closure
at all.

---

## 4. T072 -- the checkbox that was wired to nothing

`_PageGramDeps` renders every derived dependency with a checkbox, preselects
it, tells the user in its own subtitle to "Deselect anything you do not want",
and exposes `deselected_dep_guids()` returning exactly what they unchecked.
**Nothing called it.** `_compute_wizard_plan` folds in picks from the
custom-fields, phonology, entry-types, rules, skeleton, stems and texts pages
and never touched this one, so `Selection.excluded_deps` was `frozenset()` on
every plan the wizard has ever built.

Before T070 that was invisible in outcome as well as in code -- the closure
pulled nothing in, so there was almost nothing to exclude. The moment inclusion
becomes the default, "individually deselectable" stops being decoration and
becomes the user's only way to say no.

### The half the task line did not name, and why it is required anyway

The task pointed at `_PageGramDeps`, which owns inflection features, classes
and stem names. But the five registered closure edges land on **POSes, slots
and templates** -- and those live on `_PageSkeleton`. Wiring only the deps page
would have made FR-016 true of the dependencies the closure does not pull in
and false of every one it does.

`_PageSkeleton` had no accessor for this: `deselected_filled_slot_guids()`
answers a narrower question (slots a picked affix FILLS, for an EXCLUDED-LOSSY
warning count) and covers neither POSes nor templates. Added
`deselected_skeleton_guids()` beside it, and `_compute_wizard_plan` step 5h now
unions both pages into `excluded_deps`.

### The tristate trap, found by writing the negative test first

The obvious implementation -- `preselected - collect_skeleton_picks()` -- is
wrong, and the test that caught it is the one asserting an UNTOUCHED tree
deselects nothing. POS rows carry `ItemIsAutoTristate`, so a POS with any
unchecked child sits at `PartiallyChecked`, which `collect_skeleton_picks`
(an `== Checked` test) omits. The fixture's `Verb` owns one never-preselected
slot, so an untouched tree already reported `pos-verb` as REFUSED.

Since T070 a refusal is acted on: the `AFFIX_TO_POS` pull-in would have been
suppressed and the affix would have arrived with no part of speech -- the exact
defect the wizard-POS-wiring fix was written to close, reintroduced through the
opposite door. The accessor now walks the tree for explicitly `Unchecked`
nodes. Both the trap and its positive counterpart are pinned as tests.

This also surfaced a pre-existing quirk worth recording but not fixing here:
`collect_skeleton_picks()["pos_guids"]` omits a partially-checked POS, so step
5e's `pos_picks` has always omitted it too. T070 incidentally repairs the
consequence -- the affix's closure now pulls that POS in regardless.

---

## Mutation verification -- six mutations, six specific failures

| mutation | first test to fail |
|---|---|
| M1 `_plan_pulled_in_items` returns early | `test_a_pulled_in_dependency_becomes_a_plan_member` |
| M2 `pulled_in_by` stamped empty | `test_the_pulled_in_member_names_the_item_that_pulled_it_in` |
| M3 append instead of dispatch-order insert | `test_the_pulled_in_member_is_ordered_before_the_item_that_needs_it` |
| M4 deselection check disabled | `test_a_deselected_dependency_is_not_planned` |
| M5 wizard step 5h disabled | `test_a_deselected_dependency_reaches_the_selection` |
| M6 skeleton accessor derived from the picks | `test_an_untouched_skeleton_deselects_nothing` |

M6 is the one worth keeping: it is not a hypothetical mutant, it is the
implementation that was written first.

---

## What this does NOT do

* **It does not emit `IncompletenessRecord`s.** A deselected dependency
  produces a skip and a `deselected` edge; turning those into the FR-017
  records -- including the cycle case -- is **T073**, and the edge flag is the
  input it will read.
* **It does not link affixes to template columns.** FR-019 / SC-003 is
  **T074**, carried as `RunPlan.msa_slot_bindings`, not as a closure edge.
* **It does not widen the registry.** Five rows, unchanged; the three refusals
  (`MSA_TO_INFL_FEATURE`, `SLOT_TO_TEMPLATE`, `AFFIX_TO_SLOT`) stand for the
  reasons T067-T069 recorded.
* **It changes a full copy by nothing at all.** 0 edges, 0 pulled-in members,
  composition identical with the registry live or emptied -- asserted, because
  the mechanism that completes a narrow selection must not touch the case every
  existing caller uses.

---

## Test runs

* `tests/unit`: **3471 passed / 79 skipped / 14 xfailed / 0 xpassed**
  (3440 before this wave; +31 new). No stale non-strict xfail was found in any
  module touched -- T069 removed the last two.
* `tests/integration` (`--ignore=test_034_standalone_preview_live.py`):
  **393 passed / 75 skipped / 1 pre-existing failure**
  (`test_object_census.py::TestCorrectedPremiseNgoremeFlexIsTheSource` --
  `Ngoreme FLEx` has moved, `MoStemMsa` 1952 against a pinned 1949; recorded by
  T069 and unrelated).
* ruff: `preview.py` 30, `selection_wizard.py` 4, `wizard_pages_skeleton.py` 2,
  `full_run.py` 1 -- **all four identical to their pre-change counts**. New
  files: both test modules clean, the driver 14 (percent-format, matching
  `run038_closure_census.py`'s 35 in the same style).
* **T090 did not reproduce for this driver**: no `.fwdata.lock` was left on
  `Mbugwe LizzieHC practice` or the throwaway target after the run (the four
  locks on disk are the pre-existing ones on `Ejagham Full`, `Ejagham Full
  GT-Test`, `Esperanto` and `Hdi`, untouched by this work).

## Artifacts

* `debug/run038_pull_in_census.py` -- the driver, deliberately NOT folded into
  `run038_closure_census.py`, whose committed
  `plan_composition_unchanged_by_registration` claim this work is what
  invalidates.
* `tests/integration/_snapshots/closure-pull-in-038-t070.json` -- measurements
  A-E, asserted by 10 new tests in
  `tests/integration/test_038_closure_edge_audit.py`.
* `tests/integration/harness/full_run.py` gained a keyword-only
  `selection_transform` hook: the only way to measure a deselection live is to
  build the same plan twice and change nothing but the Selection.
