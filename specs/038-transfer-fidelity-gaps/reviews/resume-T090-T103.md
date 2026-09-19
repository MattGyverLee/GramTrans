# Resume report — T090 → T103

**Date**: 2026-08-22
**Feature**: 038-transfer-fidelity-gaps
**Worktree (code)**: `D:\Github\_Projects\_LEX\GramTrans-038-transfer-fidelity-gaps`,
branch `038-transfer-fidelity-gaps`, `85a2919` → `f0801a9`
**Root (`main`, specs)**: `06e740e` → `e9437d8`

---

## Where this pass resumed, and why not where the resolver said

`status-context.py` resolves `nextTask: T064` for the fourth time. T064 is
deliberately parked ("RUN AND MEASURED 2026-08-21, NOT PASSED") and its unmet
half — `MoAffixProcess` MATCHED — is owned by **T076/T077**. The worktree was
clean at `85a2919`, so there was no half-landed work to finish first, and the
actual next actionable pair was the one the T100/T101 report named: **T090 →
T103**, in that order.

## Headline

| task | status | measurement |
|---|---|---|
| **T090** | **CLOSED** | A stale lock now **reports and measures** instead of skipping. On the live `Ejagham Mini`: stale lock planted → **12 passed** (before: 10 passed, 2 skipped); live lock planted → 10 passed, 2 skipped, **lock file untouched**. The audit driver re-run leaves **no lock** and reproduces its committed snapshot byte for byte. |
| **T103** | **CLOSED** | The premise is asserted unconditionally; the exact counts moved into an append-only `sha256(.fwdata) → (MoStemMsa, PhPhoneme)` ledger. Proved by forging three ways. |

Full reasoning:
`journal/T090-T103-a-lock-is-a-claim-about-a-process.md`.

## The one thing to read if you read nothing else

**flexicon was not at fault, and T090 was right to make that the first
question.** Asked through FLExToolsMCP before any driver was touched,
`FLExProject.OpenProject`'s own docstring settles it: the project *"must be
closed with `CloseProject()` to save any changes, **and release the lock**"* —
with no read-only exemption. The lock is taken on **any** open, so an unclosed
read-only open is a leak, and the caller owns it.

That also decided the shape of half (b). Since flexicon *retakes* the lock on
open and drops it on close, the reader never needs to delete anything: a stale
file is replaced by a live one for the duration of the test and removed
afterwards. That was observed directly, not assumed.

## The asymmetry, which is the whole design of (b)

Calling a **live** lock stale is the dangerous direction — flexicon would
overwrite the lock file with our PID and delete it on close, stealing it from a
running FieldWorks. Calling a **stale** lock live merely costs a skip. So
`LOCK_STALE` requires a PID that is *definitively* not running; *running*,
*cannot tell*, *no PID in the file* and *file unreadable* all fall to the
refuse-to-measure side, and a recycled PID is left undecided on purpose.

`os.kill(pid, 0)` is unusable here: CPython implements `os.kill` on Windows
through `TerminateProcess`, so the POSIX liveness idiom would terminate the
process it is asking about. The probe goes through
`OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` + `GetExitCodeProcess`.

## What the sweep found

