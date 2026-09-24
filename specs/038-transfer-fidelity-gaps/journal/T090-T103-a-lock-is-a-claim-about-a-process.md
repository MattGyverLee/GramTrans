# T090 / T103 — a lock is a claim about a process; a count is a claim about bytes

**Date**: 2026-08-22
**Tasks**: T090 (stale lock), T103 (hardcoded live count)
**Live projects opened**: `Ejagham Mini`, `Mbugwe LizzieHC practice`,
`Ejagham W Mini`, `Ejagham W Target`, `Ngoreme`, `Ngoreme Target`,
`Ngoreme FLEx` — **all read-only**, all through paths that prove their own
read-only-ness by digest before/after. Nothing restored, nothing written.
`Esperanto` and `Target` were not opened.

---

## Why these two were the same pass

T103 exists because of T090. The last pass measured a suite whose `skipped`
went 76 → 75 while `failed` went 0 → 1, and the new failure was a *live test
that had been skipping*: a stale `.fwdata.lock` had been suppressing it, the
lock lifted, the coverage came back — carrying a stale number. So T090 is the
cause and T103 is what the cause was hiding. Fixing the first without the
second would have made the suite louder and then immediately red.

Both are the feature's recurring shape, one level apart. **A lock file is not a
fact about a file, it is a claim about a PROCESS. A count is not a fact about a
project, it is a claim about BYTES.** In each case something was being read at
a level where it could not do its job.

---

## T090

### Was flexicon at fault, or the driver?

The task said this was worth checking before blaming the driver, and it was.
Asked through FLExToolsMCP, `FLExProject.OpenProject`'s own docstring settles
it:

> *The project must be closed with `CloseProject()` to save any changes, **and
> release the lock**.*

No read-only exemption — the lock is taken on **any** open. So flexicon is
behaving as documented and the driver is at fault.
`debug/audit038_closure_edges.py` called `full_run._open_source_readonly` and
returned; it had no `try`/`finally` either, so the success path *and* every
exception path leaked the lock.

`run038_closure_census.py`, the other driver T090 names, turned out to be
**already clean**: it reaches a project only through `run_full_transfer` (which
closes both handles in a `finally`) and `census_cli` → `census.read_project`
(same). Its locks came from the audit driver sharing its default
`SOURCE = "Mbugwe LizzieHC practice"`.

**The sweep found exactly one sibling**, `debug/probe_adhoc_loss.py`, which
opens a source *and* a target read-only and closed neither. 30 files in
`debug/` touch a project; 2 leaked.

### (a) Pair the opens

`full_run.source_readonly` is a context manager, so the pairing is by
construction rather than by remembering to close on every return path. The
audit driver's body moved into `_audit(proj)` so its ~450 lines did not have to
be re-indented into a `with`. `probe_adhoc_loss` closes both handles in nested
`finally`s.

A test pins the whole class rather than the two files: **no file in `debug/`
may open a project unless the same file also closes it**, delegates to
`run_full_transfer` / `census.read_project`, or uses `source_readonly`.

### (b) A stale lock is a measurement, not a refusal

`full_run.read_project_lock` classifies the file as `ABSENT` / `HELD` /
`STALE` / `UNREADABLE` by asking whether the recorded PID is still running.
Both readers — `_open_or_skip` and `_live_project_or_skip`, the **second site**
the sweep found in `test_object_census.py` — refuse on `HELD`/`UNREADABLE`,
and on `STALE` print what they found and **measure anyway**.

**The rule is deliberately asymmetric, and that is the whole design.** Calling
a live lock stale is the dangerous direction: flexicon would overwrite the lock
file with our PID and delete it on close, stealing the lock from a running
FieldWorks — exactly the blast radius CLAUDE.md's restore-before-write rule
exists to avoid. Calling a stale lock live merely costs a skip. So `STALE`
requires a PID that is **definitively** not running; *running*, *cannot tell*,
*no PID in the file* and *file unreadable* all fall to the refuse side.

