"""US3 -- "fit the wizard on the screen you actually have" (FR-029..FR-032, SC-005).

WHY this module exists
----------------------
The wizard's minimum width has been 1100 px since feature 004 widened it for the
tree-beside-preview layout. A 1366x768 laptop -- the machine a field linguist
actually has -- can show 1100 px, but only by giving up every other window; and
1100 is a number nobody ever measured, it is the width the layout happened to
want on the developer's monitor. US3 lowers the floor to 900 px and requires
that the drop cost nothing: at 900 px

* both panes of a tree-and-preview page stay side by side (FR-029a) -- the
  failure mode a naive fix produces is a splitter that lets the operator (or Qt,
  when the width runs out) collapse the preview to zero and then wonder where it
  went;
* content too wide for its column is shortened with a visible ellipsis and its
  full value stays available on demand, and no page grows a horizontal scrollbar
  (FR-029b) -- an unindicated cut is worse than a narrow column, because the
  operator cannot tell that there is more;
* nothing is clipped and nothing is drawn over anything else (FR-030), every
  control stays reachable and the navigation buttons stay fully visible and
  operable (FR-031), and all of that still holds when the narrowest width is
  combined with the largest supported text scale (FR-032) -- 250% text on a
  900 px window is the worst case the product offers, so it is the one case
  worth measuring.

Every measurement here comes from `_ui_geometry` (T001), which owns the one
answer to "900 px at the largest supported text scale": the scale goes on
*before* construction (pages snapshot the application font into per-item
QFonts), rects are mapped into one common coordinate space before they are
compared, and ancestor/descendant pairs are excluded from the overlap check.
Nothing in this file re-implements any of that -- the harness is shared with two
later tests and must not fork.

Cost control
------------
Building the wizard is the expensive part, so the wizard is built exactly TWICE
for the whole module: once per text scale, in a module-scoped parametrised
fixture. Every test then sweeps the pages of the wizard it is handed. Pages are
swept in a loop rather than parametrised because the page set does not exist
until the wizard is built -- and cannot be known at collection time -- and
because the aggregated failure message ("these 3 pages clipped, here is what
escaped what") is more useful to whoever fixes it than eleven separate reds.

Nothing here keys off a page title, a page count or a page index: a sibling task
is splitting the projects page in two and renumbering the flow. Pages are
reached through `geom.pages()` and identified by their class name in failure
messages only.
"""
from __future__ import annotations

import os

# SC-007 convention: choose the platform before Qt is imported, or the import
# binds the real windowing system and the suite needs a display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import re  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Iterator, NamedTuple  # noqa: E402

import pytest  # noqa: E402

PyQt6 = pytest.importorskip("PyQt6")

from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402

import _ui_geometry as geom  # noqa: E402  -- tests/unit is on sys.path (conftest)
from gramtrans.Lib.ui import selection_wizard as sw  # noqa: E402


#: The height floor feature 036 does NOT change (contract: "Unchanged from
#: today (680)"). Spelled out rather than read from the module, because the
#: point of the assertion is that the number did not move.
UNCHANGED_MIN_HEIGHT = 680

#: The contract value for the width floor (FR-029). Also spelled out: reading it
#: from `sw.MIN_WINDOW_WIDTH` would make the assertion "the constant equals
#: itself", and reading it from `geom.MIN_WINDOW_WIDTH` would launder a missing
#: declaration into a pass, since the harness falls back to 900 by `getattr`.
CONTRACT_MIN_WIDTH = 900

#: How many tree-and-preview pages must exist for the FR-029a sweep to mean
#: anything. Nine pages call `_make_tree_pane_splitter` today (custom fields,
#: phonology, affixes, stems, skeleton, grammar deps, entry types, rules,
#: texts). The floor is deliberately lower than nine so a page legitimately
#: added or removed does not fail this module -- it exists only to stop the
#: sweep from passing vacuously when splitter discovery breaks.
MIN_TREE_PANE_PAGES = 5

