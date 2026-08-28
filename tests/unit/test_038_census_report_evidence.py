"""Feature 038 -- the two census reads that nothing performed.

Both gaps below were found by LIVE measurement, not by review, and each one made
a gate unsatisfiable on plumbing rather than on fidelity.

PIECE 1 -- `match_basis` was never emitted by a live run.
`census.class_row_artifact` has accepted `match_basis=` since T019 and
`census_cli` never passed it, so `census._phase_3` -- which reads
`_row_by_class(artifact, "PartOfSpeech")["match_basis"]["enriched"]` and fails
when it is falsy -- read `None` on EVERY live run and reported "PartOfSpeech
match_basis.enriched is None, not > 0". P3 was therefore unsatisfiable no matter
how well enrichment worked, and T048 is a live P3 gate run.

The derivation is the hard part. `enriched` MUST come from
`enrichments[].object_class`, the only class-keyed enrichment surface in the run
report. The tempting neighbour, `enriched_counts`, is keyed by
`GrammarCategory`, which is not 1:1 with an LCM class for the affix and MSA
categories -- the same attribution trap `matched_by_class_from_report` already
refuses. And `enriched` is NOT a summand: `census.MATCH_BASIS_SUMMANDS` is
`(identity, natural_key, created_new, unmatched_reported)` precisely because
`enriched` is a SUBSET of the first two, so adding it would double-count every
enriched object and turn a correct run into an invariant-11 mismatch.

PIECE 2 -- a REPORTED drop read as an unexplained loss.
`accounted_for=()` was `class_row_artifact`'s default and the only occurrence of
the parameter in the codebase; `transfer_run_block` read `run_id`,
`report_path`, `mode`, `started_at` and `per_category` and never touched
`dropped_items`. Measured on run `GT-20260820-002806`: `MoStemMsa` 164 -> 162,
`difference -2`, `unexplained_shortfall: 2` -- beside two `DroppedItemRecord`s
naming those two objects by GUID. The drop WAS reported; the census could not
read it, so SC-005's "either zero or accounted for by a line in the run report"
was measuring the reader, not the run.

The two traps this file pins:

- The class of a DROPPED OBJECT is `item_name`, not `owner_kind`. The MSA drops
  are recorded against `owner_kind="LexEntry"`, so grouping by `owner_kind`
  would pay down a shortfall on a class that lost nothing.
- Most drops are dropped REFERENCES, not missing objects. The same run reported
  169 `MoForm.MorphTypeRA -> "stem"` drops; the `MoMorphType` named "stem" is
  still in the destination and no class's object count moved. Crediting them
  would explain away a loss that did not happen -- R-2 `CENSUS_ERROR`.
"""

from __future__ import annotations

import json

from gramtrans import census_cli
from gramtrans.Lib import census, models

RUN_ID = "GT-20260820-002806"

#: The two GUIDs the live run actually named. Kept verbatim so a future reader
#: can grep them out of `scratchpad/038_census/t038-run-report.json`.
LIVE_MSA_GUIDS = (
    "e746ab93-39a7-432f-8a94-972553c31388",
    "8aa67141-4b32-43f3-ac6c-db0f67ef09cc",
)

#: The live reason string, verbatim from `Lib/categories.py._resolve_or_none`.
LIVE_MSA_REASON = (
    "MoStemMsa.PartOfSpeechRA (POS guid=empty) is empty on source -- MSA not "
    "transferred; the sense keeps its entry and allomorphs but loses its "
    "part-of-speech analysis"
)


def write_report(tmp_path, payload) -> "object":
    body = {"context": {"run_id": RUN_ID}}
    body.update(payload)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def enrichment(object_class, *, is_empty=False, guid="s-1"):
    """One `enrichments[]` record, shaped as `report._enrichment_json` emits."""
    return {
        "object_class": object_class,
        "source_guid": guid,
        "target_guid": "t-" + guid,
        "label": object_class,
        "was_created": False,
        "is_empty": is_empty,
        "fields_updated": [] if is_empty else ["Name"],
        "collections": [],
    }


def drop(item_name, *, owner_kind="LexEntry", field_name="MorphoSyntaxAnalysesOC",
         item_guid="g-1", reason=LIVE_MSA_REASON):
    """One `dropped_items[]` record, shaped as `report.py:1103-1113` emits."""
    return {
        "owner_kind": owner_kind,
        "owner_guid": "owner-1",
        "owner_label": "headword",
        "field_name": field_name,
        "item_name": item_name,
        "item_guid": item_guid,
        "reason": reason,
    }


def entry(object_class="MoStemMsa", owner=None, gate_scope="required"):
    return census.ClassListEntry(
        object_class=object_class,
        in_class_list_via="coverage_floor",
        gate_scope=gate_scope,
        engine_can_create=True,
        owning_feature_system=owner,
    )


def baseline_for(counts):
    return models.StarterBaseline(
        kind=models.StarterBaselineKind.PRE_TRANSFER_CENSUS,
        captured_from="Tgt",
        flex_version="9.3.10",
        captured_at="2026-08-20T00:28:06",
        entries=tuple(
            models.StarterBaselineEntry(object_class=cls, count=n)
            for cls, n in counts.items()
        ),
    )


