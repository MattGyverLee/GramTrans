"""The Texts page (feature 039, T017).

Why this module exists
----------------------
Texts is its own page and its own module because it is the one selector whose
inventory is neither a grammar block nor derived from an earlier pick: it walks
the source's interlinear texts. It is small, it shares only the generic tree
helpers, and it has no relationship to any sibling page -- which is the whole
reason it can be 200 lines on its own rather than a section of something larger.

What is deliberately absent
---------------------------
* Wordform and analysis handling. What a picked text drags with it is a
  `Lib/` transfer concern (feature 026), not a selection-page one.
"""
from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

if __package__:
    from ..merge_preview import NEW, OVERWRITE, MergePreviewService
    from ..models import GrammarCategory
    from ..selection import build_text_inventory
    from ..ws_fonts import WsFontRegistry
    from .merge_preview_pane import MergePreviewPane, PreviewRequest
    from .wizard_page_base import _FlowPage
    from .wizard_roles import _GUID_ROLE, _ITEM_CAT_ROLE, _ITEM_STATUS_ROLE
    from .wizard_widgets import (
        _carry_full_values_in_tooltips,
        _make_tree_pane_splitter,
        _page_progress,
        _show_failure_row,
        _source_counts_of,
    )
else:
    from merge_preview import NEW, OVERWRITE, MergePreviewService  # type: ignore
    from merge_preview_pane import MergePreviewPane, PreviewRequest  # type: ignore
    from models import GrammarCategory  # type: ignore
    from selection import build_text_inventory  # type: ignore
    from wizard_page_base import _FlowPage  # type: ignore
    from wizard_roles import (  # type: ignore
        _GUID_ROLE,
        _ITEM_CAT_ROLE,
        _ITEM_STATUS_ROLE,
    )
    from wizard_widgets import (  # type: ignore
        _carry_full_values_in_tooltips,
        _make_tree_pane_splitter,
        _page_progress,
        _show_failure_row,
        _source_counts_of,
    )
    from ws_fonts import WsFontRegistry  # type: ignore


# ---------------------------------------------------------------------------
# Page 4 -- Preview
# ---------------------------------------------------------------------------

