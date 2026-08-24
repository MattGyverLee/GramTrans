"""Feature 038 -- T073 (Phase 7, US3): the items that arrive INCOMPLETE say so.

FR-017: "When a dependency is deselected or cannot be satisfied, every item
left incomplete as a result MUST be reported."
SC-010: every selected item reaches exactly one of ADD / UPDATE / SKIP /
dropped-with-reason. There is no fifth, unreported outcome.

WHAT WAS ACTUALLY MISSING WHEN THIS FILE WAS WRITTEN. T070/T071 put the
pulled-in items in the plan and made them refusable, and T071 wrote
`ClosureEdge.deselected` -- measured live at 53 of 53 edges under a full
deselection. **Nothing read it.** A user who unticked a dependency got a
`DEPENDENCY_DESELECTED` skip naming the DEPENDENCY and not one word about the
items that still transfer and now arrive unwired; `RunPlan.incompleteness`,
`RunReport.incompleteness`, `RunReport.has_incomplete_items`,
`report._incompleteness_json` and the console's "Items arriving INCOMPLETE"
block all existed, all wired to each other, and all fed by an empty tuple.
That is this feature's recurring shape for the eighth time -- a signal that
exists and is read at a level where it cannot do its job.

THREE CAUSES, and the third one is why `_closure_cycle_groups` exists.
`closure.walk` is cycle-tolerant by construction and `closure.topological`
DETECTS a cycle (`if len(result) != len(visit_order)`) and then discards the
finding, emitting the survivors "by rank to keep output total" and telling
nobody. T073 does not change `topological`'s contract -- its callers want a
total order -- it recovers the cycle from the EDGES, which is where the plan
and the report both already read.

COVERAGE HONESTY. The end-to-end cases run against duck-typed fakes with
`LEAF_CATEGORIES` and `CLOSURE_EDGES_VERIFIED` patched, exactly as
`test_038_pull_in.py` does, so what is pinned is the RECORD-EMISSION rule and
not any real producer's edge set. The live measurement is T073's own census
run (`debug/run038_incompleteness_census.py`, snapshot
`tests/integration/_snapshots/incompleteness-038-t073.json`), and the cycle
cause has no live instance at all: the five registered relationships form a
DAG, so the cycle case is unit-only ON PURPOSE and says so rather than
claiming a measurement it does not have.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from gramtrans.Lib import categories as categories_mod
from gramtrans.Lib import preview as preview_mod
from gramtrans.Lib import report as report_mod
from gramtrans.Lib.models import (
    ClosureEdge,
    DependencyKind,
    GrammarCategory,
    PlannedAction,
    PlannedOverwrite,
    RunContext,
    RunMode,
    Selection,
    Skip,
    SkipReason,
    WSMapping,
)

AFFIX_G = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
POS_G = "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb"
SLOT_G = "cccccccc-3333-4333-8333-cccccccccccc"

AFFIX_REF = (GrammarCategory.AFFIXES, AFFIX_G)
POS_REF = (GrammarCategory.GRAM_CATEGORIES, POS_G)
SLOT_REF = (GrammarCategory.SLOTS, SLOT_G)


# ===========================================================================
# Unit harness -- `_plan_incompleteness` is a pure function of (edges, plan
# members, skips), which is the whole reason it is one: the cycle case has no
# live instance, so it has to be constructible.
# ===========================================================================

def _edge(dependent, dependency, kind, *, deselected=False,
          origin="pulled_in"):
    return ClosureEdge(
        dependent=dependent,
        dependency=dependency,
        kind=kind,
        verified=True,
        origin=origin,
        verified_by="T073 unit",
        deselected=deselected,
    )


def _action(ref):
    return PlannedAction(
        category=ref[0],
        source_guid=ref[1],
        intended_target_guid=ref[1],
        summary="T073 fake " + ref[0].value,
    )


def _labels(mapping):
    return lambda ref: mapping.get(
        (ref[0], str(ref[1]).lower()),
        ref[0].value + " " + str(ref[1])[:8],
    )


# ===========================================================================
# FR-017, cause="deselected"
# ===========================================================================

def test_a_deselected_dependency_makes_its_dependent_report_incomplete():
    """The clause itself. The affix still transfers; the POS it needs was
    refused; the affix therefore arrives unwired and must be named."""
    records = preview_mod._plan_incompleteness(
        (_edge(AFFIX_REF, POS_REF, DependencyKind.AFFIX_TO_POS,
               deselected=True),),
        [_action(AFFIX_REF)], [], [],
    )
    assert len(records) == 1
    rec = records[0]
    assert rec.incomplete_item == AFFIX_REF
    assert rec.missing_dependency == POS_REF
    assert rec.cause == "deselected"
    assert "deselected" in rec.consequence


def test_an_item_that_does_not_arrive_is_not_called_incomplete():
    """THE COUNTING RULE, and the one that turns 53 live edges into 35
    records. A dependent that is not in `actions`/`overwrites` is not "left
    incomplete" -- it is dropped-with-reason, and its own `Skip` already
    reports it. Emitting both would count one loss twice under two buckets
    and would state, of an object that never reaches the destination, that it
    "arrives incomplete"."""
    edges = (
        # the template arrives and loses its slot
        _edge((GrammarCategory.AFFIX_TEMPLATES, AFFIX_G), SLOT_REF,
              DependencyKind.TEMPLATE_TO_SLOT, deselected=True),
        # the slot does NOT arrive, so its own missing POS is the slot's skip
        _edge(SLOT_REF, POS_REF, DependencyKind.SLOT_TO_POS, deselected=True),
    )
    records = preview_mod._plan_incompleteness(
        edges, [_action((GrammarCategory.AFFIX_TEMPLATES, AFFIX_G))], [], [],
    )
    assert [r.incomplete_item[0] for r in records] == [
        GrammarCategory.AFFIX_TEMPLATES]


def test_an_overwrite_counts_as_arriving():
    """An ENRICHED destination object (FR-020..FR-022) is being written by
    this run, so a dependency it loses is a real incompleteness. Reading only
    `actions` would silently exempt every UPDATE."""
    ow = PlannedOverwrite(
        category=GrammarCategory.AFFIXES,
        source_guid=AFFIX_G,
        target_guid=AFFIX_G,
        summary="T073 fake merge",
        write_mode="merge",
    )
    records = preview_mod._plan_incompleteness(
        (_edge(AFFIX_REF, POS_REF, DependencyKind.AFFIX_TO_POS,
               deselected=True),),
        [], [ow], [],
    )
    assert len(records) == 1


# ===========================================================================
# FR-017, cause="unsatisfiable" -- and why this reads the PLAN, not the skips
# ===========================================================================

def test_a_dependency_that_reached_no_plan_member_is_unsatisfiable():
    """The closure asked for a POS; nothing planned it and nothing says it is
    already in the destination. The affix arrives unwired."""
    records = preview_mod._plan_incompleteness(
        (_edge(AFFIX_REF, POS_REF, DependencyKind.AFFIX_TO_POS),),
        [_action(AFFIX_REF)], [], [],
    )
    assert [r.cause for r in records] == ["unsatisfiable"]


def test_a_dependency_that_vanished_without_any_skip_is_reported_anyway():
    """WHY THIS IS DERIVED FROM PLAN MEMBERSHIP AND NOT FROM THE SKIP LIST.
    `_plan_pulled_in_items` has one silent exit: a `plan_action` that returns
    None plans nothing AND skips nothing. Reading the plan instead of the
    skips means that hole is reported rather than inherited."""
    records = preview_mod._plan_incompleteness(
        (_edge(AFFIX_REF, POS_REF, DependencyKind.AFFIX_TO_POS),),
        [_action(AFFIX_REF)], [], [],  # no skip of any kind for the POS
    )
    assert len(records) == 1


def test_a_dependency_already_in_the_destination_is_not_an_incompleteness():
    """THE NEGATIVE THAT KEEPS THIS HONEST. A pulled-in POS whose planner
    returned `ALREADY_PRESENT_BY_IDENTITY` is not missing -- it is in the
    destination and the reference resolves. Reporting it would make FR-017
    fire loudest on the case where nothing was lost, which is the phantom-loss
    failure CLAUDE.md records for flexicon 4.5.1's natural-class features."""
    for reason in (SkipReason.ALREADY_PRESENT_BY_GUID,
                   SkipReason.ALREADY_PRESENT_BY_IDENTITY):
        skips = [Skip(category=GrammarCategory.GRAM_CATEGORIES,
                      source_guid=POS_G, reason=reason, detail="present")]
        assert preview_mod._plan_incompleteness(
            (_edge(AFFIX_REF, POS_REF, DependencyKind.AFFIX_TO_POS),),
            [_action(AFFIX_REF)], [], skips,
        ) == ()


