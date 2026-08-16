# Data Model: Standalone Windows Application

**Feature**: 034-standalone-windows-app | **Date**: 2026-08-16

Six entities, all owned by the standalone shell. None of them enters the
transfer engine's data model — `RunContext`, `RunPlan`, `RunReport`,
`Selection`, `WSMapping` and `ImportResidueTag` are reused unchanged. The one
type that crosses the host boundary is `ConfirmationGate`, and it crosses as a
protocol, not as an import.

---

## ProjectChoice

A user's selection of one FLEx project for one role. Produced by the source
picker; the target side reuses the existing `Lib/api.TargetCandidate` rather
than duplicating it.

| Field | Type | Notes |
|---|---|---|
| `role` | `ProjectRole` | `SOURCE` or `TARGET` |
| `project_name` | `str` | as reported by `flexicon.AllProjectNames()` |
| `project_path` | `str` | on-disk directory; may be `""` when LCM does not surface it |
| `write_enabled` | `bool` | `False` for `SOURCE`, `True` for `TARGET` (FR-007) |

**Validation**
- `project_name` non-empty.
- The two choices in a run MUST NOT resolve to the same project, compared by
  `os.path.normcase`-normalised path first and by name second (FR-028). The
  existing `api.bind_target` already raises `SameProjectError` on both tests;
  the source picker additionally excludes nothing (it is chosen first), and the
  target picker excludes the source (existing behaviour of
  `list_target_candidates`).
- Nothing is pre-selected in either picker (FR-004): the model has no "default"
  or "last used" field, and the shell persists nothing between runs.

## HostSession

The shell's stand-in for a FlexTools run. One per application launch that
reaches project selection.

| Field | Type | Notes |
|---|---|---|
| `source_handle` | `FLExProject` | opened read-only |
| `target_handle` | `FLExProject \| None` | opened by the wizard's `bind_target`, write-enabled; the shell never opens it itself |
| `report_sink` | report protocol | `.Info` / `.Warning` / `.Error` / `.Blank` (FR-008) |
| `modify_allowed` | `bool` | **always `True`** (FR-011); not configurable |
| `log_path` | `str` | `%LOCALAPPDATA%\GramTrans\logs\gramtrans-<run_id>.log` |
| `run_id` | `str` | `GT-<YYYYmmdd-HHMMSS>`; same string as the residue tag and the log filename |
| `gate` | `ConfirmationGate` | the standalone's real gate |

**State transitions**

```
CREATED -> PREREQ_OK -> SOURCE_BOUND -> RUNNING -> RELEASED
   |           |             |            |
   +-----------+-------------+------------+--> FAILED -> RELEASED
```

**Invariants**
- `RELEASED` is reachable from every other state and is always reached
  (FR-013, SC-005): normal close, cancel, error, and failed run all release both
  handles. `MainFunction`'s existing `finally` closes the target;
  `HostSession` closes the source and calls `FLExCleanup()`.
- `modify_allowed` is a constant `True`, never read from a flag or argument
  (FR-011). There is no state in which it is `False`.
- `PREREQ_OK` requires the UI-toolkit assertion of FR-006 to have passed, so no
  state exists from which the module's no-interface fallback is reachable
  (FR-005).

## ConfirmationGate

The state guarding a Move, supplied by the host. This is the only new construct
that both hosts see, and it is a **structural protocol** — the wizard duck-types
it and never imports either implementation.

| Field | Type | Notes |
|---|---|---|
| `expected_name` | `str` | the target project's name |
| `typed_name` | `str` | what the user typed (standalone only) |
| `satisfied` | `bool` | derived: `typed_name == expected_name` exactly |

**Two implementations**

| | `AlwaysSatisfiedGate` (FlexTools, and the default) | `StandaloneConfirmationGate` |
|---|---|---|
| `confirm(target_name)` | returns `True` immediately, no UI | shows the FR-022 warning, returns `True` only on exact typed match |
| `finish_page_subtitle()` | today's literal, including the `Ctrl+Z` sentence | the irreversibility warning (FR-027 forbids the `Ctrl+Z` claim) |

