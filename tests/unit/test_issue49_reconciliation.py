"""Issue #49: reconciliation pass, template/slot outcomes, visible planner drops."""
from __future__ import annotations

import sys
import types

import pytest

import gramtrans.Lib.categories as categories
import gramtrans.Lib.preview as preview
import gramtrans.Lib.transfer as transfer
from gramtrans.Lib.models import (
    ActionOutcome, GrammarCategory, PlannedAction, RunContext, RunPlan,
    Selection, SkipReason, WSMapping,
)


class _Sink:
    def Info(self, m): pass
    def Warning(self, m): pass
    def Error(self, m): pass
    def Blank(self): pass


def _ctx():
    return RunContext(
        source_handle=object(), source_project_name="S", source_project_path="/s",
        target_handle=object(), target_project_name="T", target_project_path="/t",
        run_id="GT-20261015-120000", started_at="2026-10-15T12:00:00",
    )


@pytest.fixture
def _fake_lcm(monkeypatch):
    lcm = types.ModuleType("SIL.LCModel")
    for n in ("IMoInflAffixTemplateFactory", "IMoInflAffixTemplate", "ICmObject"):
        setattr(lcm, n, lambda o: o)
    sysmod = types.ModuleType("System")
    sysmod.Guid = type("G", (), {"Parse": staticmethod(lambda s: s)})
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    monkeypatch.setitem(sys.modules, "SIL.LCModel", lcm)
    monkeypatch.setitem(sys.modules, "System", sysmod)


@pytest.fixture
def _quiet_tail(monkeypatch):
    monkeypatch.setattr(categories, "reproduce_all_lexical_relations", lambda *a, **k: None)
    monkeypatch.setattr(categories, "reproduce_reversal_entries", lambda *a, **k: None)
    monkeypatch.setattr(transfer, "_ensure_171_subpass", lambda *a, **k: None)
    monkeypatch.setattr(transfer, "_ensure_owner_feat_strucs", lambda *a, **k: None)


class _Target:
    """Fake target with a GUID repository."""
    def __init__(self, present):
        self.present = set(present)

    def get_object_by_guid(self, guid):
        return object() if guid in self.present else None


def _act(guid, cat=GrammarCategory.SLOTS):
    return PlannedAction(category=cat, source_guid=guid,
                         intended_target_guid=guid, summary="x")


def test_reconcile_flags_only_absent_objects():
    t = _Target({"a"})
    miss = transfer.reconcile_added_actions(t, [(_act("a"), "a"), (_act("b"), "b")])
    assert [(c, g) for c, g, _ in miss] == [(GrammarCategory.SLOTS, "b")]
    assert "not found" in miss[0][2]


def test_reconcile_exempts_custom_fields_and_unverifiable_targets():
    t = _Target(set())
    cf = _act("x", GrammarCategory.CUSTOM_FIELDS)
    assert transfer.reconcile_added_actions(t, [(cf, "x")]) == []
    assert transfer.reconcile_added_actions(object(), [(_act("a"), "a")]) == []


def test_execute_downgrades_phantom_add_to_failed(monkeypatch, _quiet_tail):
    monkeypatch.setattr(categories, "for_category",
                        lambda cat: {"execute_action": lambda *a: None})
    plan = RunPlan(context=_ctx(), selection=Selection(), ws_mapping=WSMapping(entries=()),
                   actions=(_act("real"), _act("phantom")))
    rep = transfer.execute(plan, object(), _Target({"real"}), _Sink(), tag=None)
    assert rep.per_category[GrammarCategory.SLOTS].added == 1
    assert rep.leaf_failed == 1
    f = rep.leaf_execution_failures[0]
    assert f.source_guid == "phantom" and f.exception_type == "UnverifiedWrite"


def test_template_handler_declines_when_source_missing(monkeypatch, _fake_lcm):
    monkeypatch.setattr(categories, "_iter_pos", lambda h: [])
    monkeypatch.setattr(categories, "_run_tail_once", lambda *a, **k: None)
    out = categories.affix_templates_execute_action(
        _act("zz", GrammarCategory.AFFIX_TEMPLATES), _ctx(), None, None)
    assert isinstance(out, ActionOutcome) and out.status == "skipped"