def test_a_satisfied_dependency_emits_nothing():
    """The default path. Both items are in the plan, so nothing is
    incomplete and the report must stay silent -- an always-on warning is
    indistinguishable from no warning."""
    assert preview_mod._plan_incompleteness(
        (_edge(AFFIX_REF, POS_REF, DependencyKind.AFFIX_TO_POS),),
        [_action(AFFIX_REF), _action(POS_REF)], [], [],
    ) == ()


def test_no_edges_means_no_records():
    """A full copy produces 0 edges (measured by T070), and every pre-038
    caller produces 0. Both must be untouched by this task."""
    assert preview_mod._plan_incompleteness((), [_action(AFFIX_REF)], [], []) == ()


def test_a_chosen_edge_is_never_an_incompleteness():
    """`closure.walk`'s seed semantics: an item the user picked directly is
    not a dependency anyone pulled in, so it cannot be the missing half of
    one."""
    assert preview_mod._plan_incompleteness(
        (_edge(AFFIX_REF, POS_REF, DependencyKind.AFFIX_TO_POS,
               origin="chosen", deselected=True),),
        [_action(AFFIX_REF)], [], [],
    ) == ()


# ===========================================================================
# FR-017, cause="cycle" -- the case the task line names explicitly
# ===========================================================================

def test_a_two_item_cycle_is_reported_as_a_cycle():
    """A needs B and B needs A, both in the plan. Whichever is written first
    cannot resolve its reference, so BOTH are incomplete -- and neither is
    `unsatisfiable`, because both objects do arrive."""
    edges = (
        _edge(POS_REF, SLOT_REF, DependencyKind.TEMPLATE_TO_SLOT),
        _edge(SLOT_REF, POS_REF, DependencyKind.SLOT_TO_POS),
    )
    records = preview_mod._plan_incompleteness(
        edges, [_action(POS_REF), _action(SLOT_REF)], [], [],
    )
    assert {r.cause for r in records} == {"cycle"}
    assert {r.incomplete_item for r in records} == {POS_REF, SLOT_REF}
    assert all("cycle" in r.consequence for r in records)


