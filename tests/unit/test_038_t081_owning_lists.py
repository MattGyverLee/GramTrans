"""Feature 038, T081 -- the PER-OWNING-LIST dimension and its emitter.

WHY THE CLASS ROW COULD NOT CLOSE `CmPossibility`.

The row reads -308 / -397 / -335 on the three sanctioned pairs, and every one
of those figures is a BUCKET. `CmPossibility` covers Scripture note categories,
discourse-chart furniture, text genres, dialect labels AND
`MoMorphData.ProdRestrict` -- which is this feature's own grammatical content.
`contracts/cmpossibility-list-rulings.md` 5 refuses a class-keyed roster entry
by name for exactly that reason: one sentence retiring the row would cover the
productivity restrictions with the words written for Scripture notes, the row
would go green, and the restrictions would still be missing. "The class name is
not the unit of work" (T023b) is the rule these tests enforce.

So the ruling is per OWNING LIST. A per-list accounting line needs a per-list
MEASUREMENT, because R-1 rejects at construction any line that outruns its
evidence -- which is why `census.count_by_owning_list` exists and why the
artifact carries `owning_lists`.

THE LOAD-BEARING TEST IN THIS FILE is
`test_an_unruled_list_gets_no_line_even_beside_ruled_ones`: it is the one that
fails if the dimension is ever collapsed back to a class key.
"""

from __future__ import annotations

import pytest

from gramtrans import census_cli
from gramtrans.Lib import census


# A HISTORICAL FIXTURE, NOT THE LIVE PIN -- read this before touching a number
# below. This table was built from `probes/owner-probe-Ngoreme-FLEx.json`
# joined to `owner-probe-GT038-Ngoreme-After.json` (neither file is committed;
# both are gone) and its per-list deltas summed to -96, `difference_raw` on
# that RETIRED destination. The corpus problem T081 records ("the T078 trio is
# not reproducible as measured") is exactly why that destination cannot be
# regenerated -- `Ngoreme Target` must never be restored (see tasks.md T081).
#
# THE LIVE GATING PIN HAS SINCE MOVED, AND DISAGREES ON THREE OF EIGHT ROWS.
# `tests/integration/_snapshots/recensus-038-t131-ngoreme.json`'s
# `t122_per_owning_list` (checked 2026-09-18) sums to -95, one less, and not
# by a uniform shift:
#   * `LangProject.Status`       here 1->0 (-1);  live pin 5->4  (-1, same
#     magnitude, different absolute counts -- the source corpus moved)
#   * `LexDb.ExtendedNoteTypes`  here 0->1 (+1);  live pin 4->5  (+1, same)
#   * `MoMorphData.ProdRestrict` here 4->3 (-1), UNRULED and load-bearing for
#     `test_an_unruled_list_gets_no_line_even_beside_ruled_ones`; live pin
#     reads 1->1, MATCHED -- the one open defect this fixture exists to keep
#     visible has since been fixed on the live corpus.
# Re-pinning to the live artifact would delete the only UNRULED row the
# dimension test depends on, so this fixture stays a SYNTHETIC, HISTORICAL
# shape kept for its structure (one class, many owning lists, a mix of ruled
# shortfall/surplus/unruled) rather than as a current measurement. Do not
# read `NGOREME_LISTS` as "ngoreme reads this today" -- it does not.
NGOREME_LISTS = [
    {"list": "Scripture.NoteCategories",
     "source_count": 115, "destination_count": 0},      # -115  ruled
    {"list": "LangProject.GenreList",
     "source_count": 32, "destination_count": 29},      #   -3  ruled
    {"list": "LangProject.CheckLists",
     "source_count": 5, "destination_count": 0},        #   -5  ruled
    {"list": "LexDb.DialectLabels",
     "source_count": 2, "destination_count": 0},        #   -2  ruled
    {"list": "LangProject.Status",
     "source_count": 1, "destination_count": 0},        #   -1  ruled
    {"list": "DsDiscourseData.ChartMarkers",
     "source_count": 37, "destination_count": 67},      #  +30  ruled, SURPLUS
    {"list": "LexDb.ExtendedNoteTypes",
     "source_count": 0, "destination_count": 1},        #   +1  ruled, SURPLUS
    {"list": "MoMorphData.ProdRestrict",
     "source_count": 4, "destination_count": 3},        #   -1  UNRULED
]

