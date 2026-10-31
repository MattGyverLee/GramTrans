"""Issue #108 live gate -- struct-type `FeaturesRS` created before its member
features is repaired by the post-loop pass, to source order by GUID, in both
feature systems; target-only members are preserved and reported; a complete
sequence is never rewritten.

WRITE PATH: writes ONLY the private sandbox ``GT-Sandbox-108`` (restored
headlessly from a known backup before and after the test). The source
``Mbugwe Lizzie`` is opened READ-ONLY; its ``.fwdata`` SHA-256 is asserted
unchanged. ``Target`` and ``Esperanto`` are never touched.

Skips unless FLEXLIBS_REQUIRE_LIVE=1. When it is set, an unavailable LCM
FAILS rather than skips.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue108_features_rs_repair_live.py -v -s

Source facts (read-only MCP probe of ``Mbugwe Lizzie``, 2026-10-30): five
struct-types in ``MsFeatureSystemOA.TypesOC`` and one in
``PhFeatureSystemOA.TypesOC`` -- see ``SOURCE_MEMBERS`` below (14 member
slots in all).
"""
from __future__ import annotations

import hashlib
import logging
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
TARGET_NAME = "GT-Sandbox-108"         # the ONLY project this module writes
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

NOUN_AGR = "0a6c2f79-e440-4524-bd07-91bbe2b314bb"
SUBJ_AGR = "2b491f35-aa10-49cb-afb2-facce7f5155f"
PHON = "0ea53dd6-79f5-4fac-a672-f2f7026d8d15"

#: (system attr, type GUID) -> source FeaturesRS member GUIDs, in order.
SOURCE_MEMBERS = {
    ("MsFeatureSystemOA", NOUN_AGR): [CLASS, NUMBER],
    ("MsFeatureSystemOA", SUBJ_AGR): [NUMBER, CLASS, PERSON],
    ("MsFeatureSystemOA", "3293182e-dbf8-460f-a1db-947a5a7bb03b"): [NUMBER, CLASS],
    ("MsFeatureSystemOA", "4901227e-2ff3-4593-a3e9-dad496f20edc"): [NUMBER, CLASS, PERSON],
    ("MsFeatureSystemOA", "93846124-2eae-4f04-8693-30cdbcf9a83a"): [POLARITY, TENSE],
    ("PhFeatureSystemOA", PHON): [LONG, LABIAL],
}
N_SLOTS = sum(len(v) for v in SOURCE_MEMBERS.values())  # 14

#: Target-only member defns authored in the sandbox between runs 1 and 2.
X_MS = "10800000-0108-4108-8108-0000000000a1"
Y_PH = "10800000-0108-4108-8108-0000000000b2"

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
    assert TARGET_NAME == "GT-Sandbox-108"
    from harness.restore import restore_target
    restore_target(TARGET_NAME, backup_path=_backup_path())


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(autouse=True)
def _restore_around():
    _restore()
    yield
    _restore()


def _sel(*cats):
    from gramtrans.Lib.models import GrammarCategory, Selection

    def _t(_full):
        return Selection(categories={getattr(GrammarCategory, c): True
                                     for c in cats})
    return _t


SEL_TYPES_ONLY = _sel("FEATURE_STRUCT_TYPES", "PHON_FEAT_TYPES")
SEL_WITH_FEATURES = _sel("INFLECTION_FEATURES", "FEATURE_STRUCT_TYPES",
                         "PHONOLOGICAL_FEATURES", "PHON_FEAT_TYPES")


def _open_target(write: bool):
    assert TARGET_NAME == "GT-Sandbox-108"
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    proj = FLExProject()
    if write:
        proj.OpenProject(projectName=TARGET_NAME, writeEnabled=True,
                         undoable=False)
    else:
        proj.OpenProject(projectName=TARGET_NAME, writeEnabled=False)
    return proj


def _target_members() -> dict:
    """{(system attr, type guid): [FeaturesRS member guids]} for every
    struct-type in the sandbox, via a fresh read-only open."""
    from SIL.LCModel import ICmObject, IFsFeatStrucType
    proj = _open_target(write=False)
    try:
        out = {}
        for attr in ("MsFeatureSystemOA", "PhFeatureSystemOA"):
            fs = getattr(proj.lp, attr)
            for t in fs.TypesOC:
                g = str(ICmObject(t).Guid).lower()
                out[(attr, g)] = [str(ICmObject(d).Guid).lower()
                                  for d in IFsFeatStrucType(t).FeaturesRS]
        return out
    finally:
        proj.CloseProject()


