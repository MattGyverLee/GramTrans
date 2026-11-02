"""Issue #135 slice 3 live gate -- Fs feature-definition / symbolic-value
GlossAbbreviation, RightGlossSep, ShowInGloss, DisplayToRightOfValues.

WRITE PATH: writes ONLY two throwaways (never Esperanto, never shared Target):

* ``GT-Src-135-s3`` -- SOURCE: fresh file copy of ``Korean-GIAL`` (never opened
  itself; its .fwdata SHA-256 is asserted unchanged), seeded here.
* ``GT-Sandbox-135-s3`` -- TARGET: restored headlessly from
  ``Target 2026-07-06 0218.fwbackup`` before and after.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue135_slice3_live.py -v -s
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_live_project]

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)
if importlib.util.find_spec("flexicon") is None:
    pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is not importable",
                pytrace=False)

ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
ORIGIN = "Korean-GIAL"
SOURCE_NAME = "GT-Src-135-s3"
TARGET_NAME = "GT-Sandbox-135-s3"
TARGET_PATH = str(ROOT / TARGET_NAME / (TARGET_NAME + ".fwdata"))
ORIGIN_PATH = ROOT / ORIGIN / (ORIGIN + ".fwdata")
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))

FEAT_GLOSS = {"en": "135fg"}
FEAT_SEP = {"en": "135sep"}
VAL_GLOSS = {"en": "135vg"}
VAL_SEP = {"en": "135vsep"}
PHON_GLOSS = {"en": "135pg"}


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _restore():
    from harness.restore import restore_target
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            restore_target(TARGET_NAME, backup_path=d / BACKUP_NAME)
            return
    pytest.fail("[FAIL] backup not found", pytrace=False)


def _open(name, write=False):
    if write:
        assert name == SOURCE_NAME
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    p = FLExProject()
    if write:
        p.OpenProject(projectName=name, writeEnabled=True, undoable=False)
    else:
        p.OpenProject(projectName=name, writeEnabled=False)
    return p


def _h(proj, ws_id):
    for ws in proj.WritingSystems.GetAll():
        if ws.Id == ws_id:
            return ws.Handle
    pytest.fail("no ws %s" % ws_id, pytrace=False)


def _set_ms(proj, ms, alts):
    from SIL.LCModel.Core.Text import TsStringUtils
    for ws_id, text in alts.items():
        h = _h(proj, ws_id)
        ms.set_String(h, TsStringUtils.MakeString(text, h))


def _get_ms(proj, ms):
    out = {}
    for ws in proj.WritingSystems.GetAll():
        t = ms.get_String(ws.Handle).Text
        if t:
            out[ws.Id] = str(t)
    return out


def _obj(proj, guid, iface):
    from SIL.LCModel import ICmObjectRepository
    from System import Guid
    return iface(proj.ObjectRepository(ICmObjectRepository).GetObject(Guid.Parse(guid)))


def _build_source():
    sdir = ROOT / SOURCE_NAME
    if sdir.exists():
        shutil.rmtree(sdir)
    shutil.copytree(ROOT / ORIGIN, sdir, ignore=shutil.ignore_patterns("*.lock", "*.bak"))
    (sdir / (ORIGIN + ".fwdata")).rename(sdir / (SOURCE_NAME + ".fwdata"))
    proj = _open(SOURCE_NAME, write=True)
    from SIL.LCModel import (IFsClosedFeatureFactory, IFsClosedFeature,
                             IFsSymFeatValFactory, IFsSymFeatVal)
    try:
        lp = proj.lp
        # Inflection (morphosyntactic) feature + one value.
        f = IFsClosedFeature(proj.GetFactory(IFsClosedFeatureFactory).Create())
        lp.MsFeatureSystemOA.FeaturesOC.Add(f)
        _set_ms(proj, f.Name, {"en": "135 feat"})
        _set_ms(proj, f.Abbreviation, {"en": "135f"})
        _set_ms(proj, f.GlossAbbreviation, FEAT_GLOSS)
        _set_ms(proj, f.RightGlossSep, FEAT_SEP)
        f.ShowInGloss = True
        f.DisplayToRightOfValues = True
        v = IFsSymFeatVal(proj.GetFactory(IFsSymFeatValFactory).Create())
        f.ValuesOC.Add(v)
        _set_ms(proj, v.Name, {"en": "135 val"})
        _set_ms(proj, v.Abbreviation, {"en": "135v"})
        _set_ms(proj, v.GlossAbbreviation, VAL_GLOSS)
        _set_ms(proj, v.RightGlossSep, VAL_SEP)
        v.ShowInGloss = True
        # Phonological feature (feature-definition level only).
        pf = IFsClosedFeature(proj.GetFactory(IFsClosedFeatureFactory).Create())
        lp.PhFeatureSystemOA.FeaturesOC.Add(pf)
        _set_ms(proj, pf.Name, {"en": "135 phon feat"})
        _set_ms(proj, pf.Abbreviation, {"en": "135pf"})
        _set_ms(proj, pf.GlossAbbreviation, PHON_GLOSS)
        pf.ShowInGloss = True
        return {"f": str(f.Guid), "v": str(v.Guid), "pf": str(pf.Guid)}
    finally:
        proj.CloseProject()


def _read_target(g):
    from SIL.LCModel import IFsClosedFeature, IFsSymFeatVal
    proj = _open(TARGET_NAME)
    try:
        f = _obj(proj, g["f"], IFsClosedFeature)
        v = _obj(proj, g["v"], IFsSymFeatVal)
        pf = _obj(proj, g["pf"], IFsClosedFeature)
        return {
            "f.GlossAbbreviation": _get_ms(proj, f.GlossAbbreviation),
            "f.RightGlossSep": _get_ms(proj, f.RightGlossSep),
            "f.ShowInGloss": bool(f.ShowInGloss),
            "f.DisplayToRightOfValues": bool(f.DisplayToRightOfValues),
            "v.GlossAbbreviation": _get_ms(proj, v.GlossAbbreviation),
            "v.RightGlossSep": _get_ms(proj, v.RightGlossSep),
            "v.ShowInGloss": bool(v.ShowInGloss),
            "pf.GlossAbbreviation": _get_ms(proj, pf.GlossAbbreviation),
            "pf.ShowInGloss": bool(pf.ShowInGloss),
        }
    finally:
        proj.CloseProject()


@pytest.fixture(scope="module")
def src():
    before = _sha(ORIGIN_PATH)
    g = _build_source()
    yield g
    assert _sha(ORIGIN_PATH) == before, "Korean-GIAL changed"


@pytest.fixture(autouse=True)
def _around():
    _restore()
    yield
    _restore()


def _run():
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    def _sel(_full):
        return Selection(
            categories={GC.INFLECTION_FEATURES: True, GC.PHONOLOGICAL_FEATURES: True},
            include_closure=True)
    return full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, ws_mapping_mode="full",
        selection_transform=_sel)


def test_slice3_fields_round_trip(src):
    plan, report = _run()
    got = _read_target(src)
    print("[LIVE] target values:", got)
    names = {"GlossAbbreviation", "RightGlossSep", "ShowInGloss",
             "DisplayToRightOfValues"}
    drops = [(d.owner_kind, d.field_name, d.reason) for d in report.dropped_items or ()
             if d.field_name in names]
    print("[LIVE] #135 slice-3 drops:", drops)
    assert got["f.GlossAbbreviation"] == FEAT_GLOSS
    assert got["f.RightGlossSep"] == FEAT_SEP
    assert got["f.ShowInGloss"] is True and got["f.DisplayToRightOfValues"] is True
    assert got["v.GlossAbbreviation"] == VAL_GLOSS
    assert got["v.RightGlossSep"] == VAL_SEP and got["v.ShowInGloss"] is True
    assert got["pf.GlossAbbreviation"] == PHON_GLOSS and got["pf.ShowInGloss"] is True
    assert drops == []