def emit(object_class, source, destination, *, evidence=None, owner=None,
         baseline_count=0, gate_scope="required"):
    """One emitted artifact row, through the REAL emitter.

    Deliberately end-to-end over `_row_for_entry` -> `class_row_artifact`: the
    defect being fixed was a missing argument at exactly that seam, so a test
    that constructs the artifact block by hand could not have caught it.
    """
    row_entry = entry(object_class, owner=owner, gate_scope=gate_scope)
    row, kwargs = census_cli._row_for_entry(
        row_entry,
        {object_class: source},
        {object_class: destination},
        baseline_for({row_entry.row_key: baseline_count}),
        {object_class: 0},
        True,
        evidence=evidence,
    )
    return census.class_row_artifact(row, row_entry, **kwargs)


# ===========================================================================
# PIECE 1 -- the enrichment tally, and only from the class-keyed surface
# ===========================================================================


class TestCensusReadsTheEnrichmentTally:
    def test_counts_per_lcm_class_from_object_class(self, tmp_path):
        path = write_report(tmp_path, {"enrichments": [
            enrichment("PartOfSpeech", guid="a"),
            enrichment("PartOfSpeech", guid="b"),
            enrichment("MoStemMsa", guid="c"),
        ]})
        per_class, measured = census_cli.enriched_by_class_from_report(path)

        assert per_class == {"PartOfSpeech": 2, "MoStemMsa": 1}
        assert measured is True

    def test_enriched_counts_is_not_the_surface(self, tmp_path):
        """`enriched_counts` is keyed by `GrammarCategory`, which is not 1:1
        with an LCM class -- crediting a category total to a class row would
        attribute an enrichment to a class the run may never have touched."""
        path = write_report(tmp_path, {
            "enriched_counts": {"PARTS_OF_SPEECH": 7, "AFFIXES": 3},
        })
        per_class, measured = census_cli.enriched_by_class_from_report(path)

        assert per_class == {}
        assert measured is False, (
            "a category-keyed counter is not evidence about any LCM class"
        )

    def test_an_is_empty_record_is_not_an_enrichment(self, tmp_path):
        """`is_empty` is 'nothing gained AND nothing lost' -- the one case
        data-model.md 7 lets degrade to a Skip. Counting it would let the
        whole-object skip P3 exists to catch satisfy P3."""
        path = write_report(tmp_path, {"enrichments": [
            enrichment("PartOfSpeech", guid="a", is_empty=True),
            enrichment("PartOfSpeech", guid="b", is_empty=False),
        ]})
        per_class, _ = census_cli.enriched_by_class_from_report(path)

        assert per_class == {"PartOfSpeech": 1}

    def test_an_absent_list_is_no_evidence_not_a_zero(self, tmp_path):
        path = write_report(tmp_path, {})
        per_class, measured = census_cli.enriched_by_class_from_report(path)

        assert (per_class, measured) == ({}, False)

    def test_a_present_empty_list_is_a_proven_zero(self, tmp_path):
        """The lists in a run report are never capped, so a class absent from a
        PRESENT list gained nothing -- a measured 0, distinct from unknown."""
        path = write_report(tmp_path, {"enrichments": []})
        evidence = census_cli.read_report_evidence(path, ("PartOfSpeech",))

        assert evidence.enriched_measured is True
        assert evidence.enriched_for("PartOfSpeech") == 0

    def test_unmeasured_reports_none_never_zero(self, tmp_path):
        evidence = census_cli.read_report_evidence(
            write_report(tmp_path, {}), ("PartOfSpeech",))

        assert evidence.enriched_for("PartOfSpeech") is None


class TestCensusRowCarriesMatchBasis:
    """The missing argument itself. `census_cli` called `class_row_artifact`
    without `match_basis=`, so no live artifact had the block at all."""

    def _evidence(self, tmp_path, records):
        return census_cli.read_report_evidence(
            write_report(tmp_path, {"enrichments": records}),
            ("PartOfSpeech", "MoStemMsa", "FsFeatStrucType"))

    def test_a_live_row_now_carries_the_block(self, tmp_path):
        row = emit("PartOfSpeech", 30, 30, evidence=self._evidence(
            tmp_path, [enrichment("PartOfSpeech", guid="a"),
                       enrichment("PartOfSpeech", guid="b"),
                       enrichment("PartOfSpeech", guid="c")]))

        assert row["match_basis"]["basis_source"] == "run_report"
        assert row["match_basis"]["enriched"] == 3

    def test_no_run_report_means_no_block(self):
        row = emit("PartOfSpeech", 30, 30, evidence=None)

        assert "match_basis" not in row, (
            "a census run given no report has nothing to say about the basis; "
            "an empty block would look like a measurement"
        )

    def test_an_unmeasured_tally_is_null_and_said_out_loud(self, tmp_path):
        evidence = census_cli.read_report_evidence(
            write_report(tmp_path, {}), ("PartOfSpeech",))
        row = emit("PartOfSpeech", 30, 30, evidence=evidence)

        assert row["match_basis"] == {"basis_source": "run_report"}
        assert "enriched" not in row["match_basis"]
        assert any("enriched is null" in n for n in row["notes"])

    def test_a_split_row_withholds_the_tally(self, tmp_path):
        """A1: an enrichment record names a CLASS, not a feature system, so
        crediting one to a split half is unattributable and crediting it to
        both halves doubles it."""
        row = emit("FsFeatStrucType", 5, 5, owner="phonology",
                   evidence=self._evidence(
                       tmp_path, [enrichment("FsFeatStrucType")]))

        assert row["match_basis"] == {"basis_source": "run_report"}

    def test_enriched_is_not_a_summand(self, tmp_path):
        """The invariant this piece must not disturb. `enriched` is a SUBSET of
        identity + natural_key; adding it to the sum would double-count every
        enriched object and fail a correct run on invariant 11."""
        assert "enriched" not in census.MATCH_BASIS_SUMMANDS
        assert census.MATCH_BASIS_SUMMANDS == (
            "identity", "natural_key", "created_new", "unmatched_reported")

        basis = census.MatchBasis(basis_source="run_report", enriched=3)
        assert basis.summed is None, (
            "with every summand unknown the sum is unknown -- `enriched` must "
            "not stand in for one"
        )
        assert census.match_basis_sum_error("PartOfSpeech", basis, 30) is None

    def test_the_emitted_row_trips_no_invariant(self, tmp_path):
        row = emit("PartOfSpeech", 30, 30, evidence=self._evidence(
            tmp_path, [enrichment("PartOfSpeech")]))
        failures = census.validate_artifact({"classes": [row]})

        assert not [f for f in failures if "invariant 11" in f]
        assert not [f for f in failures if "match_basis" in f]

    def test_phase_3_is_now_satisfiable_by_a_live_row(self, tmp_path):
        """The whole point of PIECE 1. `census._phase_3` reads
        `row["match_basis"]["enriched"]` and fails when it is falsy; before this
        change a live run always gave it `None`."""
        enriched_row = emit("PartOfSpeech", 30, 30, evidence=self._evidence(
            tmp_path, [enrichment("PartOfSpeech", guid="a"),
                       enrichment("PartOfSpeech", guid="b")]))
        failures = census._phase_3({"classes": [enriched_row]})

        assert not [f for f in failures if "match_basis.enriched" in f]

    def test_phase_3_still_fails_when_nothing_was_enriched(self, tmp_path):
        """The gate must stay a gate: a proven zero fails P3 exactly as an
        absent tally did, and for the right reason this time."""
        row = emit("PartOfSpeech", 30, 30,
                   evidence=self._evidence(tmp_path, []))
        failures = census._phase_3({"classes": [row]})

        assert [f for f in failures if "match_basis.enriched" in f]


