"""Feature 038 T048f -- an unattributed match poisons only the classes it
could have been.

Raised by the T039 idempotence re-run
(`specs/038-transfer-fidelity-gaps/journal/T039-idempotence-rerun.md`).
`PhPhoneme` and `PhNCSegments` fell from the `baseline_matched` subtraction
basis to `baseline_gross` between two runs whose destination counts were
IDENTICAL -- 34 and 5 both times -- manufacturing a 21-object and a 2-object
phantom shortfall on a run that lost nothing at all.

The tallies were never missing. Run 2's `matched_to_source.by_object_class`
carried `PhPhoneme: 21` and `PhNCSegments: 2`, byte-for-byte what run 1
carried. They were REFUSED, because `matched_by_class_from_report` reports
completeness as ONE GLOBAL BOOLEAN and run 2 left 11 matches unattributed in
three unrelated categories (`GRAM_CATEGORIES`, `INFLECTION_FEATURES`,
`VARIANT_TYPES`). All 75 rows lost the stronger basis for it.

T048b had already settled the principle for the OTHER incompleteness signal,
in the same file twenty lines from the site this fixes: an unattributable
identity skip withholds the basis "from only the classes it could have been".
This is that rule applied to the report's own unattributed matches, through the
same two tables and the same unbounded fallback. Nothing new is trusted; a
second signal stops being blunter than the first.

WHY A THIRD GUID AUDIT WOULD NOT HAVE DONE IT. T048d's
`starter_matched_lower_bound` rescues `PartOfSpeech` on run 2 because its
starter objects match by GUID. It is blind to `PhPhoneme` BY CONSTRUCTION: a
natural-key match links a source object to a destination object holding a
DIFFERENT guid, so `B - |D \\ Q|` counts those 21 matched starters as
destination-only. The bound tested here is the only thing that can reach them.

MEASURED SCOPE OF THIS FIX, STATED HONESTLY. On the T039 pair this fix is
INERT, and the console says why: T048b's own signal is unbounded on run 2
(`AFFIXES`, `POS_INFLECTABLE_FEATS` and `STEMS` appear in neither attribution
table), which denies every class globally before this bound is ever consulted.
The phantom therefore survives, for a cause now precisely located and filed as
T048g. This file exists so the fix is not merely asserted to be correct: the
tests below drive the bound directly, with the identity-skip signal held clean,
which is the only way to see it work at all.
"""

from __future__ import annotations

import json

import pytest


def _write(tmp_path, payload, name="report.json"):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _matched(by_object_class, *, complete=True, unattributed=None):
    """A `matched_to_source` block shaped like `report.to_snapshot_json`'s."""
    block = {
        "by_object_class": dict(by_object_class),
        "total": sum(by_object_class.values()),
        "complete": complete,
    }
    if unattributed is not None:
        block["unattributed_by_category"] = dict(unattributed)
    return block


# ---------------------------------------------------------------------------
# Reading the bound
# ---------------------------------------------------------------------------