def test_template_handler_declines_when_owner_pos_missing(monkeypatch, _fake_lcm):
    class _Pos:
        AffixTemplatesOS = [type("T", (), {"Guid": "zz"})()]
    monkeypatch.setattr(categories, "_iter_pos", lambda h: [_Pos()])
    monkeypatch.setattr(categories, "_as_pos", lambda p: p)
    monkeypatch.setattr(categories, "_guid_str_from", lambda o: getattr(o, "Guid", "pos"))
    monkeypatch.setattr(categories, "_resolve_target_pos", lambda *a, **k: None)
    monkeypatch.setattr(categories, "_report_owner_pos_unresolved", lambda *a, **k: None)
    monkeypatch.setattr(categories, "_run_tail_once", lambda *a, **k: None)
    ctx = _ctx()
    out = categories.affix_templates_execute_action(
        _act("zz", GrammarCategory.AFFIX_TEMPLATES), ctx, None, None)
    # Cycle 3 P2-a: no _exec_skips on this bare context, so nothing was
    # recorded and the engine must record the skip itself.
    assert out.status == "skipped" and out.recorded is False
    object.__setattr__(ctx, "_exec_skips", [])
    out = categories.affix_templates_execute_action(
        _act("zz", GrammarCategory.AFFIX_TEMPLATES), ctx, None, None)
    assert out.status == "skipped" and out.recorded is True


def test_planner_reports_undispatched_and_empty_pick_categories():
    sel = Selection(categories={c: True for c in (
        GrammarCategory.POS, GrammarCategory.ENTRY, GrammarCategory.SENSE,
        GrammarCategory.MSA, GrammarCategory.ALLOMORPH)}, include_closure=True)
    plan = preview.build_run_plan(_ctx_with_src(), sel, WSMapping(entries=()),
                                  _FakeProj(), _FakeProj())
    by_cat = {s.category: s for s in plan.skips}
    # Issue #84: the four lexicon categories are no longer "not dispatched";
    # they are planned as AFFIXES + STEMS and the plan says so.
    for c in (GrammarCategory.ENTRY, GrammarCategory.SENSE,
              GrammarCategory.MSA, GrammarCategory.ALLOMORPH):
        assert c not in by_cat
    assert not any("not dispatched" in s.detail for s in plan.skips)
    assert plan.selection.is_on(GrammarCategory.AFFIXES)
    assert plan.selection.is_on(GrammarCategory.STEMS)
    assert any("affixes + stems" in n for n in plan.category_notes)
    assert "pos_picks is empty" in by_cat[GrammarCategory.POS].detail
    assert not any(a.category in (GrammarCategory.ENTRY,) for a in plan.actions)


class _FakeProj:
    def __getattr__(self, name):
        raise AttributeError(name)


def _ctx_with_src():
    return _ctx()


# ---------------------------------------------------------------------------
# Cycle 3 (P1-b / P1-c): expected-GUID derivation and lookup failures.
# ---------------------------------------------------------------------------

def test_remapped_create_is_not_flagged_unverified(monkeypatch, _quiet_tail):
    """A handler that created under a remapped GUID wrote; the remapped GUID
    (not the source GUID) is what must exist in the target."""
    plan = RunPlan(context=_ctx(), selection=Selection(),
                   ws_mapping=WSMapping(entries=()),
                   actions=(_act("src-1"),), identity_remap={})

    def _handler(action, ctx, ws, tag):
        plan.identity_remap["src-1"] = "new-1"   # create-under-new-GUID
        return None

    monkeypatch.setattr(categories, "for_category",
                        lambda cat: {"execute_action": _handler})
    rep = transfer.execute(plan, object(), _Target({"new-1"}), _Sink(), tag=None)
    assert rep.leaf_failed == 0
    assert rep.per_category[GrammarCategory.SLOTS].added == 1


def test_reconcile_uses_remapped_guid_and_still_flags_absent():
    t = _Target({"new-1"})
    assert transfer.reconcile_added_actions(
        t, [(_act("src-1"), None)], identity_remap={"src-1": "new-1"}) == []
    miss = transfer.reconcile_added_actions(
        t, [(_act("src-2"), None)], identity_remap={"src-1": "new-1"})
    assert [g for _, g, _ in miss] == ["src-2"]


