"""US6 + US8 -- the page header, the view controls, and the description budget.

WHY this module exists
----------------------
Two stories meet on one widget. US6 moves the zoom / colour-mode strip out of a
floating, self-positioning corner bar and into a laid-out header cell; US8 makes
the step description wrap instead of truncate. They are the same widget because
they are the same defect: before feature 036 the strip `move()`d itself to the
window's top-right corner, `raise_()`d itself above the page, and painted its own
opaque background *specifically* so that "a long wizard subtitle ever running
underneath" stayed legible (`theme.ThemeCornerBar`'s own docstring). Painting over
a collision is not fixing it. Nothing in any layout knew the strip was there, so
nothing could move out of its way, and a description that wrapped to a second or
third line ran under it.

What this module pins, therefore, is that the fix is **layout** and not
positioning:

* the window title names the tool rather than an internal milestone (FR-001,
  SC-010) -- "Phase 3c" means nothing to a field linguist and dates the tool;
* every flow page owns a header whose description label wraps and whose text is
  `page.subTitle()`, which stays the string of record (FR-012);
* the controls slot reserves its **own** space, asserted as geometry
  non-intersection at the 900 px floor and the largest supported text scale with
  the wizard's longest description -- the worst case the product offers, and the
  exact measurement SC-005a names (FR-004, FR-013a);
* the strip is labelled "Zoom:" and its buttons are "-" and "+" with no letter-A
  glyph (FR-002, FR-003);
* every capability the strip had before the move still works, and each keyboard
  shortcut is registered **exactly once** for the whole wizard (FR-005). Exactly
  once is not pedantry: there is ONE strip reparented from page to page, not one
  strip per page, and twelve registrations of `Ctrl+0` inside one window resolve
  as ambiguous -- the shortcut then does nothing at all;
* every step description fits two lines at the default width and default text
  scale (FR-013, SC-009), one that fits stays on one line with no blank second
  line reserved (FR-012), and a third line at the floor or a raised scale is
  absorbed without clipping, overlap, or content pushed off screen (FR-013a).

Every measurement comes from `_ui_geometry` (T001), which owns the one answer to
"900 px at the largest supported text scale": the scale goes on *before*
construction (pages snapshot the application font into per-item QFonts), rects
are mapped into a single coordinate space before they are compared, and
ancestor/descendant pairs are excluded from the overlap check. Nothing here
re-implements any of that.

Cost control
------------
The wizard is built exactly TWICE for the whole module, in a module-scoped
parametrised fixture: once at the default width and default text scale (where
the two-line copy budget is measured -- FR-013 is explicit that the budget is
measured once at the default, not guaranteed at every size) and once at the
900 px floor and the largest supported text scale (the SC-005a / FR-013a stress
case). The two cannot overlap: `text_scale()` restores the previous application
font on exit, so two live scaled fixtures would nest and the second would take
the first's already-scaled font as its baseline.

Pages are swept in a loop rather than parametrised because the page set does not
exist until the wizard is built, and because one aggregated failure ("these
three pages have no header") is more use than eleven separate reds. Nothing keys
off a page title or index -- a sibling task is renumbering the flow.

Shared state
------------
Several tests here have to *change* a description to measure what a one-line or a
three-line description does to the layout. The wizard is shared across the
module, so every such test restores `page.subTitle()` into the header in a
`finally`, and the wrap tests compare the page's layout faults against a
baseline captured before the change -- so a pre-existing floor defect belonging
to US3 is not reported here as a US8 regression.
"""
from __future__ import annotations

import os

# SC-007 convention: choose the platform before Qt is imported, or the import
# binds the real windowing system and the suite needs a display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import re  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Iterator, NamedTuple, Optional  # noqa: E402

import pytest  # noqa: E402

PyQt6 = pytest.importorskip("PyQt6")

from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402

import _ui_geometry as geom  # noqa: E402  -- tests/unit is on sys.path (conftest)
from gramtrans.Lib.ui import selection_wizard as sw  # noqa: E402
from gramtrans.Lib.ui import theme as gt_theme  # noqa: E402


#: The size the wizard opens at -- `self.resize(1300, 760)` in `__init__`. This
#: is what "the default window width" in FR-013 and SC-009 refers to, so it is
#: spelled out here AND checked against the production source (see
#: `test_every_step_description_fits_two_lines_at_the_default`): a budget
#: measured at a width nobody opens at would be a budget for nothing.
DEFAULT_WINDOW_WIDTH = 1300
DEFAULT_WINDOW_HEIGHT = 760

#: The narrow floor (FR-029) and the unchanged height floor. Spelled out rather
#: than read from `sw`, for the same reason the sibling module spells them out:
#: `geom.MIN_WINDOW_WIDTH` falls back to 900 via `getattr`, so reading it would
#: launder a missing declaration into a pass.
FLOOR_WINDOW_WIDTH = 900
FLOOR_WINDOW_HEIGHT = 680

#: FR-013's copy budget, at the default width and default text scale only.
LINE_BUDGET_AT_DEFAULT = 2

#: FR-013a's floor: at 900 px or a raised text scale a third line is *permitted*.
#: The absorption test forces a description this long so the third line is a
#: fact rather than a hope -- a test that only checked pages which happened to
#: wrap would pass vacuously the day the copy got shorter.
THIRD_LINE_MINIMUM = 3

#: How many headers the sweeps must find to mean anything. `flow()` declares
#: twelve pages today; the floor is deliberately lower so a page legitimately
#: added or removed does not fail this module, and high enough that a broken
#: header accessor cannot turn a sweep into a no-op.
MIN_FLOW_PAGES = 10

#: A description long enough to need three lines at any supported width and
#: scale (roughly 700 characters; the default 1300 px window fits ~200 per line).
#: Deliberately real prose rather than "x" * 700 -- a single unbroken 700-char
#: word cannot wrap at all, and would test Qt's overflow behaviour instead of
#: the header's.
LONG_DESCRIPTION = (
    "Choose the grammatical categories, inflectional slots, and affix "
    "positions that this transfer should carry across into the target project, "
    "remembering that a category selected here is created in the target only "
    "when the affixes attached to it are themselves selected on the affix "
    "picker, that a slot with no selected affixes is carried across as an "
    "empty slot rather than being silently dropped, and that every decision "
    "made on this page can be revisited before the dry run without losing any "
    "of the selections already made on the earlier pages of this wizard."
)

#: A description that fits comfortably on one line at every supported width.
SHORT_DESCRIPTION = "Pick the projects."

#: Slack in pixels when comparing a widget's allotted height against the height
#: its wrapped text needs. Qt rounds line spacing to whole pixels and a layout
#: distributes leftover pixels a row at a time, so an exact comparison would
#: report a one-pixel rounding as clipping.
HEIGHT_TOLERANCE = 2


