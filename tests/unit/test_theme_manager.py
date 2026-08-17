"""Tests for the interface theme service (``gramtrans.Lib.ui.theme``).

Covers the parts of the light/dark + text-size feature that can be asserted
without repainting the application:

- ``ThemeManager`` state machine: font scale, step clamping, mode toggling and
  the ``changed`` signal's fire/no-fire contract.
- Palette completeness: LIGHT and DARK must define the *same* token set with no
  empty values -- a token present in one mode and missing in the other is the
  exact class of bug this module exists to prevent.
- Palette validity: every colour token parses as a real ``QColor``.
- ``build_stylesheet``: scales its pixel metrics, and never invents a colour
  that is not one of the palette's own token values.
- Contrast: a WCAG relative-luminance guard on the pairs the request hinges on
  (field linguists reading small UI text), computed locally so the thresholds
  live in the test rather than in a comment.

NOTE -- ``ThemeManager.install()`` is DELIBERATELY never called here.  It adopts
the process-wide ``QApplication`` and then re-styles it (style, palette,
stylesheet, font) for the remainder of the pytest session, which would
contaminate every other offscreen Qt test in the suite.  Instead:

- Most tests drive a bare, *uninstalled* ``ThemeManager()``.  With
  ``_installed`` False, ``_apply`` returns immediately, so the state machine is
  exercised with no Qt side effects at all.
- The ``changed``-signal and diff-push tests need ``_apply`` (that is the only
  place the signal is emitted), so the ``applied_manager`` fixture points
  ``QApplication.instance()`` at a ``_FakeApplication`` first.  The real
  ``_apply`` then runs end to end with every mutation landing on the fake, and
  an autouse fixture restores the ``merge_preview`` diff theme it pushes.

Actually installing the theme onto a live application is verified in the GUI
harness, not here.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import re
from dataclasses import fields as dc_fields

import pytest

pytest.importorskip("PyQt6")
from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402

from gramtrans.Lib import merge_preview as _merge_preview  # noqa: E402
from gramtrans.Lib.ui import theme as theme_mod  # noqa: E402
from gramtrans.Lib.ui.theme import (  # noqa: E402
    DARK,
    DARK_PALETTE,
    FONT_STEP_INCREMENT,
    LIGHT,
    LIGHT_PALETTE,
    MAX_FONT_STEP,
    MIN_FONT_STEP,
    PALETTES,
    Palette,
    ThemeManager,
    build_stylesheet,
)


@pytest.fixture(scope="session")
def qapp():
    """The one QApplication for the process (a second one aborts)."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture(autouse=True)
def restore_diff_theme():
    """Restore ``merge_preview``'s pushed diff theme after every test.

    ``ThemeManager._apply`` pushes colours + render scale into the Qt-free
    renderer's module-level ``DIFF_PALETTE`` / ``DIFF_SCALE``.  Left in place
    that would leak into ``tests/unit/test_merge_preview_html.py``, whose
    ``margin-left:32px`` / ``12.0pt`` assertions assume scale 1.0.
    """
    palette_snapshot = dict(_merge_preview.DIFF_PALETTE)
    scale_snapshot = _merge_preview.DIFF_SCALE
    try:
        yield
    finally:
        _merge_preview.DIFF_PALETTE.clear()
        _merge_preview.DIFF_PALETTE.update(palette_snapshot)
        _merge_preview.DIFF_SCALE = scale_snapshot


@pytest.fixture
def manager(qapp, tmp_path):
    """A bare, *uninstalled* manager -- mutating it touches no shared Qt state.

    ``QSettings`` is pointed at a throwaway .ini so ``set_mode`` /
    ``set_font_step`` do not write the real user's ``SIL/GramTrans`` registry
    keys while the state machine is being exercised.
    """
    mgr = ThemeManager()
    mgr._settings = QtCore.QSettings(
        str(tmp_path / "gramtrans-theme.ini"), QtCore.QSettings.Format.IniFormat
    )
    return mgr


class _SignalCounter:
    """Counts emissions of a parameterless pyqtSignal."""

    def __init__(self, signal):
        self.count = 0
        signal.connect(self._on_fire)

    def _on_fire(self) -> None:
        self.count += 1


