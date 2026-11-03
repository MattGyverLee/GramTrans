"""Issue #134 (MED sites) -- offline pins for the late repair helpers.

Duck-typed fakes only. Live behaviour is covered by
tests/integration/test_issue134_med_ref_repair_live.py.
"""
from __future__ import annotations

from types import SimpleNamespace

from gramtrans.Lib import categories
from gramtrans.Lib.models import SkipReason


class _Obj:
    def __init__(self, guid):
        self.guid = guid
        self.Name = None


class _Seq(list):
    def Add(self, x):
        self.append(x)

    def Insert(self, i, x):
        self.insert(i, x)


class _NoOpAddSeq(_Seq):
    """Add does nothing — simulates a silent LCM no-op (#132)."""

    def Add(self, x):
        pass


def test_insert_missing_in_order():
    a, b, c = _Obj("a"), _Obj("b"), _Obj("c")
    tgt = _Seq([c])
    n = categories._insert_missing_in_order(
        tgt, [a, b, c], {"a": a, "b": b, "c": c}, lambda o, g: None)
    assert n == 2 and list(tgt) == [a, b, c]
    assert categories._insert_missing_in_order(
        tgt, [a, b, c], {"a": a, "b": b, "c": c}, lambda o, g: None) == 0


def test_insert_missing_diverged_returns_none_untouched():
    a, x = _Obj("a"), _Obj("x")
    tgt = _Seq([x])
    assert categories._insert_missing_in_order(
        tgt, [a], {"a": a}, lambda o, g: None) is None
    assert list(tgt) == [x]


def test_insert_missing_absent_member_reported():
    a, b = _Obj("a"), _Obj("b")
    absent = []
    tgt = _Seq()
    n = categories._insert_missing_in_order(
        tgt, [a, b], {"a": a}, lambda o, g: absent.append(g))
    assert n == 1 and absent == ["b"] and list(tgt) == [a]


def test_set_ref_if_null_only_when_null_and_resolvable():
    st = _Obj("s")
    src = SimpleNamespace(StratumRA=st)
    tgt = SimpleNamespace(StratumRA=None)
    assert categories._set_ref_if_null(src, tgt, "StratumRA", {}) == 0
    assert categories._set_ref_if_null(src, tgt, "StratumRA", {"s": st}) == 1
    assert tgt.StratumRA is st
    other = _Obj("o")
    tgt.StratumRA = other
    assert categories._set_ref_if_null(src, tgt, "StratumRA", {"s": st}) == 0
    assert tgt.StratumRA is other


def test_repair_one_allomorph_env_and_position(monkeypatch):
    monkeypatch.setattr(categories, "_cast_to_concrete", lambda o: o)
    e1, e2 = _Obj("e1"), _Obj("e2")
    src = SimpleNamespace(guid="al", PhoneEnvRC=[e1, e2],
                          PositionRS=[e1, e2], StemNameRA=None)
    tgt = SimpleNamespace(guid="al", PhoneEnvRC=_Seq([e1]),
                          PositionRS=_Seq([e2]), StemNameRA=None)
    dropped, skips = [], []
    envs = {"e1": e1, "e2": e2}
    n = categories._repair_one_allomorph(src, tgt, "al", envs, None,
                                         dropped, skips)
    assert n == 2 and list(tgt.PhoneEnvRC) == [e1, e2]
    assert list(tgt.PositionRS) == [e1, e2] and not skips and not dropped
    assert categories._repair_one_allomorph(
        src, tgt, "al", envs, None, dropped, skips) == 0


def test_repair_one_allomorph_phone_env_add_failure_recorded(monkeypatch):
    monkeypatch.setattr(categories, "_cast_to_concrete", lambda o: o)
    e1, e2 = _Obj("e1"), _Obj("e2")
    src = SimpleNamespace(guid="al", PhoneEnvRC=[e1, e2], PositionRS=[],
                          StemNameRA=None)
    tgt = SimpleNamespace(guid="al", PhoneEnvRC=_NoOpAddSeq(), PositionRS=_Seq(),
                          StemNameRA=None)
    dropped, skips = [], []
    n = categories._repair_one_allomorph(
        src, tgt, "al", {"e1": e1, "e2": e2}, None, dropped, skips)
    assert n == 0
    assert len(dropped) == 2
    assert all(d.field_name == "PhoneEnvRC" for d in dropped)
    assert all("WRITE_FAILED" in d.reason for d in dropped)
    assert not skips


