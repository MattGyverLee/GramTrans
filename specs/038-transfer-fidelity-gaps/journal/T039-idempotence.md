# T039 -- idempotence (SC-008), measured on a second live run

**Date**: 2026-08-20
**Run 1**: `GT-20260820-002806` · **Run 2**: `GT-20260820-003239`
**Pair**: `Ejagham Mini` -> `GT038 Phase4 Target` (the same target, re-run in
place -- which is the whole point)

**Substantively: SC-008 HOLDS.** A re-run adds nothing. One reporting defect
surfaced, it is a single root cause, and it is the same one already blocking
T038's `PartOfSpeech` row.

---

## What T039 asks for, and what was measured

| criterion | result |
|---|---|
| run 2 contains **zero** `PlannedAction` whose `match_basis.basis is NONE` for any class run 1 created | **PASS** -- run 2 planned **0 actions at all**, so the condition holds trivially and by a wider margin than asked |
| every class's `destination_count_total` unchanged | **PASS** -- identical across all **74** classes |
| every `EnrichedCollection.added == 0`, `already_present` equal to run 1's `added` | **NOT EVALUABLE** -- enrichment is US4 (T042-T047) and has not landed. To be re-run when it does. |

Run 2's shape, for the record:

```
actions planned  : 0        (run 1: 329)
overwrites       : 38       (run 1: 23)
skips            : 2125     (run 1: 1811)
identity subst.  : 23       (run 1: 23)
duplicate extras : 0        (run 1: 0)
```

Zero actions is the strong form of the claim: the engine did not merely avoid
creating duplicates, it found nothing left to create.

---

## The one defect this exposed

Two rows changed verdict between the runs **without any count changing**:

| class | run 1 | run 2 |
|---|---|---|
| `PhPhoneme` | MATCHED, basis `baseline_matched`, unexplained 0 | SHORTFALL, basis `baseline_gross`, unexplained **21** |
| `PhNCSegments` | MATCHED, basis `baseline_matched`, unexplained 0 | SHORTFALL, basis `baseline_gross`, unexplained **2** |

`destination_count_total` is identical in both runs for both classes. **Nothing
was lost and nothing was created.** The 21 and the 2 are phantoms, and they are
exactly the 21 duplicate phonemes and 2 duplicate natural classes the fix
stopped creating -- now reappearing as a *reporting* artifact.

### Root cause: an identity match planned as a `Skip` is invisible

- In **run 1** those 23 objects were matched by **natural key**, which emits a
  `PlannedOverwrite` carrying a `MatchBasisRecord`. The census could attribute
  the starter objects and awarded the trustworthy `baseline_matched` basis.
- In **run 2** the very same objects match by **GUID identity**, because run 1
  linked them. That path emits a bare
  `Skip(ALREADY_PRESENT_BY_GUID)` -- and **`Skip` has no `match_basis` field**.
  With no record, the census cannot attribute them, falls back to
  `baseline_gross`, and gross subtraction removes starter objects the transfer
  correctly matched -- manufacturing a shortfall on a correct run.

**This is one root cause, showing up in three places**, which is why it is
worth naming rather than patching per-row:

1. T038's `PartOfSpeech -5` (run 1) -- 5 starter POSes matched by GUID through
   `_plan_gold_reserved_edit`'s early bare `Skip`.
2. `PhPhoneme -21` (run 2) -- via `_phonology_simple_plan`'s bare `Skip`.
3. `PhNCSegments -2` (run 2) -- same path.

The perverse consequence is worth stating plainly: **the better the transfer
gets, the worse the census reports it.** Once matching works, objects stop
being created and start being skipped by identity, and every identity skip
degrades its row's subtraction basis.

### Where the fix belongs

`_emit_present_outcome` (preview.py) already attaches an IDENTITY
`MatchBasisRecord` and derives the class from the category. The two paths that
bypass it are `_plan_gold_reserved_edit` and `_phonology_simple_plan`, both of
which return a bare `Skip` on a GUID hit.

**T043 already schedules the `_plan_gold_reserved_edit` half** -- widening it so
the two early `Skip` returns fire only when the owned-collection pass also
finds nothing, otherwise falling through to
`PlannedOverwrite(write_mode="merge")`. The `_phonology_simple_plan` half needs
the same treatment and currently has no task; it should be added to Phase 5
beside T043 rather than left to be rediscovered by the next census.

An alternative -- giving `Skip` a `match_basis` field -- is recorded here as
considered and NOT recommended: `Skip` means "nothing will be written", and a
skip that carries a match is really a link, which is the LINK-vs-SKIP
distinction defect G3 already turns on (data-model.md:209-213). Widening
`Skip` would blur exactly the boundary US4 exists to sharpen.

---

## Bottom line

SC-008's substance is proven live: **a second run adds nothing, and every
class's destination count is byte-identical.** The remaining work is that the
census cannot yet *say* so for identity-matched rows, and that is one fix in
two call sites, not a transfer defect.
