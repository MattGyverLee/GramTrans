"""Issue #132: phon-rule InitialStratumRA/FinalStratumRA must not swallow writes."""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from gramtrans.Lib.models import DroppedItemRecord  # noqa: E402


@pytest.fixture(autouse=True)
def _fake_lcm(monkeypatch):
    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.ICmObject = lambda x: x
    fake_lcm.IPhRegularRule = lambda x: x
    sil = types.ModuleType("SIL")
    sil.LCModel = fake_lcm
    monkeypatch.setitem(sys.modules, "SIL", sil)
    monkeypatch.setitem(sys.modules, "SIL.LCModel", fake_lcm)


class _Stratum:
    def __init__(self, guid: str) -> None:
        self.guid = guid
        self.Guid = guid


class _Rule:
    def __init__(self, guid: str) -> None:
        self.guid = guid
        self.InitialStratumRA = None
        self.FinalStratumRA = None


class _RaRaises:
    def __init__(self, attr: str) -> None:
        self._attr = attr

    def __setattr__(self, name, value):
        if name == "_attr":
            object.__setattr__(self, name, value)
            return
        if name == self._attr:
            raise TypeError("RA assignment rejected")
        object.__setattr__(self, name, value)


def test_try_wire_stratum_ra_records_add_failure():
    from gramtrans.Lib import categories

    strat = _Stratum("stratum-1")
    rule = _RaRaises("InitialStratumRA")
    dropped = []
    ok = categories._try_wire_phon_rule_stratum_ra(
        rule, "InitialStratumRA", strat, rule_guid="rule-1", dropped=dropped,
    )
    assert ok is False
    assert len(dropped) == 1
    assert dropped[0].owner_kind == "PhRegularRule"
    assert dropped[0].field_name == "InitialStratumRA"
    assert "stratum-1" in dropped[0].item_guid


def test_try_wire_stratum_ra_wires_when_assignment_succeeds():
    from gramtrans.Lib import categories

    strat = _Stratum("stratum-1")
    rule = _Rule("rule-1")
    dropped = []
    ok = categories._try_wire_phon_rule_stratum_ra(
        rule, "InitialStratumRA", strat, rule_guid="rule-1", dropped=dropped,
    )
    assert ok is True
    assert rule.InitialStratumRA is strat
    assert dropped == []


def test_drain_stratum_wiring_records_setattr_failure():
    from gramtrans.Lib import categories

    strat = _Stratum("stratum-1")
    rule = _RaRaises("InitialStratumRA")
    rule.guid = "rule-1"

    class _PhonRulesOS:
        def __iter__(self):
            return iter([rule])

    class _PhonData:
        PhonRulesOS = _PhonRulesOS()

    class _LangProject:
        PhonologicalDataOA = _PhonData()

    class _Cache:
        LangProject = _LangProject()

    class _Target:
        Cache = _Cache()

        class _Strata:
            @staticmethod
            def GetAll():
                return [strat]

        Strata = _Strata()

    ctx = type("Ctx", (), {
        "_phon_rule_stratum_wiring": [("rule-1", "stratum-1", None)],
        "_dropped": [],
    })()
    categories._drain_phon_rule_stratum_wiring(ctx, _Target(), tag=None)
    assert len(ctx._dropped) == 1
    assert isinstance(ctx._dropped[0], DroppedItemRecord)