#: The wizard's navigation buttons, by the enum member name `QWizard.button()`
#: takes. Not all are visible at once -- Next hides on the last page, Finish on
#: every earlier one -- so the sweep checks the visible ones and separately
#: insists it found a meaningful set.
NAV_BUTTON_NAMES = ("BackButton", "NextButton", "FinishButton", "CancelButton")


class Case(NamedTuple):
    """One (width, text scale) stress case, and the wizard built for it."""

    scale: float
    wizard: QtWidgets.QWizard

    @property
    def label(self) -> str:
        return f"{self.wizard.width()}px x {self.scale} text scale"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp():
    """The one QApplication, held for the whole session.

    Session scope is not an optimisation, it is a correctness requirement: a
    QApplication with no live Python reference is garbage-collected, and its
    destruction takes every QObject in the process with it -- including the
    process-wide ThemeManager singleton, whose Python handle survives as a
    dangling wrapper. The second wizard built in such a session dies with
    "wrapped C/C++ object of type ThemeManager has been deleted". Same shape as
    the fixture in `test_034_step1_source_picker.py`.
    """
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture(
    scope="module",
    params=[geom.DEFAULT_TEXT_SCALE, geom.MAX_TEXT_SCALE],
    ids=["text-scale-default", "text-scale-max"],
)
def narrow_case(request, qapp, tmp_path_factory) -> Case:
    """A wizard at the 900 px floor, once per text scale -- two builds per module.

    Module scope with a parametrised fixture, rather than two separate
    module-scoped fixtures: pytest tears the previous parameter down before it
    sets the next one up, so only ONE scaled application font is ever installed
    at a time. Two overlapping fixtures would nest the scaling -- the second
    would capture the first's already-scaled font as its baseline -- and every
    measurement after that would be at some unintended third scale.

    `geom.wizard_at` is the single canonical stress expression (scale first,
    construct second, restore always); this fixture adds nothing to it but the
    lifetime.
    """
    geom.ensure_qapp()
    geom.needs_a_real_qwizard()
    root = tmp_path_factory.mktemp("projects_root")
    geom.projects_tree(root)
    with geom.wizard_at(
        root,
        width=CONTRACT_MIN_WIDTH,
        height=UNCHANGED_MIN_HEIGHT,
        scale=request.param,
    ) as wizard:
        yield Case(float(request.param), wizard)


@pytest.fixture(scope="module")
def wizard_source() -> str:
    """The production module's own text, for the "declared once" assertions.

    FR-029 is not only a behavioural claim ("the window narrows to 900") but a
    structural one: 900 is ONE declared value for the wizard as a whole, not a
    literal buried in a `setMinimumSize` call and not negotiated per page. That
    is a fact about the source, so it is read from the source.
    """
    return Path(sw.__file__).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Small helpers over the harness
# ---------------------------------------------------------------------------

def _at_the_floor(case: Case) -> None:
    """Assert the measurement is happening at the floor it claims to test.

    Qt clamps `resize()` against `minimumSize`, so a wizard asked for 900 px
    while its minimum is still 1100 comes back 1100 px wide -- and every
    "nothing is clipped at 900 px" assertion downstream then passes by measuring
    a window that never narrowed. That is the one failure mode that would make
    this whole module a no-op, so it is asserted, not skipped, in every test
    whose subject is the floor.
    """
    wizard = case.wizard
    assert geom.at_requested_width(wizard, CONTRACT_MIN_WIDTH) and (
        wizard.width() == CONTRACT_MIN_WIDTH
    ), (
        f"[FAIL] FR-029: asked for a {CONTRACT_MIN_WIDTH} px window and got "
        f"{wizard.width()} px -- minimumWidth() is {wizard.minimumWidth()}, so "
        f"the resize was clamped and nothing below is being measured at the "
        f"floor. Fix FR-029 first."
    )


def _tree_pane_splitters(page: QtWidgets.QWizardPage) -> list[QtWidgets.QSplitter]:
    """The horizontal two-child splitters on `page` -- what FR-029a is about.

    Discovered from the live widget tree rather than from a list of page
    accessor names, so a page added, removed or renamed by the concurrent flow
    refactor neither escapes the sweep nor breaks it. Every such splitter comes
    from `_make_tree_pane_splitter`, which is the one place a tree-and-preview
    page builds one.
    """
    horizontal = QtCore.Qt.Orientation.Horizontal
    return [
        s
        for s in page.findChildren(QtWidgets.QSplitter)
        if s.orientation() == horizontal and s.count() == 2
    ]


