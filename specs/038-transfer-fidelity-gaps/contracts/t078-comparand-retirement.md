# The T078 comparand, retired per source — the ruling T129 (2) needs

**Date:** 2026-09-18
**Task:** T129 (feature 038, Phase 10 / US6), half **(2)**
**Status:** RULED — the T078 comparand is **RETIRED for `Ngoreme FLEx` and
`Mbugwe LizzieHC practice`** and **stays VALID for `Ejagham W Mini`**
**Measured on:** the committed census artifacts themselves, read-only. No
project was opened and nothing was written.

---

## 1. Why this document exists

T128 recorded that the mbugwe source project changed on disk between t126 and
t123c, and drew the consequence for one row. T129 (2) asks for the two things
that finding implies and T128 does not deliver — and it asks for one of them in
the imperative, because the assumption being retired is the same one that had
just produced confident wrong output:

> Ngoreme is unaffected ONLY IF its source hash is still on pin — **CHECK IT, do
> not assume it**, since that is the assumption this row exists to stop
> trusting.

Checked. **Ngoreme is not unaffected.** Its source moved three weeks before the
mbugwe drift was noticed, and every ngoreme `vs T078` section since has been
invalid.

## 2. The measurement

Method: read `$.projects.source.fwdata_sha256_after` out of every committed
`census-038-*.json`, order by `generated_at`, and compare each against the pin
recorded in the pair's T078 artifact. The digests are the drivers' own output;
nothing here re-measures a project.

### 2a. `Ejagham W Mini` — ON PIN throughout. **Comparand VALID.**

| artifact | generated | source sha256 |
|---|---|---|
| `census-038-ejagham-after.json` | 2026-08-21T17:27:56 | `5ad15c10…` |
| `census-038-t078-ejagham.json` | 2026-08-25T11:52:35 | `5ad15c10…` |
| `census-038-t124-ejagham.json` | 2026-08-27T08:47:50 | `5ad15c10…` |
| `census-038-t126-ejagham.json` | 2026-08-28T14:58:59 | `5ad15c10…` |

Unbroken from 2026-08-21 to 2026-08-28. This is the control, and it matters:
a check that fired on all three pairs could not distinguish "correctly refused"
from "refuses always".

### 2b. `Ngoreme FLEx` — MOVED between t124 and t126. **Comparand RETIRED.**

| artifact | generated | source sha256 | vs T078 |
|---|---|---|---|
| `census-038-t095-ngoreme.json` | 2026-08-24T14:28:32 | `838b7635…` | — |
| `census-038-t078-ngoreme.json` | 2026-08-25T11:52:57 | `838b7635…` | **the pin** |
| `census-038-t124-ngoreme.json` | 2026-08-27T08:41:07 | `838b7635…` | VALID |
| `census-038-t126-ngoreme.json` | 2026-08-28T15:01:51 | **`d0ab2c66…`** | **VOID** |
| `census-038-t123b-ngoreme.json` | 2026-08-28T16:58:49 | `d0ab2c66…` | **VOID** |
| `census-038-t123c-ngoreme.json` | 2026-09-18T12:12:30 | `d0ab2c66…` | **VOID** |
| `census-038-t123d-ngoreme.json` | 2026-09-18T13:13:33 | `d0ab2c66…` | **VOID** |
| `census-038-t123e-ngoreme.json` | 2026-09-18T13:37:25 | `d0ab2c66…` | **VOID** |

`838b7635…b23b607f` → `d0ab2c66…c149db`, between 2026-08-27 08:41 and
2026-08-28 15:01.

**This was already visible in a committed document and was read the other way
round.** `contracts/unreferenced-feature-constraint-ruling.md` (2026-08-28)
records ngoreme's source as `d0ab2c66…` and states, correctly, that all six of
its digests match the `census-038-t126-*` pins byte for byte. That ruling is
sound and is untouched here — it compares t126 against t126. What nobody did
was compare either against **T078**, which is the comparand the `vs T078`
section cites.

### 2c. `Mbugwe LizzieHC practice` — MOVED after t126. **Comparand RETIRED.**

