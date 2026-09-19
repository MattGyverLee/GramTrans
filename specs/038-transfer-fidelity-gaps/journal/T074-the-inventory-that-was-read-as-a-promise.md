# T074 — an inventory of the source, read as a list of promises

**Date**: 2026-08-22
**Task**: T074 (FR-019 / SC-003) — link each transferred affix to the template
column it occupied in the source, or report the failure to link
**Live projects opened**: `Mbugwe LizzieHC practice` (READ-ONLY, digest
`fb6aadabb28a3606` before and after), `Ejagham Mini` (READ-ONLY, digest
`d5bb4d32c0f412cb` before and after), `GT038 Closure Target` (THROWAWAY,
restored from `Target 2026-07-06 0218.fwbackup` before each of six
measurements). `Esperanto`, `Target`, `Ngoreme*` were not opened.

---

## The task line was half right, and the wrong half was the interesting one

T074's recorded baseline is **"0 of 110 linked and 0 reported"**, and T069's
journal handed SC-003 to this task with the note that "no closure edge in this
registry links an affix to a template column". Both readings say the link
itself is missing.

**It is not.** Measured first, before any edit:

| measurement (`Mbugwe LizzieHC practice` -> restored throwaway) | affixes in their source column |
|---|---|
| FULL COPY | **125 of 125** |

The producer is exact too, on both corpora and with no silent loss anywhere in
it — `_populate_msa_slot_bindings` records precisely the MSAs that carry a
column, verified against an independent walk of the same lexicon:

| corpus | `MoInflAffMsa` | with `SlotsRC` | producer recorded | truth − producer | producer − truth |
|---|---|---|---|---|---|
| `Mbugwe LizzieHC practice` | 126 | 125 | 125 | 0 | 0 |
| `Ejagham Mini` | 83 | 79 | 79 | 0 | 0 |

So the *arrival* half of FR-019 was already sound — closed by feature
038-affix-fidelity's selection-independent safety net
(`transfer._ensure_171_subpass`) plus the `IMoInflAffMsa`-cast producer, neither
of which is T074's work. **Saying so is part of the task**: a pass that
re-claimed credit for 125 links it did not make would be reporting a fix that
did not happen, in the same direction as everything else this feature files.

What was broken was the **other** half — the one the baseline records as
"0 reported".

---

## The defect: a claim about the SOURCE, read as a claim about the RUN

`plan.msa_slot_bindings` is built by walking the **whole source lexicon**,
independent of the selection. That is deliberate and must stay: without it, the
safety net could not run the sub-pass on a selection that has no
`AFFIX_TEMPLATES` actions at all, which is the very defect
`_ensure_171_subpass`' docstring was written to fix.

So the binding set is an **inventory of the source**. The consumer,
`_run_171_subpass`, read every entry in it as a **promise this run made**, and
emitted `Skip(DEPENDENCY_UNRESOLVED)` for each one it could not resolve.

Measured, `AFFIX_TEMPLATES`-only, a run that transfers **no affixes at all**:

```
reported link failures : 203
  of them real         :   0
```