# ===========================================================================
# PIECE 2 -- a reported drop is accounting
# ===========================================================================


class TestCensusReadsReportedDrops:
    def test_grouped_by_item_name_not_owner_kind(self, tmp_path):
        """`owner_kind` is the OWNER's class. The live MSA drops are recorded
        against `LexEntry`, which lost nothing."""
        path = write_report(tmp_path, {"dropped_items": [
            drop("MoStemMsa", item_guid=LIVE_MSA_GUIDS[0]),
            drop("MoStemMsa", item_guid=LIVE_MSA_GUIDS[1]),
        ]})
        grouped = census_cli.dropped_by_class_from_report(
            path, ("MoStemMsa", "LexEntry"))

        assert set(grouped) == {"MoStemMsa"}
        (token, ref), = grouped["MoStemMsa"]
        assert token == census_cli.SOURCE_REFERENT_ABSENT_TOKEN
        assert ref.kind == "dropped_item"
        assert ref.count_in_report == 2
        assert ref.record_ids == LIVE_MSA_GUIDS
        assert ref.run_id == RUN_ID

    def test_a_dropped_reference_is_not_a_missing_object(self, tmp_path):
        """169 of the live run's 401 drops are `MoForm.MorphTypeRA -> "stem"`.
        The `MoMorphType` named "stem" is still in the destination; no class's
        object count moved. Crediting these would trip R-2."""
        path = write_report(tmp_path, {"dropped_items": [
            drop("stem", owner_kind="MoForm", field_name="MorphTypeRA",
                 reason="shared-default diverged"),
            drop("prefix", owner_kind="MoForm", field_name="MorphTypeRA",
                 reason="shared-default diverged"),
        ]})
        grouped = census_cli.dropped_by_class_from_report(
            path, ("MoForm", "MoMorphType", "MoStemMsa"))

        assert grouped == {}

    def test_an_unclassifiable_reason_yields_no_line(self, tmp_path):
        """FR-013 has no `OTHER`. Unexplained is the ABSENCE of a line, and a
        catch-all token would launder an unreadable drop into accounting."""
        path = write_report(tmp_path, {"dropped_items": [
            drop("MoStemMsa", reason="something nobody has classified yet"),
        ]})
        grouped = census_cli.dropped_by_class_from_report(path, ("MoStemMsa",))

        assert grouped == {}
        assert census_cli.drop_reason_token("something new") is None

    def test_the_unreproducible_subclass_reason_maps_to_its_own_token(
            self, tmp_path):
        path = write_report(tmp_path, {"dropped_items": [
            drop("MoStemMsa",
                 reason="MSA subclass MoStemMsa is not reproducible by this "
                        "engine (NEEDS_MANUAL) -- sense left without an MSA"),
        ]})
        grouped = census_cli.dropped_by_class_from_report(path, ("MoStemMsa",))

        (token, _), = grouped["MoStemMsa"]
        assert token == "UNSUPPORTED_SUBTYPE"

    def test_a_malformed_run_id_is_omitted_not_written_through(self, tmp_path):
        """`reportRef.run_id` is `^GT-\\d{8}-\\d{6}$` and optional; a malformed
        value would cost schema validity of the whole artifact."""
        path = tmp_path / "report.json"
        path.write_text(json.dumps({
            "context": {"run_id": "not-a-run-id"},
            "dropped_items": [drop("MoStemMsa")],
        }), encoding="utf-8")
        grouped = census_cli.dropped_by_class_from_report(path, ("MoStemMsa",))

        (_, ref), = grouped["MoStemMsa"]
        assert ref.run_id == ""

    def test_an_absent_dropped_items_key_is_not_an_error(self, tmp_path):
        assert census_cli.dropped_by_class_from_report(
            write_report(tmp_path, {}), ("MoStemMsa",)) == {}


