"""Issue #175 live gate -- relocation is skipped when the source WS script
differs from the target default analysis WS script.

Writes ONLY the private throwaway projects GT-Src-175 (source) and
GT-Sandbox-175 (target), both restored from ``Target 2026-07-06 0218.fwbackup``.
Never Target, Esperanto, or any real project.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue175_relocation_script_live.py -v -s
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "GT-Src-175"
TARGET_NAME = "GT-Sandbox-175"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))


def _guard(name):
    assert name in (SOURCE_NAME, TARGET_NAME), name


def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            return d / BACKUP_NAME
    pytest.fail("[FAIL] backup %r not found under %s" % (BACKUP_NAME, _BACKUP_DIRS))


def _restore(name):
    _guard(name)
    from harness.restore import restore_target
    restore_target(name, backup_path=_backup_path())


def _open(name, write=False):
    assert not write or name == SOURCE_NAME, name
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
        pytest.fail("[FAIL] cannot open %r: %s" % (name, exc))
    return proj


def _g(obj) -> str:
    return str(obj.Guid).lower()


def _author_source() -> dict:
    """Source-only analysis WSs: 'de' (Latin, same script as target 'en') and
    'ru' (Cyrillic). Item A is German-only, item B Russian-only."""
    from SIL.LCModel import (ICmPossibilityFactory, ICmPossibilityList,
                             ILangProject, ILexDb, ILexSense)
    from SIL.LCModel.Core.Text import TsStringUtils
    from System import Guid
    proj = _open(SOURCE_NAME, write=True)
    try:
        ws = proj.WritingSystems
        ws.Create("de", "German", is_vernacular=False)
        ws.Create("ru", "Russian", is_vernacular=False)
        lexdb = ILexDb(ILangProject(proj.Cache.LangProject).LexDbOA)
        wsf = proj.Cache.WritingSystemFactory
        de, ru = wsf.GetWsFromStr("de"), wsf.GetWsFromStr("ru")
        pf = ICmPossibilityFactory(
            proj.Cache.ServiceLocator.GetService(ICmPossibilityFactory))
        dom = ICmPossibilityList(lexdb.DomainTypesOA)
        item_a = pf.Create(Guid.NewGuid(), dom)
        item_b = pf.Create(Guid.NewGuid(), dom)
        item_a.Name.set_String(de, TsStringUtils.MakeString("GT175-A-Name-DE", de))
        item_b.Name.set_String(ru, TsStringUtils.MakeString("GT175-B-Name-RU", ru))
        entry = proj.LexEntry.Create("gtonesevenfive", create_blank_sense=False)
        sense = ILexSense(proj.Senses.Create(entry, "gt175 sense"))
        sense.ThesaurusItemsRC.Add(item_a)
        sense.ThesaurusItemsRC.Add(item_b)
        return dict(item_a=_g(item_a), item_b=_g(item_b))
    finally:
        proj.CloseProject()


def _readback(fx) -> dict:
    from SIL.LCModel import ICmPossibility
    from System import Guid
    proj = _open(TARGET_NAME)
    try:
        repo = proj.Cache.ServiceLocator.ObjectRepository
        wsf = proj.Cache.WritingSystemFactory
        out = {}
        for key in ("item_a", "item_b"):
            poss = ICmPossibility(repo.GetObject(Guid.Parse(fx[key])))
            ms = poss.Name
            out[key] = {wsf.GetStrFromWs(h): ms.get_String(h).Text
                        for h in ms.AvailableWritingSystemIds}
        return out
    finally:
        proj.CloseProject()


@pytest.fixture(scope="module")
def live():
    try:
        import flexicon
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] flexicon unavailable: %s" % exc)
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    _restore(SOURCE_NAME)
    _restore(TARGET_NAME)
    fx = _author_source()
    plan, report = full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
        selection_transform=lambda _f: Selection(categories={GC.STEMS: True}))
    res = {"fx": fx, "report": report, "post": _readback(fx)}
    print("[LIVE] fixture=%s" % fx)
    for d in report.dropped_items:
        if d.item_guid in (fx["item_a"], fx["item_b"]):
            print("[LIVE] DROPPED   %s | %s" % (d.item_guid[:8], d.reason))
    for d in getattr(report, "relocated_items", ()):
        print("[LIVE] RELOCATED %s | %s" % (d.item_guid[:8], d.reason))
    print("[LIVE] readback=%s" % res["post"])
    return res


def test_same_script_german_is_relocated(live):
    assert live["post"]["item_a"].get("en") == "GT175-A-Name-DE"


def test_different_script_russian_is_not_relocated(live):
    fx, report = live["fx"], live["report"]
    assert "GT175-B-Name-RU" not in "".join(live["post"]["item_b"].values())
    recs = [d for d in report.dropped_items if d.item_guid == fx["item_b"]]
    assert recs and "'ru' absent in target" in recs[0].reason
    assert not any(str(d.reason).startswith("relocated:") for d in recs)
    assert not [d for d in getattr(report, "relocated_items", ())
                if d.item_guid == fx["item_b"]]
