"""Issue #15 / spec 041 live gate -- opt-in LINK stale-reference re-point of
``IMoAffixAllomorph.MsEnvPartOfSpeechRA``.

Scenario (sandbox ``GT-Sandbox-15``, restored from the Target backup):
  run 1  full transfer (creates everything; ref wired at create time)
  DAMAGE null ``MsEnvPartOfSpeechRA`` on every target allomorph whose source
         counterpart has one (the stale-reference state)
  run 2  AFFIXES=LINK, flag OFF  -> 0 writes (LINK stays write-nothing)
  prev   AFFIXES=LINK, flag ON, preview_only -> N "Re-point" rows
  run 3  AFFIXES=LINK, flag ON   -> exactly N writes, state == run-1 snapshot
  run 4  flag ON again           -> 0 Re-point rows, 0 writes (idempotent)

WRITE PATH: writes ONLY ``GT-Sandbox-15`` (asserted before any write).
Source ``GT-Sandbox-15-Src`` is a disposable copy of Ejagham Mini (no real
project is written); the shipped corpora carry no MsEnvPartOfSpeechRA, so the
fixture sets it on a few affix allomorphs.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue15_link_repoint_live.py -v -s
"""
from __future__ import annotations

import dataclasses
import os
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_live_project]
if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1", allow_module_level=True)

SOURCE_NAME = "GT-Sandbox-15-Src"   # disposable, built from Ejagham Mini
SOURCE_BACKUP = "Ejagham Mini.fwbackup"
TARGET_NAME = "GT-Sandbox-15"
PROJECTS = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS / TARGET_NAME / (TARGET_NAME + ".fwdata"))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))
_REPO = Path(__file__).resolve().parents[2]


def _restore():
    from harness.restore import restore_target
    for d in (_REPO / "backups",
              Path("D:/Github/_Projects/_LEX/GramTrans/backups")):
        if (d / BACKUP_NAME).is_file():
            restore_target(TARGET_NAME, backup_path=d / BACKUP_NAME)
            return
    pytest.fail("backup not found")


def _build_source(n=3):
    """Restore the disposable source and give n affix allomorphs a
    MsEnvPartOfSpeechRA (the shipped corpora have none)."""
    from harness.restore import restore_target
    from gramtrans.Lib import categories as c
    for d in (_REPO / "backups",
              Path("D:/Github/_Projects/_LEX/GramTrans/backups")):
        if (d / SOURCE_BACKUP).is_file():
            restore_target(SOURCE_NAME, backup_path=d / SOURCE_BACKUP)
            break
    else:
        pytest.fail("source backup not found")
    p = _open(SOURCE_NAME, True)
    try:
        assert p.ProjectName() == SOURCE_NAME
        pos = next(iter(c._iter_all_pos(p)))
        done = 0
        for _g, a in _affix_allos(p):
            a.MsEnvPartOfSpeechRA = pos
            done += 1
            if done == n:
                break
        assert done == n
    finally:
        p.CloseProject()


@pytest.fixture(autouse=True)
def _around():
    _restore()
    yield
    _restore()


def _open(name, write):
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    p = FLExProject()
    if write:
        assert name in (TARGET_NAME, SOURCE_NAME)
        p.OpenProject(projectName=name, writeEnabled=True, undoable=False)
    else:
        p.OpenProject(projectName=name, writeEnabled=False)
    return p


def _affix_allos(p):
    from gramtrans.Lib import categories as c
    from gramtrans.Lib.owned import _cast_moaffix_allomorph
    for a in c._iter_all_allomorphs(p):
        if getattr(a, "ClassName", None) == "MoAffixAllomorph":
            yield c._guid_str_from(a), _cast_moaffix_allomorph(a)


def _state(name):
    from gramtrans.Lib import categories as c
    p = _open(name, False)
    try:
        out = {}
        for g, a in _affix_allos(p):
            r = a.MsEnvPartOfSpeechRA
            out[g] = c._guid_str_from(r) if r is not None else ""
        return out
    finally:
        p.CloseProject()


