"""Feature 038 -- T070/T071 (Phase 7, US3): the pulled-in item reaches the
plan, says so, and can be deselected.

FR-014: "When the linguist selects an item, the transfer MUST include the
items it depends on by default."
FR-015: "Items included by dependency MUST be shown in preview, marked as
pulled in rather than directly chosen."
FR-016: "Each pulled-in item MUST be individually deselectable."

WHAT WAS ACTUALLY MISSING WHEN THIS FILE WAS WRITTEN. T067-T069 registered
five closure edges and measured them live, and T069's own census asserted --
deliberately, as the thing that made two-hop closure safe to land ahead of
this task -- that **the pulled-in items are NOT in the plan**: under an
AFFIX_TEMPLATES-only selection the plan's actions were `{affix_templates}`
and nothing else, while `plan.closure_edges` carried 53 edges naming 23
distinct pulled-in refs. So the closure walk knew the POSes and slots were
needed, wrote that down, and the plan transferred none of them. That is this
feature's recurring shape one more time -- a signal that exists and is read
at a level where it cannot do its job -- and FR-014 is the clause it breaks.

THE SURFACE IS NOT NEW (research.md R3). A plan member already carries
`pulled_in_by`; `report.build_from_plan` already counts a member that has one
into `CategoryReport.closure_pulled_in`; `Lib/ui/stats_panel.py` already
renders that column. Nothing here adds a parallel channel -- T070 fills the
existing one, which is why the report-level assertion below matters as much
as the plan-level ones: it is the proof that the marking travels.

DESELECTION IS ALSO NOT NEW. `Selection.excluded_deps` + `is_dep_excluded`
and `Selection.scope_for`'s `CategoryScope` mapping already existed, with
exactly one consumer (`preview.py`'s verb-vertical POS check) and no way for
the wizard to populate the set at all (T072). `SkipReason
.DEPENDENCY_DESELECTED` was defined by the Phase 2 foundational work with a
docstring naming this exact case -- "an object the closure walk would have
pulled in was deliberately DESELECTED by the user" -- and had no emitter.

COVERAGE HONESTY. These run against duck-typed fakes with `LEAF_CATEGORIES`
patched, so what is pinned is the PULL-IN mechanism, not any real producer's
edge set. The five registered producers were audited live by T067-T069 and
the census of this mechanism against a live pair is T070's own census run.
"""
from __future__ import annotations

from types import SimpleNamespace