def _iter_tree_pane_splitters(
    wizard: QtWidgets.QWizard,
) -> Iterator[tuple[int, QtWidgets.QWizardPage, QtWidgets.QSplitter]]:
    """Yield `(page_id, page, splitter)` with that page CURRENT at yield time.

    A generator, not a list, and the distinction is the whole correctness of the
    FR-029a sweep. QWizard shows one page at a time and hides the rest, so a
    widget on a non-current page reports `isVisible() is False` and holds the
    geometry it had when it was last laid out. Collecting the triples first and
    measuring afterwards therefore measures ten stale pages and one live one --
    and reads out as "every pane is hidden at the floor", which is a fact about
    QWizard, not about the layout under test. Measuring at yield time, while the
    page is the current one, is the only way the numbers mean anything.
    """
    for pid, page in geom.pages(wizard):
        splitters = _tree_pane_splitters(page)
        if not splitters:
            continue
        geom.show_page(wizard, page)
        for splitter in splitters:
            yield pid, page, splitter


def _panes(splitter: QtWidgets.QSplitter) -> tuple[QtWidgets.QWidget, QtWidgets.QWidget]:
    """`(tree, pane)` -- index 0 is the tree, index 1 the preview, by construction."""
    return splitter.widget(0), splitter.widget(1)


def _visible_nav_buttons(
    wizard: QtWidgets.QWizard,
) -> list[tuple[str, QtWidgets.QAbstractButton]]:
    """The navigation buttons currently on screen, with their enum names."""
    out = []
    for name in NAV_BUTTON_NAMES:
        member = getattr(QtWidgets.QWizard.WizardButton, name)
        button = wizard.button(member)
        if button is not None and button.isVisible():
            out.append((name, button))
    return out


def _tree_views(page: QtWidgets.QWizardPage) -> list[QtWidgets.QTreeView]:
    """The tree views inside `page`'s tree-and-preview splitters.

    Only these are in scope for FR-029b's elision rule: they are the multi-column
    views whose columns cannot all fit once the window is at the floor. A preview
    pane's rich-text browser wraps instead of eliding and is not a column.
    """
    views: list[QtWidgets.QTreeView] = []
    seen: set[int] = set()
    for splitter in _tree_pane_splitters(page):
        tree, _pane = _panes(splitter)
        # The left pane itself, plus any view nested inside it -- a page that
        # wraps its tree in a frame still has the view FR-029b means. Deduped by
        # identity so a wrapped view is not reported twice.
        candidates = [tree, *tree.findChildren(QtWidgets.QTreeView)]
        for candidate in candidates:
            if isinstance(candidate, QtWidgets.QTreeView) and id(candidate) not in seen:
                seen.add(id(candidate))
                views.append(candidate)
    return views


# ---------------------------------------------------------------------------
# FR-029 -- the floor itself
# ---------------------------------------------------------------------------

