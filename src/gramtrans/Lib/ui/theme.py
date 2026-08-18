"""Interface theme + text-size service (light / dark, 10% font steps).

Why this module exists
---------------------
GramTrans' users are field linguists, many of them reading small UI text with
older eyes.  Before this module the GUI had *no* theme of its own: it inherited
whatever palette Windows handed it, and the handful of hard-coded colours in the
widgets (``#666`` prior-value grey, ``#fff3cd`` warning amber, the merge-preview
diff greens/reds) were tuned for one background only.  Under an OS dark theme
those colours went unreadable; under a light theme the greys were too faint.

This module centralises **two** things and makes both switchable at runtime:

1. **Palette** -- a full :class:`Palette` token set for LIGHT and DARK.  Every
   colour the GUI uses comes from here; nothing else in the UI layer should
   contain a hex literal.  Contrast targets: body text >= 7:1 (WCAG AAA) and
   every semantic colour (added / removed / note / warning) >= 4.5:1 against its
   own background, in *both* modes.
2. **Text size** -- an additive scale in 10-percentage-point steps
   (``scale = 1 + 0.10 * step``, so the readout walks 100, 110, 120, 130 ...
   rather than compounding to 100, 110, 121, 133), applied to the application font *and* to the
   metrics that Qt would otherwise keep fixed (checkbox indicators, scrollbar
   width, tree indentation) via :class:`_ScaledProxyStyle`, *and* to the
   merge-preview HTML (which carries absolute ``pt`` sizes from FLEx writing
   systems).  Bumping the font alone would leave 13px checkboxes next to 30px
   text, so all three move together.

Architecture
------------
- **QPalette carries colour; QSS carries metrics/chrome.**  The Fusion style is
  installed because the native ``windowsvista`` style ignores palette roles for
  many widgets, which is exactly what made a "consistent" theme impossible.
- ``Lib/merge_preview.py`` must stay Qt-free (feature 012 SC-007), so this
  module *pushes* colours and the render scale into it via
  ``merge_preview.set_diff_theme()``.  The dependency runs one way only:
  theme -> merge_preview, never back.
- Widgets that need to redraw on a change connect to :attr:`ThemeManager.changed`.
- The choice persists in ``QSettings("SIL", "GramTrans")`` under ``ui/mode`` and
  ``ui/font_step``, so a user who scales the text up once never has to do it again.

Opt-out: set ``GRAMTRANS_NO_THEME=1`` to leave the host's palette untouched
(escape hatch for a host that already themes its own Qt application).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional

from PyQt6 import QtCore, QtGui, QtWidgets

if __package__:
    from .. import merge_preview as _merge_preview
else:  # flat import mode (Lib/ + Lib/ui on sys.path)
    import merge_preview as _merge_preview  # type: ignore

_log = logging.getLogger(__name__)

LIGHT = "light"
DARK = "dark"

#: Percentage points the +/- buttons add or remove per step, as a fraction.
#: Additive (not compounding) so the readout lands on round tens: 100, 110,
#: 120, 130 ... A step of -10 would reach 0%, hence the clamp below.
FONT_STEP_INCREMENT = 0.10
#: Step clamp.  -3 => 70% (below this, labels clip); +10 => 200%.
#:
#: 200%, not 250%: this scale is applied ON TOP OF the operating system's own
#: display scaling, and an operator who needs large text is already running the
#: OS at 125% or more.  Treating our 250% as a size the layout must survive
#: therefore meant guaranteeing roughly 300% effective -- a budget no page can
#: meet without reflowing, and one no real operator asks for.  Capping here
#: buys back the layout headroom instead of spending it on an unreachable case.
#:
#: This is the value "the largest supported text scale" resolves to throughout
#: feature 036 (FR-032, SC-005, SC-005a, SC-009), so the geometry harness reads
#: it from here rather than restating a number.
MIN_FONT_STEP = -3
MAX_FONT_STEP = 10

_ENV_DISABLE = "GRAMTRANS_NO_THEME"
_SETTINGS_ORG = "SIL"
_SETTINGS_APP = "GramTrans"
_KEY_MODE = "ui/mode"
_KEY_STEP = "ui/font_step"


# ---------------------------------------------------------------------------
# Palette tokens
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Palette:
    """One complete colour scheme.

    Field names map onto either a ``QPalette.ColorRole`` (see
    :func:`_qpalette`) or a QSS/HTML token.  Contrast figures in the comments
    are against the surface the token is actually painted on.
    """

    name: str

    # -- surfaces -----------------------------------------------------------
    window: str            # dialog / page background
    base: str              # text-entry + list background
    alternate_base: str    # alternating rows
    header_bg: str         # QHeaderView sections
    tooltip_base: str

    # -- foregrounds --------------------------------------------------------
    window_text: str       # >= 7:1 on `window`
    text: str              # >= 7:1 on `base`
    header_text: str
    tooltip_text: str
    muted_text: str        # >= 4.5:1 -- secondary/"prior value" text
    disabled_text: str
    bright_text: str

    # -- controls -----------------------------------------------------------
    button: str
    button_text: str
    button_hover: str
    button_pressed: str
    border: str            # 1px separators / control outlines
    border_strong: str     # button outlines, tooltip outline
    focus: str             # 2px focus ring -- must be visible on both surfaces
    highlight: str         # selection background
    highlighted_text: str  # >= 4.5:1 on `highlight`
    link: str

    # -- semantics ----------------------------------------------------------
    warning_bg: str
    warning_text: str      # >= 4.5:1 on `warning_bg`
    warning_border: str

    # -- merge-preview diff (pushed into Lib/merge_preview.py) --------------
    diff_added: str
    diff_removed: str
    diff_note: str
    diff_divider: str


#: Light scheme.  Surfaces are a hair off pure white (#FFFFFF is kept for the
#: text/list `base` where crispness matters) because a full-page pure white at
#: high brightness is the most common glare complaint from older readers.
LIGHT_PALETTE = Palette(
    name=LIGHT,
    window="#F2F3F5",
    base="#FFFFFF",
    alternate_base="#E9ECF1",
    header_bg="#DFE3E9",
    tooltip_base="#FFFBE6",
    window_text="#12151A",       # 16.5:1 on #F2F3F5
    text="#12151A",              # 18.3:1 on #FFFFFF
    header_text="#12151A",       # 14.2:1 on #DFE3E9
    tooltip_text="#12151A",
    muted_text="#4E545B",        # 7.7:1 on #FFFFFF
    # 4.9:1 on the button face, 6.1:1 on base.  The old #7A8189 measured 3.1:1
    # on a button and 3.1:1 on the header bar -- the worst disabled contrast in
    # either scheme.  Darker, not lighter, because this is the light mode: the
    # direction that dims a label is toward the background in both cases.
    disabled_text="#5C6369",
    bright_text="#A8000F",
    button="#E3E6EB",
    button_text="#12151A",
    button_hover="#D3D8E0",
    button_pressed="#C3C9D3",
    border="#B4BAC2",
    border_strong="#7C848E",
    focus="#1B5FB0",             # 5.7:1 on #F2F3F5
    highlight="#1B5FB0",
    highlighted_text="#FFFFFF",  # 6.3:1 on #1B5FB0
    link="#0B4FA0",
    warning_bg="#FFF3C4",
    warning_text="#5C3D00",      # 8.9:1 on #FFF3C4
    warning_border="#D9A800",
    diff_added="#0A6B22",        # 6.7:1 on #FFFFFF
    diff_removed="#A8000F",      # 7.9:1 on #FFFFFF
    diff_note="#4E545B",         # 7.7:1 on #FFFFFF
    diff_divider="#B4BAC2",
)

#: Dark scheme.  Mirrors the light token-for-token so a widget styled once is
#: correct in both; nothing here is a "dimmed" light value.
#:
#: The accent family here is GREEN (`alternate_base`, `button`, `button_hover`,
#: `button_pressed`, `focus`) while the light scheme's stays neutral/blue.  Two
#: things are deliberately *not* green and the reasons are worth keeping:
#:
#: - `highlight` / `highlighted_text` stay blue.  Selection is a state, not an
#:   accent; a green band would read as an "added" marker and would stop
#:   separating from the now-green striped row behind it.
#: - Every semantic token (warning / diff) is untouched.  Chrome may be retuned;
#:   a colour that carries a *meaning* may not.
#:
#: Every value below is fenced by the automated contrast and CIE-Lab DeltaE76
#: floors in tests/unit/test_theme_manager.py -- retune freely, but rerun those.
DARK_PALETTE = Palette(
    name=DARK,
    window="#22262B",
    base="#191C20",
    # Green-tinted stripe, and a bigger step from `base` than the old #23272D:
    # the striping has to be visible at a glance (DeltaE76 10.6 from base, floor
    # 4) without becoming a second surface colour.
    alternate_base="#1F2A23",
    header_bg="#2A2F35",
    tooltip_base="#33383F",
    window_text="#E9EDF2",       # 12.9:1 on #22262B
    text="#E9EDF2",              # 14.5:1 on #191C20
    header_text="#E9EDF2",       # 11.5:1 on #2A2F35
    tooltip_text="#E9EDF2",
    muted_text="#AAB2BB",        # 8.0:1 on #191C20
    # 6.6:1 on base, and -- the number that actually mattered and was never
    # measured -- 5.1:1 on the BUTTON face.  The old #858D96 was picked against
    # `base` (5.1:1 there) but a disabled label mostly sits on a button, where it
    # measured only 3.9:1 and read as a smudge rather than as text.  Still just
    # 45% of the enabled label's 11.2:1, so it reads as plainly disabled.
    disabled_text="#9AA2AA",
    bright_text="#FF8A8A",
    button="#26332B",            # 11.2:1 for button_text
    button_text="#E9EDF2",
    button_hover="#2F4235",
    button_pressed="#39503F",
    # Deliberately lighter than a "correct" dark separator: Fusion draws
    # checkbox/radio indicator outlines from Mid/Dark, and against a #191C20
    # base a subtler pair left an unchecked radio almost invisible.
    border="#4A515A",
    border_strong="#6C7480",
    # Neon green, and it is the ring's job to be the loudest green on screen:
    # the muted accent family above says "this is chrome", the ring says "this
    # is where your keyboard is".  A saturated green also puts the most distance
    # between the ring and the frozen semantic `diff_added` below, which is the
    # one measurement that constrains this token (FR-027): DeltaE76 65.0, versus
    # a floor of 25 -- a mid mint would have measured 8.8, the same colour
    # perceptually, which is why the obvious green is the wrong one here.
    # 11.2:1 on #22262B.
    focus="#39FF14",
    # Blue on purpose in a green scheme -- see the header note.  Not darkened
    # further either: white-on-selection is 4.9:1 (AA), and a darker blue would
    # buy text contrast at the cost of the selection band's own contrast against
    # the list base (3.5:1 -> 2.8:1) -- i.e. "which row am I on?"
    highlight="#2F6FD0",
    highlighted_text="#FFFFFF",  # 4.9:1 on #2F6FD0
    link="#7FB5FF",
    warning_bg="#3D3308",
    warning_text="#FFD873",      # 9.1:1 on #3D3308
    warning_border="#8A7414",
    diff_added="#5FD48A",        # 9.2:1 on #191C20
    diff_removed="#FF8A8A",      # 7.5:1 on #191C20
    diff_note="#AAB2BB",         # 8.0:1 on #191C20
    diff_divider="#3C424A",
)

PALETTES: Dict[str, Palette] = {LIGHT: LIGHT_PALETTE, DARK: DARK_PALETTE}


# ---------------------------------------------------------------------------
# Scaled proxy style -- the metrics QSS cannot reach
# ---------------------------------------------------------------------------

class _ScaledProxyStyle(QtWidgets.QProxyStyle):
    """Fusion, with size-independent pixel metrics scaled by the font factor.

    Qt derives checkbox/radio indicator size, scrollbar width and tree
    indentation from *fixed* pixel metrics, not from the font.  At 200% text a
    13px checkbox beside 20pt text is both ugly and hard to hit, so we scale
    those metrics alongside the font.  Doing it in a proxy style (rather than
    ``QCheckBox::indicator { width: … }`` in QSS) keeps Fusion drawing the
    check mark itself -- a QSS size override makes Qt style the subcontrol from
    scratch and the tick disappears.
    """

    _SCALED = frozenset({
        QtWidgets.QStyle.PixelMetric.PM_IndicatorWidth,
        QtWidgets.QStyle.PixelMetric.PM_IndicatorHeight,
        QtWidgets.QStyle.PixelMetric.PM_ExclusiveIndicatorWidth,
        QtWidgets.QStyle.PixelMetric.PM_ExclusiveIndicatorHeight,
        QtWidgets.QStyle.PixelMetric.PM_ScrollBarExtent,
        QtWidgets.QStyle.PixelMetric.PM_SmallIconSize,
        QtWidgets.QStyle.PixelMetric.PM_ButtonIconSize,
        QtWidgets.QStyle.PixelMetric.PM_TreeViewIndentation,
    })

    def __init__(self, scale: float, base_style_name: str = "Fusion") -> None:
        base = QtWidgets.QStyleFactory.create(base_style_name)
        # QStyleFactory returns None for an unknown key; a bare QProxyStyle
        # then falls back to the application style, which is still correct.
        if base is not None:
            super().__init__(base)
        else:
            super().__init__()
        self._scale = float(scale)

    def set_scale(self, scale: float) -> None:
        """Retune in place.

        The scale is mutable *precisely so that a text-size change never calls
        ``QApplication.setStyle`` twice*: setStyle hands ownership of the new
        style to Qt and destroys the outgoing one, and the very next re-polish
        (``setStyleSheet``) then walks widgets still pointing at the freed
        object -- an access violation, reproduced reliably on the second theme
        change.  One style instance for the process lifetime, re-tuned here.
        """
        self._scale = float(scale)

    def pixelMetric(self, metric, option=None, widget=None) -> int:  # noqa: N802
        value = super().pixelMetric(metric, option, widget)
        if metric in self._SCALED and value > 0:
            return max(1, int(round(value * self._scale)))
        return value


# ---------------------------------------------------------------------------
# QPalette / QSS builders
# ---------------------------------------------------------------------------

def _qpalette(pal: Palette) -> QtGui.QPalette:
    """Map a :class:`Palette` onto a full :class:`QtGui.QPalette`.

    The Disabled colour group is set explicitly: left at its default it
    inherits the *style's* grey, which is unreadable on a dark window.
    """
    role = QtGui.QPalette.ColorRole
    group = QtGui.QPalette.ColorGroup
    c = QtGui.QColor
    p = QtGui.QPalette()

    p.setColor(role.Window, c(pal.window))
    p.setColor(role.WindowText, c(pal.window_text))
    p.setColor(role.Base, c(pal.base))
    p.setColor(role.AlternateBase, c(pal.alternate_base))
    p.setColor(role.Text, c(pal.text))
    p.setColor(role.PlaceholderText, c(pal.muted_text))
    p.setColor(role.Button, c(pal.button))
    p.setColor(role.ButtonText, c(pal.button_text))
    p.setColor(role.BrightText, c(pal.bright_text))
    p.setColor(role.ToolTipBase, c(pal.tooltip_base))
    p.setColor(role.ToolTipText, c(pal.tooltip_text))
    p.setColor(role.Highlight, c(pal.highlight))
    p.setColor(role.HighlightedText, c(pal.highlighted_text))
    p.setColor(role.Link, c(pal.link))
    p.setColor(role.LinkVisited, c(pal.link))
    p.setColor(role.Light, c(pal.button_hover))
    p.setColor(role.Midlight, c(pal.button))
    p.setColor(role.Mid, c(pal.border))
    p.setColor(role.Dark, c(pal.border_strong))
    p.setColor(role.Shadow, c(pal.border_strong))

    for disabled_role in (role.WindowText, role.Text, role.ButtonText,
                          role.HighlightedText, role.PlaceholderText):
        p.setColor(group.Disabled, disabled_role, c(pal.disabled_text))
    p.setColor(group.Disabled, role.Highlight, c(pal.border))
    return p


def build_stylesheet(pal: Palette, scale: float) -> str:
    """Chrome + metrics QSS for `pal` at `scale`.

    Colour here duplicates the palette only where Qt gives QSS no palette hook
    (tooltip border, header sections, focus ring).  Everything spatial is
    scaled so padding grows with the text instead of squeezing it.
    """
    def px(value: float) -> int:
        return max(1, int(round(value * scale)))

    return f"""
