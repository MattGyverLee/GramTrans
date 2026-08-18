"""Run-report statistics panel (T056, T066, FR-017).

Renders a `RunReport` (E6) as a tabular view inside the main window. Per
contracts/run-report.md the display lists:

- Per-category counts: added | skipped | closure_pulled_in
- Skip list with reasons
- Identity remap section (only shown when non-empty per R6)

Read-only — the panel never mutates the report.
"""
from __future__ import annotations

from typing import Optional, Sequence

from PyQt6 import QtCore, QtWidgets

if __package__:
    from ..models import GrammarCategory, RunMode, RunReport
    from ..report import render_text_summary
    from .theme import theme
else:
    from models import GrammarCategory, RunMode, RunReport  # type: ignore
    from report import render_text_summary  # type: ignore
    from theme import theme  # type: ignore


class StatsPanel(QtWidgets.QWidget):
    """Bottom-panel widget shown after Preview or Move completes."""

    #: What the header says while no report is being presented. Named because
    #: `clear()` (036 FR-041) has to put it back, and two copies of the string
    #: would let the cleared state drift from the initial one.
    _NO_RUN_PLACEHOLDER = "(No run yet -- click Preview.)"

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        self._header = QtWidgets.QLabel(self._NO_RUN_PLACEHOLDER, self)
        self._header.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._header)

        # Per-category table — 5 columns: Category, Added, Skipped,
        # Pulled in by closure, Excluded-lossy (warn+allow).
        self._table = QtWidgets.QTableWidget(0, 5, self)
        self._table.setHorizontalHeaderLabels(
            ["Category", "Added", "Skipped", "Pulled in by closure", "Excl-lossy"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self._table, 2)

        # EXCLUDED-LOSSY warning list (distinct severity — not error, not skip).
        # Held on self so `_apply_theme` can restyle it on a light/dark switch.
        self._warn_label = QtWidgets.QLabel(
            "Warnings (entries with missing references -- deliberate, warn+allow):", self
        )
        layout.addWidget(self._warn_label)
        self._warn_view = QtWidgets.QPlainTextEdit(self)
        self._warn_view.setReadOnly(True)
        self._warn_view.setMaximumBlockCount(500)
        layout.addWidget(self._warn_view, 1)

        # Skip list
        skip_label = QtWidgets.QLabel("Skips (FR-018: every selected item appears here or in counts above):", self)
        layout.addWidget(skip_label)
        self._skip_view = QtWidgets.QPlainTextEdit(self)
        self._skip_view.setReadOnly(True)
        self._skip_view.setMaximumBlockCount(2000)
        layout.addWidget(self._skip_view, 1)

        # Feature 025 (full reversals, P0-2 cycle-6 remediation): the
        # reversal Add/Link plan (`Lib/preview.py.render_reversal_
        # decisions`) and the config-view Add/Overwrite/Skip list
        # (`.render_config_view_records`), composed by `Lib/preview.py.
        # render_preview_extra_lines` and passed in by `main_window.
        # _on_preview` -- Principle III requires these be shown BEFORE
        # Move ever writes. Hidden (no row reserved) when there is nothing
        # to show, matching the identity-remap section's own posture below.
        self._extra_label = QtWidgets.QLabel(
            "Reversals & configuration views (Preview -- not yet written):", self
        )
        self._extra_view = QtWidgets.QPlainTextEdit(self)
        self._extra_view.setReadOnly(True)
        self._extra_view.setMaximumBlockCount(2000)
        self._extra_label.setVisible(False)
        self._extra_view.setVisible(False)
        layout.addWidget(self._extra_label)
        layout.addWidget(self._extra_view, 1)

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

        # The warning pair is the only colour this panel paints itself, and it
        # is the one thing an OS palette cannot supply. Re-apply on `changed`
        # because a panel already showing a report does not rebuild.
        self._apply_theme()
        theme().changed.connect(self._apply_theme)

    def _apply_theme(self) -> None:
        """(Re)build the EXCLUDED-LOSSY warning styling from the live palette.

        The amber must stay legible on both window colours, so the label's
        foreground and the view's background/foreground come from the same
        `warning_*` token trio rather than a fixed light-mode pair.
        """
        pal = theme().palette
        self._warn_label.setStyleSheet(
            f"color: {pal.warning_text}; font-weight: bold;"
        )
        self._warn_view.setStyleSheet(
            f"background-color: {pal.warning_bg};"
            f" color: {pal.warning_text};"
            f" border: 1px solid {pal.warning_border};"
        )

    def set_report(self, report: RunReport, extra_lines: Sequence[str] = ()) -> None:
        """Render `report`. `extra_lines` (feature 025 P0-2, cycle-6
        remediation) is the Preview-only composed reversal Add/Link plan +
        config-view Add/Overwrite/Skip list from `Lib/preview.py.
        render_preview_extra_lines` -- optional and empty for Move-mode
        reports (Move already wrote; there's nothing left to preview)."""
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
            el_count = getattr(r, "excluded_lossy", 0)
            el_item = QtWidgets.QTableWidgetItem(str(el_count) if el_count else "")
            if el_count:
                el_item.setForeground(QtWidgets.QApplication.palette().windowText())
            self._table.setItem(row, 4, el_item)

        # Render EXCLUDED-LOSSY warnings (distinct severity, entry-centric).
        el_list = getattr(report, "excluded_lossy", ())
        if el_list:
            lines = [f"[WARN] {el.message}" for el in el_list]
            self._warn_view.setPlainText("\n".join(lines))
            self._warn_view.setVisible(True)
        else:
            self._warn_view.setPlainText("(no warnings)")
            self._warn_view.setVisible(True)

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

        # Feature 025 (full reversals, P0-2 cycle-6 remediation): the
        # reversal Add/Link plan + config-view Add/Overwrite/Skip list --
        # BEFORE Move ever writes (Principle III). Hidden when there's
        # nothing to show (Move-mode reports, or a plan with neither).
        if extra_lines:
            self._extra_label.setVisible(True)
            self._extra_view.setVisible(True)
            self._extra_view.setPlainText("\n".join(extra_lines))
        else:
            self._extra_label.setVisible(False)
            self._extra_view.setVisible(False)

        self._footer.setText(f"Wall clock: {report.wall_clock_seconds:.3f}s")

    def clear(self) -> None:
        """Stop presenting a report. The exact inverse of `set_report`.

        Feature 036 FR-041. A dry-run report describes ONE set of selections, so
        the moment those selections can have changed -- re-entering the Finish
        page, or a dry run that failed and produced nothing -- the report on
        screen stops being a statement about the current run. Leaving it up is
        the defect FR-041 names: a panel full of last time's numbers beside a
        disabled Execute reads as "here is your plan", not as "run a dry run".

        Every widget `set_report` writes is reset here, and the header goes back
        to its pre-run placeholder. The header is the observable the guard test
        watches, because it is the one that names a run: it carries `run_id=`
        exactly while a report is being presented.

        Lives on the panel rather than in the Finish page because the panel is
        what knows which of its widgets hold report content -- a caller clearing
        them one by one would fall behind the next widget `set_report` gains.
        """
        self._header.setText(self._NO_RUN_PLACEHOLDER)
        self._table.setRowCount(0)
        self._warn_view.setPlainText("")
        self._skip_view.setPlainText("")
        self._extra_view.setPlainText("")
        self._extra_label.setVisible(False)
        self._extra_view.setVisible(False)
        self._remap_view.setPlainText("")
        self._remap_label.setVisible(False)
        self._remap_view.setVisible(False)
        self._footer.setText("")

    def render_text(self, report: RunReport) -> str:
        """Helper for tests / report-pane fallback. Uses
        `Lib/report.render_text_summary` directly."""
        return "\n".join(render_text_summary(report))
