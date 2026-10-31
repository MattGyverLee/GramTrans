"""Issue #107 -- a POS CREATED by its own PlannedAction gets its owned
collections in the SAME run, so an identical re-run has nothing to add.

Root cause (measured live, Mbugwe LizzieHC practice -> restored Target):
`gram_categories_execute_action` created the POS and copied its scalars only.
The seven owned collections were filled exclusively by the UPDATE enrichment
pass, which runs for a POS the target ALREADY held. Run 1 therefore left every
created POS a shell; run 2 (0 planned actions) found it present by GUID and
filled it -- 10 MoInflAffixSlot, 7 MoInflAffixTemplate, 47 FsFeatStruc, all
under their SOURCE GUIDs. Run 3 was clean: the transfer converged one run late.

Hermetic: reuses the fakes of `test_038_enrichment_executor.py`.
"""
from __future__ import annotations

import pytest

import test_038_enrichment_executor as base
from test_038_enrichment_executor import (  # noqa: F401 -- autouse fixtures
    _offline_tsstrings,
    _patch_guid,
)

from gramtrans.Lib import categories, transfer
from gramtrans.Lib.models import (
    ActionOutcome,
    GrammarCategory,
    PlannedAction,
    RunContext,
    RunPlan,
    Selection,
    WSMapping,
)


def _action(guid, category=GrammarCategory.GRAM_CATEGORIES):
    return PlannedAction(category=category, source_guid=guid,
                         intended_target_guid=guid, summary="Create " + guid)


def _source_pos():
    """A source POS shaped like Mbugwe's `Numeral`: slots, a template and
    reference forms -- the three classes #107 saw re-created on run 2."""
    return base._FakePOS(
        "pos-num",
        name_en="Numeral",
        AffixSlotsOC=[base._FakeChild("slot-1", name="NUM-agr")],
        AffixTemplatesOS=[base._FakeChild("tmpl-1", name="Numeral template")],
        ReferenceFormsOC=[base._FakeChild("fs-1"), base._FakeChild("fs-2")],
        StemNamesOC=[base._FakeChild("stem-1", name="stem A")],
        InflectionClassesOC=[base._FakeChild("ic-1", name="class 1")],
    )


def _fill(src_pos, created, *, category=GrammarCategory.GRAM_CATEGORIES,
          planned_action_guids=frozenset(), factories=None, dropped=None):
    source = base._FakeProject([src_pos])
    target = base._FakeProject(
        [created] if created is not None and not isinstance(created, ActionOutcome) else [],
        factories=base._all_factories() if factories is None else factories)
    sink = base._Sink()
    rows = transfer._fill_created_pos_collections(
        _action(src_pos.guid, category), created, source, target, sink,
        ws_map={}, dropped=dropped, planned_action_guids=planned_action_guids,
    )
    return rows, sink, source, target


def _guids(pos, field_name):
    return [c.guid for c in pos.collection(field_name)]


@pytest.mark.parametrize("category", [GrammarCategory.GRAM_CATEGORIES,
                                      GrammarCategory.POS])
def test_a_created_pos_gets_its_owned_collections_in_the_same_run(category):
    src = _source_pos()
    created = base._FakePOS("pos-num")          # what the factory just made

    rows, sink, _s, _t = _fill(src, created, category=category)

    assert _guids(created, "AffixSlotsOC") == ["slot-1"]
    assert _guids(created, "AffixTemplatesOS") == ["tmpl-1"]
    assert _guids(created, "ReferenceFormsOC") == ["fs-1", "fs-2"]
    assert _guids(created, "StemNamesOC") == ["stem-1"]
    assert _guids(created, "InflectionClassesOC") == ["ic-1"]
    by_name = {r.canonical_field_name: r for r in rows}
    assert by_name["ReferenceFormsOC"].added == 2
    assert all(r.dropped == 0 for r in rows)
    assert not sink.warning
    assert any("owned collections filled" in m for m in sink.info)


def test_the_children_keep_their_source_guids():
    """The re-run matches by GUID; a minted identity would re-create forever."""
    factories = base._all_factories()
    _fill(_source_pos(), base._FakePOS("pos-num"), factories=factories)
    assert factories["IMoInflAffixSlotFactory"].created_guids == ["slot-1"]
    assert factories["IMoInflAffixTemplateFactory"].created_guids == ["tmpl-1"]
    assert factories["IFsFeatStrucFactory"].created_guids == ["fs-1", "fs-2"]
    assert all(f.bare_creates == 0 for f in factories.values())


