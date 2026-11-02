"""Issue #22 live gate -- a planned Merge on an existing semantic domain WRITES.

WRITE PATH: only private throwaways restored from ``Target 2026-07-06 0218.fwbackup``
(``GT-Src-22sd`` source, ``GT-Sandbox-22sd`` target). Never Esperanto.

Flow: author a new domain on the source (move #1 creates it on the target), then
edit the TARGET copy: diverge Name[ws0], clear Abbreviation[ws0], add a
target-only Name alternative. Move #2 (Merge) must restore the diverged Name,
fill the cleared Abbreviation and preserve the target-only alternative; move #3
must plan/write nothing.

Run: set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest tests/integration/test_issue22_semdomain_merge_live.py -v -s
"""
from __future__ import annotations

import importlib.util
import os
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

PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
SOURCE_NAME = "GT-Src-22sd"
TARGET_NAME = "GT-Sandbox-22sd"
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))


def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            return d / BACKUP_NAME
    pytest.fail("[FAIL] backup %r not found" % BACKUP_NAME, pytrace=False)


def _restore(name):
    assert name in (SOURCE_NAME, TARGET_NAME), name
    from harness.restore import restore_target
    restore_target(name, backup_path=_backup_path())


def _open(name, write=False):
    if write:
        assert name in (SOURCE_NAME, TARGET_NAME), name
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
        pytest.fail("[FAIL] cannot open %r: %s" % (name, exc), pytrace=False)
    return proj


def _g(obj) -> str:
    return str(obj.Guid).lower()


def _author_source():
    from SIL.LCModel import ICmPossibilityList, ICmSemanticDomain, ICmSemanticDomainFactory
    from SIL.LCModel.Core.Text import TsStringUtils
    from System import Guid as DotNetGuid
    proj = _open(SOURCE_NAME, write=True)
    try:
        wss = [(w.Id, w.Handle) for w in proj.WritingSystems.GetAll()][:2]
        assert len(wss) >= 2
        sl = proj.Cache.ServiceLocator
        lst = ICmPossibilityList(proj.Cache.LangProject.SemanticDomainListOA)
        parent = ICmSemanticDomain(lst.PossibilitiesOS[0])
        sdf = ICmSemanticDomainFactory(sl.GetService(ICmSemanticDomainFactory))
        new = sdf.Create(DotNetGuid.NewGuid(), parent)
        for ws_id, h in wss:
            for field in ("Name", "Abbreviation", "Description"):
                getattr(new, field).set_String(
                    h, TsStringUtils.MakeString("GT22 %s (%s)" % (field, ws_id), h))
        return _g(new), [w[0] for w in wss]
    finally:
        proj.CloseProject()


def _edit_target(guid, ws_ids):
    from SIL.LCModel import ICmObjectRepository, ICmPossibility
    from SIL.LCModel.Core.Text import TsStringUtils
    from System import Guid
    proj = _open(TARGET_NAME, write=True)
    try:
        poss = ICmPossibility(proj.ObjectRepository(ICmObjectRepository).GetObject(Guid.Parse(guid)))
        handles = {w.Id: w.Handle for w in proj.WritingSystems.GetAll()}
        h0 = handles[ws_ids[0]]
        poss.Name.set_String(h0, TsStringUtils.MakeString("DIVERGED-TARGET", h0))
        poss.Abbreviation.set_String(h0, TsStringUtils.MakeString("", h0))
        extra = [i for i in handles if i not in ws_ids]
        extra_id = extra[0] if extra else None
        if extra_id:
            h = handles[extra_id]
            poss.Name.set_String(h, TsStringUtils.MakeString("TARGET-ONLY-ALT", h))
        return extra_id
    finally:
        proj.CloseProject()


def _read(name, guid):
    from SIL.LCModel import ICmObjectRepository, ICmPossibility
    from System import Guid
    proj = _open(name)
    try:
        poss = ICmPossibility(proj.ObjectRepository(ICmObjectRepository).GetObject(Guid.Parse(guid)))
        out = {}
        for field in ("Name", "Abbreviation", "Description"):
            ms = getattr(poss, field)
            out[field] = {w.Id: str(ms.get_String(w.Handle).Text)
                          for w in proj.WritingSystems.GetAll() if ms.get_String(w.Handle).Text}
        return out
    finally:
        proj.CloseProject()


def _run():
    from gramtrans.Lib.models import GrammarCategory as GC, Selection
    from harness import full_run
    return full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, ws_mapping_mode="full",
        selection_transform=lambda _full: Selection(
            categories={GC.SEMANTIC_DOMAINS: True}))


@pytest.fixture(scope="module", autouse=True)
def _fixtures():
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    _restore(SOURCE_NAME)
    _restore(TARGET_NAME)
    yield
    for n in (SOURCE_NAME, TARGET_NAME):
        try:
            _restore(n)
        except Exception as exc:  # noqa: BLE001
            print("[WARN] restore of %s failed: %s" % (n, exc))


def test_planned_merge_on_existing_semantic_domain_writes():
    guid, ws_ids = _author_source()
    _run()                                    # move #1: creates on target
    pre_src = _read(SOURCE_NAME, guid)
    extra_id = _edit_target(guid, ws_ids)
    pre = _read(TARGET_NAME, guid)
    print("[LIVE] PRE target:", pre, "extra_ws:", extra_id)
    assert pre["Name"][ws_ids[0]] == "DIVERGED-TARGET"
    assert ws_ids[0] not in pre["Abbreviation"]

    plan2, report2 = _run()                   # move #2: Merge
    post = _read(TARGET_NAME, guid)
    print("[LIVE] POST target:", post)
    mine = [o for o in plan2.overwrites if o.source_guid.lower() == guid]
    assert len(mine) == 1, "Preview must plan exactly one merge for the edited domain"
    assert post["Name"][ws_ids[0]] == pre_src["Name"][ws_ids[0]]
    assert post["Abbreviation"][ws_ids[0]] == pre_src["Abbreviation"][ws_ids[0]]
    if extra_id:
        assert post["Name"][extra_id] == "TARGET-ONLY-ALT"

    plan3, _ = _run()                         # move #3: idempotent
    again = [o for o in plan3.overwrites if o.source_guid.lower() == guid]
    assert again == []
    assert _read(TARGET_NAME, guid) == post
