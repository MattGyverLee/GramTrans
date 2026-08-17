# Implementation Plan: Standalone Windows Application (no FlexTools required)

**Feature**: 034-standalone-windows-app
**Branch**: `034-standalone-windows-app` (worktree; spec artifacts stay on `main`)
**Date**: 2026-08-16
**Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)
**Data model**: [data-model.md](data-model.md) | **Contracts**: [contracts/](contracts/)

## Summary

Ship a second delivery artifact — a frozen Windows application — that supplies
the four things FlexTools supplies today (an open project, a report sink, the
`modifyAllowed` flag, and a run wrapper) so a linguist with FieldWorks but not
FlexTools can run the same transfer. The transfer engine and the selection
wizard are reused as-is: the new code is a **host shell** under
`src/gramtrans/standalone/` that the FlexTools path never imports, plus a
`build/` tree that freezes it.

Technically this is PyInstaller (one `.spec`, two targets) wrapped by Inno Setup
for the installer, built inside a throwaway venv from a hash-pinned build-only
lock so the package's own declared floors are untouched. The shell performs no
registry access of its own — `flexicon.FLExInitialize()` already resolves
FieldWorks from the registry, validates the install, and puts the code directory
on `sys.path`, which is exactly the FR-001/FR-031/FR-032/FR-044 surface
(research R1). The one genuinely new cross-host construct is the **confirmation
gate**: a host-supplied object the wizard consults before a Move, whose FlexTools
default is satisfied on creation so that host's behaviour is byte-identical.

Because the standalone has no `Ctrl+Z`, a Move is irreversible from the
application's point of view; that is managed by an explicit warning plus a
type-the-target-name gate, not by machinery.

## Project Structure

```text
src/gramtrans/
  gramtrans.py                     # MODIFIED (exception 1) — optional gate param
  standalone/                      # NEW — the entire host shell; never imported by FlexTools
    __init__.py
    __main__.py                    # entry point; --self-check is the only flag
    app.py                         # HostSession lifecycle: init -> pick -> run -> release
    prereq.py                       # prerequisite detection + PrerequisiteReport (FR-031..033, 036)
    source_picker.py               # FR-002 source dialog (nothing pre-selected)
    gate.py                        # StandaloneConfirmationGate (FR-022..FR-027, FR-054)
    report_view.py                 # in-app log view + save/copy (FR-008..FR-010)
    logsink.py                     # tee report sink -> view + %LOCALAPPDATA% log (FR-038)
    selfcheck.py                   # FR-036/FR-037 report rendering
    errors.py                      # plain-language messages for every prerequisite failure
  Lib/
    gate.py                        # NEW (exception 6) — ConfirmationGate protocol + AlwaysSatisfiedGate
    api.py                         # MODIFIED (exception 4) — projects_root on the stub
    ui/selection_wizard.py         # MODIFIED (exceptions 2, 3, 5) — gate consult + copy
build/                             # NEW
  gramtrans.spec                   # single PyInstaller definition, onedir + onefile
  hiddenimports.py                 # globs Lib/**.py -> flat + package names (research R6)
  rthook_isolate.py                # runtime hook: scrub PYTHON* env, assert bundle prefix
  requirements.lock                # hash-pinned, build-only (FR-019/FR-041)
  build.py                         # fresh venv -> install -> freeze -> stamp -> smoke
  installer.iss                    # Inno Setup: Start Menu entry + uninstaller
  smoke/run_smoke.py               # FR-047/FR-048 post-build smoke test
.github/workflows/regression.yml   # NEW — the FR-021/SC-012 gate (repo has none today)
tests/
  unit/test_034_gate_default.py            # FlexTools default gate is satisfied, silently
  unit/test_034_flextools_contract.py      # docs dict + MainFunction signature unchanged
  unit/test_034_prereq_report.py           # PrerequisiteReport verdict logic
  unit/test_034_no_reachable_project_name.py  # FR-005 reachability
  integration/test_034_standalone_preview_live.py  # US1 parity vs FlexTools preview
```

