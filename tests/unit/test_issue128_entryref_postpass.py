"""Issue #128 (#114 follow-up) -- LexEntryRef value merge / C2 wiring on a
0-action re-run, and `Summary` copied as a run-preserving ITsString.

Covers:
- `transfer._ensure_entryref_passes` runs C1 (value merge) + C2 on a plan with
  ZERO actions, so an edited source `HideMinorEntry` / `Summary` reaches a ref
  that already exists; it is a no-op when the STEMS tail already ran (latches),
  idempotent on a second run, and never raises.
- `categories._tss_remap_ws_runs` keeps every run + its properties and
  translates each run's WS handle source -> target (embedded WS runs too).
- `_merge_entryref_value_fields` writes that ITsString (not plain text) when
  the destination is a live .NET multistring; source never blanks the target,
  a target-only alternative is never removed.

Host-free: SIL.LCModel / FwTextPropType are stubbed, ITsString is faked.
"""
from __future__ import annotations

import sys
import types

import pytest

from gramtrans.Lib import categories, transfer
from gramtrans.Lib.categories import (
    _merge_entryref_value_fields,
    _tss_remap_ws_runs,
)

from _fakes_entryref import ctx_create_and_wire, ref_record
from test_issue114_entryref_value_fields import (  # noqa: F401 -- fixture + fakes
    _Entry, _MultiString, _Ref, _Target, _stub_lcm,
)

KTPT_WS, KTPT_BASEWS, KTPT_BOLD = 1, 16, 3


# ---------------------------------------------------------------------------
# a faithful-enough ITsString / ITsStrBldr
# ---------------------------------------------------------------------------

class _Props:
    def __init__(self, ints):
        self.ints = dict(ints)

    def GetIntPropValues(self, tpt, _var):
        return (self.ints[tpt], 0) if tpt in self.ints else (-1, 0)


class _Tss:
    """Runs = [(text, {tpt: int})]."""

    def __init__(self, runs):
        self.runs = [(t, dict(p)) for t, p in runs]

    @property
    def Text(self):
        return "".join(t for t, _ in self.runs)

    @property
    def RunCount(self):
        return len(self.runs)

    def get_MinOfRun(self, i):
        return sum(len(t) for t, _ in self.runs[:i])

    def get_LimOfRun(self, i):
        return self.get_MinOfRun(i) + len(self.runs[i][0])

    def get_Properties(self, i):
        return _Props(self.runs[i][1])

    def GetBldr(self):
        return _Bldr(self)


class _Bldr:
    def __init__(self, tss):
        self.runs = [(t, dict(p)) for t, p in tss.runs]

    def SetIntPropValues(self, lo, lim, tpt, _var, val):
        pos = 0
        for t, p in self.runs:
            if pos == lo and pos + len(t) == lim:
                p[tpt] = val
            pos += len(t)

    def GetString(self):
        return _Tss(self.runs)


class _TssMultiString(_MultiString):
    """get_String returns whatever ITsString-like was stored."""

    def get_String(self, handle):
        v = self._data.get(handle)
        return v if v is not None else _Tss([])


@pytest.fixture
def _fw_props(monkeypatch):
    ki = types.ModuleType("SIL.LCModel.Core.KernelInterfaces")
    ki.FwTextPropType = types.SimpleNamespace(
        ktptWs=KTPT_WS, ktptBaseWs=KTPT_BASEWS, ktptBold=KTPT_BOLD)
    for name in ("SIL", "SIL.LCModel", "SIL.LCModel.Core"):
        monkeypatch.setitem(sys.modules, name,
                            sys.modules.get(name) or types.ModuleType(name))
    monkeypatch.setitem(sys.modules, "SIL.LCModel.Core.KernelInterfaces", ki)
    monkeypatch.setattr(categories, "_is_dotnet", lambda obj: True)


# source handles en=1 fr=2 ; target handles en=10 fr=11 (en->en, fr->fr)
SRC_IDS = {1: "en", 2: "fr"}
TGT_BY_ID = {"en": 10, "fr": 11}


def _multi_run_src():
    return _Tss([("Plain ", {KTPT_WS: 1}),
                 ("bold", {KTPT_WS: 1, KTPT_BOLD: 1}),
                 (" mot", {KTPT_WS: 2})])  # embedded fr run


# ---------------------------------------------------------------------------
# run preservation
# ---------------------------------------------------------------------------

def test_remap_keeps_every_run_and_property_and_translates_each_ws(_fw_props):
    out = _tss_remap_ws_runs(_multi_run_src(), 10, SRC_IDS, TGT_BY_ID, None)
    assert out.RunCount == 3
    assert out.Text == "Plain bold mot"
    assert [p for _, p in out.runs] == [
        {KTPT_WS: 10}, {KTPT_WS: 10, KTPT_BOLD: 1}, {KTPT_WS: 11}]


def test_remap_applies_ws_map_per_run(_fw_props):
    out = _tss_remap_ws_runs(_multi_run_src(), 12, SRC_IDS,
                             {"en-GB": 12, "fr": 11}, {"en": "en-GB"})
    assert [p[KTPT_WS] for _, p in out.runs] == [12, 12, 11]


def test_remap_unmapped_run_ws_falls_back_to_the_alt_handle_never_source(
        _fw_props):
    out = _tss_remap_ws_runs(_multi_run_src(), 10, SRC_IDS, {"en": 10}, None)
    assert [p[KTPT_WS] for _, p in out.runs] == [10, 10, 10]


