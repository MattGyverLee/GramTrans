"""Issue #15 / spec 041 -- offline pins for the opt-in stale-reference
re-point. Duck-typed fakes only; live behaviour is covered by
tests/integration/test_issue15_link_repoint_live.py."""
from __future__ import annotations

from types import SimpleNamespace

from gramtrans.Lib import categories as c
from gramtrans.Lib.models import ConflictMode, GrammarCategory, Selection


class _Pos:
    def __init__(self, guid, cls="PartOfSpeech"):
        self.guid = guid
        self.ClassName = cls


def test_stale_null_repointed():
    p = _Pos("p1")
    assert c.classify_ref_repoint(p, None, {"p1": p}) == (c.REPOINT, p)


def test_stale_different_class_repointed():
    p = _Pos("p1")
    assert c.classify_ref_repoint(p, _Pos("x", "MoInflClass"), {"p1": p}) == (c.REPOINT, p)


def test_valid_but_different_untouched():
    p = _Pos("p1")
    assert c.classify_ref_repoint(p, _Pos("p2"), {"p1": p, "p2": _Pos("p2")}) == (
        c.REPOINT_SKIP_NOT_STALE, None)


def test_already_correct_is_noop():
    p = _Pos("p1")
    assert c.classify_ref_repoint(p, _Pos("p1"), {"p1": p})[0] == c.REPOINT_NOOP
    assert c.classify_ref_repoint(None, None, {})[0] == c.REPOINT_NOOP


def test_unresolvable_referent_skips():
    p = _Pos("p1")
    assert c.classify_ref_repoint(p, None, {}) == (c.REPOINT_SKIP_UNRESOLVED, None)
    # same GUID present but wrong class in target -> not a valid referent
    assert c.classify_ref_repoint(
        p, None, {"p1": _Pos("p1", "MoInflClass")})[0] == c.REPOINT_SKIP_UNRESOLVED


# --- compute / pass over fakes ------------------------------------------------

def _allo(guid, ref):
    return SimpleNamespace(guid=guid, ClassName="MoAffixAllomorph",
                           MsEnvPartOfSpeechRA=ref)


def _proj(allos, poses):
    entries = [SimpleNamespace(guid="e" + a.guid, AlternateFormsOS=[],
                               LexemeFormOA=a) for a in allos]
    lp = SimpleNamespace(
        LexDbOA=SimpleNamespace(Entries=entries),
        PartsOfSpeechOA=SimpleNamespace(PossibilitiesOS=poses))
    return SimpleNamespace(Cache=SimpleNamespace(LangProject=lp))


def _sel(flag=True, mode=ConflictMode.LINK):
    return Selection(categories={GrammarCategory.AFFIXES: True},
                     category_conflict_modes={GrammarCategory.AFFIXES: mode},
                     repoint_stale_refs=flag)


def _world():
    p1 = _Pos("p1")
    p1.SubPossibilitiesOS = []
    src = _proj([_allo("a1", p1)], [p1])
    t_p1 = _Pos("p1")
    t_p1.SubPossibilitiesOS = []
    tgt_allo = _allo("a1", None)
    tgt = _proj([tgt_allo], [t_p1])
    return src, tgt, tgt_allo, t_p1


def test_flag_off_or_wrong_mode_yields_nothing():
    src, tgt, _a, _p = _world()
    assert c.compute_ref_repoints(src, tgt, _sel(flag=False)) == []
    assert c.compute_ref_repoints(src, tgt, _sel(mode=ConflictMode.ADD_NEW)) == []


def test_preview_rows_match_move_writes_and_idempotent():
    src, tgt, tgt_allo, t_p1 = _world()
    sel = _sel()
    rows = c.compute_ref_repoints(src, tgt, sel)
    assert [r[2] for r in rows] == [c.REPOINT]
    ctx = SimpleNamespace(source_handle=src,
                          _run_plan=SimpleNamespace(selection=sel))
    assert c._run_ref_repoint_pass(ctx, tgt) == []
    assert ctx._ref_repoint_writes == len(rows) == 1
    assert tgt_allo.MsEnvPartOfSpeechRA is t_p1
    assert c.compute_ref_repoints(src, tgt, sel) == []
    c._run_ref_repoint_pass(ctx, tgt)
    assert ctx._ref_repoint_writes == 0


def test_valid_different_ref_reported_not_written():
    src, tgt, tgt_allo, _p = _world()
    other = _Pos("p9")
    tgt_allo.MsEnvPartOfSpeechRA = other
    ctx = SimpleNamespace(source_handle=src,
                          _run_plan=SimpleNamespace(selection=_sel()))
    skips = c._run_ref_repoint_pass(ctx, tgt)
    assert ctx._ref_repoint_writes == 0 and tgt_allo.MsEnvPartOfSpeechRA is other
    assert len(skips) == 1 and "not provably stale" in skips[0].detail