**Structure Decision**: the shell is a **subpackage of `gramtrans`**, not a
sibling top-level package. It needs `gramtrans.gramtrans.MainFunction` and the
`Lib/` helpers, and living inside the package means the frozen bundle has one
import root. FR-016's "the FlexTools path never imports it" is satisfied by
direction, not by distance: nothing under `gramtrans.py` or `Lib/` imports
`gramtrans.standalone`, and `test_034_flextools_contract.py` asserts it.

## Constitution Check

Assessed against [constitution v7.0.0](../../.specify/memory/constitution.md).
**Resolved 2026-08-17**: the two recorded violations below are now sanctioned by
the v8.0.0 amendment (T054) — Principle II's one-standalone-artifact exception and
Principle III's scoped undo exception. Both entries are kept as written so the
reasoning that produced the amendment stays legible.

| Principle | Assessment |
|---|---|
| I. FLEx Domain Fidelity | **PASS** — no transfer semantics are touched. The shell opens projects and hands them to the unchanged engine; GUID handling, WS mapping, cross-reference resolution and residue tagging are entirely downstream of this feature. |
| II. FlexTools-Compatible Output, flexicon-Direct | **VIOLATION — justified, amendment required before release.** This ships a second artifact that substitutes for the FlexTools host and bundles PyQt6, pythonnet/clr_loader, flextoolslib and its transitive flexlibs1/cdfutils, exceeding the "no runtime dependencies beyond flexicon and PyQt" clause. Resolved by FR-053 / Question 1 **Option C**: a narrow amendment sanctioning exactly one standalone Windows host artifact and the components it bundles. The FlexTools-hosted module remains the primary artifact and is unchanged. See Complexity Tracking. |
| III. Preview-Before-Mutate (NON-NEGOTIABLE) | **PARTIAL — Preview mandate PASS, undo mandate VIOLATION, justified.** Both modes exist and Preview is the default; FR-012 *strengthens* this by requiring the wizard to open in Preview precisely because FR-011 removes the host-level write backstop, and the existing `_PageFinish` already forces a dry run before Move can be enabled. The undo clause ("Move Mode MUST be undoable through FLEx's standard undo stack wherever LCM permits") cannot be met: the undo stack is a property of the host session, and this host has none. Resolved by Option C — the exception is recorded against this one artifact, and is compensated by the FR-022/FR-023 warning-and-typed-confirmation gate. See Complexity Tracking. |
| IV. Phased Merge Discipline | **PASS** — no merge behaviour, mode vocabulary, or disposition logic changes. This is a delivery channel for the phases already shipped. |
| V. Referential Completeness | **PASS** — closure computation is entirely inside the reused engine and preview pane. |

**Gate verdict**: PASS with two recorded violations, both against the *same*
governance decision already taken by the owner (Question 1, Option C), both
blocking release rather than implementation. Re-checked after Phase 1 design
below — no new violations introduced; the design adds no runtime dependency
beyond those enumerated here.

### Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| Principle II — a second, non-FlexTools-hosted artifact | The feature's entire premise: users with FieldWorks but no FlexTools cannot run the module at all today. | "Tell users to install FlexTools" is the status quo the feature exists to remove. |
| Principle II — runtime dependencies beyond flexicon + PyQt (pythonnet, flextoolslib, clr_loader, transitive flexlibs1/cdfutils) | pythonnet is flexicon's own transitive requirement and is not optional. `flextoolslib` supplies the `FTM_*` names `gramtrans.py` imports at module scope. | Substituting a stand-in `flextoolslib` shim exposing just the six `FTM_*` constants — rejected by the spec's assumptions as a fork of host metadata that can drift. Vendoring pythonnet is not a thing that can be done. |
| Principle III — Move is not undoable in this host | The FLEx undo stack belongs to the host session; a standalone process cannot create one that FLEx would honour. | An in-app rollback or automatic pre-run backup — both explicitly Out of Scope, and a partial rollback of an LCM write set is a far larger correctness risk than a confirmation gate. |

## Shared-code exceptions (FR-020 / SC-014)

FR-020 requires every unavoidable change to shared code to be enumerated and
individually justified here; SC-014 makes an unlisted change a defect. This list
is the complete set. All ten are additive or textual, and none alters a
FlexTools code path's behaviour.

