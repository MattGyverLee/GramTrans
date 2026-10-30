"""Issue #37 live gate -- complex-feature `TypeRA` is wired by the post-loop
tail, repaired on a re-run, and never rewritten once correct.

WRITE PATH: writes ONLY the private sandbox ``GT-Sandbox-37`` (restored
headlessly from a known backup before every test and again at the end). The
source ``Mbugwe Lizzie`` is opened READ-ONLY. ``Target`` and ``Esperanto`` are
never touched.

Skips unless FLEXLIBS_REQUIRE_LIVE=1. When it is set, an unavailable LCM
FAILS rather than skips.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue37_complex_type_ra_live.py -v -s

Source facts (read-only probe of ``Mbugwe Lizzie``, 2026-10-30): four
``FsComplexFeature`` in ``MsFeatureSystemOA.FeaturesOC``, each with a
``TypeRA`` into ``MsFeatureSystemOA.TypesOC`` -- see ``EXPECTED`` below.
"""
from __future__ import annotations

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
TARGET_NAME = "GT-Sandbox-37"          # the ONLY project this module writes
TARGET_PATH = ("C:/ProgramData/SIL/FieldWorks/Projects/GT-Sandbox-37/"
               "GT-Sandbox-37.fwdata")
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

#: complex feature GUID -> struct-type GUID its source TypeRA names.
EXPECTED = {
    "1861cbf3-f02b-41cb-b9f5-7d5acc57323b": "4901227e-2ff3-4593-a3e9-dad496f20edc",  # object agreement
    "49eaca04-afbf-46ba-b55c-5399c7e96088": "2b491f35-aa10-49cb-afb2-facce7f5155f",  # subject agreement
    "58a4cedb-7ed8-4548-8dae-770294804ec9": "3293182e-dbf8-460f-a1db-947a5a7bb03b",  # adjective agreement
    "df4a248b-747a-4240-9618-0e1f77059de7": "0a6c2f79-e440-4524-bd07-91bbe2b314bb",  # noun agreement
}

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
    from harness.restore import restore_target
    restore_target(TARGET_NAME, backup_path=_backup_path())


@pytest.fixture(autouse=True)
def _restore_around():
    _restore()
    yield
    _restore()


def _sel_features_and_types(_full):
    from gramtrans.Lib.models import GrammarCategory, Selection
    return Selection(categories={GrammarCategory.INFLECTION_FEATURES: True,
                                 GrammarCategory.FEATURE_STRUCT_TYPES: True})


def _sel_features_only(_full):
    from gramtrans.Lib.models import GrammarCategory, Selection
    return Selection(categories={GrammarCategory.INFLECTION_FEATURES: True})


def _target_type_ra() -> dict:
    """{complex_feature_guid: TypeRA guid or None} for EXPECTED's features
    present in the sandbox, plus the set of TypesOC GUIDs, via a fresh
    read-only open."""
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


