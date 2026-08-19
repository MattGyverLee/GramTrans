# T024 -- sanity tests landed

**Commit `08c1033`** on `038-transfer-fidelity-gaps` --
`test(038): sanity-check the census against known-bad pairs (T024)`. One file, a
**pure append** (the pre-existing 2099 lines byte-identical), +1603 lines,
**24 new tests: 136 -> 160**. Nothing under `specs/`, no push.

Companion journal `T024-instrument-sanity-measurements.md` holds the measurement
detail; this records what was pinned and what is still open.

## Per pair

**`MoStemMsa` 1949 -> 0** -- `Ngoreme FLEx` -> `Ngoreme Target` -- **PASS**

```
MoStemMsa  src=1949 dest_total=0 base=0 net=0 diff=-1949 shortfall=1949
           verdict=SHORTFALL row_passes=False
```

**`PhPhoneme` 41 -> 64** -- both pairs -- **PASS**. Starter subtraction exactly right:
64 - 23 = 41 = source.

```
PhPhoneme  src=41 dest_total=64 base=23 net=41 diff=0 difference_raw=+23 verdict=MATCHED
           dup_groups=21 dup_extra=21 roster_admitted=False   (ejagham)
           dup_groups=20 dup_extra=20 roster_admitted=False   (ngoreme)
```

**`MoAffixProcess` 13 -> 0** -- Ejagham -- **PASS**, with
`in_class_list_via=census_additions` and `inventory_tables=["NONE"]`: a census built
from the transfer tables alone would have had **no row at all** here. That is the
additions ledger earning its place.

**`MoAffixAllomorph` +13 -- NOT REPRODUCIBLE.** `Ejagham W Target` holds **zero**
allomorphs, so that row is 130 -> 0: both classes destroyed, not one converted into the
other. No project on this machine holds 143. **Not manufactured.** The conversion
signature does reproduce at scale 1 on Ngoreme -- `MoAffixProcess` 1->0 beside
`MoAffixAllomorph` 146->147 (+1 surplus) -- both halves in one artifact, **not netted**.

**`MoInflAffixTemplate` 8->0 / `MoInflAffixSlot` 11->0** -- Ejagham -- **PASS**.
(Ngoreme loses 13 and 19.)

## The one thing reported clean -- a ROSTER gap, not an engine defect

21 duplicate phonemes do not fail the run: `DUPLICATE_IDENTITY` never fires,
`totals.duplicate_extra_objects` reads **0**, `row_passes=True`, run exits 0. Cause is
by design and not the cap -- `PhPhoneme` is outside 035's roster (admitted:
`WfiWordform`, `ReversalIndex`, `ReversalIndexEntry`) and `duplicates_unaccounted()`
returns 0 for unadmitted classes. Only the phase-1 predicate stops the transfer being
called done.

**A hermetic test flips `roster_admitted` alone and the verdict moves to
`DUPLICATE_IDENTITY` with a non-zero exit.** That isolates the cause precisely: the
engine is correct, the roster is empty. `census.py` unchanged. Tracked as **T024a**,
which must re-run these assertions once T028 appends the six entries.

The 20-vs-21 split is the instrument being **right**: Ngoreme Target's third `b` is
`{en: "b", ngq: "bh"}` with `ngq` the default vernacular, so its key is `bh`.

## The near-miss that justifies the whole task

**The starter baseline is a spec artifact on `main`, so the feature branch does not have
the file.** The first live run therefore silently skipped all 23 live tests and reported
a green **"137 passed, 23 skipped"** -- precisely the false comfort T024 exists to
prevent. `_t024_starter_baseline()` now falls back to `git show main:<path>`.

Worth generalising: on this repo's specs-to-`main` / code-to-worktree split, **any test
that reads a spec artifact must resolve it through `main`, not the working tree**, or it
will skip itself into a false pass on every feature branch.

## Gross-basis cap

Masked the run verdict on both pairs (`CENSUS_ACCOUNTED`, exit 0, 44-47 failing rows,
74,157 unexplained shortfall). Asserted around entirely on row-level evidence plus
`evaluate_phase(1)`/`(5)` -- both unsatisfied, naming `MoStemMsa` and `MoAffixProcess`
-- and `gate_artifact(phase=N).passed=False`. **T024b** holds the open question of
whether a bare `gate` should be able to return 0 at all on that basis; that is a
**user decision** and is flagged as such in `tasks.md`.

## Tests

- Hermetic subset: **137 passed, 23 deselected, 1.3s** (`-m "not integration"`) -- the
  gate still runs with **no live project**, which was the property to protect.
- Full file: **160 passed**. All 23 live tests marked `@pytest.mark.integration`
  **individually**; the module stays marker-free.
- `tests/unit`: **27 failed / 2624 passed / 79 skipped / 14 xfailed / 14 xpassed** --
  byte-identical to baseline. Ruff delta zero (11 before, 11 after).

## Safety

All four `.fwdata` digests byte-identical before open, after close, and again after the
pytest run. **`Ngoreme Target`: opened read-only only, never write-enabled, never
restored, no transfer run**; mtime still `Aug 19 09:30:41`. At session start FieldWorks
held both targets and the census **correctly refused** with `FP_FileLockedError` ->
`CENSUS_ERROR` exit 7; the processes were not killed.

## Two open items for whoever picks this up

1. **Two competing T024 designs exist, and this needs reconciling deliberately.** An
   orchestration error had two agents on T024 at once. The committed design
   **re-measures live**; the other is **snapshot-based** and left
   `tests/integration/_snapshots/census-038-{ngoreme,ejagham}.json` (byte-identical
   copies of the live artifacts) **untracked**. The committed tests do not read them.
   The snapshot design's advantage is real and specific: being hermetic, it **cannot
   silently skip** the way the live design did above. They are complementary --
   snapshots for a gate that must never self-skip, live runs for detecting real drift.
   Reconcile on purpose, not by whoever commits last.
2. **`FLExInitialize` dumps a survivable `Windows fatal exception: access violation`
   even on a SINGLE-FILE run**, not only on directory runs as previously recorded.
   Execution continues and the reads verifiably happen. The single-file guidance in
   earlier journals is therefore weaker than stated -- the hazard is not confined to
   directory selections, it is just survivable more often.
