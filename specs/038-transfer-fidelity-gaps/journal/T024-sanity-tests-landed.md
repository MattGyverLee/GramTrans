# T024 -- sanity tests landed

**Commits `08c1033`** (tests) **and `d8fbe65`** (the fixtures it depends on) on
`038-transfer-fidelity-gaps`.

> **CORRECTION.** `08c1033`'s message understates its contents. An orchestration
> error had **two agents on T024 concurrently**, and that commit ran `git add` over
> the whole test file while the second agent's 904-line hermetic block sat
> uncommitted in the shared worktree index -- the same shared-index hazard the
> T023b/T023c journal records. The committed blob is **3702 lines / 233 tests**, not
> the 1603 lines / 24 tests the message describes. An AST check confirms **no
> duplicate top-level names** between the two blocks, so both designs coexist
> cleanly.
>
> **73 of the committed tests read two snapshot fixtures that were left untracked**,
> so `HEAD` passed only in the worktree that happened to hold them and failed
> anywhere else with "the T024 measured census snapshot is missing". `d8fbe65` adds
> them. Verified after: **233 collected, 209 passed, 24 deselected** in 1.65s.

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

- Hermetic subset: **209 passed, 24 deselected, 1.65s** (`-m "not integration"`) -- the
  gate still runs with **no live project**, which was the property to protect.
- Full file: **233 collected**. All 23 live tests marked `@pytest.mark.integration`
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

1. **Both T024 designs are now committed in one file and need reconciling
   deliberately.** An orchestration error had two agents on T024 at once, and
   `08c1033` swept both blocks in; `d8fbe65` then committed the two snapshot fixtures
   that **73 of the committed tests read**. The two designs are complements, not
   rivals:
   - The **hermetic/snapshot** block **cannot silently skip.** That failure mode is
     structural, not a bug that was fixed: a skip path is indistinguishable from
     success in a summary line -- `137 passed, 23 skipped` reads green at a glance.
     The `git show main:<path>` fallback repairs one cause of skipping; absent project,
     locked `.fwdata`, missing FLEx host and any future path assumption remain live
     skip routes. It also enables the forged-copy tests that isolate cause from
     symptom -- flipping `roster_admitted` on a deep copy to prove the duplicate
     detector is roster-gated rather than broken, adding one `errors` entry to prove
     the cap is a ceiling on tallies not severity. None of those are possible against
     a live project. And it pins the ruined destinations permanently, which matters
     because `Ngoreme Target` is irreplaceable and a live test depends on nobody ever
     restoring it.
   - The **live** block is the only thing that **re-reads the database**. A snapshot
     pins what the instrument reported on 2026-08-19; it cannot detect that
     `count_classes` has since started reporting 1948 instead of 1949, and it goes
     stale silently if the roster, coverage floor or class list moves. It also cannot
     discover new facts -- the corrected premise that `Ngoreme FLEx` holds 1949/41
     while `Ngoreme` holds 1945/37 is unprovable from an artifact naming only one.
   **Suggested shape:** keep the hermetic block as the gate, trim the live block to
   2-3 re-measurement tests that regenerate the snapshots and assert they still match,
   and **add a guard that FAILS rather than skips when zero live tests ran** under
   `-m integration` -- otherwise the green-on-skip failure mode returns the next time a
   path assumption breaks. One hand-placed tripwire already exists (it reads 035's
   live roster and fails the moment `PhPhoneme` is admitted, telling the reader to
   regenerate the snapshots), but that is one guard, not a general property.
2. **`FLExInitialize` dumps a survivable `Windows fatal exception: access violation`
   even on a SINGLE-FILE run**, not only on directory runs as previously recorded.
   Execution continues and the reads verifiably happen. The single-file guidance in
   earlier journals is therefore weaker than stated -- the hazard is not confined to
   directory selections, it is just survivable more often.
