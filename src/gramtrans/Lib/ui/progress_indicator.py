"""Progress reporting surface -- the Qt half (feature 036, US1).

Two modules, one protocol. ``Lib/progress.py`` carries the protocol, the null
implementation, the one threshold and the anticipated-cost arithmetic, and is
**toolkit-free by contract** because ``Lib/selection.py`` imports it and must
stay importable with no application object. THIS module is the only Qt
implementation of that protocol, and it is imported only by the wizard.

WHY ONE DIALOG FOR THE WHOLE APPLICATION, NOT ONE PER SINK
----------------------------------------------------------
FR-021: concurrent or nested operations must present at most ONE indicator,
describing the work currently in progress. Inventory walks nest -- a page's
builder calls a sub-walk that reports too -- and each wizard page builds its own
sink, so "one per sink" would put two windows on screen for one wait. The dialog
and the label stack are therefore module state (``_DIALOG``, ``_STACK``), and a
``QtProgressSink`` is a thin handle onto them:

- ``begin`` pushes a level and re-labels the one dialog;
- ``end`` pops its own level and restores whatever level is now on top, so an
  inner walk finishing puts the OUTER operation's name back on screen;
- only the pop that empties the stack dismisses.

Each sink remembers which levels it pushed, so a stray ``end`` from a sink that
never began -- or one ``end`` too many -- can never pop a level belonging to
somebody else's operation.

WHY ``tick`` PUMPS THE EVENT LOOP, AND WHY IT IS THROTTLED
----------------------------------------------------------
These walks are synchronous: the wizard calls into the lexicon on the GUI
thread. Nothing repaints while that call runs, and after a couple of seconds the
operating system paints the window over as "not responding" (FR-018, SC-002).
Handing the toolkit a pass of the event loop from inside the walk is what keeps
the window alive -- and it is also what lets the deferred indicator appear at
all, since a timer cannot fire in an event loop that never runs.

Pumping on EVERY tick would be a cure worse than the disease: a walk over a
million entries would spend its life in the event loop rather than in the
lexicon. So the pump is throttled by ELAPSED TIME (``PUMP_INTERVAL_MS``), not by
a tick count. A count-based throttle behaves completely differently for a
100-unit walk than for a 10-million-unit one -- the same "every thousandth tick"
is nothing on one and ten thousand repaints on the other -- whereas a time-based
one repaints at a fixed rate whatever the tick rate, which is precisely the
property "the window keeps repainting" needs. Between pumps a tick costs one
integer add, one comparison and one monotonic clock read; the widget is not
touched at all, which matters because ``QProgressDialog.setValue`` runs an event
loop pass of its own on a modal dialog.

WHY THE ELAPSED-TIME FALLBACK IS ENFORCED TWICE
-----------------------------------------------
``deferred()`` sets the dialog's own minimum duration to
``PROGRESS_THRESHOLD_MS``: that setting IS the FR-014b fallback, and it is the
toolkit's supported mechanism. But the toolkit arms its internal timer only when
the bar sits exactly at its minimum, which does not hold for an indeterminate
range on every version, and the timer can only fire when the event loop runs. So
the pump path ALSO compares elapsed time against the same
``PROGRESS_THRESHOLD_MS`` and shows the dialog itself. Two mechanisms, one
number (FR-019a) -- there is no second threshold to drift.

Known constraint, for whoever wires the project binds (FR-023 rows 1-2): an
operation that never ticks cannot be repainted from a single thread, so a bind
that is one blocking call shows nothing until it returns. Fixing that needs
either a worker thread or a pump around the call, neither of which belongs in a
sink.

WHY NO COLOUR
-------------
``Lib/ui/theme.py`` owns every colour in this application, and installs itself
by mutating the shared application palette. An indicator that set a colour of
its own would be the one widget that ignored the operator's light/dark choice --
so this module sets none at all and inherits, which is why a wait entered in
dark mode shows a dark indicator. ``test_qt_sink_hard_codes_no_colour`` enforces
the absence.

WHY NO CANCEL AFFORDANCE
------------------------
Cancellation is explicitly out of scope for this feature, so a cancel button
would be an affordance that does nothing. Worse, the toolkit's default escape
and close routes would HIDE the indicator while the walk kept running, which
unblocks the wizard mid-read -- exactly the re-entrant database access FR-018
exists to prevent. ``_NoCancelProgressDialog`` closes those routes.

ASCII only: Windows terminals mangle anything else (house rule), so labels
spell an ellipsis as three periods.
"""

