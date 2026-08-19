"""The two Model-A item-picker pages: affixes and stems (feature 039, T014).

Why this module exists
----------------------
`specs/wizard-selection-roadmap.md` distinguishes two selection models, and
these two pages are the item-derived one (Model A): the operator picks
individual entries out of a POS-grouped tree, and what those picks imply is
computed downstream rather than chosen here. They share the grouped-tree
mechanics -- `_make_group_item`, the affix item-data roles, the
tree-beside-preview splitter -- which is what makes them one module rather than
two.

They are also the source of truth the derived pages read: `_PageSkeleton` and
`_PageGramDeps` both resolve their contents from `leaf_item_picks()` here, via
`wizard.page_item_picker()` / `wizard.page_stem_picker()`. That direction is
one-way, so `wizard_pages_skeleton` never appears in this module's imports.

What is deliberately absent
---------------------------
* Anything derived from the picks. The skeleton and grammatical-dependency
  consequences of an affix pick are their own pages, precisely so that going
  back and changing a pick re-derives them instead of leaving them stale.
"""
from __future__ import annotations

import dataclasses
from typing import Optional

from PyQt6 import QtCore, QtWidgets

if __package__:
    from ..merge_preview import NEW, OVERWRITE, MergePreviewService
    from ..models import GrammarCategory, Selection, SimilarResolution
    from ..selection import (
        PickerState,
        PosGroupedAffixInventory,
        SourceAffixInventory,
        affix_label_runs,
        build_pos_grouped_inventory,
        build_selection,
        collapse_pos_grouped,
        mirror_check_state,
    )
    from ..ws_fonts import WsFontRegistry, WsRole
    from .merge_preview_pane import MergePreviewPane, PreviewRequest, _action_to_mode
    from .wizard_page_base import _FlowPage
    from .wizard_roles import (
        _GUID_ROLE,
        _IS_PRODUCES,
        _ITEM_CAT_ROLE,
        _ITEM_STATUS_ROLE,
        _KIND_ROLE,
        _ROLE_ROLE,
    )
    from .wizard_widgets import (
        _carry_full_values_in_tooltips,
        _count_affixes_in_node,
        _make_group_item,
        _make_tree_pane_splitter,
        _page_progress,
        _show_failure_row,
        _source_counts_of,
    )
    from .ws_font_delegate import attach_ws_font_delegate, set_ws_runs
else:
    from merge_preview import NEW, OVERWRITE, MergePreviewService  # type: ignore
    from merge_preview_pane import (  # type: ignore
        MergePreviewPane,
        PreviewRequest,
        _action_to_mode,
    )
    from models import GrammarCategory, Selection, SimilarResolution  # type: ignore
    from selection import (  # type: ignore
        PickerState,
        PosGroupedAffixInventory,
        SourceAffixInventory,
        affix_label_runs,
        build_pos_grouped_inventory,
        build_selection,
        collapse_pos_grouped,
        mirror_check_state,
    )
    from wizard_page_base import _FlowPage  # type: ignore
    from wizard_roles import (  # type: ignore
        _GUID_ROLE,
        _IS_PRODUCES,
        _ITEM_CAT_ROLE,
        _ITEM_STATUS_ROLE,
        _KIND_ROLE,
        _ROLE_ROLE,
    )
    from wizard_widgets import (  # type: ignore
        _carry_full_values_in_tooltips,
        _count_affixes_in_node,
        _make_group_item,
        _make_tree_pane_splitter,
        _page_progress,
        _show_failure_row,
        _source_counts_of,
    )
    from ws_font_delegate import attach_ws_font_delegate, set_ws_runs  # type: ignore
    from ws_fonts import WsFontRegistry, WsRole  # type: ignore


# ---------------------------------------------------------------------------
# Page 2 -- Item picker (POS-grouped, specs/008-affix-pos-picker)
# ---------------------------------------------------------------------------


