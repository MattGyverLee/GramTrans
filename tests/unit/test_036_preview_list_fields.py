"""Feature 036 US4 -- preview list-field legibility (FR-033..FR-037, FR-045).

Offline, Qt-free, LCM-free: ``diff_props``/``to_html`` are pure, and the slot
enricher is duck-typed (``_lcm_cast`` returns the object unchanged when
SIL.LCModel is absent), so plain fakes exercise the real code paths.

Why the byte-identity class comes first: ``Lib/merge_preview.py`` sits on the
transfer path.  FR-045 forbids this feature from changing what GramTrans
enumerates, plans or writes, so every change here is additive and default-off --
``FieldDiff.multiline`` defaults ``False`` and every SCALAR field must render
exactly as it does today.  The golden strings below are the pre-change output,
pinned character-for-character.

Covers:
- T027 / FR-045  ``multiline`` defaults False; scalar rendering unchanged
- T027 / FR-033  one entry per line; no programmatic quoting added
- T027 / FR-034  apostrophes and quote marks inside a form preserved exactly
- T027 / FR-035  affix label separates form from gloss by whitespace only
- T027 / FR-036  an empty list-valued field renders an explicit ``(none)``
- T027 / FR-037  a capped list states the cap AND the true total
"""

from __future__ import annotations

import pytest

from gramtrans.Lib import merge_preview as mp
from gramtrans.Lib.merge_preview import (
    LINK_ONLY,
    MERGE_KEEP,
    NEW,
    OVERWRITE,
    DiffSegment,
    FieldDiff,
    MergePreview,
    SegmentKind,
    _affix_msa_label,
    _enrich_slot,
    diff_props,
    to_html,
)
from gramtrans.Lib.ws_fonts import WsFont, WsFontRegistry, WsRole

# ===========================================================================
# Fixtures / helpers
# ===========================================================================

# Pinned so the golden strings below cannot be perturbed by another test that
# pushed a dark scheme through ``set_diff_theme`` (the palette is a module
# global, mutable on purpose).  These are the light-scheme defaults.
_ADDED = "#0a6b22"
_REMOVED = "#a8000f"
_NOTE = "#4e545b"
_DIVIDER = "#b4bac2"


@pytest.fixture(autouse=True)
def _pinned_theme():
    """Pin palette + scale for every test here, then restore the prior state."""
    saved = dict(mp.DIFF_PALETTE)
    saved_scale = mp.DIFF_SCALE
    mp.set_diff_theme(
        {"added": _ADDED, "removed": _REMOVED, "note": _NOTE, "divider": _DIVIDER},
        scale=1.0,
    )
    yield
    mp.DIFF_PALETTE.clear()
    mp.DIFF_PALETTE.update(saved)
    mp.set_diff_theme(scale=saved_scale)


def _registry() -> WsFontRegistry:
    return WsFontRegistry(
        {
            WsRole.VERNACULAR: WsFont(
                ws_id="koh", font_name="Doulos SIL", size_pt=12.0, rtl=False
            ),
            WsRole.ANALYSIS: WsFont(ws_id="en", font_name="Arial", size_pt=10.0, rtl=False),
        }
    )


_ROLES = {"en": WsRole.ANALYSIS, "koh": WsRole.VERNACULAR}


def _roles_of(wid):
    return _ROLES.get(wid)


def _arrow() -> str:
    # The replacement arrow is U+2192; spelled as an escape so this source file
    # stays pure ASCII.
    return f"<span style='color:{_NOTE};'> \u2192 </span>"


def _field_div(label: str, body: str, indent_px: int = 0) -> str:
    return (
        f"<div style='margin-left:{indent_px}px;margin-bottom:4px;'>"
        f"<b>{label}</b>: {body}</div>"
    )


def _wrap(*field_divs: str) -> str:
    return "<div class='merge-preview'>" + "".join(field_divs) + "</div>"


def _texts(preview: MergePreview, field_name: str) -> list[str]:
    """Segment texts for one field, in order."""
    for fd in preview.fields:
        if fd.field_name == field_name:
            return [s.text for s in fd.segments]
    raise AssertionError(f"field {field_name!r} absent from {preview.fields!r}")


