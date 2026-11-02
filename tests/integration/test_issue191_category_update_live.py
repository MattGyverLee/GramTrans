"""Issue #191 live gate -- a wordform analysis whose part of speech exists in
BOTH projects but has DIVERGED (source Name/Abbreviation changed after the
fork) plans as a CategoryRA UPDATE. Move must apply the field update to the
target POS, not just link it.

Before the fix ``wordforms._apply_category`` treated UPDATE like LINK: the
analysis got its category but the target POS kept its stale Name.

WRITE PATH: the TARGET is the throwaway ``Target`` project, rebuilt from
``Target 2026-07-06 0218.fwbackup`` plus the shared authoring (a fork of the
source before the divergence). The SOURCE is the private throwaway
``GT-Src-191`` (also restored from the same backup). Nothing else is written.

Run (claim ``Target`` with the lockout skill first):
    set FLEXLIBS_REQUIRE_LIVE=1 && set PYTHONPATH=src && python -m pytest \
        tests/integration/test_issue191_category_update_live.py -v -s
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_live_project]

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "GT-Src-191"
TARGET_NAME = "Target"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

OLD_NAME = "GT191 old pos"
NEW_NAME = "GT191 new pos"
NEW_ABBR = "GT191new"
WORD = "gt191alpha"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))


def _guard(name):
    assert name in (SOURCE_NAME, TARGET_NAME), name
    assert name not in ("Esperanto",), name


def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            return d / BACKUP_NAME
    pytest.fail("[FAIL] backup %r not found under %s" % (BACKUP_NAME, _BACKUP_DIRS))


def _open(name, write=False):
    _guard(name)
    assert not write or name == SOURCE_NAME, name  # Target is only ever written by Move
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


def _set_name(proj, obj, name, abbr):
    from SIL.LCModel.Core.Text import TsStringUtils
    ws = proj.Cache.DefaultAnalWs
    obj.Name.set_String(ws, TsStringUtils.MakeString(name, ws))
    obj.Abbreviation.set_String(ws, TsStringUtils.MakeString(abbr, ws))


def _pos_text(proj, pos):
    ws = proj.Cache.DefaultAnalWs
    return (pos.Name.get_String(ws).Text, pos.Abbreviation.get_String(ws).Text)


def _author_shared() -> str:
    from SIL.LCModel import ILangProject, IPartOfSpeechFactory
    proj = _open(SOURCE_NAME, write=True)
    try:
        lp = ILangProject(proj.Cache.LangProject)
        pos = proj.Cache.ServiceLocator.GetService(IPartOfSpeechFactory).Create()
        lp.PartsOfSpeechOA.PossibilitiesOS.Add(pos)
        _set_name(proj, pos, OLD_NAME, "GT191old")
        return _g(pos)
    finally:
        proj.CloseProject()


def _fork_target():
    _guard(TARGET_NAME)
    tdir = PROJECTS_ROOT / TARGET_NAME
    if tdir.exists():
        shutil.rmtree(tdir)
    shutil.copytree(PROJECTS_ROOT / SOURCE_NAME, tdir,
                    ignore=shutil.ignore_patterns("*.lock"))
    (tdir / ("%s.fwdata" % SOURCE_NAME)).rename(tdir / ("%s.fwdata" % TARGET_NAME))


def _author_source_only(pos_guid) -> dict:
    """Diverge the source POS, add a text with one approved analysis on it."""
    from SIL.LCModel import ILangProject, IPartOfSpeech
    proj = _open(SOURCE_NAME, write=True)
    try:
        lp = ILangProject(proj.Cache.LangProject)
        pos = next(x for x in lp.PartsOfSpeechOA.PossibilitiesOS if _g(x) == pos_guid)
        _set_name(proj, pos, NEW_NAME, NEW_ABBR)
        text = proj.Texts.Create("GT191 text")
        sentence = WORD + "."
        para = proj.Paragraphs.Create(text, sentence)
        segs = list(proj.Paragraphs.GetSegments(para))
        if not segs:
            proj.Segments.AppendSentence(para, sentence)
            segs = list(proj.Paragraphs.GetSegments(para))
        wf = proj.Wordforms.Create(WORD)
        a = proj.WfiAnalyses.Create(wf)
        proj.WfiAnalyses.SetCategory(a, IPartOfSpeech(pos))
        proj.WfiAnalyses.ApproveAnalysis(a)
        proj.Segments.AppendAnalysis(segs[0], a)
        return dict(pos=pos_guid, text=_g(text), analysis=_g(a))
    finally:
        proj.CloseProject()


def _target_state(fx) -> dict:
    from SIL.LCModel import ILangProject
    proj = _open(TARGET_NAME)
    try:
        lp = ILangProject(proj.Cache.LangProject)
        pos = next(x for x in lp.PartsOfSpeechOA.PossibilitiesOS if _g(x) == fx["pos"])
        rows = []
        for w in proj.Wordforms.GetAll():
            if str(proj.Wordforms.GetForm(w)) != WORD:
                continue
            for a in proj.WfiAnalyses.GetAll(w):
                cat = proj.WfiAnalyses.GetCategory(a)
                rows.append((_g(a), _g(cat) if cat is not None else None))
        return dict(pos_text=_pos_text(proj, pos), analyses=rows,
                    pos_count=sum(1 for x in lp.PartsOfSpeechOA.PossibilitiesOS
                                  if _g(x) == fx["pos"]))
    finally:
        proj.CloseProject()


def _head_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(_REPO), "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "?"


@pytest.fixture(scope="module")
def live():
    try:
        import flexicon
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is unavailable: %s" % exc)
    import gramtrans
    assert str(_REPO).lower() in gramtrans.__file__.lower(), (
        "[FAIL] gramtrans resolved to %s, not %s -- set PYTHONPATH=src"
        % (gramtrans.__file__, _REPO))
    from harness import full_run
    from harness.restore import restore_target
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    def run(fx, preview_only):
        def sel(_full):
            return Selection(categories={GC.TEXTS: True},
                             text_picks=frozenset([fx["text"]]),
                             include_closure=True)
        return full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
            selection_transform=sel, preview_only=preview_only)

    restore_target(SOURCE_NAME, backup_path=_backup_path())
    pos_guid = _author_shared()
    _fork_target()
    fx = _author_source_only(pos_guid)
    res = {"fx": fx, "pre": _target_state(fx)}
    pre_bytes = Path(TARGET_PATH).read_bytes()
    res["preview"], _ = run(fx, True)
    res["preview_wrote"] = Path(TARGET_PATH).read_bytes() != pre_bytes
    res["move_plan"], res["move_report"] = run(fx, False)
    res["post"] = _target_state(fx)
    print("[LIVE] sha=%s gramtrans=%s flexicon=%s"
          % (_head_sha(), gramtrans.__file__, flexicon.__file__))
    print("[LIVE] fixture=%s" % fx)
    print("[LIVE] pre=%s" % res["pre"])
    print("[LIVE] post=%s" % res["post"])
    return res


def test_pre_state(live):
    assert live["pre"]["pos_text"] == (OLD_NAME, "GT191old")
    assert live["pre"]["analyses"] == []
    assert not live["preview_wrote"], "[FAIL] Preview wrote to the target"


def test_category_link_lands(live):
    fx, post = live["fx"], live["post"]
    assert post["analyses"] == [(fx["analysis"], fx["pos"])], post["analyses"]
    assert post["pos_count"] == 1


def test_update_applied_to_target_pos(live):
    """The #191 claim: the diverged POS field update was written, not only linked."""
    assert live["post"]["pos_text"] == (NEW_NAME, NEW_ABBR), (
        "[FAIL] UPDATE not applied: %r" % (live["post"]["pos_text"],))
