"""Issue #56 live gate -- Carrier A on real LCM objects is unchanged.

`residue.apply_carrier_a` now decides between an ITsString write and a
plain-text write on WHAT `LiftResidue` is (`texts._is_dotnet_object`), not on
whether `SIL.LCModel.Core.Text` is importable. This module proves the live
behaviour did not move:

1. A real `LexExampleSentence` (a CARRIER_A_CLASSES member): `LiftResidue` is
   a Unicode single-string on LCM 9.x, so the write takes the setattr path and
   the tag round-trips -- including across a close/reopen (persistence).
2. A genuine .NET multistring in the `LiftResidue` slot: the write is a real
   `ITsString` built by `TsStringUtils.MakeString` and reads back as the
   serialized tag at the requested writing system.

WRITE PATH: opens the throwaway project ``GT056 Target`` write-enabled (and
ONLY that project). It is restored headlessly from a known backup before the
run and again at the end, so the run is repeatable and leaves nothing behind.

Skips unless FLEXLIBS_REQUIRE_LIVE=1.  When it is set, an unavailable LCM
(flexicon missing, project cannot be opened) FAILS rather than skips.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue56_carrier_a_live.py -v -s
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_LIVE = os.environ.get("FLEXLIBS_REQUIRE_LIVE") == "1"
if not _LIVE:
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

TARGET_NAME = "GT056 Target"  # the ONLY project this module may open for writing
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (
    _REPO / "backups",
    Path("D:/Github/_Projects/_LEX/GramTrans/backups"),
)

TAG_ARGS = dict(run_id="GT-20261030-120000", source_project_name="Issue56 Source",
                timestamp="2026-10-30T12:00:00")


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


def _open():
    from flexicon import FLExProject
    proj = FLExProject()
    try:
        proj.OpenProject(projectName=TARGET_NAME, writeEnabled=True,
                         undoable=False)  # session NonUndoableTask, as production
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but cannot open %r: %s"
                    % (TARGET_NAME, exc))
    return proj


@pytest.fixture(scope="module")
def live():
    try:
        import flexicon  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is unavailable: %s" % exc)
    _restore()
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    state = {"proj": _open()}
    try:
        yield state
    finally:
        try:
            state["proj"].CloseProject()
        except Exception as exc:  # noqa: BLE001
            print("[WARN] CloseProject failed: %s" % exc)
        _restore()


def _first_example(proj):
    """An existing LexExampleSentence, or a fresh one under a new entry's sense
    (the Target backup has an empty lexicon)."""
    from SIL.LCModel import (ILexExampleSentence, ILexExampleSentenceRepository,
                             ILexExampleSentenceFactory, ILexSenseRepository)
    sl = proj.Cache.ServiceLocator
    for ex in sl.GetService(ILexExampleSentenceRepository).AllInstances():
        return ILexExampleSentence(ex)
    senses = list(sl.GetService(ILexSenseRepository).AllInstances())
    if not senses:
        entry = proj.LexEntry.Create("gtfiftysix")  # creates a blank sense
        senses = list(entry.SensesOS)
    assert senses, "[SETUP] could not obtain a sense to hang an example on"
    ex = sl.GetService(ILexExampleSentenceFactory).Create()
    senses[0].ExamplesOS.Add(ex)
    return ILexExampleSentence(ex)


def test_live_example_sentence_lift_residue_round_trips(live):
    from SIL.LCModel import ICmObject, ILexExampleSentence
    from gramtrans.Lib.residue import ImportResidueTag, apply_residue
    from gramtrans.Lib.texts import _is_dotnet_object

    proj = live["proj"]
    tag = ImportResidueTag.make(**TAG_ARGS)
    ex = _first_example(proj)
    guid = str(ICmObject(ex).Guid)
    before = ex.LiftResidue
    print("[LIVE] example %s ClassName=%s LiftResidue before=%r (type %s, dotnet=%s)"
          % (guid, ICmObject(ex).ClassName, before, type(before).__name__,
             _is_dotnet_object(before)))
    assert before is None or isinstance(before, str), (
        "LCM 9.x LiftResidue is expected to be a Unicode single-string")

    apply_residue(ex, proj.Cache.DefaultAnalWs, tag, class_name="LexExampleSentence")
    after = ex.LiftResidue
    print("[LIVE] LiftResidue after apply_residue=%r" % after)
    assert after == tag.serialize()
    assert ImportResidueTag.parse(after) == tag

    # Persistence: close, reopen fresh, re-read by GUID.
    proj.CloseProject()
    live["proj"] = proj = _open()
    from System import Guid
    reread = ILexExampleSentence(
        proj.Cache.ServiceLocator.ObjectRepository.GetObject(Guid.Parse(guid)))
    print("[LIVE] LiftResidue after reopen=%r" % reread.LiftResidue)
    assert ImportResidueTag.parse(reread.LiftResidue) == tag


def test_live_dotnet_multistring_still_gets_an_itsstring(live):
    """Carrier A's multistring branch on a GENUINE .NET multistring (the
    example's `Example` field, standing in the `LiftResidue` slot) writes a
    real ITsString -- the live half of the branch is unchanged."""
    from gramtrans.Lib.residue import ImportResidueTag, apply_carrier_a
    from gramtrans.Lib.texts import _is_dotnet_object

    proj = live["proj"]
    tag = ImportResidueTag.make(**TAG_ARGS)
    ex = _first_example(proj)
    ms = ex.Example
    assert _is_dotnet_object(ms), "[SETUP] Example is not a .NET multistring"

    class _Carrier:  # pure-Python holder; the multistring itself is live
        LiftResidue = ms

    ws = proj.Cache.DefaultVernWs
    assert apply_carrier_a(_Carrier(), ws, tag) is True
    got = ms.get_String(ws)
    print("[LIVE] Example[%s] after apply_carrier_a: %r (type %s)"
          % (ws, got.Text, type(got).__name__))
    assert _is_dotnet_object(got)
    assert got.Text == tag.serialize()
    from SIL.LCModel.Core.KernelInterfaces import FwTextPropType
    run_ws = got.get_PropertiesAt(0).GetIntPropValues(int(FwTextPropType.ktptWs))[0]
    print("[LIVE] run-0 ws=%s (requested %s)" % (run_ws, ws))
    assert run_ws == ws
