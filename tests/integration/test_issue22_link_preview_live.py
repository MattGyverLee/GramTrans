"""Issue #22 live gate -- under ConflictMode.LINK, Preview agrees with Move.

A POS present in BOTH projects with a DIVERGED Name/Abbreviation:

  * LINK:   Preview plans no merge for it (a Skip saying the differences are
            not applied) and Move leaves the target POS untouched.
  * UPDATE: Preview plans the merge and Move writes it (control: proves the
            fixture really diverged and the planner really sees it).

WRITE PATH: the TARGET is the throwaway ``Target`` project, rebuilt from
``Target 2026-07-06 0218.fwbackup`` plus a fork of the private source
``GT-Src-22``. Nothing else is written. Claim ``Target`` with lockout first.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && set PYTHONPATH=src && python -m pytest \
        tests/integration/test_issue22_link_preview_live.py -v -s
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_live_project]

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "GT-Src-22"
TARGET_NAME = "Target"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
OLD = ("GT22 old pos", "GT22old")
NEW = ("GT22 new pos", "GT22new")

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


def _open(name, write=False):
    _guard(name)
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
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but cannot open %r: %s" % (name, exc))
    return proj


def _g(obj) -> str:
    return str(obj.Guid).lower()


def _set_text(proj, pos, vals):
    from SIL.LCModel.Core.Text import TsStringUtils
    ws = proj.Cache.DefaultAnalWs
    pos.Name.set_String(ws, TsStringUtils.MakeString(vals[0], ws))
    pos.Abbreviation.set_String(ws, TsStringUtils.MakeString(vals[1], ws))


def _find(proj, guid):
    from SIL.LCModel import ILangProject
    lp = ILangProject(proj.Cache.LangProject)
    return next(x for x in lp.PartsOfSpeechOA.PossibilitiesOS if _g(x) == guid)


def _pos_text(name, guid):
    proj = _open(name)
    try:
        pos = _find(proj, guid)
        ws = proj.Cache.DefaultAnalWs
        return (pos.Name.get_String(ws).Text, pos.Abbreviation.get_String(ws).Text)
    finally:
        proj.CloseProject()


def _author_source(vals, guid=None):
    from SIL.LCModel import ILangProject, IPartOfSpeechFactory
    proj = _open(SOURCE_NAME, write=True)
    try:
        if guid is None:
            lp = ILangProject(proj.Cache.LangProject)
            pos = proj.Cache.ServiceLocator.GetService(IPartOfSpeechFactory).Create()
            lp.PartsOfSpeechOA.PossibilitiesOS.Add(pos)
        else:
            pos = _find(proj, guid)
        _set_text(proj, pos, vals)
        return _g(pos)
    finally:
        proj.CloseProject()


def _fork_target():
    _guard(TARGET_NAME)
    tdir = PROJECTS_ROOT / TARGET_NAME
    if tdir.exists():
        shutil.rmtree(tdir)
    shutil.copytree(PROJECTS_ROOT / SOURCE_NAME, tdir,
                    ignore=shutil.ignore_patterns("*.lock"))
    (tdir / ("%s.fwdata" % SOURCE_NAME)).rename(tdir / ("%s.fwdata" % TARGET_NAME))


@pytest.fixture(scope="module")
def live():
    try:
        import flexicon
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is unavailable: %s" % exc)
    import gramtrans
    assert str(_REPO).lower() in gramtrans.__file__.lower(), (
        "[FAIL] gramtrans resolved to %s -- set PYTHONPATH=src" % gramtrans.__file__)
    from harness import full_run
    from harness.restore import restore_target
    from gramtrans.Lib.models import ConflictMode, GrammarCategory as GC, Selection

    def run(mode, preview_only):
        def sel(_full):
            return Selection(
                categories={GC.GRAM_CATEGORIES: True},
                category_conflict_modes={GC.GRAM_CATEGORIES: mode},
                include_closure=True)
        return full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
            selection_transform=sel, preview_only=preview_only)

    restore_target(SOURCE_NAME, backup_path=_backup_path())
    guid = _author_source(OLD)
    _fork_target()
    _author_source(NEW, guid)  # diverge the SOURCE after the fork
    res = {"guid": guid, "pre": _pos_text(TARGET_NAME, guid)}
    res["link_preview"], _ = run(ConflictMode.LINK, True)
    res["link_plan"], res["link_report"] = run(ConflictMode.LINK, False)
    res["after_link"] = _pos_text(TARGET_NAME, guid)
    res["upd_preview"], _ = run(ConflictMode.UPDATE, True)
    res["upd_plan"], res["upd_report"] = run(ConflictMode.UPDATE, False)
    res["after_update"] = _pos_text(TARGET_NAME, guid)
    print("[LIVE] gramtrans=%s flexicon=%s" % (gramtrans.__file__, flexicon.__file__))
    for k in ("pre", "after_link", "after_update"):
        print("[LIVE] %s=%s" % (k, res[k]))
    return res


def _ow_guids(plan):
    return {str(o.source_guid).lower() for o in plan.overwrites}


def _skip_for(plan, guid):
    return [s for s in plan.skips if str(s.source_guid).lower() == guid]


def test_fixture_diverged(live):
    assert live["pre"] == OLD


def test_link_preview_does_not_promise_a_merge(live):
    g = live["guid"]
    assert g not in _ow_guids(live["link_preview"]), "[FAIL] LINK Preview planned a merge"
    sk = _skip_for(live["link_preview"], g)
    assert sk and "NOT applied" in sk[0].detail, sk
    print("[LIVE] link skip detail: %s" % sk[0].detail)


def test_link_move_writes_nothing(live):
    assert live["after_link"] == OLD, live["after_link"]
    assert live["guid"] not in _ow_guids(live["link_plan"])


def test_update_control_preview_and_move_merge(live):
    g = live["guid"]
    assert g in _ow_guids(live["upd_preview"]), "[FAIL] UPDATE Preview did not plan the merge"
    assert live["after_update"] == NEW, live["after_update"]
