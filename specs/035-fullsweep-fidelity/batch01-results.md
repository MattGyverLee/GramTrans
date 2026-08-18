# Batch 1 — measured result (T035)

**Run**: 2026-08-19, `--intent baseline`, `--workers 1`, `--exclude-categories ''`,
`--diagnostic-level verbose`
**Composition**: explicit (`--only`), FR-160's three pilots — Ejagham Mini,
Esperanto, Mbugwe LizzieHC practice
**Target**: `Target`, restored before and after each project from the pinned
baseline `backups/Target 2026-07-06 0218.fwbackup`,
sha256 `41bc18b3f1580f147d5788022d9e625068349f486cd0831eda038720f8bf0995`
**Raw artifacts**: `scratchpad/035_sweep/batch01/{Ejagham Mini,Esperanto,Mbugwe LizzieHC practice}.json`
**Code revision**: gramtrans `88c2632` (dirty), flexicon `74bc997` (dirty)

This is the **first live exercise of the real (non-SKIPPED) `run_one_project`
path**. Every prior green was a harness test.

---

## 1. What the run proves about the harness

All three projects completed all seven phases —
`restore_initial → census_before → first_transfer → census_after_first →
second_transfer → census_after_second → restore_final` — with:

| Safety property | Result |
|---|---|
| Capability preflight vs pinned fingerprint | `MATCH`, exit 0 |
| Evidence base tracked (FR-149, driver + capability) | passed before any work |
| Concurrency gate (FR-032), workers=1 | satisfied |
| Distinct target pool vs frozen sources | asserted |
| Source fingerprint before == after (all 3) | `UNCHANGED` |
| Final restore from pinned SHA (all 3) | `Target`, 12 members, containment proven |
| Sources written to | none |

The write-safety and provenance spine works live. Nothing was damaged.

---

## 2. Per-project verdicts

| Project | Verdict | Exit | Phases | Drops (1st) | Drops (2nd) | Findings |
|---|---|---|---|---|---|---|
| Ejagham Mini | `VACUOUS` | 4 | 7/7 | 210 | 0 | 11,148 |
| Esperanto | `VACUOUS` | 4 | 7/7 | 27,929 | 27,929 | 519,277 |
| Mbugwe LizzieHC practice | `VACUOUS` | 4 | 7/7 | 879 | 40 | 16,503 |

Batch driver exit 1; it stopped for analysis before admitting a further batch
(FR-153), as designed.

---

## 3. FR-161 acceptance criterion — NOT met

FR-161's figures are Esperanto's historical pilot data (29,211 recorded drops).
Measured against it:

### 3a. The two "dominant classes must be exactly zero" targets

| Class | Historical | Measured | FR-161 |
|---|---|---|---|
| `alignment token had no copied target referent` | 27,844 | **27,844** | **FAIL** — required 0, unchanged |
| `paragraph create failed` (parameter error) | 1,207 | **absent (0)** | **PASS** |

### 3b. The named residual list (expected 160 across five categories)

| Residual category | Expected | Measured | Status |
|---|---|---|---|
| shared-default divergence | 109 | 72 | reduced by 37, does not match |
| translation-field API-misuse | 37 | absent | gone |
| writing-system / custom-field absence in a configuration view | 11 | 11 (`fr` 5, `eo` 4, custom field `Summary Definition` 2) | **exact match** |
| unmappable writing system on a word-analysis gloss | 2 | 2 | **exact match** |
| text creation failure | 1 | absent | gone |
| **total residual** | **160** | **85** | |

### 3c. The reconciliation is exact

```
historical 29,211
  - 1,207  paragraph create failed        -> fixed
  -    37  translation-field API-misuse   -> fixed
  -     1  text creation failure          -> fixed
  -    37  shared-default 109 -> 72       -> reduced
  ---------
  = 27,929  measured
```

Every one of the 1,282 removed drops is accounted for. The residual list is not
drifting; four of its five categories moved exactly as recorded or vanished. The
single unmoved figure is the largest one.

**Verdict on T035: the run is done, the expectation is not met.** The primary
zero-target — `alignment token had no copied target referent` — measures exactly
its historical 27,844. T035 must stay unchecked.

---

## 4. Blocking finding: T035 cannot produce a non-VACUOUS verdict as ordered