def _author_target_only_members() -> None:
    """Sandbox-only fixture: a closed feature the source does not have,
    appended to one type's FeaturesRS in each feature system."""
    from System import Guid as DotNetGuid
    from SIL.LCModel import (ICmObject, IFsClosedFeatureFactory,
                             IFsFeatStrucType)
    from SIL.LCModel.Core.Text import TsStringUtils
    proj = _open_target(write=True)
    try:
        assert proj.ProjectName() == TARGET_NAME
        sl = proj.Cache.ServiceLocator
        ws = proj.Cache.DefaultAnalWs
        for attr, type_guid, feat_guid, name in (
                ("MsFeatureSystemOA", NOUN_AGR, X_MS, "gt108 target-only ms"),
                ("PhFeatureSystemOA", PHON, Y_PH, "gt108 target-only ph")):
            fs = getattr(proj.lp, attr)
            feat = sl.GetService(IFsClosedFeatureFactory).Create(
                DotNetGuid.Parse(feat_guid))
            fs.FeaturesOC.Add(feat)
            feat.Name.set_String(ws, TsStringUtils.MakeString(name, ws))
            for t in fs.TypesOC:
                if str(ICmObject(t).Guid).lower() == type_guid:
                    IFsFeatStrucType(t).FeaturesRS.Add(feat)
    finally:
        proj.CloseProject()


def _swap_first_two(attr, type_guid) -> None:
    """Sandbox-only fixture: put a type's first two members out of order."""
    from SIL.LCModel import ICmObject, IFsFeatStrucType
    proj = _open_target(write=True)
    try:
        assert proj.ProjectName() == TARGET_NAME
        for t in getattr(proj.lp, attr).TypesOC:
            if str(ICmObject(t).Guid).lower() == type_guid:
                seq = IFsFeatStrucType(t).FeaturesRS
                first = list(seq)[0]
                seq.RemoveAt(0)
                seq.Insert(1, first)
    finally:
        proj.CloseProject()


