# Tasks: Standalone Windows Application (no FlexTools required)

**Input**: Design documents from `/specs/034-standalone-windows-app/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/)

**Tests**: Included, and not optional here. The spec mandates them by requirement
(FR-021 regression gate, FR-047/FR-048 smoke test) and by success criterion
(SC-011 suite stays green, SC-012 gate passes on every commit, SC-014 shared-code
exceptions enumerated). Test tasks that exist only to satisfy a normal coverage
habit are not included; every test task below traces to an FR or SC.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no ordering dependency
- **[Story]**: US1 / US2 / US3 / US4, or blank for setup / foundational / release
- File paths are repository-relative and exact

## Path Conventions

Single project. Shell code under `src/gramtrans/standalone/`, shared code under
`src/gramtrans/` and `src/gramtrans/Lib/`, packaging under `build/`, tests under
`tests/unit/` and `tests/integration/`.

**Git workflow** (CLAUDE.md): every file below except `specs/**` and
`.specify/memory/constitution.md` is implementation work and is committed on the
`034-standalone-windows-app` worktree. Spec-artifact edits (T007, T054) commit to
`main`.

---

## Phase 1: Setup

**Purpose**: create the working tree and the empty structure the rest of the
feature fills in. No behaviour.

- [x] T001 Create the implementation worktree: `git worktree add ../GramTrans-034-standalone-windows-app -b 034-standalone-windows-app` from `main`. All subsequent code tasks run there; `specs/` edits stay on `main`.
- [x] T002 [P] Create the shell package skeleton `src/gramtrans/standalone/__init__.py` — docstring only, exporting nothing yet. It MUST NOT import anything from `gramtrans.gramtrans` or `gramtrans.Lib` at module scope (direction of the FR-016 boundary).
- [x] T003 [P] Create the packaging tree `build/` and `build/smoke/` with a `build/README.md` naming the four entry points from [contracts/build-and-release.md](contracts/build-and-release.md) §1.
- [x] T004 [P] Add to `.gitignore`: `src/gramtrans/_buildinfo.py` (generated, research R10), `build/.venv-build/`, `build/build/`, `build/dist/`.

---

## Phase 2: Foundational — the regression gate, the FieldWorks-globals accessor, and the packaging spike (plan P0)

**Purpose**: FR-021 requires the gate to run *continuously during development,
not once at release*, and SC-012 measures it across the whole branch. It
therefore lands before any shell code. The packaging spike lands here too,
because research R7 identifies pythonnet-under-PyInstaller as the make-or-break
risk and everything else is wasted if it cannot freeze. T012 lands here for the
same reason: it must guard Phases 3–6 as they are written, not audit them
afterwards.

**CRITICAL**: no user-story work begins until T010 is green and T011 has a
recorded verdict.

- [x] T005 Create `src/gramtrans/Lib/gate.py`: the `ConfirmationGate` structural protocol and `AlwaysSatisfiedGate` per [contracts/host-shell.md](contracts/host-shell.md) §1. `confirm()` returns `True` immediately with no dialog, no prompt and no I/O; `finish_page_subtitle()` returns byte for byte today's `_PageFinish` literal (`src/gramtrans/Lib/ui/selection_wizard.py:4476-4479`). This file must live under `Lib/` so the wizard's default never reaches into `gramtrans.standalone`.
- [x] T006 [P] Write `tests/unit/test_034_gate_default.py`: `AlwaysSatisfiedGate().confirm("anything")` is `True`; it constructs and runs with no `QApplication` present; `finish_page_subtitle()` compares equal to the literal string asserted inline in the test (so a future edit to the wizard subtitle fails here, which is the point).
- [x] T007 Amend the plan's shared-code exception table ([plan.md](plan.md) "Shared-code exceptions") with a **row 6**: `src/gramtrans/Lib/gate.py`, *new file under shared code*, justified by [contracts/host-shell.md](contracts/host-shell.md) §1 (the wizard's default gate must not import from the shell). Without this row, T009's subset check either flags a legitimate file or has to ignore additions — and SC-014 says an unlisted shared-code change is a defect. **Commits to `main`.**
- [x] T008 Write `tests/unit/test_034_flextools_contract.py` with the assertions that are true *today*, so the gate is green from the first commit: `import gramtrans.gramtrans` succeeds; `docs` carries all six `FTM_*` keys with their current values; `MainFunction` accepts three positional arguments; and an AST scan over every module under `src/gramtrans/gramtrans.py` and `src/gramtrans/Lib/` finds no import of `gramtrans.standalone` (FR-016). The gate-parameter and subtitle assertions are added later by T023 and T035 as their exceptions land.
- [x] T009 Write `.github/scripts/check_shared_exceptions.py` (SC-014): diff the branch against `main`, collect files changed under `src/gramtrans/Lib/` and `src/gramtrans/gramtrans.py`, and fail unless that set is a subset of the exception list parsed out of `specs/034-standalone-windows-app/plan.md`. Additions count as changes (that is why T007 exists).
- [x] T010 Write `.github/workflows/regression.yml` — the repository's first workflow (research R13). On every push to `034-standalone-windows-app`: `pytest -m "not integration"` (SC-011), then `tests/unit/test_034_flextools_contract.py`, then `.github/scripts/check_shared_exceptions.py`, then T012's ban test. Live-LCM integration tests are excluded: a hosted runner has no FieldWorks.
- [x] T011 Packaging spike (research R7): freeze a throwaway script that does nothing but `flexicon.FLExInitialize()` and open one project, with PyInstaller onedir, and run it on this machine. Record the verdict — including the `clr_loader` native `ClrLoader.dll` / `.runtimeconfig.json` collection behaviour — in `specs/034-standalone-windows-app/probe-results.md`. A failure here re-scopes Phase 5 before any shell code exists. **Commits to `main`.**

### T012 — the FieldWorks-globals accessor (research R1 containment)

- [x] T012 Make the research-R1 trap unwriteable rather than merely tested. Verified at source: `flexicon/__init__.py` does `from .code.FLExGlobals import FWCodeDir, FWProjectsDir, FWExecutable, FWShortVersion, FWLongVersion`, `FLExGlobals.py:37-41` binds all five to `None`, and `InitialiseFWGlobals()` (`FLExGlobals.py:88`) rebinds only the **module** globals via `global`. The package re-exports are therefore `None` on every machine forever, and a reader of them reports "FieldWorks not detected" on a perfectly healthy install. Three parts, one task, one commit:
  1. **Sole accessor** — `src/gramtrans/standalone/fwglobals.py` exposing `code_dir()`, `projects_dir()`, `executable()`, `short_version()`, `long_version()` and `supported_versions()`. Each reads `flexicon.code.FLExGlobals` **at call time**, after asserting `FLExInitialize()` has run. This is the only module in the repository permitted to name those symbols.
  2. **Loud, not false** — an accessor that finds `None` after initialisation raises a typed error the shell maps to the FR-033 "language-model runtime failed to initialise" message, never to the FR-031 "FieldWorks is not installed" message. Even a total bypass of part 3 then produces an honest failure instead of a lie.
  3. **The ban** — `tests/unit/test_034_fwglobals_only.py`: AST-scan every module under `src/gramtrans/` and `build/` and fail on any `flexicon.FWCodeDir`-style attribute read, any `from flexicon import FWCodeDir`-style name import, and any `getattr(flexicon, "FW…")`, outside `standalone/fwglobals.py` itself. Wired into T010's gate, so it guards Phases 3–6 as they are written.

  Deliberately **not** solved by raising the `pyflexicon` floor: the clean upstream fix is a PEP 562 module `__getattr__` in `flexicon/__init__.py` making the re-exports resolve lazily, but the standalone must work correctly against the declared `>=4.3.1` floor regardless, and raising that floor would push an upgrade onto every existing FlexTools install for this feature's benefit (against the spirit of FR-019). Worth filing upstream on its own merits; it does not remove the need for this task.

**Checkpoint**: the gate runs on every push and passes; the pythonnet freeze risk
has a recorded verdict; the R1 trap is a CI failure rather than a review habit.
User-story work can begin.

---

## Phase 3: User Story 1 — Run a transfer without FlexTools (Priority: P1) 🎯 MVP

**Goal**: a machine with FieldWorks 9 and no FlexTools can launch the
application, **choose a source project** from an explicit chooser, choose a
target, run a Preview, see the report in-app, and close with both projects
released. The source chooser (T014, T024) is the defining difference from the
FlexTools host, which supplies the source implicitly — here it is picked, never
assumed, defaulted, or configured.

**Independent Test**: on a clean Windows machine with FieldWorks 9, no FlexTools
and no user Python, launch, select source + target, run Preview, confirm the
preview matches the FlexTools-hosted run for the same pair and that the target is
unchanged.

### Tests for User Story 1

- [x] T013 [P] [US1] Write `tests/unit/test_034_projects_root_injection.py` (FR-001): `list_target_candidates` uses `stub.projects_root` when set, and falls back to the existing `C:\ProgramData\SIL\FieldWorks\Projects` literal when the stub carries the default `""` — the second assertion is the FlexTools-unchanged half and must pass before *and* after T016.
- [x] T014 [P] [US1] Write `tests/unit/test_034_source_chooser.py`, covering both halves of "no project is ever assumed":
  - **FR-005 (reachability)**: scan every module under `src/gramtrans/standalone/` and assert no occurrence of `DEFAULT_SOURCE_PROJECT`, `"Ejagham"`, or any hard-coded project literal; and assert the shell exposes no code path that calls `_headless_phase0`.
  - **FR-002/FR-004 (the chooser itself)**: the source chooser is constructed with its list populated from the enumerated projects and **nothing selected**; its advance control is disabled until the user makes a deliberate choice and re-disables if the selection is cleared; it persists nothing between constructions (no last-used memory); and once a source is chosen, that project is absent from the list `list_target_candidates` returns (US1 acceptance scenario 3).
- [x] T015 [P] [US1] Write `tests/integration/test_034_standalone_preview_live.py`, marked `@pytest.mark.integration` (SC-002, SC-004): run the same selections through the FlexTools-hosted path and through `HostSession` against the `Ejagham Mini` → `Ejagham Full GT-Test` pair, assert the two `RunReport`s are equivalent, and assert the target's `.fwdata` is byte-for-byte identical before and after.

### Shared-code exceptions for User Story 1

- [x] T016 [US1] **Exception 4** — `src/gramtrans/Lib/api.py`: add `projects_root: str = ""` as the last, defaulted field of `RunContextStub`; add an optional `projects_root=""` keyword to `initialize_run`; change `list_target_candidates` to `root = stub.projects_root or projects_root`. Signature shape per [contracts/host-shell.md](contracts/host-shell.md) §4. The FlexTools path passes nothing and gets an identical candidate list.
- [x] T017 [P] [US1] **Exception 5** — `src/gramtrans/Lib/ui/target_picker.py:49`: reword the label `"The current FlexTools project is always the SOURCE (read-only)."` to `"The project chosen as SOURCE is opened read-only."`. Same dialog, same controls, same flow (SC-013).
- [x] T018 [US1] **Exception 1** — `src/gramtrans/gramtrans.py`: add keyword-only `confirmation_gate=None` to `MainFunction` (`gramtrans.py:131`) and thread it into `_run_gui` (`gramtrans.py:182`). `None` resolves to `AlwaysSatisfiedGate()` from T005. The three positional parameter names, the `docs` dict, `DEFAULT_SOURCE_PROJECT`, `_headless_phase0` and the existing `finally`-block target `CloseProject()` are untouched. Do **not** yet pass the gate into `SelectionWizard` — that is exception 2, in Phase 4.

### Shell implementation for User Story 1

- [x] T019 [P] [US1] `src/gramtrans/standalone/errors.py`: one plain-language message per prerequisite and guard-rail failure, per [contracts/cli-and-selfcheck.md](contracts/cli-and-selfcheck.md) §3 — FieldWorks missing (FR-031), unsupported version (FR-032), runtime load failed (FR-033), target locked naming the project (FR-029), one project unopenable attributed by name (FR-034), migration required caught as `flexicon` `FP_MigrationRequired` (FR-035). Every message names the log file. No tracebacks. Keep the FR-031 and FR-033 messages distinct — T012 part 2 depends on a `None` global mapping to the latter, never the former.
- [x] T020 [US1] `src/gramtrans/standalone/prereq.py`: `PrerequisiteCheck` / `PrerequisiteReport` per [data-model.md](data-model.md), and the detection that fills them. Calls `flexicon.FLExInitialize()`, then reads **every** FieldWorks value through `standalone/fwglobals.py` (T012) — this module names no `flexicon` global directly, and T012's ban test enforces that. No `winreg` access of our own (FR-044).
- [x] T021 [P] [US1] `src/gramtrans/standalone/logsink.py`: a report sink exposing exactly `Info` / `Warning` / `Error` / `Blank` (FR-008) that tees each call to the in-app view and to `%LOCALAPPDATA%\GramTrans\logs\gramtrans-<run_id>.log`, where `<run_id>` is the `GT-<YYYYmmdd-HHMMSS>` string also used as the Import Residue tag (research R11, FR-038). Retained across runs; directory created on demand.
- [x] T022 [P] [US1] `src/gramtrans/standalone/report_view.py`: the in-app log view (FR-009) — visible during and after the run, header showing the log-file path, and Save-to-file plus Copy-to-clipboard controls (FR-010).
- [x] T023 [US1] Extend `tests/unit/test_034_flextools_contract.py` (from T008) with the exception-1 assertions now that T018 has landed: `confirmation_gate` is keyword-only with default `None`, and the resolved default is an `AlwaysSatisfiedGate` whose `confirm()` returns `True` with no UI.
- [x] T024 [US1] `src/gramtrans/standalone/source_picker.py`: **the source project chooser** (FR-002) — a real selection dialog, not an inferred or configured project. There is no host-provided "currently open project" in this host, so this is the screen where the source comes from and it is the first thing the user sees after the prerequisite checks pass.
  - Populated from `flexicon.AllProjectNames()` (research R2), which honours a relocated projects directory rather than assuming the default path.
  - **Nothing pre-selected**, no default, no last-used, no hard-coded project (FR-004/FR-005). The advance control starts disabled and enables only on a deliberate choice — copy the disabled-until-chosen behaviour of `Lib/ui/target_picker.py`.
  - The chosen source is then excluded from the target picker's candidates, which `list_target_candidates` already does by name and by normalised path once T016 feeds it the right root.
  - A project in the list that cannot be opened is reported against that project by name and leaves the rest of the list selectable (FR-034); an empty list gets its own message rather than an empty dialog.
  - The screen states, before selection, that the target must be closed in FLEx **even for a Preview** (FR-030).
- [x] T025 [US1] `src/gramtrans/standalone/app.py`: `HostSession` per [data-model.md](data-model.md) — the `CREATED -> PREREQ_OK -> SOURCE_BOUND -> RUNNING -> RELEASED` lifecycle. Startup assertions in the order fixed by [contracts/host-shell.md](contracts/host-shell.md) §6: assert `PyQt6.QtWidgets` imports and a `QApplication` constructs (FR-006) *before* anything else, then `FLExInitialize()`, then the post-init reads via `fwglobals` (T012). Opens the source read-only (FR-007), sets `modify_allowed` to a hard-coded `True` (FR-011 — no flag, no argument, no attribute that can be `False`), and calls `gramtrans.MainFunction(source_handle, sink, True)`. Passes `fwglobals.projects_dir()` through `initialize_run(projects_root=...)`.
- [x] T026 [US1] Implement `HostSession.release()` and wire it to **every** exit path — normal close, user cancel, error, failed run (FR-013, SC-005). `MainFunction`'s existing `finally` closes the target handle; the session closes the source and calls `flexicon.FLExCleanup()`. Verify by opening both projects in FLEx immediately after each exit path.
- [x] T027 [US1] `src/gramtrans/standalone/__main__.py`: the entry point. Argument handling is Phase 6's job; for now accept no arguments, construct the `QApplication`, and run `HostSession`. Any unexpected argument is an error (FR-011 forbids a mode toggle).
- [x] T028 [US1] Guard rail FR-028: refuse a run where source and target resolve to the same project. `api.bind_target` already raises `SameProjectError` on both name and normalised path; the task is to render it as the FR-028 plain-language message from T019 rather than letting it surface raw.
- [x] T029 [US1] Run T015 live against `Ejagham Mini` → `Ejagham Full GT-Test` and record the parity evidence (SC-002) in `specs/034-standalone-windows-app/probe-results.md`. **Evidence commits to `main`.**

**Checkpoint**: US1 is demonstrable from a source checkout — `python -m gramtrans.standalone` opens the source chooser, then the target picker, runs a Preview, shows the report, and leaves both projects openable in FLEx. Nothing is frozen yet and Move is still ungated.

---

## Phase 4: User Story 2 — Commit a Move, irreversibility made unmissable (Priority: P2)

**Goal**: a Move cannot start without the FR-022 warning and an exactly-typed
target name, and a partial failure tells the user how to find what was written.

**Independent Test**: against a disposable copy of a target project, confirm the
gate cannot be bypassed by pressing Enter or clicking through, complete it, and
verify the written objects carry the expected residue tags.

### Tests for User Story 2

- [x] T030 [P] [US2] Write `tests/unit/test_034_standalone_gate.py` (FR-023, FR-025): the proceed control is disabled until the typed text equals the target name **exactly** — case-sensitive, whitespace-significant, no trimming, no case folding; the proceed control is not the dialog's default button, so neither Enter nor a click-through satisfies it; Cancel returns `False`.
- [x] T031 [P] [US2] Write `tests/unit/test_034_gate_text_content.py` (FR-022, FR-027, FR-054): the standalone gate's warning text contains the cannot-be-undone-from-within-the-application statement, the back-up-the-target-first instruction, and the Send/Receive recovery path (Send/Receive before running; on a bad run delete the local project and receive again). Assert that neither the gate text nor `StandaloneConfirmationGate.finish_page_subtitle()` contains `Ctrl+Z` or the word "undo" in an affirmative claim.
- [x] T032 [P] [US2] Write `tests/integration/test_034_move_gate_live.py`, marked `@pytest.mark.integration` (SC-003, FR-024): a Preview run reaches `execute_preview` with `confirm()` never called; a Move run reaches `execute_move` only after `confirm()` returned `True`.

### Implementation for User Story 2

- [x] T033 [US2] `src/gramtrans/standalone/gate.py`: `StandaloneConfirmationGate` per [contracts/host-shell.md](contracts/host-shell.md) §1 — the modal warning of FR-022/FR-054, the exact-match text field, the disabled non-default proceed control, Cancel returning `False`, and a `finish_page_subtitle()` that states irreversibility without mentioning undo (FR-027). `confirm()` MUST NOT raise.
- [x] T034 [US2] **Exception 2** — `src/gramtrans/Lib/ui/selection_wizard.py`: add keyword-only `confirmation_gate=None` to `SelectionWizard.__init__` (`selection_wizard.py:4640`), defaulting to `AlwaysSatisfiedGate()`, and have `_PageFinish._on_move` (`selection_wizard.py:4533`) call `gate.confirm(target_name)` **once**, immediately before `gt_api.execute_move` and **after** the existing EXCLUDED-LOSSY dialog. A `False` return aborts with no write and the wizard intact. Parameter order and every existing name unchanged. Then complete the T018 thread: `_run_gui` passes the gate through.
- [x] T035 [US2] **Exception 3** — `src/gramtrans/Lib/ui/selection_wizard.py`: `_PageFinish.__init__` (`selection_wizard.py:4468`) takes the subtitle from `gate.finish_page_subtitle()` instead of the inline literal at `selection_wizard.py:4476-4479`. Then extend `tests/unit/test_034_flextools_contract.py` to assert the FlexTools-default subtitle is byte-identical to today's string (SC-013).
- [x] T036 [US2] Wire the gate through `HostSession`: `app.py` constructs `StandaloneConfirmationGate` and passes it as `MainFunction(..., confirmation_gate=gate)`. This is the first call site that passes the parameter at all.
- [x] T037 [US2] Partial-failure reporting (FR-026), per [contracts/cli-and-selfcheck.md](contracts/cli-and-selfcheck.md) §5: when a Move raises partway, one message stating that the target **may be partially modified**, the `run_id` described as the tag to search for in FLEx's Import Residue, and the full log-file path. It MUST NOT offer, imply, or document a rollback.

**Checkpoint**: US1 and US2 both work from a source checkout, and the FlexTools path is provably unchanged — same dialogs, same subtitle, same sequence.

---

## Phase 5: User Story 3 — Produce a reproducible release (Priority: P3)

**Goal**: two artifacts from one packaging definition, built in a throwaway venv
from a hash-pinned lock, both smoke-tested before anything ships.

**Independent Test**: from a fresh clone on a machine that has never built
GramTrans, run the documented build command and confirm the artifacts are
produced, contain the identical dependency set as the previous build of the same
commit, and pass the smoke test.

- [x] T038 [US3] Generate and check in `build/requirements.lock` — fully pinned with `--generate-hashes`, roots `pyflexicon`, `PyQt6`, `flextoolslib`, `pyinstaller` (research R8). Record in a header comment that `flextoolslib` drags in stock `flexlibs` (flexlibs1) and `cdfutils` transitively, that they are inert at runtime, and that they are nonetheless shipped components falling under FR-052 and the FR-053 amendment. `pyproject.toml` is **not** edited — its `pyflexicon>=4.3.1` / `PyQt6>=6.4` floors stay floors (FR-019/FR-041).
- [x] T039 [P] [US3] `build/hiddenimports.py`: glob `src/gramtrans/Lib/**/*.py` and emit each module under **both** its flat top-level name and its `gramtrans.Lib.…` package name (research R6). Generated, never hand-listed — a new helper module must need no build-file edit. Include the build-time collision check: fail if any bundled third-party distribution provides a top-level module matching one of ours (`api`, `models`, `preview`, `report`, `selection`, …).
- [x] T040 [P] [US3] `build/rthook_isolate.py`: PyInstaller runtime hook running before any application import — scrub `PYTHONPATH`, `PYTHONHOME`, `PYTHONSTARTUP` from `os.environ`, assert `sys.prefix` resolves inside the bundle, and fail with a clear message rather than a traceback (FR-043, SC-009).
- [x] T041 [US3] `build/gramtrans.spec`: exactly **one** `Analysis`, feeding both a `COLLECT` (onedir) and a onefile `EXE` (FR-046). Consumes T039's hiddenimports and T040's runtime hook. Divergence between the two artifacts' contents is a defect.
- [x] T042 [US3] `build/build.py` with the four entry points and the seven ordered steps of [contracts/build-and-release.md](contracts/build-and-release.md) §1: fresh `build/.venv-build` deleting any prior one; `PYTHONNOUSERSITE=1` and cleared `PYTHONPATH`/`PYTHONHOME` for every child; `pip install --require-hashes --no-cache-dir -r build/requirements.lock` with **no fallback** to the machine's environment (FR-042); stamp; freeze; smoke; manifest.
- [x] T043 [US3] Version stamping (FR-049, research R10): `build.py` writes `src/gramtrans/_buildinfo.py` from `git describe --tags --always --dirty` + short SHA + ISO timestamp, and the shell reads it — falling back to `gramtrans.__version__` plus `(source checkout)` when absent, so a developer run needs no build step. Surface the version in the application UI and in the self-check block.
- [x] T044 [US3] `build/installer.iss`: Inno Setup over the onedir tree, producing `GramTrans-Setup-<version>.exe` with a Start Menu entry and an uninstaller (FR-046). This is the **supported** artifact; the onefile `GramTrans-<version>.exe` is best-effort.
- [x] T045 [US3] `build/smoke/run_smoke.py <artifact-path>`: the eight checks of [contracts/build-and-release.md](contracts/build-and-release.md) §4 — starts and exits cleanly; `--self-check` returns PASS; project list populated; the no-interface fallback unreachable and `DEFAULT_SOURCE_PROJECT` absent from all output (FR-005/FR-006); a Preview against a known pair with the target byte-for-byte unchanged (SC-004); every locked component present at exactly the locked version; no FieldWorks or LibLCM assembly bundled (FR-045); no flat-name collision.
- [x] T046 [US3] Emit the per-artifact manifest from `build.py` — kind, support status, source commit, smoke verdict, resolved component/version list — and enforce the release rule: a `FAIL` verdict blocks that artifact, and a failing `portable` MUST NOT block the `installer` (FR-047, SC-010).
- [x] T047 [US3] Build the same commit twice and diff the two manifests' component/version sets to demonstrate SC-008. Record the result in `specs/034-standalone-windows-app/probe-results.md`. **Evidence commits to `main`.**

**Checkpoint**: `python build\build.py` produces both artifacts from a clean checkout, and both carry a smoke verdict.

---

## Phase 6: User Story 4 — Diagnose a machine where it will not start (Priority: P4)

**Goal**: a user who cannot start the application can produce one copyable block
that names the failing prerequisite and its remedy.

**Independent Test**: on a machine with FieldWorks absent or mis-registered, run
the self-check and confirm it names the specific missing prerequisite and its
remedy.

- [x] T048 [P] [US4] Write `tests/unit/test_034_prereq_report.py`: `PrerequisiteReport.overall` is `FAIL` if any check fails; **every** `FAIL` check carries a non-empty `remedy` (FR-036, SC-006). Plus the behavioural half of the R1 guard that T012's AST ban cannot express: patch `flexicon.code.FLExGlobals.FWProjectsDir` to a known value and assert the report shows it — a detection wired to the package re-export would show `None` and report a false FAIL.
- [x] T049 [US4] `src/gramtrans/standalone/selfcheck.py`: render `PrerequisiteReport` as the single ASCII block of [contracts/cli-and-selfcheck.md](contracts/cli-and-selfcheck.md) §2 — `[PASS]` / `[FAIL]` / `[UNKNOWN]` prefixes, no colour, no box drawing, a `remedy:` line under every `[FAIL]`, a `VERDICT: PASS (n of m)` footer, and the log-file path. Copyable and savable as one unit (FR-037).
- [x] T050 [US4] Argument handling in `src/gramtrans/standalone/__main__.py` per [contracts/cli-and-selfcheck.md](contracts/cli-and-selfcheck.md) §1: `--self-check` and `--version` are the **only** accepted flags; any other argument is an error naming the two valid flags. Exit codes `0` pass / normal, `1` self-check failed, `2` invalid arguments. No `--source`, `--target`, `--move`, `--preview` or read-only switch (FR-011, and no headless transfer interface).
- [x] T051 [US4] Add **Help → Self-check…** to the application menu, rendering the same block in a window with a Copy button. This is the route that matters for the users FR-036 is written for — they will not open a terminal (research R12).
- [x] T052 [US4] Surface the log-file location in the interface (FR-038): the status bar and the report view's header, in addition to the self-check block.
- [x] T053 [US4] Review the report sink's output against FR-039 — no project content beyond what identifies the objects in the run (GUIDs and short summaries, which is what the engine's report lines already emit). This is a review constraint on `logsink.py`, recorded in the task's commit message, not new machinery.

**Checkpoint**: all four stories are independently functional.

---

## Phase 7: Release gate (not a phase of implementation)

**Purpose**: these block **release**, not implementation. Nothing in Phases 1–6
waits on them, and nothing ships until they are done.

- [x] T054 **FR-053 — constitution amendment, Option C.** Amend `.specify/memory/constitution.md`: Principle II gains a clause sanctioning exactly **one** standalone Windows host artifact and the components it bundles (PyQt6, pythonnet/clr_loader, flextoolslib and its transitive flexlibs1/cdfutils); Principle III gains a note recording the undo exception **against that artifact alone**. Both general constraints keep their force for every other delivery; any future second channel needs its own amendment. MAJOR version bump with a Sync Impact Report — a NON-NEGOTIABLE principle's scope is being qualified. **Commits to `main`.**
- [x] T055 [P] Release documentation per [contracts/build-and-release.md](contracts/build-and-release.md) §6: the artifact is **unsigned**, what the SmartScreen / antivirus warning looks like and how to proceed (FR-051); the licence under which the **binary** is distributed, stricter than the project's MIT source licence because PyQt6 is GPL-or-commercial and flextoolslib pulls flexlibs1 and cdfutils (FR-052); FieldWorks 9 as a user-installed prerequisite, never bundled (FR-045); that the target must be closed in FLEx **even for a Preview** (FR-030); and that a Move cannot be undone from within the application, with the backup and Send/Receive recovery guidance (FR-027, FR-054).
- [x] T056 Final success-criteria sweep: walk SC-001 through SC-014 and record the evidence for each in `specs/034-standalone-windows-app/probe-results.md`. SC-012 in particular is measured **across the whole branch** — confirm no commit merged with a red gate. **Commits to `main`.**

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)** — no dependencies.
- **Phase 2 (Foundational)** — depends on Phase 1. **Blocks every user story.**
  T010 must be green and T011 must have a recorded verdict before Phase 3 opens.
- **Phase 3 (US1)** — depends on Phase 2, and specifically on T012: `prereq.py`
  and `app.py` are the first consumers of the accessor.
- **Phase 4 (US2)** — depends on Phase 3. T034 completes the gate thread that
  T018 began, and T036 needs `HostSession` from T025. US2 is *not* independently
  startable ahead of US1, which is why the spec priorities put the preview slice
  first.
- **Phase 5 (US3)** — depends on Phase 3 for something to freeze. It does not
  depend on Phase 4: the artifact can be built and smoke-tested with Move still
  ungated, though it must not be *released* that way.
- **Phase 6 (US4)** — depends on T020 (`prereq.py`, built in Phase 3 because
  startup needs it). The rendering, the CLI and the menu route are Phase 6.
- **Phase 7 (Release gate)** — depends on nothing in the code; blocks release
  only. T054 and T055 can start at any time.

### Critical path

T001 → T005 → T008/T009 → T010 → T012 → T020 → T025 → T034 → T042 → T045 → T054

### Within-story ordering

- T005 before T006, T018, T034 (everything gate-shaped needs the protocol).
- T007 before T009 lands in CI, or the subset check flags `Lib/gate.py`.
- T012 before T020 and T025, and before anything else that touches a FieldWorks
  value; T019's FR-031/FR-033 message split is what T012 part 2 maps onto.
- T016 before T025 (the shell injects `projects_root` through `initialize_run`).
- T019 before T020 and T024 (messages before the code that raises them).
- T020 before T025 (startup asserts prerequisites first) and before T049.
- T021 before T022 and T025 (the sink is what the view renders).
- T033 before T034 and T036.
- T038 → T039/T040 → T041 → T042 → T043 → T044 → T045 → T046.
- T049 before T050 and T051 (both routes render the same block).

### Parallel opportunities

- T002, T003, T004 together.
- T006 alongside T008/T009 (different files, both depend only on T005).
- T011 and T012 together — unrelated files, both foundational.
- T013, T014, T015 together — all three are test files with no shared target.
- T017 alongside T016 and T018 — three different shared files, three different
  exceptions.
- T019, T021, T022 together once T005 and T012 are in.
- T030, T031, T032 together.
- T039 and T040 together once T038 pins the versions.
- T048 alongside T049's implementation.
- T055 at any point, alongside anything.

---

## Implementation Strategy

### MVP first

Phases 1 → 2 → 3. That yields a source-checkout application that previews without
FlexTools, which is the whole of US1 and already useful: a user can see what a
transfer *would* do. Stop and validate here — run T015 live, confirm SC-002
parity and SC-005 lock release — before touching the write path.

### Incremental delivery

1. Phase 2 → the gate runs continuously, the freeze risk is retired, and the R1
   trap is contained.
2. Phase 3 → US1, previewable, demonstrable, no write risk.
3. Phase 4 → US2, the write path behind the confirmation gate.
4. Phase 5 → US3, shippable artifacts.
5. Phase 6 → US4, supportable in the field.
6. Phase 7 → release unblocked.

### Notes

- Every task under `src/`, `tests/`, `build/` and `.github/` commits on the
  `034-standalone-windows-app` worktree. T007, T011, T029, T047, T054 and T056
  write under `specs/` or `.specify/` and commit to `main` (CLAUDE.md).
- Five of the fifty-six tasks touch shared code — T016, T017, T018, T034, T035 —
  plus T005's new `Lib/gate.py`. Any *sixth* shared-code file touched is a defect
  under SC-014 until the plan's exception table says otherwise.
- The recurring correctness trap in this feature was research R1: read
  `flexicon.code.FLExGlobals.X` post-init, never `flexicon.X`. As of T012 that is
  no longer a discipline — one module may name those symbols, an AST ban in the
  regression gate enforces it, and a `None` that slips through raises the
  runtime-failed error rather than the false "FieldWorks not installed".
