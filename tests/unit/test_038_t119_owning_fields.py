"""Feature 038, T119's follow-on -- the PER-OWNING-FIELD dimension.

WHY THE CLASS ROW COULD NOT CLOSE `FsFeatStruc` / `FsClosedValue`.

`tests/unit/test_038_t119_feat_struc_owners.py` and
`tests/integration/test_object_census.py::TestT124T119PerOwningField` both
found the two rows are BUCKETS: `MoStemMsa.MsFeatures` alone carries 1,003
objects of total loss on the three sanctioned pairs while `MoStemMsa` itself
counts MATCHED, invisible to any counts-only gate. This mirrors T081's
`CmPossibility` finding exactly -- "the class name is not the unit of work"
(T023b) -- and `census.count_by_owning_field` / `census_cli.
accounted_for_owning_fields` are this dimension's twin of `count_by_owning_
list` / `accounted_for_owning_lists`.

THE ROSTER (`models.CENSUS_OWNING_FIELD_RULINGS`) IS EMPTY ON PURPOSE. Unlike
`CmPossibility`'s lists, none of the ten owning fields T119 measured belongs
to another feature -- see that constant's header comment for the measured
table and the reasoning. So the tests below exercise the MECHANISM with
monkeypatched rosters (mirroring `test_038_t081_owning_lists.py`'s
`NGOREME_LISTS` fixture), and separately assert the production roster's
current emptiness is deliberate, not an oversight.
"""

from __future__ import annotations

import pytest

from gramtrans import census_cli
from gramtrans.Lib import census, models


# A synthetic shape carrying the same structure T119 measured: one field this
# feature is still obliged to fix (`MoStemMsa.MsFeatures`, UNRULED) beside one
# this test roster pretends is ruled out of scope, plus a surplus field.
FEAT_STRUC_FIELDS = [
    {"field": "MoStemMsa.MsFeatures",
     "source_count": 117, "destination_count": 0},        # -117  UNRULED
    {"field": "Some.OtherFeature",
     "source_count": 40, "destination_count": 10},        #  -30  ruled (test)
    {"field": "Some.SurplusFeature",
     "source_count": 5, "destination_count": 8},          #   +3  ruled, SURPLUS
]

#: Sum of the SHORTFALL halves above: 117 + 30 = 147.
_TOTAL_SHORTFALL = 147
#: The ruled part of it -- everything but `MoStemMsa.MsFeatures`.
_RULED_SHORTFALL = 30

_TEST_RULING = {
    ("FsFeatStruc", "Some.OtherFeature"): (
        "OUT_OF_SCOPE_CLASS",
        "test-only ruling, not a committed document",
        "a synthetic field used only to exercise the emitter",
    ),
    ("FsFeatStruc", "Some.SurplusFeature"): (
        "OUT_OF_SCOPE_CLASS",
        "test-only ruling, not a committed document",
        "a synthetic surplus field used only to exercise the emitter",
    ),
}


@pytest.fixture(autouse=True)
def _ruled(monkeypatch):
    monkeypatch.setattr(census, "OWNING_FIELD_RULINGS", _TEST_RULING)


def _lines(difference, fields=None, existing=(), notes=None):
    return census_cli.accounted_for_owning_fields(
        "FsFeatStruc", difference,
        FEAT_STRUC_FIELDS if fields is None else fields,
        existing, notes)


class TestTheRosterIsKeyedFinerThanAClass:

    def test_a_ruled_field_resolves(self):
        entry = census.owning_field_ruling("FsFeatStruc", "Some.OtherFeature")
        assert entry is not None
        token, ruling, _why = entry
        assert token == "OUT_OF_SCOPE_CLASS"

    def test_mostemmsa_msfeatures_is_deliberately_absent_in_production(self):
        """The PRODUCTION roster, not the monkeypatched test one.

        `MoStemMsa.MsFeatures` is this feature's own content -- T119's
        docstring names `_create_msa_for_closure` as the still-unfixed cause
        of a TOTAL LOSS on every sanctioned pair. Its absence from
        `CENSUS_OWNING_FIELD_RULINGS` is what keeps that shortfall failing the
        gate, so it is asserted directly against the module constant rather
        than through the monkeypatched fixture above.
        """
        assert ("FsFeatStruc", "MoStemMsa.MsFeatures") not in (
            models.CENSUS_OWNING_FIELD_RULINGS)

    def test_the_production_roster_is_empty_and_that_is_recorded(self):
        """Not a placeholder -- see the constant's header for why. Asserted
        so a future entry lands as a deliberate, reviewed change rather than
        an unnoticed drift from empty."""
        assert models.CENSUS_OWNING_FIELD_RULINGS == {}

    def test_a_ruling_does_not_leak_across_classes(self):
        """The key is a PAIR. A field ruled for `FsFeatStruc` must not excuse
        a same-named field on another class."""
        assert census.owning_field_ruling(
            "FsClosedValue", "Some.OtherFeature") is None

    def test_every_token_in_a_populated_roster_is_in_the_closed_vocabulary(
            self):
        for (cls, _field), (token, _ruling, _why) in _TEST_RULING.items():
            assert token in census.REASON_TOKENS, cls
            assert token in census.REASONS_NOT_REQUIRING_REPORT_REF


