"""Shared offscreen geometry harness for the 036 wizard-UI tests.

WHY this exists as one module rather than three copies
-----------------------------------------------------
Three separate success criteria are, underneath, the same measurement:

* **SC-005** (US3) -- the window narrows to 900 px with nothing clipped,
  nothing overlapped, and no page growing a horizontal scrollbar.
* **SC-005a** (US6) -- the zoom / colour-mode controls never overlap the step
  title or the step description, "verified at 900 pixels and the largest
  supported text scale".
* **SC-009** (US8) -- every step description fits its budget, and at 900 px or
  a raised text scale the extra wrapped line is absorbed without clipping.

All three hinge on the phrase "900 px at the largest supported text scale".
If each test spelled that out for itself, the three would drift: one would
`resize(900, 680)` and forget that Qt clamps to `minimumSize`, another would
scale the font but build the wizard *before* applying the scale (the pages
snapshot the application font into per-item QFonts while they build their
trees -- see `SelectionWizard.__init__`'s comment on `install_theme()`), and a
third would compare rects that live in different parents' coordinate systems,
where "does not intersect" means nothing at all. This module fixes one answer
to each of those questions:

* `MIN_WINDOW_WIDTH` / `MAX_TEXT_SCALE` -- the stress case, named once.
* `wizard_at(...)` -- scale first, construct second, restore always.
* `rect_in(widget, root)` -- every rect mapped into one common coordinate
  space via `mapTo`, so non-intersection is a real claim.

Why the scale is applied to the QApplication font and NOT via ThemeManager
--------------------------------------------------------------------------
The root `conftest.py` pins `GRAMTRANS_NO_THEME=1` for the whole suite (see
its comment at line 25 onwards): `install_theme()` returns False and the
palette, style and font are left alone, precisely so a developer's saved
160% text size cannot make their suite differ from CI's. That means there is
no installed theme for a test to turn a font step on -- and asking the
ThemeManager to install one would re-introduce exactly the shared-state
leakage the pin exists to prevent. So `text_scale()` multiplies the point size
of `QApplication.font()` directly and restores the previous font on exit.
Qt propagates an application-font change to every widget that has not been
given an explicit font of its own, which is what the wizard's widgets are, so
this reproduces what a raised text step does to layout. The *numeric* ceiling
is still taken from the theme (`MAX_FONT_STEP`), so the harness cannot claim
to test a scale the product does not offer.

This is a HELPER module, not a test module: nothing in it is named `test_*`.
`tests/unit` is on `sys.path` (root `conftest.py`), so consumers write
`import _ui_geometry as geom`.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterable, Iterator, NamedTuple, Optional, Sequence

# SC-007 convention, and a hard requirement here: the offscreen platform must
# be chosen before Qt is imported or the import binds the real windowing
# system and the suite needs a display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

PyQt6 = pytest.importorskip("PyQt6")

from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402

from gramtrans.Lib.ui import selection_wizard as sw  # noqa: E402
from gramtrans.Lib.ui import theme as gt_theme  # noqa: E402


# ---------------------------------------------------------------------------
# The stress case, declared once
# ---------------------------------------------------------------------------

#: The narrow-window floor (FR-029). Read from the wizard module when it
#: declares the constant, so this harness follows the product rather than
#: asserting a second opinion; 900 is the contract value and the fallback for
#: the window in which T023 has not landed yet. A test that wants to *assert*
#: the declaration exists must still read `sw.MIN_WINDOW_WIDTH` itself -- this
#: getattr must not be allowed to launder a missing constant into a pass.
MIN_WINDOW_WIDTH: int = int(getattr(sw, "MIN_WINDOW_WIDTH", 900))

#: The height floor is unchanged by feature 036 (contract: "Unchanged from
#: today (680)"), and is here only so a caller can ask for the floor in both
#: axes without repeating the number.
MIN_WINDOW_HEIGHT: int = int(getattr(sw, "MIN_WINDOW_HEIGHT", 680))

#: "The largest supported text scale" -- derived from the theme's own clamp
#: (`MAX_FONT_STEP` steps of `FONT_STEP_INCREMENT`) rather than hard-coded, so
#: raising the product's ceiling automatically raises what the tests stress.
MAX_TEXT_SCALE: float = round(
    1.0 + gt_theme.FONT_STEP_INCREMENT * gt_theme.MAX_FONT_STEP, 4
)

#: The default scale, for symmetry at call sites that vary only the width.
DEFAULT_TEXT_SCALE: float = 1.0

#: How long a widget's text is allowed to be in a failure message. Rects are
#: useless to debug without knowing *which* label overlapped which button, but
#: a full step description in a pytest diff buries the numbers.
_LABEL_TEXT_CHARS = 44


# ---------------------------------------------------------------------------
# Fixtures-in-a-function: the pieces every wizard-construction test needs
# ---------------------------------------------------------------------------

class Sink:
    """The four methods a FlexTools report sink has, remembering the calls.

    Same shape as `_Sink` in `test_034_step1_source_picker.py`; lifted here so
    the three consumer tests do not each re-declare it. `lines` is a list of
    `(kind, message)` pairs in call order.
    """

    def __init__(self) -> None:
        self.lines: list[tuple[str, str]] = []

    def Info(self, msg=""):  # noqa: N802 -- FlexTools naming
        self.lines.append(("info", msg))

    def Warning(self, msg=""):  # noqa: N802 -- FlexTools naming
        self.lines.append(("warn", msg))

    def Error(self, msg=""):  # noqa: N802 -- FlexTools naming
        self.lines.append(("error", msg))

    def Blank(self):  # noqa: N802 -- FlexTools naming
        self.lines.append(("blank", ""))


def projects_tree(root: Path | str, names: Iterable[str] = ("Alpha", "Beta")) -> Path:
    """Make `root` look like a FLEx projects root: `<name>/<name>.fwdata`.

    The wizard's source and target candidate lists scan for that shape, so a
    `projects_root` without it yields an empty picker and a step-1 page that
    never becomes complete -- which reads, from a geometry test, as a layout
    bug rather than as a missing fixture. Returns `root` for chaining.
    """
    root = Path(root)
    for name in names:
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.fwdata").write_text("<!-- fixture -->", encoding="utf-8")
    return root


def ensure_qapp() -> QtWidgets.QApplication:
    """The one process-wide QApplication, created on first need.

    Consumers keep their own session-scoped `qapp` fixture (suite convention);
    this exists so the harness's own helpers work whichever order things run
    in, and so `text_scale()` can be used before any fixture has run.
    """
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def needs_a_real_qwizard() -> None:
    """Skip when a sibling module has swapped a QWizard double into PyQt6.

    `test_wizard_page_flow.py` and `test_ui_gating.py` install a Qt double at
    import time and overwrite `QtWidgets.QWizard` / `QWizardPage` on whatever
    is in `sys.modules` -- including the real extension module, when real
    PyQt6 was imported first. Constructing a real wizard is then impossible
    for the rest of the session, so every geometry test in this feature has to
    be able to bow out cleanly. The tell is that the double carries no nested
    `WizardStyle` enum type. Copied from
    `test_034_step1_source_picker.py:_needs_a_real_qwizard`.
    """
    if not isinstance(getattr(QtWidgets.QWizard, "WizardStyle", None), type):
        pytest.skip("a PyQt6 double is installed in this session (see docstring)")


# ---------------------------------------------------------------------------
# Text scale
# ---------------------------------------------------------------------------

@contextmanager
def text_scale(scale: float) -> Iterator[QtGui.QFont]:
    """Run the body with the application font multiplied by `scale`.

    Point-size fonts are scaled in points; a pixel-sized font (some Linux
    offscreen defaults) is scaled in pixels, because `setPointSizeF` on a
    pixel-sized font silently discards the pixel size. The previous font
    object is restored on the way out -- including on an exception -- so a
    failing geometry assertion cannot leave every later Qt test running at
    the maximum text scale.

    Yields the scaled font, which is occasionally useful for a QFontMetrics
    computation in the caller.
    """
    app = ensure_qapp()
    previous = QtGui.QFont(app.font())
    scaled = QtGui.QFont(previous)
    if previous.pointSizeF() > 0:
        scaled.setPointSizeF(previous.pointSizeF() * float(scale))
    else:
        scaled.setPixelSize(max(1, int(round(previous.pixelSize() * float(scale)))))
    app.setFont(scaled)
    try:
        yield scaled
    finally:
        # setFont, not a saved-and-mutated object: Qt keeps a copy, so handing
        # back the original instance is enough to undo the propagation.
        app.setFont(previous)


# ---------------------------------------------------------------------------
# Building the wizard
# ---------------------------------------------------------------------------

def build_wizard(
    tmp_path: Path | str,
    *,
    width: int = MIN_WINDOW_WIDTH,
    height: int = MIN_WINDOW_HEIGHT,
    projects: Sequence[str] = ("Alpha", "Beta"),
    source_binder: Optional[Callable[[str], object]] = None,
    report_sink=None,
    modify_allowed: bool = True,
    show: bool = True,
) -> QtWidgets.QWizard:
    """A real `SelectionWizard`, shown offscreen and resized to `width` x `height`.

    The construction call is the verified pattern from
    `test_034_step1_source_picker.py:test_the_wizard_constructs_with_no_source_at_all`
    -- no host project, a source binder, and a `projects_root` that has the
    `<name>/<name>.fwdata` shape.

    `show=True` (the default) is not cosmetic: before a widget is shown its
    children have their pre-layout guess geometry and `isVisible()` is False
    for all of them, so *every* rect this module returns would be a fiction.
    The offscreen platform makes showing free.

    Note the wizard clamps `resize()` against its own `minimumSize`, so
    `wizard.width()` can come back larger than `width` -- that is the FR-029
    finding, not a harness bug. Callers asserting the floor should compare
    `wizard.minimumWidth()` against `sw.MIN_WINDOW_WIDTH` directly, and use
    `at_requested_width()` when they need to know whether the resize took.
    """
    ensure_qapp()
    needs_a_real_qwizard()
    root = projects_tree(tmp_path, projects)
    wizard = sw.SelectionWizard(
        None, report_sink if report_sink is not None else Sink(), modify_allowed,
        source_project_name="",
        projects_root=str(root),
        source_binder=source_binder or (lambda name: object()),
    )
    wizard.resize(int(width), int(height))
    if show:
        wizard.show()
    settle(wizard)
    return wizard


@contextmanager
def wizard_at(
    tmp_path: Path | str,
    *,
    width: int = MIN_WINDOW_WIDTH,
    height: int = MIN_WINDOW_HEIGHT,
    scale: float = DEFAULT_TEXT_SCALE,
    **kwargs,
) -> Iterator[QtWidgets.QWizard]:
    """The canonical "wizard at this width and this text scale" -- one way, three tests.

    Order matters and is the whole reason this is a context manager rather
    than two calls: the scale goes on **before** construction because the
    pages copy the application font into per-item QFonts as they build their
    trees, so a scale applied afterwards leaves every bolded header at the old
    size and the measured geometry is a mixture of two scales.

    The stress case named in SC-005a and SC-009 is therefore exactly:

        with geom.wizard_at(tmp_path, width=geom.MIN_WINDOW_WIDTH,
                            scale=geom.MAX_TEXT_SCALE) as wizard:
            ...

    On exit the wizard is closed and scheduled for deletion before the font is
    restored, so no live widget is left holding the scaled font and leaking it
    into the next test.
    """
    with text_scale(scale):
        wizard = build_wizard(tmp_path, width=width, height=height, **kwargs)
        try:
            yield wizard
        finally:
            wizard.close()
            wizard.deleteLater()
            settle(None)


def at_requested_width(wizard: QtWidgets.QWidget, width: int) -> bool:
    """Did the resize actually take, or did `minimumWidth` clamp it?"""
    return wizard.width() <= int(width)


def settle(widget: Optional[QtWidgets.QWidget]) -> None:
    """Flush pending layout and paint work so geometry is final.

    Qt defers layout to the event loop. Without this, a rect read immediately
    after `resize()` is the *previous* layout's answer and the whole harness
    silently measures the wrong window.
    """
    app = ensure_qapp()
    if widget is not None:
        layout = widget.layout()
        if layout is not None:
            layout.activate()
        widget.updateGeometry()
    app.processEvents()
    if widget is not None:
        app.sendPostedEvents(widget, QtCore.QEvent.Type.LayoutRequest)
        app.processEvents()


def pages(wizard: QtWidgets.QWizard) -> list[tuple[int, QtWidgets.QWizardPage]]:
    """`(page_id, page)` for every page registered with the wizard, in id order."""
    return [(pid, wizard.page(pid)) for pid in sorted(wizard.pageIds())]


def show_page(
    wizard: QtWidgets.QWizard, page: QtWidgets.QWizardPage
) -> QtWidgets.QWizardPage:
    """Make `page` the current page and let its layout settle.

    `setStartId` + `restart()` rather than repeated `next()`: a geometry test
    must be able to reach page 9 without satisfying eight advance gates, and
    the gates are somebody else's assertions. Returns the page, so a caller
    can write `rects = geom.visible_rects(geom.show_page(w, w.page_rules()))`.
    """
    for pid, candidate in pages(wizard):
        if candidate is page:
            wizard.setStartId(pid)
            wizard.restart()
            settle(wizard)
            settle(page)
            return page
    raise LookupError(f"page {page!r} is not registered with {wizard!r}")


# ---------------------------------------------------------------------------
# Rects, in one coordinate space
# ---------------------------------------------------------------------------

class WidgetRect(NamedTuple):
    """A visible widget and its rect in the chosen root's coordinate space."""

    name: str
    widget: QtWidgets.QWidget
    rect: QtCore.QRect