def test_remap_does_not_mutate_the_source_string(_fw_props):
    src = _multi_run_src()
    _tss_remap_ws_runs(src, 10, SRC_IDS, TGT_BY_ID, None)
    assert [p[KTPT_WS] for _, p in src.runs] == [1, 1, 2]


def _rec_with_tss(src):
    rec = ref_record("ref-1", summary={"en": src.Text})
    rec["summary_tss"] = {"en": src}
    rec["summary_src_ws_ids"] = SRC_IDS
    return rec


def test_merge_writes_the_run_preserving_tss_not_plain_text(_fw_props):
    rec = _rec_with_tss(_multi_run_src())
    ref = _Ref("ref-1", summary=_TssMultiString())
    target = _Target({}, ws_pairs=(("en", 10), ("fr", 11)))
    dropped = []
    written = _merge_entryref_value_fields(rec, ref, target, None, dropped)

    assert written == ["Summary@en"] and dropped == []
    ((handle, value),) = ref.Summary.set_log
    assert handle == 10 and isinstance(value, _Tss)
    assert value.RunCount == 3
    assert [p.get(KTPT_BOLD) for _, p in value.runs] == [None, 1, None]


def test_merge_never_blanks_and_never_removes_a_target_only_alt(_fw_props):
    rec = _rec_with_tss(_multi_run_src())
    keep = _Tss([("target only", {KTPT_WS: 11})])
    ref = _Ref("ref-1", summary=_TssMultiString({11: keep}))
    target = _Target({}, ws_pairs=(("en", 10), ("fr", 11)))
    _merge_entryref_value_fields(rec, ref, target, None, [])
    assert ref.Summary.get_String(11) is keep           # untouched
    assert [h for h, _ in ref.Summary.set_log] == [10]  # only en written

    ref.Summary.set_log.clear()
    _merge_entryref_value_fields(ref_record("ref-1", summary={}), ref, target,
                                 None, [])                # empty source
    assert ref.Summary.set_log == []


def test_merge_idempotent_second_pass_writes_nothing(_fw_props):
    rec = _rec_with_tss(_multi_run_src())
    ref = _Ref("ref-1", summary=_TssMultiString())
    target = _Target({}, ws_pairs=(("en", 10), ("fr", 11)))
    _merge_entryref_value_fields(rec, ref, target, None, [])
    ref.Summary.set_log.clear()
    assert _merge_entryref_value_fields(rec, ref, target, None, []) == []
    assert ref.Summary.set_log == []


# ---------------------------------------------------------------------------
# 0-action re-run
# ---------------------------------------------------------------------------

def _ctx(records):
    ctx = ctx_create_and_wire({"entry-1": records})
    object.__setattr__(ctx, "_ws_map", None)
    object.__setattr__(ctx, "_exec_skips", [])
    ctx._run_plan.actions = []  # ZERO planned actions: every entry present
    return ctx


def test_zero_action_rerun_merges_edited_hide_and_summary(_stub_lcm):
    existing = _Ref("ref-1", hide=0, summary=_MultiString({10: "old"}))
    target = _Target({"entry-1": _Entry("entry-1", refs=[existing])})
    ctx = _ctx([ref_record("ref-1", hide_minor_entry=1,
                           summary={"en": "edited"})])

    transfer._ensure_entryref_passes(ctx, target, None, ctx._exec_skips)

    assert existing.HideMinorEntry == 1
    assert existing.Summary.get_String(10).Text == "edited"
    assert target.factory.created == []  # nothing created on a re-run


def test_zero_action_rerun_second_pass_makes_zero_writes(_stub_lcm):
    existing = _Ref("ref-1", hide=0, summary=_MultiString({10: "old"}))
    target = _Target({"entry-1": _Entry("entry-1", refs=[existing])})
    recs = [ref_record("ref-1", hide_minor_entry=1, summary={"en": "edited"})]

    transfer._ensure_entryref_passes(_ctx(recs), target, None, [])
    hide_sets, sets = existing.hide_sets, len(existing.Summary.set_log)
    transfer._ensure_entryref_passes(_ctx(recs), target, None, [])

    assert (existing.hide_sets, len(existing.Summary.set_log)) == (hide_sets, sets)


def test_ensure_is_a_noop_when_the_stems_tail_already_ran(_stub_lcm):
    existing = _Ref("ref-1", hide=0)
    target = _Target({"entry-1": _Entry("entry-1", refs=[existing])})
    ctx = _ctx([ref_record("ref-1", hide_minor_entry=1)])
    object.__setattr__(ctx, "_did_entryref_create_pass", True)
    object.__setattr__(ctx, "_did_post_pass_a", True)

    transfer._ensure_entryref_passes(ctx, target, None, [])

    assert existing.hide_sets == 0


def test_ensure_with_no_lexicon_in_scope_is_a_noop(_stub_lcm):
    target = _Target({})
    ctx = _ctx([])
    ctx._run_plan.entryref_create_bindings = {}
    transfer._ensure_entryref_passes(ctx, target, None, ctx._exec_skips)
    assert ctx._exec_skips == []


def test_ensure_never_raises(_stub_lcm, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(categories, "_run_entryref_create_pass", boom)
    ctx = _ctx([ref_record("ref-1")])
    transfer._ensure_entryref_passes(ctx, _Target({}), None, [])  # no raise