| | |
|---|---|
| files in `debug/` that touch a project | 30 |
| that opened without any paired close | **2** — `audit038_closure_edges.py` (T090's) and `probe_adhoc_loss.py` (its sibling) |
| `run038_closure_census.py`, T090's other named driver | **already clean** — reaches a project only through `run_full_transfer` and `census.read_project`, both of which close in a `finally`. Its locks came from the audit driver sharing its default source. |
| readers that treated lock-file PRESENCE as "locked" | **2** — `_open_or_skip` (named) and `_live_project_or_skip` in `test_object_census.py:3928` (**not** named; found by the sweep) |

A test pins the class rather than the two files: no file in `debug/` may open a
project unless the same file also closes it, delegates to
`run_full_transfer`/`census.read_project`, or uses `source_readonly`.

## T103 — why (b), and why (c) applies to exactly one clause

The count moved 1949 → 1952 → **1953**, and the premise never stopped holding
for a moment. So the two claims in that test were separated, because they are
not the same kind of claim:

* **The premise** — the projects differ, both count nonzero, `Ngoreme FLEx`
  holds more `MoStemMsa` **and** more `PhPhoneme` — is asserted against
  whatever is on disk, every run. That honours the test comment's *"a moved
  file makes it MORE useful, not less"*, which is sound about the premise and
  only about the premise.
* **The exact counts** are asserted only against the bytes they were measured
  from. At unchanged bytes that is a real tripwire; at changed bytes it is a
  claim about a file that no longer exists.

Both readings are recorded, so the ledger is evidence rather than a pin. **1952
gets no row**: it was seen in a failure message with no digest captured, and a
count without the bytes it was counted from is what the ledger exists to stop.

### The half that makes a permissive gate safe

A gate that can stand down can be talked into standing down. An **offline**
test — it runs on a host with no FieldWorks — asserts that every ledger row
satisfies the premise, so a contradicting row cannot be appended to buy green
and the block cannot become a no-op. And a run where **both** projects drift
off the ledger **fails**, because a run that checked no exact count anywhere
must not read as green.

| forgery | result |
|---|---|
| row → `(9999, 41)` at the **unchanged** digest | **FAILS**, naming the same-bytes contradiction |
| digest key corrupted, project drifts off the ledger | **PASSES**, premise asserted, prints the exact line to append |
| `Ngoreme` row → `(9999, 99)`, contradicting the premise | offline test **FAILS** at `assert 1949 > 9999` |

## Suites

| suite | after T100/T101 | after T090/T103 |
|---|---|---|
| `tests/unit` | 3587 passed, 79 skipped, 14 xfailed | **3587 passed, 79 skipped, 14 xfailed** (unmoved) |
| `tests/integration` | 448 passed, **1 failed**, 75 skipped | **480 passed, 0 failed, 75 skipped** |

The `+32` is fully accounted for: **30** new tests in `test_038_stale_lock.py`,
**+1** from the T103 test splitting into a live half and an offline half, and
**+1** from the pre-existing `Ngoreme FLEx` failure resolving.

**`skipped` is unchanged at 75**, and that is worth stating plainly rather than
claiming T090 unblocked coverage: there were no stale locks on the six projects
that module walks when the suite ran. T090's effect was measured by *planting*
a lock, not by waiting for one.

Still run separately — a combined invocation fails collection on the
`test_038_process_rules.py` basename collision.

## Live-project discipline

Every open was **read-only**, and each path proves its own read-only-ness by
digesting the `.fwdata` before and after. Opened: `Ejagham Mini`, `Mbugwe
LizzieHC practice`, `Ejagham W Mini`, `Ejagham W Target`, `Ngoreme`, `Ngoreme
Target`, `Ngoreme FLEx`. Nothing was restored, no target was bound, nothing was
written. `Esperanto` and `Target` were not opened.

The two locks planted on `Ejagham Mini` were planted by this work and removed
by it — one of them by flexicon itself, on close. The **four pre-existing stale
locks** on disk (`Ejagham Full GT-Test`, `Ejagham Full`, `Esperanto`, `Hdi`,
from three dead PIDs) were **left in place**: the classifier reads all four
correctly, so they cost nothing, and deleting other people's lock files is not
this task's business. This session left no new ones — which is half (a)
working.

## Commits

| repo | commit | subject |
|---|---|---|
| feature | `f0801a9` | `fix(038): T090/T103 -- a lock file is a claim about a process, not a file` |
| `main` | `e9437d8` | `docs(038): T090 and T103 closed -- a lock is a claim about a process` |

The branch still has not been merged to `main`; `git merge main` conflicts in
`tests/integration/harness/full_run.py` because `main` has moved on with other
features' code since the merge-base at `4a319af`. That merge is **T085's**
business, and this pass adds to it — `full_run.py` is one of the files it
touched.

## Not done, deliberately

* **T064** — still parked. Owned by T076/T077. Fourth pass to skip it on
  purpose, and that is now the loudest thing in the queue.
* **T102** — still filed, not fixed. Needs three live driver re-runs.
* **T092** — `preview.plan_match_decision` still has no production caller.

## Suggested next pass

**T076 → T077.** It is what finally moves T064's P4 (`MoAffixProcess`
18 / 12 / −6 → MATCHED), and T064 has now been stepped over four times, which
is the point at which "deliberately parked" starts to look like "quietly
dropped". Live work is also cheaper than it was: a driver run no longer poisons
the next suite run.

Alternatives, unchanged in priority: **T074** (affix-to-template-column
linking, measured baseline 0 of 110 linked and 0 reported), or **T092**, which
T091 left as a decide-on-the-evidence question — whether the plan-time seam
earns its callers or should be deleted.
