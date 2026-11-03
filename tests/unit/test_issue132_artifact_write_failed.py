"""Issue #132: artifact-schema must document WRITE_FAILED affix slot links.

impl-111 added `AffixSlotLinkOutcome.WRITE_FAILED` and extended
`RunReport.to_dict()` / `_affix_slot_link_block`; the #132 never-silent audit
listed `artifact-schema.md` as missing that vocabulary.
"""
from __future__ import annotations

from pathlib import Path

from gramtrans.Lib import report as report_mod
from gramtrans.Lib.models import AffixSlotLinkOutcome, AffixSlotLinkRecord

_SCHEMA = (
    Path(__file__).resolve().parents[2]
    / "specs/035-fullsweep-fidelity/contracts/artifact-schema.md"
)


def test_artifact_schema_documents_write_failed_block():
    text = _SCHEMA.read_text(encoding="utf-8")
    assert "WRITE_FAILED" in text
    assert "unwritten_slot_guids" in text
    assert "affix_slot_links" in text
    assert "linked_of_attempted" in text


def test_affix_slot_link_block_failure_keys_match_contract():
    rec = AffixSlotLinkRecord(
        entry_guid="entry-1",
        msa_guid="msa-1",
        source_slot_guids=("slot-a",),
        outcome=AffixSlotLinkOutcome.WRITE_FAILED,
        unresolved_slot_guids=(),
        unwritten_slot_guids=("slot-a",),
        detail="RuntimeError: Add reported failure",
    )
    block = report_mod._affix_slot_link_block([rec])
    assert block["failures"][0]["outcome"] == "WRITE_FAILED"
    assert block["failures"][0]["unwritten_slot_guids"] == ["slot-a"]
    assert block["failures"][0]["detail"]

    schema = _SCHEMA.read_text(encoding="utf-8")
    for key in (
        "outcome", "entry_guid", "msa_guid", "source_slot_guids",
        "unresolved_slot_guids", "unwritten_slot_guids", "detail",
    ):
        assert key in schema, f"artifact-schema must document failure key {key!r}"
