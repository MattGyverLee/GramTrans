"""Live LCM gate for the issue #78 refactor of `_ensure_writing_systems`.

`_ensure_writing_systems` now classifies each `create_in_target` tag through
`ws_mapping.ws_create_state`, the same classifier Preview's read-only
`preflight_ws_creates` uses. This proves against a real project that:

* Preview's preflight writes nothing and predicts no block for a creatable tag;
* Move still creates an absent tag (and makes it ACTIVE), skips an active one,
  and reports nothing for either;
* a tag stored but not active (when the restored Target has one) is predicted
  by Preview and then reported by Move as the SAME warning record.

Skips unless FLEXLIBS_REQUIRE_LIVE=1.  Writes only to the throwaway `Target`,
restored from backup before and after:

    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_ws_followups_live.py -v
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


@pytest.fixture(scope="module")
def target():
    try:
        from flexicon import FLExProject
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is unavailable: %s" % exc)
    _restore()
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    proj = FLExProject()
    try:
        proj.OpenProject(projectName=TARGET_NAME, writeEnabled=True, undoable=False)
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but cannot open %r: %s"
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


def _stored_inactive(proj) -> list:
    """Tags in the LDML store that are not active, if the store is enumerable."""
    try:
        wsm = proj.project.ServiceLocator.WritingSystemManager
        stored = {str(ws.Id) for ws in wsm.WritingSystems}
    except Exception:  # noqa: BLE001
        return []
    active = _active(proj)
    return sorted(t for t in stored if t.lower() not in active)


def _plan(*tags):
    from gramtrans.Lib.models import WSKind, WSMapping, WSMappingEntry
    mapping = WSMapping(entries=tuple(
        WSMappingEntry(source_ws_id=t, source_ws_kind=WSKind.ANALYSIS,
                       target_ws_id=t, create_in_target=True) for t in tags))
    return type("P", (), {"ws_mapping": mapping})()


def test_preflight_and_move_agree_live(target):
    from gramtrans.Lib import api
    from gramtrans.Lib.ws_mapping import preflight_ws_creates

    active_before = _active(target)
    assert NEW_TAG not in active_before, "[SETUP] restored Target already has the tag"
    existing = sorted(active_before)[0]
    inactive = _stored_inactive(target)[:1]
    plan = _plan(NEW_TAG, existing, *inactive)

    predicted = preflight_ws_creates(target, plan.ws_mapping)
    assert _active(target) == active_before, "[FAIL] Preview preflight changed the target"
    assert [r.item_name for r in predicted] == inactive
    assert all(r.severity == "warning" for r in predicted)

    failures = []
    created = api._ensure_writing_systems(target, None, plan, failures)

    assert created == [NEW_TAG]
    assert NEW_TAG in _active(target), "[FAIL] created WS is not active"
    assert failures == predicted, "[FAIL] Move's failures differ from Preview's prediction"
    print("[PASS] created=%s existing-skipped=%s stored-inactive=%s"
          % (created, existing, inactive or "(none in this Target)"))
