"""Issue #132: unresolved adhoc rule members must reach the run report."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.models import DroppedItemRecord, GrammarCategory, PlannedAction, WSMapping


class _FakeMember:
    def __init__(self, guid: str) -> None:
        self.guid = guid.lower()
        self.Guid = guid


class _FakeAlloRule:
    def __init__(self, rule_guid: str, first: _FakeMember | None,
                 rest: tuple[_FakeMember, ...] = ()) -> None:
        self.guid = rule_guid.lower()
        self.ClassName = "MoAlloAdhocProhib"
        self.FirstAllomorphRA = first
        self.RestOfAllosRS = list(rest)


class _FakeRestSeq:
    def __init__(self) -> None:
        self.add_log = []

    def Add(self, member):
        self.add_log.append(member)


class _FakeNewRule:
    def __init__(self) -> None:
        self.FirstAllomorphRA = None
        self.RestOfAllosRS = _FakeRestSeq()


def test_report_adhoc_unresolved_member_dedupes():
    dropped = []
    categories._report_adhoc_unresolved_member(
        dropped, owner_kind="MoAlloAdhocProhib", rule_guid="rule-1",
        field_name="FirstAllomorphRA", member_guid="allo-missing",
    )
    categories._report_adhoc_unresolved_member(
        dropped, owner_kind="MoAlloAdhocProhib", rule_guid="rule-1",
        field_name="FirstAllomorphRA", member_guid="allo-missing",
    )
    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.field_name == "FirstAllomorphRA"
    assert rec.item_guid == "allo-missing"
    assert "not in target" in rec.reason


def test_execute_unresolved_first_allomorph_records_drop(monkeypatch):
    first = _FakeMember("allo-head")
    src_rule = _FakeAlloRule("rule-9", first)
    new_rule = _FakeNewRule()
    dropped = []

    monkeypatch.setattr(categories, "_guid_str_from",
                        lambda obj: getattr(obj, "guid", ""))
    monkeypatch.setattr(
        categories, "_rules_enumerate_all", lambda _src: iter([src_rule]))
    monkeypatch.setattr(
        categories, "_rule_subclass_info",
        lambda _r: ("MoAlloAdhocProhib", object(), {}))
    monkeypatch.setattr(
        categories, "_create_with_guid",
        lambda *_a, **_k: (new_rule, False))
    monkeypatch.setattr(categories, "_copy_supplemental_scalars_ctx",
                        lambda *a, **k: None)
    monkeypatch.setattr(categories, "_wire_stratum", lambda *a, **k: None)
    monkeypatch.setattr(categories, "_iter_all_allomorphs", lambda _t: iter(()))

    class _MorphRules:
        def GetSyncableProperties(self, _obj):
            return {}

        def ApplySyncableProperties(self, *_a, **_k):
            return None

    class _MorphData:
        AdhocCoProhibitionsOC = object()

    class _Cache:
        LangProject = type("LP", (), {
            "MorphologicalDataOA": _MorphData(),
        })()

    target = type("T", (), {"Cache": _Cache(), "MorphRules": _MorphRules()})()
    ctx = type("Ctx", (), {
        "source_handle": object(),
        "target_handle": target,
        "_dropped": dropped,
    })()
    action = PlannedAction(
        category=GrammarCategory.ADHOC_COMPOUND_RULES,
        source_guid="rule-9",
        intended_target_guid="rule-9",
        summary="t",
    )

    lcm_mock = MagicMock()
    lcm_mock.ICmObject = lambda x: x
    with patch.dict("sys.modules", {"SIL": lcm_mock, "SIL.LCModel": lcm_mock}):
        categories.adhoc_compound_rules_execute_action(
            action, ctx, WSMapping(entries=()), "tag")

    assert new_rule.FirstAllomorphRA is None
    assert len(dropped) == 1
    assert isinstance(dropped[0], DroppedItemRecord)
    assert dropped[0].field_name == "FirstAllomorphRA"
    assert dropped[0].item_guid == "allo-head"
