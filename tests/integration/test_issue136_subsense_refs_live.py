"""Issue #136 live gate -- sub-sense (and sub-sub-sense) AppendixesRC,
ThesaurusItemsRC and PicturesOS survive a REAL Preview + Move.

Before the fix `LexSense.SensesOS` sub-senses went only through
`_apply_reference_fields` / `_decide_reference_fields`; the 030 appendix /
thesaurus resolvers and the 029 picture seam never ran for them, so those three
fields were lost with no DroppedItemRecord.

WRITE PATH: writes ONLY the two private throwaway projects below, both rebuilt
from ``Target 2026-07-06 0218.fwbackup``:

* ``GT-Src-136``     -- SOURCE (write-enabled only while authoring)
* ``GT-Sandbox-136`` -- TARGET (a fork of the source after the shared appendix)

Names are pinned here, before any write.  Never GT-Src-42, Target, Esperanto.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue136_subsense_refs_live.py -v -s
"""
from __future__ import annotations

import os
import shutil
import struct
import sys
import tempfile
import zlib
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "GT-Src-136"
TARGET_NAME = "GT-Sandbox-136"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))

AP_PRESENT_TEXT = "Appendix 136-PRESENT: shared, linked by GUID"
AP_ABSENT_TEXT = "Appendix 136-ABSENT: source only, must drop"
_FIELDS = ("AppendixesRC", "ThesaurusItemsRC", "PicturesOS")


def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            return d / BACKUP_NAME
    pytest.fail("[FAIL] backup %r not found under %s" % (BACKUP_NAME, _BACKUP_DIRS))


def _restore(name):
    assert name in (SOURCE_NAME, TARGET_NAME), name  # write guard
    from harness.restore import restore_target
    restore_target(name, backup_path=_backup_path())


def _open(name, write=False):
    assert not write or name == SOURCE_NAME, name  # write guard
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    proj = FLExProject()
    try:
        if write:
            proj.OpenProject(projectName=name, writeEnabled=True, undoable=False)
        else:
            proj.OpenProject(projectName=name, writeEnabled=False)
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but cannot open %r: %s" % (name, exc))
    return proj


def _g(obj) -> str:
    return str(obj.Guid).lower()