| # | File | Change | Justification | Why FlexTools is unaffected |
|---|---|---|---|---|
| 1 | `src/gramtrans/gramtrans.py` | Add keyword-only `confirmation_gate=None` **and `projects_root=""`** to `MainFunction`, pass both through `_run_gui`. `None` → `AlwaysSatisfiedGate()`. | FR-017: the gate must be host-supplied, and `MainFunction` is the host boundary. FR-001: so must the projects root — see the amendment note below. | FlexTools calls with three positional args; the defaults reproduce today's "no prompt" behaviour and today's candidate list exactly. `run_gui_harness.py` also unchanged. |
| 2 | `src/gramtrans/Lib/ui/selection_wizard.py` | Add keyword-only `confirmation_gate=None` **and `projects_root=""`** to `SelectionWizard.__init__`; pass `projects_root` into its `gt_api.initialize_run` call; `_PageFinish._on_move` consults `gate.confirm(target_name)` immediately before `gt_api.execute_move`, after the existing EXCLUDED-LOSSY dialog. | FR-017: the wizard must *request* confirmation without *owning* it. FR-001: the wizard is what actually calls `initialize_run`, so it is what has to carry the root. | The default gate returns `True` without UI and an empty root keeps the historical literal, so the FlexTools sequence is unchanged — no new dialog, no new step (SC-013). |
| 3 | `src/gramtrans/Lib/ui/selection_wizard.py` | `_PageFinish` subtitle: the literal "changes can be undone in FLEx with Ctrl+Z" becomes gate-supplied text. FlexTools' gate supplies the current sentence verbatim; the standalone's supplies the irreversibility warning. | FR-027 forbids the application claiming a Move can be undone; that sentence is false in the standalone. | The FlexTools-supplied string is byte-identical to today's. |
| 4 | `src/gramtrans/Lib/api.py` | Add optional `projects_root: str = ""` to `RunContextStub` and an optional `projects_root` kwarg to `initialize_run`; `list_target_candidates` uses `stub.projects_root or <existing literal default>`. **Plus**: reword the `SameProjectError` and `TargetUnavailable` message text from developer notation to the plain-language FR-028/FR-029 wording. | FR-001: the projects location must come from what FieldWorks records, not a hard-coded path. FR-028/FR-029: the wizard shows these strings to the user verbatim, and "Phase 0 refuses to run (FR-019)" is not a sentence any user can act on. | The FlexTools path never passes `projects_root`, so the existing `C:\ProgramData\SIL\FieldWorks\Projects` default still applies — identical candidate list. The exception *types* and the conditions that raise them are unchanged; only the human-readable text differs, which is the same class of change as exception 5. |
| 5 | `src/gramtrans/Lib/ui/target_picker.py` | Reword one label: "The current FlexTools project is always the SOURCE (read-only)" → "The project chosen as SOURCE is opened read-only." | The current wording is false in the standalone and would confuse a user who has never installed FlexTools. | Same meaning, same dialog, same controls, same flow — a reworded static label is not a new dialog, prompt, or step (SC-013). |
| 6 | `src/gramtrans/Lib/gate.py` | **New file** under shared code: the `ConfirmationGate` structural protocol, `AlwaysSatisfiedGate`, and the `FLEXTOOLS_FINISH_SUBTITLE` literal that exception 3 moves out of the wizard. | [contracts/host-shell.md](contracts/host-shell.md) §1 — the wizard's *default* gate must not reach into `gramtrans.standalone`, which the FR-016 import direction forbids outright. Exceptions 1, 2 and 3 all resolve `None` to this default, so it has to live where both `gramtrans.py` and `Lib/ui/selection_wizard.py` can already see it. | Nothing imports it until exceptions 1–3 land, and when they do it reproduces today's behaviour exactly: `confirm()` returns `True` with no dialog and no I/O, and `finish_page_subtitle()` returns the current `_PageFinish` string byte for byte. The module imports only `typing`. |
| 7 | `src/gramtrans/gramtrans.py` | Add keyword-only `source_binder=None` to `MainFunction`, pass it through `_run_gui` into `SelectionWizard`. `_run_gui` tolerates `project is None` (no `ProjectName()` call, and it logs "source: chosen on step 1"); `MainFunction` reports plainly instead of entering the headless fallback when PyQt6 is missing *and* there is no open project to be the fallback's target. | FR-002 as amended (2026-08-17, below): the source chooser moves onto the wizard's step 1, so the host's *binder* — not an already-open handle — is what crosses the boundary. `MainFunction` is that boundary, exactly as for exception 1. | FlexTools passes three positional arguments and no `source_binder`; `project` is never `None`, so both new branches are unreachable and the wizard is constructed with the same arguments as before. |
| 8 | `src/gramtrans/Lib/ui/selection_wizard.py` | Keyword-only `source_binder=None` on `SelectionWizard.__init__` and on `_PageProjectWS`. When it is not `None`: step 1's Source row grows a "Pick source project..." button mirroring the Target row's, the Target button starts disabled until a source exists, re-picking the source releases a bound target, and the page's subtitle names both choices. When it is `None`, none of that is built. | FR-002/FR-003 as amended: the two selectors must sit on the same step, in matching controls. Placing the choice here rather than before the wizard is the whole point — three windows opening at once (log window, chooser, wizard) is what this replaces. | The `None` default builds no button, opens no dialog, leaves the Target button enabled, and keeps the Source label ("… (open in FlexTools)") and the step-1 subtitle byte-identical — asserted in `tests/unit/test_034_step1_source_picker.py`. |
| 9 | `src/gramtrans/Lib/api.py` | Add `SourceCandidate` and `list_source_candidates(projects_root, exclude_names, exclude_paths)`; factor the existing project walk and the path-identity comparison out of `list_target_candidates` into `_walk_flex_projects` / `_same_project_path`, and name the historical default root as `_DEFAULT_PROJECTS_ROOT`. | The source list has to obey the same rule as the target list — same definition of "a project", same root, same order — or the two pickers disagree about what exists. `exclude_*` is the other half of the same-project rule (a bound target must not be offered as a source). | `list_target_candidates` keeps its name, signature, default value and results; the helper it now calls is the code it already ran inline. `list_source_candidates` has no FlexTools caller — nothing constructs a `source_binder` there. |
| 10 | `src/gramtrans/Lib/ui/source_picker.py` | **New file** under shared code: `SourcePickerDialog`, the twin of `target_picker.py` (same controls, same disabled-until-chosen rule, same `mark_unopenable` behaviour), carrying the FR-030 "close the target in FLEx, even for a Preview" guidance. Moved out of `gramtrans/standalone/source_picker.py`, which is deleted. | Step 1 is what opens it, and `Lib/ui/` may not import `gramtrans.standalone` (FR-016) — the same reason exception 6 puts `gate.py` under `Lib/`. Keeping it beside `target_picker.py` is also what keeps the two dialogs behaving identically. | Nothing on the FlexTools path constructs it: `_PageProjectWS` only reaches the import when a `source_binder` was supplied. It imports `PyQt6` and `..api` and nothing else. |