def _description_of_lines(label: QtWidgets.QLabel, lines: int) -> str:
    """Prose that occupies exactly `lines` wrapped lines in `label`'s width.

    WHY THIS IS COMPUTED AND NOT A CONSTANT
    ---------------------------------------
    FR-013a is about a THIRD line -- "at 900 px or a raised text scale a third
    line is permitted and absorbed". A fixed string cannot express that across
    both cases: the 700-character `LONG_DESCRIPTION` is three lines in a 1300 px
    window at 100% text and THIRTY lines in a 515 px label at 250%. Asserting
    that thirty lines are absorbed without clipping is not FR-013a, it is a
    demand that a 680 px window contain an 836 px label -- a test the layout
    must fail however correct it is.

    So the description is grown a word at a time until it first reaches the
    requested line count, measured with the label's own font metrics at its own
    width, which is the same measurement `geom.wrapped_line_count` makes. Words
    are recycled from `LONG_DESCRIPTION` so the text stays real prose that can
    actually wrap (a single unbroken long word cannot, and would measure Qt's
    overflow behaviour instead of the header's).
    """
    width = max(1, label.contentsRect().width())
    words = LONG_DESCRIPTION.split()
    text = ""
    for i in range(1, len(words) * 8):
        candidate = " ".join(words[j % len(words)] for j in range(i))
        metrics = QtGui.QFontMetrics(label.font())
        flags = int(QtCore.Qt.TextFlag.TextWordWrap)
        bounds = metrics.boundingRect(
            QtCore.QRect(0, 0, width, 10_000), flags, candidate
        )
        spacing = max(1, metrics.lineSpacing())
        if max(1, int(round(bounds.height() / spacing))) >= lines:
            return candidate
        text = candidate
    return text


class Case(NamedTuple):
    """One (width, text scale) case, and the wizard built for it."""

    name: str
    width: int
    height: int
    scale: float
    wizard: QtWidgets.QWizard

    @property
    def is_default(self) -> bool:
        """The default width and default text scale -- FR-013's measuring point."""
        return self.name == "default"

    @property
    def label(self) -> str:
        return f"{self.wizard.width()}px x {self.scale} text scale"


