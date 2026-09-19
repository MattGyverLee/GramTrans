"""Feature 038 T048e -- a correct no-op enrichment must leave a record.

Raised by the T039 idempotence re-run
(`specs/038-transfer-fidelity-gaps/journal/T039-idempotence-rerun.md`), which
found SC-008's criterion 3b unevaluable: the three parts of speech a first run
enriched produced NO enrichment surface at all on a second run, so there was
nothing to compare `already_present` against.

The cause was not a wrong decision. `_plan_gold_reserved_edit` runs
`_compare_pos_owned_collections` BEFORE either of its early skips (T043), and
the skip fires only on `not all_gaps and not all_conflicts and not
collection_delta` -- so data-model.md section 9's requirement, that a SKIP be
emitted only where every scalar field AND all seven owned collections were
compared and needed no write, was genuinely met. The comparison happened. Its
RESULT was then thrown away, and the skip detail said only "all WS slots
equal", which reads as though the collections were never looked at.

WHY THIS IS NOT THE WIDENING THE EARLIER JOURNAL REJECTED.
`journal/T039-idempotence.md` recorded giving `Skip` a `match_basis` as
considered and NOT recommended: "a skip that carries a match is really a link,
which is the LINK-vs-SKIP distinction defect G3 already turns on". That
objection is about asserting a MATCH. `collections_compared` asserts only that
a comparison ran and found nothing to add -- the precondition the clause
already demands of every SKIP. It sharpens the boundary rather than blurring
it: a skip that can show its comparison is now distinguishable from one that
cannot.

The invariant that keeps the two dispositions apart is checked, not documented:
every member must be a no-op. A collection that added or dropped a child is an
enrichment and belongs on a `PlannedOverwrite` carrying an `EnrichmentRecord`.
"""

from __future__ import annotations

import json

import pytest

from gramtrans.Lib.models import (
    EnrichedCollection,
    GrammarCategory,
    Skip,
    SkipReason,
)


def _noop(field_name, already_present=0):
    return EnrichedCollection(
        field_name=field_name, added=0,
        already_present=already_present, dropped=0)


def _skip(collections=()):
    return Skip(
        category=GrammarCategory.GRAM_CATEGORIES,
        source_guid="a8e41fd3-e343-4c7c-aa05-01ea3dd5cfb5",
        reason=SkipReason.ALREADY_PRESENT_BY_GUID,
        detail="GUID a8e41fd3... present in target; all WS slots equal.",
        collections_compared=tuple(collections),
    )


class TestTheEvidenceIsCarried:

    def test_a_skip_carries_the_collections_it_compared(self):
        skip = _skip([_noop("AffixSlotsOC", 1), _noop("AffixTemplatesOS", 1)])
        assert len(skip.collections_compared) == 2
        assert [c.field_name for c in skip.collections_compared] == [
            "AffixSlotsOC", "AffixTemplatesOS"]
        assert [c.already_present for c in skip.collections_compared] == [1, 1]

    def test_the_field_defaults_to_empty_so_every_existing_caller_is_valid(self):
        """The five non-POS categories sharing `_plan_gold_reserved_edit` own no
        collections, and every other Skip site in the engine passes nothing."""
        skip = Skip(
            category=GrammarCategory.SEMANTIC_DOMAINS,
            source_guid="s-1",
            reason=SkipReason.ALREADY_PRESENT_BY_GUID,
            detail="present.",
        )
        assert skip.collections_compared == ()

    def test_empty_is_not_the_same_claim_as_compared_and_complete(self):
        """Distinct states, and the report must not conflate them: `()` means
        no comparison applies or was made, NOT "compared, found nothing"."""
        made = _skip([_noop("AffixSlotsOC", 0)])
        not_made = _skip([])
        assert made.collections_compared != not_made.collections_compared
        assert len(made.collections_compared) == 1


