"""The three silent deaths `_handle_unexpected` cannot see.

`__main__._handle_unexpected` is the last-resort funnel for an exception that
*escapes* `run_application()`. It works by catching, so it only ever sees a
failure that unwinds Python. Three failure modes reach the user as a window
that vanishes with nothing in the log, because none of them unwinds:

1. **A Python exception raised inside a Qt callback.** Slots, and reimplemented
   virtuals like `QWizardPage.initializePage`, `QWizardPage.nextId` and
   `QStyledItemDelegate.paint`, are called *from C++*. There is no Python frame
   above them to catch, so PyQt6 calls `sys.excepthook` and then `qFatal()` --
   which calls `abort()`. The process is gone before `run_application`'s
   `except` is reachable. Seen in Windows Error Reporting as exception code
   `0xc0000409` (FAST_FAIL_FATAL_APP_EXIT) faulting in `Qt6Core.dll`.

2. **Qt's own fatal message.** `qFatal()` from inside Qt -- a re-entrancy
   assertion, a deleted-object-in-use, a missing plugin -- prints its reason to
   stderr and aborts. Same `0xc0000409`, and the reason is the only thing that
   explains it.

3. **A native access violation.** An LCM/.NET or Qt memory fault
   (`0xc0000005`) kills the process with no Python involvement at all.

In a windowed PyInstaller build (`console=False`) `sys.stderr` goes nowhere, so
each of the three loses its own explanation as well as its log entry. This
module puts every one on the record *before* the process dies:

* `sys.excepthook` / `threading.excepthook` -> the traceback, to the run log.
* `qInstallMessageHandler` -> Qt's warnings and its fatal reason, to the run log.
* `faulthandler` -> a native stack, to a sibling file (`faulthandler` writes to
  a file descriptor from a fault context, which the `LogSink` is not).

`RELEASE-NOTES.md` asks the user to send the log file when something breaks.
This is what makes that instruction true for the failures most worth sending.
"""

from __future__ import annotations

import faulthandler
import os
import sys
import threading
import traceback
from typing import Any, Callable, Optional

# Kept so `install()` is idempotent: it is called once, but a second call must
# not chain a hook onto our own hook and report everything twice.
_installed = False
_fault_stream: Optional[Any] = None


def native_log_path(log_path: str) -> str:
    """Sibling of the run log, for `faulthandler`'s native stacks.

    A separate file keeps a native stack -- which is noise to the user -- out of
    the report view they are asked to read, and gives `faulthandler` the real
    file descriptor it needs.
    """
    base, _ext = os.path.splitext(log_path)
    return f"{base}-native.txt"


def install(report_sink: Any, log_path: str = "") -> None:
    """Route the three unwind-free failure modes to `report_sink`.

    Call once, as early as a report sink exists, and always *before* the Qt
    event loop starts -- a hook installed after the exception it was meant to
    catch is a hook that was never there.

    Every hook here is written to survive a broken sink: they run while the
    process is already failing, and a hook that raises would replace a
    diagnosable crash with an undiagnosable one.
    """
    global _installed, _fault_stream
    if _installed:
        return
    _installed = True

    def _emit(level: str, block: str) -> None:
        """Best-effort write of a multi-line block to the log, then stderr."""
        emit = getattr(report_sink, level, None)
        for line in str(block).rstrip().splitlines() or [""]:
            try:
                if emit is None:  # pragma: no cover - sink without the 4 methods
                    raise AttributeError(level)
                emit(line)
            except Exception:  # noqa: BLE001 - stderr is the only fallback left
                try:
                    print(line, file=sys.stderr)
                except Exception:  # noqa: BLE001 - windowed build: no stderr
                    pass

    # -- 1. Python exception inside a Qt callback ---------------------------
    #
    # PyQt6 calls this and *then* aborts, so this is the only chance the
    # traceback gets. It deliberately does not try to keep the process alive:
    # PyQt6 has already decided to abort and we cannot veto that. The goal is
    # for the log to name the line, not to survive.
    _prev_excepthook = sys.excepthook

    def _excepthook(etype, exc, tb) -> None:
        # Not every raising virtual aborts. `paint()` and `sizeHint()` are
        # called once per item per repaint, so the same exception can arrive
        # hundreds of times while the window is still up. Reporting each one
        # would bury the run in a single repeated traceback -- and the run log
        # is a document the user is asked to read and send. The first few are
        # the diagnosis; the rest are a count.
        if _suppressed(_repeat_key(etype, exc, tb), _emit):
            return
        _emit("Error", f"[GramTrans] Unhandled {etype.__name__}: {exc}")
        _emit("Error", "".join(traceback.format_exception(etype, exc, tb)))
        _emit("Error", _abort_note(log_path))
        _flush(report_sink)
        try:
            _prev_excepthook(etype, exc, tb)
        except Exception:  # noqa: BLE001 - we have already recorded it
            pass

    sys.excepthook = _excepthook

    # -- 1b. The same thing on a worker thread -----------------------------
    def _threadhook(args) -> None:
        if args.exc_type is SystemExit:
            return
        name = getattr(args.thread, "name", "?")
        _emit("Error", f"[GramTrans] Unhandled {args.exc_type.__name__} "
                       f"on thread {name!r}: {args.exc_value}")
        _emit("Error", "".join(traceback.format_exception(
            args.exc_type, args.exc_value, args.exc_traceback)))
        _flush(report_sink)

    threading.excepthook = _threadhook

    # -- 2. Qt's own messages, including its fatal reason ------------------
    _install_qt_handler(_emit, report_sink, log_path)

    # -- 3. Native faults --------------------------------------------------
    if log_path:
        try:
            _fault_stream = open(  # noqa: SIM115 - must outlive this function
                native_log_path(log_path), "a", encoding="utf-8", buffering=1
            )
            faulthandler.enable(file=_fault_stream, all_threads=True)
        except Exception:  # noqa: BLE001 - a log we cannot open is not fatal
            _fault_stream = None
    if _fault_stream is None:
        try:
            faulthandler.enable(all_threads=True)
        except Exception:  # noqa: BLE001 - no usable stderr in a windowed build
            pass


