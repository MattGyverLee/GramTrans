"""Issue #49 live gate -- the default category set reports what it wrote.

WRITE PATH: writes ONLY the throwaway project ``Target`` (restored headlessly
from a known backup before and after), or the throwaway named by
``GT_LIVE_TARGET`` when set (a parallel worktree's own copy, e.g. "GT084 Target").  The source ``Ngoreme FLEx`` is opened
READ-ONLY.  Skips unless FLEXLIBS_REQUIRE_LIVE=1.

Asserts: the target .fwdata changes; template/slot/POS added counts equal the
objects found in Target by GUID; every reported added is a verified-present
object; the four lexicon categories (no planner of their own since the legacy
verb-vertical path was retired) are dispatched as AFFIXES + STEMS, so entries,
senses, MSAs and allomorphs actually land (issue #84).
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "Ngoreme FLEx"   # READ-ONLY
# The ONLY project this module writes (a throwaway, restored before/after).
TARGET_NAME = os.environ.get("GT_LIVE_TARGET", "Target")
TARGET_DIR = Path("C:/ProgramData/SIL/FieldWorks/Projects") / TARGET_NAME
TARGET_PATH = str(TARGET_DIR / (TARGET_NAME + ".fwdata"))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))

sys.path.insert(0, str(Path(__file__).parent))


def _restore():
    from harness.restore import restore_target
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            restore_target(TARGET_NAME, backup_path=d / BACKUP_NAME)
            return
    pytest.fail("[FAIL] backup %r not found" % BACKUP_NAME)


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _guids_by_class(project_name, classes):
    """{class_name: set(guid)} over every object of `classes` (read-only open)."""
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    from SIL.LCModel import ICmObjectRepository
    proj = FLExProject()
    proj.OpenProject(projectName=project_name, writeEnabled=False)
    try:
        repo = proj.ObjectRepository(ICmObjectRepository)
        out = {c: set() for c in classes}
        for obj in repo.AllInstances():
            cn = obj.ClassName
            if cn in out:
                out[cn].add(str(obj.Guid).lower())
        return out
    finally:
        proj.CloseProject()


def _source_pos_guids():
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    from SIL.LCModel import ICmObject
    proj = FLExProject()
    proj.OpenProject(projectName=SOURCE_NAME, writeEnabled=False)
    try:
        return [str(ICmObject(p.concrete if hasattr(p, "concrete") else p).Guid).lower()
                for p in proj.POS.GetAll(recursive=True)]
    finally:
        proj.CloseProject()


@pytest.fixture(autouse=True)
def _restore_around():
    _restore()
    yield
    _restore()


def test_default_set_added_counts_match_target_state():
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    cats = {c: True for c in (GC.POS, GC.AFFIX_TEMPLATES, GC.SLOTS, GC.ENTRY, GC.SENSE,
                              GC.MSA, GC.ALLOMORPH, GC.PH_ENVIRONMENT)}
    picks = frozenset(_source_pos_guids())
    assert picks, "[SETUP] source has no POS"
    classes = ("MoInflAffixTemplate", "MoInflAffixSlot", "PartOfSpeech",
               "LexEntry", "LexSense", "MoStemMsa", "MoStemAllomorph",
               "PhEnvironment", "MoInflAffMsa", "MoAffixAllomorph")
    before_hash = _sha(TARGET_PATH)
    before = _guids_by_class(TARGET_NAME, classes)

    def _sel(_full):
        return Selection(categories=cats, include_closure=True, pos_picks=picks,
                         enable_overwrite=True, interactive_merge=True)

    plan, report = full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, selection_transform=_sel)
    after_hash = _sha(TARGET_PATH)
    after = _guids_by_class(TARGET_NAME, classes)

    print("[LIVE] sha256 before=%s after=%s" % (before_hash, after_hash))
    cls_of = {GC.AFFIX_TEMPLATES: "MoInflAffixTemplate", GC.SLOTS: "MoInflAffixSlot",
              GC.POS: "PartOfSpeech", GC.ENTRY: "LexEntry", GC.SENSE: "LexSense",
              GC.MSA: "MoStemMsa", GC.ALLOMORPH: "MoStemAllomorph",
              GC.PH_ENVIRONMENT: "PhEnvironment"}
    for cat, cn in cls_of.items():
        rep = report.per_category.get(cat)
        print("[LIVE] %-16s reported added=%s  target new=%d  (before=%d after=%d)"
              % (cat.value, getattr(rep, "added", None),
                 len(after[cn] - before[cn]), len(before[cn]), len(after[cn])))
    print("[LIVE] leaf_failed=%s failures=%s" % (
        report.leaf_failed,
        [(f.category.value, f.exception_type) for f in report.leaf_execution_failures][:10]))

    assert after_hash != before_hash, "target .fwdata unchanged"

    # Every reported added is a verified-present object (by GUID).
    added_guids = {}
    failed = {(f.category, f.source_guid) for f in report.leaf_execution_failures}
    skipped = {(s.category, s.source_guid) for s in report.skips}
    for a in plan.actions:
        key = (a.category, a.source_guid)
        if a.category in cls_of and key not in failed and key not in skipped:
            added_guids.setdefault(a.category, set()).add(a.source_guid.lower())
    for cat, guids in added_guids.items():
        missing = guids - after[cls_of[cat]]
        assert not missing, "%s reported added but absent from Target: %s" % (cat, sorted(missing)[:3])

    # Template / slot / POS counts match exactly what landed in the target.
    for cat in (GC.AFFIX_TEMPLATES, GC.SLOTS, GC.POS):
        cn = cls_of[cat]
        landed = len(after[cn] - before[cn])
        rep = report.per_category.get(cat)
        assert rep is not None
        assert rep.added == landed, "%s: reported added=%s but %d landed" % (
            cat.value, rep.added, landed)
    assert len(after["MoInflAffixTemplate"] - before["MoInflAffixTemplate"]) > 0, (
        "no templates transferred")

    # Issue #84: the lexicon categories are dispatched as AFFIXES + STEMS,
    # visibly (an [INFO] note), and their objects actually land.
    assert not any("not dispatched" in s.detail for s in report.skips)
    assert any("affixes + stems" in n for n in report.category_notes)
    assert plan.selection.is_on(GC.AFFIXES) and plan.selection.is_on(GC.STEMS)
    for cn in ("LexEntry", "LexSense", "MoStemMsa", "MoStemAllomorph",
               "MoInflAffMsa", "MoAffixAllomorph"):
        print("[LIVE] %-16s target new=%d" % (cn, len(after[cn] - before[cn])))
    for cn in ("LexEntry", "LexSense", "MoStemAllomorph"):
        assert after[cn] - before[cn], "no %s transferred" % cn

    # Idempotent: an identical second run adds no lexicon object.
    plan2, report2 = full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, selection_transform=_sel)
    again = _guids_by_class(TARGET_NAME, classes)
    for cn in classes:
        assert again[cn] == after[cn], "%s changed on an identical rerun" % cn
    assert not [a for a in plan2.actions
                if a.category in (GC.AFFIXES, GC.STEMS)], "rerun re-adds entries"
