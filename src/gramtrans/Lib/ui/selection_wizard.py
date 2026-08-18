"""Selection Wizard (Phase 3c, plan.md Refinement 3, 2026-07-01).

A QWizard that replaces the single-window `main_window.py`.  The existing
widgets are re-hosted verbatim; no widget logic is rewritten.  How many pages a
run shows is a property of the run, not of this module -- see `flow()`.

Pages: there is no page list here, deliberately. `SelectionWizard.flow()` is the
single declaration of which pages exist, in what order, and which of them may
drop out of a run that has nothing for them to decide (feature 036 FR-010). A
second list in this docstring is how the old one came to describe five pages
while eleven were registered.

Two facts the declaration cannot state and a reader needs:
  * Projects and Writing Systems are two pages (036 FR-006). Binding a pair of
    projects and mapping their writing systems are separate decisions, and the
    second is not answerable until the first is done.
  * Finish / Move is the ONLY write point.

Writing-system rules:
- Enumerate ACTIVE writing systems only (analysis + vernacular active in
  the project; not the full installed superset).
- The two-stage NEEDS_WS_MAPPING handshake is RETIRED -- page-1 handles WS
  once, project-level.

Constitution alignment:
- Principle III: the only write is in the page-5 Finish handler, which
  first queries `plan.excluded_lossy_count()` and blocks/confirms if > 0.
- Principle V: per-item deselection surfaces on page 3; EXCLUDED-LOSSY
  warnings surface on page 4 (StatsPanel).
"""
from __future__ import annotations

import dataclasses
from contextlib import contextmanager
from typing import Optional, Set

from PyQt6 import QtCore, QtWidgets

if __package__:
    from .. import api as gt_api
    from ..models import (
        CategoryScope,
        ConflictMode,
        ExcludedLossy,
        GrammarCategory,
        RunMode,
        Selection,
        WSKind,
        WSMapping,
        WSMappingEntry,
        _DEFAULT_CONFLICT_MODES,
    )
    from ..selection import (
        PickerState,
        PosGroupedAffixInventory,
        SourceAffixInventory,
        affix_label_runs,
        build_deps_inventory,
        build_entry_types_inventory,
        build_excluded_lossy_warnings,
        build_phonology_excluded_lossy,
        build_phonology_inventory,
        build_pos_grouped_inventory,
        build_rules_inventory,
        build_selection,
        build_skeleton_inventory,
        build_text_inventory,
        collapse_entry_types,
        collapse_phonology,
        collapse_pos_grouped,
        entry_types_missing_ref_warnings,
        mirror_check_state,
        phonology_uses_untraversed_rules,
    )
    from ..ws_fonts import WsFontRegistry, WsRole
    from .stats_panel import StatsPanel
    from .source_picker import SourcePickerDialog
    from .target_picker import TargetPickerDialog
    from .ws_font_delegate import attach_ws_font_delegate, set_ws_runs
    from .merge_preview_pane import MergePreviewPane, PreviewRequest, _action_to_mode
    from .theme import ThemeCornerBar, install_theme
    from .page_header import PageHeader
    from ..merge_preview import MergePreviewService, OVERWRITE, MERGE_KEEP, NEW
    from ..models import SimilarResolution
    from ..report import RunReport
    from ..ws_mapping import closest_ws_defaults
else:
    import api as gt_api  # type: ignore
    from models import (  # type: ignore
        CategoryScope,
        ConflictMode,
        ExcludedLossy,
        GrammarCategory,
        RunMode,
        Selection,
        WSKind,
        WSMapping,
        WSMappingEntry,
        _DEFAULT_CONFLICT_MODES,
    )
    from selection import (  # type: ignore
        PickerState,
        PosGroupedAffixInventory,
        SourceAffixInventory,
        affix_label_runs,
        build_deps_inventory,
        build_entry_types_inventory,
        build_excluded_lossy_warnings,
        build_phonology_excluded_lossy,
        build_phonology_inventory,
        build_pos_grouped_inventory,
        build_rules_inventory,
        build_selection,
        build_skeleton_inventory,
        build_text_inventory,
        collapse_entry_types,
        collapse_phonology,
        collapse_pos_grouped,
        entry_types_missing_ref_warnings,
        mirror_check_state,
        phonology_uses_untraversed_rules,
    )
    from ws_fonts import WsFontRegistry, WsRole  # type: ignore
    from stats_panel import StatsPanel  # type: ignore
    from source_picker import SourcePickerDialog  # type: ignore
    from target_picker import TargetPickerDialog  # type: ignore
    from ws_font_delegate import attach_ws_font_delegate, set_ws_runs  # type: ignore
    from merge_preview_pane import MergePreviewPane, PreviewRequest, _action_to_mode  # type: ignore
    from theme import ThemeCornerBar, install_theme  # type: ignore
    from page_header import PageHeader  # type: ignore
    from merge_preview import MergePreviewService, OVERWRITE, MERGE_KEEP, NEW  # type: ignore
    from models import SimilarResolution  # type: ignore  (already imported above but needs bare-name alias)
    from report import RunReport  # type: ignore
    from ws_mapping import closest_ws_defaults  # type: ignore

if __package__:
    from ..gate import resolve_gate as _resolve_gate
    from ..progress import (
        SourceCounts,
        label_for,
        rate_for,
        reporting,
        warrants_indicator,
    )
    from .progress_indicator import deferred, immediate
else:
    from gate import resolve_gate as _resolve_gate  # type: ignore
    from progress import (  # type: ignore
        SourceCounts,
        label_for,
        rate_for,
        reporting,
        warrants_indicator,
    )
    from progress_indicator import deferred, immediate  # type: ignore


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# T024 / FR-029: the window floor, as ONE declared value for the wizard as a
# whole. 1100 px had been the floor since feature 004 widened the window for the
# tree-beside-preview layout, and it was never a measurement -- it is the width
# that layout happened to want on the machine it was built on. A 1366x768
# laptop, which is what a field linguist actually has, can show 1100 px only by
# surrendering every other window.
#
# Named rather than inlined because FR-029 is a structural claim as well as a
# behavioural one: no page negotiates its own floor, so no page can quietly
# become the real arbiter of how narrow the window may get. The per-pane
# minimums below are deliberately far smaller and their sum is checked against
# this number by the US3 test module.
MIN_WINDOW_WIDTH = 900

# Unchanged by feature 036 (US3 lowers the width only) and named here so the
# pair reads as one geometry decision instead of one constant and one literal.
MIN_WINDOW_HEIGHT = 680

# T025 / FR-029a: what a tree-and-preview page's two panes may be squeezed to.
# Their sum must stay well inside MIN_WINDOW_WIDTH -- minimums that sum past the
# window floor would make the floor unreachable and Qt would silently clamp the
# window back up, which is FR-029 failing in the name of FR-029a.
_TREE_PANE_MIN_WIDTH = 360
_PREVIEW_PANE_MIN_WIDTH = 260

_SCOPE_LABELS = {
    CategoryScope.NONE: "NONE",
    CategoryScope.AS_NEEDED: "AS-NEEDED (default)",
    CategoryScope.ALL: "ALL",
}

_CONFLICT_LABELS = {
    ConflictMode.ADD_NEW: "Add new (always create a copy)",
    ConflictMode.LINK: "Link (link existing by ID, else add; no field update)",
    ConflictMode.UPDATE: "Update (non-destructive: source wins on diverged fields; never blanks target)",
    ConflictMode.OVERWRITE: "Overwrite (replace target values with source)",
}

# Schema categories for the per-category scope selectors on page 3.
_SCHEMA_CATEGORIES = [
    GrammarCategory.POS,
    GrammarCategory.GRAM_CATEGORIES,
    GrammarCategory.INFLECTION_FEATURES,
    GrammarCategory.INFLECTION_CLASSES,
    GrammarCategory.STEM_NAMES,
    GrammarCategory.EXCEPTION_FEATURES,
    GrammarCategory.VARIANT_TYPES,
    GrammarCategory.COMPLEX_FORM_TYPES,
]

# Categories that are GOLD_RESERVED at Layer 1 (ADD_NEW hidden, OVERWRITE forbidden).
_GOLD_RESERVED = {
    GrammarCategory.GRAM_CATEGORIES,
    GrammarCategory.INFLECTION_FEATURES,
    GrammarCategory.VARIANT_TYPES,
    GrammarCategory.COMPLEX_FORM_TYPES,
    GrammarCategory.POS,
    GrammarCategory.PHONOLOGICAL_FEATURES,
    GrammarCategory.SEMANTIC_DOMAINS,
}

# CUSTOM_FIELDS: conservative (ADD hidden, OVERWRITE forbidden).
_CUSTOM_FIELDS_ONLY = {GrammarCategory.CUSTOM_FIELDS}

# All item category toggles (page 2 / 3).
_CATEGORY_TOGGLES = [
    GrammarCategory.POS,
    GrammarCategory.GRAM_CATEGORIES,
    GrammarCategory.INFLECTION_FEATURES,
    GrammarCategory.INFLECTION_CLASSES,
    GrammarCategory.STEM_NAMES,
    GrammarCategory.EXCEPTION_FEATURES,
    GrammarCategory.VARIANT_TYPES,
    GrammarCategory.COMPLEX_FORM_TYPES,
    GrammarCategory.ADHOC_COMPOUND_RULES,
    GrammarCategory.CUSTOM_FIELDS,
    GrammarCategory.AFFIXES,
    GrammarCategory.SLOTS,
    GrammarCategory.AFFIX_TEMPLATES,
]


# ---------------------------------------------------------------------------
# Layer-1 helper: which ConflictMode values are offered for a category?
# ---------------------------------------------------------------------------

def _count_says_content(count) -> bool:
    """Turn a cheap count into "show this page?" -- unknown means show.

    `None` out of `SourceCounts` means "could not be had cheaply", never "zero".
    Treating it as zero would skip a page whose contents were merely
    unmeasurable, which is the one direction FR-009c does not tolerate.
    """
    return True if count is None else count > 0


# ---------------------------------------------------------------------------
# T020/T021/T022 -- the one way a page reports a wait (FR-014..FR-023)
# ---------------------------------------------------------------------------
# EVERY one of the thirteen FR-023 operations goes through `_page_progress`.
# Written once because the decision it makes is the same everywhere and is easy
# to get subtly wrong per call site: which of FR-014's two triggers applies,
# and whether the indicator comes down on the failure path.
#
#   * the trigger is `warrants_indicator(total, rate)` and nothing else -- an
#     anticipated wait past the threshold is shown up front (FR-014a), and
#     everything else waits for the elapsed-time fallback (FR-014b). Whichever
#     fires first wins, so a mis-calibrated rate can only pick the wrong
#     trigger, never suppress the indicator.
#   * the label and the rate come from ONE lookup each, both keyed by the FR-023
#     operation name, so a page cannot name a row the calibration table has
#     never heard of (`label_for`/`rate_for` raise on a typo, at wiring time).
#   * `reporting()` owns the dismissal, so a walk that raises still takes its
#     indicator down (FR-020) and the error message the wizard shows next is
#     never trapped behind a modal corpse.


def _source_counts_of(page) -> SourceCounts:
    """The run's cheap-count snapshot, or the all-unknown one.

    A page is constructed standalone by a good deal of the test suite and by
    `_PagePreview`'s host, so `wizard()` may be None and a wizard may predate
    the snapshot. Unknown counts are the correct answer in both cases: they mean
    "no total", which is the indeterminate indicator, not a missing one.
    """
    wizard = page.wizard()
    getter = getattr(wizard, "source_counts", None)
    if getter is None:
        return SourceCounts.unknown()
    try:
        return getter()
    except Exception:  # noqa: BLE001 -- a count is never worth a failed page entry
        return SourceCounts.unknown()


@contextmanager
def _page_progress(page, operation: str, total: Optional[int] = None):
    """Report one FR-023 operation for the duration of the `with` block.

    `total` is a count the caller ALREADY HAS -- `SourceCounts` for the
    source-derived pages, a `len()` for the two selection-derived ones. It is
    never obtained by counting (FR-014d); that is the whole point of the
    snapshot, and a counting pass here would pay the cost the indicator exists
    to cover.

    Yields the sink, so the body ticks from inside its walk.
    """
    label = label_for(operation)
    if warrants_indicator(total, rate_for(operation)):
        sink = immediate(label, total, parent=page)     # FR-014a: up front
    else:
        sink = deferred(label, total, parent=page)      # FR-014b: after 500 ms
    with reporting(sink, label, total) as prog:
        yield prog


def _operation_failed_note(operation: str) -> str:
    """The one sentence a page says when its walk raised (T022, FR-020).

    Dismissing the indicator is half of FR-020; the other half is that the
    operator is TOLD. A page that quietly renders an empty tree is
    indistinguishable from a project that genuinely has nothing in it, and the
    two call for opposite responses -- so the failure gets its own words rather
    than the page's "nothing here" wording.

    Phrased from the operation's own label, so the sentence names the operation
    in the same vocabulary the indicator just used (FR-015), and no page invents
    a second name for the thing it was doing.
    """
    return (
        f"({label_for(operation).rstrip('. ')} failed. Nothing could be read "
        "from the source project -- see the GramTrans log for the reason.)"
    )


