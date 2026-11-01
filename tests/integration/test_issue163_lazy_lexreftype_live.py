"""Issue #163 live gate -- Move creates a missing relation type only when at
least one relation of that type survives the structural guards, and Preview
announces exactly the types Move creates.

Before the fix `_evaluate_lexical_relation` resolved (and, in Move, CREATED) a
missing `LexRefType` before the pair/tree/zero-member guards ran. A type whose
only relation was then dropped was left in the target as an EMPTY relation
type, and Preview announced its create to match.

Fixture (source only, authored after the target fork):

* ``GT163 Keep`` -- a NEW relation type with one relation (s1, s2) whose
  members are both stems: it survives, so the type MUST be created.
* ``GT163 Drop`` -- a NEW pair-type with one relation (s1, affix-sense): under
  a STEMS-only selection the affix sense is not copied, so the pair is reduced
  below its minimum and dropped -- the type must NOT be created.

WRITE PATH: writes ONLY the two private throwaway projects below, both rebuilt
from ``Target 2026-07-06 0218.fwbackup``:

* ``GT-Src-163``     -- SOURCE (write-enabled only while authoring)
* ``GT-Sandbox-163`` -- TARGET (a fork of the source before authoring)

Never Target, Esperanto, Ejagham*, Mbugwe*, Ngoreme*, or another agent's
GT-Src-NNN / GT-Sandbox-NNN.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue163_lazy_lexreftype_live.py -v -s
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
KEEP_TYPE_NAME = "GT163 Keep"
DROP_TYPE_NAME = "GT163 Drop"
_PAIR_TYPES = {1, 2, 6, 7, 11, 12}

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


def _author_source() -> dict:
    """Source-only: 2 stem senses, 1 affix sense, a NEW relation type with a
    surviving relation and a NEW pair type whose only relation drops."""
    from SIL.LCModel import ILexRefType
    proj = _open(SOURCE_NAME, write=True)
    try:
        lr = proj.LexReferences
        senses = []
        for i, gloss in enumerate(("one", "two"), start=1):
            e = proj.LexEntry.Create("gtonesixtythree%d" % i, "stem",
                                     create_blank_sense=False)
            senses.append(proj.LexEntry.AddSense(e, "gt163 %s" % gloss))
        affix = proj.LexEntry.Create("gtsixtythreeaff", "suffix",
                                     create_blank_sense=False)
        affix_sense = proj.LexEntry.AddSense(affix, "GT163.AFF")
        keep_type = lr.CreateType(KEEP_TYPE_NAME, "Symmetric")
        drop_type = lr.CreateType(DROP_TYPE_NAME, "Asymmetric",
                                  reverse_name="GT163 Drop Rev")
        keep_mt = int(ILexRefType(keep_type).MappingType)
        drop_mt = int(ILexRefType(drop_type).MappingType)
        print("[LIVE] keep mt=%d drop mt=%d" % (keep_mt, drop_mt))
        r_keep = lr.Create(keep_type, [senses[0], senses[1]])
        r_drop = lr.Create(drop_type, [senses[0], affix_sense])
        return dict(keep_type=_g(keep_type), drop_type=_g(drop_type),
                    keep_mt=keep_mt, drop_mt=drop_mt,
                    r_keep=_g(r_keep), r_drop=_g(r_drop),
                    senses=[_g(s) for s in senses],
                    affix_sense=_g(affix_sense))
    finally:
        proj.CloseProject()


def _target_state() -> dict:
    from SIL.LCModel import ILexRefType, ILexReference
    proj = _open(TARGET_NAME)
    try:
        lr = proj.LexReferences
        types = {_g(t): t for t in lr.GetAllTypes()}
        rels = {}
        for t_guid, t in types.items():
            for r in ILexRefType(t).MembersOC:
                r = ILexReference(r)
                rels[_g(r)] = (t_guid, [_g(x) for x in r.TargetsRS])
        return {"type_guids": sorted(types),
                "type_names": sorted(lr.GetTypeName(t) for t in types.values()),
                "rels": rels}
    finally:
        proj.CloseProject()


def _lexrel(plan):
    return [(d.owner_kind, d.action.value, d.item_guid, d.item_name)
            for d in getattr(plan, "lexical_relation_decisions", ())]


def _lex_drops(items):
    return sorted((d.owner_kind, d.owner_guid, d.item_guid, d.reason)
                  for d in items
                  if d.owner_kind in ("LexReference", "LexRefType"))


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
        res = {"fx": fx, "pre": _target_state()}
        res["preview1"], res["preview1_report"] = run(True)
        res["preview1_lines"] = render_preview_extra_lines(res["preview1"])
        res["move1_plan"], res["move1_report"] = run(False)
        res["post1"] = _target_state()
        import gramtrans
        print("[LIVE] gramtrans=%s flexicon=%s" % (gramtrans.__file__, flexicon.__file__))
        print("[LIVE] source=%s target=%s fixture=%s" % (SOURCE_NAME, TARGET_NAME, fx))
        print("[LIVE] preview1 lexrel=%s" % _lexrel(res["preview1"]))
        print("[LIVE] preview1 lines=%s" % [
            l for l in res["preview1_lines"] if "relation" in l.lower()])
        print("[LIVE] move1 lexrel=%s" % _lexrel(res["move1_plan"]))
        print("[LIVE] preview1 lexrel drops=%s" % _lex_drops(
            getattr(res["preview1"], "dropped_items", ()) or ()))
        print("[LIVE] move1 lexrel drops=%s" % _lex_drops(
            res["move1_report"].dropped_items))
        print("[LIVE] post1 new types=%s" % sorted(
            set(res["post1"]["type_guids"]) - set(res["pre"]["type_guids"])))
        print("[LIVE] post1 new rels=%s" % {
            k: v for k, v in res["post1"]["rels"].items()
            if k not in res["pre"]["rels"]})
        yield res
    finally:
        for name in (TARGET_NAME, SOURCE_NAME):
            try:
                _restore(name)
            except Exception as exc:  # noqa: BLE001
                print("[WARN] restore of %s failed: %s" % (name, exc))


def test_fixture_shape(live):
    fx, pre = live["fx"], live["pre"]
    assert fx["drop_mt"] in _PAIR_TYPES, fx["drop_mt"]
    # Keep's mapping type is immaterial ("Symmetric" maps to a pair, 1, on
    # flexicon): both its members are stems, so it clears every guard.
    assert fx["keep_type"] not in pre["type_guids"]
    assert fx["drop_type"] not in pre["type_guids"]
    # The drop really drops: Move reported the pair guard for r_drop. If this
    # fails the fixture is wrong (the affix sense was copied), not the fix.
    assert any(d.owner_guid == fx["r_drop"] and "pair relation" in d.reason
               for d in live["move1_report"].dropped_items), _lex_drops(
        live["move1_report"].dropped_items)


def test_type_whose_only_relation_drops_is_not_created(live):
    fx, post = live["fx"], live["post1"]
    assert fx["drop_type"] not in post["type_guids"]
    assert DROP_TYPE_NAME not in post["type_names"]
    assert fx["r_drop"] not in post["rels"]


def test_type_with_a_surviving_relation_is_created(live):
    fx, post = live["fx"], live["post1"]
    assert fx["keep_type"] in post["type_guids"]
    s1, s2 = fx["senses"]
    assert post["rels"][fx["r_keep"]] == (fx["keep_type"], [s1, s2])


def test_preview_announces_only_the_surviving_type(live):
    fx = live["fx"]
    rows = _lexrel(live["preview1"])
    assert sorted(rows) == sorted([
        ("LexRefType", "create", fx["keep_type"], KEEP_TYPE_NAME),
        ("LexReference", "create", fx["r_keep"], KEEP_TYPE_NAME),
    ]), rows
    lines = live["preview1_lines"]
    assert ("    Create relation type '%s' {%s}" % (KEEP_TYPE_NAME, fx["keep_type"])
            in lines), lines
    assert not [l for l in lines if DROP_TYPE_NAME in l], lines


def test_preview_equals_move(live):
    pre, post = live["pre"], live["post1"]
    assert sorted(_lexrel(live["move1_plan"])) == sorted(_lexrel(live["preview1"]))
    preview_types = sorted(g for k, _a, g, _n in _lexrel(live["preview1"])
                           if k == "LexRefType")
    preview_rels = sorted(g for k, _a, g, _n in _lexrel(live["preview1"])
                          if k == "LexReference")
    assert sorted(set(post["type_guids"]) - set(pre["type_guids"])) == preview_types
    assert sorted(set(post["rels"]) - set(pre["rels"])) == preview_rels
