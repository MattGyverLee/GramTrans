"""Issue #134 (MED sites) live gate -- allomorph PhoneEnvRC/PositionRS/StemNameRA,
affix-template slot sequences + StratumRA, compound-rule StratumRA and owned
MSA PartOfSpeechRA are repaired by the post-loop pass when their OWNER is
already present in the target.

Scenario: run 1 (full transfer) -> snapshot -> DAMAGE those references on
Target -> run 2 (every owner is ALREADY_PRESENT) -> state equals the snapshot;
run 3 writes nothing.

WRITE PATH: writes ONLY the throwaway ``Target`` (restored from a known backup
before and after). Source ``Mbugwe LizzieHC practice`` is opened read-only.

Run (hold the lockout claim on Target first):
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue134_med_ref_repair_live.py -v -s
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_live_project]
if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1", allow_module_level=True)

SOURCE_NAME = "Mbugwe LizzieHC practice"
TARGET_NAME = "Target"
PROJECTS = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS / TARGET_NAME / (TARGET_NAME + ".fwdata"))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))
_REPO = Path(__file__).resolve().parents[2]


def _restore():
    from harness.restore import restore_target
    for d in (_REPO / "backups",
              Path("D:/Github/_Projects/_LEX/GramTrans/backups")):
        if (d / BACKUP_NAME).is_file():
            restore_target(TARGET_NAME, backup_path=d / BACKUP_NAME)
            return
    pytest.fail("backup not found")


@pytest.fixture(autouse=True)
def _around():
    _restore()
    yield
    _restore()


def _open(name, write):
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    p = FLExProject()
    if write:
        assert name == TARGET_NAME
        p.OpenProject(projectName=name, writeEnabled=True, undoable=False)
    else:
        p.OpenProject(projectName=name, writeEnabled=False)
    return p


def _templates_and_rules(p):
    from gramtrans.Lib import categories as c
    tpls = []
    for pos in c._iter_pos(p):
        tpls.extend(getattr(c._as_pos(pos), "AffixTemplatesOS", None) or [])
    rules = [r for r in c._rules_enumerate_all(p)
             if getattr(r, "ClassName", None) in
             ("MoEndoCompound", "MoExoCompound")]
    return tpls, rules


def _allos(p):
    from gramtrans.Lib import categories as c
    return list(c._iter_all_allomorphs(p))


def _state(name):
    """Per-object reference state, keyed by guid, for the repaired fields."""
    from gramtrans.Lib import categories as c
    g = c._guid_str_from
    p = _open(name, False)
    from SIL.LCModel import IMoInflAffixTemplate
    try:
        st = {}
        for a in _allos(p):
            cc = c._cast_to_concrete(a)
            st[("allo", g(a))] = (
                tuple(sorted(g(x) for x in (getattr(cc, "PhoneEnvRC", None) or []))),
                tuple(g(x) for x in (getattr(cc, "PositionRS", None) or [])),
                g(getattr(cc, "StemNameRA", None)) if getattr(
                    cc, "StemNameRA", None) is not None else "")
        tpls, rules = _templates_and_rules(p)
        for t in tpls:
            tt = IMoInflAffixTemplate(t)
            seqs = tuple(tuple(g(x) for x in (getattr(tt, s, None) or []))
                         for s in c._TEMPLATE_SLOT_SEQS)
            strat = tt.StratumRA
            st[("tpl", g(t))] = (seqs, g(strat) if strat is not None else "")
        for r in rules:
            rc = c._cast_rule_concrete(r)
            strat = getattr(rc, "StratumRA", None)
            pos = []
            for slot in ("LeftMsaOA", "RightMsaOA", "OverridingMsaOA",
                         "ToMsaOA"):
                m = getattr(rc, slot, None)
                if m is not None:
                    pr = getattr(c._cast_to_concrete(m), "PartOfSpeechRA", None)
                    pos.append(g(pr) if pr is not None else "")
            st[("rule", g(r))] = (g(strat) if strat is not None else "",
                                  tuple(pos))
        return st
    finally:
        p.CloseProject()


def _damage():
    """Null / clear every field the pass repairs, on Target only."""
    from gramtrans.Lib import categories as c
    p = _open(TARGET_NAME, True)
    from SIL.LCModel import IMoInflAffixTemplate
    try:
        assert p.ProjectName() == TARGET_NAME
        for a in _allos(p):
            cc = c._cast_to_concrete(a)
            for attr in ("PhoneEnvRC", "PositionRS"):
                coll = getattr(cc, attr, None)
                if coll is not None:
                    coll.Clear()
            if getattr(cc, "StemNameRA", None) is not None:
                cc.StemNameRA = None
        tpls, rules = _templates_and_rules(p)
        for t in tpls:
            tt = IMoInflAffixTemplate(t)
            for s in c._TEMPLATE_SLOT_SEQS:
                seq = getattr(tt, s, None)
                if seq is not None:
                    seq.Clear()
            tt.StratumRA = None
        for r in rules:
            rc = c._cast_rule_concrete(r)
            rc.StratumRA = None
            for slot in ("LeftMsaOA", "RightMsaOA", "OverridingMsaOA",
                         "ToMsaOA"):
                m = getattr(rc, slot, None)
                if m is not None:
                    c._cast_to_concrete(m).PartOfSpeechRA = None
    finally:
        p.CloseProject()


def _summ(st):
    out = {"allo_env": 0, "allo_pos": 0, "allo_stemname": 0, "tpl_slots": 0,
           "tpl_stratum": 0, "rule_stratum": 0, "rule_msa_pos": 0}
    for (kind, _g), v in st.items():
        if kind == "allo":
            out["allo_env"] += len(v[0])
            out["allo_pos"] += len(v[1])
            out["allo_stemname"] += bool(v[2])
        elif kind == "tpl":
            out["tpl_slots"] += sum(len(s) for s in v[0])
            out["tpl_stratum"] += bool(v[1])
        else:
            out["rule_stratum"] += bool(v[0])
            out["rule_msa_pos"] += sum(1 for x in v[1] if x)
    return out


def _run(monkeypatch):
    from harness import full_run
    from gramtrans.Lib import transfer
    counts = []
    real = transfer._ensure_late_rule_refs

    def _spy(ctx, tgt, skips):
        real(ctx, tgt, skips)
        counts.append(getattr(ctx, "_late_rule_ref_writes", None))
    monkeypatch.setattr(transfer, "_ensure_late_rule_refs", _spy)
    full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset())
    monkeypatch.undo()
    return counts


def test_med_refs_repaired_on_present_owners(monkeypatch):
    src = _summ(_state(SOURCE_NAME))
    _run(monkeypatch)
    snap = _state(TARGET_NAME)
    print("[LIVE] source summary  =", src)
    print("[LIVE] run1 target     =", _summ(snap))
    assert any(_summ(snap).values()), "scenario has no refs to repair"

    _damage()
    dmg = _state(TARGET_NAME)
    print("[LIVE] after DAMAGE    =", _summ(dmg))
    assert _summ(dmg) != _summ(snap)

    counts2 = _run(monkeypatch)
    fixed = _state(TARGET_NAME)
    print("[LIVE] run2 (repaired) =", _summ(fixed), "counts=", counts2)
    assert fixed == snap
    assert counts2 and counts2[-1]["allomorph_refs"] \
        + counts2[-1]["template_rule_refs"] > 0

    counts3 = _run(monkeypatch)
    print("[LIVE] run3 counts     =", counts3)
    assert all(v == 0 for v in counts3[-1].values()), counts3[-1]
    assert _state(TARGET_NAME) == snap