def test_the_minimum_width_is_declared_once_as_900(wizard_source: str) -> None:
    """FR-029: "The window's minimum width MUST be 900 pixels, down from 1100".

    The contract adds how: `MIN_WINDOW_WIDTH` is "one declared value for the
    wizard as a whole, not negotiated per page". So three things are checked --
    the constant exists and is 900, the old 1100 literal is gone from the
    minimum-size call, and no per-page widget sets a minimum width of its own
    that is as large as the window floor (which would make some page, not the
    wizard, the real arbiter of how narrow the window can get).
    """
    declared = getattr(sw, "MIN_WINDOW_WIDTH", None)
    assert declared is not None, (
        "[FAIL] FR-029: selection_wizard declares no MIN_WINDOW_WIDTH. The floor "
        "must be one named module-level value, not a literal inside "
        "setMinimumSize()."
    )
    assert isinstance(declared, int) and declared == CONTRACT_MIN_WIDTH, (
        f"[FAIL] FR-029: MIN_WINDOW_WIDTH is {declared!r}; the contract value is "
        f"{CONTRACT_MIN_WIDTH}."
    )

    assert re.search(r"(?m)^MIN_WINDOW_WIDTH\s*=\s*900\b", wizard_source), (
        "[FAIL] FR-029: MIN_WINDOW_WIDTH must be assigned at module level in "
        "selection_wizard.py (a class attribute or a value computed at runtime "
        "is not 'one declared value for the wizard as a whole')."
    )
    assert "QSize(1100" not in wizard_source, (
        "[FAIL] FR-029: the 1100 px literal is still in a QSize() -- the old "
        "floor survives somewhere in the minimum-size path."
    )

    over_wide = [
        int(m.group(1))
        for m in re.finditer(r"setMinimumWidth\(\s*(\d+)\s*\)", wizard_source)
        if int(m.group(1)) >= CONTRACT_MIN_WIDTH
    ]
    assert not over_wide, (
        f"[FAIL] FR-029: per-page setMinimumWidth({over_wide}) is at or above the "
        f"{CONTRACT_MIN_WIDTH} px window floor, so that page -- not the declared "
        f"constant -- decides how narrow the window can be."
    )


def test_the_wizard_minimum_size_is_the_floor_by_the_unchanged_height(
    narrow_case: Case,
) -> None:
    """FR-029: `minimumWidth() == MIN_WINDOW_WIDTH`; "minimum height is unchanged"."""
    wizard = narrow_case.wizard
    assert wizard.minimumWidth() == getattr(sw, "MIN_WINDOW_WIDTH", None), (
        f"[FAIL] FR-029 at {narrow_case.label}: minimumWidth() is "
        f"{wizard.minimumWidth()}, MIN_WINDOW_WIDTH is "
        f"{getattr(sw, 'MIN_WINDOW_WIDTH', '<undeclared>')}."
    )
    assert wizard.minimumWidth() == CONTRACT_MIN_WIDTH
    assert wizard.minimumHeight() == UNCHANGED_MIN_HEIGHT, (
        f"[FAIL] FR-029 at {narrow_case.label}: the minimum height moved to "
        f"{wizard.minimumHeight()}; US3 changes the width only."
    )


def test_the_window_narrows_to_the_floor_without_refusing_or_snapping_back(
    narrow_case: Case,
) -> None:
    """FR-029: narrows "continuously to that floor without refusing or snapping back".

    Three widths, because each catches a different failure: an intermediate
    width that must be honoured exactly (no snapping to a preferred size), the
    floor itself (not refused), and one pixel-run below the floor, which must
    stop AT the floor rather than somewhere above it -- a layout whose own
    minimum still wants 1100 would clamp there and satisfy neither FR-029 nor
    the operator.
    """
    wizard = narrow_case.wizard
    try:
        for requested, expected in (
            (1000, 1000),
            (CONTRACT_MIN_WIDTH, CONTRACT_MIN_WIDTH),
            (CONTRACT_MIN_WIDTH - 50, CONTRACT_MIN_WIDTH),
        ):
            wizard.resize(requested, UNCHANGED_MIN_HEIGHT)
            geom.settle(wizard)
            assert wizard.width() == expected, (
                f"[FAIL] FR-029 at {narrow_case.scale} text scale: resize to "
                f"{requested} px settled at {wizard.width()} px, expected "
                f"{expected} px (minimumWidth() is {wizard.minimumWidth()})."
            )
    finally:
        # The wizard is shared across this module's tests: hand it back at the
        # floor, or a later test measures whatever width this one left behind.
        wizard.resize(CONTRACT_MIN_WIDTH, UNCHANGED_MIN_HEIGHT)
        geom.settle(wizard)


# ---------------------------------------------------------------------------
# FR-029a -- both panes survive the floor
# ---------------------------------------------------------------------------