class _PageItemPicker(_FlowPage):
    """Page 2: POS-grouped affix item picker.

    Tree layout (5 columns):
        Col 0: Affix form -> glosses  |  Col 1: Type  |  Col 2: From  |
        Col 3: To  |  Col 4: Target

    POS hierarchy:
        [POS node]
          [Inflectional]   <- swept by POS header-check
            affix rows...
          [Derivation - attaches to]  <- swept by POS header-check
            affix rows...
          [Derivation - produces]  <- NOT swept by POS header-check
            affix rows...
        [Unattached affixes]
          [No part of speech]
            affix rows...
          [No sense / no analysis]
            affix rows...

    Stems live on their own full wizard page (``_PageStemPicker``) that
    immediately follows this one; this page is affix-only.

    Group-check semantics:
        Checking a POS node sweeps Inflectional + Derivation-attaches subgroups
        and descendant POS nodes, but NOT the Derivation-produces subgroup.
        This is achieved by marking produces rows with _IS_PRODUCES=True so that
        the Qt auto-tristate propagation covers the entire subtree; the header
        check logic in collect_selection filters them out by role.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Unnumbered: this run assigns the number on entry, because a
        # position is a fact about the run and not about the page
        # (SelectionWizard._apply_step_number). The literal that used to
        # be here stated a total across a flow that could skip pages.
        self.setTitle("Affix Picker")
        self.setSubTitle(
            "Select the affixes to transfer, grouped by the part of speech they attach to. "
            "Stems are picked on the next page."
        )
        self._inventory: Optional[PosGroupedAffixInventory] = None
        # Map from entry_guid -> list of QTreeWidgetItem (for mirroring)
        self._guid_to_items: dict = {}
        # Re-entrancy guard for itemChanged mirroring
        self._mirroring: bool = False
        # T009/T010: per-page resolution store (FR-008, R3)
        self._resolution_store: dict = {}
        self._preview_service = None
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        # FR-017(a): instruction label making clear the pick unit is affixes
        layout.addWidget(QtWidgets.QLabel(
            "Select the affixes to transfer. "
            "Parts of speech below are groupings only -- "
            "checking one selects the affixes under it.",
            self,
        ))
        self._tree = QtWidgets.QTreeWidget(self)
        # FR-017(d): 5 columns; col 4 = Target presence
        self._tree.setColumnCount(5)
        self._tree.setHeaderLabels(["Affix / Group", "Type", "From", "To", "Target"])
        self._tree.header().setStretchLastSection(False)
        self._tree.setAlternatingRowColors(True)
        # T009: merge-preview pane docked to the right via a horizontal splitter (FR-005)
        self._pane = MergePreviewPane(self)
        splitter = _make_tree_pane_splitter(self._tree, self._pane)
        layout.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    def initializePage(self) -> None:
        """Called when the wizard enters page 2.

        Builds the inventory from the bound source project and populates
        the tree. This is the missing feed that caused the empty picker.
        Guards for no-source (renders empty labeled tree, no crash).
        """
        self._tree.itemChanged.disconnect() if self._tree.receivers(
            self._tree.itemChanged
        ) > 0 else None

        source = self._get_source()
        if source is None:
            # No source bound yet -- show empty labeled tree, no crash
            self._inventory = None
            self._guid_to_items = {}
            self._tree.clear()
            empty_item = QtWidgets.QTreeWidgetItem(
                self._tree, ["(No source project bound)"]
            )
            empty_item.setFlags(empty_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
            return

        # FR-018(e): obtain target handle from page-0 context; guard for no-target
        target = self._get_target()

        # FR-023 row 5. The total is the whole-lexicon entry count taken at bind:
        # this walk visits every entry to decide which are affixes, so the
        # lexicon size is the number of units it will actually cover.
        try:
            with _page_progress(
                self, "affixes", _source_counts_of(self).lexicon_entries
            ) as prog:
                inventory = build_pos_grouped_inventory(
                    source, target=target, progress=prog
                )
        except Exception:  # noqa: BLE001
            # T022: the indicator is already down (`reporting`'s finally); this
            # is the half that says so on the page.
            _show_failure_row(self._tree, "affixes")
            inventory = None  # type: ignore[assignment]

        if inventory is None:
            self._inventory = None
            self._guid_to_items = {}
            return

        self._inventory = inventory
        self._guid_to_items = {}
        # spec 011: vernacular lexeme forms (col 0) + analysis glosses/POS
        # (cols 0/2/3) each in their FLEx-defined WS font.
        attach_ws_font_delegate(
            self._tree, [0, 2, 3], WsFontRegistry.from_project(source)
        )
        self.populate_pos_tree(inventory)
        _carry_full_values_in_tooltips(self._tree)   # T026 / FR-029b
        self._tree.itemChanged.connect(self._on_item_changed)

        # T009/T010: resolution store seeding (FR-008, R3)
        self._resolution_store = {}
        for entry_guid, suggested_target_guid in self._similar_affix_pairs():
            self._resolution_store[entry_guid] = SimilarResolution(
                entry_guid=entry_guid,
                action="overwrite",
                target_guid=suggested_target_guid,
            )
        # Reflect default seed in Target column
        for entry_guid, resolution in self._resolution_store.items():
            self._update_target_column(entry_guid, resolution)

        # T009: construct service and set pane context (FR-006)
        self._preview_service = MergePreviewService(source, target)
        candidates = self._candidate_list()
        self._pane.set_context(
            self._preview_service,
            WsFontRegistry.from_project(source),
            candidates,
        )
        self._pane.clear()
        # Connect tree selection handler (with double-connect guard)
        if self._tree.receivers(self._tree.currentItemChanged) == 0:
            self._tree.currentItemChanged.connect(self._on_tree_selection_changed)
        # Connect pane resolution_changed signal (T009)
        self._pane.resolution_changed.connect(self._on_resolution_changed)

    # T009/T010: helper methods
    def _candidate_list(self):
        """Return list of (guid, form, gloss) for SIMILAR affix candidates."""
        # All SIMILAR rows' suggested targets become candidates for the combo
        candidates = []
        seen = set()
        root = self._tree.invisibleRootItem()

        def _walk(node):
            for i in range(node.childCount()):
                child = node.child(i)
                status = child.data(0, _ITEM_STATUS_ROLE)
                if status == "similar":
                    # The suggested target guid is in the resolution store
                    # (seeded from inventory row). Gather from inventory.
                    pass
                _walk(child)

        # Build candidates from inventory rows that have similar matches
        if self._inventory is not None:
            def _collect_similar_rows(node):
                for row in node.inflectional + node.deriv_attaches + node.deriv_produces:
                    if getattr(row, "status", None) == "similar":
                        tg = getattr(row, "suggested_target_guid", None) or ""
                        if tg and tg not in seen:
                            seen.add(tg)
                            form = getattr(row, "target_form", "") or tg[:8]
                            gloss = getattr(row, "target_gloss", "") or ""
                            candidates.append((tg, form, gloss))
                for child in node.children:
                    _collect_similar_rows(child)

            for root_node in self._inventory.roots:
                _collect_similar_rows(root_node)
        return candidates

    def _similar_affix_pairs(self):
        """Return list of (source_guid, suggested_target_guid) for SIMILAR affix rows."""
        pairs = []
        root = self._tree.invisibleRootItem()

        def _walk(node):
            for i in range(node.childCount()):
                child = node.child(i)
                status = child.data(0, _ITEM_STATUS_ROLE)
                if status == "similar":
                    source_guid = child.data(0, _GUID_ROLE)
                    # Look up suggested target from inventory row
                    # The row.suggested_target_guid is set by build_pos_grouped_inventory
                    suggested_tg = self._find_suggested_target(source_guid)
                    if source_guid and suggested_tg:
                        pairs.append((source_guid, suggested_tg))
                _walk(child)

        _walk(self._tree.invisibleRootItem())
        return pairs

    def _find_suggested_target(self, entry_guid: str) -> str:
        """Look up the suggested target GUID for a SIMILAR affix from the inventory."""
        if self._inventory is None:
            return ""

        def _search_rows(rows):
            for row in rows:
                if row.entry_guid == entry_guid:
                    return getattr(row, "suggested_target_guid", "") or ""
            return ""

        def _search_node(node):
            result = _search_rows(node.inflectional)
            if result:
                return result
            result = _search_rows(node.deriv_attaches)
            if result:
                return result
            result = _search_rows(node.deriv_produces)
            if result:
                return result
            for child in node.children:
                result = _search_node(child)
                if result:
                    return result
            return ""

        for root_node in self._inventory.roots:
            result = _search_node(root_node)
            if result:
                return result
        # Also check junk
        if self._inventory.junk:
            for row in (list(getattr(self._inventory.junk, "no_pos", []))
                        + list(getattr(self._inventory.junk, "no_analysis", []))):
                if row.entry_guid == entry_guid:
                    return getattr(row, "suggested_target_guid", "") or ""
        return ""

    def _on_tree_selection_changed(self, current, previous) -> None:
        """T009: build PreviewRequest from selected row and call pane.show_item."""
        pane = self._pane
        if current is None:
            pane.clear()
            return
        kind = current.data(0, _KIND_ROLE)
        if kind != "affix":
            # Group or subgroup header -> clear pane
            pane.clear()
            return

        source_guid = current.data(0, _GUID_ROLE) or ""
        category = current.data(0, _ITEM_CAT_ROLE)
        status = current.data(0, _ITEM_STATUS_ROLE) or ""

        # Derive target_guid and mode per status (R1)
        if status == "new":
            target_guid = ""
            mode = NEW
        elif status == "in_target":
            target_guid = source_guid
            mode = OVERWRITE
        elif status == "similar":
            resolution = self._resolution_store.get(source_guid)
            if resolution is not None:
                target_guid = resolution.target_guid or ""
                mode = _action_to_mode(resolution.action)
            else:
                target_guid = ""
                mode = NEW
        else:
            pane.clear()
            return

        # resolvable only for affix SIMILAR rows (R5); the resolution store
        # and candidate combo are affix-scoped, so stems are never resolvable.
        resolvable = status == "similar" and kind == "affix"

        current_resolution = self._resolution_store.get(source_guid)
        cat_str = category.value if category is not None else GrammarCategory.AFFIXES.value

        request = PreviewRequest(
            category=cat_str,
            source_guid=source_guid,
            target_guid=target_guid,
            status=status,
            mode=mode,
            resolvable=resolvable,
            current_resolution=current_resolution,
            owner_guid="",
        )
        pane.show_item(request)

    def _on_resolution_changed(self, entry_guid: str, resolution) -> None:
        """T010: update the resolution store and reflect in Target column."""
        self._resolution_store[entry_guid] = resolution
        self._update_target_column(entry_guid, resolution)

    def _update_target_column(self, entry_guid: str, resolution) -> None:
        """T010: set Target column text for the given entry_guid's tree items."""
        _ACTION_LABELS = {
            "overwrite": "SIMILAR -> overwrite",
            "merge": "SIMILAR -> merge",
            "create_new": "SIMILAR -> new",
        }
        label = _ACTION_LABELS.get(getattr(resolution, "action", ""), "")
        for item in self._guid_to_items.get(entry_guid, []):
            item.setText(4, label)

    def _get_source(self):
        """Return the source project handle from page 0, or None."""
        try:
            wizard = self.wizard()
            if wizard is None:
                return None
            page0 = wizard.page_project_ws()
            if page0 is None:
                return None
            # Try context().source_handle first, then _host directly
            ctx = page0.context()
            if ctx is not None:
                h = getattr(ctx, "source_handle", None)
                if h is not None:
                    return h
            host = getattr(page0, "_host", None)
            return host
        except Exception:  # noqa: BLE001
            return None

    def _get_target(self):
        """Return the target project handle from page-0 context, or None.

        FR-018(e): the RunContext (set when user picks a target on page 1)
        exposes .target_handle.  If no context or no target yet, returns None
        so the builder is called with target=None (Target column blank, no crash).
        """
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

    # ------------------------------------------------------------------
    def populate_pos_tree(self, inventory: PosGroupedAffixInventory) -> None:
        """Populate the 4-column POS-hierarchy tree from inventory.

        Called by initializePage; may also be called directly in tests.
        """
        self._tree.clear()
        self._guid_to_items = {}

        # --- POS hierarchy nodes ---
        for pos_node in inventory.roots:
            self._add_pos_node(self._tree.invisibleRootItem(), pos_node)

        # --- Unattached drawer ---
        has_junk = bool(inventory.junk.no_pos or inventory.junk.no_analysis)
        if has_junk:
            drawer = _make_group_item(
                self._tree, "Unattached affixes",
                kind="pos_group", checkable=True, is_produces_group=False,
            )
            if inventory.junk.no_pos:
                sg = _make_group_item(
                    drawer, "No part of speech",
                    kind="subgroup", checkable=True, is_produces_group=False,
                )
                for row in inventory.junk.no_pos:
                    self._add_affix_row(sg, row)
            if inventory.junk.no_analysis:
                sg2 = _make_group_item(
                    drawer, "No sense / no analysis",
                    kind="subgroup", checkable=True, is_produces_group=False,
                )
                for row in inventory.junk.no_analysis:
                    self._add_affix_row(sg2, row)

        self._tree.expandAll()
        # Resize columns to content after population (5 columns now)
        for col in range(5):
            self._tree.resizeColumnToContents(col)

    def _add_pos_node(self, parent, pos_node) -> None:
        """Recursively add a PosNode and its subgroups/children to the tree."""
        # FR-017(b): annotate POS group label with distinct affix count
        affix_count = _count_affixes_in_node(pos_node)
        affix_word = "affix" if affix_count == 1 else "affixes"
        pos_label = f"{pos_node.label} -- {affix_count} {affix_word}"
        pos_item = _make_group_item(
            parent, pos_label,
            kind="pos_group", checkable=True, is_produces_group=False,
        )
        pos_item.setData(0, _GUID_ROLE, pos_node.pos_guid)
        # spec 011: POS name in the analysis WS font; affix-count suffix is chrome.
        set_ws_runs(pos_item, 0, (
            (pos_node.label, WsRole.ANALYSIS),
            (f" -- {affix_count} {affix_word}", None),
        ))

        # Inflectional subgroup
        if pos_node.inflectional:
            sg_infl = _make_group_item(
                pos_item, "Inflectional",
                kind="subgroup", checkable=True, is_produces_group=False,
            )
            for row in pos_node.inflectional:
                self._add_affix_row(sg_infl, row)

        # Derivation - attaches to subgroup
        if pos_node.deriv_attaches:
            sg_att = _make_group_item(
                pos_item, "Derivation - attaches to",
                kind="subgroup", checkable=True, is_produces_group=False,
            )
            for row in pos_node.deriv_attaches:
                self._add_affix_row(sg_att, row)

        # Derivation - produces subgroup (NOT swept by header check)
        if pos_node.deriv_produces:
            sg_prod = _make_group_item(
                pos_item, "Derivation - produces",
                kind="subgroup", checkable=True, is_produces_group=True,
            )
            for row in pos_node.deriv_produces:
                self._add_affix_row(sg_prod, row)

        # Descendant POS nodes
        for child in pos_node.children:
            self._add_pos_node(pos_item, child)

    def _add_affix_row(self, parent: QtWidgets.QTreeWidgetItem,
                       row) -> None:
        """Add a leaf AffixRow item to the tree under parent."""
        # spec 011: form is vernacular, gloss is analysis -- split into WS runs.
        label_runs = affix_label_runs(row.form, row.glosses)
        label = "".join(text for text, _ in label_runs)
        type_label = {"infl": "Infl", "deriv": "Deriv", "uncl": "Uncl"}.get(
            row.msa_kind, row.msa_kind
        )
        from_label = row.from_pos if row.from_pos else ("—" if row.role == "produces" else "")
        to_label = row.to_pos if row.to_pos else ("—" if row.msa_kind == "deriv" else "")
        # FR-017(d): Target column -- "NEW" / "IN TARGET" / "SIMILAR" / ""
        _status_labels = {
            "new": "NEW",
            "in_target": "IN TARGET",
            "similar": "SIMILAR",
        }
        target_label = _status_labels.get(row.status or "", "")

        item = QtWidgets.QTreeWidgetItem(
            parent, [label, type_label, from_label, to_label, target_label]
        )
        # spec 011: per-WS fonts -- form+gloss on col 0, POS names on cols 2/3.
        set_ws_runs(item, 0, label_runs)
        if from_label and from_label != "—":
            set_ws_runs(item, 2, ((from_label, WsRole.ANALYSIS),))
        if to_label and to_label != "—":
            set_ws_runs(item, 3, ((to_label, WsRole.ANALYSIS),))
        item.setData(0, _GUID_ROLE, row.entry_guid)
        item.setData(0, _KIND_ROLE, "affix")
        item.setData(0, _ROLE_ROLE, row.role)
        item.setData(0, _IS_PRODUCES, row.role == "produces")
        # T005: data roles for pane PreviewRequest construction (FR-010, R6)
        item.setData(0, _ITEM_STATUS_ROLE, row.status or "")
        item.setData(0, _ITEM_CAT_ROLE, GrammarCategory.AFFIXES)
        item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        # FR-001 (T009): affixes open fully preselected; deselection is the
        # primary user action (opens checked, not unchecked).
        item.setCheckState(0, QtCore.Qt.CheckState.Checked)

        # Register for GUID mirroring
        guid = row.entry_guid
        if guid not in self._guid_to_items:
            self._guid_to_items[guid] = []
        self._guid_to_items[guid].append(item)

    # ------------------------------------------------------------------
    def _on_item_changed(self, item: QtWidgets.QTreeWidgetItem, column: int) -> None:
        """Mirror check state to all other appearances of the same entry GUID."""
        if self._mirroring:
            return
        if column != 0:
            return
        guid = item.data(0, _GUID_ROLE)
        kind = item.data(0, _KIND_ROLE)
        if kind != "affix" or guid is None:
            return
        new_state = item.checkState(0)
        siblings = self._guid_to_items.get(guid, [])
        if len(siblings) <= 1:
            return
        assignments = mirror_check_state(siblings, new_state)
        self._mirroring = True
        try:
            for sibling, state in assignments:
                if sibling is not item:
                    sibling.setCheckState(0, state)
        finally:
            self._mirroring = False

    # ------------------------------------------------------------------
    def picker_state(self) -> PickerState:
        """Collect checked leaf entry_guids from the tree."""
        checked: set = set()
        self._collect_checked(self._tree.invisibleRootItem(), checked)
        return PickerState(checked_affixes=frozenset(checked))

    def _collect_checked(self, node: QtWidgets.QTreeWidgetItem, out: set) -> None:
        """Recursively collect checked affix entry_guids.

        Produces-role rows (_IS_PRODUCES=True) are excluded from header-driven
        collection (FR-008): a POS-header check must not pull produces-only GUIDs
        into affix_picks.  Only attaches-role leaf rows contribute.
        """
        for i in range(node.childCount()):
            child = node.child(i)
            kind = child.data(0, _KIND_ROLE)
            if kind == "affix":
                # Skip produces-role rows; they MUST NOT be swept by header check
                is_produces = child.data(0, _IS_PRODUCES)
                if is_produces:
                    continue
                if child.checkState(0) == QtCore.Qt.CheckState.Checked:
                    guid = child.data(0, _GUID_ROLE)
                    if guid:
                        out.add(guid)
            else:
                self._collect_checked(child, out)

    def collect_selection(self) -> Selection:
        """Build a Selection from the current picker state (T011, FR-009).

        Affix-only: stems are collected on the separate ``_PageStemPicker``
        page and folded into the final plan by ``_compute_wizard_plan``.
        Folds the page's resolution store into the returned Selection via
        dataclasses.replace.  Returns a shallow copy of the store so callers
        cannot mutate the live store.
        """
        if self._inventory is None:
            dummy = SourceAffixInventory()
            base = build_selection(PickerState(), dummy)
            # Empty similar_resolutions (dataclass default) on fallback path
            return base
        ps = self.picker_state()
        base = collapse_pos_grouped(ps.checked_affixes, self._inventory)
        return dataclasses.replace(
            base,
            similar_resolutions=dict(self._resolution_store),
        )


