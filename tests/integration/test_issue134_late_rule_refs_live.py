"""Issue #134 live gate -- phon-rule InputPOSesRC and adhoc-prohibition member
chains are wired by the post-loop pass after the POS / allomorphs / MSAs they
reference exist.

WRITE PATH: writes ONLY the throwaway ``Target`` (restored from a known backup
before and after). Source ``Mbugwe LizzieHC practice`` is opened read-only.

Run (hold the lockout claim on Target first):
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue134_late_rule_refs_live.py -v -s
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
ADHOC = ["33541817-2fe3-423a-ba75-e9e2e8f36cf5",
         "e95de38e-6177-421a-817d-8af6054c5ef8"]
RULES = ["dd7188af-2dec-4658-b3f4-f1bbac37dfa1",
         "3fa6f87d-aa61-4daf-b575-ba204feed9ad"]

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


def _state(name):
    """{adhoc guid: [chain guids]}, {rule guid: sorted InputPOS guids}."""
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    from SIL.LCModel import ICmObject, IPhRegularRule, IMoMorphAdhocProhib
    g = lambda o: str(ICmObject(o).Guid).lower()
    p = FLExProject()
    p.OpenProject(projectName=name, writeEnabled=False)
    try:
        adhoc, poses = {}, {}
        for r in p.lp.MorphologicalDataOA.AdhocCoProhibitionsOC:
            if g(r) in ADHOC:
                m = IMoMorphAdhocProhib(r)
                first = m.FirstMorphemeRA
                adhoc[g(r)] = ([g(first)] if first is not None else []) + [
                    g(x) for x in m.RestOfMorphsRS]
        for r in (getattr(x, "_obj", x) for x in p.PhonRules.GetAll()):
            if g(r) in RULES:
                poses[g(r)] = sorted(
                    g(pos) for rhs in IPhRegularRule(r).RightHandSidesOS
                    for pos in rhs.InputPOSesRC)
        return adhoc, poses
    finally:
        p.CloseProject()


def _run(monkeypatch, enable):
    from harness import full_run
    from gramtrans.Lib import transfer
    if not enable:
        monkeypatch.setattr(transfer, "_ensure_late_rule_refs",
                            lambda *a, **k: None)
    counts = []
    real = transfer._ensure_late_rule_refs

    def _spy(ctx, tgt, skips):
        real(ctx, tgt, skips)
        counts.append(getattr(ctx, "_late_rule_ref_writes", None))
    if enable:
        monkeypatch.setattr(transfer, "_ensure_late_rule_refs", _spy)
    plan, report = full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset())
    monkeypatch.undo()
    return report, counts


def test_late_rule_refs_wired_and_rerun_writes_nothing(monkeypatch):
    src_adhoc, src_poses = _state(SOURCE_NAME)
    print("[LIVE] source adhoc=%s poses=%s" % (src_adhoc, src_poses))
    assert all(src_adhoc.values()) and all(src_poses.values())

    _run(monkeypatch, enable=False)
    base_adhoc, base_poses = _state(TARGET_NAME)
    print("[LIVE] BASELINE (pass disabled) adhoc=%s poses=%s"
          % (base_adhoc, base_poses))
    _restore()

    report, counts = _run(monkeypatch, enable=True)
    adhoc, poses = _state(TARGET_NAME)
    print("[LIVE] FIXED run1 adhoc=%s poses=%s counts=%s"
          % (adhoc, poses, counts))
    assert adhoc == src_adhoc
    assert poses == src_poses
    stale = [d for d in report.dropped_items
             if d.field_name == "InputPOSesRC"
             and d.owner_label and any(r[:8] in d.owner_label for r in RULES)]
    assert stale == [], stale

    _report2, counts2 = _run(monkeypatch, enable=True)
    print("[LIVE] run2 counts=%s" % counts2)
    assert counts2 and all(
        v == 0 for k, v in counts2[-1].items() if k in ("input_poses", "adhoc"))
    assert _state(TARGET_NAME) == (src_adhoc, src_poses)