def test_tree_and_preview_stay_side_by_side_at_the_floor(narrow_case: Case) -> None:
    """FR-029a: both panes side by side at the floor; no reflow, stack, or hide.

    "Side by side" is asserted as a real geometric claim in the splitter's own
    coordinate space -- the tree's right edge at or left of the preview's left
    edge, and the two sharing vertical extent. A layout that stacked them
    vertically, or that gave one of them the full width and the other nothing,
    satisfies "both widgets exist" and fails this.

    `childrenCollapsible()` is the same requirement stated as a property: while
    a splitter allows collapse, the operator can drag the preview to zero width
    at any window size and Qt will do it for them as the width runs out.
    """
    _at_the_floor(narrow_case)
    wizard = narrow_case.wizard
    checked = 0
    problems: list[str] = []
    for pid, page, splitter in _iter_tree_pane_splitters(wizard):
        checked += 1
        where = f"page {pid} ({type(page).__name__})"
        tree, pane = _panes(splitter)
        sizes = splitter.sizes()

        if splitter.childrenCollapsible():
            problems.append(
                f"{where}: splitter is still collapsible -- either pane can be "
                f"dragged (or squeezed) to zero width"
            )
        if not tree.isVisible() or not pane.isVisible():
            problems.append(
                f"{where}: pane visibility tree={tree.isVisible()} "
                f"pane={pane.isVisible()} -- one of them is hidden at the floor"
            )
        if min(sizes) <= 0:
            problems.append(f"{where}: splitter sizes {sizes} -- a pane is collapsed")
            continue

        tree_rect = geom.rect_in(tree, splitter)
        pane_rect = geom.rect_in(pane, splitter)
        if tree_rect.width() <= 0 or pane_rect.width() <= 0:
            problems.append(
                f"{where}: zero-width pane, tree={tree_rect} pane={pane_rect}"
            )
            continue
        if tree_rect.right() > pane_rect.left():
            problems.append(
                f"{where}: panes are not side by side -- tree {tree_rect} "
                f"reaches past the left edge of pane {pane_rect}"
            )
        vertically_shares = (
            tree_rect.top() <= pane_rect.bottom()
            and pane_rect.top() <= tree_rect.bottom()
        )
        if not vertically_shares:
            problems.append(
                f"{where}: panes stacked rather than side by side -- tree "
                f"{tree_rect}, pane {pane_rect}"
            )

    assert checked >= MIN_TREE_PANE_PAGES, (
        f"[FAIL] found only {checked} tree-and-preview splitter(s) to check at "
        f"{narrow_case.label}; expected at least {MIN_TREE_PANE_PAGES}. Either "
        f"splitter discovery broke or the pages stopped using "
        f"_make_tree_pane_splitter -- either way this sweep is vacuous."
    )
    assert not problems, (
        f"[FAIL] FR-029a at {narrow_case.label}:\n  - " + "\n  - ".join(problems)
    )


def test_the_pane_minimums_sum_below_the_window_floor(narrow_case: Case) -> None:
    """FR-029a: pane minimums exist, and together they fit inside the floor.

    A non-collapsible splitter is only half the guarantee: without minimums Qt
    is free to shrink a pane to its own minimumSizeHint, which for a QTreeWidget
    is a couple of columns' worth of nothing. With minimums, the pane cannot be
    squeezed below a useful width -- but minimums that sum to more than the
    window floor make the floor unreachable, and Qt would silently clamp the
    window back up. Both halves are checked here: each pane has a minimum of its
    own, and the two sum below 900.
    """
    wizard = narrow_case.wizard
    checked = 0
    problems: list[str] = []
    for pid, page, splitter in _iter_tree_pane_splitters(wizard):
        checked += 1
        where = f"page {pid} ({type(page).__name__})"
        tree, pane = _panes(splitter)
        tree_min, pane_min = tree.minimumWidth(), pane.minimumWidth()
        if tree_min <= 0 or pane_min <= 0:
            problems.append(
                f"{where}: pane minimum widths are (tree={tree_min}, "
                f"pane={pane_min}); both must be set so neither pane can be "
                f"squeezed away at the floor"
            )
        if tree_min + pane_min >= CONTRACT_MIN_WIDTH:
            problems.append(
                f"{where}: pane minimums {tree_min} + {pane_min} = "
                f"{tree_min + pane_min} do not leave room inside the "
                f"{CONTRACT_MIN_WIDTH} px floor, so the floor is unreachable"
            )

    assert checked >= MIN_TREE_PANE_PAGES, (
        f"[FAIL] vacuous sweep: only {checked} splitter(s) found at "
        f"{narrow_case.label}"
    )
    assert not problems, (
        f"[FAIL] FR-029a at {narrow_case.label}:\n  - " + "\n  - ".join(problems)
    )


