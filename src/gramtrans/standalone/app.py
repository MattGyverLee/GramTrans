"""`HostSession` — the shell's stand-in for a FlexTools run (`data-model.md`).

FlexTools hands the module four things: an open source project, a report sink,
a `modifyAllowed` flag, and a run wrapper. This class is all four, for a host
that has none of them.

```
CREATED -> PREREQ_OK -> RUNNING -> RELEASED
   |           |           |
   +-----------+-----------+--> FAILED -> RELEASED
```

`SOURCE_BOUND` sits between `PREREQ_OK` and `RUNNING` for a caller that binds
a source *before* running (the parity test does, and `build_stub` needs one).
The application itself no longer takes that route: the source is chosen on
step 1 of the wizard, beside the target, so `bind_source` is called from inside
`RUNNING` and leaves the state alone. Opening a modal project chooser *before*
the wizard meant three windows appearing at once with no obvious order to them,
and the wizard's step 1 is already the screen that asks this question.

`RELEASED` is reachable from every state and is always reached (FR-013,
SC-005). Two FLEx projects left locked by a crashed transfer tool is a bad
afternoon for a linguist with no other way to open their data, so release is
wired to normal close, cancel, error and failed run alike, and is idempotent.

**`modify_allowed` is a hard-coded `True`** (FR-011). Not a flag, not an
argument, not an attribute that can be `False`. FlexTools has a read-only mode
because FlexTools has a host-level toggle; reproducing it here would create a
second, quieter way to prevent a write, and the wizard already opens in
Preview (FR-012) with Move behind a dry run and the confirmation gate. There
is no state in which this is `False`, which is why it is a class constant.

**Startup order is fixed by `contracts/host-shell.md` §6** and is not
arbitrary:

1. UI toolkit first, because if it fails there is no way to *show* any later
   failure — and because `MainFunction`'s no-interface fallback must never be
   entered (FR-006), which is what makes FR-005 hold.
2. `import flexicon` next. This, not `FLExInitialize()`, is where a missing
   FieldWorks presents: flexicon runs `InitialiseFWGlobals()` at import scope
   and it raises when the registry key is absent. Measured, not assumed — see
   probe-results.md §T012.
3. `FLExInitialize()`, then and only then the FieldWorks values, through
   `fwglobals` and nowhere else.
"""
from __future__ import annotations

import enum
import logging
from typing import Optional

_log = logging.getLogger(__name__)

__all__ = ["SessionState", "HostSession", "StartupError"]


class SessionState(enum.Enum):
    CREATED = "created"
    PREREQ_OK = "prereq_ok"
    SOURCE_BOUND = "source_bound"
    RUNNING = "running"
    FAILED = "failed"
    RELEASED = "released"


class StartupError(Exception):
    """A prerequisite failed. Carries the plain-language message to show.

    The message is built at the raise site, where the failure type is known,
    so callers never have to re-derive the FR-031 / FR-033 distinction.
    """

    def __init__(self, message: str, cause: Optional[BaseException] = None) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause


class HostSession:
    """One application launch that reaches project selection."""

    # FR-011. A constant, not a field: there must be no state in which the
    # standalone runs write-disabled, and no argument that could make it so.
    MODIFY_ALLOWED = True

    def __init__(self, log_dir: Optional[str] = None) -> None:
        from gramtrans.standalone.logsink import LogSink, make_run_id

        self.run_id, self.started_at = make_run_id()
        self.report_sink = LogSink(self.run_id, log_dir=log_dir)
        self.state = SessionState.CREATED
        self.source_handle = None
        self.source_project_name = ""
        self._flexicon = None
        self._qapp = None
        self._confirmation_gate = None

    # -- properties --------------------------------------------------------

    @property
    def modify_allowed(self) -> bool:
        return self.MODIFY_ALLOWED

    @property
    def log_path(self) -> str:
        return self.report_sink.log_path

    # -- startup (contract §6) --------------------------------------------

    def start(self):
        """Run the startup assertions in order. Returns the QApplication.

        Raises `StartupError` with a message ready to show. Never a traceback:
        the detail goes to the log, the sentence goes to the user.
        """
        from gramtrans.standalone import errors, fwglobals

        self.report_sink.Info(f"[GramTrans] Standalone host  run_id={self.run_id}")
        self.report_sink.Info(f"  Log file: {self.log_path}")

        # 1. UI toolkit (FR-006).
        try:
            from PyQt6 import QtWidgets
        except Exception as exc:  # noqa: BLE001
            raise self._fail(errors.runtime_failed_to_start(
                "PyQt6 (the user interface toolkit)", str(exc), self.log_path
            ), exc) from exc
        try:
            self._qapp = QtWidgets.QApplication.instance()
            if self._qapp is None:
                self._qapp = QtWidgets.QApplication([])
        except Exception as exc:  # noqa: BLE001
            raise self._fail(errors.runtime_failed_to_start(
                "the Windows user interface", str(exc), self.log_path
            ), exc) from exc
        self.report_sink.Info("  User interface: OK")

        # 2. import flexicon -> FR-031 (see the module docstring).
        try:
            self._flexicon = fwglobals.probe()
        except fwglobals.FieldWorksNotDetected as exc:
            raise self._fail(
                errors.fieldworks_not_installed(self.log_path), exc
            ) from exc

        # 3. FLExInitialize() -> FR-033.
        try:
            self._flexicon.FLExInitialize()
        except Exception as exc:  # noqa: BLE001
            raise self._fail(errors.runtime_failed_to_start(
                "the FieldWorks language model", str(exc), self.log_path
            ), exc) from exc
        fwglobals.mark_initialized()

        # 4. Post-init reads, through fwglobals only, plus the FR-032 check.
        try:
            supported = fwglobals.supported_versions()
            detected = fwglobals.short_version()
            major = fwglobals.major_version()
            self.report_sink.Info(f"  FieldWorks: {detected}")
            self.report_sink.Info(f"  Code dir:   {fwglobals.code_dir()}")
            self.report_sink.Info(f"  Projects:   {fwglobals.projects_dir()}")
        except fwglobals.FieldWorksRuntimeUnavailable as exc:
            raise self._fail(
                errors.describe_startup_failure(exc, self.log_path), exc
            ) from exc

        if major not in supported:
            raise self._fail(errors.unsupported_fieldworks_version(
                detected, supported, self.log_path
            ), None)

        self.state = SessionState.PREREQ_OK
        return self._qapp

    def _fail(self, message: str, cause: Optional[BaseException]) -> StartupError:
        self.state = SessionState.FAILED
        self.report_sink.Error(message.replace("\n", " "))
        if cause is not None:
            _log.exception("HostSession startup failed", exc_info=cause)
        return StartupError(message, cause)

    # -- source selection --------------------------------------------------
    #
    # Enumeration is not here. The wizard's step 1 lists projects through
    # `Lib/api.list_source_candidates(projects_root)` -- the same directory rule
    # and the same root the target list has always used, so the two lists cannot
    # disagree about what a project is or where they live. What stays the
    # shell's business is *opening* one, below, and closing it in `release()`.

    def bind_source(self, project_name: str):
        """Open the chosen project **read-only** (FR-007).

        `writeEnabled=False` is the shell's only defence for the source: the
        engine reads it and the wizard never opens it for write, but the
        source is the user's other real project and a read-only handle makes
        "we did not touch it" a property of the open rather than a promise.

        This is also what the wizard's step-1 source picker calls, through the
        `source_binder` it is handed: the picker chooses, the session opens, so
        the handle stays owned by the thing that has to release it (FR-013).
        Re-picking is therefore normal here, and closes the previous source
        first -- otherwise a user who changed their mind would leave a
        read-only handle open for the rest of the process with nothing holding
        a reference to it.
        """
        from gramtrans.standalone import errors

        if self._flexicon is None:
            raise StartupError(errors.runtime_failed_to_start(
                "the FieldWorks language model",
                "the session was not started", self.log_path,
            ))

        self._close_source()
        handle = self._flexicon.FLExProject()
        try:
            handle.OpenProject(projectName=project_name, writeEnabled=False)
        except Exception as exc:  # noqa: BLE001 — LCM raises a variety of types
            self.report_sink.Error(
                f"[GramTrans] Could not open source {project_name!r}: {exc}"
            )
            raise self._open_failed(project_name, exc) from exc

        self.source_handle = handle
        self.source_project_name = project_name
        # Do not walk the state machine backwards: the wizard binds the source
        # from *inside* the run, so RUNNING is already the further state.
        if self.state is not SessionState.RUNNING:
            self.state = SessionState.SOURCE_BOUND
        self.report_sink.Info(f"  Source (read-only): {project_name!r}")
        return handle

    def _close_source(self) -> None:
        """Close the currently-open source handle, if any. Never raises.

        Shared by `release()` and by a re-pick in `bind_source`, so both routes
        out of a source handle are the same code and cannot diverge.
        """
        if self.source_handle is None:
            return
        try:
            self.source_handle.CloseProject()
            self.report_sink.Info("[GramTrans] Source project closed.")
        except Exception as exc:  # noqa: BLE001
            self.report_sink.Warning(
                f"[GramTrans] Could not close the source project: {exc}"
            )
            _log.exception("_close_source: CloseProject() raised")
        finally:
            self.source_handle = None

    def _open_failed(self, project_name: str, exc: BaseException) -> Exception:
        """FR-034 / FR-035 — attributed to the project, by type where it matters."""
        from gramtrans.standalone import errors

        migration = getattr(self._flexicon, "FP_MigrationRequired", None)
        if migration is not None and isinstance(exc, migration):
            return StartupError(errors.migration_required(project_name, self.log_path), exc)
        return StartupError(
            errors.project_cannot_be_opened(project_name, str(exc), self.log_path), exc
        )

    def source_project_path(self) -> str:
        """Best-effort on-disk path for the source, for same-project detection.

        flexicon does not expose it directly, so fall back to composing it from
        the projects root — which matters, because `bind_target`'s path-based
        `SameProjectError` check is the half that catches two names pointing at
        one directory.
        """
        from gramtrans.standalone import fwglobals

        for attr in ("ProjectPath", "ProjectFilename", "ProjectFolder"):
            try:
                v = getattr(self.source_handle, attr)
                value = v() if callable(v) else str(v)
                if value:
                    return value
            except Exception:  # noqa: BLE001
                continue
        try:
            import os

            candidate = os.path.join(fwglobals.projects_dir(), self.source_project_name)
            return candidate if os.path.isdir(candidate) else ""
        except Exception:  # noqa: BLE001
            return ""

    def build_stub(self):
        """The `RunContextStub` this host would hand the wizard.

        Exposed as its own step because it is the exact boundary the parity
        test compares (T015): same engine, same selection, one differing
        input — `projects_root`.
        """
        from gramtrans.Lib import api as gt_api
        from gramtrans.standalone import fwglobals

        return gt_api.initialize_run(
            self.source_handle,
            source_project_name=self.source_project_name,
            source_project_path=self.source_project_path(),
            projects_root=fwglobals.projects_dir(),
        )

    # -- the run -----------------------------------------------------------

    def run(self) -> None:
        """Hand control to the shared module, exactly as FlexTools would.

        Calls `MainFunction` rather than constructing `SelectionWizard`
        directly: `MainFunction`/`_run_gui` also own the QApplication setup,
        the debug-logging hook, the fatal-exception funnel and the
        target-handle `CloseProject()` that FR-013 depends on. Re-implementing
        those here is the forking FR-015 forbids.

        `source_binder=self.bind_source` is what lets the source be chosen on
        step 1 instead of in a modal before the window: the wizard picks, this
        session opens read-only, and the handle stays owned by the object whose
        `release()` closes it. `self.source_handle` is therefore normally `None`
        at this point, and that is expected -- a caller that bound a source
        first (the parity test) simply passes it through instead.
        """
        from gramtrans.gramtrans import MainFunction
        from gramtrans.standalone import fwglobals

        if self.state not in (SessionState.PREREQ_OK, SessionState.SOURCE_BOUND):
            raise RuntimeError(
                f"run() requires a started session; state is {self.state.value}"
            )
        self.state = SessionState.RUNNING
        try:
            MainFunction(
                self.source_handle,
                self.report_sink,
                self.MODIFY_ALLOWED,
                confirmation_gate=self._gate(),
                projects_root=fwglobals.projects_dir(),
                source_binder=self.bind_source,
            )
        except Exception:
            self.state = SessionState.FAILED
            raise

    def _gate(self):
        """The host's confirmation gate — the first call site that supplies one.

        Built lazily and kept, so `gate.last_decision` is readable after the
        run: "the Move happened" and "the user confirmed it" then have separate
        evidence in the log, which is what a partial-failure report (FR-026)
        needs to be trustworthy.
        """
        if self._confirmation_gate is None:
            from gramtrans.standalone.gate import StandaloneConfirmationGate

            self._confirmation_gate = StandaloneConfirmationGate()
        return self._confirmation_gate

    @property
    def gate(self):
        return self._confirmation_gate

    # -- FR-026 ------------------------------------------------------------

    def partial_failure_message(self) -> Optional[str]:
        """The FR-026 message, or `None` if this run does not warrant one.

        Warranted when **both**: the user confirmed a Move through the gate,
        and the run reported an error. Neither alone is enough — a confirmed
        Move that succeeded needs no warning, and an error on a Preview cannot
        have modified anything.

        This is an inference rather than a caught exception, and deliberately
        so. The write happens inside the wizard, and `MainFunction` funnels any
        exception into `report.Error(...)` by design — reaching in to intercept
        it would mean the shell re-implementing the host boundary that FR-015
        forbids it to fork. Inference is also why the message says the target
        "may be" partially modified: that is genuinely all we know, and
        claiming more precision than we have is the failure mode to avoid here.
        """
        from gramtrans.standalone import errors

        gate = self._confirmation_gate
        if gate is None or getattr(gate, "last_decision", None) is not True:
            return None
        if not any(line.startswith("[ERROR]") for line in self.report_sink.lines()):
            return None
        return errors.move_failed_partway(
            self._confirmed_target or "the target project",
            self.run_id,
            self.log_path,
        )

    @property
    def _confirmed_target(self) -> str:
        """The project name the user typed into the gate, if any."""
        gate = self._confirmation_gate
        return getattr(gate, "last_target_name", "") if gate else ""

    # -- release (FR-013, SC-005) -----------------------------------------

    def release(self) -> None:
        """Close the source and shut flexicon down. Idempotent.

        `MainFunction`'s existing `finally` closes the *target*; this closes
        the source and calls `FLExCleanup()`. Idempotent because it is wired
        to several exit paths that can overlap — a second call must be a
        no-op, not a second failure to report.
        """
        if self.state is SessionState.RELEASED:
            return

        self._close_source()

        if self._flexicon is not None:
            try:
                self._flexicon.FLExCleanup()
            except Exception as exc:  # noqa: BLE001
                _log.warning("release: FLExCleanup() raised: %s", exc)
            finally:
                self._flexicon = None

        # NOT cleared: `fwglobals`' initialised flag. `FLExCleanup()` shuts
        # down the SLDR/ICU session, but the FieldWorks *globals* were read
        # from the registry at `import flexicon` and remain valid — the paths
        # and versions did not stop being true. Clearing the flag here would
        # make a later read raise "read before FLExInitialize() completed",
        # which is a startup-ordering claim that would simply be false. The
        # flag is process-scoped because flexicon's own initialisation is.
        self.state = SessionState.RELEASED
        self.report_sink.Info("[GramTrans] Session released.")
        self.report_sink.close()

    def __enter__(self) -> "HostSession":
        return self

    def __exit__(self, *exc_info) -> None:
        self.release()