def test_repair_one_allomorph_absent_env_dropped(monkeypatch):
    monkeypatch.setattr(categories, "_cast_to_concrete", lambda o: o)
    e1 = _Obj("e1")
    src = SimpleNamespace(guid="al", PhoneEnvRC=[e1], PositionRS=[],
                          StemNameRA=None)
    tgt = SimpleNamespace(guid="al", PhoneEnvRC=_Seq(), PositionRS=_Seq(),
                          StemNameRA=None)
    dropped, skips = [], []
    n = categories._repair_one_allomorph(src, tgt, "al", {}, None,
                                         dropped, skips)
    assert n == 0 and [d.field_name for d in dropped] == ["PhoneEnvRC"]


def test_repair_one_allomorph_diverged_position_needs_manual(monkeypatch):
    monkeypatch.setattr(categories, "_cast_to_concrete", lambda o: o)
    e1, x = _Obj("e1"), _Obj("x")
    src = SimpleNamespace(guid="al", PhoneEnvRC=[], PositionRS=[e1],
                          StemNameRA=None)
    tgt = SimpleNamespace(guid="al", PhoneEnvRC=_Seq(), PositionRS=_Seq([x]),
                          StemNameRA=None)
    skips = []
    categories._repair_one_allomorph(src, tgt, "al", {"e1": e1}, None,
                                     [], skips)
    assert list(tgt.PositionRS) == [x]
    assert skips[0].reason == SkipReason.NEEDS_MANUAL


def test_insert_missing_insert_failure_reported():
    a, b = _Obj("a"), _Obj("b")
    failures = []

    class _RaisingSeq(_Seq):
        def Insert(self, i, x):
            if getattr(x, "guid", None) == "b":
                raise TypeError("Insert rejected")
            return super().Insert(i, x)

    tgt = _RaisingSeq()
    n = categories._insert_missing_in_order(
        tgt, [a, b], {"a": a, "b": b},
        lambda o, g: None,
        lambda o, g, detail: failures.append((g, detail)),
    )
    assert n == 1 and list(tgt) == [a]
    assert failures and failures[0][0] == "b"


def test_repair_one_allomorph_position_insert_failure_recorded(monkeypatch):
    monkeypatch.setattr(categories, "_cast_to_concrete", lambda o: o)
    e1, e2 = _Obj("e1"), _Obj("e2")

    class _RaisingSeq(_Seq):
        def Insert(self, i, x):
            if getattr(x, "guid", None) == "e2":
                raise TypeError("Insert rejected")
            return super().Insert(i, x)

    src = SimpleNamespace(guid="al", PhoneEnvRC=[], PositionRS=[e1, e2],
                          StemNameRA=None)
    tgt = SimpleNamespace(guid="al", PhoneEnvRC=_Seq(), PositionRS=_RaisingSeq(),
                          StemNameRA=None)
    dropped, skips = [], []
    n = categories._repair_one_allomorph(
        src, tgt, "al", {"e1": e1, "e2": e2}, None, dropped, skips)
    assert n == 1 and [d.field_name for d in dropped] == ["PositionRS"]
    assert list(tgt.PositionRS) == [e1]


def test_phoneme_features_late_latches(monkeypatch):
    calls = []
    monkeypatch.setattr(categories, "_wire_phoneme_features",
                        lambda c, t, tag: calls.append(1) or [])
    ctx = SimpleNamespace(_did_phoneme_features=False)
    categories._repair_phoneme_features_late(ctx, None, None, None, [])
    categories._repair_phoneme_features_late(ctx, None, None, None, [])
    assert calls == [1]
