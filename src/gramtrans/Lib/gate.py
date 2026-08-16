"""Confirmation gate — the one construct both hosts see (feature 034).

`contracts/host-shell.md` §1. A *host* decides how much ceremony a Move
demands; the wizard only has to *ask*. Under FlexTools the answer is "yes,
obviously" — the host wraps the run in a unit of work and `Ctrl+Z` undoes it —
so the default gate says yes with no dialog and no I/O, and the FlexTools
sequence is byte-identical to what it was before the parameter existed
(SC-013). Under the standalone there is no undo stack to fall back on, so its
gate (``gramtrans.standalone.gate``) shows a warning and demands the target's
name typed exactly.

`ConfirmationGate` is a **structural** protocol: the wizard duck-types it and
imports neither implementation. That is what lets the standalone's gate live in
`gramtrans/standalone/` while this default lives here, under `Lib/`, next to
the wizard that defaults to it — the FR-016 import direction forbids the
wizard reaching into the shell for anything, including its own default.

This module imports nothing but `typing`. Keep it that way: the default gate
has to construct in a process with no PyQt6, no QApplication and no flexicon
(`tests/unit/test_034_gate_default.py` asserts exactly that).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

# The `_PageFinish` subtitle as it stood before feature 034 made it
# gate-supplied (`Lib/ui/selection_wizard.py`, exception 3). Byte-identical is
# the whole point: `test_034_flextools_contract.py` compares the FlexTools
# default against its own inline copy of this string, so an edit here that is
# not also an edit there fails the regression gate.
FLEXTOOLS_FINISH_SUBTITLE = (
    "Click 'Execute Move' to write all planned actions to the target project. "
    "This is the only write point -- changes can be undone in FLEx with Ctrl+Z."
)


@runtime_checkable
class ConfirmationGate(Protocol):
    """What the wizard asks before it writes.

    Implementations are supplied by the host and passed down
    `MainFunction` -> `_run_gui` -> `SelectionWizard` -> `_PageFinish`.
    """

    def confirm(self, target_project_name: str) -> bool:
        """Permit (``True``) or refuse (``False``) the write.

        Called **once**, immediately before ``gt_api.execute_move``, and only
        on the Move path — a Preview never reaches it (FR-024). A ``False``
        return aborts with no write and leaves the wizard and all selections
        intact (FR-025).

        MUST NOT raise. A gate that raises would surface through the wizard's
        fatal-exception funnel as an opaque failure at the exact moment the
        user is deciding whether to write.
        """
        ...

    def finish_page_subtitle(self) -> str:
        """The `_PageFinish` subtitle. Called during page construction."""
        ...


class AlwaysSatisfiedGate:
    """The default gate, and the FlexTools gate: satisfied on creation.

    ``confirm()`` returns ``True`` immediately — no dialog, no prompt, no I/O.
    ``MainFunction(project, report, modifyAllowed)`` with no
    ``confirmation_gate=`` resolves to one of these, which is what makes the
    FlexTools path unchanged.
    """

    __slots__ = ()

    def confirm(self, target_project_name: str) -> bool:  # noqa: ARG002
        return True

    def finish_page_subtitle(self) -> str:
        return FLEXTOOLS_FINISH_SUBTITLE


def resolve_gate(gate: object) -> ConfirmationGate:
    """Normalise a possibly-``None`` gate parameter to a real gate.

    Every site that accepts ``confirmation_gate=None`` funnels through here so
    "``None`` means the FlexTools default" is stated once rather than
    re-implemented at `MainFunction`, `_run_gui` and `SelectionWizard`.
    """
    if gate is None:
        return AlwaysSatisfiedGate()
    return gate  # type: ignore[return-value]
