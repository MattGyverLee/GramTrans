# T087 -- the explanation the instrument could not read

**Date**: 2026-08-22
**Task**: T087 (US2) -- a loss that IS reported reads as unexplained to the
acceptance instrument
**Worktree**: `GramTrans-038-transfer-fidelity-gaps`, branch
`038-transfer-fidelity-gaps`, `044d644` -> this commit
**Corpus**: `Mbugwe LizzieHC practice` -> `GT038 Phase6 Target`, both opened
READ-ONLY, both byte-identical to the digests the committed artifact recorded

---

## What was wrong

The 6 condition-4 `MoAffixProcess` rules of run `GT-20260821-020541` are
reported **twice**. `Lib/categories.py._reproduce_affix_process._skip(reason)`
writes the same `reason` string to a `DroppedItemRecord`
(`item_name="MoAffixProcess"`, `item_guid=<rule guid>`) *and* to a
`ProcessRuleTransferRecord` (`reproduced=False`,
`not_reproducible_reason=<same string>`), and `RunReport.rules_not_reproduced`
surfaces the second. So the loss was never silent: Principle I was satisfied
before this task started.

What the census could not do was **read** either surface. `read_report_evidence`
consumed `dropped_items` only, through `drop_reason_token`, and none of
`DROP_REASON_TOKENS`' three needles occurs in any reason
`_reproduce_affix_process` produces. Measured against the committed report:

| needle | matches in the 6 reasons |
|---|---|
| `is not reproducible by this engine` | 0 |
| `not resolvable in target` | 0 |
| `is empty on source` | 0 |

So the row scored `unexplained_shortfall: 6` with an empty `accounted_for`.