class TestCensusAccountsForReportedDrops:
    """The row-level payoff, on the live numbers."""

    def _evidence(self, tmp_path, records, classes=("MoStemMsa",)):
        return census_cli.read_report_evidence(
            write_report(tmp_path, {"dropped_items": records}), classes)

    def test_the_live_mostemmsa_shortfall_becomes_accounted(self, tmp_path):
        """Run GT-20260820-002806: 164 -> 162, `unexplained_shortfall: 2`
        beside two DroppedItemRecords naming those exact objects."""
        row = emit("MoStemMsa", 164, 162, evidence=self._evidence(
            tmp_path, [drop("MoStemMsa", item_guid=LIVE_MSA_GUIDS[0]),
                       drop("MoStemMsa", item_guid=LIVE_MSA_GUIDS[1])]))

        assert row["difference"] == -2
        assert row["unexplained_shortfall"] == 0
        assert row["unexplained_surplus"] == 0
        assert row["verdict_class"] == "SHORTFALL", (
            "accounting does not change WHAT HAPPENED -- the row still reports "
            "a shortfall; it changes whether the run's verdict may be "
            "CENSUS_ACCOUNTED instead of UNEXPLAINED_SHORTFALL"
        )
        line, = row["accounted_for"]
        assert line == {
            "reason": census_cli.SOURCE_REFERENT_ABSENT_TOKEN,
            "count": 2,
            "direction": "shortfall",
            "report_ref": {
                "kind": "dropped_item",
                "count_in_report": 2,
                "run_id": RUN_ID,
                "report_path": line["report_ref"]["report_path"],
                "record_ids": list(LIVE_MSA_GUIDS),
            },
            "detail": census_cli.SOURCE_REFERENT_ABSENT_DETAIL,
        }

    def test_the_side_of_the_transfer_is_stated_in_the_artifact(self, tmp_path):
        """Was `test_the_provisional_token_is_stated_in_the_artifact` (T096).

        It used to pin the SUBSTITUTION -- `DEPENDENCY_UNRESOLVED` plus a
        `PROVISIONAL TOKEN` detail -- because the closed vocabulary had no
        member for "the required referent was absent ON THE SOURCE". Contract
        commit b2cb356 added `SOURCE_REFERENT_ABSENT`, so what must now be
        legible to a reviewer holding only the artifact is not an apology for
        the wrong word but WHICH SIDE of the transfer the referent was missing
        from -- and the detail must NOT still claim a substitution that no
        longer happens."""
        row = emit("MoStemMsa", 164, 163, evidence=self._evidence(
            tmp_path, [drop("MoStemMsa")]))
        line, = row["accounted_for"]

        assert line["reason"] == "SOURCE_REFERENT_ABSENT"
        assert "absent ON THE SOURCE" in line["detail"]
        assert "PROVISIONAL" not in line["detail"]

    def test_over_accounting_is_capped_not_claimed(self, tmp_path):
        """R-2: the census must not explain away more than happened. Five
        reported drops against a 2-object shortfall claim 2, and the
        `report_ref` still names all five so R-1 has real evidence."""
        row = emit("MoStemMsa", 164, 162, evidence=self._evidence(
            tmp_path, [drop("MoStemMsa", item_guid="g%d" % i)
                       for i in range(5)]))
        line, = row["accounted_for"]

        assert line["count"] == 2
        assert line["report_ref"]["count_in_report"] == 5
        assert row["unexplained_shortfall"] == 0
        assert "CLAIM CAPPED" in line["detail"]
        assert any("R-2" in n for n in row["notes"])
        assert not [f for f in census.validate_artifact({"classes": [row]})
                    if "R-2" in f or "R-1" in f]

    def test_a_drop_never_pays_down_a_surplus(self, tmp_path):
        """R-3. A dropped object cannot explain an over-creation, and a MATCHED
        row that also reports a drop is a real finding an accounting line would
        hide."""
        surplus = emit("MoStemMsa", 160, 164, evidence=self._evidence(
            tmp_path, [drop("MoStemMsa")]))
        matched = emit("MoStemMsa", 164, 164, evidence=self._evidence(
            tmp_path, [drop("MoStemMsa")]))

        assert surplus["accounted_for"] == []
        assert surplus["unexplained_surplus"] == 4
        assert matched["accounted_for"] == []
        assert matched["verdict_class"] == "MATCHED"

    def test_a_split_row_is_never_credited(self, tmp_path):
        """A1: a `dropped_items` record names a class, not a feature system.
        Crediting one half is unattributable; crediting both doubles it."""
        row = emit("FsFeatStrucType", 5, 4, owner="phonology",
                   evidence=self._evidence(
                       tmp_path, [drop("FsFeatStrucType")],
                       classes=("FsFeatStrucType",)))

        assert row["accounted_for"] == []
        assert row["unexplained_shortfall"] == 1

    def test_two_reasons_on_one_class_are_two_lines(self, tmp_path):
        row = emit("MoStemMsa", 164, 162, evidence=self._evidence(
            tmp_path, [
                drop("MoStemMsa", item_guid="a"),
                drop("MoStemMsa", item_guid="b",
                     reason="MSA subclass MoStemMsa is not reproducible by "
                            "this engine (NEEDS_MANUAL)"),
            ]))

        # `drop()`'s default reason is `LIVE_MSA_REASON` ("is empty on
        # source"), so line 1 is the SOURCE-side token. It read
        # `DEPENDENCY_UNRESOLVED` until T096, when the contract's
        # `SOURCE_REFERENT_ABSENT` replaced the least-wrong substitute.
        assert sorted(line["reason"] for line in row["accounted_for"]) == [
            "SOURCE_REFERENT_ABSENT", "UNSUPPORTED_SUBTYPE"]
        assert sum(line["count"] for line in row["accounted_for"]) == 2
        assert row["unexplained_shortfall"] == 0

    def test_no_report_leaves_the_shortfall_unexplained(self):
        row = emit("MoStemMsa", 164, 162, evidence=None)

        assert row["accounted_for"] == []
        assert row["unexplained_shortfall"] == 2