def _install_qt_handler(
    emit: Callable[[str, str], None], report_sink: Any, log_path: str
) -> None:
    """Send Qt's message stream to the log.

    Qt's fatal message is the *only* record of case 2, and its warnings are
    frequently the breadcrumb before case 1 (a "QWizard: ..." warning
    immediately before a page's slot raises). Both are invisible in a windowed
    build.

    Debug and info are dropped: Qt is chatty, and the run log is a document the
    user is asked to read and send.
    """
    try:
        from PyQt6 import QtCore
    except Exception:  # noqa: BLE001 - no Qt means no Qt messages to catch
        return

    levels = {
        QtCore.QtMsgType.QtWarningMsg: ("Warning", "Qt warning"),
        QtCore.QtMsgType.QtCriticalMsg: ("Error", "Qt critical"),
        QtCore.QtMsgType.QtFatalMsg: ("Error", "Qt FATAL"),
    }

    def _handler(mode, context, message) -> None:
        entry = levels.get(mode)
        if entry is None:
            return
        level, label = entry
        where = ""
        try:
            if context is not None and context.file:
                where = f"  ({context.file}:{context.line})"
        except Exception:  # noqa: BLE001 - the message matters, not the site
            pass
        emit(level, f"[GramTrans] {label}: {message}{where}")
        if mode is QtCore.QtMsgType.QtFatalMsg:
            # Qt aborts the moment this returns, so the stack goes out now.
            emit("Error", "".join(traceback.format_stack()))
            emit("Error", _abort_note(log_path))
            _flush(report_sink)

    try:
        QtCore.qInstallMessageHandler(_handler)
    except Exception:  # noqa: BLE001 - Qt without a settable handler
        pass


# How many times one distinct exception is reported in full before the funnel
# starts counting instead. Three is enough to show it is a repeat rather than a
# one-off, and small enough that a per-repaint raise cannot bury the run.
_REPEAT_LIMIT = 3
_repeats: dict = {}


def _repeat_key(etype, exc, tb) -> tuple:
    """Identity of a repeating failure: its type, message and raising line.

    The innermost frame is what distinguishes "the same delegate raising on
    every row" from two different bugs that share an exception type.
    """
    site: tuple = ()
    try:
        last = traceback.extract_tb(tb)[-1]
        site = (last.filename, last.lineno, last.name)
    except Exception:  # noqa: BLE001 - a key without a site still dedups
        pass
    return (etype.__name__, str(exc)) + site


def _suppressed(key: tuple, emit: Callable[[str, str], None]) -> bool:
    """True once `key` has been reported `_REPEAT_LIMIT` times.

    Emits one line at the threshold so the log says it is suppressing rather
    than going quiet, and a running count every hundred after that so a storm
    is still visible as a storm.
    """
    seen = _repeats[key] = _repeats.get(key, 0) + 1
    if seen <= _REPEAT_LIMIT:
        return False
    if seen == _REPEAT_LIMIT + 1:
        emit("Error", f"[GramTrans] ... {key[0]}: {key[1]} is repeating; "
                      "further identical reports suppressed.")
    elif seen % 100 == 0:
        emit("Error", f"[GramTrans] ... {key[0]}: {key[1]} x{seen}")
    return True


def _abort_note(log_path: str) -> str:
    """The sentence that turns an abort into something the user can report."""
    tail = f" Log: {log_path}" if log_path else ""
    return (
        "[GramTrans] The application is about to close on this error. Nothing "
        "was written to either project unless a Move was already "
        f"confirmed.{tail}"
    )


def _flush(report_sink: Any) -> None:
    """Force the sink's buffer out: `abort()` runs no `atexit` and no `finally`."""
    for attr in ("flush", "_flush"):
        fn = getattr(report_sink, attr, None)
        if callable(fn):
            try:
                fn()
            except Exception:  # noqa: BLE001
                pass
    # `LogSink` opens its file line-buffered as `_handle`; the fsync is what
    # makes the last line survive an `abort()`, which runs no `atexit`.
    stream = getattr(report_sink, "_handle", None)
    try:
        if stream is not None:
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:  # noqa: BLE001 - an unflushable sink is not worth raising
        pass
    for std in (sys.stdout, sys.stderr):
        try:
            if std is not None:
                std.flush()
        except Exception:  # noqa: BLE001
            pass
