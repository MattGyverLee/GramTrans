# Contracts: Full-Corpus Double-Move Fidelity Sweep

**Feature**: `035-fullsweep-fidelity`

Every identifier in these documents is **verbatim**. Do not rename, recase, or
pluralize a key, a guard name, a verdict token, or a CLI flag when implementing
against them -- those exact strings are the contract, and the unit tests assert on
them.

## Documents

| File | Covers | Primary consumer |
|---|---|---|
| [`guards.md`](guards.md) | The fifteen-guard registry, keyed by exact spec name; the FR-109 completeness meta-rule | `debug/fullsweep/guards.py` |
| [`verdict-exit-model.md`](verdict-exit-model.md) | The ten verdicts: machine token, human label, exit code, and the published severity ordering | `debug/fullsweep/verdict.py` |
| [`artifact-schema.md`](artifact-schema.md) | The per-project result artifact: phase vocabulary, required blocks, provenance stamping | `debug/fullsweep/artifact.py` |
| [`rosters.md`](rosters.md) | The tracked rosters, loss allowlist, capability fingerprint, and status ledger | `allowlist.py`, `identity.py`, `coverage.py`, `preflight.py`, `batch.py` |
| [`sweep-cli.md`](sweep-cli.md) | The CLI surface: global options, subcommands, value conventions, caller invariants | `debug/run_fullcopy_sweep.py` |
| [`silence-ledger-crosswalk.md`](silence-ledger-crosswalk.md) | The spec's Anti-Silence Acceptance Surface: S-01..S-65 mapped to module and test | `tests/unit/test_035_silence_ledger.py` |

## Tracked data files these contracts describe

These are populated during implementation, not at plan time. They live beside
this README and are reviewed as source, because FR-149 makes trackedness a
correctness property -- a verdict produced by an untracked driver, or against an
untracked roster, is not admissible evidence.

| File | Contract | Purpose |
|---|---|---|
| `expected-divergent.json` | `rosters.md` | Fields legitimately expected to differ; never reported as loss |
| `natural-key-identity.json` | `rosters.md` | Classes admitted to the FR-185 natural-key identity basis |
| `engine-bug-signatures.json` | `rosters.md` | Drop-reason signatures that mean an engine bug; never allowlistable |
| `coverage-floor.json` | `rosters.md` | Every in-scope class; absent ones report NOT-EVALUATED |
| `loss-allowlist.json` | `rosters.md` | Capped, expiring, exact-match loss exceptions |
| `flexicon-capability.json` | `rosters.md` | The pinned capability fingerprint the preflight checks |

`ledger.json` (the per-project status ledger) is also tracked, but sits one level
up at `specs/035-fullsweep-fidelity/ledger.json` because it is run state rather
than a reviewed input.

## Reading order

1. `verdict-exit-model.md` -- what the sweep can conclude, and what each
   conclusion costs at the exit code.
2. `guards.md` -- what has to be true for a conclusion to be reachable at all.
3. `artifact-schema.md` -- what a run must leave behind to have proved anything.
4. `rosters.md` -- the reviewed inputs that can soften a verdict, and the strict
   rules on when they may.
5. `sweep-cli.md` -- how to actually invoke it.
6. `silence-ledger-crosswalk.md` -- the acceptance surface the whole feature is
   measured against.

## The one rule behind all of them

None of these mechanisms may fail quietly. A guard that cannot be evaluated is a
failure, not a pass. A category with source objects but no comparisons is a
failure. A class absent from the corpus is NOT-EVALUATED, never clean. A loss is
either matched to a valid allowlist entry or it fails the run. There is no
verdict meaning "loss reported, review advisable, exit success" -- retiring that
verdict is why this feature exists.