class Overlap(NamedTuple):
    """Two peer widgets whose rects intersect, and the intersection."""

    a: WidgetRect
    b: WidgetRect
    area: QtCore.QRect

    def __repr__(self) -> str:  # pragma: no cover -- failure messages only
        return (f"{self.a.name} overlaps {self.b.name} by "
                f"{self.area.width()}x{self.area.height()} px at "
                f"({self.area.x()},{self.area.y()})")


class Clip(NamedTuple):
    """A visible child whose rect escapes its parent's usable area."""

    child: str
    parent: str
    child_rect: QtCore.QRect
    parent_rect: QtCore.QRect

    def __repr__(self) -> str:  # pragma: no cover -- failure messages only
        return (f"{self.child} {_r(self.child_rect)} escapes "
                f"{self.parent} {_r(self.parent_rect)}")


class ScrollBar(NamedTuple):
    """A horizontal scrollbar found on a descendant scroll area."""

    name: str
    widget: QtWidgets.QWidget
    visible: bool
    maximum: int


def _r(rect: QtCore.QRect) -> str:
    return f"[{rect.x()},{rect.y()} {rect.width()}x{rect.height()}]"


def describe(widget: QtWidgets.QWidget) -> str:
    """A short, stable, ASCII-only identifier for failure messages."""
    parts = [type(widget).__name__]
    name = widget.objectName()
    if name:
        parts.append(f"#{name}")
    text = ""
    for getter in ("text", "title", "placeholderText"):
        fn = getattr(widget, getter, None)
        if callable(fn):
            try:
                text = str(fn() or "")
            except TypeError:  # a getter that wants arguments (e.g. a view's)
                text = ""
            if text:
                break
    if text:
        flat = " ".join(text.split())
        if len(flat) > _LABEL_TEXT_CHARS:
            flat = flat[:_LABEL_TEXT_CHARS - 3] + "..."
        parts.append(f" {flat!r}")
    return "".join(parts)


