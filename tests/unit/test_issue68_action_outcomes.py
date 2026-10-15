"""Issue #68: RunReport `added` is built from dispatch OUTCOMES, not the plan.

A leaf `execute_action` that declines (e.g. stem_names with no owner POS in
the destination) used to return None and still be counted as 'added'. Handlers
now return `ActionOutcome.skipped/failed`; a None / created-object legacy
return still counts as added.
"""
from __future__ import annotations

import sys
import types

import pytest

import gramtrans.Lib.categories as categories
import gramtrans.Lib.transfer as transfer
from gramtrans.Lib.models import (
    ActionOutcome,
    GrammarCategory,
    PlannedAction,
    RunContext,
    RunPlan,
    Selection,
    SkipReason,
    WSMapping,
)
from gramtrans.Lib.report import disposition_totals


class _Sink:
    def __init__(self):
        self.messages = []

    def Info(self, m): self.messages.append(("I", m))
    def Warning(self, m): self.messages.append(("W", m))
    def Error(self, m): self.messages.append(("E", m))
    def Blank(self): pass


def _ctx():
    return RunContext(
        source_handle=object(), source_project_name="S", source_project_path="/s",
        target_handle=object(), target_project_name="T", target_project_path="/t",
        run_id="GT-20261015-120000", started_at="2026-10-15T12:00:00",
    )


def _plan(guids, category=GrammarCategory.STEM_NAMES):
    return RunPlan(
        context=_ctx(), selection=Selection(), ws_mapping=WSMapping(entries=()),
        actions=tuple(
            PlannedAction(category=category, source_guid=g,
                          intended_target_guid=g, summary="x")
            for g in guids),
    )


@pytest.fixture
def _quiet_tail(monkeypatch):
    """Neutralise the post-dispatch passes so execute() runs on bare fakes."""
    monkeypatch.setattr(categories, "reproduce_all_lexical_relations",
                        lambda *a, **k: None)
    monkeypatch.setattr(categories, "reproduce_reversal_entries",
                        lambda *a, **k: None)
    monkeypatch.setattr(transfer, "_ensure_171_subpass", lambda *a, **k: None)
    monkeypatch.setattr(transfer, "_ensure_owner_feat_strucs",
                        lambda *a, **k: None)


def _run(monkeypatch, handler, guids):
    monkeypatch.setattr(
        categories, "for_category", lambda cat: {"execute_action": handler})
    plan = _plan(guids)
    return transfer.execute(plan, object(), object(), _Sink(), tag=None)


def test_decline_is_skipped_never_added(monkeypatch, _quiet_tail):
    def handler(action, ctx, ws, tag):
        if action.source_guid == "declined":
            return ActionOutcome.skipped("owner POS missing")
        return None  # legacy success

    rep = _run(monkeypatch, handler, ["ok", "declined"])
    cat = rep.per_category[GrammarCategory.STEM_NAMES]
    assert cat.added == 1
    assert cat.skipped == 1
    assert [s.source_guid for s in rep.skips] == ["declined"]
    assert rep.skips[0].reason is SkipReason.DEPENDENCY_UNRESOLVED
    assert "owner POS missing" in rep.skips[0].detail
    assert rep.leaf_failed == 0
    d = disposition_totals(rep)
    assert d["add_created"] == 1 and d["add_created_written"] == 1


def test_explicit_failed_outcome_is_a_leaf_failure_not_added(monkeypatch, _quiet_tail):
    def handler(action, ctx, ws, tag):
        return ActionOutcome.failed("create refused")

    rep = _run(monkeypatch, handler, ["a"])
    cat = rep.per_category[GrammarCategory.STEM_NAMES]
    assert cat.added == 0
    assert rep.leaf_failed == 1
    assert rep.leaf_execution_failures[0].exception_type == "ActionFailed"
    assert rep.leaf_execution_failures[0].message == "create refused"
    assert GrammarCategory.STEM_NAMES not in rep.empty_categories


def test_raised_exception_is_not_counted_as_added(monkeypatch, _quiet_tail):
    def handler(action, ctx, ws, tag):
        if action.source_guid == "boom":
            raise RuntimeError("boom")
        return object()  # legacy: created object -> added

    rep = _run(monkeypatch, handler, ["ok", "boom"])
    assert rep.per_category[GrammarCategory.STEM_NAMES].added == 1
    assert rep.leaf_failed == 1
    d = disposition_totals(rep)
    assert d["add_created"] == 2          # attempted creates, declines excluded
    assert d["add_write_failed"] == 1
    assert d["add_created_written"] == 1  # not subtracted twice
    assert d["create_split_reconciles"] is True


