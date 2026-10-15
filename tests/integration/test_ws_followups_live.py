"""Live LCM gate for the issue #78 refactor of `_ensure_writing_systems`
(flexicon >= 4.8.0, issue #250 store semantics).

`_ensure_writing_systems` classifies each `create_in_target` tag through
`ws_mapping.ws_create_state` (WS_ACTIVE / WS_ACTIVATE / WS_CREATE), the same
classifier Preview's read-only `preflight_ws_creates` uses. Proved against a
real project:

* Preview's preflight writes nothing and says nothing for a creatable or an
  already-active tag;
* Move creates an absent tag (and makes it ACTIVE), skips an active one, and
  reports nothing for either;
* a tag STORED but INACTIVE -- set up on every run through LCM exactly as FLEx
  leaves a user-unchecked writing system (on AnalysisWss, off CurAnalysisWss;
  project closed and reopened), so this scenario always RUNS -- is announced by
  Preview as exactly ONE info record ("will activate stored writing system"),
  and Move then ACTIVATES it: re-queried (not cached) it is in `GetAll()`,
  there is exactly one definition for the tag (no duplicate LDML), and no
  failure record is emitted.

Skips unless FLEXLIBS_REQUIRE_LIVE=1.  Writes only to the throwaway `Target`,
restored from backup before and after:

    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest tests/integration/test_ws_followups_live.py -v
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_LIVE = os.environ.get("FLEXLIBS_REQUIRE_LIVE") == "1"
if not _LIVE:
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

TARGET_NAME = "Target"  # the ONLY project this module may open for writing
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
NEW_TAG = "qaa-x-gtlive"
STORED_TAG = "es"  # staged as stored-but-inactive in Target (see _make_stored_but_inactive)
_PROJECTS_ROOT = Path(os.environ.get("GRAMTRANS_PROJECTS_ROOT",
                                     r"C:\ProgramData\SIL\FieldWorks\Projects"))
_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (
    _REPO / "backups",
    Path("D:/Github/_Projects/_LEX/GramTrans/backups"),
)


def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        p = d / BACKUP_NAME
        if p.is_file():
            return p
    pytest.fail("[FAIL] backup %r not found under %s" % (BACKUP_NAME, _BACKUP_DIRS))


def _restore() -> None:
    import sys
    here = str(Path(__file__).parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    from harness.restore import restore_target
    restore_target(TARGET_NAME, backup_path=_backup_path())


def _open_target():
    from flexicon import FLExProject
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    proj = FLExProject()
    proj.OpenProject(projectName=TARGET_NAME, writeEnabled=True, undoable=False)
    return proj


def _make_stored_but_inactive(proj) -> None:
    """Put STORED_TAG in the state FLEx holds after a user unchecks a writing
    system: still on the analysis "all" list (AnalysisWss) and in the LDML store,
    but absent from the CURRENT analysis list (CurAnalysisWss). Done through LCM
    in a write transaction, then the project is closed and reopened by the caller
    so the state is persisted the way a real project holds it."""
    from flexicon import WritingSystemOperations
    ops = WritingSystemOperations(proj)
    assert not ops.ExistsInStore(STORED_TAG), "[SETUP] restored Target already has %r" % STORED_TAG
    ops.Create(STORED_TAG, "Spanish", is_vernacular=False)  # store + all + current
    lp = proj.lp
    with ops._TransactionCM("test: deactivate %s" % STORED_TAG):
        lp.CurAnalysisWss = " ".join(
            t for t in str(lp.CurAnalysisWss).split() if t.lower() != STORED_TAG)
    assert STORED_TAG in str(lp.AnalysisWss).split(), "[SETUP] %r left the all-list" % STORED_TAG


@pytest.fixture(scope="module")
def target():
    try:
        import flexicon  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is unavailable: %s" % exc)
    _restore()
    try:
        proj = _open_target()
        _make_stored_but_inactive(proj)
        proj.CloseProject()
        proj = _open_target()  # reopen: state is what a saved project holds
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but cannot set up/open %r: %s"
                    % (TARGET_NAME, exc))
    try:
        yield proj
    finally:
        try:
            proj.CloseProject()
        except Exception as exc:  # noqa: BLE001
            print("[WARN] CloseProject failed: %s" % exc)
        _restore()


def _active(proj) -> set:
    from flexicon import WritingSystemOperations
    return {str(w.Id).lower() for w in WritingSystemOperations(proj).GetAll()}


def _ops(proj):
    from flexicon import WritingSystemOperations
    return WritingSystemOperations(proj)


def _store_files() -> list:
    d = _PROJECTS_ROOT / TARGET_NAME / "WritingSystemStore"
    return sorted(p.name for p in d.glob("*.ldml"))


def _definition_count(proj, tag) -> int:
    """How many WritingSystemDefinitions the live manager holds for `tag`,
    re-queried every call (never cached)."""
    wsm = proj.project.ServiceLocator.WritingSystemManager
    return sum(1 for ws in wsm.WritingSystems if str(ws.Id).lower() == tag.lower())


def _plan(*tags):
    from gramtrans.Lib.models import WSKind, WSMapping, WSMappingEntry
    mapping = WSMapping(entries=tuple(
        WSMappingEntry(source_ws_id=t, source_ws_kind=WSKind.ANALYSIS,
                       target_ws_id=t, create_in_target=True) for t in tags))
    return type("P", (), {"ws_mapping": mapping})()


def test_preflight_and_move_create_and_skip_live(target):
    from gramtrans.Lib import api
    from gramtrans.Lib.ws_mapping import preflight_ws_creates

    active_before = _active(target)
    assert NEW_TAG not in active_before, "[SETUP] restored Target already has the tag"
    existing = sorted(active_before)[0]
    plan = _plan(NEW_TAG, existing)

    predicted = preflight_ws_creates(target, plan.ws_mapping)
    assert _active(target) == active_before, "[FAIL] Preview preflight changed the target"
    assert predicted == [], "[FAIL] Preview must say nothing for CREATE / ACTIVE tags"

    failures = []
    created = api._ensure_writing_systems(target, None, plan, failures)

    assert created == [NEW_TAG]
    assert NEW_TAG in _active(target), "[FAIL] created WS is not active"
    assert failures == []
    print("[PASS] created=%s existing-skipped=%s" % (created, existing))


def test_stored_but_inactive_ws_is_activated_live(target):
    from gramtrans.Lib import api
    from gramtrans.Lib.ws_mapping import preflight_ws_creates

    ops = _ops(target)
    # --- before Move: really stored-but-inactive ---------------------------
    assert ops.Exists(STORED_TAG) is False, "[FAIL] Exists() must be active-only"
    assert ops.ExistsInStore(STORED_TAG) is True, "[SETUP] es not in the store"
    assert STORED_TAG not in _active(target)
    files_before = _store_files()
    active_before = _active(target)
    defs_before = _definition_count(target, STORED_TAG)
    assert defs_before == 1

    plan = _plan(STORED_TAG)
    predicted = preflight_ws_creates(target, plan.ws_mapping)
    assert [(r.item_name, r.severity) for r in predicted] == [(STORED_TAG, "info")]
    assert "will activate stored writing system" in predicted[0].reason
    assert _active(target) == active_before, "[FAIL] Preview changed the active set"
    assert _store_files() == files_before, "[FAIL] Preview wrote to the store"
    assert _definition_count(target, STORED_TAG) == defs_before

    # --- Move --------------------------------------------------------------
    failures = []
    created = api._ensure_writing_systems(target, None, plan, failures)

    # --- after Move: re-queried, not cached --------------------------------
    assert created == [STORED_TAG]
    assert failures == [], "[FAIL] activation emitted a failure record: %s" % failures
    assert STORED_TAG in _active(target), "[FAIL] stored WS was not activated"
    assert _ops(target).Exists(STORED_TAG) is True
    assert _definition_count(target, STORED_TAG) == 1, "[FAIL] duplicate definition"
    assert [f for f in _store_files() if f.lower().startswith(STORED_TAG)]         == ["%s.ldml" % STORED_TAG], "[FAIL] duplicate LDML written"
    print("[PASS] stored-inactive %r: Preview info x1, Move activated, no failure"
          % STORED_TAG)
