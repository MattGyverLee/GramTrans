"""Issues #141 / #142 live gate -- Preview shows the lexical relations (and the
new relation type) a REAL Move then creates, and a second run plans none.

Before the fix `build_run_plan` discarded `plan_all_lexical_relations`'s CREATE
records and never recorded a `PLAN_TIME_PENDING` relation type, so Preview
showed neither while Move created both.

WRITE PATH: writes ONLY the two private throwaway projects below, both rebuilt
from ``Target 2026-07-06 0218.fwbackup``:

* ``GT-Src-141``     -- SOURCE (write-enabled only while authoring)
* ``GT-Sandbox-141`` -- TARGET (a fork of the source before authoring)

Never Target, Esperanto, Ejagham*, Mbugwe*, Ngoreme*, or another agent's
GT-Src-NNN / GT-Sandbox-NNN.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue141_preview_lexrel_live.py -v -s
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

SOURCE_NAME = "GT-Src-141"
TARGET_NAME = "GT-Sandbox-141"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
NEW_TYPE_NAME = "GT141 Kin"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))


def _guard(name):
    # Write guard: these two throwaway projects and nothing else.
    assert name in (SOURCE_NAME, TARGET_NAME), name
    assert TARGET_NAME == "GT-Sandbox-141" and SOURCE_NAME == "GT-Src-141"


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


def _author_source() -> dict:
    """Source-only: 3 entries (one sense each), a NEW relation type with one
    relation (s1, s2), and one relation (s2, s3) of an EXISTING type that the
    fork shares by GUID."""
    from SIL.LCModel import ILexRefType
    proj = _open(SOURCE_NAME, write=True)
    try:
        lr = proj.LexReferences
        types_before = list(lr.GetAllTypes())
        print("[LIVE] source relation types: %s" % [
            (lr.GetTypeName(t), int(ILexRefType(t).MappingType), _g(t))
            for t in types_before])
        senses = []
        for i, gloss in enumerate(("one", "two", "three"), start=1):
            e = proj.LexEntry.Create("gtonefortyone%d" % i, "stem",
                                     create_blank_sense=False)
            senses.append(proj.LexEntry.AddSense(e, "gt141 %s" % gloss))
        new_type = lr.CreateType(NEW_TYPE_NAME, "Symmetric")
        new_mt = int(ILexRefType(new_type).MappingType)
        # An existing type with the same mapping type, so the same targets
        # are valid for it.
        old_type = next(t for t in types_before
                        if int(ILexRefType(t).MappingType) == new_mt)
        r_new = lr.Create(new_type, [senses[0], senses[1]])
        r_old = lr.Create(old_type, [senses[1], senses[2]])
        return dict(new_type=_g(new_type), old_type=_g(old_type),
                    old_type_name=lr.GetTypeName(old_type), mapping_type=new_mt,
                    r_new=_g(r_new), r_old=_g(r_old),
                    senses=[_g(s) for s in senses])
    finally:
        proj.CloseProject()


def _target_state(fx) -> dict:
    from SIL.LCModel import ILexRefType, ILexReference
    proj = _open(TARGET_NAME)
    try:
        lr = proj.LexReferences
        types = {_g(t): t for t in lr.GetAllTypes()}
        out = {"type_guids": sorted(types),
               "new_type_name": (lr.GetTypeName(types[fx["new_type"]])
                                 if fx["new_type"] in types else None),
               "new_type_mt": (int(ILexRefType(types[fx["new_type"]]).MappingType)
                               if fx["new_type"] in types else None)}
        rels = {}
        for t_guid, t in types.items():
            for r in ILexRefType(t).MembersOC:
                r = ILexReference(r)
                rels[_g(r)] = (t_guid, [_g(x) for x in r.TargetsRS])
        out["rels"] = rels
        return out
    finally:
        proj.CloseProject()


def _lexrel(plan):
    return [(d.owner_kind, d.action.value, d.item_guid, d.item_name)
            for d in getattr(plan, "lexical_relation_decisions", ())]


@pytest.fixture(scope="module")
def live():
    try:
        import flexicon  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is unavailable: %s" % exc)
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection
    from gramtrans.Lib.preview import render_preview_extra_lines

    def stems_only(_full):
        return Selection(categories={GC.STEMS: True})

    def run(preview_only):
        return full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
            selection_transform=stems_only, preview_only=preview_only)

    try:
        _fork_target()
        fx = _author_source()
        res = {"fx": fx, "pre": _target_state(fx)}
        pre_bytes = Path(TARGET_PATH).read_bytes()
        res["preview1"], _ = run(True)
        res["preview1_wrote"] = Path(TARGET_PATH).read_bytes() != pre_bytes
        res["preview1_lines"] = render_preview_extra_lines(res["preview1"])
        res["move1_plan"], res["move1_report"] = run(False)
        res["post1"] = _target_state(fx)
        res["preview2"], _ = run(True)
        res["preview2_lines"] = render_preview_extra_lines(res["preview2"])
        res["move2_plan"], res["move2_report"] = run(False)
        res["post2"] = _target_state(fx)
        import gramtrans
        print("[LIVE] gramtrans=%s flexicon=%s" % (gramtrans.__file__, flexicon.__file__))
        print("[LIVE] source=%s target=%s fixture=%s" % (SOURCE_NAME, TARGET_NAME, fx))
        print("[LIVE] preview1 lexrel=%s" % _lexrel(res["preview1"]))
        print("[LIVE] preview1 lines=%s" % [l for l in res["preview1_lines"]])
        print("[LIVE] move1 actions=%d lexrel=%s" % (
            len(res["move1_plan"].actions), _lexrel(res["move1_plan"])))
        print("[LIVE] post1 new type=%s rels(new)=%s" % (
            (res["post1"]["new_type_name"], res["post1"]["new_type_mt"]),
            {k: v for k, v in res["post1"]["rels"].items()
             if k in (fx["r_new"], fx["r_old"])}))
        print("[LIVE] preview2 actions=%d lexrel=%s lines=%s" % (
            len(res["preview2"].actions), _lexrel(res["preview2"]),
            [l for l in res["preview2_lines"] if "relation" in l.lower()]))
        print("[LIVE] move2 actions=%d" % len(res["move2_plan"].actions))
        print("[LIVE] move1 lexrel drops=%s" % [
            (d.owner_kind, d.owner_guid, d.reason)
            for d in res["move1_report"].dropped_items
            if d.owner_kind in ("LexReference", "LexRefType")])
        yield res
    finally:
        for name in (TARGET_NAME, SOURCE_NAME):
            try:
                _restore(name)
            except Exception as exc:  # noqa: BLE001
                print("[WARN] restore of %s failed: %s" % (name, exc))


def test_fixture_and_preview_wrote_nothing(live):
    fx, pre = live["fx"], live["pre"]
    assert fx["old_type"] in pre["type_guids"]          # shared by GUID
    assert fx["new_type"] not in pre["type_guids"]      # source only
    assert fx["r_new"] not in pre["rels"] and fx["r_old"] not in pre["rels"]
    assert not live["preview1_wrote"]


def test_preview_records_relation_and_type_creates(live):
    fx = live["fx"]
    rows = _lexrel(live["preview1"])
    assert rows == [
        ("LexRefType", "create", fx["new_type"], NEW_TYPE_NAME),
        ("LexReference", "create", fx["r_new"], NEW_TYPE_NAME),
        ("LexReference", "create", fx["r_old"], fx["old_type_name"]),
    ] or sorted(rows) == sorted([
        ("LexRefType", "create", fx["new_type"], NEW_TYPE_NAME),
        ("LexReference", "create", fx["r_new"], NEW_TYPE_NAME),
        ("LexReference", "create", fx["r_old"], fx["old_type_name"]),
    ]), rows


def test_preview_renders_them(live):
    fx, lines = live["fx"], live["preview1_lines"]
    assert "  Lexical relations:" in lines, lines
    assert ("    Create relation type '%s' {%s}" % (NEW_TYPE_NAME, fx["new_type"])
            in lines), lines
    assert "    Create 1 relation of type '%s'" % NEW_TYPE_NAME in lines, lines
    assert "    Create 1 relation of type '%s'" % fx["old_type_name"] in lines, lines


def test_move_creates_exactly_what_preview_showed(live):
    fx, pre, post = live["fx"], live["pre"], live["post1"]
    # Move's own plan agrees with the Preview.
    assert sorted(_lexrel(live["move1_plan"])) == sorted(_lexrel(live["preview1"]))
    new_types = sorted(set(post["type_guids"]) - set(pre["type_guids"]))
    new_rels = sorted(set(post["rels"]) - set(pre["rels"]))
    preview_types = sorted(g for k, _a, g, _n in _lexrel(live["preview1"])
                           if k == "LexRefType")
    preview_rels = sorted(g for k, _a, g, _n in _lexrel(live["preview1"])
                          if k == "LexReference")
    assert new_types == preview_types == [fx["new_type"]]
    assert new_rels == preview_rels == sorted([fx["r_new"], fx["r_old"]])
    assert post["new_type_name"] == NEW_TYPE_NAME
    assert post["new_type_mt"] == fx["mapping_type"]
    s1, s2, s3 = fx["senses"]
    assert post["rels"][fx["r_new"]] == (fx["new_type"], [s1, s2])
    assert post["rels"][fx["r_old"]] == (fx["old_type"], [s2, s3])


def test_second_run_plans_and_creates_nothing(live):
    assert _lexrel(live["preview2"]) == []
    assert not [l for l in live["preview2_lines"] if "relation" in l.lower()]
    assert len(live["preview2"].actions) == 0
    assert len(live["move2_plan"].actions) == 0
    assert live["post2"]["type_guids"] == live["post1"]["type_guids"]
    assert live["post2"]["rels"] == live["post1"]["rels"]
