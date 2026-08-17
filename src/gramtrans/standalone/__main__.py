"""Entry point: ``python -m gramtrans.standalone`` / ``GramTrans.exe``.

`contracts/cli-and-selfcheck.md` §1.

    GramTrans.exe                 launch the application
    GramTrans.exe --self-check    print the prerequisite report and exit
    GramTrans.exe --version       print the stamped version and exit

Those two flags are the **only** ones accepted, and that is a requirement
rather than an omission. FR-011 forbids a mode toggle, so there is no
read-only switch; "no headless transfer interface" rules out ``--source``,
``--target``, ``--move`` and ``--preview``. The developer harness
(`run_gui_harness.py`) has ``--source`` and ``--move`` switches and they are
deliberately not carried over: this host's write permission is a constant
``True``, and what decides whether a write happens is the confirmation gate,
not the command line. A flag that could start a Move without a human present
would route straight around the thing US2 exists to build.

Anything else is an error naming the two valid flags — not silently ignored. A
user who typed ``--preview`` needs to be told there is no such thing, not left
believing the run they got was the run they asked for.

Exit codes: ``0`` normal exit or self-check passed; ``1`` self-check failed, or
a prerequisite stopped the application starting; ``2`` invalid arguments.
"""
from __future__ import annotations

import sys
from typing import List, Optional

USAGE = (
    "Usage:\n"
    "  GramTrans                 start the application\n"
    "  GramTrans --self-check    print a diagnostic report and exit\n"
    "  GramTrans --version       print the version and exit\n"
)

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_BAD_ARGS = 2


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv:
        return run_application()

    if len(argv) == 1 and argv[0] == "--version":
        return print_version()

    if len(argv) == 1 and argv[0] == "--self-check":
        return run_self_check()

    print(f"[ERROR] Unrecognised argument(s): {' '.join(argv)}\n", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return EXIT_BAD_ARGS


# ---------------------------------------------------------------------------
# --version
# ---------------------------------------------------------------------------

def print_version() -> int:
    """FR-049. Reads the stamped `_buildinfo`, falling back on a source checkout."""
    from gramtrans.standalone.prereq import _app_version

    print(f"GramTrans {_app_version()}")
    return EXIT_OK


# ---------------------------------------------------------------------------
# --self-check
# ---------------------------------------------------------------------------

def run_self_check() -> int:
    """Print the block and exit `0` PASS / `1` FAIL.

    Creates a real `LogSink` first, so the block reports the log location the
    application would actually use — and so the self-check itself is logged.
    A diagnostic that leaves no trace of having been run is one less thing a
    support conversation can rely on.
    """
    from gramtrans.standalone import selfcheck
    from gramtrans.standalone.logsink import LogSink, make_run_id

    run_id, _started = make_run_id()
    sink = LogSink(run_id)
    try:
        text, report = selfcheck.produce(
            log_path=sink.log_path, log_error=sink.file_error
        )
        print(text)
        for line in text.splitlines():
            sink.Info(line)
        return EXIT_OK if report.overall.value == "PASS" else EXIT_FAILED
    finally:
        sink.close()


# ---------------------------------------------------------------------------
# The application
# ---------------------------------------------------------------------------

def run_application() -> int:
    from gramtrans.standalone.app import HostSession, StartupError

    session = HostSession()
    try:
        try:
            app = session.start()
        except StartupError as exc:
            _show_fatal(exc.message)
            return EXIT_FAILED

        from PyQt6 import QtWidgets

        from gramtrans.standalone.source_picker import (
            SourcePickerDialog,
            enumerate_projects,
        )
        from gramtrans.standalone.window import GramTransWindow

        # The window opens before the source is chosen, so the report view and
        # the Help menu exist for the whole session -- including while the
        # modal wizard is up, and after it closes.
        window = GramTransWindow(session)
        window.show()
        app.processEvents()

        try:
            names = enumerate_projects()
        except Exception as exc:  # noqa: BLE001
            from gramtrans.standalone import errors

            _show_fatal(errors.describe_startup_failure(exc, session.log_path))
            return EXIT_FAILED

        picker = SourcePickerDialog(names, parent=window)
        if picker.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            # Cancel is a normal exit -- and still goes through release().
            return EXIT_OK

        chosen = picker.selected_project_name()
        if chosen is None:
            return EXIT_OK

        try:
            session.bind_source(chosen)
        except StartupError as exc:
            _show_fatal(exc.message)
            return EXIT_FAILED

        session.run()
        window.refresh()

        # FR-026: if the user confirmed a Move and the run reported an error,
        # say plainly that the target may be partially modified and how to
        # find what was written. Shown after the wizard closes, because until
        # then the user is still looking at the run.
        partial = session.partial_failure_message()
        if partial:
            _show_fatal(partial)

        # The window stays up after the run so the report is still readable
        # (FR-009). Closing it ends the session, and the `finally` releases.
        app.exec()
        return EXIT_OK
    except Exception as exc:  # noqa: BLE001 — the last-resort funnel
        return _handle_unexpected(session, exc)
    finally:
        # FR-013 / SC-005: normal close, cancel, error and failed run all
        # release both projects. This `finally` is the single place that is
        # true for every one of them.
        session.release()


def _handle_unexpected(session, exc: BaseException) -> int:
    """Last resort: an unexpected exception must still reach the log.

    Without this the exception escapes `main()` and is caught by PyInstaller's
    bootloader, which shows its own "Failed to execute script '__main__'"
    dialog carrying a raw traceback, and writes **nothing** to our log. That is
    the worst available combination: `RELEASE-NOTES.md` tells the user to send
    the log file when something breaks, and for this class of failure the log
    would end at the last thing that went *right* -- which is precisely what
    the first portable build did, stopping at "Session released." while the
    real failure was a missing bundled data file.

    So the traceback goes to the log, where support can read it, and the user
    gets the same plain sentence every other failure gives them. The mapper is
    reused rather than reimplemented: an unexpected exception is by definition
    the case its fall-through branch already handles.
    """
    import traceback

    from gramtrans.standalone import errors

    detail = traceback.format_exc()
    try:
        session.report_sink.Error(
            f"[GramTrans] Unhandled {type(exc).__name__}: {exc}"
        )
        for line in detail.rstrip().splitlines():
            session.report_sink.Error(line)
    except Exception:  # noqa: BLE001 — the dialog below is the part that matters
        print(detail, file=sys.stderr)

    _show_fatal(errors.describe_startup_failure(exc, session.log_path))
    return EXIT_FAILED


def _show_fatal(message: str) -> None:
    """Show a plain-language failure, with a console fallback.

    A modal is the right surface for the users FR-036 is written for, but the
    message must still arrive when the toolkit itself is what failed — which
    is exactly when a modal cannot be shown.
    """
    print(message, file=sys.stderr)
    try:
        from PyQt6 import QtWidgets

        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication([])
        QtWidgets.QMessageBox.critical(None, "GramTrans", message)
    except Exception:  # noqa: BLE001 — the console copy above already landed
        pass


if __name__ == "__main__":
    sys.exit(main())