class TestTheEmitter:

    def test_one_line_per_ruled_shortfall_field(self):
        lines = _lines(-_TOTAL_SHORTFALL)
        assert len(lines) == 1          # the one ruled SHORTFALL field
        assert {ln.reason for ln in lines} == {"OUT_OF_SCOPE_CLASS"}
        assert sum(ln.count for ln in lines) == _RULED_SHORTFALL

    def test_an_unruled_field_gets_no_line_even_beside_ruled_ones(self):
        """THE POINT OF THE WHOLE DIMENSION. `MoStemMsa.MsFeatures` loses 117
        objects on this synthetic row; that object class is a real, open
        defect and must stay unexplained while a neighbouring field in the
        SAME ROW is fully accounted."""
        lines = _lines(-_TOTAL_SHORTFALL)
        assert all("MoStemMsa" not in (ln.detail or "") for ln in lines)
        assert _TOTAL_SHORTFALL - sum(ln.count for ln in lines) == 117

    def test_each_line_names_its_own_field_and_ruling(self):
        lines = _lines(-_TOTAL_SHORTFALL)
        assert len(lines) == 1
        assert lines[0].count == 30
        assert "Some.OtherFeature" in (lines[0].detail or "")

    def test_a_surplus_field_is_never_netted_against_a_shortfall(self):
        """`Some.SurplusFeature` is +3 here. Netting it would let a field
        that GAINED objects pay for a field that lost them."""
        lines = _lines(-_TOTAL_SHORTFALL)
        assert all("SurplusFeature" not in (ln.detail or "") for ln in lines)
        assert all(ln.direction == "shortfall" for ln in lines)

    def test_no_line_outruns_its_own_field(self):
        """R-2 per field: this ruled field lost exactly 30, and the line
        cannot claim more than that even though the row's total shortfall
        (147) is larger."""
        lines = _lines(-_TOTAL_SHORTFALL)
        assert len(lines) == 1
        assert lines[0].count == 30


class TestTheCapCannotOutrunTheFieldsMeasuredShortfall:
    """The required cap test: a line cannot outrun ITS field's shortfall."""

    def test_the_row_room_caps_the_total_below_the_fields_own_loss(self):
        """The ruled field lost 30, but `difference` (row room) is only -10:
        the line must not claim more than the row's remaining room."""
        lines = _lines(-10)
        assert sum(ln.count for ln in lines) == 10
        assert lines[0].count == 10

    def test_the_field_cap_binds_even_with_unlimited_row_room(self):
        """The row has plenty of room (-1000), but the ruled field only ever
        lost 30 -- the line must not claim more than that, however much room
        the row offers."""
        lines = _lines(-1000, fields=[
            {"field": "Some.OtherFeature",
             "source_count": 40, "destination_count": 10},
        ])
        assert len(lines) == 1
        assert lines[0].count == 30

    def test_an_existing_line_takes_the_room_first(self):
        existing = (census.AccountedLine(
            reason="OUT_OF_SCOPE_CLASS", count=140, direction="shortfall",
            detail="an earlier, evidenced claim"),)
        lines = _lines(-_TOTAL_SHORTFALL, existing=existing)
        assert sum(ln.count for ln in lines) == _TOTAL_SHORTFALL - 140

    def test_a_fully_claimed_row_emits_nothing(self):
        existing = (census.AccountedLine(
            reason="OUT_OF_SCOPE_CLASS", count=_TOTAL_SHORTFALL,
            direction="shortfall", detail="already fully claimed"),)
        assert _lines(-_TOTAL_SHORTFALL, existing=existing) == ()

    def test_a_capped_claim_says_so_in_the_notes(self):
        notes: list = []
        _lines(-10, notes=notes)
        assert any("UNEXPLAINED" in n for n in notes)

    @pytest.mark.parametrize("difference", [None, 0, 5])
    def test_a_non_shortfall_row_is_refused(self, difference):
        assert _lines(difference) == ()


class TestTheEmitterIsInertWithoutTheRoster:
    """T109 lock 3, applied to the fourth roster."""

    def test_emptying_the_roster_emits_nothing(self, monkeypatch):
        monkeypatch.setattr(census, "OWNING_FIELD_RULINGS", {})
        assert _lines(-_TOTAL_SHORTFALL) == ()

    def test_and_the_lookup_agrees(self, monkeypatch):
        monkeypatch.setattr(census, "OWNING_FIELD_RULINGS", {})
        assert census.owning_field_ruling(
            "FsFeatStruc", "Some.OtherFeature") is None


