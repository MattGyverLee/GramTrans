# T080 — the invariant that covered two of four, and the fifth outcome that was real

**Closed** 2026-08-25. **No successor filed** — the two gaps are closed, the
fifth outcome is measured on every run from here, and the classification table
fails on its own the next time someone adds a bucket.

## What T080 asked

> Audit SC-010 end to end: every selected item reaches exactly one of ADD,
> UPDATE (enriched), SKIP, or dropped-with-reason, and each appears in the
> post-run statistics panel — **there is no fifth, unreported outcome**
> (data-model.md:232-235). Assert the extended `RunReport.__post_init__`
> accounting invariant covers all four buckets.

The last sentence contains an assumption, and the audit's first job was to
check it rather than to assert it.

## Measured first: the invariant covered TWO of the four

Probed against the worktree at `ad443fd`, before T080 changed anything:

| bucket | counter | records tuple | invariant |
| --- | --- | --- | --- |
| ADD | `per_category[*].added` | *(none on the report)* | **NONE** |
| UPDATE (enriched) | `per_category[*].enriched` | `enrichments` | equality |
| SKIP | `per_category[*].skipped` | `skips` | equality (FR-018) |
| dropped-with-reason | *(none)* | `dropped_items` | **NONE** |

The two covered buckets are covered for one reason: each counter has a records
tuple **on the report** that is its single source of truth, so the check is
`counter == len(records)`. The two uncovered buckets are uncovered for
*opposite* structural reasons, and neither is fixed by copying that check
across:

* **ADD has a counter and no records.** `added` is one per `PlannedAction`, and
  the plan is not carried on the `RunReport`. There is nothing to count
  against. Measured: `CategoryReport(added=-5)` constructed a report whose
  disposition panel rendered `-5`.
* **dropped-with-reason has records and no counter.** It is
  `len(dropped_items)` and nothing else. `DroppedItemRecord.__post_init__`
  refuses an empty `reason` — but that guards the RECORD's construction, not
  the TUPLE's membership. Measured: a stand-in carrying `reason=""` went into
  `dropped_items`, was counted in `dropped_with_reason`, and rendered a report
  line ending in a bare `- `.

Each bucket now has the invariant its shape actually admits, both in
`RunReport.__post_init__`:

* ADD → a **range** check. `CATEGORY_REPORT_COUNTERS` names every int field of
  `CategoryReport`, and every one must be a non-negative int.
* dropped-with-reason → a **membership** check. Every entry must carry a
  reason, tested where the bucket is COUNTED rather than only where the record
  is built — the bucket is named *dropped-WITH-REASON*.

**The range check is needed on the reconciling buckets too**, which is why it
is not ADD-only: the equality checks constrain the **sum**, and
`{A: skipped=-3, B: skipped=4}` against one `Skip` sums to 1 and passes.

**And it runs FIRST**, ahead of both equality checks. `enriched=-1` trips the
equality check too, and that check reports `sum(...)=-1 != len(...)=0` —
arithmetic over a nonsense value, naming the tuple instead of the counter that
is actually wrong. The more fundamental fact speaks first.

## The fifth outcome was real, in its exact literal form

`ProcessRuleTransferRecord`'s docstring states a HARD INVARIANT: a rule with
`reproduced=False` "is reported — via a `DroppedItemRecord` plus
`Skip(NOT_REPRODUCIBLE)` — and SKIPPED". Its own `__post_init__` enforces the
half it can see (the reason must be non-empty). **Nothing enforced the other
half**, which is the half SC-010 is about.

A report carrying a rule the engine *knew* it had not rebuilt, named by no Skip
and no dropped record, is an item that reached none of the four buckets. It
constructed silently, rendered a clean panel, and produced an artifact whose
`disposition.note` said "there is no fifth, unreported outcome" as an
unconditional promise.

That is now `RunReport.unreported_not_reproduced`. A rule counts as reported
when its GUID appears as a `Skip.source_guid` **or** as a `DroppedItemRecord`'s
`item_guid` **or** `owner_guid` — all three, because both producers in
`Lib/categories.py` report a dropped rule against its **owning entry**
(`owner_kind="LexEntry"`, `item_name="MoAffixProcess"`, `item_guid=<rule>`, per
the create-path contract section 5), while a rule that OWNS the thing lost is
reported with itself as `owner_guid`. Insisting on any one field would report
phantom fifth outcomes on correct runs. Matching is case-insensitive for the
same reason: LCM hands GUIDs back in mixed case.