# ---------------------------------------------------------------------------
# FR-029b -- ellipsis and tooltip instead of a silent cut or a scrollbar
# ---------------------------------------------------------------------------

def test_no_page_acquires_a_horizontal_scrollbar_at_the_floor(
    narrow_case: Case,
) -> None:
    """FR-029b: "the page MUST NOT acquire a horizontal scrollbar" (SC-005).

    Both facts the harness reports are used. A *visible* bar is the literal
    requirement; a hidden bar with a non-zero `maximum` is the same defect with
    the symptom suppressed -- content wider than its viewport, unreachable
    without scrolling a bar that is not there.
    """
    _at_the_floor(narrow_case)
    wizard = narrow_case.wizard
    problems: list[str] = []
    for pid, page in geom.pages(wizard):
        geom.show_page(wizard, page)
        for bar in geom.horizontal_scrollbars(page):
            if bar.visible:
                problems.append(
                    f"page {pid} ({type(page).__name__}): {bar.name} shows a "
                    f"horizontal scrollbar (maximum {bar.maximum})"
                )
            elif bar.maximum > 0:
                problems.append(
                    f"page {pid} ({type(page).__name__}): {bar.name} is "
                    f"{bar.maximum} px wider than its viewport with the bar "
                    f"hidden -- content cut off without indication"
                )
    assert not problems, (
        f"[FAIL] FR-029b at {narrow_case.label}:\n  - " + "\n  - ".join(problems)
    )


def test_over_narrow_columns_elide_right_rather_than_cutting(
    narrow_case: Case,
) -> None:
    """FR-029b: over-narrow content "MUST be shortened with a visible ellipsis".

    Three properties per view, because Qt splits the job three ways and the
    default settings only get one of them right:

    * `textElideMode` -- the cells. Already ElideRight by default; asserted as a
      regression guard, since a page that sets ElideNone to "show everything"
      reintroduces the silent cut.
    * `header().textElideMode()` -- the column headings, which default to
      ElideNone and therefore *do* cut without indication at the floor today.
    * `horizontalScrollBarPolicy` -- ScrollBarAlwaysOff. FR-029b's ellipsis and
      its no-scrollbar clause are one decision: a view left on AsNeeded answers
      a too-narrow column by growing a bar instead of eliding.
    """
    wizard = narrow_case.wizard
    elide_right = QtCore.Qt.TextElideMode.ElideRight
    always_off = QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff

    checked = 0
    problems: list[str] = []
    for pid, page in geom.pages(wizard):
        for view in _tree_views(page):
            checked += 1
            where = f"page {pid} ({type(page).__name__}) {type(view).__name__}"
            if view.textElideMode() != elide_right:
                problems.append(
                    f"{where}: textElideMode is {view.textElideMode()!r}, "
                    f"expected ElideRight"
                )
            header = view.header()
            if header is not None and header.textElideMode() != elide_right:
                problems.append(
                    f"{where}: header textElideMode is "
                    f"{header.textElideMode()!r}, expected ElideRight -- a "
                    f"column heading too wide for its section is cut with no "
                    f"ellipsis at the floor"
                )
            if view.horizontalScrollBarPolicy() != always_off:
                problems.append(
                    f"{where}: horizontalScrollBarPolicy is "
                    f"{view.horizontalScrollBarPolicy()!r}, expected "
                    f"ScrollBarAlwaysOff -- FR-029b forbids the page acquiring "
                    f"a horizontal scrollbar, so the view must elide instead"
                )

    assert checked >= MIN_TREE_PANE_PAGES, (
        f"[FAIL] vacuous sweep: only {checked} tree view(s) examined at "
        f"{narrow_case.label}"
    )
    assert not problems, (
        f"[FAIL] FR-029b at {narrow_case.label}:\n  - " + "\n  - ".join(problems)
    )


