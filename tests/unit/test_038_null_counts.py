"""T099: the difference between "this project holds none" and "nobody counted".

WHAT WAS WRONG. `contracts/census-artifact.schema.json` has typed
`$defs.classRow.source_count` and `destination_count_total` as
`["integer", "null"]` from the start, with the meaning spelled out in the
`$comment`: "null only on a NOT_EVALUATED row where the class could not be
counted at all; a genuine zero is 0, never null". `models.ClassCensusRow`
declared `source_count: int`. Two consequences, in opposite directions, from one
narrowing:

  * `census_cli._row_for_entry` emitted `0 / 0` for every
    `excluded_not_measurable` class and said so in a note -- "The 0 counts are
    placeholders -- the schema's honest value is null". Measured on the Ngoreme
    pair, `MoForm` and `MoMorphSynAnalysis` carried `source_count 0`,
    `destination_count_total 0`, `difference 0` and `verdict_class
    NOT_EVALUATED`. A reader holding only the artifact could not tell those
    rows from a class the project genuinely holds none of.
  * `census_cli._report_unmeasurable` ABORTED the whole run for a class whose
    repository accessor did not resolve, on the stated grounds that "there is
    no honest row to write". The abort was loud in the console and silent in
    the record: no artifact, so nothing named the class afterwards.

WHY THESE TESTS ARE THE ONES. The narrowing itself was invisible because nothing
compared the model to the schema (`test_the_model_admits_every_type_the_schema_
does`), and the emitter's `if value is None: continue` would have silently
DROPPED three required keys the moment the model told the truth
(`test_a_null_count_is_emitted_as_null_not_omitted`) -- an honest row turned
into an invalid artifact. Both are structural: they fail on the defect's shape,
not on one corpus.

WHAT IS DELIBERATELY NOT HERE. No test requires a `not_evaluated_reason` on an
unresolved-accessor row. The reason vocabulary is CLOSED at 17 and none of its
three NOT_EVALUATED members means "the accessor did not resolve";
`ABSENT_BY_CONSTRUCTION` is the abstract-base case and would be a false
statement about a class whose repository merely drifted. Filed as T100.
"""

from __future__ import annotations

import json
import typing
from pathlib import Path

import pytest