class _FakeApplication:
    """Stand-in ``QApplication`` that absorbs everything ``_apply`` mutates.

    ``_apply`` is the only place ``changed`` is emitted, so the signal contract
    cannot be tested without running it -- but running it against the real
    ``QApplication`` would re-style every other offscreen Qt test in the
    process.  Redirecting ``QApplication.instance()`` at this fake lets the
    *real* ``_apply`` run end to end with all of its mutations landing here.

    It deliberately has no ``styleHints()``: ``_sync_color_scheme`` guards on
    ``AttributeError``, and that guard is worth exercising too.
    """

    def __init__(self, base_font: QtGui.QFont) -> None:
        self._font = QtGui.QFont(base_font)
        self.styles: list = []
        self.palettes: list = []
        self.stylesheets: list = []
        self.fonts: list = []

    def font(self) -> QtGui.QFont:
        return self._font

    def setStyle(self, style) -> None:  # noqa: N802 -- Qt naming
        self.styles.append(style)

    def setPalette(self, palette) -> None:  # noqa: N802
        self.palettes.append(palette)

    def setStyleSheet(self, sheet) -> None:  # noqa: N802
        self.stylesheets.append(sheet)

    def setFont(self, font) -> None:  # noqa: N802
        self._font = font
        self.fonts.append(font)

    def topLevelWidgets(self) -> list:  # noqa: N802
        return []


class _FakeApplicationClass:
    """Only the ``instance()`` classmethod ``_apply`` actually calls."""

    current: _FakeApplication | None = None

    @classmethod
    def instance(cls):
        return cls.current


class _QtWidgetsProxy:
    """``theme.QtWidgets`` with ``QApplication`` swapped for the fake.

    Everything else (``QStyleFactory`` for ``_ScaledProxyStyle``, the widget
    classes ``rescale_item_fonts`` looks for) delegates to the real module.
    """

    def __init__(self, app_class) -> None:
        self.QApplication = app_class

    def __getattr__(self, name):
        return getattr(QtWidgets, name)


@pytest.fixture
def applied_manager(manager, monkeypatch, qapp):
    """``(manager, fake_app)`` with ``_apply`` live but aimed at the fake app.

    ``install()`` is still never called -- it would adopt the real
    ``QApplication``.  ``_installed`` is set directly so the mutators reach
    ``_apply``.
    """
    fake = _FakeApplication(qapp.font())
    monkeypatch.setattr(_FakeApplicationClass, "current", fake)
    monkeypatch.setattr(theme_mod, "QtWidgets", _QtWidgetsProxy(_FakeApplicationClass))
    manager._installed = True
    return manager, fake


# ============================================================================
# Font scale / step
# ============================================================================


class TestFontScale:
    def test_default_step_is_zero_and_scale_is_one(self, manager):
        assert manager.font_step == 0
        assert manager.font_scale == pytest.approx(1.0)
        assert manager.font_percent() == 100

    @pytest.mark.parametrize("step", [-3, -1, 0, 1, 3, 10, 15])
    def test_scale_is_linear_in_the_step(self, manager, step):
        manager.set_font_step(step)
        assert manager.font_step == step
        assert manager.font_scale == pytest.approx(1.0 + FONT_STEP_INCREMENT * step)

    @pytest.mark.parametrize("step,percent", [
        (-3, 70), (-2, 80), (-1, 90), (0, 100),
        (1, 110), (2, 120), (3, 130), (4, 140), (5, 150), (15, 250),
    ])
    def test_percent_walks_in_round_tens(self, manager, step, percent):
        """No compounding: the readout is 100/110/120/130, not 100/110/121/133."""
        manager.set_font_step(step)
        assert manager.font_percent() == percent

    def test_increase_then_decrease_returns_to_default(self, manager):
        manager.increase_font()
        assert manager.font_step == 1
        assert manager.font_scale == pytest.approx(1.0 + FONT_STEP_INCREMENT)

        manager.decrease_font()
        assert manager.font_step == 0
        assert manager.font_scale == pytest.approx(1.0)
        assert manager.font_percent() == 100

    def test_reset_font_returns_to_default(self, manager):
        manager.set_font_step(5)
        manager.reset_font()
        assert manager.font_step == 0
        assert manager.font_percent() == 100

    def test_one_step_up_is_ten_percent(self, manager):
        manager.increase_font()
        assert manager.font_percent() == 110


