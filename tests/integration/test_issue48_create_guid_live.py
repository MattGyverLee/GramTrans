"""Issue #48 live gate -- Create(Guid) failures are reported truthfully.

WRITE PATH: opens the throwaway project ``Target`` write-enabled (and ONLY that
project).  ``Target`` is restored headlessly from a known backup before the run
and again at the end, so the run is repeatable and leaves nothing behind.

Skips unless FLEXLIBS_REQUIRE_LIVE=1.  When it is set, an unavailable LCM
(flexicon missing, project cannot be opened) FAILS rather than skips.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue48_create_guid_live.py -v -s
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_LIVE = os.environ.get("FLEXLIBS_REQUIRE_LIVE") == "1"
if not _LIVE:
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

TARGET_NAME = "Target"  # the ONLY project this module may open for writing
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
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
    import sys
    here = str(Path(__file__).parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    from harness.restore import restore_target
    restore_target(TARGET_NAME, backup_path=_backup_path())


@pytest.fixture(scope="module")
def target():
    try:
        import flexicon  # noqa: F401
        from flexicon import FLExProject
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is unavailable: %s" % exc)
    _restore()
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    proj = FLExProject()
    try:
        proj.OpenProject(projectName=TARGET_NAME, writeEnabled=True,
                         undoable=False)  # session NonUndoableTask, as production
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but cannot open %r: %s"
                    % (TARGET_NAME, exc))
    try:
        yield proj
    finally:
        try:
            proj.CloseProject()
        except Exception as exc:  # noqa: BLE001
            print("[WARN] CloseProject failed: %s" % exc)
        _restore()


def _phoneme_set(target):
    sets = target.Cache.LangProject.PhonologicalDataOA.PhonemeSetsOS
    assert len(sets) > 0, "[SETUP] Target has no phoneme set"
    return sets[0]


def _existing_phoneme_guid(pset) -> str:
    phonemes = list(pset.PhonemesOC)
    assert phonemes, "[SETUP] Target phoneme set has no phonemes"
    return str(phonemes[0].Guid)


def test_duplicate_guid_is_reported_truthfully_with_owner(target):
    from SIL.LCModel import IPhPhonemeFactory
    from gramtrans.Lib import categories

    pset = _phoneme_set(target)
    dup = _existing_phoneme_guid(pset)
    with pytest.raises(RuntimeError) as ei:
        categories._create_with_guid(IPhPhonemeFactory, pset.PhonemesOC, dup, target)
    msg = str(ei.value)
    print("[LIVE] _create_with_guid duplicate message: %s" % msg)
    assert "InvalidOperationException" in msg
    assert "identical GUID" in msg
    assert "does not support" not in msg
    assert ei.value.__cause__ is not None


def test_duplicate_guid_is_reported_truthfully_oa(target):
    from SIL.LCModel import IPhSimpleContextNCFactory
    from gramtrans.Lib import categories

    dup = _existing_phoneme_guid(_phoneme_set(target))
    with pytest.raises(RuntimeError) as ei:
        categories._create_with_guid_oa(IPhSimpleContextNCFactory, dup, target)
    msg = str(ei.value)
    print("[LIVE] _create_with_guid_oa duplicate message: %s" % msg)
    assert "InvalidOperationException" in msg
    assert "identical GUID" in msg
    assert "does not support" not in msg
    assert ei.value.__cause__ is not None


def test_normal_path_create_with_guid(target):
    from SIL.LCModel import IPhPhonemeFactory
    from gramtrans.Lib import categories

    pset = _phoneme_set(target)
    want = str(uuid.uuid4())
    new_obj, ok = categories._create_with_guid(
        IPhPhonemeFactory, pset.PhonemesOC, want, target)
    assert ok is True
    assert str(new_obj.Guid).lower() == want.lower()


def test_normal_path_create_with_guid_oa(target):
    from SIL.LCModel import IPhSimpleContextNCFactory
    from gramtrans.Lib import categories

    want = str(uuid.uuid4())
    new_obj = categories._create_with_guid_oa(IPhSimpleContextNCFactory, want, target)
    assert str(new_obj.Guid).lower() == want.lower()


def test_duplicate_guid_complex_feature_site(target):
    """The hand-rolled IFsComplexFeatureFactory site (issue #48, cycle 2): an
    already-present feature GUID must surface the real InvalidOperationException,
    not "does not support Create(Guid)".  The Create throws, so nothing is written."""
    import types
    from gramtrans.Lib import categories

    # Target has no feature defs; ANY live object's GUID collides in the
    # cache-wide identity map, so reuse an existing phoneme's.
    dup = _existing_phoneme_guid(_phoneme_set(target)).lower()
    src_feat = types.SimpleNamespace(guid=dup, ClassName="FsComplexFeature")
    source = types.SimpleNamespace(InflectionFeatures=types.SimpleNamespace(
        FeatureGetAll=lambda: [src_feat]))
    ctx = types.SimpleNamespace(source_handle=source, target_handle=target)
    with pytest.raises(RuntimeError) as ei:
        categories.inflection_features_execute_action(
            types.SimpleNamespace(source_guid=dup), ctx, {}, None)
    msg = str(ei.value)
    print("[LIVE] IFsComplexFeatureFactory duplicate message: %s" % msg)
    assert "InvalidOperationException" in msg
    assert "identical GUID" in msg
    assert "does not support" not in msg
    assert dup in msg
    assert ei.value.__cause__ is not None
