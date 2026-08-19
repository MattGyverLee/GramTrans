"""The four Model-B "independent block" pages (feature 039, T016).

Why this module exists
----------------------
`specs/wizard-selection-roadmap.md`'s second selection model is the independent
block: one tree, one whole-block checkbox, wholesale NONE/ALL, nothing derived
from an earlier page. Custom Fields, Rules, Phonology and Lexical-Entry Types
are exactly the four pages that work that way -- and they are exactly the four
that carried the duplicated whole-block cluster the split measured (seven
methods, identical four times over, differing only in docstring wording and the
name of a loop variable).

That coincidence is the argument for `_BlockPage`: the base is not a DRY
convenience laid over four unrelated pages, it is the selection model written
once, and these are its four instances.

Each page keeps its own `collect_*` API. Those contracts genuinely differ --
`leaf_item_picks() -> dict`, `collect_rules_picks() -> Optional[frozenset]`
(where `None` means transfer-all, which is not the same as the empty set),
`collect_phonology_picks() -> dict[GrammarCategory, set]`,
`collect_entry_type_picks() -> dict` -- so they stay per-page.

What is deliberately absent
---------------------------
* The phonology and entry-type EXCLUDED-LOSSY helpers
  (`_phonology_excluded_lossy_for`, `_entry_types_missing_ref_for`). They stay
  in the facade: three test modules patch them with
  `monkeypatch.setattr(sw, ...)`, and a facade re-export cannot satisfy that --
  the caller resolved the name in its own module namespace at import time.
"""
from __future__ import annotations

from typing import Optional

from PyQt6 import QtCore, QtWidgets

if __package__:
    from ..merge_preview import NEW, OVERWRITE, MergePreviewService
    from ..models import GrammarCategory
    from ..selection import (
        build_entry_types_inventory,
        build_phonology_inventory,
        build_rules_inventory,
    )
    from ..ws_fonts import WsFontRegistry
    from .merge_preview_pane import MergePreviewPane, PreviewRequest
    from .wizard_page_base import _FlowPage
    from .wizard_roles import (
        _CF_GUID_ROLE,
        _CF_KIND_ROLE,
        _CF_LEVEL_LABELS,
        _CF_STATUS_ROLE,
        _ET_CAT_ROLE,
        _ET_GUID_ROLE,
        _ET_KIND_ROLE,
        _ET_STATUS_ROLE,
        _PHON_CAT_ROLE,
        _PHON_GUID_ROLE,
        _PHON_KIND_ROLE,
        _PHON_STATUS_ROLE,
        _RULES_GUID_ROLE,
        _RULES_KIND_ROLE,
        _RULES_STATUS_LABELS,
        _RULES_STATUS_ROLE,
        _STATUS_LABELS,
    )
    from .wizard_widgets import (
        _carry_full_values_in_tooltips,
        _make_tree_pane_splitter,
        _operation_failed_note,
        _page_progress,
        _show_failure_row,
        _source_counts_of,
    )
    from .ws_font_delegate import attach_ws_font_delegate, set_ws_runs
else:
    from merge_preview import NEW, OVERWRITE, MergePreviewService  # type: ignore
    from merge_preview_pane import MergePreviewPane, PreviewRequest  # type: ignore
    from models import GrammarCategory  # type: ignore
    from selection import (  # type: ignore
        build_entry_types_inventory,
        build_phonology_inventory,
        build_rules_inventory,
    )
    from wizard_page_base import _FlowPage  # type: ignore
    from wizard_roles import (  # type: ignore
        _CF_GUID_ROLE,
        _CF_KIND_ROLE,
        _CF_LEVEL_LABELS,
        _CF_STATUS_ROLE,
        _ET_CAT_ROLE,
        _ET_GUID_ROLE,
        _ET_KIND_ROLE,
        _ET_STATUS_ROLE,
        _PHON_CAT_ROLE,
        _PHON_GUID_ROLE,
        _PHON_KIND_ROLE,
        _PHON_STATUS_ROLE,
        _RULES_GUID_ROLE,
        _RULES_KIND_ROLE,
        _RULES_STATUS_LABELS,
        _RULES_STATUS_ROLE,
        _STATUS_LABELS,
    )
    from wizard_widgets import (  # type: ignore
        _carry_full_values_in_tooltips,
        _make_tree_pane_splitter,
        _operation_failed_note,
        _page_progress,
        _show_failure_row,
        _source_counts_of,
    )
    from ws_font_delegate import attach_ws_font_delegate, set_ws_runs  # type: ignore
    from ws_fonts import WsFontRegistry  # type: ignore


# ---------------------------------------------------------------------------
# Page 2 -- Custom Fields  (Feature 016, US1/US2/US4)
# ---------------------------------------------------------------------------


