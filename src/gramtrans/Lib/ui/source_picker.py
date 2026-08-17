"""Source project picker (feature 034 exception 7, FR-002/FR-004/FR-030).

The twin of `target_picker.py`, for the role FlexTools supplies and a
standalone host does not. Under FlexTools this module is never constructed:
the source is whatever project the host already had open, and step 1 shows it
as a plain label. A host that has no open project passes a source binder into
the wizard, and step 1 grows a "Pick source project..." button in the row
above the target's.

Why this lives here and not in the standalone shell: `Lib/ui/` may not import
`gramtrans.standalone` (FR-016), and step 1 is the screen that needs the
dialog. The shell keeps what is genuinely host-specific -- *opening* the
project read-only and closing it again on release.

Contract, deliberately identical to `TargetPickerDialog`:
- Reads: `list[SourceCandidate]`
- Returns: the chosen `SourceCandidate` (or None on cancel)
- Forbidden: opening the project itself (the host's binder does that), and
  pre-selecting a row -- FR-004 has no default and no last-used memory.
"""
from __future__ import annotations

from typing import List, Optional

from PyQt6 import QtCore, QtWidgets

if __package__:
    from ..api import SourceCandidate
else:
    from api import SourceCandidate  # type: ignore


# What the screen says before anything is chosen. The second paragraph is
# FR-030, phrased to answer the objection it will actually get ("but I only
# wanted a preview") -- `api.bind_target` opens the target write-enabled in
# both modes, so even a Preview needs it closed in FLEx.
GUIDANCE = (
    "Choose the project to copy grammar pieces FROM.\n"
    "It is opened read-only and is never modified.\n\n"
    "Before you continue: the project you copy INTO must be closed in "
    "FieldWorks Language Explorer — even for a Preview."
)


class SourcePickerDialog(QtWidgets.QDialog):
    """Modal single-select list of FLEx projects, nothing pre-selected.

    Usage:
        dlg = SourcePickerDialog(gt_api.list_source_candidates(root))
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            choice = dlg.selected_candidate()
    """

    def __init__(self,
                 candidates: List[SourceCandidate],
                 parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._candidates = list(candidates)
        self._selected_index: Optional[int] = None
        self._unopenable_message = ""

        self.setWindowTitle("GramTrans — Pick source project")
        self.setModal(True)
        self.resize(520, 420)

        layout = QtWidgets.QVBoxLayout(self)

        self._guidance = QtWidgets.QLabel(GUIDANCE, self)
        self._guidance.setWordWrap(True)
        layout.addWidget(self._guidance)

        self._list = QtWidgets.QListWidget(self)
        for cand in self._candidates:
            item = QtWidgets.QListWidgetItem(
                f"{cand.project_name}\n    {cand.project_path}",
                self._list,
            )
            item.setData(QtCore.Qt.ItemDataRole.UserRole, cand)
        layout.addWidget(self._list, 1)

        # An empty list gets a message, not a bare empty box: "no projects" and
        # "the list failed to load" look identical otherwise.
        self._empty_label = QtWidgets.QLabel(
            "No FieldWorks projects were found. Create or restore a project in "
            "FieldWorks Language Explorer first, then start GramTrans again.",
            self,
        )
        self._empty_label.setWordWrap(True)
        self._empty_label.setVisible(self.is_empty())
        layout.addWidget(self._empty_label)
        self._list.setVisible(not self.is_empty())

        # FR-034: one project that will not open is reported against that
        # project and leaves the rest of the list selectable.
        self._problem_label = QtWidgets.QLabel("", self)
        self._problem_label.setWordWrap(True)
        self._problem_label.setVisible(False)
        layout.addWidget(self._problem_label)

        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        self._list.itemDoubleClicked.connect(lambda _: self.accept())

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            QtCore.Qt.Orientation.Horizontal,
            self,
        )
        self._ok_button = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        # FR-004: starts disabled, and no code path pre-selects a row -- so the
        # only thing that can enable it is a deliberate choice.
        self._ok_button.setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # -- queries -----------------------------------------------------------

    def project_names(self) -> List[str]:
        return [c.project_name for c in self._candidates]

    def is_empty(self) -> bool:
        return not self._candidates

    def guidance_text(self) -> str:
        return self._guidance.text()

    def empty_message(self) -> str:
        return self._empty_label.text()

    def unopenable_message(self) -> str:
        return self._unopenable_message

    def selected_candidate(self) -> Optional[SourceCandidate]:
        if self._selected_index is None:
            return None
        return self._candidates[self._selected_index]

    def selected_project_name(self) -> Optional[str]:
        choice = self.selected_candidate()
        return choice.project_name if choice is not None else None

    def advance_enabled(self) -> bool:
        return bool(self._ok_button.isEnabled())

    # -- commands ----------------------------------------------------------

    def select_by_name(self, name: str) -> None:
        """Select a row as a user click would. Test seam and keyboard route."""
        for row, cand in enumerate(self._candidates):
            if cand.project_name == name:
                self._list.setCurrentRow(row)
                return
        raise KeyError(f"{name!r} is not in the list")

    def clear_selection(self) -> None:
        self._list.clearSelection()
        self._list.setCurrentItem(None)
        self._on_selection_changed()

    def mark_unopenable(self, project_name: str, reason: str = "") -> None:
        """Report that one project could not be opened (FR-034).

        The row stays in the list. Removing it would silently rewrite what the
        user is looking at, and the project may well open fine once they close
        it in FLEx.
        """
        detail = f"\n\nDetails: {reason}" if reason else ""
        self._unopenable_message = (
            f"GramTrans could not open {project_name!r}.\n\n"
            f"If it is open in FieldWorks Language Explorer, close it and try "
            f"again. You can also choose a different project.{detail}"
        )
        self._problem_label.setText(self._unopenable_message)
        self._problem_label.setVisible(True)

    # -- internals ---------------------------------------------------------

    def _on_selection_changed(self) -> None:
        items = self._list.selectedItems()
        self._selected_index = self._list.row(items[0]) if items else None
        self._ok_button.setEnabled(self._selected_index is not None)