from __future__ import annotations

import contextlib
import logging
import time
from typing import List, Optional

from PyQt6 import QtCore, QtGui, QtWidgets

if __package__:
    from ..progress import PROGRESS_THRESHOLD_MS
else:  # pragma: no cover - direct-script import path, mirrors sibling modules
    from progress import PROGRESS_THRESHOLD_MS  # type: ignore

logger = logging.getLogger(__name__)


# ===========================================================================
# The pump throttle
# ===========================================================================

PUMP_INTERVAL_MS = 40
"""Shortest gap between two event-loop passes driven from inside a walk.

40 ms is 25 repaints a second: above the rate at which motion reads as
continuous rather than as a stutter, and below the rate at which the pump starts
costing more than the work it is interleaved with. It also bounds how late the
elapsed-time fallback can put the indicator up (one interval past
``PROGRESS_THRESHOLD_MS``), which is why it must stay well under that threshold.

This is NOT a second progress threshold. It is a repaint rate, it is not
per-operation, and nothing compares it to a predicted duration.
"""


def _now_ms() -> int:
    """Monotonic milliseconds.

    A plain monotonic clock rather than a toolkit timer object: this is read on
    every single tick, so it must not cross the Python/C++ boundary, and it must
    not be affected by the system clock being adjusted mid-walk. Module-level so
    tests can drive the throttle and the elapsed-time fallback deterministically
    instead of sleeping.
    """
    return time.monotonic_ns() // 1_000_000


def _pump_events() -> None:
    """Give the toolkit one pass of the event loop (FR-018, SC-002).

    Guarded on there being an application at all: a sink constructed in a
    headless context degrades to doing nothing rather than raising, because a
    display fault must never be the error the operator sees.
    """
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()


# ===========================================================================
# The dialog
# ===========================================================================


class _NoCancelProgressDialog(QtWidgets.QProgressDialog):
    """A progress dialog with no way out (FR-018).

    Cancellation is out of scope, and the cancel button is removed for that
    reason. But removing the button leaves two routes that would still HIDE the
    dialog -- the Escape key, which the base class turns into a rejection, and
    the window's close box. Either one would drop the modal block while the walk
    kept running, unblocking the wizard for a re-entrant read of the lexical
    database. Both are refused here.

    A wait that never finishes is therefore only escapable through the operating
    system, which the spec accepts as the cost of having no cancellation.
    """

    def keyPressEvent(self, event: Optional[QtGui.QKeyEvent]) -> None:  # noqa: N802
        """Swallow Escape; everything else behaves normally."""
        if event is not None and event.key() == QtCore.Qt.Key.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: Optional[QtGui.QCloseEvent]) -> None:  # noqa: N802
        """Refuse the window close box: only ``end()`` takes this down."""
        if event is not None:
            event.ignore()

    def reject(self) -> None:
        """No rejection path exists, so there is nothing to do here."""
        return None


# ===========================================================================
# Shared state: ONE indicator for the whole application (FR-021)
# ===========================================================================