### Amendment (2026-08-17, during T016/T018/T028)

Two rows above were widened once implementation reached them. Both stay inside
the already-enumerated files, and both keep the additive, keyword-only,
defaulted shape:

1. **`projects_root` has to be threaded, not just accepted.** Exception 4 makes
   `RunContextStub.projects_root` injectable, but the shell never calls
   `initialize_run` — `SelectionWizard.__init__` does. So the value has to
   travel `MainFunction` → `_run_gui` → `SelectionWizard` → `initialize_run`,
   exactly alongside `confirmation_gate`. Rows 1 and 2 now say so. The
   alternative — a module-level default in `gt_api` set by the shell — was
   rejected as hidden global state that both hosts would share.
2. **T028 is a wording change in `api.py`, not a new render site.** The wizard
   already shows `str(e)` for `SameProjectError` and `TargetUnavailable`. FR-028
   and FR-029 ask for plain language naming the project; the smallest way to get
   it is to write the exception text in plain language at the raise site. It is
   *not* imported from `gramtrans.standalone.errors`, because FR-016 forbids
   shared code depending on the shell — the shell keeps its own copies, which
   additionally carry the log-file path this layer cannot know.

Explicitly **not** changed, and each is a deliberate finding rather than an
oversight:

- `DEFAULT_SOURCE_PROJECT` and `_headless_phase0` stay exactly as they are.
  FR-005 is a *reachability* requirement and FR-006 makes that path unreachable
  in the standalone by asserting the UI toolkit at startup. Deleting them would
  change FlexTools behaviour for no gain.