#: Sum of the SHORTFALL halves above: 115 + 3 + 5 + 2 + 1 + 1 = 127.
_TOTAL_SHORTFALL = 127
#: The ruled part of it -- everything but `MoMorphData.ProdRestrict`.
_RULED_SHORTFALL = 126


def _lines(difference, lists=None, existing=(), notes=None):
    return census_cli.accounted_for_owning_lists(
        "CmPossibility", difference,
        NGOREME_LISTS if lists is None else lists,
        existing, notes)


class TestTheRosterIsKeyedFinerThanAClass:

    def test_a_ruled_list_resolves(self):
        entry = census.owning_list_ruling(
            "CmPossibility", "Scripture.NoteCategories")
        assert entry is not None
        token, ruling, _why = entry
        assert token == "OUT_OF_SCOPE_CLASS"
        assert "cmpossibility-list-rulings.md" in ruling

    def test_prod_restrict_is_deliberately_absent(self):
        """`MoMorphData.ProdRestrict` is THIS feature's own content. Its
        absence from the roster is the reason the roster is safe to be
        load-bearing, so it is asserted rather than assumed."""
        assert census.owning_list_ruling(
            "CmPossibility", "MoMorphData.ProdRestrict") is None

    def test_a_ruling_does_not_leak_across_classes(self):
        """The key is a PAIR. A list ruled for `CmPossibility` must not excuse
        a same-named list on another class."""
        assert census.owning_list_ruling(
            "LexEntryType", "Scripture.NoteCategories") is None

    def test_every_token_is_in_the_closed_vocabulary(self):
        for (cls, _list), (token, _ruling, _why) in \
                census.OWNING_LIST_RULINGS.items():
            assert token in census.REASON_TOKENS, cls
            # Every entry must be report_ref-exempt, or `AccountedLine` would
            # reject the emitted line at construction for want of evidence
            # this roster structurally cannot supply.
            assert token in census.REASONS_NOT_REQUIRING_REPORT_REF


class TestTheEmitter:

    def test_one_line_per_ruled_shortfall_list(self):
        lines = _lines(-_TOTAL_SHORTFALL)
        assert len(lines) == 5          # the five ruled SHORTFALL lists
        assert {ln.reason for ln in lines} == {"OUT_OF_SCOPE_CLASS"}
        assert sum(ln.count for ln in lines) == _RULED_SHORTFALL

    def test_an_unruled_list_gets_no_line_even_beside_ruled_ones(self):
        """THE POINT OF THE WHOLE DIMENSION. `MoMorphData.ProdRestrict` loses
        one object on this pair; that object is a real defect and must stay
        unexplained while five neighbouring lists in the SAME ROW are fully
        accounted. A class-keyed roster could not express this, which is why
        `cmpossibility-list-rulings.md` 5 refuses one."""
        lines = _lines(-_TOTAL_SHORTFALL)
        assert all("ProdRestrict" not in (ln.detail or "") for ln in lines)
        # Exactly the one unruled object is left over.
        assert _TOTAL_SHORTFALL - sum(ln.count for ln in lines) == 1

    def test_each_line_names_its_own_list_and_ruling(self):
        by_list = {}
        for ln in _lines(-_TOTAL_SHORTFALL):
            for item in NGOREME_LISTS:
                if item["list"] in (ln.detail or ""):
                    by_list[item["list"]] = ln
        assert by_list["Scripture.NoteCategories"].count == 115
        assert by_list["LangProject.Status"].count == 1
        assert "cmpossibility-list-rulings.md" in (
            by_list["LangProject.Status"].detail or "")

    def test_a_surplus_list_is_never_netted_against_a_shortfall(self):
        """`ChartMarkers` is +30 here. Netting it would let a list that GAINED
        objects pay for lists that lost them -- the cancellation `build_totals`
        refuses at the artifact level, reappearing one dimension down."""
        lines = _lines(-_TOTAL_SHORTFALL)
        assert all("ChartMarkers" not in (ln.detail or "") for ln in lines)
        assert all(ln.direction == "shortfall" for ln in lines)

    def test_no_line_outruns_its_own_list(self):
        """R-2 per list. Each claim is capped by what ITS list actually lost,
        so a regression in an unruled list can never be absorbed by a ruled
        one."""
        shortfalls = {i["list"]: i["source_count"] - i["destination_count"]
                      for i in NGOREME_LISTS}
        for ln in _lines(-_TOTAL_SHORTFALL):
            named = [name for name in shortfalls
                     if name in (ln.detail or "")]
            assert len(named) == 1
            assert ln.count <= shortfalls[named[0]]


