"""Issue #135 slice 2 live gate -- LexReference.Name/Comment, LexEntryInflType
GlossPrepend/GlossAppend, adhoc prohibition Adjacency/Disabled round-trip.

WRITE PATH: writes ONLY two throwaways (never Esperanto, never shared Target):

* ``GT-Src-135-s2`` -- SOURCE: fresh file copy of ``Korean-GIAL`` (never opened
  itself; its .fwdata SHA-256 is asserted unchanged), seeded here.
* ``GT-Sandbox-135`` -- TARGET: restored headlessly from
  ``Target 2026-07-06 0218.fwbackup`` before and after.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue135_slice2_live.py -v -s
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
SOURCE_NAME = "GT-Src-135-s2"
TARGET_NAME = "GT-Sandbox-135"
TARGET_PATH = str(ROOT / TARGET_NAME / (TARGET_NAME + ".fwdata"))
ORIGIN_PATH = ROOT / ORIGIN / (ORIGIN + ".fwdata")
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
ENTRY = "00e82a75-27fe-4396-9fa3-38b6cac28581"   # stem entry, no refs

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))

REL_NAME = {"en": "135 rel name"}
REL_COMMENT = {"en": "135 rel comment"}
PREPEND = {"en": "135pre"}
APPEND = {"en": "135app"}
ADJ = 2


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
    from SIL.LCModel import (
        ILexEntry, ILexEntryInflType, ILexEntryInflTypeFactory,
        ILexRefType, ILexRefTypeFactory, ILexReferenceFactory,
        IMoMorphAdhocProhibFactory, ILexDb, IMoMorphData,
    )
    try:
        lp = proj.lp
        lexdb = ILexDb(lp.LexDbOA)
        a = _obj(proj, ENTRY, ILexEntry)
        other = None
        for e in proj.LexiconAllEntries():
            e = ILexEntry(e.concrete if hasattr(e, "concrete") else e)
            if (str(e.Guid) != ENTRY and e.SensesOS.Count >= 1
                    and e.EntryRefsOS.Count == 0 and e.AlternateFormsOS.Count == 0):
                other = e
                break
        assert other is not None and a.SensesOS.Count >= 1
        # Lexical relation (default mapping type: sense collection).
        rt = ILexRefType(proj.GetFactory(ILexRefTypeFactory).Create())
        lexdb.ReferencesOA.PossibilitiesOS.Add(rt)
        _set_ms(proj, rt.Name, {"en": "135 rel type"})
        rel = proj.GetFactory(ILexReferenceFactory).Create()
        rt.MembersOC.Add(rel)
        rel.TargetsRS.Add(a.SensesOS[0])
        rel.TargetsRS.Add(other.SensesOS[0])
        _set_ms(proj, rel.Name, REL_NAME)
        _set_ms(proj, rel.Comment, REL_COMMENT)
        # Inflectional variant type with glosses.
        it = ILexEntryInflType(proj.GetFactory(ILexEntryInflTypeFactory).Create())
        lexdb.VariantEntryTypesOA.PossibilitiesOS.Add(it)
        _set_ms(proj, it.Name, {"en": "135 infl type"})
        _set_ms(proj, it.GlossPrepend, PREPEND)
        _set_ms(proj, it.GlossAppend, APPEND)
        # Adhoc morph prohibition with Adjacency / Disabled.
        ap = proj.GetFactory(IMoMorphAdhocProhibFactory).Create()
        IMoMorphData(lp.MorphologicalDataOA).AdhocCoProhibitionsOC.Add(ap)
        ap.Adjacency = ADJ
        ap.Disabled = True
        return {"a": str(a.Guid), "other": str(other.Guid), "rt": str(rt.Guid),
                "rel": str(rel.Guid), "it": str(it.Guid), "ap": str(ap.Guid)}
    finally:
        proj.CloseProject()


def _read_target(g):
    from SIL.LCModel import (ILexReference, ILexEntryInflType,
                             IMoMorphAdhocProhib)
    proj = _open(TARGET_NAME)
    try:
        rel = _obj(proj, g["rel"], ILexReference)
        it = _obj(proj, g["it"], ILexEntryInflType)
        ap = _obj(proj, g["ap"], IMoMorphAdhocProhib)
        return {
            "rel.Name": _get_ms(proj, rel.Name),
            "rel.Comment": _get_ms(proj, rel.Comment),
            "rel.targets": rel.TargetsRS.Count,
            "it.GlossPrepend": _get_ms(proj, it.GlossPrepend),
            "it.GlossAppend": _get_ms(proj, it.GlossAppend),
            "ap.Adjacency": int(ap.Adjacency),
            "ap.Disabled": bool(ap.Disabled),
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


def _run(g):
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    def _sel(_full):
        picks = frozenset({g["a"], g["other"]})
        return Selection(
            categories={GC.STEMS: True, GC.AFFIXES: True,
                        GC.VARIANT_TYPES: True, GC.ADHOC_COMPOUND_RULES: True},
            include_closure=True,
            leaf_item_picks={GC.STEMS: picks, GC.AFFIXES: picks,
                             GC.VARIANT_TYPES: frozenset({g["it"]}),
                             GC.ADHOC_COMPOUND_RULES: frozenset({g["ap"]})})
    return full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, ws_mapping_mode="full",
        selection_transform=_sel)


def test_slice2_fields_round_trip(src):
    plan, report = _run(src)
    got = _read_target(src)
    print("[LIVE] target values:", got)
    names = {"Name", "Comment", "GlossPrepend", "GlossAppend", "Adjacency", "Disabled"}
    drops = [(d.owner_kind, d.field_name, d.reason) for d in report.dropped_items or ()
             if d.field_name in names]
    print("[LIVE] #135 slice-2 drops:", drops)
    assert got["rel.Name"] == REL_NAME and got["rel.Comment"] == REL_COMMENT
    assert got["rel.targets"] == 2
    assert got["it.GlossPrepend"] == PREPEND and got["it.GlossAppend"] == APPEND
    assert got["ap.Adjacency"] == ADJ and got["ap.Disabled"] is True
    assert drops == []
