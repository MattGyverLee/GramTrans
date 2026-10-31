"""Issue #146 live gate -- Preview row actions match Move for a SHARED
thesaurus item and a SHARED picture file across two senses.

Before the fix a real Preview showed the second sense's reference to a
planned-CREATE thesaurus item as CREATE again (Move LINKs it), and the second
sense's picture of an already-planned image as CREATE (a second copy) although
Move's run-wide asset cache copies the file once.

Fixture (authored in the SOURCE only, after forking the target):
  entry "gtfixonefortysix"
    s1: ThesaurusItemsRC=[C]  PicturesOS=[red.png]
    s2: ThesaurusItemsRC=[C]  PicturesOS=[red.png]     <- shared item + file
    s3: ThesaurusItemsRC=[N]  PicturesOS=[blue.png]    <- negative control
  C and N are new source-only children of an item present in both projects.

WRITE PATH: writes ONLY the two private throwaway projects below, both rebuilt
from ``Target 2026-07-06 0218.fwbackup``:

* ``GT-Src-146``     -- SOURCE (write-enabled only while authoring)
* ``GT-Sandbox-146`` -- TARGET

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue146_preview_cache_picture_dedup_live.py -v -s
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

SOURCE_NAME = "GT-Src-146"
TARGET_NAME = "GT-Sandbox-146"
assert TARGET_NAME == "GT-Sandbox-146"  # write guard: the ONLY transfer target
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_DIR = PROJECTS_ROOT / TARGET_NAME
TARGET_PATH = str(TARGET_DIR / ("%s.fwdata" % TARGET_NAME))
TARGET_PICTURES = TARGET_DIR / "LinkedFiles" / "Pictures"
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))

_FIELDS = ("ThesaurusItemsRC", "PicturesOS")


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


def _png(path: Path, rgb: bytes) -> None:
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = (b"\x00" + rgb * 4)
    data = (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    path.write_bytes(data)


def _name(proj, item, name):
    from SIL.LCModel.Core.Text import TsStringUtils
    ws = proj.Cache.DefaultAnalWs
    item.Name.set_String(ws, TsStringUtils.MakeString(name, ws))
    item.Abbreviation.set_String(ws, TsStringUtils.MakeString(name[:8], ws))


def _clear_pictures(name):
    """`restore_target` rewrites the .fwdata but leaves LinkedFiles alone, so a
    previous run's image files would make the next run's fixture non-hermetic
    (a byte-identical file already in the folder turns CREATE into a reuse)."""
    assert name in (SOURCE_NAME, TARGET_NAME), name  # write guard
    shutil.rmtree(PROJECTS_ROOT / name / "LinkedFiles" / "Pictures", ignore_errors=True)


def _fork_target():
    """Restore the source, then copy it as the target -- shared baseline."""
    _restore(SOURCE_NAME)
    _clear_pictures(SOURCE_NAME)
    if TARGET_DIR.exists():
        shutil.rmtree(TARGET_DIR)
    shutil.copytree(PROJECTS_ROOT / SOURCE_NAME, TARGET_DIR,
                    ignore=shutil.ignore_patterns("*.lock"))
    (TARGET_DIR / ("%s.fwdata" % SOURCE_NAME)).rename(Path(TARGET_PATH))


def _author_source(red: Path, blue: Path) -> dict:
    from SIL.LCModel import (ILangProject, ILexDb, ICmPossibilityList, ICmPossibility,
                             ICmPossibilityFactory, ILexSense)
    from System import Guid as DotNetGuid
    proj = _open(SOURCE_NAME, write=True)
    try:
        lexdb = ILexDb(ILangProject(proj.Cache.LangProject).LexDbOA)
        sl = proj.Cache.ServiceLocator
        pf = ICmPossibilityFactory(sl.GetService(ICmPossibilityFactory))
        dom = ICmPossibilityList(lexdb.DomainTypesOA)
        e_old = ICmPossibility(dom.PossibilitiesOS[0])          # exists in target
        c_new = pf.Create(DotNetGuid.NewGuid(), e_old)           # shared, source only
        _name(proj, c_new, "GT146 shared item")
        n_new = pf.Create(DotNetGuid.NewGuid(), e_old)           # control, source only
        _name(proj, n_new, "GT146 control item")

        entry = proj.LexEntry.Create("gtfixonefortysix", create_blank_sense=False)
        senses = [ILexSense(proj.Senses.Create(entry, "sense %d" % i)) for i in (1, 2, 3)]
        senses[0].ThesaurusItemsRC.Add(c_new)
        senses[1].ThesaurusItemsRC.Add(c_new)
        senses[2].ThesaurusItemsRC.Add(n_new)
        pics = [proj.Senses.AddPicture(senses[0], str(red), "s1 pic"),
                proj.Senses.AddPicture(senses[1], str(red), "s2 pic"),
                proj.Senses.AddPicture(senses[2], str(blue), "s3 pic")]
        return dict(entry=_g(entry), E=_g(e_old), C=_g(c_new), N=_g(n_new),
                    s=[_g(s) for s in senses], pics=[_g(p) for p in pics])
    finally:
        proj.CloseProject()


def _picture_files() -> list:
    if not TARGET_PICTURES.is_dir():
        return []
    return sorted(p.name for p in TARGET_PICTURES.iterdir() if p.is_file())


def _sandbox_state(fx) -> dict:
    from SIL.LCModel import ILexSense, ICmPicture, ICmPossibility
    from System import Guid
    proj = _open(TARGET_NAME)
    try:
        repo = proj.Cache.ServiceLocator.ObjectRepository
        e_old = ICmPossibility(repo.GetObject(Guid.Parse(fx["E"])))
        out = {"E_children": sorted(_g(x) for x in e_old.SubPossibilitiesOS),
               "files": _picture_files(), "senses": {}}
        for sg in fx["s"]:
            try:
                s = ILexSense(repo.GetObject(Guid.Parse(sg)))
            except Exception:  # noqa: BLE001
                out["senses"][sg] = None
                continue
            out["senses"][sg] = {
                "thesaurus": sorted(_g(t) for t in s.ThesaurusItemsRC),
                "pictures": [str(ICmPicture(p).PictureFileRA.InternalPath)
                             for p in s.PicturesOS],
            }
        return out
    finally:
        proj.CloseProject()


def _rows(plan, fx):
    """Ordered (sense index, field, action) rows for the fixture's senses."""
    idx = {g: i + 1 for i, g in enumerate(fx["s"])}
    out = []
    for a in plan.actions:
        for d in (getattr(a, "reference_decisions", ()) or ()):
            if d.field_name in _FIELDS and d.owner_guid in idx:
                out.append((idx[d.owner_guid], d.field_name, d.action.value))
    return out