def test_an_over_narrow_item_keeps_its_full_value_in_a_tooltip(
    narrow_case: Case,
) -> None:
    """FR-029b: "its full value MUST remain available to the operator on demand".

    Qt draws the ellipsis; nothing in Qt supplies the full string behind it. The
    tooltip is the "on demand" channel, and it only exists if something sets
    Qt::ToolTipRole on the item -- so the production module must own one helper
    that sets a cell's text and its full-value tooltip together, exactly as
    `_make_tree_pane_splitter` owns splitter construction. This test pins that
    helper:

        sw._set_item_text_with_tooltip(item, column, text)

    and requires that after the call the *data* is the untruncated value (no
    ellipsis baked into the model, which would corrupt the value FR-034 says is
    preserved exactly) and the tooltip is the untruncated value too.

    The value used is longer than the column it goes in -- verified here with
    the view's own font metrics, so the precondition holds at both text scales
    rather than being asserted on faith.
    """
    wizard = narrow_case.wizard
    helper = getattr(sw, "_set_item_text_with_tooltip", None)
    assert callable(helper), (
        "[FAIL] FR-029b: selection_wizard exposes no "
        "_set_item_text_with_tooltip(item, column, text) helper. Elided cells "
        "need one place that also records the full value as the item's tooltip; "
        "without it the ellipsis hides the value instead of standing in for it."
    )

    first = next(_iter_tree_pane_splitters(wizard), None)
    assert first is not None, (
        f"[FAIL] no tree-and-preview page found at {narrow_case.label}"
    )
    pid, page, splitter = first
    tree, _pane = _panes(splitter)
    assert isinstance(tree, QtWidgets.QTreeWidget), (
        f"[FAIL] page {pid} ({type(page).__name__}) left pane is "
        f"{type(tree).__name__}, expected a QTreeWidget"
    )

    long_value = (
        "Nominalising suffix attaching to transitive verbs of motion "
        "(Ejagham, class 7/8 concord)"
    )
    item = QtWidgets.QTreeWidgetItem()
    try:
        tree.addTopLevelItem(item)
        tree.setColumnWidth(0, 40)          # far narrower than the value
        helper(item, 0, long_value)
        geom.settle(page)

        metrics = QtGui.QFontMetrics(tree.font())
        assert metrics.horizontalAdvance(long_value) > tree.columnWidth(0), (
            "[FAIL] test precondition: the value fits column 0 after all, so "
            "nothing would be elided and the tooltip claim is untested"
        )
        assert item.text(0) == long_value, (
            f"[FAIL] FR-029b: the item's stored text is {item.text(0)!r}; the "
            f"model must keep the untruncated value and let the view elide it "
            f"for display."
        )
        assert item.toolTip(0) == long_value, (
            f"[FAIL] FR-029b: the item's tooltip is {item.toolTip(0)!r}, so the "
            f"full value behind the ellipsis is not available on demand."
        )
    finally:
        index = tree.indexOfTopLevelItem(item)
        if index >= 0:
            tree.takeTopLevelItem(index)     # shared wizard: leave no residue
        geom.settle(page)


# ---------------------------------------------------------------------------
# FR-030 / FR-031 / FR-032 / SC-005 -- nothing clipped, nothing overlapped,
# navigation still there, at both text scales
# ---------------------------------------------------------------------------