def _fd(preview: MergePreview, field_name: str) -> FieldDiff:
    for fd in preview.fields:
        if fd.field_name == field_name:
            return fd
    raise AssertionError(f"field {field_name!r} absent from {preview.fields!r}")


class FakeObj:
    """Duck-typed LCM stand-in; GUID read via the ``.guid`` fallback."""

    def __init__(self, guid=None, **attrs):
        if guid is not None:
            self.guid = guid
        for k, v in attrs.items():
            setattr(self, k, v)


def _affix_msa(form="-i", hn=2, gloss="PST"):
    """An affix MSA whose owning entry carries a lexeme form + gloss."""
    msa = FakeObj("msa-1")
    sense = FakeObj("s-1", MorphoSyntaxAnalysisRA=msa, Gloss={"en": gloss} if gloss else {})
    entry = FakeObj(
        "e-1",
        LexemeFormOA=FakeObj("lf-1", Form={"koh": form}),
        HomographNumber=hn,
        SensesOS=[sense],
    )
    msa.Owner = entry
    return msa


# ===========================================================================
# FR-045 -- additive and default-off: scalars byte-identical, multiline False
# ===========================================================================


class TestMultilineDefaultsFalse:
    def test_field_diff_multiline_defaults_false(self):
        """The new member must be defaulted, so every existing construction --
        in this module and in any consumer -- keeps today's behaviour."""
        fd = FieldDiff(field_name="Name", segments=())
        assert fd.multiline is False

    def test_field_diff_still_constructible_positionally(self):
        """``multiline`` is appended last, so positional construction of the
        pre-existing members is untouched."""
        fd = FieldDiff("Gloss", (DiffSegment("x", SegmentKind.ADDED, None),), 1, "Sense 1 > Gloss")
        assert fd.indent == 1
        assert fd.display_name == "Sense 1 > Gloss"
        assert fd.multiline is False

    @pytest.mark.parametrize(
        "value",
        [
            "n'ka",                       # plain str
            {"en": "ABBR", "koh": "abrv"},  # multistring
            3,                            # int
            True,                         # bool
            None,                         # absent
        ],
    )
    @pytest.mark.parametrize("mode", [NEW, LINK_ONLY, OVERWRITE, MERGE_KEEP])
    def test_scalar_field_is_never_multiline(self, value, mode):
        src = {"Prop": value}
        tgt = None if mode == NEW else {"Prop": value}
        pv = diff_props(src, tgt, mode, _roles_of)
        assert _fd(pv, "Prop").multiline is False

    def test_sequence_field_is_multiline(self):
        """The one shape that flips the flag (FR-033)."""
        for seq in (["a", "b"], ("a", "b"), {"a", "b"}, frozenset({"a", "b"})):
            pv = diff_props({"Members": seq}, None, NEW, _roles_of)
            assert _fd(pv, "Members").multiline is True, seq

    # -- golden HTML: the pre-change bytes, pinned -------------------------

    def test_scalar_str_replacement_html_byte_identical(self):
        pv = diff_props({"Name": "n'ka"}, {"Name": "nka"}, OVERWRITE, _roles_of)
        expected = _wrap(
            _field_div(
                "Name",
                f"<span style='color:{_REMOVED};text-decoration:line-through;'>nka</span>"
                + _arrow()
                + f"<span style='color:{_ADDED};'>n&#x27;ka</span>",
            )
        )
        assert to_html(pv, WsFontRegistry.empty()) == expected

    def test_scalar_int_new_html_byte_identical(self):
        pv = diff_props({"Rank": 3}, None, NEW, _roles_of)
        expected = _wrap(_field_div("Rank", f"<span style='color:{_ADDED};'>3</span>"))
        assert to_html(pv, WsFontRegistry.empty()) == expected

    def test_scalar_unchanged_str_html_byte_identical(self):
        """An unchanged plain string keeps its repr-free passthrough; an
        unchanged value reached through the *scalar* path keeps its repr."""
        pv = diff_props({"Same": "identical"}, {"Same": "identical"}, OVERWRITE, _roles_of)
        expected = _wrap(_field_div("Same", "<span>&#x27;identical&#x27;</span>"))
        assert to_html(pv, WsFontRegistry.empty()) == expected

    def test_multistring_replacement_html_byte_identical(self):
        pv = diff_props({"Abbrev": {"en": "ABBR"}}, {"Abbrev": {"en": "ABR"}},
                        OVERWRITE, _roles_of)
        arial = "font-family:'Arial';font-size:10.0pt;"
        expected = _wrap(
            _field_div(
                "Abbrev",
                f"<sub style='color:{_NOTE};font-size:0.75em;vertical-align:sub;'>en</sub> "
                f"<span style='color:{_REMOVED};text-decoration:line-through;{arial}'>ABR</span>"
                + _arrow()
                + f"<span style='color:{_ADDED};{arial}'>ABBR</span>",
            )
        )
        assert to_html(pv, _registry()) == expected

    def test_scalar_fields_render_on_one_line(self):
        """No scalar field may gain a line break: the only ``<div``s are the
        wrapper and one per field."""
        src = {"Name": "n'ka", "Rank": 3, "Optional": True}
        html_out = to_html(diff_props(src, None, NEW, _roles_of), WsFontRegistry.empty())
        assert html_out.count("<div") == 1 + len(src)
        assert "<br" not in html_out