#: (name, width, height, scale). Two cases, two builds, no overlap.
_CASES = (
    ("default", DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT, geom.DEFAULT_TEXT_SCALE),
    ("floor", FLOOR_WINDOW_WIDTH, FLOOR_WINDOW_HEIGHT, geom.MAX_TEXT_SCALE),
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp():
    """The one QApplication, held for the whole session.

    Session scope is a correctness requirement, not an optimisation: a
    QApplication with no live Python reference is garbage-collected, and its
    destruction takes every QObject in the process with it -- including the
    process-wide ThemeManager singleton, whose Python handle survives as a
    dangling wrapper. The second wizard built in such a session dies with
    "wrapped C/C++ object of type ThemeManager has been deleted". Same shape as
    the fixture in `test_036_min_width_layout.py`.
    """
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture(
    scope="module",
    params=_CASES,
    ids=["default-1300px-100pct", "floor-900px-max-scale"],
)
def header_case(request, qapp, tmp_path_factory) -> Iterator[Case]:
    """A wizard at one of the two cases -- exactly two builds for the module.

    Module scope with a parametrised fixture, rather than two module-scoped
    fixtures: pytest tears the previous parameter down before it sets the next
    one up, so only ONE scaled application font is ever installed at a time. Two
    overlapping fixtures would nest the scaling -- the second capturing the
    first's already-scaled font as its baseline -- and every measurement after
    that would be at some unintended third scale.

    `geom.wizard_at` is the single canonical stress expression (scale first,
    construct second, restore always); this fixture adds nothing but the
    lifetime and the case labelling.
    """
    name, width, height, scale = request.param
    geom.ensure_qapp()
    geom.needs_a_real_qwizard()
    root = tmp_path_factory.mktemp("projects_root")
    geom.projects_tree(root)
    with geom.wizard_at(root, width=width, height=height, scale=scale) as wizard:
        yield Case(name, width, height, float(scale), wizard)


@pytest.fixture
def default_case(header_case: Case) -> Case:
    """`header_case` narrowed to the default width and default text scale.

    FR-013 is explicit that the two-line budget "is a copy-length budget,
    measured once at the default, not a guarantee at every size", and FR-013a
    then *permits* a third line at the floor or a raised scale. A test of the
    budget therefore has exactly one valid measuring point, and asserting it at
    the floor case would contradict the requirement it is meant to protect.
    The other parameter is skipped rather than silently tolerated so the skip
    line in the report says which case was measured and which was not.
    """
    if not header_case.is_default:
        pytest.skip(
            "FR-013's two-line budget is measured only at the default width and "
            "text scale; the floor case is covered by the FR-013a absorption test"
        )
    return header_case


@pytest.fixture(scope="module")
def wizard_source() -> str:
    """The production module's own text, for the "this IS the default" assertion.

    "The default window width" is only meaningful if it is the width the wizard
    actually opens at. That is a fact about the source, so it is read from the
    source rather than assumed.
    """
    return Path(sw.__file__).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Reaching the header and the strip
# ---------------------------------------------------------------------------

def _header_of(page: QtWidgets.QWizardPage) -> Optional[QtWidgets.QWidget]:
    """`page.header()`, or None when the accessor does not exist yet.

    `getattr` rather than a bare attribute access so a page without the
    accessor produces this module's own [FAIL] message naming FR-004 and T041,
    instead of an AttributeError that says only "no attribute 'header'".
    """
    getter = getattr(page, "header", None)
    if not callable(getter):
        return None
    header = getter()
    return header if isinstance(header, QtWidgets.QWidget) else None


def _require_header(case: Case, page: QtWidgets.QWizardPage, pid: int):
    """The header of `page`, or a failure that says what is missing and why."""
    header = _header_of(page)
    assert header is not None, (
        f"[FAIL] FR-004/FR-012 at {case.label}: page {pid} "
        f"({type(page).__name__}) exposes no header() widget. Every flow page "
        f"must own one laid-out header (contract: 'page.header()'), because a "
        f"description and a control strip can only be kept apart by a layout "
        f"that knows about both."
    )
    for accessor in ("description_label", "controls_slot"):
        assert callable(getattr(header, accessor, None)), (
            f"[FAIL] FR-004/FR-012 at {case.label}: page {pid} "
            f"({type(page).__name__}) header {type(header).__name__} has no "
            f"{accessor}() -- the contract's two header accessors are what the "
            f"description/controls separation is asserted through."
        )
    return header


def _iter_headers(
    case: Case,
) -> Iterator[tuple[int, QtWidgets.QWizardPage, QtWidgets.QWidget]]:
    """Yield `(page_id, page, header)` with that page CURRENT at yield time.

    A generator, not a list, and the distinction is the correctness of every
    sweep below. QWizard shows one page at a time and hides the rest, so a
    widget on a non-current page reports `isVisible() is False` and holds the
    geometry it had when it was last laid out. Collecting first and measuring
    afterwards would measure eleven stale pages and one live one -- a fact about
    QWizard, not about the layout under test.
    """
    for pid, page in geom.pages(case.wizard):
        header = _require_header(case, page, pid)
        geom.show_page(case.wizard, page)
        geom.settle(header)
        yield pid, page, header


def _control_strips(wizard: QtWidgets.QWizard) -> list[QtWidgets.QWidget]:
    """Every `ThemeCornerBar` anywhere under the wizard.

    Discovered from the live object tree rather than through an accessor name:
    T042 keeps one strip and moves it between page header slots, and whether the
    accessor is still called `theme_bar()` afterwards is not what FR-005 is
    about. The COUNT is.
    """
    return list(wizard.findChildren(gt_theme.ThemeCornerBar))


def _the_strip(case: Case) -> QtWidgets.QWidget:
    """The one and only control strip, or a failure naming the ambiguity risk."""
    strips = _control_strips(case.wizard)
    assert len(strips) == 1, (
        f"[FAIL] FR-005/D8 at {case.label}: found {len(strips)} ThemeCornerBar "
        f"instances under the wizard, expected exactly 1. One strip per page "
        f"would register ZoomIn, ZoomOut and Ctrl+0 twelve times inside one "
        f"window, and Qt resolves an ambiguous shortcut by firing nothing -- so "
        f"'the shortcuts survive' would be false while every button still worked."
    )
    return strips[0]


def _strip_buttons(strip: QtWidgets.QWidget) -> list[QtWidgets.QAbstractButton]:
    return list(strip.findChildren(QtWidgets.QAbstractButton))


def _button_texts(strip: QtWidgets.QWidget) -> list[str]:
    return [b.text() for b in _strip_buttons(strip)]


def _buttons_with_text(strip: QtWidgets.QWidget, text: str):
    return [b for b in _strip_buttons(strip) if b.text() == text]


def _labels_with_text(strip: QtWidgets.QWidget, text: str) -> list[QtWidgets.QLabel]:
    return [lb for lb in strip.findChildren(QtWidgets.QLabel) if lb.text() == text]


# ---------------------------------------------------------------------------
# Shortcuts
# ---------------------------------------------------------------------------

def _shortcut_registrations(
    wizard: QtWidgets.QWizard,
) -> list[tuple[QtGui.QKeySequence, str]]:
    """Every key sequence reachable from the wizard, with who owns it.

    All three of Qt's registration channels are walked, because FR-005's
    "registered exactly once" is a claim about the *window*, not about one
    channel: a `QShortcut` on the wizard and a `setShortcut` on a button are
    both active whenever the window is, and two owners of one sequence inside
    one window is precisely the ambiguity that makes the sequence dead.
    """
    found: list[tuple[QtGui.QKeySequence, str]] = []
    for shortcut in wizard.findChildren(QtGui.QShortcut):
        # `.parent()`, not `.parentWidget()`: QShortcut is a QObject, and only
        # QWidget carries the widget-typed accessor. A shortcut's parent is
        # always a widget in practice (Qt needs one to scope the shortcut), but
        # it is reached through the QObject API.
        owner = shortcut.parent()
        found.append(
            (
                shortcut.key(),
                f"QShortcut parented to "
                f"{geom.describe(owner) if isinstance(owner, QtWidgets.QWidget) else '<no widget>'}",
            )
        )
    for action in wizard.findChildren(QtGui.QAction):
        for sequence in action.shortcuts():
            found.append((sequence, f"QAction {action.text()!r}"))
    for button in wizard.findChildren(QtWidgets.QAbstractButton):
        sequence = button.shortcut()
        if not sequence.isEmpty():
            found.append(
                (sequence, f"{type(button).__name__} button {button.text()!r}")
            )
    return found


def _targets_for(key) -> list[QtGui.QKeySequence]:
    """Every sequence a `StandardKey` resolves to, or the literal sequence.

    `button.setShortcut(StandardKey.ZoomIn)` stores whichever binding the
    platform lists first, so a test comparing against a hand-written "Ctrl++"
    would pass or fail by platform. `keyBindings()` is the same list Qt itself
    consults.
    """
    if isinstance(key, QtGui.QKeySequence.StandardKey):
        bindings = QtGui.QKeySequence.keyBindings(key)
        return list(bindings) if bindings else []
    return [QtGui.QKeySequence(key)]


def _owners_of(
    registrations: list[tuple[QtGui.QKeySequence, str]], key
) -> list[str]:
    """Who has registered `key` (a StandardKey or a literal sequence)."""
    targets = _targets_for(key)
    exact = QtGui.QKeySequence.SequenceMatch.ExactMatch
    owners: list[str] = []
    for sequence, owner in registrations:
        if any(sequence.matches(target) == exact for target in targets):
            owners.append(owner)
    return owners


# ---------------------------------------------------------------------------
# Descriptions and layout faults
# ---------------------------------------------------------------------------

def _flat(text: Optional[str]) -> str:
    """Collapse whitespace, so a multi-line source literal measures as one string."""
    return " ".join((text or "").split())


def _longest_description(case: Case) -> tuple[int, QtWidgets.QWizardPage, str]:
    """`(page_id, page, text)` for the wizard's longest `subTitle()`.

    SC-005a names the worst case exactly: "verified at 900 pixels and the
    largest supported text scale using the longest description in the wizard".
    The longest description is therefore discovered, not chosen -- shortening a
    different page's copy must not quietly move the measurement somewhere easier.
    """
    best: Optional[tuple[int, QtWidgets.QWizardPage, str]] = None
    for pid, page in geom.pages(case.wizard):
        text = _flat(page.subTitle())
        if best is None or len(text) > len(best[2]):
            best = (pid, page, text)
    assert best is not None and best[2], (
        f"[FAIL] at {case.label}: no page carries a subTitle(), so there is no "
        f"'longest description in the wizard' to measure SC-005a with."
    )
    return best


def _line_spacing(label: QtWidgets.QLabel) -> int:
    """One line's pitch in `label`'s own font -- the unit FR-012/FR-013 count in."""
    return max(1, QtGui.QFontMetrics(label.font()).lineSpacing())


def _layout_faults(page: QtWidgets.QWidget, wizard: QtWidgets.QWidget) -> dict:
    """Every clip, overlap and off-window escape on `page`, keyed by identity.

    Keyed by *names* rather than by rects on purpose. These dicts are diffed
    before and after a description is changed, and keying on geometry would
    report a pre-existing fault that shifted by one pixel as a new one. The
    value keeps the numbers for the failure message.
    """
    faults: dict[str, str] = {}
    for clip in geom.clipped(page):
        faults[f"clipped {clip.child} inside {clip.parent}"] = repr(clip)
    rects = geom.visible_rects(page)
    for overlap in geom.overlaps(rects):
        faults[f"overlap {overlap.a.name} | {overlap.b.name}"] = repr(overlap)
    window = wizard.rect()
    for item in rects:
        if not window.contains(item.rect):
            faults[f"offscreen {item.name}"] = (
                f"{item.rect} is not inside the window {window}"
            )
    return faults


def _new_faults(before: dict, after: dict) -> list[str]:
    """Faults present after a change that were not present before it.

    US3 owns "nothing is clipped at 900 px" and has its own module. What US8
    owns is that *growing a description* introduces nothing new, so the baseline
    is subtracted -- otherwise this module would redden for a floor defect it
    does not describe, and whoever fixed it would look in the wrong story.
    """
    return [f"{key}: {after[key]}" for key in after if key not in before]


# ---------------------------------------------------------------------------
# FR-001 / SC-010 -- the window title
# ---------------------------------------------------------------------------

def test_the_window_title_names_the_application_and_no_development_phase(
    header_case: Case,
) -> None:
    """FR-001, SC-010: the title identifies the tool and carries no phase label.

    The title read "GramTrans -- Selection Wizard (Phase 3c)". "Phase 3c" is an
    internal milestone: it means nothing to a field linguist, and it dates the
    tool every time they look at the window. Three claims, because each is a
    different way to get this wrong:

    * the title still names the application -- an empty or generic title would
      satisfy "no phase label" while telling the operator less than before;
    * it says something beyond the bare product name, since FR-001 asks for the
      application "and its purpose";
    * no `Phase`, no `3c`, and no milestone/iteration word of the same family
      (`Milestone`, `Iteration`, `Alpha`, `Beta`, `RC`) -- SC-010 is a claim
      about the class of label, not about one string that was there once.
    """
    title = header_case.wizard.windowTitle()
    assert title.strip(), "[FAIL] FR-001: the wizard has no window title at all."
    assert "GramTrans" in title, (
        f"[FAIL] FR-001: the window title {title!r} does not name the "
        f"application; the operator must be able to tell which tool this is."
    )
    assert len(_flat(title).split()) >= 2, (
        f"[FAIL] FR-001: the window title {title!r} names the application but "
        f"not its purpose -- FR-001 asks for both."
    )
    banned = re.compile(
        r"(?i)\b(phase\s*\w*|3c|milestone|iteration|sprint|alpha|beta|rc\d*)\b"
    )
    match = banned.search(title)
    assert match is None, (
        f"[FAIL] FR-001/SC-010: the window title {title!r} still carries the "
        f"development designation {match.group(0)!r}. The title bar is the one "
        f"place an internal milestone is guaranteed to be read by somebody it "
        f"means nothing to."
    )


# ---------------------------------------------------------------------------
# FR-004 / FR-012 -- the header exists, wraps, and renders subTitle()
# ---------------------------------------------------------------------------

def test_every_flow_page_owns_a_laid_out_header(header_case: Case) -> None:
    """FR-004: the header is *laid out*, never floating and never raise_()ed.

    "Laid out" is the whole fix, so it is asserted structurally rather than
    inferred from geometry: the header must be reachable from one of the page's
    layouts. A widget that is merely parented to the page (which is what the old
    corner bar was, relative to the wizard) has no layout item, so no layout can
    make room for it and no layout can be told to move out of its way -- which
    is exactly how a wrapped description came to run underneath the controls.
    """
    checked = 0
    problems: list[str] = []
    for pid, page, header in _iter_headers(header_case):
        checked += 1
        where = f"page {pid} ({type(page).__name__})"
        layouts = [lay for lay in page.findChildren(QtCore.QObject)
                   if isinstance(lay, QtWidgets.QLayout)]
        page_layout = page.layout()
        if page_layout is not None:
            layouts.append(page_layout)
        if not any(lay.indexOf(header) >= 0 for lay in layouts):
            problems.append(
                f"{where}: the header is not an item in any of the page's "
                f"layouts -- it is positioned, not laid out"
            )
        if header.parentWidget() is not page and not page.isAncestorOf(header):
            problems.append(
                f"{where}: the header is not a descendant of the page "
                f"(parent is {header.parentWidget()!r})"
            )

    assert checked >= MIN_FLOW_PAGES, (
        f"[FAIL] vacuous sweep at {header_case.label}: only {checked} page(s) "
        f"examined, expected at least {MIN_FLOW_PAGES}."
    )
    assert not problems, (
        f"[FAIL] FR-004 at {header_case.label}:\n  - " + "\n  - ".join(problems)
    )


def test_the_description_label_wraps_and_renders_the_page_subtitle(
    header_case: Case,
) -> None:
    """FR-012: `wordWrap() is True`, and the text IS `page.subTitle()`.

    Two halves, and the second is the one that rots. `wordWrap` is what makes a
    long description wrap instead of truncate. Equality with `subTitle()` is what
    keeps `subTitle()` the string of record: a header handed a second, separately
    maintained copy of the text would drift, and the copy the operator reads
    would stop being the copy T044 measures against the two-line budget.

    Truncation is checked as well as wrapping, because a wrapping label with
    `ElideRight` set would satisfy `wordWrap()` and still cut the sentence off.
    """
    checked = 0
    problems: list[str] = []
    for pid, page, header in _iter_headers(header_case):
        where = f"page {pid} ({type(page).__name__})"
        label = header.description_label()
        assert isinstance(label, QtWidgets.QLabel), (
            f"[FAIL] FR-012 at {header_case.label}: {where} "
            f"description_label() returned {type(label).__name__}, expected a "
            f"QLabel."
        )
        subtitle = _flat(page.subTitle())
        if not subtitle:
            # A page with nothing to say reserves nothing; that is FR-012's own
            # principle applied to the first line, and there is no text to check.
            continue
        checked += 1
        if label.wordWrap() is not True:
            problems.append(
                f"{where}: description_label().wordWrap() is "
                f"{label.wordWrap()!r} -- a description too long for one line "
                f"would be truncated instead of wrapping"
            )
        if _flat(label.text()) != subtitle:
            problems.append(
                f"{where}: the header renders {_flat(label.text())[:60]!r} but "
                f"subTitle() is {subtitle[:60]!r} -- subTitle() must remain the "
                f"string of record that the header renders"
            )

    assert checked >= MIN_FLOW_PAGES, (
        f"[FAIL] vacuous sweep at {header_case.label}: only {checked} page(s) "
        f"carried a description to check, expected at least {MIN_FLOW_PAGES}."
    )
    assert not problems, (
        f"[FAIL] FR-012 at {header_case.label}:\n  - " + "\n  - ".join(problems)
    )


def test_qt_no_longer_draws_the_subtitle_itself(header_case: Case) -> None:
    """FR-004: `IgnoreSubTitles` is set, so the subtitle is drawn once.

    Without this option the wizard paints `subTitle()` in its own header band and
    the page header paints it again lower down: the operator reads the same
    sentence twice, and the band Qt paints is not in any layout the page controls
    -- so the duplicate is also the copy that can still be truncated.
    """
    wizard = header_case.wizard
    assert wizard.testOption(QtWidgets.QWizard.WizardOption.IgnoreSubTitles), (
        f"[FAIL] FR-004 at {header_case.label}: "
        f"QWizard.WizardOption.IgnoreSubTitles is not set, so Qt still draws "
        f"subTitle() in its own band as well as the page header drawing it."
    )


# ---------------------------------------------------------------------------
# FR-004 / FR-013a / SC-005a -- the controls reserve their own space
# ---------------------------------------------------------------------------

def test_the_controls_slot_reserves_space_the_description_cannot_enter(
    header_case: Case,
) -> None:
    """FR-004, FR-013a, SC-005a: description and controls occupy separate space.

    This is the binding assertion of US6. It is made on the page carrying the
    wizard's longest description, and -- at the `floor-900px-max-scale`
    parameter -- at the 900 px window floor and the largest supported text
    scale, which is the case SC-005a names in as many words: "verified at 900
    pixels and the largest supported text scale using the longest description in
    the wizard -- the worst case for both".

    Four things are asserted, and the first three exist so the fourth cannot
    pass by accident:

    * the strip is *in* this page's controls slot. Before T042 the strip floats,
      parented to the wizard and in no layout, so the slot is empty -- and an
      empty slot trivially intersects nothing. That would be the loudest
      possible vacuous pass, so an empty slot is a failure here.
    * the slot's rect is non-degenerate. A zero-width cell also intersects
      nothing.
    * the description's rect is non-degenerate, for the same reason.
    * the description does not intersect the slot, nor the strip inside it, with
      both rects mapped into the wizard's coordinate space -- two widgets under
      different parents have rects in different origins, and comparing their
      raw `geometry()` values would compare unrelated numbers.

    Then the description is grown to a deliberately over-long value and the
    non-intersection is re-asserted, because FR-004 is not "they do not overlap
    today" but "a description grown to its full wrapped height -- however many
    lines that takes -- cannot run underneath them".
    """
    wizard = header_case.wizard
    pid, page, longest = _longest_description(header_case)
    header = _require_header(header_case, page, pid)
    geom.show_page(wizard, page)
    geom.settle(header)

    slot = header.controls_slot()
    label = header.description_label()
    strip = _the_strip(header_case)

    occupant = header.controls() if callable(getattr(header, "controls", None)) else None
    assert occupant is strip, (
        f"[FAIL] FR-004/FR-005 at {header_case.label}: page {pid} "
        f"({type(page).__name__}) has {occupant!r} in its controls slot, not the "
        f"wizard's one ThemeCornerBar. Until the strip is laid out in the slot it "
        f"is still floating over the page, the slot reserves nothing, and "
        f"'the description does not intersect the controls' is true only because "
        f"the slot is empty."
    )

    original = page.subTitle()
    try:
        for stage, text in (("its own longest description", longest),
                            ("a description grown past any budget",
                             LONG_DESCRIPTION)):
            header.set_description(text)
            geom.settle(header)
            geom.settle(page)

            slot_rect = geom.rect_in(slot, wizard)
            label_rect = geom.rect_in(label, wizard)
            strip_rect = geom.rect_in(strip, wizard)
            lines = geom.wrapped_line_count(label)
            context = (
                f"at {header_case.label}, page {pid} "
                f"({type(page).__name__}) with {stage} ({lines} line(s))"
            )

            assert not slot_rect.isEmpty() and slot_rect.width() > 0, (
                f"[FAIL] FR-004 {context}: the controls slot is "
                f"{slot_rect.width()}x{slot_rect.height()} px, so it reserves no "
                f"space and a non-intersection claim about it is meaningless."
            )
            assert not label_rect.isEmpty() and label_rect.width() > 0, (
                f"[FAIL] FR-004 {context}: the description label is "
                f"{label_rect.width()}x{label_rect.height()} px -- it was given "
                f"no room, so nothing can be concluded about overlap."
            )
            assert not label_rect.intersects(slot_rect), (
                f"[FAIL] FR-004/SC-005a {context}: the description "
                f"{label_rect} runs into the controls slot {slot_rect} "
                f"(intersection {label_rect.intersected(slot_rect)}). The two "
                f"must reserve separate space by layout; painting an opaque "
                f"background over the collision was the workaround being removed."
            )
            assert not label_rect.intersects(strip_rect), (
                f"[FAIL] FR-004/SC-005a {context}: the description "
                f"{label_rect} runs under the control strip {strip_rect} "
                f"(intersection {label_rect.intersected(strip_rect)})."
            )
    finally:
        header.set_description(original)
        geom.settle(header)
        geom.settle(page)


# ---------------------------------------------------------------------------
# FR-002 / FR-003 -- the strip's labels
# ---------------------------------------------------------------------------

def test_the_zoom_control_is_labelled_and_the_letter_a_is_gone(
    header_case: Case,
) -> None:
    """FR-002, FR-003: a visible "Zoom:" label, and buttons reading "-" and "+".

    The buttons read `A-` and `A+` today. The letter-A glyph is a convention
    borrowed from word processors, where it sits beside a font-size box that
    explains it; alone in a corner strip beside a percentage it explains nothing,
    and the requester asked for it gone. "Zoom:" is quoted exactly in the
    contract, so it is compared exactly -- "Zoom" without the colon, or "zoom:",
    is a different string and a different decision.

    `isHidden()` rather than `isVisible()` for the label: the one strip lives in
    the *current* page's header slot, so on any other page the whole strip is
    legitimately not visible through its ancestors. `isHidden()` asks the
    question FR-002 actually poses -- has anything hidden this label -- without
    depending on which page happens to be current.

    The ordering claim ("preceded by") is geometric, in the strip's own
    coordinate space: a label placed after the buttons would satisfy every text
    assertion and still read as "- + Zoom:".
    """
    wizard = header_case.wizard
    strip = _the_strip(header_case)
    # Show a page first: an unshown widget's children hold pre-layout guess
    # geometry, and the ordering claim below is geometric.
    first_pid, first_page = geom.pages(wizard)[0]
    geom.show_page(wizard, first_page)
    geom.settle(strip)

    texts = _button_texts(strip)
    assert texts, (
        f"[FAIL] FR-003 at {header_case.label}: the control strip has no "
        f"buttons at all."
    )

    zoom_labels = _labels_with_text(strip, "Zoom:")
    assert len(zoom_labels) == 1, (
        f"[FAIL] FR-002 at {header_case.label}: found {len(zoom_labels)} label(s) "
        f"reading exactly 'Zoom:' on the control strip, expected 1. Labels "
        f"present: "
        f"{[lb.text() for lb in strip.findChildren(QtWidgets.QLabel)]!r}"
    )
    zoom_label = zoom_labels[0]
    assert not zoom_label.isHidden(), (
        f"[FAIL] FR-002 at {header_case.label}: the 'Zoom:' label exists but is "
        f"hidden -- FR-002 requires a *visible* label preceding the zoom control."
    )

    decrease = _buttons_with_text(strip, "-")
    increase = _buttons_with_text(strip, "+")
    assert len(decrease) == 1, (
        f"[FAIL] FR-003 at {header_case.label}: found {len(decrease)} button(s) "
        f"reading exactly '-', expected 1. Button texts: {texts!r}"
    )
    assert len(increase) == 1, (
        f"[FAIL] FR-003 at {header_case.label}: found {len(increase)} button(s) "
        f"reading exactly '+', expected 1. Button texts: {texts!r}"
    )

    letter_a = re.compile(r"(?i)^\s*a\s*[-+]\s*$")
    offenders = [t for t in texts if letter_a.match(t)]
    assert not offenders, (
        f"[FAIL] FR-003 at {header_case.label}: the letter-A glyph survives on "
        f"{offenders!r} -- FR-003 marks the controls as increase and decrease "
        f"only."
    )

    label_rect = geom.rect_in(zoom_label, strip)
    decrease_rect = geom.rect_in(decrease[0], strip)
    increase_rect = geom.rect_in(increase[0], strip)
    assert not label_rect.isEmpty() and not decrease_rect.isEmpty(), (
        f"[FAIL] FR-002 at {header_case.label}: the strip's children have no "
        f"laid-out geometry (label {label_rect}, decrease {decrease_rect}), so "
        f"the ordering claim cannot be measured. Page {first_pid} "
        f"({type(first_page).__name__}) was made current first."
    )
    assert label_rect.left() < min(decrease_rect.left(), increase_rect.left()), (
        f"[FAIL] FR-002 at {header_case.label}: the 'Zoom:' label {label_rect} "
        f"does not precede the zoom buttons (decrease {decrease_rect}, increase "
        f"{increase_rect}) -- FR-002 requires the label before the control."
    )


# ---------------------------------------------------------------------------
# FR-005 -- every capability survives the move, each shortcut registered once
# ---------------------------------------------------------------------------

def test_the_percentage_readout_and_its_click_to_reset_survive(
    header_case: Case,
) -> None:
    """FR-005: the readout still shows the current percentage and resets to 100%.

    Two claims. The readout is text -- exactly one control on the strip reads
    `"{percent}%"`, matching what the ThemeManager reports, so the operator can
    see the size they are at. The reset is behaviour -- clicking that control
    puts the scale back to 100%, which is the only affordance that returns from
    250% without counting clicks on the decrease button.

    Behaviour, not the readout *text*, is what the click is checked by. The
    suite pins `GRAMTRANS_NO_THEME=1` (root conftest), so the ThemeManager is
    never installed: `_apply()` returns early and the `changed` signal that
    refreshes the strip's labels never fires. The step still moves, which is the
    capability FR-005 is about; a text assertion here would be asserting a
    signal the test environment deliberately suppresses.

    The font step is restored in a `finally`. It is persisted to QSettings, so
    leaving it moved would change what the developer's next real GUI session
    opens at.
    """
    strip = _the_strip(header_case)
    theme = gt_theme.theme()

    readout = re.compile(r"^\d+%$")
    readouts = [b for b in _strip_buttons(strip) if readout.match(b.text())]
    assert len(readouts) == 1, (
        f"[FAIL] FR-005 at {header_case.label}: found {len(readouts)} "
        f"percentage readout(s) on the strip, expected 1. Button texts: "
        f"{_button_texts(strip)!r}"
    )
    button = readouts[0]
    assert button.text() == f"{theme.font_percent()}%", (
        f"[FAIL] FR-005 at {header_case.label}: the readout shows "
        f"{button.text()!r} while the theme reports {theme.font_percent()}%."
    )

    original_step = theme.font_step
    try:
        theme.set_font_step(2)
        assert theme.font_percent() != 100, (
            "[FAIL] test precondition: the font step did not move, so clicking "
            "the readout could not be observed returning it to 100%."
        )
        button.click()
        assert theme.font_percent() == 100, (
            f"[FAIL] FR-005 at {header_case.label}: clicking the percentage "
            f"readout left the scale at {theme.font_percent()}% -- the "
            f"click-to-100% reset did not survive the move into the header."
        )
    finally:
        theme.set_font_step(original_step)


def test_the_colour_mode_toggle_survives(header_case: Case) -> None:
    """FR-005: the light/dark toggle is still there, still labelled by its target.

    The button's text is the mode it will switch *to* ("Dark Mode" while light,
    "Light Mode" while dark), which is why both strings are accepted and the one
    shown is checked against the manager's current mode. `toggle_mode()` is not
    called: it persists the choice to QSettings, and flipping a developer's saved
    interface mode is a side effect no layout test should have.
    """
    strip = _the_strip(header_case)
    theme = gt_theme.theme()
    expected = "Light Mode" if theme.mode == gt_theme.DARK else "Dark Mode"

    toggles = [b for b in _strip_buttons(strip)
               if b.text() in ("Dark Mode", "Light Mode")]
    assert len(toggles) == 1, (
        f"[FAIL] FR-005 at {header_case.label}: found {len(toggles)} colour-mode "
        f"toggle(s) on the strip, expected 1. Button texts: "
        f"{_button_texts(strip)!r}"
    )
    assert toggles[0].text() == expected, (
        f"[FAIL] FR-005 at {header_case.label}: the toggle reads "
        f"{toggles[0].text()!r} while the theme is in {theme.mode!r} mode -- it "
        f"should name the mode it switches to ({expected!r})."
    )
    assert toggles[0].isEnabled(), (
        f"[FAIL] FR-005 at {header_case.label}: the colour-mode toggle is "
        f"disabled."
    )


def test_each_view_control_shortcut_is_registered_exactly_once(
    header_case: Case,
) -> None:
    """FR-005: `ZoomIn`, `ZoomOut` and `Ctrl+0` all survive, each registered once.

    "Exactly once" is the load-bearing half. Twelve pages each holding their own
    control strip would each register `Ctrl+0` on the same window, and Qt
    resolves an ambiguous shortcut by firing *nothing* -- so the naive
    one-strip-per-page implementation of FR-004 would silently delete three
    keyboard shortcuts while every button still worked, and a test that only
    checked "at least one" would call that a pass.

    All three of Qt's registration channels are counted together (`QShortcut`,
    `QAction`, and `QAbstractButton.setShortcut`), because ambiguity does not
    care which channel a sequence arrived through. Standard keys are compared
    against `QKeySequence.keyBindings()` rather than a hand-written "Ctrl++", so
    the test does not pass or fail by platform.
    """
    wizard = header_case.wizard
    registrations = _shortcut_registrations(wizard)
    assert registrations, (
        f"[FAIL] FR-005 at {header_case.label}: the wizard registers no keyboard "
        f"shortcuts at all, so none of the strip's shortcuts survived."
    )

    problems: list[str] = []
    for name, key in (
        ("ZoomIn", QtGui.QKeySequence.StandardKey.ZoomIn),
        ("ZoomOut", QtGui.QKeySequence.StandardKey.ZoomOut),
        ("Ctrl+0", "Ctrl+0"),
    ):
        targets = [t.toString() for t in _targets_for(key)]
        owners = _owners_of(registrations, key)
        if len(owners) == 0:
            problems.append(
                f"{name} ({targets}) is registered nowhere -- the shortcut did "
                f"not survive the move into the header"
            )
        elif len(owners) > 1:
            problems.append(
                f"{name} ({targets}) is registered {len(owners)} times, by "
                f"{owners} -- Qt resolves an ambiguous shortcut by firing "
                f"nothing, so this shortcut is dead"
            )

    assert not problems, (
        f"[FAIL] FR-005 at {header_case.label}:\n  - " + "\n  - ".join(problems)
    )


# ---------------------------------------------------------------------------
# FR-013 / SC-009 -- the two-line copy budget, at the default only
# ---------------------------------------------------------------------------

def test_every_step_description_fits_two_lines_at_the_default(
    default_case: Case, wizard_source: str
) -> None:
    """FR-013, SC-009: no description exceeds two lines at the default size.

    FR-013 is a *copy* budget, not a layout guarantee: "measured once at the
    default, not a guarantee at every size". So the measurement has one valid
    point, and it has to be the size the wizard actually opens at -- hence the
    source check below. A budget measured at a width nobody opens at would
    licence copy that overflows for every real operator.

    Line counts come from the harness, which measures with the label's own
    QFontMetrics at the label's own width and divides by `lineSpacing()` -- the
    pitch Qt lays wrapped text out on. Pixels would not do: the requirement is
    stated in lines, and a pixel budget would have to be re-derived every time
    the default font changed.

    Over-long descriptions are reported together, with their line count and the
    text, because T044's job is to shorten exactly this list.
    """
    assert re.search(r"self\.resize\(\s*1300\s*,\s*760\s*\)", wizard_source), (
        f"[FAIL] FR-013: the wizard no longer opens at "
        f"{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}, so this module is "
        f"measuring the two-line budget at a width that is not the default any "
        f"more. Update DEFAULT_WINDOW_WIDTH here and re-measure the copy."
    )
    assert default_case.wizard.width() == DEFAULT_WINDOW_WIDTH, (
        f"[FAIL] FR-013: measuring at {default_case.wizard.width()} px, not the "
        f"{DEFAULT_WINDOW_WIDTH} px default (minimumWidth() is "
        f"{default_case.wizard.minimumWidth()})."
    )

    checked = 0
    over: list[str] = []
    for pid, page, header in _iter_headers(default_case):
        label = header.description_label()
        if not _flat(label.text()):
            continue
        checked += 1
        lines = geom.wrapped_line_count(label)
        if lines > LINE_BUDGET_AT_DEFAULT:
            over.append(
                f"page {pid} ({type(page).__name__}): {lines} lines in "
                f"{label.width()} px -- {_flat(label.text())!r}"
            )

    assert checked >= MIN_FLOW_PAGES, (
        f"[FAIL] vacuous sweep: only {checked} description(s) measured at "
        f"{default_case.label}, expected at least {MIN_FLOW_PAGES}."
    )
    assert not over, (
        f"[FAIL] FR-013/SC-009: {len(over)} step description(s) exceed the "
        f"{LINE_BUDGET_AT_DEFAULT}-line budget at {default_case.label}. The "
        f"budget is the ceiling, not a starting point -- shorten the copy "
        f"(T044):\n  - " + "\n  - ".join(over)
    )


# ---------------------------------------------------------------------------
# FR-012 -- a description that fits reserves no blank second line
# ---------------------------------------------------------------------------

def test_a_description_that_fits_reserves_no_blank_second_line(
    header_case: Case,
) -> None:
    """FR-012: "a description that fits MUST remain on one line".

    Measured by *setting* a short description rather than by hoping some page
    has one. A test that filtered the pages for one-liners would go quiet the day
    the copy changed, and would say nothing at the 900 px floor where nothing
    fits on one line -- yet the requirement holds at both sizes.

    The claim is asserted on the label's own vertical demand
    (`heightForWidth`), not on the height the layout gave it. The label shares a
    row with the control strip, which is taller than one line of text, so the
    *allotted* height is the row's height and would report two lines' worth of
    space for a one-line label that reserved nothing. `sizeHint().height()` is no
    use either: for a wrapping QLabel it is Qt's own aspect-ratio guess, which is
    frequently two lines, and the production header deliberately keeps a
    `Preferred` vertical policy so that guess never becomes a floor.
    """
    wizard = header_case.wizard
    pid, page, _longest = _longest_description(header_case)
    header = _require_header(header_case, page, pid)
    geom.show_page(wizard, page)

    label = header.description_label()
    original = page.subTitle()
    try:
        header.set_description(SHORT_DESCRIPTION)
        geom.settle(header)
        geom.settle(page)

        one_line = _line_spacing(label)
        width = max(1, label.contentsRect().width())
        lines = geom.wrapped_line_count(label, width=width)
        demanded = label.heightForWidth(width) if label.hasHeightForWidth() else None

        assert lines == 1, (
            f"[FAIL] test precondition at {header_case.label}: "
            f"{SHORT_DESCRIPTION!r} wrapped to {lines} lines in {width} px, so "
            f"there is no one-line case to check. Shorten SHORT_DESCRIPTION."
        )
        assert demanded is not None, (
            f"[FAIL] FR-012 at {header_case.label}: the description label does "
            f"not implement heightForWidth, so its height cannot follow its "
            f"wrapped text and the layout must be reserving a fixed number of "
            f"lines."
        )
        assert demanded < 2 * one_line, (
            f"[FAIL] FR-012 at {header_case.label}: a one-line description asks "
            f"for {demanded} px at {width} px wide, which is at least two lines "
            f"({one_line} px each) -- a blank second line is being reserved."
        )
    finally:
        header.set_description(original)
        geom.settle(header)
        geom.settle(page)


# ---------------------------------------------------------------------------
# FR-013a / SC-009 -- a wrapped description is absorbed, not paid for
# ---------------------------------------------------------------------------

def test_a_wrapped_description_pushes_nothing_off_screen_and_overlaps_nothing(
    header_case: Case,
) -> None:
    """FR-013a: the extra line is absorbed -- no clipping, overlap, or overflow.

    The page's faults are captured *before* the description is grown and
    subtracted from the faults captured after, so only what growing the
    description introduced is reported. US3 owns "nothing is clipped at 900 px"
    and has its own module; if this test redded for a pre-existing floor defect,
    whoever picked it up would go looking in the wrong story.

    All three failure modes named in the requirement are counted, because they
    are three different bugs: a widget escaping its parent's usable area
    (clipped), two peers drawn over one another (overlapped), and a widget
    pushed outside the window (off screen).
    """
    wizard = header_case.wizard
    pid, page, _longest = _longest_description(header_case)
    header = _require_header(header_case, page, pid)
    geom.show_page(wizard, page)
    geom.settle(page)

    label = header.description_label()
    original = page.subTitle()
    try:
        header.set_description(SHORT_DESCRIPTION)
        geom.settle(header)
        geom.settle(page)
        baseline = _layout_faults(page, wizard)

        header.set_description(_description_of_lines(label, THIRD_LINE_MINIMUM))
        geom.settle(header)
        geom.settle(page)
        lines = geom.wrapped_line_count(label)
        assert lines >= 2, (
            f"[FAIL] test precondition at {header_case.label}: the long "
            f"description occupies {lines} line(s) in {label.width()} px, so "
            f"nothing was actually wrapped and this test proves nothing."
        )

        introduced = _new_faults(baseline, _layout_faults(page, wizard))
        assert not introduced, (
            f"[FAIL] FR-013a at {header_case.label}: growing the description on "
            f"page {pid} ({type(page).__name__}) to {lines} lines introduced "
            f"{len(introduced)} layout fault(s) that a one-line description did "
            f"not have. The extra line must be absorbed, not paid for by the "
            f"page:\n  - " + "\n  - ".join(introduced)
        )
    finally:
        header.set_description(original)
        geom.settle(header)
        geom.settle(page)


def test_a_third_line_is_absorbed_without_clipping_the_description(
    header_case: Case,
) -> None:
    """FR-013a, SC-009: a third line is permitted, and absorbed without clipping.

    FR-013a permits a third line at a narrower width or a larger text scale and
    then makes the layout responsible for it: absorb it "without clipping the
    description, overlapping the zoom and colour-mode controls (FR-004), or
    pushing page content off screen". So four things are checked once a
    three-line description is in place:

    * the label was actually *given* the height its wrapped text needs -- a
      label handed two lines' worth of space for three lines of text is the
      clipping this forbids, and it is invisible to an overlap check;
    * the label stays inside the header's own usable area;
    * the header grew relative to the one-line case, which is what "absorbed"
      means -- a header of fixed height cannot be absorbing anything;
    * the description still does not touch the controls slot, since a third line
      is the case where the old floating strip was run under.

    The three-line description is forced rather than found. At the default width
    and scale nothing in the wizard should need three lines at all (that is
    FR-013), so a test that waited for one would be permanently vacuous exactly
    where FR-013 is being obeyed.
    """
    wizard = header_case.wizard
    pid, page, _longest = _longest_description(header_case)
    header = _require_header(header_case, page, pid)
    geom.show_page(wizard, page)

    label = header.description_label()
    slot = header.controls_slot()
    original = page.subTitle()
    try:
        header.set_description(SHORT_DESCRIPTION)
        geom.settle(header)
        geom.settle(page)
        one_line_header_height = header.height()

        header.set_description(_description_of_lines(label, THIRD_LINE_MINIMUM))
        geom.settle(header)
        geom.settle(page)

        width = max(1, label.contentsRect().width())
        lines = geom.wrapped_line_count(label, width=width)
        one_line = _line_spacing(label)
        needed = (
            label.heightForWidth(width) if label.hasHeightForWidth()
            else lines * one_line
        )

        assert lines >= THIRD_LINE_MINIMUM, (
            f"[FAIL] test precondition at {header_case.label}: the long "
            f"description occupies {lines} line(s) in {width} px, fewer than "
            f"the {THIRD_LINE_MINIMUM} this test is about -- "
            f"`_description_of_lines` could not compose one."
        )
        assert label.height() + HEIGHT_TOLERANCE >= needed, (
            f"[FAIL] FR-013a at {header_case.label}: the description needs "
            f"{needed} px for {lines} lines at {width} px wide but was given "
            f"{label.height()} px -- the extra line is clipped, not absorbed."
        )
        header_allowed = geom.usable_rect(header)
        assert header_allowed.contains(label.geometry()), (
            f"[FAIL] FR-013a at {header_case.label}: the description "
            f"{label.geometry()} escapes its header's usable area "
            f"{header_allowed}."
        )
        assert header.height() > one_line_header_height, (
            f"[FAIL] FR-013a at {header_case.label}: the header is "
            f"{header.height()} px tall with a {lines}-line description and "
            f"{one_line_header_height} px with a one-line one -- it is not "
            f"growing to absorb the extra lines, so they can only be going "
            f"somewhere they do not belong."
        )
        label_rect = geom.rect_in(label, wizard)
        slot_rect = geom.rect_in(slot, wizard)
        assert not slot_rect.isEmpty(), (
            f"[FAIL] FR-004 at {header_case.label}: the controls slot reserves "
            f"no space ({slot_rect}), so the non-intersection claim below is "
            f"vacuous -- see the SC-005a test."
        )
        assert not label_rect.intersects(slot_rect), (
            f"[FAIL] FR-013a/FR-004 at {header_case.label}: a {lines}-line "
            f"description {label_rect} runs into the controls slot {slot_rect} "
            f"(intersection {label_rect.intersected(slot_rect)})."
        )
    finally:
        header.set_description(original)
        geom.settle(header)
        geom.settle(page)
