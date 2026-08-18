# Quickstart: Full-Corpus Double-Move Fidelity Sweep

**Feature**: `035-fullsweep-fidelity` | **Date**: 2026-08-18

How to run the sweep, and — more importantly — how to read what it tells you.
The whole point of this instrument is that a green result means something; this
page is where you learn what each colour of green and red actually claims.

Console output is plain ASCII: `[OK]`, `[FAIL]`, `[WARN]`, `[INFO]`, and `-`
bullets. No emoji, no box-drawing.

---

## 0. Preconditions

```powershell
python -c "import flexicon; print(flexicon.__file__)"   # must NOT be site-packages
pip install -e D:/Github/_Projects/_LEX/flexicon        # if it is
```

The sweep refuses to start unless:

- flexicon satisfies the pinned capability fingerprint by **behavioral
  introspection**, not by version string. A mismatch exits `6`
  (`PREFLIGHT_MISMATCH`) with a field-by-field diff, **before any restore or any
  write**.
- Every write target it intends to claim matches the anchored target-name
  pattern and appears nowhere in the frozen source manifest.

There is no `--force`, no `--best-effort`, and no runtime path selection that
routes around a preflight mismatch. Those are forbidden by FR-132 and FR-133,
and their absence is deliberate.

---

## 1. See what the corpus is, without touching anything

```powershell
python debug/run_fullcopy_sweep.py list
```

Prints every directory examined beneath the projects root and, for each, whether
it was admitted as a source or excluded and why (`no_fwdata`,
`target_name_pattern`, `empty_shell`, `not_a_project`). Nothing is opened.

The exclusion record matters: an empty shell directory whose name differs from a
real project only in spacing has already been mistaken for a real project in this
repo. `Mbugwe Lizzie HCPractice` is that shell; `Mbugwe LizzieHC practice` is the
real project. The enumeration is by disk contents, never by name.

---

## 2. Run one project

```powershell
python debug/run_fullcopy_sweep.py project "Ejagham Mini" --intent BASELINE
```

What happens, in order — and the artifact is flushed after **every** one of these
phases, so a crash leaves partial evidence rather than none:

```
restore -> transfer_1 -> census_1 -> transfer_2 -> census_2 -> restore_final
```

The source is fingerprinted before and after. An unexplained fingerprint delta on
a source aborts the **entire run**, not just this project.

`--intent` is required and has no default. Pass `BASELINE` while you are still
finding defects; pass `GATE` only for a run you intend to count as evidence. A
`BASELINE` artifact is never admissible toward the corpus-wide fidelity claim, no
matter how clean it is.

---

## 3. Run a batch

```powershell
python debug/run_fullcopy_sweep.py batch --size 4 --intent BASELINE
```

Batches are 3 to 5 projects with the canary in every one. The run **stops after
each batch** for analysis; only failures within a completed batch are re-run. A
batch is not complete, and the next batch will not start, until every member has
a durable artifact.

Batch 1's composition is fixed: the three pilot projects.

---

## 4. Read the result

### The verdict line

```
[FAIL] Ejagham Mini  VACUOUS  (exit 4)  guard NO-ENGINE-BUG-AS-LOSS: not-evaluated
```

Ten verdicts, exactly two of which are success. See
[contracts/verdict-exit-model.md](./contracts/verdict-exit-model.md) for the full table. The three
you will meet most:

- **`CLEAN_PASS` (0)** — zero loss, zero extras, all fifteen guards `pass`, no
  allowlist entry consumed. This is the only unqualified green.
- **`PASS_WITH_ALLOWLIST` (0)** — green, but it forgave something. The artifact
  names every entry it consumed, the count it matched, and its remaining headroom.
  A passing result always discloses exactly what it forgave.
- **`VACUOUS` (4)** — the run proved nothing. Either the first transfer produced
  no measurable change, or no comparisons were performed, or some guard could not
  be evaluated. **`VACUOUS` is not a milder failure than `UNEXPLAINED_LOSS`; it is
  a worse one**, because it means the numbers on the page are not evidence.

### Why the severity order is not the exit-code order

Corpus status is the single most severe per-project verdict, under a **published
ordering that is deliberately not the exit-code integer**:

```
HARNESS_ERROR > PREFLIGHT_MISMATCH > ALLOWLIST_INVALID > VACUOUS > INCOMPLETE
  > UNEXPLAINED_LOSS > NON_IDEMPOTENT > COVERAGE_REDUCED
  > PASS_WITH_ALLOWLIST > CLEAN_PASS
```

