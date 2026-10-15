"""Writing-system path fidelity: issues #44, #46, #53, #69.

Four defects on the same path -- a source writing system the target lacks, or
has under a different id -- each of which either lost content without a
report, reported a loss that had not happened, or crashed the Move:

* #44 -- `_ensure_writing_systems` downgraded a failed WS create to a log
  warning, treated a tag that is in the LDML store but not ACTIVE as already
  present, and `debuglog` discarded every flexicon log record.
* #46 -- a reversal alt in a WS absent from the target escaped as a .NET
  `ArgumentNullException` and aborted the Move mid-write.
* #53 -- the `.fwdictconfig` scan checked raw source WS ids, so a WS the user
  explicitly mapped (`etu-x-Tone -> etu`) was still reported absent.
* #69 -- `phase2_interactive_move` skipped the WS pre-pass, so a WS-wizard
  CREATE choice on that path was never carried out.

All host-free: no SIL.LCModel / pythonnet, no FLEx project.
"""
from __future__ import annotations

import logging
import os

import pytest

from _fakes_ws import FakeWS, FakeWSOps, make_project
from gramtrans.Lib import api as api_mod
from gramtrans.Lib import config_views
from gramtrans.Lib import debuglog
from gramtrans.Lib import flexinit
from gramtrans.Lib import reversals
from gramtrans.Lib import transfer as transfer_mod
from gramtrans.Lib.models import (
    ConfigViewAction,
    RunContext,
    RunMode,
    RunPlan,
    RunReport,
    Selection,
    WSKind,
    WSMapping,
    WSMappingEntry,
)

# Imported at collection time (not inside the test) so a broken host import
# surfaces as a collection error/skip, not a mid-test failure.
try:
    from gramtrans import gramtrans as _gt
    import api as _flat_api  # the flat module gramtrans.py imports lazily
except ImportError as _exc:  # pragma: no cover - host-only modules
    _gt = _flat_api = None
    _GT_IMPORT_ERROR = str(_exc)
else:
    _GT_IMPORT_ERROR = ""


# ============================================================================
# #44 -- _ensure_writing_systems: store vs active, and failures are reported
# ============================================================================

_FakeWS = FakeWS
_StoreVsActiveWSOps = FakeWSOps  # flexicon >= 4.8.0 semantics


@pytest.fixture()
def store_ops(monkeypatch):
    monkeypatch.setattr("flexicon.WritingSystemOperations", _StoreVsActiveWSOps,
                        raising=False)
    monkeypatch.setattr(api_mod, "_persist_without_close", lambda proj, what: None)


def _ctx_plan(target, tags):
    ctx = RunContext(
        source_handle=None, source_project_name="S", source_project_path="",
        target_handle=target, target_project_name="T", target_project_path="",
        run_id="GT-20261015-120000", started_at="2026-10-15T12:00:00",
    )
    entries = tuple(
        WSMappingEntry(source_ws_id=t, source_ws_kind=WSKind.VERNACULAR,
                       target_ws_id=t, create_in_target=True)
        for t in tags
    )
    return ctx, RunPlan(context=ctx, selection=Selection(),
                        ws_mapping=WSMapping(entries=entries), actions=())


def test_stored_but_inactive_ws_is_activated_not_reported(store_ops):
    target = make_project(["etu"], store=["etu", "mgz-fonipa"])
    _, plan = _ctx_plan(target, ["mgz-fonipa"])
    failures = []

    created = api_mod._ensure_writing_systems(target, None, plan, failures)

    assert created == ["mgz-fonipa"]
    assert failures == []
    assert target["activated"] == ["mgz-fonipa"] and target["created"] == []
    assert "mgz-fonipa" in target["active"]


def test_failed_create_is_reported(store_ops):
    target = make_project(["etu"], refuse=["fr-Zxxx-x-audio"])
    _, plan = _ctx_plan(target, ["fr-Zxxx-x-audio", "pt"])
    failures = []

    created = api_mod._ensure_writing_systems(target, None, plan, failures)

    assert created == ["pt"], "one bad tag must not stop the others"
    assert [f.item_name for f in failures] == ["fr-Zxxx-x-audio"]
    assert "RuntimeError" in failures[0].reason