def _png(path: Path) -> None:
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = (b"\x00" + b"\xff\x00\x00" * 4)
    data = (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    path.write_bytes(data)


def _make_appendix(proj, text) -> str:
    from SIL.LCModel import (ILangProject, ILexDb, ILexAppendixFactory, IStTextFactory,
                             IStTxtParaFactory, IStText)
    from SIL.LCModel.Core.Text import TsStringUtils
    sl = proj.Cache.ServiceLocator
    lexdb = ILexDb(ILangProject(proj.Cache.LangProject).LexDbOA)
    ap = sl.GetService(ILexAppendixFactory).Create()
    lexdb.AppendixesOC.Add(ap)
    st = sl.GetService(IStTextFactory).Create()
    ap.ContentsOA = st
    para = sl.GetService(IStTxtParaFactory).Create()
    IStText(st).ParagraphsOS.Add(para)
    para.Contents = TsStringUtils.MakeString(text, proj.Cache.DefaultAnalWs)
    return _g(ap)


def _name(proj, item, name):
    from SIL.LCModel.Core.Text import TsStringUtils
    ws = proj.Cache.DefaultAnalWs
    item.Name.set_String(ws, TsStringUtils.MakeString(name, ws))
    item.Abbreviation.set_String(ws, TsStringUtils.MakeString(name[:8], ws))


def _author_shared_state() -> str:
    _restore(SOURCE_NAME)
    proj = _open(SOURCE_NAME, write=True)
    try:
        present = _make_appendix(proj, AP_PRESENT_TEXT)
    finally:
        proj.CloseProject()
    tdir = PROJECTS_ROOT / TARGET_NAME
    if tdir.exists():
        shutil.rmtree(tdir)
    shutil.copytree(PROJECTS_ROOT / SOURCE_NAME, tdir,
                    ignore=shutil.ignore_patterns("*.lock"))
    (tdir / ("%s.fwdata" % SOURCE_NAME)).rename(tdir / ("%s.fwdata" % TARGET_NAME))
    return present


def _author_source_only_state(present: str, png: Path) -> dict:
    from SIL.LCModel import (ILangProject, ILexDb, ICmPossibilityList, ICmPossibility,
                             ICmPossibilityFactory, ILexSense, ILexSenseFactory)
    from System import Guid as DotNetGuid
    proj = _open(SOURCE_NAME, write=True)
    try:
        lp = ILangProject(proj.Cache.LangProject)
        lexdb = ILexDb(lp.LexDbOA)
        sl = proj.Cache.ServiceLocator
        absent = _make_appendix(proj, AP_ABSENT_TEXT)
        pf = ICmPossibilityFactory(sl.GetService(ICmPossibilityFactory))
        dom = ICmPossibilityList(lexdb.DomainTypesOA)
        e_old = ICmPossibility(dom.PossibilitiesOS[0])                 # exists in target
        c_new = pf.Create(DotNetGuid.NewGuid(), e_old)                  # source only
        _name(proj, c_new, "GT136 new child")

        aps = {_g(a): a for a in lexdb.AppendixesOC}
        entry = proj.LexEntry.Create("gtfixonethirtysix", create_blank_sense=False)
        top = ILexSense(proj.Senses.Create(entry, "top sense"))
        sf = ILexSenseFactory(sl.GetService(ILexSenseFactory))
        sub = sf.Create(DotNetGuid.NewGuid(), top)
        subsub = sf.Create(DotNetGuid.NewGuid(), sub)
        sub, subsub = ILexSense(sub), ILexSense(subsub)
        # sub-sense: present+absent appendix, CREATE item C + LINK item E
        sub.AppendixesRC.Add(aps[present])
        sub.AppendixesRC.Add(aps[absent])
        sub.ThesaurusItemsRC.Add(c_new)
        sub.ThesaurusItemsRC.Add(e_old)
        # sub-sub-sense: present appendix + C
        subsub.AppendixesRC.Add(aps[present])
        subsub.ThesaurusItemsRC.Add(c_new)
        fx = dict(appendix_present=present, appendix_absent=absent,
                  entry=_g(entry), top=_g(top), sub=_g(sub), subsub=_g(subsub),
                  C=_g(c_new), E=_g(e_old), pictures=False)
        try:
            pic = proj.Senses.AddPicture(sub, str(png), "sub pic")
            fx["pic_sub"] = _g(pic)
            pic2 = proj.Senses.AddPicture(subsub, str(png), "subsub pic")
            fx["pic_subsub"] = _g(pic2)
            fx["pictures"] = True
        except Exception as exc:  # noqa: BLE001
            print("[WARN] picture authoring failed: %r" % exc)
        return fx
    finally:
        proj.CloseProject()


def _sandbox_state(fx) -> dict:
    from SIL.LCModel import ILexSense, ICmPicture
    from System import Guid
    proj = _open(TARGET_NAME)
    try:
        repo = proj.Cache.ServiceLocator.ObjectRepository
        out = {}
        for key in ("top", "sub", "subsub"):
            try:
                obj = repo.GetObject(Guid.Parse(fx[key]))
            except Exception:  # noqa: BLE001
                out[key] = None
                continue
            s = ILexSense(obj)
            out[key] = {
                "appendixes": sorted(_g(a) for a in s.AppendixesRC),
                "thesaurus": sorted(_g(t) for t in s.ThesaurusItemsRC),
                "pictures": [str(ICmPicture(p).PictureFileRA.InternalPath)
                             for p in s.PicturesOS],
                "subs": [_g(x) for x in s.SensesOS],
            }
        try:
            c = repo.GetObject(Guid.Parse(fx["C"]))
            out["C"] = str(c.ClassName)
        except Exception:  # noqa: BLE001
            out["C"] = None
        return out
    finally:
        proj.CloseProject()


@pytest.fixture(scope="module")
def live():
    try:
        import flexicon  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is unavailable: %s" % exc)
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    tmp = Path(tempfile.mkdtemp(prefix="gt136_"))
    try:
        png = tmp / "gt136_red.png"
        _png(png)
        present = _author_shared_state()
        fx = _author_source_only_state(present, png)

        def stems_only(_full):
            return Selection(categories={GC.STEMS: True})

        res = {"fx": fx, "pre": _sandbox_state(fx)}
        pre_bytes = Path(TARGET_PATH).read_bytes()
        res["preview_plan"], _ = full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
            selection_transform=stems_only, preview_only=True)
        res["preview_wrote"] = Path(TARGET_PATH).read_bytes() != pre_bytes
        res["plan"], res["report"] = full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
            selection_transform=stems_only)
        res["post"] = _sandbox_state(fx)
        import gramtrans
        import flexicon
        print("[LIVE] gramtrans=%s flexicon=%s" % (gramtrans.__file__, flexicon.__file__))
        print("[LIVE] source=%s target=%s fixture=%s" % (SOURCE_NAME, TARGET_NAME, fx))
        print("[LIVE] post=%s" % res["post"])
        yield res
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        for name in (TARGET_NAME, SOURCE_NAME):
            try:
                _restore(name)
            except Exception as exc:  # noqa: BLE001
                print("[WARN] restore of %s failed: %s" % (name, exc))


