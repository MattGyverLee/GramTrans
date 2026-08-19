"""Wizard step 2 -- map the source's writing systems onto the target (feature 039, T013).

Why this module exists
----------------------
Writing-system mapping is one decision, made once, project-level. The
two-stage `NEEDS_WS_MAPPING` handshake this replaced is retired: the page
enumerates the source's ACTIVE analysis and vernacular writing systems -- not
the full installed superset, which is a much longer list of systems the project
does not actually use -- and offers a target for each.

The two enumeration helpers live here rather than in `wizard_widgets` because
they are not widget code: they walk a FLEx project's writing systems and are
specific to what this page has to ask. Nothing else calls them.

What is deliberately absent
---------------------------
* Any project binding. That happened on step 1; this page reads the pair through
  `wizard.page_project_ws()`.
* `closest_ws_defaults`' policy. Which target a source system defaults to is a
  `Lib/ws_mapping.py` decision; this page renders it and lets the operator
  override.
"""
from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

if __package__:
    from ..models import WSKind, WSMapping, WSMappingEntry
    from ..ws_mapping import closest_ws_defaults
    from .wizard_page_base import _FlowPage
else:
    from models import WSKind, WSMapping, WSMappingEntry  # type: ignore
    from wizard_page_base import _FlowPage  # type: ignore
    from ws_mapping import closest_ws_defaults  # type: ignore


# ---------------------------------------------------------------------------
# Page 2 -- Writing Systems  (feature 036 T010, FR-006)
# ---------------------------------------------------------------------------