All **15 guards** on all three projects report `not-evaluated`
("cannot be evaluated: ... was not measured"), and **100% of findings** on all
three projects carry the verdict `NOT_YET_CLASSIFIED_MISSING_FROM_TARGET`
(11,148 / 519,277 / 16,503 — every single one).

The censuses *were* measured (Ejagham Mini: 35 classes before, 55 after) and the
drop reasons *were* recorded. What is missing is the classification layer that
turns those measurements into guard inputs — which is **T036–T043 (US2)**,
ordered *after* T035 in tasks.md.

Per the spec's own severity ordering, `VACUOUS` outranks `UNEXPLAINED_LOSS`
because the numbers are not evidence. So the harness is behaving correctly: it
refuses to certify a measurement whose classifier does not exist yet.

**This is a dependency inversion in tasks.md.** T035 as written can only ever
return `VACUOUS`. The pilot *run* is worth having now — it produced the
reconciliation in §3c and proved the live path — but T035's acceptance criterion
cannot be evaluated until the US2 classifier lands, at which point batch 1 must
be re-run.

### 4a. Addendum (same day): the deeper cause is emptier than that

Investigating US2 found a simpler and more consequential reason the guards had
nothing to report. `run_one_project` calls:

```python
guard_results = run_all_guards(RunContext(project=source_name))
```

**Positionally empty.** Every `RunContext` measurement field defaults to `None`,
and a `None` input is exactly what makes a guard return `not-evaluated` — by
design, per that dataclass's own docstring, because an empty container would let
a guard "report all-zeros and pass a project it never opened". FR-109 then turns
any single `not-evaluated` into `VACUOUS`.

So the run reports `VACUOUS` **regardless of how much it measured**. And it
measured plenty: the census triple, the written-class delta, idempotency, the
coverage categories, and 210 / 27,929 / 879 drop reasons — none of which reached
a single guard. The in-code comment above that call still explains the `VACUOUS`
as "no guard in the registry has real pass/fail logic yet (Phase 2
taxonomy-spine scope, T011-T014)", which T033 made stale when it gave all fifteen
guards real logic.

The §4 ordering inversion is still real — the field plane genuinely did not exist
yet. But it was not the binding constraint. Even a fully built US2 would have
returned `VACUOUS` while the context stayed empty. Recorded as **T045a**, which
no task previously covered, and which must land before T035 is re-run.

---

---

## 5. Secondary findings

1. **Esperanto's second transfer re-drops identically**: `drops[second]` == 
   `drops[first]` == 27,929, class for class. Nothing from the alignment-token
   class persists between transfers, consistent with the class's own reason
   string. Contrast Ejagham Mini (210 → 0, clean) and Mbugwe (879 → 40).
2. **Mbugwe's 40-drop residual is structural**, not transient: eight classes of
   5 each — four absent custom fields (`Diminutive PL`, `Diminutive SG`,
   `OwningEntry`, `Plural2`) and four absent writing systems (`mgz`,
   `mgz-fonipa-x-emic`, `mgz-fonipa-x-etic`, `swh`). Three custom fields present
   in the first transfer's drops (`Plural`, `ProtoBantu`, `Speaker`) are absent
   from the second.
3. **FR-149 trackedness gap, again**: batch 1's artifacts live in
   `scratchpad/035_sweep/batch01/`, and `.gitignore:117` ignores `scratchpad/`.
   `assert_evidence_base_tracked()` currently checks only the driver and the
   capability contract, so it did not catch this. A `gate` run whose evidence
   sits there would be inadmissible. This file is the tracked record; the
   artifact location itself still needs fixing before T049/T050.
4. **`IAnalysis` has no `SpellingStatus`**: swallowed `AttributeError`, repeated
   ~23x per project in `Lib/texts.py` `texts.apply`. Silently absorbed today.
5. **Legacy-target GUID warning fires on a freshly restored target**: "1 of 3
   analyses were matched by STRUCTURAL fingerprint, not by source GUID (0 matched
   by GUID)". The warning's own text says a non-zero count on a *fresh restored
   target* is "a regression, not legacy data" — and this target was restored from
   the pinned baseline moments earlier. Worth checking against
   `specs/033-guid-preservation/TODO.md`.
6. **`Sldr.Initialize failed (already initialized?)`** on every project; benign
   but noisy.
