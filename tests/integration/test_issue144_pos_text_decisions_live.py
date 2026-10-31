"""Issue #144 live gate -- the Preview lines for reversal-entry categories and
text genres / markup tags match what Move then writes, and a re-run is
idempotent.

`preview.render_reversal_and_text_decisions` renders
`ReversalDecision.pos_decision` and `RunPlan.text_plans`' genre and tag
decisions. This module runs a REAL Preview + Move and checks every rendered
row against the target afterwards.

Genres: on this flexicon/LCM the plan carries NO genre decision at all
(`Texts.GetGenre` raises live, see the #144 report's follow-up), so Move
writes no genre either. The genre assertions here are therefore AGREEMENT
checks (Preview rows == genres Move attached), which hold today (both empty)
and keep holding once the genre path is fixed.

WRITE PATH: writes ONLY the two private throwaway projects below, both rebuilt
from ``Target 2026-07-06 0218.fwbackup``:

* ``GT-Src-144``     -- SOURCE (write-enabled only while authoring)
* ``GT-Sandbox-144`` -- TARGET (a fork of the source after the shared state)

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue144_pos_text_decisions_live.py -v -s
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

SOURCE_NAME = "GT-Src-144"
TARGET_NAME = "GT-Sandbox-144"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))


def _write_guard(name):
    assert name in (SOURCE_NAME, TARGET_NAME), name
    assert TARGET_NAME == "GT-Sandbox-144" and SOURCE_NAME == "GT-Src-144"


def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            return d / BACKUP_NAME
    pytest.fail("[FAIL] backup %r not found under %s" % (BACKUP_NAME, _BACKUP_DIRS))


def _restore(name):
    _write_guard(name)
    from harness.restore import restore_target
    restore_target(name, backup_path=_backup_path())


def _open(name, write=False):
    assert not write or name == SOURCE_NAME, name  # only the source is authored
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


def _name(proj, obj, name):
    from SIL.LCModel.Core.Text import TsStringUtils
    ws = proj.Cache.DefaultAnalWs
    obj.Name.set_String(ws, TsStringUtils.MakeString(name, ws))
    obj.Abbreviation.set_String(ws, TsStringUtils.MakeString(name[:10], ws))


def _add_to_list(proj, lst, name, factory_iface):
    obj = proj.Cache.ServiceLocator.GetService(factory_iface).Create()
    lst.PossibilitiesOS.Add(obj)
    _name(proj, obj, name)
    return obj


def _add_child(proj, parent, name):
    from SIL.LCModel import ICmPossibilityFactory
    from System import Guid
    pf = ICmPossibilityFactory(proj.Cache.ServiceLocator.GetService(ICmPossibilityFactory))
    obj = pf.Create(Guid.NewGuid(), parent)
    _name(proj, obj, name)
    return obj


def _rev_index(proj):
    from SIL.LCModel import ILangProject, IReversalIndex
    lp = ILangProject(proj.Cache.LangProject)
    return lp, IReversalIndex(list(lp.LexDbOA.ReversalIndexesOC)[0])


def _author_shared_state() -> dict:
    """A reversal category both projects will have (the LINK case)."""
    from SIL.LCModel import IPartOfSpeechFactory
    _restore(SOURCE_NAME)
    proj = _open(SOURCE_NAME, write=True)
    try:
        _, idx = _rev_index(proj)
        shared = _add_to_list(proj, idx.PartsOfSpeechOA, "GT144 shared revpos",
                              IPartOfSpeechFactory)
        fx = {"shared_pos": _g(shared)}
    finally:
        proj.CloseProject()
    _write_guard(TARGET_NAME)
    tdir = PROJECTS_ROOT / TARGET_NAME
    if tdir.exists():
        shutil.rmtree(tdir)
    shutil.copytree(PROJECTS_ROOT / SOURCE_NAME, tdir,
                    ignore=shutil.ignore_patterns("*.lock"))
    (tdir / ("%s.fwdata" % SOURCE_NAME)).rename(tdir / ("%s.fwdata" % TARGET_NAME))
    return fx


def _author_source_only_state(fx: dict) -> dict:
    """Source only: a reversal category (CREATE), three reversal entries
    (CREATE category / LINK category / no category = negative control), a
    genre and a markup tag (CREATE), and three texts: A (new genre; new + shared
    tag), B (shared genre, no tag), C (no genre, no tag = negative control)."""
    from SIL.LCModel import (ICmPossibility, ICmPossibilityFactory, ILexSense,
                             IPartOfSpeechFactory, IReversalIndexEntry, IStText,
                             IText, ITextTag, ITextTagFactory)
    proj = _open(SOURCE_NAME, write=True)
    try:
        lp, idx = _rev_index(proj)
        new_pos = _add_to_list(proj, idx.PartsOfSpeechOA, "GT144 new revpos",
                               IPartOfSpeechFactory)
        shared_pos = [p for p in idx.PartsOfSpeechOA.PossibilitiesOS
                      if _g(p) == fx["shared_pos"]][0]
        entry = proj.LexEntry.Create("gtfixonefortyfour", create_blank_sense=False)
        sense = ILexSense(proj.Senses.Create(entry, "gt144 sense"))
        rev = {}
        for form, pos in (("gt144revA", new_pos), ("gt144revB", shared_pos),
                          ("gt144revC", None)):
            e = IReversalIndexEntry(proj.ReversalEntries.Create(idx, form, sense))
            if pos is not None:
                e.PartOfSpeechRA = pos
            rev[form] = _g(e)
        shared_genre = ICmPossibility(lp.GenreListOA.PossibilitiesOS[0])
        new_genre = _add_to_list(proj, lp.GenreListOA, "GT144 new genre",
                                 ICmPossibilityFactory)
        tag_type = ICmPossibility(lp.TextMarkupTagsOA.PossibilitiesOS[1])
        shared_tag = ICmPossibility(tag_type.SubPossibilitiesOS[0])
        new_tag = _add_child(proj, tag_type, "GT144 new tag")
        texts = {}
        for key, genre, tags in (("A", new_genre, (new_tag, shared_tag)),
                                 ("B", shared_genre, ()), ("C", None, ())):
            t = proj.Texts.Create("GT144 text %s" % key)
            if genre is not None:
                IText(t).GenresRC.Add(genre)
            para = proj.Paragraphs.Create(t, "gt one. gt two.")
            segs = list(proj.Segments.GetAll(para) or [])
            assert segs, "authoring: paragraph produced no segments"
            st = IStText(IText(t).ContentsOA)
            for poss in tags:
                tt = proj.Cache.ServiceLocator.GetService(ITextTagFactory).Create()
                st.TagsOC.Add(tt)
                tt = ITextTag(tt)
                tt.BeginSegmentRA = segs[0]
                tt.EndSegmentRA = segs[0]
                tt.BeginAnalysisIndex = 0
                tt.EndAnalysisIndex = 0
                tt.TagRA = poss
            texts[key] = _g(t)
        fx.update(
            new_pos=_g(new_pos), rev=rev, sense=_g(sense),
            shared_genre=_g(shared_genre), new_genre=_g(new_genre),
            shared_tag=_g(shared_tag), new_tag=_g(new_tag),
            texts=texts, src_genres={"A": [_g(new_genre)], "B": [_g(shared_genre)],
                                     "C": []})
        return fx
    finally:
        proj.CloseProject()


def _sandbox_state() -> dict:
    from SIL.LCModel import IReversalIndexEntry, IStText, IText, ITextTag
    proj = _open(TARGET_NAME)
    try:
        lp, idx = _rev_index(proj)
        out = {
            "revpos": sorted(_g(p) for p in idx.PartsOfSpeechOA.PossibilitiesOS),
            "rev_entries": sorted(
                (str(e.ReversalForm.BestAnalysisAlternative.Text),
                 _g(e.PartOfSpeechRA) if e.PartOfSpeechRA is not None else None)
                for e in (IReversalIndexEntry(x) for x in idx.EntriesOC)),
            "genre_list": sorted(_g(p) for p in lp.GenreListOA.PossibilitiesOS),
            "tag_list": sorted(_g(s) for t in lp.TextMarkupTagsOA.PossibilitiesOS
                               for s in t.SubPossibilitiesOS),
            "texts": {},
        }
        for t in proj.Texts.GetAll():
            name = str(proj.Texts.GetName(t))
            if not name.startswith("GT144 text "):
                continue
            it = IText(t)
            st = IStText(it.ContentsOA)
            out["texts"][name[-1]] = {
                "genres": sorted(_g(x) for x in it.GenresRC),
                "tags": sorted(_g(ITextTag(x).TagRA) for x in st.TagsOC
                               if ITextTag(x).TagRA is not None),
                "paras": st.ParagraphsOS.Count,
            }
        return out
    finally:
        proj.CloseProject()


@pytest.fixture(scope="module")
def live():
    try:
        import flexicon  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is unavailable: %s" % exc)
    from harness import full_run
    from gramtrans.Lib import preview
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    try:
        fx = _author_shared_state()
        fx = _author_source_only_state(fx)

        def sel(_full):
            return Selection(categories={GC.STEMS: True, GC.TEXTS: True},
                             text_picks=frozenset(fx["texts"].values()))

        def run():
            _write_guard(TARGET_NAME)
            pre_bytes = Path(TARGET_PATH).read_bytes()
            plan, _ = full_run.run_full_transfer(
                SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
                selection_transform=sel, preview_only=True)
            preview_wrote = Path(TARGET_PATH).read_bytes() != pre_bytes
            _plan2, report = full_run.run_full_transfer(
                SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
                selection_transform=sel)
            return {"plan": plan, "lines": preview.render_reversal_and_text_decisions(plan),
                    "extra": preview.render_preview_extra_lines(plan),
                    "preview_wrote": preview_wrote, "report": report,
                    "post": _sandbox_state()}

        res = {"fx": fx, "pre": _sandbox_state()}
        res["r1"] = run()
        res["r2"] = run()
        import gramtrans
        import flexicon
        print("[LIVE] gramtrans=%s flexicon=%s" % (gramtrans.__file__, flexicon.__file__))
        print("[LIVE] source=%s target=%s fixture=%s" % (SOURCE_NAME, TARGET_NAME, fx))
        for key in ("r1", "r2"):
            print("[LIVE] %s Preview lines:\n%s" % (key, "\n".join(res[key]["lines"])))
            print("[LIVE] %s post=%s" % (key, res[key]["post"]))
        yield res
    finally:
        for name in (TARGET_NAME, SOURCE_NAME):
            try:
                _restore(name)
            except Exception as exc:  # noqa: BLE001
                print("[WARN] restore of %s failed: %s" % (name, exc))


def _rows(lines, section):
    """The `    <Label>  '<name>' {<guid>}  (...)` rows under one header."""
    out, inside = [], False
    for ln in lines:
        if not ln.startswith("    "):
            inside = ln.strip().startswith(section)
            continue
        if inside and ln.lstrip()[:1] not in ("(", "+"):
            label, rest = ln.strip().split("  ", 1)
            out.append((label, rest[rest.index("{") + 1:rest.index("}")]))
    return sorted(out)


def test_preview_wrote_nothing_and_target_started_without_fixture(live):
    fx, pre = live["fx"], live["pre"]
    assert not live["r1"]["preview_wrote"] and not live["r2"]["preview_wrote"]
    assert fx["new_pos"] not in pre["revpos"] and fx["shared_pos"] in pre["revpos"]
    assert pre["rev_entries"] == [] and pre["texts"] == {}
    assert fx["new_tag"] not in pre["tag_list"] and fx["shared_tag"] in pre["tag_list"]


def test_preview_lines_reach_the_extra_lines_seam(live):
    r1 = live["r1"]
    assert r1["lines"], "no #144 Preview lines rendered"
    assert all(ln in r1["extra"] for ln in r1["lines"])


def test_reversal_category_rows_match_move(live):
    fx, r1 = live["fx"], live["r1"]
    assert _rows(r1["lines"], "Reversal categories") == sorted(
        [("Create", fx["new_pos"]), ("Link", fx["shared_pos"])])
    post = r1["post"]
    assert fx["new_pos"] in post["revpos"]
    # Negative control: gt144revC had no category -> no row, still none after Move.
    assert post["rev_entries"] == [("gt144revA", fx["new_pos"]),
                                   ("gt144revB", fx["shared_pos"]),
                                   ("gt144revC", None)]


def test_text_tag_rows_match_move(live):
    fx, r1 = live["fx"], live["r1"]
    assert _rows(r1["lines"], "Text markup tags") == sorted(
        [("Create", fx["new_tag"]), ("Link", fx["shared_tag"])])
    post = r1["post"]
    assert fx["new_tag"] in post["tag_list"]
    assert post["texts"]["A"]["tags"] == sorted([fx["new_tag"], fx["shared_tag"]])
    # Negative control: B and C carry no tag and get none.
    assert post["texts"]["B"]["tags"] == [] and post["texts"]["C"]["tags"] == []


def test_text_genre_rows_agree_with_move(live):
    """Agreement, not presence: every genre row Preview shows is a genre Move
    attached, and vice versa (see the module docstring for why both sides are
    empty on today's flexicon)."""
    fx, r1 = live["fx"], live["r1"]
    rows = _rows(r1["lines"], "Text genres")
    attached = sorted({g for t in r1["post"]["texts"].values() for g in t["genres"]})
    assert sorted({g for _, g in rows}) == attached, (rows, attached)
    plan_genres = [d for tp in r1["plan"].text_plans for d in tp.genre_decisions]
    print("[LIVE] genre decisions in plan: %d (source texts carry %s)"
          % (len(plan_genres), fx["src_genres"]))
    assert r1["post"]["texts"]["C"]["genres"] == []


def test_rerun_is_idempotent_and_preview_says_so(live):
    fx, r1, r2 = live["fx"], live["r1"], live["r2"]
    assert r2["post"] == r1["post"]
    # Entry + senses already present -> nothing in the copy set -> no reversal
    # decision at all (no re-add), so no category rows.
    assert r2["plan"].reversal_decisions == ()
    assert _rows(r2["lines"], "Reversal categories") == []
    # The tag possibilities now exist -> Link; the texts are matched (UPDATE)
    # and already have paragraphs, so Move adds no tag -- the note says so.
    assert _rows(r2["lines"], "Text markup tags") == sorted(
        [("Link", fx["new_tag"]), ("Link", fx["shared_tag"])])
    assert any("already in the target: tags are added only if the target text "
               "has no paragraphs yet" in ln for ln in r2["lines"]), r2["lines"]