class TestFontStepClamp:
    def test_clamps_at_maximum(self, manager):
        manager.set_font_step(MAX_FONT_STEP + 50)
        assert manager.font_step == MAX_FONT_STEP

    def test_clamps_at_minimum(self, manager):
        manager.set_font_step(MIN_FONT_STEP - 50)
        assert manager.font_step == MIN_FONT_STEP

    def test_increase_font_cannot_pass_maximum(self, manager):
        manager.set_font_step(MAX_FONT_STEP)
        manager.increase_font()
        assert manager.font_step == MAX_FONT_STEP

    def test_decrease_font_cannot_pass_minimum(self, manager):
        manager.set_font_step(MIN_FONT_STEP)
        manager.decrease_font()
        assert manager.font_step == MIN_FONT_STEP

    def test_can_increase_reports_the_upper_boundary(self, manager):
        assert manager.can_increase() is True
        manager.set_font_step(MAX_FONT_STEP - 1)
        assert manager.can_increase() is True
        manager.set_font_step(MAX_FONT_STEP)
        assert manager.can_increase() is False

    def test_can_decrease_reports_the_lower_boundary(self, manager):
        assert manager.can_decrease() is True
        manager.set_font_step(MIN_FONT_STEP + 1)
        assert manager.can_decrease() is True
        manager.set_font_step(MIN_FONT_STEP)
        assert manager.can_decrease() is False


# ============================================================================
# Mode
# ============================================================================


class TestMode:
    def test_toggle_flips_light_to_dark_and_back(self, manager):
        manager.set_mode(LIGHT)
        assert manager.mode == LIGHT

        manager.toggle_mode()
        assert manager.mode == DARK

        manager.toggle_mode()
        assert manager.mode == LIGHT

    def test_palette_follows_the_mode(self, manager):
        manager.set_mode(LIGHT)
        assert manager.palette is LIGHT_PALETTE
        assert manager.palette.name == LIGHT

        manager.toggle_mode()
        assert manager.palette is DARK_PALETTE
        assert manager.palette.name == DARK

    def test_unknown_mode_falls_back_to_light(self, manager):
        manager.set_mode(DARK)
        manager.set_mode("chartreuse")
        assert manager.mode == LIGHT

    def test_palettes_registry_matches_the_constants(self):
        assert PALETTES == {LIGHT: LIGHT_PALETTE, DARK: DARK_PALETTE}


# ============================================================================
# changed signal
# ============================================================================


class TestChangedSignal:
    def test_fires_on_a_real_mode_change(self, applied_manager):
        manager, _fake = applied_manager
        counter = _SignalCounter(manager.changed)
        manager.set_mode(DARK)
        assert counter.count == 1

    def test_does_not_fire_when_mode_is_unchanged(self, applied_manager):
        manager, _fake = applied_manager
        manager.set_mode(DARK)
        counter = _SignalCounter(manager.changed)
        manager.set_mode(DARK)
        assert counter.count == 0

    def test_fires_on_a_real_font_step_change(self, applied_manager):
        manager, _fake = applied_manager
        counter = _SignalCounter(manager.changed)
        manager.increase_font()
        assert counter.count == 1

    def test_does_not_fire_when_font_step_is_unchanged(self, applied_manager):
        manager, _fake = applied_manager
        manager.set_font_step(3)
        counter = _SignalCounter(manager.changed)
        manager.set_font_step(3)
        assert counter.count == 0

    def test_does_not_fire_when_clamped_to_the_current_step(self, applied_manager):
        manager, _fake = applied_manager
        manager.set_font_step(MAX_FONT_STEP)
        counter = _SignalCounter(manager.changed)
        manager.increase_font()                     # clamps back to MAX -> no change
        manager.set_font_step(MAX_FONT_STEP + 7)    # ditto
        assert counter.count == 0

    def test_toggle_mode_fires_once_per_toggle(self, applied_manager):
        manager, _fake = applied_manager
        counter = _SignalCounter(manager.changed)
        manager.toggle_mode()
        manager.toggle_mode()
        assert counter.count == 2

    def test_no_op_mutators_touch_nothing_on_the_application(self, applied_manager):
        """A no-op must not re-style the app either, not just not signal."""
        manager, fake = applied_manager
        manager.set_mode(DARK)
        manager.set_font_step(2)
        before = (len(fake.styles), len(fake.palettes),
                  len(fake.stylesheets), len(fake.fonts))
        manager.set_mode(DARK)
        manager.set_font_step(2)
        after = (len(fake.styles), len(fake.palettes),
                 len(fake.stylesheets), len(fake.fonts))
        assert before == after


