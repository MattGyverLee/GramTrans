"""Tests for the merge-preview theme seam (light/dark + text-size feature).

``gramtrans.Lib.merge_preview`` is Qt-free (feature 012 SC-007) but must still
follow the interface theme, so it exposes a *push* seam instead of reaching for
a palette:

- ``DIFF_PALETTE``  -- the live added / removed / note / divider colours.
- ``DIFF_SCALE``    -- multiplier for absolute ``pt`` sizes and ``px`` indents.
- ``set_diff_theme(colors=..., scale=...)`` -- what ``Lib/ui/theme.py`` calls.

These tests exercise that seam with no PyQt import at all: the whole point of
the seam is that the renderer never needs Qt to be themed.

Both module attributes are module-level MUTABLE state, so the autouse
``restore_diff_theme`` fixture snapshots and restores them around every test.
Without it a leaked ``DIFF_SCALE`` would silently break the fixed
``margin-left:32px`` / ``12.0pt`` assertions in
``tests/unit/test_merge_preview_html.py`` depending on collection order.
"""

from __future__ import annotations

import pytest

from gramtrans.Lib import merge_preview as mp
from gramtrans.Lib.merge_preview import (
    DiffSegment,
    FieldDiff,
    MergePreview,
    SegmentKind,
    set_diff_theme,
    to_html,
)
from gramtrans.Lib.ws_fonts import WsFont, WsFontRegistry, WsRole

#: The shipped defaults, captured at import (collection) time -- i.e. before any
#: test has had a chance to push a scheme in.  Used by the isolation guard below
#: so it stays correct if the shipped palette is ever re-tuned.
_SHIPPED_PALETTE = dict(mp.DIFF_PALETTE)
_SHIPPED_SCALE = mp.DIFF_SCALE

# ============================================================================
# Fixtures / helpers
# ============================================================================


@pytest.fixture(autouse=True)
def restore_diff_theme():
    """Snapshot + restore the module-level diff theme around every test.

    ``DIFF_PALETTE`` is mutated in place (other modules hold a reference to the
    same dict), so it is restored by clear()+update() rather than rebinding.
    """
    palette_snapshot = dict(mp.DIFF_PALETTE)
    scale_snapshot = mp.DIFF_SCALE
    try:
        yield
    finally:
        mp.DIFF_PALETTE.clear()
        mp.DIFF_PALETTE.update(palette_snapshot)
        mp.DIFF_SCALE = scale_snapshot


def _make_registry(vern_rtl=False, anal_rtl=False, ipa_rtl=False) -> WsFontRegistry:
    """Same fixture shape as tests/unit/test_merge_preview_html.py::_make_registry."""
    return WsFontRegistry(
        {
            WsRole.VERNACULAR: WsFont(
                ws_id="koh", font_name="Doulos SIL", size_pt=12.0, rtl=vern_rtl
            ),
            WsRole.ANALYSIS: WsFont(ws_id="en", font_name="Arial", size_pt=10.0, rtl=anal_rtl),
            WsRole.IPA: WsFont(
                ws_id="koh-fonipa", font_name="Charis SIL", size_pt=11.0, rtl=ipa_rtl
            ),
        }
    )


def _make_preview(field_name: str, segments: list, indent: int = 0) -> MergePreview:
    return MergePreview(
        status="similar",
        fields=(FieldDiff(field_name=field_name, segments=tuple(segments), indent=indent),),
        notes=(),
    )


def _render_kind(kind: SegmentKind) -> str:
    seg = DiffSegment(text="value", kind=kind, ws_role=None)
    return to_html(_make_preview("F", [seg]), WsFontRegistry.empty())


def _render_group() -> str:
    """Render a grouped field so the group divider (border-top) is emitted."""
    seg = DiffSegment(text="value", kind=SegmentKind.UNCHANGED, ws_role=None)
    fd = FieldDiff(
        field_name="sense\x1ftok\x1fGloss",
        segments=(seg,),
        indent=1,
        display_name="Sense 1 > Gloss",
        sort_key=(1, 0),
        group="Sense 1",
    )
    return to_html(MergePreview(status="", fields=(fd,), notes=()), WsFontRegistry.empty())


# A deliberately non-default scheme; nothing here overlaps the shipped values.
_TEST_COLORS = {
    "added": "#5fd48a",
    "removed": "#ff8a8a",
    "note": "#aab2bb",
    "divider": "#3c424a",
}


# ============================================================================
# Colour push
# ============================================================================


