"""Widget and tree helpers shared by the wizard's pages (feature 039, T009).

Why this module exists
----------------------
These are the wizard's cross-page mechanics: the one way a page reports a wait,
the one way a tree-beside-preview page builds its splitter, and the tooltip and
elision helpers that keep a narrow window legible. Each was written once
precisely because the decision it makes is the same on every page and is easy to
get subtly wrong per call site -- and each was then declared in the middle of
`selection_wizard.py`, where "written once" was a property of the file rather
than a property anything enforced.

Nothing here holds page state. Every function takes the page, tree or view it
operates on as its first argument, which is what let them relocate verbatim.

What is deliberately absent
---------------------------
* `_count_says_content`. It reads a `SourceCounts` field to answer "show this
  page?", and the only caller is `SelectionWizard`'s own skip predicates, so it
  stays in the facade with them.
* `_set_item_text_with_tooltip` is kept even though nothing calls it:
  `test_036_min_width_layout.py` asserts it is exposed. Deleting an unused
  helper that a test names is how a structural guard silently stops guarding.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Optional, Set

from PyQt6 import QtCore, QtWidgets

if __package__:
    from ..progress import (
        SourceCounts,
        label_for,
        rate_for,
        reporting,
        warrants_indicator,
    )
    from .progress_indicator import deferred, immediate
    from .wizard_roles import _IS_PRODUCES, _KIND_ROLE
else:
    from progress import (  # type: ignore
        SourceCounts,
        label_for,
        rate_for,
        reporting,
        warrants_indicator,
    )
    from progress_indicator import deferred, immediate  # type: ignore
    from wizard_roles import _IS_PRODUCES, _KIND_ROLE  # type: ignore


# T025 / FR-029a: what a tree-and-preview page's two panes may be squeezed to.
# Their sum must stay well inside MIN_WINDOW_WIDTH -- minimums that sum past the
# window floor would make the floor unreachable and Qt would silently clamp the
# window back up, which is FR-029 failing in the name of FR-029a.
_TREE_PANE_MIN_WIDTH = 360
_PREVIEW_PANE_MIN_WIDTH = 260


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
