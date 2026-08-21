"""Feature 038 -- T065 (Phase 7, US3): the FR-018 gate, asserted where it
actually has to hold.

FR-018: "Each declared dependency relationship MUST be verified as correct
before it is allowed to influence a plan."

The mechanism is `categories.CLOSURE_EDGES_VERIFIED`, a per-relationship
allowlist keyed by `DependencyKind` (research.md R3). All 23
`*_dependencies()` producers in `Lib/categories.py` are unverified by
construction, so the registry ships EMPTY and emptiness is the safety
property.

WHY THIS FILE EXISTS, GIVEN test_038_foundational.py ALREADY HAS
`TestBuildRunPlanClosureGate`. That class is named for `build_run_plan` and
its docstring says "`build_run_plan` must RAISE on an unverified edge" -- but
every one of its assertions calls the HELPER, `preview._materialise_closure_
edges`, directly. The public entry point is never invoked, so nothing there
would notice if `build_run_plan`'s call site grew a `try/except Exception`
around `_walk_verified_closure` and turned the gate into a warning nobody
reads. That is the same shape as the defects T048b, T086 and T087 each
record: a signal that genuinely exists, read at a level where it cannot do
its job. The tests below drive `build_run_plan` itself.

THE TRICHOTOMY. An edge is in exactly one of three states, and each has a
different required outcome -- which is why one global "closure is on" flag
cannot satisfy FR-018 at all:

    unregistered          -> the producer is NEVER CALLED (no edges)
    registered, unverified -> build_run_plan RAISES
    registered, verified   -> the edge reaches plan.closure_edges

Asserting only the first two would leave them both satisfiable by a closure
walk that is simply broken, so the third is what makes the other two mean
something.

COVERAGE HONESTY. These run against duck-typed fakes with `LEAF_CATEGORIES`
patched for one category, so what is pinned is the GATE's behaviour, not any
real producer's edge set. No producer is registered here and none is
verified: auditing the three real edges against a live pair is T067-T069, and
`verified_by` must name that audit rather than this file.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from gramtrans.Lib import categories as categories_mod
from gramtrans.Lib import preview as preview_mod
from gramtrans.Lib.models import (
    DependencyKind,
    GrammarCategory,
    PlannedAction,
    RunContext,
    Selection,
    WSMapping,
)

# Lower-case throughout: `categories._guid_str_from` lower-cases every GUID it
# extracts, and `closure_dependencies_for` indexes its piece cache by that
# lower-cased form. A mixed-case literal here would look fine and silently
# miss the cache.
AFFIX_G = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
POS_G = "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb"
SLOT_G = "cccccccc-3333-4333-8333-cccccccccccc"
TEMPLATE_G = "dddddddd-4444-4444-8444-dddddddddddd"

AFFIX_REF = (GrammarCategory.AFFIXES, AFFIX_G)
POS_REF = (GrammarCategory.GRAM_CATEGORIES, POS_G)


# ===========================================================================
# Harness
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


class _SpyProducer:
    """A `*_dependencies(piece)` stand-in that records every call.

    The call COUNT is the point. "The unregistered producer returned no
    edges" is a weaker claim than "the unregistered producer was never
    consulted", and only the latter rules out a fall-through path that reads
    `LEAF_CATEGORIES[...]["dependencies"]` behind the registry's back.
    """

    def __init__(self, refs=(POS_REF,)) -> None:
        self.refs = tuple(refs)
        self.calls: list = []

    def __call__(self, piece):
        self.calls.append(piece)
        return self.refs


def _fake_bundle(category, guid, producer, summary):
    piece = SimpleNamespace(guid=guid)
    bundle = dict(categories_mod.LEAF_CATEGORIES[category])
    bundle["enumerate_source"] = lambda context, selection: [piece]
    bundle["plan_action"] = lambda pc, context, ws: PlannedAction(
        category=category,
        source_guid=guid,
        intended_target_guid=guid,
        summary=summary,
    )
    bundle["dependencies"] = producer
    return bundle


def _patch_bundles(monkeypatch, by_category):
    """Point LEAF_CATEGORIES at one fake piece per named category.

    `LEAF_CATEGORIES` is patched rather than `for_category` because the two
    consumers reach the bundle by different routes: `build_run_plan`'s leaf
    dispatch goes through `for_category`, which is a one-line read of
    `LEAF_CATEGORIES`, while `closure_dependencies_for._pieces_for` subscripts
    `LEAF_CATEGORIES` directly. Patching the dict covers both; patching
    `for_category` would leave the closure walk enumerating the real source.
    """
    patched = dict(categories_mod.LEAF_CATEGORIES)
    for category, (guid, producer) in by_category.items():
        patched[category] = _fake_bundle(
            category, guid, producer, "T065 fake " + category.value
        )
    monkeypatch.setattr(categories_mod, "LEAF_CATEGORIES", patched)
    return patched


def _patch_affixes_bundle(monkeypatch, producer):
    _patch_bundles(monkeypatch, {GrammarCategory.AFFIXES: (AFFIX_G, producer)})


def _registry(producer, *, verified=None, verified_by="T065 fake audit"):
    """One AFFIX_TO_POS row.

    `verified` is omitted rather than passed as True in the verified case, so
    these tests exercise the same default the real registry rows will use.
    """
    entry = {
        "category": GrammarCategory.AFFIXES,
        "producer": producer,
        "dependency_category": None,  # the producer yields full refs
        "verified_by": verified_by,
    }
    if verified is not None:
        entry["verified"] = verified
    return {DependencyKind.AFFIX_TO_POS: entry}


def _build(monkeypatch, registry, producer):
    _patch_affixes_bundle(monkeypatch, producer)
    monkeypatch.setattr(categories_mod, "CLOSURE_EDGES_VERIFIED", registry)
    selection = Selection(categories={GrammarCategory.AFFIXES: True})
    return preview_mod.build_run_plan(
        _ctx(), selection, WSMapping(), SimpleNamespace(), SimpleNamespace()
    )


# ===========================================================================
# State 1 -- unregistered: the producer is never consulted
# ===========================================================================

def test_an_empty_registry_short_circuits_the_walk_entirely(monkeypatch) -> None:
    """With nothing verified, `_walk_verified_closure` returns before it even
    builds a dependency callable.

    NOTE what this does and does not prove. It pins the short-circuit, which
    is a real and desirable property -- no work whose result must be empty.
    It does NOT prove the per-relationship gate, because with an empty
    registry the gate inside `closure_dependencies_for` is never reached at
    all. `test_a_registered_edge_does_not_admit_its_unregistered_neighbour`
    below is what covers that, and it is the one that fails if the gate grows
    a fall-through to `LEAF_CATEGORIES[...]["dependencies"]`.
    """
    spy = _SpyProducer()
    plan = _build(monkeypatch, {}, spy)
    assert spy.calls == []
    assert plan.closure_edges == ()


def test_a_registered_edge_does_not_admit_its_unregistered_neighbour(
    monkeypatch,
) -> None:
    """The per-relationship guarantee, and the reason a global flag cannot
    satisfy FR-018.

    The walk is RUNNING here -- AFFIX_TO_POS is registered and verified -- so
    the empty-registry short-circuit is not what protects the second
    relationship. SLOTS is selected, planned, and therefore handed to the
    dependency callable as a seed; its producer is simply not registered, and
    must never be consulted. A fall-through to
    `LEAF_CATEGORIES[SLOTS]["dependencies"]` would let an unaudited edge set
    into the plan under a neighbouring relationship's verification.
    """
    affix_spy = _SpyProducer(refs=(POS_REF,))
    slot_spy = _SpyProducer(refs=((GrammarCategory.AFFIX_TEMPLATES, TEMPLATE_G),))
    _patch_bundles(monkeypatch, {
        GrammarCategory.AFFIXES: (AFFIX_G, affix_spy),
        GrammarCategory.SLOTS: (SLOT_G, slot_spy),
    })
    monkeypatch.setattr(
        categories_mod, "CLOSURE_EDGES_VERIFIED", _registry(affix_spy)
    )
    selection = Selection(categories={
        GrammarCategory.AFFIXES: True,
        GrammarCategory.SLOTS: True,
    })
    plan = preview_mod.build_run_plan(
        _ctx(), selection, WSMapping(), SimpleNamespace(), SimpleNamespace()
    )

    assert affix_spy.calls, "the registered producer must be consulted"
    assert slot_spy.calls == [], (
        "an unregistered producer was consulted while the walk was running -- "
        "the registry gates relationships individually, not globally"
    )
    kinds = {edge.kind for edge in plan.closure_edges}
    assert kinds == {DependencyKind.AFFIX_TO_POS}
    dependencies = {edge.dependency for edge in plan.closure_edges}
    assert (GrammarCategory.AFFIX_TEMPLATES, TEMPLATE_G) not in dependencies


def test_the_empty_registry_changes_nothing_else_about_the_plan(monkeypatch) -> None:
    """Phase 2's safety claim, at `build_run_plan` rather than at the helper:
    a producer that WOULD yield an edge leaves the plan byte-identical to one
    that yields nothing, because neither is consulted."""
    would_yield = _build(monkeypatch, {}, _SpyProducer(refs=(POS_REF,)))
    yields_nothing = _build(monkeypatch, {}, _SpyProducer(refs=()))
    for plan in (would_yield, yields_nothing):
        assert plan.closure_edges == ()
    assert len(would_yield.actions) == len(yields_nothing.actions) == 1
    assert len(would_yield.skips) == len(yields_nothing.skips)
    assert len(would_yield.overwrites) == len(yields_nothing.overwrites)


# ===========================================================================
# State 2 -- registered but unverified: build_run_plan RAISES
# ===========================================================================

def test_build_run_plan_raises_on_an_unverified_edge(monkeypatch) -> None:
    """T065's headline claim, asserted at the public entry point.

    `_materialise_closure_edges` raising is necessary but not sufficient: the
    gate only protects anything if the raise propagates out of
    `build_run_plan` instead of being logged and discarded on the way.
    """
    spy = _SpyProducer()
    with pytest.raises(ValueError, match="UNVERIFIED"):
        _build(monkeypatch, _registry(spy, verified=False), spy)


def test_the_unverified_raise_names_the_relationship(monkeypatch) -> None:
    """A refusal that does not say WHICH relationship is unverified cannot be
    acted on -- the operator has 23 producers to choose from."""
    spy = _SpyProducer()
    with pytest.raises(ValueError) as excinfo:
        _build(monkeypatch, _registry(spy, verified=False), spy)
    message = str(excinfo.value)
    assert "AFFIX_TO_POS" in message
    assert AFFIX_G in message and POS_G in message


def test_no_plan_is_returned_when_an_edge_is_unverified(monkeypatch) -> None:
    """FR-018 says the edge must not INFLUENCE a plan. Degrading to "plan
    built, edge dropped" would satisfy the letter and lose the point: the
    operator would get a plan that silently transfers less than the closure
    said it needed."""
    spy = _SpyProducer()
    result = None
    with pytest.raises(ValueError, match="UNVERIFIED"):
        result = _build(monkeypatch, _registry(spy, verified=False), spy)
    assert result is None


# ===========================================================================
# State 3 -- registered and verified: the edge reaches the plan
#
# Without this group, both groups above are satisfiable by a closure walk
# that never produces an edge at all.
# ===========================================================================

def test_a_verified_edge_reaches_the_plan(monkeypatch) -> None:
    spy = _SpyProducer()
    plan = _build(monkeypatch, _registry(spy), spy)
    assert spy.calls, "a registered producer must actually be consulted"
    assert len(plan.closure_edges) == 1
    edge = plan.closure_edges[0]
    assert edge.dependent == AFFIX_REF
    assert edge.dependency == POS_REF
    assert edge.kind is DependencyKind.AFFIX_TO_POS
    assert edge.verified is True
    assert edge.verified_by == "T065 fake audit"


def test_the_pulled_in_item_is_marked_pulled_in_not_chosen(monkeypatch) -> None:
    """FR-015: the POS arrived because the affix needed it, and the plan has
    to say so. `closure.walk`'s seed semantics put the affix in `chosen`; the
    POS nobody selected is `pulled_in`."""
    spy = _SpyProducer()
    plan = _build(monkeypatch, _registry(spy), spy)
    assert plan.closure_edges[0].origin == "pulled_in"


def test_registration_is_the_only_difference_between_raise_and_edge(
    monkeypatch,
) -> None:
    """Same producer, same fake source, same selection -- only `verified`
    differs. That isolates the gate as the cause of both outcomes, rather
    than some difference in what the walk found."""
    spy = _SpyProducer()
    plan = _build(monkeypatch, _registry(spy, verified=True), spy)
    assert len(plan.closure_edges) == 1

    spy_again = _SpyProducer()
    with pytest.raises(ValueError, match="UNVERIFIED"):
        _build(monkeypatch, _registry(spy_again, verified=False), spy_again)


# ===========================================================================
# The registry's own guard rails, exercised through build_run_plan
# ===========================================================================

def test_a_row_without_evidence_cannot_influence_a_plan(monkeypatch) -> None:
    """`verified_by` is mandatory (FR-018). An empty one must fail loudly at
    registry-build time rather than be dropped -- a silently-skipped row is
    indistinguishable from a correctly-empty registry, which is exactly the
    ambiguity the allowlist exists to remove."""
    spy = _SpyProducer()
    with pytest.raises(ValueError, match="verified_by"):
        _build(monkeypatch, _registry(spy, verified_by=""), spy)


def test_the_shipped_registry_holds_only_what_was_audited() -> None:
    """The Phase 7 landing-order canary, updated BY T067 rather than deleted.

    Its predecessor asserted the registry was empty and said in so many words
    that it "is expected to CHANGE when T067 lands". T067 landed two rows, so
    this is that change: an exact set, not a non-emptiness check.

    An exact set is the point. A `>= 1 row` assertion would pass on a registry
    that had quietly grown a third row nobody audited, which is the one thing
    FR-018 must never allow. `MSA_TO_INFL_FEATURE` is named in the refusal set
    on purpose: its producer works and its edges are live, and it is STILL not
    registrable because 30 of 34 distinct far GUIDs on Mbugwe (8 of 10 on
    Ejagham Mini) are `IFsSymFeatVal` symbolic values that
    `inflection_features_enumerate_source` never yields (T089).
    """
    assert set(categories_mod.CLOSURE_EDGES_VERIFIED) == {
        DependencyKind.AFFIX_TO_POS,
        DependencyKind.MSA_TO_FEAT_STRUC_TYPE,
    }
    assert DependencyKind.MSA_TO_INFL_FEATURE not in \
        categories_mod.CLOSURE_EDGES_VERIFIED


def test_every_registered_row_names_a_narrow_producer() -> None:
    """The composite-producer trap T067 had to avoid, asserted rather than
    described.

    `affixes_dependencies` returns GRAM_CATEGORIES, FEATURE_STRUCT_TYPES and
    INFLECTION_FEATURES edges from one call. Registering it under a single
    `DependencyKind` would file two unaudited relationships under a third's
    `verified_by` -- so no row may name it, and every row must declare an
    EXPLICIT `dependency_category` (a `None` there is the `(AFFIXES, None)`
    wildcard in `preview._closure_kind_lookup`, which swallows its own
    siblings).
    """
    for kind, entry in categories_mod.CLOSURE_EDGES_VERIFIED.items():
        assert entry["producer"] is not categories_mod.affixes_dependencies, kind
        assert entry["dependency_category"] is not None, kind
        assert isinstance(entry["dependency_category"], GrammarCategory), kind
        assert entry["producer"].__name__.startswith("affixes_"), kind


def test_an_unregistered_far_category_from_a_registered_source_raises() -> None:
    """Why the narrow producers filter STRICTLY, stated as a consequence.

    `_feat_struc_deps` classifies a `TypeRA` by OWNERSHIP across BOTH feature
    systems, so an MSA whose structure pointed into `PhFeatureSystemOA` would
    hand back a `(PHON_FEAT_TYPES, guid)` edge. AFFIXES is a registered source
    but that far category is not a registered relationship, so
    `_materialise_closure_edges` RAISES -- which is correct (an edge no row
    authorises must not reach a plan) and is also why the producers drop such
    edges rather than passing them on and gambling on the raise.

    Neither corpus produced one (`foreign_edges == 0` on both), so this guard
    is live and currently unexercised by real data. That is exactly the kind of
    thing worth pinning rather than assuming.
    """
    from gramtrans.Lib import preview as preview_module

    affix = (GrammarCategory.AFFIXES, "a" * 8)
    phon_type = (GrammarCategory.PHON_FEAT_TYPES, "b" * 8)
    with pytest.raises(ValueError, match="FR-018"):
        preview_module._materialise_closure_edges(
            visit_order=(affix, phon_type),
            pulled_in_by={affix: (), phon_type: (affix,)},
            registry=categories_mod.CLOSURE_EDGES_VERIFIED,
        )


def test_the_registered_rows_do_not_collide_in_the_kind_lookup() -> None:
    """Two rows on the same source category is legal ONLY while their
    `dependency_category` values differ -- `_closure_kind_lookup` keys on the
    pair and RAISES on a collision. Both T067 rows are `category=AFFIXES`, so
    this is the assertion that keeps that legal."""
    from gramtrans.Lib import preview as preview_module

    lookup = preview_module._closure_kind_lookup(
        categories_mod.CLOSURE_EDGES_VERIFIED)
    assert set(lookup) == {
        (GrammarCategory.AFFIXES, GrammarCategory.GRAM_CATEGORIES),
        (GrammarCategory.AFFIXES, GrammarCategory.FEATURE_STRUCT_TYPES),
    }