def test_a_self_dependency_is_a_cycle():
    """One item, one arc, onto itself -- the shape a POS->parent-POS
    relationship would produce for a POS that (mis)references itself. A
    component of size one is a cycle only when it carries a self-loop."""
    records = preview_mod._plan_incompleteness(
        (_edge(POS_REF, POS_REF, DependencyKind.TEMPLATE_TO_POS),),
        [_action(POS_REF)], [], [],
    )
    assert [r.cause for r in records] == ["cycle"]


def test_a_deselection_inside_a_cycle_names_the_deselection():
    """CAUSE PRECEDENCE: `deselected` > `cycle` > `unsatisfiable`. The user's
    own action is the most actionable explanation there is, so it names itself
    even when the refused item also happens to sit in a cycle."""
    edges = (
        _edge(POS_REF, SLOT_REF, DependencyKind.TEMPLATE_TO_SLOT,
              deselected=True),
        _edge(SLOT_REF, POS_REF, DependencyKind.SLOT_TO_POS),
    )
    records = preview_mod._plan_incompleteness(
        edges, [_action(POS_REF), _action(SLOT_REF)], [], [],
    )
    by_item = {r.incomplete_item: r.cause for r in records}
    assert by_item[POS_REF] == "deselected"
    assert by_item[SLOT_REF] == "cycle"


