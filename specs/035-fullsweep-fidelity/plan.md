# Implementation Plan: Full-Corpus Double-Move Fidelity Sweep

**Feature**: `035-fullsweep-fidelity`
**Branch**: `035-fullsweep-fidelity`
**Date**: 2026-08-18
**Spec**: [spec.md](spec.md) -- RATIFIED at FR-001..FR-193 / SC-001..SC-017
**Research**: [research.md](research.md) -- decisions D-01..D-12
**Data model**: [data-model.md](data-model.md)
**Contracts**: [contracts/](contracts/)

## Summary

Four existing fidelity instruments are replaced by one tracked sweep that opens
every transferable FLEx project on this machine exactly once per corpus pass,
transfers its grammar into a disposable target twice, and generically compares
every field of every object it touched against the source -- failing loudly, with
a distinct exit status, whenever it finds loss it cannot account for, cannot prove
it measured anything, or cannot prove it covered what it claims. The work grows
the existing tracked skeleton `debug/run_fullcopy_sweep.py` (commit 8c72bdc,
Groups A/B/C/D/K/L already implemented) into a package `debug/fullsweep/`, filling
in the comparator, the fifteen vacuity guards, the verdict model, the loss
allowlist, the capability preflight, the coverage floor, the negative controls,
the identity-substitution rules, and the three-axis corpus survey.

No new runtime dependency is introduced. The sweep drives the shipped engine
through the existing `Lib/preview.py` + `Lib/transfer.py` split via
`tests/integration/harness/full_run.py`, and reads fields through flexicon's
native `GetSyncableProperties` surface at the `pyflexicon>=4.3.1` floor already
pinned in `pyproject.toml`. Everything the sweep adds is offline-testable except
the live measurements the spec explicitly gates.

## Project Structure

```
debug/
  run_fullcopy_sweep.py        # thin CLI entry point (exists; re-exports package)
  fullsweep/                   # NEW tracked package
    __init__.py                # public surface, version/SHA stamping
    corpus.py                  # Group A: runtime enumeration + exclusion record
    safety.py                  # Group B: allowlist choke point, fingerprints, claims
    pool.py                    # Group C: worker pool, memory admission, concurrency gate
    moves.py                   # Group D: double-move loop, written-class derivation
    census.py                  # Group E: generic per-object field census
    compare.py                 # Group E: comparator + difference classification
    guards.py                  # Group F: the 15-guard registry
    verdict.py                 # Group G: verdict taxonomy, severity order, exit codes
    allowlist.py               # Group H: loss allowlist load/validate/match/cap
    preflight.py               # Group I: capability fingerprint introspection
    coverage.py                # Group J: coverage floor, NOT-EVALUATED accounting
    artifact.py                # Group K: per-project artifact + provenance stamping
    batch.py                   # Group L: batching, gating, scope derivation, ledger
    baseline.py                # Group M: pinned baseline identity + containment
    errors.py                  # Group N: failure taxonomy + cross-worker abort flag
    identity.py                # Group P: identity substitution, natural-key roster
    select.py                  # Group Q: three-axis ordering and batch composition
  prescan_type_coverage.py     # EXTEND: emit ws_breadth + same_class_depth axes
  audit_guid_preservation.py   # PROMOTE: inventory_all kept as library; verdict retired
  run_fullsweep_verify.py      # EXTEND: its domain diff seeds compare.py; then retired

src/gramtrans/Lib/
  preview.py                   # unchanged -- plan builder (Principle III)
  transfer.py                  # unchanged -- plan executor (Principle III)

tests/
  integration/harness/full_run.py    # EXTEND: explicit exclude arg; delete reopen_and_count
  unit/test_035_sweep_safety.py      # exists (20 offline tests)
  unit/test_035_guards.py            # NEW: one test per guard, pass/fail/not-evaluated
  unit/test_035_verdict_order.py     # NEW: taxonomy, severity order, exit-code mapping
  unit/test_035_allowlist.py         # NEW: validity, caps, expiry, staleness, FR-182
  unit/test_035_compare.py           # NEW: difference classification, EXPECTED_DIVERGENT
  unit/test_035_negative_controls.py # NEW: seeded defects; writes the durable artifact
  unit/test_035_selection.py         # NEW: three-axis ordering, subset NOT-EVALUATED
  unit/test_035_silence_ledger.py    # NEW: the 65-row crosswalk is complete and live

specs/035-fullsweep-fidelity/
  contracts/                   # tracked inputs (rosters, fingerprint, schemas)
  ledger.json                  # tracked per-project status ledger

scratchpad/035_sweep/          # untracked run outputs (artifacts, logs, manifests)
scratchpad/prescan_results/    # exists: 84 per-project surveys + _enumeration.json
```

