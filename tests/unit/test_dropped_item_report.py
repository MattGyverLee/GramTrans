"""Unit tests for US4 -- the linguist is told what was dropped (feature 024,
T021).

Covers contracts/dropped-item-report.md:
- Exactly ONE `DroppedItemRecord` per REPORT_DROPPED outcome, with correct
  owner_kind/owner_guid/owner_label/field_name/item_name/item_guid/reason
  (the "never-silent" backstop, FR-010).
- No duplicate on re-walk of the same (owner, field, item) triple (the
  contract's exactly-once invariant).
- A fully-reproduced transfer (no divergence) yields an EMPTY `dropped_items`
  (SC-003 acceptance 2).
- `render_text_summary`'s "Dropped references / owned items" section renders
  the ASCII-only line format (`->`/`-`, never unicode arrows/dashes, per
  Windows console rules).

TDD RED STATE: `categories._apply_reference_fields` does not yet enrich
`decision.dropped` with the real owner_guid/owner_label (both are hardcoded
"" placeholders built inside `references.py`, which has no owner-instance
context), and `_apply_reference_fields` does not yet accept an `owner_guid`
keyword at all. `report.render_text_summary` does not yet emit a "Dropped
references / owned items" section. Every test below is expected to FAIL
until T022/T024 land. Do NOT implement those fixes here; this file only
records the write-first contract.

Fakes are modeled on `tests/unit/test_reference_resolver.py` /
`tests/unit/test_blanking_fix.py`'s `_FakeTsString` / `_FakeMultiString` /
`_FakePossibility` / `_FakeTargetList` / `_FakeTargetProject` pattern.
"""
from __future__ import annotations

import types

from gramtrans.Lib import categories
from gramtrans.Lib.models import (
    DroppedItemRecord,
    GrammarCategory,
    RunContext,
    RunMode,
    RunPlan,
    Selection,
    WSMapping,
)
from gramtrans.Lib.report import RunReport

WS_EN = 100


# ============================================================================
# Fakes
# ============================================================================

class _FakeTsString:
    def __init__(self, text):
        self.Text = text or None


class _FakeMultiString:
    """Fake ICmMultiString: per-handle text storage (duck-typed `_data`)."""

    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})

    def get_String(self, ws_handle):
        return _FakeTsString(self._data.get(ws_handle))


class _FakePossibility:
    """Duck-typed ICmPossibility: Guid, Name, IsProtected, top-level
    Owner/OwningPossibility (both None -- no ancestor chain needed here)."""

    def __init__(self, guid, name="", is_protected=False):
        self.Guid = guid
        self.guid = guid
        self.Name = _FakeMultiString({WS_EN: name} if name else {})
        self.Abbreviation = _FakeMultiString({})
        self.IsProtected = is_protected
        self.Owner = None
        self.OwningPossibility = None


class _FakeTargetList:
    """Fake ICmPossibilityList: flat GUID-searchable container."""

    def __init__(self, items=()) -> None:
        self.PossibilitiesOS = list(items)


class _FakeLexDb:
    def __init__(self, sense_types_list) -> None:
        self.SenseTypesOA = sense_types_list


class _FakeLangProject:
    def __init__(self, lex_db) -> None:
        self.LexDbOA = lex_db


class _FakeCache:
    def __init__(self, lang_project) -> None:
        self.LangProject = lang_project


class _FakeTargetProject:
    """Minimal fake target FLExProject: only `.Cache.LangProject.LexDbOA.
    SenseTypesOA` -- the one field left un-skipped below."""

    def __init__(self, sense_types_list) -> None:
        self.Cache = _FakeCache(_FakeLangProject(_FakeLexDb(sense_types_list)))


# Every LexSense reference field except SenseTypeRA -- skipped so this fake
# target (which only models SenseTypesOA) never trips over an unmodeled
# accessor for the other nine fields in `references.REFERENCE_FIELD_MAP`.
_OTHER_LEXSENSE_FIELDS = frozenset({
    "UsageTypesRC", "DomainTypesRC", "AnthroCodesRC", "DialectLabelsRS",
    "StatusRA", "SemanticDomainsRC", "PublishIn", "DoNotPublishInRC",
    "DoNotShowMainEntryInRC",
})


def _make_src_sense(sense_type_item, gloss_text="the-gloss"):
    return types.SimpleNamespace(
        SenseTypeRA=sense_type_item,
        Gloss=_FakeMultiString({WS_EN: gloss_text} if gloss_text else {}),
    )


# ============================================================================
# (1) Exactly one DroppedItemRecord, correctly populated, per REPORT_DROPPED
# ============================================================================

def test_report_dropped_yields_exactly_one_correctly_populated_record():
    guid = "dddddddd-0000-0000-0000-dddddddddddd"
    source_item = _FakePossibility(guid, name="Water", is_protected=True)
    target_item = _FakePossibility(guid, name="Aqua", is_protected=True)  # diverged + shared/default
    target = _FakeTargetProject(_FakeTargetList([target_item]))
    src_obj = _make_src_sense(source_item, gloss_text="wash")
    new_obj = types.SimpleNamespace(SenseTypeRA=None)
    dropped: list = []

    categories._apply_reference_fields(
        "LexSense", src_obj, new_obj, target, None, {}, dropped,
        skip_fields=_OTHER_LEXSENSE_FIELDS, owner_guid="sense-guid-0001",
    )

    assert len(dropped) == 1, "exactly one DroppedItemRecord for one REPORT_DROPPED outcome"
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.owner_kind == "LexSense"
    assert rec.owner_guid == "sense-guid-0001"
    assert rec.owner_label == "wash", (
        "owner_label must be the OWNING sense's own label (Gloss), not left "
        "as references.py's placeholder empty string"
    )
    assert rec.field_name == "SenseTypeRA"
    assert rec.item_name == "Water", "item_name is the SOURCE item's label"
    assert rec.item_guid == guid
    assert rec.reason == "shared-default diverged"


