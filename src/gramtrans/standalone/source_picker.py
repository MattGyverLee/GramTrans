"""The source project chooser (FR-002, FR-004, FR-005, FR-030, FR-034).

The screen that makes this a different host. FlexTools *has* a source — the
project the user already had open — and the module simply receives it. There
is no such thing here, so the source is chosen, and the spec is emphatic about
how: nothing pre-selected, no default, no last-used memory, no hard-coded
name. It is the first thing the user sees once the prerequisite checks pass.

Design notes worth keeping:

* **Enumeration goes through `flexicon.AllProjectNames()`** (research R2),
  which asks LCM (`FwDirectoryFinder.ProjectsDirectory`) rather than walking a
  hard-coded path. That is what makes a relocated projects directory work.
  Injectable for tests, and the injection point is the *list*, never a
  "default project" — there is deliberately no way to pre-select one.
* **Disabled until chosen**, copying `Lib/ui/target_picker.py` exactly. Two
  pickers behaving differently about the same question would be its own bug.
* **The FR-030 warning appears before selection**, not after. `api.bind_target`
  opens the target write-enabled in *both* modes, so even a Preview needs the
  target closed in FLEx — and the moment to learn that is before choosing, not
  in an error dialog afterwards.

This module names no project. `tests/unit/test_034_source_chooser.py` scans
the whole shell for one, in prose as well as in code, because an example in a
docstring is how a hard-coded default gets reintroduced.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from PyQt6 import QtCore, QtWidgets

__all__ = ["SourcePickerDialog", "enumerate_projects"]


# What the screen says before anything is chosen. FR-030 in the second
# paragraph, phrased to answer the objection it will actually get ("but I only
# wanted a preview").
GUIDANCE = (
    "Choose the project to copy grammar pieces FROM.\n"
    "It is opened read-only and is never modified.\n\n"
    "Before you continue: the project you copy INTO must be closed in "
    "FieldWorks Language Explorer — even for a Preview."
)


def enumerate_projects() -> List[str]:
    """Every FLEx project LCM knows about, sorted (research R2).

    Not a directory walk: `AllProjectNames()` applies LCM's own rule for what
    counts as a project, and honours a projects directory that is not in the
    default location.
    """
    from gramtrans.standalone import fwglobals

    flexicon = fwglobals.probe()
    return sorted(str(n) for n in flexicon.AllProjectNames())


class SourcePickerDialog(QtWidgets.QDialog):
    """Modal single-select list of FLEx projects, nothing pre-selected.

    Usage:
        dlg = SourcePickerDialog(enumerate_projects())
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            name = dlg.selected_project_name()
    """

    def __init__(
        self,
        project_names: List[str],
        parent: Optional[QtWidgets.QWidget] = None,
        on_open_failed: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._names = list(project_names)
        self._on_open_failed = on_open_failed
        self._unopenable_message = ""

        self.setWindowTitle("GramTrans — Choose source project")
        self.setModal(True)
        self.resize(520, 420)

        layout = QtWidgets.QVBoxLayout(self)

        self._guidance = QtWidgets.QLabel(GUIDANCE, self)
        self._guidance.setWordWrap(True)
        layout.addWidget(self._guidance)

        self._list = QtWidgets.QListWidget(self)
        for name in self._names:
            QtWidgets.QListWidgetItem(name, self._list)
        layout.addWidget(self._list, 1)

        # An empty list gets a message, not a bare empty box (FR-034 neighbour):
        # "no projects" and "the list failed to load" look identical otherwise.
        self._empty_label = QtWidgets.QLabel(self._empty_text(), self)
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
        # FR-004: starts disabled, and there is no code path that pre-selects
        # a row — so the only thing that can enable it is a deliberate choice.
        self._ok_button.setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # -- queries -----------------------------------------------------------

    def project_names(self) -> List[str]:
        return list(self._names)

    def is_empty(self) -> bool:
        return not self._names

    def guidance_text(self) -> str:
        return self._guidance.text()

    def empty_message(self) -> str:
        return self._empty_label.text()

    def unopenable_message(self) -> str:
        return self._unopenable_message

    def selected_project_name(self) -> Optional[str]:
        items = self._list.selectedItems()
        return items[0].text() if items else None

    def advance_enabled(self) -> bool:
        return bool(self._ok_button.isEnabled())

    # -- commands ----------------------------------------------------------

    def select_by_name(self, name: str) -> None:
        """Select a row as a user click would. Test seam and keyboard route."""
        matches = self._list.findItems(name, QtCore.Qt.MatchFlag.MatchExactly)
        if not matches:
            raise KeyError(f"{name!r} is not in the list")
        self._list.setCurrentItem(matches[0])

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
        from gramtrans.standalone import errors

        self._unopenable_message = errors.project_cannot_be_opened(
            project_name, reason
        )
        self._problem_label.setText(self._unopenable_message)
        self._problem_label.setVisible(True)
        if self._on_open_failed is not None:
            self._on_open_failed(project_name, reason)

    # -- internals ---------------------------------------------------------

    def _empty_text(self) -> str:
        from gramtrans.standalone import errors, fwglobals

        try:
            root = fwglobals.projects_dir()
        except Exception:  # noqa: BLE001 — the message must render regardless
            root = "the FieldWorks projects folder"
        return errors.no_projects_found(root)

    def _on_selection_changed(self) -> None:
        self._ok_button.setEnabled(self.selected_project_name() is not None)