**Structure Decision**: the sweep is a tracked test instrument under `debug/`,
not part of the shipped FlexTools module. `debug/` is already version-controlled,
already on the driver's `sys.path` bootstrap, and already hosts the two modules
the skeleton imports -- so promoting the single 1,300-line file into a package
there costs no import rewiring and keeps the shipped `src/gramtrans/Lib/` surface
untouched (research D-01).

## Constitution Check

Constitution **v8.0.0** (ratified 2026-06-15, last amended 2026-08-17). Note the
version: the dispatch brief for this step cites v5.1.0, which is superseded.
Principle III's Preview/Move clause survives unchanged in v8.0.0, and both
`Lib/preview.py` and `Lib/transfer.py` already exist in this tree.

| # | Principle | Assessment |
|---|---|---|
| I | FLEx Domain Fidelity (NON-NEGOTIABLE) | **PASS.** The feature exists to prove this principle holds. GUID-primary identity is the comparator's default basis; the Natural-Key Identity Roster (FR-185) is the narrow, git-tracked, per-class exception for classes where LCM does not make identity authoritative, and every substitution is counted on the artifact (FR-187). The sweep detects and reports only -- it never repairs a fidelity defect it finds. |
| II | FlexTools-Compatible Output, flexicon-Direct | **PASS.** The sweep adds nothing to the shipped module and introduces no runtime dependency. It imports flexicon directly (no adapter, no `flavors/`), reads fields through the native `GetSyncableProperties` surface, and pins that surface behaviorally in the preflight. LibLCM is not consumed; `flexlibs_stable` is present on the machine but unused. |
| III | Preview-Before-Mutate (NON-NEGOTIABLE) | **PASS.** The sweep never writes through a private path. Every write goes `build_full_selection` -> `Lib/preview.build_run_plan` -> `Lib/transfer.execute` via the integration harness, so it measures the engine users run. Preview remains the source of the plan whose conservation VG-06 checks (`plan.actions == added + skipped`). |
| IV | Phased Merge Discipline | **PASS.** Phase 0 additive semantics are what the sweep asserts; it introduces no merge sophistication. Where a later-phase behavior is absent, the coverage floor reports it `NOT-EVALUATED` rather than treating its absence as a clean result. |
| V | Referential Completeness | **PASS.** VG-04 total accounting and the inbound cross-reference closure of FR-186 are stronger checks of dependency-closure completeness than the principle requires: an object reachable from a transferred object but absent in the target lands in the `unaccounted` bucket and fails the run. |

Additional gates from the constitution's Development Workflow section:

- **No silent skips** -- satisfied by construction. Every skip becomes a counted,
  reasoned record; a skipped project still writes a `SKIPPED` artifact (S-12), and
  an uncounted skip trips the accessor-integrity guard.
- **Verification on a known pair** -- the first batch is the three known-good
  pilots, with the Ejagham Mini to Ejagham Full GT-Test pair among them (SC-005).
- **Preview engine first** -- already closed; `Lib/preview.py` and
  `Lib/transfer.py` exist.

**No violations. Complexity Tracking omitted.**

Re-checked after Phase 1 design: unchanged. The design adds no adapter layer, no
optional dependency, no second write path, and no hand-picked measurement set.

## Anti-Silence Acceptance Surface

The spec makes the 65-row silence ledger (`reviews/cycle1-qc.md` Section 1,
S-01 through S-65) an acceptance condition of this feature: every row must be
satisfied by the delivered sweep, or explicitly waived on the record here.

The row-by-row crosswalk is
[contracts/silence-ledger-crosswalk.md](contracts/silence-ledger-crosswalk.md),
which maps each S-row to the module that satisfies it and the test that proves it.

**Waivers: none.** All 65 rows are satisfied. S-60 is the ledger's one "(GOOD)"
row -- source open raising an actionable `RuntimeError` -- and is satisfied by
adoption: it becomes the house style for the whole package rather than an
exception within it.

## Implementation Phases

Phases are ordered by what unblocks what. Groups A/B/C/D/K/L already exist in the
skeleton and are refactored, not rebuilt.

### Phase 1 -- Package promotion and the taxonomy spine