class TestCensusVocabularyGapIsNamedNotHidden:
    """The blocker this work surfaced rather than papered over -- now closed.

    `fidelity-census.md` 7.1's enum is CLOSED and, until contract commit
    b2cb356, had no token for "the source referent is legitimately absent and
    the engine required it". Every candidate was wrong for a different reason,
    and the contract is a spec artifact this module may not edit -- so the
    substitution was a named constant and this class was the tripwire that
    would fire when the contract closed the gap. It fired (T096), by way of a
    rebase rather than a live run. The tests below now guard the OTHER
    direction: that nobody regresses to the substitute.
    """

    def test_the_token_is_inside_the_closed_vocabulary(self):
        assert (census_cli.SOURCE_REFERENT_ABSENT_TOKEN
                in census.REASON_TOKENS)

    def test_no_invented_token_leaks_into_the_artifact(self):
        for _, token in census_cli.DROP_REASON_TOKENS:
            assert token in census.REASON_TOKENS, (
                "there is no 18th token: an unclassifiable drop must produce "
                "NO line, never a new reason"
            )

    def test_the_contract_token_is_used_not_the_least_wrong_substitute(self):
        """Was `test_the_substitution_is_flagged_for_the_contract`, which
        pinned `== "DEPENDENCY_UNRESOLVED"` and required the word PROVISIONAL
        in the detail. Both pins are now backwards."""
        assert census_cli.SOURCE_REFERENT_ABSENT_TOKEN == "SOURCE_REFERENT_ABSENT"
        assert "PROVISIONAL" not in census_cli.SOURCE_REFERENT_ABSENT_DETAIL
        assert "fidelity-census.md" in census_cli.SOURCE_REFERENT_ABSENT_DETAIL

    def test_the_two_sides_of_the_transfer_no_longer_collide(self):
        """The substitute's real cost. While `SOURCE_REFERENT_ABSENT_TOKEN`
        held `"DEPENDENCY_UNRESOLVED"`, both rows of `DROP_REASON_TOKENS` that
        classify a missing referent yielded the SAME token -- so source-side
        and destination-side losses grouped into ONE accounting line per class
        and could not be told apart in the artifact."""
        by_needle = dict(census_cli.DROP_REASON_TOKENS)
        assert by_needle["is empty on source"] == "SOURCE_REFERENT_ABSENT"
        assert by_needle["not resolvable in target"] == "DEPENDENCY_UNRESOLVED"
        assert (by_needle["is empty on source"]
                != by_needle["not resolvable in target"])

    def test_no_needle_shadows_another(self):
        """`drop_reason_token` returns the FIRST match, so a needle that is a
        substring of another would make the later row unreachable."""
        needles = [n for n, _ in census_cli.DROP_REASON_TOKENS]
        for i, outer in enumerate(needles):
            for j, inner in enumerate(needles):
                if i != j:
                    assert inner not in outer, (inner, outer)

    def test_a_source_side_drop_classifies_to_the_source_side_token(self):
        """End to end over the live reason string this feature measured."""
        assert (census_cli.drop_reason_token(LIVE_MSA_REASON)
                == "SOURCE_REFERENT_ABSENT")
        assert (census_cli.drop_reason_token(
            "MoForm.MorphTypeRA not resolvable in target")
            == "DEPENDENCY_UNRESOLVED")

    def test_a_reported_reference_drop_needs_no_token(self, tmp_path):
        """Why the gap is narrow: the 169 MorphTypeRA drops need no vocabulary
        at all, because they are not object losses and must not be accounted."""
        grouped = census_cli.dropped_by_class_from_report(
            write_report(tmp_path, {"dropped_items": [
                drop("stem", owner_kind="MoForm", field_name="MorphTypeRA",
                     reason="MoForm.MorphTypeRA not resolvable in target"),
            ]}), ("MoForm", "MoMorphType"))

        assert grouped == {}, (
            "the class filter, not the vocabulary, is what keeps a dropped "
            "reference out of the accounting"
        )


# ===========================================================================
# PIECE 3 (T087) -- a loss that IS reported, on a surface nothing read
#
# The third instance of this file's shape and the narrowest. The 6 condition-4
# `MoAffixProcess` rules of run GT-20260821-020541 are reported TWICE -- a
# `DroppedItemRecord` and a `ProcessRuleTransferRecord` with
# `reproduced=False` and a non-empty `not_reproducible_reason` -- and the
# census still scored the row `unexplained_shortfall: 6` with an empty
# `accounted_for`, because `read_report_evidence` read `dropped_items` only
# and no needle in `DROP_REASON_TOKENS` matches what
# `_reproduce_affix_process` writes.
#
# The direction matters. Piece 2's defect inflated a real loss into an
# unexplained one; this one inflates a NAMED, DELIBERATE deferral into an
# unaccounted loss, which is the direction 5.2's cap rationale says an
# instrument must not be wrong in. A report that cries loss where the loss was
# announced teaches the reader to stop reading it.
# ===========================================================================

