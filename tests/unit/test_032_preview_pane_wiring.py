"""Feature 032 (pane wiring): _PageRules and _PageTexts now carry a
MergePreviewPane and dispatch the correct category on row selection.

Regression guard for the gap where US1 added the Stage-1 readers for
``adhoc_compound_rules`` and ``texts`` but the wizard pages that host those
items had no preview-pane widget, so the reader was never invoked (the pane
would render blank). These widget-level tests assert (1) the page builds a
pane and (2) selecting a row builds a PreviewRequest with the right category
and mode and calls ``pane.show_item``.

Offscreen Qt; no live LCM.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
pytest.importorskip("PyQt6")
from PyQt6 import QtWidgets

from gramtrans.Lib.merge_preview import OVERWRITE, NEW
from gramtrans.Lib.ui.merge_preview_pane import MergePreviewPane
from gramtrans.Lib.ui.selection_wizard import (
    _PageRules,
    _PageTexts,
    _RULES_GUID_ROLE,
    _RULES_KIND_ROLE,
    _RULES_STATUS_ROLE,
    _GUID_ROLE,
    _ITEM_STATUS_ROLE,
)


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


class _RecordingPane:
    """Stand-in for the MergePreviewPane that records show_item / clear."""

    def __init__(self):
        self.shown = []
        self.cleared = 0

    def show_item(self, request):
        self.shown.append(request)

    def clear(self):
        self.cleared += 1


# ---------------------------------------------------------------------------
# _PageRules (Ad hoc / Compound rule)
# ---------------------------------------------------------------------------

def test_rules_page_builds_a_pane(qapp):
    page = _PageRules()
    assert isinstance(page._pane, MergePreviewPane)


def test_rules_selection_dispatches_adhoc_category(qapp):
    page = _PageRules()
    page._pane = _RecordingPane()
    item = QtWidgets.QTreeWidgetItem(["r", "NEW"])
    item.setData(0, _RULES_KIND_ROLE, "item")
    item.setData(0, _RULES_GUID_ROLE, "rule-guid-1")
    item.setData(0, _RULES_STATUS_ROLE, "NEW")

    page._on_tree_selection_changed(item, None)

    assert len(page._pane.shown) == 1
    req = page._pane.shown[0]
    assert req.category == "adhoc_compound_rules"
    assert req.source_guid == "rule-guid-1"
    assert req.target_guid == ""      # NEW -> no target
    assert req.mode == NEW


def test_rules_in_target_row_is_overwrite(qapp):
    page = _PageRules()
    page._pane = _RecordingPane()
    item = QtWidgets.QTreeWidgetItem(["r", "IN TARGET"])
    item.setData(0, _RULES_KIND_ROLE, "item")
    item.setData(0, _RULES_GUID_ROLE, "rule-guid-2")
    item.setData(0, _RULES_STATUS_ROLE, "IN TARGET")

    page._on_tree_selection_changed(item, None)

    req = page._pane.shown[0]
    assert req.target_guid == "rule-guid-2"
    assert req.mode == OVERWRITE


def test_rules_group_header_clears_pane(qapp):
    page = _PageRules()
    page._pane = _RecordingPane()
    group = QtWidgets.QTreeWidgetItem(["Ad Hoc Rules (2)", ""])
    group.setData(0, _RULES_KIND_ROLE, "group")

    page._on_tree_selection_changed(group, None)

    assert page._pane.shown == []
    assert page._pane.cleared == 1


# ---------------------------------------------------------------------------
# _PageTexts
# ---------------------------------------------------------------------------

def test_texts_page_builds_a_pane(qapp):
    page = _PageTexts()
    assert isinstance(page._pane, MergePreviewPane)


def test_texts_selection_dispatches_texts_category(qapp):
    page = _PageTexts()
    page._pane = _RecordingPane()
    item = QtWidgets.QTreeWidgetItem(["A Story", "AS", "NEW"])
    item.setData(0, _GUID_ROLE, "text-guid-1")
    item.setData(0, _ITEM_STATUS_ROLE, "new")

    page._on_text_selection_changed(item, None)

    assert len(page._pane.shown) == 1
    req = page._pane.shown[0]
    assert req.category == "texts"
    assert req.source_guid == "text-guid-1"
    assert req.target_guid == ""
    assert req.mode == NEW


def test_texts_in_target_row_is_overwrite(qapp):
    page = _PageTexts()
    page._pane = _RecordingPane()
    item = QtWidgets.QTreeWidgetItem(["A Story", "AS", "IN TARGET"])
    item.setData(0, _GUID_ROLE, "text-guid-2")
    item.setData(0, _ITEM_STATUS_ROLE, "in_target")

    page._on_text_selection_changed(item, None)

    req = page._pane.shown[0]
    assert req.target_guid == "text-guid-2"
    assert req.mode == OVERWRITE
