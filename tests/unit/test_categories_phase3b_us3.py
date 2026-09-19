"""Phase 3b US3 unit tests: variant_types, complex_form_types,
semantic_domains callbacks (T024, T027, T030).

execute_action requires live LCM (factory.Create + Cache.LangProject);
exercised at live MCP time only. The tests here cover enumerate_source,
dependencies, plan_action GOLD-skip and ALREADY_PRESENT_BY_GUID skip
paths.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.models import (
    GrammarCategory,
    PlannedAction,
    RunContext,
    Selection,
    Skip,
    SkipReason,
    WSMapping,
)


# ============================================================================
# Fakes
# ============================================================================

class _Node:
    """CmPossibility-shaped node. Children belong to SubPossibilitiesOS."""
    def __init__(self, guid, catalog_source_id="", children=(), owner=None,
                 infl_feats=None):
        self.guid = guid
        self.Guid = guid
        self.CatalogSourceId = catalog_source_id
        self.SubPossibilitiesOS = list(children)
        self.Owner = owner
        if infl_feats is not None:
            self.InflFeatsOA = infl_feats
        # back-link children to self
        for c in children:
            c.Owner = self

    @property
    def concrete(self):
        return self


class _List:
    """CmPossibilityList-shaped owning collection."""
    def __init__(self, guid, items=()):
        self.guid = guid
        self.Guid = guid
        self.PossibilitiesOS = list(items)
        for i in items:
            i.Owner = self


class _LexDb:
    def __init__(self, variants=None, complex_forms=None):
        self.VariantEntryTypesOA = variants or _List("vlst-empty", [])
        self.ComplexEntryTypesOA = complex_forms or _List("clst-empty", [])


class _LangProject:
    def __init__(self, lex_db=None, sem_dom_list=None):
        self.LexDbOA = lex_db or _LexDb()
        self.SemanticDomainListOA = sem_dom_list or _List("sdlst-empty", [])


class _Cache:
    def __init__(self, lp=None):
        self.LangProject = lp or _LangProject()


class _Project:
    def __init__(self, lp=None):
        self.Cache = _Cache(lp)


class _FsSpec:
    def __init__(self, val_guid, feature=None):
        self.ValueRA = _ValueRef(val_guid, owner=feature)
        if feature is not None:
            self.FeatureRA = feature


class _ValueRef:
    def __init__(self, guid, owner=None):
        self.guid = guid
        self.Guid = guid
        if owner is not None:
            # T089: `ICmObject.Owner`. An `IFsSymFeatVal` is owned by the
            # `IFsClosedFeature` whose `ValuesOC` holds it, and that owner is
            # the endpoint the dependency now names -- the value itself is not
            # something `inflection_features_enumerate_source` yields.
            self.Owner = owner


class _FeatStruc:
    def __init__(self, value_guids, feature_guid=None):
        feature = None if feature_guid is None else _ValueRef(feature_guid)
        self.FeatureSpecsOC = [_FsSpec(g, feature) for g in value_guids]


def _ctx(src, tgt) -> RunContext:
    return RunContext(
        source_handle=src, source_project_name="Src", source_project_path="/s",
        target_handle=tgt, target_project_name="Tgt", target_project_path="/t",
        run_id="GT-3B-US3", started_at="2026-06-21T02:20:00",
    )


WSM = WSMapping(entries=())
SEL = Selection(categories={})


@pytest.fixture(autouse=True)
def _patch_guid(monkeypatch):
    monkeypatch.setattr(categories, "_guid_str_from", lambda o: o.guid)


# ============================================================================
# variant_types
# ============================================================================

def test_variant_types_enumerate_recursive() -> None:
    leaf = _Node("vt-leaf")
    parent = _Node("vt-parent", children=[leaf])
    lst = _List("vt-list", [parent])
    src = _Project(_LangProject(lex_db=_LexDb(variants=lst)))
    tgt = _Project()
    items = categories.variant_types_enumerate_source(_ctx(src, tgt), SEL)
    assert {n.guid for n in items} == {"vt-parent", "vt-leaf"}


def test_variant_types_enumerate_empty_no_lexdb() -> None:
    """Missing LexDb / VariantEntryTypesOA returns [] gracefully."""
    items = categories.variant_types_enumerate_source(
        _ctx(object(), object()), SEL
    )
    assert list(items) == []


def test_variant_types_dependencies_walks_inflfeats() -> None:
    """T089: the constraint's two `IFsSymFeatVal`s collapse onto the ONE
    feature that owns them. The value guids used to be emitted directly, and
    nothing enumerates an `IFsSymFeatVal` -- so those edges named an endpoint
    that could be neither planned (FR-015) nor deselected (FR-016)."""
    fs = _FeatStruc(value_guids=["val-a", "val-b"], feature_guid="feat-1")
    vt = _Node("vt-with-constraint", infl_feats=fs)
    deps = tuple(categories.variant_types_dependencies(vt))
    assert deps == ((GrammarCategory.INFLECTION_FEATURES, "feat-1"),)


def test_variant_types_dependencies_drop_a_value_with_no_owning_feature() -> None:
    """The absence of a plannable endpoint, not the dropping of one: a value
    whose `Owner` is unreadable and whose spec declares no `FeatureRA` names
    nothing this repo can enumerate, so no edge is the correct output."""
    fs = _FeatStruc(value_guids=["val-a"])  # no owner, no FeatureRA
    vt = _Node("vt-orphan-constraint", infl_feats=fs)
    assert tuple(categories.variant_types_dependencies(vt)) == ()


def test_variant_types_dependencies_empty_for_base_type() -> None:
    """A base ILexEntryType (no InflFeatsOA) yields no dependencies."""
    vt = _Node("vt-base")  # no infl_feats
    assert tuple(categories.variant_types_dependencies(vt)) == ()


def test_variant_types_plan_action_gold_absent_transfers() -> None:
    """v7.0.0 GOLD unlock: a GOLD variant type is an ordinary item; absent from
    the target it transfers (PlannedAction), not a GOLD_INVIOLABLE skip."""
    gold = _Node("vt-gold", catalog_source_id="varent-gold-spelling")
    src = _Project()
    tgt = _Project()
    result = categories.variant_types_plan_action(gold, _ctx(src, tgt), WSM)
    assert isinstance(result, PlannedAction)
    assert result.category == GrammarCategory.VARIANT_TYPES


def test_variant_types_plan_action_emits_planned_action_for_user_defined() -> None:
    vt = _Node("vt-custom")
    src = _Project()
    tgt = _Project()
    result = categories.variant_types_plan_action(vt, _ctx(src, tgt), WSM)
    assert isinstance(result, PlannedAction)
    assert result.source_guid == "vt-custom"
    assert result.category == GrammarCategory.VARIANT_TYPES


def test_variant_types_plan_action_already_present_skip() -> None:
    vt = _Node("vt-dup")
    src = _Project()
    tgt = _Project(_LangProject(lex_db=_LexDb(variants=_List("vl", [_Node("vt-dup")]))))
    result = categories.variant_types_plan_action(vt, _ctx(src, tgt), WSM)
    assert isinstance(result, Skip)
    assert result.reason == SkipReason.ALREADY_PRESENT_BY_GUID


# ============================================================================
# complex_form_types
# ============================================================================

def test_complex_form_types_enumerate_recursive() -> None:
    leaf = _Node("cft-leaf")
    parent = _Node("cft-parent", children=[leaf])
    lst = _List("cl", [parent])
    src = _Project(_LangProject(lex_db=_LexDb(complex_forms=lst)))
    tgt = _Project()
    items = categories.complex_form_types_enumerate_source(_ctx(src, tgt), SEL)
    assert {n.guid for n in items} == {"cft-parent", "cft-leaf"}


def test_complex_form_types_dependencies_is_leaf() -> None:
    assert categories.complex_form_types_dependencies(_Node("cft-x")) == ()


def test_complex_form_types_plan_action_gold_absent_transfers() -> None:
    """v7.0.0 GOLD unlock: a GOLD complex-form type is ordinary; absent from the
    target it transfers (PlannedAction), not a GOLD_INVIOLABLE skip."""
    gold = _Node("cft-gold", catalog_source_id="cmpd")
    result = categories.complex_form_types_plan_action(
        gold, _ctx(_Project(), _Project()), WSM
    )
    assert isinstance(result, PlannedAction)


def test_complex_form_types_plan_action_user_defined_emits_action() -> None:
    cft = _Node("cft-user")
    result = categories.complex_form_types_plan_action(
        cft, _ctx(_Project(), _Project()), WSM
    )
    assert isinstance(result, PlannedAction)
    assert result.source_guid == "cft-user"


def test_complex_form_types_plan_action_already_present_skip() -> None:
    cft = _Node("cft-dup")
    tgt = _Project(_LangProject(lex_db=_LexDb(
        complex_forms=_List("cl", [_Node("cft-dup")])
    )))
    result = categories.complex_form_types_plan_action(cft, _ctx(_Project(), tgt), WSM)
    assert isinstance(result, Skip)
    assert result.reason == SkipReason.ALREADY_PRESENT_BY_GUID


# ============================================================================
# semantic_domains  (FR-326 GOLD catalog skip)
# ============================================================================

def test_semantic_domains_enumerate_recursive() -> None:
    leaf = _Node("sd-leaf")
    parent = _Node("sd-parent", children=[leaf])
    lst = _List("sdlst", [parent])
    src = _Project(_LangProject(sem_dom_list=lst))
    tgt = _Project()
    items = categories.semantic_domains_enumerate_source(_ctx(src, tgt), SEL)
    assert {n.guid for n in items} == {"sd-parent", "sd-leaf"}


def test_semantic_domains_plan_action_gold_catalog_absent_transfers() -> None:
    """v7.0.0 GOLD unlock: a standard FW catalog entry (CatalogSourceId set) is
    an ordinary item -- absent from the target it now transfers (PlannedAction)
    instead of a GOLD_INVIOLABLE skip. NOTE: whether the ~1792-item SEMANTIC_DOMAINS
    catalog should be guarded against bulk-copy is an open Half-2 design decision."""
    catalog = _Node("sd-1.2.3", catalog_source_id="SemDom-1.2.3")
    result = categories.semantic_domains_plan_action(
        catalog, _ctx(_Project(), _Project()), WSM
    )
    assert isinstance(result, PlannedAction)
    assert result.category == GrammarCategory.SEMANTIC_DOMAINS


def test_semantic_domains_plan_action_custom_emits_action() -> None:
    custom = _Node("sd-custom")
    result = categories.semantic_domains_plan_action(
        custom, _ctx(_Project(), _Project()), WSM
    )
    assert isinstance(result, PlannedAction)
    assert result.source_guid == "sd-custom"
    assert result.category == GrammarCategory.SEMANTIC_DOMAINS


def test_semantic_domains_plan_action_already_present_skip() -> None:
    sd = _Node("sd-dup")
    tgt = _Project(_LangProject(sem_dom_list=_List("sdl", [_Node("sd-dup")])))
    result = categories.semantic_domains_plan_action(sd, _ctx(_Project(), tgt), WSM)
    assert isinstance(result, Skip)
    assert result.reason == SkipReason.ALREADY_PRESENT_BY_GUID


# ============================================================================
# Helper sanity
# ============================================================================

def test_walk_possibilities_handles_none() -> None:
    assert categories._walk_possibilities(None) == []


def test_walk_possibilities_deeply_nested() -> None:
    g3 = _Node("g3")
    g2 = _Node("g2", children=[g3])
    g1 = _Node("g1", children=[g2])
    g0 = _Node("g0", children=[g1])
    lst = _List("root", [g0])
    items = categories._walk_possibilities(lst)
    assert {n.guid for n in items} == {"g0", "g1", "g2", "g3"}