@pytest.fixture(scope="module")
def live():
    try:
        import flexicon  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is unavailable: %s" % exc)
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    def stems_only(_full):
        return Selection(categories={GC.STEMS: True})

    def run(preview_only=False):
        assert TARGET_NAME == "GT-Sandbox-146"  # write guard
        return full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
            selection_transform=stems_only, preview_only=preview_only)

    tmp = Path(tempfile.mkdtemp(prefix="gt146_"))
    try:
        red, blue = tmp / "gt146_red.png", tmp / "gt146_blue.png"
        _png(red, b"\xff\x00\x00")
        _png(blue, b"\x00\x00\xff")
        _fork_target()
        fx = _author_source(red, blue)

        res = {"fx": fx, "pre": _sandbox_state(fx)}
        pre_bytes = Path(TARGET_PATH).read_bytes()
        res["preview_plan"], _ = run(preview_only=True)
        res["preview_wrote"] = Path(TARGET_PATH).read_bytes() != pre_bytes
        res["after_preview_files"] = _picture_files()
        res["plan"], res["report"] = run()
        res["post"] = _sandbox_state(fx)
        res["plan2"], res["report2"] = run()                 # idempotent re-run
        res["post2"] = _sandbox_state(fx)
        res["preview3"], _ = run(preview_only=True)          # after Move
        import gramtrans
        import flexicon
        print("[LIVE] gramtrans=%s flexicon=%s" % (gramtrans.__file__, flexicon.__file__))
        print("[LIVE] source=%s target=%s fixture=%s" % (SOURCE_NAME, TARGET_NAME, fx))
        print("[LIVE] pre=%s" % res["pre"])
        print("[LIVE] preview rows=%s" % _rows(res["preview_plan"], fx))
        print("[LIVE] post=%s" % res["post"])
        print("[LIVE] post2=%s" % res["post2"])
        print("[LIVE] preview-after-move rows=%s" % _rows(res["preview3"], fx))
        yield res
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        for name in (TARGET_NAME, SOURCE_NAME):
            try:
                _restore(name)
                _clear_pictures(name)
            except Exception as exc:  # noqa: BLE001
                print("[WARN] restore of %s failed: %s" % (name, exc))