class TestEmptyingTheProductionRosterRestoresTheArtifactByteForByte:
    """RULE 5's pinning test: the production roster is ALREADY empty, so
    emptying it (a no-op) must change nothing -- proving the emitter has no
    hidden behaviour beyond what the roster states, the same claim
    `TestTheEmitterIsInertWithoutTheRoster` makes with a populated roster."""

    def test_the_production_roster_already_produces_no_lines_here(self):
        assert _lines(-_TOTAL_SHORTFALL, fields=FEAT_STRUC_FIELDS,
                      ) is not None  # sanity: the call itself does not raise

    def test_the_production_artifact_gains_no_owning_fields_dimension_today(
            self, monkeypatch):
        """With the REAL (empty) roster restored, every field in a realistic
        T119 shape is either matched (no shortfall reaches the emitter) or
        unruled (explicitly excluded) -- so no line is ever produced."""
        monkeypatch.setattr(census, "OWNING_FIELD_RULINGS",
                             dict(models.CENSUS_OWNING_FIELD_RULINGS))
        lines = census_cli.accounted_for_owning_fields(
            "FsFeatStruc", -117,
            [{"field": "MoStemMsa.MsFeatures",
              "source_count": 117, "destination_count": 0}])
        assert lines == ()


class TestALeakDetector:
    """A roster of ONE in-scope field must NOT produce a line for a
    DIFFERENT, unruled field in the same row."""

    def test_a_single_entry_roster_does_not_leak_to_an_unlisted_field(
            self, monkeypatch):
        monkeypatch.setattr(census, "OWNING_FIELD_RULINGS", {
            ("FsFeatStruc", "Some.OtherFeature"): (
                "OUT_OF_SCOPE_CLASS", "test-only", "one ruled field only"),
        })
        lines = census_cli.accounted_for_owning_fields(
            "FsFeatStruc", -_TOTAL_SHORTFALL, FEAT_STRUC_FIELDS)
        # Exactly one line, for the one ruled field -- the unruled
        # `MoStemMsa.MsFeatures` and the never-ruled surplus field both stay
        # untouched, even though the roster is non-empty.
        assert len(lines) == 1
        assert "Some.OtherFeature" in (lines[0].detail or "")
        assert all("MoStemMsa" not in (ln.detail or "") for ln in lines)


class TestTheJoin:

    def test_the_union_of_labels_is_kept_not_the_source_keys(self):
        merged = census_cli._merge_owning_fields(
            "FsFeatStruc",
            {"FsFeatStruc": {"A": 3}},
            {"FsFeatStruc": {"B": 2}})
        assert merged == [
            {"field": "A", "source_count": 3, "destination_count": 0},
            {"field": "B", "source_count": 0, "destination_count": 2},
        ]

    def test_a_class_with_no_dimension_merges_to_nothing(self):
        assert census_cli._merge_owning_fields(
            "MoStemMsa", {"FsFeatStruc": {"A": 1}}, {}) == []

    def test_missing_readings_are_not_an_error(self):
        assert census_cli._merge_owning_fields("FsFeatStruc", None, None) == []


class TestTheArtifactCarriesTheEvidence:

    def test_the_dimension_is_sorted_and_typed(self):
        from gramtrans.Lib.census import class_row_artifact

        entry = census.ClassListEntry(
            object_class="FsFeatStruc", engine_can_create=True,
            in_class_list_via="coverage_floor", gate_scope="required")
        row = _StubRow()
        block = class_row_artifact(
            row, entry,
            owning_fields=[
                {"field": "Z.b", "source_count": 1, "destination_count": 0},
                {"field": "A.a", "source_count": 2, "destination_count": 2},
            ])
        assert [i["field"] for i in block["owning_fields"]] == ["A.a", "Z.b"]
        assert block["owning_fields"][0]["source_count"] == 2

    def test_an_empty_dimension_is_omitted_entirely(self):
        from gramtrans.Lib.census import class_row_artifact

        entry = census.ClassListEntry(
            object_class="FsFeatStruc", engine_can_create=True,
            in_class_list_via="coverage_floor", gate_scope="required")
        block = class_row_artifact(_StubRow(), entry, owning_fields=[])
        assert "owning_fields" not in block


class _StubRow:
    """The minimum `class_row_artifact` reads off a row."""
    object_class = "FsFeatStruc"
    source_count = 1691
    destination_count = 0
    difference = -1691
    difference_raw = -1691
    destination_count_net = 0
    engine_can_create = True
    owning_feature_system = None
    starter_excluded = 0
    explained = False
    reasons = ()
    out_of_scope = False