def test_a_diamond_is_not_a_cycle():
    """THE FALSE-POSITIVE GUARD, and the reason this is SCC and not "the
    dependency was seen before". The live shape is a diamond -- 11 templates
    and 18 slots all pointing at 5 shared POSes, 53 edges over 23 refs -- and
    a cycle detector that called that a cycle would report every live
    transfer as broken."""
    edges = (
        _edge((GrammarCategory.AFFIX_TEMPLATES, AFFIX_G), SLOT_REF,
              DependencyKind.TEMPLATE_TO_SLOT),
        _edge((GrammarCategory.AFFIX_TEMPLATES, AFFIX_G), POS_REF,
              DependencyKind.TEMPLATE_TO_POS),
        _edge(SLOT_REF, POS_REF, DependencyKind.SLOT_TO_POS),
    )
    assert preview_mod._closure_cycle_groups(edges) == {}


def test_the_cycle_walk_does_not_recurse_on_depth():
    """A source project's closure depth is data, not a constant, so the SCC
    pass is iterated. 3000 chained refs would blow Python's recursion limit
    in the textbook Tarjan."""
    refs = [(GrammarCategory.GRAM_CATEGORIES,
             format(i, "08x") + "-0000-4000-8000-000000000000")
            for i in range(3000)]
    edges = tuple(
        _edge(refs[i], refs[i + 1], DependencyKind.TEMPLATE_TO_POS)
        for i in range(len(refs) - 1)
    )
    assert preview_mod._closure_cycle_groups(edges) == {}


# ===========================================================================
# The record has to be usable: labels and consequence
# ===========================================================================

def test_every_record_carries_two_labels_and_a_consequence():
    """`IncompletenessRecord` already refuses an empty `consequence`; the
    LABELS it does not police, and a record whose two labels are blank tells
    the reader which GUIDs are involved and nothing about which ITEMS."""
    records = preview_mod._plan_incompleteness(
        (_edge(AFFIX_REF, POS_REF, DependencyKind.AFFIX_TO_POS,
               deselected=True),),
        [_action(AFFIX_REF)], [], [],
        _labels({(GrammarCategory.GRAM_CATEGORIES, POS_G): "Verb",
                 (GrammarCategory.AFFIXES, AFFIX_G): "-mVn"}),
    )
    assert records[0].incomplete_label == "-mVn"
    assert records[0].missing_label == "Verb"


def test_a_label_that_cannot_be_resolved_falls_back_to_the_ref():
    """Never blank. With no resolver at all the label is the console form of
    the ref, which is strictly more than nothing."""
    records = preview_mod._plan_incompleteness(
        (_edge(AFFIX_REF, POS_REF, DependencyKind.AFFIX_TO_POS,
               deselected=True),),
        [_action(AFFIX_REF)], [], [],
    )
    assert records[0].missing_label == "gram_categories " + POS_G[:8]


def test_the_label_helper_reads_the_name_multistring():
    """`_pull_in_label` reuses `references._item_label` -- the same
    best-effort Name reader `DroppedItemRecord.item_name` uses -- rather than
    inventing a second dialect of "what is this item called"."""
    piece = SimpleNamespace(guid=POS_G, Name=SimpleNamespace(_data={"en": "Verb"}))
    assert preview_mod._pull_in_label(lambda c, g: piece, POS_REF) == "Verb"
    assert preview_mod._pull_in_label(
        lambda c, g: None, POS_REF) == "gram_categories " + POS_G[:8]


def test_the_label_helper_never_fails_a_plan():
    """A resolver that raises must cost a label, not the run."""
    def _boom(category, guid):
        raise RuntimeError("enumeration exploded")

    assert preview_mod._pull_in_label(_boom, POS_REF).startswith(
        "gram_categories ")


# ===========================================================================
# End to end through `build_run_plan`, and out to both report surfaces
# ===========================================================================