def rect_in(widget: QtWidgets.QWidget, root: QtWidgets.QWidget) -> QtCore.QRect:
    """`widget`'s rect expressed in `root`'s coordinate space.

    This is the point of the harness. Two widgets under different parents have
    rects in different origins, so comparing their `geometry()` values --
    which is the obvious thing to write -- compares two unrelated numbers and
    "they do not intersect" is worthless. `mapTo` walks the parent chain and
    puts both into one space. When `root` is not an ancestor (a floating bar
    parented elsewhere, say) we fall back to global coordinates translated
    into `root`, which is equivalent but slower.
    """
    size = widget.size()
    if root.isAncestorOf(widget):
        origin = widget.mapTo(root, QtCore.QPoint(0, 0))
    elif widget is root:
        origin = QtCore.QPoint(0, 0)
    else:
        origin = widget.mapToGlobal(QtCore.QPoint(0, 0)) - root.mapToGlobal(
            QtCore.QPoint(0, 0)
        )
    return QtCore.QRect(origin, size)


def visible_widgets(
    page: QtWidgets.QWidget,
    *,
    include: Optional[Callable[[QtWidgets.QWidget], bool]] = None,
) -> list[QtWidgets.QWidget]:
    """Every visible, non-degenerate descendant widget of `page`.

    Hidden widgets are dropped because a hidden widget's geometry is whatever
    it was when it was last laid out, which produces phantom overlaps. Empty
    rects are dropped because a 0-wide widget intersects nothing and clips
    nothing, so it can only add noise.
    """
    out: list[QtWidgets.QWidget] = []
    for w in page.findChildren(QtWidgets.QWidget):
        if not w.isVisible() or w.size().isEmpty():
            continue
        if include is not None and not include(w):
            continue
        out.append(w)
    return out


