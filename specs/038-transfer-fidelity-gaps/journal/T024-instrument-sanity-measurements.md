# T024 -- live sanity measurements (tests NOT yet written)

**Status: measurements complete, tests not written, nothing committed.** Branch HEAD
still `3973fa0`, worktree clean, `test_object_census.py` still 2099 lines / 136 tests.
The run stopped before the drafted ~500-line test block landed (a bash heredoc
quoting failure). **T024 stays open**; a follow-up appends the tests from the numbers
below and the two saved artifacts, so the 76 MB Ngoreme open need not be repeated.

Saved artifacts: `scratchpad/census-ngoreme.json`, `scratchpad/census-ejagham.json`.

## Safety -- all four projects read-only, digests unchanged

| project | sha256 before -> after | mtime | opened |
|---|---|---|---|
| `Ngoreme FLEx` | `052243ea...9843b` unchanged | Aug 18 16:56:06 | read-only, closed |
| **`Ngoreme Target`** | `dda21971...4af3b` unchanged | **Aug 19 09:30:41** | **read-only, closed** |
| `Ejagham W Mini` | `c174f0b4...24ec6` unchanged | Aug 18 21:04:33 | read-only, closed |
| `Ejagham W Target` | `1cbef60c...94ccc` unchanged | Aug 19 08:40:06 | read-only, closed |

`Ngoreme Target` was opened **read-only only** -- never write-enabled, never restored,
no transfer run. Its mtime still predates this session's work. Digests verified before
open, after close, and again at teardown. No project created or deleted.

**Lock event, handled correctly:** at start both target projects were held by live
`FieldWorks.exe` (PIDs 59512, 58780) with `.fwdata.lock` present, and the first census
attempt **correctly refused** with `FP_FileLockedError` -> `CENSUS_ERROR` exit 7. The
processes were not killed. Once FLEx was closed the projects were re-digested to
confirm FieldWorks had written nothing on close, then the run proceeded. Worth keeping:
the instrument refuses a locked project rather than reading a half-written one.

## Results

| expected | pair used | measured | |
|---|---|---|---|
| `MoStemMsa` 1949->0 | **`Ngoreme FLEx` -> `Ngoreme Target`** | src 1949, dest 0, base 0, diff **-1949**, shortfall 1949, `row_passes=False` | **PASS** |
| `PhPhoneme` 41->64 | both pairs | src 41, dest_total 64, base **23**, net **41**, diff **0**, `MATCHED`, `difference_raw` +23 | **PASS** |
| 21 duplicate names | Ejagham 21 / Ngoreme 20 | `duplicates.extra_objects` -- but see the finding below | **QUALIFIED** |
| `MoAffixProcess` 13->0 | `Ejagham W Mini` -> `Ejagham W Target` | src 13, dest 0, diff -13, `row_passes=False`, `in_class_list_via=census_additions`, `inventory_tables=["NONE"]` | **PASS** |
| `MoAffixAllomorph` **+13** | -- | `Ejagham W Target` holds **0** allomorphs; that row is 130 -> 0 | **NOT REPRODUCIBLE** |
| `MoInflAffixTemplate` 8->0 / `MoInflAffixSlot` 11->0 | `Ejagham W Mini` -> `Ejagham W Target` | 8->0 diff -8; 11->0 diff -11; both `row_passes=False` | **PASS** |

**No case where the instrument reported an expected-loss row as clean**, with the one
qualified exception of the PhPhoneme duplicate row.

### Three premises in tasks.md were wrong; corrected in place

1. The `MoStemMsa` 1949 source is **`Ngoreme FLEx`**, not `Ngoreme`. `Ngoreme` holds
   MoStemMsa **1945** / PhPhoneme **37**; `Ngoreme FLEx` holds exactly **1949 / 41**.
2. `MoInflAffixTemplate` 8 / `MoInflAffixSlot` 11 is the **Ejagham** pair. The Ngoreme
   pair loses **13** and **19**.
