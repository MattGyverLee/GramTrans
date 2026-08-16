# Phase 0 Research: Standalone Windows Application

**Feature**: 034-standalone-windows-app
**Date**: 2026-08-16
**Input**: [spec.md](spec.md), [constitution v7.0.0](../../.specify/memory/constitution.md)

Every decision below was checked against the current source tree, the installed
flexicon working copy (`D:/Github/_Projects/_LEX/flexicon`), and the live
FieldWorks 9.3.10.1 install on this machine. Findings that changed the shape of
the plan are marked **[load-bearing]**.

---

## R1. FieldWorks discovery — flexicon already does all of it **[load-bearing]**

**Decision**: The shell performs **no registry access of its own**. It calls
`flexicon.FLExInitialize()` and then reads the globals flexicon populates.

**Rationale**: `flexicon/code/FLExGlobals.py::InitialiseFWGlobals()` already
does, in order: probe `HKCU\SOFTWARE\SIL\FieldWorks\9` then
`HKLM\SOFTWARE\SIL\FieldWorks\9`; read `RootCodeDir` and `ProjectsDir`; verify
`FieldWorks.exe` exists under the code dir; **append `FWCodeDir` to `sys.path`**;
`clr.AddReference("FwUtils")`; and read `FWShortVersion` / `FWLongVersion` from
FieldWorks' own `VersionInfoProvider`. Verified live on this machine:
`ProjectsDir = C:\ProgramData\SIL\FieldWorks\Projects\`,
`RootCodeDir = C:\Program Files\SIL\FieldWorks 9\`, `FieldWorksVersion = 9.3.10.1`.

That single function is the whole of FR-001, FR-031, FR-032, FR-033 and FR-044 —
including the FR-044 constraint that the *only* external path added is the
FieldWorks code directory, which is literally what line 149 does. Writing our own
`winreg` probe would duplicate it and could disagree with the path flexicon
actually loaded assemblies from.

`FW_SUPPORTED_VERSIONS = ["9"]` in the same module is the authoritative supported
range for FR-032; the shell reports it rather than defining its own.

**Gotcha [load-bearing]**: `flexicon/__init__.py` does
`from .code.FLExGlobals import FWProjectsDir, FWCodeDir, FWShortVersion, ...`.
That binds the names **at package import time, before `FLExInitialize()` runs**,
so `flexicon.FWProjectsDir` is `None` and *stays* `None` after initialization.
The shell and the self-check MUST read the module attributes
(`flexicon.code.FLExGlobals.FWProjectsDir`) post-init, never the re-exported
package names. A self-check that reads the package names would silently report
"not detected" on a perfectly healthy machine.

**Alternatives considered**:
- *Own `winreg` probe in the shell.* Rejected: duplicates R1, and can report a
  code dir different from the one whose assemblies were actually loaded.
- *Ask LCM via `FwDirectoryFinder.ProjectsDirectory`.* Not rejected — it is what
  `AllProjectNames()` uses internally (see R2) — but it is unavailable until
  after init, so it cannot serve the "FieldWorks is missing" message.

## R2. Project enumeration — `AllProjectNames()`, not a directory walk

**Decision**: The source picker enumerates via `flexicon.AllProjectNames()`. The
target picker keeps using the existing `Lib/api.list_target_candidates()`, but
the standalone injects the registry-derived projects root into it (see R6).

**Rationale**: `AllProjectNames()` → `FLExLCM.GetListOfProjects()` →
`FwDirectoryFinder.ProjectsDirectory`, i.e. LCM's own answer, which honours a
non-default projects location (spec edge case: *Non-default projects
directory*). `list_target_candidates()` by contrast defaults to a hard-coded
`C:\ProgramData\SIL\FieldWorks\Projects` literal — correct on a default install,
wrong on a relocated one.

**Alternatives considered**: walking `ProjectsDir` for `<name>/<name>.fwdata`
ourselves. Rejected for the source side — it re-implements LCM's rule for what
counts as a project and would drift.

## R3. Host boundary — the shell calls `MainFunction`, and the gate is a parameter **[load-bearing]**

**Decision**: The standalone shell is a *host*, not a second entry point. It
reproduces exactly what FlexTools hands the module — an open source project, a
report sink, `modifyAllowed` — and calls
`gramtrans.MainFunction(source, report, True, confirmation_gate=gate)`. One new
**keyword-only** parameter, defaulting to an always-satisfied gate, threads down
through `_run_gui` → `SelectionWizard` → `_PageFinish._on_move`.

**Rationale**: FR-017 requires the Move gate to be host-supplied. The wizard is
where Preview-vs-Move is chosen, so the gate must be *reachable from* the wizard
but *owned by* the host. A keyword parameter with a permissive default is the
smallest construct that gives both: FlexTools' existing positional call
`MainFunction(project, report, modifyAllowed)` is unchanged and gets a gate that
returns "satisfied" without prompting, so its behaviour is byte-identical
(SC-013). `run_gui_harness.py` likewise keeps working unmodified.

The alternative shape — the shell constructing `SelectionWizard` directly — was
rejected because `MainFunction`/`_run_gui` also own QApplication setup, the
`_enable_debug_logging()` call, the fatal-exception funnel, and the target-handle
`CloseProject()` cleanup that FR-013 depends on. Re-implementing those in the
shell is exactly the forking FR-015 forbids.

**Gate protocol** (see [contracts/host-shell.md](contracts/host-shell.md)): a
duck-typed object with one method, `confirm(target_project_name) -> bool`.
FlexTools' default returns `True` immediately. The standalone's returns `True`
only after its warning dialog has been shown and the typed name matched.

## R4. Source picker lives in the shell; the target picker stays in the wizard

**Decision**: FR-002's source picker is a **new shell-owned dialog** shown before
`MainFunction` is called. FR-003's target picker is the **existing**
`Lib/ui/target_picker.py` on wizard page 0, unchanged.

**Rationale**: This maps the two hosts onto one code path. Under FlexTools the
source is the host's open project; under the standalone the shell's picker
*produces* that open project and then behaves identically from `MainFunction`
onward. Nothing about target selection differs between hosts, so nothing about
it should be duplicated.

FR-004 ("nothing pre-selected") and the "source not selectable as target"
constraint are already satisfied on the target side:
`list_target_candidates()` filters the source out by name *and* by normalised
path, `bind_target()` raises `SameProjectError` on both, and
`TargetPickerDialog` starts with its OK button disabled. The new source dialog
must reproduce that disabled-until-chosen behaviour; the existing dialog is the
model to copy.

## R5. Packaging — PyInstaller `.spec` + Inno Setup, both from one definition

**Decision**: One PyInstaller `.spec` file with two build targets (onedir and
onefile) driven by a `build/build.py` orchestrator; Inno Setup wraps the onedir
output into the installer. PyInstaller and Inno Setup were named by the owner in
the feature input.

**Rationale**: FR-046 demands two artifacts from a *single* packaging
definition. PyInstaller supports both `COLLECT` (onedir) and `EXE(..., onefile)`
from one `Analysis`, which is precisely that. Inno Setup consumes the onedir tree
and supplies the Start Menu entry and uninstaller FR-046 requires. The onefile
target is best-effort per the spec's assumption, and rightly so: it unpacks to a
temp directory at every launch, which interacts badly with both pythonnet
assembly loading and antivirus.

**Alternatives considered**: cx_Freeze (no onefile story), Nuitka (compilation
makes the pythonnet/CLR interaction far harder to diagnose), briefcase
(cross-platform machinery we have no use for — FR-050 is Windows-only).

## R6. The flat-import convention survives freezing without a refactor **[load-bearing]**

**Decision**: Every module under `src/gramtrans/Lib/` and `src/gramtrans/Lib/ui/`
is declared in the `.spec` file's `hiddenimports` under **both** its flat
top-level name (`preview`, `selection_wizard`, …) and its package name
(`gramtrans.Lib.preview`, …), generated by globbing at build time. No source file
changes.

**Rationale**: FR-018 forbids the import refactor, and 31 files under `src/`
carry `if __package__:` dual-mode guards that depend on it. `gramtrans.py` puts
`Lib/` and `Lib/ui/` on `sys.path` via `site.addsitedir`, which PyInstaller's
static analysis cannot follow — hence every flat name must be declared. Because
PyInstaller's `FrozenImporter` resolves top-level names from the archive
directly, the frozen flat names resolve whether or not `addsitedir` finds
anything on disk, so the guards keep taking their flat branch exactly as they do
today. Declaring both names also keeps the package-import fallback branches
(`from gramtrans.Lib.debuglog import …`) working.

**Risk accepted**: the flat namespace claims generic top-level names —
`api`, `models`, `preview`, `report`, `selection`, `texts`, `matcher`,
`closure`, `conflict`, `transfer`, `residue`, `references`, `reversals`,
`wordforms`, `pictures`, `protection`, `owned`, `categories`, `fingerprints`,
`merge_preview`, `config_views`, `debuglog`, `ws_mapping`, `ws_fonts`. None
collide with the stdlib or with any current dependency, but a future dependency
shipping a top-level `models` or `api` would shadow ours inside the bundle. The
smoke test's Preview run (FR-048) is what catches this, and a build-time
collision check over the frozen module table is cheap insurance.

**Alternatives considered**: shipping `Lib/` as `--add-data` and relying on
`addsitedir` at runtime. Works, but ships source into the bundle and defers
every import error to runtime. Rejected. Refactoring the imports is forbidden
outright (FR-018, Out of Scope).

## R7. pythonnet is the highest packaging risk

**Decision**: Treat pythonnet/`clr_loader` as the make-or-break item. Prove it
with a throwaway freeze **before** any shell code is written, and give it its own
smoke-test assertion.

**Rationale**: flexicon depends on `pythonnet >=3.0.3,<3.1` (installed: 3.0.5,
`clr_loader` 0.2.7.post0, which itself needs `cffi`). `clr_loader` ships a
native `ClrLoader.dll` plus `.runtimeconfig.json` data files that PyInstaller's
hooks must pick up; `clr.AddReference` then resolves FieldWorks assemblies from
the `sys.path` entry flexicon added (R1). Nothing else in the bundle has a native
+ data-file + late-binding profile like this, and a failure here presents to the
user as the opaque "nothing happened" FR-033 exists to prevent.

**Alternatives considered**: none viable — flexicon's entire LCM access is
pythonnet. This is a risk to retire early, not a choice to make.

## R8. Dependency lock — build-only, hash-pinned, fresh venv

**Decision**: `build/requirements.lock` — fully pinned with hashes, generated by
`uv pip compile --generate-hashes` (or `pip-compile` as fallback) — is checked
in. `build/build.py` creates a throwaway venv, installs with
`--require-hashes --no-cache-dir`, sets `PYTHONNOUSERSITE=1`, and runs
PyInstaller from inside it. `pyproject.toml` is **not touched**.

**Rationale**: FR-019/FR-041 put the pins in a build-only lock precisely so
FlexTools installs keep their `pyflexicon>=4.3.1` / `PyQt6>=6.4` floors. FR-042's
"must not resolve any dependency from an environment already present on the build
machine" is satisfied by the fresh venv plus `PYTHONNOUSERSITE`; hashes make
SC-008's "identical dependency set across two builds of one commit" checkable
rather than hoped-for.

The lock's roots are `pyflexicon`, `PyQt6`, and `flextoolslib` — the last because
`gramtrans.py` opens with `from flextoolslib import *` for the `FTM_*` metadata
names. **Note**: `flextoolslib` requires `flexlibs>=1.2.7.1` and `cdfutils<1.2`,
so stock flexlibs1 lands in the bundle transitively. It is inert (nothing imports
it at runtime; the module imports flexicon explicitly and the FlexTools comment
block at `gramtrans.py:40` explains why), but it is a real component of the
shipped artifact and therefore falls under the FR-053 amendment's "components it
bundles" clause and the FR-052 licence statement.

**Alternatives considered**: substituting a stand-in `flextoolslib` shim exposing
just the six `FTM_*` names. Explicitly rejected by the spec's assumptions
("Bundling the real FlexTools support library, pinned, is the chosen way"), and
rightly — a shim is a fork of host metadata that could drift.

## R9. Runtime isolation from a host Python

**Decision**: A PyInstaller **runtime hook** that runs before any application
import: scrub `PYTHONPATH`, `PYTHONHOME`, `PYTHONSTARTUP`, `PYTHONNOUSERSITE`
from `os.environ`, and assert `sys.prefix` resolves inside the bundle. Failure is
a clear message, not a traceback.

**Rationale**: FR-043 and SC-009. PyInstaller's bootloader already sets
`Py_IgnoreEnvironmentFlag`, so this is belt-and-braces — but the failure mode it
guards against (a stray `PYTHONPATH` shadowing a flat-named module from R6) is
both plausible on a linguist's machine and undiagnosable from the symptom.
Cheap, explicit, and directly testable by the smoke test.

## R10. Version stamping

**Decision**: Build time writes `src/gramtrans/_buildinfo.py` (git describe +
short SHA + ISO timestamp + dirty flag), which the shell reads. It is
gitignored; the shell falls back to `gramtrans.__version__` plus "(source
checkout)" when absent.

**Rationale**: FR-049 wants the exact source commit visible in the UI and in the
self-check. A generated module is the only mechanism that works identically
frozen and unfrozen without shipping git metadata. The fallback keeps a developer
run of the shell working without a build step.

## R11. Logging

**Decision**: `%LOCALAPPDATA%\GramTrans\logs\gramtrans-<run_id>.log`, one file
per run, retained; the path is shown in the UI and repeated in the self-check
output. The shell's report sink tees to both the in-app log view and the file.

**Rationale**: FR-038 requires a documented, user-reachable, retained location;
`%LOCALAPPDATA%` needs no elevation and survives the uninstaller. Keying the
filename on `run_id` makes FR-026's "identify the run so its residue tag can be
searched in FLEx" a one-step instruction — the same `GT-<timestamp>` string is
the log name *and* the residue tag (`residue.ImportResidueTag`).

FR-039 (no project content beyond object identification) is a review constraint
on the report sink, not a mechanism: the engine's existing report lines already
emit GUID + short summary, which is the intended level.

## R12. The self-check is a mode of the same executable

**Decision**: `GramTrans.exe --self-check` prints the prerequisite report to a
window with a Copy button (and to stdout when a console is attached). It is
reachable from the UI's Help menu as well, so a user who cannot get to a command
line can still produce it.

**Rationale**: FR-036 requires it be invocable without selecting a project;
FR-037 requires one copyable block. A menu item matters more than the flag —
the users who need FR-036 most are exactly the ones who will not open a terminal.
This is the *only* command-line flag the application accepts; FR-011 forbids a
mode toggle, and the spec's assumption that "the self-check is a diagnostic, not
a transfer interface" forbids a headless transfer path.

## R13. Regression gate

**Decision**: A GitHub Actions workflow (the repo has **no** `.github/workflows`
today — this creates the first) running `pytest -m "not integration"` plus a
FlexTools-path import check, on every push to the feature branch. The
FlexTools-path check imports `gramtrans.gramtrans`, asserts the `docs` dict
carries all six `FTM_*` keys, asserts `MainFunction` is callable with the
three-positional signature, and asserts the default confirmation gate is
satisfied without prompting.

**Rationale**: FR-021 and SC-012 both say *continuously during development, not
once at release*. Nothing enforces that today, so this is net-new infrastructure
and is a P0-phase task, not a release task. The live-LCM integration tests cannot
run on a hosted runner (no FieldWorks), which is why the gate is the unit suite
plus a signature/metadata contract check — those are the parts that a
host-boundary change can actually break.

## R14. Constitution reconciliation — Option C, recorded

**Decision**: Before release, amend the constitution narrowly: Principle II gains
a clause sanctioning exactly one standalone Windows host artifact (and the
components it bundles — PyQt6, pythonnet/clr_loader, flextoolslib and its
transitive flexlibs1/cdfutils); Principle III gains a note recording the undo
exception against that artifact alone. MAJOR bump (a NON-NEGOTIABLE principle's
scope is qualified), with a Sync Impact Report.

**Rationale**: The owner chose Option C (recorded in spec.md Question 1). It
keeps both general constraints binding for every other delivery, which matters
because Principle II's "no optional runtime dependencies" clause is the thing
that has kept this module's dependency surface small.

**Alternatives considered**: Options A, B and D as tabled in the spec — A is
broader than the evidence supports, B leaves the undo tension unaddressed in the
text, D leaves a NON-NEGOTIABLE principle visibly contradicted by a shipped
artifact.

## R15. Send/Receive targets — stated, not enforced

**Decision**: The FR-022 warning carries one extra sentence naming the recovery
path (Send/Receive first; on a bad run, delete the local project and receive
again). No detection, no second gate, no refusal. Same text in the release
documentation.

**Rationale**: The owner's answer to Question 2. The reasoning is that the
procedure is equally correct under FlexTools, so it is not a property of this
host — building detection machinery into the standalone alone would imply
otherwise, and would add a failure mode (mis-detection) to buy nothing. Worth
recording that a Send/Receive user arguably has a *better* recovery story than a
local-only user, since re-receiving restores the pre-run state; the warning says
so plainly.
