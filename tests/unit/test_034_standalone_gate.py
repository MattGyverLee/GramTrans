"""T030 / FR-023, FR-025 — the Move gate cannot be satisfied by reflex.

The gate's whole value is that it costs deliberate effort. Every test here
covers a specific way a user could get past it without meaning to: a near-miss
that "looks right", a trailing space from a copy-paste, Enter on a dialog whose
proceed button grabbed the default, a double-click landing on the wrong button.

If any of these start passing the gate, the feature has quietly become a
confirmation prompt, and a confirmation prompt in front of an irreversible
write is worse than nothing — it teaches the click-through it is supposed to
prevent.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

PyQt6 = pytest.importorskip("PyQt6")

from PyQt6 import QtWidgets  # noqa: E402

TARGET = "Ejagham Full GT-Test"


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture()
def dialog(qapp):
    from gramtrans.standalone.gate import MoveConfirmationDialog

    return MoveConfirmationDialog(TARGET)


# ---------------------------------------------------------------------------
# FR-023 — exact match, and nothing less
# ---------------------------------------------------------------------------

def test_proceed_starts_disabled(dialog):
    assert dialog.typed_text() == ""
    assert dialog.satisfied() is False
    assert dialog.proceed_enabled() is False


def test_the_exact_name_enables_proceed(dialog):
    dialog.set_typed_text(TARGET)
    assert dialog.satisfied() is True
    assert dialog.proceed_enabled() is True


@pytest.mark.parametrize(
    "typed, why",
    [
        (TARGET.lower(), "case folded"),
        (TARGET.upper(), "upper-cased"),
        (TARGET + " ", "trailing space — the classic copy-paste artifact"),
        (" " + TARGET, "leading space"),
        (TARGET + "\t", "trailing tab"),
        (TARGET.replace(" ", ""), "spaces removed"),
        (TARGET.replace("-", " "), "hyphen turned into a space"),
        (TARGET[:-1], "one character short"),
        (TARGET + "x", "one character long"),
        ("Ejagham Full GT-test", "one letter's case wrong"),
        ("", "empty"),
    ],
)
def test_near_misses_do_not_satisfy_the_gate(dialog, typed, why):
    dialog.set_typed_text(typed)
    assert dialog.satisfied() is False, f"{why!r} should not satisfy the gate"
    assert dialog.proceed_enabled() is False, f"{why!r} enabled proceed"


def test_proceed_re_disables_when_the_text_stops_matching(dialog):
    dialog.set_typed_text(TARGET)
    assert dialog.proceed_enabled() is True
    dialog.set_typed_text(TARGET[:-1])
    assert dialog.proceed_enabled() is False
    dialog.set_typed_text("")
    assert dialog.proceed_enabled() is False


def test_proceed_is_not_the_default_button(dialog):
    """Enter must not commit, and must not commit after focus moves either.

    `autoDefault` is checked as well as `isDefault`: a QPushButton in a dialog
    reclaims default status when it takes focus unless auto-default is turned
    off, so checking only `isDefault()` would pass while Enter still wrote.
    """
    assert dialog.proceed_is_default_button() is False
    dialog.set_typed_text(TARGET)
    assert dialog.proceed_is_default_button() is False, (
        "the proceed button became the default once it was enabled"
    )


def test_a_target_name_with_awkward_characters_still_compares_exactly(qapp):
    from gramtrans.standalone.gate import MoveConfirmationDialog

    awkward = "  Two  Spaces  and trailing "
    dlg = MoveConfirmationDialog(awkward)
    dlg.set_typed_text(awkward.strip())
    assert dlg.satisfied() is False, "the gate trimmed whitespace"
    dlg.set_typed_text(awkward)
    assert dlg.satisfied() is True


# ---------------------------------------------------------------------------
# FR-025 — Cancel returns False, and so does anything unexpected
# ---------------------------------------------------------------------------

def test_cancel_returns_false(qapp, monkeypatch):
    from gramtrans.standalone import gate as gate_mod

    class _Cancelled(gate_mod.MoveConfirmationDialog):
        def exec(self):
            return int(QtWidgets.QDialog.DialogCode.Rejected)

    monkeypatch.setattr(gate_mod, "MoveConfirmationDialog", _Cancelled)
    assert gate_mod.StandaloneConfirmationGate().confirm(TARGET) is False


def test_an_accepted_dialog_with_unsatisfied_text_still_returns_false(qapp, monkeypatch):
    """The result code alone is not trusted, because the write is irreversible."""
    from gramtrans.standalone import gate as gate_mod

    class _AcceptedButEmpty(gate_mod.MoveConfirmationDialog):
        def exec(self):
            return int(QtWidgets.QDialog.DialogCode.Accepted)

    monkeypatch.setattr(gate_mod, "MoveConfirmationDialog", _AcceptedButEmpty)
    assert gate_mod.StandaloneConfirmationGate().confirm(TARGET) is False


def test_a_satisfied_accepted_dialog_returns_true(qapp, monkeypatch):
    from gramtrans.standalone import gate as gate_mod

    class _Confirmed(gate_mod.MoveConfirmationDialog):
        def exec(self):
            self.set_typed_text(TARGET)
            return int(QtWidgets.QDialog.DialogCode.Accepted)

    monkeypatch.setattr(gate_mod, "MoveConfirmationDialog", _Confirmed)
    gate = gate_mod.StandaloneConfirmationGate()
    assert gate.confirm(TARGET) is True
    assert gate.last_decision is True


def test_confirm_never_raises(qapp, monkeypatch):
    """Contract §1: `confirm()` MUST NOT raise, and refuses when unsure.

    It is called at the instant the user is deciding whether to write; an
    exception there would reach them as an opaque failure through the wizard's
    fatal-exception funnel.
    """
    from gramtrans.standalone import gate as gate_mod

    class _Exploding(gate_mod.MoveConfirmationDialog):
        def __init__(self, *a, **kw):
            raise RuntimeError("boom")

    monkeypatch.setattr(gate_mod, "MoveConfirmationDialog", _Exploding)
    gate = gate_mod.StandaloneConfirmationGate()
    assert gate.confirm(TARGET) is False
    assert gate.last_decision is False


def test_the_gate_satisfies_the_structural_protocol(qapp):
    from gramtrans.Lib.gate import ConfirmationGate
    from gramtrans.standalone.gate import StandaloneConfirmationGate

    assert isinstance(StandaloneConfirmationGate(), ConfirmationGate)