/* --- tooltips: the one surface Qt paints outside the palette by default --- */
QToolTip {{
    color: {pal.tooltip_text};
    background-color: {pal.tooltip_base};
    border: 1px solid {pal.border_strong};
    padding: {px(4)}px {px(6)}px;
}}

/* --- menus --- */
QMenu {{ background-color: {pal.base}; color: {pal.text};
         border: 1px solid {pal.border}; padding: {px(3)}px; }}
QMenu::item {{ padding: {px(4)}px {px(18)}px; }}
QMenu::item:selected {{ background-color: {pal.highlight}; color: {pal.highlighted_text}; }}
QMenu::separator {{ height: 1px; background: {pal.border}; margin: {px(4)}px 0; }}

/* --- item views: both panes of every wizard page live here --- */
QTreeView, QTreeWidget, QListView, QListWidget, QTableView, QTableWidget {{
    border: 1px solid {pal.border};
    alternate-background-color: {pal.alternate_base};
}}
QTreeView::item, QListView::item, QTableView::item {{
    padding: {px(3)}px {px(2)}px;
}}
QTreeView::item:selected, QListView::item:selected, QTableView::item:selected {{
    background-color: {pal.highlight};
    color: {pal.highlighted_text};
}}
QHeaderView::section {{
    background-color: {pal.header_bg};
    color: {pal.header_text};
    padding: {px(4)}px {px(6)}px;
    border: 0px;
    border-right: 1px solid {pal.border};
    border-bottom: 1px solid {pal.border};
    font-weight: 600;
}}
QHeaderView::section:last {{ border-right: 0px; }}

