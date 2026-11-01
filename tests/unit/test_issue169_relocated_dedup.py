"""Issue #169 -- a `relocated:` record (#158) must never mask a real loss or an
apply failure on the same possibility item, and sibling relocations must not
collapse into one.

Every record from the possibility CREATE arm shares
`(owner_guid, "ThesaurusItemsRC", item_guid)`, the published dedup identity.
Before the fix `categories._append_dropped_once` kept the FIRST record for that
key, so a Name relocation hid a Description loss, an ApplySyncableProperties
failure, and the Abbreviation/Description relocations.
"""
from __future__ import annotations

import json

from gramtrans.Lib import categories, references
from gramtrans.Lib.models import (
    DroppedItemRecord, RunMode, dropped_dedup_key, dropped_identity,
    is_relocated_record, merge_dropped_records,
)
from gramtrans.Lib.report import RunReport, render_text_summary

from test_dropped_item_report import _plan
from test_issue129_create_arm_multistring import (
    _MS, _Ops, _Owner, _Src, _WS, _run,
)
import types

OWNER = "abcdef00-0000-0000-0000-000000000001"
ITEM = "11111111-2222-3333-4444-555555555555"


def _rec(reason, relocated=False, item=ITEM):
    return DroppedItemRecord(
        owner_kind="LexSense", owner_guid=OWNER, owner_label="owner-name",
        field_name="ThesaurusItemsRC", item_name="Probe", item_guid=item,
        reason=reason, relocated=relocated)


def _reloc(field):
    return _rec(f"relocated: {field} text from source writing system 'de' "
                "written into target default analysis writing system 'en' "
                "(no source writing system present in target)", relocated=True)


LOSS = "source writing system 'qaa' absent in target"


# --- the collector -----------------------------------------------------------

def _collect(*records):
    dropped = []
    for r in records:
        categories._append_dropped_once(dropped, r)
    return dropped


def test_relocation_does_not_mask_a_later_loss():
    out = _collect(_reloc("Name"), _rec(LOSS))
    assert [is_relocated_record(r) for r in out] == [True, False]


def test_loss_does_not_mask_a_later_relocation():
    out = _collect(_rec(LOSS), _reloc("Name"))
    assert [is_relocated_record(r) for r in out] == [False, True]


def test_relocation_does_not_mask_a_later_apply_failure():
    failure = _rec("created item's Name/Abbreviation/Description could not "
                   "be copied: TypeError('boom')")
    out = _collect(_reloc("Name"), failure)
    assert failure in out


def test_sibling_relocations_are_all_kept():
    out = _collect(_reloc("Name"), _reloc("Abbreviation"), _reloc("Description"))
    assert len(out) == 3


def test_identical_relocation_is_still_deduped():
    out = _collect(_reloc("Name"), _reloc("Name"))
    assert len(out) == 1


def test_losses_keep_the_published_first_in_contract():
    out = _collect(_rec(LOSS), _rec("source writing system 'de' absent in target"))
    assert len(out) == 1 and out[0].reason == LOSS


def test_dropped_identity_shape_is_unchanged():
    assert dropped_identity(_reloc("Name")) == (OWNER, "ThesaurusItemsRC", ITEM)
    assert dropped_dedup_key(_rec(LOSS)) == (OWNER, "ThesaurusItemsRC", ITEM)
    assert dropped_dedup_key(_reloc("Name")) != dropped_dedup_key(_rec(LOSS))


def test_merge_dropped_records_keeps_relocation_and_loss_apart():
    merged = merge_dropped_records([_reloc("Name")], [_rec(LOSS), _reloc("Name")])
    assert [is_relocated_record(r) for r in merged] == [True, False]


# --- the CREATE arm (references.apply_reference) ----------------------------

def _source():
    """Handle 1 = 'de' (analysis), 2 = 'qaa' (vernacular); neither in target."""
    all_ws = [_WS("de", 1), _WS("qaa", 2)]
    return types.SimpleNamespace(WritingSystems=types.SimpleNamespace(
        GetAll=lambda: all_ws,
        GetVernacular=lambda: [w for w in all_ws if w.Id == "qaa"]))


def _guid(c):
    return c * 8 + "-1690-1690-1690-" + c * 12