class _PageWritingSystems(_FlowPage):
    """Page 2: map every ACTIVE source writing system into the target.

    Split out of the old `_PageProjectWS` by feature 036 FR-006. The behaviour
    is unchanged; what changed is *when* it runs. The tables used to be built
    inside `_on_pick_target`, i.e. while the operator was still on the projects
    page and could not see them; they are now built in `initializePage`, from
    the two handles the previous page bound.

    Rebuilt from scratch on EVERY entry, never merged into existing rows. That
    is not defensiveness: releasing a bound project on step 1 (`_on_pick_source`
    -> `_release_bound_target`) invalidates every row that named it, and this
    page is the only owner of that row state after the split. Repopulating is
    what makes "the released target's rows cannot come back" true by
    construction instead of by a second owner remembering to clear them.

    WS decision: enumerate ACTIVE writing systems from the source project and
    present a three-way MAP / CREATE / SKIP control re-hosted from
    ws_mapping_dialog.py / ws_wizard.py mechanics.  Writing systems are split
    into two groups: Vernacular WS and Analysis WS (by WSKind).  A dual-role
    WS (appears in both groups) defaults both rows to the same choice and is
    independently overridable (linked-until-touched).  A dual-role CREATE
    choice points BOTH roles at the SAME target WS (no double-create).

    Vernacular is lead: when a vernacular row is set, the same-tag analysis
    row defaults to the vernacular choice and remains independently
    overridable.

    This is a PROJECT-LEVEL decision made once; no per-category WS negotiation.
    """

    # Choice constants (MAP=0, CREATE=1, SKIP=2) mirrored from WSChoice.
    _CHOICE_MAP = 0
    _CHOICE_CREATE = 1
    _CHOICE_SKIP = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        # Handles, adopted from the projects page on every entry. Held rather
        # than fetched per call because `_populate_ws_tables` and
        # `_sync_analysis_row_widget` read the source several times while
        # building one table, and the accessor chain is not free.
        self._host = None
        self._context = None
        self._target_ws_ids: list = []  # existing WS IDs in the target
        # Row state: dict keyed by (ws_id, kind_value) -> {"choice": int, "target": str}
        # kind_value is WSKind.VERNACULAR.value or WSKind.ANALYSIS.value
        self._row_state: dict = {}
        # Track which analysis rows are still "linked" to their vernacular twin.
        self._analysis_linked: set = set()  # set of ws_id strings
        # Feature 032 US4: {source_ws_id: target_ws_id} related-languages MAP
        # defaults, computed in _populate_ws_tables once the target is bound.
        self._ws_map_defaults: dict = {}

        # Unnumbered: the run assigns the number on entry (FR-009a).
        self.setTitle("Writing Systems")
        self.setSubTitle(
            "Map each source writing system onto a target one, create it "
            "there, or skip it. Vernacular and analysis systems are listed "
            "separately."
        )
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        layout.addWidget(QtWidgets.QLabel(
            "Writing-system mapping (MAP / CREATE / SKIP per WS):", self
        ))

        # Scrollable area holding the two WS group tables (Vernacular, Analysis).
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll_container = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_container)

        # -- Vernacular WS group --
        vern_group = QtWidgets.QGroupBox("Vernacular Writing Systems", scroll_container)
        self._vern_layout = QtWidgets.QVBoxLayout(vern_group)
        self._vern_table = self._make_ws_table(vern_group)
        self._vern_layout.addWidget(self._vern_table)
        scroll_layout.addWidget(vern_group)

        # -- Analysis WS group --
        anal_group = QtWidgets.QGroupBox("Analysis Writing Systems", scroll_container)
        self._anal_layout = QtWidgets.QVBoxLayout(anal_group)
        self._anal_table = self._make_ws_table(anal_group)
        self._anal_layout.addWidget(self._anal_table)
        scroll_layout.addWidget(anal_group)

        scroll.setWidget(scroll_container)
        layout.addWidget(scroll, 1)

        # Explains what an empty pair of tables means. Without it, a run whose
        # source has no ACTIVE writing systems (or whose handles did not open)
        # shows two blank boxes that look like a bug.
        self._empty_note = QtWidgets.QLabel("", self)
        self._empty_note.setWordWrap(True)
        self._empty_note.setVisible(False)
        layout.addWidget(self._empty_note)

        # No developer note under the tables. What used to be here -- that the
        # WS choice is project-level and made once, that the per-category
        # handshake is retired, and that vernacular leads its same-tag analysis
        # row -- is design commentary addressed to whoever maintains this page.
        # Two of the three describe a *previous* design a user never saw, and
        # the third describes behaviour the linked rows already demonstrate.
        # It lives in this class's docstring instead, which is where a
        # maintainer looks and a linguist does not.

    def _make_ws_table(self, parent) -> "QtWidgets.QTableWidget":
        """Create a QTableWidget with columns: Source WS | Choice | Target WS."""
        table = QtWidgets.QTableWidget(0, 3, parent)
        table.setHorizontalHeaderLabels(["Source WS", "Choice", "Target WS"])
        table.horizontalHeader().setStretchLastSection(True)
        return table

    # ------------------------------------------------------------------
    def _projects_page(self):
        """The page that owns the two handles, or None outside a wizard."""
        wizard = self.wizard()
        if wizard is None or not hasattr(wizard, "page_project_ws"):
            return None
        return wizard.page_project_ws()

    def initializePage(self) -> None:
        """Adopt the bound handles and rebuild both tables from scratch.

        From scratch, every time -- see the class docstring. A merge into
        existing rows would let a row that named a since-released project
        survive, and this page is the only owner of that state.
        """
        projects = self._projects_page()
        self._host = getattr(projects, "_host", None) if projects is not None else None
        self._context = projects.context() if projects is not None else None

        # Drop everything the previous visit built BEFORE deciding whether the
        # handles are usable, so an unbound re-entry leaves nothing behind.
        self._row_state.clear()
        self._analysis_linked = set()
        self._ws_map_defaults = {}
        self._target_ws_ids = []
        self._vern_table.setRowCount(0)
        self._anal_table.setRowCount(0)

        target = getattr(self._context, "target_handle", None) \
            if self._context is not None else None
        if self._host is None:
            self._empty_note.setText(
                "<i>No source project is bound, so there are no writing "
                "systems to map. Go back and pick the projects first.</i>"
            )
            self._empty_note.setVisible(True)
            return
        if target is not None:
            self._target_ws_ids = _enumerate_active_ws_ids(target)
        self._populate_ws_tables()
        empty = (self._vern_table.rowCount() == 0
                 and self._anal_table.rowCount() == 0)
        self._empty_note.setText(
            "<i>The source project reports no active writing systems, so there "
            "is nothing to map here.</i>" if empty else ""
        )
        self._empty_note.setVisible(empty)

    def _populate_ws_tables(self) -> None:
        """Enumerate ACTIVE writing systems from the source project and build rows.

        Writing systems are classified as VERNACULAR, ANALYSIS, or both (dual-role).
        Dual-role WS appears in both groups; the analysis row is linked to the
        vernacular choice until the user touches it independently.
        """
        vern_ids, anal_ids = _enumerate_ws_by_kind(self._host)
        dual_ids = set(vern_ids) & set(anal_ids)

        # Feature 032 US4: pre-compute the best-effort correspondence defaults --
        # source primary vernacular/analysis -> target primary of the same kind,
        # and each source variant -> the CLOSEST target variant of the same kind
        # (by subtag suffix). A source WS with no identical target Id thus
        # defaults to MAP-to-its-correspondent instead of CREATE.
        # {source_ws_id: target_ws_id}.
        self._ws_map_defaults = {}
        target = getattr(self._context, "target_handle", None) if self._context is not None else None
        if target is not None:
            try:
                self._ws_map_defaults = closest_ws_defaults(self._host, target) or {}
            except Exception:  # noqa: BLE001 -- defaulting is best-effort; never block the page
                self._ws_map_defaults = {}

        # Reset state.
        self._row_state.clear()
        self._analysis_linked = set(dual_ids)  # start linked for dual-role WSes

        self._fill_table(
            self._vern_table, vern_ids, kind_value=WSKind.VERNACULAR.value,
            is_vernacular=True,
        )
        self._fill_table(
            self._anal_table, anal_ids, kind_value=WSKind.ANALYSIS.value,
            is_vernacular=False,
        )

    def _fill_table(self, table, ws_ids: list, kind_value: str,
                    is_vernacular: bool) -> None:
        """Populate `table` with one row per ws_id."""
        table.setRowCount(0)
        for ws_id in ws_ids:
            row = table.rowCount()
            table.insertRow(row)

            # Col 0: source WS label (read-only)
            src_item = QtWidgets.QTableWidgetItem(ws_id)
            src_item.setFlags(src_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 0, src_item)

            # Col 1: choice combo (MAP / CREATE / SKIP)
            choice_cb = QtWidgets.QComboBox(table)
            choice_cb.addItem("MAP to existing target WS", self._CHOICE_MAP)
            choice_cb.addItem("CREATE new target WS", self._CHOICE_CREATE)
            choice_cb.addItem("SKIP (drop objects using this WS)", self._CHOICE_SKIP)
            # Feature 032 US4: resolve the default choice + target for this row.
            #   1. identical target Id present -> MAP to it (self, common case);
            #   2. else closest_ws_defaults proposes a correspondence:
            #        ("map", tid)    -> MAP to the matched target WS;
            #        ("create", tid) -> CREATE a new WS, rebased under the target
            #                           primary base (don't split the language);
            #   3. else no proposal at all -> CREATE with the source tag.
            proposal = getattr(self, "_ws_map_defaults", {}).get(ws_id)
            if ws_id in self._target_ws_ids:
                default_choice = self._CHOICE_MAP
                default_target = ws_id
            elif proposal is not None:
                pchoice, ptarget = proposal
                if pchoice == "create":
                    default_choice = self._CHOICE_CREATE
                    default_target = ptarget  # rebased tag, e.g. abc-x-emic
                else:
                    default_choice = self._CHOICE_MAP
                    default_target = ptarget
            else:
                default_choice = self._CHOICE_CREATE
                default_target = ws_id  # CREATE: use source tag as proposed name

            # Pre-select the resolved choice.
            choice_cb.setCurrentIndex(default_choice)
            table.setCellWidget(row, 1, choice_cb)

            # Col 2: target WS combo (editable; used for MAP).
            tgt_cb = QtWidgets.QComboBox(table)
            tgt_cb.setEditable(True)
            tgt_cb.addItem("")
            for t in self._target_ws_ids:
                tgt_cb.addItem(t)
            tgt_cb.setCurrentText(default_target)
            table.setCellWidget(row, 2, tgt_cb)

            # Initialize row state.
            key = (ws_id, kind_value)
            self._row_state[key] = {
                "choice": choice_cb.currentIndex(),
                "target": tgt_cb.currentText(),
            }

            # Wire change signals to state updater.
            choice_cb.currentIndexChanged.connect(
                lambda idx, k=key, is_v=is_vernacular, wid=ws_id:
                self._on_choice_changed(k, idx, is_v, wid)
            )
            tgt_cb.currentTextChanged.connect(
                lambda text, k=key, is_v=is_vernacular, wid=ws_id:
                self._on_target_changed(k, text, is_v, wid)
            )

    def _on_choice_changed(self, key, idx: int, is_vernacular: bool, ws_id: str) -> None:
        """Update row state; propagate to linked analysis row if vernacular lead."""
        self._row_state[key] = dict(self._row_state.get(key, {}), choice=idx)
        if is_vernacular:
            # Seed the linked analysis row if it hasn't been independently touched.
            anal_key = (ws_id, WSKind.ANALYSIS.value)
            if anal_key in self._row_state and ws_id in self._analysis_linked:
                self._row_state[anal_key] = dict(
                    self._row_state[anal_key], choice=idx
                )
                self._sync_analysis_row_widget(ws_id, idx)

    def _on_target_changed(self, key, text: str, is_vernacular: bool, ws_id: str) -> None:
        """Update row state; break link when analysis row is independently changed."""
        self._row_state[key] = dict(self._row_state.get(key, {}), target=text)
        if not is_vernacular:
            # User explicitly changed analysis row: break the link.
            self._analysis_linked.discard(ws_id)
        if is_vernacular:
            # Propagate to linked analysis row.
            anal_key = (ws_id, WSKind.ANALYSIS.value)
            if anal_key in self._row_state and ws_id in self._analysis_linked:
                self._row_state[anal_key] = dict(
                    self._row_state[anal_key], target=text
                )

    def _sync_analysis_row_widget(self, ws_id: str, choice_idx: int) -> None:
        """Sync the analysis table widget for ws_id to choice_idx (linked update)."""
        vern_ids, anal_ids = _enumerate_ws_by_kind(self._host)
        if ws_id not in anal_ids:
            return
        row_idx = anal_ids.index(ws_id)
        if row_idx >= self._anal_table.rowCount():
            return
        choice_cb = self._anal_table.cellWidget(row_idx, 1)
        if choice_cb is not None and hasattr(choice_cb, "setCurrentIndex"):
            # Block signal to avoid recursive propagation.
            try:
                choice_cb.blockSignals(True)
                choice_cb.setCurrentIndex(choice_idx)
            finally:
                choice_cb.blockSignals(False)

    # ------------------------------------------------------------------
    def selected_ws_ids(self) -> list:
        """Return the list of source WS IDs that are not SKIP.

        When the WS table has been populated (_row_state is set), derive the
        list from the three-way control state.  Falls back to reading
        _ws_list (the legacy QListWidget) if _row_state is unavailable,
        for backward compatibility with existing test doubles that inject
        a bare _ws_list mock.
        """
        row_state = getattr(self, "_row_state", None)
        if row_state is not None:
            result = []
            seen = set()
            for (ws_id, _kind), state in row_state.items():
                if ws_id not in seen and state.get("choice") != self._CHOICE_SKIP:
                    result.append(ws_id)
                    seen.add(ws_id)
            return result
        # Legacy fallback (used by test_wizard_page_flow.py and old callers).
        ws_list = getattr(self, "_ws_list", None)
        if ws_list is None:
            return []
        return [
            ws_list.item(i).text()
            for i in range(ws_list.count())
            if ws_list.item(i).isSelected()
        ]

    def ws_mapping(self) -> "WSMapping":
        """Build a WSMapping from the current page state.

        MAP rows:    source_ws_id -> target_ws_id (create_in_target=False)
        CREATE rows: source_ws_id -> source_ws_id (create_in_target=True)
        SKIP rows:   omitted from the mapping.

        Dual-role CREATE: both VERNACULAR and ANALYSIS entries point at the SAME
        target WS (no double-create), identified by the source tag.
        """
        entries = []
        seen_creates: dict = {}  # ws_id -> target_ws_id for CREATE rows
        for (ws_id, kind_value), state in self._row_state.items():
            choice = state.get("choice", self._CHOICE_SKIP)
            target_text = (state.get("target") or ws_id).strip()
            kind = WSKind(kind_value)
            if choice == self._CHOICE_SKIP:
                continue
            if choice == self._CHOICE_CREATE:
                # Dual-role: reuse the same target tag as the vernacular twin.
                create_target = seen_creates.get(ws_id, target_text)
                seen_creates[ws_id] = create_target
                entries.append(WSMappingEntry(
                    source_ws_id=ws_id,
                    source_ws_kind=kind,
                    target_ws_id=create_target,
                    create_in_target=True,
                ))
            else:  # MAP
                entries.append(WSMappingEntry(
                    source_ws_id=ws_id,
                    source_ws_kind=kind,
                    target_ws_id=target_text or ws_id,
                    create_in_target=False,
                ))
        return WSMapping(entries=tuple(entries))


