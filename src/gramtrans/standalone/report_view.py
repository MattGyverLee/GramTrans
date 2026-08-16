"""The in-app report view (FR-009, FR-010, FR-038).

Under FlexTools the run's narrative appears in the host's report pane. This
host has to supply that pane. Three requirements shape it:

* **Visible during *and* after the run** (FR-009). A view that only appears at
  the end turns a long transfer into a frozen window, and a view that vanishes
  on completion loses the one artifact the user needs.
* **Save to file and copy to clipboard** (FR-010) — because the realistic next
  step after something goes wrong is pasting the output into an email.
* **The log path in the header** (FR-038), so the file is discoverable without
  reading documentation.

The widget owns no state of its own: it renders what `logsink.LogSink`
collected, and the sink is what the engine writes to. That keeps one source of
truth for "what happened in this run" — the alternative, a view that
accumulates its own copy, drifts the moment one of them drops a line.
"""
from __future__ import annotations

from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets

__all__ = ["ReportView"]


class ReportView(QtWidgets.QWidget):
    """A read-only log pane with a header, Save and Copy."""

    def __init__(self, sink, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._sink = sink

        layout = QtWidgets.QVBoxLayout(self)

        self._header = QtWidgets.QLabel(self._header_text(), self)
        self._header.setWordWrap(True)
        self._header.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self._header)

        self._text = QtWidgets.QPlainTextEdit(self)
        self._text.setReadOnly(True)
        self._text.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self._text.setFont(QtGui.QFontDatabase.systemFont(
            QtGui.QFontDatabase.SystemFont.FixedFont
        ))
        layout.addWidget(self._text, 1)

        buttons = QtWidgets.QHBoxLayout()
        self._save_btn = QtWidgets.QPushButton("Save to file...", self)
        self._save_btn.clicked.connect(self.save_to_file)
        buttons.addWidget(self._save_btn)

        self._copy_btn = QtWidgets.QPushButton("Copy to clipboard", self)
        self._copy_btn.clicked.connect(self.copy_to_clipboard)
        buttons.addWidget(self._copy_btn)

        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.refresh()
        # The sink pushes each line here as it is emitted, which is what makes
        # the view live during the run rather than a post-mortem (FR-009).
        if hasattr(sink, "attach_view"):
            sink.attach_view(self._on_sink_line)

    # -- header ------------------------------------------------------------

    def _header_text(self) -> str:
        path = getattr(self._sink, "log_path", "")
        error = getattr(self._sink, "file_error", None)
        if error:
            return (
                f"Run {getattr(self._sink, 'run_id', '')}  —  the log file could "
                f"not be written ({error}).\nIntended location: {path}"
            )
        return f"Run {getattr(self._sink, 'run_id', '')}  —  log file:\n{path}"

    # -- content -----------------------------------------------------------

    def refresh(self) -> None:
        """Re-render from the sink. Used at construction and after a replay."""
        self._text.setPlainText(self._sink.text())
        self._scroll_to_end()
        self._header.setText(self._header_text())

    def _on_sink_line(self, level: str, msg: str) -> None:
        self._text.appendPlainText(f"[{level}] {msg}" if level else "")
        self._scroll_to_end()

    def _scroll_to_end(self) -> None:
        bar = self._text.verticalScrollBar()
        bar.setValue(bar.maximum())

    def contents(self) -> str:
        return self._text.toPlainText()

    # -- FR-010 ------------------------------------------------------------

    def copy_to_clipboard(self) -> None:
        clipboard = QtWidgets.QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.contents())

    def save_to_file(self, path: Optional[str] = None) -> Optional[str]:
        """Write the view's contents somewhere the user chooses.

        Separate from the run log on purpose: the run log lives in
        `%LOCALAPPDATA%`, which is exactly where a user cannot find it when
        asked to attach it to an email. `path` is injectable so the behaviour
        is testable without driving a native file dialog.
        """
        if path is None:
            suggested = f"gramtrans-{getattr(self._sink, 'run_id', 'run')}.log"
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save GramTrans report", suggested, "Log files (*.log *.txt)"
            )
            if not path:
                return None
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.contents())
        except OSError as exc:
            QtWidgets.QMessageBox.warning(
                self, "GramTrans", f"Could not save the report:\n{exc}"
            )
            return None
        return path
