"""Issue #163 live gate (orphan delete): when a relation's create FAILS in
Move, a LexRefType lazily created in this run and still empty is deleted again
(`_discard_empty_lazy_lex_ref_type`, a new LCM write).

The LexReference factory Create used by `reproduce_lexical_relation` is wrapped
to raise on selected calls; the TARGET is re-opened from LCM and read back.

* (a) type "GT163O A", ONE relation, create forced to fail: type GUID ABSENT
  from the target; a 'create failed' drop record is in the run report.
* (c) type "GT163O C", TWO relations, the FIRST create fails, the second
  succeeds: exactly ONE LexRefType with that GUID holding exactly ONE relation
  (the survivor) with the right members (delete-then-recreate, same GUID).
* (b) control: type "GT163O B" pre-exists in the target; its relation create
  fails: the type is still present.

WRITE PATH: ONLY GT-Src-163 and GT-Sandbox-163, restored from
``Target 2026-07-06 0218.fwbackup`` before and after. Never Esperanto.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue163_orphan_delete_live.py -q -s
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "GT-Src-163"
TARGET_NAME = "GT-Sandbox-163"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
A_NAME = "GT163O A"
B_NAME = "GT163O B"
C_NAME = "GT163O C"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))


def _guard(name):
    # Write guard: these two throwaway projects and nothing else.
    assert name in (SOURCE_NAME, TARGET_NAME), name
    assert TARGET_NAME == "GT-Sandbox-163" and SOURCE_NAME == "GT-Src-163"


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
    assert not write or name == SOURCE_NAME, name  # write guard
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


def _fork_target():
    _restore(SOURCE_NAME)
    _guard(TARGET_NAME)
    tdir = PROJECTS_ROOT / TARGET_NAME
    if tdir.exists():
        shutil.rmtree(tdir)
    shutil.copytree(PROJECTS_ROOT / SOURCE_NAME, tdir,
                    ignore=shutil.ignore_patterns("*.lock"))
    (tdir / ("%s.fwdata" % SOURCE_NAME)).rename(tdir / ("%s.fwdata" % TARGET_NAME))


def _mk_stems(proj, tag, n):
    out = []
    for i in range(1, n + 1):
        e = proj.LexEntry.Create("gtorph%s%d" % (tag, i), "stem",
                                 create_blank_sense=False)
        out.append(proj.LexEntry.AddSense(e, "gt163o %s%d" % (tag, i)))
    return out


def _author_pre_fork() -> dict:
    """Source: relation type B (forked into the target, so it PRE-EXISTS
    there). Its relation is authored after the fork."""
    proj = _open(SOURCE_NAME, write=True)
    try:
        b_type = proj.LexReferences.CreateType(B_NAME, "Symmetric")
        return dict(b_type=_g(b_type))
    finally:
        proj.CloseProject()


def _author_post_fork(fx) -> dict:
    proj = _open(SOURCE_NAME, write=True)
    try:
        lr = proj.LexReferences
        b_type = proj.Object(fx["b_type"])
        b_sen = _mk_stems(proj, "b", 2)
        a_type = lr.CreateType(A_NAME, "Symmetric")
        c_type = lr.CreateType(C_NAME, "Symmetric")
        a_sen = _mk_stems(proj, "a", 2)
        c_sen = _mk_stems(proj, "c", 4)
        r_b = lr.Create(b_type, b_sen)
        r_a = lr.Create(a_type, a_sen)
        r_c1 = lr.Create(c_type, [c_sen[0], c_sen[1]])
        r_c2 = lr.Create(c_type, [c_sen[2], c_sen[3]])
        return dict(
            a_type=_g(a_type), c_type=_g(c_type),
            r_a=_g(r_a), r_b=_g(r_b), r_c=[_g(r_c1), _g(r_c2)],
            a_senses=[_g(s) for s in a_sen],
            c_senses={_g(r_c1): [_g(c_sen[0]), _g(c_sen[1])],
                      _g(r_c2): [_g(c_sen[2]), _g(c_sen[3])]})
    finally:
        proj.CloseProject()


def _target_state() -> dict:
    """Re-open the TARGET from LCM and read every relation type / relation."""
    from SIL.LCModel import ILexRefType, ILexReference
    proj = _open(TARGET_NAME)
    try:
        lr = proj.LexReferences
        type_list = [(_g(t), lr.GetTypeName(t)) for t in lr.GetAllTypes()]
        rels = []
        for t in lr.GetAllTypes():
            for r in ILexRefType(t).MembersOC:
                r = ILexReference(r)
                rels.append((_g(r), _g(t), [_g(x) for x in r.TargetsRS]))
        return {"types": type_list,
                "type_guids": [g for g, _n in type_list],
                "rels": rels}
    finally:
        proj.CloseProject()


class _FailingFactory:
    """Delegates to the real ILexReferenceFactory; raises on selected Creates."""

    def __init__(self, real, fail, log):
        self._real, self._fail, self._log = real, fail, log

    def Create(self, *args):
        guid, owner = str(args[0]).lower(), args[1]
        owner_guid = str(owner.Guid).lower()
        self._log.append((guid, owner_guid))
        if self._fail(guid, owner_guid):
            raise RuntimeError("forced LexReference create failure (%s)" % guid)
        return self._real.Create(*args)

    def __getattr__(self, name):
        return getattr(self._real, name)


@pytest.fixture(scope="module")
def live():
    try:
        import flexicon  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is unavailable: %s" % exc)
    from unittest import mock
    from harness import full_run
    from gramtrans.Lib import owned
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    def stems_only(_full):
        return Selection(categories={GC.STEMS: True})

    try:
        _restore(SOURCE_NAME)
        fx = _author_pre_fork()
        _guard(TARGET_NAME)
        tdir = PROJECTS_ROOT / TARGET_NAME
        if tdir.exists():
            shutil.rmtree(tdir)
        shutil.copytree(PROJECTS_ROOT / SOURCE_NAME, tdir,
                        ignore=shutil.ignore_patterns("*.lock"))
        (tdir / ("%s.fwdata" % SOURCE_NAME)).rename(
            tdir / ("%s.fwdata" % TARGET_NAME))
        fx.update(_author_post_fork(fx))
        pre = _target_state()

        create_log = []
        c_failed = []

        def fail(rel_guid, owner_guid):
            if rel_guid == fx["r_a"] or rel_guid == fx["r_b"]:
                return True
            if owner_guid == fx["c_type"] and not c_failed:
                c_failed.append(rel_guid)  # FIRST relation walked for C
                return True
            return False

        real_get = owned._get_owned_factory

        def patched(target, name):
            f = real_get(target, name)
            if name == "ILexReferenceFactory":
                return _FailingFactory(f, fail, create_log)
            return f

        with mock.patch.object(owned, "_get_owned_factory", patched):
            plan, report = full_run.run_full_transfer(
                SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
                selection_transform=stems_only, preview_only=False)
        post = _target_state()
        res = dict(fx=fx, pre=pre, post=post, report=report,
                   create_log=create_log,
                   c_failed=c_failed[0] if c_failed else None)
        import gramtrans
        print("[LIVE] gramtrans=%s flexicon=%s" % (gramtrans.__file__, flexicon.__file__))
        print("[LIVE] fixture=%s" % fx)
        print("[LIVE] create calls (rel, type)=%s forced-fail C=%s" % (
            create_log, res["c_failed"]))
        print("[LIVE] PRE  types=%s" % [
            (g, n) for g, n in pre["types"] if n.startswith("GT163O")])
        print("[LIVE] POST types=%s" % [
            (g, n) for g, n in post["types"] if n.startswith("GT163O")])
        print("[LIVE] POST rels=%s" % [
            r for r in post["rels"]
            if r[1] in (fx["a_type"], fx["b_type"], fx["c_type"])])
        print("[LIVE] drops=%s" % [
            (d.owner_guid, d.reason) for d in report.dropped_items
            if d.owner_kind == "LexReference"])
        yield res
    finally:
        for name in (TARGET_NAME, SOURCE_NAME):
            try:
                _restore(name)
                print("[LIVE] restored %s" % name)
            except Exception as exc:  # noqa: BLE001
                print("[WARN] restore of %s failed: %s" % (name, exc))


def _create_failed(report, rel_guid):
    return any(d.owner_kind == "LexReference" and d.owner_guid == rel_guid
               and d.reason.startswith("create failed")
               for d in report.dropped_items)


def test_fixture_shape(live):
    fx, pre = live["fx"], live["pre"]
    assert fx["b_type"] in pre["type_guids"]          # (b) pre-exists
    assert fx["a_type"] not in pre["type_guids"]
    assert fx["c_type"] not in pre["type_guids"]
    created = {g for g, _o in live["create_log"]}
    assert fx["r_a"] in created and fx["r_b"] in created
    assert live["c_failed"] in fx["r_c"]


def test_a_single_relation_failed_create_leaves_no_type(live):
    fx, post = live["fx"], live["post"]
    assert fx["a_type"] not in post["type_guids"]
    assert A_NAME not in [n for _g2, n in post["types"]]
    assert fx["r_a"] not in [r[0] for r in post["rels"]]
    assert _create_failed(live["report"], fx["r_a"]), [
        (d.owner_guid, d.reason) for d in live["report"].dropped_items]


def test_c_delete_then_recreate_same_guid_one_type_one_relation(live):
    fx, post = live["fx"], live["post"]
    assert post["type_guids"].count(fx["c_type"]) == 1, post["type_guids"]
    assert [n for _g2, n in post["types"]].count(C_NAME) == 1
    failed = live["c_failed"]
    survivor = [g for g in fx["r_c"] if g != failed][0]
    in_type = [r for r in post["rels"] if r[1] == fx["c_type"]]
    assert [r[0] for r in in_type] == [survivor], in_type
    assert in_type[0][2] == fx["c_senses"][survivor]
    assert failed not in [r[0] for r in post["rels"]]
    assert _create_failed(live["report"], failed)


def test_b_preexisting_type_survives_failed_create(live):
    fx, post = live["fx"], live["post"]
    assert post["type_guids"].count(fx["b_type"]) == 1
    assert fx["r_b"] not in [r[0] for r in post["rels"]]
    assert _create_failed(live["report"], fx["r_b"])