class _RepairCounter(logging.Handler):
    """Counts the pass's per-type `FeaturesRS repaired` log lines -- one per
    rewrite -- so "a re-run writes nothing" is measured, not inferred."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.repaired = []

    def emit(self, record) -> None:
        msg = record.getMessage()
        if "FeaturesRS repaired" in msg:
            self.repaired.append(msg)


def _run(selection_transform, monkeypatch):
    """One Preview + Move into the sandbox.

    Returns (plan, report, repaired_log_lines, preview_rows). The Preview rows
    are rendered against the still-open target immediately before Move
    writes -- exactly what `_on_preview` would show."""
    from harness import full_run
    from gramtrans.Lib import preview
    log = logging.getLogger("gramtrans.Lib.categories")
    counter = _RepairCounter()
    old_level = log.level
    log.setLevel(logging.INFO)
    log.addHandler(counter)
    rows: list = []
    real = full_run.api.execute_move

    def _capture(context, plan, *a, **k):
        rows.extend(preview.render_struct_type_features_rs(plan))
        return real(context, plan, *a, **k)
    monkeypatch.setattr(full_run.api, "execute_move", _capture)
    try:
        plan, report = full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH,
            selection_transform=selection_transform)
    finally:
        monkeypatch.undo()
        log.removeHandler(counter)
        log.setLevel(old_level)
    return plan, report, counter.repaired, rows


def _features_rs_drops(items):
    return sorted((d.owner_guid, d.item_guid) for d in items
                  if d.field_name == "FeaturesRS")


def _target_only_skips(report):
    return sorted((s.source_guid, s.reason.value) for s in report.skips
                  if "preserved, not removed" in (s.detail or ""))


def _rows(rows, prefix):
    return [r for r in rows if r.strip().startswith(prefix)]


def test_features_rs_repaired_to_source_order_and_rerun_writes_nothing(monkeypatch):
    import gramtrans
    import flexicon
    print("[LIVE] gramtrans=%s" % gramtrans.__file__)
    print("[LIVE] flexicon=%s" % flexicon.__file__)
    assert "GramTrans-fix-108" in gramtrans.__file__
    src_sha = _sha(SOURCE_FWDATA)
    print("[LIVE] source sha256 before=%s" % src_sha)

    before = _target_members()
    print("[LIVE] pre  sandbox types=%s" % before)
    assert not set(before) & set(SOURCE_MEMBERS), "[SETUP] sandbox has the types"

    # ---- Run 1: struct-types WITHOUT their member features ---------------
    plan1, report1, rep1, rows1 = _run(SEL_TYPES_ONLY, monkeypatch)
    after1 = _target_members()
    print("\n".join(["[LIVE] run1 preview:"] + rows1))
    print("[LIVE] run1 repaired=%d members=%s" % (len(rep1), after1))
    assert set(plan1.struct_type_feature_refs) == {g for _a, g in SOURCE_MEMBERS}
    assert len(_rows(rows1, "Wire at create")) == len(SOURCE_MEMBERS)
    assert _rows(rows1, "Repair") == [] and rep1 == []
    for key in SOURCE_MEMBERS:
        assert after1[key] == [], "type %s should be incomplete" % (key,)
    # The gap is a REPORT drop record (Preview and Move), not only a log line.
    expected_drops = sorted((g, m) for (_a, g), ms in SOURCE_MEMBERS.items()
                            for m in ms)
    assert len(expected_drops) == N_SLOTS
    assert _features_rs_drops(plan1.dropped_items) == expected_drops
    assert _features_rs_drops(report1.dropped_items) == expected_drops

    # ---- Fixture: one target-only member per feature system --------------
    _author_target_only_members()
    seeded = _target_members()
    assert seeded[("MsFeatureSystemOA", NOUN_AGR)] == [X_MS]
    assert seeded[("PhFeatureSystemOA", PHON)] == [Y_PH]

    # ---- Run 2: including the features -> repaired to source order -------
    plan2, report2, rep2, rows2 = _run(SEL_WITH_FEATURES, monkeypatch)
    after2 = _target_members()
    print("\n".join(["[LIVE] run2 preview:"] + rows2))
    print("[LIVE] run2 repaired=%d members=%s" % (len(rep2), after2))
    expected2 = {k: list(v) for k, v in SOURCE_MEMBERS.items()}
    expected2[("MsFeatureSystemOA", NOUN_AGR)] += [X_MS]   # kept, after source
    expected2[("PhFeatureSystemOA", PHON)] += [Y_PH]
    for key, want in expected2.items():
        assert after2[key] == want, key
    assert len(rep2) == len(SOURCE_MEMBERS) == len(_rows(rows2, "Repair"))
    assert _features_rs_drops(report2.dropped_items) == []
    assert _features_rs_drops(plan2.dropped_items) == []
    assert _target_only_skips(report2) == sorted(
        [(NOUN_AGR, "needs_manual"), (PHON, "needs_manual")])
    assert len(_rows(rows2, "REPORT (target-only member kept)")) == 2

    # ---- Run 3: idempotent -------------------------------------------------
    _p3, report3, rep3, rows3 = _run(SEL_WITH_FEATURES, monkeypatch)
    after3 = _target_members()
    print("[LIVE] run3 repaired=%d" % len(rep3))
    assert rep3 == [] and _rows(rows3, "Repair") == []
    assert len(_rows(rows3, "SKIP (already complete)")) == len(SOURCE_MEMBERS)
    assert {k: after3[k] for k in expected2} == expected2
    assert _target_only_skips(report3) == _target_only_skips(report2)

    # ---- Run 4: out-of-order members are reordered, not appended ---------
    _swap_first_two("MsFeatureSystemOA", SUBJ_AGR)
    swapped = _target_members()[("MsFeatureSystemOA", SUBJ_AGR)]
    assert swapped == [CLASS, NUMBER, PERSON]
    _p4, _r4, rep4, rows4 = _run(SEL_WITH_FEATURES, monkeypatch)
    after4 = _target_members()
    print("[LIVE] run4 repaired=%d %s" % (len(rep4), after4[("MsFeatureSystemOA", SUBJ_AGR)]))
    assert len(rep4) == 1 == len(_rows(rows4, "Repair"))
    assert {k: after4[k] for k in expected2} == expected2

    src_sha_after = _sha(SOURCE_FWDATA)
    print("[LIVE] source sha256 after=%s" % src_sha_after)
    assert src_sha_after == src_sha