from gramtrans.Lib import categories as categories_mod
from gramtrans.Lib import preview as preview_mod
from gramtrans.Lib import report as report_mod
from gramtrans.Lib.models import (
    CategoryScope,
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

# Lower-case, for the reason test_038_closure.py records: every GUID that
# reaches the piece cache has been through `categories._guid_str_from`.
AFFIX_G = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
POS_G = "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb"

AFFIX_REF = (GrammarCategory.AFFIXES, AFFIX_G)
POS_REF = (GrammarCategory.GRAM_CATEGORIES, POS_G)


# ===========================================================================
# Harness -- deliberately the same shape as test_038_closure.py's, with the
# one addition that file did not need: the DEPENDENCY's category also gets a
# fake bundle, because a pull-in has to plan an item in it.
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


def _fake_bundle(category, guid, *, pieces=None, producer=None,
                 plan_action=None):
    """A one-item LEAF_CATEGORIES bundle whose `plan_action` yields an ADD.

    `pieces=()` models a dependency whose category cannot enumerate the item
    the walk asked for -- the unsatisfiable case FR-017 has to report rather
    than drop.

    `plan_action` overrides the ADD. T093 needs it: what the DEPENDENCY's
    planner decides -- ADD, OVERWRITE, `ALREADY_PRESENT_*`, or a raise -- is
    the whole of "is this thing already in the destination", and the default
    ADD models only one of the four.
    """
    piece = SimpleNamespace(guid=guid)
    if pieces is None:
        pieces = [piece]
    bundle = dict(categories_mod.LEAF_CATEGORIES[category])
    bundle["enumerate_source"] = lambda context, selection: list(pieces)
    bundle["plan_action"] = plan_action or (
        lambda pc, context, ws: PlannedAction(
            category=category,
            source_guid=str(getattr(pc, "guid", guid)),
            intended_target_guid=str(getattr(pc, "guid", guid)),
            summary="T070 fake " + category.value,
        )
    )
    if producer is not None:
        bundle["dependencies"] = producer
    return bundle


def _registry(producer):
    return {
        DependencyKind.AFFIX_TO_POS: {
            "category": GrammarCategory.AFFIXES,
            "producer": producer,
            "dependency_category": GrammarCategory.GRAM_CATEGORIES,
            "verified_by": "T070 fake audit",
        }
    }


def _build(monkeypatch, selection=None, *, pos_pieces=None,
           pos_plan_action=None):
    """Plan an AFFIXES-only selection whose one affix needs one POS."""
    def _producer(piece):
        return (POS_REF,)

    patched = dict(categories_mod.LEAF_CATEGORIES)
    patched[GrammarCategory.AFFIXES] = _fake_bundle(
        GrammarCategory.AFFIXES, AFFIX_G, producer=_producer)
    patched[GrammarCategory.GRAM_CATEGORIES] = _fake_bundle(
        GrammarCategory.GRAM_CATEGORIES, POS_G, pieces=pos_pieces,
        plan_action=pos_plan_action)
    monkeypatch.setattr(categories_mod, "LEAF_CATEGORIES", patched)
    monkeypatch.setattr(
        categories_mod, "CLOSURE_EDGES_VERIFIED", _registry(_producer))
    if selection is None:
        selection = Selection(categories={GrammarCategory.AFFIXES: True})
    return preview_mod.build_run_plan(
        _ctx(), selection, WSMapping(), SimpleNamespace(), SimpleNamespace()
    )


def _actions_for(plan, category):
    return [a for a in plan.actions if a.category == category]


# ===========================================================================
# T070 -- FR-014/FR-015: the pulled-in item is in the plan, and marked
# ===========================================================================

def test_a_pulled_in_dependency_becomes_a_plan_member(monkeypatch) -> None:
    """FR-014. The affix was chosen; the POS was not, and must transfer
    anyway or the affix arrives wired to nothing."""
    plan = _build(monkeypatch)
    assert len(plan.closure_edges) == 1, "the walk must still produce its edge"
    pos_actions = _actions_for(plan, GrammarCategory.GRAM_CATEGORIES)
    assert [a.source_guid for a in pos_actions] == [POS_G]


def test_the_pulled_in_member_names_the_item_that_pulled_it_in(
    monkeypatch,
) -> None:
    """FR-015, through the EXISTING surface. `pulled_in_by` is what every
    downstream consumer already reads; an empty one is indistinguishable from
    a directly-chosen item."""
    plan = _build(monkeypatch)
    pos_action = _actions_for(plan, GrammarCategory.GRAM_CATEGORIES)[0]
    assert pos_action.pulled_in_by == (AFFIX_G,)


def test_the_chosen_item_is_not_marked_pulled_in(monkeypatch) -> None:
    """The other half of FR-015: `closure.walk`'s seed semantics have to
    survive into the plan, or "pulled in" degrades to "in the plan"."""
    plan = _build(monkeypatch)
    affix_action = _actions_for(plan, GrammarCategory.AFFIXES)[0]
    assert affix_action.pulled_in_by == ()


def test_the_pulled_in_member_is_ordered_before_the_item_that_needs_it(
    monkeypatch,
) -> None:
    """`transfer.execute` walks `plan.actions` IN ORDER (transfer.py:516), so
    a dependency appended at the end of the plan is created after the item
    that wires to it -- which is the same "arrives wired to nothing" failure
    FR-014 exists to prevent, just moved one layer down.

    The order is the leaf-dispatch order, not the closure walk's: that is
    what makes a pulled-in member indistinguishable in position from one the
    user had selected directly."""
    plan = _build(monkeypatch)
    cats = [a.category for a in plan.actions]
    assert cats.index(GrammarCategory.GRAM_CATEGORIES) < cats.index(
        GrammarCategory.AFFIXES)


def test_the_run_report_counts_the_pulled_in_member(monkeypatch) -> None:
    """The marking has to TRAVEL. `report.build_from_plan` counts any member
    with a non-empty `pulled_in_by` into `CategoryReport.closure_pulled_in`
    (report.py:233), and `Lib/ui/stats_panel.py:149` renders that column --
    both of which predate this task. If the plan-level assertions above pass
    and this one fails, the mark was written somewhere nothing reads."""
    plan = _build(monkeypatch)
    rpt = report_mod.RunReport.build_from_plan(plan, RunMode.PREVIEW)
    per_cat = rpt.per_category[GrammarCategory.GRAM_CATEGORIES]
    assert per_cat.closure_pulled_in == 1
    assert per_cat.added == 1
    assert rpt.per_category[GrammarCategory.AFFIXES].closure_pulled_in == 0


def test_an_item_the_user_chose_is_never_restamped_as_pulled_in(
    monkeypatch,
) -> None:
    """A POS that is in the plan because its own category was selected is
    CHOSEN, even when an affix also depends on it. Restamping it would
    overstate the closure's contribution in the very counter the report
    renders, and duplicating it would plan the same object twice."""
    selection = Selection(categories={
        GrammarCategory.AFFIXES: True,
        GrammarCategory.GRAM_CATEGORIES: True,
    })
    plan = _build(monkeypatch, selection)
    pos_actions = _actions_for(plan, GrammarCategory.GRAM_CATEGORIES)
    assert len(pos_actions) == 1, "the pull-in must not duplicate the member"
    assert pos_actions[0].pulled_in_by == ()
    rpt = report_mod.RunReport.build_from_plan(plan, RunMode.PREVIEW)
    assert rpt.per_category[
        GrammarCategory.GRAM_CATEGORIES].closure_pulled_in == 0


def test_a_dependency_its_category_cannot_enumerate_is_reported(
    monkeypatch,
) -> None:
    """Never-silent (FR-023). The walk named a ref the dependency's own
    category cannot produce a piece for -- T089's live shape, where
    `MSA_TO_INFL_FEATURE`'s far endpoint is an `IFsSymFeatVal` that
    `inflection_features_enumerate_source` never yields. The item cannot be
    planned; the plan must say so rather than drop it."""
    plan = _build(monkeypatch, pos_pieces=())
    assert _actions_for(plan, GrammarCategory.GRAM_CATEGORIES) == []
    unresolved = [
        s for s in plan.skips
        if s.reason == SkipReason.DEPENDENCY_UNRESOLVED
        and s.source_guid == POS_G
    ]
    assert len(unresolved) == 1
    assert "closure" in unresolved[0].detail.lower()


# ===========================================================================
# T071 -- FR-016: deselection, through the machinery that already existed
# ===========================================================================

def test_a_deselected_dependency_is_not_planned(monkeypatch) -> None:
    """`Selection.excluded_deps` is the per-item deselection set. Before this
    task its only consumer was the verb-vertical POS check at
    preview.py:2269, so a GUID in it had no effect on the closure path at
    all."""
    selection = Selection(
        categories={GrammarCategory.AFFIXES: True},
        excluded_deps=frozenset({POS_G}),
    )
    plan = _build(monkeypatch, selection)
    assert _actions_for(plan, GrammarCategory.GRAM_CATEGORIES) == []


def test_a_deselected_dependency_is_reported_not_dropped(monkeypatch) -> None:
    """`SkipReason.DEPENDENCY_DESELECTED` exists for exactly this and had no
    emitter. A deselection that leaves no trace is indistinguishable from a
    closure that never found the dependency."""
    selection = Selection(
        categories={GrammarCategory.AFFIXES: True},
        excluded_deps=frozenset({POS_G}),
    )
    plan = _build(monkeypatch, selection)
    deselected = [
        s for s in plan.skips
        if s.reason == SkipReason.DEPENDENCY_DESELECTED
    ]
    assert len(deselected) == 1
    assert deselected[0].source_guid == POS_G
    assert deselected[0].category == GrammarCategory.GRAM_CATEGORIES
    assert AFFIX_G[:8] in deselected[0].detail, (
        "the skip must name what is left incomplete by the deselection")


def test_the_edge_records_that_its_dependency_was_deselected(
    monkeypatch,
) -> None:
    """`ClosureEdge.deselected` landed with the Phase 2 foundational types
    (T066) and was never written by anything. T073 builds
    `IncompletenessRecord`s from these edges, so the edge -- not just the
    skip -- has to carry the fact."""
    selection = Selection(
        categories={GrammarCategory.AFFIXES: True},
        excluded_deps=frozenset({POS_G}),
    )
    plan = _build(monkeypatch, selection)
    assert len(plan.closure_edges) == 1
    edge = plan.closure_edges[0]
    assert edge.deselected is True
    assert edge.dependency == POS_REF
    assert edge.origin == "pulled_in"


def test_an_edge_whose_dependency_was_kept_is_not_marked_deselected(
    monkeypatch,
) -> None:
    """The negative that makes the assertion above mean something."""
    plan = _build(monkeypatch)
    assert plan.closure_edges[0].deselected is False


def test_a_category_scoped_none_suppresses_the_pull_in(monkeypatch) -> None:
    """`Selection.scope_for`'s three-scope mapping is the WHOLE-CATEGORY
    deselection knob (CategoryScope.NONE), sibling to the per-item set. Reused
    rather than reinvented: research.md R3 names both."""
    selection = Selection(
        categories={GrammarCategory.AFFIXES: True},
        category_scopes={GrammarCategory.GRAM_CATEGORIES: CategoryScope.NONE},
    )
    plan = _build(monkeypatch, selection)
    assert _actions_for(plan, GrammarCategory.GRAM_CATEGORIES) == []
    assert plan.closure_edges[0].deselected is True


def test_include_closure_false_pulls_nothing_in(monkeypatch) -> None:
    """The back-compatible spelling of the same knob: `include_closure=False`
    means every category with no explicit scope is NONE. A plan built that way
    must not start pulling items in because a registry row was added."""
    selection = Selection(
        categories={GrammarCategory.AFFIXES: True},
        include_closure=False,
    )
    plan = _build(monkeypatch, selection)
    assert _actions_for(plan, GrammarCategory.GRAM_CATEGORIES) == []


def test_scope_as_needed_is_the_default_and_pulls_in(monkeypatch) -> None:
    """The default has to be inclusion (FR-014 says "by default"), and the
    default is what every existing caller that passes no `category_scopes`
    gets."""
    selection = Selection(categories={GrammarCategory.AFFIXES: True})
    assert selection.scope_for(
        GrammarCategory.GRAM_CATEGORIES) == CategoryScope.AS_NEEDED
    plan = _build(monkeypatch, selection)
    assert len(_actions_for(plan, GrammarCategory.GRAM_CATEGORIES)) == 1


# ===========================================================================
# The empty-registry canary -- the pull-in must not fire without FR-018
# ===========================================================================

def test_an_empty_registry_pulls_nothing_in(monkeypatch) -> None:
    """FR-018 is upstream of FR-014: with no verified relationship there are
    no edges, so there is nothing to pull in. Asserting it here as well as in
    test_038_closure.py is the point -- this is the layer that would newly
    ADD objects to a target, so a leak here writes data."""
    def _producer(piece):
        return (POS_REF,)

    patched = dict(categories_mod.LEAF_CATEGORIES)
    patched[GrammarCategory.AFFIXES] = _fake_bundle(
        GrammarCategory.AFFIXES, AFFIX_G, producer=_producer)
    patched[GrammarCategory.GRAM_CATEGORIES] = _fake_bundle(
        GrammarCategory.GRAM_CATEGORIES, POS_G)
    monkeypatch.setattr(categories_mod, "LEAF_CATEGORIES", patched)
    monkeypatch.setattr(categories_mod, "CLOSURE_EDGES_VERIFIED", {})
    plan = preview_mod.build_run_plan(
        _ctx(), Selection(categories={GrammarCategory.AFFIXES: True}),
        WSMapping(), SimpleNamespace(), SimpleNamespace(),
    )
    assert plan.closure_edges == ()
    assert _actions_for(plan, GrammarCategory.GRAM_CATEGORIES) == []


# ===========================================================================
# T093 -- a REFUSED dependency that is nevertheless ALREADY IN THE DESTINATION
# ===========================================================================
#
# T071 suppresses a deselected ref BEFORE its planner runs. That is correct
# for the PLAN -- a refused dependency must not be written -- and it is what
# `test_a_deselected_dependency_is_not_planned` above pins. What it also did
# was leave `_plan_incompleteness` with no way to tell a dependency that is
# MISSING from one that is merely NOT BEING RE-TRANSFERRED: no
# `ALREADY_PRESENT_BY_*` skip exists on that path, so every deselected
# dependency looked absent. Measured on `Mbugwe LizzieHC practice`: 2 of the
# 5 pulled-in POSes were already in the target and 8 of T073's 35 records
# named one of them -- ~23% phantom loss, the failure shape CLAUDE.md records
# for flexicon 4.5.1's natural-class features.
#
# The repair asks the DEPENDENCY'S OWN PLANNER and keeps nothing but its
# verdict. Not a GUID probe: a bare `guid in target` check is Defect G3's
# exact shape, the premise this feature exists to remove.

def _deselect_pos():
    return Selection(
        categories={GrammarCategory.AFFIXES: True},
        excluded_deps=frozenset({POS_G}),
    )


def _pos_overwrite(pc, context, ws):
    """The live shape: T070 planned 2 of the 5 pulled-in POSes as OVERWRITEs,
    which is the planner saying "this object is already there"."""
    return PlannedOverwrite(
        category=GrammarCategory.GRAM_CATEGORIES,
        source_guid=POS_G,
        target_guid=POS_G,
        summary="T093 fake merge",
        write_mode="merge",
    )


def _pos_already_present(pc, context, ws):
    return Skip(
        category=GrammarCategory.GRAM_CATEGORIES,
        source_guid=POS_G,
        reason=SkipReason.ALREADY_PRESENT_BY_IDENTITY,
        detail="T093 fake identity match",
    )


def test_a_deselected_dependency_that_is_already_there_is_not_an_incompleteness(
    monkeypatch,
) -> None:
    """THE DEFECT ITSELF. The user refused to re-transfer a POS that the
    destination already has; the affix's reference resolves against the object
    that is there, so nothing arrives incomplete and the report must say
    nothing. Before this task it said the affix was unwired."""
    plan = _build(monkeypatch, _deselect_pos(),
                  pos_plan_action=_pos_overwrite)
    assert plan.incompleteness == ()


def test_an_already_present_skip_from_the_probe_counts_the_same(
    monkeypatch,
) -> None:
    """The other verdict that means "already there". `PlannedOverwrite` is a
    match that will be enriched; `ALREADY_PRESENT_BY_IDENTITY` is a match with
    nothing to write. Both resolve the dependent's reference."""
    plan = _build(monkeypatch, _deselect_pos(),
                  pos_plan_action=_pos_already_present)
    assert plan.incompleteness == ()


def test_the_refusal_is_still_a_refusal(monkeypatch) -> None:
    """WHY THIS IS NOT REPAIR (a) FROM THE TASK LINE. Running the refused
    ref's planner to learn the presence fact must not turn the refusal into
    something else: no POS is planned, and the skip the user sees is still
    `DEPENDENCY_DESELECTED` -- not the `ALREADY_PRESENT_*` its planner
    happened to return. T071's measured composition is unchanged."""
    plan = _build(monkeypatch, _deselect_pos(),
                  pos_plan_action=_pos_overwrite)
    assert _actions_for(plan, GrammarCategory.GRAM_CATEGORIES) == []
    assert [ow for ow in plan.overwrites
            if ow.category == GrammarCategory.GRAM_CATEGORIES] == []
    pos_skips = [s for s in plan.skips
                 if s.category == GrammarCategory.GRAM_CATEGORIES]
    assert [s.reason for s in pos_skips] == [SkipReason.DEPENDENCY_DESELECTED]


def test_the_edge_is_still_marked_deselected(monkeypatch) -> None:
    """The edge records what the USER did. Presence changes what is reported
    as incomplete, not the history of the selection -- an edge that lost its
    `deselected` stamp would make T071's own measurement unreadable."""
    plan = _build(monkeypatch, _deselect_pos(),
                  pos_plan_action=_pos_overwrite)
    assert [e.deselected for e in plan.closure_edges] == [True]


def test_a_deselected_dependency_that_is_NOT_there_is_still_reported(
    monkeypatch,
) -> None:
    """THE REGRESSION GUARD, and the reason the fix is a probe rather than a
    blanket exemption. The default fake planner returns an ADD -- the POS is
    not in the destination -- so the affix really does arrive unwired and
    FR-017 must still say so. This is 27 of the 35 live records."""
    plan = _build(monkeypatch, _deselect_pos())
    assert [r.cause for r in plan.incompleteness] == ["deselected"]


def test_a_probe_that_raises_reports_the_dependency_missing(
    monkeypatch,
) -> None:
    """UNKNOWN RESOLVES TO "REPORT IT". A planner that raises tells us
    nothing about the destination, and Principle I's failure is the silent
    one: over-reporting one item is recoverable, a quiet loss is not."""
    def _boom(pc, context, ws):
        raise RuntimeError("T093 fake planner failure")

    plan = _build(monkeypatch, _deselect_pos(), pos_plan_action=_boom)
    assert [r.cause for r in plan.incompleteness] == ["deselected"]


def test_the_probe_does_not_fire_when_nothing_is_deselected(
    monkeypatch,
) -> None:
    """The quiet case is untouched: with no deselection the POS is planned
    normally (T070) and there is nothing to report either way."""
    plan = _build(monkeypatch, pos_plan_action=_pos_overwrite)
    assert plan.incompleteness == ()
    assert len([ow for ow in plan.overwrites
                if ow.category == GrammarCategory.GRAM_CATEGORIES]) == 1
