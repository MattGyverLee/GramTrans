# Contract: Sweep CLI Surface

**Feature**: `035-fullsweep-fidelity`
**Entry point**: `debug/run_fullcopy_sweep.py` (thin CLI over `debug/fullsweep/`)
**Baseline**: the surface already implemented at commit 8c72bdc, extended here

Existing flags keep their exact spellings; nothing below renames one. New flags
are marked **NEW**.

## Global options

| Flag | Type | Default | Notes |
|---|---|---|---|
| `--projects-root` | path | `C:\ProgramData\SIL\FieldWorks\Projects` | The single projects-location authority; must be the same one the host data layer uses when resolving a project by name |
| `--artifacts-dir` | path | see below | Per-run output |
| `--runtime-dir` | path | `scratchpad/035_sweep` | Ephemeral coordination state; lives outside the projects collection so a restore can never remove it (FR-034) |
| `--allowlist` | str... | the anchored write-target pattern | The write-target name allowlist. Empty or absent raises; it never degrades to permitting anything |
| `--contracts-dir` | path | `specs/035-fullsweep-fidelity/contracts` | **NEW** Where the tracked rosters, allowlist and capability fingerprint are read from |
| `--ledger` | path | `specs/035-fullsweep-fidelity/ledger.json` | **NEW** The tracked per-project status ledger |

**Changed default.** `--artifacts-dir` moves from
`specs/035-fullsweep-fidelity/artifacts` to `scratchpad/035_sweep/artifacts`
(research D-10): per-run result artifacts are evidence, not reviewed source.
What stays tracked is the driver, the rosters, the allowlist, the capability
fingerprint, the negative-control artifact and the ledger -- exactly what FR-149
names.

## Subcommands

### `list` -- enumerate the corpus (read-only)

Emits the derived corpus and the exclusion record. Every directory examined and
not admitted appears with its reason, so the source count is reconstructable from
the output alone with no hardcoded list (SC-001). Opens nothing.

| Flag | Notes |
|---|---|
| `--json` | Machine-readable enumeration |
| `--axes` | **NEW** Include the three measured coverage axes per project |

### `survey` -- **NEW**, the read-only three-axis survey

Opens every source read-only and measures the three axes. Obeys the Group B
write-safety requirements in full, because it opens every source in the corpus
(FR-192). Writes per-project survey JSON; never writes to a source.

| Flag | Notes |
|---|---|
| `--out` | Survey output directory (default `scratchpad/prescan_results`) |
| `--only` | Restrict to named projects, for a re-survey |

### `preflight` -- **NEW**, the capability check

Introspects the dependency against the pinned fingerprint and exits. Touches no
database, performs no restore and no write (SC-008). Exit 0 on match, 6 with a
field-by-field diff on mismatch.

### `project` -- worker mode, one project

| Flag | Required | Notes |
|---|---|---|
| `--source` | yes | |
| `--target` | yes | Must satisfy the anchored pattern at both the restore and pre-write boundaries |
| `--backup` | no | Pinned baseline archive |
| `--baseline-sha256` | **NEW**, yes with `--backup` | A run that cannot name and hash its baseline does not start; there is no newest-archive glob fallback |
| `--intent` | yes | `baseline` or `gate` |
| `--exclude-categories` | **NEW**, yes | Explicit, possibly empty. Never a default argument. A non-empty value forces `COVERAGE_REDUCED` |
| `--diagnostic-level` | **NEW**, yes | Set explicitly and recorded; never `setdefault` from the environment |

### `batch` -- driver mode, admit and run one batch

| Flag | Default | Notes |
|---|---|---|
| `--batch-size` | 3 | Spec range is 3 to 5 |
| `--workers` | 1 | Above 1 requires a present, valid concurrency-trial artifact (SC-012) |
| `--canary` | first canary project | Included in every batch regardless of ledger status (SC-011) |
| `--intent` | required | `baseline` or `gate` |
| `--scope-from` | **NEW** | Changed files; the re-run scope is derived from their transitive importers. A derivation that cannot prove narrowness yields the full corpus (SC-013) |

### `negative-controls` -- **NEW**

Runs the seeded-defect suite and writes the durable negative-control artifact,
stamping each guard's module content hash.

### `report` -- **NEW**

Aggregates per-project artifacts into the corpus verdict. Exits with the most
severe verdict's code (FR-113). Refuses to issue a corpus-level fidelity claim
from artifacts spanning more than one revision pair (SC-014) or from any artifact
recording the `BASELINE` intent (SC-016).

## Value conventions

- **Run intent.** The CLI accepts `baseline` / `gate` lowercase; the artifact
  records `BASELINE` / `GATE` uppercase. `debug/fullsweep/artifact.py` performs
  the normalization in one place, and a test pins both spellings.
- **Ledger status.** `pending`, `running`, `passed`, `failed`, `skipped`. Derived
  from artifact presence and content; never hand-set (S-63).
- **Source fingerprint verdicts.** `UNCHANGED`, `MIGRATION_FINDING`,
  `UNEXPLAINED_WRITE_ABORT`, `HASH_ONLY_CHANGE_ABORT`,
  `SHARING_SETTINGS_CHANGED_ABORT`, `SOURCE_DATA_FILE_MISSING_ABORT`. These are
  already implemented at 8c72bdc and are unchanged. `MIGRATION_FINDING` requires
  an observed increase in the data-model version (FR-022, SC-002).

## Exit codes

The process exit code is always the `exit_code` of the most severe verdict
reached, per `verdict-exit-model.md`. There is no separate CLI-usage exit code
space: an argument error raises before any verdict exists and exits 5
(`HARNESS_ERROR`), since a run that could not be configured measured nothing.

## Invariants any caller may rely on

1. No write is ever attempted against a name failing the anchored pattern, at
   either boundary (SC-003).
2. The preflight runs, and may refuse, before any restore or write (SC-008).
3. Every project reaches a terminal verdict or an explicit exclusion record;
   neither a silent absence nor a bare `return` without an artifact is possible
   (SC-006, S-12).
4. The artifact is flushed after every phase, so a crash leaves a partial
   artifact naming the last completed phase (SC-009).
5. A source is never written to, never unlocked, and never repaired.
