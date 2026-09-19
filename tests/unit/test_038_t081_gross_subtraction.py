"""Feature 038 T081 (6th re-gate): the GROSS SUBTRACTION lane.

WHAT THE GATE WAS READING. On `baseline_gross`, a row's `difference` is
`destination - starter_excluded - source`, so it subtracts the starter
population from a destination that -- on a correct run -- is exactly where the
source's own objects LANDED, by natural-key match onto starter content.
`fidelity-census.md` 5.2 says so outright ("gross subtraction also subtracts
the starter objects the transfer correctly matched, so it reports a shortfall
on a correct run") and `gross_basis_cap_notes` already caps the VERDICT for
it -- but that cap never reached `_phase_5`, so P5 kept reading a phantom as an
unexplained loss.

MEASURED, on the committed `census-038-t134-*` artifacts' `CmPossibility` row:

    pair      source  dest_total  starter  difference  difference_raw  unexpl.
    ejagham      308         302      302        -308              -6      302
    ngoreme      398         303      302        -397             -95      271
    mbugwe       338         305      302        -335             -33      301

`difference_raw - difference` is 302 on every pair -- exactly
`starter_excluded` -- and the per-list table sums to the RAW figure to the
object on all three. That reconciliation is the witness this lane requires.

WHY THE BASIS ALONE MAY NOT LICENSE THE LINE. If it did, this lane would
excuse every real loss on every gross-basis row in the artifact. It is
therefore gated on an INDEPENDENT, ARTIFACT-INTERNAL witness: a per-owning-list
or per-owning-field table, measured per sub-key from both projects and knowing
nothing of the baseline document, whose summed `source - destination`
reconciles to `difference_raw` EXACTLY. Off by ONE object and no line is
emitted -- which is the single most important test in this file, because it is
the one that stops the lane being a blanket amnesty.
"""
from __future__ import annotations

from gramtrans import census_cli
from gramtrans.Lib import census


GROSS = census.GROSS_SUBTRACTION_BASIS


def _lists(pairs):
    return [{"list": name, "source_count": s, "destination_count": d}
            for name, s, d in pairs]


def _call(difference, difference_raw, starter_excluded, items,
          basis=GROSS, existing=(), notes=None, kind="list"):
    return census_cli.accounted_for_gross_subtraction(
        "CmPossibility", difference, difference_raw, starter_excluded, basis,
        kind, items, existing, notes)


# --------------------------------------------------------------------------
# The measured rows
# --------------------------------------------------------------------------

def test_ejagham_the_whole_row_is_the_gross_subtraction():
    """Per-list sums 308 -> 302, reconciling to difference_raw -6. The ruled
    GenreList line has already claimed the entire REAL loss (6), so the room
    left is 302 and the lane closes the row exactly."""
    existing = (census.AccountedLine(
        reason="OUT_OF_SCOPE_CLASS", count=6, direction="shortfall",
        detail="GenreList"),)
    lines = _call(-308, -6, 302, _lists([("GenreList", 35, 29),
                                         ("Roles", 273, 273)]),
                  existing=existing)
    assert len(lines) == 1
    assert lines[0].reason == "STARTER_CONTENT"
    assert lines[0].count == 302
    assert lines[0].direction == "shortfall"
    assert census.accounted_in_direction(existing + lines, "shortfall") == 308


def test_ngoreme_the_claim_is_capped_by_the_rows_room():
    """Ruled lists claim 126 -- MORE than the raw 95, because ChartMarkers is
    +30 and surpluses are never netted. Room is 397 - 126 = 271, below the 302
    over-subtraction, so the lane claims 271 and says so."""
    existing = (census.AccountedLine(
        reason="OUT_OF_SCOPE_CLASS", count=126, direction="shortfall",
        detail="five ruled lists"),)
    notes = []
    lines = _call(-397, -95, 302,
                  _lists([("NoteCategories", 115, 0), ("ChartMarkers", 37, 67),
                          ("rest", 246, 236)]),
                  existing=existing, notes=notes)
    assert len(lines) == 1 and lines[0].count == 271
    assert "CLAIM CAPPED BY THE ROW'S ROOM" in lines[0].detail
    assert any("stays UNEXPLAINED (R-2)" in n for n in notes)
    assert census.accounted_in_direction(existing + lines, "shortfall") == 397