def test_reconcile_resolved_destination_guid_wins_over_source_guid():
    """The planned (resolved) destination GUID is the expected one, even when
    the source GUID happens to be absent from the target."""
    t = _Target({"dest-9"})
    assert transfer.reconcile_added_actions(
        t, [(_act("src-1"), "dest-9")]) == []
    miss = transfer.reconcile_added_actions(
        _Target({"src-1"}), [(_act("src-1"), "dest-9")])
    assert [g for _, g, _ in miss] == ["src-1"]
    assert "dest-9" in miss[0][2]


def test_execute_uses_resolved_destination_guid(monkeypatch, _quiet_tail):
    dest = transfer.PlannedDestination(
        outcome=transfer.DESTINATION_RESOLVED, obj=object(),
        target_guid="dest-9", object_class="X", basis=None, detail="")
    monkeypatch.setattr(transfer, "planned_destination_for",
                        lambda item, target, **k: dest)
    monkeypatch.setattr(categories, "for_category",
                        lambda cat: {"execute_action": lambda *a: None})
    plan = RunPlan(context=_ctx(), selection=Selection(),
                   ws_mapping=WSMapping(entries=()), actions=(_act("src-1"),))
    rep = transfer.execute(plan, object(), _Target({"dest-9"}), _Sink(), tag=None)
    assert rep.leaf_failed == 0


def test_lookup_exception_is_logged_and_reported_unverified(
        monkeypatch, _quiet_tail, caplog):
    class _Boom(_Target):
        def get_object_by_guid(self, guid):
            if guid == "bad":
                raise RuntimeError("repo exploded")
            return super().get_object_by_guid(guid)

    monkeypatch.setattr(categories, "for_category",
                        lambda cat: {"execute_action": lambda *a: None})
    plan = RunPlan(context=_ctx(), selection=Selection(),
                   ws_mapping=WSMapping(entries=()),
                   actions=(_act("ok"), _act("bad")))
    with caplog.at_level("WARNING", logger=transfer.__name__):
        rep = transfer.execute(plan, object(), _Boom({"ok"}), _Sink(), tag=None)
    assert any("UNVERIFIED" in r.getMessage() and r.levelname == "WARNING"
               for r in caplog.records)
    # Not counted as verified-added; surfaced in the report instead.
    assert rep.per_category[GrammarCategory.SLOTS].added == 1
    assert rep.leaf_failed == 1
    f = rep.leaf_execution_failures[0]
    assert f.source_guid == "bad" and f.exception_type == "LookupUnverified"
    assert "repo exploded" in f.message


def test_reconcile_collects_unverified_list():
    class _Boom:
        def get_object_by_guid(self, guid):
            raise ValueError("nope")
    out = []
    assert transfer.reconcile_added_actions(
        _Boom(), [(_act("a"), "a")], unverified=out) == []
    assert [(c, g) for c, g, _ in out] == [(GrammarCategory.SLOTS, "a")]


def test_plan_action_exception_becomes_a_skip_not_an_add(monkeypatch):
    """Cycle 3 P2-b: a raising planner yields a Skip with the reason; it must
    not leave a PlannedAction with an empty intended_target_guid."""
    piece = types.SimpleNamespace(Guid="g-boom")

    def _boom(piece, context, ws):
        raise RuntimeError("planner exploded")

    bundle = {"enumerate_source": lambda c, s: [piece], "plan_action": _boom}
    monkeypatch.setattr(categories, "for_category", lambda cat: bundle)
    sel = Selection(categories={GrammarCategory.SLOTS: True},
                    include_closure=False)
    plan = preview.build_run_plan(_ctx_with_src(), sel, WSMapping(entries=()),
                                  _FakeProj(), _FakeProj())
    assert not [a for a in plan.actions if a.category == GrammarCategory.SLOTS]
    boom = [s for s in plan.skips if s.source_guid == "g-boom"]
    assert len(boom) == 1
    assert "planner exploded" in boom[0].detail
    assert "RuntimeError" in boom[0].detail