PROCESS_RULE_RUN = "GT-20260821-020541"

#: The live reason, verbatim from `_run_reports/038-phase6-mbugwe-report.json`
#: (rule `fda9c04e-...`). Kept whole rather than abbreviated because the
#: classification is a substring match and a paraphrase would test the
#: paraphrase.
LIVE_PROCESS_RULE_REASON = (
    "MoAffixProcess fda9c04e-e71b-43ed-b4a1-c977610fa3b9 input member 0 "
    "(PhSequenceContext) references PhSimpleContextNC "
    "6464f7f4-1405-4427-a397-983ddb0b06fc at position 0, which this rule does "
    "NOT own -- it belongs to the shared project-level PhPhonData.ContextsOS "
    "and is absent from the destination. The rule is not transferred until "
    "that closure lands; a partly-filled MembersRS is not an acceptable "
    "outcome (FR-023/FR-024/FR-025, create-path contract condition 4)"
)

LIVE_RULE_GUID = "fda9c04e-e71b-43ed-b4a1-c977610fa3b9"


def process_rule(source_guid, *, reproduced=False,
                 reason=LIVE_PROCESS_RULE_REASON):
    """One `process_rules[]` record, shaped as the live report emits."""
    return {
        "source_guid": source_guid,
        "target_guid": ("t-" + source_guid) if reproduced else None,
        "reproduced": reproduced,
        "not_reproducible_reason": None if reproduced else reason,
        "input_contexts": [],
        "output_steps": [],
        "reference_decisions": [],
    }


def rule_drop(item_guid, *, reason=LIVE_PROCESS_RULE_REASON):
    return drop("MoAffixProcess", owner_kind="MoAffixProcess",
                field_name="InputOS", item_guid=item_guid, reason=reason)


def rule_report(tmp_path, rules, drops):
    """A report carrying BOTH surfaces, which is the only shape that can be
    credited -- see `process_rules_by_class_from_report`."""
    body = {
        "context": {"run_id": PROCESS_RULE_RUN},
        "process_rules": rules,
        "dropped_items": drops,
    }
    path = tmp_path / "rule-report.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


class TestTheProcessRuleSurfaceIsRead:
    def test_a_corroborated_non_reproduction_is_classified(self, tmp_path):
        grouped = census_cli.process_rules_by_class_from_report(
            rule_report(tmp_path, [process_rule(LIVE_RULE_GUID)],
                        [rule_drop(LIVE_RULE_GUID)]),
            ("MoAffixProcess",))

        (token, ref, detail), = grouped["MoAffixProcess"]
        assert token == "DEPENDENCY_UNRESOLVED"
        assert ref.kind == "dropped_item"
        assert ref.count_in_report == 1
        assert ref.run_id == PROCESS_RULE_RUN
        assert ref.record_ids == (LIVE_RULE_GUID,)
        assert "ProcessRuleTransferRecord" in detail
        assert "is absent from the destination" in detail

    def test_a_reproduced_rule_is_not_a_loss(self, tmp_path):
        assert census_cli.process_rules_by_class_from_report(
            rule_report(tmp_path,
                        [process_rule(LIVE_RULE_GUID, reproduced=True)], []),
            ("MoAffixProcess",)) == {}

    def test_an_uncorroborated_record_is_not_credited(self, tmp_path):
        """A `ProcessRuleTransferRecord` with no paired `DroppedItemRecord`.
        Two surfaces are available, so requiring both is the strongest claim
        the evidence supports -- and a producer that writes one without the
        other is a bug this must not absorb."""
        assert census_cli.process_rules_by_class_from_report(
            rule_report(tmp_path, [process_rule(LIVE_RULE_GUID)], []),
            ("MoAffixProcess",)) == {}

    def test_a_reason_that_drifted_between_surfaces_is_not_credited(
            self, tmp_path):
        """Verbatim agreement, not merely same-GUID agreement. If the two
        reasons disagree the run is describing one event two ways and the
        census may not pick a winner."""
        assert census_cli.process_rules_by_class_from_report(
            rule_report(
                tmp_path, [process_rule(LIVE_RULE_GUID)],
                [rule_drop(LIVE_RULE_GUID,
                           reason=LIVE_PROCESS_RULE_REASON + " (edited)")]),
            ("MoAffixProcess",)) == {}

    def test_a_drop_on_another_guid_does_not_corroborate(self, tmp_path):
        assert census_cli.process_rules_by_class_from_report(
            rule_report(tmp_path, [process_rule(LIVE_RULE_GUID)],
                        [rule_drop("some-other-guid")]),
            ("MoAffixProcess",)) == {}

    def test_an_unclassifiable_reason_yields_no_line(self, tmp_path):
        """FR-013 again: unclassified is an ABSENT line, never an 18th token.
        The source-side empty-MembersRS skips land here."""
        reason = ("MoAffixProcess " + LIVE_RULE_GUID
                  + " has an empty MembersRS in the SOURCE")
        assert census_cli.process_rules_by_class_from_report(
            rule_report(tmp_path,
                        [process_rule(LIVE_RULE_GUID, reason=reason)],
                        [rule_drop(LIVE_RULE_GUID, reason=reason)]),
            ("MoAffixProcess",)) == {}

    def test_the_class_filter_still_governs(self, tmp_path):
        path = rule_report(tmp_path, [process_rule(LIVE_RULE_GUID)],
                           [rule_drop(LIVE_RULE_GUID)])
        assert census_cli.process_rules_by_class_from_report(
            path, ("MoStemMsa",)) == {}

    def test_an_absent_process_rules_key_is_not_an_error(self, tmp_path):
        assert census_cli.process_rules_by_class_from_report(
            write_report(tmp_path, {}), ("MoAffixProcess",)) == {}


