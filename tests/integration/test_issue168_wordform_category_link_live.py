"""Issue #168 live gate -- a wordform analysis whose part of speech exists in
BOTH projects (a legitimate CategoryRA LINK) really gets that category after a
Move, and a morph bundle's allomorph (MorphRA) link lands too.

Before the fix ``wordforms._apply_category`` handed flexicon's
``WfiAnalyses.SetCategory`` the resolver's ``ICmPossibility`` proxy (a
``PartsOfSpeechOA.PossibilitiesOS`` element). flexicon guards with
``isinstance(category, IPartOfSpeech)`` -- False for that proxy -- and raised
``FP_ParameterError``, which ``texts._safe`` swallowed: CategoryRA stayed None
with nothing reported. Sibling (pattern audit): ``apply_morph_bundles`` wired
MorphRA through ``WfiMorphBundles.SetMorphType``, which flexicon retired (it
always raises), so no bundle ever got its allomorph link either.

Negative control: analyses on a POS ABSENT from the target must still end with
CategoryRA None (a POS is never fabricated) and the POS must not be created.

WRITE PATH: writes ONLY the two private throwaway projects below, both rebuilt
from ``Target 2026-07-06 0218.fwbackup``:

* ``GT-Src-168``     -- SOURCE (write-enabled only while authoring)
* ``GT-Sandbox-168`` -- TARGET (a fork of the source before source-only authoring)

Never Target, Esperanto, Ejagham*, Mbugwe*, Ngoreme*, or another agent's
GT-Src-NNN / GT-Sandbox-NNN.

Run (PYTHONPATH pins this checkout's ``src`` ahead of the editable install):
    set FLEXLIBS_REQUIRE_LIVE=1 && set PYTHONPATH=src && python -m pytest \
        tests/integration/test_issue168_wordform_category_link_live.py -v -s
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "GT-Src-168"
TARGET_NAME = "GT-Sandbox-168"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

SHARED_POS = "GT168 shared pos"
ABSENT_POS = "GT168 absent pos"
ENTRY_FORM = "gtonesixtyeightstem"
# (wordform, POS key, carries a morph bundle?)
WORDS = (
    ("gt168alpha", "absent", False),
    ("gt168beta", "absent", False),
    ("gt168delta", "shared", True),
)
SET_FAILED_REASON = "category set failed in target"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))

# Module-level write guard: these two throwaway projects and nothing else.
assert SOURCE_NAME == "GT-Src-168" and TARGET_NAME == "GT-Sandbox-168"


def _guard(name):
    assert name in (SOURCE_NAME, TARGET_NAME), name
    assert TARGET_NAME == "GT-Sandbox-168" and SOURCE_NAME == "GT-Src-168"


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
    _guard(name)
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


def _set_name(proj, obj, text):
    from SIL.LCModel.Core.Text import TsStringUtils
    ws = proj.Cache.DefaultAnalWs
    obj.Name.set_String(ws, TsStringUtils.MakeString(text, ws))
    obj.Abbreviation.set_String(ws, TsStringUtils.MakeString(text[:12], ws))


def _add_pos(proj, text):
    from SIL.LCModel import ILangProject, IPartOfSpeechFactory
    lp = ILangProject(proj.Cache.LangProject)
    pos = proj.Cache.ServiceLocator.GetService(IPartOfSpeechFactory).Create()
    lp.PartsOfSpeechOA.PossibilitiesOS.Add(pos)
    _set_name(proj, pos, text)
    return pos


def _author_shared() -> dict:
    """Authored BEFORE the fork, so the target holds these by GUID: the shared
    POS and a stem entry (allomorph + sense) a morph bundle will reference."""
    from SIL.LCModel import ILexEntry
    proj = _open(SOURCE_NAME, write=True)
    try:
        pos = _add_pos(proj, SHARED_POS)
        entry = proj.LexEntry.Create(ENTRY_FORM, "stem", create_blank_sense=False)
        sense = proj.LexEntry.AddSense(entry, "gt168 stem gloss")
        allo = ILexEntry(entry).LexemeFormOA
        return dict(shared=_g(pos), entry=_g(entry), sense=_g(sense),
                    allomorph=_g(allo))
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


def _author_source_only(fx) -> dict:
    """Source-only: an ABSENT POS, one text, three approved analyses on three
    wordforms (two on the absent POS, one on the shared POS), and one morph
    bundle on the shared-POS analysis wired to the shared stem's allomorph +
    sense."""
    from SIL.LCModel import ILangProject, IPartOfSpeech
    proj = _open(SOURCE_NAME, write=True)
    try:
        absent = _add_pos(proj, ABSENT_POS)
        lp = ILangProject(proj.Cache.LangProject)
        shared = next(x for x in lp.PartsOfSpeechOA.PossibilitiesOS
                      if _g(x) == fx["shared"])
        cats = {"absent": absent, "shared": shared}
        text = proj.Texts.Create("GT168 text")
        sentence = " ".join(w for w, _, _ in WORDS) + "."
        para = proj.Paragraphs.Create(text, sentence)
        segs = list(proj.Paragraphs.GetSegments(para))
        if not segs:
            proj.Segments.AppendSentence(para, sentence)
            segs = list(proj.Paragraphs.GetSegments(para))
        seg = segs[0]
        allo = proj.Object(fx["allomorph"])
        sense = proj.Object(fx["sense"])
        analyses, bundles = {}, {}
        for form, key, with_bundle in WORDS:
            wf = proj.Wordforms.Create(form)
            a = proj.WfiAnalyses.Create(wf)
            proj.WfiAnalyses.SetCategory(a, IPartOfSpeech(cats[key]))
            if with_bundle:
                b = proj.WfiMorphBundles.Create(a)
                proj.WfiMorphBundles.SetForm(b, ENTRY_FORM,
                                             proj.Cache.DefaultVernWs)
                proj.WfiMorphBundles.SetMorph(b, allo)
                proj.WfiMorphBundles.SetSense(b, sense)
                bundles[form] = _g(b)
            proj.WfiAnalyses.ApproveAnalysis(a)
            proj.Segments.AppendAnalysis(seg, a)
            analyses[form] = _g(a)
        out = dict(fx)
        out.update(absent=_g(absent), text=_g(text), analyses=analyses,
                   bundles=bundles)
        return out
    finally:
        proj.CloseProject()


def _target_state(fx) -> dict:
    from SIL.LCModel import ILangProject, IWfiMorphBundle
    proj = _open(TARGET_NAME)
    try:
        lp = ILangProject(proj.Cache.LangProject)
        out = {"pos": sorted(_g(x) for x in lp.PartsOfSpeechOA.PossibilitiesOS),
               "an": {}, "bundles": {}}
        for form, _, _ in WORDS:
            rows = []
            for w in proj.Wordforms.GetAll():
                if str(proj.Wordforms.GetForm(w)) != form:
                    continue
                for a in proj.WfiAnalyses.GetAll(w):
                    cat = proj.WfiAnalyses.GetCategory(a)
                    rows.append((_g(a), _g(cat) if cat is not None else None))
                    for b in proj.WfiMorphBundles.GetAll(a):
                        b = IWfiMorphBundle(b)
                        out["bundles"][_g(b)] = (
                            _g(b.MorphRA) if b.MorphRA is not None else None,
                            _g(b.SenseRA) if b.SenseRA is not None else None)
            out["an"][form] = rows
        return out
    finally:
        proj.CloseProject()


def _cat_drops(items):
    return [d for d in (items or ())
            if d.owner_kind == "WfiAnalysis" and d.field_name == "CategoryRA"]


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
    # The run must exercise THIS checkout, not the editable install.
    assert str(_REPO).lower() in gramtrans.__file__.lower(), (
        "[FAIL] gramtrans resolved to %s, not %s -- set PYTHONPATH=src"
        % (gramtrans.__file__, _REPO))
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    def run(fx, preview_only):
        _guard(SOURCE_NAME)
        _guard(TARGET_NAME)

        def sel(_full):
            return Selection(categories={GC.TEXTS: True},
                             text_picks=frozenset([fx["text"]]),
                             include_closure=True)
        return full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
            selection_transform=sel, preview_only=preview_only)

    _restore(SOURCE_NAME)
    fx = _author_shared()
    _fork_target()
    fx = _author_source_only(fx)
    res = {"fx": fx, "pre": _target_state(fx)}
    pre_bytes = Path(TARGET_PATH).read_bytes()
    res["preview"], _ = run(fx, True)
    res["preview_wrote"] = Path(TARGET_PATH).read_bytes() != pre_bytes
    res["move_plan"], res["move_report"] = run(fx, False)
    res["post"] = _target_state(fx)
    print("[LIVE] sha=%s gramtrans=%s flexicon=%s"
          % (_head_sha(), gramtrans.__file__, flexicon.__file__))
    print("[LIVE] source=%s target=%s fixture=%s" % (SOURCE_NAME, TARGET_NAME, fx))
    print("[LIVE] pre=%s" % res["pre"])
    print("[LIVE] preview CategoryRA drops=%s" % sorted(
        d.owner_guid for d in _cat_drops(res["preview"].dropped_items)))
    report_drops = getattr(res["move_report"], "dropped_items", ()) or ()
    print("[LIVE] move report CategoryRA drops=%s" % [
        (d.owner_guid, d.reason) for d in _cat_drops(report_drops)])
    print("[LIVE] post=%s" % res["post"])
    return res


def test_pre_state(live):
    fx, pre = live["fx"], live["pre"]
    assert fx["shared"] in pre["pos"]
    assert fx["absent"] not in pre["pos"]
    assert all(rows == [] for rows in pre["an"].values()), pre["an"]
    assert not live["preview_wrote"], "[FAIL] Preview wrote to the target"


def test_shared_pos_category_link_lands(live):
    """The #168 claim: the analysis on the shared POS LINKs to it."""
    fx, post = live["fx"], live["post"]
    rows = post["an"]["gt168delta"]
    assert rows == [(fx["analyses"]["gt168delta"], fx["shared"])], (
        "[FAIL] shared-POS analysis category did not land: %r" % (rows,))


