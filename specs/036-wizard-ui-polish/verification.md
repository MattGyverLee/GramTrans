# T047 — Live verification

**Feature**: 036-wizard-ui-polish
**Date**: 2026-08-18
**Constitution gate**: Principle III live-verification requirement
**Covers**: SC-001, SC-001a, SC-001b, SC-002, SC-011 (FR-045)

## What was run, and against what

Three live FieldWorks projects, all opened **read-only** through FLExToolsMCP
2.9.1 (flexicon 4.4.0, liblcm 11.0.0, FieldWorks 9):

| Project | Lexical entries | Texts | Custom fields | Phonology | Entry types | Ad-hoc rules |
|---|---|---|---|---|---|---|
| `Ejagham Mini` | 252 | 9 | 2 | 6 | 12 | 0 |
| `Ejagham Full` | 4304 | 8 | 11 | 6 | 14 | 0 |
| `Ejagham Full GT-Test` | 0 | 0 | 0 | 3 | 12 | 0 |

`Ejagham Full GT-Test` is the transfer **target** and is currently empty — it has
been reset for exactly this pairing. It is therefore useless as a timing source,
which is why `Ejagham Full` (the same data, unreset) carries the calibration.

Every operation was run **twice**: once with `progress=None` and once with a
counting sink, so the FR-045 equality is a comparison of two real results rather
than an inspection of a code path. Ops `op-083238142-001` .. `op-083605073-005`
in `~/.flextoolsmcp/logs/operations.jsonl`. All five runs are certified
read-only by the MCP write-certification gate (`mutating_calls_detected: []`).

## SC-011 / FR-045 — the transferred objects are unchanged: **PASS**

Two independent lines of evidence.

**1. The inventories are identical with and without a sink.** All nine
source-reading operations, on all three projects, produced byte-identical
results between the `progress=None` run and the sink run:

| Operation | Mini | Full | GT-Test |
|---|---|---|---|
| affixes, stems, skeleton, dependencies | identical | identical | identical |
| phonology, rules, entry_types, texts | identical | identical | identical |
| custom_fields | identical | identical | identical |

> Note on method: the first pass compared `repr()` and reported custom fields as
> differing. That was an artefact — `_CustomFieldRecord` uses `__slots__` and
> defines no `__repr__`, so the default repr is an object address and two runs
> can never match. Re-run comparing the record's actual attributes (`guid`,
> `owner_class`, `name`, `field_id`, `field_type`, `list_root_guid`): identical.
> Recorded because a reader who finds only the corrected result should know the
> first one existed and why it was wrong.

**2. The write path cannot see progress at all.** `Lib/transfer.py` and
`Lib/preview.py` contain zero references to `progress` (the single hit in
`Lib/api.py` is the phrase "in-progress" in a comment). The only call sites that
pass a sink are the eight inventory builders in `Lib/ui/selection_wizard.py`,
all of them presentation-layer reads. So the objects transferred and their
content are unchanged **by construction**, not merely by measurement.

## SC-002 — the window never stops repainting: **PASS**

A `QtProgressSink` pumps the event loop on tick, so the longest stretch between
ticks is the longest stretch in which the window cannot repaint. Windows marks a
window unresponsive at roughly 5 s. Longest gap observed, on the 4304-entry
project:

| Operation | Longest gap between ticks |
|---|---|
| stems | 74.4 ms |
| dependencies | 66.5 ms |
| affixes | 64.3 ms |
| skeleton | 10.4 ms |
| everything else | < 1 ms |

Two orders of magnitude inside the limit.

**Caveat, not covered by this measurement:** FR-023 rows 12 and 13 (dry-run plan
assembly and the execute-move write) are single engine calls that take no sink,
so nothing pumps the loop inside them. They are the only places SC-002 could
still fail, and neither was exercised here — see "Not covered" below.

## SC-001 — no wait past 500 ms without an indicator: **PASS**

One operation crossed the threshold in the whole run: `stems` on `Ejagham Full`,
at 497.7 ms (`progress=None`) / 555.3 ms (with sink). It is covered — after
recalibration its predicted cost is 478 ms, which is below the bar, so the
elapsed-time fallback is what shows it, exactly as FR-014b intends. Nothing else
came within 250 ms of the threshold.

## SC-001a — nothing appears for work under the threshold: **FAILED, then FIXED (T048)**

This is what the run was for. With the placeholder rates, three operations would
have thrown up a **modal indicator before work that finishes in a fifth of a
second** — the flash FR-019 exists to forbid:

| Operation | Placeholder predicted | Actually took | Verdict |
|---|---|---|---|
| affixes | 4782 ms | 73 ms | FLASH |
| skeleton | 8608 ms | 193 ms | FLASH |
| dependencies | 12297 ms | 245 ms | FLASH |

T048 replaced every measurable rate with the measured one. Re-checked against
the same wall-clock figures:

| Operation | Total | Actual | Predicted (after T048) | Up-front? | Actually slow? |
|---|---|---|---|---|---|
| affixes | 4304 | 72.7 ms | 86.1 ms | no | no |
| stems | 4304 | 497.7 ms | 478.2 ms | no | no |
| skeleton | 4304 | 193.1 ms | 215.2 ms | no | no |
| dependencies | 4304 | 244.7 ms | 226.5 ms | no | no |
| phonology | 6 | 188.0 ms | 2.4 ms | no | no |
| rules | 0 | 3.5 ms | 0.0 ms | no | no |
| entry_types | 14 | 4.3 ms | 3.1 ms | no | no |
| texts | 8 | 8.0 ms | 8.0 ms | no | no |
| custom_fields | 11 | 2.4 ms | 2.4 ms | no | no |

**0 mispredictions out of 9, down from 3.** Every prediction now lands within
about 30 ms of the measured time.

## SC-001b — the indicator's total matches the work performed: **FAILS on 4 of 9**

The up-front/elapsed decision is now right, but the **bar itself** is wrong on
four operations. The declared total and the number of ticks the walk actually
emits do not agree:

| Operation | Declared total | Ticks emitted | Ratio | What the operator sees |
|---|---|---|---|---|
| **affixes** | 4304 | 20 | **0.005x** | bar reaches 0.5% and vanishes |
| **skeleton** | 4304 | 12912 | **3.00x** | bar fills, then degrades to indeterminate at 33% |
| **phonology** | 6 | 38 | **6.33x** | same, at 16% |
| **entry_types** | 14 | 16 | **1.14x** | same, at 88% |
| stems | 4304 | 4284 | 1.00x | correct |
| dependencies | 4304 | 4304 | 1.00x | correct |
| texts | 8 | 8 | 1.00x | correct |
| custom_fields | 11 | 11 | 1.00x | correct |
| rules | 0 | 0 | — | n/a (no ad-hoc rules in any Ejagham project) |

Confirmed on both `Ejagham Mini` and `Ejagham Full`, and phonology's overrun
reproduces on `GT-Test` too (8.33x there), so none of these is a property of one
project's data.

Two distinct causes:

- **affixes / stems** tick once per entry in their own partition, but take
  `LexiconNumberOfEntries()` as the total. On `Ejagham Full` only 20 of 4304
  entries are affixes, so the affix bar is effectively a no-op. Stems happen to
  agree only because that project is almost all stems (4284 of 4304) — the same
  bug, hidden by the data.
- **skeleton / phonology / entry_types** tick at a finer granularity than the
  cheap total counts: the skeleton walk emits three ticks per entry, and
  phonology counts possibility *lists* while ticking their *members*.

This is a presentation defect only — it cannot affect what is transferred
(SC-011 above), and `QtProgressSink` degrades an overrun to indeterminate rather
than displaying over 100%. It is recorded here rather than fixed because the fix
requires a spec-level choice between changing the declared unit (data-model §3)
and changing the tick placement in `Lib/selection.py`, which is on the transfer
path and therefore governed by FR-045. **Recommend a follow-up task.**

## Not covered by this run

| Gap | Why | Consequence |
|---|---|---|
| FR-023 rows 12 (plan assembly) and 13 (execute-move write) | Both need a bound source/target pair; row 13 is a live write to a real project, not run unattended | Their `units_per_second` stay documented placeholders; SC-002 unproven for the two operations most likely to breach it |
| `rules` calibration | All three Ejagham projects have zero ad-hoc prohibitions | Placeholder stands, labelled as one |
| `texts` calibration | Eight to nine short texts is far too small a sample for a walk whose per-unit cost is paragraphs x segments x wordforms | Deliberately set to the slowest observation (1000/s); documented as the least trustworthy value in the table |
| An end-to-end Move | Not run — see above | SC-011 rests on the two lines of evidence above, which do not require it |

## Verdict

| Criterion | Result |
|---|---|
| SC-001 | PASS |
| SC-001a | FAILED as found, FIXED by T048, re-verified |
| SC-001b | **FAIL on 4 of 9 operations** — follow-up required |
| SC-002 | PASS for the nine measured operations; unproven for rows 12-13 |
| SC-011 / FR-045 | PASS, on two independent lines of evidence |