class TestSetDiffThemeColors:
    def test_added_colour_follows_palette(self):
        before = _render_kind(SegmentKind.ADDED)
        assert f"color:{mp.DIFF_PALETTE['added']}" in before

        set_diff_theme(colors=_TEST_COLORS)
        after = _render_kind(SegmentKind.ADDED)
        assert f"color:{_TEST_COLORS['added']}" in after
        assert after != before

    def test_removed_colour_follows_palette_and_keeps_strike(self):
        set_diff_theme(colors=_TEST_COLORS)
        html_out = _render_kind(SegmentKind.REMOVED)
        assert f"color:{_TEST_COLORS['removed']}" in html_out
        assert "line-through" in html_out

    def test_note_colour_follows_palette_and_keeps_italic(self):
        set_diff_theme(colors=_TEST_COLORS)
        html_out = _render_kind(SegmentKind.NOTE)
        assert f"color:{_TEST_COLORS['note']}" in html_out
        assert "italic" in html_out

    def test_divider_colour_follows_palette(self):
        before = _render_group()
        assert f"border-top:1px solid {mp.DIFF_PALETTE['divider']}" in before

        set_diff_theme(colors=_TEST_COLORS)
        after = _render_group()
        assert f"border-top:1px solid {_TEST_COLORS['divider']}" in after

    def test_every_palette_key_is_settable(self):
        """No shipped key is silently ignored by the push seam."""
        keys = sorted(mp.DIFF_PALETTE)
        assert keys == ["added", "divider", "note", "removed"]
        set_diff_theme(colors=_TEST_COLORS)
        for key in keys:
            assert mp.DIFF_PALETTE[key] == _TEST_COLORS[key]

    def test_unknown_keys_ignored_and_do_not_raise(self):
        """A newer theme pushing extra tokens must not break an older renderer."""
        set_diff_theme(colors={"added": "#123456", "sparkle": "#abcdef", "": "#000000"})
        assert mp.DIFF_PALETTE["added"] == "#123456"
        assert "sparkle" not in mp.DIFF_PALETTE
        assert "" not in mp.DIFF_PALETTE

    def test_partial_colours_leave_others_untouched(self):
        original_note = mp.DIFF_PALETTE["note"]
        set_diff_theme(colors={"added": "#123456"})
        assert mp.DIFF_PALETTE["added"] == "#123456"
        assert mp.DIFF_PALETTE["note"] == original_note

    def test_no_arguments_is_a_no_op(self):
        snapshot = dict(mp.DIFF_PALETTE)
        set_diff_theme()
        colors = dict(mp.DIFF_PALETTE)
        assert colors == snapshot
        assert mp.DIFF_SCALE == 1.0


# ============================================================================
# Render scale
# ============================================================================


class TestSetDiffThemeScale:
    def test_default_scale_is_one(self):
        assert mp.DIFF_SCALE == 1.0

    def test_scale_doubles_indent(self):
        seg = DiffSegment(text="indented", kind=SegmentKind.UNCHANGED, ws_role=None)
        preview = _make_preview("Nested", [seg], indent=2)

        assert "margin-left:32px" in to_html(preview, WsFontRegistry.empty())

        set_diff_theme(scale=2.0)
        assert "margin-left:64px" in to_html(preview, WsFontRegistry.empty())

    def test_scale_doubles_ws_font_size(self):
        registry = _make_registry()
        seg = DiffSegment(text="form", kind=SegmentKind.UNCHANGED, ws_role=WsRole.VERNACULAR)
        preview = _make_preview("Form", [seg])

        assert "12.0pt" in to_html(preview, registry)

        set_diff_theme(scale=2.0)
        assert "24.0pt" in to_html(preview, registry)

    def test_scale_does_not_disturb_colours(self):
        snapshot = dict(mp.DIFF_PALETTE)
        set_diff_theme(scale=1.5)
        colors = dict(mp.DIFF_PALETTE)
        assert colors == snapshot

    def test_scale_clamped_high(self):
        set_diff_theme(scale=99)
        assert mp.DIFF_SCALE == 4.0

    def test_scale_clamped_low(self):
        set_diff_theme(scale=0.01)
        assert mp.DIFF_SCALE == 0.5

    def test_scale_within_range_kept_exactly(self):
        set_diff_theme(scale=1.331)
        scale = mp.DIFF_SCALE
        assert scale == pytest.approx(1.331)

    def test_clamped_scale_still_scales_indent(self):
        """Clamping happens once, in the setter -- the renderer uses the clamp."""
        seg = DiffSegment(text="indented", kind=SegmentKind.UNCHANGED, ws_role=None)
        preview = _make_preview("Nested", [seg], indent=1)
        set_diff_theme(scale=99)
        assert "margin-left:64px" in to_html(preview, WsFontRegistry.empty())  # 16 * 4.0


# ============================================================================
# Isolation guard -- the fixture itself
# ============================================================================


class TestThemeStateIsolation:
    """These two tests would fail each other if the autouse fixture regressed."""

    def test_a_mutates_everything(self):
        set_diff_theme(colors=_TEST_COLORS, scale=3.0)
        assert mp.DIFF_SCALE == 3.0
        assert mp.DIFF_PALETTE["added"] == _TEST_COLORS["added"]

    def test_b_sees_shipped_defaults(self):
        assert mp.DIFF_SCALE == _SHIPPED_SCALE
        assert mp.DIFF_PALETTE == _SHIPPED_PALETTE