class _WireCounter(logging.Handler):
    """Counts the tail's per-feature `TypeRA wired` log lines -- one per
    write -- so "a re-run writes nothing" is measured, not inferred."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.wired = []

    def emit(self, record) -> None:
        msg = record.getMessage()
        if "TypeRA wired" in msg:
            self.wired.append(msg)


def _run(selection_transform, monkeypatch=None, preview_lines=None):
    """One Move into the sandbox; returns (plan, report, wired_log_lines)."""
    from harness import full_run
    from gramtrans.Lib import preview
    log = logging.getLogger("gramtrans.Lib.categories")
    counter = _WireCounter()
    old_level = log.level
    log.setLevel(logging.INFO)
    log.addHandler(counter)
    if monkeypatch is not None and preview_lines is not None:
        # Render the Preview rows against the still-open target, immediately
        # before Move writes -- exactly what `_on_preview` would show.
        real = full_run.api.execute_move

        def _capture(context, plan, *a, **k):
            preview_lines.extend(preview.render_complex_feature_type_refs(plan))
            return real(context, plan, *a, **k)
        monkeypatch.setattr(full_run.api, "execute_move", _capture)
    try:
        plan, report = full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH,
            selection_transform=selection_transform)
    finally:
        log.removeHandler(counter)
        log.setLevel(old_level)
    return plan, report, counter.wired


def _type_ra_skips(report):
    return [s for s in report.skips
            if s.source_guid in EXPECTED and "TypeRA" in (s.detail or "")]


def test_fresh_move_wires_type_ra_and_rerun_writes_nothing(monkeypatch):
    before, before_types = _target_type_ra()
    print("[LIVE] pre  features=%s types=%d" % (before, len(before_types)))
    assert before == {}, "[SETUP] sandbox already has the complex features"
    assert not set(EXPECTED.values()) & before_types

    preview_rows: list = []
    plan, report, wired = _run(_sel_features_and_types, monkeypatch, preview_rows)
    print("\n".join(["[LIVE] preview:"] + preview_rows))
    print("[LIVE] run1 wired=%d skips=%s" % (len(wired), _type_ra_skips(report)))
    assert plan.complex_feature_type_refs == EXPECTED
    wire_rows = [r for r in preview_rows if r.strip().startswith("Wire")]
    assert len(wire_rows) == len(EXPECTED)
    assert len(wired) == len(EXPECTED) == len(wire_rows)
    assert _type_ra_skips(report) == []

    after, _ = _target_type_ra()
    print("[LIVE] post run1 %s" % after)
    assert after == EXPECTED

    preview_rows2: list = []
    monkeypatch.undo()
    _plan2, report2, wired2 = _run(_sel_features_and_types, monkeypatch,
                                   preview_rows2)
    print("\n".join(["[LIVE] preview run2:"] + preview_rows2))
    print("[LIVE] run2 wired=%d" % len(wired2))
    assert wired2 == []
    assert all("SKIP (already wired)" in r for r in preview_rows2[1:])
    assert _type_ra_skips(report2) == []
    assert _target_type_ra()[0] == EXPECTED


def test_null_type_ra_from_earlier_run_is_repaired(monkeypatch):
    # Run 1: features only. The struct-types are absent, so every TypeRA is
    # left null -- and REPORTED, not silent.
    _p1, report1, wired1 = _run(_sel_features_only)
    after1, types1 = _target_type_ra()
    print("[LIVE] run1 (features only) %s skips=%d"
          % (after1, len(_type_ra_skips(report1))))
    assert wired1 == []
    assert after1 == {g: None for g in EXPECTED}
    assert {s.source_guid for s in _type_ra_skips(report1)} == set(EXPECTED)

    # Run 2: features + types. Every complex feature is ALREADY_PRESENT, so
    # the INFLECTION_FEATURES category plans no create for it -- the case the
    # pre-#37 code never revisited. The post-loop tail repairs all four.
    _p2, report2, wired2 = _run(_sel_features_and_types)
    after2, _ = _target_type_ra()
    print("[LIVE] run2 repaired=%d %s" % (len(wired2), after2))
    assert len(wired2) == len(EXPECTED)
    assert after2 == EXPECTED
    assert _type_ra_skips(report2) == []

    # Run 3: idempotent.
    _p3, _r3, wired3 = _run(_sel_features_and_types)
    print("[LIVE] run3 wired=%d" % len(wired3))
    assert wired3 == []
    assert _target_type_ra()[0] == EXPECTED


def test_pre_fix_code_path_leaves_null_then_fixed_code_repairs(monkeypatch):
    # Reproduce the issue's history exactly: both categories selected, tail
    # disabled (the pre-#37 behaviour) -> null TypeRA on all four.
    from gramtrans.Lib import transfer
    monkeypatch.setattr(transfer, "_ensure_complex_feature_type_ra",
                        lambda *a, **k: None)
    _run(_sel_features_and_types)
    after1, types1 = _target_type_ra()
    print("[LIVE] pre-fix run %s" % after1)
    assert after1 == {g: None for g in EXPECTED}
    assert set(EXPECTED.values()) <= types1  # the types DID land

    monkeypatch.undo()
    _p2, report2, wired2 = _run(_sel_features_and_types)
    after2, _ = _target_type_ra()
    print("[LIVE] fixed re-run repaired=%d %s" % (len(wired2), after2))
    assert len(wired2) == len(EXPECTED)
    assert after2 == EXPECTED