| artifact | generated | source sha256 | vs T078 |
|---|---|---|---|
| `census-038-t078-mbugwe.json` | 2026-08-25T11:53:11 | `fb6aadab…` | **the pin** |
| `census-038-t124-mbugwe.json` | 2026-08-27T08:43:40 | `fb6aadab…` | VALID |
| `census-038-t126-mbugwe.json` | 2026-08-28T15:02:50 | `fb6aadab…` | VALID |
| `census-038-t123c-mbugwe.json` | 2026-09-18T12:14:35 | **`3fb29a29…`** | **VOID** |
| `census-038-t123d-mbugwe.json` | 2026-09-18T13:18:07 | `3fb29a29…` | **VOID** |

`fb6aadab…226c3161` → `3fb29a29…7cd5436d`, matching T128's on-disk mtime
evidence (2026-09-06 22:43) and its object-count reading (~23,760 → ~48,622).

## 3. The ruling

**The T078 comparand is RETIRED for ngoreme and mbugwe.** No later reader may
cite a `vs T078` section from the seven artifacts marked **VOID** above:

    recensus-038-t126-ngoreme.json     fixed=5   still=22   regressed=0
    recensus-038-t123b-ngoreme.json    fixed=6   still=21   regressed=0
    recensus-038-t123c-ngoreme.json    fixed=8   still=19   regressed=0
    recensus-038-t123d-ngoreme.json    fixed=8   still=19   regressed=0
    recensus-038-t123e-ngoreme.json    fixed=8   still=19   regressed=0
    recensus-038-t123c-mbugwe.json     fixed=6   still=16   regressed=1
    recensus-038-t123d-mbugwe.json     fixed=6   still=16   regressed=1

**Including — especially — the `fixed` entries.** T128 already drew this
conclusion for mbugwe ("every mbugwe `vs T078` verdict in t123c crosses that
source change, INCLUDING ITS SIX 'FIXED' ENTRIES"); it applies unchanged to
ngoreme's five tags, which T128 did not reach. A comparison across a changed
source measures source growth as well as this feature's work, in **both**
directions: the `regressed=1` on mbugwe is T128's `MoMorphAdhocProhib` row,
already shown to be source drift plus a genuine `-4`, and the `fixed` columns
are the same arithmetic run the other way.

**`Ejagham W Mini` keeps its comparand.** Its `vs T078` sections in
`recensus-038-t124-ejagham.json` and `recensus-038-t126-ejagham.json` are
valid as measured.

**Retired, not re-pinned.** Re-pinning requires a freshly measured baseline on
the current sources, which is a live restore-bounded transfer and therefore the
user's call, not the crew's. The next authorized re-census establishes that
baseline; until then, ngoreme and mbugwe have **no** historical comparand and
their `vs T078` sections are simply absent rather than wrong. Within-run
source → destination results are unaffected on every pair and every tag — both
sides of those are measured inside a single run — and they remain the evidence
T123(a) and T123(b) were closed on.

## 4. What enforces this, and what does not

**The ruling is not the mechanism.** `debug/run038_t124_recensus.py` now reads
the pin back out of the comparand artifact and compares it
(`_source_pin_status`), withholds the `fixed` / `still_short` / `regressed`
counts entirely when it does not match, names both hashes, and records
`vs_t078.refused: true` with a reason in the summary it writes. So a future run
against a moved source refuses by construction rather than by a reader
remembering this document. `tests/unit/test_038_t129_source_pin_enforced.py`
locks the three outcomes against the committed artifacts above.

**The counts are withheld, not annotated.** A number printed beside a warning
still gets quoted without it — that is not a hypothetical, it is what happened
to the `LexEntryType SHORTFALL -> MATCHED (net 0 -> 12)` reading that was
relayed and then retracted.

**This document deliberately contains no table the code reads.** The digests in
section 2 are a dated observation. Making them a hand-kept constant that the
driver consulted would recreate exactly the failure being retired: a second
place that can drift from the artifacts it claims to describe. The artifact is
the pin; the check reads the artifact.

## 5. Why this is a separate row from T128

T128's residual `-4` is a **transfer** defect and its acceptance is a
destination-side `MembersOC` GUID diff. This is an **instrument** defect and
its acceptance is that a moved source cannot produce a confident diff again. It
is the third instrument failure of the spurt — after file:line citations read
from the wrong tree, and a pinning test that SET the value it then asserted —
which is why the standing rules now cover the tools as well as the code:

> **An instrument that cannot report its own violated premise is the same
> failure class as a test that cannot fail.**