def _ctx() -> RunContext:
    return RunContext(
        source_handle=SimpleNamespace(),
        source_project_name="Src",
        source_project_path=r"C:\p\Src",
        target_handle=SimpleNamespace(),
        target_project_name="Tgt",
        target_project_path=r"C:\p\Tgt",
        run_id="GT-20260821-000000",
        started_at="2026-08-21T00:00:00",
    )


def _fake_bundle(category, guid, *, pieces=None, producer=None, name=None):
    piece = SimpleNamespace(guid=guid)
    if name is not None:
        piece.Name = SimpleNamespace(_data={"en": name})
    if pieces is None:
        pieces = [piece]
    bundle = dict(categories_mod.LEAF_CATEGORIES[category])
    bundle["enumerate_source"] = lambda context, selection: list(pieces)
    bundle["plan_action"] = lambda pc, context, ws: PlannedAction(
        category=category,
        source_guid=str(getattr(pc, "guid", guid)),
        intended_target_guid=str(getattr(pc, "guid", guid)),
        summary="T073 fake " + category.value,
    )
    if producer is not None:
        bundle["dependencies"] = producer
    return bundle


def _build(monkeypatch, selection=None, *, pos_pieces=None):
    def _producer(piece):
        return (POS_REF,)

    patched = dict(categories_mod.LEAF_CATEGORIES)
    patched[GrammarCategory.AFFIXES] = _fake_bundle(
        GrammarCategory.AFFIXES, AFFIX_G, producer=_producer, name="-mVn")
    patched[GrammarCategory.GRAM_CATEGORIES] = _fake_bundle(
        GrammarCategory.GRAM_CATEGORIES, POS_G, pieces=pos_pieces, name="Verb")
    monkeypatch.setattr(categories_mod, "LEAF_CATEGORIES", patched)
    monkeypatch.setattr(categories_mod, "CLOSURE_EDGES_VERIFIED", {
        DependencyKind.AFFIX_TO_POS: {
            "category": GrammarCategory.AFFIXES,
            "producer": _producer,
            "dependency_category": GrammarCategory.GRAM_CATEGORIES,
            "verified_by": "T073 fake audit",
        }
    })
    if selection is None:
        selection = Selection(categories={GrammarCategory.AFFIXES: True})
    return preview_mod.build_run_plan(
        _ctx(), selection, WSMapping(), SimpleNamespace(), SimpleNamespace()
    )


def test_the_plan_carries_the_record_for_a_deselected_dependency(monkeypatch):
    """The end-to-end assertion that would have failed before T073: T071
    already produced the skip and the `deselected` edge, and
    `plan.incompleteness` was `()`."""
    selection = Selection(
        categories={GrammarCategory.AFFIXES: True},
        excluded_deps=frozenset({POS_G}),
    )
    plan = _build(monkeypatch, selection)
    assert plan.closure_edges[0].deselected is True
    assert len(plan.incompleteness) == 1
    rec = plan.incompleteness[0]
    assert rec.incomplete_item == AFFIX_REF
    assert rec.cause == "deselected"
    assert rec.incomplete_label == "-mVn"
    assert rec.missing_label == "Verb", (
        "the label has to come from the source piece the pull-in already "
        "resolved, not from the plan member's guid-shaped summary")


def test_a_satisfied_plan_reports_no_incompleteness(monkeypatch):
    """The negative that makes the assertion above mean something: the same
    plan with nothing deselected pulls the POS in and loses nothing."""
    plan = _build(monkeypatch)
    assert plan.incompleteness == ()


def test_an_unsatisfiable_dependency_names_the_item_it_leaves_broken(
    monkeypatch,
):
    """T089's live shape one level up. T070 reports the DEPENDENCY it could
    not enumerate (`DEPENDENCY_UNRESOLVED`); FR-017 wants the DEPENDENT that
    is still transferring and now arrives unwired."""
    plan = _build(monkeypatch, pos_pieces=())
    assert any(s.reason == SkipReason.DEPENDENCY_UNRESOLVED
               for s in plan.skips), "T070's half must still hold"
    assert [r.cause for r in plan.incompleteness] == ["unsatisfiable"]
    assert plan.incompleteness[0].incomplete_item == AFFIX_REF