**The direction is the point.** T038's defect (piece 2 of the same unit-test
file) inflated a real loss into an unexplained one. This one inflates a
**named, deliberate deferral** into an unaccounted loss -- the direction 5.2's
cap rationale says an instrument must not be wrong in, and the direction
CLAUDE.md records as what made flexicon 4.5.1 unshippable ("reports a loss that
did not happen"). A report that cries loss where the loss was announced teaches
the reader to stop reading it.

## Measurement

Both projects were **byte-identical for the two runs**, so the pair measures the
instrument and nothing else:

| | recorded in the committed artifact | on disk 2026-08-22 |
|---|---|---|
| `Mbugwe LizzieHC practice.fwdata` | `fb6aadab...c3161` | `fb6aadab...c3161` |
| `GT038 Phase6 Target.fwdata` | `3753d416...af480` | `3753d416...af480` |

No transfer was re-run, no project was restored, nothing was written
(`opened_read_only: true`, `fwdata_sha256_before == _after` on both sides of the
new artifact). Only the `run` subcommand was re-executed, with the same
arguments `debug/run038_phase6_live.py` passes.

**Exactly 3 rows moved**, and one of them is this task's:

| row | before | after | whose fix |
|---|---|---|---|
| `MoAffixProcess` | `unexplained_shortfall: 6`, `accounted_for: []` | `unexplained_shortfall: 0`, one line claiming 6 | **T087** |
| `MoForm` | `0/0` counts | `null` counts | T099, which landed after the artifact was committed |
| `MoMorphSynAnalysis` | `0/0` counts | `null` counts | T099 |

Totals: `accounted_shortfall` **0 -> 6**, `unexplained_shortfall`
**9403 -> 9397**. Every counted quantity on every other row is unchanged, and
`verdict` / `exit_code` stay `DUPLICATE_IDENTITY` / 3 -- the `PhNCFeatures`
duplicate finding T064 already pinned as a source property. 0 schema errors, 0
section-11 invariant failures, empty `errors[]`.

A fourth corroborating move, unasserted but worth recording: 5.2's advisory
suppression note listed **23** baseline-gross rows before and **22** after.
`MoAffixProcess` left that list because it no longer has an unexplained tally to
suppress -- it moved from *advisory* to genuinely *accounted*, which is a
stronger position, not the same one relabelled.

## The line is required to carry its evidence

T087's text asks that "an `accounted_for` entry has to carry the report
reference (the rule GUID and its reason), so a shortfall is only ever explained
by evidence that actually exists". The emitted line:

```
reason:  DEPENDENCY_UNRESOLVED          count: 6      direction: shortfall
ref:     kind=dropped_item  count_in_report=6  run_id=GT-20260821-020541
         record_ids=[all 6 rule GUIDs]   report_path=<the committed report>
detail:  reproduced=False on 6 ProcessRuleTransferRecord(s), each corroborated
         by a DroppedItemRecord carrying the SAME reason verbatim on run
         GT-20260821-020541; classified from 'is absent from the destination'
         -- see report_ref.record_ids for the rule GUIDs and the report for
         each full reason
```

`accounted_for_drops`' default detail names only the `DroppedItemRecord`, which
is **half** of what this line rests on, so the drop tuple grew an optional third
element that overrides it. The cap suffix is appended to the override rather
than replacing it, so an over-claimed line still says it was capped
(`test_over_accounting_is_still_capped`).

## Four decisions, and why each is the narrow one

1. **Corroboration is REQUIRED, not assumed.** A `reproduced=False` record is
   credited only when `dropped_items` also carries a `DroppedItemRecord` with
   the same `item_guid` **and the same `reason` verbatim**. Two independent
   surfaces of one report agreeing is stronger than either alone, and it means a
   future producer bug -- one surface written without the other, or a reason
   that drifted between them -- reads as UNCLASSIFIABLE rather than being
   silently trusted. Live ratio: **6/6**.
2. **The two needle tables do NOT merge.** Folding
   `is absent from the destination` into `DROP_REASON_TOKENS` would let
   `dropped_by_class_from_report` classify the same drop a second time on its
   own uncorroborated path, and the merge would credit one lost rule as two
   accounted objects -- the over-accounting R-2 forbids. Disjointness is now
   asserted in both directions (`TestTheTwoTablesDoNotMerge`) rather than
   asserted in a comment.
3. **No 18th token, and no 7th `reportRef.kind`.** `DEPENDENCY_UNRESOLVED`
   (FR-017, destination-side absence) is the exact existing member for "a
   reference the rule cannot own resolves to nothing in the target", and
   `dropped_item` is a truthful `kind` because the corroborating
   `DroppedItemRecord` is what the credit requires. Both vocabularies are
   CLOSED contracts; T100 is the open filing about what it costs to add to one.
4. **The pre-fix artifact is KEPT, not overwritten** -- see the finding below.

## The finding this raised: T102

`census-038-mbugwe-phase6.json` could not simply be replaced.
`test_038_closure_edge_audit.py` asserts its class table **equal** to
`census-038-t067-registered.json`, `-t068-` and `-t069-`, row by row including
`unexplained_shortfall`, plus `totals` equality -- four artifacts from four
separately restored targets, compared against each other to prove that
registering a closure edge moved no object count. Overwriting one link would
turn three passing tests red for a reason that has nothing to do with what they
assert, and that file's own docstring names the hazard: *"a chain of pairwise
comparisons can drift if one link is ever re-measured and the others are not."*

So the new reading landed beside the old one as
`census-038-t087-mbugwe.json`, and
`test_the_pre_fix_artifact_is_kept_and_differs_only_by_the_instrument` makes the
pair defensible: identical digests, identical counted fields on all 72 other
rows, and the accounting delta required to be confined to `MoAffixProcess`.

But the chain is now measurably behind the instrument, and that is **T102**.
Eleventh appearance of this feature's recurring shape, and the first where the
thing read at the wrong level is a *committed artifact* rather than a value, a
signal or an assumption: four files read as current evidence while no current
instrument would produce any of them, and nothing compares them to one.

## Suites

| suite | after T098 | after T087 |
|---|---|---|
| `tests/unit` | 3568 passed, 79 skipped, 14 xfailed | **3587 passed, 79 skipped, 14 xfailed** |
| `tests/integration` | 432 passed, 0 failed, 76 skipped | **434 passed, 0 failed, 76 skipped** |

Run separately: `pytest tests/unit tests/integration` in one invocation still
fails collection on the pre-existing `test_038_process_rules.py` basename
collision.

**Recorded, not caused by this change**: `tests/integration` prints a
`Windows fatal exception: access violation` faulthandler dump from
`flexicon/code/FLExInit.py:64` (`FLExInitialize`) during
`test_034_standalone_preview_live.py`'s `flex` fixture. The dump is non-fatal --
that file reports 4 passed on its own -- and nothing in this change is reachable
from it. Noted because a native access violation printed by a suite that reports
green is the shape this feature keeps filing.

## What T087 did NOT do

**P4 is still not satisfied, and this task was never going to satisfy it.** The
predicate is `MoAffixProcess` **MATCHED**, and the row is still `SHORTFALL` at
`-6`: the 6 rules really are missing, and T076/T077 are what transfer them.
Gating the new artifact at `--phase 4` still fails on
`P4: MoAffixProcess is SHORTFALL (difference -6), not MATCHED`, and still exits
3 on `PhNCFeatures`.

What changed is one line of the section-6 report: **24 classes** failed section
6 before, **23** after, because an accounted shortfall is no longer an
unexplained one. Accounting says the loss was *named*, not that it did not
happen.
