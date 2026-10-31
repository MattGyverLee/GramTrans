"""Issue #110 live gate -- complex-feature `TypeRA` has ONE writer, so Move's
reported write count equals Preview's "Wire" rows even when the struct-types
already exist in the target.

Before #110 the INFLECTION_FEATURES create path also wired `TypeRA` whenever
the target struct-type already existed. The post-loop tail (#37) then saw
ALREADY_WIRED, so Preview showed N "Wire" rows while Move reported fewer
(here: 0) writes. The data was right; the report was not. The #37 live gate
only held because its target started with no struct-types.

WRITE PATH: writes ONLY the private sandbox ``GT-Sandbox-110`` (restored
headlessly from a known backup before every test and again at the end). The
source ``Mbugwe LizzieHC practice 2026`` is opened READ-ONLY. ``Target`` and
``Esperanto`` are never touched.

Skips unless FLEXLIBS_REQUIRE_LIVE=1. When it is set, an unavailable LCM
FAILS rather than skips.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue110_type_ra_single_writer_live.py -v -s

Source facts (read-only MCP probe of ``Mbugwe LizzieHC practice 2026``,
2026-10-30): two ``FsComplexFeature`` in ``MsFeatureSystemOA.FeaturesOC``,
each with a ``TypeRA`` into ``MsFeatureSystemOA.TypesOC`` -- ``EXPECTED``.
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

SOURCE_NAME = "Mbugwe LizzieHC practice 2026"   # READ-ONLY
TARGET_NAME = "GT-Sandbox-110"                  # the ONLY project this module writes
TARGET_PATH = ("C:/ProgramData/SIL/FieldWorks/Projects/GT-Sandbox-110/"
               "GT-Sandbox-110.fwdata")
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

#: complex feature GUID -> struct-type GUID its source TypeRA names.
EXPECTED = {
    "49eaca04-afbf-46ba-b55c-5399c7e96088": "2b491f35-aa10-49cb-afb2-facce7f5155f",  # subject agreement
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
    import flexicon
    import gramtrans
    print("[LIVE] gramtrans=%s flexicon=%s" % (gramtrans.__file__, flexicon.__file__))
    _restore()
    yield
    _restore()


def _sel(*cats):
    from gramtrans.Lib.models import GrammarCategory, Selection

    def _transform(_full):
        return Selection(categories={getattr(GrammarCategory, c): True for c in cats})
    return _transform


_TYPES_ONLY = _sel("FEATURE_STRUCT_TYPES")
_FEATURES_AND_TYPES = _sel("INFLECTION_FEATURES", "FEATURE_STRUCT_TYPES")


def _target_type_ra() -> tuple:
    """({complex_feature_guid: TypeRA guid or None} for EXPECTED's features
    present in the sandbox, set of TypesOC GUIDs), via a fresh read-only open."""
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
    """Counts the tail's per-feature `TypeRA wired` log lines -- one per write."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.wired = []

    def emit(self, record) -> None:
        if "TypeRA wired" in record.getMessage():
            self.wired.append(record.getMessage())


def _run(selection_transform, monkeypatch):
    """One Move into the sandbox. Returns (plan, report, preview_rows,
    wired_log_lines, reported_writes) where `reported_writes` is the tail's
    own counter (`_complex_type_ra_writes`) as Move left it on its context."""
    from harness import full_run
    from gramtrans.Lib import categories, preview
    preview_rows: list = []
    reported: list = []

    real_execute = full_run.api.execute_move

    def _capture_preview(context, plan, *a, **k):
        # Render against the still-unwritten target, exactly what Preview shows.
        preview_rows.extend(preview.render_complex_feature_type_refs(plan))
        return real_execute(context, plan, *a, **k)

    real_pass = categories._run_complex_feature_type_ra_pass

    def _capture_count(context, target, tag=None):
        skips = real_pass(context, target, tag)
        reported.append(getattr(context, "_complex_type_ra_writes", None))
        return skips

    monkeypatch.setattr(full_run.api, "execute_move", _capture_preview)
    monkeypatch.setattr(categories, "_run_complex_feature_type_ra_pass", _capture_count)

    log = logging.getLogger("gramtrans.Lib.categories")
    counter = _WireCounter()
    old_level = log.level
    log.setLevel(logging.INFO)
    log.addHandler(counter)
    try:
        plan, report = full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH,
            selection_transform=selection_transform)
    finally:
        log.removeHandler(counter)
        log.setLevel(old_level)
        monkeypatch.setattr(full_run.api, "execute_move", real_execute)
        monkeypatch.setattr(categories, "_run_complex_feature_type_ra_pass", real_pass)
    assert len(reported) == 1, "[FAIL] the TypeRA tail did not run exactly once"
    return plan, report, preview_rows, counter.wired, reported[0]


