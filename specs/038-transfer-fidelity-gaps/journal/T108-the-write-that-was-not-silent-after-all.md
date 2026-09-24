# T108 — the write that was not silent after all

**Closed** 2026-08-25. Filed by T107, which found the defect and fixed it one
run too late to use the fix.

## What T108 asked

T076 added `ProcessContextSpec.co_created_shared` so that a write into the
shared, project-level `PhPhonData.ContextsOS` — made as a side effect of
transferring a lexical entry — would not be a **silent** write (SC-010). It
asserted the field on the **in-memory record only**. `report._process_rule_json`
emitted `context_class` / `index` / `referent_guid` / `label` and dropped it, so
from T076 until T107 the claim was true of the object and **false of the
artifact anybody reads**.

T107 found this the hard way: its live Ejagham run could not say whether the
destination's one `PhPhonData`-owned `PhSimpleContextBdry` was co-created by the
affix-process leg (`categories._create_shared_process_context`) or brought
across by the phonological-rule path (`_copy_context_cell`), because **both
write that collection** and the only field that distinguishes them was dropped
on the way out. T107 fixed the serializer — and its own committed run predates
the fix. So it recorded `shared_context_attribution: "NOT DETERMINABLE FROM
THIS RUN…"` rather than leaving a silence to be read as success, and filed
T108: one more run, on the fixed serializer.

## The trap, and the guard that now sits on it

T108's own task text carried the warning: **it must not re-transfer `GT038
Ejagham After`.** T107's census artifacts are asserted to hash to that project
as it stands (`TestT107TheBoundaryContextCreatePath::
test_these_artifacts_are_the_ones_that_now_reproduce`), so a re-run into the
same target would drift T107's evidence off its recorded digests — the exact
T102 failure T107 already had to edit T078's table for, one link further on
again.

So `debug/run038_before_after_pairs.py` gained three things rather than an
edited target name:

- an **`ejagham-t108` pair** — same source, `GT038 T108 Target` as destination,
  restored from `backups/Target 2026-07-06 0218.fwbackup`. Added *beside*
  `ejagham` so the pair that produced the committed before/after diff stays
  runnable;
- **`--no-census`**, which stops after the transfer. T108's question lives
  entirely in the run report, and a census would have answered a question
  nobody asked while adding a second artifact to keep current — and would have
  had to be diffed against a `before` taken on a different destination;
- **`_EVIDENCE_TARGETS`**, which **refuses** a `--no-census` run into a target
  whose `.fwdata` digest a committed census records. Re-transferring one does
  not corrupt anything; it silently turns a committed measurement into a
  description of a project that no longer exists, and that damage is invisible
  until an unrelated test goes red. Verified by running the refusal:

  ```
  [FAIL] refusing to re-transfer 'GT038 Ejagham After': a committed census
         records its .fwdata digest and a test asserts the file still hashes
         to it. Add a pair with its own throwaway target instead.
  ```

## The answer, and it was not the only possible one

`Ejagham W Mini` → `GT038 T108 Target`, run `GT-20260825-151533`, one restored
target, no census taken and **no committed census touched**.

The field could have come back **empty on all 13 rules** — meaning the
phonological-rule path got there first. That would have been an answer too, and
the deriver writes it up as one rather than as a failure. It did not.

| | |
| --- | --- |
| shared `PhPhonData.ContextsOS` members co-created | **13**, on 4 of 13 rules |
| by class | 1 `PhSimpleContextBdry`, 7 `PhSimpleContextNC`, 5 `PhSimpleContextSeg` |
| owner in the source | `PhPhonData` — **all 13** |

**The boundary context is among them.** `391e8cba-b951-4f1b-a64a-c5dc5fbe19c9`,
`PhPhonData`-owned in the source, created by rule
`de6df83e-3556-42f8-82fc-30d22d4a68b9`. So the destination's one
`PhPhonData`-owned `PhSimpleContextBdry` came from the **affix-process
co-create leg**, not from the phonological-rule path. The ambiguity T107
recorded is resolved by measurement rather than by argument.

**Five rules reach that context, exactly one reports creating it.** The five —
reproducing T107's read-only count from the source graph, object for object —
are `19bab2cf`, `24ed706a`, `3dba60c1`, `9d57bc7c`, `de6df83e`. Only `de6df83e`
reports the co-creation, because `_resolve_process_graph` consults
`member_targets` before the co-create leg: the second rule to reach a shared
member finds what the first one made. One of the other four is `24ed706a`, the
source-defect rule, which never gets as far as its input members.

**So 13 is a count of objects CREATED, never of rules that use them**, and the
test says so in its name. A reader who took it for a rule count would conclude
the leg runs four times more often than it does.

## What the run also proves, which nobody asked it to

T107's per-rule figures were taken **once, into one project**. If any of them
depended on that project's starting state rather than on the source and the
engine, this run — a different target, restored from the same backup — would
have said so. It does not:

- 13 rules, **12 reproduced**, the same single refusal (`24ed706a`) for the
  same reason, naming `MoCopyFromInput` and not `PhSimpleContextBdry`;
- the same **8** direct `PhSimpleContextBdry` input members, on the same 8
  rules, all wired to the same word-boundary marker;
- `input_context_class_totals` **identical** row for row.

That is T107's acceptance reproduced on an independent target, for free.

## Why the deriver reads the source `.fwdata`

The run report names co-created members **by GUID and nothing else**, and "13
shared members were created" does not answer the question T108 was filed for,
which is about **one object**. `debug/derive038_t108_shared_context.py`
therefore does a read-only walk of `Ejagham W Mini.fwdata` to resolve each
co-created GUID's class and owner, and — for a boundary context — every
`MoAffixProcess` that reaches it through a rule-owned `PhSequenceContext`.

Putting that **in the artifact** rather than in a hand-typed test table is the
point: T107's residual-owner table is prose-backed and can drift away from the
measurement it explains; this one cannot, because the assertion and the
measurement are the same file. The deriver also **refuses** a report with a
single `input_contexts` entry missing the key — a report that predates the
serializer fix, or one produced after a regression, must not be written up as
if it had answered anything. That silence is the whole defect T108 exists to
end.

## Landed

- `debug/run038_before_after_pairs.py` — `ejagham-t108` pair, `--no-census`,
  `_EVIDENCE_TARGETS` refusal.
- `debug/derive038_t108_shared_context.py` — **new**, read-only, committed so
  the artifact is reproducible rather than hand-made.
- `tests/integration/_snapshots/process-rules-038-t108-ejagham.json` — **new**.
- `tests/integration/_snapshots/process-rules-038-t107-ejagham.json` —
  `shared_context_attribution` replaced. It now carries the measurement, names
  the run that made it (which is **not** the run that artifact describes), and
  points at T108's artifact.
- `tests/integration/test_object_census.py` —
  `TestT107…::test_the_shared_route_attribution_is_recorded_as_undetermined`
  **deleted**, which is what it existed for; `TestT108TheSharedRouteAttribution`
  added (9 tests). The serializer round-trip through the real
  `_process_rule_json` that the deleted test carried moved into
  `test_the_field_reached_every_reported_context` rather than being dropped.

`tests/unit` 3731 passed / 79 skipped / 14 xfailed; `tests/integration` 607
passed / 0 failed / 75 skipped.

## The one thing this run does not settle

`GT038 T108 Target` is now a live project holding a full Ejagham transfer, and
**no census was taken of it**. That is deliberate — the question was answered
by the run report — but it means the target is a run artifact, not evidence,
and nothing asserts its digest. If a later task wants a census of this pair, it
should take its own; re-censusing this project later would be measuring a
project whose provenance is only this journal entry.