# ---------------------------------------------------------------------------
# Stem picker -- own full page, immediately after the Affix picker (019)
# ---------------------------------------------------------------------------

class _PageStemPicker(_FlowPage):
    """Full page: POS-grouped stem item picker.

    Mirrors ``_PageItemPicker`` but for stems.  Stems used to share the affix
    page as a second tab; they now occupy their own wizard step that follows
    the Affix picker.  Rows carry ``GrammarCategory.STEMS``, open preselected
    (checked), and expose the checked set via :meth:`stem_picks`.

    Stems are never SIMILAR-resolvable (R5: resolution is affix-only), so this
    page has no resolution store and the docked preview pane carries no
    candidate combo.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Unnumbered: this run assigns the number on entry, because a
        # position is a fact about the run and not about the page
        # (SelectionWizard._apply_step_number). The literal that used to
        # be here stated a total across a flow that could skip pages.
        self.setTitle("Stem Picker")
        self.setSubTitle(
            "Select the stem entries to transfer, grouped by the part of speech "
            "they belong to. Checking a part of speech selects the stems under it."
        )
        self._stem_inventory: Optional[PosGroupedAffixInventory] = None
        self._stem_guid_to_items: dict = {}
        self._preview_service = None
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(
            "Select the stem entries to transfer, grouped by part of speech. "
            "Checking a part of speech selects the stems under it.",
            self,
        ))
        self._stem_tree = QtWidgets.QTreeWidget(self)
        self._stem_tree.setColumnCount(5)
        self._stem_tree.setHeaderLabels(
            ["Stem / Group", "Type", "From", "To", "Target"]
        )
        self._stem_tree.header().setStretchLastSection(False)
        self._stem_tree.setAlternatingRowColors(True)
        self._stem_pane = MergePreviewPane(self)
        splitter = _make_tree_pane_splitter(self._stem_tree, self._stem_pane)
        layout.addWidget(splitter, 1)

    # -- source/target handles (per-page copy, matching the wizard convention) --
    def _get_source(self):
        """Return the source project handle from page 0, or None."""
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
        """Return the target project handle from page-0 context, or None."""
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

    # ------------------------------------------------------------------
    def initializePage(self) -> None:
        """Build the stem inventory from the bound source + populate the tree.

        Guards for no-source (renders an empty labeled tree, no crash).
        """
        source = self._get_source()
        if source is None:
            self._stem_inventory = None
            self._stem_guid_to_items = {}
            self._stem_tree.clear()
            empty_item = QtWidgets.QTreeWidgetItem(
                self._stem_tree, ["(No source project bound)"]
            )
            empty_item.setFlags(empty_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
            return

        target = self._get_target()
        # FR-023 row 6. Same walk as the affix page over the same lexicon, with
        # the other half of the affix/stem split kept -- so the same total.
        try:
            with _page_progress(
                self, "stems", _source_counts_of(self).lexicon_entries
            ) as prog:
                stem_inventory = build_pos_grouped_inventory(
                    source, target=target, want_affix=False, progress=prog
                )
        except Exception:  # noqa: BLE001
            _show_failure_row(self._stem_tree, "stems")   # T022
            stem_inventory = None  # type: ignore[assignment]

        self._stem_inventory = stem_inventory
        self._stem_guid_to_items = {}
        registry = WsFontRegistry.from_project(source)
        attach_ws_font_delegate(self._stem_tree, [0, 2, 3], registry)
        if stem_inventory is not None:
            self.populate_stem_tree(stem_inventory)
            _carry_full_values_in_tooltips(self._stem_tree)   # T026 / FR-029b
        # Own preview service; stems carry no SIMILAR resolution combo (R5),
        # so the candidate list stays empty.  set_context() also clears.
        self._preview_service = MergePreviewService(source, target)
        self._stem_pane.set_context(self._preview_service, registry, [])
        self._stem_pane.clear()
        if self._stem_tree.receivers(self._stem_tree.currentItemChanged) == 0:
            self._stem_tree.currentItemChanged.connect(self._on_tree_selection_changed)

    # ------------------------------------------------------------------
    # Population (mirrors _PageItemPicker.populate_pos_tree for stems)
    # ------------------------------------------------------------------
    def populate_stem_tree(self, inventory: PosGroupedAffixInventory) -> None:
        """Populate the POS-grouped Stems tree from the stem inventory.

        Rows carry ``GrammarCategory.STEMS`` and open preselected (checked).
        Called by initializePage; may also be called directly in tests.
        """
        self._stem_tree.clear()
        self._stem_guid_to_items = {}
        for pos_node in inventory.roots:
            self._add_stem_pos_node(self._stem_tree.invisibleRootItem(), pos_node)
        has_junk = bool(inventory.junk.no_pos or inventory.junk.no_analysis)
        if has_junk:
            drawer = _make_group_item(
                self._stem_tree, "Unattached stems",
                kind="pos_group", checkable=True, is_produces_group=False,
            )
            for label, rows in (
                ("No part of speech", inventory.junk.no_pos),
                ("No sense / no analysis", inventory.junk.no_analysis),
            ):
                if rows:
                    sg = _make_group_item(
                        drawer, label,
                        kind="subgroup", checkable=True, is_produces_group=False,
                    )
                    for row in rows:
                        self._add_stem_row(sg, row)
        self._stem_tree.expandAll()
        for col in range(5):
            self._stem_tree.resizeColumnToContents(col)

    def _add_stem_pos_node(self, parent, pos_node) -> None:
        """Recursively add a stem POS group and its stem rows + child POSes."""
        stem_count = _count_affixes_in_node(pos_node)
        word = "stem" if stem_count == 1 else "stems"
        label = f"{pos_node.label} -- {stem_count} {word}"
        pos_item = _make_group_item(
            parent, label,
            kind="pos_group", checkable=True, is_produces_group=False,
        )
        pos_item.setData(0, _GUID_ROLE, pos_node.pos_guid)
        set_ws_runs(pos_item, 0, (
            (pos_node.label, WsRole.ANALYSIS),
            (f" -- {stem_count} {word}", None),
        ))
        # Stems land in the inflectional (attaches) bucket of the shared row shape.
        for row in pos_node.inflectional:
            self._add_stem_row(pos_item, row)
        for child in pos_node.children:
            self._add_stem_pos_node(pos_item, child)

    def _add_stem_row(self, parent: QtWidgets.QTreeWidgetItem, row) -> None:
        """Add a leaf stem row; renders the NEW / IN TARGET / SIMILAR column."""
        label_runs = affix_label_runs(row.form, row.glosses)
        label = "".join(text for text, _ in label_runs)
        _status_labels = {"new": "NEW", "in_target": "IN TARGET", "similar": "SIMILAR"}
        target_label = _status_labels.get(row.status or "", "")
        item = QtWidgets.QTreeWidgetItem(
            parent, [label, "Stem", "", "", target_label]
        )
        set_ws_runs(item, 0, label_runs)
        item.setData(0, _GUID_ROLE, row.entry_guid)
        item.setData(0, _KIND_ROLE, "stem")
        item.setData(0, _IS_PRODUCES, False)
        item.setData(0, _ITEM_STATUS_ROLE, row.status or "")
        item.setData(0, _ITEM_CAT_ROLE, GrammarCategory.STEMS)
        item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        # Open preselected (mirror the affix picker default; deselect is primary).
        item.setCheckState(0, QtCore.Qt.CheckState.Checked)
        self._stem_guid_to_items.setdefault(row.entry_guid, []).append(item)

    # ------------------------------------------------------------------
    # Pick collection
    # ------------------------------------------------------------------
    def _collect_checked_stems(self, node: QtWidgets.QTreeWidgetItem,
                               out: set) -> None:
        """Recursively collect checked stem entry_guids from the Stems tree."""
        for i in range(node.childCount()):
            child = node.child(i)
            if child.data(0, _KIND_ROLE) == "stem":
                if child.checkState(0) == QtCore.Qt.CheckState.Checked:
                    guid = child.data(0, _GUID_ROLE)
                    if guid:
                        out.add(guid)
            else:
                self._collect_checked_stems(child, out)

    def stem_picks(self) -> frozenset:
        """Checked stem GUIDs intersected with the known stem inventory."""
        if self._stem_inventory is None:
            return frozenset()
        checked: set = set()
        self._collect_checked_stems(self._stem_tree.invisibleRootItem(), checked)
        return frozenset(checked) & self._stem_inventory.all_affix_guids()

    # ------------------------------------------------------------------
    def _on_tree_selection_changed(self, current, previous) -> None:
        """Build a PreviewRequest from the selected stem row and show it."""
        pane = self._stem_pane
        if current is None:
            pane.clear()
            return
        if current.data(0, _KIND_ROLE) != "stem":
            pane.clear()
            return
        source_guid = current.data(0, _GUID_ROLE) or ""
        category = current.data(0, _ITEM_CAT_ROLE)
        status = current.data(0, _ITEM_STATUS_ROLE) or ""
        if status == "in_target":
            target_guid = source_guid
            mode = OVERWRITE
        else:
            # "new" (and any other status) -> create-new; stems are never SIMILAR.
            target_guid = ""
            mode = NEW
        cat_str = category.value if category is not None else GrammarCategory.STEMS.value
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
        pane.show_item(request)