class _PageCustomFields(_FlowPage):
    """Page 2: Custom Fields block (Feature 016, US1/US2/US4).

    Grouped tree: four owner-class levels (Entry / Sense / Example / Allomorph),
    each with a count on its header.  Every row shows ``name + type-label`` in
    col 0 and target-status in col 1 (US4).  ALL rows preselected on open.

    The whole-block tristate toggle mirrors _PagePhonology: empty block =>
    unchecked + disabled (not vacuously full, per Acceptance 1.3).

    No ADD_NEW / LINK / UPDATE / OVERWRITE conflict-mode control (per spec: CUSTOM_FIELDS
    uses conservative LINK-only default, applied automatically at plan time).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Unnumbered: this run assigns the number on entry, because a
        # position is a fact about the run and not about the page
        # (SelectionWizard._apply_step_number). The literal that used to
        # be here stated a total across a flow that could skip pages.
        self.setTitle("Custom Fields")
        self.setSubTitle(
            "Every custom field in the source is preselected. Deselect any "
            "you do not want; Status shows what the target already has."
        )
        self._mirroring: bool = False
        self._records: list = []   # list[_CustomFieldRecord]
        self._preview_service = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        self._whole_block = QtWidgets.QCheckBox("Transfer custom fields block", self)
        self._whole_block.setTristate(True)
        self._whole_block.clicked.connect(self._on_whole_block_clicked)
        layout.addWidget(self._whole_block)

        self._tree = QtWidgets.QTreeWidget(self)
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["Field (type)", "Status"])
        self._tree.header().setStretchLastSection(True)
        self._tree.setAlternatingRowColors(True)
        # Feature 032 follow-up: merge-preview pane docked right, mirroring the
        # phonology page, so selecting a custom field shows its definition.
        self._pane = MergePreviewPane(self)
        splitter = _make_tree_pane_splitter(self._tree, self._pane)
        layout.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    def initializePage(self) -> None:
        """Called when the wizard enters this page; populates from source."""
        if self._tree.receivers(self._tree.itemChanged) > 0:
            self._tree.itemChanged.disconnect(self._on_item_changed)
        self._populate_from_source()
        self._tree.itemChanged.connect(self._on_item_changed)

        # Feature 032 follow-up: wire the preview pane (source-vs-target diff of
        # the field definition). Best-effort; a missing source leaves it blank.
        source = self._get_source()
        if source is not None:
            target = self._get_target()
            self._preview_service = MergePreviewService(source, target)
            self._pane.set_context(
                self._preview_service, WsFontRegistry.from_project(source), []
            )
            self._pane.clear()
            if self._tree.receivers(self._tree.currentItemChanged) == 0:
                self._tree.currentItemChanged.connect(self._on_tree_selection_changed)

    # ------------------------------------------------------------------
    def _on_tree_selection_changed(self, current, previous) -> None:
        """Build a display-only PreviewRequest from the selected custom-field row.

        Custom-field rows are never resolvable (no similar-affix header). A field
        already in the target (IN_TARGET) diffs against it (OVERWRITE mode); a
        new field renders all-added (NEW mode). Both sides resolve the synthetic
        cf:<owner>:<name> id via the dedicated reader in merge_preview.
        """
        if current is None:
            self._pane.clear()
            return
        if current.data(0, _CF_KIND_ROLE) != "item":
            self._pane.clear()
            return
        guid = current.data(0, _CF_GUID_ROLE) or ""
        status = current.data(0, _CF_STATUS_ROLE) or ""
        if status == "IN_TARGET":
            target_guid = guid  # same synthetic id resolves on the target side
            mode = OVERWRITE
            status_str = "in_target"
        else:
            target_guid = ""
            mode = NEW
            status_str = "new"
        request = PreviewRequest(
            category=GrammarCategory.CUSTOM_FIELDS.value,
            source_guid=guid,
            target_guid=target_guid,
            status=status_str,
            mode=mode,
            resolvable=False,
            current_resolution=None,
            owner_guid="",
        )
        self._pane.show_item(request)

    def _populate_from_source(self) -> None:
        """Enumerate source custom fields and build the four-level tree."""
        self._tree.clear()
        self._records = []

        source = self._get_source()
        target = self._get_target()

        if source is None:
            empty = QtWidgets.QTreeWidgetItem(self._tree, ["(No source project bound)", ""])
            empty.setFlags(empty.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
            self._refresh_whole_block()
            return

        # Import enumerate helper from categories (read-only, safe inside UoW).
        if __package__:
            from ..categories import (
                _enumerate_custom_fields,
                classify_custom_field,
                custom_field_type_label,
            )
        else:
            from categories import (  # type: ignore
                _enumerate_custom_fields,
                classify_custom_field,
                custom_field_type_label,
            )

        # FR-023 row 3. This page has no `build_*` in Lib/selection.py to hand a
        # sink to -- it consumes a generator out of `categories.py` directly --
        # so the tick happens where the consumption does. Same contract either
        # way: one tick per unit, from inside the walk (FR-014).
        try:
            with _page_progress(
                self, "custom_fields", _source_counts_of(self).custom_fields
            ) as prog:
                all_records = []
                for _rec in _enumerate_custom_fields(source):
                    all_records.append(_rec)
                    prog.tick()
        except Exception:  # noqa: BLE001
            # T022. Not `_show_failure_row`: the four owner-class headers below
            # are built unconditionally and are the page's own structure, so the
            # note goes ABOVE them rather than replacing the tree they are about
            # to repopulate.
            all_records = []
            note = QtWidgets.QTreeWidgetItem(
                self._tree, [_operation_failed_note("custom_fields"), ""]
            )
            note.setFlags(note.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)

        self._records = all_records

        # Group by owner class in canonical order.
        from PyQt6 import QtGui as _QtGui

        if __package__:
            from ..categories import _CUSTOM_FIELD_OWNER_CLASSES
        else:
            from categories import _CUSTOM_FIELD_OWNER_CLASSES  # type: ignore

        by_class: dict = {cls: [] for cls in _CUSTOM_FIELD_OWNER_CLASSES}
        for rec in all_records:
            if rec.owner_class in by_class:
                by_class[rec.owner_class].append(rec)

        for cls in _CUSTOM_FIELD_OWNER_CLASSES:
            rows = by_class[cls]
            level_label = _CF_LEVEL_LABELS.get(cls, cls)
            count = len(rows)
            header = QtWidgets.QTreeWidgetItem(
                self._tree, [f"{level_label} ({count})", ""]
            )
            header.setData(0, _CF_KIND_ROLE, "group")
            header.setFlags(
                header.flags()
                | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                | QtCore.Qt.ItemFlag.ItemIsAutoTristate
            )
            header.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
            bold = header.font(0)
            bold.setBold(True)
            header.setFont(0, bold)

            for rec in rows:
                type_label = custom_field_type_label(rec.field_type)
                row_label = f"{rec.name} ({type_label})"

                # US4: classify against target.
                status, type_diff_note = ("", None)
                if target is not None:
                    try:
                        status, type_diff_note = classify_custom_field(rec, target)
                    except Exception:  # noqa: BLE001
                        status, type_diff_note = "", None

                # Map status token to display text.
                _status_display = {
                    "NEW": "NEW",
                    "IN_TARGET": "IN TARGET",
                    "": "",
                }
                status_text = _status_display.get(status, status)
                if type_diff_note:
                    status_text = "IN TARGET"  # field exists, type differs

                item = QtWidgets.QTreeWidgetItem(header, [row_label, status_text])
                item.setData(0, _CF_GUID_ROLE, rec.guid)
                item.setData(0, _CF_KIND_ROLE, "item")
                item.setData(0, _CF_STATUS_ROLE, status)
                item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, QtCore.Qt.CheckState.Checked)
                if type_diff_note:
                    item.setToolTip(0, type_diff_note)
                    item.setToolTip(1, type_diff_note)

        self._tree.expandAll()
        for col in range(2):
            self._tree.resizeColumnToContents(col)
        # T026 / FR-029b. Last, so the type-difference tooltips set above keep
        # their richer text -- the sweep fills only the cells that have none.
        _carry_full_values_in_tooltips(self._tree)
        self._refresh_whole_block()

    # -- whole-block toggle -----------------------------------------------
    def _on_whole_block_clicked(self, _checked: bool = False) -> None:
        if not self._has_any_item():
            self._refresh_whole_block()
            return
        want_checked = not self._all_items_checked()
        self._set_all_items(want_checked)
        self._refresh_whole_block()

    def _set_all_items(self, checked: bool) -> None:
        state = (QtCore.Qt.CheckState.Checked if checked
                 else QtCore.Qt.CheckState.Unchecked)
        self._mirroring = True
        try:
            for _grp, item in self._iter_item_rows():
                item.setCheckState(0, state)
        finally:
            self._mirroring = False

    def _refresh_whole_block(self) -> None:
        """Reflect aggregate item state on the whole-block tristate box.

        Empty block => unchecked + disabled (NOT vacuously full, per Acceptance 1.3).
        """
        self._mirroring = True
        try:
            if not self._has_any_item():
                self._whole_block.setEnabled(False)
                self._whole_block.setCheckState(QtCore.Qt.CheckState.Unchecked)
                return
            self._whole_block.setEnabled(True)
            checked = sum(
                1 for _g, it in self._iter_item_rows()
                if it.checkState(0) == QtCore.Qt.CheckState.Checked
            )
            total = sum(1 for _ in self._iter_item_rows())
            if checked == 0:
                self._whole_block.setCheckState(QtCore.Qt.CheckState.Unchecked)
            elif checked == total:
                self._whole_block.setCheckState(QtCore.Qt.CheckState.Checked)
            else:
                self._whole_block.setCheckState(QtCore.Qt.CheckState.PartiallyChecked)
        finally:
            self._mirroring = False

    def _on_item_changed(self, item, column) -> None:
        if self._mirroring or column != 0:
            return
        self._refresh_whole_block()

    # -- tree walking helpers -----------------------------------------------
    def _iter_item_rows(self):
        """Yield (group_item, item) for every checkable custom-field item row."""
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            group = root.child(i)
            if group.data(0, _CF_KIND_ROLE) != "group":
                continue
            for j in range(group.childCount()):
                item = group.child(j)
                if item.data(0, _CF_KIND_ROLE) == "item":
                    yield group, item

    def _has_any_item(self) -> bool:
        for _ in self._iter_item_rows():
            return True
        return False

    def _all_items_checked(self) -> bool:
        any_item = False
        for _g, item in self._iter_item_rows():
            any_item = True
            if item.checkState(0) != QtCore.Qt.CheckState.Checked:
                return False
        return any_item

    # -- state API (US2) ---------------------------------------------------
    def leaf_item_picks(self) -> dict:
        """Return leaf_item_picks dict for custom fields.

        Fully-checked => omit key (transfer-all back-compat).
        Partial => {GrammarCategory.CUSTOM_FIELDS: frozenset[str guids]}.
        Fully-unchecked / empty => {GrammarCategory.CUSTOM_FIELDS: frozenset()}.
        """
        if not self._has_any_item():
            return {}

        checked_guids: set = set()
        total = 0
        for _grp, item in self._iter_item_rows():
            total += 1
            if item.checkState(0) == QtCore.Qt.CheckState.Checked:
                guid = item.data(0, _CF_GUID_ROLE)
                if guid:
                    checked_guids.add(guid)

        if len(checked_guids) == total:
            # Fully checked => omit key (transfer-all).
            return {}
        return {GrammarCategory.CUSTOM_FIELDS: frozenset(checked_guids)}

    def whole_block_on(self) -> bool:
        """True iff any field row is checked."""
        for _g, item in self._iter_item_rows():
            if item.checkState(0) == QtCore.Qt.CheckState.Checked:
                return True
        return False

    # -- source/target helpers ---------------------------------------------
    def _get_source(self):
        try:
            w = self.wizard()
            if w is None:
                return None
            p0 = w.page_project_ws()
            if p0 is None:
                return None
            ctx = p0.context()
            if ctx is not None:
                h = getattr(ctx, "source_handle", None)
                if h is not None:
                    return h
            return getattr(p0, "_host", None)
        except Exception:  # noqa: BLE001
            return None

    def _get_target(self):
        try:
            w = self.wizard()
            if w is None:
                return None
            p0 = w.page_project_ws()
            if p0 is None:
                return None
            ctx = p0.context()
            if ctx is None:
                return None
            return getattr(ctx, "target_handle", None)
        except Exception:  # noqa: BLE001
            return None


class _PageRules(_FlowPage):
    """Rules page (018-rules-page): Ad Hoc Rules + Compound Rules block.

    Two grouped tristate trees, all rows preselected.  Whole-block toggle
    controls the entire block (tristate: all / none / partial).  Empty
    category renders as empty (FR-011) — not an error.

    No ADD_NEW / LINK / UPDATE / OVERWRITE conflict-mode control (FR-016):
    per-category Layer-1 defaults are applied automatically at plan time.

    On page-leave, ``collect_rules_picks()`` collapses checked rows into
    ``Selection.leaf_item_picks[ADHOC_COMPOUND_RULES]``:
      - whole block ON, nothing trimmed  => key ABSENT (SC-004)
      - whole block OFF                  => empty frozenset (SC-005)
      - individual trim                  => full set minus deselected GUIDs
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Unnumbered: this run assigns the number on entry, because a
        # position is a fact about the run and not about the page
        # (SelectionWizard._apply_step_number). The literal that used to
        # be here stated a total across a flow that could skip pages.
        self.setTitle("Rules")
        self.setSubTitle(
            "Every ad hoc and compound rule in the source is preselected. "
            "Untick the block or deselect single rules. Status shows what the "
            "target has."
        )
        self._inventory = None   # RulesInventory | None
        self._mirroring: bool = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        self._whole_block = QtWidgets.QCheckBox("Transfer rules block", self)
        self._whole_block.setTristate(True)
        self._whole_block.clicked.connect(self._on_whole_block_clicked)
        layout.addWidget(self._whole_block)

        self._tree = QtWidgets.QTreeWidget(self)
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["Rule", "Target"])
        self._tree.header().setStretchLastSection(True)
        self._tree.setAlternatingRowColors(True)
        self._pane = MergePreviewPane(self)
        splitter = _make_tree_pane_splitter(self._tree, self._pane)
        layout.addWidget(splitter, 1)
        self._preview_service = None

    # ------------------------------------------------------------------
    def initializePage(self) -> None:
        """Build the inventory from source+target; ALL rows preselected."""
        if self._tree.receivers(self._tree.itemChanged) > 0:
            self._tree.itemChanged.disconnect(self._on_item_changed)
        self._tree.clear()
        self._inventory = None

        source = self._get_source()
        if source is None:
            empty = QtWidgets.QTreeWidgetItem(
                self._tree, ["(No source project bound)", ""]
            )
            empty.setFlags(empty.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
            self._refresh_whole_block()
            return

        target = self._get_target()
        # FR-023 row 10. Unit is the ad-hoc prohibition, counted off the owning
        # collection at bind.
        try:
            with _page_progress(
                self, "rules", _source_counts_of(self).rules
            ) as prog:
                inventory = build_rules_inventory(source, target=target, progress=prog)
        except Exception:  # noqa: BLE001
            _show_failure_row(self._tree, "rules")   # T022
            inventory = None

        if inventory is None:
            self._refresh_whole_block()
            return

        self._inventory = inventory
        self._populate_tree(inventory)
        _carry_full_values_in_tooltips(self._tree)   # T026 / FR-029b
        self._tree.expandAll()
        for col in range(2):
            self._tree.resizeColumnToContents(col)
        self._tree.itemChanged.connect(self._on_item_changed)
        self._refresh_whole_block()

        # Feature 032 US1: per-rule preview pane (adhoc_compound_rules reader).
        self._preview_service = MergePreviewService(source, target)
        self._pane.set_context(
            self._preview_service, WsFontRegistry.from_project(source), []
        )
        self._pane.clear()
        if self._tree.receivers(self._tree.currentItemChanged) == 0:
            self._tree.currentItemChanged.connect(self._on_tree_selection_changed)

    def _on_tree_selection_changed(self, current, previous) -> None:
        """Build a display-only PreviewRequest from the selected rule row."""
        if current is None or current.data(0, _RULES_KIND_ROLE) != "item":
            self._pane.clear()
            return
        source_guid = current.data(0, _RULES_GUID_ROLE) or ""
        status = current.data(0, _RULES_STATUS_ROLE) or ""
        if status == "IN TARGET":
            target_guid, mode = source_guid, _ET_MODE_OVERWRITE
        else:
            target_guid, mode = "", _ET_MODE_NEW
        request = PreviewRequest(
            category=GrammarCategory.ADHOC_COMPOUND_RULES.value,
            source_guid=source_guid,
            target_guid=target_guid,
            status=status,
            mode=mode,
            resolvable=False,
            current_resolution=None,
            owner_guid="",
        )
        self._pane.show_item(request)

    def _populate_tree(self, inventory) -> None:
        """One tristate group per category (count on header); item rows checked."""
        for group in (inventory.adhoc, inventory.compound):
            header = QtWidgets.QTreeWidgetItem(
                self._tree,
                [f"{group.category_label} ({group.count})", ""]
            )
            header.setData(0, _RULES_KIND_ROLE, "group")
            header.setFlags(
                header.flags()
                | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                | QtCore.Qt.ItemFlag.ItemIsAutoTristate
            )
            header.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
            bold = header.font(0)
            bold.setBold(True)
            header.setFont(0, bold)

            if not group.rows:
                # FR-011: empty category renders as empty, not an error
                none_item = QtWidgets.QTreeWidgetItem(header, ["(none)", ""])
                none_item.setFlags(
                    none_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled
                )
                continue

            for row in group.rows:
                status_text = _RULES_STATUS_LABELS.get(row.target_status, row.target_status)
                item = QtWidgets.QTreeWidgetItem(
                    header, [row.label, status_text]
                )
                item.setData(0, _RULES_GUID_ROLE, row.guid)
                item.setData(0, _RULES_KIND_ROLE, "item")
                item.setData(0, _RULES_STATUS_ROLE, row.target_status)
                item.setFlags(
                    item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                )
                cs = (QtCore.Qt.CheckState.Checked if row.checked
                      else QtCore.Qt.CheckState.Unchecked)
                item.setCheckState(0, cs)

    # -- whole-block toggle ------------------------------------------------
    def _on_whole_block_clicked(self, _checked: bool = False) -> None:
        """User toggled the whole-block checkbox: check-all or uncheck-all."""
        if not self._has_any_item():
            self._refresh_whole_block()
            return
        want_checked = not self._all_items_checked()
        self._set_all_items(want_checked)
        self._refresh_whole_block()

    def _set_all_items(self, checked: bool) -> None:
        state = (QtCore.Qt.CheckState.Checked if checked
                 else QtCore.Qt.CheckState.Unchecked)
        self._mirroring = True
        try:
            for _g, item in self._iter_item_rows():
                item.setCheckState(0, state)
        finally:
            self._mirroring = False

    def _refresh_whole_block(self) -> None:
        """Reflect aggregate item state on the whole-block tristate box.

        Empty block => unchecked + disabled (NOT vacuously fully-selected,
        per edge-case invariant — mirrors _PagePhonology / _PageCustomFields).
        """
        self._mirroring = True
        try:
            if not self._has_any_item():
                self._whole_block.setEnabled(False)
                self._whole_block.setCheckState(QtCore.Qt.CheckState.Unchecked)
                return
            self._whole_block.setEnabled(True)
            checked = sum(
                1 for _g, it in self._iter_item_rows()
                if it.checkState(0) == QtCore.Qt.CheckState.Checked
            )
            total = sum(1 for _ in self._iter_item_rows())
            if checked == 0:
                self._whole_block.setCheckState(QtCore.Qt.CheckState.Unchecked)
            elif checked == total:
                self._whole_block.setCheckState(QtCore.Qt.CheckState.Checked)
            else:
                self._whole_block.setCheckState(
                    QtCore.Qt.CheckState.PartiallyChecked
                )
        finally:
            self._mirroring = False

    def _on_item_changed(self, item, column) -> None:
        if self._mirroring or column != 0:
            return
        self._refresh_whole_block()

    # -- tree walking helpers ----------------------------------------------
    def _iter_item_rows(self):
        """Yield (group_item, item) for every checkable rule item row."""
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            group = root.child(i)
            if group.data(0, _RULES_KIND_ROLE) != "group":
                continue
            for j in range(group.childCount()):
                item = group.child(j)
                if item.data(0, _RULES_KIND_ROLE) == "item":
                    yield group, item

    def _has_any_item(self) -> bool:
        for _ in self._iter_item_rows():
            return True
        return False

    def _all_items_checked(self) -> bool:
        any_item = False
        for _g, item in self._iter_item_rows():
            any_item = True
            if item.checkState(0) != QtCore.Qt.CheckState.Checked:
                return False
        return any_item

    def whole_block_on(self) -> bool:
        """True iff any item row is currently checked."""
        for _g, item in self._iter_item_rows():
            if item.checkState(0) == QtCore.Qt.CheckState.Checked:
                return True
        return False

    # -- state API (T019) --------------------------------------------------
    def collect_rules_picks(self) -> Optional[frozenset]:
        """Return checked GUIDs as a frozenset, or None for 'transfer all'.

        None  => key absent from leaf_item_picks (SC-004 untouched default).
        frozenset() => whole block OFF, transfer nothing (SC-005).
        frozenset({...}) => individual trim — full set minus deselected.

        Grouping node semantics: a group node is included iff >=1 child is
        kept; deselected children are excluded (data-model.md edge case).
        """
        if self._inventory is None:
            return None

        all_item_guids = frozenset(
            item.data(0, _RULES_GUID_ROLE)
            for _g, item in self._iter_item_rows()
            if item.data(0, _RULES_GUID_ROLE)
        )
        checked_guids = frozenset(
            item.data(0, _RULES_GUID_ROLE)
            for _g, item in self._iter_item_rows()
            if item.checkState(0) == QtCore.Qt.CheckState.Checked
            and item.data(0, _RULES_GUID_ROLE)
        )

        # Whole block OFF => empty frozenset
        if not checked_guids:
            return frozenset()

        # All rows checked => key absent (SC-004 / data-model "untouched" case)
        if checked_guids == all_item_guids:
            return None

        # Individual trim
        return checked_guids

    def inventory(self):
        """Return the current RulesInventory (may be None before initializePage)."""
        return self._inventory

    # ------------------------------------------------------------------
    def _get_source(self):
        try:
            w = self.wizard()
            if w is None:
                return None
            p0 = w.page_project_ws()
            if p0 is None:
                return None
            ctx = p0.context()
            if ctx is not None:
                h = getattr(ctx, "source_handle", None)
                if h is not None:
                    return h
            return getattr(p0, "_host", None)
        except Exception:  # noqa: BLE001
            return None

    def _get_target(self):
        try:
            w = self.wizard()
            if w is None:
                return None
            p0 = w.page_project_ws()
            if p0 is None:
                return None
            ctx = p0.context()
            if ctx is None:
                return None
            return getattr(ctx, "target_handle", None)
        except Exception:  # noqa: BLE001
            return None


# ---------------------------------------------------------------------------
# Page 3 -- Phonology  (spec 010, Model-B independent block)
# ---------------------------------------------------------------------------


# SC-008: module-level aliases used inside _PagePhonology instead of string literals.
_PHON_MODE_OVERWRITE = OVERWRITE
_PHON_MODE_NEW = NEW


class _PagePhonology(_FlowPage):
    """Page 2: Phonology block (spec 010 — the first Model-B selector).

    A grouped tree of the five user-facing phonology categories (features,
    phonemes, natural classes, environments, rules), each with a count on its
    header, ALL rows preselected. The user may toggle the whole block off, trim
    a whole category, or deselect individual items; trimmed categories emit a
    ``leaf_item_picks`` subset at collapse time (fully-checked categories omit
    the key ⇒ transfer-all).

    Strata are NEVER a user row (FR-009) — they travel automatically iff a rule
    is kept, decided in ``collapse_phonology``.

    Deliberately renders NO ADD_NEW/LINK/UPDATE/OVERWRITE conflict-mode control
    (FR-012 / SC-008); Layer-1 default conflict modes are applied automatically
    when the Preview page builds the Selection.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Unnumbered: this run assigns the number on entry, because a
        # position is a fact about the run and not about the page
        # (SelectionWizard._apply_step_number). The literal that used to
        # be here stated a total across a flow that could skip pages.
        self.setTitle("Phonology")
        self.setSubTitle(
            "Every phoneme, natural class and rule is preselected. Untick the "
            "block, a category, or single items to trim. Strata follow any rule "
            "you keep."
        )
        self._inventory: Optional[object] = None  # PhonologyInventory
        self._mirroring: bool = False
        # T012: preview service (initialized in initializePage)
        self._preview_service = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        self._whole_block = QtWidgets.QCheckBox(
            "Transfer phonology block", self
        )
        self._whole_block.setTristate(True)
        # `clicked` fires on user action only (not on programmatic setCheckState),
        # so the aggregate refresh below never re-enters through it.
        self._whole_block.clicked.connect(self._on_whole_block_clicked)
        layout.addWidget(self._whole_block)

        self._tree = QtWidgets.QTreeWidget(self)
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["Item", "Target"])
        self._tree.header().setStretchLastSection(True)
        self._tree.setAlternatingRowColors(True)
        # T012: merge-preview pane docked to the right (FR-005)
        self._pane = MergePreviewPane(self)
        splitter = _make_tree_pane_splitter(self._tree, self._pane)
        layout.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    def initializePage(self) -> None:
        """Build the inventory from the bound source+target; ALL preselected."""
        if self._tree.receivers(self._tree.itemChanged) > 0:
            self._tree.itemChanged.disconnect(self._on_item_changed)
        self._tree.clear()
        self._inventory = None

        source = self._get_source()
        if source is None:
            empty = QtWidgets.QTreeWidgetItem(
                self._tree, ["(No source project bound)", ""]
            )
            empty.setFlags(empty.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
            self._refresh_whole_block()
            return

        target = self._get_target()
        # FR-023 row 4. Unit is the list item: phoneme sets + natural classes +
        # phonological rules, summed at bind. The sum is None unless all three
        # were readable, because an under-stated total is worse than none
        # (Lib/progress.py `_sum_or_none`).
        try:
            with _page_progress(
                self, "phonology", _source_counts_of(self).phonology
            ) as prog:
                inventory = build_phonology_inventory(
                    source, target=target, progress=prog
                )
        except Exception:  # noqa: BLE001
            _show_failure_row(self._tree, "phonology")   # T022
            inventory = None

        if inventory is None:
            self._refresh_whole_block()
            return

        self._inventory = inventory
        # spec 011: render each item in its FLEx-defined WS font (phoneme
        # grapheme in the vernacular font, /IPA/ in the IPA font, etc.).
        attach_ws_font_delegate(
            self._tree, [0], WsFontRegistry.from_project(source)
        )
        self._populate_tree(inventory)
        _carry_full_values_in_tooltips(self._tree)   # T026 / FR-029b
        self._tree.expandAll()
        for col in range(2):
            self._tree.resizeColumnToContents(col)
        self._tree.itemChanged.connect(self._on_item_changed)
        self._refresh_whole_block()

        # T012: construct service and set pane context (FR-006)
        self._preview_service = MergePreviewService(source, target)
        self._pane.set_context(
            self._preview_service,
            WsFontRegistry.from_project(source),
            [],  # no candidates for phonology
        )
        self._pane.clear()
        # Double-connect guard (existing pattern preserved)
        if self._tree.receivers(self._tree.currentItemChanged) == 0:
            self._tree.currentItemChanged.connect(self._on_tree_selection_changed)

    def _populate_tree(self, inventory) -> None:
        """One tristate group per category (count on header); item rows checked."""
        from PyQt6 import QtGui  # noqa: F401  (font bolding, mirrors sibling pages)
        for group in inventory.groups:
            header = QtWidgets.QTreeWidgetItem(
                self._tree, [f"{group.label} ({group.count})", ""]
            )
            header.setData(0, _PHON_KIND_ROLE, "group")
            header.setData(0, _PHON_CAT_ROLE, group.category)
            header.setFlags(
                header.flags()
                | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                | QtCore.Qt.ItemFlag.ItemIsAutoTristate
            )
            header.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
            bold = header.font(0)
            bold.setBold(True)
            header.setFont(0, bold)

            if not group.rows:
                none_item = QtWidgets.QTreeWidgetItem(header, ["(none)", ""])
                none_item.setFlags(
                    none_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled
                )
                continue

            for row in group.rows:
                item = QtWidgets.QTreeWidgetItem(
                    header,
                    [row.label, _STATUS_LABELS.get(row.status or "", "")]
                )
                set_ws_runs(item, 0, row.runs)
                item.setData(0, _PHON_GUID_ROLE, row.guid)
                item.setData(0, _PHON_KIND_ROLE, "item")
                item.setData(0, _PHON_CAT_ROLE, row.category)
                # T008: status role for pane PreviewRequest construction (FR-010, R6)
                item.setData(0, _PHON_STATUS_ROLE, row.status or "")
                item.setFlags(
                    item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                )
                cs = (QtCore.Qt.CheckState.Checked if row.preselected
                      else QtCore.Qt.CheckState.Unchecked)
                item.setCheckState(0, cs)

    # T012: tree selection handler (display-only, R8)
    def _on_tree_selection_changed(self, current, previous) -> None:
        """Build PreviewRequest from selected phonology row (display-only, R8).

        Phonology rows never show the resolution header (resolvable=False).
        SIMILAR phonology rows use the overwrite diff mode for compare display.
        Mode strings come from merge_preview constants imported at module level;
        the string form is used here to avoid ConflictMode references (SC-008).
        """
        if current is None:
            self._pane.clear()
            return
        kind = current.data(0, _PHON_KIND_ROLE)
        if kind == "group":
            self._pane.clear()
            return

        source_guid = current.data(0, _PHON_GUID_ROLE) or ""
        category = current.data(0, _PHON_CAT_ROLE)
        status = current.data(0, _PHON_STATUS_ROLE) or ""

        # R8: all phonology rows use resolvable=False.
        # SIMILAR -> compare diff (overwrite diff mode); NEW -> all-green (new mode).
        # Use module-level aliases _PHON_MODE_OVERWRITE / _PHON_MODE_NEW (SC-008).
        if status == "similar":
            # matched_target_guid: 011 stores the match target in _PHON_GUID_ROLE
            # for SIMILAR rows when available; fall back to source_guid.
            matched_target_guid = getattr(
                self, "_phon_similar_target", {}
            ).get(source_guid, source_guid)
            target_guid = matched_target_guid
            mode = _PHON_MODE_OVERWRITE
        elif status == "new":
            target_guid = ""
            mode = _PHON_MODE_NEW
        else:  # "in_target"
            target_guid = source_guid
            mode = _PHON_MODE_OVERWRITE

        cat_str = category.value if category is not None else GrammarCategory.PHONEMES.value
        request = PreviewRequest(
            category=cat_str,
            source_guid=source_guid,
            target_guid=target_guid,
            status=status,
            mode=mode,
            resolvable=False,
            current_resolution=None,
            owner_guid="",
        )
        self._pane.show_item(request)

    # -- whole-block toggle (T017) -------------------------------------
    def _on_whole_block_clicked(self, _checked: bool = False) -> None:
        """User toggled the whole-block checkbox: check-all or uncheck-all.

        Ignores Qt's cycled tristate state and decides from the tree so the
        behaviour is deterministic (partial ⇒ check-all, full ⇒ uncheck-all).
        """
        if not self._has_any_item():
            self._refresh_whole_block()
            return
        want_checked = not self._all_items_checked()
        self._set_all_items(want_checked)
        self._refresh_whole_block()

    def _set_all_items(self, checked: bool) -> None:
        state = (QtCore.Qt.CheckState.Checked if checked
                 else QtCore.Qt.CheckState.Unchecked)
        self._mirroring = True
        try:
            for group, item in self._iter_item_rows():
                item.setCheckState(0, state)
        finally:
            self._mirroring = False

    def _refresh_whole_block(self) -> None:
        """Reflect the aggregate item state on the whole-block tristate box.

        Empty block (no items at all) ⇒ unchecked + disabled (NOT vacuously
        fully-selected, per the edge-case invariant in the contract).
        """
        self._mirroring = True
        try:
            if not self._has_any_item():
                self._whole_block.setEnabled(False)
                self._whole_block.setCheckState(QtCore.Qt.CheckState.Unchecked)
                return
            self._whole_block.setEnabled(True)
            checked = sum(
                1 for _g, it in self._iter_item_rows()
                if it.checkState(0) == QtCore.Qt.CheckState.Checked
            )
            total = sum(1 for _ in self._iter_item_rows())
            if checked == 0:
                self._whole_block.setCheckState(QtCore.Qt.CheckState.Unchecked)
            elif checked == total:
                self._whole_block.setCheckState(QtCore.Qt.CheckState.Checked)
            else:
                self._whole_block.setCheckState(
                    QtCore.Qt.CheckState.PartiallyChecked
                )
        finally:
            self._mirroring = False

    def _on_item_changed(self, item, column) -> None:
        if self._mirroring or column != 0:
            return
        self._refresh_whole_block()

    # -- tree walking helpers ------------------------------------------
    def _iter_item_rows(self):
        """Yield (group_item, item) for every checkable phonology item row."""
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            group = root.child(i)
            if group.data(0, _PHON_KIND_ROLE) != "group":
                continue
            for j in range(group.childCount()):
                item = group.child(j)
                if item.data(0, _PHON_KIND_ROLE) == "item":
                    yield group, item

    def _has_any_item(self) -> bool:
        for _ in self._iter_item_rows():
            return True
        return False

    def _all_items_checked(self) -> bool:
        any_item = False
        for _g, item in self._iter_item_rows():
            any_item = True
            if item.checkState(0) != QtCore.Qt.CheckState.Checked:
                return False
        return any_item

    # -- state API (contract §Page state) ------------------------------
    def collect_phonology_picks(self) -> dict:
        """Return {GrammarCategory: set[str] checked guids} for the 5 categories."""
        picks: dict = {}
        for group, item in self._iter_item_rows():
            if item.checkState(0) != QtCore.Qt.CheckState.Checked:
                continue
            cat = item.data(0, _PHON_CAT_ROLE)
            guid = item.data(0, _PHON_GUID_ROLE)
            if cat is None or not guid:
                continue
            picks.setdefault(cat, set()).add(guid)
        return picks

    def whole_block_on(self) -> bool:
        """True iff any category has >=1 checked row."""
        for _g, item in self._iter_item_rows():
            if item.checkState(0) == QtCore.Qt.CheckState.Checked:
                return True
        return False

    def deselected_needed_guids(self) -> frozenset:
        """Preselected-but-unchecked guids (input to EXCLUDED-LOSSY, T024)."""
        out = set()
        for _g, item in self._iter_item_rows():
            if item.checkState(0) != QtCore.Qt.CheckState.Checked:
                guid = item.data(0, _PHON_GUID_ROLE)
                if guid:
                    out.add(guid)
        return frozenset(out)

    def inventory(self):
        return self._inventory

    # ------------------------------------------------------------------
    def _get_source(self):
        try:
            w = self.wizard()
            if w is None:
                return None
            p0 = w.page_project_ws()
            if p0 is None:
                return None
            ctx = p0.context()
            if ctx is not None:
                h = getattr(ctx, "source_handle", None)
                if h is not None:
                    return h
            return getattr(p0, "_host", None)
        except Exception:  # noqa: BLE001
            return None

    def _get_target(self):
        try:
            w = self.wizard()
            if w is None:
                return None
            p0 = w.page_project_ws()
            if p0 is None:
                return None
            ctx = p0.context()
            if ctx is None:
                return None
            return getattr(ctx, "target_handle", None)
        except Exception:  # noqa: BLE001
            return None


# ---------------------------------------------------------------------------
# Page 7 -- Lexical-Entry Types (spec 021, Model-B independent block)
# ---------------------------------------------------------------------------


# SC-008: module-level mode aliases used inside _PageEntryTypes (no ConflictMode refs).
_ET_MODE_OVERWRITE = OVERWRITE
_ET_MODE_NEW = NEW


class _PageEntryTypes(_FlowPage):
    """Page 7: Lexical-Entry Types block (spec 021 -- the second Model-B selector).

    A grouped tree of two entry-type categories (Variant Types, Complex Form Types),
    each with a count on its header, ALL user-defined rows preselected.  The user may
    toggle the whole block off, trim a whole category, or deselect individual types.
    Trimmed categories emit a ``leaf_item_picks`` subset at collapse time (fully-
    checked categories omit the key => transfer-all).

    Hierarchy: sub-types (SubPossibilitiesOS children) appear as nested tree children
    under their parent item.

    Types already present in the target are shown as IN TARGET (a cross-referencing
    display device per spec 021 FR-009). This is display only — all rows stay
    preselected and transferable; under constitution v7.0.0 there is no GOLD-based
    skip, and a present item merges/updates non-destructively at Move time.

    Deliberately renders NO ADD_NEW/MERGE/OVERWRITE conflict-mode control
    (FR-012 / SC-008); Layer-1 default conflict modes are applied automatically when
    the Preview page builds the Selection.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Unnumbered: this run assigns the number on entry, because a
        # position is a fact about the run and not about the page
        # (SelectionWizard._apply_step_number). The literal that used to
        # be here stated a total across a flow that could skip pages.
        self.setTitle("Lexical-Entry Types")
        self.setSubTitle(
            "Every variant type and complex form type in the source is "
            "preselected. Untick the block, a category, or single types to trim."
        )
        self._inventory: Optional[object] = None  # EntryTypesInventory
        self._mirroring: bool = False
        self._preview_service = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        self._whole_block = QtWidgets.QCheckBox(
            "Transfer lexical-entry types block", self
        )
        self._whole_block.setTristate(True)
        self._whole_block.clicked.connect(self._on_whole_block_clicked)
        layout.addWidget(self._whole_block)

        self._tree = QtWidgets.QTreeWidget(self)
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["Item", "Target"])
        self._tree.header().setStretchLastSection(True)
        self._tree.setAlternatingRowColors(True)
        self._pane = MergePreviewPane(self)
        splitter = _make_tree_pane_splitter(self._tree, self._pane)
        layout.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    def initializePage(self) -> None:
        """Build the inventory from the bound source+target; ALL preselected."""
        if self._tree.receivers(self._tree.itemChanged) > 0:
            self._tree.itemChanged.disconnect(self._on_item_changed)
        self._tree.clear()
        self._inventory = None

        source = self._get_source()
        if source is None:
            empty = QtWidgets.QTreeWidgetItem(
                self._tree, ["(No source project bound)", ""]
            )
            empty.setFlags(empty.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
            self._refresh_whole_block()
            return

        target = self._get_target()
        # FR-023 row 9. Unit is the list item: variant types + complex-form
        # types, both counted off their possibility lists at bind.
        try:
            with _page_progress(
                self, "entry_types", _source_counts_of(self).entry_types
            ) as prog:
                inventory = build_entry_types_inventory(
                    source, target=target, progress=prog
                )
        except Exception:  # noqa: BLE001
            _show_failure_row(self._tree, "entry_types")   # T022
            inventory = None

        if inventory is None:
            self._refresh_whole_block()
            return

        self._inventory = inventory
        attach_ws_font_delegate(
            self._tree, [0], WsFontRegistry.from_project(source)
        )
        self._populate_tree(inventory)
        _carry_full_values_in_tooltips(self._tree)   # T026 / FR-029b
        self._tree.expandAll()
        for col in range(2):
            self._tree.resizeColumnToContents(col)
        self._tree.itemChanged.connect(self._on_item_changed)
        self._refresh_whole_block()

        self._preview_service = MergePreviewService(source, target)
        self._pane.set_context(
            self._preview_service,
            WsFontRegistry.from_project(source),
            [],  # no candidates for entry types
        )
        self._pane.clear()
        if self._tree.receivers(self._tree.currentItemChanged) == 0:
            self._tree.currentItemChanged.connect(self._on_tree_selection_changed)

    def _populate_tree(self, inventory) -> None:
        """One tristate group per category (count on header); item rows checked."""
        from PyQt6 import QtGui  # noqa: F401
        for group in inventory.groups:
            header = QtWidgets.QTreeWidgetItem(
                self._tree, [f"{group.label} ({group.count})", ""]
            )
            header.setData(0, _ET_KIND_ROLE, "group")
            header.setData(0, _ET_CAT_ROLE, group.category)
            header.setFlags(
                header.flags()
                | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                | QtCore.Qt.ItemFlag.ItemIsAutoTristate
            )
            header.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
            bold = header.font(0)
            bold.setBold(True)
            header.setFont(0, bold)

            if not group.rows:
                none_item = QtWidgets.QTreeWidgetItem(header, ["(none)", ""])
                none_item.setFlags(
                    none_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled
                )
                continue

            # Build tree hierarchy: maintain a stack of (depth, tree_item).
            # Rows are in depth-first order from _walk_entry_type_nodes so a
            # depth increase always means the row is a child of the preceding.
            parent_stack = [(- 1, header)]  # sentinel (-1 depth, group header)
            for row in group.rows:
                # Find the appropriate parent: the nearest ancestor whose depth < row.depth
                while len(parent_stack) > 1 and parent_stack[-1][0] >= row.depth:
                    parent_stack.pop()
                tree_parent = parent_stack[-1][1]

                item = QtWidgets.QTreeWidgetItem(
                    tree_parent,
                    [row.label, _STATUS_LABELS.get(row.status or "", "")]
                )
                set_ws_runs(item, 0, row.runs)
                item.setData(0, _ET_GUID_ROLE, row.guid)
                item.setData(0, _ET_KIND_ROLE, "item")
                item.setData(0, _ET_CAT_ROLE, row.category)
                item.setData(0, _ET_STATUS_ROLE, row.status or "")
                item.setFlags(
                    item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                )
                cs = (QtCore.Qt.CheckState.Checked if row.preselected
                      else QtCore.Qt.CheckState.Unchecked)
                item.setCheckState(0, cs)
                parent_stack.append((row.depth, item))

    def _on_tree_selection_changed(self, current, previous) -> None:
        """Build PreviewRequest from selected entry-type row (display-only)."""
        if current is None:
            self._pane.clear()
            return
        kind = current.data(0, _ET_KIND_ROLE)
        if kind == "group":
            self._pane.clear()
            return

        source_guid = current.data(0, _ET_GUID_ROLE) or ""
        category = current.data(0, _ET_CAT_ROLE)
        status = current.data(0, _ET_STATUS_ROLE) or ""

        if status == "in_target":
            target_guid = source_guid
            mode = _ET_MODE_OVERWRITE
        else:
            target_guid = ""
            mode = _ET_MODE_NEW

        cat_str = (category.value if category is not None
                   else GrammarCategory.VARIANT_TYPES.value)
        request = PreviewRequest(
            category=cat_str,
            source_guid=source_guid,
            target_guid=target_guid,
            status=status,
            mode=mode,
            resolvable=False,
            current_resolution=None,
            owner_guid="",
        )
        self._pane.show_item(request)

    # -- whole-block toggle (mirrors _PagePhonology) ------------------
    def _on_whole_block_clicked(self, _checked: bool = False) -> None:
        if not self._has_any_item():
            self._refresh_whole_block()
            return
        want_checked = not self._all_items_checked()
        self._set_all_items(want_checked)
        self._refresh_whole_block()

    def _set_all_items(self, checked: bool) -> None:
        state = (QtCore.Qt.CheckState.Checked if checked
                 else QtCore.Qt.CheckState.Unchecked)
        self._mirroring = True
        try:
            for _g, item in self._iter_item_rows():
                item.setCheckState(0, state)
        finally:
            self._mirroring = False

    def _refresh_whole_block(self) -> None:
        """Reflect the aggregate item state on the whole-block tristate box.

        Empty block (no items) => unchecked + disabled (NOT vacuously checked).
        """
        self._mirroring = True
        try:
            if not self._has_any_item():
                self._whole_block.setEnabled(False)
                self._whole_block.setCheckState(QtCore.Qt.CheckState.Unchecked)
                return
            self._whole_block.setEnabled(True)
            checked = sum(
                1 for _g, it in self._iter_item_rows()
                if it.checkState(0) == QtCore.Qt.CheckState.Checked
            )
            total = sum(1 for _ in self._iter_item_rows())
            if checked == 0:
                self._whole_block.setCheckState(QtCore.Qt.CheckState.Unchecked)
            elif checked == total:
                self._whole_block.setCheckState(QtCore.Qt.CheckState.Checked)
            else:
                self._whole_block.setCheckState(
                    QtCore.Qt.CheckState.PartiallyChecked
                )
        finally:
            self._mirroring = False

    def _on_item_changed(self, item, column) -> None:
        if self._mirroring or column != 0:
            return
        self._refresh_whole_block()

    # -- tree walking helpers ------------------------------------------
    def _iter_item_rows(self):
        """Yield (group_item, item) for every checkable entry-type item row.

        Walks the full tree depth (groups -> items -> sub-items) so that
        nested child types are included in the whole-block count.
        """
        root = self._tree.invisibleRootItem()

        def _walk(parent, in_group_item):
            for i in range(parent.childCount()):
                child = parent.child(i)
                kind = child.data(0, _ET_KIND_ROLE)
                if kind == "group":
                    # Recurse into group header's children
                    _walk(child, False)
                elif kind == "item":
                    if in_group_item or True:  # always yield items
                        yield (parent, child)
                    # Also walk children of this item (sub-types)
                    for j in range(child.childCount()):
                        grandchild = child.child(j)
                        if grandchild.data(0, _ET_KIND_ROLE) == "item":
                            yield (child, grandchild)

        for i in range(root.childCount()):
            group = root.child(i)
            if group.data(0, _ET_KIND_ROLE) != "group":
                continue
            for pair in _walk(group, False):
                yield pair

    def _has_any_item(self) -> bool:
        for _ in self._iter_item_rows():
            return True
        return False

    def _all_items_checked(self) -> bool:
        any_item = False
        for _g, item in self._iter_item_rows():
            any_item = True
            if item.checkState(0) != QtCore.Qt.CheckState.Checked:
                return False
        return any_item

    # -- state API -----------------------------------------------------
    def collect_entry_type_picks(self) -> dict:
        """Return {GrammarCategory: set[str checked guids]} for both categories."""
        picks: dict = {}
        for _g, item in self._iter_item_rows():
            if item.checkState(0) != QtCore.Qt.CheckState.Checked:
                continue
            cat = item.data(0, _ET_CAT_ROLE)
            guid = item.data(0, _ET_GUID_ROLE)
            if cat is None or not guid:
                continue
            picks.setdefault(cat, set()).add(guid)
        return picks

    def whole_block_on(self) -> bool:
        """True iff any category has >= 1 checked row."""
        for _g, item in self._iter_item_rows():
            if item.checkState(0) == QtCore.Qt.CheckState.Checked:
                return True
        return False

    def deselected_needed_guids(self) -> frozenset:
        """Preselected-but-unchecked guids (input to missing-ref warning)."""
        out = set()
        for _g, item in self._iter_item_rows():
            if item.checkState(0) != QtCore.Qt.CheckState.Checked:
                guid = item.data(0, _ET_GUID_ROLE)
                if guid:
                    out.add(guid)
        return frozenset(out)

    def inventory(self):
        return self._inventory

    # -- source/target accessors (mirror _PagePhonology pattern) ------
    def _get_source(self):
        wizard = self.wizard()
        if wizard is None:
            return None
        return getattr(wizard, "_host", None)

    def _get_target(self):
        wizard = self.wizard()
        if wizard is None:
            return None
        page0 = wizard.page_project_ws() if hasattr(wizard, "page_project_ws") else None
        if page0 is None:
            return None
        ctx = page0.context() if hasattr(page0, "context") else None
        if ctx is None:
            return None
        return getattr(ctx, "target_handle", None)