def test_active_ws_is_still_skipped_silently(store_ops):
    target = make_project(["etu"])
    _, plan = _ctx_plan(target, ["etu"])
    failures = []
    assert api_mod._ensure_writing_systems(target, None, plan, failures) == []
    assert failures == []
    assert target["created"] == []


def test_execute_move_puts_ws_failures_on_the_report(store_ops, monkeypatch):
    target = make_project(["etu"], refuse=["fr-Zxxx-x-audio"])
    ctx, plan = _ctx_plan(target, ["fr-Zxxx-x-audio"])
    monkeypatch.setattr(
        transfer_mod, "execute",
        lambda plan, source, target, sink, tag:
            RunReport(context=plan.context, mode=RunMode.MOVE),
    )

    report = api_mod.execute_move(ctx, plan)

    assert [d.item_name for d in report.dropped_items] == ["fr-Zxxx-x-audio"]
    assert report.dropped_items[0].owner_kind == "WritingSystem"


def test_debuglog_configures_the_flexicon_logger():
    assert "flexicon" in debuglog.LOGGER_NAMES
    # flexicon modules log under `__name__`, i.e. children of "flexicon".
    child = logging.getLogger("flexicon.code.FLExInit")
    assert child.parent is logging.getLogger("flexicon") or \
        child.name.startswith("flexicon.")


# ============================================================================
# #46 -- reversal alts in a WS absent from the target
# ============================================================================

class _FakeTs:
    def __init__(self, text):
        self.Text = text or None


class _FakeMultiString:
    def __init__(self, data):
        self._data = dict(data)

    def get_String(self, ws_handle):  # noqa: N802
        return _FakeTs(self._data.get(ws_handle))


class _WS:
    def __init__(self, ws_id, handle):
        self.Id = ws_id
        self.Handle = handle


class _WSRepo:
    def __init__(self, ws):
        self._ws = list(ws)

    def GetAll(self):  # noqa: N802
        return list(self._ws)


class _Indexes:
    def __init__(self, idx=()):
        self._idx = list(idx)

    def GetAll(self):  # noqa: N802
        return list(self._idx)


class _Project:
    def __init__(self, ws, indexes=()):
        self.WritingSystems = _WSRepo(ws)
        self.ReversalIndexes = _Indexes(indexes)


class _Sense:
    def __init__(self, guid):
        self.Guid = self.guid = guid


class _Entry:
    def __init__(self, guid, senses, alts):
        self.Guid = self.guid = guid
        self.SensesRS = list(senses)
        self.ReversalForm = _FakeMultiString(alts)
        self.PartOfSpeechRA = None
        self.SubentriesOS = []


class _Index:
    def __init__(self, guid, ws, entries):
        self.Guid = self.guid = guid
        self.WritingSystem = ws
        self.EntriesOC = list(entries)
        self.PartsOfSpeechOA = None


class _Ctx:
    _ws_map: dict = {}


def test_reversal_alt_in_absent_ws_is_gated_and_reported():
    """The index's own WS (`en`) passes the gate; the entry's etic alt does
    not exist in the target. It must be dropped AND reported at decision
    time, never handed to the write path."""
    entry = _Entry("e1", [_Sense("s1")], {1: "run", 2: "[ɾʌn]"})
    src = _Project([_WS("en", 1), _WS("mgz-fonipa-x-etic", 2)],
                   [_Index("idx", "en", [entry])])
    target = _Project([_WS("en", 10)])
    dropped = []

    decisions = reversals.plan_reversals({"s1"}, src, target, _Ctx(), {}, dropped)

    assert decisions[0].reversal_form_alts == {"en": "run"}
    alt_drops = [d for d in dropped if d.field_name == "ReversalForm"]
    assert len(alt_drops) == 1
    assert alt_drops[0].item_name == "mgz-fonipa-x-etic"
    assert "absent in target" in alt_drops[0].reason