def visible_rects(
    page: QtWidgets.QWidget,
    *,
    root: Optional[QtWidgets.QWidget] = None,
    include: Optional[Callable[[QtWidgets.QWidget], bool]] = None,
) -> list[WidgetRect]:
    """Walk the visible widgets of `page` and return their rects.

    `root` defaults to the page's window (the wizard), which is the space the
    three consumer tests care about: it is where the page header, the page
    content and the wizard's own navigation buttons and corner bar can all be
    compared against one another.
    """
    root = root if root is not None else (page.window() or page)
    return [
        WidgetRect(describe(w), w, rect_in(w, root))
        for w in visible_widgets(page, include=include)
    ]


# ---------------------------------------------------------------------------
# The three assertions the consumers make
# ---------------------------------------------------------------------------

def overlaps(
    items: Sequence[WidgetRect],
    *,
    tolerance: int = 0,
) -> list[Overlap]:
    """Pairwise non-intersection, over peers only.

    A naive all-pairs check is guaranteed to "fail": a parent contains its
    children by construction, so every container overlaps everything inside
    it. Only pairs where neither widget is an ancestor of the other are a
    genuine claim -- those are the widgets that a layout is supposed to keep
    apart, and an intersection between two of them is the bug SC-005a is
    about (a control strip sitting on top of a wrapped description).

    `tolerance` shrinks each rect by that many pixels per side before the
    test, for the rare case where a 1 px shared border between two frames is
    not the finding you are after. Note Qt's inclusive-edge convention already
    means two exactly-adjacent rects do NOT intersect, so 0 is the right
    default.
    """
    found: list[Overlap] = []
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if a.widget.isAncestorOf(b.widget) or b.widget.isAncestorOf(a.widget):
                continue
            ra = a.rect.adjusted(tolerance, tolerance, -tolerance, -tolerance)
            rb = b.rect.adjusted(tolerance, tolerance, -tolerance, -tolerance)
            if ra.isEmpty() or rb.isEmpty():
                continue
            if ra.intersects(rb):
                found.append(Overlap(a, b, ra.intersected(rb)))
    return found


