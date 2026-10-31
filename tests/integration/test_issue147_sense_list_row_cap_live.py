"""Issue #147 live gate -- the sense-list reference-decision renderer caps its
rows on a REAL Preview of a lexicon that exceeds `SENSE_LIST_REF_ROW_CAP`.

Fixture (authored in the source, Preview only -- Move is never run):

* CAP + 5 appendixes created BEFORE the target fork -> shared -> LINK rows.
  They must collapse to one AppendixesRC count line.
* CAP + 3 new DomainTypes thesaurus items created AFTER the fork -> CREATE
  rows. Exactly CAP are itemized plus "... and 3 more Create rows".
* 2 appendixes created AFTER the fork -> not transferred, itemized.

WRITE PATH: authoring writes ONLY ``GT-Src-147``; ``GT-Sandbox-147`` is a file
copy of it and is only read (Preview). Both are restored from
``Target 2026-07-06 0218.fwbackup`` afterwards. Names are pinned here.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue147_sense_list_row_cap_live.py -v -s
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "GT-Src-147"
TARGET_NAME = "GT-Sandbox-147"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))

N_SENSES = 10
EXTRA_LINK, EXTRA_CREATE, N_DROP = 5, 3, 2


def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            return d / BACKUP_NAME
    pytest.fail("[FAIL] backup %r not found under %s" % (BACKUP_NAME, _BACKUP_DIRS))


def _restore(name):
    assert name in (SOURCE_NAME, TARGET_NAME), name  # write guard
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


def _make_appendix(proj, text) -> str:
    from SIL.LCModel import (ILangProject, ILexDb, ILexAppendixFactory, IStTextFactory,
                             IStTxtParaFactory, IStText)
    from SIL.LCModel.Core.Text import TsStringUtils
    sl = proj.Cache.ServiceLocator
    lexdb = ILexDb(ILangProject(proj.Cache.LangProject).LexDbOA)
    ap = sl.GetService(ILexAppendixFactory).Create()
    lexdb.AppendixesOC.Add(ap)
    st = sl.GetService(IStTextFactory).Create()
    ap.ContentsOA = st
    para = sl.GetService(IStTxtParaFactory).Create()
    IStText(st).ParagraphsOS.Add(para)
    para.Contents = TsStringUtils.MakeString(text, proj.Cache.DefaultAnalWs)
    return _g(ap)


def _author(cap: int) -> dict:
    # 1. Shared appendixes, then fork the target.
    _restore(SOURCE_NAME)
    proj = _open(SOURCE_NAME, write=True)
    try:
        shared = [_make_appendix(proj, "GT147 shared appendix %02d" % i)
                  for i in range(cap + EXTRA_LINK)]
    finally:
        proj.CloseProject()
    tdir = PROJECTS_ROOT / TARGET_NAME
    if tdir.exists():
        shutil.rmtree(tdir)
    shutil.copytree(PROJECTS_ROOT / SOURCE_NAME, tdir,
                    ignore=shutil.ignore_patterns("*.lock"))
    (tdir / ("%s.fwdata" % SOURCE_NAME)).rename(tdir / ("%s.fwdata" % TARGET_NAME))

    # 2. Source-only state: new thesaurus items, absent appendixes, senses.
    from SIL.LCModel import (ILangProject, ILexDb, ICmPossibilityList,
                             ICmPossibilityFactory, ILexSense)
    from SIL.LCModel.Core.Text import TsStringUtils
    from System import Guid as DotNetGuid
    proj = _open(SOURCE_NAME, write=True)
    try:
        lexdb = ILexDb(ILangProject(proj.Cache.LangProject).LexDbOA)
        sl = proj.Cache.ServiceLocator
        ws = proj.Cache.DefaultAnalWs
        absent = [_make_appendix(proj, "GT147 source-only appendix %d" % i)
                  for i in range(N_DROP)]
        pf = ICmPossibilityFactory(sl.GetService(ICmPossibilityFactory))
        dom = ICmPossibilityList(lexdb.DomainTypesOA)
        created = []
        for i in range(cap + EXTRA_CREATE):
            item = pf.Create(DotNetGuid.NewGuid(), dom)  # appends to PossibilitiesOS
            name = "GT147 new item %02d" % i
            item.Name.set_String(ws, TsStringUtils.MakeString(name, ws))
            item.Abbreviation.set_String(ws, TsStringUtils.MakeString("GT147n%02d" % i, ws))
            created.append(item)
        aps = {_g(a): a for a in lexdb.AppendixesOC}
        entry = proj.LexEntry.Create("gtfixonefortyseven", create_blank_sense=False)
        senses = [ILexSense(proj.Senses.Create(entry, "sense %d" % i))
                  for i in range(N_SENSES)]
        for j, g in enumerate(shared):
            senses[j % N_SENSES].AppendixesRC.Add(aps[g])
        for j, item in enumerate(created):
            senses[j % N_SENSES].ThesaurusItemsRC.Add(item)
        for g in absent:
            senses[0].AppendixesRC.Add(aps[g])
        return dict(shared=shared, absent=absent,
                    created=[_g(c) for c in created],
                    senses=[_g(s) for s in senses])
    finally:
        proj.CloseProject()


@pytest.fixture(scope="module")
def live():
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection
    from gramtrans.Lib.preview import SENSE_LIST_REF_ROW_CAP as cap
    try:
        fx = _author(cap)
        pre_bytes = Path(TARGET_PATH).read_bytes()
        plan, _ = full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
            selection_transform=lambda _f: Selection(categories={GC.STEMS: True}),
            preview_only=True)
        wrote = Path(TARGET_PATH).read_bytes() != pre_bytes
        import gramtrans
        import flexicon
        print("[LIVE] gramtrans=%s flexicon=%s" % (gramtrans.__file__, flexicon.__file__))
        yield dict(fx=fx, plan=plan, wrote=wrote, cap=cap)
    finally:
        for name in (TARGET_NAME, SOURCE_NAME):
            try:
                _restore(name)
            except Exception as exc:  # noqa: BLE001
                print("[WARN] restore of %s failed: %s" % (name, exc))


def test_preview_wrote_nothing(live):
    assert not live["wrote"]


def test_preview_pane_caps_and_collapses_with_exact_counts(live):
    from gramtrans.Lib.preview import (render_preview_extra_lines,
                                       render_sense_list_reference_decisions)
    cap, fx = live["cap"], live["fx"]
    lines = render_sense_list_reference_decisions(live["plan"])
    print("[LIVE] sense-list section (%d lines):\n%s" % (len(lines), "\n".join(lines)))
    assert set(lines) <= set(render_preview_extra_lines(live["plan"]))

    # The decisions themselves are complete -- the cap is render-only.
    recs = {(d.field_name, d.action.value, d.item_guid)
            for a in live["plan"].actions
            for d in (getattr(a, "reference_decisions", ()) or ())}
    assert {("AppendixesRC", "link", g) for g in fx["shared"]} <= recs
    assert {("ThesaurusItemsRC", "create", g) for g in fx["created"]} <= recs
    assert {("AppendixesRC", "report_dropped", g) for g in fx["absent"]} <= recs

    create = [ln for ln in lines if ln.startswith("    Create  ThesaurusItemsRC '")]
    assert len(create) == cap
    assert ("    ... and %d more Create rows not shown here (%d total)"
            % (EXTRA_CREATE, cap + EXTRA_CREATE)) in lines
    link = [ln for ln in lines if ln.startswith("    Link  ")]
    assert link == [
        "    Link  AppendixesRC: %d items already in the target  (%d senses) "
        "-- itemized list collapsed above %d rows"
        % (cap + EXTRA_LINK, N_SENSES, cap)], link
    drop = [ln for ln in lines if ln.startswith("    Not transferred  AppendixesRC '")]
    assert len(drop) == N_DROP
    assert all(re.search(r"\{(%s)\}" % "|".join(fx["absent"]), ln) for ln in drop)
    assert not any("Not transferred rows not shown" in ln for ln in lines)