def test_preview_wrote_nothing(live):
    assert live["pre"]["files"] == []  # hermetic: target Pictures folder empty
    assert not live["preview_wrote"]
    assert live["after_preview_files"] == live["pre"]["files"]
    assert all(v is None for v in live["pre"]["senses"].values())


def test_preview_create_then_link_for_shared_item_and_file(live):
    rows = _rows(live["preview_plan"], live["fx"])
    assert sorted(rows) == sorted([
        (1, "ThesaurusItemsRC", "create"),
        (2, "ThesaurusItemsRC", "link"),      # was "create" before #146
        (3, "ThesaurusItemsRC", "create"),    # negative control: distinct item
        (1, "PicturesOS", "create"),
        (2, "PicturesOS", "link"),            # was "create" before #146
        (3, "PicturesOS", "create"),          # negative control: distinct file
    ]), rows
    # Order matters: the CREATE precedes the LINK, as in Move.
    th = [r for r in rows if r[1] == "ThesaurusItemsRC"]
    assert th[0] == (1, "ThesaurusItemsRC", "create"), rows


def test_move_created_one_item_and_copied_one_file_per_distinct_asset(live):
    fx, pre, post = live["fx"], live["pre"], live["post"]
    # Preview said 2 thesaurus CREATEs (C, N) -> Move created exactly those.
    assert sorted(set(post["E_children"]) - set(pre["E_children"])) == sorted(
        [fx["C"], fx["N"]])
    # Preview said 2 picture CREATEs -> Move copied exactly 2 files.
    new_files = sorted(set(post["files"]) - set(pre["files"]))
    assert len(new_files) == 2, new_files
    s1, s2, s3 = (post["senses"][g] for g in fx["s"])
    assert s1["thesaurus"] == s2["thesaurus"] == [fx["C"]]
    assert s3["thesaurus"] == [fx["N"]]
    assert len(s1["pictures"]) == len(s2["pictures"]) == len(s3["pictures"]) == 1
    assert s1["pictures"] == s2["pictures"]        # shared file reused (LINK)
    assert s3["pictures"] != s1["pictures"]


def test_move_rerun_is_idempotent(live):
    post, post2 = live["post"], live["post2"]
    assert post2 == post


def test_preview_after_move_links_everything(live):
    rows = _rows(live["preview3"], live["fx"])
    # Entry now present by GUID -> skipped, or every ref is a LINK.
    assert all(r[2] == "link" for r in rows), rows


# ============================================================================
# Plan-carried decisions: Move's texts leg APPLIES Preview's genre decisions
# (plan.text_plans) rather than re-deciding. Two texts share a new genre G; a
# third uses a different new genre H (negative control). Preview must show
# G create then G link, and Move must still give BOTH texts G (a planned LINK
# carries no target item; Move re-binds it against its own cache).
# ============================================================================

def _author_texts() -> dict:
    from SIL.LCModel import (ILangProject, ICmPossibilityList, ICmPossibilityFactory)
    from System import Guid as DotNetGuid
    proj = _open(SOURCE_NAME, write=True)
    try:
        lp = ILangProject(proj.Cache.LangProject)
        sl = proj.Cache.ServiceLocator
        pf = ICmPossibilityFactory(sl.GetService(ICmPossibilityFactory))
        genres = ICmPossibilityList(lp.GenreListOA)
        g_new = pf.Create(DotNetGuid.NewGuid(), genres)
        _name(proj, g_new, "GT146 shared genre")
        h_new = pf.Create(DotNetGuid.NewGuid(), genres)
        _name(proj, h_new, "GT146 control genre")
        texts = [proj.Texts.Create("GT146 text one", genre=g_new),
                 proj.Texts.Create("GT146 text two", genre=g_new),
                 proj.Texts.Create("GT146 text three", genre=h_new)]
        try:
            proj.Texts.GetGenre(texts[0])
            getgenre_error = ""
        except Exception as exc:  # noqa: BLE001
            getgenre_error = repr(exc)
        return dict(G=_g(g_new), H=_g(h_new), t=[_g(t) for t in texts],
                    getgenre_error=getgenre_error)
    finally:
        proj.CloseProject()