**Nothing deletes a lock file**, per T090's explicit instruction. It does not
need to: flexicon replaces the stale file with a live one on open and removes
it on close. That was observed directly — a planted stale lock was gone after
the test run without anything in this repo touching it.

**`os.kill(pid, 0)` is not usable here.** CPython implements `os.kill` on
Windows through `TerminateProcess`, so the POSIX liveness idiom would terminate
the very process it is asking about. `_pid_is_running` goes through
`OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` + `GetExitCodeProcess`, which
is read-only by construction. `ERROR_INVALID_PARAMETER` is the only answer that
means dead; `ERROR_ACCESS_DENIED` means the process exists and we may not look,
which reads as alive.

**One case deliberately left undecided**: a recycled PID. If the OS has handed
the number to an unrelated process the lock is stale and this still calls it
`HELD`. Matching the recorded `ProcessName` to the live image would move a case
from HELD to STALE — the one direction that must not be guessed at. Getting it
wrong here can only make the suite quieter, never less safe.

### The measurement

On the live `Ejagham Mini`, `tests/integration/test_038_phon_empty_drop_live.py`:

| lock planted | before T090 | after T090 |
|---|---|---|
| none | 12 passed | 12 passed |
| **stale** (PID 999999, `python`) | 10 passed, 2 skipped | **12 passed**, `[WARN] … STALE … measuring anyway` |
| **live** (PID 4, `FieldWorks`) | 10 passed, 2 skipped | 10 passed, 2 skipped, **lock file untouched** |

The stale row is the defect and the live row is the guard rail; both were
measured against a real project rather than a fake.

`audit038_closure_edges.py` was then run end to end on `Ejagham Mini`: exit 0,
**no lock left behind**, and its six relationship verdicts reproduce the
committed `closure-edge-audit-038-ejagham-mini.json` **byte for byte** — so
half (a) landed without disturbing what the audit says. Its verdicts also agree
relationship-for-relationship with the Mbugwe corpus, which is the corroboration
that driver's own docstring asks for.

Four stale locks sit on disk right now (`Ejagham Full GT-Test`, `Ejagham Full`,
`Esperanto`, `Hdi`) from three dead PIDs. **They were left in place.** The
classifier reads all four correctly as `STALE`, so they cost nothing, and
deleting other people's lock files is not this task's business. This session
added none.

---

## T103

### What had actually failed

`test_ngoreme_flex_holds_1949_and_ngoreme_holds_1945` asserted
`{'Ngoreme FLEx': (1949, 41), 'Ngoreme': (1945, 37)}` exactly. Measured today:

| project | digest | MoStemMsa | PhPhoneme |
|---|---|---|---|
| `Ngoreme FLEx` | `e10a44ef1b74…` (moved) | **1953** | 41 |
| `Ngoreme` | `6d35c9575fc6…` | 1945 | 37 |

1949 when written, 1952 at T087, 1953 now. The **premise** — `Ngoreme FLEx` is
a different and larger project than `Ngoreme`, which is what stops a reader
"correcting" tasks.md's name back — never stopped holding for a moment. So the
defect is the decision to hardcode an exact count of a project a human edits,
which is direction **(b)**, as the task's own reasoning predicted.

### The resolution, and why it is (b) *with* a bounded (c)

Direction (a), re-pinning to 1953, buys green until the next edit; two passes
already declined it. Direction (c) alone — gate everything on the digest —
runs into the test's own comment, which argues *"a moved file makes it MORE
useful, not less"*, and that argument is **right about the premise**: the
premise is measured live and a moved file is a fresh opportunity to check it.

So the two claims were separated, because they are not the same kind of claim:

* **The premise is asserted unconditionally**, against whatever is on disk —
  the two projects differ, both count nonzero (a 0-vs-0 vacuous pass is
  refused), and `Ngoreme FLEx` holds more `MoStemMsa` **and** more `PhPhoneme`.