def test_an_empty_registry_reports_no_incompleteness(monkeypatch):
    """FR-018 is upstream of everything here: no verified relationship, no
    edges, no records. A leak at this layer would make every pre-038 run
    start claiming losses it cannot substantiate."""
    patched = dict(categories_mod.LEAF_CATEGORIES)
    patched[GrammarCategory.AFFIXES] = _fake_bundle(
        GrammarCategory.AFFIXES, AFFIX_G, producer=lambda p: (POS_REF,))
    monkeypatch.setattr(categories_mod, "LEAF_CATEGORIES", patched)
    monkeypatch.setattr(categories_mod, "CLOSURE_EDGES_VERIFIED", {})
    plan = preview_mod.build_run_plan(
        _ctx(), Selection(categories={GrammarCategory.AFFIXES: True}),
        WSMapping(), SimpleNamespace(), SimpleNamespace(),
    )
    assert plan.closure_edges == ()
    assert plan.incompleteness == ()


def test_the_record_travels_to_the_run_report(monkeypatch):
    """THE MARK HAS TO TRAVEL. `RunReport.incompleteness` and
    `has_incomplete_items` both predate this task and both read an empty
    tuple until now; SC-010's never-silent contract is stated in terms of the
    report, not the plan."""
    selection = Selection(
        categories={GrammarCategory.AFFIXES: True},
        excluded_deps=frozenset({POS_G}),
    )
    plan = _build(monkeypatch, selection)
    rpt = report_mod.RunReport.build_from_plan(plan, RunMode.PREVIEW)
    assert len(rpt.incompleteness) == 1
    assert rpt.has_incomplete_items is True


def test_the_console_summary_states_what_is_incomplete(monkeypatch):
    """The human surface. `render_text_summary`'s "Items arriving INCOMPLETE"
    block existed and had nothing to render."""
    selection = Selection(
        categories={GrammarCategory.AFFIXES: True},
        excluded_deps=frozenset({POS_G}),
    )
    plan = _build(monkeypatch, selection)
    rpt = report_mod.RunReport.build_from_plan(plan, RunMode.PREVIEW)
    text = "\n".join(report_mod.render_text_summary(rpt))
    assert "Items arriving INCOMPLETE" in text
    assert '"-mVn"' in text and '"Verb"' in text
    assert "deselected" in text


def test_the_snapshot_artifact_carries_the_record(monkeypatch):
    """The machine surface (FR-011's sibling rule for this bucket): the
    artifact is never truncated, and it is what a linguist can consult after
    the console has scrolled away."""
    selection = Selection(
        categories={GrammarCategory.AFFIXES: True},
        excluded_deps=frozenset({POS_G}),
    )
    plan = _build(monkeypatch, selection)
    rpt = report_mod.RunReport.build_from_plan(plan, RunMode.PREVIEW)
    payload = json.loads(rpt.to_snapshot_json())
    assert len(payload["incompleteness"]) == 1
    row = payload["incompleteness"][0]
    assert row["cause"] == "deselected"
    assert row["incomplete_item"]["guid"] == AFFIX_G
    assert row["missing_dependency"]["guid"] == POS_G
    assert row["consequence"]


def test_a_run_with_no_closure_omits_the_key_entirely(monkeypatch):
    """Snapshot compatibility, the rule report.py states for every 038
    bucket: an empty bucket is OMITTED, not emitted as `[]`, so a pre-038
    golden snapshot keeps matching byte for byte."""
    plan = _build(monkeypatch)
    rpt = report_mod.RunReport.build_from_plan(plan, RunMode.PREVIEW)
    assert "incompleteness" not in json.loads(rpt.to_snapshot_json())