def test_apply_reversals_never_raises_and_reports(monkeypatch):
    """Whatever an entry's apply raises -- .NET exceptions are not
    `TypeError` -- `apply_reversals` records it and carries on, as its
    docstring promises."""
    class _DotNetLike(Exception):
        pass

    def _boom(*a, **k):
        raise _DotNetLike("Value cannot be null.")

    monkeypatch.setattr(reversals, "_apply_one_entry", _boom)
    entry = _Entry("e1", [_Sense("s1")], {1: "run"})
    src = _Project([_WS("en", 1)], [_Index("idx", "en", [entry])])
    target = _Project([_WS("en", 10)])
    decisions = reversals.plan_reversals({"s1"}, src, target, _Ctx(), {}, [])
    dropped = []

    reversals.apply_reversals(decisions + decisions, target, _Ctx(), None, {}, dropped)

    assert len(dropped) == 2
    assert all("_DotNetLike" in d.reason for d in dropped)


def test_set_reversal_form_alt_reports_a_handle_miss(monkeypatch):
    """Live branch: `WSHandle` returns None for an absent WS. The write must
    record a drop rather than build a TsString from a null handle."""
    monkeypatch.setattr(reversals._texts, "_is_dotnet_object", lambda obj: True)

    import sys
    import types
    fake_text = types.ModuleType("SIL.LCModel.Core.Text")

    class _Ts:
        @staticmethod
        def MakeString(text, ws):  # noqa: N802
            raise AssertionError("must not be reached with a null handle")

    fake_text.TsStringUtils = _Ts
    monkeypatch.setitem(sys.modules, "SIL.LCModel.Core.Text", fake_text)

    class _Target:
        def WSHandle(self, ws_id):  # noqa: N802
            return None

    class _Ms:
        def set_String(self, *a):  # noqa: N802
            raise AssertionError("must not be written")

    class _NewEntry:
        ReversalForm = _Ms()

    dropped = []
    reversals._set_reversal_form_alt(_NewEntry(), _Target(), "zz-absent", "x",
                                     dropped, "e1")
    assert len(dropped) == 1
    assert dropped[0].item_name == "zz-absent"
    assert dropped[0].owner_guid == "e1"


# ============================================================================
# #53 -- .fwdictconfig WS references go through the mapping
# ============================================================================

class _CVWSCollection:
    def __init__(self, ids):
        self._ids = list(ids)

    def GetAll(self):  # noqa: N802
        return [_FakeWS(i) for i in self._ids]


class _CVProject:
    def __init__(self, project_dir, ws_ids):
        self.ProjectFolder = str(project_dir)
        self.WritingSystems = _CVWSCollection(ws_ids)


_TONE_CONFIG = """<?xml version="1.0" encoding="utf-8"?>
<DictionaryConfiguration name="Lexeme" writingSystem="etu-x-Tone" version="26">
  <ConfigurationItem name="Headword" field="MLHeadWord">
    <WritingSystemOptions writingSystemType="vernacular">
      <Option id="etu-x-Tone" isEnabled="true" />
      <Option id="vernacular" isEnabled="false" />
    </WritingSystemOptions>
  </ConfigurationItem>
  <ConfigurationItem name="Note" field="etu-x-Tone">
  </ConfigurationItem>
</DictionaryConfiguration>
"""


def _dict_file(project_dir, body):
    d = os.path.join(project_dir, "ConfigurationSettings", "Dictionary")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "Lexeme.fwdictconfig")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(body)
    return path


def test_mapped_ws_is_not_reported_absent(tmp_path):
    _dict_file(tmp_path / "Src", _TONE_CONFIG)
    src = _CVProject(tmp_path / "Src", ["etu-x-Tone"])
    tgt = _CVProject(tmp_path / "Tgt", ["etu"])

    unmapped = config_views.plan_config_views(src, tgt)
    assert [r.item_name for r in unmapped[0].missing_refs] == ["etu-x-Tone"]

    mapped = config_views.plan_config_views(src, tgt, ws_map={"etu-x-Tone": "etu"})
    assert mapped[0].missing_refs == []
    assert mapped[0].ws_renames == {"etu-x-Tone": "etu"}


def test_mapped_to_absent_target_names_both_ids(tmp_path):
    _dict_file(tmp_path / "Src", _TONE_CONFIG)
    src = _CVProject(tmp_path / "Src", ["etu-x-Tone"])
    tgt = _CVProject(tmp_path / "Tgt", ["en"])

    recs = config_views.plan_config_views(src, tgt, ws_map={"etu-x-Tone": "etu"})
    reasons = [r.reason for r in recs[0].missing_refs]
    assert reasons == ["writing system 'etu-x-Tone' (mapped to 'etu') absent in target"]