# ===========================================================================
# FR-033 / FR-034 -- sequence members are str(), never repr()
# ===========================================================================


class TestSequenceMemberText:
    def test_added_sequence_uses_str(self):
        """NEW / source-only path (``_added_segments``)."""
        pv = diff_props({"Affixes": ["-i2  PST", "-a1  IMP"]}, None, NEW, _roles_of)
        assert _texts(pv, "Affixes") == ["-i2  PST", "-a1  IMP"]

    def test_unchanged_sequence_uses_str(self):
        """LINK_ONLY / target-only path (``_value_to_unchanged``)."""
        pv = diff_props({"Affixes": ["-i2", "-a1"]}, {"Affixes": ["-i2", "-a1"]},
                        LINK_ONLY, _roles_of)
        assert _texts(pv, "Affixes") == ["-i2", "-a1"]

    def test_sequence_union_uses_str(self):
        """OVERWRITE differing-sequence path (``_segments_for_sequence``)."""
        pv = diff_props({"Members": ["p", "t"]}, {"Members": ["p", "k"]}, OVERWRITE, _roles_of)
        assert _texts(pv, "Members") == ["p", "t", "k"]

    def test_merge_keep_sequence_uses_str(self):
        pv = diff_props({"Members": ["p", "t"]}, {"Members": ["p"]}, MERGE_KEEP, _roles_of)
        assert _texts(pv, "Members") == ["p", "t"]

    def test_no_quote_characters_added_around_entries(self):
        for mode, tgt in ((NEW, None), (OVERWRITE, {"Members": ["z"]})):
            pv = diff_props({"Members": ["ba", "ta"]}, tgt, mode, _roles_of)
            for text in _texts(pv, "Members"):
                assert not text.startswith(("'", '"')), (mode, text)
                assert not text.endswith(("'", '"')), (mode, text)

    # -- FR-034: quote marks INSIDE the data are linguistic, not quoting ----

    @pytest.mark.parametrize(
        "form",
        [
            "ba'a",        # glottal stop written with an apostrophe
            "k'ap",        # ejective
            "n'ka",        # orthographic apostrophe
            'ba"a',        # double quote used as a length/tone mark
            "ts'i'",       # both, and a trailing one
            "'ori",        # leading apostrophe
        ],
    )
    def test_quote_characters_inside_an_entry_preserved_exactly(self, form):
        """``repr()`` would wrap the entry in quotes and could escape the
        interior; ``str()`` must hand the form through untouched."""
        pv = diff_props({"Members": [form]}, None, NEW, _roles_of)
        assert _texts(pv, "Members") == [form]

    def test_quote_characters_survive_every_sequence_path(self):
        form = "ts'i\"n"
        cases = (
            (NEW, None),
            (LINK_ONLY, {"Members": [form]}),
            (OVERWRITE, {"Members": ["other"]}),
            (MERGE_KEEP, {"Members": ["other"]}),
        )
        for mode, tgt in cases:
            pv = diff_props({"Members": [form]}, tgt, mode, _roles_of)
            assert form in _texts(pv, "Members"), mode

    def test_non_sequence_object_still_repred(self):
        """FR-045: only *sequence members* change.  A bare object on a scalar
        field keeps its repr, exactly as today."""
        pv = diff_props({"Name": "n'ka"}, None, NEW, _roles_of)
        assert _texts(pv, "Name") == ['"n\'ka"']


