"""Issue #55 live gate -- GOLD_RESERVED merge still writes a real ITsString.

The fix makes `_execute_gold_reserved_merge` branch on the OBJECT
(`texts._is_dotnet_object`) instead of on whether `TsStringUtils` imports.
This module proves the LIVE branch is unchanged: against a real LCM
multistring, a write_mode="merge" overwrite fills the empty target slot with
the source text, tagged with the TARGET's writing-system handle, and the
value survives CloseProject + reopen.

WRITE PATH: writes ONLY the throwaway project ``GT055 Target`` (restored
headlessly from ``Target 2026-07-06 0218.fwbackup`` first). The source
``Ejagham Mini`` is opened READ-ONLY. Skips unless FLEXLIBS_REQUIRE_LIVE=1;
when set, an unavailable LCM FAILS rather than skips.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue55_gold_merge_live.py -v -s
"""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "Ejagham Mini"    # READ-ONLY
TARGET_NAME = "GT055 Target"    # the ONLY project this module writes
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
_FIELDS = ("Name", "Abbreviation", "Description")

sys.path.insert(0, str(Path(__file__).parent))


def _restore():
    from harness.restore import restore_target
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            restore_target(TARGET_NAME, backup_path=d / BACKUP_NAME)
            return
    pytest.fail("[FAIL] backup %r not found" % BACKUP_NAME)


def _open(name, write):
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    proj = FLExProject()
    try:
        if write:
            proj.OpenProject(projectName=name, writeEnabled=True, undoable=False)
        else:
            proj.OpenProject(projectName=name, writeEnabled=False)
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but cannot open %r: %s" % (name, exc))
    return proj


def _variant_types(proj):
    from gramtrans.Lib.categories import _guid_str_from, _walk_possibilities
    lst = proj.Cache.LangProject.LexDbOA.VariantEntryTypesOA
    return {_guid_str_from(o): o for o in _walk_possibilities(lst)}


def _text(ms, handle):
    ts = ms.get_String(handle)
    return getattr(ts, "Text", None) if ts is not None else None


def test_gold_reserved_merge_writes_itsstring_on_live_lcm():
    from gramtrans.Lib import texts, transfer
    from gramtrans.Lib.models import GrammarCategory, PlannedOverwrite

    _restore()
    source = _open(SOURCE_NAME, write=False)
    target = _open(TARGET_NAME, write=True)
    from SIL.LCModel.Core.Text import TsStringUtils  # loaded by the open
    try:
        src_items = _variant_types(source)
        tgt_items = _variant_types(target)
        src_ws = {w.Id: w.Handle for w in source.WritingSystems.GetAll()}
        tgt_ws = {w.Id: w.Handle for w in target.WritingSystems.GetAll()}
        common_ws = sorted(set(src_ws) & set(tgt_ws))
        assert common_ws, "[SETUP] no shared writing system"

        # Pick a shared variant type with source text in some shared WS slot.
        pick = None
        for guid in sorted(set(src_items) & set(tgt_items)):
            for field in _FIELDS:
                for ws_id in common_ws:
                    if _text(getattr(src_items[guid], field), src_ws[ws_id]):
                        pick = (guid, field, ws_id)
                        break
                if pick:
                    break
            if pick:
                break
        assert pick, "[SETUP] no shared variant type with source text"
        guid, field, ws_id = pick
        src_obj, tgt_obj = src_items[guid], tgt_items[guid]
        h = tgt_ws[ws_id]

        # Setup: blank that slot in the throwaway target so merge must fill it.
        tgt_ms = getattr(tgt_obj, field)
        tgt_ms.set_String(h, TsStringUtils.EmptyString(h))
        assert not _text(tgt_ms, h)
        assert texts._is_dotnet_object(tgt_ms), "live multistring must be .NET"

        # Every (field, ws) slot the merge should fill: source text, target empty.
        expected = {}
        for f in _FIELDS:
            for w in common_ws:
                s = _text(getattr(src_obj, f), src_ws[w])
                if s and not _text(getattr(tgt_obj, f), tgt_ws[w]):
                    expected[(f, w)] = s
        assert (field, ws_id) in expected

        class _Sink:
            def __init__(self):
                self.info, self.warnings = [], []

            def Info(self, m):  # noqa: N802
                self.info.append(m)

            def Warning(self, m):  # noqa: N802
                self.warnings.append(m)

        sink = _Sink()
        ow = PlannedOverwrite(category=GrammarCategory.VARIANT_TYPES,
                              source_guid=guid, target_guid=guid,
                              summary="issue55 live", write_mode="merge")
        transfer._execute_overwrite(
            ow, source, target, sink,
            types.SimpleNamespace(run_id="gt055", serialize=lambda: "t",
                                  with_snapshot=lambda p: None))

        print("[LIVE] variant type %s  field=%s ws=%s(handle %s)" % (guid, field, ws_id, h))
        print("[LIVE] sink info=%s warnings=%s" % (sink.info, sink.warnings))
        assert sink.warnings == []
        assert any("filled %d WS slot(s)" % len(expected) in m for m in sink.info)

        for (f, w), s in expected.items():
            ts = getattr(tgt_obj, f).get_String(tgt_ws[w])
            assert type(ts).__name__ != "str"
            assert ts.Text == s
            assert TsStringUtils.GetWsAtOffset(ts, 0) == tgt_ws[w]
            print("[LIVE] in-session %s@%s = %r (%s, ws handle %s)"
                  % (f, w, ts.Text, type(ts).__name__, TsStringUtils.GetWsAtOffset(ts, 0)))
    finally:
        source.CloseProject()
        target.CloseProject()

    # Persistence: reopen read-only and read the slot back.
    again = _open(TARGET_NAME, write=False)
    try:
        h2 = {w.Id: w.Handle for w in again.WritingSystems.GetAll()}[ws_id]
        got = _text(getattr(_variant_types(again)[guid], field), h2)
        print("[LIVE] after reopen %s@%s = %r" % (field, ws_id, got))
        assert got == expected[(field, ws_id)]
    finally:
        again.CloseProject()