def _show_failure_row(tree, operation: str) -> None:
    """Replace a tree's contents with the single disabled row that explains why.

    Clearing first is the point: the affix and stem pages did not clear on the
    failure path, so a second visit to a page whose walk had just raised showed
    the PREVIOUS visit's rows as though they were current.
    """
    tree.clear()
    item = QtWidgets.QTreeWidgetItem(tree, [_operation_failed_note(operation)])
    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)


# ---------------------------------------------------------------------------
# Layer-1 helper: which ConflictMode values are offered for a category?
# ---------------------------------------------------------------------------

def _allowed_modes(cat: GrammarCategory) -> list:
    """Return the list of ConflictMode values offered for `cat` per Layer 1."""
    if cat in _CUSTOM_FIELDS_ONLY:
        # CUSTOM_FIELDS remains conservative (LINK-only); not a GOLD category.
        return [ConflictMode.LINK]
    # Constitution v7.0.0 GOLD unlock: GOLD_RESERVED categories are ordinary
    # items and offer the full mode set (default UPDATE via _DEFAULT_CONFLICT_MODES).
    return [ConflictMode.ADD_NEW, ConflictMode.LINK, ConflictMode.UPDATE, ConflictMode.OVERWRITE]


# ---------------------------------------------------------------------------
# Shared splitter helper (T004, FR-005, FR-011, R7)
# ---------------------------------------------------------------------------

def _make_tree_pane_splitter(tree_widget, pane_widget,
                             tree_stretch=3, pane_stretch=2):
    """Return a horizontal QSplitter with tree on the left and pane on the right.

    Replaces the direct layout.addWidget(tree, 1) call in each page's _build_ui.
    Stretch factors default to 3:2 (tree:pane) per plan R7.

    THE ONE PLACE A TREE-AND-PREVIEW PAGE IS MADE TO SURVIVE 900 PX
    ---------------------------------------------------------------
    Nine pages build their splitter here, so 036 T025/T026 are applied here
    rather than nine times. Three separate ways a narrowed window can eat a pane
    or a column, and the default Qt behaviour is wrong for all three:

    * **collapse** (FR-029a). A splitter that allows collapse lets the operator
      drag the preview to zero -- and lets Qt do it for them as the width runs
      out. `setChildrenCollapsible(False)` plus a real minimum on each pane is
      what makes "both panes side by side" survive the floor instead of
      depending on how wide the window happens to be.
    * **silent cut** (FR-029b). Cells elide right by default; column HEADINGS do
      not, so a heading too wide for its section is chopped today with nothing
      to say it was. An unindicated cut is worse than a narrow column: the
      operator cannot tell there is more.
    * **a scrollbar instead of an ellipsis** (FR-029b). A view left on
      `ScrollBarAsNeeded` answers a too-narrow column by growing a horizontal
      bar, which is the thing FR-029b forbids the page acquiring. The ellipsis
      and the no-scrollbar clause are one decision, so they are made together.
    """
    splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
    splitter.addWidget(tree_widget)
    splitter.addWidget(pane_widget)
    splitter.setStretchFactor(0, tree_stretch)
    splitter.setStretchFactor(1, pane_stretch)
    # T025 / FR-029a.
    splitter.setChildrenCollapsible(False)
    tree_widget.setMinimumWidth(_TREE_PANE_MIN_WIDTH)
    pane_widget.setMinimumWidth(_PREVIEW_PANE_MIN_WIDTH)
    # T026 / FR-029b. The left pane is a view on every page that calls this, but
    # the guard keeps the helper usable for a page whose left half is not one.
    for view in _item_views_of(tree_widget):
        _elide_over_narrow_columns(view)
    return splitter


def _item_views_of(widget):
    """`widget` itself if it is an item view, plus any view nested inside it.

    A page that wraps its tree in a frame still has the view FR-029b means, and
    a page that hands its tree over directly is the common case. Both are
    reached the same way so neither has to be special-cased at the call site.
    """
    views = []
    if isinstance(widget, QtWidgets.QAbstractItemView):
        views.append(widget)
    views.extend(
        v for v in widget.findChildren(QtWidgets.QAbstractItemView)
        if v not in views
    )
    return views