def _type_ra_skips(report):
    return [s for s in report.skips
            if s.source_guid in EXPECTED and "TypeRA" in (s.detail or "")]


def _seed_struct_types(monkeypatch) -> None:
    """Run 1: FEATURE_STRUCT_TYPES only -- the struct-types land, the complex
    features do not. Reaches #110's scenario: types pre-exist in the target."""
    before, before_types = _target_type_ra()
    assert before == {}, "[SETUP] sandbox already has the complex features"
    assert not set(EXPECTED.values()) & before_types
    _run(_TYPES_ONLY, monkeypatch)
    after, types = _target_type_ra()
    print("[LIVE] seed: complex features=%s, expected types present=%s"
          % (after, sorted(set(EXPECTED.values()) & types)))
    assert set(EXPECTED.values()) <= types, "[SETUP] struct-types did not land"
    assert after == {}, "[SETUP] seed run created the complex features too"


def test_preexisting_struct_types_writes_equal_wire_rows(monkeypatch):
    _seed_struct_types(monkeypatch)

    # Run 2: features + types. Types already exist, features are created.
    plan, report, rows, wired, writes = _run(_FEATURES_AND_TYPES, monkeypatch)
    print("\n".join(["[LIVE] preview run2:"] + rows))
    wire_rows = [r for r in rows if r.strip().startswith("Wire")]
    print("[LIVE] run2 wire_rows=%d reported_writes=%s wired_log=%d skips=%s"
          % (len(wire_rows), writes, len(wired), _type_ra_skips(report)))
    assert plan.complex_feature_type_refs == EXPECTED
    assert len(wire_rows) == len(EXPECTED)
    assert writes == len(wire_rows) == len(wired)
    assert _type_ra_skips(report) == []

    after, _ = _target_type_ra()
    print("[LIVE] post run2 %s" % after)
    assert after == EXPECTED          # read back: wired, by GUID, to source's type
    assert sum(1 for v in after.values() if v is not None) == writes

    # Run 3: idempotent -- nothing to write, nothing written.
    _p3, _r3, rows3, wired3, writes3 = _run(_FEATURES_AND_TYPES, monkeypatch)
    print("\n".join(["[LIVE] preview run3:"] + rows3))
    print("[LIVE] run3 reported_writes=%s wired_log=%d" % (writes3, len(wired3)))
    assert writes3 == 0 and wired3 == []
    assert all("SKIP (already wired)" in r for r in rows3[1:])
    assert _target_type_ra()[0] == EXPECTED


def test_mutation_create_path_second_writer_undercounts(monkeypatch):
    """Mutation check, pinned: re-add the pre-#110 create-path wiring (wire
    TypeRA at create time when the target struct-type exists). The data is
    still right, but the tail's reported count falls to 0 against 2 Wire
    rows -- the exact defect, and proof the count assertion above bites."""
    from gramtrans.Lib import categories
    from gramtrans.Lib.models import GrammarCategory

    _seed_struct_types(monkeypatch)

    bundle = categories.LEAF_CATEGORIES[GrammarCategory.INFLECTION_FEATURES]
    real_create = bundle["execute_action"]

    def _old_create(action, ctx, ws_map, tag):
        result = real_create(action, ctx, ws_map, tag)
        type_guid = EXPECTED.get(str(action.source_guid).lower())
        if result is not None and type_guid:
            from SIL.LCModel import ICmObject, IFsComplexFeature, IFsFeatStrucType
            fs = ctx.target_handle.Cache.LangProject.MsFeatureSystemOA
            for t in fs.TypesOC:
                if str(ICmObject(t).Guid).lower() == type_guid:
                    IFsComplexFeature(result).TypeRA = IFsFeatStrucType(t)
        return result

    monkeypatch.setitem(bundle, "execute_action", _old_create)
    _plan, _report, rows, wired, writes = _run(_FEATURES_AND_TYPES, monkeypatch)
    wire_rows = [r for r in rows if r.strip().startswith("Wire")]
    print("[LIVE] mutation: wire_rows=%d reported_writes=%s wired_log=%d"
          % (len(wire_rows), writes, len(wired)))
    assert _target_type_ra()[0] == EXPECTED   # data right ...
    assert len(wire_rows) == len(EXPECTED)
    assert writes == 0 and wired == []        # ... count wrong: the #110 defect
    assert writes != len(wire_rows)
