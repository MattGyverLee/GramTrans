"""Issue #132 (never-silent batch): unresolved StratumRA must Skip, not vanish."""
from __future__ import annotations

import sys
import types

import pytest

from gramtrans.Lib.models import GrammarCategory, SkipReason


@pytest.fixture(autouse=True)
def _fake_lcm(monkeypatch):
    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.ICmObject = lambda x: x
    sil = types.ModuleType("SIL")
    sil.LCModel = fake_lcm
    monkeypatch.setitem(sys.modules, "SIL", sil)
    monkeypatch.setitem(sys.modules, "SIL.LCModel", fake_lcm)


class _Stratum:
    def __init__(self, guid: str) -> None:
        self.Guid = guid


class _Piece:
    def __init__(self, guid: str, stratum=None) -> None:
        self.guid = guid
        self.StratumRA = stratum


class _Target:
    class _Strata:
        def __init__(self, items):
            self._items = items

        def GetAll(self):
            return list(self._items)

    def __init__(self, strata=()):
        self.Strata = _Target._Strata(strata)


def test_wire_stratum_reports_missing_stratum_on_exec_skips(_fake_lcm) -> None:
    from gramtrans.Lib import categories

    src = _Piece("msa-1", _Stratum("stratum-missing"))
    new = _Piece("msa-1")
    target = _Target([])
    skips = []
    ctx = type("Ctx", (), {
        "_exec_skips": skips,
        "_closure_category": GrammarCategory.STEMS,
    })()

    categories._wire_stratum(src, new, target, ctx, source_guid="msa-1")

    assert new.StratumRA is None
    assert len(skips) == 1
    assert skips[0].reason == SkipReason.DEPENDENCY_UNRESOLVED
    assert skips[0].category == GrammarCategory.STEMS
    assert skips[0].source_guid == "msa-1"
    assert "stratum-missing" in skips[0].detail


def test_wire_stratum_wires_when_stratum_present(_fake_lcm) -> None:
    from gramtrans.Lib import categories

    strat = _Stratum("stratum-1")
    src = _Piece("msa-1", _Stratum("stratum-1"))
    new = _Piece("msa-1")
    target = _Target([strat])
    skips = []
    ctx = type("Ctx", (), {"_exec_skips": skips})()

    categories._wire_stratum(src, new, target, ctx, source_guid="msa-1")

    assert new.StratumRA is strat
    assert skips == []


def test_wire_stratum_no_source_stratum_is_silent(_fake_lcm) -> None:
    from gramtrans.Lib import categories

    src = _Piece("msa-1", None)
    new = _Piece("msa-1")
    target = _Target([])
    skips = []
    ctx = type("Ctx", (), {"_exec_skips": skips})()

    categories._wire_stratum(src, new, target, ctx, source_guid="msa-1")

    assert skips == []


def test_wire_stratum_honors_explicit_category(_fake_lcm) -> None:
    from gramtrans.Lib import categories

    src = _Piece("rule-1", _Stratum("stratum-missing"))
    new = _Piece("rule-1")
    target = _Target([])
    skips = []
    ctx = type("Ctx", (), {"_exec_skips": skips})()

    categories._wire_stratum(
        src, new, target, ctx,
        category=GrammarCategory.ADHOC_COMPOUND_RULES,
        source_guid="rule-1",
    )

    assert len(skips) == 1
    assert skips[0].category == GrammarCategory.ADHOC_COMPOUND_RULES
    assert skips[0].source_guid == "rule-1"
