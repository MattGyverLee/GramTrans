"""Laid-out wizard page header: wrapping description + a controls slot (T038).

Why this module exists
---------------------
Before feature 036 the zoom / colour-mode strip (``theme.ThemeCornerBar``) was
parented to the wizard but **not laid out**: it ``move()``d itself to the
window's top-right corner in ``reposition()`` and ``raise_()``d itself above the
page, and it painted its own background specifically so that "a long wizard
subtitle ever running underneath" stayed legible.  Painting over the collision
is not a fix -- the collision is the defect (FR-004).  A step description that
wraps to a second or third line runs *under* the floating controls, and nothing
in any layout knows the controls are there, so nothing can move out of the way.

This header replaces positioning with **layout**.  A single ``QHBoxLayout``
gives the description the left cell (stretching) and the controls the right cell
(fixed to its own size hint).  A box layout allocates non-overlapping
x-intervals to its items by construction, so a description grown to *any*
wrapped height cannot intersect the controls: it grows the header's height
instead.  That is the binding assertion behind SC-005a -- geometry
non-intersection at the 900 px window floor and the largest supported text scale
(``theme.MAX_FONT_STEP`` steps of ``theme.FONT_STEP_INCREMENT`` = 2.5x) with the
wizard's longest description.

Deliberate non-coupling
-----------------------
This module imports **nothing from GramTrans** -- not even ``theme``.  The
controls widget is *injected* by the caller (the wizard, T042), never
constructed here.  Two reasons: the whole test suite runs with
``GRAMTRANS_NO_THEME=1`` pinned (root ``conftest.py``), so a header that reached
for an installed theme would be measuring a state the suite deliberately does
not create; and there must be exactly ONE control strip per wizard (so
``Ctrl+0`` / ``ZoomIn`` / ``ZoomOut`` are registered once, not once per page),
which means the strip's owner is the wizard and the header is only ever a
temporary host for it.

Contract (specs/036-wizard-ui-polish/contracts/wizard-ui.md, "Page header")
--------------------------------------------------------------------------
- ``header.description_label()`` -- a ``QLabel`` with ``wordWrap() is True``,
  carrying ``page.subTitle()`` (which stays the string of record; the wizard
  sets ``QWizard.WizardOption.IgnoreSubTitles`` so Qt stops drawing it twice).
  Wraps rather than truncating, and reserves no blank second line when the text
  fits on one.
- ``header.controls_slot()`` -- reserves its own space, so the description
  cannot run underneath the controls at any wrapped height.

No custom background is painted.  Layout is the fix; an opaque backdrop was the
workaround being removed.
"""
from __future__ import annotations

from typing import Optional

from PyQt6 import QtCore, QtWidgets


# Gap between the description's cell and the controls' cell.  Wide enough that
# the two read as separate regions at the 900 px floor, small enough that the
# description keeps most of the width for wrapping.
_CELL_SPACING = 12

# The header sits directly above page content, so it carries no left/right
# margin of its own (the page's own layout margin already inset it) and only a
# small breathing gap underneath.
_MARGINS = (0, 0, 0, 6)