def test_recorded_outcome_does_not_double_record_the_skip(monkeypatch, _quiet_tail):
    def handler(action, ctx, ws, tag):
        return ActionOutcome.skipped("already recorded", recorded=True)

    rep = _run(monkeypatch, handler, ["a"])
    assert rep.per_category[GrammarCategory.STEM_NAMES].added == 0
    assert rep.skips == ()  # handler's own exec_skips entry is the only record


def test_outcome_requires_reason():
    with pytest.raises(ValueError):
        ActionOutcome.skipped("")
    with pytest.raises(ValueError):
        ActionOutcome.failed("")


# ---------------------------------------------------------------------------
# The real handler: a missing owner POS is skipped, never added.
# ---------------------------------------------------------------------------

class _SN:
    def __init__(self, guid): self.guid = guid


class _POS:
    def __init__(self, guid, sns=()):
        self.guid = guid
        self.Guid = guid
        self.StemNamesOC = list(sns)

    @property
    def concrete(self):
        return self


class _POSOps:
    def __init__(self, poses): self._p = list(poses)
    def GetAll(self, recursive=True): return list(self._p)


class _Proj:
    def __init__(self, poses=()): self.POS = _POSOps(poses)


def test_stem_names_missing_owner_pos_is_skipped(monkeypatch):
    monkeypatch.setattr(categories, "_guid_str_from",
                        lambda o: str(getattr(o, "guid", "")).lower())
    ident = lambda o: o  # noqa: E731
    fake_lcm = types.ModuleType("SIL.LCModel")
    for n in ("IMoStemNameFactory", "IMoStemName", "IPartOfSpeech", "ICmObject"):
        setattr(fake_lcm, n, ident)
    fake_system = types.ModuleType("System")
    fake_system.Guid = type("G", (), {"Parse": staticmethod(lambda s: s)})
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    monkeypatch.setitem(sys.modules, "SIL.LCModel", fake_lcm)
    monkeypatch.setitem(sys.modules, "System", fake_system)

    src = _Proj([_POS("pos-a", [_SN("sn-1")])])
    tgt = _Proj([])  # owner POS absent in the destination
    ctx = RunContext(
        source_handle=src, source_project_name="S", source_project_path="/s",
        target_handle=tgt, target_project_name="T", target_project_path="/t",
        run_id="GT-20261015-120000", started_at="2026-10-15T12:00:00")
    action = PlannedAction(category=GrammarCategory.STEM_NAMES,
                           source_guid="sn-1", intended_target_guid="sn-1",
                           summary="x")

    result = categories.stem_names_execute_action(action, ctx, WSMapping(), None)

    assert isinstance(result, ActionOutcome)
    assert result.status == "skipped"
    assert "owner part of speech" in result.reason


# ---------------------------------------------------------------------------
# #45/#49/#68 (cycle 3 P1-a): stems_execute_action mirrors the affixes sibling.
# ---------------------------------------------------------------------------

def _stem_ctx():
    return RunContext(
        source_handle=object(), source_project_name="S", source_project_path="/s",
        target_handle=object(), target_project_name="T", target_project_path="/t",
        run_id="GT-20261015-120000", started_at="2026-10-15T12:00:00")


def _stem_action():
    return PlannedAction(category=GrammarCategory.STEMS, source_guid="g-1",
                         intended_target_guid="g-1", summary="x")


def test_stems_missing_source_entry_is_skipped(monkeypatch):
    monkeypatch.setattr(categories, "_iter_lex_entries", lambda s: ())
    tails = []
    monkeypatch.setattr(categories, "_run_tail_once",
                        lambda *a, **k: tails.append(a))
    result = categories.stems_execute_action(
        _stem_action(), _stem_ctx(), WSMapping(), None)
    assert isinstance(result, ActionOutcome)
    assert result.status == "skipped"
    assert "not found" in result.reason


