"""Issue #119 live gate -- possibility-list CREATE through a REAL transfer for
the two item types #42 only proved at factory-binding level:

* ``CmAnthroItem`` (ItemClsid 26)  -- ``LexSense.AnthroCodesRC`` into
  ``LangProject.AnthroListOA``.  CREATE is correct: GUID preserved, hierarchy
  (new ancestors created top-down, existing ancestors reused), idempotent.
* ``MoMorphType`` (ItemClsid 5042) -- ``MoForm.MorphTypeRA`` into
  ``LexDb.MorphTypesOA``.  See the morph-type tests below for the decision.

WRITE PATH: only the private throwaway projects ``GT-Src-119`` (source) and
``GT-Sandbox-119`` (target; override with ``GT119_TARGET_NAME``), both rebuilt
from ``Target 2026-07-06 0218.fwbackup`` at module start and restored at the
end.  Never ``Target``, ``Esperanto`` or any real project.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue119_anthro_morphtype_create_live.py -v -s
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "GT-Src-119"
TARGET_NAME = os.environ.get("GT119_TARGET_NAME", "GT-Sandbox-119")
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
# Run against THIS checkout's sources even when the editable install points at
# another worktree.
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(Path(__file__).parent))


def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            return d / BACKUP_NAME
    pytest.fail("[FAIL] backup %r not found under %s" % (BACKUP_NAME, _BACKUP_DIRS))


def _restore(name):
    from harness.restore import restore_target
    restore_target(name, backup_path=_backup_path())


def _open(name, write=False):
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


def _name(proj, item, name):
    from SIL.LCModel.Core.Text import TsStringUtils
    ws = proj.Cache.DefaultAnalWs
    item.Name.set_String(ws, TsStringUtils.MakeString(name, ws))
    item.Abbreviation.set_String(ws, TsStringUtils.MakeString(name[:8], ws))


# --------------------------------------------------------------------------
# fixture authoring (direct LCM writes on the PRIVATE source only)
# --------------------------------------------------------------------------

def _author_shared_state() -> str:
    """Restored source + one anthropology item E; fork to the sandbox so both
    projects own E under the SAME GUID (an EXISTING ancestor for the CREATE)."""
    from SIL.LCModel import (ILangProject, ICmPossibilityList, ICmAnthroItemFactory)
    from System import Guid as DotNetGuid
    _restore(SOURCE_NAME)
    proj = _open(SOURCE_NAME, write=True)
    try:
        sl = proj.Cache.ServiceLocator
        af = ICmAnthroItemFactory(sl.GetService(ICmAnthroItemFactory))
        alist = ICmPossibilityList(ILangProject(proj.Cache.LangProject).AnthroListOA)
        e = af.Create(DotNetGuid.NewGuid(), alist)
        _name(proj, e, "GT119 shared anthro item")
        shared = _g(e)
    finally:
        proj.CloseProject()
    tdir = PROJECTS_ROOT / TARGET_NAME
    if tdir.exists():
        shutil.rmtree(tdir)
    shutil.copytree(PROJECTS_ROOT / SOURCE_NAME, tdir,
                    ignore=shutil.ignore_patterns("*.lock"))
    (tdir / ("%s.fwdata" % SOURCE_NAME)).rename(tdir / ("%s.fwdata" % TARGET_NAME))
    return shared


def _author_source(shared: str) -> dict:
    from SIL.LCModel import (ILangProject, ILexDb, ICmPossibilityList, ICmPossibility,
                             ICmAnthroItemFactory, ICmAnthroItem, IMoMorphTypeFactory,
                             IMoMorphType, ILexSense, ILexEntry)
    from System import Guid as DotNetGuid
    proj = _open(SOURCE_NAME, write=True)
    try:
        lp = ILangProject(proj.Cache.LangProject)
        lexdb = ILexDb(lp.LexDbOA)
        sl = proj.Cache.ServiceLocator

        # ---- anthropology items (ItemClsid 26) ----
        af = ICmAnthroItemFactory(sl.GetService(ICmAnthroItemFactory))
        alist = ICmPossibilityList(lp.AnthroListOA)
        assert alist.ItemClsid == 26, alist.ItemClsid
        ap_new = af.Create(DotNetGuid.NewGuid(), alist)                  # NEW top-level
        _name(proj, ap_new, "GT119 anthro parent")
        ac_new = af.Create(DotNetGuid.NewGuid(), ICmAnthroItem(ap_new))  # NEW child of NEW
        _name(proj, ac_new, "GT119 anthro child")
        e_old = next(ICmPossibility(i) for i in alist.PossibilitiesOS if _g(i) == shared)
        ac2_new = af.Create(DotNetGuid.NewGuid(), ICmAnthroItem(e_old))   # NEW child of EXISTING
        _name(proj, ac2_new, "GT119 anthro child of existing")

        # ---- a source-only morph type (ItemClsid 5042) ----
        mlist = ICmPossibilityList(lexdb.MorphTypesOA)
        assert mlist.ItemClsid == 5042, mlist.ItemClsid
        mraw = proj.GetFactory(IMoMorphTypeFactory)       # uncast: Create(Guid) binds
        mt_new = IMoMorphType(mraw.Create(DotNetGuid.NewGuid()))
        mlist.PossibilitiesOS.Add(mt_new)
        _name(proj, mt_new, "GT119 morph type")

        e1 = proj.LexEntry.Create("gtfixonenineteen", create_blank_sense=False)
        s1 = ILexSense(proj.Senses.Create(e1, "anthro sense"))
        s1.AnthroCodesRC.Add(ac_new)
        s1.AnthroCodesRC.Add(ac2_new)
        s1.AnthroCodesRC.Add(e_old)
        e2 = proj.LexEntry.Create("gtfixonenineteenmt", create_blank_sense=False)
        ILexSense(proj.Senses.Create(e2, "morph type sense"))
        lf = ILexEntry(e2).LexemeFormOA
        lf.MorphTypeRA = mt_new
        return dict(
            AP=_g(ap_new), AC=_g(ac_new), AC2=_g(ac2_new),
            E=_g(e_old),
            anthro_list=_g(alist), MT=_g(mt_new),
            e1=_g(e1), s1=_g(s1), e2=_g(e2),
        )
    finally:
        proj.CloseProject()


def _count_items(lst) -> int:
    from SIL.LCModel import ICmPossibility
    n, stack = 0, list(lst.PossibilitiesOS)
    while stack:
        item = stack.pop()
        n += 1
        stack.extend(ICmPossibility(item).SubPossibilitiesOS)
    return n


def _sandbox_state(fx) -> dict:
    from SIL.LCModel import (ILangProject, ILexDb, ICmPossibilityList, ICmPossibility,
                             ICmObject, ILexSense, ILexEntry)
    from System import Guid
    proj = _open(TARGET_NAME)
    try:
        lp = ILangProject(proj.Cache.LangProject)
        lexdb = ILexDb(lp.LexDbOA)
        repo = proj.Cache.ServiceLocator.ObjectRepository

        def get(guid):
            try:
                return repo.GetObject(Guid.Parse(guid))
            except Exception:  # noqa: BLE001 -- absent
                return None

        out = {
            "entries": int(proj.LexiconNumberOfEntries()),
            "anthro_total": _count_items(ICmPossibilityList(lp.AnthroListOA)),
            "morphtypes_total": _count_items(ICmPossibilityList(lexdb.MorphTypesOA)),
        }
        for key in ("AP", "AC", "AC2", "E", "MT"):
            obj = get(fx[key]) if fx.get(key) else None
            if obj is None:
                out[key] = None
                continue
            pos = ICmPossibility(obj)
            parent = pos.OwningPossibility
            out[key] = {
                "class": str(obj.ClassName),
                "owner": _g(ICmObject(obj).Owner),
                "parent": _g(parent) if parent is not None else None,
                "name": pos.Name.BestAnalysisAlternative.Text,
            }
        s1 = get(fx["s1"])
        out["s1"] = None if s1 is None else {
            "anthro": sorted(_g(a) for a in ILexSense(s1).AnthroCodesRC)}
        e2 = get(fx["e2"])
        if e2 is None:
            out["e2"] = None
        else:
            lf = ILexEntry(e2).LexemeFormOA
            mt = None if lf is None else lf.MorphTypeRA
            out["e2"] = {"lexeme_form": lf is not None,
                         "morph_type": None if mt is None else _g(mt)}
        return out
    finally:
        proj.CloseProject()


def _load_objects(path):
    out, cur, buf = {}, None, []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r'<rt class="(\w+)" guid="([^"]+)"', line)
            if m:
                cur, buf = (m.group(1), m.group(2).lower()), []
            if cur:
                buf.append(line)
            if cur and (line.startswith("</rt>") or line.rstrip().endswith("/>")
                        and line.startswith("<rt ")):
                out[cur[1]] = (cur[0], "".join(buf))
                cur = None
    return out


def _drops(items, field):
    return [d for d in items if d.field_name == field]


@pytest.fixture(scope="module")
def live():
    try:
        import flexicon  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is unavailable: %s" % exc)
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    snapdir = tempfile.mkdtemp(prefix="gt119_")
    try:
        fx = _author_source(_author_shared_state())

        def stems_only(_full):
            return Selection(categories={GC.STEMS: True})

        def move(preview_only=False):
            return full_run.run_full_transfer(
                SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
                selection_transform=stems_only, preview_only=preview_only)

        res = {"fx": fx, "pre": _sandbox_state(fx)}
        pre_bytes = Path(TARGET_PATH).read_bytes()
        res["preview_plan"], _ = move(preview_only=True)
        res["preview_wrote"] = Path(TARGET_PATH).read_bytes() != pre_bytes
        for i in (1, 2):
            plan, report = move()
            snap = os.path.join(snapdir, "move%d.fwdata" % i)
            shutil.copyfile(TARGET_PATH, snap)
            res["move%d" % i] = {"plan": plan, "report": report,
                                 "state": _sandbox_state(fx),
                                 "objects": _load_objects(snap)}
        import gramtrans
        print("[LIVE] gramtrans=%s flexicon=%s" % (gramtrans.__file__, flexicon.__file__))
        print("[LIVE] source=%s target=%s" % (SOURCE_NAME, TARGET_NAME))
        print("[LIVE] fixture=%s" % fx)
        print("[LIVE] pre=%s" % res["pre"])
        for i in (1, 2):
            print("[LIVE] move%d actions=%d state=%s" % (
                i, len(res["move%d" % i]["plan"].actions), res["move%d" % i]["state"]))
            for d in res["move%d" % i]["report"].dropped_items:
                print("[LIVE] move%d drop: %s %s %s | %s" % (
                    i, d.field_name, d.item_name, d.item_guid, d.reason))
        yield res
    finally:
        shutil.rmtree(snapdir, ignore_errors=True)
        for name in (TARGET_NAME, SOURCE_NAME):
            try:
                _restore(name)
            except Exception as exc:  # noqa: BLE001
                print("[WARN] restore of %s failed: %s" % (name, exc))


def test_fixture_preconditions(live):
    pre = live["pre"]
    assert pre["entries"] == 0
    for key in ("AP", "AC", "AC2", "MT"):
        assert pre[key] is None, "%s must be absent from the sandbox" % key


def test_preview_writes_nothing(live):
    assert not live["preview_wrote"], "Preview modified the target .fwdata"


def test_anthro_create_preserves_guid_class_and_hierarchy(live):
    fx, pre, st = live["fx"], live["pre"], live["move1"]["state"]
    assert not _drops(live["move1"]["report"].dropped_items, "AnthroCodesRC")
    # New top-level AP + new child AC under it (ancestor first); GUIDs preserved,
    # class CmAnthroItem (typed factory, ItemClsid 26), owned by the anthro list.
    assert st["AP"] == {"class": "CmAnthroItem", "owner": fx["anthro_list"],
                        "parent": None, "name": "GT119 anthro parent"}
    assert st["AC"] == {"class": "CmAnthroItem", "owner": fx["AP"],
                        "parent": fx["AP"], "name": "GT119 anthro child"}
    # New child under an EXISTING item: E reused (not duplicated), AC2 beneath it.
    assert st["AC2"] == {"class": "CmAnthroItem", "owner": fx["E"],
                         "parent": fx["E"], "name": "GT119 anthro child of existing"}
    assert st["E"] == pre["E"]
    assert st["anthro_total"] == pre["anthro_total"] + 3          # AP, AC, AC2
    assert st["s1"]["anthro"] == sorted([fx["AC"], fx["AC2"], fx["E"]])


def test_preview_plans_the_same_morph_drop_as_move(live):
    fx = live["fx"]
    drops = _drops(live["preview_plan"].dropped_items, "MorphTypeRA")
    assert [d.item_guid for d in drops] == [fx["MT"]], drops
    move_drops = _drops(live["move1"]["report"].dropped_items, "MorphTypeRA")
    assert [(d.item_guid, d.reason) for d in drops] == \
        [(d.item_guid, d.reason) for d in move_drops]


def test_morph_type_is_reported_drop_never_created(live):
    """Issue #119 decision: a source-only morph type is NOT minted in the
    target's fixed morph-types list; the loss is reported."""
    fx, pre, st = live["fx"], live["pre"], live["move1"]["state"]
    assert st["MT"] is None, "a source-only morph type was created in the target"
    assert st["morphtypes_total"] == pre["morphtypes_total"] == 19
    drops = _drops(live["move1"]["report"].dropped_items, "MorphTypeRA")
    assert len(drops) == 1, drops
    assert drops[0].item_guid == fx["MT"]
    assert drops[0].item_name == "GT119 morph type"
    assert "not created" in drops[0].reason
    # The entry itself still transfers (its other content is not lost).
    assert st["e2"] is not None and st["e2"]["lexeme_form"]
    assert st["e2"]["morph_type"] != fx["MT"]


def test_rerun_is_idempotent_zero_writes(live):
    assert len(live["move2"]["plan"].actions) == 0, "re-run planned actions"
    assert live["move2"]["state"] == live["move1"]["state"]
    before, after = live["move1"]["objects"], live["move2"]["objects"]
    assert set(after) == set(before), "re-run added/removed objects"
    changed = [(before[g][0], g) for g in before if before[g][1] != after[g][1]]
    assert not changed, "re-run changed objects: %s" % changed[:20]