class TestTheRowCapStillBinds:

    def test_the_row_room_caps_the_total(self):
        """The per-list shortfalls sum to 127, but `difference` is starter-net
        and can be smaller. The lines must not explain away more than the row
        actually lost, however honest each list is on its own."""
        lines = _lines(-10)
        assert sum(ln.count for ln in lines) == 10

    def test_an_existing_line_takes_the_room_first(self):
        existing = (census.AccountedLine(
            reason="OUT_OF_SCOPE_CLASS", count=120, direction="shortfall",
            detail="an earlier, evidenced claim"),)
        lines = _lines(-_TOTAL_SHORTFALL, existing=existing)
        assert sum(ln.count for ln in lines) == _TOTAL_SHORTFALL - 120

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
        """A null `difference` is NOT_EVALUATED -- `_phase_5` skips it and the
        row zeroes both residues, so a line would claim objects nobody
        counted. A surplus is something that DID happen and no ruling here has
        looked at."""
        assert _lines(difference) == ()


class TestTheEmitterIsInertWithoutTheRoster:
    """T109 lock 3, applied to the third roster. The lookup reads the module
    global at call time precisely so this test can prove the emitter carries no
    hidden fallback of its own."""

    def test_emptying_the_roster_emits_nothing(self, monkeypatch):
        monkeypatch.setattr(census, "OWNING_LIST_RULINGS", {})
        assert _lines(-_TOTAL_SHORTFALL) == ()

    def test_and_the_lookup_agrees(self, monkeypatch):
        monkeypatch.setattr(census, "OWNING_LIST_RULINGS", {})
        assert census.owning_list_ruling(
            "CmPossibility", "Scripture.NoteCategories") is None


class TestTheJoin:

    def test_the_union_of_labels_is_kept_not_the_source_keys(self):
        """A list present only in the DESTINATION is a surplus and must stay
        visible. `LexDb.ExtendedNoteTypes` is 0 -> 1 on two of three pairs, so
        keying off the source alone would drop exactly the rows that prove the
        dimension is not merely a shortfall detector."""
        merged = census_cli._merge_owning_lists(
            "CmPossibility",
            {"CmPossibility": {"A": 3}},
            {"CmPossibility": {"B": 2}})
        assert merged == [
            {"list": "A", "source_count": 3, "destination_count": 0},
            {"list": "B", "source_count": 0, "destination_count": 2},
        ]

    def test_a_class_with_no_dimension_merges_to_nothing(self):
        assert census_cli._merge_owning_lists(
            "MoStemMsa", {"CmPossibility": {"A": 1}}, {}) == []

    def test_missing_readings_are_not_an_error(self):
        assert census_cli._merge_owning_lists("CmPossibility", None, None) == []


class TestTheArtifactCarriesTheEvidence:

    def test_the_dimension_is_sorted_and_typed(self):
        """Sorted so two censuses of one project are byte-identical -- the
        drift checks compare digests, and iteration order is not a
        measurement."""
        from gramtrans.Lib.census import class_row_artifact

        entry = census.ClassListEntry(
            object_class="CmPossibility", engine_can_create=True,
            in_class_list_via="coverage_floor", gate_scope="required")
        row = _StubRow()
        block = class_row_artifact(
            row, entry,
            owning_lists=[
                {"list": "Z.b", "source_count": 1, "destination_count": 0},
                {"list": "A.a", "source_count": 2, "destination_count": 2},
            ])
        assert [i["list"] for i in block["owning_lists"]] == ["A.a", "Z.b"]
        assert block["owning_lists"][0]["source_count"] == 2

    def test_an_empty_dimension_is_omitted_entirely(self):
        """`$defs.classRow` is `additionalProperties: false`; an empty
        dimension is better absent than present-and-meaningless."""
        from gramtrans.Lib.census import class_row_artifact

        entry = census.ClassListEntry(
            object_class="CmPossibility", engine_can_create=True,
            in_class_list_via="coverage_floor", gate_scope="required")
        block = class_row_artifact(_StubRow(), entry, owning_lists=[])
        assert "owning_lists" not in block


class _StubRow:
    """The minimum `class_row_artifact` reads off a row."""
    object_class = "CmPossibility"
    source_count = 400
    destination_count = 3
    difference = -397
    difference_raw = -397
    destination_count_net = 3
    engine_can_create = True
    owning_feature_system = None
    starter_excluded = 0
    explained = False
    reasons = ()
    out_of_scope = False