class _Level:
    """One ``begin``/``end`` pair's worth of report state (data-model s2).

    ``__slots__`` because a nested walk can push and pop these often and they
    hold nothing but four numbers and a string.
    """

    __slots__ = ("label", "total", "completed", "indeterminate", "began_at_ms")

    def __init__(self, label: str, total: Optional[int], began_at_ms: int) -> None:
        self.label = label
        self.total = total
        self.completed = 0
        # No total means "size not cheaply knowable" (FR-017). A total of zero
        # or less is treated the same rather than drawn as a full bar: there is
        # no finish line to show, and a negative total is a caller bug we must
        # not render as progress.
        self.indeterminate = total is None or total <= 0
        # When the WAIT started, for the elapsed-time fallback (FR-014b). Read
        # from the outermost level, because that is the moment the operator
        # began waiting -- a nested walk inherits the clock rather than
        # restarting it.
        self.began_at_ms = began_at_ms


#: The one dialog. Created lazily on the first ``begin`` (so a deferred sink that
#: is never used allocates no widget at all) and then REUSED: a fresh dialog per
#: operation would flicker on the nested case and would leak one widget per walk.
_DIALOG: Optional[QtWidgets.QProgressDialog] = None

#: Nested labels, outermost first. The top of the stack is what is on screen.
_STACK: List[_Level] = []

#: Whether the shared dialog is currently up. Mirrors the widget's own
#: visibility, and exists only so the tick fast path can ask the question with an
#: integer comparison instead of a call into the widget -- see `_show_is_due`. A
#: momentary disagreement with the widget costs at most one extra event-loop
#: pass, never a missing or a duplicated indicator.
_VISIBLE = False


def _ensure_dialog(parent: Optional[QtWidgets.QWidget]) -> Optional[QtWidgets.QProgressDialog]:
    """The shared dialog, created on first use. None when there is no application.

    Returning None rather than raising is deliberate: every caller treats a
    missing display as "report nothing", so a sink used headless is a no-op
    instead of an error (contract: a display fault is never the caller's error).
    """
    global _DIALOG
    if _DIALOG is not None:
        _reparent(_DIALOG, parent)
        return _DIALOG
    if QtWidgets.QApplication.instance() is None:
        return None

    dialog = _NoCancelProgressDialog(parent)
    # FR-018, in order: no cancel button at all (the base class installs one by
    # default and this deletes it), application-modal so no wizard control
    # accepts input for the duration, and no auto-close/auto-reset so that a
    # determinate walk reaching its total does NOT dismiss an indicator whose
    # outer operation is still running.
    dialog.setCancelButton(None)
    dialog.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)
    dialog.setWindowFlag(QtCore.Qt.WindowType.WindowCloseButtonHint, False)
    dialog.setMinimumDuration(PROGRESS_THRESHOLD_MS)
    dialog.setLabelText("")
    # No palette, no style sheet, no colour: see the module docstring.
    _DIALOG = dialog
    return dialog


def _reparent(dialog: QtWidgets.QProgressDialog, parent: Optional[QtWidgets.QWidget]) -> None:
    """Move the shared dialog under a new owner, but only while it is down.

    The indicator should be centred on, and owned by, the window it blocks. The
    two-argument form preserves the window flags -- the one-argument form would
    turn a modal dialog into a child widget of the wizard and it would vanish
    into the page. Re-parenting a VISIBLE modal dialog is never worth the risk,
    so a mid-wait parent change is ignored.
    """
    if parent is None or dialog.parent() is parent:
        return
    try:
        if not dialog.isVisible():
            dialog.setParent(parent, dialog.windowFlags())
    except Exception:  # noqa: BLE001 - a display fault is never the caller's error
        logger.debug("progress indicator re-parent failed", exc_info=True)