def test_nothing_is_clipped_on_any_page_at_the_floor(narrow_case: Case) -> None:
    """FR-030 / FR-032 / SC-005: no control clipped at the floor, at either scale.

    Parent-local rather than window-global on purpose (see `geom.clipped`): a
    label pushed past the right edge of its own container is clipped whatever
    the window is doing, and that parent-local escape is exactly what a narrowed
    window produces. Because `narrow_case` is parametrised over the default and
    the largest supported text scale, this single test is the FR-032
    ("narrowest width combined with the largest supported text scale") case as
    well as the FR-030 one.
    """
    _at_the_floor(narrow_case)
    wizard = narrow_case.wizard
    problems: list[str] = []
    for pid, page in geom.pages(wizard):
        geom.show_page(wizard, page)
        for clip in geom.clipped(page):
            problems.append(f"page {pid} ({type(page).__name__}): {clip!r}")
    assert not problems, (
        f"[FAIL] FR-030/FR-032 at {narrow_case.label} -- clipped widgets:\n  - "
        + "\n  - ".join(problems)
    )


def test_no_two_controls_are_drawn_over_each_other_at_the_floor(
    narrow_case: Case,
) -> None:
    """FR-030 / FR-032 / SC-005: nothing is "drawn over another control".

    Peer pairs only -- a container contains its children by construction, and
    the harness already excludes ancestor/descendant pairs, so every finding
    here is two widgets a layout was supposed to keep apart.
    """
    _at_the_floor(narrow_case)
    wizard = narrow_case.wizard
    problems: list[str] = []
    for pid, page in geom.pages(wizard):
        geom.show_page(wizard, page)
        rects = geom.visible_rects(page)
        assert rects, (
            f"[FAIL] page {pid} ({type(page).__name__}) reports no visible "
            f"widgets at {narrow_case.label} -- the page never laid out, so "
            f"this sweep would pass vacuously"
        )
        for overlap in geom.overlaps(rects):
            problems.append(f"page {pid} ({type(page).__name__}): {overlap!r}")
    assert not problems, (
        f"[FAIL] FR-030/FR-032 at {narrow_case.label} -- overlapping controls:"
        f"\n  - " + "\n  - ".join(problems)
    )


def test_the_navigation_buttons_stay_fully_visible_at_the_floor(
    narrow_case: Case,
) -> None:
    """FR-031: "the wizard's navigation controls MUST remain fully visible and operable".

    Three claims, one per way a 900 px window can take the buttons away:

    * the button row is still there at all -- Cancel plus an advance button
      (Next on any page but the last, Finish on the last), so a run that found
      no buttons fails rather than passing with an empty sweep;
    * each visible button sits wholly inside the window and inside its own
      parent's usable area, at 250% text as at 100% -- a button pushed off the
      right edge is not operable even though `isVisible()` is True;
    * no button overlaps the current page's content, which is the other way a
      too-short window "keeps" the buttons: by drawing them on top of the page.
    """
    _at_the_floor(narrow_case)
    wizard = narrow_case.wizard
    problems: list[str] = []

    for pid, page in geom.pages(wizard):
        geom.show_page(wizard, page)
        buttons = _visible_nav_buttons(wizard)
        names = {name for name, _ in buttons}
        if "CancelButton" not in names or not (
            names & {"NextButton", "FinishButton"}
        ):
            problems.append(
                f"page {pid} ({type(page).__name__}): visible navigation buttons "
                f"are {sorted(names)} -- expected Cancel plus Next or Finish"
            )

        page_rects = geom.visible_rects(page)
        for name, button in buttons:
            where = f"page {pid} ({type(page).__name__}) {name}"
            rect = geom.rect_in(button, wizard)
            if not wizard.rect().contains(rect):
                problems.append(
                    f"{where}: {rect} is not wholly inside the window "
                    f"{wizard.rect()} -- pushed off the edge at the floor"
                )
            parent = button.parentWidget()
            if parent is not None:
                allowed = geom.usable_rect(parent)
                if not allowed.contains(button.geometry()):
                    problems.append(
                        f"{where}: {button.geometry()} escapes its parent's "
                        f"usable area {allowed}"
                    )
            for item in page_rects:
                if rect.intersects(item.rect):
                    problems.append(
                        f"{where}: {rect} is drawn over page content "
                        f"{item.name} {item.rect}"
                    )

    assert not problems, (
        f"[FAIL] FR-031/FR-032 at {narrow_case.label}:\n  - "
        + "\n  - ".join(problems)
    )
