"""Entry point: ``python -m gramtrans.standalone`` / ``GramTrans.exe``.

Argument handling proper is T050 (`contracts/cli-and-selfcheck.md` §1); for now
this accepts **no** arguments at all, and says so for anything it is given.
That is not a placeholder — it is the requirement. FR-011 forbids a mode
toggle, and "no headless transfer interface" rules out `--source`, `--target`,
`--move` and `--preview`. The developer harness's `--source` / `--move`
switches are deliberately not carried over: this host's write permission is a
constant `True`, and the thing that decides whether a write happens is the
confirmation gate, not the command line.

The flow is deliberately linear, and every exit goes through `release()`:

    prerequisites -> choose source -> hand to MainFunction -> release

Exit codes (the subset T050 will complete): ``0`` normal, ``2`` invalid
arguments.
"""
from __future__ import annotations

import sys
from typing import List, Optional

USAGE = (
    "GramTrans takes no command-line arguments.\n"
    "Run it with no arguments to start the application."
)


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        # Wrong arguments are an error, not a silently ignored extra: a user
        # who typed `--preview` needs to be told there is no such thing, not
        # left believing the run they got was the run they asked for.
        print(f"[ERROR] Unrecognised argument(s): {' '.join(argv)}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2

    return run_application()


def run_application() -> int:
    from gramtrans.standalone.app import HostSession, StartupError

    session = HostSession()
    try:
        try:
            app = session.start()
        except StartupError as exc:
            _show_fatal(exc.message)
            return 1

        from PyQt6 import QtWidgets

        from gramtrans.standalone.source_picker import (
            SourcePickerDialog,
            enumerate_projects,
        )

        try:
            names = enumerate_projects()
        except Exception as exc:  # noqa: BLE001
            from gramtrans.standalone import errors

            _show_fatal(errors.describe_startup_failure(exc, session.log_path))
            return 1

        picker = SourcePickerDialog(names)
        if picker.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            # Cancel is a normal exit -- and still goes through release().
            return 0

        chosen = picker.selected_project_name()
        if chosen is None:
            return 0

        try:
            session.bind_source(chosen)
        except StartupError as exc:
            _show_fatal(exc.message)
            return 1

        session.run()
        _ = app
        return 0
    finally:
        # FR-013 / SC-005: normal close, cancel, error and failed run all
        # release both projects. This `finally` is the single place that is
        # true for every one of them.
        session.release()


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