"The measurement cannot be trusted" outranks "the measurement is trustworthy and
reports loss". An unexplained-loss report is actionable; a harness error means the
loss figure in front of you came out of a broken instrument. Sorting by exit code
would send you chasing that figure.

### The three things a reader must not misread

1. **Zero mismatches is not a pass.** The artifact keeps
   `attempted_and_clean` and `never_attempted` as separate, separately counted
   buckets. A class in `never_attempted` reports `NOT-EVALUATED`.
2. **Appendix, stratum, and one phonological-rule subclass exist in NO project on
   this machine.** They will always report `NOT-EVALUATED` until a project
   carrying them appears. Any run reporting them clean is a defect in the sweep.
3. **A reduced-coverage run is not a full-coverage run.** Any excluded category
   forces `COVERAGE_REDUCED`, and the excluded set is an explicit recorded field —
   never an invisible default argument.

### Where the evidence lives

- Per-project artifacts and worker logs: `scratchpad/035_sweep/` (untracked).
- Rosters, allowlist, capability fingerprint, coverage floor, and the
  negative-control artifact: `specs/035-fullsweep-fidelity/contracts/` (tracked,
  reviewed as source).
- Per-project standing: `specs/035-fullsweep-fidelity/ledger.json` (tracked).

A verdict produced by an untracked driver is not admissible evidence. That is why
the sweep stamps its own revision and dirty-tree flag onto every artifact.

---

## 5. When a run fails, in the order worth checking

| Verdict | First thing to look at |
|---|---|
| `PREFLIGHT_MISMATCH` | The diff block. flexicon's surface moved; the fingerprint is a fact, not a preference. |
| `ALLOWLIST_INVALID` | An entry expired, its issue closed, it went stale over two runs, or a cap was breached. Fix the entry or the defect — not the cap. |
| `VACUOUS` | Which guard returned `not-evaluated`. If it is a guard you just edited, its negative control is stale: re-run the control in the same change. |
| `HARNESS_ERROR` | The `phase` field. A failure in one phase is never reported as a whole-project failure. |
| `UNEXPLAINED_LOSS` | The `findings` list. Every finding carries the concrete source value, the concrete target value, and the real class/category/field. |
| `INCOMPLETE` | Which corpus project has no artifact. Any single `INCOMPLETE` forbids overall success even if everything that ran was clean. |

---

## 6. Adding an allowlist entry (read this before you do)

The allowlist is capped at 25 entries, and at 1% of any one project's in-scope
source objects. It is not a place to put things. Every entry needs a stable id, an
owner, an **open** tracking issue, exact project/class/field, an **exact-match**
reason string (no wildcards), a hard cap, a first-observed date, an expiry no more
than 120 days later, and a written justification.

Two entries will never be accepted, however you write them:

- A reason matching the engine-bug signature roster. This includes any reason that
  references an internal task, ticket, issue, probe, or TODO identifier — that is a
  developer note leaking into a user-facing string, and it is an engine bug, not an
  accepted loss.
- A second instance of a tool-owned-identity class. More than one is never expected.

If the justification is that a dependency capability is missing, name that
capability's identifier on the entry. The entry then dies the moment the preflight
reports that capability present — before its declared expiry, and regardless of
whether it still matches losses.

---

## 7. The uniform final sweep

The corpus-wide fidelity claim is admissible on exactly one thing: **one clean
full sweep in which every project passed at the same frozen driver-and-dependency
revision pair, with every per-project artifact recording intent `GATE` and its own
axis coverage.**

```powershell
python debug/run_fullcopy_sweep.py sweep --intent GATE
```

Passing results assembled across differing revision pairs do not satisfy it,
however green each looks on its own. Scope-based re-run narrowing is an
optimization for deciding what to re-run between batches; a mis-scoped derivation
can cost extra time but can never corrupt the final claim, because the claim
depends only on that one uniform sweep.

---

## 8. Running the offline tests

```powershell
python -m pytest tests/unit/test_035_*.py -q
```

These need no FLEx project and no live database. They cover the guard registry's
completeness, the verdict severity ordering and exit-code map, allowlist
validation, comparator classification, three-axis selection, and the seeded-defect
negative controls.

The negative controls are the reason a guard edit and its control re-run must land
in the same change: each control records a content hash of its guard's own module,
and a guard whose hash moved without a fresh control reports `not-evaluated` —
which makes the whole run `VACUOUS`. That is the mechanism working, not a
nuisance.
