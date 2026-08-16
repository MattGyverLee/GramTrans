# Contract: Host-Shell Boundary

**Feature**: 034-standalone-windows-app | **Date**: 2026-08-16

The interface between the standalone shell and the shared module. Every
identifier here is normative — the plan's shared-code exception list (FR-020)
and the regression gate (FR-021) both assert against these exact names.

---

## 1. `ConfirmationGate` (structural protocol)

The wizard duck-types this. It imports neither implementation.

```python
class ConfirmationGate(Protocol):
    def confirm(self, target_project_name: str) -> bool: ...
    def finish_page_subtitle(self) -> str: ...
```

| Member | Contract |
|---|---|
| `confirm(target_project_name)` | Called **once**, immediately before `gt_api.execute_move`, and **only** on the Move path (FR-024). Returns `True` to permit the write, `False` to abort with no write and the wizard left intact (FR-025). MUST NOT raise. |
| `finish_page_subtitle()` | The `_PageFinish` subtitle string. Called during page construction. |

### `AlwaysSatisfiedGate` — the default, and the FlexTools gate

Lives in `src/gramtrans/Lib/` alongside the wizard, because the wizard's default
must not reach into `gramtrans.standalone`.

- `confirm()` returns `True` immediately. No dialog, no prompt, no I/O.
- `finish_page_subtitle()` returns, byte for byte, today's literal:
  `"Click 'Execute Move' to write all planned actions to the target project. This is the only write point -- changes can be undone in FLEx with Ctrl+Z."`

### `StandaloneConfirmationGate` — `gramtrans.standalone.gate`

- `confirm()` shows a modal that MUST contain, in plain language: that the
  change **cannot be undone from within the application** (FR-022); that the
  target should be **backed up first** (FR-022); and the Send/Receive recovery
  path — Send/Receive before running, and on a bad run delete the local project
  and receive again (FR-054).
- A text field whose content is compared **exactly** — case-sensitive,
  whitespace-significant — to `target_project_name`. The proceed control is
  disabled until equal, and is **not** the dialog's default button, so neither
  Enter nor a click-through can satisfy it (FR-023).
- Cancel returns `False`.
- `finish_page_subtitle()` returns text that states the write is irreversible and
  MUST NOT mention `Ctrl+Z` or undo (FR-027).

## 2. `MainFunction` — unchanged for FlexTools, extended for the shell

```python
def MainFunction(project, report, modifyAllowed, *, confirmation_gate=None): ...
```

| Rule | |
|---|---|
| FlexTools calls | `MainFunction(project, report, modifyAllowed)` — three positional args, exactly as today. |
| `confirmation_gate=None` | Resolves to `AlwaysSatisfiedGate()`. This is what makes FlexTools byte-identical (SC-013). |
| The shell calls | `MainFunction(source_handle, report_sink, True, confirmation_gate=StandaloneConfirmationGate(...))`. |
| Threading | `MainFunction` → `_run_gui` → `SelectionWizard(..., confirmation_gate=gate)` → `_PageFinish`. |
| Not changed | The `docs` dict, the three positional parameter names, the no-interface fallback, `DEFAULT_SOURCE_PROJECT`, `_headless_phase0`. |

## 3. `SelectionWizard` — one new keyword-only parameter

```python
SelectionWizard(
    host_project, report_sink, modify_allowed, *,
    source_project_name: str,
    parent=None,
    confirmation_gate=None,      # NEW
)
```

`None` → `AlwaysSatisfiedGate()`. Parameter order and every existing name are
unchanged.

## 4. `Lib/api` — projects root becomes injectable

```python
@dataclass(frozen=True)
class RunContextStub:
    source_handle: object
    source_project_name: str
    source_project_path: str
    run_id: str
    started_at: str
    projects_root: str = ""      # NEW, last, defaulted

def initialize_run(host_handle, *, source_project_name, source_project_path="",
                   projects_root=""): ...

def list_target_candidates(stub, projects_root=r"C:\ProgramData\SIL\FieldWorks\Projects"):
    root = stub.projects_root or projects_root
    ...
```

- The FlexTools path passes nothing → the existing literal default applies →
  identical candidate list.
- The shell passes `flexicon.code.FLExGlobals.FWProjectsDir` (post-init), which
  is FR-001's "the location FieldWorks itself records".
- `SameProjectError` and `TargetUnavailable` keep their current meanings and are
  what the shell renders as FR-028 and FR-029 messages respectively.

## 5. Report sink

The shell supplies an object with exactly the four methods FlexTools supplies
(FR-008): `Info(msg)`, `Warning(msg)`, `Error(msg)`, `Blank()`. The shell's
implementation tees each call to the in-app log view (FR-009) and to the run's
log file (FR-038). The view offers save-to-file and copy-to-clipboard (FR-010).

## 6. Startup assertions the shell owns

Run before any project is opened, in this order:

1. **UI toolkit** — import `PyQt6.QtWidgets` and construct a `QApplication`. On
   failure, stop with a plain-language message. The module's no-interface
   fallback MUST NOT be entered (FR-006), which is what makes FR-005 hold.
2. **`flexicon.FLExInitialize()`** — on failure, map to the FieldWorks-missing
   (FR-031), version-unsupported (FR-032) or runtime-load-failed (FR-033)
   message. Never a traceback.
3. **Post-init reads** — `flexicon.code.FLExGlobals.FWCodeDir`,
   `.FWProjectsDir`, `.FWShortVersion`, `.FWLongVersion`,
   `.FW_SUPPORTED_VERSIONS`. **Never** the `flexicon.*` re-exports, which bind
   before initialisation and remain `None` (research R1).
4. **Preview warning** — state on the source-picker screen, before selection,
   that the target must be closed in FLEx *even for a Preview* (FR-030).

## 7. Forbidden in the standalone

| | |
|---|---|
| A read-only launch option or any mode toggle | FR-011 — write permission is a constant `True` |
| Any command-line flag other than `--self-check` | FR-011, and "no headless transfer interface" (Out of Scope) |
| Defaulting the wizard to Move | FR-012 — expressly forbidden |
| Any reachable project name — default, development, or test | FR-005 |
| Persisting last-used projects or selections | "No persistence between runs" (Assumptions) |
| Claiming a Move can be undone, in UI or documentation | FR-027 |
| Detecting or refusing a Send/Receive target | FR-054 — stated, not enforced |
| Importing `gramtrans.standalone` from `gramtrans.py` or `Lib/` | FR-016 — asserted by `test_034_flextools_contract.py` |
