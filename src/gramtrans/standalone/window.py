"""The application window (FR-009, FR-036, FR-038; T051, T052).

Under FlexTools the host supplies the window: its report pane shows the run,
and its menus are where a user goes for anything that is not the run itself.
This host has to supply that, and it turns out to need only three things:

* the **report view** as its central widget, so the run is visible during and
  after it (FR-009) — the wizard is modal and covers the screen while it is
  open, and when it closes this is what is underneath;
* **Help -> Self-check...**, which is the route that actually matters for the
  users FR-036 is written for. The `--self-check` flag exists and is what a
  support person will ask for, but a linguist who cannot start the application
  is not going to open a terminal to produce it (research R12);
* the **log file path in the status bar** (FR-038), permanently, because "where
  is the log?" is the first question of every support conversation.

There is deliberately no toolbar, no settings, and no File menu. Every command
this host has is either the run itself (which the wizard owns) or a
diagnostic.
"""
from __future__ import annotations

from typing import Optional

from PyQt6 import QtGui, QtWidgets

from gramtrans.standalone.report_view import ReportView

__all__ = ["GramTransWindow", "SelfCheckDialog"]


class SelfCheckDialog(QtWidgets.QDialog):
    """The self-check block in a window, with a Copy button (FR-037).

    Read-only and monospaced: the block's alignment carries meaning, and a
    user who can edit it will eventually send back one they have "tidied".
    """

    def __init__(self, text: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GramTrans — Self-check")
        self.setModal(True)
        self.resize(720, 560)

        layout = QtWidgets.QVBoxLayout(self)

        intro = QtWidgets.QLabel(
            "Copy this whole block and include it when you ask for help.", self
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._text = QtWidgets.QPlainTextEdit(self)
        self._text.setReadOnly(True)
        self._text.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self._text.setFont(QtGui.QFontDatabase.systemFont(
            QtGui.QFontDatabase.SystemFont.FixedFont
        ))
        self._text.setPlainText(text)
        layout.addWidget(self._text, 1)

        row = QtWidgets.QHBoxLayout()
        copy_btn = QtWidgets.QPushButton("Copy to clipboard", self)
        copy_btn.clicked.connect(self.copy_to_clipboard)
        row.addWidget(copy_btn)

        save_btn = QtWidgets.QPushButton("Save to file...", self)
        save_btn.clicked.connect(self.save_to_file)
        row.addWidget(save_btn)

        row.addStretch(1)
        close_btn = QtWidgets.QPushButton("Close", self)
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn)
        layout.addLayout(row)

    def contents(self) -> str:
        return self._text.toPlainText()

    def copy_to_clipboard(self) -> None:
        clipboard = QtWidgets.QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.contents())

    def save_to_file(self, path: Optional[str] = None) -> Optional[str]:
        if path is None:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save the self-check", "gramtrans-self-check.txt",
                "Text files (*.txt *.log)",
            )
            if not path:
                return None
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.contents())
        except OSError as exc:
            QtWidgets.QMessageBox.warning(
                self, "GramTrans", f"Could not save the self-check:\n{exc}"
            )
            return None
        return path


class GramTransWindow(QtWidgets.QMainWindow):
    """The application's own window: report view, Help menu, status bar."""

    def __init__(self, session, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._session = session

        self.setWindowTitle(f"GramTrans — {self._version()}")
        self.resize(900, 600)

        self._report_view = ReportView(session.report_sink, self)
        self.setCentralWidget(self._report_view)

        self._build_menus()

        # FR-038: permanent, not a transient message, because the log path has
        # to be readable at the moment the user is asked for it -- which is
        # after something went wrong, not while it is happening.
        self._log_label = QtWidgets.QLabel(self._status_text(), self)
        self.statusBar().addPermanentWidget(self._log_label)

    # -- construction ------------------------------------------------------

    def _build_menus(self) -> None:
        help_menu = self.menuBar().addMenu("&Help")

        self_check_action = QtGui.QAction("&Self-check...", self)
        self_check_action.setStatusTip(
            "Check that everything GramTrans needs is present on this computer"
        )
        self_check_action.triggered.connect(self.show_self_check)
        help_menu.addAction(self_check_action)

        help_menu.addSeparator()

        about_action = QtGui.QAction("&About GramTrans", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _version(self) -> str:
        from gramtrans.standalone.prereq import _app_version

        return _app_version()

    def _status_text(self) -> str:
        sink = self._session.report_sink
        error = getattr(sink, "file_error", None)
        if error:
            return f"Log file could not be written ({error}) — {sink.log_path}"
        return f"Log file: {sink.log_path}"

    # -- actions -----------------------------------------------------------

    def show_self_check(self) -> SelfCheckDialog:
        """Help -> Self-check... (FR-036, research R12).

        Runs the checks fresh rather than replaying startup's: the user may be
        opening this *because* they have just plugged something in, closed a
        project, or repaired an install, and a cached answer would tell them
        nothing has changed when it has.
        """
        from gramtrans.standalone import selfcheck

        sink = self._session.report_sink
        text, _report = selfcheck.produce(
            log_path=sink.log_path, log_error=getattr(sink, "file_error", None)
        )
        dialog = SelfCheckDialog(text, self)
        dialog.exec()
        return dialog

    def show_about(self) -> None:
        QtWidgets.QMessageBox.about(
            self,
            "About GramTrans",
            f"GramTrans {self._version()}\n\n"
            "Additive grammar-piece transfer between FieldWorks Language "
            "Explorer projects.\n\n"
            "FieldWorks 9 is a separate prerequisite and is not included with "
            "GramTrans.\n\n"
            f"Log file:\n{self._session.report_sink.log_path}",
        )

    def refresh(self) -> None:
        self._report_view.refresh()
        self._log_label.setText(self._status_text())