def _enumerate_active_ws_ids(project) -> list:
    """Enumerate ACTIVE writing systems from a FLExProject.

    Active = analysis + vernacular writing systems currently active in the
    project (not the full installed superset). Falls back to an empty list
    on any introspection failure.
    """
    ws_ids = []
    try:
        # Attempt 1: flexicon's GetSyncableProperties-compatible path.
        # flexicon exposes WritingSystems.GetAll().
        all_wss = project.WritingSystems.GetAll()
        for ws in all_wss:
            ws_id = getattr(ws, "Id", None)
            if ws_id:
                ws_ids.append(str(ws_id))
        if ws_ids:
            return ws_ids
    except (AttributeError, TypeError, Exception):  # noqa: BLE001
        pass

    # Attempt 2: try AnalysisWritingSystems + VernacularWritingSystems (LCM 9.x).
    try:
        for attr in ("AnalysisWritingSystems", "VernacularWritingSystems"):
            wss = getattr(project, attr, None)
            if wss is None:
                continue
            for ws in wss:
                ws_id = getattr(ws, "Id", None) or getattr(ws, "IcuLocale", None)
                if ws_id and ws_id not in ws_ids:
                    ws_ids.append(str(ws_id))
        if ws_ids:
            return ws_ids
    except (AttributeError, TypeError, Exception):  # noqa: BLE001
        pass

    # Attempt 3: best-effort GetWritingSystems (used by old WS dialog).
    try:
        for ws in project.GetWritingSystems():
            ws_id = getattr(ws, "Id", None)
            if ws_id and ws_id not in ws_ids:
                ws_ids.append(str(ws_id))
    except (AttributeError, TypeError, Exception):  # noqa: BLE001
        pass

    return ws_ids