/* --- text entry / display --- */
QLineEdit, QPlainTextEdit, QTextEdit, QTextBrowser, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {pal.base};
    color: {pal.text};
    border: 1px solid {pal.border};
    border-radius: {px(3)}px;
    padding: {px(3)}px {px(4)}px;
    selection-background-color: {pal.highlight};
    selection-color: {pal.highlighted_text};
}}
QComboBox QAbstractItemView {{
    background-color: {pal.base};
    color: {pal.text};
    border: 1px solid {pal.border};
    selection-background-color: {pal.highlight};
    selection-color: {pal.highlighted_text};
}}

/* --- a focus ring you can actually see (2px, scaled) ---
   This block is the ONLY thing that paints a focus ring, and its colour is the
   `focus` token -- so retuning `focus` (green in dark mode, blue in light)
   retints every ring in the application with no other edit.  Width stays 2px at
   100% and grows with the text; 1px vanishes on a high-DPI field laptop. */
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QTextBrowser:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QTreeView:focus, QTreeWidget:focus, QListView:focus, QListWidget:focus,
QTableView:focus, QTableWidget:focus, QPushButton:focus, QToolButton:focus {{
    border: {px(2)}px solid {pal.focus};
}}

/* --- buttons --- */
QPushButton {{
    background-color: {pal.button};
    color: {pal.button_text};
    border: 1px solid {pal.border_strong};
    border-radius: {px(3)}px;
    padding: {px(5)}px {px(12)}px;
    min-height: {px(18)}px;
}}
QPushButton:hover {{ background-color: {pal.button_hover}; }}
QPushButton:pressed {{ background-color: {pal.button_pressed}; }}
QPushButton:disabled {{ color: {pal.disabled_text}; border-color: {pal.border}; }}
QPushButton:default {{ border: {px(2)}px solid {pal.focus}; }}