# ===========================================================================
# FR-033 -- one entry per line
# ===========================================================================


class TestOneEntryPerLine:
    def test_multiline_field_emits_one_line_per_entry(self):
        pv = diff_props({"Affixes": ["-i2  PST", "-a1  IMP", "-u3  FUT"]}, None, NEW, _roles_of)
        html_out = to_html(pv, WsFontRegistry.empty())
        # wrapper + field div + one div per entry
        assert html_out.count("<div") == 2 + 3
        for entry in ("-i2  PST", "-a1  IMP", "-u3  FUT"):
            assert f">{entry}</span></div>" in html_out

    def test_entries_are_not_concatenated_into_one_line(self):
        pv = diff_props({"Affixes": ["aa", "bb"]}, None, NEW, _roles_of)
        html_out = to_html(pv, WsFontRegistry.empty())
        assert "</span><span" not in html_out  # no run-on segments

    def test_no_bullet_or_added_punctuation(self):
        pv = diff_props({"Affixes": ["aa", "bb"]}, None, NEW, _roles_of)
        html_out = to_html(pv, WsFontRegistry.empty())
        for artifact in ("<ul", "<li", "<br", "&#8226;", "&bull;", "* ", " - ", ", "):
            assert artifact not in html_out, artifact

    def test_replacement_pair_still_collapses_within_a_line(self):
        """A removed+added pair stays one ``old -> new`` line, so a per-line
        layout does not split a replacement in half."""
        pv = diff_props({"Name": "new"}, {"Name": "old"}, OVERWRITE, _roles_of)
        html_out = to_html(pv, WsFontRegistry.empty())
        assert _arrow() in html_out
        assert html_out.count("<div") == 2


# ===========================================================================
# FR-035 -- affix label: form and gloss separated by whitespace only
# ===========================================================================


class TestAffixLabel:
    def test_form_and_gloss_separated_by_whitespace(self):
        label = _affix_msa_label(_affix_msa(form="-i", hn=2, gloss="PST"))
        assert label.startswith("-i2")
        assert label.endswith("PST")
        between = label[len("-i2"):-len("PST")]
        assert between.strip() == "", repr(between)
        assert between != "", "form and gloss must be separated"

    def test_no_quote_characters_added(self):
        label = _affix_msa_label(_affix_msa(form="-i", hn=2, gloss="PST"))
        assert "'" not in label
        assert '"' not in label

    def test_no_punctuation_added_between_form_and_gloss(self):
        label = _affix_msa_label(_affix_msa(form="-i", hn=0, gloss="IMP"))
        between = label[len("-i"):-len("IMP")]
        for ch in between:
            assert ch.isspace(), repr(between)

    def test_apostrophe_in_the_form_preserved(self):
        """FR-034 at the label level: the apostrophe here is a glottal stop."""
        label = _affix_msa_label(_affix_msa(form="-ba'", hn=0, gloss="PL"))
        assert label.startswith("-ba'")
        assert label.count("'") == 1

    def test_apostrophe_in_the_gloss_preserved(self):
        label = _affix_msa_label(_affix_msa(form="-i", hn=0, gloss="POSS'3S"))
        assert label.endswith("POSS'3S")
        assert label.count("'") == 1

    def test_form_only_label_has_no_trailing_gap(self):
        label = _affix_msa_label(_affix_msa(form="-i", hn=2, gloss=""))
        assert label == "-i2"

    def test_slot_enricher_uses_the_gap_form(self):
        slot = FakeObj("slot-1", Affixes=[_affix_msa(form="-i", hn=2, gloss="PST")])
        raw: dict = {"Name": {"en": "aug"}}
        _enrich_slot(slot, raw)
        assert len(raw["Affixes"]) == 1
        assert "'" not in raw["Affixes"][0]
        assert raw["Affixes"][0].split() == ["-i2", "PST"]