3. **`MoAffixAllomorph` +13 does not exist on disk.** No project on this machine holds
   143 allomorphs; `Ejagham W Target` lost *both* classes outright (130->0 and 13->0).
   It was **not manufactured**. The conversion *signature* is reproducible at scale 1
   on the Ngoreme pair: `MoAffixProcess` 1->0 (shortfall 1) beside `MoAffixAllomorph`
   146->**147** (surplus +1, baseline 0) -- both halves in one artifact, **not netted**,
   which is the property that actually matters.

## FINDING 1 -- 21 duplicate phonemes do NOT fail the run

`DUPLICATE_IDENTITY` **never fires** and `totals.duplicate_extra_objects` reads **0**
against a destination holding 21 duplicate phoneme names.

Cause is neither the cap nor a bug: **`PhPhoneme` is absent from 035's roster**
(admitted: `WfiWordform`, `ReversalIndex`, `ReversalIndexEntry`), so
`duplicates.roster_admitted` is `False` and `duplicates_unaccounted()` returns 0 **by
design**. `contracts/natural-key-roster-extension.json` still holds **zero entries** --
**T028 has not populated it.** The row reports `row_passes=True`.

The loss is not invisible: `_phase_1` (`census.py:3582`) carries a dedicated PhPhoneme
duplicate check that fires with the exact SC-002 wording *"baseline arithmetic alone
would have passed this row"*. **So the correct assertion is phase-1 unsatisfied, not
`DUPLICATE_IDENTITY`.** Recorded as **T024a**, including re-running the duplicate
assertions once T028 appends its six entries.

### The 20-vs-21 gap is the instrument being MORE right than the brief

A writing-system-agnostic scan finds three `b` phonemes in `Ngoreme Target`, but the
third is `{en: "b", ngq: "bh"}` and `ngq` is the default vernacular -- so its key is
**`bh`**, not a duplicate. `census._ws_handle_for`'s no-fallback rule prevented a
fabricated match. 20 is correct for that pair; 21 is correct for Ejagham.

## FINDING 2 -- `census gate` returns a bare exit 0 on a ruined transfer

Both pairs: `CENSUS_ACCOUNTED`, **exit 0**, `gate_artifact().passed=True` -- while
carrying **44-47 failing rows and 74,157 units of unexplained shortfall**.

This is the 5.2 gross-basis cap behaving exactly as specified (the real baseline is
count-only, so every row is `baseline_gross`), and it is still an **unsafe default for
a release gate**: the headline reports success on a catastrophically incomplete
transfer, and the failing evidence surfaces only if the caller thinks to pass
`--phase`. `evaluate_phase(1)` and `(5)` both fail correctly and name `MoStemMsa` and
`MoAffixProcess`, and `gate_artifact(phase=N).passed` is `False` -- the information
exists; the **default** is what is wrong. Recorded as **T024b**.

This is also why T023c's note-rendering matters: without it, exit 0 here would have
printed nothing at all about the cap.

## How to assert around the cap

Assert on row-level evidence, which the cap deliberately leaves untouched:
`difference`, `unexplained_shortfall`, `verdict_class`, `row_passes`, plus
`evaluate_phase(1)` / `evaluate_phase(5)`. Do **not** assert on the run verdict or exit
code for shortfall pairs -- they are capped by design.

## For the follow-up that writes the tests

- Append to `tests/integration/test_object_census.py`; do not rewrite existing tests.
- Mark each live test `@pytest.mark.integration` **individually** -- the marker is
  registered at `pyproject.toml:99`, and T014's module docstring reserves this. Do
  **not** promote the module: it is currently hermetic (136 tests, `tmp_path` JSON only,
  no `flexicon`/`FLExInit` at module scope) and the gate must stay runnable with no
  live project.
- Reuse the two saved artifacts rather than re-opening projects.
- Tests must **skip cleanly** when a project is absent -- and note both target projects
  must not be open in FieldWorks, or the census correctly refuses with
  `FP_FileLockedError`.