class TestTheNoOpInvariant:
    """A skip is "nothing will be written". Evidence that something WAS written
    is a contradiction, and conflating the two is how an enrichment would get
    reported as a skip -- the exact G3 shape US4 exists to remove."""

    def test_a_collection_that_added_a_child_is_refused(self):
        with pytest.raises(ValueError, match="no-op collections"):
            _skip([EnrichedCollection(
                field_name="AffixSlotsOC", added=1, already_present=0)])

    def test_a_collection_that_dropped_a_child_is_refused(self):
        from gramtrans.Lib.models import DroppedItemRecord
        dropped = DroppedItemRecord(
            item_name="MoInflAffixSlot", item_guid="d-1",
            owner_kind="PartOfSpeech", owner_guid="o-1",
            owner_label="Noun", field_name="AffixSlotsOC",
            reason="no create path")
        with pytest.raises(ValueError, match="no-op collections"):
            _skip([EnrichedCollection(
                field_name="AffixSlotsOC", added=0, already_present=0,
                dropped=1, dropped_records=(dropped,))])

    def test_the_error_names_the_offending_collection(self):
        with pytest.raises(ValueError) as excinfo:
            _skip([_noop("AffixSlotsOC", 2),
                   EnrichedCollection(field_name="StemNamesOC", added=3)])
        assert "StemNamesOC" in str(excinfo.value)
        assert "added=3" in str(excinfo.value)

    def test_the_error_points_at_the_right_disposition(self):
        """The message must say where the record belongs, or the next caller
        will simply zero the counts to get past the check."""
        with pytest.raises(ValueError) as excinfo:
            _skip([EnrichedCollection(field_name="AffixSlotsOC", added=1)])
        message = str(excinfo.value)
        assert "PlannedOverwrite" in message
        assert "EnrichmentRecord" in message


class TestTheReportSurface:
    """`report._skip_snapshot` -- what reaches the artifact."""

    def test_the_evidence_is_serialised_with_all_three_buckets(self):
        from gramtrans.Lib.report import _skip_snapshot
        row = _skip_snapshot(_skip([_noop("AffixSlotsOC", 1),
                                    _noop("InflectableFeatsRC", 2)]))
        assert row["collections_compared"] == [
            {"field_name": "AffixSlotsOC", "added": 0,
             "already_present": 1, "dropped": 0},
            {"field_name": "InflectableFeatsRC", "added": 0,
             "already_present": 2, "dropped": 0},
        ]

    def test_the_key_is_OMITTED_when_there_is_no_evidence(self):
        """Not `[]`. An empty list would read as "compared, and there are
        none", manufacturing evidence for a comparison that never ran on the
        five categories that own no collections."""
        from gramtrans.Lib.report import _skip_snapshot
        row = _skip_snapshot(_skip([]))
        assert "collections_compared" not in row

    def test_the_pre_existing_keys_are_unchanged(self):
        """The refactor from an inline dict to a helper must not move anything
        a consumer already reads -- census_cli's identity-skip reader keys off
        `category` and `reason`."""
        from gramtrans.Lib.report import _skip_snapshot
        row = _skip_snapshot(_skip([]))
        assert sorted(row) == ["category", "detail", "reason", "source_guid"]
        assert row["category"] == "GRAM_CATEGORIES"
        assert row["reason"] == "ALREADY_PRESENT_BY_GUID"

    def test_the_row_is_json_serialisable(self):
        from gramtrans.Lib.report import _skip_snapshot
        row = _skip_snapshot(_skip([_noop("AffixSlotsOC", 1)]))
        assert json.loads(json.dumps(row)) == row


class TestTheHumanHalf:
    """`categories._collections_compared_detail` -- the same fact where a
    person reading the report will see it."""

    def test_the_detail_names_the_collections_and_their_counts(self):
        from gramtrans.Lib.categories import _collections_compared_detail
        text = _collections_compared_detail(
            [_noop("AffixSlotsOC", 1), _noop("AffixTemplatesOS", 2)])
        assert "2 owned collection(s) compared, nothing to add" in text
        assert "AffixSlotsOC=1" in text
        assert "AffixTemplatesOS=2" in text

    def test_no_collections_yields_no_text_at_all(self):
        """So the five non-POS categories keep their detail byte-identical."""
        from gramtrans.Lib.categories import _collections_compared_detail
        assert _collections_compared_detail([]) == ""
        assert _collections_compared_detail(()) == ""

    def test_the_detail_no_longer_reads_as_ws_only(self):
        """The defect was a reader's one: "all WS slots equal." sounded like
        the collections were never examined."""
        from gramtrans.Lib.categories import _collections_compared_detail
        detail = "GUID a8e41fd3... present in target; all WS slots equal" + \
            _collections_compared_detail([_noop("AffixSlotsOC", 1)]) + "."
        assert "all WS slots equal" in detail
        assert "owned collection(s) compared" in detail