class TestDiffThemePush:
    """``_apply`` is the wire between the Qt palette and the Qt-free renderer."""

    def test_mode_change_pushes_its_diff_colours_into_merge_preview(self, applied_manager):
        manager, _fake = applied_manager

        manager.set_mode(DARK)
        pushed = dict(_merge_preview.DIFF_PALETTE)
        assert pushed == {
            "added": DARK_PALETTE.diff_added,
            "removed": DARK_PALETTE.diff_removed,
            "note": DARK_PALETTE.diff_note,
            "divider": DARK_PALETTE.diff_divider,
        }

        manager.set_mode(LIGHT)
        pushed = dict(_merge_preview.DIFF_PALETTE)
        assert pushed == {
            "added": LIGHT_PALETTE.diff_added,
            "removed": LIGHT_PALETTE.diff_removed,
            "note": LIGHT_PALETTE.diff_note,
            "divider": LIGHT_PALETTE.diff_divider,
        }

    def test_font_step_change_pushes_the_render_scale(self, applied_manager):
        manager, _fake = applied_manager
        manager.set_font_step(3)
        pushed_scale = _merge_preview.DIFF_SCALE
        assert pushed_scale == pytest.approx(manager.font_scale)


# ============================================================================
# Palette token completeness / validity
# ============================================================================

_PALETTE_FIELDS = tuple(f.name for f in dc_fields(Palette))


class TestPaletteTokens:
    def test_both_modes_define_the_same_field_set(self):
        light_names = {f.name for f in dc_fields(LIGHT_PALETTE)}
        dark_names = {f.name for f in dc_fields(DARK_PALETTE)}
        assert light_names == dark_names == set(_PALETTE_FIELDS)

    @pytest.mark.parametrize("pal", [LIGHT_PALETTE, DARK_PALETTE], ids=[LIGHT, DARK])
    def test_every_token_is_non_empty(self, pal):
        missing = [name for name in _PALETTE_FIELDS if not str(getattr(pal, name)).strip()]
        assert missing == [], f"{pal.name} palette has empty token(s): {missing}"

    def test_no_mode_is_missing_a_token_the_other_has(self):
        """A token defined in one mode and blank in the other is the bug this
        module exists to prevent -- state it as its own assertion."""
        for name in _PALETTE_FIELDS:
            light_value = str(getattr(LIGHT_PALETTE, name)).strip()
            dark_value = str(getattr(DARK_PALETTE, name)).strip()
            assert light_value, f"token {name!r} is blank in the light palette"
            assert dark_value, f"token {name!r} is blank in the dark palette"

    @pytest.mark.parametrize("pal", [LIGHT_PALETTE, DARK_PALETTE], ids=[LIGHT, DARK])
    def test_every_colour_token_parses_as_a_colour(self, qapp, pal):
        bad = []
        for name in _PALETTE_FIELDS:
            if name == "name":
                continue
            value = getattr(pal, name)
            if not QtGui.QColor(value).isValid():
                bad.append((name, value))
        assert bad == [], f"{pal.name} palette has unparseable colour(s): {bad}"

    @pytest.mark.parametrize("pal", [LIGHT_PALETTE, DARK_PALETTE], ids=[LIGHT, DARK])
    def test_diff_tokens_exist_for_the_merge_preview_push(self, pal):
        """theme._apply pushes exactly these four into merge_preview."""
        for name in ("diff_added", "diff_removed", "diff_note", "diff_divider"):
            assert getattr(pal, name)


# ============================================================================
# build_stylesheet
# ============================================================================

_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")
_PX_RE = re.compile(r"(\d+)px")


