"""Issue #134 -- end-of-run repair of adhoc-prohibition member chains.

Offline: duck-typed fakes only. Pins: a chain the create path left empty is
completed once its members exist; insert-only (a diverged chain is reported,
not rewritten); an absent member is a DroppedItemRecord and ends wiring (no
reordering hole); a second run writes nothing; the transfer `_ensure` latches.
"""
from __future__ import annotations

from types import SimpleNamespace

from gramtrans.Lib import categories, transfer
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


def _rule(first=None, rest=()):
    return SimpleNamespace(guid="r1", FirstMorphemeRA=first,
                           RestOfMorphsRS=_Seq(rest))


def _target(msas):
    entry = SimpleNamespace(MorphoSyntaxAnalysesOC=list(msas))
    lex = SimpleNamespace(Entries=[entry])
    return SimpleNamespace(Cache=SimpleNamespace(
        LangProject=SimpleNamespace(LexDbOA=lex)))


def _run(src, tgt, target):
    dropped, skips = [], []
    n = categories._repair_adhoc_prohib_chain(
        src, tgt, "MoMorphAdhocProhib", target, dropped, skips)
    return n, dropped, skips


def test_empty_chain_completed_then_idempotent():
    a, b, c = _Obj("a"), _Obj("b"), _Obj("c")
    src = _rule(a, [b, c])
    tgt = _rule()
    target = _target([a, b, c])
    n, dropped, skips = _run(src, tgt, target)
    assert n == 3 and not dropped and not skips
    assert tgt.FirstMorphemeRA is a and list(tgt.RestOfMorphsRS) == [b, c]
    n2, _, _ = _run(src, tgt, target)
    assert n2 == 0


def test_live_shape_first_missing_rest_present():
    # create path wired Rest only (First MSA did not exist yet)
    a, b = _Obj("a"), _Obj("b")
    src = _rule(a, [b])
    tgt = _rule(None, [b])
    n, dropped, skips = _run(src, tgt, _target([a, b]))
    assert n == 1 and tgt.FirstMorphemeRA is a and list(tgt.RestOfMorphsRS) == [b]
    assert not dropped and not skips


def test_missing_rest_member_inserted_at_source_position():
    a, b, c = _Obj("a"), _Obj("b"), _Obj("c")
    src = _rule(a, [b, c])
    tgt = _rule(a, [c])
    n, _, _ = _run(src, tgt, _target([a, b, c]))
    assert n == 1 and list(tgt.RestOfMorphsRS) == [b, c]


def test_absent_member_dropped():
    a, b = _Obj("a"), _Obj("b")
    src = _rule(a, [b])
    tgt = _rule()
    n, dropped, _ = _run(src, tgt, _target([a]))  # b absent
    assert n == 1 and [d.item_guid for d in dropped] == ["b"]


def test_diverged_rest_left_alone_and_reported():
    a, b, x = _Obj("a"), _Obj("b"), _Obj("x")
    src = _rule(a, [b])
    tgt = _rule(a, [x])
    n, dropped, skips = _run(src, tgt, _target([a, b, x]))
    assert n == 0 and list(tgt.RestOfMorphsRS) == [x]
    assert skips and skips[0].reason == SkipReason.NEEDS_MANUAL


def test_ensure_latches_and_noop_without_plan(monkeypatch):
    calls = []
    monkeypatch.setattr(categories, "_run_late_rule_ref_repair_pass",
                        lambda ctx, tgt, tag=None: calls.append(1) or [])
    ctx = SimpleNamespace(_run_plan=None)
    transfer._ensure_late_rule_refs(ctx, None, [])
    assert calls == []
    ctx = SimpleNamespace(_run_plan=object())
    out = []
    transfer._ensure_late_rule_refs(ctx, None, out)
    transfer._ensure_late_rule_refs(ctx, None, out)
    assert calls == [1]
