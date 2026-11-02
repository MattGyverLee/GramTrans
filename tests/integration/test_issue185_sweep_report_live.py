"""Issue #185 live gate: the end-of-run sweep REPORTS the lazily created
relation type it deletes (and the run-once entry point is wired in).

Setup (Target is the ONLY project written):
  * Target is restored from ``Target 2026-07-06 0218.fwbackup``.
  * The relation type used by Esperanto's single `LexReference`
    (GUID b77a435c-...) is deleted from Target, so Move must create it LAZILY.
  * The `ILexReferenceFactory.Create` used by `reproduce_lexical_relation` is
    wrapped to raise, so no relation of that type survives and the sweep
    deletes the now-empty type.
Esperanto is the SOURCE, opened read-only by the harness; it is never written.

Asserts, re-reading Target from LCM after the run: the type is absent, the
relation is absent, and the run report carries BOTH the relation's
"create failed" drop AND an info-level `LexRefType` drop saying the type was
not created.

Run (after claiming Target with the lockout skill):
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue185_sweep_report_live.py -q -s
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

SOURCE_NAME = "Esperanto"          # READ-ONLY source, never written
TARGET_NAME = "Target"             # the ONLY project this test writes
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
TYPE_GUID = "b77a435c-ea5e-11de-9a66-0013722f8dec"   # Esperanto's relation type
REL_GUID = "d989ee63-94ba-43c4-9b32-c15f245f5f25"    # its one LexReference

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))


def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            return d / BACKUP_NAME
    pytest.fail("[FAIL] backup %r not found under %s" % (BACKUP_NAME, _BACKUP_DIRS))


def _restore_target():
    from harness.restore import restore_target
    restore_target(TARGET_NAME, backup_path=_backup_path())


def _open(name, write=False):
    # Write guard: Target and nothing else.
    assert not write or name == TARGET_NAME, name
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    proj = FLExProject()
    try:
        proj.OpenProject(projectName=name, writeEnabled=write,
                         **({"undoable": False} if write else {}))
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but cannot open %r: %s" % (name, exc))
    return proj


def _target_type_guids():
    proj = _open(TARGET_NAME)
    try:
        return [str(t.Guid).lower() for t in proj.LexReferences.GetAllTypes()]
    finally:
        proj.CloseProject()


def _delete_type_from_target():
    proj = _open(TARGET_NAME, write=True)
    try:
        for t in list(proj.LexReferences.GetAllTypes()):
            if str(t.Guid).lower() == TYPE_GUID:
                proj.LexReferences.DeleteType(t)
    finally:
        proj.CloseProject()


class _FailingFactory:
    def __init__(self, real, log):
        self._real, self._log = real, log

    def Create(self, *args):
        self._log.append(str(args[0]).lower())
        raise RuntimeError("forced LexReference create failure (%s)" % args[0])

    def __getattr__(self, name):
        return getattr(self._real, name)


@pytest.fixture(scope="module")
def live():
    """Drive the REAL production entry point (`reproduce_all_lexical_relations
    _once`) against live handles: Esperanto read-only as source, Target open
    for write as target. A full STEMS transfer of Esperanto is not needed to
    reach the sweep -- the relation's members are put in the copy set
    directly, and every relation create is forced to fail."""
    from types import SimpleNamespace
    from unittest import mock
    from gramtrans.Lib import categories, owned

    src = tgt = None
    try:
        _restore_target()
        _delete_type_from_target()
        pre = _target_type_guids()
        src = _open(SOURCE_NAME)
        tgt = _open(TARGET_NAME, write=True)
        from SIL.LCModel import ILexReference
        rel = ILexReference(src.Object(REL_GUID))
        members = {str(m.Guid).lower(): m for m in rel.TargetsRS}
        assert members, "source relation has no members"
        ctx = SimpleNamespace(source_handle=src, target_handle=tgt,
                              _copy_set=dict(members), _ws_map={})
        create_log = []
        real_get = owned._get_owned_factory

        def patched(target, name):
            f = real_get(target, name)
            if name == "ILexReferenceFactory":
                return _FailingFactory(f, create_log)
            return f

        cache, dropped = {}, []
        with mock.patch.object(owned, "_get_owned_factory", patched):
            categories.reproduce_all_lexical_relations_once(
                ctx, "gt185-live", cache, dropped)
            second_raised = False
            try:
                categories.reproduce_all_lexical_relations_once(
                    ctx, "gt185-live", cache, dropped)
            except RuntimeError:
                second_raised = True
        tgt.CloseProject()
        tgt = None
        post = _target_type_guids()
        print("[LIVE] PRE  type present=%s" % (TYPE_GUID in pre))
        print("[LIVE] create attempts=%s" % create_log)
        print("[LIVE] POST type present=%s" % (TYPE_GUID in post))
        print("[LIVE] second call raised=%s" % second_raised)
        print("[LIVE] drops=%s" % [
            (d.owner_kind, d.owner_guid, d.severity, d.reason)
            for d in dropped])
        yield dict(pre=pre, post=post, dropped=dropped,
                   create_log=create_log, second_raised=second_raised)
    finally:
        for h in (tgt, src):
            try:
                if h is not None:
                    h.CloseProject()
            except Exception:  # noqa: BLE001
                pass
        try:
            _restore_target()
            print("[LIVE] restored Target")
        except Exception as exc:  # noqa: BLE001
            print("[WARN] restore of Target failed: %s" % exc)


def test_fixture_shape(live):
    assert TYPE_GUID not in live["pre"]           # Move must create it lazily
    assert REL_GUID in live["create_log"]         # the relation create was tried


def test_empty_lazy_type_is_deleted_from_target(live):
    assert TYPE_GUID not in live["post"]


def test_sweep_reports_the_deleted_type(live):
    rows = [d for d in live["dropped"]
            if d.owner_kind == "LexRefType" and d.owner_guid == TYPE_GUID]
    assert len(rows) == 1, rows
    assert rows[0].severity == "info"
    assert "was not created" in rows[0].reason


def test_second_call_is_refused(live):
    assert live["second_raised"]


def test_relation_create_failure_is_still_reported(live):
    assert any(d.owner_kind == "LexReference" and d.owner_guid == REL_GUID
               and d.reason.startswith("create failed")
               for d in live["dropped"])
