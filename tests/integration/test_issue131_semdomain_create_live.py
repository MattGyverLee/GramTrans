"""Issue #131 live gate -- a created CmSemanticDomain carries Name /
Abbreviation / Description.

WRITE PATH: writes ONLY two private throwaways, both restored headlessly from
``Target 2026-07-06 0218.fwbackup``:

* ``GT-Src-131``     -- the SOURCE: a NEW semantic domain (child of an existing
  domain, absent from the backup) is authored on it with Name, Abbreviation and
  Description in several writing systems.
* ``GT-Sandbox-131`` -- the TARGET.

Transfer is SEMANTIC_DOMAINS only. Asserts: the domain exists in the sandbox by
GUID, nested under the same parent, all three fields populated per WS (Description
carries the source text followed by exactly one [GT-Tag] line); a second run
creates nothing and leaves the sandbox identical.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue131_semdomain_create_live.py -v -s

SKIPS when FLEXLIBS_REQUIRE_LIVE != 1; under =1 a missing backup/flexicon FAILS.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)
if importlib.util.find_spec("flexicon") is None:
    pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is not importable",
                pytrace=False)

PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
SOURCE_NAME = "GT-Src-131"
TARGET_NAME = "GT-Sandbox-131"
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))

NAME_TEXT = "GT131 domain name"
ABBR_TEXT = "GT131 abbr"
DESC_TEXT = "GT131 domain description"


def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            return d / BACKUP_NAME
    pytest.fail("[FAIL] backup %r not found" % BACKUP_NAME, pytrace=False)


def _restore(name):
    assert name in (SOURCE_NAME, TARGET_NAME), name  # pinned before any write
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
    """New child domain under an existing domain, text in >=2 WS. Returns
    (new_guid, parent_guid, {field: {ws_id: text}})."""
    from SIL.LCModel import (ICmPossibilityList, ICmSemanticDomain,
                             ICmSemanticDomainFactory)
    from SIL.LCModel.Core.Text import TsStringUtils
    from System import Guid as DotNetGuid
    proj = _open(SOURCE_NAME, write=True)
    try:
        wss = [(w.Id, w.Handle) for w in proj.WritingSystems.GetAll()]
        assert len(wss) >= 2, "backup project needs >=2 writing systems: %s" % wss
        wss = wss[:3]
        sl = proj.Cache.ServiceLocator
        lst = ICmPossibilityList(proj.Cache.LangProject.SemanticDomainListOA)
        parent = ICmSemanticDomain(lst.PossibilitiesOS[0])
        sdf = ICmSemanticDomainFactory(sl.GetService(ICmSemanticDomainFactory))
        new = sdf.Create(DotNetGuid.NewGuid(), parent)
        want = {"Name": {}, "Abbreviation": {}, "Description": {}}
        for ws_id, h in wss:
            for field, base in (("Name", NAME_TEXT), ("Abbreviation", ABBR_TEXT),
                                ("Description", DESC_TEXT)):
                text = "%s (%s)" % (base, ws_id)
                getattr(new, field).set_String(h, TsStringUtils.MakeString(text, h))
                want[field][ws_id] = text
        return _g(new), _g(parent), want
    finally:
        proj.CloseProject()


def _read(name, guid):
    """{exists, parent, count, fields{field:{ws:text}}} via a fresh read-only open."""
    from SIL.LCModel import (ICmObject, ICmObjectRepository, ICmPossibility,
                             ICmPossibilityList)
    from System import Guid
    proj = _open(name)
    try:
        repo = proj.ObjectRepository(ICmObjectRepository)
        total = [0]

        def walk(items):
            for it in items:
                total[0] += 1
                walk(ICmPossibility(it).SubPossibilitiesOS)
        walk(ICmPossibilityList(proj.Cache.LangProject.SemanticDomainListOA).PossibilitiesOS)
        res = {"count": total[0]}
        try:
            obj = repo.GetObject(Guid.Parse(guid))
        except Exception:  # noqa: BLE001 -- absent GUID
            res["exists"] = False
            return res
        poss = ICmPossibility(obj)
        res["exists"] = True
        res["class"] = ICmObject(obj).ClassName
        res["parent"] = _g(ICmObject(obj).Owner)
        wss = [(w.Id, w.Handle) for w in proj.WritingSystems.GetAll()]
        res["fields"] = {}
        for field in ("Name", "Abbreviation", "Description"):
            ms = getattr(poss, field)
            res["fields"][field] = {
                ws_id: str(ms.get_String(h).Text)
                for ws_id, h in wss if ms.get_String(h).Text}
        return res
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
    import flexicon
    import gramtrans
    print("[LIVE] gramtrans.__file__ =", gramtrans.__file__)
    print("[LIVE] flexicon.__file__  =", flexicon.__file__)
    _restore(SOURCE_NAME)
    _restore(TARGET_NAME)
    yield
    for n in (SOURCE_NAME, TARGET_NAME):
        try:
            _restore(n)
        except Exception as exc:  # noqa: BLE001
            print("[WARN] restore of %s failed: %s" % (n, exc))


def test_created_semantic_domain_carries_name_abbreviation_description():
    guid, parent, want = _author_source()
    print("[LIVE] authored", guid, "under", parent, want)
    src = _read(SOURCE_NAME, guid)
    assert src["exists"] and src["fields"] == want

    pre = _read(TARGET_NAME, guid)
    assert pre["exists"] is False, "sandbox not clean"

    plan1, report1 = _run()
    creates = [a for a in plan1.actions if a.source_guid.lower() == guid]
    print("[LIVE] move#1 actions=%d creates-for-new-domain=%d" % (
        len(plan1.actions), len(creates)))
    assert len(creates) == 1
    got1 = _read(TARGET_NAME, guid)
    print("[LIVE] target after move#1:", got1)
    assert got1["exists"] and got1["class"] == "CmSemanticDomain"
    assert got1["parent"] == parent
    assert got1["count"] == pre["count"] + 1
    assert got1["fields"]["Name"] == want["Name"]
    assert got1["fields"]["Abbreviation"] == want["Abbreviation"]
    # Description: source text per WS, then exactly one carrier-B tag line on
    # the default analysis WS alternative.
    tagged = 0
    for ws_id, text in want["Description"].items():
        have = got1["fields"]["Description"][ws_id]
        assert have.startswith(text), (ws_id, have)
        tagged += have.count("[GT-Tag]")
    assert tagged == 1, got1["fields"]["Description"]

    # Idempotence: a second run creates nothing and changes nothing.
    plan2, _ = _run()
    again = [a for a in plan2.actions if a.source_guid.lower() == guid]
    print("[LIVE] move#2 actions=%d creates-for-new-domain=%d" % (
        len(plan2.actions), len(again)))
    assert again == []
    got2 = _read(TARGET_NAME, guid)
    assert got2 == got1, (got1, got2)