class TestTheBoundIsRead:
    """`census_cli.matched_tally_bound_from_report`."""

    def test_a_complete_tally_bounds_nothing(self, tmp_path):
        from gramtrans import census_cli
        path = _write(tmp_path, {
            "matched_to_source": _matched({"PhPhoneme": 21}, complete=True)})
        bound = census_cli.matched_tally_bound_from_report(path)
        assert bound.measured is True
        assert bound.unbounded is False
        assert bound.withheld == frozenset()

    def test_an_absent_block_is_unmeasured_and_not_a_bound(self, tmp_path):
        """No `matched_to_source` at all is not a clean bill of health, but it
        needs no bound either: with no per-class tally, no row can reach the
        matched basis in the first place."""
        from gramtrans import census_cli
        bound = census_cli.matched_tally_bound_from_report(
            _write(tmp_path, {"context": {"run_id": "GT-20260820-133834"}}))
        assert bound.measured is False
        assert bound.unbounded is False
        assert bound.withheld == frozenset()

    def test_a_one_to_one_category_bounds_to_exactly_one_class(self, tmp_path):
        """A `GRAM_CATEGORIES` match can only ever have been a
        `PartOfSpeech`, so that is the only row it may poison."""
        from gramtrans import census_cli
        path = _write(tmp_path, {"matched_to_source": _matched(
            {"PhPhoneme": 21}, complete=False,
            unattributed={"GRAM_CATEGORIES": 5})})
        bound = census_cli.matched_tally_bound_from_report(path)
        assert bound.unbounded is False
        assert bound.withheld == frozenset({"PartOfSpeech"})

    def test_an_ambiguous_category_bounds_to_its_closed_candidate_set(
            self, tmp_path):
        from gramtrans import census_cli
        path = _write(tmp_path, {"matched_to_source": _matched(
            {"PhPhoneme": 21}, complete=False,
            unattributed={"INFLECTION_FEATURES": 5, "VARIANT_TYPES": 1})})
        bound = census_cli.matched_tally_bound_from_report(path)
        assert bound.unbounded is False
        assert bound.withheld == frozenset({
            "FsClosedFeature", "FsComplexFeature",
            "LexEntryType", "LexEntryInflType"})

    def test_the_exact_run_2_breakdown_bounds_to_five_classes(self, tmp_path):
        """The measured case, pinned. `PhPhoneme` and `PhNCSegments` are NOT in
        the withheld set -- which is the entire point of the fix."""
        from gramtrans import census_cli
        path = _write(tmp_path, {"matched_to_source": _matched(
            {"PartOfSpeech": 4, "PhNCSegments": 2, "PhPhoneme": 21},
            complete=False,
            unattributed={"GRAM_CATEGORIES": 5, "INFLECTION_FEATURES": 5,
                          "VARIANT_TYPES": 1})})
        bound = census_cli.matched_tally_bound_from_report(path)
        assert bound.withheld == frozenset({
            "PartOfSpeech", "FsClosedFeature", "FsComplexFeature",
            "LexEntryType", "LexEntryInflType"})
        assert "PhPhoneme" not in bound.withheld
        assert "PhNCSegments" not in bound.withheld

    def test_an_unknown_category_is_unbounded(self, tmp_path):
        """`AFFIXES` is in neither table. Bounding it would be a guess, and a
        wrong bound lets a row claim a basis its tally cannot support."""
        from gramtrans import census_cli
        path = _write(tmp_path, {"matched_to_source": _matched(
            {"PhPhoneme": 21}, complete=False,
            unattributed={"AFFIXES": 88})})
        bound = census_cli.matched_tally_bound_from_report(path)
        assert bound.unbounded is True

    def test_one_unknown_category_poisons_the_whole_bound(self, tmp_path):
        """Mixing a bounded category with an unbounded one must not yield a
        partial bound that reads as complete."""
        from gramtrans import census_cli
        path = _write(tmp_path, {"matched_to_source": _matched(
            {"PhPhoneme": 21}, complete=False,
            unattributed={"GRAM_CATEGORIES": 5, "STEMS": 164})})
        bound = census_cli.matched_tally_bound_from_report(path)
        assert bound.unbounded is True

    def test_incomplete_with_no_breakdown_is_unbounded(self, tmp_path):
        """A report that asserts an incompleteness and declines to locate it is
        the one case where being blunt is right -- and is what the global flag
        used to handle for every case."""
        from gramtrans import census_cli
        path = _write(tmp_path, {"matched_to_source": _matched(
            {"PhPhoneme": 21}, complete=False)})
        bound = census_cli.matched_tally_bound_from_report(path)
        assert bound.unbounded is True
        assert bound.withheld == frozenset()

    def test_a_zero_count_is_not_a_risk(self, tmp_path):
        """An `unattributed_by_category` entry of 0 names no match, so it
        withholds nothing."""
        from gramtrans import census_cli
        path = _write(tmp_path, {"matched_to_source": _matched(
            {"PhPhoneme": 21}, complete=False,
            unattributed={"GRAM_CATEGORIES": 0})})
        bound = census_cli.matched_tally_bound_from_report(path)
        # No positive risk anywhere -> the `complete is False` claim is left
        # unlocated, so the conservative answer stands.
        assert bound.withheld == frozenset()
        assert bound.unbounded is True

    def test_a_negative_or_nonint_count_is_ignored(self, tmp_path):
        from gramtrans import census_cli
        path = _write(tmp_path, {"matched_to_source": _matched(
            {"PhPhoneme": 21}, complete=False,
            unattributed={"GRAM_CATEGORIES": -3, "VARIANT_TYPES": "many"})})
        bound = census_cli.matched_tally_bound_from_report(path)
        assert bound.withheld == frozenset()
        assert bound.unbounded is True


