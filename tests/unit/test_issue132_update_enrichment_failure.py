"""Issue #132: UPDATE enrichment pass failures must reach dropped_items."""
from __future__ import annotations

import pytest

from gramtrans.Lib import transfer
from gramtrans.Lib.models import (
    DroppedItemRecord,
    EnrichedCollection,
    EnrichmentRecord,
    GrammarCategory,
    PlannedOverwrite,
)


def test_enrichment_pass_exception_records_drop_when_collector_wired():
    ow = PlannedOverwrite(
        category=GrammarCategory.GRAM_CATEGORIES,
        source_guid="pos-guid-1",
        target_guid="pos-guid-1",
        match_via="guid",
        write_mode="merge",
        summary="Verb",
        enrichment=EnrichmentRecord(
            object_class="PartOfSpeech",
            source_guid="pos-guid-1",
            target_guid="pos-guid-1",
            label="Verb",
            collections=(
                EnrichedCollection(field_name="AffixSlotsOC", added=1),
            ),
        ),
    )
    dropped: list = []
    boom = RuntimeError("LCM collection pass aborted")

    transfer._record_enrichment_pass_failure(ow, dropped, boom)

    assert len(dropped) == 1
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.owner_guid == "pos-guid-1"
    assert rec.field_name == "(owned-collection enrichment)"
    assert "RuntimeError" in rec.reason
    assert "LCM collection pass aborted" in rec.reason


def test_enrichment_pass_exception_no_collector_is_noop():
    ow = PlannedOverwrite(
        category=GrammarCategory.GRAM_CATEGORIES,
        source_guid="pos-guid-1",
        target_guid="pos-guid-1",
        match_via="guid",
        write_mode="merge",
        summary="Verb",
        enrichment=None,
    )
    transfer._record_enrichment_pass_failure(ow, None, ValueError("x"))
