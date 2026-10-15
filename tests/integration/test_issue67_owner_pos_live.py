"""Issue #67 live gate -- a STEM_NAMES-only transfer pulls in its owner POS.

WRITE PATH: writes ONLY the throwaway project ``Target`` (restored headlessly
from a known backup before every run and again at the end).  The source
``Mbugwe Lizzie`` is opened READ-ONLY.  ``Esperanto`` is never touched.

Skips unless FLEXLIBS_REQUIRE_LIVE=1.  When it is set, an unavailable LCM
FAILS rather than skips.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue67_owner_pos_live.py -v -s

Positive: owner-POS closure edge registered -> the POS and the stem name both
land under their SOURCE GUIDs and the RunReport counts are truthful (#68).
Negative: closure disabled so the owner POS is missing -> the stem name is
reported skipped/failed, never added, and is absent from Target (#68).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_LIVE = os.environ.get("FLEXLIBS_REQUIRE_LIVE") == "1"
if not _LIVE:
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "Mbugwe Lizzie"          # READ-ONLY
TARGET_NAME = "Target"                 # the ONLY project this module writes
TARGET_PATH = ("C:/ProgramData/SIL/FieldWorks/Projects/Target/Target.fwdata")
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
STEM_NAME_GUID = "c1724868-9eeb-4e32-a5f7-f01e752d5260"
OWNER_POS_GUID = "923e5aed-d84a-48b0-9b7a-331c1336864a"   # "Preposition"

if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (
    _REPO / "backups",
    Path("D:/Github/_Projects/_LEX/GramTrans/backups"),
)


def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        p = d / BACKUP_NAME
        if p.is_file():
            return p
    pytest.fail("[FAIL] backup %r not found under %s" % (BACKUP_NAME, _BACKUP_DIRS))


def _restore() -> None:
    here = str(Path(__file__).parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    from harness.restore import restore_target
    restore_target(TARGET_NAME, backup_path=_backup_path())


def _selection_stem_names_only(_full):
    from gramtrans.Lib.models import GrammarCategory, Selection
    return Selection(categories={GrammarCategory.STEM_NAMES: True})


def _target_guids() -> tuple:
    """(pos_guids, stem_name_guids) in Target, via a fresh read-only open."""
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    from SIL.LCModel import ICmObject, IPartOfSpeech
    proj = FLExProject()
    proj.OpenProject(projectName=TARGET_NAME, writeEnabled=False)
    try:
        pos_guids, sn_guids = set(), set()
        for pos in proj.POS.GetAll(recursive=True):
            concrete = pos.concrete if hasattr(pos, "concrete") else pos
            pos_guids.add(str(ICmObject(concrete).Guid).lower())
            for sn in IPartOfSpeech(concrete).StemNamesOC:
                sn_guids.add(str(ICmObject(sn).Guid).lower())
        return pos_guids, sn_guids
    finally:
        proj.CloseProject()


@pytest.fixture(autouse=True)
def _restore_around():
    from harness import full_run  # noqa: F401  (ensures harness path)
    _restore()
    yield
    _restore()


def _total_added(report) -> int:
    return sum(r.added for r in report.per_category.values())


def _describe(report) -> str:
    from gramtrans.Lib.models import GrammarCategory
    lines = ["[LIVE] total_added=%s skips=%d dropped=%d leaf_failures=%d"
             % (_total_added(report), len(report.skips),
                len(report.dropped_items), len(report.leaf_execution_failures))]
    for cat, rep in report.per_category.items():
        lines.append("[LIVE]   %s added=%s skipped=%s closure_pulled_in=%s"
                     % (getattr(cat, "value", cat), rep.added, rep.skipped,
                        rep.closure_pulled_in))
    for sk in report.skips:
        lines.append("[LIVE]   skip %s %s %s"
                     % (getattr(sk.category, "value", sk.category),
                        str(sk.source_guid)[:8], getattr(sk, "reason", "")))
    _ = GrammarCategory
    return "\n".join(lines)


def test_stem_names_only_pulls_in_owner_pos_and_reports_truthfully():
    sys.path.insert(0, str(Path(__file__).parent))
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory

    before_pos, before_sn = _target_guids()
    assert OWNER_POS_GUID not in before_pos, "[SETUP] Target already has the POS"
    assert STEM_NAME_GUID not in before_sn

    plan, report = full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH,
        selection_transform=_selection_stem_names_only)
    print(_describe(report))

    cats = {a.category for a in plan.actions}
    assert GrammarCategory.STEM_NAMES in cats
    assert GrammarCategory.GRAM_CATEGORIES in cats, (
        "owner POS was not planned -- closure edge not followed")
    assert report.per_category[GrammarCategory.STEM_NAMES].added >= 1
    pulled = sum(r.closure_pulled_in for r in report.per_category.values())
    assert pulled >= 1
    assert report.per_category[GrammarCategory.GRAM_CATEGORIES].closure_pulled_in >= 1

    after_pos, after_sn = _target_guids()
    assert OWNER_POS_GUID in after_pos
    assert STEM_NAME_GUID in after_sn
    # Truthful counts: what the report says was added is what is in Target.
    assert report.per_category[GrammarCategory.STEM_NAMES].added == len(
        after_sn - before_sn)


def test_missing_owner_pos_is_skipped_never_added(monkeypatch):
    """#68 interaction: with the closure edge disabled the owner POS is never
    created; the stem name must be reported skipped/failed, not added."""
    sys.path.insert(0, str(Path(__file__).parent))
    from harness import full_run
    from gramtrans.Lib import categories
    from gramtrans.Lib.models import GrammarCategory

    monkeypatch.setattr(categories, "CLOSURE_EDGES_VERIFIED", {})

    plan, report = full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH,
        selection_transform=_selection_stem_names_only)
    print(_describe(report))

    assert GrammarCategory.GRAM_CATEGORIES not in {a.category for a in plan.actions}
    sn = report.per_category[GrammarCategory.STEM_NAMES]
    assert sn.added == 0, "stem name counted as added with no owner POS"
    assert _total_added(report) == 0
    not_added = [s for s in report.skips
                 if s.category == GrammarCategory.STEM_NAMES] or [
        d for d in report.dropped_items]
    assert not_added, "stem name neither skipped nor failed -- silent drop"

    after_pos, after_sn = _target_guids()
    assert OWNER_POS_GUID not in after_pos
    assert STEM_NAME_GUID not in after_sn
