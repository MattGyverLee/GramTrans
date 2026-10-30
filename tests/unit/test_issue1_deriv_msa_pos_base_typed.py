"""Issue #1 -- derivational MSA From-/ToPartOfSpeechRA on a BASE-TYPED proxy.

A live `ILexEntry.MorphoSyntaxAnalysesOC` member is typed
`IMoMorphSynAnalysis`; `From-`/`ToPartOfSpeechRA` are declared only on
`IMoDerivAffMsa`, so they are invisible until the ClassName-driven cast
(`categories._cast_to_concrete`). The fake here mimics that: POS attributes
raise AttributeError until `_cast_lcm` returns the concrete twin.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib import categories as C
from gramtrans.Lib import fingerprints as F
from gramtrans.Lib.models import GrammarCategory


class _Coll:
    def __init__(self, items=()):
        self._items = list(items)

    def __iter__(self):
        return iter(self._items)


class _Pos:
    def __init__(self, guid, abbr):
        self.Guid = guid
        self.Abbreviation = type("A", (), {"Text": abbr})()


class _ConcreteDeriv:
    ClassName = "MoDerivAffMsa"

    def __init__(self, frm, to):
        self.FromPartOfSpeechRA = frm
        self.ToPartOfSpeechRA = to
        self.SlotsRC = _Coll()


class _BaseProxy:
    """Base-typed proxy: only ClassName is visible; POS attrs raise."""
    ClassName = "MoDerivAffMsa"

    def __init__(self, concrete):
        self._concrete = concrete

    def __getattr__(self, name):
        raise AttributeError(name)


class _Entry:
    def __init__(self, msas):
        self.MorphoSyntaxAnalysesOC = _Coll(msas)


@pytest.fixture(autouse=True)
def _cast(monkeypatch):
    def fake_cast(obj, iface):
        if isinstance(obj, _BaseProxy) and iface == "IMoDerivAffMsa":
            return obj._concrete
        return obj
    monkeypatch.setattr(C, "_cast_lcm", fake_cast)
    # _guid_str_from reads .Guid off real LCM objects; the fake has .Guid too.


def _deriv(frm, to):
    return _BaseProxy(_ConcreteDeriv(frm, to))


def _pos_edges(entry):
    return {g for k, g in C.affixes_dependencies(entry)
            if k == GrammarCategory.GRAM_CATEGORIES}


def test_uncast_proxy_hides_pos():
    p = _deriv(_Pos("g-root", "Root"), _Pos("g-v", "v"))
    assert getattr(p, "FromPartOfSpeechRA", None) is None


def test_both_from_and_to_edges_emitted():
    e = _Entry([_deriv(_Pos("g-root", "Root"), _Pos("g-v", "v"))])
    assert _pos_edges(e) == {"g-root", "g-v"}


@pytest.mark.parametrize("frm,to,expected", [
    (None, _Pos("g-v", "v"), {"g-v"}),
    (_Pos("g-root", "Root"), None, {"g-root"}),
    (None, None, set()),
])
def test_null_side_is_skipped(frm, to, expected):
    assert _pos_edges(_Entry([_deriv(frm, to)])) == expected


def test_label_reads_through_cast_and_shows_from_to():
    p = _deriv(_Pos("g-root", "Root"), _Pos("g-v", "v"))
    assert F.msa_label_from_obj(p) == "Root>v"


def test_label_null_side():
    assert F.msa_label_from_obj(_deriv(None, _Pos("g-v", "v"))) == ">v"
    assert F.msa_label_from_obj(_deriv(None, None)) == ""


def test_import_error_falls_back_uncast_and_warns_once(monkeypatch, caplog):
    import builtins
    import logging

    real_import = builtins.__import__

    def boom(name, globals=None, locals=None, fromlist=(), level=0):
        if fromlist and "_cast_to_concrete" in fromlist:
            raise ImportError("simulated")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", boom)
    monkeypatch.setattr(F, "_CAST_IMPORT_WARNED", False)
    # Concrete-typed object: readable without a cast, so the fallback works.
    concrete = _ConcreteDeriv(_Pos("g-root", "Root"), _Pos("g-v", "v"))
    with caplog.at_level(logging.WARNING, logger=F.__name__):
        assert F.msa_label_from_obj(concrete) == "Root>v"
        assert F.msa_label_from_obj(concrete) == "Root>v"
    warns = [r for r in caplog.records if "_cast_to_concrete" in r.getMessage()]
    assert len(warns) == 1
