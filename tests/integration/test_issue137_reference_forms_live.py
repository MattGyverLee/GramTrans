"""Issue #137 live gate -- a POS `ReferenceFormsOC` `IFsFeatStruc` arrives WITH
its `TypeRA` and `FeatureSpecsOC` (target-side GUID remapping), not as an empty
shell.

WRITE PATH: writes ONLY the private sandbox ``GT-Sandbox-137`` (restored
headlessly from a known backup before every test and again at the end). The
source ``Mbugwe LizzieHC practice`` is opened READ-ONLY. ``Target``,
``Esperanto`` and every other project are never touched.

Skips unless FLEXLIBS_REQUIRE_LIVE=1. When it is set, an unavailable LCM
FAILS rather than skips.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue137_reference_forms_live.py -v -s
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_live_project]

_LIVE = os.environ.get("FLEXLIBS_REQUIRE_LIVE") == "1"
if not _LIVE:
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "Mbugwe LizzieHC practice"        # READ-ONLY
TARGET_NAME = "GT-Sandbox-137"                  # the ONLY project this module writes
TARGET_PATH = ("C:/ProgramData/SIL/FieldWorks/Projects/GT-Sandbox-137/"
               "GT-Sandbox-137.fwdata")
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

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
    assert TARGET_NAME == "GT-Sandbox-137"
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


SEL_SEED = _sel("GRAM_CATEGORIES", "INFLECTION_FEATURES", "FEATURE_STRUCT_TYPES")


def _read_struc(struc, g):
    """{"type": guid, "pairs": {...}, "n": top-level spec count}. A complex
    spec contributes ("complex", feature, frozenset(nested pairs)) so nested
    values are compared too, not merely counted."""
    from SIL.LCModel import IFsClosedValue, IFsComplexValue, IFsFeatStruc
    fs = IFsFeatStruc(struc)
    pairs = set()
    n = 0
    for spec in fs.FeatureSpecsOC:
        n += 1
        try:
            cv = IFsClosedValue(spec)
            pairs.add((g(cv.FeatureRA), g(cv.ValueRA)))
            continue
        except Exception:  # noqa: BLE001 -- complex/other
            pass
        try:
            xv = IFsComplexValue(spec)
            if xv.ValueOA is not None:
                nested = _read_struc(xv.ValueOA, g)
                pairs.add(("complex", g(xv.FeatureRA),
                           frozenset(nested["pairs"]), nested["type"]))
        except Exception:  # noqa: BLE001 -- negated/disjunctive: not a pair
            pass
    return {"type": g(fs.TypeRA) if fs.TypeRA is not None else "",
            "pairs": pairs, "n": n}


def _reference_forms(project_name: str) -> dict:
    """{struc guid: {"type", "pairs", "n"}} over every POS ReferenceFormsOC,
    via a fresh read-only open."""
    from SIL.LCModel import ICmObject, IPartOfSpeech
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    proj = FLExProject()
    proj.OpenProject(projectName=project_name, writeEnabled=False)
    try:
        def g(o):
            return str(ICmObject(o).Guid).lower()
        out = {}
        for pos in proj.POS.GetAll(recursive=True):
            c = IPartOfSpeech(pos.concrete if hasattr(pos, "concrete") else pos)
            for rf in c.ReferenceFormsOC:
                out[g(rf)] = _read_struc(rf, g)
        return out
    finally:
        proj.CloseProject()


def test_reference_form_structs_arrive_with_type_and_specs():
    from harness import full_run

    src = _reference_forms(SOURCE_NAME)
    src_with_specs = {k: v for k, v in src.items() if v["n"]}
    pre = _reference_forms(TARGET_NAME)
    print("[LIVE] PRE  source ReferenceForms=%d (with specs=%d, spec total=%d); "
          "sandbox ReferenceForms=%d (with specs=%d)"
          % (len(src), len(src_with_specs),
             sum(v["n"] for v in src.values()), len(pre),
             sum(1 for v in pre.values() if v["n"])))
    assert src_with_specs, "[SETUP] source has no ReferenceForms with specs"

    plan, report = full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, selection_transform=SEL_SEED)
    post = _reference_forms(TARGET_NAME)
    print("[LIVE] POST sandbox ReferenceForms=%d (with specs=%d, spec total=%d)"
          % (len(post), sum(1 for v in post.values() if v["n"]),
             sum(v["n"] for v in post.values())))

    # A struc holding a negated/disjunctive/empty-complex spec is deferred WHOLE
    # by the shared resolver (FR-023, never silent: a DroppedItemRecord names
    # it). Those are out of scope for the copy and counted separately.
    unsupported = {k for k, v in src_with_specs.items()
                   if v["n"] != len(v["pairs"])}
    print("[LIVE] source strucs with a non-closed spec (reported, not copied)=%d"
          % len(unsupported))
    src_with_specs = {k: v for k, v in src_with_specs.items()
                      if k not in unsupported}
    missing = [k for k in src_with_specs if k not in post]
    hollow = [k for k, v in src_with_specs.items()
              if k in post and post[k]["n"] != v["n"]]
    wrong_type = [k for k, v in src_with_specs.items()
                  if k in post and post[k]["type"] != v["type"]]
    wrong_pairs = [k for k, v in src_with_specs.items()
                   if k in post and post[k]["pairs"] != v["pairs"]]
    print("[LIVE] missing=%d hollow=%d wrong_type=%d wrong_pairs=%d"
          % (len(missing), len(hollow), len(wrong_type), len(wrong_pairs)))
    assert not missing, "[FAIL] ReferenceForms struc not created: %s" % missing[:5]
    assert not hollow, "[FAIL] struc created without all its specs: %s" % hollow[:5]
    assert not wrong_type, "[FAIL] TypeRA differs: %s" % wrong_type[:5]
    assert not wrong_pairs, "[FAIL] feature/value pairs differ: %s" % wrong_pairs[:5]

    # Idempotent re-run: nothing duplicated, nothing lost.
    full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, selection_transform=SEL_SEED)
    again = _reference_forms(TARGET_NAME)
    assert again == post, "[FAIL] a second run changed the ReferenceForms"
    print("[PASS] ReferenceForms feature structures copied; re-run is a no-op")