# ===========================================================================
# FR-036 -- an empty list-valued field is explicitly empty
# ===========================================================================


class TestEmptyListField:
    def test_empty_list_new_mode_renders_none(self):
        """Today the key is dropped entirely; the operator cannot tell an empty
        list from an unread one."""
        pv = diff_props({"Affixes": []}, None, NEW, _roles_of)
        assert _texts(pv, "Affixes") == ["(none)"]

    def test_empty_list_note_kind(self):
        pv = diff_props({"Affixes": []}, None, NEW, _roles_of)
        seg = _fd(pv, "Affixes").segments[0]
        assert seg.kind == SegmentKind.NOTE
        assert seg.ws_role is None

    def test_empty_list_both_sides_renders_none(self):
        pv = diff_props({"Affixes": []}, {"Affixes": []}, OVERWRITE, _roles_of)
        assert _texts(pv, "Affixes") == ["(none)"]

    def test_empty_list_target_only_renders_none(self):
        pv = diff_props({}, {"Affixes": []}, OVERWRITE, _roles_of)
        assert _texts(pv, "Affixes") == ["(none)"]

    def test_empty_list_link_only_renders_none(self):
        pv = diff_props({"Affixes": []}, {"Affixes": []}, LINK_ONLY, _roles_of)
        assert _texts(pv, "Affixes") == ["(none)"]

    def test_source_emptied_a_populated_target_still_shows_members(self):
        """An empty SOURCE list against a populated target is not an empty
        field -- the union still has members, so no ``(none)``."""
        pv = diff_props({"Affixes": []}, {"Affixes": ["-i2"]}, OVERWRITE, _roles_of)
        assert _texts(pv, "Affixes") == ["-i2"]

    def test_empty_list_html_shows_none_not_a_blank(self):
        html_out = to_html(diff_props({"Affixes": []}, None, NEW, _roles_of),
                           WsFontRegistry.empty())
        assert "(none)" in html_out
        assert "<b>Affixes</b>: " in html_out

    def test_empty_scalar_string_unaffected(self):
        """FR-045: only *list*-valued fields gain the note."""
        pv = diff_props({"Name": ""}, None, NEW, _roles_of)
        assert _texts(pv, "Name") == ["''"]


# ===========================================================================
# FR-037 -- a capped list states the cap AND the true total
# ===========================================================================


class TestTruncationNote:
    def test_list_item_limit_unchanged(self):
        assert mp._LIST_ITEM_LIMIT == 25

    def test_note_states_cap_and_true_total(self):
        slot = FakeObj(
            "slot-big",
            Affixes=[_affix_msa(form=f"-a{i}", hn=0, gloss=f"G{i}") for i in range(41)],
        )
        raw: dict = {"Name": {"en": "big"}}
        _enrich_slot(slot, raw)
        assert len(raw["Affixes"]) == 25
        assert raw["Truncated"] == "showing 25 of 41 affixes"

    def test_note_is_never_a_bare_truncated(self):
        slot = FakeObj(
            "slot-big",
            Affixes=[_affix_msa(form=f"-a{i}", hn=0, gloss=f"G{i}") for i in range(30)],
        )
        raw: dict = {}
        _enrich_slot(slot, raw)
        note = raw["Truncated"]
        assert note != "affix list truncated"
        assert "25" in note and "30" in note

    def test_no_note_when_under_the_cap(self):
        slot = FakeObj(
            "slot-small",
            Affixes=[_affix_msa(form=f"-a{i}", hn=0, gloss=f"G{i}") for i in range(3)],
        )
        raw: dict = {}
        _enrich_slot(slot, raw)
        assert "Truncated" not in raw
        assert len(raw["Affixes"]) == 3

    def test_note_reaches_the_pane_as_a_field(self):
        """The disclosure has to be visible, not merely present in the props."""
        slot = FakeObj(
            "slot-big",
            Affixes=[_affix_msa(form=f"-a{i}", hn=0, gloss=f"G{i}") for i in range(41)],
        )
        raw: dict = {}
        _enrich_slot(slot, raw)
        html_out = to_html(diff_props(raw, None, NEW, _roles_of), WsFontRegistry.empty())
        assert "showing 25 of 41 affixes" in html_out