**IT DOES NOT FIRE ON THE REAL PATH, and that was checked before it landed.**
All three `ProcessRuleTransferRecord` producers in `src/` were read
(`categories.py:6271`, `:8594`, `:8709`); both non-reproduction sites emit the
`DroppedItemRecord` with `item_guid=rule_guid` on the line **before** the
record. The linkage holds by construction, which is what makes this a tripwire
rather than a new failure — it agrees with T078's live finding that Ejagham's
13 unreproduced rules "are dropped WITH a reason naming the class".

## Why it is a PROPERTY and not a `__post_init__` raise

The one design decision here worth stating, and it is pinned by a test so a
later reading does not "complete" the audit by hardening it.

Every invariant in `__post_init__` rejects a report that **contradicts
itself** — a counter disagreeing with the records that define it, where no
reading of the report is safe. This one describes a report that is merely
**incomplete**. Raising on it would destroy, at build time, the very report
carrying the evidence of the loss: answering "what did this run silently
discard?" by discarding the answer. That is the SC-010 anti-pattern in
miniature.

T048c already set the precedent in the same direction — when the create split
had no valid basis it **withheld the number and said so** rather than refusing
to build. An incomplete report that names its own gap beats no report. That
withhold path is itself pinned here (`TestTheDeliberateNonInvariants`), because
`add_write_failed > add_created` looks exactly like a missing invariant and a
raise there would make the disagreement unreportable.

## Two prose promises became measurements

The check reaches both surfaces, unconditionally and in both directions:
`Fifth-outcome check: PASS` / `[FAIL]` on the console (with the GUIDs listed),
and `no_fifth_outcome` / `unreported_not_reproduced` /
`unreported_not_reproduced_guids` in the artifact, derived from **one**
`disposition_totals` call so the two cannot disagree.

Which made two existing sentences false-by-construction on a `[FAIL]` run, so
both were edited rather than left standing:

* the artifact's `disposition.note` asserted "there is no fifth, unreported
  outcome" — it now says whether THIS run met it is the `no_fifth_outcome` key,
  not the sentence;
* the console panel's heading did the same, and now defers to the check below
  it.

## The classification table is the audit's actual substance

"There is no fifth outcome" is only checkable if the set of things that COULD
be one is enumerated. `tests/integration/test_038_no_silent_skips.py` names
every one of `CategoryReport`'s **13** counters and every one of `RunReport`'s
**19** fields with the role it plays — bucket, annotation, provenance, or
not-an-item — and fails when a new field appears unclassified. That is the
moment a fifth outcome would enter, and the only cheap moment to catch it.

Three classifications are worth writing down because they look like fifth
outcomes and are not:

* **`excluded_lossy`** — the ENTRY still transfers, with a null reference and a
  warning. The thing omitted is a **deselected dependency**, which was never a
  selected item.
* **`leaf_execution_failures`** — an ADD that was planned and did not reach the
  database. It refines the ADD bucket's outcome (`add_created_written`); it
  does not sit outside the four.
* **`closure_pulled_in` / `closure_edges`** — how an item ENTERED the run, not
  what became of it. Counting a pulled-in item as an outcome would
  double-count it.

`CATEGORY_REPORT_COUNTERS` is pinned to the dataclass by reflection rather than
maintained beside it, so a counter added without being range-checked fails too.

## Why an integration test with no live project

This is an audit of the contract between **three modules** —
`Lib/models.py`'s invariants, `Lib/report.py`'s `disposition_totals`, and the
console panel — and its whole point is that the three agree. A unit test of any
one of them is what allowed both gaps to sit open while every module's own
suite passed. No project is opened and nothing is written.

## Numbers

`tests/unit` **3731 passed** / 79 skipped / 14 xfailed — unmoved from T108's
baseline, as it must be: nothing T080 touches can change a count.
`tests/integration` 607 → **641 passed** / 0 failed / 75 skipped, the +34 being
this file exactly.

Pre-existing and not T080's: `pytest tests/unit tests/integration` in ONE
invocation still errors on a basename collision between
`tests/unit/test_038_process_rules.py` and its integration namesake, and
`test_034_standalone_preview_live.py` still prints a `FLExInitialize` access
violation from `faulthandler` while skipping. Both reproduce at `ad443fd`.

Files: `src/gramtrans/Lib/models.py`, `src/gramtrans/Lib/report.py`,
`tests/integration/test_038_no_silent_skips.py` (new).