203 = 125 from the `SlotsRC` loop + 78 from the `InflFeats` loop
(`_wire_msa_infl_feats`, feature 033's half, same shape and same cause). And
those 203 lines were the run's **entire report** — nothing else in it. Every
one named a source affix the run never touched.

CLAUDE.md already records this exact direction as unshippable: flexicon 4.5.1's
source-aware guard "reports a loss that did not happen", and **3** phantom
losses were enough to keep 4.5.1 out. This was 203, and it was 100% of the
report.

Thirteenth appearance of this feature's recurring shape — something read at a
level where it cannot do its job — and the first where the mis-levelled thing
is an **inventory**: not a value, not a signal, not an assumption, not a
committed artifact, but a *list of what exists*, mistaken for a list of what was
attempted.

### The second, quieter half

`AFFIXES`-only — affixes arrive, the slots they reference do not:

```
linked                 : 73 of 125
reported failures      : 52          (73 + 52 = 125, exactly)
```

The accounting was already **complete** — every unlinked affix had a report. But
each of those 52 skips was keyed by the **absent slot**
(`source_guid=<slot guid>`, `category=AFFIX_TEMPLATES`), so the report named the
thing that was *missing* and never the affix that had *lost* something. FR-019
asks about the affix. A reader could not answer it from the report at all.

And nothing anywhere carried a link **tally**: `report.py` had no field, no
counter and no rendered line, so SC-003 was answerable only from a bespoke
driver and never from the report a user actually gets.

---

## The fix, and the one question that makes it correct

The consumer has to turn a source inventory into a statement about this run. The
question that does it is **"is this affix in the destination at all"** —
asked of the DESTINATION, not of the plan.

That choice matters and is pinned by its own test. `"did this run plan the
affix"` would have been wrong in a way that only shows up under FR-020: an
affix the destination **already held** may legitimately be enriched with a
column it lacked, and a plan-based predicate calls that "not in run" and
suppresses a real link. Asking the target covers both cases and needs no plan.

Four outcomes, one record per source affix MSA that occupied a column
(`AffixSlotLinkOutcome`):

- `LINKED` — it occupies its source column now.
- `SLOT_MISSING` — the affix is here, a column it occupied is not. **Real, and
  uniquely reported by this pass.** A *partial* link counts here, not as
  `LINKED`: an affix in some of its columns has not occupied "the column it
  occupied in the source".
- `MSA_MISSING` — the owning entry is here but its inflectional MSA is not, so
  there is nothing to place in a column. Real, and now reported against the
  **entry**.
- `NOT_IN_RUN` — neither is here. **Recorded, not skipped.**

`NOT_IN_RUN` is the member that makes the other three trustworthy, and it is a
record rather than a `continue` on purpose: a fix that merely dropped the
binding would be indistinguishable, in the report, from a fix that stopped
looking — which is this same failure mode pointing the other way.

The owner map (`RunPlan.msa_owner_entry`) is a new additive field because the
consumer has a target handle and **no source handle**, so the owner cannot be
recovered where the question is asked. It records EVERY MSA, not only the ones
with columns, so the `InflFeats` half can read the same map and so a map keyed
by whatever the *other* producer chose to keep cannot go silently incomplete.

### The sweep: the defect's blast radius is exactly two producers

Both whole-lexicon producers had it, and both are fixed
(`_run_171_subpass` and `_wire_msa_infl_feats`). The third binding dict,
`lexentry_ref_bindings`, is **scoped by construction** and needed nothing:
`_stash_entry_bindings` is called only from `affixes_plan_action`
(`categories.py:9818`) and `stems_plan_action` (`:10343`), i.e. once per
*planned* piece. So "walks the whole lexicon" is the discriminator, there are
exactly two such producers, and both are now read at the right level.

---

## What the numbers did

Same driver (`debug/run038_msa_slot_link_census.py`), same source, same backup,
three selections, before and after. Artifact:
`tests/integration/_snapshots/msa-slot-link-038-t074.json`.

| | linked in target | reported failures | of them real | report carries a tally |
|---|---|---|---|---|
| **A** full copy | 125 -> **125** | 0 -> **0** | 0 -> 0 | none -> **125 records** |
| **B** templates-only | 0 -> **0** | **203 -> 0** | 0 -> 0 | none -> **125 records** |
| **C** affixes-only | 73 -> **73** | 52 -> **52** | — | none -> **125 records** |

The three columns are load-bearing together:

- **B is the fix**: 203 -> 0.
- **A and C prove it removed REPORTS, not LINKS**: the arrival column is
  identical in all three (125 / 0 / 73). A scoping change that had quietly
  stopped wiring slots would move it.
- **C is the negative that carries the whole thing**: the real failures still
  report, all 52, and now every failure row names its affix
  (`entry_guid` populated on 52 of 52) with the unresolved slots a subset of
  what the source claimed. Without C, "scope the skips to the run" is
  indistinguishable from "emit fewer skips".

And the new tally closes SC-003 as an equation rather than a deduction: in C,
`LINKED 73 + SLOT_MISSING 52 == attempted 125`, with `NOT_IN_RUN` stated
**beside** the ratio rather than inside it, so a reader can see the scoping
instead of having to trust it.

B's ratio is deliberately `0 of 0`, not `0 of 125`: a run that transferred no
affixes has no link rate, and reporting one would be the original defect in
percentage form.

---

## Mutation-verified five ways, with one honest negative that became a fix

| mutation | result |
|---|---|
| **M1** scoping predicate returns True on an empty owner | 1 unit FAIL |
| **M2** `NOT_IN_RUN` dropped instead of recorded | **3** unit FAIL |
| **M3** a partial link recorded as `LINKED` | 1 unit FAIL |
| **M4** owner-map producer never called from `build_run_plan` | **0 FAIL — green** |
| **M5** the ratio counts `NOT_IN_RUN` as attempted | **3** FAIL (unit + live) |

**M4 was the finding.** Deleting the producer call left the entire unit suite
green at 3609 passed, because every fake hands the sub-pass a ready-made owner
map — the consumer was covered and its INPUT was not. That is precisely the
duck-typed-fake blind spot T069's journal recorded, and its consequence is
severe in the direction that matters: an owner map that is never populated turns
every REAL failure in FR-019's second half into a silent `NOT_IN_RUN`. The fix
that made this pass a fix rather than a regression-in-waiting is three tests —
a direct producer test, a set-relation test (`set(bindings) <= set(owners)`, so
it keeps holding if either producer's filter changes), and a **structural pin**
grepping `preview.py` for the call, the same instrument T094 used for its
open-coded resolvers, because behavioural coverage provably cannot reach it. All
three re-run mutations now fail: M4b (producer walks nothing) 2 FAIL, M4 (call
deleted) 1 FAIL.

---

## Filed rather than fixed

**Nothing new.** The one thing worth stating explicitly and NOT filing: the
slot-unresolved `Skip.source_guid` still names the **missing slot**, not the
affix. That is correct — the skip is about a slot that is not there — and the
affix is now named in the skip's `detail` and, structurally, in the record's
`entry_guid`, which is the surface a consumer can count. The integration test
says so in its own docstring so a later reader does not "fix" it into
double-counting.

---

## Numbers

- `tests/unit` **3587 -> 3612** passed (+25: 23 new in
  `test_038_affix_slot_links.py`, +2 net from re-pointing three tests), 79
  skipped, 14 xfailed, **0 failed**.
- `tests/integration` (`--ignore=test_034_standalone_preview_live.py`)
  **476 -> 486** passed (+10, exactly the new
  `test_038_affix_slot_links_live.py`), 75 skipped, **0 failed**. The 476
  baseline was re-measured today with this pass stashed — the `480` in T103's
  journal was taken at different project digests.
- The `Windows fatal exception: access violation` dump in
  `FLExInitialize` during the integration run is **pre-existing**: it
  reproduces with this pass stashed, in `test_038_phon_empty_drop_live.py`,
  and does not fail the run.
- ruff **unchanged on every engine file**: `categories.py` 176, `preview.py`
  79, `models.py` 65, `report.py` 5, `transfer.py` 56.
- Three tests re-pointed, none deleted: `test_171_unresolved_msa` (x2, in
  `test_phase3c_post_pass_a.py` and `test_categories_affix_templates.py`) and
  `test_wire_reports_unresolved_msa_rather_than_silently_dropping`. Each
  asserted the unconditional skip that WAS the defect; each now asserts both
  branches, so the narrowing cannot decay into a weakening.

---

## For the next pass

SC-003 is closed on a full copy at 125 of 125 and is now auditable from the run
report. T074's checkbox is flipped. The next actionable task is **T076** (extend
closure to the `PhSimpleContext*` objects a rule's `PhSequenceContext.MembersRS`
references), then **T077**, and only then **T064** — whose `MoAffixProcess` half
is short by exactly 6, the condition-4 rules T076 unblocks.