def _elide_over_narrow_columns(view) -> None:
    """Make one item view shorten over-narrow content instead of cutting it.

    Separate from the splitter factory so a view built outside a tree-and-preview
    page can be given the same treatment by name rather than by copying three
    property calls.
    """
    elide_right = QtCore.Qt.TextElideMode.ElideRight
    view.setTextElideMode(elide_right)
    view.setHorizontalScrollBarPolicy(
        QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    header = getattr(view, "header", None)
    header = header() if callable(header) else None
    if header is not None:
        # The half Qt does not do for itself: QHeaderView defaults to ElideNone.
        header.setTextElideMode(elide_right)


def _set_item_text_with_tooltip(item, column: int, text: str) -> None:
    """Set a cell's text and record the untruncated value as its tooltip.

    FR-029b has two halves and Qt supplies only the first: it draws the ellipsis,
    and nothing in it keeps the string that was elided. The tooltip is the "full
    value remains available on demand" channel, and it exists only if something
    sets it -- so this is the one place a cell's text and its full-value tooltip
    are set together, exactly as `_make_tree_pane_splitter` is the one place a
    splitter is built.

    The MODEL keeps the untruncated value. Baking an ellipsis into the data would
    corrupt the value FR-034 requires be preserved exactly, and would make the
    truncation permanent rather than a property of the current column width.
    """
    item.setText(column, text)
    item.setToolTip(column, text)


def _carry_full_values_in_tooltips(tree) -> None:
    """Give every populated cell a tooltip holding its own untruncated text.

    The other half of FR-029b, applied to trees that were populated by the nine
    `_populate_*` methods rather than through `_set_item_text_with_tooltip`. One
    sweep at the end of population is what makes the ellipsis stand IN FOR the
    value instead of hiding it, without rewriting every row-building loop in the
    module to thread a tooltip through.

    Signals are blocked for the duration, and that is load-bearing, not
    defensive: `setToolTip` on a `QTreeWidgetItem` emits `itemChanged`, and the
    pages connect `itemChanged` to check-state mirroring. An unblocked sweep
    would look to those handlers exactly like the operator ticking every box on
    the page.

    Only empty tooltips are filled, so a cell that already carries a richer
    tooltip (a status explanation, say) keeps it.
    """
    blocked = tree.signalsBlocked()
    tree.blockSignals(True)
    try:
        columns = tree.columnCount()
        iterator = QtWidgets.QTreeWidgetItemIterator(tree)
        while iterator.value() is not None:
            item = iterator.value()
            for column in range(columns):
                text = item.text(column)
                if text and not item.toolTip(column):
                    item.setToolTip(column, text)
            iterator += 1
    except Exception:  # noqa: BLE001 -- a tooltip is never worth a failed page
        pass
    finally:
        tree.blockSignals(blocked)


# ---------------------------------------------------------------------------
# Flow-aware page base (T013, FR-009b)
# ---------------------------------------------------------------------------

class _FlowPage(QtWidgets.QWizardPage):
    """A page that resolves its successor from `SelectionWizard.flow()`.

    WHY `nextId()` AND NOT A FILTERED PAGE LIST
    -------------------------------------------
    `QWizardPage.nextId()` is Qt's own hook for a conditional flow, and Qt calls
    it to decide whether Next is even *enabled*. Resolving the successor here
    means the button is right before the click, rather than the alternative --
    registering only the pages a run "will" need, which has to guess before the
    operator has picked anything and cannot change its mind afterwards.

    Back needs nothing: Qt replays its own stack of visited pages, so an
    operator returning through a run that skipped pages retraces exactly the
    pages they saw.

    `flow()` is read at CALL TIME, never cached. The operator may go back and
    pick an affix after Morphology Skeleton was skipped for having none, and the
    page then re-enters the flow -- a baked list could not.
    """

    # -- The page header (T041, FR-004 / FR-012) ---------------------------
    # Every page in the flow carries one. `subTitle()` stays the string of
    # record -- the wizard sets `IgnoreSubTitles` so Qt stops drawing it, and
    # the header renders it instead in a label that WRAPS. Qt's own subtitle
    # does not wrap: it elides, which is how a description could end mid-word
    # with nothing to say it had been cut (FR-013).

    def header(self):
        """This page's laid-out header row, or None before one is installed.

        Returns None rather than raising for a page constructed standalone --
        a good deal of the unit suite builds pages with no wizard at all, and
        a header is something the wizard installs, not something a page makes
        for itself.
        """
        return getattr(self, "_page_header", None)

    def install_header(self, header) -> None:
        """Adopt `header` as row 0 of this page's own layout.

        Laid out, never positioned. That is the whole of FR-004: a box layout
        allocates disjoint x-intervals to the description and the controls, so
        a description grown to any wrapped height cannot intersect the strip --
        it grows the header's height instead. The floating bar this replaces
        had no layout relationship with anything, so nothing could move out of
        its way and it painted an opaque background to stay legible on top of
        whatever it covered.

        Idempotent: installing twice on one page is a no-op, so a second call
        cannot stack two header rows.
        """
        if getattr(self, "_page_header", None) is not None:
            return
        layout = self.layout()
        if layout is None:
            return
        self._page_header = header
        header.setParent(self)
        insert = getattr(layout, "insertWidget", None)
        if callable(insert):
            insert(0, header)
        else:                       # not a box layout: better appended than lost
            layout.addWidget(header)
        header.set_description(self.subTitle())

    def refresh_header_description(self) -> None:
        """Re-render `subTitle()` into the header. Cheap; safe before install.

        Called on page entry because `subTitle()` is not frozen at construction
        -- the Finish page takes its subtitle from the host's confirmation gate,
        and a page may restate itself in `initializePage`.
        """
        header = self.header()
        if header is not None:
            header.set_description(self.subTitle())

    def nextId(self) -> int:  # noqa: N802 -- Qt naming
        """The next page this run will SHOW, or -1 to end the run.

        Walks the declaration forward from this page and returns the first entry
        that is either unskippable or whose `has_content()` says yes. A
        predicate that raises is treated as "yes" for the same reason `None` is
        (FR-009c): a page that is wrongly shown costs a click, a page that is
        wrongly skipped costs a decision.
        """
        wizard = self.wizard()
        if wizard is None or not hasattr(wizard, "flow"):
            # Constructed standalone (several unit tests do) or hosted by a
            # wizard that predates the declaration: fall back to Qt's
            # registration order rather than refusing to navigate.
            return super().nextId()
        entries = list(wizard.flow())
        here = -1
        for idx, (attr, _short, _skippable, _has) in enumerate(entries):
            if getattr(wizard, attr, None) is self:
                here = idx
                break
        if here == -1:
            return super().nextId()

        for attr, _short, skippable, has_content in entries[here + 1:]:
            page_id = wizard.flow_page_id(attr)
            if page_id == -1:
                continue                    # declared but not registered
            if not skippable or has_content is None:
                return page_id              # FR-009d outranks any emptiness
            try:
                if has_content():
                    return page_id
            except Exception:  # noqa: BLE001 -- unsure means shown
                return page_id
        return -1                           # last shown page ends the run


# ---------------------------------------------------------------------------
# Page 1 -- Projects  (feature 036 T010, FR-006/FR-007)
# ---------------------------------------------------------------------------
# WHY THIS PAGE IS NO LONGER "Project + Writing Systems"
# -----------------------------------------------------
# One page used to ask two unrelated questions: which two projects, and how
# every source writing system maps into the target. The second question is
# answerable only *after* the first, so the WS tables sat empty for the whole
# time the operator was reading the page they were on -- and the page's
# subtitle promised a table that was not usable yet. Feature 036 FR-006 splits
# them: this page binds a pair of projects and nothing else, and
# `_PageWritingSystems` (the step after it) owns the mapping and repopulates
# itself from the two bound handles on every entry.
#
# The accessor name `page_project_ws()` is deliberately NOT renamed: 25 call
# sites across this module and the test suite reach the source handle and the
# bound context through it, and renaming a name that still means the same thing
# ("the page that owns the projects") would be churn with no reader benefit.
# The *attribute* behind it is `_page_projects`.


class _PageProjects(_FlowPage):
    """Page 1: bind the source + target projects. Nothing else.

    Under FlexTools the source is already bound (the host's open project,
    passed in at wizard construction time) and the user picks only the target.

    A host with no open project -- the standalone -- passes a `source_binder`,
    and the source becomes a picked project too: the Source row grows a "Pick
    source project..." button that mirrors the Target row's, using the twin
    dialog in `source_picker.py` (feature 034 exception 7). This page is then
    the application's entry point, which is why the choice lives here rather
    than in a separate dialog the host throws up before the wizard opens.

    Same-project is refused in both directions: the source's own project is
    excluded from `list_target_candidates` and refused by `bind_target`, and a
    bound target is excluded from the source list. Re-picking the source
    releases a bound target, because everything downstream -- the writing-system
    mapping on the next page most of all -- is a statement about a *pair* of
    projects and cannot outlive either half.

    Advancing off this page requires BOTH handles (FR-008). Two mechanisms,
    deliberately, because they say different things: the `target_ready*`
    required field greys the Next button, and `validatePage()` plus the inline
    reason label say *why* on the page itself. A greyed button with no
    explanation is the defect FR-008 names.
    """

    def __init__(self, stub, host_project, parent=None, *,
                 source_binder=None, report_sink=None):
        super().__init__(parent)
        self._stub = stub
        self._host = host_project
        # Feature 034 exception 7. `None` (every FlexTools construction) means
        # "the source is host-supplied": no button, no picker, no behaviour
        # change. Callable means "this host has no source of its own"; it takes
        # a project name and returns an open read-only handle. The host keeps
        # ownership of that handle, because the host is what has to close it.
        self._source_binder = source_binder
        self._report = report_sink
        self._context = None   # set when target is bound

        # Unnumbered here on purpose: the run's flow assigns the number on
        # entry (`SelectionWizard._apply_step_number`), because a position is a
        # fact about a *run* and this class cannot know one. The literal that
        # used to be here claimed a total of ten while eleven pages were
        # registered -- the total was already a lie before any page was skipped.
        # (The literal itself is banned from this file by a source-level test,
        # which is why even a comment does not spell one out.)
        self.setTitle("Projects")
        self.setSubTitle(
            (
                "Pick the source project to read from and the target project "
                "to write to. Both are required before you can continue."
            )
            if source_binder is not None else
            # Under FlexTools the source is not picked, so the page describes
            # exactly one choice and must not invite the operator to change a
            # project the host owns (SC-013).
            "Bind the target project to write to. The source project is "
            "already open and cannot be changed here."
        )
        self._build_ui()
        self.registerField("target_ready*", self, "target_ready_prop",
                            self.target_ready_changed)

    # Qt property for the required-field completion gate.
    _target_ready = False
    target_ready_changed = QtCore.pyqtSignal()

    @QtCore.pyqtProperty(bool, notify=target_ready_changed)
    def target_ready_prop(self) -> bool:
        return self._target_ready

    def _set_target_ready(self, val: bool) -> None:
        if val != self._target_ready:
            self._target_ready = val
            self.target_ready_changed.emit()
            self.completeChanged.emit()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        # The two project rows are built the same way on purpose: same layout,
        # same label-then-button shape, same dialog mechanics. The only
        # difference is that the Source row's button exists solely for a host
        # that does not supply a source (feature 034 exception 7).
        src_row = QtWidgets.QHBoxLayout()
        src_row.addWidget(QtWidgets.QLabel("Source:", self))
        self._src_label = QtWidgets.QLabel(self._initial_source_text(), self)
        src_row.addWidget(self._src_label, 1)
        self._pick_source_btn = None
        if self._source_binder is not None:
            self._pick_source_btn = QtWidgets.QPushButton(
                "Pick source project...", self
            )
            self._pick_source_btn.clicked.connect(self._on_pick_source)
            src_row.addWidget(self._pick_source_btn)
        layout.addLayout(src_row)

        tgt_row = QtWidgets.QHBoxLayout()
        tgt_row.addWidget(QtWidgets.QLabel("Target:", self))
        self._tgt_label = QtWidgets.QLabel("<i>(not picked)</i>", self)
        tgt_row.addWidget(self._tgt_label, 1)
        self._pick_target_btn = QtWidgets.QPushButton("Pick target project...", self)
        self._pick_target_btn.clicked.connect(self._on_pick_target)
        tgt_row.addWidget(self._pick_target_btn)
        layout.addLayout(tgt_row)
        # Target-after-source is not a preference, it is what makes the
        # same-project rule enforceable by *omission*: the target list is built
        # by excluding the source, so there has to be a source first. Disabled
        # only in the deferred-source case; under FlexTools there always is one.
        if not self._source_is_bound():
            self._pick_target_btn.setEnabled(False)
            self._pick_target_btn.setToolTip(
                "Pick the source project first — the target list is everything "
                "except the source."
            )

        # T011 / FR-008: the refusal, stated on the page. A disabled Next button
        # is the *consequence* of a missing binding, not an explanation of it;
        # an operator who cannot see which of the two halves is missing has to
        # guess. Updated by `_refresh_reason` on every binding change, and read
        # back by `validatePage()` so the two can never disagree.
        self._reason_label = QtWidgets.QLabel("", self)
        self._reason_label.setWordWrap(True)
        layout.addWidget(self._reason_label)
        layout.addStretch(1)
        self._refresh_reason()

    # ------------------------------------------------------------------
    # The advance gate (T011, FR-008)
    # ------------------------------------------------------------------

    def _missing_binding_reason(self) -> str:
        """Why this page will not advance, or "" when it will.

        Names the half that is missing rather than the pair, because "pick your
        projects" is not actionable to someone who has already picked one.
        """
        if not self._source_is_bound():
            if self._source_binder is None:
                # FlexTools with no open project: the operator cannot fix this
                # from here, so say where it is fixed.
                return ("No source project is open. GramTrans reads grammar "
                        "from the project open in FieldWorks; open one and run "
                        "GramTrans again.")
            return "Pick the source project to read from."
        if self._context is None:
            return "Pick the target project to write to."
        return ""

    def _refresh_reason(self) -> None:
        """Show or clear the inline reason. Never raises: it is only a label."""
        label = getattr(self, "_reason_label", None)
        if label is None:
            return
        reason = self._missing_binding_reason()
        label.setText(f"<i>{reason}</i>" if reason else "")
        label.setVisible(bool(reason))

    def validatePage(self) -> bool:
        """Refuse to advance until BOTH projects are bound (FR-008).

        `target_ready*` already greys Next, so this hook is not what stops a
        click in the normal case -- it is what stops every *other* way forward
        (Enter on a focused field, a programmatic `next()`, a future Commit
        button).

        No dialog: the reason is already on the page, and a modal that repeats
        a sentence the operator can see would be the third window feature 034
        removed. `_refresh_reason` is re-run here so the label cannot be stale
        at the moment the refusal happens.
        """
        reason = self._missing_binding_reason()
        self._refresh_reason()
        return not reason

    # ------------------------------------------------------------------
    # Source binding (feature 034 exception 7)
    # ------------------------------------------------------------------

    def _source_is_bound(self) -> bool:
        return bool(getattr(self._stub, "source_project_name", ""))

    def _initial_source_text(self) -> str:
        if not self._source_is_bound():
            return "<i>(not picked)</i>"
        if self._source_binder is None:
            # FlexTools: unchanged wording, because there it is the truth.
            return f"<b>{self._stub.source_project_name}</b> (open in FlexTools)"
        return f"<b>{self._stub.source_project_name}</b> (read-only)"

    def _on_pick_source(self) -> None:
        """Pick + open the source, mirroring `_on_pick_target` step for step."""
        if self._source_binder is None:      # defensive: no button exists
            return
        if self._context is not None and not self._confirm_release_target():
            return

        candidates = gt_api.list_source_candidates(
            getattr(self._stub, "projects_root", ""),
            # The other half of the same-project rule. `list_target_candidates`
            # excludes the source; this excludes a target already bound, so the
            # pair can never collapse onto one project from either direction.
            exclude_names=tuple(
                n for n in (self._bound_target_name(),) if n
            ),
            exclude_paths=tuple(
                p for p in (self._bound_target_path(),) if p
            ),
        )
        dlg = SourcePickerDialog(candidates, parent=self)
        if not candidates:
            # Show the dialog anyway: its empty-list message says what to do,
            # where a QMessageBox here would say it in a different voice.
            dlg.exec()
            return
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        choice = dlg.selected_candidate()
        if choice is None:
            return

        # FR-023 row 1. No cheap total exists -- nothing can be counted before
        # the project is open -- so this is the elapsed-time trigger by
        # construction (FR-014b/FR-014d): indeterminate, and shown only if
        # opening takes longer than the threshold. `_page_progress` reads that
        # off `rate_for("bind_source") is None`, so the choice is declared in the
        # calibration table rather than repeated here.
        try:
            with _page_progress(self, "bind_source"):
                handle = self._source_binder(choice.project_name)
        except Exception as exc:  # noqa: BLE001 -- LCM raises a variety of types
            # FR-034: attributed to the project that would not open, with the
            # rest of the list still choosable.
            QtWidgets.QMessageBox.critical(
                self, "GramTrans",
                f"GramTrans could not open {choice.project_name!r} as the "
                f"source project.\n\nIf it is open in FieldWorks Language "
                f"Explorer, close it and try again, or choose a different "
                f"project.\n\nDetails: {exc!s}",
            )
            self._log(f"[GramTrans] Could not open source "
                      f"{choice.project_name!r}: {exc}", error=True)
            return

        self._release_bound_target()
        self._bind_source_handle(handle, choice.project_name, choice.project_path)

    def _bind_source_handle(self, handle, project_name: str,
                            project_path: str) -> None:
        """Adopt an opened source handle: stub, labels, and the wizard's `_host`.

        `dataclasses.replace` rather than a fresh `initialize_run` so `run_id`
        and `started_at` survive re-picking. They are stamped into the residue
        tag of everything a Move writes, and a run that changed its identity
        halfway through choosing projects would be untraceable afterwards.
        """
        import dataclasses

        self._host = handle
        self._stub = dataclasses.replace(
            self._stub,
            source_handle=handle,
            source_project_name=project_name,
            source_project_path=project_path,
        )
        # Same shape as the target row's label, so the pair reads as a pair.
        if project_path:
            self._src_label.setText(
                f"<b>{project_name}</b> (read-only) (<code>{project_path}</code>)"
            )
        else:
            self._src_label.setText(f"<b>{project_name}</b> (read-only)")
        # Downstream pages resolve the source through `wizard._host` (or through
        # the bound context); keep the wizard's copy in step with ours.
        wizard = self.wizard()
        if wizard is not None:
            wizard._host = handle
            # T014: the ONE place a bind refreshes the cheap-count snapshot the
            # page-skip predicates read. Doing it here, at the bind, is what
            # keeps `nextId()` free of project queries (D5b).
            if hasattr(wizard, "refresh_source_counts"):
                wizard.refresh_source_counts(handle)
        self._pick_target_btn.setEnabled(True)
        self._pick_target_btn.setToolTip("")
        self._refresh_reason()
        self._log(f"  Source (read-only): {project_name!r}")

    def _confirm_release_target(self) -> bool:
        """Changing the source after a target is bound: ask, then release.

        The writing-system mapping, and every inventory the later pages build,
        are statements about a *pair* of projects. Silently keeping the target
        bound while the source changes underneath it would leave the WS table
        describing a pairing that no longer exists.
        """
        answer = QtWidgets.QMessageBox.question(
            self, "GramTrans — Change the source project?",
            f"{self._bound_target_name() or 'The target project'} is currently "
            "bound as the target.\n\nChanging the source releases it and clears "
            "your writing-system choices, and you will need to pick the target "
            "again.\n\nChange the source anyway?",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        return answer == QtWidgets.QMessageBox.StandardButton.Yes

    def _release_bound_target(self) -> None:
        """Close a previously-bound target and reset everything that named it.

        `CloseProject()` matters here and is not merely tidy: `bind_target`
        opened it write-enabled, so a dropped handle would leave the project
        locked for the rest of the process with nothing left holding a
        reference to unlock it. `gramtrans.py._run_gui` only ever closes the
        *current* context's handle.
        """
        ctx = self._context
        if ctx is None:
            return
        target = getattr(ctx, "target_handle", None)
        name = getattr(ctx, "target_project_name", "")
        self._context = None
        if target is not None:
            try:
                target.CloseProject()
                self._log(f"[GramTrans] Target project {name!r} released "
                          "(source changed).")
            except Exception as exc:  # noqa: BLE001
                self._log(f"[GramTrans] Could not close target project "
                          f"{name!r}: {exc}", warning=True)
        self._tgt_label.setText("<i>(not picked)</i>")
        self._set_target_ready(False)
        self._refresh_reason()
        # The WS row state that named the released target is NOT cleared from
        # here any more, and must not be: after the FR-006 split this page has
        # no reference to those tables. `_PageWritingSystems.initializePage`
        # rebuilds them from scratch on every entry, so a released project's
        # rows cannot survive into the next visit (data-model s1 edge case).
        # Clearing across the split would be a second owner of the same state.

    def _bound_target_name(self) -> str:
        return getattr(self._context, "target_project_name", "") \
            if self._context is not None else ""

    def _bound_target_path(self) -> str:
        return getattr(self._context, "target_project_path", "") \
            if self._context is not None else ""

    def _log(self, message: str, *, warning: bool = False,
             error: bool = False) -> None:
        """Best-effort line to the host's report sink; never raises."""
        sink = self._report
        if sink is None:
            return
        try:
            if error:
                sink.Error(message)
            elif warning:
                sink.Warning(message)
            else:
                sink.Info(message)
        except Exception:  # noqa: BLE001 -- logging must not break the picker
            pass

    # ------------------------------------------------------------------
    def _on_pick_target(self) -> None:
        if not self._source_is_bound():
            QtWidgets.QMessageBox.information(
                self, "GramTrans",
                "Pick the source project first. GramTrans copies grammar from "
                "one project into another, so the target list is everything "
                "except the source.",
            )
            return
        candidates = gt_api.list_target_candidates(self._stub)
        if not candidates:
            QtWidgets.QMessageBox.warning(
                self,
                "GramTrans",
                "No candidate target projects found in the FieldWorks projects directory.",
            )
            return
        dlg = TargetPickerDialog(candidates, parent=self)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        choice = dlg.selected_candidate()
        if choice is None:
            return
        # FR-023 row 2. Same shape as the source bind above, and the same reason:
        # a project has no cheap size until it is open.
        try:
            with _page_progress(self, "bind_target"):
                self._context = gt_api.bind_target(self._stub, choice)
        except gt_api.SameProjectError as e:
            QtWidgets.QMessageBox.critical(self, "GramTrans", str(e))
            return
        except gt_api.TargetUnavailable as e:
            QtWidgets.QMessageBox.critical(self, "GramTrans", str(e))
            return
        self._tgt_label.setText(
            f"<b>{choice.project_name}</b> (<code>{choice.project_path}</code>)"
        )
        # The target WS enumeration and the MAP/CREATE/SKIP tables used to be
        # built from here, on this page. They now belong to the step after this
        # one, which enumerates on `initializePage` from the two handles this
        # page bound -- so binding a target no longer pays for a WS walk the
        # operator may never look at (FR-006).
        self._set_target_ready(True)
        self._refresh_reason()

    def context(self):
        return self._context

    def isComplete(self) -> bool:
        return self._target_ready


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


# ---------------------------------------------------------------------------
# Item-data roles used throughout _PageItemPicker
# ---------------------------------------------------------------------------

_GUID_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1   # entry_guid string
_KIND_ROLE = QtCore.Qt.ItemDataRole.UserRole + 2   # "affix" | "pos_group" | "subgroup"
_ROLE_ROLE = QtCore.Qt.ItemDataRole.UserRole + 3   # "attaches" | "produces" (leaf rows)
_IS_PRODUCES = QtCore.Qt.ItemDataRole.UserRole + 4  # bool: True for deriv_produces rows
# T005 -- Data roles for _PageItemPicker (FR-010, R6)
_ITEM_STATUS_ROLE = QtCore.Qt.ItemDataRole.UserRole + 30  # "new" | "in_target" | "similar"
_ITEM_CAT_ROLE    = QtCore.Qt.ItemDataRole.UserRole + 31  # GrammarCategory


# ---------------------------------------------------------------------------
# Page 2 -- Item picker (POS-grouped, specs/008-affix-pos-picker)
# ---------------------------------------------------------------------------

def _count_affixes_in_node(pos_node) -> int:
    """Return the count of distinct affix entry_guids in pos_node's whole subtree.

    Counts guids in inflectional + deriv_attaches + deriv_produces at this
    node and recursively in all children.  Deduplicates across sub-lists so
    an entry appearing in multiple subgroups of the same node is counted once.
    Used by FR-017(b) to annotate POS group header labels.
    """
    guids: Set[str] = set()

    def _collect(node) -> None:
        for row in node.inflectional:
            guids.add(row.entry_guid)
        for row in node.deriv_attaches:
            guids.add(row.entry_guid)
        for row in node.deriv_produces:
            guids.add(row.entry_guid)
        for child in node.children:
            _collect(child)

    _collect(pos_node)
    return len(guids)


def _make_group_item(parent, label: str, *,
                     kind: str, checkable: bool,
                     is_produces_group: bool) -> "QtWidgets.QTreeWidgetItem":
    """Create a group/header tree item (shared by the affix + stem pickers).

    FR-017(c): header rows (pos_group and subgroup) are styled with bold
    font so they are visually distinct from leaf rows.
    """
    # 5 columns: label, type, from, to, target (blank for headers)
    item = QtWidgets.QTreeWidgetItem(parent, [label, "", "", "", ""])
    item.setData(0, _KIND_ROLE, kind)
    item.setData(0, _IS_PRODUCES, is_produces_group)
    if checkable:
        item.setFlags(
            item.flags()
            | QtCore.Qt.ItemFlag.ItemIsUserCheckable
            | QtCore.Qt.ItemFlag.ItemIsAutoTristate
        )
        item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
    # FR-017(c): bold font for all header/group rows
    bold_font = item.font(0)
    bold_font.setBold(True)
    item.setFont(0, bold_font)
    return item


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


# ---------------------------------------------------------------------------
# Page 3 -- Schema scope + conflict mode
# ---------------------------------------------------------------------------

class _PageScopeConflict(QtWidgets.QWizardPage):
    """Per-category three-scope selector + conflict mode. NOT IN THE FLOW.

    Retained for back-compat and constructed by the wizard, but absent from
    `SelectionWizard.flow()` and therefore never registered (conflict UI
    deferred, FR-012). It is the reason FR-011 exists: its title claimed a
    position in a five-step flow for as long as the flow had ten steps,
    because nothing numbered it and nothing renumbered it either. Permanent exclusion and
    per-run skipping now use the same mechanism -- absence from `flow()` --
    so an unreachable page cannot acquire a number it never shows.

    Re-hosts the existing scope-combo controls from main_window and adds
    per-category ConflictMode selectors gated by the Layer-1 kind table.

    The LINK control carries an explicit label ("link existing by ID, else
    add; no field update") per spec section (i) (022: renamed from MERGE).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # T015 / FR-011: the stale step-number-and-total is REMOVED, not
        # renumbered. This page is in no run, so it has no position to state.
        self.setTitle("Schema Scope + Conflict Mode")
        self.setSubTitle(
            "For each schema category, choose how much to transfer (NONE / AS-NEEDED / ALL) "
            "and what to do when a source item already exists in the target."
        )
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QtWidgets.QVBoxLayout(self)

        # --- Category toggles (which categories to transfer at all) ---
        toggles_group = QtWidgets.QGroupBox("Grammar piece categories to transfer", self)
        toggles_layout = QtWidgets.QGridLayout(toggles_group)
        self._toggles: dict = {}
        for i, cat in enumerate(_CATEGORY_TOGGLES):
            cb = QtWidgets.QCheckBox(cat.value.replace("_", " "), toggles_group)
            toggles_layout.addWidget(cb, i // 3, i % 3)
            self._toggles[cat] = cb
        outer.addWidget(toggles_group)

        # --- Per-schema-category scope + conflict mode combos ---
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(container)
        grid.addWidget(QtWidgets.QLabel("<b>Category</b>", container), 0, 0)
        grid.addWidget(QtWidgets.QLabel("<b>Scope</b>", container), 0, 1)
        grid.addWidget(QtWidgets.QLabel("<b>Conflict mode</b>", container), 0, 2)

        self._scope_combos: dict = {}
        self._conflict_combos: dict = {}
        for row_i, cat in enumerate(_SCHEMA_CATEGORIES, start=1):
            grid.addWidget(
                QtWidgets.QLabel(cat.value.replace("_", " ") + ":", container),
                row_i, 0,
            )

            scope_cb = QtWidgets.QComboBox(container)
            for scope in (CategoryScope.NONE, CategoryScope.AS_NEEDED, CategoryScope.ALL):
                scope_cb.addItem(_SCOPE_LABELS[scope], scope)
            scope_cb.setCurrentIndex(1)  # AS_NEEDED default
            grid.addWidget(scope_cb, row_i, 1)
            self._scope_combos[cat] = scope_cb

            conflict_cb = QtWidgets.QComboBox(container)
            for mode in _allowed_modes(cat):
                conflict_cb.addItem(_CONFLICT_LABELS[mode], mode)
            # Default: Layer-1 default mode
            default_mode = _DEFAULT_CONFLICT_MODES.get(cat, ConflictMode.LINK)  # 022: LINK as ultimate fallback
            for idx in range(conflict_cb.count()):
                if conflict_cb.itemData(idx) == default_mode:
                    conflict_cb.setCurrentIndex(idx)
                    break
            grid.addWidget(conflict_cb, row_i, 2)
            self._conflict_combos[cat] = conflict_cb

        scroll.setWidget(container)
        outer.addWidget(scroll, 1)

        # Legacy closure checkbox (back-compat fallback)
        self._closure_cb = QtWidgets.QCheckBox(
            "Include dependency closure (legacy fallback; per-category scopes above take precedence)",
            self,
        )
        self._closure_cb.setChecked(True)
        outer.addWidget(self._closure_cb)

    # ------------------------------------------------------------------
    def collect_selection(self, picker_state: PickerState,
                          inventory: SourceAffixInventory) -> Selection:
        """Build a Selection from this page's current UI state."""
        cats = {cat: True for cat, cb in self._toggles.items() if cb.isChecked()}
        category_scopes = {}
        for cat, combo in self._scope_combos.items():
            scope = combo.currentData()
            if scope is not None:
                category_scopes[cat] = scope
        category_conflict_modes = {}
        for cat, combo in self._conflict_combos.items():
            mode = combo.currentData()
            if mode is not None:
                category_conflict_modes[cat] = mode

        return build_selection(
            picker_state,
            inventory,
            include_closure=self._closure_cb.isChecked(),
            extra_categories=list(cats.keys()),
            category_scopes=category_scopes,
        )._replace_conflict_modes(category_conflict_modes)  # helper below


# ---------------------------------------------------------------------------
# Data roles for _PageSkeleton and _PageGramDeps trees
# ---------------------------------------------------------------------------

_SKEL_GUID_ROLE = QtCore.Qt.ItemDataRole.UserRole + 10   # slot/tpl/pos guid
_SKEL_KIND_ROLE = QtCore.Qt.ItemDataRole.UserRole + 11   # "pos"|"slot"|"template"|"dep"
_SKEL_READ_ONLY = QtCore.Qt.ItemDataRole.UserRole + 12   # bool: template slot entry
# T006 -- Data roles for _PageSkeleton (FR-010, R6)
_SKEL_STATUS_ROLE = QtCore.Qt.ItemDataRole.UserRole + 40  # "new" | "in_target" | "similar"
_SKEL_CAT_ROLE    = QtCore.Qt.ItemDataRole.UserRole + 41  # GrammarCategory (slot / template)
_SKEL_OWNER_ROLE  = QtCore.Qt.ItemDataRole.UserRole + 42  # owner POS GUID (for template/slot preview)
# T007 -- Data roles for _PageGramDeps (FR-010, R6)
# GrammarCategory mapping (research: _populate_deps_tree sections):
#   "Inflection Features" -> GrammarCategory.INFLECTION_FEATURES
#   "Inflection Classes"  -> GrammarCategory.INFLECTION_CLASSES
#   "Stem Names"          -> GrammarCategory.STEM_NAMES
_DEPS_STATUS_ROLE = QtCore.Qt.ItemDataRole.UserRole + 50  # "new" | "in_target" | "similar"
_DEPS_CAT_ROLE    = QtCore.Qt.ItemDataRole.UserRole + 51  # GrammarCategory

# Target-status label map (shared with affix picker).
_STATUS_LABELS = {
    "new": "NEW",
    "in_target": "IN TARGET",
    "similar": "SIMILAR",
}


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


# ---------------------------------------------------------------------------
# Page 2 -- Custom Fields  (Feature 016, US1/US2/US4)
# ---------------------------------------------------------------------------

# Data roles for _PageCustomFields
_CF_GUID_ROLE   = QtCore.Qt.ItemDataRole.UserRole + 60  # synthetic "cf:<owner>:<name>" guid
_CF_KIND_ROLE   = QtCore.Qt.ItemDataRole.UserRole + 61  # "group" | "item"
_CF_STATUS_ROLE = QtCore.Qt.ItemDataRole.UserRole + 63  # "NEW" | "IN TARGET" | ""

# Display labels for the four owner-class levels.
_CF_LEVEL_LABELS = {
    "LexEntry":           "Entry",
    "LexSense":           "Sense",
    "LexExampleSentence": "Example",
    "MoForm":             "Allomorph",
}


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
                custom_field_type_label,
                classify_custom_field,
            )
        else:
            from categories import (  # type: ignore
                _enumerate_custom_fields,
                custom_field_type_label,
                classify_custom_field,
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


# ---------------------------------------------------------------------------
# Page 3 -- Phonology  (spec 010, Model-B independent block)
# ---------------------------------------------------------------------------

_PHON_GUID_ROLE = QtCore.Qt.ItemDataRole.UserRole + 20   # source GUID (item rows)
_PHON_KIND_ROLE = QtCore.Qt.ItemDataRole.UserRole + 21   # "group" | "item"
_PHON_CAT_ROLE = QtCore.Qt.ItemDataRole.UserRole + 22    # GrammarCategory (group + item)
# T008 -- Data role for _PagePhonology (FR-010, R6)
_PHON_STATUS_ROLE = QtCore.Qt.ItemDataRole.UserRole + 23  # "new" | "in_target" | "similar"

# SC-008: module-level aliases used inside _PagePhonology instead of string literals.
_PHON_MODE_OVERWRITE = OVERWRITE
_PHON_MODE_NEW = NEW

# ---------------------------------------------------------------------------
# Data roles for _PageRules (018-rules-page T017)
# ---------------------------------------------------------------------------

_RULES_GUID_ROLE   = QtCore.Qt.ItemDataRole.UserRole + 70  # normalized rule GUID (item rows)
_RULES_KIND_ROLE   = QtCore.Qt.ItemDataRole.UserRole + 71  # "group" | "item"
_RULES_STATUS_ROLE = QtCore.Qt.ItemDataRole.UserRole + 72  # "NEW" | "IN TARGET" | "SIMILAR" | ""

# Status display map shared with phonology convention
_RULES_STATUS_LABELS = {
    "NEW": "NEW",
    "IN TARGET": "IN TARGET",
    "SIMILAR": "SIMILAR",
    "": "",
}


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
# Shared phonology EXCLUDED-LOSSY channel (spec 010 US5 — T024/T025/T026b)
# ---------------------------------------------------------------------------

def _phonology_nc_or_phoneme_trimmed(inventory, checked_by_category) -> bool:
    """True iff the user deselected any NC or phoneme (KL-010-1 guard input)."""
    for cat in (GrammarCategory.NATURAL_CLASSES, GrammarCategory.PHONEMES):
        grp = inventory.group_for(cat)
        if grp is None:
            continue
        all_guids = {r.guid for r in grp.rows}
        if all_guids - set(checked_by_category.get(cat, set())):
            return True
    return False


def _kl010_notice(inventory, checked_rule_guids) -> ExcludedLossy:
    """Coarse Principle-V notice for a kept metathesis/reduplication rule.

    The reference traversal does not follow metathesis/reduplication part
    sequences (KL-010-1), so a trim MIGHT strand a reference we cannot see.
    Surface one honest notice into the shared Move gate rather than transfer
    silently. Attributed to the first such kept rule.
    """
    rule_guids = sorted(inventory.untraversed_rule_guids & set(checked_rule_guids))
    rg = rule_guids[0] if rule_guids else "?"
    label = rg[:8]
    grp = inventory.group_for(GrammarCategory.PHONOLOGICAL_RULES)
    if grp is not None:
        for r in grp.rows:
            if r.guid == rg:
                label = r.label
                break
    return ExcludedLossy(
        category=GrammarCategory.PHONOLOGICAL_RULES,
        entry_guid=rg or "?",
        entry_label=label,
        dep_category=GrammarCategory.PHONOLOGICAL_RULES,
        dep_guid=rg or "?",
        dep_label=label,
        message=(
            f"Reference check is not supported for rule '{label}' "
            "(metathesis/reduplication); trimming phonemes or natural classes "
            "may strand references not verified here (KL-010-1)."
        ),
    )


def _phonology_excluded_lossy_for(wizard) -> list:
    """Intra-phonology EXCLUDED-LOSSY warnings for the current page state.

    Shared by Preview (StatsPanel channel, T025) and Finish (Move gate, T024)
    so both agree on the entry-centric count. Returns a list of ExcludedLossy;
    empty when there is no phonology page / inventory. Appends the coarse
    KL-010-1 notice (T026b) when a kept metathesis/reduplication rule coincides
    with an NC/phoneme trim.
    """
    phon_page = (wizard.page_phonology()
                 if hasattr(wizard, "page_phonology") else None)
    if phon_page is None or phon_page.inventory() is None:
        return []
    inventory = phon_page.inventory()
    checked = phon_page.collect_phonology_picks()

    # Target GUIDs per category drive the absent-from-target test. Reuse the
    # builder against the target handle (read-only) rather than re-deriving.
    target = None
    try:
        p0 = wizard.page_project_ws()
        ctx = p0.context() if p0 is not None else None
        target = getattr(ctx, "target_handle", None) if ctx is not None else None
    except Exception:  # noqa: BLE001
        target = None
    tgt_by_cat: dict = {}
    if target is not None:
        try:
            tinv = build_phonology_inventory(target)
            tgt_by_cat = {g.category: {r.guid for r in g.rows}
                          for g in tinv.groups}
        except Exception:  # noqa: BLE001
            tgt_by_cat = {}

    warnings = list(build_phonology_excluded_lossy(inventory, checked, tgt_by_cat))

    checked_rules = checked.get(GrammarCategory.PHONOLOGICAL_RULES, set())
    if (phonology_uses_untraversed_rules(inventory, checked_rules)
            and _phonology_nc_or_phoneme_trimmed(inventory, checked)):
        warnings.append(_kl010_notice(inventory, checked_rules))
    return warnings


# ---------------------------------------------------------------------------
# Page 7 -- Lexical-Entry Types (spec 021, Model-B independent block)
# ---------------------------------------------------------------------------

# Data roles for _PageEntryTypes
_ET_GUID_ROLE   = QtCore.Qt.ItemDataRole.UserRole + 70  # source GUID (item rows)
_ET_KIND_ROLE   = QtCore.Qt.ItemDataRole.UserRole + 71  # "group" | "item"
_ET_CAT_ROLE    = QtCore.Qt.ItemDataRole.UserRole + 72  # GrammarCategory
_ET_STATUS_ROLE = QtCore.Qt.ItemDataRole.UserRole + 73  # "new" | "in_target" | ""

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


def _entry_types_missing_ref_for(wizard) -> list:
    """Entry-types inflection-feature missing-ref warnings for the current page state.

    Shared by Finish (Move gate) so the count is aggregated into the single
    consolidated dialog (FR-011). Returns a list of warning dicts; empty when
    there is no entry-types page / inventory.
    """
    et_page = (wizard.page_entry_types()
               if hasattr(wizard, "page_entry_types") else None)
    if et_page is None or et_page.inventory() is None:
        return []
    inventory = et_page.inventory()
    checked = et_page.collect_entry_type_picks()
    target = et_page._get_target()
    return entry_types_missing_ref_warnings(inventory, checked, target=target)


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


class _PagePreview(QtWidgets.QWizardPage):
    """Preview / StatsPanel. NOT IN THE FLOW.

    Retained and reachable through `page_preview()` for back-compat, but absent
    from `SelectionWizard.flow()` and never registered: the dry run and its
    report live on the Finish page. Like `_PageScopeConflict` it therefore
    carries NO step number -- "(inactive)" is the whole of what its title has to
    say, and giving it a number would claim a position in a run it is not part
    of (T015, FR-011).

    Re-hosts the existing StatsPanel widget verbatim.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Preview (inactive)")
        self.setSubTitle(
            "Review the planned transfer before committing. "
            "Warnings (entries with missing references) are highlighted."
        )
        self._cached_plan = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        self._preview_btn = QtWidgets.QPushButton("Compute Preview", self)
        self._preview_btn.clicked.connect(self._on_preview)
        layout.addWidget(self._preview_btn)
        self._stats = StatsPanel(self)
        layout.addWidget(self._stats, 1)

    def _on_preview(self) -> None:
        """Thin wrapper delegating to _compute_wizard_plan (DR-5, FR-005)."""
        wizard = self.wizard()
        if wizard is None:
            return
        plan, report = _compute_wizard_plan(wizard)
        if plan is None:
            # DR-5: wrapper owns QMessageBox dialogs.
            context = wizard.page_project_ws().context()
            if context is None:
                QtWidgets.QMessageBox.warning(
                    self, "GramTrans", "No target project bound. Go back to page 1."
                )
            else:
                QtWidgets.QMessageBox.warning(
                    self, "GramTrans", "Plan assembly failed. Check project state."
                )
            return
        self._cached_plan = plan
        self._stats.set_report(report)
        self.completeChanged.emit()

    def cached_plan(self):
        return self._cached_plan

    def isComplete(self) -> bool:
        return self._cached_plan is not None


# ---------------------------------------------------------------------------
# Module-level plan assembler (DR-4, FR-004)
# ---------------------------------------------------------------------------

def _compute_wizard_plan(wizard) -> tuple:
    """Assemble the transfer plan from all wizard page selections.

    Returns (plan, report) on success, (None, None) on any failure.
    Does not display QMessageBox -- callers own all UI dialogs (DR-5).

    DR-4 step order:
    1. Context None-guard.
    2. affix_selection = page_items.collect_selection().
    3. build_selection + _replace_conflict_modes.
    4. dataclasses.replace stamp with similar_resolutions (single call -- SC-005).
    5. similar_resolutions stamp BEFORE phonology merge block (P1 ordering).
    6. ws_mapping from page0.
    7. gt_api.compute_preview; return (None, None) on payload-None or failure.
    8. RunReport.build_from_plan; return (payload, report).
    """
    # Step 1: context None-guard (no QMessageBox here -- caller owns dialogs).
    context = wizard.page_project_ws().context()
    if context is None:
        return (None, None)

    # Step 2: affix selection (single collect_selection call -- SC-005).
    page_items = wizard.page_items()
    affix_selection = page_items.collect_selection()

    # Step 3: build selection + apply Layer-1 conflict-mode defaults.
    selection = build_selection(
        PickerState(
            checked_affixes=affix_selection.affix_picks,
            checked_templates=affix_selection.template_picks,
        ),
        SourceAffixInventory(
            unbound_affixes=affix_selection.affix_picks,
            template_to_slots={t: () for t in affix_selection.template_picks},
        ),
        category_scopes={},
    )._replace_conflict_modes(dict(_DEFAULT_CONFLICT_MODES))

    # Step 4: stamp similar_resolutions BEFORE phonology merge (DR-4 step 5, P1).
    # Uses the already-collected affix_selection -- no second collect_selection call.
    selection = dataclasses.replace(
        selection,
        similar_resolutions=affix_selection.similar_resolutions,
    )

    # Step 5a: custom-fields merge (US2/T014 -- fold leaf_item_picks into selection).
    cf_page = wizard.page_custom_fields() if hasattr(wizard, "page_custom_fields") else None
    if cf_page is not None:
        cf_picks = cf_page.leaf_item_picks()
        if cf_picks:
            merged_categories = dict(selection.categories)
            merged_categories[GrammarCategory.CUSTOM_FIELDS] = True
            merged_leaf = dict(selection.leaf_item_picks)
            merged_leaf.update(cf_picks)
            selection = dataclasses.replace(
                selection,
                categories=merged_categories,
                leaf_item_picks=merged_leaf,
            )
        elif cf_page.whole_block_on():
            # Fully selected => include CUSTOM_FIELDS category (transfer-all).
            merged_categories = dict(selection.categories)
            merged_categories[GrammarCategory.CUSTOM_FIELDS] = True
            selection = dataclasses.replace(selection, categories=merged_categories)

    # Step 5b: phonology collapse-merge (applied AFTER resolution stamp per DR-4/P1).
    phon_page = wizard.page_phonology()
    if phon_page is not None and phon_page.inventory() is not None:
        collapsed = collapse_phonology(
            phon_page.inventory(), phon_page.collect_phonology_picks()
        )
        if collapsed["categories"]:
            merged_categories = dict(selection.categories)
            merged_categories.update(collapsed["categories"])
            merged_leaf = dict(selection.leaf_item_picks)
            merged_leaf.update(collapsed["leaf_item_picks"])
            selection = dataclasses.replace(
                selection,
                categories=merged_categories,
                leaf_item_picks=merged_leaf,
            )

    # Step 5c: entry-types collapse-merge (spec 021, applied after phonology).
    et_page = (wizard.page_entry_types()
               if hasattr(wizard, "page_entry_types") else None)
    if et_page is not None and et_page.inventory() is not None:
        collapsed = collapse_entry_types(
            et_page.inventory(), et_page.collect_entry_type_picks()
        )
        if collapsed["categories"]:
            merged_categories = dict(selection.categories)
            merged_categories.update(collapsed["categories"])
            merged_leaf = dict(selection.leaf_item_picks)
            merged_leaf.update(collapsed["leaf_item_picks"])
            selection = dataclasses.replace(
                selection,
                categories=merged_categories,
                leaf_item_picks=merged_leaf,
            )

    # Step 5d: rules block collapse-merge (018-rules-page T019).
    # collect_rules_picks() returns:
    #   None         => key absent (transfer ALL, SC-004 untouched default)
    #   frozenset()  => whole block OFF, zero rules transferred (SC-005)
    #   frozenset({..}) => individual trim subset
    rules_page = wizard.page_rules() if hasattr(wizard, "page_rules") else None
    if rules_page is not None and rules_page.inventory() is not None:
        rules_picks = rules_page.collect_rules_picks()
        if rules_picks is None:
            # Untouched / fully-checked => include category, key absent (transfer all)
            merged_categories = dict(selection.categories)
            merged_categories[GrammarCategory.ADHOC_COMPOUND_RULES] = True
            selection = dataclasses.replace(selection, categories=merged_categories)
        else:
            # Trimmed or whole-block-OFF: include category + emit frozenset (may be empty)
            merged_categories = dict(selection.categories)
            merged_categories[GrammarCategory.ADHOC_COMPOUND_RULES] = True
            merged_leaf = dict(selection.leaf_item_picks)
            merged_leaf[GrammarCategory.ADHOC_COMPOUND_RULES] = rules_picks
            selection = dataclasses.replace(
                selection,
                categories=merged_categories,
                leaf_item_picks=merged_leaf,
            )

    # Step 5e: POS/grammar-category wiring (fix/wizard-pos-grammar-wiring).
    # The Skeleton page pre-checks exactly the POSes the picked affixes' MSAs
    # attach to (SkeletonPosNode.preselected). Fold those POS GUIDs into the
    # Selection as pos_picks + flag GRAM POS, so the verb-vertical POS closure
    # (_select_source_poses -> _plan_pos_closure) walks precisely those POSes,
    # creates them in the target, and affix/stem MSAs resolve to a real POS via
    # _resolve_target_pos instead of None ("no grammatical info").  This is
    # dependency-driven and minimal: it never flags the leaf GRAM_CATEGORIES
    # pass (which would enumerate EVERY source POS), and an empty pos_guids set
    # (skeleton not built / no attaching POS) leaves the selection untouched --
    # we never flag POS with empty picks, which would walk every source POS.
    skel_page = wizard.page_skeleton() if hasattr(wizard, "page_skeleton") else None
    if skel_page is not None and hasattr(skel_page, "collect_skeleton_picks"):
        pos_guids = skel_page.collect_skeleton_picks().get("pos_guids") or set()
        if pos_guids:
            merged_categories = dict(selection.categories)
            merged_categories[GrammarCategory.POS] = True
            selection = dataclasses.replace(
                selection,
                categories=merged_categories,
                pos_picks=frozenset(g.lower() for g in pos_guids),
            )

    # Step 5f: stems -- fold the dedicated Stems page picks into the selection.
    # The leaf dispatch enumerates STEMS via selection.leaf_picks_for(STEMS)
    # (i.e. leaf_item_picks[GrammarCategory.STEMS]); mirror that contract here.
    # GUIDs are lower-cased to match categories._guid_str_from() on the source
    # side.  Empty picks leave STEMS off (nothing to transfer).
    stem_page = wizard.page_stems() if hasattr(wizard, "page_stems") else None
    if stem_page is not None and hasattr(stem_page, "stem_picks"):
        stem_picks = stem_page.stem_picks()
        if stem_picks:
            merged_categories = dict(selection.categories)
            merged_categories[GrammarCategory.STEMS] = True
            merged_leaf = dict(selection.leaf_item_picks)
            merged_leaf[GrammarCategory.STEMS] = frozenset(
                g.lower() for g in stem_picks
            )
            selection = dataclasses.replace(
                selection,
                categories=merged_categories,
                leaf_item_picks=merged_leaf,
            )

    # Step 5g: texts -- fold the dedicated Texts page picks into the selection
    # (Feature 026, FR-001). The preview/transfer TEXTS hook enumerates the
    # source's texts filtered by selection.text_picks; mirror that contract
    # here. GUIDs are lower-cased to match the source-side _text_guid()
    # normalization. Empty picks leave TEXTS off (nothing to transfer).
    texts_page = wizard.page_texts() if hasattr(wizard, "page_texts") else None
    if texts_page is not None and hasattr(texts_page, "text_picks"):
        text_picks = texts_page.text_picks()
        if text_picks:
            merged_categories = dict(selection.categories)
            merged_categories[GrammarCategory.TEXTS] = True
            selection = dataclasses.replace(
                selection,
                categories=merged_categories,
                text_picks=frozenset(g.lower() for g in text_picks),
            )

    # Step 6: WS mapping -- from the writing-systems page, which owns it since
    # the FR-006 split. `page_project_ws()` no longer answers for the mapping,
    # and the hasattr guards keep the fake wizards in the unit suite (which
    # supply only the pages they exercise) working unchanged.
    ws_page = wizard.page_writing_systems() \
        if hasattr(wizard, "page_writing_systems") else None
    ws_mapping = ws_page.ws_mapping() \
        if ws_page is not None and hasattr(ws_page, "ws_mapping") else None

    # FR-023 row 12 -- "Building the transfer plan...". The indicator covers
    # steps 7 and 8, which is where the wait is: everything above is dict merges
    # over trees the operator has already populated, while `compute_preview`
    # walks the source for every selected category.
    #
    # The total is the declared unit -- selected categories -- and it is knowable
    # here and not earlier, because the merges above are what decide which
    # categories are in. It is a `len()` over a dict already in hand, so no count
    # is paid for it (FR-014d).
    #
    # No intermediate ticks, deliberately: `compute_preview` is one engine call
    # and takes no sink, so there is no inside for a walk to report from. The
    # single tick on success is what leaves the last frame reading complete
    # rather than stalled; a failure never reaches it and the bar is dismissed
    # where it stood (FR-020).
    n_categories = sum(1 for on in selection.categories.values() if on)
    with _page_progress(wizard, "plan_assembly", n_categories) as prog:
        # Step 7: compute preview; return (None, None) on failure or None payload.
        state, payload = gt_api.compute_preview(context, selection, ws_mapping)
        if payload is None:
            return (None, None)
        prog.tick(n_categories)

        # Step 8: build run report and return.
        phon_warnings = _phonology_excluded_lossy_for(wizard)
        # QC P1 (cycle-1 review, feature 024): surface the plan's projected drops
        # (Lib/references.py `decide_reference`, run read-only during AFFIXES/
        # STEMS plan_action) here too, so the wizard's Preview report is
        # symmetric with both Move and the main-window Preview path.
        # Feature 024 (T023, FR-013): per-object FidelityStatus, mirroring the
        # Move-mode wiring in `Lib/transfer.py.execute`.
        if __package__:
            from ..categories import compute_fidelity_by_guid
        else:
            from categories import compute_fidelity_by_guid  # type: ignore
        _plan_dropped = getattr(payload, "dropped_items", ())
        report = RunReport.build_from_plan(
            payload, RunMode.PREVIEW, extra_excluded_lossy=phon_warnings,
            extra_dropped_items=_plan_dropped,
            fidelity_by_guid=compute_fidelity_by_guid(_plan_dropped),
        )
    return (payload, report)


# ---------------------------------------------------------------------------
# Page 5 -- Finish / Move
# ---------------------------------------------------------------------------

class _PageFinish(_FlowPage):
    """Page 5: Finish / Move.

    The ONLY write point.  The Finish handler:
    1. Queries `plan.excluded_lossy_count()`.
    2. When > 0: blocks and pops the summary dialog.
       Confirm -> write; cancel -> stay on wizard.
    3. Executes the move via `gt_api.execute_move`.
    4. Shows the RunReport (MOVE) in the StatsPanel.
    """

    def __init__(self, report_sink, modify_allowed: bool, parent=None,
                 confirmation_gate=None):
        super().__init__(parent)
        self._report_sink = report_sink
        self._modify_allowed = modify_allowed
        self._move_done = False
        # Feature 034 exceptions 2 and 3. The gate answers two questions for
        # this page: what the subtitle says about reversibility, and whether a
        # Move may proceed. `None` resolves to the FlexTools default, whose
        # subtitle is byte-identical to the literal that used to be inline
        # here and whose confirm() returns True with no UI (SC-013).
        self._gate = _resolve_gate(confirmation_gate)
        # Unnumbered: this run assigns the number on entry, because a
        # position is a fact about the run and not about the page
        # (SelectionWizard._apply_step_number). The literal that used to
        # be here stated a total across a flow that could skip pages.
        self.setTitle("Finish / Move")
        # Exception 3: gate-supplied, because "changes can be undone in FLEx
        # with Ctrl+Z" is true under FlexTools and false in the standalone,
        # and FR-027 forbids the application claiming otherwise.
        self.setSubTitle(self._gate.finish_page_subtitle())
        # data-model section 6: `None` on CONSTRUCTION, not merely on entry. A
        # page built but not yet entered used to have no `_cached_plan` attribute
        # at all, so every guard that asked about it had to reach through a
        # getattr default -- and a guard whose subject may be absent is one
        # refactor away from reading absence as permission.
        self._cached_plan = None
        self._build_ui()
        # DR-1: Move starts disabled unconditionally; enabled only after dry run.
        self._set_execute_enabled(False)

    def initializePage(self) -> None:
        """Re-arm the guard on every Finish page entry.

        DR-2a cleared the cached plan and disabled Move here. Feature 036 T036
        adds the third thing entry has to undo: the report on SCREEN (FR-041).
        Any route back to this page has passed through pages where a selection
        could change, so the plan the previous dry run described may no longer be
        the plan the current selections would produce -- and a StatsPanel still
        full of that run's numbers presents it as current. The cached plan and the
        displayed report are two halves of one authorisation and are dropped
        together.
        """
        self._cached_plan = None
        self._stats.clear()
        self._set_execute_enabled(False)

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        if not self._modify_allowed:
            warn = QtWidgets.QLabel(
                "[WARN] GramTrans is running in read-only (preview-only) mode. "
                "Move is disabled.",
                self,
            )
            warn.setWordWrap(True)
            layout.addWidget(warn)
        self._dry_run_btn = QtWidgets.QPushButton("Dry run (preview plan)", self)
        self._dry_run_btn.clicked.connect(self._on_dry_run)
        layout.addWidget(self._dry_run_btn)
        self._move_btn = QtWidgets.QPushButton("Execute Move", self)
        self._move_btn.setEnabled(False)
        self._move_btn.clicked.connect(self._on_move)
        layout.addWidget(self._move_btn)
        # T035 / FR-039: the reason lives next to the control it is about, so it
        # cannot describe a state the button is no longer in.
        self._move_reason = QtWidgets.QLabel("", self)
        self._move_reason.setWordWrap(True)
        layout.addWidget(self._move_reason)
        self._stats = StatsPanel(self)
        layout.addWidget(self._stats, 1)

    # ------------------------------------------------------------------
    # T035 / FR-039 + FR-044 -- a dead control that says why it is dead
    # ------------------------------------------------------------------

    @property
    def execute_disabled_reason(self) -> str:
        """Why Execute is unavailable, or `""` when it is available.

        THE THREE REASONS, IN THE ORDER THAT MATTERS TO THE OPERATOR
        ------------------------------------------------------------
        1. **Read-only** (FR-044) first, because it is the only one they cannot
           act on from here. Telling someone to run a dry run when no dry run
           could ever arm the button is worse than saying nothing: they do the
           work and the button stays dead. This reason therefore outlives a
           successful dry run.
        2. **Already executed** (FR-043). The plan has been written; a second
           write of the same plan would duplicate every object it created.
        3. **No dry run yet** (FR-039), the ordinary case: Preview-before-Mutate
           has not been satisfied for the CURRENT selections.

        Derived, never stored. A stored string is a second source of truth about
        the button's state and drifts from it the first time an enablement path
        forgets to update it -- which is exactly how a dead control comes to
        carry a stale explanation.
        """
        if not self._modify_allowed:
            return (
                "Execute is unavailable: GramTrans is running in read-only "
                "(preview-only) mode, so it cannot write to the target project."
            )
        if self._move_done:
            return (
                "Execute is unavailable: this plan has already been written to "
                "the target project. Close the wizard and start a new run to "
                "transfer anything further."
            )
        if self._cached_plan is None:
            return (
                "Execute is unavailable: a successful dry run of the current "
                "selections is required first. Click \"Dry run (preview plan)\"."
            )
        return ""

    def _may_execute(self) -> bool:
        """The FR-038/FR-043/FR-044 conjunction, in one place.

        A cached plan, write permission, and no completed Execute this session.
        `_on_dry_run` used to consult only `modify_allowed`, so a second dry run
        after a completed move re-armed the button and the same selections could
        be written twice -- `_move_done` was already recorded and simply not
        read.
        """
        return (
            self._cached_plan is not None
            and self._modify_allowed
            and not self._move_done
        )

    def _set_execute_enabled(self, enabled: bool) -> None:
        """Set the button's state and its explanation together.

        One method, so the two cannot disagree. The reason goes onto the control
        itself (tooltip and accessible description, for a pointer and for a
        screen reader) and onto the label beneath it, because a tooltip alone is
        invisible to an operator who has not thought to hover over a button that
        looks broken.
        """
        self._move_btn.setEnabled(bool(enabled))
        reason = "" if enabled else self.execute_disabled_reason
        self._move_btn.setToolTip(reason)
        self._move_btn.setAccessibleDescription(reason)
        self._move_reason.setText(f"<i>{reason}</i>" if reason else "")
        self._move_reason.setVisible(bool(reason))

    def _refresh_execute_state(self) -> None:
        """Re-derive both halves from the current guard state."""
        self._set_execute_enabled(self._may_execute())

    def _on_dry_run(self) -> None:
        """DR-5, G1, FR-006: compute the plan and show report; enable Move on success."""
        wizard = self.wizard()
        if wizard is None:
            return
        plan, report = _compute_wizard_plan(wizard)
        if plan is None:
            # T036 / FR-041 + FR-042: a dry run that produced nothing must not
            # leave the PREVIOUS run's report on screen. Without this the only
            # report visible after a failure is the stale one, next to a message
            # box saying the run failed -- and once the box is dismissed there is
            # nothing left to say the numbers are old.
            self._cached_plan = None
            self._stats.clear()
            self._refresh_execute_state()
            # DR-5: caller owns QMessageBox.
            context = wizard.page_project_ws().context()
            if context is None:
                QtWidgets.QMessageBox.warning(
                    self, "GramTrans", "No target project bound. Go back to page 1."
                )
            else:
                # G1: assembly failure -- Move stays disabled, no partial state.
                QtWidgets.QMessageBox.warning(
                    self, "GramTrans", "Plan assembly failed. Check project state."
                )
            return
        self._cached_plan = plan
        self._stats.set_report(report)
        # FR-043/FR-044 live here too: a successful dry run is necessary for
        # Execute, never sufficient. `_refresh_execute_state` re-derives the whole
        # conjunction, so read-only mode and an already-completed move both keep
        # the button dead -- with the reason updated to match.
        self._refresh_execute_state()

    def _on_move(self) -> None:
        wizard = self.wizard()
        if wizard is None:
            return
        # DR-6: read cached plan from self (set by dry run), not preview page.
        plan = self._cached_plan
        if plan is None:
            QtWidgets.QMessageBox.warning(
                self, "GramTrans",
                "No plan available. Run a dry run on the Finish page first."
            )
            return
        # FR-043 / FR-044: the same conjunction that decides whether the button
        # is live decides whether the write happens, so the guard does not depend
        # on the button being the only way in. A disabled button stops a click; it
        # does not stop Enter on a focused control, a programmatic `click()`, or a
        # future affordance -- and a second write of an already-written plan
        # duplicates every object it created.
        if not self._may_execute():
            QtWidgets.QMessageBox.warning(
                self, "GramTrans", self.execute_disabled_reason
            )
            self._refresh_execute_state()
            return
        context = wizard.page_project_ws().context()
        if context is None:
            return

        # T017: Aggregate EXCLUDED-LOSSY from the plan + skeleton/deps deselections.
        # plan.excluded_lossy_count() covers warnings emitted during preview planning.
        # Additionally, check skeleton page (index 2) and deps page (index 3) for
        # slots/deps the user deselected that a picked affix needs.
        el_count = plan.excluded_lossy_count()

        # Extra skeleton EXCLUDED-LOSSY (T017)
        skel_page = wizard.page_skeleton()
        if skel_page is not None and hasattr(skel_page, "deselected_filled_slot_guids"):
            deselected_slots = skel_page.deselected_filled_slot_guids()
            if deselected_slots and skel_page._skeleton is not None:
                # Build affix_slot_map from skeleton
                affix_slot_map = {
                    affix_guid: list(slot_guids)
                    for affix_guid, slot_guids in (
                        (ag, frozenset(
                            sg for sg, fills in skel_page._skeleton.affix_fills.items()
                            if ag in fills
                        ))
                        for ag in skel_page._skeleton.affix_picks
                    )
                }
                # target slot guids (blank; skeleton doesn't have live target here)
                extra_warnings = build_excluded_lossy_warnings(
                    affix_slot_map=affix_slot_map,
                    deselected_slot_guids=set(deselected_slots),
                    target_slot_guids=set(),
                )
                el_count += len(extra_warnings)

        # Extra phonology EXCLUDED-LOSSY + KL-010-1 guard (spec 010 T024/T026b).
        # Aggregated into the SAME el_count so a single consolidated dialog
        # covers skeleton/deps AND phonology (FR-011 — no second dialog).
        el_count += len(_phonology_excluded_lossy_for(wizard))

        # Extra entry-types missing-ref warnings (spec 021 T024 / FR-010/FR-011).
        # Kept ILexEntryInflType whose infl-feat ref is absent from target; counted
        # into the SAME consolidated dialog -- never a separate prompt.
        el_count += len(_entry_types_missing_ref_for(wizard))

        # Consolidated single confirmation dialog (FR-011 / T017).
        if el_count > 0:
            answer = QtWidgets.QMessageBox.question(
                self,
                "GramTrans -- Missing references",
                (
                    f"{el_count} entr{'y' if el_count == 1 else 'ies'} will transfer "
                    f"with missing references (deliberately excluded dependencies).\n\n"
                    "These entries will have null fields in the target project.\n\n"
                    "Proceed with Move?"
                ),
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return  # User cancelled -- no write occurs.

        # Feature 034 exception 2 (FR-017, FR-024): the host's confirmation
        # gate, consulted ONCE, immediately before the write and after the
        # EXCLUDED-LOSSY dialog -- so a user who backs out of that one is
        # never asked to type a project name they have already decided not to
        # write to. Under FlexTools this returns True with no UI, so the
        # sequence here is unchanged. A False return aborts with no write and
        # leaves the wizard and every selection intact (FR-025).
        #
        # Preview never reaches this line: it is on the Move path only, which
        # is what FR-024 requires.
        target_name = getattr(context, "target_project_name", "") or ""
        if not self._gate.confirm(target_name):
            return  # Gate refused -- no write occurs.

        # FR-023 row 13 -- "Writing to the target project...". The unit is the
        # planned action and the total is `len()` over the plan already in hand,
        # so the write's size is known before a single object is created. This is
        # the operation the operator most needs told about: it is the only one
        # that changes their project, and the only one they must not interrupt.
        #
        # Like row 12 this is one engine call with no sink, so the tick lands on
        # success (see the comment there). A failure below dismisses the
        # indicator through `reporting()` and then says what went wrong, in that
        # order -- a modal indicator left up over a message box would block the
        # only control that can acknowledge it (FR-020).
        n_actions = len(getattr(plan, "actions", ()) or ())
        try:
            with _page_progress(self, "move_write", n_actions) as prog:
                report = gt_api.execute_move(context, plan)
                prog.tick(n_actions)
        except gt_api.PreviewStale as e:
            QtWidgets.QMessageBox.critical(self, "GramTrans", str(e))
            return
        self._stats.set_report(report)
        self._move_done = True
        # DR-2b, G3: invalidate Finish page's own cached plan (post-move).
        # Move non-repeatability: a double-click or re-entry cannot re-execute
        # the same plan and create duplicate LCM objects. initializePage also
        # clears on re-entry (DR-2a), so this provides belt-and-suspenders safety.
        self._cached_plan = None
        # Both halves after the state above, so the reason the operator now reads
        # is FR-043's ("already written"), not FR-039's.
        self._refresh_execute_state()
        self.completeChanged.emit()


# ---------------------------------------------------------------------------
# Main wizard
# ---------------------------------------------------------------------------

class SelectionWizard(QtWidgets.QWizard):
    """The GramTrans selection wizard (Phase 3c, Refinement 3).

    Page order, skip eligibility and per-run numbering all come from `flow()`;
    no count of pages is stated here or anywhere else (036 FR-009a).

    Replaces `main_window.MainWindow`.  All existing widgets are re-hosted
    verbatim; no widget logic is rewritten.

    Constructor args:
        host_project: the FlexTools host's open FLExProject (the SOURCE).
        report_sink:  FlexTools report object (.Info / .Warning / .Error / .Blank).
        modify_allowed: True when FlexTools is running write-enabled.
        source_project_name: display name of the source project.
        projects_root: feature 034 exception 4 (FR-001) -- where the host says
            FLEx projects live. Keyword-only and defaulted, so the FlexTools
            call is unchanged and `list_target_candidates` keeps its historical
            C:\\ProgramData\\SIL\\FieldWorks\\Projects default. The standalone
            passes the location FieldWorks itself records.
        confirmation_gate: feature 034 exceptions 2 and 3 (FR-017) -- the
            host's answer to "may I write?", consulted once by `_PageFinish`
            immediately before `gt_api.execute_move` and never on the Preview
            path. Also supplies the Finish page's subtitle, because whether a
            Move can be undone is a fact about the host, not about the wizard.
            `None` resolves to `Lib/gate.AlwaysSatisfiedGate`: True with no UI,
            and today's subtitle byte for byte (SC-013).
        source_binder: feature 034 exception 7 -- for a host that has no open
            project of its own. A callable taking a project name and returning
            an open **read-only** handle, supplied by the host because the host
            is what must close it again. When given, `host_project` may be
            `None` and `source_project_name` empty, and step 1 grows a "Pick
            source project..." button beside the target's. `None` (every
            FlexTools call) means the source is host-supplied: no button, no
            picker, no change to the page (SC-013).
    """

    def __init__(
        self,
        host_project,
        report_sink,
        modify_allowed: bool,
        *,
        source_project_name: str,
        parent: Optional[QtWidgets.QWidget] = None,
        projects_root: str = "",
        confirmation_gate=None,
        source_binder=None,
    ) -> None:
        super().__init__(parent)
        # Install the palette/text-size theme BEFORE any page is constructed.
        # The pages snapshot the *application* font into per-item QFonts while
        # they build their trees (bolded section headers etc.), so a scale
        # applied afterwards would leave those items at the size that was in
        # force when the tree was built -- the first paint would come up
        # unscaled even though the user had saved a larger text size.
        install_theme()
        self._host = host_project
        self._report = report_sink
        self._modify_allowed = modify_allowed
        # T014: filled once, here, from whatever source the host already has
        # open (None under the standalone, whose source is picked on step 1 and
        # which calls `refresh_source_counts` from there). Every page-skip
        # predicate reads this snapshot, so nothing on a navigation path ever
        # queries the project (D5b).
        self.refresh_source_counts(host_project)

        # T040 / FR-001. The title used to read "GramTrans -- Selection Wizard
        # (Phase 3c)". "Phase 3c" is OUR development milestone: it tells the
        # operator nothing about the tool and, worse, reads as a beta warning on
        # software they are about to point at their language data. What a title
        # bar owes them is what the application is and what this window does.
        # No phase, no milestone, no iteration designation -- a source-level test
        # keeps one from creeping back.
        self.setWindowTitle("GramTrans -- copy grammar between FieldWorks projects")
        self.setModal(True)
        self.resize(1300, 760)
        # 036 T024/FR-029: the floor is the declared constant, and the height is
        # the one feature 004 set. The default size above is unchanged: US3
        # lowers how narrow the window CAN go, not how wide it opens.
        self.setMinimumSize(
            QtCore.QSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        )
        # ClassicStyle renders pages using the widget palette instead of forcing
        # a white page (AeroStyle/ModernStyle default on Windows). Under an OS
        # dark theme the forced-white page left every QLabel white-on-white
        # (illegible); ClassicStyle keeps text/background consistent with the
        # palette in both light and dark themes.  The reasoning is stronger now
        # that the palette is ours (Lib/ui/theme.py) rather than the OS's: a
        # style that forces its own white page would ignore the dark scheme the
        # user selected in-app, not merely the one Windows reported.
        self.setWizardStyle(QtWidgets.QWizard.WizardStyle.ClassicStyle)

        stub = gt_api.initialize_run(
            host_handle=host_project,
            source_project_name=source_project_name,
            source_project_path=_safe_path(host_project),
            projects_root=projects_root,
        )

        # Create pages. The ORDER they are registered in, and which of them a
        # given run shows, is `flow()` and nothing else (FR-010) -- the numbered
        # comment block that used to sit here restated the `addPage` order beside
        # it, which is exactly the second source of truth that let the titles
        # drift to "of 10" across eleven registered pages.
        #
        # _PagePreview and _PageScopeConflict are constructed and retained for
        # back-compat (`page_preview()`, `page_scope`) but are absent from
        # `flow()` and therefore never registered and never numbered (FR-011).
        self._page_projects = _PageProjects(
            stub, host_project,
            source_binder=source_binder, report_sink=report_sink,
        )
        self._page_writing_systems = _PageWritingSystems()
        self._page_custom_fields = _PageCustomFields()
        self._page_phonology = _PagePhonology()
        self._page_items = _PageItemPicker()
        self._page_stems = _PageStemPicker()
        self._page_skeleton = _PageSkeleton()
        self._page_gram_deps = _PageGramDeps()
        self._page_entry_types = _PageEntryTypes()   # spec 021
        # _PageScopeConflict kept but NOT added to the wizard (conflict UI deferred FR-012).
        self._page_scope = _PageScopeConflict()
        # 018-rules-page: Rules page sits after Lexical-entry types (021, not yet added)
        # and before Preview (FR-007).  Positioned after _PageGramDeps per spec order.
        self._page_rules = _PageRules()
        self._page_texts = _PageTexts()        # Feature 026 texts-wordforms
        self._page_preview = _PagePreview()
        self._page_finish = _PageFinish(
            report_sink, modify_allowed, confirmation_gate=confirmation_gate
        )

        # T009 / FR-010: registration is READ OFF the declaration. The eleven
        # hand-written `addPage` lines that used to be here carried their own
        # index comments, so the declaration and the registration were two
        # statements of the same fact and could disagree -- and did.
        #
        # `_page_id_by_attr` is filled here so `nextId()` can turn a declared
        # attr into a Qt page id by dict lookup. Qt may call `nextId()` on every
        # `completeChanged`, and searching `pageIds()` on each call would make
        # the cheap predicates pointless (FR-009c, D5b).
        self._page_id_by_attr: dict = {}
        for attr, _short, _skippable, _has_content in self.flow():
            page = getattr(self, attr)
            self._page_id_by_attr[attr] = self.addPage(page)

        # Provisional numbers, so a page carries a plausible title before any
        # run has entered it (the wizard is inspectable at construction). Entry
        # overwrites them with the position this run actually reached
        # (`_apply_step_number`); nothing derives or displays a total (FR-009a).
        self._apply_declared_step_numbers()

        self.setOption(QtWidgets.QWizard.WizardOption.HaveHelpButton, False)

        # T041 / FR-004 + FR-012. Qt stops drawing the subtitle, and each page's
        # own header draws it instead. `setSubTitle(...)` remains the string of
        # record everywhere -- this is a change of RENDERER, not a second copy of
        # the text to keep in step. Qt's renderer elides; the header's wraps, and
        # a description that ends mid-word with no ellipsis is FR-013's defect.
        self.setOption(QtWidgets.QWizard.WizardOption.IgnoreSubTitles, True)
        for attr, _short, _skippable, _has_content in self.flow():
            page = getattr(self, attr, None)
            if page is not None and hasattr(page, "install_header"):
                page.install_header(PageHeader(page))

        # T042 / FR-005 + D8. ONE strip for the whole wizard, moved into the
        # current page's header slot on every transition.
        #
        # WHY ONE, AND NOT ONE PER PAGE
        # -----------------------------
        # The obvious implementation -- give each header its own strip -- would
        # register `ZoomIn`, `ZoomOut` and `Ctrl+0` twelve times inside one
        # window. Qt resolves an ambiguous shortcut by firing NOTHING, so all
        # three keys would go quietly dead while every button still worked: a
        # failure nobody would attribute to the header refactor. One instance
        # means one registration, which is what FR-005 asks for.
        #
        # It is created after the pages exist because it is moved INTO one of
        # their headers immediately, and the headers are installed just above.
        self._theme_bar = ThemeCornerBar(self)
        self.currentIdChanged.connect(self._install_theme_bar_on_current_page)
        self._install_theme_bar_on_current_page()

    # =====================================================================
    # The declared flow (T009, FR-010; data-model section 1)
    # =====================================================================

    def flow(self):
        """The ordered flow: `(attr, short_title, skippable, has_content)` x 12.

        THE SINGLE SOURCE OF PAGE ORDER AND SKIP ELIGIBILITY (FR-010).
        Registration reads it (`__init__`), numbering reads it
        (`_apply_step_number`), and skipping reads it (`_FlowPage.nextId`), so
        the three cannot disagree about what a run contains.

        WHAT IS DELIBERATELY ABSENT
        ---------------------------
        **Positions, and any length.** A position is (pages shown before this
        one in *this run*) + 1, so an integer in this table could only be a slot
        number -- and a slot number displayed as a position is how eleven
        registered pages came to announce "of 10". Nothing here derives a total
        and nothing displays one (FR-009a). The operator may also go back and
        pick an affix, which re-admits Morphology Skeleton and shifts every
        position after it: the length of a run is not knowable until the run is
        over.

        `skippable` / `has_content`
        ---------------------------
        `has_content` is `None` if and only if `skippable` is False, so an
        unskippable page carries no predicate for a caller to consult and skip
        on anyway. Where it is present it is a zero-argument callable that Qt
        may invoke on every `completeChanged`; each one is a field read or a
        `len()`, never an inventory build (FR-009c, D5b).

        The Affix and Stem pickers are unskippable **by mandate** (FR-009d), not
        because they always have content: "your source has no affixes" is
        something the operator needs told, and an absent page does not say it.
        Projects, Writing Systems and Finish are unskippable because they always
        ask something.
        """
        return (
            ("_page_projects",        "Projects",                 False, None),
            ("_page_writing_systems", "Writing Systems",          False, None),
            ("_page_custom_fields",   "Custom Fields",            True,
             self._has_custom_fields),
            ("_page_phonology",       "Phonology",                True,
             self._has_phonology),
            ("_page_items",           "Affix Picker",             False, None),
            ("_page_stems",           "Stem Picker",              False, None),
            ("_page_skeleton",        "Morphology Skeleton",      True,
             self._has_item_picks),
            ("_page_gram_deps",       "Grammatical Dependencies", True,
             self._has_gram_deps),
            ("_page_entry_types",     "Lexical-Entry Types",      True,
             self._has_entry_types),
            ("_page_rules",           "Rules",                    True,
             self._has_rules),
            ("_page_texts",           "Texts",                    True,
             self._has_texts),
            ("_page_finish",          "Finish / Move",            False, None),
        )

    def flow_page_id(self, attr: str) -> int:
        """Qt's id for a declared page, or -1 before it has been registered."""
        return getattr(self, "_page_id_by_attr", {}).get(attr, -1)

    # =====================================================================
    # The emptiness predicates (T014, FR-009c / FR-009d / D5b)
    # =====================================================================
    # THE CONSERVATIVE RULE IS ABSOLUTE. Every predicate below returns True
    # when it does not know. An empty page that is shown costs the operator one
    # Next click and says on the page that it has nothing to decide; a non-empty
    # page that is skipped silently drops a decision they were entitled to make.
    # The two errors are not symmetric, so unknown means SHOWN.
    #
    # Cost matters here in a way it does not elsewhere: Qt calls `nextId()` to
    # decide whether Next is enabled, which can be on every `completeChanged`.
    # Nothing below queries a project. The five source-derived pages read a
    # `SourceCounts` snapshot filled once at bind (`Lib/progress.py`), and the
    # two selection-derived pages read the picker trees the operator just
    # touched. No inventory is built -- building one to find out whether a page
    # would be empty is precisely the expensive walk US1 exists to cover, and
    # FR-009c forbids paying for it here.

    def source_counts(self) -> "SourceCounts":
        """The cheap-count snapshot of the currently bound source."""
        return self._source_counts

    def refresh_source_counts(self, source) -> None:
        """Re-snapshot the counts because the source binding changed.

        Called from `_PageProjects._bind_source_handle` (the standalone's
        re-pick) and once from `__init__` (FlexTools, whose source is the host's
        already-open project). Filling it anywhere else would mean a count was
        read on a page-navigation path, which is the cost D5b rules out.
        """
        self._source_counts = (
            SourceCounts(source) if source is not None else SourceCounts.unknown()
        )

    def _has_custom_fields(self) -> bool:
        """Row 3: source custom-field definitions across the owner classes."""
        return _count_says_content(self._source_counts.custom_fields)

    def _has_phonology(self) -> bool:
        """Row 4: phoneme sets + natural classes + phonological rules."""
        return _count_says_content(self._source_counts.phonology)

    def _has_entry_types(self) -> bool:
        """Row 9: variant types + complex-form types."""
        return _count_says_content(self._source_counts.entry_types)

    def _has_rules(self) -> bool:
        """Row 10: ad-hoc prohibitions."""
        return _count_says_content(self._source_counts.rules)

    def _has_texts(self) -> bool:
        """Row 11: `TextsNumberOfTexts()`."""
        return _count_says_content(self._source_counts.texts)

    def _has_item_picks(self) -> bool:
        """Row 7: "the operator picked at least one affix or stem".

        The declared proxy for Morphology Skeleton. Deliberately NOT "the
        skeleton inventory would come back empty": answering that means
        building the inventory, which is the multi-second walk the page already
        shows a progress indicator for.

        Before either picker has been populated the answer is unknown, not
        "no" -- an unbound run has picked nothing simply because it has not been
        asked yet -- so both pages are shown. A page whose proxy says "maybe"
        and whose inventory then comes back empty says so and keeps its number
        (spec edge case).
        """
        items = getattr(self, "_page_items", None)
        stems = getattr(self, "_page_stems", None)
        populated = (getattr(items, "_inventory", None) is not None
                     or getattr(stems, "_stem_inventory", None) is not None)
        if not populated:
            return True                     # unknown -> show
        try:
            if items is not None and len(items.picker_state().checked_affixes):
                return True
            if stems is not None and len(stems.stem_picks()):
                return True
        except Exception:  # noqa: BLE001 -- a broken tree read is "unknown"
            return True
        return False

    def _has_gram_deps(self) -> bool:
        """Return whether the selected items have grammatical dependencies.

        Dependency enumeration is cached per source and picker selection so
        Qt can ask this predicate repeatedly without rebuilding the inventory.
        An unavailable or failed enumeration is treated as unknown and keeps
        the page visible.
        """
        items = getattr(self, "_page_items", None)
        stems = getattr(self, "_page_stems", None)
        try:
            affix_picks = items.collect_selection().affix_picks if items else frozenset()
            stem_picks = stems.stem_picks() if stems else frozenset()
            populated = (getattr(items, "_inventory", None) is not None
                         or getattr(stems, "_stem_inventory", None) is not None)
            if not populated:
                return True
            source = self._page_projects.context().source_handle
            if source is None:
                return True
        except Exception:  # noqa: BLE001 -- a broken read is "unknown"
            return True

        cache_key = (id(source), frozenset(affix_picks), frozenset(stem_picks))
        cached = getattr(self, "_gram_deps_content_cache", None)
        if cached is not None and cached[0] == cache_key:
            return cached[1]
        if not affix_picks and not stem_picks:
            result = False
        else:
            try:
                deps = build_deps_inventory(
                    source, frozenset(affix_picks), stem_picks=frozenset(stem_picks)
                )
                result = bool(deps.infl_features or deps.infl_classes or deps.stem_names)
            except Exception:  # noqa: BLE001 -- unknown means show
                return True
        self._gram_deps_content_cache = (cache_key, result)
        return result

    # -- Step numbering (T012, FR-009 / FR-009a) -----------------------------

    def _short_title_for_page(self, page) -> str:
        """The declared, unnumbered title of `page`, or "" when undeclared.

        Undeclared is a real answer, not a failure: `_PageScopeConflict` and
        `_PagePreview` are retained and never in the flow, so they have no
        number to state and must never be given one (FR-011).
        """
        for attr, short, _skippable, _has_content in self.flow():
            if getattr(self, attr, None) is page:
                return short
        return ""

    def _apply_declared_step_numbers(self) -> None:
        """Number every declared page by its slot, as a pre-run placeholder.

        Only correct for a run that shows everything -- which is why entry
        recomputes it. It exists because the wizard is inspectable before it is
        walked, and a page whose title read "Projects" with no number in a
        numbered flow would look like the un-numbered page SC-004 removed.
        """
        for i, (attr, short, _skippable, _has) in enumerate(self.flow(), 1):
            page = getattr(self, attr, None)
            if page is not None:
                page.setTitle(f"Step {i}: {short}")

    def _apply_step_number(self, page_id: int) -> None:
        """Title `page_id` as "Step {n}: {short}" for this run's n.

        n counts the pages this run has actually SHOWN, so a run that skipped
        Phonology reads 1, 2, 3 with no hole where it would have been (SC-003a).
        Qt's own visited stack is the counter: it does not yet contain `page_id`
        when `initializePage` fires (verified against Qt 6.7), and Back pops it,
        so retracing a run reproduces the numbers the operator saw.
        """
        page = self.page(page_id)
        if page is None:
            return
        short = self._short_title_for_page(page)
        if not short:
            return          # not in the flow -> not numbered (FR-011)
        visited = list(self.visitedIds())
        position = (visited.index(page_id) + 1) if page_id in visited \
            else len(visited) + 1
        page.setTitle(f"Step {position}: {short}")

    def initializePage(self, page_id: int) -> None:  # noqa: N802 -- Qt naming
        """Number the page being entered, then let it initialise itself.

        The number is assigned HERE rather than in each page's own
        `initializePage` because it is a fact about the run, not about the page,
        and because five of the twelve pages have no `initializePage` at all.

        The header's description is re-rendered for the same reason (T041):
        `subTitle()` is the string of record and a page may restate it as it
        initialises, so the render happens on entry rather than once at install.
        """
        self._apply_step_number(page_id)
        page = self.page(page_id)
        if page is not None and hasattr(page, "refresh_header_description"):
            page.refresh_header_description()
        super().initializePage(page_id)

    def context(self):
        """Return the bound RunContext (available after page 1 is completed)."""
        return self._page_projects.context()

    # -- Named page accessors (spec 010 P-1) ---------------------------------
    # Pages MUST reference each other through these, never by literal index:
    # inserting a page (e.g. Phonology at index 1) shifts every literal
    # `wizard.page(N)` silently. Each accessor returns the stored attribute.
    def page_project_ws(self):
        """The projects page. 036 FR-006 renamed the attribute, not the name.

        25 call sites reach the source handle and the bound context through
        this accessor; the page it returns no longer owns the writing-system
        mapping (see `page_writing_systems`).
        """
        return self._page_projects

    def page_writing_systems(self):
        """The writing-systems page -- `ws_mapping()` and `selected_ws_ids()`.

        New in 036 (FR-006). One owner: reading a mapping off
        `page_project_ws()` is no longer possible, so no caller can silently get
        a stale or empty one from the half that lost it.
        """
        return self._page_writing_systems

    def page_custom_fields(self):
        return self._page_custom_fields

    def page_phonology(self):
        return self._page_phonology

    def page_items(self):
        return self._page_items

    def page_stems(self):
        return self._page_stems

    def page_skeleton(self):
        return self._page_skeleton

    def page_gram_deps(self):
        return self._page_gram_deps

    def page_entry_types(self):
        return self._page_entry_types

    def page_rules(self):
        """Named accessor for _PageRules (018-rules-page P-1 pattern)."""
        return self._page_rules

    def page_texts(self):
        """Named accessor for _PageTexts (Feature 026, P-1 pattern)."""
        return self._page_texts

    def page_preview(self):
        return self._page_preview

    def page_finish(self):
        return self._page_finish

    def theme_bar(self):
        """Named accessor for the one theme / text-size control strip.

        Kept under its historical name: callers reach it to ask about zoom and
        colour mode, which is still what it is for. What changed is where it
        lives -- a header slot on the current page, not a floating overlay.
        """
        return self._theme_bar

    # -- The one control strip, moved between page headers (T042, FR-005) ----
    # No geometry hooks any more. `resizeEvent` and `showEvent` used to exist
    # solely to re-pin a bar that nothing laid out; the header's layout does
    # that now, at every width and every text scale, without being told.

    def _install_theme_bar_on_current_page(self, *_args) -> None:
        """Move the strip into the current page's header controls slot.

        Every guard here is a real state this runs in. `currentIdChanged` fires
        during construction (before `_theme_bar` exists) and again after the
        last page, with id -1; a page outside the flow has no header; and Qt
        rebuilds its page stack on every transition, so the move has to happen
        on each one rather than once at the start.

        `set_controls` detaches the strip from the previous page's slot first,
        so exactly one header holds it at any moment and the others collapse
        their controls cell to nothing.
        """
        bar = getattr(self, "_theme_bar", None)
        if bar is None:
            return
        page = self.currentPage()
        header = page.header() if hasattr(page, "header") else None
        if header is None:
            return
        header.set_controls(bar)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _safe_path(flex_project) -> str:
    for attr in ("ProjectPath", "ProjectFilename", "ProjectFolder"):
        try:
            v = getattr(flex_project, attr)
            return v() if callable(v) else str(v)
        except Exception:
            continue
    return ""


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