def test_create_arm_three_relocations_all_survive_the_collector(monkeypatch):
    ops = _Ops()
    src = _Src(_guid("a"), Name={1: "N"}, Abbreviation={1: "A"},
               Description={1: "D"})
    raw = _run(monkeypatch, src, ops, source=_source(), owner=_Owner())
    assert all(is_relocated_record(r) for r in raw) and len(raw) == 3
    out = _collect(*raw)
    assert sorted(r.reason.split()[1] for r in out) == [
        "Abbreviation", "Description", "Name"]


def test_create_arm_mixed_item_reports_loss_and_relocation(monkeypatch):
    """Name relocates (analysis 'de'); Description is vernacular-only ('qaa')
    and is LOST. Both must survive -- the loss as a loss."""
    ops = _Ops()
    src = _Src(_guid("b"), Name={1: "N"}, Description={2: "VernDesc"})
    raw = _run(monkeypatch, src, ops, source=_source(), owner=_Owner())
    assert ops.calls[0] == {"Name": {"en": "N"}}
    out = _collect(*raw)
    losses = [r for r in out if not is_relocated_record(r)]
    relocs = [r for r in out if is_relocated_record(r)]
    assert [r.reason for r in losses] == ["source writing system 'qaa' absent in target"]
    assert len(relocs) == 1 and relocs[0].reason.startswith("relocated: Name ")


def test_create_arm_apply_failure_after_relocation_reports_no_relocation(monkeypatch):
    """Nothing was written, so no record may claim the text was relocated; the
    failure is the loss the collector keeps."""
    ops = _Ops(raises=TypeError("boom"))
    src = _Src(_guid("c"), Name={1: "N"}, Description={2: "VernDesc"})
    raw = _run(monkeypatch, src, ops, source=_source(), owner=_Owner())
    assert not any(is_relocated_record(r) for r in raw)
    assert not any(r.reason.startswith("relocated:") for r in raw)
    assert "could not be copied" in raw[0].reason
    assert "source writing system 'de' absent in target" in [r.reason for r in raw]
    out = _collect(*raw)
    assert len(out) == 1 and "could not be copied" in out[0].reason


def test_create_arm_legacy_source_none_emits_no_relocation(monkeypatch):
    ops = _Ops()
    src = _Src(_guid("d"), Name={99: "Plain"}, Description={98: "Desc"})
    raw = _run(monkeypatch, src, ops, owner=_Owner())
    assert raw == []
    assert set(ops.calls[0]) == {"Name", "Description"}


def test_create_arm_legacy_source_none_apply_failure_is_a_loss(monkeypatch):
    ops = _Ops(raises=TypeError("boom"))
    src = _Src(_guid("e"), Name={99: "Plain"})
    raw = _run(monkeypatch, src, ops, owner=_Owner())
    assert len(raw) == 1 and not is_relocated_record(raw[0])
    assert "could not be copied" in raw[0].reason


# --- the report --------------------------------------------------------------

def _report():
    return RunReport.build_from_plan(
        _plan(), RunMode.MOVE,
        extra_dropped_items=(_reloc("Name"), _rec(LOSS), _reloc("Description")))


def test_build_routes_relocations_to_their_own_collection():
    report = _report()
    assert [r.reason for r in report.dropped_items] == [LOSS]
    assert len(report.relocated_items) == 2
    assert all(is_relocated_record(r) for r in report.relocated_items)


def test_render_has_separate_relocated_section():
    lines = list(render_text_summary(_report()))
    drop_hdr = next(i for i, l in enumerate(lines) if "Dropped references" in l)
    reloc_hdr = next(i for i, l in enumerate(lines) if "Relocated text" in l)
    assert "-- 1 total" in lines[drop_hdr]
    assert "-- 2 total" in lines[reloc_hdr]
    reloc_lines = lines[reloc_hdr + 1:reloc_hdr + 3]
    assert all("relocated:" in l for l in reloc_lines)
    assert not any("relocated:" in l for l in lines[drop_hdr + 1:reloc_hdr])


def test_snapshot_json_relocated_key_is_additive_and_omitted_when_empty():
    data = json.loads(_report().to_snapshot_json())
    assert [d["reason"] for d in data["dropped_items"]] == [LOSS]
    assert len(data["relocated_items"]) == 2
    plain = RunReport.build_from_plan(
        _plan(), RunMode.MOVE, extra_dropped_items=(_rec(LOSS),))
    assert "relocated_items" not in json.loads(plain.to_snapshot_json())
    assert not any("Relocated text" in l for l in render_text_summary(plain))