Split `debug/run_fullcopy_sweep.py` into `debug/fullsweep/`, preserving the
existing CLI surface and keeping `test_035_sweep_safety.py` green unchanged.
Then land the three modules everything downstream depends on: `errors.py` (the
structured failure taxonomy with stable identity codes plus the
out-of-collection abort flag), `verdict.py` (the ten verdicts, the severity
order, the exit-code map), and `guards.py` (the registry with all fifteen guards
registered and every one returning `not-evaluated` until implemented).

This phase alone changes the driver's failure posture: with every guard
registered and unimplemented, the sweep reports `VACUOUS` -- the correct answer
for an instrument that cannot yet prove anything, and the thing none of the four
retired instruments ever said.

### Phase 2 -- The measurement core (Groups E, F, J)

`census.py` and `compare.py`: the generic per-object field census over
`GetSyncableProperties`, the per-class omitted-property set published on every
artifact, the difference classification, and the `EXPECTED_DIVERGENT` roster.
Then the fifteen guards become real, and `coverage.py` lands the git-tracked
coverage floor so that appendix, stratum, and the absent phonological-rule
subclass report `NOT-EVALUATED` -- never clean.

### Phase 3 -- The gates around the measurement (Groups H, I, M, N, P)

`preflight.py` (capability fingerprint, refusing before any restore or write),
`allowlist.py` (validity, caps, expiry, staleness, and FR-182's invalidation of
capability-justified entries once the capability appears), `baseline.py` (pinned
hash-identified baseline; no glob fallback), and `identity.py` (identity
substitution, the Natural-Key Identity Roster, per-class substitution counts).

### Phase 4 -- Corpus survey and three-axis selection (Group Q)

Extend `prescan_type_coverage.py` with the writing-system-breadth and
structural-depth axes, re-run the read-only survey over the corpus, and land
`select.py`. Selection retains each axis's **measured** maximum carrier; it does
not name projects. Every subset run records its per-axis maxima beside the
corpus's and reports `NOT-EVALUATED` for any claim whose axis it does not reach.

### Phase 5 -- Negative controls (Group O)

The seeded-defect suite, and the durable negative-control artifact whose
freshness is keyed to a content hash of each guard's own module. A guard whose
control is stale reports `not-evaluated`, which makes the run `VACUOUS`.

### Phase 6 -- Live gates and the batched corpus run (Group L)

In order: the concurrency trial that gates any worker count above 1; the census
cost run against the corpus's largest project; then batches of 3 to 5 projects
with the canary in every batch, each batch analyzed and fixed before the next is
admitted, and re-run scope derived mechanically from changed files' transitive
importers -- defaulting to the whole corpus whenever narrowness cannot be proven.
The feature is delivered only by a uniform final sweep at one frozen revision
pair, recording the `GATE` intent.

## Scheduled live measurements

These are the spec's three Open Questions, scheduled rather than assumed:

1. **Concurrency serialization** (gates FR-032) -- unmeasured. Until its artifact
   exists, worker count stays 1 and no estimate may presume otherwise.
2. **Census cost on the largest project** -- partially answered (~2,500 field
   reads in ~0.1 s on a live project). Every artifact records its own census cost
   regardless, so a pathological case is caught in flight.
3. **FR-162: does a diverged shared/default item leave the target link resolved,
   or silently unset?** 109 of the 160 residual pilot records. This is the first
   measurement the link census makes, in batch 1.

Plus one carried caveat now actionable: `reviews/cycle5-domain-identity.md` flags
identity rulings taken from documented LCM semantics because FLExToolsMCP was
unavailable in three of five review cycles. **FLExToolsMCP is reachable now**
(server 2.9.1; flexicon 4.3.1 exact-match index; LibLCM 11.0.0), so those flagged
live-check points become an explicit verification task rather than a standing
caveat.

## Risks

- **The corpus moves under the run.** Enumeration is at runtime and never
  hardcoded (SC-001), so drift is tolerated -- but a project added mid-batch is
  outside that batch's frozen manifest and must land in the exclusion record, not
  vanish from both.
- **Live source locks.** Two sources were locked by a running process at planning
  time. FR-040 requires recording such locks and never repairing them; with a
  concurrent session on this machine this is the normal case, not the edge.
- **The provisional memory slope.** The ~190 MB floor plus ~1.9 MB per MB of data
  file is a one-point regression from a single large project. It is adequate for
  an admission check with reserve and inadequate as a budget; observed actuals
  must supersede it once recorded.
- **Comparator scope creep.** The census surface is whatever
  `GetSyncableProperties` exposes. If that set grows between runs, coverage
  shrinks relative to it silently -- which is why FR-066 requires the omitted set
  published per class on every artifact.