class _PageTexts(_FlowPage):
    """Texts item picker (Feature 026, US1 — Model-A per-text selection, FR-001).

    A flat, checkable list of the source's interlinear texts. The wordform
    analyses a human evaluated ride along as the closure of the checked texts
    (FR-001a), so there is no separate wordform picker. Rows open preselected
    (checked); deselect is the primary gesture (SC-004 — deselect any text
    without affecting the others). Exposes the checked set via
    :meth:`text_picks`, folded into the Selection by `_compute_wizard_plan`.

    Kept intentionally simple (no MergePreviewPane, no POS grouping): texts are
    never SIMILAR-resolvable and the analysis wiring is decided by the transfer
    walk (Lib/texts.py + Lib/wordforms.py), not the picker.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Texts")
        self.setSubTitle(
            "Pick the interlinear texts to transfer. Their evaluated analyses, "
            "translations, notes and genres travel with them."
        )
        self._text_inventory = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(
            "Interlinear texts in the source project (checked = transfer):", self
        ))
        self._text_tree = QtWidgets.QTreeWidget(self)
        self._text_tree.setColumnCount(3)
        self._text_tree.setHeaderLabels(["Text", "Abbrev.", "Target"])
        self._text_tree.setAlternatingRowColors(True)
        self._text_tree.setRootIsDecorated(False)
        self._pane = MergePreviewPane(self)
        splitter = _make_tree_pane_splitter(self._text_tree, self._pane)
        layout.addWidget(splitter, 1)
        self._preview_service = None
        btn_row = QtWidgets.QHBoxLayout()
        select_all = QtWidgets.QPushButton("Select all", self)
        select_none = QtWidgets.QPushButton("Select none", self)
        select_all.clicked.connect(lambda: self._set_all(QtCore.Qt.CheckState.Checked))
        select_none.clicked.connect(lambda: self._set_all(QtCore.Qt.CheckState.Unchecked))
        btn_row.addWidget(select_all)
        btn_row.addWidget(select_none)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

    # -- source/target handles (per-page copy, matching the wizard convention) --
    def _get_source(self):
        try:
            wizard = self.wizard()
            if wizard is None:
                return None
            page0 = wizard.page_project_ws()
            if page0 is None:
                return None
            ctx = page0.context()
            if ctx is not None:
                h = getattr(ctx, "source_handle", None)
                if h is not None:
                    return h
            return getattr(page0, "_host", None)
        except Exception:  # noqa: BLE001
            return None

    def _get_target(self):
        try:
            wizard = self.wizard()
            if wizard is None:
                return None
            page0 = wizard.page_project_ws()
            if page0 is None:
                return None
            ctx = page0.context()
            if ctx is None:
                return None
            return getattr(ctx, "target_handle", None)
        except Exception:  # noqa: BLE001
            return None

    def initializePage(self) -> None:
        """Build the text inventory from the bound source and populate the list.

        Guards for no-source (renders a disabled placeholder row, no crash).
        """
        source = self._get_source()
        self._text_tree.clear()
        if source is None:
            self._text_inventory = None
            empty = QtWidgets.QTreeWidgetItem(self._text_tree, ["(No source project bound)"])
            empty.setFlags(empty.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
            return
        target = self._get_target()
        # FR-023 row 11. Unit is the text. This is the slowest per-unit walk in
        # the wizard (a text carries paragraphs, segments and wordforms), which
        # is why a modest text count still predicts a wait worth announcing.
        try:
            with _page_progress(
                self, "texts", _source_counts_of(self).texts
            ) as prog:
                inventory = build_text_inventory(source, target=target, progress=prog)
        except Exception:  # noqa: BLE001
            _show_failure_row(self._text_tree, "texts")   # T022
            inventory = None
        self._text_inventory = inventory
        if inventory is None:
            return
        self.populate_text_list(inventory)
        _carry_full_values_in_tooltips(self._text_tree)   # T026 / FR-029b

        # Feature 032 US1: per-text preview pane (texts reader -> Title/Baseline).
        self._preview_service = MergePreviewService(source, target)
        self._pane.set_context(
            self._preview_service, WsFontRegistry.from_project(source), []
        )
        self._pane.clear()
        if self._text_tree.receivers(self._text_tree.currentItemChanged) == 0:
            self._text_tree.currentItemChanged.connect(self._on_text_selection_changed)

    def _on_text_selection_changed(self, current, previous) -> None:
        """Build a display-only PreviewRequest from the selected text row."""
        if current is None:
            self._pane.clear()
            return
        source_guid = current.data(0, _GUID_ROLE) or ""
        if not source_guid:
            self._pane.clear()
            return
        status = current.data(0, _ITEM_STATUS_ROLE) or ""
        if status == "in_target":
            target_guid, mode = source_guid, OVERWRITE
        else:
            target_guid, mode = "", NEW
        request = PreviewRequest(
            category=GrammarCategory.TEXTS.value,
            source_guid=source_guid,
            target_guid=target_guid,
            status=status,
            mode=mode,
            resolvable=False,
            current_resolution=None,
            owner_guid="",
        )
        self._pane.show_item(request)

    def populate_text_list(self, inventory) -> None:
        """Populate the checkable text list from a TextInventory.

        Rows open preselected (checked). Called by initializePage; may also be
        called directly in tests.
        """
        self._text_tree.clear()
        _status_labels = {"new": "NEW", "in_target": "IN TARGET"}
        for row in inventory.texts:
            target_label = _status_labels.get(row.status or "", "")
            item = QtWidgets.QTreeWidgetItem(
                self._text_tree, [row.title, row.abbreviation, target_label]
            )
            item.setData(0, _GUID_ROLE, row.guid)
            item.setData(0, _ITEM_CAT_ROLE, GrammarCategory.TEXTS)
            item.setData(0, _ITEM_STATUS_ROLE, row.status or "")
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, QtCore.Qt.CheckState.Checked)
        for col in range(3):
            self._text_tree.resizeColumnToContents(col)

    def _set_all(self, state) -> None:
        root = self._text_tree.invisibleRootItem()
        for i in range(root.childCount()):
            child = root.child(i)
            if child.flags() & QtCore.Qt.ItemFlag.ItemIsUserCheckable:
                child.setCheckState(0, state)

    def text_picks(self) -> frozenset:
        """Checked text GUIDs intersected with the known text inventory."""
        if self._text_inventory is None:
            return frozenset()
        checked: set = set()
        root = self._text_tree.invisibleRootItem()
        for i in range(root.childCount()):
            child = root.child(i)
            if child.checkState(0) == QtCore.Qt.CheckState.Checked:
                guid = child.data(0, _GUID_ROLE)
                if guid:
                    checked.add(guid)
        return frozenset(checked) & self._text_inventory.all_text_guids()