- No import-convention refactor anywhere (FR-018) — packaging absorbs the flat
  convention instead (research R6).
- `pyproject.toml` dependency floors are untouched (FR-019/FR-041).

### Amendment (2026-08-17, post-completion) — the source chooser moves to step 1

Rows 7–10 were added after the feature was first marked complete, from live
use: launching the application opened the log window, a modal source chooser
and the wizard at once, and the modal read as a third window with no obvious
relationship to the other two. The chooser is now the Source row of the
wizard's step 1, beside the Target row that was always there.

The shape this takes is the same one exceptions 1–3 already established, and
deliberately so: the host supplies a *capability* (`source_binder`, alongside
`confirmation_gate` and `projects_root`), the shared wizard decides when to ask,
and `None` reproduces FlexTools byte for byte. The alternative — the shell
driving the wizard's page 1 from outside — would need the shell to reach into
`Lib/ui/`, which is the coupling FR-015 and FR-016 exist to prevent.

Two consequences worth naming:

1. **`gramtrans/standalone/source_picker.py` is deleted**, and its dialog moves
   to `Lib/ui/source_picker.py` (row 10). It has to: `Lib/ui/` cannot import the
   shell (FR-016), and the wizard is what opens the dialog now. What stays in
   the shell is the half that is genuinely host-specific — `HostSession.bind_source`
   opening the project read-only and `release()` closing it (FR-007/FR-013).
2. **Source enumeration changes mechanism**, from `flexicon.AllProjectNames()`
   to the same directory walk the target list has always used, rooted at the
   `projects_root` the shell already derives from `FWProjectsDir`. FR-001 is
   still met (the root comes from what FieldWorks records, not a hard-coded
   path) and the two pickers can no longer disagree about which projects exist
   — which they could before, having asked two different questions.

## Phasing

Ordered by the spec's user-story priorities; each phase is independently
demonstrable.

- **P0 — Regression gate and packaging spike.** `.github/workflows/regression.yml`
  and `test_034_flextools_contract.py` land *first*, so FR-021's "runs
  continuously during development" is true from the first commit rather than
  retrofitted. In parallel, a throwaway freeze that does nothing but
  `FLExInitialize()` and open a project, to retire the pythonnet risk (R7) before
  any shell code is written.
- **P1 — US1, preview end to end.** `standalone/` shell: prerequisites, source
  picker, `MainFunction` call with the default-permissive gate, report view, log
  file, clean release of both projects. Exceptions 1, 4 and 5 land here.
- **P2 — US2, the Move gate.** `gate.py` plus exceptions 2 and 3. The gate is
  where FR-022 through FR-027 and FR-054 live.
- **P3 — US3, the release build.** Lock, `build.py`, `.spec`, Inno Setup, smoke
  test, version stamping.
- **P4 — US4, diagnostics.** `--self-check` and the Help-menu route, plus the
  plain-language message for every prerequisite failure.
- **Release gate (not a phase).** The Option C constitution amendment (FR-053),
  the unsigned-artifact and licence documentation (FR-051/FR-052). Release is
  blocked until these land; implementation is not.

## Risks

1. **pythonnet under PyInstaller** (research R7) — retired first, in P0, because
   everything else is wasted if it cannot freeze.
2. **Flat-name shadowing in the frozen bundle** (research R6) — a future
   dependency shipping a top-level `api`/`models`/`report` would silently
   shadow ours. Mitigated by a build-time collision check and caught by the
   smoke test's Preview run.
3. **`flexicon.FWProjectsDir` is `None` post-init** (research R1) — a self-check
   that reads the re-exported package name reports a false negative on a healthy
   machine. The contract pins the correct read.
4. **Target-open-in-FLEx surprises Preview users** — `bind_target` opens the
   target write-enabled in *both* modes, so even a preview needs the target
   closed in FLEx. FR-030 requires saying so up front; the source picker screen
   is the place.