# ============================================================================
# (2) No duplicate on re-walk of the same (owner, field, item) triple
# ============================================================================

def test_no_duplicate_dropped_record_on_rewalk_of_same_triple():
    guid = "eeeeeeee-0000-0000-0000-eeeeeeeeeeee"
    source_item = _FakePossibility(guid, name="Water", is_protected=True)
    target_item = _FakePossibility(guid, name="Aqua", is_protected=True)
    target = _FakeTargetProject(_FakeTargetList([target_item]))
    src_obj = _make_src_sense(source_item)
    new_obj = types.SimpleNamespace(SenseTypeRA=None)
    dropped: list = []

    for _ in range(2):  # simulate the SAME owner/field/item being walked twice
        categories._apply_reference_fields(
            "LexSense", src_obj, new_obj, target, None, {}, dropped,
            skip_fields=_OTHER_LEXSENSE_FIELDS, owner_guid="sense-guid-0002",
        )

    assert len(dropped) == 1, (
        "contract invariant: a record is emitted exactly once per "
        "(owner, field, item) triple -- re-walking must not duplicate it"
    )


# ============================================================================
# (3) Fully-reproduced transfer -> EMPTY dropped_items (SC-003 acceptance 2)
# ============================================================================

def test_fully_reproduced_transfer_yields_empty_dropped_items():
    guid = "ffffffff-0000-0000-0000-ffffffffffff"
    source_item = _FakePossibility(guid, name="Idiom")
    target_item = _FakePossibility(guid, name="Idiom")  # identical -> LINK
    target = _FakeTargetProject(_FakeTargetList([target_item]))
    src_obj = _make_src_sense(source_item)
    new_obj = types.SimpleNamespace(SenseTypeRA=None)
    dropped: list = []

    categories._apply_reference_fields(
        "LexSense", src_obj, new_obj, target, None, {}, dropped,
        skip_fields=_OTHER_LEXSENSE_FIELDS, owner_guid="sense-guid-0003",
    )

    assert dropped == [], "a fully-reproduced (identical) reference must never drop"
    assert new_obj.SenseTypeRA is target_item


# ============================================================================
# Bonus (T023): compute_fidelity_by_guid -- FULL by absence, PARTIAL by drop
# ============================================================================

def test_compute_fidelity_by_guid_partial_for_dropped_full_by_absence():
    record = DroppedItemRecord(
        owner_kind="LexSense", owner_guid="sense-guid-0004", owner_label="x",
        field_name="SenseTypeRA", item_name="Water", item_guid="g", reason="x",
    )
    fidelity = categories.compute_fidelity_by_guid([record])
    from gramtrans.Lib.models import FidelityStatus
    assert fidelity == {"sense-guid-0004": FidelityStatus.PARTIAL}
    # "sense-guid-9999" never appears -- FULL is implied by absence, not an
    # explicit dict entry (see compute_fidelity_by_guid's docstring).
    assert "sense-guid-9999" not in fidelity


# ============================================================================
# (4) render_text_summary -- exact ASCII line format
# ============================================================================

def _ctx() -> RunContext:
    return RunContext(
        source_handle=object(),
        source_project_name="Ejagham Mini",
        source_project_path=r"C:\fake\Ejagham Mini\Ejagham Mini.fwdata",
        target_handle=object(),
        target_project_name="Ejagham Full",
        target_project_path=r"C:\fake\Ejagham Full\Ejagham Full.fwdata",
        run_id="GT-20260711-000000",
        started_at="2026-07-11T00:00:00",
    )


def _plan() -> RunPlan:
    return RunPlan(
        context=_ctx(),
        selection=Selection(categories={}),
        ws_mapping=WSMapping(entries=()),
    )


def test_render_text_summary_dropped_section_matches_contract_ascii_format():
    from gramtrans.Lib import report as report_module

    record = DroppedItemRecord(
        owner_kind="LexSense",
        owner_guid="12345678-abcd-abcd-abcd-1234567890ab",
        owner_label="wash",
        field_name="SenseTypeRA",
        item_name="Water",
        item_guid="dddddddd-0000-0000-0000-dddddddddddd",
        reason="shared-default diverged",
    )
    report = RunReport.build_from_plan(
        _plan(), RunMode.PREVIEW, extra_dropped_items=(record,),
    )

    lines = list(report_module.render_text_summary(report))
    expected = (
        '    - wash [LexSense 12345678] . SenseTypeRA -> "Water" '
        '(dddddddd) - shared-default diverged'
    )
    assert expected in lines, (
        f"expected ASCII-only contract-format line not found; got lines: {lines}"
    )
    # Never unicode arrows/dashes (Windows console rules -- ASCII only).
    joined = "\n".join(lines)
    assert "→" not in joined  # -> (never the unicode arrow)
    assert "—" not in joined  # - (never the unicode em dash)


def test_render_text_summary_no_dropped_section_when_empty():
    report = RunReport.build_from_plan(_plan(), RunMode.PREVIEW)
    lines = list(__import__("gramtrans.Lib.report", fromlist=["render_text_summary"]).render_text_summary(report))
    assert not any("Dropped references" in ln for ln in lines), (
        "an empty dropped list must render no section at all"
    )