def _text_state(fx) -> dict:
    from SIL.LCModel import ILangProject, IText
    from System import Guid
    proj = _open(TARGET_NAME)
    try:
        repo = proj.Cache.ServiceLocator.ObjectRepository
        lp = ILangProject(proj.Cache.LangProject)
        out = {"genres": sorted(_g(x) for x in lp.GenreListOA.PossibilitiesOS
                                if _g(x) in (fx["G"], fx["H"])),
               "texts": {}}
        for tg in fx["t"]:
            try:
                t = IText(repo.GetObject(Guid.Parse(tg)))
                out["texts"][tg] = sorted(_g(x) for x in t.GenresRC)
            except Exception:  # noqa: BLE001
                out["texts"][tg] = None
        return out
    finally:
        proj.CloseProject()


def _genre_rows(plan, fx):
    idx = {g: i + 1 for i, g in enumerate(fx["t"])}
    rows = []
    for tp in getattr(plan, "text_plans", ()) or ():
        i = idx.get(getattr(tp, "source_guid", ""))
        if i is None:
            continue
        for d in tp.genre_decisions:
            rows.append((i, d.action.value))
    return sorted(rows)


@pytest.fixture(scope="module")
def live_texts():
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    def run(fx, preview_only=False):
        assert TARGET_NAME == "GT-Sandbox-146"  # write guard

        def _sel(_full):
            return Selection(categories={GC.TEXTS: True},
                             text_picks=frozenset(fx["t"]), include_closure=True)
        return full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH, selection_transform=_sel,
            preview_only=preview_only)

    try:
        _fork_target()
        fx = _author_texts()
        res = {"fx": fx, "pre": _text_state(fx)}
        res["preview"], _ = run(fx, preview_only=True)
        res["plan"], res["report"] = run(fx)
        res["post"] = _text_state(fx)
        run(fx)
        res["post2"] = _text_state(fx)
        print("[LIVE-TEXTS] fixture=%s" % fx)
        print("[LIVE-TEXTS] preview genre rows=%s" % _genre_rows(res["preview"], fx))
        print("[LIVE-TEXTS] post=%s" % res["post"])
        print("[LIVE-TEXTS] post2=%s" % res["post2"])
        yield res
    finally:
        for name in (TARGET_NAME, SOURCE_NAME):
            try:
                _restore(name)
                _clear_pictures(name)
            except Exception as exc:  # noqa: BLE001
                print("[WARN] restore of %s failed: %s" % (name, exc))


def _xfail_if_genres_unreadable(live_texts):
    """`texts._decide_genres` reads genres through flexicon `Texts.GetGenre`,
    which (measured 2026-10-31, flexicon working tree) raises AttributeError
    ('ILcmReferenceCollection' has no 'FirstOrDefault') -- so NO text genre is
    planned or transferred at all, independent of #146. The rebind path is
    then unreachable live (unit-tested instead). Becomes a real assertion as
    soon as GetGenre works."""
    err = live_texts["fx"].get("getgenre_error")
    if err:
        pytest.xfail("flexicon Texts.GetGenre raises %s; genre path dead live" % err)


def test_texts_preview_genre_create_then_link(live_texts):
    _xfail_if_genres_unreadable(live_texts)
    assert _genre_rows(live_texts["preview"], live_texts["fx"]) == [
        (1, "create"), (2, "link"), (3, "create")]


def test_texts_move_links_shared_genre_on_both_texts(live_texts):
    _xfail_if_genres_unreadable(live_texts)
    fx, pre, post = live_texts["fx"], live_texts["pre"], live_texts["post"]
    assert pre["genres"] == [] and all(v is None for v in pre["texts"].values())
    assert post["genres"] == sorted([fx["G"], fx["H"]])   # each created once
    t1, t2, t3 = (post["texts"][g] for g in fx["t"])
    assert t1 == t2 == [fx["G"]]                          # 2nd text still linked
    assert t3 == [fx["H"]]
    assert live_texts["post2"] == post                    # idempotent
