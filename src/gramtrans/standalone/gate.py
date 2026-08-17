"""The standalone's confirmation gate (FR-022..FR-027, FR-054).

`contracts/host-shell.md` §1. Under FlexTools a Move is wrapped in a host unit
of work and `Ctrl+Z` undoes it, so its gate says yes immediately and the user
loses nothing by clicking through. This host has no undo stack — the stack is a
property of the FLEx session, and a separate process cannot create one FLEx
would honour. The write is therefore irreversible from the application's point
of view, and the only honest response is to make that unmissable before it
happens.

Three deliberate frictions, each answering a specific way a click-through
happens:

* **A modal that states the consequence** (FR-022), including the backup
  instruction and the Send/Receive recovery path (FR-054). Not "are you sure?" —
  a question whose answer is always yes teaches people to stop reading.
* **The target's name, typed exactly** (FR-023). Case-sensitive,
  whitespace-significant, no trimming, no folding. Typing a project name is
  work you cannot do by reflex, and it forces the user to look at *which*
  project they are about to write to — the mistake that matters most here is
  not "did I mean to Move?" but "did I mean to Move into *that* one?".
* **Proceed is not the default button** (FR-023). Enter must not commit, and
  neither must a click that lands where the user expected Cancel.

FR-054 is **stated, not enforced**: no Send/Receive detection, no second gate,
no refusal. The recovery procedure is equally correct under FlexTools, so it is
not a property of this host; building detection here would imply otherwise and
would add a mis-detection failure mode to buy nothing (research R15).

`confirm()` MUST NOT raise. It is called at the exact moment the user is
deciding whether to write, and an exception there would surface through the
wizard's fatal-exception funnel as an opaque failure at the worst possible
moment. Everything inside is defended accordingly, and the default on any
internal failure is `False` — refusing a write we are unsure about is always
the recoverable direction.
"""
from __future__ import annotations

from typing import Optional

from PyQt6 import QtCore, QtWidgets

__all__ = ["StandaloneConfirmationGate", "MoveConfirmationDialog", "warning_text",
           "FINISH_PAGE_SUBTITLE"]


#: The `_PageFinish` subtitle in this host. FR-027 forbids claiming a Move can
#: be undone — the FlexTools string ends "changes can be undone in FLEx with
#: Ctrl+Z", which is simply false here.
FINISH_PAGE_SUBTITLE = (
    "Click 'Execute Move' to write all planned actions to the target project. "
    "This is the only write point. GramTrans cannot undo the write once it has "
    "started -- make sure you have a backup of the target project."
)


def warning_text(target_project_name: str) -> str:
    """The modal's body (FR-022, FR-054).

    Separate from the widget so the wording can be asserted without
    constructing a dialog, and so `T031` can check what it must *not* say.
    """
    return (
        f"You are about to write into the project {target_project_name!r}.\n\n"
        "This cannot be undone from within GramTrans. There is no Undo in this "
        "application, and closing it will not put the target project back the "
        "way it was.\n\n"
        "Before you continue, make a backup of the target project "
        "(in FieldWorks Language Explorer: File > Back up this Project).\n\n"
        "If this project uses Send/Receive: do a Send/Receive first. Then, if "
        "the run goes wrong, you can delete your local copy of the project and "
        "receive it again to get back to where you started.\n\n"
        f"To continue, type the target project's name exactly as it appears "
        f"here:\n{target_project_name}"
    )


class MoveConfirmationDialog(QtWidgets.QDialog):
    """The modal itself. Public so its behaviour is testable without `exec()`."""

    def __init__(self, target_project_name: str,
                 parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._expected = target_project_name

        self.setWindowTitle("GramTrans — Confirm Move")
        self.setModal(True)
        self.resize(560, 420)

        layout = QtWidgets.QVBoxLayout(self)

        self._warning = QtWidgets.QLabel(warning_text(target_project_name), self)
        self._warning.setWordWrap(True)
        self._warning.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self._warning, 1)

        self._field = QtWidgets.QLineEdit(self)
        self._field.setPlaceholderText("Type the target project's name")
        self._field.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._field)

        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        self._cancel_btn = QtWidgets.QPushButton("Cancel", self)
        self._cancel_btn.clicked.connect(self.reject)
        row.addWidget(self._cancel_btn)

        self._proceed_btn = QtWidgets.QPushButton("Write to the target project", self)
        self._proceed_btn.setEnabled(False)
        self._proceed_btn.clicked.connect(self.accept)
        row.addWidget(self._proceed_btn)
        layout.addLayout(row)

        # FR-023: Enter must not commit. Cancel carries the default, so the
        # reflex keystroke and the reflex click both land on the safe action;
        # `setAutoDefault(False)` stops the proceed button reclaiming default
        # status when it takes focus.
        self._proceed_btn.setDefault(False)
        self._proceed_btn.setAutoDefault(False)
        self._cancel_btn.setDefault(True)
        self._cancel_btn.setAutoDefault(True)

    # -- state -------------------------------------------------------------

    def typed_text(self) -> str:
        return self._field.text()

    def set_typed_text(self, text: str) -> None:
        self._field.setText(text)

    def satisfied(self) -> bool:
        """Exact equality. No `strip()`, no `casefold()` — see FR-023."""
        return self._field.text() == self._expected

    def proceed_enabled(self) -> bool:
        return bool(self._proceed_btn.isEnabled())

    def proceed_is_default_button(self) -> bool:
        return bool(self._proceed_btn.isDefault() or self._proceed_btn.autoDefault())

    def warning_body(self) -> str:
        return self._warning.text()

    def _on_text_changed(self, _text: str) -> None:
        self._proceed_btn.setEnabled(self.satisfied())


class StandaloneConfirmationGate:
    """`ConfirmationGate` for a host with no undo stack."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        self._parent = parent
        #: Set by `confirm()`. The shell reads both for the FR-026
        #: partial-failure report: "the user confirmed a Move into X" plus "the
        #: run reported an error" is what warrants telling them the target may
        #: be partially modified. Neither fact alone does.
        self.last_decision: Optional[bool] = None
        self.last_target_name: str = ""

    def confirm(self, target_project_name: str) -> bool:
        self.last_target_name = target_project_name
        try:
            dialog = MoveConfirmationDialog(target_project_name, self._parent)
            accepted = dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted
            # Belt and braces: `accept()` is only reachable from the proceed
            # button, which is only enabled on an exact match — but the write
            # is irreversible, so the condition is re-checked rather than
            # inferred from the dialog result code.
            decision = bool(accepted and dialog.satisfied())
        except Exception:  # noqa: BLE001 — MUST NOT raise (contract §1)
            decision = False
        self.last_decision = decision
        return decision

    def finish_page_subtitle(self) -> str:
        return FINISH_PAGE_SUBTITLE
