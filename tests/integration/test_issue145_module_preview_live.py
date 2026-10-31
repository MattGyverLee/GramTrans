"""Issue #145 live gate -- the FlexTools-module Preview paths in `gramtrans.py`
show the `render_preview_extra_lines` output against a REAL project pair.

Drives the actual module entry points, preview-only (``modifyAllowed=False``):

* ``phase2_interactive_move(..., categories={STEMS})`` -- the primary proof;
* ``_headless_phase0`` -- first exactly as shipped (its hard-coded POS /
  AFFIX_TEMPLATES / SLOTS selection, which has no sense-list references), then
  with ``gramtrans.Selection`` swapped for a STEMS selection so the same code
  path is fed a plan that carries #116 appendix / thesaurus decisions.

WRITE PATH: writes ONLY the two private throwaway projects below, both rebuilt
from ``Target 2026-07-06 0218.fwbackup``:

* ``GT-Src-145``     -- SOURCE (write-enabled only while authoring)
* ``GT-Sandbox-145`` -- TARGET (a fork of the source after the shared appendix);
  opened READ-ONLY here -- the module runs are preview-only.

Never Target, Esperanto, Ejagham*, Mbugwe*, Ngoreme*, or another agent's pair.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue145_module_preview_live.py -v -s
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "GT-Src-145"
TARGET_NAME = "GT-Sandbox-145"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))

AP_PRESENT_TEXT = "Appendix 145-PRESENT: shared, linked by GUID"
AP_ABSENT_TEXT = "Appendix 145-ABSENT: source only, must drop"
SECTION = "Sense appendix / thesaurus references:"


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
    assert not write or name == SOURCE_NAME, name  # write guard: only the source is authored
    assert name in (SOURCE_NAME, TARGET_NAME), name
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


def _author() -> dict:
    """Shared appendix -> fork target -> source-only appendix + entry whose
    sense references both appendixes and an existing thesaurus item."""
    _restore(SOURCE_NAME)
    proj = _open(SOURCE_NAME, write=True)
    try:
        present = _make_appendix(proj, AP_PRESENT_TEXT)
    finally:
        proj.CloseProject()
    tdir = PROJECTS_ROOT / TARGET_NAME
    assert tdir.name == TARGET_NAME  # write guard
    if tdir.exists():
        shutil.rmtree(tdir)
    shutil.copytree(PROJECTS_ROOT / SOURCE_NAME, tdir,
                    ignore=shutil.ignore_patterns("*.lock"))
    (tdir / ("%s.fwdata" % SOURCE_NAME)).rename(tdir / ("%s.fwdata" % TARGET_NAME))

    from SIL.LCModel import (ILangProject, ILexDb, ICmPossibilityList, ICmPossibility,
                             ILexSense)
    proj = _open(SOURCE_NAME, write=True)
    try:
        lexdb = ILexDb(ILangProject(proj.Cache.LangProject).LexDbOA)
        absent = _make_appendix(proj, AP_ABSENT_TEXT)
        aps = {_g(a): a for a in lexdb.AppendixesOC}
        e_old = ICmPossibility(ICmPossibilityList(lexdb.DomainTypesOA).PossibilitiesOS[0])
        entry = proj.LexEntry.Create("gtfixonefortyfive", create_blank_sense=False)
        sense = ILexSense(proj.Senses.Create(entry, "gt145 sense"))
        sense.AppendixesRC.Add(aps[present])
        sense.AppendixesRC.Add(aps[absent])
        sense.ThesaurusItemsRC.Add(e_old)
        return dict(present=present, absent=absent, E=_g(e_old),
                    entry=_g(entry), sense=_g(sense))
    finally:
        proj.CloseProject()


class _Report:
    def __init__(self):
        self.lines = []

    def Info(self, msg):  # noqa: N802
        self.lines.append(msg)

    def Warning(self, msg):  # noqa: N802
        self.lines.append("[WARNING] " + msg)

    def Error(self, msg):  # noqa: N802
        self.lines.append("[ERROR] " + msg)

    def Blank(self):  # noqa: N802
        self.lines.append("")

    @property
    def text(self):
        return "\n".join(self.lines)


class _NoWSChange:
    def resolve(self, mismatches):
        return ()


class _CancelConflicts:
    """Preview-only: the extra lines are reported before this step, so a
    cancel here ends the run with nothing written and no PyQt dialog."""
    invoked = 0

    def resolve(self, prompts):
        from gramtrans.Lib.conflict import UserCancelled
        _CancelConflicts.invoked = len(prompts)
        raise UserCancelled("issue #145 live gate: preview only")


def _with_target(fn):
    target = _open(TARGET_NAME)  # READ-ONLY
    try:
        assert target.ProjectName() == TARGET_NAME  # write guard
        return fn(target)
    finally:
        target.CloseProject()


@pytest.fixture(scope="module")
def live():
    try:
        import flexicon  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is unavailable: %s" % exc)
    import gramtrans
    from gramtrans import gramtrans as gt
    # gramtrans.py imports `models` FLAT (site.addsitedir(Lib)); its
    # GrammarCategory is a different enum class from gramtrans.Lib.models',
    # so a package-enum key never matches the module's planner dispatch.
    GC = gt.GrammarCategory

    mp = pytest.MonkeyPatch()
    try:
        fx = _author()
        pre_bytes = Path(TARGET_PATH).read_bytes()
        res = {"fx": fx}

        rep = _Report()
        _with_target(lambda t: gt.phase2_interactive_move(
            t, rep, False, source_project_name=SOURCE_NAME,
            categories={GC.STEMS: True},
            ws_resolver=_NoWSChange(), conflict_resolver=_CancelConflicts()))
        res["phase2"] = rep.text

        mp.setattr(gt, "DEFAULT_SOURCE_PROJECT", SOURCE_NAME)
        rep = _Report()
        _with_target(lambda t: gt._headless_phase0(t, rep, False))
        res["headless_shipped"] = rep.text

        real_selection = gt.Selection
        mp.setattr(gt, "Selection", lambda **kw: real_selection(
            categories={GC.STEMS: True}, include_closure=True))
        rep = _Report()
        _with_target(lambda t: gt._headless_phase0(t, rep, False))
        res["headless_stems"] = rep.text

        res["target_unchanged"] = Path(TARGET_PATH).read_bytes() == pre_bytes
        print("[LIVE] gramtrans=%s flexicon=%s" % (gramtrans.__file__, flexicon.__file__))
        print("[LIVE] source=%s target=%s fixture=%s" % (SOURCE_NAME, TARGET_NAME, fx))
        print("[LIVE] conflict prompts at cancel=%s" % _CancelConflicts.invoked)
        for key in ("phase2", "headless_shipped", "headless_stems"):
            print("[LIVE] ===== %s report =====" % key)
            print(res[key])
        yield res
    finally:
        mp.undo()
        for name in (TARGET_NAME, SOURCE_NAME):
            try:
                _restore(name)
            except Exception as exc:  # noqa: BLE001
                print("[WARN] restore of %s failed: %s" % (name, exc))


def _assert_extra_lines(text, fx):
    assert SECTION in text, text
    assert "Link  AppendixesRC '" in text and "{%s}" % fx["present"] in text, text
    assert "Not transferred  AppendixesRC" in text and "{%s}" % fx["absent"] in text, text
    assert "{%s}" % fx["E"] in text, text


def test_preview_wrote_nothing(live):
    assert live["target_unchanged"]
    for key in ("phase2", "headless_shipped", "headless_stems"):
        assert "[ERROR]" not in live[key], live[key]


def test_phase2_module_preview_shows_extra_lines(live):
    text = live["phase2"]
    _assert_extra_lines(text, live["fx"])
    assert "[Phase 2] [Preview]   " + SECTION in text
    # Shown before the conflict step / any Move.
    marker = next(m for m in ("conflict prompt(s) collected", "No conflicts in plan")
                  if m in text)
    assert text.index(SECTION) < text.index(marker)


def test_headless_module_preview_shows_extra_lines(live):
    text = live["headless_stems"]
    _assert_extra_lines(text, live["fx"])
    assert text.index(SECTION) < text.index("(Preview-only run: no writes performed.)")


def test_headless_shipped_selection_runs_clean(live):
    # The shipped POS/AFFIX_TEMPLATES/SLOTS selection has no sense-list refs;
    # it must still run the preview to completion through the new call.
    text = live["headless_shipped"]
    assert "(Preview-only run: no writes performed.)" in text
    # The Target backup's configuration views still reach this path's report.
    assert "Configuration views:" in text, text
