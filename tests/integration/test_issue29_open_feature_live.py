"""Issue #29 live gate -- an IFsOpenFeature transfers GUID-preserved with its
WritingSystem / WsSelector, idempotently on re-run.

No probed project carries an open feature, so the gate SEEDS one: both
projects are private sandboxes restored headlessly from a known backup. The
seed open feature is written into the SOURCE sandbox ``GT-Src-29``; the Move
writes ONLY ``GT-Sandbox-29``. ``Target``, ``Esperanto`` and real projects are
never touched.

Skips unless FLEXLIBS_REQUIRE_LIVE=1 (then an unavailable LCM FAILS).

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue29_open_feature_live.py -v -s
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_live_project]

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "GT-Src-29"
TARGET_NAME = "GT-Sandbox-29"
ROOT = "C:/ProgramData/SIL/FieldWorks/Projects/"
TARGET_PATH = ROOT + TARGET_NAME + "/" + TARGET_NAME + ".fwdata"
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
OPEN_GUID = "29292929-aaaa-4bbb-8ccc-292929292929"

if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

_REPO = Path(__file__).resolve().parents[2]


def _restore(name: str) -> None:
    from harness.restore import restore_target
    restore_target(name, backup_path=_REPO / "backups" / BACKUP_NAME)


def _seed_source() -> str:
    """Add one FsOpenFeature to the source sandbox; return its WritingSystem."""
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    from System import Guid
    from SIL.LCModel.Core.Text import TsStringUtils
    from SIL.LCModel import IFsOpenFeatureFactory, IFsOpenFeature
    from SIL.LCModel.Infrastructure import NonUndoableUnitOfWorkHelper
    proj = FLExProject()
    proj.OpenProject(projectName=SOURCE_NAME, writeEnabled=True)
    try:
        cache = proj.project
        fs = cache.LangProject.MsFeatureSystemOA
        ws = cache.ServiceLocator.WritingSystems.DefaultAnalysisWritingSystem

        def _do():
            raw = cache.ServiceLocator.GetService(IFsOpenFeatureFactory).Create(
                Guid.Parse(OPEN_GUID))
            fs.FeaturesOC.Add(raw)
            f = IFsOpenFeature(raw)
            f.Name.set_String(ws.Handle, TsStringUtils.MakeString("OpenGate29", ws.Handle))
            f.WritingSystem = ws.Id
            f.WsSelector = -3
        from System import Action
        NonUndoableUnitOfWorkHelper.Do(cache.ActionHandlerAccessor, Action(_do))
        return ws.Id
    finally:
        proj.CloseProject()


def _read_target():
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    from SIL.LCModel import ICmObject, IFsOpenFeature
    proj = FLExProject()
    proj.OpenProject(projectName=TARGET_NAME, writeEnabled=False)
    try:
        out = []
        for f in proj.lp.MsFeatureSystemOA.FeaturesOC:
            if f.ClassName == "FsOpenFeature":
                o = IFsOpenFeature(f)
                out.append((str(ICmObject(f).Guid).lower(), o.WritingSystem, o.WsSelector))
        return out
    finally:
        proj.CloseProject()


def _run():
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory, Selection
    return full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH,
        selection_transform=lambda _f: Selection(
            categories={GrammarCategory.INFLECTION_FEATURES: True}))


def test_open_feature_transfers_and_is_idempotent():
    _restore(SOURCE_NAME)
    _restore(TARGET_NAME)
    ws_id = _seed_source()
    assert _read_target() == []
    plan1, report1 = _run()
    after1 = _read_target()
    print("[LIVE] run1 target open features:", after1)
    assert [g for g, _w, _s in after1] == [OPEN_GUID]
    assert after1[0][2] == -3
    assert after1[0][1], "WritingSystem not copied"
    assert not [s for s in report1.skips if s.source_guid == OPEN_GUID], report1.skips
    plan2, _report2 = _run()
    after2 = _read_target()
    print("[LIVE] run2 target open features:", after2)
    assert after2 == after1
    assert len(plan2.actions) == 0 or not [
        a for a in plan2.actions if getattr(a, "source_guid", None) == OPEN_GUID
        and "ALREADY" not in str(getattr(a, "kind", "")).upper()]
