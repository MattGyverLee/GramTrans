"""The two pick-derived pages: morphology skeleton and grammar deps (feature 039, T015).

Why this module exists
----------------------
Both pages answer the same shape of question -- "given what you picked on the
affix and stem pages, what else has to come across for those picks to mean
anything in the target?" Neither enumerates the source project directly; both
derive from `leaf_item_picks()`, and both can therefore be empty for a run whose
picks imply nothing, which is why both are skippable in `flow()`.

They share `_STATUS_LABELS` and the `_SKEL_*` / `_DEPS_*` role blocks, and they
share the two pick accessors that `_PickDerivedMixin` now holds once.

What is deliberately absent
---------------------------
* `_BlockPage`. `_PageSkeleton` has an `_on_item_changed` and it uses
  `_mirroring`, so it *looks* like the four whole-block pages, but its semantics
  are template-slot mirroring, not wholesale NONE/ALL over one tree. Giving it
  the block base would be pattern-matching on method names rather than on
  behaviour.
"""
from __future__ import annotations

from typing import Optional, Set

from PyQt6 import QtCore, QtWidgets

if __package__:
    from ..merge_preview import NEW, OVERWRITE, MergePreviewService
    from ..models import GrammarCategory
    from ..selection import build_deps_inventory, build_skeleton_inventory
    from ..ws_fonts import WsFontRegistry, WsRole
    from .merge_preview_pane import MergePreviewPane, PreviewRequest
    from .wizard_page_base import _FlowPage
    from .wizard_roles import (
        _DEPS_CAT_ROLE,
        _DEPS_STATUS_ROLE,
        _SKEL_CAT_ROLE,
        _SKEL_GUID_ROLE,
        _SKEL_KIND_ROLE,
        _SKEL_OWNER_ROLE,
        _SKEL_READ_ONLY,
        _SKEL_STATUS_ROLE,
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
    from selection import build_deps_inventory, build_skeleton_inventory  # type: ignore
    from wizard_page_base import _FlowPage  # type: ignore
    from wizard_roles import (  # type: ignore
        _DEPS_CAT_ROLE,
        _DEPS_STATUS_ROLE,
        _SKEL_CAT_ROLE,
        _SKEL_GUID_ROLE,
        _SKEL_KIND_ROLE,
        _SKEL_OWNER_ROLE,
        _SKEL_READ_ONLY,
        _SKEL_STATUS_ROLE,
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
    from ws_fonts import WsFontRegistry, WsRole  # type: ignore


# ---------------------------------------------------------------------------
# Page 3b -- Morphology Skeleton  (T011-T012)
# ---------------------------------------------------------------------------

class _PageSkeleton(_FlowPage):
    """Page 3b: Morphology skeleton derived from the affix picks.

    POS-rooted tree:
        [POS node — preselected if any picked affix attaches]
          [Slots subgroup]
            [slot row — preselected if any picked affix fills it]
            ...
          [Templates subgroup]
            [template row — preselected if any referenced slot is filled]
              (slot read-only child items listing referenced slots)
            ...

    Target-status column: "NEW" / "IN TARGET" / "SIMILAR" / ""

    Template semantics (T012):
      - Checking a template selects its full referenced slot set (extra
        slots may transfer empty; FR-007).
      - Deselecting a template leaves only the affix-filled slots selected.
      - Template check/deselect NEVER re-expands affix_picks.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Unnumbered: this run assigns the number on entry, because a
        # position is a fact about the run and not about the page
        # (SelectionWizard._apply_step_number). The literal that used to
        # be here stated a total across a flow that could skip pages.
        self.setTitle("Morphology Skeleton")
        self.setSubTitle(
            "The parts of speech, slots and templates your picked affixes "
            "need, preselected. Deselect to trim; check extras to add more."
        )
        self._skeleton: Optional[object] = None  # SkeletonInventory
        self._mirroring: bool = False
        # T013: preview service (initialized in initializePage)
        self._preview_service = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(
            "Slots/templates needed by the selected affixes are pre-checked. "
            "Checking a template includes all slots it arranges (even unfilled ones). "
            "Deselecting a template retains only slots filled by picked affixes.",
            self,
        ))
        self._tree = QtWidgets.QTreeWidget(self)
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(["Slot / Template", "Affixes", "Target"])
        self._tree.header().setStretchLastSection(False)
        self._tree.setAlternatingRowColors(True)
        # T013: merge-preview pane docked to the right (FR-005)
        self._pane = MergePreviewPane(self)
        splitter = _make_tree_pane_splitter(self._tree, self._pane)
        layout.addWidget(splitter, 1)

    def initializePage(self) -> None:
        """Build skeleton from affix picks + bound target when the page is entered."""
        self._tree.itemChanged.disconnect() if self._tree.receivers(
            self._tree.itemChanged
        ) > 0 else None
        self._tree.clear()
        self._skeleton = None

        affix_picks = self._get_affix_picks()
        source = self._get_source()
        if source is None or not affix_picks:
            empty = QtWidgets.QTreeWidgetItem(
                self._tree, ["(No affixes selected or no source bound)"]
            )
            empty.setFlags(empty.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
            return

        target = self._get_target()
        # FR-023 row 7. Unit is the lexical entry again: the walk reaches MSAs
        # and slots THROUGH entries, so the entry count is what it covers, not
        # the number of affixes the operator picked.
        failed = False
        try:
            with _page_progress(
                self, "skeleton", _source_counts_of(self).lexicon_entries
            ) as prog:
                skeleton = build_skeleton_inventory(
                    source, affix_picks, target=target, progress=prog
                )
        except Exception:  # noqa: BLE001
            skeleton = None
            failed = True   # T022: distinguish "read nothing" from "read failed"

        if skeleton is None or not skeleton.pos_nodes:
            empty = QtWidgets.QTreeWidgetItem(
                self._tree,
                [_operation_failed_note("skeleton")] if failed
                else ["(No skeleton derived from current affix picks)"],
            )
            empty.setFlags(empty.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
            return

        self._skeleton = skeleton
        # spec 011: POS / slot / template names render in the analysis WS font.
        attach_ws_font_delegate(
            self._tree, [0], WsFontRegistry.from_project(source)
        )
        self._populate_skeleton_tree(skeleton)
        _carry_full_values_in_tooltips(self._tree)   # T026 / FR-029b
        self._tree.expandAll()
        for col in range(3):
            self._tree.resizeColumnToContents(col)
        self._tree.itemChanged.connect(self._on_item_changed)

        # T013: construct service and set pane context (FR-006)
        self._preview_service = MergePreviewService(source, target)
        self._pane.set_context(
            self._preview_service,
            WsFontRegistry.from_project(source),
            [],  # no candidates for skeleton
        )
        self._pane.clear()
        # Double-connect guard
        if self._tree.receivers(self._tree.currentItemChanged) == 0:
            self._tree.currentItemChanged.connect(self._on_tree_selection_changed)

    def _populate_skeleton_tree(self, skeleton) -> None:
        """Build the POS-rooted skeleton tree from a SkeletonInventory."""
        for pos_node in skeleton.pos_nodes:
            pos_item = QtWidgets.QTreeWidgetItem(
                self._tree,
                [pos_node.label, "", _STATUS_LABELS.get(pos_node.status or "", "")]
            )
            pos_item.setData(0, _SKEL_GUID_ROLE, pos_node.pos_guid)
            set_ws_runs(pos_item, 0, ((pos_node.label, WsRole.ANALYSIS),))
            pos_item.setData(0, _SKEL_KIND_ROLE, "pos")
            pos_item.setFlags(
                pos_item.flags()
                | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                | QtCore.Qt.ItemFlag.ItemIsAutoTristate
            )
            check_state = (QtCore.Qt.CheckState.Checked if pos_node.preselected
                           else QtCore.Qt.CheckState.Unchecked)
            pos_item.setCheckState(0, check_state)
            from PyQt6 import QtGui
            bold_font = pos_item.font(0)
            bold_font.setBold(True)
            pos_item.setFont(0, bold_font)

            # Slots subgroup
            if pos_node.slots:
                slots_group = QtWidgets.QTreeWidgetItem(pos_item, ["Slots", "", ""])
                slots_group.setData(0, _SKEL_KIND_ROLE, "slots_group")
                slots_group.setFlags(
                    slots_group.flags()
                    | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                    | QtCore.Qt.ItemFlag.ItemIsAutoTristate
                )
                slots_group.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
                bold_f = slots_group.font(0)
                bold_f.setBold(True)
                slots_group.setFont(0, bold_f)
                for slot_node in pos_node.slots:
                    count_label = (
                        f"{slot_node.affix_count} affix"
                        + ("es" if slot_node.affix_count != 1 else "")
                        if slot_node.affix_count > 0 else ""
                    )
                    slot_item = QtWidgets.QTreeWidgetItem(
                        slots_group,
                        [slot_node.label, count_label,
                         _STATUS_LABELS.get(slot_node.status or "", "")]
                    )
                    slot_item.setData(0, _SKEL_GUID_ROLE, slot_node.slot_guid)
                    set_ws_runs(slot_item, 0, ((slot_node.label, WsRole.ANALYSIS),))
                    slot_item.setData(0, _SKEL_KIND_ROLE, "slot")
                    slot_item.setFlags(
                        slot_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                    )
                    slot_cs = (QtCore.Qt.CheckState.Checked if slot_node.preselected
                               else QtCore.Qt.CheckState.Unchecked)
                    slot_item.setCheckState(0, slot_cs)
                    # T006: data roles for pane PreviewRequest (FR-010, R6)
                    slot_item.setData(0, _SKEL_STATUS_ROLE, slot_node.status or "")
                    slot_item.setData(0, _SKEL_CAT_ROLE, GrammarCategory.SLOTS)
                    slot_item.setData(0, _SKEL_OWNER_ROLE, pos_node.pos_guid)

            # Templates subgroup
            if pos_node.templates:
                tpl_group = QtWidgets.QTreeWidgetItem(pos_item, ["Templates", "", ""])
                tpl_group.setData(0, _SKEL_KIND_ROLE, "templates_group")
                tpl_group.setFlags(
                    tpl_group.flags()
                    | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                    | QtCore.Qt.ItemFlag.ItemIsAutoTristate
                )
                tpl_group.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
                bold_tf = tpl_group.font(0)
                bold_tf.setBold(True)
                tpl_group.setFont(0, bold_tf)
                for tpl_node in pos_node.templates:
                    tpl_item = QtWidgets.QTreeWidgetItem(
                        tpl_group,
                        [tpl_node.label, "",
                         _STATUS_LABELS.get(tpl_node.status or "", "")]
                    )
                    tpl_item.setData(0, _SKEL_GUID_ROLE, tpl_node.template_guid)
                    set_ws_runs(tpl_item, 0, ((tpl_node.label, WsRole.ANALYSIS),))
                    tpl_item.setData(0, _SKEL_KIND_ROLE, "template")
                    tpl_item.setFlags(
                        tpl_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                    )
                    tpl_cs = (QtCore.Qt.CheckState.Checked if tpl_node.preselected
                              else QtCore.Qt.CheckState.Unchecked)
                    tpl_item.setCheckState(0, tpl_cs)
                    # T006: data roles for pane PreviewRequest (FR-010, R6)
                    tpl_item.setData(0, _SKEL_STATUS_ROLE, tpl_node.status or "")
                    tpl_item.setData(0, _SKEL_CAT_ROLE, GrammarCategory.AFFIX_TEMPLATES)
                    tpl_item.setData(0, _SKEL_OWNER_ROLE, pos_node.pos_guid)
                    # Read-only slot list under the template (FR-006)
                    for ref_sg in tpl_node.referenced_slot_guids:
                        # Find the slot node from the POS to recover its label
                        # and Optional flag.
                        ref_slot = next(
                            (s for s in pos_node.slots if s.slot_guid == ref_sg),
                            None,
                        )
                        slot_label = ref_slot.label if ref_slot else ref_sg[:8]
                        # FLEx convention: optional slots are shown in parentheses.
                        if ref_slot is not None and ref_slot.optional:
                            slot_label = f"({slot_label})"
                        ro_item = QtWidgets.QTreeWidgetItem(
                            tpl_item, [f"  {slot_label}", "", ""]
                        )
                        set_ws_runs(ro_item, 0,
                                    (("  ", None), (slot_label, WsRole.ANALYSIS)))
                        ro_item.setData(0, _SKEL_GUID_ROLE, ref_sg)
                        ro_item.setData(0, _SKEL_KIND_ROLE, "template_slot_ro")
                        ro_item.setData(0, _SKEL_READ_ONLY, True)
                        # Read-only: no checkable flag
                        ro_item.setFlags(
                            ro_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsUserCheckable
                        )

        # Strike through referenced-slot rows whose slot won't copy over.
        self._refresh_template_strikethroughs()

    # T013: tree selection handler (display-only, resolvable=False for all rows)
    def _on_tree_selection_changed(self, current, previous) -> None:
        """Build PreviewRequest from selected skeleton row (display-only)."""
        if current is None:
            self._pane.clear()
            return
        kind = current.data(0, _SKEL_KIND_ROLE)
        # Group/header rows -> clear
        if kind not in ("slot", "template"):
            self._pane.clear()
            return

        source_guid = current.data(0, _SKEL_GUID_ROLE) or ""
        category = current.data(0, _SKEL_CAT_ROLE)
        status = current.data(0, _SKEL_STATUS_ROLE) or ""
        owner_guid = current.data(0, _SKEL_OWNER_ROLE) or ""

        if status == "new":
            target_guid = ""
            mode = NEW
        elif status == "similar":
            target_guid = source_guid
            mode = OVERWRITE
        else:  # "in_target"
            target_guid = source_guid
            mode = OVERWRITE

        cat_str = (category.value if category is not None
                   else GrammarCategory.SLOTS.value)
        request = PreviewRequest(
            category=cat_str,
            source_guid=source_guid,
            target_guid=target_guid,
            status=status,
            mode=mode,
            resolvable=False,
            current_resolution=None,
            owner_guid=owner_guid,
        )
        self._pane.show_item(request)

    def _on_item_changed(self, item: QtWidgets.QTreeWidgetItem, column: int) -> None:
        """Handle template check/deselect semantics (T012)."""
        if self._mirroring or column != 0:
            return
        if self._skeleton is None:
            return
        kind = item.data(0, _SKEL_KIND_ROLE)
        if kind == "template":
            # Template check/deselect: update slot check states accordingly.
            tpl_guid = item.data(0, _SKEL_GUID_ROLE)
            new_state = item.checkState(0)
            self._mirroring = True
            try:
                self._apply_template_slot_semantics(tpl_guid, new_state)
            finally:
                self._mirroring = False
        # Any slot/template toggle can change what copies over -> restrike
        # the template referenced-slot rows. Font-only, so no itemChanged
        # recursion, but keep it under the guard for safety.
        self._mirroring = True
        try:
            self._refresh_template_strikethroughs()
        finally:
            self._mirroring = False

    def _refresh_template_strikethroughs(self) -> None:
        """Strike through template referenced-slot rows whose slot won't copy.

        A referenced slot copies over iff its slot checkbox is currently
        checked. Empty (deselected) slots -- including empty optional slots
        like Repetitive -- render struck through so the user can see at a
        glance which template positions carry nothing across.
        """
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            pos_item = root.child(i)
            if pos_item.data(0, _SKEL_KIND_ROLE) != "pos":
                continue
            # Map slot_guid -> checked for this POS's real (checkable) slots.
            checked: dict = {}
            for j in range(pos_item.childCount()):
                group = pos_item.child(j)
                if group.data(0, _SKEL_KIND_ROLE) != "slots_group":
                    continue
                for k in range(group.childCount()):
                    slot_item = group.child(k)
                    if slot_item.data(0, _SKEL_KIND_ROLE) != "slot":
                        continue
                    sg = slot_item.data(0, _SKEL_GUID_ROLE)
                    checked[sg] = (
                        slot_item.checkState(0) == QtCore.Qt.CheckState.Checked
                    )
            # Apply strikethrough to template_slot_ro rows accordingly.
            for j in range(pos_item.childCount()):
                group = pos_item.child(j)
                if group.data(0, _SKEL_KIND_ROLE) != "templates_group":
                    continue
                for k in range(group.childCount()):
                    tpl_item = group.child(k)
                    for m in range(tpl_item.childCount()):
                        ro = tpl_item.child(m)
                        if ro.data(0, _SKEL_KIND_ROLE) != "template_slot_ro":
                            continue
                        sg = ro.data(0, _SKEL_GUID_ROLE)
                        struck = not checked.get(sg, False)
                        f = ro.font(0)
                        f.setStrikeOut(struck)
                        ro.setFont(0, f)

    def _apply_template_slot_semantics(self, tpl_guid: str,
                                        tpl_state) -> None:
        """Apply template check/deselect semantics to the slot checkboxes.

        Checked: force all referenced slots checked.
        Unchecked: revert slots to affix-filled state only (bare-bones).
        Never modifies affix_picks (FR-007).
        """
        if self._skeleton is None:
            return
        # Find the template node
        tpl_node = None
        pos_node_found = None
        for pos_node in self._skeleton.pos_nodes:
            for tn in pos_node.templates:
                if tn.template_guid == tpl_guid:
                    tpl_node = tn
                    pos_node_found = pos_node
                    break
            if tpl_node is not None:
                break
        if tpl_node is None or pos_node_found is None:
            return

        if tpl_state == QtCore.Qt.CheckState.Checked:
            # Force all referenced slots checked
            slots_to_check = set(tpl_node.referenced_slot_guids)
        else:
            # Deselect: only affix-filled slots remain
            slots_to_check = self._skeleton.affix_filled_slot_guids()

        # Walk the tree and update slot items under this POS
        self._update_slot_checks_in_tree(pos_node_found.pos_guid, slots_to_check,
                                          tpl_state == QtCore.Qt.CheckState.Checked)

    def _update_slot_checks_in_tree(self, pos_guid: str, slot_guids: set,
                                     force_checked: bool) -> None:
        """Walk the tree and set slot check states under the given POS."""
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            pos_item = root.child(i)
            if pos_item.data(0, _SKEL_GUID_ROLE) != pos_guid:
                continue
            for j in range(pos_item.childCount()):
                group = pos_item.child(j)
                if group.data(0, _SKEL_KIND_ROLE) != "slots_group":
                    continue
                for k in range(group.childCount()):
                    slot_item = group.child(k)
                    if slot_item.data(0, _SKEL_KIND_ROLE) != "slot":
                        continue
                    sg = slot_item.data(0, _SKEL_GUID_ROLE)
                    if force_checked and sg in slot_guids:
                        slot_item.setCheckState(0, QtCore.Qt.CheckState.Checked)
                    elif not force_checked:
                        # Deselect: only keep affix-filled
                        cs = (QtCore.Qt.CheckState.Checked
                              if sg in slot_guids
                              else QtCore.Qt.CheckState.Unchecked)
                        slot_item.setCheckState(0, cs)

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

    def _get_affix_picks(self) -> frozenset:
        """Retrieve affix_picks from the item-picker page (index 1)."""
        try:
            w = self.wizard()
            if w is None:
                return frozenset()
            page_items = w.page_items()
            if page_items is None:
                return frozenset()
            sel = page_items.collect_selection()
            return sel.affix_picks
        except Exception:  # noqa: BLE001
            return frozenset()

    def _get_stem_picks(self) -> frozenset:
        """019: retrieve stem_picks from the dedicated Stems page (mirror of
        _get_affix_picks). The skeleton builder itself stays AFFIX-ONLY per
        FR-013; this accessor exists for parity and downstream use.
        """
        try:
            w = self.wizard()
            if w is None:
                return frozenset()
            page_stems = w.page_stems()
            if page_stems is None:
                return frozenset()
            return page_stems.stem_picks()
        except Exception:  # noqa: BLE001
            return frozenset()

    def collect_skeleton_picks(self) -> dict:
        """Return the current skeleton selections as:
        {
          "pos_guids": set[str],
          "slot_guids": set[str],
          "template_guids": set[str],
        }
        """
        pos_guids: Set[str] = set()
        slot_guids: Set[str] = set()
        template_guids: Set[str] = set()
        root = self._tree.invisibleRootItem()

        def _walk(node: QtWidgets.QTreeWidgetItem) -> None:
            kind = node.data(0, _SKEL_KIND_ROLE)
            state = node.checkState(0)
            if kind == "pos" and state == QtCore.Qt.CheckState.Checked:
                g = node.data(0, _SKEL_GUID_ROLE)
                if g:
                    pos_guids.add(g)
            elif kind == "slot" and state == QtCore.Qt.CheckState.Checked:
                g = node.data(0, _SKEL_GUID_ROLE)
                if g:
                    slot_guids.add(g)
            elif kind == "template" and state == QtCore.Qt.CheckState.Checked:
                g = node.data(0, _SKEL_GUID_ROLE)
                if g:
                    template_guids.add(g)
            for i in range(node.childCount()):
                _walk(node.child(i))

        for i in range(root.childCount()):
            _walk(root.child(i))

        return {
            "pos_guids": pos_guids,
            "slot_guids": slot_guids,
            "template_guids": template_guids,
        }

    def deselected_filled_slot_guids(self) -> frozenset:
        """Return slot GUIDs that a picked affix fills but the user unchecked.

        Used by the EXCLUDED-LOSSY gate at Move (T017).
        """
        if self._skeleton is None:
            return frozenset()
        picks = self.collect_skeleton_picks()
        checked_slots = picks["slot_guids"]
        affix_filled = self._skeleton.affix_filled_slot_guids()
        return frozenset(affix_filled - checked_slots)


# ---------------------------------------------------------------------------
# Page 3c -- Grammatical Dependencies  (T014)
# ---------------------------------------------------------------------------

class _PageGramDeps(_FlowPage):
    """Page 3c: Grammatical dependencies derived from the affix picks' POSes.

    Sections:
      - Inflection Features
      - Inflection Classes
      - Stem Names

    ExceptionFeaturesOC does not exist on the live LCM runtime; that dep-kind
    is tracked under a separate shared-bug ticket and is NOT shown here.

    All items are preselected (AS-NEEDED); per-item deselect is the user action.
    Empty sections render cleanly (no error, section header visible but empty).
    Target-status column (NEW / IN TARGET / SIMILAR).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Unnumbered: this run assigns the number on entry, because a
        # position is a fact about the run and not about the page
        # (SelectionWizard._apply_step_number). The literal that used to
        # be here stated a total across a flow that could skip pages.
        self.setTitle("Grammatical Dependencies")
        self.setSubTitle(
            "The inflection features, classes and stem names those parts of "
            "speech need, all preselected. Deselect anything you do not want."
        )
        self._deps: Optional[object] = None  # DepsInventory
        # T014: preview service (initialized in initializePage)
        self._preview_service = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        self._tree = QtWidgets.QTreeWidget(self)
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["Item", "Target"])
        self._tree.header().setStretchLastSection(True)
        self._tree.setAlternatingRowColors(True)
        # T014: merge-preview pane docked to the right (FR-005)
        self._pane = MergePreviewPane(self)
        splitter = _make_tree_pane_splitter(self._tree, self._pane)
        layout.addWidget(splitter, 1)

    def initializePage(self) -> None:
        """Build deps from affix picks + bound target when the page is entered."""
        self._tree.clear()
        self._deps = None

        affix_picks = self._get_affix_picks()
        stem_picks = self._get_stem_picks()
        source = self._get_source()
        if source is None or not (affix_picks or stem_picks):
            empty = QtWidgets.QTreeWidgetItem(
                self._tree, ["(No affixes or stems selected, or no source bound)"]
            )
            empty.setFlags(empty.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
            return

        target = self._get_target()
        # FR-023 row 8. The heaviest per-entry walk (reference closure), so the
        # one most likely to want its indicator up before it starts.
        try:
            with _page_progress(
                self, "dependencies", _source_counts_of(self).lexicon_entries
            ) as prog:
                deps = build_deps_inventory(
                    source, affix_picks, target=target, stem_picks=stem_picks,
                    progress=prog,
                )
        except Exception:  # noqa: BLE001
            _show_failure_row(self._tree, "dependencies")   # T022
            deps = None

        if deps is None:
            return

        self._deps = deps
        # spec 011: feature / class / stem-name labels in the analysis WS font.
        attach_ws_font_delegate(
            self._tree, [0], WsFontRegistry.from_project(source)
        )
        self._populate_deps_tree(deps)
        _carry_full_values_in_tooltips(self._tree)   # T026 / FR-029b
        self._tree.expandAll()
        for col in range(2):
            self._tree.resizeColumnToContents(col)

        # T014: construct service and set pane context (FR-006)
        self._preview_service = MergePreviewService(source, target)
        self._pane.set_context(
            self._preview_service,
            WsFontRegistry.from_project(source),
            [],  # no candidates for deps
        )
        self._pane.clear()
        # Double-connect guard
        if self._tree.receivers(self._tree.currentItemChanged) == 0:
            self._tree.currentItemChanged.connect(self._on_tree_selection_changed)

    def _on_tree_selection_changed(self, current, previous) -> None:
        """T014: build PreviewRequest from selected deps row (display-only)."""
        if current is None:
            self._pane.clear()
            return
        kind = current.data(0, _SKEL_KIND_ROLE)
        # Section-header rows -> clear
        if kind != "dep":
            self._pane.clear()
            return

        source_guid = current.data(0, _SKEL_GUID_ROLE) or ""
        category = current.data(0, _DEPS_CAT_ROLE)
        status = current.data(0, _DEPS_STATUS_ROLE) or ""

        if status == "new":
            target_guid = ""
            mode = NEW
        elif status == "similar":
            target_guid = source_guid
            mode = OVERWRITE
        else:  # "in_target"
            target_guid = source_guid
            mode = OVERWRITE

        cat_str = (category.value if category is not None
                   else GrammarCategory.INFLECTION_FEATURES.value)
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

    def _populate_deps_tree(self, deps) -> None:
        """Populate the sections tree from a DepsInventory."""
        # T007: category mapping (research confirmed from section labels)
        _SECTION_CAT = {
            "Inflection Features": GrammarCategory.INFLECTION_FEATURES,
            "Inflection Classes": GrammarCategory.INFLECTION_CLASSES,
            "Stem Names": GrammarCategory.STEM_NAMES,
        }
        sections = [
            ("Inflection Features", deps.infl_features),
            ("Inflection Classes", deps.infl_classes),
            ("Stem Names", deps.stem_names),
        ]
        for section_label, rows in sections:
            section_item = QtWidgets.QTreeWidgetItem(
                self._tree, [section_label, ""]
            )
            section_item.setData(0, _SKEL_KIND_ROLE, "section")
            # Section-header rows do NOT receive item-level status roles (T007)
            section_item.setFlags(
                section_item.flags()
                | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                | QtCore.Qt.ItemFlag.ItemIsAutoTristate
            )
            section_item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
            from PyQt6 import QtGui
            bold_f = section_item.font(0)
            bold_f.setBold(True)
            section_item.setFont(0, bold_f)
            if not rows:
                empty_child = QtWidgets.QTreeWidgetItem(
                    section_item, ["(none)", ""]
                )
                empty_child.setFlags(
                    empty_child.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled
                )
            else:
                grammar_cat = _SECTION_CAT.get(section_label)
                # Build nested tree: depth-stack pattern (mirrors entry-types at
                # selection_wizard.py:3523-3548).  depth=0 rows attach to the
                # section header; depth=1+ rows attach to the nearest shallower item.
                parent_stack = [(-1, section_item)]  # sentinel
                for row in rows:
                    while len(parent_stack) > 1 and parent_stack[-1][0] >= row.depth:
                        parent_stack.pop()
                    tree_parent = parent_stack[-1][1]
                    row_item = QtWidgets.QTreeWidgetItem(
                        tree_parent,
                        [row.label, _STATUS_LABELS.get(row.status or "", "")]
                    )
                    set_ws_runs(row_item, 0, ((row.label, WsRole.ANALYSIS),))
                    row_item.setData(0, _SKEL_GUID_ROLE, row.guid)
                    row_item.setData(0, _SKEL_KIND_ROLE, "dep")
                    # T007: data roles for pane PreviewRequest (FR-010, R6)
                    row_item.setData(0, _DEPS_STATUS_ROLE, row.status or "")
                    if grammar_cat is not None:
                        row_item.setData(0, _DEPS_CAT_ROLE, grammar_cat)
                    row_item.setFlags(
                        row_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                    )
                    cs = (QtCore.Qt.CheckState.Checked if row.preselected
                          else QtCore.Qt.CheckState.Unchecked)
                    row_item.setCheckState(0, cs)
                    parent_stack.append((row.depth, row_item))

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

    def _get_affix_picks(self) -> frozenset:
        try:
            w = self.wizard()
            if w is None:
                return frozenset()
            page_items = w.page_items()
            if page_items is None:
                return frozenset()
            sel = page_items.collect_selection()
            return sel.affix_picks
        except Exception:  # noqa: BLE001
            return frozenset()

    def _get_stem_picks(self) -> frozenset:
        """019: retrieve stem_picks from the dedicated Stems page (mirror of
        _get_affix_picks)."""
        try:
            w = self.wizard()
            if w is None:
                return frozenset()
            page_stems = w.page_stems()
            if page_stems is None:
                return frozenset()
            return page_stems.stem_picks()
        except Exception:  # noqa: BLE001
            return frozenset()

    def collect_dep_picks(self) -> dict:
        """Return currently-checked dep GUIDs by section.

        Returns
        -------
        dict with keys:
          "infl_features", "infl_classes", "stem_names", "exception_features"
          each a set[str] of GUIDs.
        """
        result = {
            "infl_features": set(),
            "infl_classes": set(),
            "stem_names": set(),
        }
        section_map = {
            "Inflection Features": "infl_features",
            "Inflection Classes": "infl_classes",
            "Stem Names": "stem_names",
        }
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            section_item = root.child(i)
            section_label = section_item.text(0)
            key = section_map.get(section_label)
            if key is None:
                continue
            for j in range(section_item.childCount()):
                row_item = section_item.child(j)
                if row_item.checkState(0) == QtCore.Qt.CheckState.Checked:
                    g = row_item.data(0, _SKEL_GUID_ROLE)
                    if g:
                        result[key].add(g)
        return result

    def deselected_dep_guids(self) -> frozenset:
        """Return all GUIDs that were preselected but the user unchecked.

        Used for EXCLUDED-LOSSY warnings.
        """
        if self._deps is None:
            return frozenset()
        all_preselected = frozenset(
            row.guid
            for collection in (
                self._deps.infl_features,
                self._deps.infl_classes,
                self._deps.stem_names,
            )
            for row in collection
            if row.preselected
        )
        picks = self.collect_dep_picks()
        checked = frozenset(
            g
            for guids in picks.values()
            for g in guids
        )
        return all_preselected - checked
