# T102 -- the chain that was measured only against itself

**Date:** 2026-08-24
**Task:** T102 (US2)
**Branch commit:** `09cf87b` on `038-transfer-fidelity-gaps`
**Evidence:** the four census artifacts' own recorded `fwdata_sha256_after`
against the files on disk, and the three paired registration artifacts'
`registered` lists against the live `CLOSURE_EDGES_VERIFIED`. **No FLEx host
was needed and no project was opened** -- which is the point.

---

## The one-line version

T102 said the decision needed three live re-runs' evidence. It needed four
digests and three lists, and they force the decision: the chain cannot be
repaired by re-measuring, because none of the three inputs it pins still
exists in the state it pins.

## What the chain claimed, and what it was measured against

`census-038-mbugwe-phase6` -> `-t067-` -> `-t068-` -> `-t069-`, each compared
with the one before it and the last also with the first, to prove that
**registering a closure edge moved no object count.** That claim is sound and
the chain is internally consistent. The defect is what the consistency is
measured against: four artifacts asserted equal to **each other** and to no
instrument, over a projection (`_census_table`) that included
`unexplained_shortfall` and `verdict_class` -- the census's *reading* of the
counts, not the counts.

The file's own docstring named the hazard: *"a chain of pairwise comparisons
can drift if one link is ever re-measured and the others are not."*

## The measurement

| artifact | source | destination | destination project |
|---|---|---|---|
| `census-038-mbugwe-phase6` | match | **DRIFTED** | `GT038 Phase6 Target` |
| `census-038-t067-registered` | match | match | `GT038 T067 Target` |
| `census-038-t068-registered` | match | **DRIFTED** | `GT038 Closure Target` |
| `census-038-t069-registered` | match | **DRIFTED** | `GT038 Closure Target` |

One of four links is still byte-reproducible. Two things follow that the
filing did not say:

**1. `-t068-` and `-t069-` name the SAME destination project.** Two censuses of
one mutable project cannot both be reproducible at any moment, whatever anyone
does. The chain was never independently re-measurable -- from the day the
second of them was written, not from the day something drifted. (This very
session's T093 run restored that project again, which is how ordinary the
mechanism is.)

**2. Re-measuring is impossible in principle, not merely inconvenient.** Each
link pins a REGISTRY STATE, recorded in its paired registration artifact:

| | rows live when taken |
|---|---|
| `closure-registration-038-t067` | 2 (`AFFIX_TO_POS`, `MSA_TO_FEAT_STRUC_TYPE`) |
| `closure-registration-038-t068` | 3 (+ `SLOT_TO_POS`) |
| `closure-registration-038-t069` | 5 (+ the two template rows) |
| **live today** | **8** (T076 added two, T104 one) |

And T070-T072 then changed what a registered row DOES -- from emitting an edge
to planning a member. A re-run today would answer a different question under
the same filename, which is the drift the chain was built to prevent arriving
by the other door.

## The decision, forced

T102 named two candidate repairs and said choosing between them needed the
three re-runs' evidence. The evidence above eliminates the first: re-measuring
`-t067-`/`-t068-`/`-t069-` cannot produce the comparison it was meant to
inform. So the second is what landed.

* **`_census_table` narrowed** from six fields to four -- `source_count`,
  `destination_count_total`, `destination_count_net`, `difference`. The claim
  is about object counts; `verdict_class` and `unexplained_shortfall` are the
  instrument's reading, and the instrument is *allowed to improve*. T087 and
  T099 both did, and both would have turned three of these tests red with
  nothing having moved. The `totals` equality asserted alongside each
  comparison still carries the instrument-level reading, so nothing is
  unwatched -- it is watched where it belongs.
* **Four pins added**: the narrowing itself (so re-widening is deliberate);
  the per-link reproducibility status, measured against the world; the
  shared-destination fact; and the registry the chain pins no longer existing.

## The pin that is meant to go red

`test_every_link_in_the_chain_declares_whether_it_is_reproducible` is T102's
second half -- "a test that fails when a committed artifact stops being
reproducible". When a project is restored, re-transferred or deleted, the link
that pinned it stops being evidence and this test says so. Until now a link
could stop being evidence and nothing anywhere would change colour.

A `match` becoming `drifted` is a **loss of evidence**, never a passing
condition to be quietly re-baselined; updating the expectation is a deliberate
edit that records the loss, the way T093's pin required its number to be
changed on purpose.

## The shape

Fourteenth appearance, and the second in this session where the thing read at
the wrong level is a committed ARTIFACT. T093's was a signal the code declined
to compute; this one is a comparison whose *reference frame* was the thing
being compared. Four files can agree with each other perfectly and describe a
world that no longer exists -- and every test in the chain was green the whole
time.
