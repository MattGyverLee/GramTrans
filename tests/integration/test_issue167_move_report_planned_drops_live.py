"""Issue #167 live gate -- the Move RunReport carries every Preview-planned
text-walk drop that Move does not resolve, exactly once.

Before the fix `api.execute_move` (and `transfer.execute` under it) built
`RunReport.dropped_items` from Move-time drops only. The wordform-category
drops are decided at Preview (`wordforms.resolve_or_report_category`) and Move
returns early on REPORT_DROPPED, so a Move that left three analyses'
categories unset reported 0 drops (batch 141-147 cycle-2 Finding A).

Fixture (the GT-Src-146P1 scenario): a POS authored in the source BEFORE the
target is forked (so it is shared), then -- source only -- an absent POS and
one text whose segment carries four approved analyses, three on the absent
POS and one on the shared POS.

WRITE PATH: writes ONLY the two private throwaway projects below, both rebuilt
from ``Target 2026-07-06 0218.fwbackup``:

* ``GT-Src-167``     -- SOURCE (write-enabled only while authoring)
* ``GT-Sandbox-167`` -- TARGET (a fork of the source before authoring)

Never Target, Esperanto, Ejagham*, Mbugwe*, Ngoreme*, or another agent's
GT-Src-NNN / GT-Sandbox-NNN.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue167_move_report_planned_drops_live.py -v -s
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "GT-Src-167"
TARGET_NAME = "GT-Sandbox-167"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_DIR = PROJECTS_ROOT / TARGET_NAME
TARGET_PATH = str(TARGET_DIR / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
ABSENT_FORMS = ("gt167alpha", "gt167beta", "gt167gamma")
SHARED_FORM = "gt167delta"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))


def _guard(name):
    # Write guard: these two throwaway projects and nothing else.
    assert name in (SOURCE_NAME, TARGET_NAME), name
    assert TARGET_NAME == "GT-Sandbox-167" and SOURCE_NAME == "GT-Src-167"


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
    _guard(name)
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


def _add_pos(proj, name):
    from SIL.LCModel import ILangProject, IPartOfSpeechFactory
    from SIL.LCModel.Core.Text import TsStringUtils
    lp = ILangProject(proj.Cache.LangProject)
    pos = proj.Cache.ServiceLocator.GetService(IPartOfSpeechFactory).Create()
    lp.PartsOfSpeechOA.PossibilitiesOS.Add(pos)
    ws = proj.Cache.DefaultAnalWs
    pos.Name.set_String(ws, TsStringUtils.MakeString(name, ws))
    pos.Abbreviation.set_String(ws, TsStringUtils.MakeString(name[:10], ws))
    return pos


def _fork_target():
    """Restore the source, add the shared POS, then copy it as the target."""
    _restore(SOURCE_NAME)
    proj = _open(SOURCE_NAME, write=True)
    try:
        shared = _g(_add_pos(proj, "GT167 shared pos"))
    finally:
        proj.CloseProject()
    _guard(TARGET_NAME)
    if TARGET_DIR.exists():
        shutil.rmtree(TARGET_DIR)
    shutil.copytree(PROJECTS_ROOT / SOURCE_NAME, TARGET_DIR,
                    ignore=shutil.ignore_patterns("*.lock"))
    (TARGET_DIR / ("%s.fwdata" % SOURCE_NAME)).rename(Path(TARGET_PATH))
    return shared


def _author(shared_guid) -> dict:
    from SIL.LCModel import ILangProject, IPartOfSpeech
    proj = _open(SOURCE_NAME, write=True)
    try:
        lp = ILangProject(proj.Cache.LangProject)
        absent = _add_pos(proj, "GT167 absent pos")
        shared = [x for x in lp.PartsOfSpeechOA.PossibilitiesOS if _g(x) == shared_guid][0]
        text = proj.Texts.Create("GT167 text")
        body = " ".join(ABSENT_FORMS + (SHARED_FORM,)) + "."
        para = proj.Paragraphs.Create(text, body)
        segs = list(proj.Paragraphs.GetSegments(para))
        if not segs:
            proj.Segments.AppendSentence(para, body)
            segs = list(proj.Paragraphs.GetSegments(para))
        seg = segs[0]
        analyses = {}
        for form, cat in [(f, absent) for f in ABSENT_FORMS] + [(SHARED_FORM, shared)]:
            wf = proj.Wordforms.Create(form)
            a = proj.WfiAnalyses.Create(wf)
            proj.WfiAnalyses.SetCategory(a, IPartOfSpeech(cat))
            proj.WfiAnalyses.ApproveAnalysis(a)
            proj.Segments.AppendAnalysis(seg, a)
            analyses[form] = _g(a)
        return dict(text=_g(text), absent=_g(absent), shared=shared_guid, an=analyses)
    finally:
        proj.CloseProject()


def _target_state(fx) -> dict:
    from SIL.LCModel import ILangProject
    proj = _open(TARGET_NAME)
    try:
        lp = ILangProject(proj.Cache.LangProject)
        out = {"pos": sorted(_g(x) for x in lp.PartsOfSpeechOA.PossibilitiesOS), "cat": {}}
        for form in fx["an"]:
            row = []
            for w in proj.Wordforms.GetAll():
                if str(proj.Wordforms.GetForm(w)) != form:
                    continue
                for a in proj.WfiAnalyses.GetAll(w):
                    c = proj.WfiAnalyses.GetCategory(a)
                    row.append(_g(c) if c is not None else None)
            out["cat"][form] = row
        return out
    finally:
        proj.CloseProject()


def _cat_drops(records):
    return [d for d in records
            if d.owner_kind == "WfiAnalysis" and d.field_name == "CategoryRA"]


@pytest.fixture(scope="module")
def live(tmp_path_factory):
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection
    import gramtrans
    import flexicon
    print("[ENV] gramtrans=%s" % gramtrans.__file__)
    print("[ENV] flexicon=%s" % flexicon.__file__)
    report_json = tmp_path_factory.mktemp("issue167") / "move-report.json"

    def run(fx, preview_only=False, report_path=None):
        _guard(TARGET_NAME)

        def _sel(_full):
            return Selection(categories={GC.TEXTS: True},
                             text_picks=frozenset([fx["text"]]), include_closure=True)
        return full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
            selection_transform=_sel, preview_only=preview_only,
            report_path=report_path)
    try:
        fx = _author(_fork_target())
        res = {"fx": fx, "pre": _target_state(fx)}
        before = Path(TARGET_PATH).read_bytes()
        res["preview"], _ = run(fx, preview_only=True)
        res["preview_wrote"] = Path(TARGET_PATH).read_bytes() != before
        res["plan"], res["report"] = run(fx, report_path=str(report_json))
        res["json"] = (json.loads(report_json.read_text(encoding="utf-8"))
                       if report_json.is_file() else None)
        res["post"] = _target_state(fx)
        print("[LIVE-167] fixture=%s" % fx)
        print("[LIVE-167] pre=%s" % res["pre"])
        print("[LIVE-167] preview CategoryRA drops=%s" % sorted(
            (d.owner_guid, d.origin) for d in _cat_drops(res["preview"].dropped_items)))
        print("[LIVE-167] move plan drops=%d report drops=%d" % (
            len(res["plan"].dropped_items), len(res["report"].dropped_items)))
        print("[LIVE-167] report CategoryRA drops=%s" % sorted(
            (d.owner_guid, d.reason) for d in _cat_drops(res["report"].dropped_items)))
        print("[LIVE-167] post=%s" % res["post"])
        yield res
    finally:
        for name in (TARGET_NAME, SOURCE_NAME):
            try:
                _restore(name)
            except Exception as exc:  # noqa: BLE001
                print("[WARN] restore of %s failed: %s" % (name, exc))


def test_fixture_preconditions(live):
    fx, pre = live["fx"], live["pre"]
    assert fx["absent"] not in pre["pos"] and fx["shared"] in pre["pos"]
    assert all(v == [] for v in pre["cat"].values()), pre
    assert not live["preview_wrote"]


def test_preview_plans_one_text_walk_drop_per_absent_pos_analysis(live):
    from gramtrans.Lib.models import DROP_ORIGIN_PREVIEW_TEXTS
    fx = live["fx"]
    drops = _cat_drops(live["preview"].dropped_items)
    assert sorted(d.owner_guid for d in drops) == sorted(fx["an"][f] for f in ABSENT_FORMS)
    assert all(d.origin == DROP_ORIGIN_PREVIEW_TEXTS for d in drops)


def test_move_leaves_the_three_categories_unset(live):
    fx, post = live["fx"], live["post"]
    assert fx["absent"] not in post["pos"], "absent POS must never be fabricated"
    for form in ABSENT_FORMS:
        assert post["cat"][form] == [None], (form, post["cat"])


def test_move_report_carries_each_planned_drop_exactly_once(live):
    """The #167 claim: the 3 planned drops are on the Move report, once each.
    RED on unfixed code (report had 0)."""
    from gramtrans.Lib.models import dropped_identity, move_blind_plan_drops
    fx, plan, report = live["fx"], live["plan"], live["report"]
    absent_guids = sorted(fx["an"][f] for f in ABSENT_FORMS)
    report_cat = _cat_drops(report.dropped_items)
    assert sorted(d.owner_guid for d in report_cat
                  if d.owner_guid in absent_guids) == absent_guids
    planned = move_blind_plan_drops(plan)
    assert planned, "the Move's own plan must carry the text-walk drops"
    counts = Counter(dropped_identity(d) for d in report.dropped_items)
    for d in planned:
        assert counts[dropped_identity(d)] == 1, (dropped_identity(d), counts)


def test_move_report_has_no_duplicate_drop(live):
    from gramtrans.Lib.models import dropped_identity
    counts = Counter(dropped_identity(d) for d in live["report"].dropped_items)
    assert [k for k, n in counts.items() if n > 1] == []


def test_report_json_names_the_origin(live):
    data = live["json"]
    if data is None:
        pytest.skip("run_full_transfer wrote no report JSON")
    absent_guids = {live["fx"]["an"][f] for f in ABSENT_FORMS}
    rows = [r for r in data.get("dropped_items", [])
            if r.get("field_name") == "CategoryRA" and r.get("owner_guid") in absent_guids]
    assert len(rows) == 3, rows
    assert all(r.get("origin") == "preview:texts" for r in rows), rows
