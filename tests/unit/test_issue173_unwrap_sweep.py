"""Issue #173: sweep of bare `.concrete` / `_obj`-only unwrap sites (#130 class).

flexicon wrappers (AffixSlot-shaped) hold `_concrete`/`_obj` but no public
`.concrete`. A strict pythonnet-style cast of one raises TypeError, so every
site must route through `lcm_unwrap.unwrap`.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from gramtrans.Lib import categories as cats, selection, transfer  # noqa: E402


class _Raw:
    def __init__(self, guid="g1"):
        self.Guid = guid
        self.ClassName = "PartOfSpeech"
        self.MembersOC = []


class _Wrapper:
    """No public .concrete; _concrete + _obj only."""

    def __init__(self, raw):
        self._concrete = raw
        self._obj = raw

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
    for n in ("ICmObject", "IPartOfSpeech"):
        setattr(mod, n, _strict(n))
    monkeypatch.setitem(sys.modules, "SIL", types.ModuleType("SIL"))
    monkeypatch.setitem(sys.modules, "SIL.LCModel", mod)


def test_unwrap_lcm_uses_shared_order():
    raw = _Raw()
    assert cats._unwrap_lcm(_Wrapper(raw)) is raw
    assert cats._unwrap_lcm(raw) is raw


def test_as_pos_casts_wrapper():
    raw = _Raw()
    assert cats._as_pos(_Wrapper(raw)) is raw


def test_find_target_env_by_guid_wrapper():
    raw = _Raw("e1")
    target = types.SimpleNamespace(
        Environments=types.SimpleNamespace(GetAll=lambda: [_Wrapper(raw)]))
    assert transfer._find_target_env_by_guid(target, "e1") is raw


def test_selection_compound_walk_unwraps_wrapper():
    raw = _Raw()
    src = types.SimpleNamespace(
        MorphRules=types.SimpleNamespace(
            GetAllCompoundRules=lambda: [_Wrapper(raw)]))
    assert list(selection._rules_walk_compound(src)) == [raw]


def test_selection_adhoc_walk_unwraps_wrapper():
    raw = _Raw()
    src = types.SimpleNamespace(
        MorphRules=types.SimpleNamespace(
            GetAllAdhocCoProhibitions=lambda: [_Wrapper(raw)]))
    assert list(selection._rules_walk_adhoc(src)) == [(raw, None)]
