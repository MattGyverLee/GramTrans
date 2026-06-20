"""Run-report statistics panel (T056, T066, FR-017).

Renders a `RunReport` (E6) as a tabular view inside the main window. Per
contracts/run-report.md the display lists:

- Per-category counts: added | skipped | closure_pulled_in
- Skip list with reasons
- Identity remap section (only shown when non-empty per R6)

Read-only — the panel never mutates the report.
"""
from __future__ import annotations

from typing import Optional

try:
    from PyQt5 import QtCore, QtWidgets
except ImportError:  # pragma: no cover
    from PySide2 import QtCore, QtWidgets  # type: ignore

if __package__:
    from ..models import GrammarCategory, RunMode, RunReport
    from ..report import render_text_summary
else:
    from models import GrammarCategory, RunMode, RunReport  # type: ignore
    from report import render_text_summary  # type: ignore


class StatsPanel(QtWidgets.QWidget):
    """Bottom-panel widget shown after Preview or Move completes."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        self._header = QtWidgets.QLabel("(No run yet — click Preview.)", self)
        self._header.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._header)

        # Per-category table
        self._table = QtWidgets.QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels(
            ["Category", "Added", "Skipped", "Pulled in by closure"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        layout.addWidget(self._table, 2)

        # Skip list
        skip_label = QtWidgets.QLabel("Skips (FR-018: every selected item appears here or in counts above):", self)
        layout.addWidget(skip_label)
        self._skip_view = QtWidgets.QPlainTextEdit(self)
        self._skip_view.setReadOnly(True)
        self._skip_view.setMaximumBlockCount(2000)
        layout.addWidget(self._skip_view, 1)

        # Identity remap (hidden unless non-empty)
        self._remap_label = QtWidgets.QLabel("Identity remap (LCM denied GUID-on-create):", self)
        self._remap_view = QtWidgets.QPlainTextEdit(self)
        self._remap_view.setReadOnly(True)
        self._remap_label.setVisible(False)
        self._remap_view.setVisible(False)
        layout.addWidget(self._remap_label)
        layout.addWidget(self._remap_view)

        # Wall-clock footer
        self._footer = QtWidgets.QLabel("", self)
        layout.addWidget(self._footer)

    def set_report(self, report: RunReport) -> None:
        mode_word = "Preview" if report.mode is RunMode.PREVIEW else "Move"
        self._header.setText(
            f"{mode_word} run · run_id={report.context.run_id} · "
            f"source={report.context.source_project_name!r} → target={report.context.target_project_name!r}"
        )

        cats = sorted(report.per_category.keys(), key=lambda c: c.value)
        self._table.setRowCount(len(cats))
        for row, cat in enumerate(cats):
            r = report.per_category[cat]
            self._table.setItem(row, 0, QtWidgets.QTableWidgetItem(cat.value))
            self._table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(r.added)))
            self._table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(r.skipped)))
            self._table.setItem(row, 3, QtWidgets.QTableWidgetItem(str(r.closure_pulled_in)))

        if report.skips:
            lines = []
            for s in report.skips:
                lines.append(f"[{s.category.value}] {s.source_guid}  {s.reason.value}: {s.detail}")
            self._skip_view.setPlainText("\n".join(lines))
        else:
            self._skip_view.setPlainText("(no skips)")

        if report.identity_remap:
            self._remap_label.setVisible(True)
            self._remap_view.setVisible(True)
            self._remap_view.setPlainText(
                "\n".join(f"{src} -> {dst}" for src, dst in sorted(report.identity_remap.items()))
            )
        else:
            self._remap_label.setVisible(False)
            self._remap_view.setVisible(False)

        self._footer.setText(f"Wall clock: {report.wall_clock_seconds:.3f}s")

    def render_text(self, report: RunReport) -> str:
        """Helper for tests / report-pane fallback. Uses
        `Lib/report.render_text_summary` directly."""
        return "\n".join(render_text_summary(report))
