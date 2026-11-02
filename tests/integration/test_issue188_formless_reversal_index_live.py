"""Issue #188 live gate -- Move creates a target ReversalIndex only once an
entry survives the formless-entry drop, and Preview announces exactly that.

Before the fix `reversals._apply_one_entry` called `_ensure_target_index`
BEFORE `_create_top_level_entry` dropped an entry with no form, so a source
reversal index whose only entries were formless left an EMPTY ReversalIndex
in the target.

Fixture (source only, authored after the target fork): a NEW reversal index
(analysis WS the target has no index for) whose only entry has NO ReversalForm
and links a copied stem sense.

WRITE PATH: writes ONLY the two private throwaway projects below, both rebuilt
from ``Target 2026-07-06 0218.fwbackup``:

* ``GT-Src-188``     -- SOURCE (write-enabled only while authoring)
* ``GT-Sandbox-188`` -- TARGET (a fork of the source before authoring)

Never Target, Esperanto, Ejagham*, Mbugwe*, Ngoreme*, or another agent's
GT-Src-NNN / GT-Sandbox-NNN.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest         tests/integration/test_issue188_formless_reversal_index_live.py -v -s
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

SOURCE_NAME = "GT-Src-188"
TARGET_NAME = "GT-Sandbox-188"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))


def _guard(name):
    # Write guard: these two throwaway projects and nothing else.
    assert name in (SOURCE_NAME, TARGET_NAME), name
    assert TARGET_NAME == "GT-Sandbox-188" and SOURCE_NAME == "GT-Src-188"


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
    assert not write or name in (SOURCE_NAME, TARGET_NAME), name  # write guard
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




REV_WS = "en"  # the only analysis WS; the backup carries an EMPTY "en" index


def _g(obj) -> str:
    return str(obj.Guid).lower()


def _fork_target():
    _restore(SOURCE_NAME)
    _guard(TARGET_NAME)
    tdir = PROJECTS_ROOT / TARGET_NAME
    if tdir.exists():
        shutil.rmtree(tdir)
    shutil.copytree(PROJECTS_ROOT / SOURCE_NAME, tdir,
                    ignore=shutil.ignore_patterns("*.lock"))
    (tdir / ("%s.fwdata" % SOURCE_NAME)).rename(tdir / ("%s.fwdata" % TARGET_NAME))


def _drop_target_index():
    """Make the target's "en" index a to-create one (the fork carries an
    empty index; the plan must see none)."""
    proj = _open(TARGET_NAME, write=True)
    try:
        idx = proj.ReversalIndexes.FindByWritingSystem(REV_WS)
        assert idx is not None and idx.EntriesOC.Count == 0
        proj.ReversalIndexes.Delete(idx)
    finally:
        proj.CloseProject()


def _author_source() -> dict:
    """Source-only: one stem sense plus a NEW reversal index whose only entry
    has an empty ReversalForm and links that sense."""
    proj = _open(SOURCE_NAME, write=True)
    try:
        e = proj.LexEntry.Create("gtoneeightyeight", "stem", create_blank_sense=False)
        sense = proj.LexEntry.AddSense(e, "gt188 one")
        idx = proj.ReversalIndexes.FindByWritingSystem(REV_WS)
        assert idx is not None
        entry = proj.ReversalEntries.Create(idx, "placeholder", sense)
        # Blank every alt of the form so the entry is genuinely formless.
        ms = entry.ReversalForm
        for ws in proj.WritingSystems.GetAll():
            h = proj.WSHandle(ws.Id)
            if h:
                ms.set_String(h, None)
        return dict(index=_g(idx), entry=_g(entry), sense=_g(sense))
    finally:
        proj.CloseProject()


def _target_state() -> dict:
    proj = _open(TARGET_NAME)
    try:
        return {"indexes": {_g(i): (i.WritingSystem, i.EntriesOC.Count)
                            for i in proj.ReversalIndexes.GetAll()}}
    finally:
        proj.CloseProject()


def _revs(items):
    return sorted((d.owner_kind, d.owner_guid, d.reason) for d in items
                  if d.owner_kind in ("ReversalIndex", "ReversalIndexEntry"))


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

    def run(preview_only):
        return full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
            selection_transform=stems_only, preview_only=preview_only)

    try:
        _fork_target()
        _drop_target_index()
        fx = _author_source()
        res = {"fx": fx, "pre": _target_state()}
        res["preview"], res["preview_report"] = run(True)
        res["move_plan"], res["move_report"] = run(False)
        res["post"] = _target_state()
        from gramtrans.Lib.preview import render_reversal_decisions
        res["preview_lines"] = render_reversal_decisions(res["preview"])
        print("[LIVE] fixture=%s" % fx)
        print("[LIVE] pre indexes=%s" % res["pre"]["indexes"])
        print("[LIVE] post indexes=%s" % res["post"]["indexes"])
        print("[LIVE] preview lines=%s" % (res["preview_lines"],))
        print("[LIVE] move rev drops=%s" % _revs(res["move_report"].dropped_items))
        yield res
    finally:
        for name in (TARGET_NAME, SOURCE_NAME):
            try:
                _restore(name)
            except Exception as exc:  # noqa: BLE001
                print("[WARN] restore of %s failed: %s" % (name, exc))


def test_formless_entry_really_dropped(live):
    fx = live["fx"]
    assert any(d.owner_kind == "ReversalIndexEntry" and "no reversal form" in d.reason
               for d in live["move_report"].dropped_items), _revs(
        live["move_report"].dropped_items)
    assert fx["index"] not in live["pre"]["indexes"]  # target has no en index


def test_no_empty_reversal_index_created(live):
    pre, post = live["pre"]["indexes"], live["post"]["indexes"]
    new = {g: v for g, v in post.items() if g not in pre}
    assert not [v for v in new.values() if v[0] == REV_WS], new
    assert sorted(post) == sorted(pre)


def test_preview_announces_no_index(live):
    assert not [l for l in live["preview_lines"] if REV_WS in l], live["preview_lines"]