def _enumerate_ws_by_kind(project) -> "tuple[list, list]":
    """Enumerate ACTIVE writing systems split by kind.

    Returns:
        (vern_ids, anal_ids) -- each a list[str] of WS IDs in active order.
        A dual-role WS (both vernacular + analysis) appears in BOTH lists.
        Falls back to treating all active WSes as both kinds on total failure.

    Primary access path (LCM 9.x via flexicon FLExProject.Cache):
        project.Cache.LangProject.CurrentVernacularWritingSystems
        project.Cache.LangProject.CurrentAnalysisWritingSystems
    Each entry exposes .Id (full BCP-47 tag, e.g. 'etu', 'etu-fonipa').
    Current* is the correct "active/enabled" list; each distinct variant tag
    (e.g. 'etu' vs 'etu-fonipa') is a separate entry and maps 1:1 by default.

    NOTE: project.VernacularWritingSystems and project.AnalysisWritingSystems
    are NOT exposed by the flexicon FLExProject wrapper and return None --
    the Cache.LangProject.Current* path is the correct primary path.
    """
    vern_ids: list = []
    anal_ids: list = []
    try:
        cache = getattr(project, "Cache", None)
        lang = getattr(cache, "LangProject", None)
        if lang is not None:
            cvws = getattr(lang, "CurrentVernacularWritingSystems", None)
            if cvws is not None:
                for ws in cvws:
                    ws_id = getattr(ws, "Id", None)
                    if ws_id and str(ws_id) not in vern_ids:
                        vern_ids.append(str(ws_id))
            caws = getattr(lang, "CurrentAnalysisWritingSystems", None)
            if caws is not None:
                for ws in caws:
                    ws_id = getattr(ws, "Id", None)
                    if ws_id and str(ws_id) not in anal_ids:
                        anal_ids.append(str(ws_id))
        if vern_ids or anal_ids:
            return (vern_ids, anal_ids)
    except (AttributeError, TypeError, Exception):  # noqa: BLE001
        pass

    # Fallback: treat all active WSes as both kinds (graceful degradation).
    all_ids = _enumerate_active_ws_ids(project)
    return (list(all_ids), list(all_ids))