**Validation**
- The name comparison is exact — case-sensitive, whitespace-significant. No
  trimming, no case folding (FR-023).
- The dialog's proceed control is disabled until `satisfied`, and no default
  button is bound to it, so Enter or a click-through cannot satisfy it (FR-023).
- `confirm` is called for Move only; Preview never reaches it (FR-024). Cancel
  returns `False`, leaving the wizard and all selections intact (FR-025).

## PrerequisiteReport

The self-check result: an ordered list of checks, each independently verdicted.

| Field | Type | Notes |
|---|---|---|
| `checks` | `list[PrerequisiteCheck]` | ordered as rendered |
| `overall` | `Verdict` | `FAIL` if any check fails, else `PASS` |
| `app_version` | `str` | from `_buildinfo` (FR-049) |
| `generated_at` | `str` | ISO timestamp |

`PrerequisiteCheck`: `name`, `detected` (`str`), `expected` (`str`),
`verdict` (`PASS` / `FAIL` / `UNKNOWN`), `remedy` (`str`, empty when PASS).

**The checks** (FR-036 enumerates the required set):

| name | detected from | expected |
|---|---|---|
| FieldWorks installed | `FLExGlobals.FWCodeDir` after init | a directory containing `FieldWorks.exe` |
| FieldWorks version | `FLExGlobals.FWShortVersion` / `FWLongVersion` | major version in `FW_SUPPORTED_VERSIONS` (`["9"]`) |
| FieldWorks code location | `FLExGlobals.FWCodeDir` | non-empty, exists |
| FieldWorks projects location | `FLExGlobals.FWProjectsDir` | non-empty, exists |
| Language-model runtime | `FLExInitialize()` outcome + `clr` import | initialises without raising |
| UI toolkit | `PyQt6.QtWidgets` import + `QApplication` construction | importable and constructible (FR-006) |
| Bundled component versions | `importlib.metadata` for pyflexicon, PyQt6, pythonnet, flextoolslib | present at the locked versions |
| Application version | `_buildinfo` | git describe + short SHA |
| Log location | `HostSession.log_path` | writable |

**Validation**
- Every check MUST read the **module attribute** (`flexicon.code.FLExGlobals.X`)
  post-init, never `flexicon.X` — the package-level re-export binds before
  initialisation and stays `None` (research R1). A check reading the re-export
  reports a false `FAIL` on a healthy machine.
- A failing check MUST carry a non-empty `remedy` (FR-036, SC-006).
- The whole report renders to one copyable block (FR-037).

## DependencyLock

The pinned set the artifact is built from. Not a runtime object — it exists as
`build/requirements.lock` and is *read back* by the smoke test to verify the
bundle.

| Field | Type | Notes |
|---|---|---|
| `component` | `str` | distribution name |
| `version` | `str` | exact, `==`-pinned |
| `hashes` | `list[str]` | `--generate-hashes` output |

**Validation**
- Pins live here and **only** here; `pyproject.toml` keeps its floors
  (FR-019/FR-041).
- Post-build verification asserts every locked component is present inside the
  bundle at exactly the locked version (FR-047, acceptance scenario US3-2), and
  that no FieldWorks or LibLCM assembly was bundled (FR-045).

## ReleaseArtifact

One shipped output.

| Field | Type | Notes |
|---|---|---|
| `kind` | `installer \| portable` | |
| `support_status` | `supported \| best_effort` | `installer` → supported, `portable` → best-effort |
| `source_commit` | `str` | git short SHA, stamped at build (FR-049) |
| `smoke_verdict` | `PASS \| FAIL` | |

**Validation**
- Both are produced from one packaging definition (FR-046) and run the same
  smoke test (FR-047).
- An artifact with `smoke_verdict == FAIL` MUST NOT be released; a failing
  `portable` MUST NOT block the `installer` (FR-047, SC-010).