def _damage(source_state):
    p = _open(TARGET_NAME, True)
    try:
        assert p.ProjectName() == TARGET_NAME
        n = 0
        for g, a in _affix_allos(p):
            if source_state.get(g) and a.MsEnvPartOfSpeechRA is not None:
                a.MsEnvPartOfSpeechRA = None
                n += 1
        return n
    finally:
        p.CloseProject()


def _transform(flag):
    from gramtrans.Lib.models import ConflictMode, GrammarCategory

    def _t(sel):
        modes = dict(sel.category_conflict_modes)
        modes[GrammarCategory.AFFIXES] = ConflictMode.LINK
        return dataclasses.replace(
            sel, category_conflict_modes=modes, repoint_stale_refs=flag)
    return _t


def _move(flag, monkeypatch):
    from harness import full_run
    from gramtrans.Lib import transfer
    writes = []
    real = transfer._ensure_ref_repoint

    def _spy(ctx, tgt, skips):
        real(ctx, tgt, skips)
        writes.append(getattr(ctx, "_ref_repoint_writes", None))
    monkeypatch.setattr(transfer, "_ensure_ref_repoint", _spy)
    full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
        selection_transform=_transform(flag))
    monkeypatch.undo()
    return writes


def _preview_rows(monkeypatch):
    """Count Preview's "Re-point" rows. Rendered from inside the harness
    (handles close when run_full_transfer returns), via its plan hook."""
    from harness import full_run
    from gramtrans.Lib import preview
    seen = []
    real = full_run._dump_plan_composition

    def _hook(plan):
        real(plan)
        seen.append(preview.count_ref_repoints(plan))
    monkeypatch.setattr(full_run, "_dump_plan_composition", _hook)
    full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
        selection_transform=_transform(True), preview_only=True)
    monkeypatch.undo()
    return seen[-1]


def test_link_repoint_stale_allomorph_category(monkeypatch):
    _build_source()
    src = _state(SOURCE_NAME)
    src_set = {g: v for g, v in src.items() if v}
    _move(False, monkeypatch)                       # run 1
    snap = _state(TARGET_NAME)
    want = {g: v for g, v in snap.items() if src_set.get(g)}
    print("[LIVE] source allos with ref =", len(src_set),
          " run1 target same-guid with ref =",
          sum(1 for v in want.values() if v))
    assert any(want.values()), "scenario has no MsEnvPartOfSpeechRA to damage"

    n = _damage(src_set)
    dmg = _state(TARGET_NAME)
    print("[LIVE] DAMAGED (nulled) =", n,
          " refs now =", sum(1 for g in want if dmg.get(g)))
    assert n > 0

    off = _move(False, monkeypatch)                 # run 2, flag OFF
    after_off = _state(TARGET_NAME)
    print("[LIVE] run2 flag OFF writes =", off,
          " refs =", sum(1 for g in want if after_off.get(g)))
    assert after_off == dmg, "LINK without the flag must write nothing"

    rows = _preview_rows(monkeypatch)                          # Preview, flag ON
    after_prev = _state(TARGET_NAME)
    print("[LIVE] preview Re-point rows =", rows)
    assert after_prev == dmg, "Preview wrote"
    assert rows == n

    on = _move(True, monkeypatch)                   # run 3, flag ON
    fixed = _state(TARGET_NAME)
    print("[LIVE] run3 flag ON writes =", on,
          " refs =", sum(1 for g in want if fixed.get(g)))
    assert on and on[-1] == rows == n               # Preview == Move
    for g, v in want.items():
        assert fixed.get(g) == v, g

    assert _preview_rows(monkeypatch) == 0                     # idempotent
    again = _move(True, monkeypatch)                # run 4
    print("[LIVE] run4 writes =", again)
    assert again and again[-1] == 0
    assert _state(TARGET_NAME) == fixed