* **The exact counts moved into an append-only ledger** keyed by
  `sha256(.fwdata)`. At **unchanged** bytes an exact count is a genuine
  tripwire — the same file must count the same way, and a counting regression
  shows up here. At **changed** bytes it is a claim about a file that no longer
  exists, so it stands down and prints the exact line to append. That is the
  same stand-down-on-drift `_t024_census` already applies to snapshot-based
  blocks, now applied only to the claim that is literally "these bytes counted
  N".

Both readings are recorded, so the ledger is evidence rather than a pin:
`052243ea…` → (1949, 41), the digest the committed snapshot was measured at,
and `e10a44ef…` → (1953, 41), today. **The 1952 reading gets no row**: it was
seen in a failure message and no digest was captured with it, and a count
without the bytes it was counted from is precisely what the ledger exists to
stop.

### The half that makes a permissive gate safe

A gate that can stand down is a gate that can be talked into standing down, so
two guards were added:

1. **An offline test** — it runs on a host with no FieldWorks — asserts that
   **every row in the ledger satisfies the premise**. A row that contradicts it
   cannot be appended to buy a green live run, and the block cannot become a
   no-op by the ledger being emptied.
2. If **both** projects drift off the ledger in one run, the live test
   **fails**: the premise held, but nothing was watching the counting code any
   more, and a run that checks no exact count anywhere must not read as green.

### Proved by forging, three ways

| forgery | result |
|---|---|
| ledger row changed to `(9999, 41)` at the **unchanged** digest | **FAILS**: *"counted (1953, 41) at the SAME bytes that previously counted (9999, 41) … this is the counting code changing, not the data"* |
| `Ngoreme FLEx`'s digest key corrupted, so it drifts off the ledger | **PASSES**, premise asserted, and prints the exact `"e10a44ef…": (1953, 41)` line to append |
| `Ngoreme`'s row changed to `(9999, 99)`, contradicting the premise | offline test **FAILS**: `assert 1949 > 9999` |

---

## Suites

| suite | after T100/T101 | after T090/T103 |
|---|---|---|
| `tests/unit` | 3587 passed, 79 skipped, 14 xfailed | **3587 passed, 79 skipped, 14 xfailed** (unmoved) |
| `tests/integration` | 448 passed, **1 failed**, 75 skipped | **480 passed, 0 failed, 75 skipped** |

The `+32` is fully accounted for: **30** new tests in
`tests/integration/test_038_stale_lock.py`, **+1** from the T103 test splitting
into a live half and an offline half, and **+1** from the pre-existing
`Ngoreme FLEx` failure resolving. `skipped` is **unchanged at 75** — which is
worth stating plainly, because "T090 made things stop skipping" would be the
easy thing to claim and it is not what happened here: there were no stale locks
on the six projects that module walks when the suite ran. T090's effect was
measured by *planting* one, not by waiting for one.

Still run separately: a combined invocation fails collection on the
`test_038_process_rules.py` basename collision.

---

## Live-project discipline

Every open was read-only. The census path digests each `.fwdata` before and
after and raises if it moved; the phonology path does the same. No project was
restored, no target was bound, nothing was written. The two locks planted on
`Ejagham Mini` were planted by this work and removed by it (one of them by
flexicon itself, on close). **The four pre-existing stale locks on disk were
not touched**, and this session left no new ones — which is half (a) working.

## Not done, deliberately

* **T064** — still parked. Its unmet half (`MoAffixProcess` MATCHED) is owned
  by T076/T077. Fourth pass to leave it on purpose.
* **T102** — still filed, not fixed. Needs three live driver re-runs.
* **T092** — `preview.plan_match_decision` still has no production caller.

## Suggested next pass

**T076 → T077**, if the next pass can restore a target: it is what finally
moves T064's P4 (`MoAffixProcess` 18/12/-6 → MATCHED), and T064 has now been
skipped over four times, which is the point at which "deliberately parked"
starts to look like "quietly dropped". Live work is also cheaper now than it
was: a driver run no longer poisons the next suite run.

Alternatives, unchanged: **T074** (affix-to-template-column linking, measured
baseline 0 of 110 linked and 0 reported), or **T092**, which T091 left as a
decide-on-the-evidence question — whether the plan-time seam earns its callers
or should be deleted.