def test_stems_declined_closure_is_skipped(monkeypatch):
    entry = types.SimpleNamespace(guid="g-1")
    monkeypatch.setattr(categories, "_iter_lex_entries", lambda s: [entry])
    monkeypatch.setattr(categories, "_find_target_obj_by_guid",
                        lambda it, g: entry)
    monkeypatch.setattr(categories, "_walk_lex_entry_closure",
                        lambda *a, **k: None)
    monkeypatch.setattr(categories, "_run_tail_once", lambda *a, **k: None)
    result = categories.stems_execute_action(
        _stem_action(), _stem_ctx(), WSMapping(), None)
    assert isinstance(result, ActionOutcome)
    assert result.status == "skipped"
    assert "declined" in result.reason


# ---------------------------------------------------------------------------
# Cycle 3 P2-a: `recorded` reflects whether a Skip was really appended.
# ---------------------------------------------------------------------------

def _pos_decline_setup(monkeypatch, exec_skips):
    """inflection_classes_execute_action with an owner POS absent in the
    destination (`_resolve_target_pos` -> None) -- one of the five sites that
    used to hard-code recorded=True."""
    ident = lambda o: o  # noqa: E731
    fake_lcm = types.ModuleType("SIL.LCModel")
    for n in ("IMoInflClassFactory", "IMoInflClass", "ICmObject"):
        setattr(fake_lcm, n, ident)
    fake_system = types.ModuleType("System")
    fake_system.Guid = type("G", (), {"Parse": staticmethod(lambda s: s)})
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    monkeypatch.setitem(sys.modules, "SIL.LCModel", fake_lcm)
    monkeypatch.setitem(sys.modules, "System", fake_system)
    ic = types.SimpleNamespace(guid="ic-1")
    pos = types.SimpleNamespace(guid="pos-a")
    monkeypatch.setattr(categories, "_guid_str_from",
                        lambda o: str(getattr(o, "guid", "")).lower())
    monkeypatch.setattr(categories, "_iter_pos", lambda h: [pos])
    monkeypatch.setattr(categories, "_as_pos", lambda p: p)
    monkeypatch.setattr(categories, "_inflection_classes_from_pos",
                        lambda p: [ic])
    monkeypatch.setattr(categories, "_resolve_target_pos",
                        lambda *a, **k: None)
    ctx = RunContext(
        source_handle=object(), source_project_name="S",
        source_project_path="/s", target_handle=object(),
        target_project_name="T", target_project_path="/t",
        run_id="GT-20261015-120000", started_at="2026-10-15T12:00:00")
    if exec_skips is not None:
        object.__setattr__(ctx, "_exec_skips", exec_skips)
    action = PlannedAction(category=GrammarCategory.INFLECTION_CLASSES,
                           source_guid="ic-1", intended_target_guid="ic-1",
                           summary="x")
    return ctx, action


def test_pos_decline_without_exec_skips_is_not_marked_recorded(monkeypatch):
    ctx, action = _pos_decline_setup(monkeypatch, None)
    res = categories.inflection_classes_execute_action(action, ctx, WSMapping(), None)
    assert res.status == "skipped"
    # No Skip was appended anywhere, so the engine must still record one.
    assert res.recorded is False


def test_pos_decline_with_exec_skips_is_marked_recorded(monkeypatch):
    skips = []
    ctx, action = _pos_decline_setup(monkeypatch, skips)
    res = categories.inflection_classes_execute_action(
        action, ctx, WSMapping(), None)
    assert res.recorded is True and len(skips) == 1


def test_pos_decline_engine_records_exactly_one_skip(monkeypatch, _quiet_tail):
    """End to end through transfer.execute: exactly one Skip, never zero (lost)
    and never two (double-counted), and nothing counted as added."""
    ctx, action = _pos_decline_setup(monkeypatch, None)
    monkeypatch.setattr(
        categories, "for_category",
        lambda cat: {"execute_action":
                     categories.inflection_classes_execute_action})
    plan = RunPlan(context=ctx, selection=Selection(),
                   ws_mapping=WSMapping(entries=()), actions=(action,))
    rep = transfer.execute(plan, ctx.source_handle, ctx.target_handle,
                           _Sink(), tag=None)
    ic_skips = [s for s in rep.skips
                if s.category == GrammarCategory.INFLECTION_CLASSES]
    assert len(ic_skips) == 1
    assert rep.per_category[GrammarCategory.INFLECTION_CLASSES].added == 0
