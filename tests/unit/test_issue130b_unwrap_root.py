"""Issue #130 follow-up (PR #150): `_unwrap` root cause + equal-set no-op.

flexicon wrappers (AffixSlot) hold `_concrete`/`_obj` but no public
`.concrete`. A pythonnet interface cast of such a wrapper RAISES
`TypeError: object does not implement ...` (live-verified); the stub below
reproduces that so each sweep row is proven broken-before / fixed-after.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from gramtrans.Lib import conflict, merge_preview, preview, transfer  # noqa: E402
from gramtrans.Lib.lcm_unwrap import unwrap  # noqa: E402


class _Raw:
    """Stands in for a raw LCM object (the only thing casts accept)."""

    def __init__(self, guid, name="N"):
        self.Guid = guid
        self.Name = types.SimpleNamespace(
            BestAnalysisAlternative=types.SimpleNamespace(Text=name))


class _Wrapper:
    """flexicon AffixSlot shape: _concrete + _obj, NO public .concrete."""

    def __init__(self, raw, base=None):
        self._concrete = raw
        self._obj = base if base is not None else raw

    def __getattr__(self, name):
        raise AttributeError(name)


def _strict(iface):
    def cast(o):
        if not isinstance(o, _Raw):
            raise TypeError("object does not implement %s" % iface)
        return o
    return cast


@pytest.fixture(autouse=True)
def strict_lcm(monkeypatch):
    mod = types.ModuleType("SIL.LCModel")
    mod.ICmObject = _strict("ICmObject")
    mod.IMoInflAffixSlot = _strict("IMoInflAffixSlot")
    monkeypatch.setitem(sys.modules, "SIL", types.ModuleType("SIL"))
    monkeypatch.setitem(sys.modules, "SIL.LCModel", mod)


def test_unwrap_fallback_order():
    raw, base = _Raw("a"), _Raw("b")
    assert unwrap(_Wrapper(raw, base)) is raw                    # _concrete first
    w = _Wrapper(None, base)
    assert unwrap(w) is base                                     # then _obj
    pub = types.SimpleNamespace(concrete=raw, _concrete=base)
    assert unwrap(pub) is raw                                    # .concrete first
    assert unwrap(raw) is raw and unwrap(None) is None           # passthrough


@pytest.mark.parametrize("mod", [transfer, preview, conflict, merge_preview])
def test_all_four_unwraps_reach_the_raw_object(mod):
    raw = _Raw("g")
    assert mod._unwrap(_Wrapper(raw)) is raw


class _POS:
    def __init__(self, slots):
        self._slots = slots

    def GetAffixSlots(self, pos):  # noqa: N802
        return list(self._slots)


def _target(slots):
    return types.SimpleNamespace(POS=_POS(slots))


def test_row1_find_target_slot_by_guid():
    raw = _Raw("g1")
    assert transfer._find_target_slot_by_guid(_target([_Wrapper(raw)]), None, "g1") is raw


def test_row2_scan_fallback_guid_match():
    raw = _Raw("g1")
    assert transfer._guid_str(transfer._unwrap(_Wrapper(raw))) == "g1"


def test_row3_slot_name_both_modules():
    w = _Wrapper(_Raw("g1", "LOC"))
    assert transfer._slot_name(w) == "LOC"
    assert preview._slot_name(w) == "LOC"


def test_row4_preview_target_has_slot_guid(monkeypatch):
    monkeypatch.setattr(preview, "_find_pos_by_guid", lambda t, g: object(),
                        raising=False)
    assert preview._target_has_slot_guid(_target([_Wrapper(_Raw("g1"))]),
                                         "pos", "g1") is True


def test_row5_merge_preview_obj_guid_and_unwrap_on_wrapper():
    # merge_preview's slot scan iterates RAW refs, but _obj_guid/_unwrap must
    # still be safe on a wrapper.
    w = _Wrapper(_Raw("g1"))
    assert merge_preview._obj_guid(w) == "g1"
    assert merge_preview._unwrap(w) is w._concrete


def test_lcm_slot_prefers_concrete_over_obj(monkeypatch):
    raw, base = _Raw("c"), _Raw("o")
    seen = {}
    from gramtrans.Lib import categories
    monkeypatch.setattr(categories, "_cast_lcm",
                        lambda o, n: seen.setdefault("o", o))
    transfer._lcm_slot(_Wrapper(raw, base))
    assert seen["o"] is raw


# ---- P2: equal-set OVERWRITE is a no-op ---------------------------------

class _G:
    def __init__(self, guid):
        self.guid = guid


class _Coll:
    def __init__(self, items):
        self.items, self.writes = list(items), 0

    def Add(self, i):  # noqa: N802
        self.writes += 1
        self.items.append(i)

    def Clear(self):  # noqa: N802
        self.writes += 1
        self.items.clear()

    def __iter__(self):
        return iter(list(self.items))


class _IA:
    def __init__(self, items):
        self.SlotsRC = _Coll(items)


class _Sink:
    def Warning(self, m): pass  # noqa: N802,E704
    def Info(self, m): pass  # noqa: N802,E704


def _overwrite(tgt_members, src_members):
    s1, s2, s3 = _G("s1"), _G("s2"), _G("s3")
    idx = {"s1": s1, "s2": s2, "s3": s3}
    new_ia = _IA([idx[g] for g in tgt_members])
    links = []
    transfer._overwrite_msa_slots(
        _IA([_G(g) for g in src_members]), new_ia, idx, src_msa_guid="m",
        entry_guid="e", report_sink=_Sink(), dropped=[], affix_slot_links=links)
    return new_ia, links


def test_equal_slot_sets_skip_clear_and_add_even_when_reordered():
    ia, links = _overwrite(["s1", "s2"], ["s2", "s1"])
    assert ia.SlotsRC.writes == 0 and links == []
    assert [x.guid for x in ia.SlotsRC.items] == ["s1", "s2"]


def test_differing_slot_sets_still_rewrite():
    ia, links = _overwrite(["s1"], ["s2", "s3"])
    assert ia.SlotsRC.writes > 0 and links == []
    assert {x.guid for x in ia.SlotsRC.items} == {"s2", "s3"}