def test_after_the_fill_the_rerun_planner_has_nothing_to_add():
    """THE #107 acceptance, at unit level: the run-2 planner
    (`_compare_pos_owned_collections`) must find every child already present,
    so no enrichment -- and no write -- is planned."""
    src = _source_pos()
    created = base._FakePOS("pos-num")
    _rows, _sink, source, target = _fill(src, created)

    ctx = RunContext(
        source_handle=source, source_project_name="S", source_project_path="",
        target_handle=target, target_project_name="T", target_project_path="",
        run_id="GT-20261030-000000", started_at="2026-10-30T00:00:00",
    )
    rerun = categories._compare_pos_owned_collections(src, created, ctx)
    assert rerun, "the planner compared nothing"
    assert [(r.canonical_field_name, r.added) for r in rerun if r.added] == []


def test_without_the_fill_the_rerun_planner_would_add_them():
    """Negative control: the shell the old create path left behind is exactly
    what made run 2 enrich (and therefore create) again."""
    src = _source_pos()
    shell = base._FakePOS("pos-num")
    ctx = RunContext(
        source_handle=base._FakeProject([src]), source_project_name="S",
        source_project_path="", target_handle=base._FakeProject([shell]),
        target_project_name="T", target_project_path="",
        run_id="GT-20261030-000000", started_at="2026-10-30T00:00:00",
    )
    rerun = categories._compare_pos_owned_collections(src, shell, ctx)
    assert sum(r.added for r in rerun) == 6


def test_a_child_with_its_own_planned_action_is_still_deferred():
    """A sub-POS (or a slot the SLOTS category plans) is created by its own
    dedicated path later in the leaf loop; the fill must not pre-empt it."""
    src = base._FakePOS(
        "pos-v", SubPossibilitiesOS=[base._FakeChild("sub-1", name="vt")],
        AffixSlotsOC=[base._FakeChild("slot-planned")],
    )
    created = base._FakePOS("pos-v")
    factories = base._all_factories()
    rows, sink, _s, _t = _fill(
        src, created, factories=factories,
        planned_action_guids=frozenset({"sub-1", "slot-planned"}))
    assert _guids(created, "SubPossibilitiesOS") == []
    assert _guids(created, "AffixSlotsOC") == []
    assert factories["IPartOfSpeechFactory"].created_guids == []
    assert factories["IMoInflAffixSlotFactory"].created_guids == []
    assert sum(1 for m in sink.info if "deferred" in m) == 2


def test_a_failed_child_create_is_a_reported_drop():
    dropped: list = []
    factories = base._all_factories(fail=("AffixSlotsOC",))
    rows, sink, _s, _t = _fill(_source_pos(), base._FakePOS("pos-num"),
                               factories=factories, dropped=dropped)
    by_name = {r.canonical_field_name: r for r in rows}
    assert by_name["AffixSlotsOC"].dropped == 1
    assert [d.item_guid for d in dropped] == ["slot-1"]
    assert sink.warning


@pytest.mark.parametrize("created", [None, ActionOutcome.skipped("owner missing")])
def test_nothing_happens_when_nothing_was_created(created):
    """`None` = already present (the guard returned early); an ActionOutcome
    decline created nothing. Neither may be filled."""
    factories = base._all_factories()
    rows, sink, _s, _t = _fill(_source_pos(), created, factories=factories)
    assert rows is None
    assert all(f.created_guids == [] for f in factories.values())


def test_a_non_pos_category_is_never_filled():
    factories = base._all_factories()
    created = base._FakePOS("pos-num")
    rows, _sink, _s, _t = _fill(_source_pos(), created,
                                category=GrammarCategory.STEM_NAMES,
                                factories=factories)
    assert rows is None
    assert _guids(created, "AffixSlotsOC") == []


def test_an_unfound_source_pos_is_warned_not_silent():
    source = base._FakeProject([])
    target = base._FakeProject([], factories=base._all_factories())
    sink = base._Sink()
    rows = transfer._fill_created_pos_collections(
        _action("pos-gone"), base._FakePOS("pos-gone"), source, target, sink)
    assert rows is None
    assert any("NOT filled" in m for m in sink.warning)


def test_an_unfound_source_pos_records_a_drop_per_collection():
    from gramtrans.Lib.models import POS_OWNED_COLLECTION_FIELDS
    dropped: list = []
    transfer._fill_created_pos_collections(
        _action("pos-gone"), base._FakePOS("pos-gone"),
        base._FakeProject([]), base._FakeProject([], factories=base._all_factories()),
        base._Sink(), dropped=dropped)
    assert sorted(d.field_name for d in dropped) == sorted(
        POS_OWNED_COLLECTION_FIELDS)
    assert all(d.owner_guid == "pos-gone" and d.owner_label and d.reason
               for d in dropped)