def test_absent_pos_negative_control(live):
    """A POS absent from the target is never fabricated; the analyses that use
    it are created with CategoryRA unset, and Preview reports each one."""
    fx, post = live["fx"], live["post"]
    assert fx["absent"] not in post["pos"]
    for form in ("gt168alpha", "gt168beta"):
        assert post["an"][form] == [(fx["analyses"][form], None)], post["an"][form]
    planned = sorted(d.owner_guid for d in _cat_drops(live["preview"].dropped_items))
    assert planned == sorted(fx["analyses"][f] for f in ("gt168alpha", "gt168beta"))


def test_no_category_set_failure_reported(live):
    report_drops = getattr(live["move_report"], "dropped_items", ()) or ()
    failed = [d for d in report_drops if d.reason == SET_FAILED_REASON]
    assert failed == [], failed


def test_morph_bundle_allomorph_and_sense_links_land(live):
    """Pattern-audit sibling: MorphRA (was wired via the retired SetMorphType)
    and SenseRA both land on the shared stem."""
    fx, post = live["fx"], live["post"]
    bguid = fx["bundles"]["gt168delta"]
    assert post["bundles"].get(bguid) == (fx["allomorph"], fx["sense"]), (
        "[FAIL] bundle links: %r" % (post["bundles"].get(bguid),))