def usable_rect(parent: QtWidgets.QWidget, *, contents: bool = False) -> QtCore.QRect:
    """The area of `parent` a child is allowed to occupy, in `parent`'s space.

    For a scroll area the answer is the viewport, not the frame: content that
    extends past the viewport is unreachable without scrolling, which is the
    clipping SC-005 forbids. For anything else it is `rect()` by default --
    `contents=True` tightens it to `contentsRect()`, which excludes layout
    margins and a group box's title strip, and is the stricter reading of
    "sits inside its parent".
    """
    if isinstance(parent, QtWidgets.QAbstractScrollArea):
        viewport = parent.viewport()
        if viewport is not None:
            # Children of the scroll AREA (viewport, scrollbars, frame) are
            # bounded by the frame; children of the VIEWPORT are bounded by
            # the viewport. `usable_rect` is called with the actual parent, so
            # reaching here means the parent is the area itself.
            return parent.rect()
    return parent.contentsRect() if contents else parent.rect()


def clipped(
    page: QtWidgets.QWidget,
    *,
    contents: bool = False,
    tolerance: int = 0,
    skip: Optional[Callable[[QtWidgets.QWidget], bool]] = None,
) -> list[Clip]:
    """Visible widgets whose rect escapes their parent's usable area.

    This is the "nothing is cut off" half of SC-005. It is deliberately
    parent-local rather than window-global: a label pushed past the right edge
    of its own container is clipped even if the window happens to be wide
    enough, and that parent-local failure is what a 900 px reflow produces.

    `skip` lets a caller exempt a widget that is *meant* to exceed its parent
    -- the tall content widget of a deliberately vertical scroll area, for
    instance. Prefer exempting it here over loosening `tolerance`.
    """
    out: list[Clip] = []
    for w in visible_widgets(page):
        if skip is not None and skip(w):
            continue
        parent = w.parentWidget()
        if parent is None or w.isWindow():
            continue
        allowed = usable_rect(parent, contents=contents).adjusted(
            -tolerance, -tolerance, tolerance, tolerance
        )
        if not allowed.contains(w.geometry()):
            out.append(Clip(describe(w), describe(parent), w.geometry(), allowed))
    return out