def _palette_colour_values(pal: Palette) -> set:
    return {
        str(getattr(pal, f.name)).lower()
        for f in dc_fields(pal)
        if f.name != "name"
    }


class TestBuildStylesheet:
    @pytest.mark.parametrize("pal", [LIGHT_PALETTE, DARK_PALETTE], ids=[LIGHT, DARK])
    def test_scaling_up_grows_the_pixel_metrics(self, pal):
        small = [int(v) for v in _PX_RE.findall(build_stylesheet(pal, 1.0))]
        large = [int(v) for v in _PX_RE.findall(build_stylesheet(pal, 2.0))]
        assert small, "stylesheet emitted no px metrics at all"
        assert len(small) == len(large)
        assert sum(large) > sum(small)
        assert all(b >= a for a, b in zip(small, large))

    @pytest.mark.parametrize("pal", [LIGHT_PALETTE, DARK_PALETTE], ids=[LIGHT, DARK])
    def test_never_invents_a_colour(self, pal):
        """Every ``#rrggbb`` in the QSS must be one of the palette's own values."""
        allowed = _palette_colour_values(pal)
        for scale in (1.0, 2.0):
            found = {h.lower() for h in _HEX_RE.findall(build_stylesheet(pal, scale))}
            invented = sorted(found - allowed)
            assert invented == [], (
                f"{pal.name} stylesheet at scale {scale} invents colour(s): {invented}"
            )

    @pytest.mark.parametrize("pal", [LIGHT_PALETTE, DARK_PALETTE], ids=[LIGHT, DARK])
    def test_uses_the_palette_it_was_given(self, pal):
        qss = build_stylesheet(pal, 1.0)
        assert pal.highlight.lower() in qss.lower()
        assert pal.border.lower() in qss.lower()


# ============================================================================
# Contrast guard (WCAG 2.x relative luminance)
# ============================================================================


def _srgb_channel(value: int) -> float:
    channel = value / 255.0
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_colour: str) -> float:
    """WCAG relative luminance of a ``#rrggbb`` colour."""
    raw = hex_colour.lstrip("#")
    r, g, b = (int(raw[i:i + 2], 16) for i in (0, 2, 4))
    return (
        0.2126 * _srgb_channel(r)
        + 0.7152 * _srgb_channel(g)
        + 0.0722 * _srgb_channel(b)
    )


def _contrast_ratio(fg: str, bg: str) -> float:
    """WCAG contrast ratio, order-independent."""
    lum_a = _relative_luminance(fg)
    lum_b = _relative_luminance(bg)
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


#: (foreground token, background token, minimum ratio).  7.0 = WCAG AAA body
#: text; 4.5 = AA.  These are the pairs the light/dark request hinges on --
#: older readers on small field-laptop screens.
_CONTRAST_PAIRS = (
    ("text", "base", 7.0),
    ("window_text", "window", 7.0),
    ("muted_text", "base", 4.5),
    ("highlighted_text", "highlight", 4.5),
    ("warning_text", "warning_bg", 4.5),
    ("diff_added", "base", 4.5),
    ("diff_removed", "base", 4.5),
    ("diff_note", "base", 4.5),
)


class TestContrast:
    def test_helper_matches_known_reference_ratios(self):
        """Sanity-check the local helper before trusting its verdicts:
        black on white is 21:1 and any colour on itself is 1:1."""
        assert _contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)
        assert _contrast_ratio("#1b5fb0", "#1b5fb0") == pytest.approx(1.0, abs=1e-9)

    @pytest.mark.parametrize("pal", [LIGHT_PALETTE, DARK_PALETTE], ids=[LIGHT, DARK])
    @pytest.mark.parametrize("fg,bg,minimum", _CONTRAST_PAIRS,
                             ids=[f"{a}_on_{b}" for a, b, _ in _CONTRAST_PAIRS])
    def test_pair_meets_its_threshold(self, pal, fg, bg, minimum):
        ratio = _contrast_ratio(getattr(pal, fg), getattr(pal, bg))
        assert ratio >= minimum, (
            f"{pal.name}: {fg} ({getattr(pal, fg)}) on {bg} ({getattr(pal, bg)}) "
            f"measured {ratio:.2f}:1, below the required {minimum}:1"
        )
