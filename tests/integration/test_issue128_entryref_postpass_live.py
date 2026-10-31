"""Issue #128 live gate -- LexEntryRef value merge on a 0-action re-run, and a
run-preserving `Summary`.

WRITE PATH: writes ONLY two private throwaways, both restored headlessly from
``Target 2026-07-06 0218.fwbackup`` (``harness.restore.restore_target``):

* ``GT-Src-128``     -- the SOURCE, authored here: a stem + a complex-form
  entry whose LexEntryRef carries a MULTI-RUN ``Summary`` (a bold run, a
  named-style run and an embedded run in a second writing system).
* ``GT-Sandbox-128`` -- the TARGET.

Nothing else is opened write-enabled (asserted before every write open).

Sequence (the one test, because each step depends on the last):

1. Move 1 copies both entries + the ref; the target Summary has the SAME
   runs as the source (text, per-run WS id, bold, style).
2. Edit the source ref's ``HideMinorEntry`` (0 -> 1) and ``Summary`` text.
   Move 2 plans ZERO actions (every entry is already present) yet the edit
   still lands on the existing target ref, runs intact.
3. Move 3 (nothing changed) writes nothing: the target ref's XML is
   byte-identical.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue128_entryref_postpass_live.py -v -s

SKIPS when FLEXLIBS_REQUIRE_LIVE != 1; under FLEXLIBS_REQUIRE_LIVE=1 a missing
backup/flexicon FAILS (never a quiet skip).
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)
if importlib.util.find_spec("flexicon") is None:
    pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is not importable",
                pytrace=False)

PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
SOURCE_NAME = "GT-Src-128"
TARGET_NAME = "GT-Sandbox-128"
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))

_REF_RT = re.compile(
    r'<rt class="LexEntryRef" guid="([^"]+)" ownerguid="([^"]+)">(.*?)</rt>', re.S)

MAIN_WS, SECOND_WS = "en", "etu"
STYLE = "Emphasized Text"
# (text, ws_id, bold, style) per run -- the authored multi-run Summary.
SUMMARY_V1 = "Summary BOLD styled etu"
SUMMARY_V2 = "EDITED BOLD styled etu"


def _restore(name):
    assert name in (SOURCE_NAME, TARGET_NAME), name  # pinned before any write
    from harness.restore import restore_target
    path = _REPO / "backups" / BACKUP_NAME
    if not path.is_file():
        pytest.fail("[FAIL] backup %s not found" % path, pytrace=False)
    restore_target(name, backup_path=path)


def _open(name, write=False):
    if write:
        assert name in (SOURCE_NAME, TARGET_NAME), name  # never anything else
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
        pytest.fail("[FAIL] cannot open %r: %s" % (name, exc), pytrace=False)
    return proj


def _handle(proj, ws_id):
    for ws in proj.WritingSystems.GetAll():
        if ws.Id == ws_id:
            return ws.Handle
    pytest.fail("[FAIL] %s has no writing system %r" % (proj, ws_id), pytrace=False)


def _ref(proj, guid):
    from SIL.LCModel import ICmObjectRepository, ILexEntryRef
    from System import Guid
    repo = proj.ObjectRepository(ICmObjectRepository)
    return ILexEntryRef(repo.GetObject(Guid.Parse(guid)))


def _author_summary(proj, ref, text):
    """Multi-run Summary on the main WS: plain / bold / named style / an
    embedded run in the second WS; plus a separate second-WS alternative."""
    from SIL.LCModel.Core.KernelInterfaces import FwTextPropType, FwTextPropVar
    from SIL.LCModel.Core.Text import TsStringUtils
    en, etu = _handle(proj, MAIN_WS), _handle(proj, SECOND_WS)
    bldr = TsStringUtils.MakeString(text, en).GetBldr()
    i_bold = text.index("BOLD")
    i_sty = text.index("styled")
    i_etu = text.rindex("etu")
    bldr.SetIntPropValues(i_bold, i_bold + 4, int(FwTextPropType.ktptBold),
                          int(FwTextPropVar.ktpvEnum), 1)
    bldr.SetStrPropValue(i_sty, i_sty + 6, int(FwTextPropType.ktptNamedStyle), STYLE)
    bldr.SetIntPropValues(i_etu, i_etu + 3, int(FwTextPropType.ktptWs),
                          int(FwTextPropVar.ktpvDefault), etu)
    ref.Summary.set_String(en, bldr.GetString())
    ref.Summary.set_String(etu, TsStringUtils.MakeString("second-ws alt", etu))


def _runs(proj, ref, ws_id):
    """[(text, run_ws_id, bold, style)] of one Summary alternative."""
    from SIL.LCModel.Core.KernelInterfaces import FwTextPropType
    id_by_handle = {w.Handle: w.Id for w in proj.WritingSystems.GetAll()}
    tss = ref.Summary.get_String(_handle(proj, ws_id))
    out = []
    for i in range(int(tss.RunCount)):
        props = tss.get_Properties(i)
        ws = props.GetIntPropValues(int(FwTextPropType.ktptWs), 0)
        bold = props.GetIntPropValues(int(FwTextPropType.ktptBold), 0)
        ws = ws[0] if isinstance(ws, tuple) else ws
        bold = bold[0] if isinstance(bold, tuple) else bold
        style = props.GetStrPropValue(int(FwTextPropType.ktptNamedStyle))
        out.append((str(tss.get_RunText(i)), id_by_handle.get(int(ws)),
                    int(bold) if int(bold) != -1 else 0,
                    str(style) if style else None))
    return out


def _values(name, ref_guid):
    proj = _open(name)
    try:
        ref = _ref(proj, ref_guid)
        return {
            "hide": int(ref.HideMinorEntry),
            "main": _runs(proj, ref, MAIN_WS),
            "second": str(ref.Summary.get_String(_handle(proj, SECOND_WS)).Text),
        }
    finally:
        proj.CloseProject()


def _ref_body(ref_guid):
    txt = Path(TARGET_PATH).read_text(encoding="utf-8")
    for m in _REF_RT.finditer(txt):
        if m.group(1).lower() == ref_guid.lower():
            return m.group(0)
    return None


def _selection(picks):
    from gramtrans.Lib.models import GrammarCategory as GC, Selection
    return Selection(categories={GC.STEMS: True, GC.AFFIXES: True},
                     include_closure=True,
                     leaf_item_picks={GC.STEMS: frozenset(picks),
                                      GC.AFFIXES: frozenset(picks)})


def _move(picks):
    from harness import full_run
    return full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, ws_mapping_mode="full",
        selection_transform=lambda _full: _selection(picks))


def _value_drops(report):
    return [(d.owner_guid, d.field_name, d.reason)
            for d in report.dropped_items or ()
            if d.owner_kind == "LexEntryRef"
            and d.field_name in ("HideMinorEntry", "Summary")]


def test_zero_action_rerun_carries_edits_and_summary_runs_are_preserved():
    import flexicon
    import gramtrans
    print("[LIVE] gramtrans.__file__ =", gramtrans.__file__)
    print("[LIVE] flexicon.__file__  =", flexicon.__file__)
    _restore(SOURCE_NAME)
    _restore(TARGET_NAME)

    # ---- author the source ------------------------------------------------
    proj = _open(SOURCE_NAME, write=True)
    try:
        comp = proj.LexEntry.Create("gt128comp")
        cform = proj.LexEntry.Create("gt128 complexform")
        proj.LexEntry.AddComplexFormComponent(cform, comp)
        ref = cform.EntryRefsOS[0]
        _author_summary(proj, ref, SUMMARY_V1)
        comp_guid, cform_guid = str(comp.Guid), str(cform.Guid)
        ref_guid = str(ref.Guid)
    finally:
        proj.CloseProject()
    picks = {comp_guid, cform_guid}
    src_v1 = _values(SOURCE_NAME, ref_guid)
    print("[LIVE] source v1:", src_v1)
    assert len(src_v1["main"]) >= 4, "source not multi-run: %s" % src_v1["main"]
    assert any(r[2] == 1 for r in src_v1["main"]), "no bold run authored"
    assert any(r[3] == STYLE for r in src_v1["main"]), "no styled run authored"
    assert any(r[1] == SECOND_WS for r in src_v1["main"]), "no embedded WS run"
    assert _ref_body(ref_guid) is None, "sandbox not clean"

    # ---- Move 1: copy ------------------------------------------------------
    plan1, report1 = _move(picks)
    t1 = _values(TARGET_NAME, ref_guid)
    print("[LIVE] move#1 actions=%d drops=%s target=%s" % (
        len(plan1.actions), _value_drops(report1), t1))
    assert len(plan1.actions) >= 2
    assert _value_drops(report1) == []
    assert t1 == src_v1, "Summary runs not preserved on create"

    # ---- edit the source, Move 2 (0 actions) -------------------------------
    proj = _open(SOURCE_NAME, write=True)
    try:
        ref = _ref(proj, ref_guid)
        ref.HideMinorEntry = 1
        _author_summary(proj, ref, SUMMARY_V2)
    finally:
        proj.CloseProject()
    src_v2 = _values(SOURCE_NAME, ref_guid)
    assert src_v2["hide"] == 1 and src_v2 != src_v1

    plan2, report2 = _move(picks)
    t2 = _values(TARGET_NAME, ref_guid)
    print("[LIVE] move#2 actions=%d drops=%s target=%s" % (
        len(plan2.actions), _value_drops(report2), t2))
    assert len(plan2.actions) == 0, "Move 2 must plan 0 STEMS actions"
    assert _value_drops(report2) == []
    assert t2["hide"] == 1, "HideMinorEntry edit did not land on a 0-action run"
    assert t2 == src_v2, "Summary edit/runs did not land on a 0-action run"
    assert any(r[2] == 1 for r in t2["main"]) and any(
        r[3] == STYLE for r in t2["main"]) and any(
        r[1] == SECOND_WS for r in t2["main"])

    # ---- Move 3: nothing changed -> zero writes ----------------------------
    body = _ref_body(ref_guid)
    assert body
    plan3, report3 = _move(picks)
    print("[LIVE] move#3 actions=%d drops=%s" % (
        len(plan3.actions), _value_drops(report3)))
    assert len(plan3.actions) == 0
    assert _value_drops(report3) == []
    assert _ref_body(ref_guid) == body, "Move 3 rewrote the target ref"
    assert _values(TARGET_NAME, ref_guid) == src_v2
