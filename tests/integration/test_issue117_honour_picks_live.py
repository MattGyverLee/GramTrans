"""Issue #117 live gate: stem_picks / affix_picks narrow a real transfer.

WRITE PATH. Source = private ``GT-Src-117`` (restored from the Target backup,
then two stems and two affixes are authored in it). Target = the throwaway
``Target`` (override: GT117_TARGET_NAME), restored from the same backup first.
Never Esperanto or any real project.

Run (hold the lockout claim "Target-live-flex" while it runs):
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue117_honour_picks_live.py -v -s
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

SOURCE_NAME = "GT-Src-117"
TARGET_NAME = os.environ.get("GT117_TARGET_NAME", "Target")
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))


def _restore(name):
    from harness.restore import restore_target
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            return restore_target(name, backup_path=d / BACKUP_NAME)
    pytest.fail("[FAIL] backup %r not found" % BACKUP_NAME)


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
        pytest.fail("[FAIL] cannot open %r: %s" % (name, exc))
    return proj


def _g(o):
    return str(o.Guid).lower()


def _entry_guids(name):
    proj = _open(name)
    try:
        return {_g(e) for e in proj.LexEntry.GetAll()}
    finally:
        proj.CloseProject()


@pytest.fixture(scope="module")
def live():
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    _restore(TARGET_NAME)
    _restore(SOURCE_NAME)
    fx = {}
    try:
        proj = _open(SOURCE_NAME, write=True)
        try:
            fx["stemA"] = _g(proj.LexEntry.Create("gtonesevenstema"))
            fx["stemB"] = _g(proj.LexEntry.Create("gtonesevenstemb"))
            fx["affA"] = _g(proj.LexEntry.Create("-gtonesevena", "suffix"))
            fx["affB"] = _g(proj.LexEntry.Create("-gtonesevenb", "suffix"))
        finally:
            proj.CloseProject()
        res = {"fx": fx, "before": _entry_guids(TARGET_NAME)}

        def run(cats, preview_only=False, **picks):
            sel = Selection(categories={c: True for c in cats}, **picks)
            return full_run.run_full_transfer(
                SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
                selection_transform=lambda _f: sel, preview_only=preview_only)

        res["pre_stem"] = run([GC.STEMS], preview_only=True,
                              stem_picks=frozenset({fx["stemA"]}))[0]
        res["pre_none"] = run([GC.STEMS], preview_only=True)[0]
        run([GC.STEMS], stem_picks=frozenset({fx["stemA"]}))
        res["after_stem"] = _entry_guids(TARGET_NAME)
        run([GC.AFFIXES], affix_picks=frozenset({fx["affA"]}))
        res["after_aff"] = _entry_guids(TARGET_NAME)
        print("[LIVE] fixture=%s" % fx)
        print("[LIVE] new after stem run=%s" % sorted(res["after_stem"] - res["before"]))
        print("[LIVE] new after affix run=%s" % sorted(res["after_aff"] - res["after_stem"]))
        yield res
    finally:
        for n in (TARGET_NAME, SOURCE_NAME):
            try:
                _restore(n)
            except Exception as exc:  # noqa: BLE001
                print("[WARN] restore of %s failed: %s" % (n, exc))


def test_stem_run_with_one_pick_transfers_only_that_stem(live):
    fx = live["fx"]
    new = live["after_stem"] - live["before"]
    assert fx["stemA"] in new
    assert fx["stemB"] not in new
    assert not ({fx["affA"], fx["affB"]} & new)


def test_affix_run_with_one_pick_transfers_only_that_affix(live):
    fx = live["fx"]
    new = live["after_aff"] - live["after_stem"]
    assert fx["affA"] in new
    assert fx["affB"] not in new
    assert fx["stemB"] not in live["after_aff"]


def test_preview_states_picks_vs_no_picks(live):
    picked = " | ".join(live["pre_stem"].category_notes)
    none = " | ".join(live["pre_none"].category_notes)
    assert "only the 1 picked stem entry" in picked
    assert "no stem picks set" in none