def test_mbugwe_closes_at_301():
    existing = (census.AccountedLine(
        reason="OUT_OF_SCOPE_CLASS", count=34, direction="shortfall",
        detail="four ruled lists"),)
    lines = _call(-335, -33, 302,
                  _lists([("ChartMarkers", 77, 67), ("Languages", 15, 0),
                          ("rest", 246, 238)]),
                  existing=existing)
    assert len(lines) == 1 and lines[0].count == 301
    assert census.accounted_in_direction(existing + lines, "shortfall") == 335


# --------------------------------------------------------------------------
# Falsifiability -- the tests that stop this being an amnesty
# --------------------------------------------------------------------------

def test_a_table_off_by_one_object_emits_NOTHING():
    """THE LOAD-BEARING TEST. The witness is the reconciliation, not the
    basis. One object of disagreement means the phantom and a real loss are
    indistinguishable on this row, so the shortfall STAYS unexplained."""
    notes = []
    lines = _call(-308, -6, 302, _lists([("GenreList", 35, 30),
                                         ("Roles", 273, 273)]),  # sums to -5
                  notes=notes)
    assert lines == ()
    assert any("does NOT reconcile" in n for n in notes)
    assert any("an unreconciled witness is not a witness" in n for n in notes)


def test_no_sub_key_table_emits_nothing():
    """Absence of the witness is not the witness."""
    notes = []
    assert _call(-308, -6, 302, [], notes=notes) == ()
    assert _call(-308, -6, 302, None, notes=notes) == ()


def test_a_non_gross_basis_row_is_untouched():
    """`baseline_matched` did not double-subtract, so there is nothing to
    undo and the lane must not invent a claim."""
    assert _call(-308, -6, 302, _lists([("GenreList", 308, 302)]),
                 basis="baseline_matched") == ()
    assert _call(-308, -6, 302, _lists([("GenreList", 308, 302)]),
                 basis="no_baseline") == ()


def test_a_zero_starter_baseline_claims_nothing():
    """`FsFeatStruc` has no starter population, so difference == difference_raw
    and the lane has nothing to undo even though its per-field table
    reconciles."""
    assert _call(-21, -21, 0, _lists([("PhPhoneme.Features", 41, 20)]),
                 kind="field") == ()


def test_a_matched_or_surplus_row_is_untouched():
    assert _call(0, 0, 302, _lists([("x", 1, 1)])) == ()
    assert _call(5, 5, 302, _lists([("x", 1, 1)])) == ()
    assert _call(None, None, 302, _lists([("x", 1, 1)])) == ()


def test_a_fully_claimed_row_gets_no_second_line():
    """R-2: the census must not explain away more than actually happened."""
    existing = (census.AccountedLine(
        reason="OUT_OF_SCOPE_CLASS", count=308, direction="shortfall",
        detail="everything"),)
    assert _call(-308, -6, 302, _lists([("GenreList", 35, 29),
                                        ("Roles", 273, 273)]),
                 existing=existing) == ()


# --------------------------------------------------------------------------
# Admissibility -- the line must actually satisfy the gate it is written for
# --------------------------------------------------------------------------

def test_the_token_is_phase_5_admissible_and_report_ref_exempt():
    """Both are properties of the CLOSED VOCABULARY, not of this lane, and
    asserting them here is what makes the lane's choice of token falsifiable
    if either roster ever moves."""
    assert "STARTER_CONTENT" in census.PHASE_5_ADMISSIBLE_REASONS
    assert "STARTER_CONTENT" in census.REASONS_NOT_REQUIRING_REPORT_REF
    assert "STARTER_CONTENT" not in census.NOT_EVALUATED_REASONS


def test_the_detail_names_its_basis_and_its_witness():
    """A reader must be able to tell from the LINE why the objects were not
    lost, without going back to the source."""
    lines = _call(-308, -6, 302, _lists([("GenreList", 35, 29),
                                         ("Roles", 273, 273)]))
    detail = lines[0].detail
    assert GROSS in detail
    assert "per-list table reconciles to difference_raw -6 exactly" in detail
    assert "fidelity-census.md 5.2" in detail
    assert "report_ref" in detail


def test_the_per_field_dimension_works_the_same_way():
    """The lane is keyed on the witness, not on the class, so a per-FIELD
    table reconciles identically -- `reconciling_kind` only names it."""
    lines = census_cli.accounted_for_gross_subtraction(
        "SomeClass", -50, -10, 40, GROSS, "field",
        [{"field": "A.B", "source_count": 30, "destination_count": 20}],
        (), None)
    assert len(lines) == 1 and lines[0].count == 40
    assert "per-field table" in lines[0].detail
