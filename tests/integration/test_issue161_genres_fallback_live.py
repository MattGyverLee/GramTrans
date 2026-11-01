"""Issue #161 live gate -- the pre-flexicon-4.9.0 genre FALLBACK path.

`texts._source_genres` prefers flexicon `Texts.GetGenres` (first shipped in
4.9.0). The pyproject floor is 4.8.0, where the fallback (`text.GenresRC`, then
`IText(text).GenresRC`) is the only path. This module removes `GetGenres` for
the duration of a REAL transfer and checks the target text's `GenresRC` GUIDs
re-read from the LCM equal the source's. It records which fallback branch ran.

WRITE PATH: writes ONLY the throwaway projects below, rebuilt from
``Target 2026-07-06 0218.fwbackup``:

* ``GT-Src-161``     -- SOURCE (write-enabled only while authoring)
* ``GT-Sandbox-161`` -- TARGET

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue161_genres_fallback_live.py -v -s
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

SOURCE_NAME = "GT-Src-161"
TARGET_NAME = "GT-Sandbox-161"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))


def _write_guard(name):
    assert name in (SOURCE_NAME, TARGET_NAME), name


def _restore(name):
    _write_guard(name)
    from harness.restore import restore_target
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            restore_target(name, backup_path=d / BACKUP_NAME)
            return
    pytest.fail("[FAIL] backup %r not found under %s" % (BACKUP_NAME, _BACKUP_DIRS))


def _open(name, write=False):
    assert not write or name == SOURCE_NAME, name
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


def _author_source() -> dict:
    """Source text A with TWO genres (so the fallback must return every genre,
    not just the first); text C with none (negative control)."""
    from SIL.LCModel import ICmPossibility, IText
    _restore(SOURCE_NAME)
    _restore(TARGET_NAME)
    proj = _open(SOURCE_NAME, write=True)
    try:
        lp = proj.Cache.LangProject
        from SIL.LCModel import ILangProject
        glist = ILangProject(lp).GenreListOA.PossibilitiesOS
        genres = [ICmPossibility(glist[0]), ICmPossibility(glist[1])]
        out = {}
        for key, gs in (("A", genres), ("C", [])):
            t = proj.Texts.Create("GT161 text %s" % key)
            for g in gs:
                IText(t).GenresRC.Add(g)
            proj.Paragraphs.Create(t, "gt one. gt two.")
            out[key] = _g(t)
        return {"texts": out, "src_genres": {"A": sorted(_g(g) for g in genres), "C": []}}
    finally:
        proj.CloseProject()


def _genres_of(name, text_guids) -> dict:
    from SIL.LCModel import IText
    proj = _open(name)
    try:
        res = {}
        for t in proj.Texts.GetAll():
            nm = str(proj.Texts.GetName(t))
            if nm.startswith("GT161 text "):
                res[nm[-1]] = sorted(_g(x) for x in IText(t).GenresRC)
        return res
    finally:
        proj.CloseProject()


@pytest.fixture(scope="module")
def live(monkeypatch_module):
    try:
        import flexicon  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is unavailable: %s" % exc)
    from flexicon.code.TextsWords.TextOperations import TextOperations
    from gramtrans.Lib import texts
    from gramtrans.Lib.models import GrammarCategory as GC, Selection
    from harness import full_run

    try:
        fx = _author_source()
        pre = _genres_of(TARGET_NAME, fx["texts"])
        branches = []
        real = texts._source_genres

        def spy(source, source_text):
            has_ops = callable(getattr(getattr(source, "Texts", None), "GetGenres", None))
            raw = getattr(source_text, "GenresRC", None) is not None
            branches.append("GetGenres" if has_ops else
                            "uncast GenresRC" if raw else "IText cast")
            return real(source, source_text)

        monkeypatch_module.delattr(TextOperations, "GetGenres")
        monkeypatch_module.setattr(texts, "_source_genres", spy)

        def sel(_full):
            return Selection(categories={GC.TEXTS: True},
                             text_picks=frozenset(fx["texts"].values()))

        _write_guard(TARGET_NAME)
        plan, report = full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
            selection_transform=sel)
        post = _genres_of(TARGET_NAME, fx["texts"])
        res = {"fx": fx, "pre": pre, "post": post, "branches": branches,
               "plan": plan, "report": report}
        print("[LIVE] fallback branches run: %s" % sorted(set(branches)))
        print("[LIVE] source genres=%s" % fx["src_genres"])
        print("[LIVE] target pre=%s post=%s" % (pre, post))
        yield res
    finally:
        for name in (TARGET_NAME, SOURCE_NAME):
            try:
                _restore(name)
            except Exception as exc:  # noqa: BLE001
                print("[WARN] restore of %s failed: %s" % (name, exc))


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def test_target_started_without_the_texts(live):
    assert live["pre"] == {}


def test_getgenres_was_absent_and_a_fallback_branch_ran(live):
    assert live["branches"], "_source_genres never ran"
    assert "GetGenres" not in live["branches"]
    assert set(live["branches"]) <= {"uncast GenresRC", "IText cast"}


def test_target_genre_guids_equal_source(live):
    src = live["fx"]["src_genres"]
    assert len(src["A"]) == 2
    assert live["post"]["A"] == src["A"]
    assert live["post"]["C"] == []