class _ControlsSlot(QtWidgets.QWidget):
    """The right-hand cell: an empty, self-collapsing host for ONE strip.

    Lifecycle this has to survive (T042 keeps a single ``ThemeCornerBar`` for
    the whole wizard and moves it into the *current* page's header on
    ``currentIdChanged``):

    1. **Empty** -- every page's header is built before the strip exists, and
       every non-current page's header is empty at any given moment.  An empty
       slot must reserve nothing: its layout has no items, so its size hint is
       ``(0, 0)`` and the description takes the full width.
    2. **Filled** -- the strip is added to this widget's own ``QHBoxLayout``, so
       it is *laid out*, not positioned.  Its size hint is what makes this cell
       reserve space, which is the whole point of FR-004.
    3. **Emptied again** -- the strip is moved to another page's header.  Qt
       does this half for us: ``QLayout::widgetEvent`` handles
       ``QEvent::ChildRemoved`` and drops the reparented widget from this
       layout, so the cell collapses back to ``(0, 0)`` with no bookkeeping of
       ours.  :meth:`PageHeader.set_controls` detaches from the previous
       layout explicitly first, only so Qt does not log its
       "already in a layout; moved to new layout" warning on every page change.

    Case 2 has one trap worth the code below.  A caller who writes
    ``bar.setParent(slot)`` instead of using :meth:`PageHeader.set_controls`
    reparents the strip *without* putting it in any layout -- which reproduces
    the exact defect this widget exists to remove (an unmanaged child painting
    at whatever geometry it last had).  So an unlaid-out direct child is adopted
    into the layout automatically.  The adoption is deferred by a zero-timer
    rather than done inside ``childEvent``, because ``QLayout::addWidget``
    itself reparents: adopting synchronously would add a *second*
    ``QWidgetItem`` for the same widget on the normal path, since the outer
    ``addWidget`` call resumes and adds its own item after the ChildAdded event
    returns.  By the time the timer fires, the normal path has finished and
    ``indexOf`` reports the widget as already laid out, so the safety net costs
    nothing when it is not needed.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("gtPageHeaderControls")

        self._box = QtWidgets.QHBoxLayout(self)
        self._box.setContentsMargins(0, 0, 0, 0)
        self._box.setSpacing(0)

        # Fixed horizontally: the cell is exactly as wide as the strip asks for,
        # never wider, so every remaining pixel goes to the description.
        # Preferred vertically so a tall strip is not squashed.
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed,
                           QtWidgets.QSizePolicy.Policy.Preferred)

        # Child of self, so it dies with self -- a module-level
        # QTimer.singleShot(0, self._adopt) would fire into a deleted C++
        # object if the page were torn down in the same event loop turn.
        self._adopt_timer = QtCore.QTimer(self)
        self._adopt_timer.setSingleShot(True)
        self._adopt_timer.setInterval(0)
        self._adopt_timer.timeout.connect(self.adopt_orphans)

    # -- layout access ----------------------------------------------------
    def box(self) -> QtWidgets.QHBoxLayout:
        """The slot's own layout -- what a filled slot's child lives in."""
        return self._box

    def occupant(self) -> Optional[QtWidgets.QWidget]:
        """The widget currently laid out in the slot, or None when empty."""
        item = self._box.itemAt(0)
        return item.widget() if item is not None else None

    # -- the setParent safety net -----------------------------------------
    def childEvent(self, event: QtCore.QChildEvent) -> None:  # noqa: N802 -- Qt
        super().childEvent(event)
        if event.type() != QtCore.QEvent.Type.ChildAdded:
            return
        child = event.child()
        # The layout object and the timer are children too; only widgets can be
        # laid out.  `isWidgetType` is safe on a partially constructed child,
        # which is what this event carries.
        if child is None or not child.isWidgetType():
            return
        timer = getattr(self, "_adopt_timer", None)
        if timer is not None:
            timer.start()

    def adopt_orphans(self) -> None:
        """Put any direct child widget that is not in the layout into it.

        Public and synchronous so a caller that reparented by hand and needs
        final geometry *now* (a test reading rects without spinning the event
        loop, say) can force the adoption instead of waiting for the timer.
        """
        direct = QtCore.Qt.FindChildOption.FindDirectChildrenOnly
        adopted = False
        for child in self.findChildren(QtWidgets.QWidget, options=direct):
            if self._box.indexOf(child) >= 0:
                continue
            self._box.addWidget(child)
            child.show()
            adopted = True
        if adopted:
            self.updateGeometry()


class PageHeader(QtWidgets.QWidget):
    """A wizard page's header row: wrapping description | view controls.

    Usage (T041 installs one per flow page; T042 moves the one strip in):

        header = PageHeader(page)
        page.layout().addWidget(header)          # laid out, never raise_()d
        header.set_description(page.subTitle())  # subTitle stays the record
        ...
        header.set_controls(wizard.corner_bar()) # on becoming current

    The description's height is driven by height-for-width, so the header is
    exactly as tall as the text needs at the current width and text scale: one
    line when the text fits (FR-012 -- no blank second line reserved), three
    when 900 px at 250% text needs three (FR-013a -- absorbed, not clipped).
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("gtPageHeader")

        self._description = QtWidgets.QLabel(self)
        self._description.setObjectName("gtPageHeaderDescription")
        self._description.setWordWrap(True)
        self._description.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        # Text hugs the top-left of its cell, so a one-line description sits
        # level with the controls instead of floating in the middle of a cell
        # that a *sibling* made tall.
        self._description.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft
                                       | QtCore.Qt.AlignmentFlag.AlignTop)
        # Horizontal `Ignored`, not `Preferred`, on purpose.  A wrapping
        # QLabel's minimumSizeHint().width() is the width of its widest WORD, and
        # `Preferred` would make that a hard floor on the header -- so one long
        # word in one description could raise the wizard's 900 px minimum width
        # (FR-029) from a distance.  `Ignored` lets the label wrap as narrow as
        # the layout needs; the explicit stretch below is what actually hands it
        # all the width the controls did not take.
        #
        # Vertical `Preferred`, not `Minimum`: a wrapping QLabel's
        # sizeHint().height() is Qt's own aspect-ratio *guess* at how many lines
        # the text wants, which is frequently two.  `Minimum` (grow-only) would
        # turn that guess into a minimum height and reserve the blank second line
        # FR-012 forbids.  `Preferred` lets the minimum fall back to
        # minimumSizeHint() -- one line -- and leaves the real height to
        # height-for-width.
        self._description.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored,
                                        QtWidgets.QSizePolicy.Policy.Preferred)

        self._slot = _ControlsSlot(self)

        box = QtWidgets.QHBoxLayout(self)
        box.setContentsMargins(*_MARGINS)
        box.setSpacing(_CELL_SPACING)
        # Stretch 1 on the description and 0 on the slot: the two cells are
        # disjoint x-intervals, and every pixel the controls do not need is
        # width the description can wrap into.  No alignment flag on the
        # description, so its rect *is* its cell and can never escape the
        # header's contents rect (a stray alignment flag would size it to its
        # own sizeHint -- Qt's multi-line guess -- and that can exceed the cell).
        box.addWidget(self._description, 1)
        # AlignTop on the controls: when the description wraps to three lines the
        # strip stays up at the top edge where it was before this change, rather
        # than drifting down to the middle of a tall header.
        box.addWidget(self._slot, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        # `Minimum` vertically (grow-only) with a height-for-width layout: a
        # QBoxLayout substitutes heightForWidth() for both the sizeHint and the
        # minimumSize of an hfw item when it lays it out vertically, so the page
        # gives this header exactly the height its wrapped text needs.
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred,
                           QtWidgets.QSizePolicy.Policy.Minimum)

        # Empty text starts out occupying nothing at all (see set_description).
        self._description.setVisible(False)

    # -- description ------------------------------------------------------
    def description_label(self) -> QtWidgets.QLabel:
        """The wrapping ``QLabel`` that renders ``page.subTitle()``."""
        return self._description

    def description(self) -> str:
        """The description text currently displayed."""
        return self._description.text()

    def set_description(self, text: Optional[str]) -> None:
        """Show `text` as the description.  Pass ``page.subTitle()``.

        ``subTitle()`` remains the string of record: this is a render of it, not
        a second copy to keep in sync by hand.  An empty description hides the
        label outright, so a page with nothing to say reserves no line at all
        rather than a blank one -- the same principle as FR-012's "no blank
        second line", applied to the first line.
        """
        value = "" if text is None else str(text)
        self._description.setText(value)
        self._description.setVisible(bool(value))
        # setText on a wrapping label invalidates its cached hints, but the
        # parent chain is only told when we ask; without this a description
        # changed after the page was shown keeps the previous text's height.
        self._description.updateGeometry()
        self.updateGeometry()

    # -- controls ---------------------------------------------------------
    def controls_slot(self) -> QtWidgets.QWidget:
        """The widget the view-control strip is laid out inside.

        Prefer :meth:`set_controls` over ``strip.setParent(header.controls_slot())``:
        both end up laid out (the slot adopts an unmanaged child on the next
        event-loop turn), but ``set_controls`` is synchronous and does not make
        Qt log a warning about stealing the strip from the previous page's slot.
        """
        return self._slot

    def controls(self) -> Optional[QtWidgets.QWidget]:
        """The strip currently in the slot, or None while the slot is empty."""
        return self._slot.occupant()

    def set_controls(self, widget: Optional[QtWidgets.QWidget]) -> None:
        """Move `widget` into the controls slot (``None`` empties the slot).

        Written for the one-strip-many-pages lifecycle: the strip usually
        arrives still laid out in *another* page's header, so it is detached
        from that layout first.  ``QLayout::addWidget`` would do the same thing
        on its own, but with a warning on stderr every single page change.
        """
        if widget is None:
            self.take_controls()
            return

        current = self._slot.occupant()
        if current is widget:
            return

        # Detach from wherever it is now, quietly.
        old_parent = widget.parentWidget()
        old_layout = old_parent.layout() if old_parent is not None else None
        if (old_layout is not None and old_layout is not self._slot.box()
                and old_layout.indexOf(widget) >= 0):
            old_layout.removeWidget(widget)

        self._slot.box().addWidget(widget)
        # Reparenting hides a widget; Qt would re-show it via a queued call, but
        # that leaves the slot's size hint at (0, 0) for one event-loop turn --
        # long enough for a caller measuring geometry straight after the move to
        # read a collapsed cell.
        widget.show()
        self._slot.updateGeometry()
        self.updateGeometry()

    def take_controls(self) -> Optional[QtWidgets.QWidget]:
        """Remove and return the strip, leaving the slot empty and collapsed.

        The strip keeps this slot as its Qt parent (reparenting it to ``None``
        would turn it into a top-level window) but is removed from the layout
        and hidden -- hidden because an unlaid-out visible child painting at its
        last geometry is precisely the floating-control defect being removed.
        The next header's :meth:`set_controls` reparents and re-shows it.
        """
        widget = self._slot.occupant()
        if widget is None:
            return None
        self._slot.box().removeWidget(widget)
        widget.hide()
        self._slot.updateGeometry()
        self.updateGeometry()
        return widget