# ----------------------------------------------------------------------------
# Wiring: execute()'s leaf loop must call the fill on every successful create
# ----------------------------------------------------------------------------

@pytest.fixture
def _quiet_tail(monkeypatch):
    monkeypatch.setattr(categories, "reproduce_all_lexical_relations",
                        lambda *a, **k: None)
    monkeypatch.setattr(categories, "reproduce_reversal_entries",
                        lambda *a, **k: None)
    monkeypatch.setattr(transfer, "_ensure_171_subpass", lambda *a, **k: None)
    monkeypatch.setattr(transfer, "_ensure_owner_feat_strucs",
                        lambda *a, **k: None)


class _ExecSink:
    def __init__(self):
        self.messages = []

    def Info(self, m): self.messages.append(("I", m))
    def Warning(self, m): self.messages.append(("W", m))
    def Error(self, m): self.messages.append(("E", m))
    def Blank(self): pass


def _execute(monkeypatch, handler, guids, fill):
    monkeypatch.setattr(
        categories, "for_category", lambda cat: {"execute_action": handler})
    monkeypatch.setattr(transfer, "_fill_created_pos_collections", fill)
    ctx = RunContext(
        source_handle=object(), source_project_name="S", source_project_path="",
        target_handle=object(), target_project_name="T", target_project_path="",
        run_id="GT-20261030-000000", started_at="2026-10-30T00:00:00",
    )
    plan = RunPlan(context=ctx, selection=Selection(),
                   ws_mapping=WSMapping(entries=()),
                   actions=tuple(_action(g) for g in guids))
    sink = _ExecSink()
    return transfer.execute(plan, object(), object(), sink, tag=None), sink


def test_execute_fills_each_created_pos_with_the_planned_guids(monkeypatch,
                                                               _quiet_tail):
    made = {}
    calls = []

    def handler(action, ctx, ws, tag):
        made[action.source_guid] = object()
        return made[action.source_guid]

    def fill(action, created, source, target, sink, **kw):
        calls.append((action.source_guid, created,
                      kw.get("planned_action_guids")))

    _execute(monkeypatch, handler, ["p1", "p2"], fill)
    assert [(g, c) for g, c, _p in calls] == [("p1", made["p1"]),
                                               ("p2", made["p2"])]
    assert calls[0][2] == frozenset({"p1", "p2"})


def test_a_failing_fill_does_not_fail_the_pos_create(monkeypatch, _quiet_tail):
    def handler(action, ctx, ws, tag):
        return object()

    def fill(*a, **k):
        raise RuntimeError("collection boom")

    rep, sink = _execute(monkeypatch, handler, ["p1"], fill)
    assert rep.leaf_failed == 0
    assert rep.per_category[GrammarCategory.GRAM_CATEGORIES].added == 1
    assert any(lvl == "W" and "collection boom" in m for lvl, m in sink.messages)


def test_a_failing_fill_records_a_drop_per_collection(monkeypatch, _quiet_tail):
    from gramtrans.Lib.models import POS_OWNED_COLLECTION_FIELDS

    def handler(action, ctx, ws, tag):
        return object()

    def fill(*a, **k):
        raise RuntimeError("collection boom")

    rep, _sink = _execute(monkeypatch, handler, ["p1"], fill)
    drops = [d for d in rep.dropped_items if d.owner_guid == "p1"]
    assert sorted(d.field_name for d in drops) == sorted(
        POS_OWNED_COLLECTION_FIELDS)
    assert all("collection boom" in d.reason for d in drops)


def test_add_only_check_is_not_fooled_by_fresh_proxy_wrappers():
    """pythonnet yields NEW wrapper objects on each iteration; the same LCM
    object (same GUID) at the same index must not be reported as moved."""
    a, b = base._FakeChild("a"), base._FakeChild("b")
    a2, b2 = base._FakeChild("a"), base._FakeChild("b")   # distinct proxies
    sink = base._Sink()
    assert transfer._check_add_only(
        "AffixTemplatesOS", [a, b], base._FakeOwningCollection([a2, b2]),
        sink, "pos-1") is True
    assert sink.warning == []
    # a genuinely different member at the index is still a violation
    assert transfer._check_add_only(
        "AffixTemplatesOS", [a, b],
        base._FakeOwningCollection([b2, a2]), sink, "pos-1") is False
