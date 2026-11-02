"""Issue #138 live gate (FR-018) -- a struct-types-only selection pulls in the
feature defns its `FeaturesRS` names (STRUCT_TYPE_TO_INFL_FEATURE and
PHON_STRUCT_TYPE_TO_PHON_FEATURE), so the types arrive fully wired in ONE run.

WRITE PATH: writes ONLY the private sandbox ``GT-Sandbox-138`` (restored
headlessly from a known backup before and after the test). The source
``Mbugwe Lizzie`` is opened READ-ONLY; its ``.fwdata`` SHA-256 is asserted
unchanged. ``Target`` and ``Esperanto`` are never touched.

Skips unless FLEXLIBS_REQUIRE_LIVE=1. When it is set, an unavailable LCM
FAILS rather than skips.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue138_struct_type_closure_live.py -v -s
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_live_project]

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "Mbugwe Lizzie"          # READ-ONLY
TARGET_NAME = "GT-Sandbox-138"         # the ONLY project this module writes
PROJECTS = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS / TARGET_NAME / (TARGET_NAME + ".fwdata"))
SOURCE_FWDATA = PROJECTS / SOURCE_NAME / (SOURCE_NAME + ".fwdata")
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

NUMBER = "bd1d7f21-7cf2-44c9-a952-69d218bc1028"
CLASS = "e49c7be8-7055-4905-b993-861ef0576b4c"
PERSON = "55706aa1-2381-45a6-bba2-ea489bb4a636"
POLARITY = "974d2ec1-579b-4483-91da-0d22295742dd"
TENSE = "833d061d-c424-4520-ae5d-1507310be47f"
LONG = "799ca058-04fa-44ee-a318-b637a8625acb"
LABIAL = "bd13af9f-bef2-47a3-80f2-c78c645f4102"

#: (system attr, struct-type GUID) -> source FeaturesRS member GUIDs, in order
#: (same read-only probe of `Mbugwe Lizzie` as the #108 live gate).
SOURCE_MEMBERS = {
    ("MsFeatureSystemOA", "0a6c2f79-e440-4524-bd07-91bbe2b314bb"): [CLASS, NUMBER],
    ("MsFeatureSystemOA", "2b491f35-aa10-49cb-afb2-facce7f5155f"): [NUMBER, CLASS, PERSON],
    ("MsFeatureSystemOA", "3293182e-dbf8-460f-a1db-947a5a7bb03b"): [NUMBER, CLASS],
    ("MsFeatureSystemOA", "4901227e-2ff3-4593-a3e9-dad496f20edc"): [NUMBER, CLASS, PERSON],
    ("MsFeatureSystemOA", "93846124-2eae-4f04-8693-30cdbcf9a83a"): [POLARITY, TENSE],
    ("PhFeatureSystemOA", "0ea53dd6-79f5-4fac-a672-f2f7026d8d15"): [LONG, LABIAL],
}

if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups",
                Path("D:/Github/_Projects/_LEX/GramTrans/backups"))


def _restore() -> None:
    assert TARGET_NAME == "GT-Sandbox-138"
    from harness.restore import restore_target
    for d in _BACKUP_DIRS:
        p = d / BACKUP_NAME
        if p.is_file():
            restore_target(TARGET_NAME, backup_path=p)
            return
    pytest.fail("[FAIL] backup %r not found" % BACKUP_NAME)


@pytest.fixture(autouse=True)
def _restore_around():
    _restore()
    yield
    _restore()


def _types_only(closure: bool):
    def _sel(_full):
        from gramtrans.Lib.models import GrammarCategory, Selection
        return Selection(
            categories={GrammarCategory.FEATURE_STRUCT_TYPES: True,
                        GrammarCategory.PHON_FEAT_TYPES: True},
            include_closure=closure)
    return _sel


def _target_members() -> dict:
    """{(system attr, type guid): [FeaturesRS member guids]} for the source's
    struct-types that exist in the sandbox, via a fresh read-only open."""
    assert TARGET_NAME == "GT-Sandbox-138"
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    from SIL.LCModel import ICmObject, IFsFeatStrucType
    proj = FLExProject()
    proj.OpenProject(projectName=TARGET_NAME, writeEnabled=False)
    try:
        out = {}
        for attr in ("MsFeatureSystemOA", "PhFeatureSystemOA"):
            for t in getattr(proj.lp, attr).TypesOC:
                g = str(ICmObject(t).Guid).lower()
                if (attr, g) in SOURCE_MEMBERS:
                    out[(attr, g)] = [str(ICmObject(d).Guid).lower()
                                      for d in IFsFeatStrucType(t).FeaturesRS]
        return out
    finally:
        proj.CloseProject()


def _run(closure: bool):
    from harness import full_run
    return full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH,
        selection_transform=_types_only(closure))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_types_only_with_closure_pulls_in_member_features_in_one_run():
    from gramtrans.Lib.models import GrammarCategory
    src_sha = _sha(SOURCE_FWDATA)
    before = _target_members()
    print("[LIVE] pre  sandbox source-type members=%s" % before)
    assert before == {}, "[SETUP] sandbox already holds the types"

    plan, report = _run(True)
    cats = {a.category for a in plan.actions}
    print("[LIVE] planned categories: %s" % sorted(c.value for c in cats))
    assert GrammarCategory.INFLECTION_FEATURES in cats, "features not pulled in"
    assert GrammarCategory.PHONOLOGICAL_FEATURES in cats, \
        "phonological features not pulled in"
    pulled_ms = report.per_category[
        GrammarCategory.INFLECTION_FEATURES].closure_pulled_in
    pulled_ph = report.per_category[
        GrammarCategory.PHONOLOGICAL_FEATURES].closure_pulled_in
    print("[LIVE] closure_pulled_in infl=%d phon=%d" % (pulled_ms, pulled_ph))
    assert pulled_ms >= 1 and pulled_ph >= 1

    after = _target_members()
    print("[LIVE] post sandbox source-type members=%s" % after)
    assert after == SOURCE_MEMBERS, "types not fully wired in a single run"

    gaps = [d for d in report.dropped_items if d.field_name == "FeaturesRS"]
    print("[LIVE] FeaturesRS drops=%d" % len(gaps))
    assert gaps == []
    assert _sha(SOURCE_FWDATA) == src_sha, "source .fwdata changed"


def test_types_only_without_closure_leaves_types_unwired():
    """Negative control: closure off reproduces the pre-#138 behaviour -- the
    types arrive with their FeaturesRS empty (member defns not selected)."""
    _run(False)
    after = _target_members()
    print("[LIVE] control (no closure) members=%s" % after)
    assert set(after) == set(SOURCE_MEMBERS)
    assert all(v == [] for v in after.values())