def test_copied_config_carries_the_target_ws_id(tmp_path):
    _dict_file(tmp_path / "Src", _TONE_CONFIG)
    src = _CVProject(tmp_path / "Src", ["etu-x-Tone"])
    tgt = _CVProject(tmp_path / "Tgt", ["etu"])
    recs = config_views.plan_config_views(src, tgt, ws_map={"etu-x-Tone": "etu"})
    assert recs[0].action is ConfigViewAction.ADD

    config_views.apply_config_views(recs, [])

    with open(recs[0].tgt_path, encoding="utf-8") as fh:
        out = fh.read()
    assert 'writingSystem="etu"' in out
    assert '<Option id="etu" isEnabled="true" />' in out
    # Only WS-id positions are rewritten -- a field= value spelling the same
    # tag, and the magic group token, are left alone.
    assert 'field="etu-x-Tone"' in out
    assert '<Option id="vernacular"' in out
    assert out == _TONE_CONFIG.replace('writingSystem="etu-x-Tone"', 'writingSystem="etu"') \
                              .replace('<Option id="etu-x-Tone"', '<Option id="etu"')

    # Re-planning against the now-populated target is a SKIP: the comparison
    # is against the rewritten bytes, not the source file.
    again = config_views.plan_config_views(src, tgt, ws_map={"etu-x-Tone": "etu"})
    assert again[0].action is ConfigViewAction.SKIP


# ============================================================================
# #69 -- phase2_interactive_move runs the WS pre-pass
# ============================================================================

def run_phase2_with_ws_failure(monkeypatch, patched_api):
    """Drive `phase2_interactive_move` with `patched_api._ensure_writing_systems`
    faked to report one WS failure. Returns `(calls, result, report)`."""
    gt = _gt
    calls = []

    class _Src:
        def OpenProject(self, **kw):  # noqa: N802
            pass

        def CloseProject(self):  # noqa: N802
            pass

    class _Tgt:
        def ProjectName(self):  # noqa: N802
            return "Target"

    class _Report:
        def __init__(self):
            self.warnings = []

        def Info(self, msg):  # noqa: N802
            pass

        def Warning(self, msg):  # noqa: N802
            self.warnings.append(msg)

        def Blank(self):  # noqa: N802
            pass

    class _Plan:
        actions = overwrites = skips = ()

    failure = api_mod._ws_create_failure("fr-Zxxx-x-audio", "RuntimeError: no")

    def _fake_ensure(proj, source, plan, failures=None):
        calls.append("ws")
        failures.append(failure)
        return []

    def _fake_execute(plan, source, target, report, tag, interactive_session=None):
        calls.append("execute")
        return RunReport(context=None, mode=RunMode.MOVE)

    monkeypatch.setattr(flexinit, "ensure_sldr_initialized", lambda: None)
    monkeypatch.setattr(gt, "FLExProject", _Src)
    monkeypatch.setattr(gt, "_safe_project_path", lambda p: "")
    monkeypatch.setattr(gt, "detect_ws_mismatches", lambda s, t: [])
    monkeypatch.setattr(gt, "default_ws_choices", lambda s, t: ())
    monkeypatch.setattr(gt, "build_run_plan", lambda *a, **k: _Plan())
    monkeypatch.setattr(gt, "collect_overwrite_conflicts", lambda *a: [])
    monkeypatch.setattr(gt, "execute", _fake_execute)
    monkeypatch.setattr(gt, "render_text_summary", lambda r: [])
    monkeypatch.setattr(patched_api, "_ensure_writing_systems", _fake_ensure)

    report = _Report()
    result = gt.phase2_interactive_move(_Tgt(), report, True, source_project_name="S")
    return calls, result, report


@pytest.mark.skipif(_gt is None, reason=f"gramtrans host imports unavailable: {_GT_IMPORT_ERROR}")
def test_phase2_interactive_move_runs_ws_prepass(monkeypatch):
    calls, result, report = run_phase2_with_ws_failure(monkeypatch, _flat_api)

    assert calls == ["ws", "execute"], "WS pre-pass must run before execute"
    assert [d.item_name for d in result.dropped_items] == ["fr-Zxxx-x-audio"]
    assert any("fr-Zxxx-x-audio" in w for w in report.warnings)