def _schema() -> dict:
    root = Path(__file__).resolve().parents[2]
    path = (root / "specs" / "038-transfer-fidelity-gaps" / "contracts"
            / "census-artifact.schema.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _row(**overrides):
    from gramtrans.Lib import models

    kwargs = dict(
        object_class="MoForm",
        source_count=None,
        destination_count=None,
        starter_excluded=0,
        difference=None,
        explained=False,
        engine_can_create=False,
        out_of_scope=True,
        reasons=("ABSENT_BY_CONSTRUCTION",),
    )
    kwargs.update(overrides)
    return models.ClassCensusRow(**kwargs)


# ---------------------------------------------------------------------------
# The tripwire that was missing: model type vs schema type
# ---------------------------------------------------------------------------


class TestTheModelMatchesTheSchemasOwnTypes:
    """The defect was a NARROWING, and nothing in the tree compared the two."""

    @pytest.mark.parametrize(
        "internal,artifact_key",
        [("source_count", "source_count"),
         ("destination_count", "destination_count_total"),
         ("difference", "difference")],
    )
    def test_the_model_admits_every_type_the_schema_does(
            self, internal, artifact_key):
        """THE TEST THAT WOULD HAVE CAUGHT T099. The schema said nullable, the
        model said `int`, and the gap was recorded only in a code comment. A
        comment cannot fail."""
        from gramtrans.Lib import models

        prop = _schema()["$defs"]["classRow"]["properties"][artifact_key]
        assert "null" in prop["type"], (
            artifact_key + " is no longer nullable in the schema; this test is "
            "the wrong way round now")
        hints = typing.get_type_hints(models.ClassCensusRow)
        admitted = typing.get_args(hints[internal])
        assert type(None) in admitted, (
            "ClassCensusRow." + internal + " is " + repr(hints[internal])
            + " but $defs.classRow." + artifact_key + " is " + repr(prop["type"])
            + " -- the model cannot express the schema's own honest value, "
            "which is how a knowingly-false 0 got emitted for two classes")

    def test_the_emitter_knows_which_required_fields_may_be_null(self):
        """`CLASS_ROW_REQUIRED_NULLABLE_FIELDS` must be exactly the mapped
        fields the schema lists as required AND types nullable -- otherwise the
        emitter either drops a required key or emits a null the schema
        forbids."""
        from gramtrans.Lib import models

        class_row = _schema()["$defs"]["classRow"]
        required = set(class_row["required"])
        expected = {
            internal
            for internal, key in models.CLASS_CENSUS_ROW_ARTIFACT_FIELDS.items()
            if key is not None and key in required
            and "null" in class_row["properties"][key]["type"]
        }
        assert models.CLASS_ROW_REQUIRED_NULLABLE_FIELDS == expected


# ---------------------------------------------------------------------------
# What a null count obliges the row to say
# ---------------------------------------------------------------------------


class TestNullIsNotASmallerZero:

    def test_an_uncounted_row_carries_null_and_reads_not_evaluated(self):
        row = _row()
        assert row.source_count is None
        assert row.destination_count is None
        assert row.difference is None
        assert row.destination_count_net is None
        assert row.difference_raw is None
        assert row.verdict_class == "NOT_EVALUATED"

    def test_a_genuine_zero_is_still_zero_and_reads_matched(self):
        """The other half of the schema's rule, and the one a careless fix
        breaks: a class the project genuinely holds none of is 0/0 MATCHED, and
        must not be swept into null along with the uncountable ones."""
        row = _row(object_class="MoAffixProcess", source_count=0,
                   destination_count=0, difference=0, out_of_scope=False,
                   reasons=(), engine_can_create=True)
        assert row.verdict_class == "MATCHED"
        assert row.difference_raw == 0
        assert row.destination_count_net == 0

    def test_a_placeholder_zero_difference_over_null_counts_is_refused(self):
        """The exact shape of the defect, refused at construction.
        `verdict_class` reads 0 as MATCHED, so this is the one value that turns
        "nobody counted it" into "it agreed"."""
        with pytest.raises(ValueError, match="no difference"):
            _row(difference=0)

    def test_a_measured_row_may_not_withhold_its_difference(self):
        with pytest.raises(ValueError, match="owes"):
            _row(source_count=3, destination_count=3, difference=None,
                 out_of_scope=False, reasons=(), engine_can_create=True)

    def test_a_null_count_row_is_not_evaluated_whatever_the_caller_says(self):
        """The schema's "null only on a NOT_EVALUATED row" clause, from the
        direction it can actually be enforced. A caller that supplies a null
        count with `out_of_scope=False` and no reasons -- which is what an
        unresolved repository accessor looks like, since no member of the closed
        18-token vocabulary means "the accessor did not resolve" -- still gets a
        NOT_EVALUATED row. The clause is a CONSEQUENCE of the null difference,
        not a demand on the caller, and `_check_null_counts` re-asserts it so
        the two rules cannot drift apart."""
        row = _row(out_of_scope=False, reasons=(), engine_can_create=True)
        assert row.verdict_class == "NOT_EVALUATED"
        assert row.counts_pass is True

    def test_a_null_count_row_cannot_claim_to_be_explained(self):
        """An `accounted_for` line credits a quantity against a DIFFERENCE, and
        R-2 over-accounting is SKIPPED on a null difference
        (`census.unexplained_counts` returns (0, 0)), so nothing downstream
        would catch it."""
        with pytest.raises(ValueError, match="nothing for an explanation"):
            _row(explained=True, reasons=("ABSENT_BY_CONSTRUCTION",))

    def test_a_null_destination_may_not_publish_a_subtrahend(self):
        with pytest.raises(ValueError, match="did not happen"):
            _row(starter_excluded=4)

    def test_starter_excluded_itself_is_never_null(self):
        """The subtrahend has no honest null: 5.2 expresses an unknown
        subtraction as 0 on the `no_baseline` basis plus a failing verdict."""
        with pytest.raises(ValueError, match="must be an int"):
            _row(starter_excluded=None)

    def test_one_side_may_be_null_while_the_other_is_known(self):
        """Unmeasurability is a property of ONE project. Collapsing the two
        sides would report a source count as unknown when it is known."""
        row = _row(source_count=None, destination_count=7, out_of_scope=True,
                   reasons=("ABSENT_BY_CONSTRUCTION",))
        assert row.destination_count_net == 7
        assert row.difference_raw is None
        assert row.verdict_class == "NOT_EVALUATED"

    def test_a_null_difference_cannot_fail_a_gate_by_comparison(self):
        """`counts_pass` used to be `difference == 0 or explained`. `None == 0`
        is False, so without the guard an uncounted gate-relevant row would
        have FAILED on counts -- reporting a loss nobody measured."""
        row = _row(object_class="PhPhoneme", source_count=None,
                   destination_count=None, difference=None,
                   out_of_scope=False, reasons=("OUT_OF_SCOPE_CLASS",),
                   engine_can_create=True)
        assert row.verdict_class == "NOT_EVALUATED"
        assert row.counts_pass is True


# ---------------------------------------------------------------------------
# The emitter
# ---------------------------------------------------------------------------


class TestTheArtifactSaysNullOutLoud:

    def _entry(self, object_class="MoForm",
               in_class_list_via="excluded_not_measurable"):
        from gramtrans.Lib import census

        return census.ClassListEntry(
            object_class=object_class,
            in_class_list_via=in_class_list_via,
            gate_scope="advisory",
            engine_can_create=False,
            not_evaluated_reason="ABSENT_BY_CONSTRUCTION",
        )

    def test_a_null_count_is_emitted_as_null_not_omitted(self):
        """THE SECOND TEST THAT WOULD HAVE CAUGHT T099, one layer down.
        `class_row_artifact` skipped any mapped field whose value was None, on
        a comment asserting no REQUIRED field could be None -- true only while
        the model lied. All three of these are REQUIRED in `$defs.classRow`, so
        omitting them turns an honest row into an invalid artifact."""
        from gramtrans.Lib import census

        block = census.class_row_artifact(_row(), self._entry())
        for key in ("source_count", "destination_count_total", "difference",
                    "destination_count_net", "difference_raw"):
            assert key in block, key + " was dropped, not emitted as null"
            assert block[key] is None
        assert block["verdict_class"] == "NOT_EVALUATED"
        assert block["unexplained_shortfall"] == 0
        assert block["unexplained_surplus"] == 0

    def test_an_optional_property_is_still_omitted_when_none(self):
        """The distinction the name-based guard exists to preserve:
        `owning_feature_system` is OPTIONAL on an object that is
        `additionalProperties: false`, so a null there is a hard failure."""
        from gramtrans.Lib import census

        block = census.class_row_artifact(_row(), self._entry())
        assert "owning_feature_system" not in block

    def test_a_null_row_contributes_nothing_to_the_totals(self):
        """`build_totals` skips a null difference, so the gate quantity every
        phase reads is unchanged by the fix -- measured: `total_shortfall`
        70659 before and after on the Ngoreme pair."""
        from gramtrans.Lib import census

        block = census.class_row_artifact(_row(), self._entry())
        totals = census.build_totals([block])
        assert totals["total_shortfall"] == 0
        assert totals["total_surplus"] == 0
        assert totals["advisory_shortfall"] == 0
        assert totals["classes_not_evaluated"] == 1
        assert totals["classes_matched"] == 0


# ---------------------------------------------------------------------------
# `_row_for_entry`: which side goes null, and why
# ---------------------------------------------------------------------------


class TestRowForEntryNullsPerSide:

    def _entry(self, object_class, in_class_list_via="coverage_floor",
               reason=None):
        from gramtrans.Lib import census

        return census.ClassListEntry(
            object_class=object_class,
            in_class_list_via=in_class_list_via,
            gate_scope="advisory",
            engine_can_create=False,
            not_evaluated_reason=reason,
        )

    def _missing_baseline(self):
        from gramtrans.Lib import models

        return models.StarterBaseline.missing()

    def test_an_abstract_base_is_null_on_both_sides(self):
        from gramtrans import census_cli

        row, _kwargs = census_cli._row_for_entry(
            self._entry("MoForm", "excluded_not_measurable",
                        "ABSENT_BY_CONSTRUCTION"),
            {}, {}, self._missing_baseline(),
        )
        assert (row.source_count, row.destination_count) == (None, None)
        assert row.difference is None

    def test_the_note_no_longer_calls_the_counts_placeholders(self):
        """A note saying "the 0 counts are placeholders" was the artifact
        apologising for its own data. Deliberate wording change, journaled."""
        from gramtrans import census_cli

        _unused, kwargs = census_cli._row_for_entry(
            self._entry("MoForm", "excluded_not_measurable",
                        "ABSENT_BY_CONSTRUCTION"),
            {}, {}, self._missing_baseline(),
        )
        note = kwargs["notes"][0]
        assert "placeholder" not in note
        assert "null, not 0" in note

    def test_an_unresolved_accessor_nulls_only_the_project_it_failed_in(self):
        """The class is countable in the source and not in the destination. The
        source number is KNOWN and must survive."""
        from gramtrans import census_cli

        row, kwargs = census_cli._row_for_entry(
            self._entry("PhPhoneme"),
            {"PhPhoneme": 41}, {}, self._missing_baseline(),
            destination_unmeasurable=frozenset({"PhPhoneme"}),
            source_name="Src", destination_name="Dst",
        )
        assert row.source_count == 41
        assert row.destination_count is None
        assert row.difference is None
        assert row.verdict_class == "NOT_EVALUATED"
        assert any("'Dst'" in note for note in kwargs["notes"])
        assert not any("'Src'" in note for note in kwargs["notes"])

    def test_a_measured_class_absent_from_counts_still_raises(self):
        """The guard is on the unmeasurable SET, not on a `.get` default. A
        class missing from `counts` with no recorded reason is a bug in the
        counting pass, and a defaulted None would look exactly like an honest
        inability to count."""
        from gramtrans import census_cli

        with pytest.raises(KeyError):
            census_cli._row_for_entry(
                self._entry("PhPhoneme"), {}, {}, self._missing_baseline())


# ---------------------------------------------------------------------------
# The abort that became a row -- without becoming quiet
# ---------------------------------------------------------------------------


class _Counts:
    def __init__(self, unmeasurable, reasons):
        self.unmeasurable = tuple(unmeasurable)
        self.unresolved_accessors = dict(reasons)


class _Reading:
    def __init__(self, name, unmeasurable, reasons):
        self.name = name
        self.counts = _Counts(unmeasurable, reasons)


class TestTheUnresolvedAccessorIsReportedNotSwallowed:

    def _reading(self):
        return _Reading(
            "Dst", ("PhPhoneme",),
            {"PhPhoneme": "IPhPhonemeRepository could not be resolved"})

    def test_the_run_path_reports_every_accessor_and_does_not_raise(
            self, capsys):
        from gramtrans import census_cli

        entries = census_cli._print_unmeasurable(self._reading())
        assert len(entries) == 1
        assert entries[0]["class"] == "PhPhoneme"
        out = capsys.readouterr().out
        assert "PhPhoneme" in out
        assert "[FAIL]" in out
        assert "may not fail QUIETLY" in out

    def test_the_entries_drive_the_verdict_to_census_error(self):
        """The abort becoming a row is only acceptable because `errors[]`
        non-empty is CENSUS_ERROR on its own. Without this the change would be
        exactly the silencing T099 forbids."""
        from gramtrans.Lib import census

        entries = list(census.unmeasurable_errors(self._reading()))
        assert entries
        assert census.recompute_verdict({"errors": entries}) == "CENSUS_ERROR"
        assert census.exit_code_for("CENSUS_ERROR") == 7

    def test_capture_baseline_still_aborts(self):
        """A baseline document is a count MAP a later run SUBTRACTS, and
        `unmatched_starter` refuses to read an absent count as zero -- a null
        there would be subtracted as 0. There is also no `classes` array in a
        baseline for the row to go into."""
        from gramtrans import census_cli
        from gramtrans.Lib import census

        with pytest.raises(census.CensusError, match="subtracted as 0"):
            census_cli._report_unmeasurable(self._reading())
