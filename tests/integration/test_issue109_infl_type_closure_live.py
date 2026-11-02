"""Issue #109 live gate -- an INFLECTION_FEATURES-only selection pulls in the
struct-types its complex features' `TypeRA` names, and wires `TypeRA` in ONE run.

WRITE PATH: writes ONLY the throwaway project ``Target`` (restored from a known
backup before and after). Source ``Mbugwe Lizzie`` is opened READ-ONLY.
``Esperanto`` is never touched. Claim ``Target`` with the lockout skill first.

Skips unless FLEXLIBS_REQUIRE_LIVE=1.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue109_infl_type_closure_live.py -v -s
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_live_project]

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "Mbugwe Lizzie"          # READ-ONLY
TARGET_NAME = "Target"                 # the ONLY project this module writes
TARGET_PATH = "C:/ProgramData/SIL/FieldWorks/Projects/Target/Target.fwdata"
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

#: complex feature GUID -> struct-type GUID its source TypeRA names.
EXPECTED = {
    "1861cbf3-f02b-41cb-b9f5-7d5acc57323b": "4901227e-2ff3-4593-a3e9-dad496f20edc",
    "49eaca04-afbf-46ba-b55c-5399c7e96088": "2b491f35-aa10-49cb-afb2-facce7f5155f",
    "58a4cedb-7ed8-4548-8dae-770294804ec9": "3293182e-dbf8-460f-a1db-947a5a7bb03b",
    "df4a248b-747a-4240-9618-0e1f77059de7": "0a6c2f79-e440-4524-bd07-91bbe2b314bb",
}

if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups",
                Path("D:/Github/_Projects/_LEX/GramTrans/backups"))


def _restore() -> None:
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


def _features_only(closure: bool):
    def _sel(_full):
        from gramtrans.Lib.models import GrammarCategory, Selection
        return Selection(categories={GrammarCategory.INFLECTION_FEATURES: True},
                         include_closure=closure)
    return _sel


def _target_type_ra() -> tuple:
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    from SIL.LCModel import ICmObject, IFsComplexFeature
    proj = FLExProject()
    proj.OpenProject(projectName=TARGET_NAME, writeEnabled=False)
    try:
        fs = proj.lp.MsFeatureSystemOA
        out = {}
        for f in fs.FeaturesOC:
            g = str(ICmObject(f).Guid).lower()
            if g in EXPECTED and f.ClassName == "FsComplexFeature":
                t = IFsComplexFeature(f).TypeRA
                out[g] = None if t is None else str(ICmObject(t).Guid).lower()
        types = {str(ICmObject(t).Guid).lower() for t in fs.TypesOC}
        return out, types
    finally:
        proj.CloseProject()


def _run(closure: bool):
    from harness import full_run
    return full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH,
        selection_transform=_features_only(closure))


def test_features_only_with_closure_wires_type_ra_in_one_run():
    from gramtrans.Lib.models import GrammarCategory
    before, before_types = _target_type_ra()
    assert before == {} and not set(EXPECTED.values()) & before_types

    plan, report = _run(True)
    cats = {a.category for a in plan.actions}
    print("[LIVE] planned categories: %s" % sorted(c.value for c in cats))
    assert GrammarCategory.FEATURE_STRUCT_TYPES in cats, "struct-types not pulled in"
    assert report.per_category[
        GrammarCategory.FEATURE_STRUCT_TYPES].closure_pulled_in >= 1
    assert plan.complex_feature_type_refs == EXPECTED

    after, types = _target_type_ra()
    print("[LIVE] post %s" % after)
    assert set(EXPECTED.values()) <= types
    assert after == EXPECTED, "TypeRA not wired in a single run"
    assert not [s for s in report.skips if s.source_guid in EXPECTED
                and "TypeRA" in (s.detail or "")]


def test_features_only_without_closure_still_reports_unresolved():
    """Negative control: closure off reproduces the pre-#109 behaviour."""
    _run(False)
    after, types = _target_type_ra()
    assert after == {g: None for g in EXPECTED}
    assert not set(EXPECTED.values()) & types
