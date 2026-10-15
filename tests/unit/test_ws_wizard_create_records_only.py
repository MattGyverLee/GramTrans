"""Issue #43 -- WSWizard records a CREATE choice and never touches the target.

The wizard used to call `target.WritingSystems.Add(...)` on Apply. flexicon's
WritingSystemOperations has no `Add`, so the call always raised AttributeError
and was swallowed. The side-effect was removed: writing-system creation is
owned by `Lib/api.py::_ensure_writing_systems` (create_in_target=True pre-pass).
These tests pin that the wizard only records the choice.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6")

from PyQt6 import QtWidgets

from gramtrans.Lib.models import WSChoice, WSKind, WSMismatch
from gramtrans.Lib.ui.ws_wizard import WSWizard


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    yield app


class _TripwireTarget:
    """A target project whose every attribute access is recorded and raises,
    so any wizard mutation (or even a read) of the target is detected."""

    def __init__(self):
        object.__setattr__(self, "accessed", [])

    def __getattr__(self, name):
        self.accessed.append(name)
        raise AssertionError(f"WSWizard touched target.{name}")


def _select(wizard, row_idx, choice):
    row = wizard._tree.topLevelItem(row_idx)
    cb = wizard._tree.itemWidget(row, 1)
    cb.setCurrentIndex(cb.findData(choice))


def test_create_choice_is_recorded_without_touching_target(qapp):
    target = _TripwireTarget()
    mismatches = (
        WSMismatch(source_ws_id="ejg-fonipa", source_ws_kind=WSKind.VERNACULAR),
    )
    wizard = WSWizard(mismatches, target_project=target)
    _select(wizard, 0, WSChoice.CREATE)

    assert wizard._capture_choices() is True

    (choice,) = wizard._choices
    assert choice.choice == WSChoice.CREATE
    assert choice.source_ws_id == "ejg-fonipa"
    assert choice.source_ws_kind == WSKind.VERNACULAR
    assert target.accessed == []


def test_create_choice_without_target_still_records(qapp):
    mismatches = (
        WSMismatch(source_ws_id="ejg-Zxxx-x-audio", source_ws_kind=WSKind.VERNACULAR),
    )
    wizard = WSWizard(mismatches)
    _select(wizard, 0, WSChoice.CREATE)

    assert wizard._capture_choices() is True
    assert wizard._choices[0].choice == WSChoice.CREATE


def test_wizard_source_has_no_writing_systems_mutation():
    """Guard against the dead `WritingSystems.Add` call being reintroduced."""
    import gramtrans.Lib.ui.ws_wizard as mod

    with open(mod.__file__, encoding="utf-8") as fh:
        src = fh.read()
    assert "WritingSystems.Add" not in src.replace("`WritingSystems.Add`", "")