def _plan_rows(plan):
    return {(d.owner_guid, d.field_name, d.action.value, d.item_guid)
            for a in plan.actions for d in (getattr(a, "reference_decisions", ()) or ())
            if d.field_name in _FIELDS}


def test_preview_wrote_nothing_and_target_started_empty(live):
    assert not live["preview_wrote"]
    assert live["pre"]["sub"] is None and live["pre"]["C"] is None


def test_preview_shows_subsense_decisions(live):
    fx = live["fx"]
    rows = _plan_rows(live["preview_plan"])
    ap, th = "AppendixesRC", "ThesaurusItemsRC"
    for owner in (fx["sub"], fx["subsub"]):
        assert (owner, ap, "link", fx["appendix_present"]) in rows, rows
        assert (owner, th, "create", fx["C"]) in rows or \
            (owner, th, "link", fx["C"]) in rows, rows
    assert (fx["sub"], ap, "report_dropped", fx["appendix_absent"]) in rows, rows
    assert (fx["sub"], th, "link", fx["E"]) in rows, rows
    drops = {(d.owner_guid, d.item_guid) for d in live["preview_plan"].dropped_items
             if d.field_name == ap}
    assert (fx["sub"], fx["appendix_absent"]) in drops


def test_move_applied_subsense_refs_by_guid(live):
    fx, post = live["fx"], live["post"]
    assert post["sub"] is not None and post["subsub"] is not None
    assert post["top"]["subs"] == [fx["sub"]] and post["sub"]["subs"] == [fx["subsub"]]
    assert post["sub"]["appendixes"] == [fx["appendix_present"]]
    assert post["subsub"]["appendixes"] == [fx["appendix_present"]]
    assert post["sub"]["thesaurus"] == sorted([fx["C"], fx["E"]])
    assert post["subsub"]["thesaurus"] == [fx["C"]]
    assert post["C"] == "CmPossibility"


def test_move_reported_unresolvable_subsense_appendix(live):
    fx = live["fx"]
    drops = [(d.owner_guid, d.item_guid) for d in live["report"].dropped_items
             if d.field_name == "AppendixesRC"]
    assert drops == [(fx["sub"], fx["appendix_absent"])], drops


def test_subsense_pictures_reproduced(live):
    fx, post = live["fx"], live["post"]
    if not fx["pictures"]:
        pytest.skip("picture authoring unavailable; PicturesOS covered by unit tests only")
    assert len(post["sub"]["pictures"]) == 1, post["sub"]
    assert len(post["subsub"]["pictures"]) == 1, post["subsub"]
    assert all(p.lower().endswith(".png") for p in
               post["sub"]["pictures"] + post["subsub"]["pictures"])