class TestTheBoundErrsTowardWithholding:
    """The direction property. Over-withholding costs a row the strong basis
    and reports a shortfall it does not have -- advisory, capped by 5.2.
    Under-withholding lets a row subtract starter objects it never matched,
    which HIDES a real loss. Only the first is acceptable."""

    @pytest.mark.parametrize("unattributed", [
        {"AFFIXES": 1},
        {"STEMS": 164},
        {"POS_INFLECTABLE_FEATS": 13},
        {"SOMETHING_NOBODY_HAS_NAMED_YET": 1},
    ])
    def test_every_unrecognised_category_declines_rather_than_guesses(
            self, tmp_path, unattributed):
        from gramtrans import census_cli
        path = _write(tmp_path, {"matched_to_source": _matched(
            {"PhPhoneme": 21}, complete=False, unattributed=unattributed)})
        bound = census_cli.matched_tally_bound_from_report(path)
        assert bound.unbounded is True, (
            "an unrecognised category was silently bounded: "
            + repr(sorted(bound.withheld)))

    def test_the_bound_never_names_a_class_no_category_could_be(self, tmp_path):
        """Whatever the bound contains, it is drawn from the two tables and
        nowhere else -- so it can never name a class the unattributed
        categories could not have been."""
        from gramtrans import census_cli
        from gramtrans.census_cli import (
            _AMBIGUOUS_IDENTITY_SKIP_CLASSES,
            identity_skip_class_table,
        )
        table, _ = identity_skip_class_table()
        permitted = set(table.values())
        for candidates in _AMBIGUOUS_IDENTITY_SKIP_CLASSES.values():
            permitted.update(candidates)
        path = _write(tmp_path, {"matched_to_source": _matched(
            {"PhPhoneme": 21}, complete=False,
            unattributed={"GRAM_CATEGORIES": 5, "INFLECTION_FEATURES": 5,
                          "VARIANT_TYPES": 1, "NATURAL_CLASSES": 3,
                          "COMPLEX_FORM_TYPES": 7})})
        bound = census_cli.matched_tally_bound_from_report(path)
        assert bound.withheld <= permitted


class TestTheBoundIsNotTheSkipBound:
    """The two signals are separate and must both be consulted. This pins the
    separation so a later refactor cannot quietly collapse them back into one
    global flag -- which is the defect T048f exists to remove."""

    def test_the_two_readers_are_independent(self, tmp_path):
        from gramtrans import census_cli
        # A report whose identity skips are entirely attributable, but whose
        # own tally left a bounded match unattributed.
        path = _write(tmp_path, {
            "skips": [{"category": "GRAM_CATEGORIES", "source_guid": "g-1",
                       "reason": "ALREADY_PRESENT_BY_GUID", "detail": "x"}],
            "matched_to_source": _matched(
                {"PhPhoneme": 21}, complete=False,
                unattributed={"INFLECTION_FEATURES": 5}),
        })
        skips = census_cli.identity_skips_from_report(path)
        bound = census_cli.matched_tally_bound_from_report(path)
        assert skips.unbounded is False
        assert bound.unbounded is False
        # Disjoint concerns, and the union is what the row gate must use.
        assert skips.withheld == frozenset()
        assert bound.withheld == frozenset(
            {"FsClosedFeature", "FsComplexFeature"})
        assert "PhPhoneme" not in (skips.withheld | bound.withheld)