QToolButton {{
    background-color: transparent;
    color: {pal.window_text};
    border: 1px solid transparent;
    border-radius: {px(3)}px;
    padding: {px(2)}px {px(6)}px;
}}
QToolButton:hover {{ background-color: {pal.button_hover}; border-color: {pal.border}; }}
QToolButton:pressed {{ background-color: {pal.button_pressed}; }}

/* --- grouping / structure --- */
QGroupBox {{
    border: 1px solid {pal.border};
    border-radius: {px(4)}px;
    margin-top: {px(10)}px;
    padding-top: {px(8)}px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: {px(8)}px;
    padding: 0 {px(4)}px;
    color: {pal.window_text};
}}
QSplitter::handle {{ background-color: {pal.border}; }}
QSplitter::handle:horizontal {{ width: {px(4)}px; }}
QSplitter::handle:vertical {{ height: {px(4)}px; }}
QTabBar::tab {{ padding: {px(5)}px {px(10)}px; }}
QTabWidget::pane {{ border: 1px solid {pal.border}; }}
QProgressBar {{ border: 1px solid {pal.border}; border-radius: {px(3)}px; text-align: center; }}
QProgressBar::chunk {{ background-color: {pal.highlight}; }}

/* --- the theme/text-size strip, laid out in each page's header slot --- */
#gtThemeBar {{
    background-color: {pal.header_bg};
    border: 1px solid {pal.border};
    border-radius: {px(4)}px;
}}
/* min-width:0 because a bare QToolButton reports a ~60px minimum hint whatever
   its text is; the bar sizes its own buttons from font metrics instead, and
   without this the strip balloons to ~390px and takes width the page header's
   description needs for wrapping. */