class TestTheTwoTablesDoNotMerge:
    """Why `PROCESS_RULE_REASON_TOKENS` is separate from
    `DROP_REASON_TOKENS` -- asserted, rather than asserted in a comment."""

    def test_no_general_needle_matches_a_process_rule_reason(self):
        """The disjointness the no-double-credit argument rests on. If a
        general needle ever matched, `dropped_by_class_from_report` would
        classify the SAME drop on its own uncorroborated path and the merge
        would credit one lost rule as two accounted objects (R-2)."""
        assert census_cli.drop_reason_token(LIVE_PROCESS_RULE_REASON) is None

    def test_no_process_needle_matches_the_general_live_reason(self):
        assert census_cli.process_rule_reason_token(LIVE_MSA_REASON) is None

    def test_every_process_token_is_inside_the_closed_vocabulary(self):
        for _, token in census_cli.PROCESS_RULE_REASON_TOKENS:
            assert token in census.REASON_TOKENS

    def test_no_process_needle_shadows_another(self):
        needles = [n for n, _ in census_cli.PROCESS_RULE_REASON_TOKENS]
        for i, outer in enumerate(needles):
            for j, inner in enumerate(needles):
                if i != j:
                    assert inner not in outer, (inner, outer)

    def test_the_needle_is_returned_so_the_detail_can_quote_it(self):
        needle, token = census_cli.process_rule_reason_match(
            LIVE_PROCESS_RULE_REASON)
        assert needle == "is absent from the destination"
        assert token == "DEPENDENCY_UNRESOLVED"
        assert census_cli.process_rule_reason_match("nothing here") is None

    def test_a_non_string_reason_is_none_not_a_crash(self):
        assert census_cli.process_rule_reason_token(None) is None
        assert census_cli.process_rule_reason_match(42) is None


class TestTheProcessRuleShortfallBecomesAccounted:
    """The row-level payoff, on the live 6."""

    def _evidence(self, tmp_path, n):
        guids = ["rule-%d" % i for i in range(n)]
        return census_cli.read_report_evidence(
            rule_report(tmp_path, [process_rule(g) for g in guids],
                        [rule_drop(g) for g in guids]),
            ("MoAffixProcess",))

    def test_the_live_six_are_accounted_not_unexplained(self, tmp_path):
        """Run GT-20260821-020541: 18 -> 12, `difference -6`, and 6 rules
        reported twice each. Before this piece the row read
        `unexplained_shortfall: 6` with `accounted_for: []`."""
        row = emit("MoAffixProcess", 18, 12,
                   evidence=self._evidence(tmp_path, 6))

        assert row["difference"] == -6
        assert row["unexplained_shortfall"] == 0
        assert row["verdict_class"] == "SHORTFALL", (
            "the rules really are missing -- accounting says the loss was "
            "named, not that it did not happen"
        )
        line, = row["accounted_for"]
        assert line["reason"] == "DEPENDENCY_UNRESOLVED"
        assert line["count"] == 6
        assert line["report_ref"]["count_in_report"] == 6
        assert len(line["report_ref"]["record_ids"]) == 6

    def test_the_line_names_its_own_corroboration(self, tmp_path):
        """T087's requirement: the entry carries the report reference AND the
        reason, so the shortfall is explained by evidence that exists. The
        default detail names only the `DroppedItemRecord`, which is half of
        what this line rests on."""
        row = emit("MoAffixProcess", 18, 12,
                   evidence=self._evidence(tmp_path, 6))
        line, = row["accounted_for"]

        assert "ProcessRuleTransferRecord" in line["detail"]
        assert "corroborated" in line["detail"]
        assert PROCESS_RULE_RUN in line["detail"]
        assert "is absent from the destination" in line["detail"]

    def test_the_accounted_row_trips_no_accounting_rule(self, tmp_path):
        """Scoped to the ROW rules, as `test_over_accounting_is_still_capped`
        already is: a bare `{"classes": [row]}` has no `census_id`, no
        provenance and no verdict, so the document-level failures it collects
        say nothing about this line."""
        row = emit("MoAffixProcess", 18, 12,
                   evidence=self._evidence(tmp_path, 6))
        failures = census.validate_artifact({"classes": [row]})

        assert not [f for f in failures
                    if "R-1" in f or "R-2" in f or "R-3" in f]
        assert not [f for f in failures if "MoAffixProcess" in f]

    def test_over_accounting_is_still_capped(self, tmp_path):
        """R-2 holds on the new surface too: 6 reported non-reproductions
        against a 4-object shortfall claim 4, and the `report_ref` still names
        all 6."""
        row = emit("MoAffixProcess", 18, 14,
                   evidence=self._evidence(tmp_path, 6))
        line, = row["accounted_for"]

        assert line["count"] == 4
        assert line["report_ref"]["count_in_report"] == 6
        assert "CLAIM CAPPED" in line["detail"]
        assert "ProcessRuleTransferRecord" in line["detail"], (
            "the cap suffix must be appended to the overridden detail, not "
            "replace it"
        )
        assert any("R-2" in n for n in row["notes"])

    def test_a_non_reproduction_never_pays_down_a_surplus(self, tmp_path):
        row = emit("MoAffixProcess", 12, 18,
                   evidence=self._evidence(tmp_path, 6))
        assert row["accounted_for"] == []
        assert row["unexplained_surplus"] == 6