def _apply_top() -> None:
    """Push the top level's state onto the dialog. The whole of what is drawn.

    Every property is written only when it actually changed. That is not
    micro-optimisation: re-setting the label text asks the dialog to reconsider
    its size hint, so writing an unchanged string 25 times a second would make
    the window twitch for the duration of a wait.
    """
    if _DIALOG is None or not _STACK:
        return
    level = _STACK[-1]

    if _DIALOG.labelText() != level.label:
        # Verbatim (FR-015): the label is the operator's vocabulary, decided by
        # the caller from the FR-023 table, and this module never decorates it.
        _DIALOG.setLabelText(level.label)

    if level.indeterminate:
        # A busy range: animates visibly without claiming a finish line
        # (FR-017), and the state an overrun total degrades into.
        if (_DIALOG.minimum(), _DIALOG.maximum()) != (0, 0):
            _DIALOG.setRange(0, 0)
        return

    total = level.total or 0
    if (_DIALOG.minimum(), _DIALOG.maximum()) != (0, total):
        _DIALOG.setRange(0, total)
    # Clamped as well as degraded: the degradation flips the range on the very
    # tick that overruns, but clamping here means no intermediate state can ever
    # paint past the end of the bar.
    value = level.completed if level.completed < total else total
    if _DIALOG.value() != value:
        _DIALOG.setValue(value)


def _show_now() -> None:
    """Put the indicator on screen and let it paint before the caller continues.

    The pump is the load-bearing half for FR-014a/SC-001b: ``show()`` only
    queues the paint, so without a pass of the event loop the operator would see
    a still window until the walk's first tick.
    """
    global _VISIBLE
    if _DIALOG is None:
        return
    _DIALOG.show()
    _VISIBLE = True
    _pump_events()


def _maybe_show(minimum_duration: int, now_ms: int) -> None:
    """Show the indicator once the wait has run past ``minimum_duration``.

    This is the FR-014b fallback, measured from the OUTERMOST level's start: the
    operator has been waiting since then, whatever the walk has nested into
    since.
    """
    if _DIALOG is None or not _STACK or _DIALOG.isVisible():
        return
    if now_ms - _STACK[0].began_at_ms >= minimum_duration:
        _show_now()


def _dismiss() -> None:
    """Take the indicator down and leave it ready for the next operation.

    ``reset()`` before ``hide()`` is what makes the NEXT wait's minimum-duration
    window start fresh; without it a second operation would inherit the first
    one's elapsed time and appear instantly. The widget itself is kept: one
    dialog for the whole application, created once.
    """
    global _VISIBLE
    _VISIBLE = False
    if _DIALOG is None:
        return
    _DIALOG.reset()
    _DIALOG.hide()
    # Pump so the indicator is actually gone before the caller carries on -- the
    # next thing a failed operation does is show the operator a message, and it
    # must not appear behind a corpse of an indicator (FR-020).
    _pump_events()


# ===========================================================================
# The sink
# ===========================================================================