#gtThemeBar QToolButton {{ color: {pal.header_text}; padding: {px(2)}px {px(4)}px;
                           min-width: 0px; }}
#gtThemeBar QLabel {{ color: {pal.header_text}; }}
"""


# ---------------------------------------------------------------------------
# Item-font rescaling
# ---------------------------------------------------------------------------

def _rescale_item_font(font: QtGui.QFont, point_size: float) -> QtGui.QFont:
    out = QtGui.QFont(font)
    out.setPointSizeF(point_size)
    return out


def _rescale_tree_item(item, point_size: float) -> None:
    role = QtCore.Qt.ItemDataRole.FontRole
    for col in range(item.columnCount()):
        stored = item.data(col, role)
        if isinstance(stored, QtGui.QFont):
            item.setData(col, role, _rescale_item_font(stored, point_size))
    for i in range(item.childCount()):
        _rescale_tree_item(item.child(i), point_size)


def rescale_item_fonts(root: QtWidgets.QWidget, point_size: float) -> None:
    """Re-point every *explicitly set* item font under `root` to `point_size`.

    ``QApplication.setFont`` reaches widgets but not per-item fonts: the wizard
    bolds section headers with ``item.setFont(0, item.font(0))``, which snapshots
    the size in force when the tree was built.  Without this pass, pressing A+
    scales the leaf rows and leaves every bold header behind at the old size.
    Bold/italic/family are preserved -- only the point size moves.
    """
    role = QtCore.Qt.ItemDataRole.FontRole

    for tree in root.findChildren(QtWidgets.QTreeWidget):
        header = tree.headerItem()
        if header is not None:
            _rescale_tree_item(header, point_size)
        for i in range(tree.topLevelItemCount()):
            _rescale_tree_item(tree.topLevelItem(i), point_size)

    for table in root.findChildren(QtWidgets.QTableWidget):
        for col in range(table.columnCount()):
            head = table.horizontalHeaderItem(col)
            if head is not None:
                stored = head.data(role)
                if isinstance(stored, QtGui.QFont):
                    head.setData(role, _rescale_item_font(stored, point_size))
        for r in range(table.rowCount()):
            for col in range(table.columnCount()):
                cell = table.item(r, col)
                if cell is None:
                    continue
                stored = cell.data(role)
                if isinstance(stored, QtGui.QFont):
                    cell.setData(role, _rescale_item_font(stored, point_size))

    for listw in root.findChildren(QtWidgets.QListWidget):
        for i in range(listw.count()):
            cell = listw.item(i)
            if cell is None:
                continue
            stored = cell.data(role)
            if isinstance(stored, QtGui.QFont):
                cell.setData(role, _rescale_item_font(stored, point_size))


def rescale_view_columns(root: QtWidgets.QWidget, ratio: float) -> None:
    """Grow/shrink interactively-sized view columns by `ratio`.

    A column that was wide enough for "Verb" at 9pt elides it to "..." at 15pt:
    Qt sizes ``Interactive`` sections once and never revisits them, so scaling
    the text up without this makes the affix and status columns *less* readable
    than before -- the opposite of what the +/- buttons are for.

    Only ``Interactive`` sections are touched.  ``ResizeToContents`` /
    ``Stretch`` sections already follow the font, and a stretched last section
    owns the leftover width by definition, so both are left alone.
    """
    if ratio == 1.0:
        return
    interactive = QtWidgets.QHeaderView.ResizeMode.Interactive
    views: list = list(root.findChildren(QtWidgets.QTreeView))
    views += list(root.findChildren(QtWidgets.QTableView))
    for view in views:
        header = (view.header() if isinstance(view, QtWidgets.QTreeView)
                  else view.horizontalHeader())
        if header is None:
            continue
        count = header.count()
        for i in range(count):
            if header.isSectionHidden(i):
                continue
            if header.sectionResizeMode(i) != interactive:
                continue
            if header.stretchLastSection() and i == count - 1:
                continue
            header.resizeSection(i, max(1, int(round(header.sectionSize(i) * ratio))))


def rescale_table_row_heights(root: QtWidgets.QWidget) -> None:
    """Re-fit ``QTableWidget``/``QTableView`` row heights to their cell widgets.

    ``app.setFont`` grows the font inside cell widgets (e.g. the WS-mapping
    table's MAP/CREATE/SKIP and target-WS combo boxes) but a table never
    revisits a row height it already computed, so at a large zoom step those
    combos get clipped inside their old, too-short rows. ``resizeRowsToContents``
    re-measures every row against its current cell widgets/items.
    """
    for table in root.findChildren(QtWidgets.QTableView):
        table.resizeRowsToContents()


# ---------------------------------------------------------------------------
# ThemeManager
# ---------------------------------------------------------------------------

class ThemeManager(QtCore.QObject):
    """Application-wide palette + text-size state.

    Use the module-level :func:`theme` accessor; there is exactly one manager
    per process.  Call :meth:`install` once a ``QApplication`` exists, then
    :meth:`toggle_mode` / :meth:`increase_font` / :meth:`decrease_font`.

    :attr:`changed` fires *after* the new palette, stylesheet, font, style
    metrics and merge-preview colours are all in place, so a handler can assume
    a fully consistent state.
    """

    changed = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._mode: str = LIGHT
        self._font_step: int = 0
        self._base_point_size: float = 9.0
        self._base_family: str = ""
        # Last size actually pushed to the app, so a step change knows the
        # ratio to widen view columns by (0.0 = nothing applied yet).
        self._applied_point_size: float = 0.0
        self._installed = False
        # Created once, then re-tuned; the reference is held for the process
        # lifetime so the Python wrapper outlives every re-polish.
        self._style: Optional[_ScaledProxyStyle] = None
        self._settings: Optional[QtCore.QSettings] = None

    # -- state ------------------------------------------------------------
    @property
    def mode(self) -> str:
        """``"light"`` or ``"dark"``."""
        return self._mode

    @property
    def palette(self) -> Palette:
        return PALETTES[self._mode]

    @property
    def font_step(self) -> int:
        """Signed number of 10% steps away from the OS default text size."""
        return self._font_step

    @property
    def font_scale(self) -> float:
        """``1 + 0.10 * font_step`` -- the factor applied to text and metrics."""
        return 1.0 + FONT_STEP_INCREMENT * self._font_step

    @property
    def base_point_size(self) -> float:
        """The OS default UI font size captured at :meth:`install` time."""
        return self._base_point_size

    @property
    def scaled_point_size(self) -> float:
        return round(self._base_point_size * self.font_scale, 2)

    @property
    def installed(self) -> bool:
        return self._installed

    # -- install ----------------------------------------------------------
    def install(self, app: Optional[QtWidgets.QApplication] = None) -> bool:
        """Adopt `app`, restore the saved choice, and apply.  Idempotent.

        Returns False (leaving the host's look untouched) when there is no
        ``QApplication`` or ``GRAMTRANS_NO_THEME`` is set.
        """
        if self._installed:
            return True
        if _truthy(os.environ.get(_ENV_DISABLE)):
            _log.info("theme: %s set -- host palette left untouched", _ENV_DISABLE)
            return False
        app = app or QtWidgets.QApplication.instance()
        if app is None:
            _log.debug("theme.install: no QApplication yet")
            return False

        base_font = app.font()
        size = base_font.pointSizeF()
        if size <= 0:  # a pixel-sized font: convert so 10% steps stay meaningful
            px = base_font.pixelSize()
            size = (px * 72.0 / 96.0) if px > 0 else 9.0
        self._base_point_size = float(size)
        self._base_family = base_font.family()

        self._mode = self._restore_mode()
        self._font_step = self._restore_step()
        self._installed = True
        self._apply()
        _log.info("theme: installed mode=%s font_step=%+d (%.1fpt base)",
                  self._mode, self._font_step, self._base_point_size)
        return True

    # -- mutation ---------------------------------------------------------
    def set_mode(self, mode: str) -> None:
        mode = DARK if str(mode).lower() == DARK else LIGHT
        if mode == self._mode:
            return
        self._mode = mode
        self._store(_KEY_MODE, mode)
        self._apply()

    def toggle_mode(self) -> None:
        self.set_mode(LIGHT if self._mode == DARK else DARK)

    def set_font_step(self, step: int) -> None:
        step = max(MIN_FONT_STEP, min(MAX_FONT_STEP, int(step)))
        if step == self._font_step:
            return
        self._font_step = step
        self._store(_KEY_STEP, step)
        self._apply()

    def increase_font(self) -> None:
        """+10% interface text (and the metrics that go with it)."""
        self.set_font_step(self._font_step + 1)

    def decrease_font(self) -> None:
        """-10% interface text."""
        self.set_font_step(self._font_step - 1)

    def reset_font(self) -> None:
        self.set_font_step(0)

    def can_increase(self) -> bool:
        return self._font_step < MAX_FONT_STEP

    def can_decrease(self) -> bool:
        return self._font_step > MIN_FONT_STEP

    def font_percent(self) -> int:
        """Scale as a whole percentage, for the readout on the corner bar.

        Computed from the step in integer arithmetic so the readout is exactly
        100 / 110 / 120 ... instead of whatever ``1 + 0.1 * 3`` rounds to.
        """
        return 100 + int(round(FONT_STEP_INCREMENT * 100)) * self._font_step

    # -- apply ------------------------------------------------------------
    def _apply(self) -> None:
        app = QtWidgets.QApplication.instance()
        if app is None or not self._installed:
            return
        pal = self.palette
        scale = self.font_scale
        point_size = self.scaled_point_size

        # The style is installed ONCE and re-tuned thereafter -- see
        # _ScaledProxyStyle.set_scale for why swapping it is a use-after-free.
        # Order still matters on that first pass: setStyle re-polishes every
        # widget and would otherwise hand back the style's own palette, so
        # palette/QSS/font follow it.
        if self._style is None:
            self._style = _ScaledProxyStyle(scale)
            app.setStyle(self._style)
        else:
            self._style.set_scale(scale)
        app.setPalette(_qpalette(pal))
        app.setStyleSheet(build_stylesheet(pal, scale))

        font = QtGui.QFont(app.font())
        if self._base_family:
            font.setFamily(self._base_family)
        font.setPointSizeF(point_size)
        # setFont invalidates every widget's cached size hint, which is what
        # makes the re-tuned pixel metrics (indicators, scrollbars) take effect
        # without a setStyle round-trip.
        app.setFont(font)

        # Tell Qt which scheme we're in so native bits (e.g. the QTextBrowser
        # caret, dialog frames on Qt >= 6.8) stop guessing from the OS setting.
        self._sync_color_scheme(app)

        # Push colours + render scale into the Qt-free HTML renderer, then let
        # the panes re-render (their cached HTML carries the old colours).
        _merge_preview.set_diff_theme(
            colors={
                "added": pal.diff_added,
                "removed": pal.diff_removed,
                "note": pal.diff_note,
                "divider": pal.diff_divider,
            },
            scale=scale,
        )

        ratio = (point_size / self._applied_point_size
                 if self._applied_point_size > 0 else 1.0)
        for top in app.topLevelWidgets():
            # A window closed but not yet collected is still listed here; its
            # C++ side may already be gone, which PyQt reports as RuntimeError.
            try:
                rescale_item_fonts(top, point_size)
                rescale_view_columns(top, ratio)
                rescale_table_row_heights(top)
            except RuntimeError:
                continue
        self._applied_point_size = point_size

        self.changed.emit()

    def _sync_color_scheme(self, app) -> None:
        """Best-effort ``QStyleHints.setColorScheme`` (Qt >= 6.8); older Qt
        simply keeps the OS scheme, which our palette already overrides."""
        try:
            hints = app.styleHints()
            scheme = QtCore.Qt.ColorScheme
            hints.setColorScheme(scheme.Dark if self._mode == DARK else scheme.Light)
        except (AttributeError, TypeError):
            pass

    # -- persistence ------------------------------------------------------
    def _qsettings(self) -> Optional[QtCore.QSettings]:
        if self._settings is None:
            try:
                self._settings = QtCore.QSettings(_SETTINGS_ORG, _SETTINGS_APP)
            except Exception:  # noqa: BLE001 -- a read-only registry must not crash the GUI
                _log.debug("theme: QSettings unavailable; choice will not persist")
                return None
        return self._settings

    def _store(self, key: str, value) -> None:
        settings = self._qsettings()
        if settings is None:
            return
        try:
            settings.setValue(key, value)
        except Exception:  # noqa: BLE001
            _log.debug("theme: could not persist %s", key)

    def _restore_mode(self) -> str:
        settings = self._qsettings()
        if settings is not None:
            saved = settings.value(_KEY_MODE, "")
            if str(saved).lower() in (LIGHT, DARK):
                return str(saved).lower()
        return _detect_os_mode()

    def _restore_step(self) -> int:
        settings = self._qsettings()
        if settings is None:
            return 0
        try:
            step = int(settings.value(_KEY_STEP, 0))
        except (TypeError, ValueError):
            return 0
        return max(MIN_FONT_STEP, min(MAX_FONT_STEP, step))


def _detect_os_mode() -> str:
    """First-run default: follow the OS scheme when Qt reports one, else light.

    Light is the fallback because it is the scheme this module is designed
    around and the one the request asked for.
    """
    try:
        app = QtWidgets.QApplication.instance()
        hints = app.styleHints() if app is not None else None
        scheme = hints.colorScheme() if hints is not None else None
        if scheme == QtCore.Qt.ColorScheme.Dark:
            return DARK
    except (AttributeError, TypeError):
        pass
    return LIGHT


def _truthy(value: Optional[str]) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on") if value else False


_MANAGER: Optional[ThemeManager] = None


def theme() -> ThemeManager:
    """The process-wide :class:`ThemeManager` (created on first use)."""
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = ThemeManager()
    return _MANAGER


def install_theme(app: Optional[QtWidgets.QApplication] = None) -> ThemeManager:
    """Convenience: fetch the manager and :meth:`ThemeManager.install` it."""
    manager = theme()
    manager.install(app)
    return manager


# ---------------------------------------------------------------------------
# Corner control bar
# ---------------------------------------------------------------------------

class ThemeCornerBar(QtWidgets.QWidget):
    """``Zoom: [-] [100%] [+] | [Dark Mode]`` strip, laid out by its host.

    Before feature 036 this bar positioned itself: it was parented to the wizard
    but not laid out, ``move()``d itself to the window's top-right in a
    ``reposition()`` method and ``raise_()``d itself above the page.  That is
    what let it sit on top of a wrapped step description, and it is exactly the
    overlap FR-004 exists to forbid -- so the positioning is gone.  The bar is
    now an ordinary laid-out child: the wizard keeps one instance and moves it
    into the current page's header controls slot (``page_header.PageHeader``),
    which reserves a cell for it, so nothing can ever be drawn underneath it.

    The bar therefore reports an honest size hint (its own layout's) and asks its
    host to re-lay-out whenever a zoom step changes the button widths.  It still
    paints its ``#gtThemeBar`` panel, not to cover text any more -- nothing runs
    under it now -- but so the strip reads as one group of view controls rather
    than four loose buttons in the header row.

    The bar's own font is capped at 1.3x: the controls must stay reachable at
    the largest supported text scale instead of growing until they crowd the
    description out of its share of the header.
    """

    _BAR_FONT_CAP = 1.3

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("gtThemeBar")
        # A plain QWidget ignores a stylesheet background unless it is told to
        # paint a styled one; without this the bar's panel and border simply do
        # not render and the buttons read as four loose header widgets.
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        # Fixed both ways: the strip is exactly as big as its contents ask for.
        # The header's controls cell is Fixed-width too, so every pixel the bar
        # does not claim is width the wrapping description gets instead.
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed,
                           QtWidgets.QSizePolicy.Policy.Fixed)
        self._theme = theme()

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        # FR-002: the zoom control is preceded by a visible "Zoom:" label.  The
        # text is the contract's, verbatim -- colon included.
        self._zoom_label = QtWidgets.QLabel("Zoom:", self)
        self._zoom_label.setObjectName("gtThemeBarZoomLabel")

        # FR-003: "-" and "+" only.  The old "A-"/"A+" glyphs read as a font
        # picker rather than a zoom control, and the letter A means nothing to a
        # reader of a language that does not use it.  What the buttons act on is
        # now said once, by the label beside them.
        self._btn_smaller = self._make_button(
            "-", "Smaller interface text (-10%)  [Ctrl+-]", self._theme.decrease_font)
        self._btn_smaller.setShortcut(QtGui.QKeySequence.StandardKey.ZoomOut)

        self._btn_percent = self._make_button(
            "100%", "Interface text size -- click to return to 100%  [Ctrl+0]",
            self._theme.reset_font)

        self._btn_bigger = self._make_button(
            "+", "Larger interface text (+10%)  [Ctrl++]", self._theme.increase_font)
        self._btn_bigger.setShortcut(QtGui.QKeySequence.StandardKey.ZoomIn)

        # A screen reader announcing "minus" / "plus" says nothing about what is
        # being changed, and unlike a tooltip an accessible name is not tied to
        # hovering a mouse.
        self._btn_smaller.setAccessibleName("Decrease interface text size")
        self._btn_bigger.setAccessibleName("Increase interface text size")

        separator = QtWidgets.QFrame(self)
        separator.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        separator.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)

        self._btn_mode = self._make_button(
            "Dark Mode", "Switch between light and dark interface",
            self._theme.toggle_mode)

        for widget in (self._zoom_label, self._btn_smaller, self._btn_percent,
                       self._btn_bigger, separator, self._btn_mode):
            layout.addWidget(widget)

        # Ctrl+0 has no StandardKey, so it needs an explicit QShortcut.  Parented
        # to the bar, not to the host: the bar is moved from one page's header
        # slot to the next, and a shortcut owned by whatever widget happened to
        # be the parent at construction time would either outlive the bar or be
        # left behind by the first page change.  One shortcut per bar instance,
        # created here and only here -- there is exactly one bar per wizard, so
        # `Ctrl+0` resolves unambiguously.  The default WindowShortcut context is
        # what makes it fire from any focused pane in the wizard rather than only
        # when the percentage button has focus; the bar is a visible child of the
        # current page's header whenever the wizard is showing a page, which is
        # the condition Qt requires for a widget-parented shortcut to be live.
        self._reset_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+0"), self)
        self._reset_shortcut.activated.connect(self._theme.reset_font)

        self._theme.changed.connect(self._sync)
        self._sync()

    # ------------------------------------------------------------------
    def _make_button(self, text: str, tip: str, slot) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton(self)
        button.setText(text)
        button.setToolTip(tip)
        button.setAutoRaise(True)
        button.setFocusPolicy(QtCore.Qt.FocusPolicy.TabFocus)
        button.clicked.connect(slot)
        return button

    def _sync(self) -> None:
        """Refresh labels/enablement and re-fit after a theme or size change."""
        self._btn_percent.setText(f"{self._theme.font_percent()}%")
        self._btn_smaller.setEnabled(self._theme.can_decrease())
        self._btn_bigger.setEnabled(self._theme.can_increase())
        self._btn_mode.setText(
            "Light Mode" if self._theme.mode == DARK else "Dark Mode")

        capped = min(self._theme.font_scale, self._BAR_FONT_CAP)
        font = QtGui.QFont(self.font())
        font.setPointSizeF(round(self._theme.base_point_size * capped, 2))
        metrics = QtGui.QFontMetrics(font)
        # The label follows the same capped font as the buttons; left on the
        # application font it would keep growing past the cap and be the one part
        # of the strip that crowds the description at a high text scale.
        self._zoom_label.setFont(font)
        # Size each button to its own text: Qt's QToolButton hint is ~60px wide
        # regardless of content (it reserves icon space it will never use), which
        # made the strip ~390px and left the description almost no width.
        hpad = max(14, int(round(18 * capped)))
        vpad = max(6, int(round(9 * capped)))
        height = metrics.height() + vpad
        for child in (self._btn_smaller, self._btn_percent,
                      self._btn_bigger, self._btn_mode):
            child.setFont(font)
            width = metrics.horizontalAdvance(child.text()) + hpad
            if child is self._btn_smaller or child is self._btn_bigger:
                # "-" and "+" advance only a few pixels, so text width plus
                # padding alone would make these two a sliver of a click target.
                # Square them off against the row height instead.
                width = max(width, height)
            child.setFixedSize(width, height)

        # The bar no longer moves itself; it tells whoever lays it out that its
        # hint changed.  Without this a zoom step resizes the buttons but the
        # host's layout keeps the old cell width, and the strip is clipped.
        self.updateGeometry()
