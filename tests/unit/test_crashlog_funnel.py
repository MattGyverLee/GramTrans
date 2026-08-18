"""The crash funnel must record the failures that do not unwind.

These are regression tests for a real silent crash: the portable build closed
with no dialog and a log that ended at the last thing that went right, because
the exception was raised inside a Qt virtual and PyQt6 answered it with
`qFatal()`/`abort()` -- which no `except` clause can see.

The tests here do not need Qt: `crashlog` installs hooks and the hooks are
callable, so what matters is that invoking one puts the traceback on the sink.
The Qt half is covered by `test_qt_handler_is_installed_when_qt_present`, which
skips cleanly on a headless checkout without PyQt6.
"""

from __future__ import annotations

import sys
import threading

import pytest

from gramtrans.standalone import crashlog


class FakeSink:
    """A `LogSink`-shaped sink that keeps its lines."""

    def __init__(self) -> None:
        self.lines: list[tuple[str, str]] = []

    def Info(self, msg: str = "") -> None:  # noqa: N802 - host-mandated name
        self.lines.append(("INFO", msg))

    def Warning(self, msg: str = "") -> None:  # noqa: N802
        self.lines.append(("WARN", msg))

    def Error(self, msg: str = "") -> None:  # noqa: N802
        self.lines.append(("ERROR", msg))

    def Blank(self) -> None:  # noqa: N802
        self.lines.append(("", ""))

    def text(self) -> str:
        return "\n".join(m for _lvl, m in self.lines)


@pytest.fixture
def sink(monkeypatch, tmp_path):
    """A funnel installed on a fresh sink, with global state restored after."""
    monkeypatch.setattr(crashlog, "_installed", False)
    monkeypatch.setattr(crashlog, "_repeats", {})
    monkeypatch.setattr(sys, "excepthook", sys.__excepthook__)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    s = FakeSink()
    crashlog.install(s, str(tmp_path / "run.log"))
    return s


def _raise_and_hook(exc: BaseException) -> None:
    """Send `exc` through `sys.excepthook`, as PyQt6 does before aborting."""
    try:
        raise exc
    except BaseException:  # noqa: BLE001 - the point is to hand it to the hook
        sys.excepthook(*sys.exc_info())


def test_excepthook_logs_type_message_and_traceback(sink):
    _raise_and_hook(ValueError("preview blew up"))
    text = sink.text()
    assert "ValueError" in text
    assert "preview blew up" in text
    assert "Traceback (most recent call last)" in text
    # The raising function must be named: "which line" is the whole point.
    assert "_raise_and_hook" in text


def test_excepthook_says_the_app_is_closing_and_names_the_log(sink, tmp_path):
    _raise_and_hook(RuntimeError("nope"))
    text = sink.text()
    assert "about to close" in text
    assert str(tmp_path / "run.log") in text
    # FR-013's promise must not be overstated on a crash path.
    assert "unless a Move was already confirmed" in text


def test_repeats_are_collapsed_not_dropped_silently(sink):
    for _ in range(50):
        _raise_and_hook(ValueError("same every repaint"))
    text = sink.text()
    assert text.count("Traceback (most recent call last)") == crashlog._REPEAT_LIMIT
    assert "further identical reports suppressed" in text


def test_distinct_failures_are_not_collapsed_into_each_other(sink):
    for _ in range(10):
        _raise_and_hook(ValueError("first"))
    _raise_and_hook(KeyError("second"))
    text = sink.text()
    assert "first" in text and "second" in text
    assert "KeyError" in text


def test_thread_exceptions_reach_the_log(sink):
    def boom() -> None:
        raise OSError("worker died")

    t = threading.Thread(target=boom, name="gt-worker")
    t.start()
    t.join()
    text = sink.text()
    assert "OSError" in text
    assert "worker died" in text
    assert "gt-worker" in text


def test_install_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(crashlog, "_installed", False)
    monkeypatch.setattr(crashlog, "_repeats", {})
    monkeypatch.setattr(sys, "excepthook", sys.__excepthook__)
    s = FakeSink()
    crashlog.install(s, str(tmp_path / "run.log"))
    first = sys.excepthook
    crashlog.install(s, str(tmp_path / "run.log"))
    assert sys.excepthook is first, "a second install chained a duplicate hook"
    _raise_and_hook(ValueError("once"))
    assert s.text().count("Unhandled ValueError") == 1


def test_a_broken_sink_does_not_replace_the_crash_with_its_own(monkeypatch, tmp_path):
    """A sink that raises must not turn a diagnosable crash into a new one."""
    class BrokenSink:
        def Error(self, msg: str = "") -> None:  # noqa: N802
            raise OSError("disk full")

    monkeypatch.setattr(crashlog, "_installed", False)
    monkeypatch.setattr(crashlog, "_repeats", {})
    monkeypatch.setattr(sys, "excepthook", sys.__excepthook__)
    crashlog.install(BrokenSink(), str(tmp_path / "run.log"))
    _raise_and_hook(ValueError("still needs to be survivable"))  # must not raise


def test_native_log_path_is_a_sibling_of_the_run_log():
    assert crashlog.native_log_path(r"C:\logs\gramtrans-GT-1.log") == (
        r"C:\logs\gramtrans-GT-1-native.txt"
    )


def test_qt_handler_is_installed_when_qt_present(monkeypatch, tmp_path):
    """Qt's own `qFatal` reason is the only record of a Qt-side abort."""
    pytest.importorskip("PyQt6")
    from PyQt6 import QtCore

    installed = {}

    def fake_install(handler):
        installed["handler"] = handler

    monkeypatch.setattr(QtCore, "qInstallMessageHandler", fake_install)
    monkeypatch.setattr(crashlog, "_installed", False)
    monkeypatch.setattr(crashlog, "_repeats", {})
    s = FakeSink()
    crashlog.install(s, str(tmp_path / "run.log"))

    assert "handler" in installed, "Qt messages would have gone to a dead stderr"
    installed["handler"](QtCore.QtMsgType.QtCriticalMsg, None, "qt said no")
    assert "qt said no" in s.text()
    # Debug chatter must stay out of a log the user is asked to read.
    installed["handler"](QtCore.QtMsgType.QtDebugMsg, None, "noise")
    assert "noise" not in s.text()