# ---------------------------------------------------------------------------
# T081 (4th re-gate) -- the source-side process-rule needle
# ---------------------------------------------------------------------------
#
# `straggler-rulings.md` #5 rules ejagham's one refused `MoAffixProcess`
# ("correctly refused; no fix is available in this repo") because its
# `OutputOS[0]` is an `MoCopyFromInput` whose content is EMPTY IN THE SOURCE.
# The ruling was committed and nothing in the instrument wrote it into
# `accounted_for`, so the row read UNEXPLAINED for a shortfall that is, on the
# record, explained. The needle closes that; `SOURCE_REFERENT_ABSENT` is the
# token, because 7.1 defines it as "a referent the engine required is absent on
# the SOURCE".
#
# THE REASON TEXT IS THE LIVE ONE, copied from
# `_run_reports/038-t126-ejagham-report.json` (rule `24ed706a`), which is the
# same string `Lib/categories.py` emits with `content_guid or "(no ContentRA)"`
# interpolated. That interpolation is what makes the needle discriminate: the
# same sentence carrying a GUID means the referent EXISTS but is not one of this
# rule's own input members, which is a different and unruled situation.

T081_EMPTY_CONTENT_REASON = (
    "MoAffixProcess 24ed706a-7df2-4609-a37b-2bfa28853ccc output step 0 "
    "(MoCopyFromInput) copies (no ContentRA), which is not one of this rule's "
    "own input members -- the intra-rule back-reference cannot be rebuilt and "
    "the step would copy nothing (FR-023)"
)

#: The SAME sentence with a resolved content GUID in it. Not ruled on by any
#: committed document, so it must stay unclassified.
T081_WRONG_MEMBER_REASON = T081_EMPTY_CONTENT_REASON.replace(
    "(no ContentRA)", "5c0e9d5e-1111-2222-3333-444455556666")


class TestT081TheSourceSideProcessRuleNeedle:

    def test_the_live_empty_content_reason_is_classified_source_side(self):
        needle, token = census_cli.process_rule_reason_match(
            T081_EMPTY_CONTENT_REASON)
        assert needle == "(no ContentRA)"
        assert token == census_cli.SOURCE_REFERENT_ABSENT_TOKEN
        assert token in census.REASON_TOKENS

    def test_the_same_sentence_with_a_real_guid_stays_unclassified(self):
        """FR-013: unclassified is an ABSENT line, never a guess. A rule whose
        copy step points at a real object that is merely not one of its own
        input members is a different situation and no ruling covers it."""
        assert census_cli.process_rule_reason_match(
            T081_WRONG_MEMBER_REASON) is None

    def test_the_general_drop_table_still_does_not_match_it(self):
        """The no-double-credit argument, extended to the new needle. If a
        general needle matched, `dropped_by_class_from_report` would classify
        the same drop on its own uncorroborated path and the merge would credit
        one lost rule as two accounted objects (R-2)."""
        assert census_cli.drop_reason_token(T081_EMPTY_CONTENT_REASON) is None

    def test_corroboration_is_still_required(self, tmp_path):
        """A `ProcessRuleTransferRecord` with no paired `DroppedItemRecord`
        earns nothing, needle or no needle."""
        assert census_cli.process_rules_by_class_from_report(
            rule_report(
                tmp_path,
                [process_rule(LIVE_RULE_GUID,
                              reason=T081_EMPTY_CONTENT_REASON)],
                []),
            ("MoAffixProcess",)) == {}

    def test_a_corroborated_pair_becomes_one_accounted_object(self, tmp_path):
        grouped = census_cli.process_rules_by_class_from_report(
            rule_report(
                tmp_path,
                [process_rule(LIVE_RULE_GUID,
                              reason=T081_EMPTY_CONTENT_REASON)],
                [rule_drop(LIVE_RULE_GUID,
                           reason=T081_EMPTY_CONTENT_REASON)]),
            ("MoAffixProcess",))
        (token, ref, detail), = grouped["MoAffixProcess"]
        assert token == "SOURCE_REFERENT_ABSENT"
        assert ref.count_in_report == 1
        assert ref.record_ids == (LIVE_RULE_GUID,)
        assert "(no ContentRA)" in detail
        (line,) = census_cli.accounted_for_drops(
            -1, ((token, ref, detail),))
        assert line.reason == "SOURCE_REFERENT_ABSENT"
        assert line.count == 1
        assert line.report_ref is ref

    def test_the_token_is_deliberately_not_phase_five_admissible(self):
        """`MoAffixProcess` is named by PHASE 4's own predicate, so admitting
        the token would let a class this feature has an executable gate on go
        green at P5 -- what T109 LOCK 1 exists to make impossible. The line
        still zeroes the row's `unexplained_shortfall`; whether 9.1 should
        admit the token is a ruling for a human."""
        assert census_cli.SOURCE_REFERENT_ABSENT_TOKEN not in \
            census.PHASE_5_ADMISSIBLE_REASONS
        assert "MoAffixProcess" in census.PHASE_4_CLASSES

    def test_no_needle_shadows_another_after_the_addition(self):
        needles = [n for n, _ in census_cli.PROCESS_RULE_REASON_TOKENS]
        assert len(needles) == len(set(needles))
        for i, outer in enumerate(needles):
            for j, inner in enumerate(needles):
                if i != j:
                    assert inner not in outer, (inner, outer)