def horizontal_scrollbars(
    page: QtWidgets.QWidget, *, include_internal: bool = False
) -> list[ScrollBar]:
    """Every descendant scroll area, with the state of its horizontal bar.

    Both facts are reported. `visible` is the literal question FR-029b asks
    ("no page acquires a horizontal scrollbar"), and `maximum` is the
    corroborating one: a bar can be policy-hidden while the content is still
    wider than the viewport, which is clipping wearing a different hat.

    `QHeaderView` is a `QAbstractScrollArea` too, so every table contributes
    two extra entries that can never be a finding -- a header scrolls by
    following its view's offset, never by showing a bar of its own. They are
    dropped unless `include_internal=True`, so the returned list is short
    enough to put straight into an assertion message.
    """
    out: list[ScrollBar] = []
    for area in page.findChildren(QtWidgets.QAbstractScrollArea):
        if not area.isVisible():
            continue
        if not include_internal and isinstance(area, QtWidgets.QHeaderView):
            continue
        bar = area.horizontalScrollBar()
        if bar is None:
            continue
        out.append(ScrollBar(describe(area), area, bool(bar.isVisible()),
                             int(bar.maximum())))
    return out


def has_horizontal_scrollbar(page: QtWidgets.QWidget) -> bool:
    """Does this page contain a widget with a visible horizontal scrollbar?"""
    return any(sb.visible for sb in horizontal_scrollbars(page))


# ---------------------------------------------------------------------------
# Wrapped-text budget (SC-009)
# ---------------------------------------------------------------------------

def wrapped_line_count(label: QtWidgets.QLabel, *, width: Optional[int] = None) -> int:
    """How many lines `label`'s text occupies at `width` (default: its own).

    SC-009 is stated in lines, not pixels, so it needs a line count rather
    than a rect. Measured with the label's *own* QFontMetrics so a raised
    application font is reflected, and divided by `lineSpacing()` because that
    -- not `height()` -- is the pitch Qt lays wrapped text out on. Returns 0
    for an empty label, which is how a caller distinguishes "fits on one line"
    from "has nothing to say".
    """
    text = " ".join((label.text() or "").split())
    if not text:
        return 0
    w = int(width) if width is not None else max(1, label.contentsRect().width())
    metrics = QtGui.QFontMetrics(label.font())
    flags = int(QtCore.Qt.TextFlag.TextWordWrap)
    bounds = metrics.boundingRect(QtCore.QRect(0, 0, w, 10_000), flags, text)
    spacing = max(1, metrics.lineSpacing())
    return max(1, int(round(bounds.height() / spacing)))