class QtProgressSink:
    """One modal indicator for the whole application (FR-021).

    - Modal, with no cancel affordance: cancellation is out of scope, and wizard
      input is blocked for the duration (FR-018).
    - ``tick`` advances the bar and pumps the event loop, so the window keeps
      repainting and the operating system never reports it unresponsive
      (FR-018, SC-002).
    - Drawn from the active palette, never from hard-coded colour, so a wait
      entered in dark mode shows a dark indicator.

    Prefer the ``deferred()`` and ``immediate()`` builders below; they are the
    two trigger choices FR-014 offers, and constructing this class directly means
    deciding the minimum duration by hand.

    Guarantees, matching ``progress.NullSink`` exactly (contract):
    ``tick`` never raises, including after ``end`` and including when the display
    has been destroyed under it, and ``end`` is idempotent.
    """

    __slots__ = ("_minimum_duration", "_parent", "_own", "_primed", "_last_pump_ms")

    def __init__(
        self,
        *,
        minimum_duration: int = PROGRESS_THRESHOLD_MS,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """A sink that shows its indicator after ``minimum_duration`` ms.

        Both parameters are keyword-only with defaults, so the documented
        surface of this class stays the three protocol methods.
        """
        self._minimum_duration = minimum_duration
        self._parent = parent
        # The levels THIS sink pushed. Popping only from here is what stops one
        # sink's stray `end` from dismissing another sink's operation.
        self._own: List[_Level] = []
        # True when `immediate()` put a dialog up that no `begin` has adopted.
        self._primed = False
        self._last_pump_ms = 0

    # -- protocol ----------------------------------------------------------

    def begin(self, label: str, total: Optional[int] = None) -> None:
        """Show, or re-label an indicator that is already up (FR-021).

        With ``total``, determinate from the first frame (FR-014c). Without,
        indeterminate but visibly animating (FR-017).

        The level is pushed BEFORE any display work, and the display work is
        guarded, so the stack stays balanced with the caller's ``end`` even if
        the dialog is unhappy. An unbalanced stack would be the one failure mode
        that leaves a modal indicator on screen forever.
        """
        now = _now_ms()
        level = _Level(label, total, now)
        _STACK.append(level)
        self._own.append(level)
        self._primed = False
        self._last_pump_ms = now
        try:
            dialog = _ensure_dialog(self._parent)
            if dialog is None:
                return
            if len(_STACK) == 1 and not dialog.isVisible():
                # A fresh minimum-duration window for a new outermost wait. Only
                # while down: resetting a visible dialog is both pointless and,
                # depending on the auto-close settings, a way to hide it.
                dialog.reset()
            _apply_top()
            # THE FR-014b mechanism. Set after the bar's value, because the
            # toolkit arms its own timer from this call only while the bar sits
            # at its minimum.
            dialog.setMinimumDuration(self._minimum_duration)
            if self._minimum_duration <= 0:
                _show_now()
        except Exception:  # noqa: BLE001 - a display fault is never the caller's error
            logger.debug("progress indicator begin(%r) failed", label, exc_info=True)

    def tick(self, n: int = 1) -> None:
        """Advance, pump, and degrade to indeterminate on overrun.

        Pumping is throttled so a million-tick walk does not spend its time in
        the event loop. Exceeding ``total`` switches the bar to indeterminate
        rather than displaying over 100%.

        The fast path -- the overwhelming majority of calls -- is an integer add,
        a comparison and a clock read, with the widget untouched.
        """
        own = self._own
        if not own:
            # Ticked before `begin` or after `end`: absorbed silently, because a
            # nested walk that outlives its indicator must not take the
            # operation down with it (contract).
            return
        level = own[-1]
        level.completed += n

        forced = False
        if not level.indeterminate and level.completed > (level.total or 0):
            # data-model s2: the counted total was wrong -- an under-stated
            # count, or a walk that makes more passes than the caller knew about
            # -- so stop promising a finish line instead of painting past the end
            # of the bar. One-way: a degraded level never becomes determinate
            # again, since the total is now known to be untrue.
            level.indeterminate = True
            forced = True

        now = _now_ms()
        if (
            not forced
            and now - self._last_pump_ms < PUMP_INTERVAL_MS
            and not self._show_is_due(now)
        ):
            return
        self._last_pump_ms = now
        try:
            _apply_top()
            _maybe_show(self._minimum_duration, now)
            _pump_events()
        except Exception:  # noqa: BLE001 - a display fault is never the caller's error
            logger.debug("progress indicator tick failed", exc_info=True)

    def end(self) -> None:
        """Dismiss, restoring an outer indicator's label if one was nested."""
        own = self._own
        if not own:
            # Idempotent (contract). One case still has work to do: an
            # `immediate()` sink primes the dialog before anything calls
            # `begin`, so a walk that bailed out early -- a guard clause, an
            # empty inventory -- would otherwise leave that primed indicator up
            # with nobody able to take it down. Only when nothing else is
            # running, so this can never dismiss another operation's indicator.
            if self._primed and not _STACK:
                self._primed = False
                self._guarded_dismiss()
            return

        level = own.pop()
        self._primed = False
        # Removed by identity (`_Level` defines no equality), not by position, so
        # an `end` that arrives out of order takes down the right level and never
        # the one at the top by accident. Tolerant of a stack already emptied.
        with contextlib.suppress(ValueError):
            _STACK.remove(level)
        try:
            if _STACK:
                # FR-021: the operation that is still running gets its name, its
                # range and its count back.
                _apply_top()
            else:
                _dismiss()
        except Exception:  # noqa: BLE001 - a display fault is never the caller's error
            logger.debug("progress indicator end() failed", exc_info=True)

    # -- internals ---------------------------------------------------------

    def _show_is_due(self, now_ms: int) -> bool:
        """True when the wait has passed its threshold with nothing on screen yet.

        The throttle skips the widget entirely between pumps, which would let the
        indicator appear up to one pump interval AFTER its deadline. FR-014b
        names a deadline, and a repaint budget is no reason to miss it -- so this
        one question is asked on the fast path as well. It costs two integer
        comparisons and a module-flag read, with no call into the widget.
        """
        if _VISIBLE or not _STACK:
            return False
        return now_ms - _STACK[0].began_at_ms >= self._minimum_duration

    def _guarded_dismiss(self) -> None:
        """``_dismiss`` with the contract's "never raises" wrapper."""
        try:
            _dismiss()
        except Exception:  # noqa: BLE001 - a display fault is never the caller's error
            logger.debug("progress indicator dismiss failed", exc_info=True)

    def _prime(self, label: str, total: Optional[int]) -> None:
        """Put the indicator on screen before the work starts (FR-014a).

        Used only by ``immediate()``. No level is pushed: the stack stays an
        exact mirror of the caller's ``begin``/``end`` pairs, and the first
        ``begin`` finds a dialog already up and simply keeps it there.

        When an indicator is ALREADY up, this leaves its label alone. That
        indicator describes the work currently in progress (FR-021), the
        operator is already looking at an active indicator -- which is all
        SC-001b asks for -- and clobbering it for the microseconds before our
        own ``begin`` would only make the label flicker.
        """
        try:
            dialog = _ensure_dialog(self._parent)
            if dialog is None:
                return
            self._primed = True
            if _STACK:
                _show_now()
                return
            if not dialog.isVisible():
                dialog.reset()
            dialog.setLabelText(label)
            if total is None or total <= 0:
                dialog.setRange(0, 0)
            else:
                # The scale of the work, on the first frame and before the walk
                # starts (FR-014c, FR-016).
                dialog.setRange(0, total)
                dialog.setValue(0)
            dialog.setMinimumDuration(self._minimum_duration)
            _show_now()
        except Exception:  # noqa: BLE001 - a display fault is never the caller's error
            logger.debug("progress indicator prime(%r) failed", label, exc_info=True)


# ===========================================================================
# The two builders -- FR-014's two triggers, one each
# ===========================================================================


def deferred(
    label: str,
    total: Optional[int] = None,
    *,
    parent: Optional[QtWidgets.QWidget] = None,
) -> QtProgressSink:
    """A sink that shows nothing until PROGRESS_THRESHOLD_MS has elapsed.

    This is the elapsed-time fallback (FR-014b). An operation that finishes
    first displays nothing at all -- no flash, no flicker (FR-019). Nothing is
    even constructed: the dialog appears on the first tick past the threshold,
    so a deferred sink that is never used costs one Python object.

    ``label`` and ``total`` are accepted here so a call site reads as one
    declaration of the operation, and passed again by ``progress.reporting``;
    the sink itself takes them from ``begin``.
    """
    return QtProgressSink(minimum_duration=PROGRESS_THRESHOLD_MS, parent=parent)


def immediate(
    label: str,
    total: int,
    *,
    parent: Optional[QtWidgets.QWidget] = None,
) -> QtProgressSink:
    """A sink that is on screen before the work starts (FR-014a).

    For an operation whose cheap count predicted a wait past the threshold. The
    operator never sees a still window ahead of the indicator (SC-001b): the
    dialog is shown, and the event loop pumped so it actually paints, before this
    function returns -- which is before the caller has read its first entry.

    ``total`` is required, not optional: an operation with no total could not
    have been predicted slow, so it belongs to ``deferred()`` by construction
    (FR-014d).
    """
    sink = QtProgressSink(minimum_duration=0, parent=parent)
    sink._prime(label, total)
    return sink