# ===========================================================================
# T093 -- "already there" is not a cause, so it outranks every cause
# ===========================================================================
#
# `_plan_pulled_in_items` refuses a deselected ref BEFORE its planner runs, so
# no `ALREADY_PRESENT_BY_*` skip can exist for the reader above to consult.
# `already_present_refs` is the channel that carries the fact it probed for
# instead. The precedence question is separate and is the one this section
# pins: cause precedence (`deselected` > `cycle` > `unsatisfiable`) orders
# EXPLANATIONS for an incompleteness and cannot decide whether there is one.

def test_a_deselected_dependency_already_in_the_destination_is_not_reported():
    """The live defect, at the unit layer. 2 of the 5 pulled-in POSes on
    `Mbugwe LizzieHC practice` were already in the target and 8 of T073's 35
    records named one of them. The user refused to re-transfer an object the
    destination already has; the reference still resolves."""
    assert preview_mod._plan_incompleteness(
        (_edge(AFFIX_REF, POS_REF, DependencyKind.AFFIX_TO_POS,
               deselected=True),),
        [_action(AFFIX_REF)], [], [],
        None,
        [POS_REF],
    ) == ()


def test_presence_outranks_the_cycle_cause_too():
    """WHY THE TEST MOVED ABOVE THE CAUSE LADDER RATHER THAN INTO THE
    `deselected` BRANCH. The cycle cause fires precisely when the dependency
    IS in the plan -- "whichever is written first cannot resolve its
    reference". An object already in the destination is not being written by
    this run at all, so there is no ordering problem to report. No live
    instance (the five registered relationships form a DAG); constructible,
    therefore pinned."""
    edges = (
        _edge(AFFIX_REF, POS_REF, DependencyKind.AFFIX_TO_POS),
        _edge(POS_REF, AFFIX_REF, DependencyKind.AFFIX_TO_POS),
    )
    assert [r.cause for r in preview_mod._plan_incompleteness(
        edges, [_action(AFFIX_REF), _action(POS_REF)], [], [])] == [
        "cycle", "cycle"]
    assert preview_mod._plan_incompleteness(
        edges, [_action(AFFIX_REF), _action(POS_REF)], [], [],
        None, [POS_REF, AFFIX_REF],
    ) == ()


def test_the_channel_is_additive_to_the_skip_derived_set():
    """The skip-derived set covers every path except the deselected one, and
    both feed the same question. A ref present on either reading is present."""
    skips = [Skip(category=GrammarCategory.GRAM_CATEGORIES,
                  source_guid=POS_G,
                  reason=SkipReason.ALREADY_PRESENT_BY_GUID, detail="present")]
    edges = (_edge(AFFIX_REF, POS_REF, DependencyKind.AFFIX_TO_POS,
                   deselected=True),)
    assert preview_mod._plan_incompleteness(
        edges, [_action(AFFIX_REF)], [], skips, None, [],
    ) == ()
    assert preview_mod._plan_incompleteness(
        edges, [_action(AFFIX_REF)], [], [], None, [POS_REF],
    ) == ()


def test_an_empty_channel_changes_nothing():
    """The default. Every pre-T093 caller passes nothing, and a deselected
    dependency nobody vouched for is still reported -- 27 of the 35 live
    records are exactly this."""
    edges = (_edge(AFFIX_REF, POS_REF, DependencyKind.AFFIX_TO_POS,
                   deselected=True),)
    assert [r.cause for r in preview_mod._plan_incompleteness(
        edges, [_action(AFFIX_REF)], [], [], None, ())] == ["deselected"]
    assert [r.cause for r in preview_mod._plan_incompleteness(
        edges, [_action(AFFIX_REF)], [], [])] == ["deselected"]


def test_the_channel_normalises_guid_case():
    """Every other ref in this module is lower-cased on the way in (the piece
    cache's contract, pinned by test_038_closure.py). A probe result that
    arrived upper-cased would silently fail to match and re-open the defect."""
    assert preview_mod._plan_incompleteness(
        (_edge(AFFIX_REF, POS_REF, DependencyKind.AFFIX_TO_POS,
               deselected=True),),
        [_action(AFFIX_REF)], [], [],
        None,
        [(GrammarCategory.GRAM_CATEGORIES, POS_G.upper())],
    ) == ()
