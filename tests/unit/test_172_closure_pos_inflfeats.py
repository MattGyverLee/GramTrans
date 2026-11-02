"""Issue #172 -- a POS created by dependency closure gets its
InflectableFeatsRC links through the single link pass.

`resolve_or_create_target_pos` (the closure creation path: owner/parent chain,
an allomorph's MsEnvPartOfSpeechRA) never went through `_plan_pos_piece`, so
the source POS's inflectable features were never stashed into
`plan.feature_category_links` and each pair surfaced as a named drop.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from gramtrans.Lib import categories as cat
from gramtrans.Lib.models import DroppedItemRecord


class _Obj:
    def __init__(self, guid, owner=None):
        self.guid = guid.lower()
        self.Owner = owner


class _Feat(_Obj):
    pass


class _RC:
    def __init__(self, items=()):
        self._items = list(items)

    def __iter__(self):
        return iter(list(self._items))

    def Add(self, x):
        self._items.append(x)


class _Pos(_Obj):
    def __init__(self, guid, owner=None, feats=()):
        super().__init__(guid, owner)
        self.InflectableFeatsRC = _RC(feats)


class _Factory:
    def __init__(self):
        self.made = []

    def Create(self, guid, owner):
        p = _Pos(str(guid))
        self.made.append(p)
        return p


class _Target:
    def __init__(self, objs=()):
        self.objs = {o.guid: o for o in objs}

    def get_object_by_guid(self, g):
        return self.objs.get(str(g).lower())


class _Plan:
    def __init__(self):
        self.feature_category_links = {}


def _ctx(target, plan):
    return SimpleNamespace(target_handle=target, source_handle=None,
                           _run_plan=plan, _dropped=[])


@pytest.fixture
def factory(monkeypatch):
    f = _Factory()
    monkeypatch.setattr(cat, "_get_pos_factory", lambda _t: f)
    monkeypatch.setattr(cat, "_resolve_target_pos", lambda *a, **k: None)
    monkeypatch.setattr(cat, "_owner_is_pos", lambda o: isinstance(o, _Pos))
    monkeypatch.setattr(cat, "_sync_pos_properties", lambda *a, **k: None)
    monkeypatch.setattr(cat, "_target_pos_for_source_guid",
                        lambda ctx, target, g: target.get_object_by_guid(g))
    return f


def _create(ctx, src_pos, target):
    new = cat.resolve_or_create_target_pos(ctx, src_pos, {}, "tag")
    if new is not None:
        target.objs[new.guid] = new  # a real LCM repository does this
    return new


def test_closure_created_pos_links_to_existing_features(factory):
    src = _Pos("p1", feats=[_Feat("f1"), _Feat("f2")])
    target = _Target([_Feat("f1"), _Feat("f2")])
    ctx = _ctx(target, _Plan())

    new = _create(ctx, src, target)
    assert ctx._run_plan.feature_category_links == {"p1": ["f1", "f2"]}

    assert cat._run_infl_feature_link_pass(ctx, target) == []
    assert ctx._dropped == []
    assert [x.guid for x in new.InflectableFeatsRC] == ["f1", "f2"]
    assert ctx._infl_feature_link_writes == 2


def test_ancestor_chain_created_by_closure_is_stashed_too(factory):
    parent_src = _Pos("parent", feats=[_Feat("f1")])
    child_src = _Pos("child", owner=parent_src, feats=[_Feat("f2")])
    target = _Target([_Feat("f1"), _Feat("f2")])
    ctx = _ctx(target, _Plan())

    # the parent is created first by the recursion; register it as it appears
    real_create = factory.Create

    def create_and_register(guid, owner):
        p = real_create(guid, owner)
        target.objs[p.guid] = p
        return p
    factory.Create = create_and_register

    _create(ctx, child_src, target)
    assert ctx._run_plan.feature_category_links == {
        "child": ["f2"], "parent": ["f1"]}
    assert cat._run_infl_feature_link_pass(ctx, target) == []
    assert ctx._infl_feature_link_writes == 2


def test_feature_absent_from_target_is_not_created_only_reported(factory):
    """Cycle-2 boundary: the pass links to features that EXIST; it never
    creates or edits one. An absent feature stays a named drop."""
    src = _Pos("p1", feats=[_Feat("f1")])
    target = _Target()  # no features
    ctx = _ctx(target, _Plan())
    new = _create(ctx, src, target)

    cat._run_infl_feature_link_pass(ctx, target)
    assert list(new.InflectableFeatsRC) == []
    assert len(ctx._dropped) == 1
    assert isinstance(ctx._dropped[0], DroppedItemRecord)
    assert ctx._dropped[0].item_guid == "f1"
    assert set(target.objs) == {"p1"}  # nothing but the POS was added


def test_leaf_pick_subset_is_honored_for_closure_pos(factory):
    src = _Pos("p1", feats=[_Feat("f1"), _Feat("f2")])
    target = _Target([_Feat("f1"), _Feat("f2")])
    ctx = _ctx(target, _Plan())
    ctx._selection = SimpleNamespace(
        is_on=lambda c: True, leaf_picks_for=lambda c: {"f2"})
    _create(ctx, src, target)
    assert ctx._run_plan.feature_category_links == {"p1": ["f2"]}


def test_pos_without_features_stashes_nothing(factory):
    target = _Target()
    ctx = _ctx(target, _Plan())
    _create(ctx, _Pos("p1"), target)
    assert ctx._run_plan.feature_category_links == {}


def test_stash_failure_does_not_undo_the_create(factory, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(cat, "_stash_feature_category_links", boom)
    target = _Target()
    ctx = _ctx(target, _Plan())
    assert _create(ctx, _Pos("p1", feats=[_Feat("f1")]), target) is not None


def test_no_stash_when_pos_was_not_created(factory, monkeypatch):
    """An already-present POS (resolved, not created) is left alone."""
    existing = _Pos("p1")
    monkeypatch.setattr(cat, "_resolve_target_pos", lambda *a, **k: existing)
    ctx = _ctx(_Target(), _Plan())
    got = cat.resolve_or_create_target_pos(
        ctx, _Pos("p1", feats=[_Feat("f1")]), {}, "tag")
    assert got is existing
    assert ctx._run_plan.feature_category_links == {}


# ---------------------------------------------------------------------------
# Preview twin (G6): Preview's link map must already name what Move links.
# ---------------------------------------------------------------------------

def test_preview_helper_skips_present_ancestor(factory, monkeypatch):
    parent_src = _Pos("parent", feats=[_Feat("f1")])
    child_src = _Pos("child", owner=parent_src, feats=[_Feat("f2")])
    present = {"parent": _Pos("parent")}  # Move creates only the child
    monkeypatch.setattr(cat, "_resolve_target_pos",
                        lambda target, g, **k: present.get(g))
    ctx = _ctx(_Target(), _Plan())
    cat.stash_feature_links_for_creatable_pos(ctx, child_src)
    assert ctx._run_plan.feature_category_links == {"child": ["f2"]}
    cat.stash_feature_links_for_creatable_pos(ctx, child_src)  # idempotent
    assert ctx._run_plan.feature_category_links == {"child": ["f2"]}


def test_preview_helper_includes_absent_ancestor(factory, monkeypatch):
    parent_src = _Pos("parent", feats=[_Feat("f1")])
    child_src = _Pos("child", owner=parent_src, feats=[_Feat("f2")])
    monkeypatch.setattr(cat, "_resolve_target_pos", lambda *a, **k: None)
    ctx = _ctx(_Target(), _Plan())
    cat.stash_feature_links_for_creatable_pos(ctx, child_src)
    assert ctx._run_plan.feature_category_links == {
        "child": ["f2"], "parent": ["f1"]}


def test_preview_helper_leaves_present_pos_alone(factory, monkeypatch):
    monkeypatch.setattr(cat, "_resolve_target_pos",
                        lambda *a, **k: _Pos("p1"))
    ctx = _ctx(_Target(), _Plan())
    cat.stash_feature_links_for_creatable_pos(
        ctx, _Pos("p1", feats=[_Feat("f1")]))
    assert ctx._run_plan.feature_category_links == {}


def test_plan_msenv_pos_ra_create_branch_stashes(factory, monkeypatch):
    from gramtrans.Lib import owned
    src_pos = _Pos("p1", feats=[_Feat("f1")])
    allo = SimpleNamespace(MsEnvPartOfSpeechRA=src_pos, guid="a1")
    monkeypatch.setattr(owned, "_cast_moaffix_allomorph", lambda a: a)
    monkeypatch.setattr(owned, "_resolve_target_pos_by_guid",
                        lambda *a, **k: None)
    monkeypatch.setattr(owned._references, "_guid_str",
                        lambda o: getattr(o, "guid", ""))
    monkeypatch.setattr(owned._references, "_item_label", lambda o: "x")
    monkeypatch.setattr(cat, "target_has_pos_create_infra", lambda t: True)
    ctx = _ctx(_Target(), _Plan())
    out = owned._plan_msenv_pos_ra(allo, ctx, [], resolver_cache={})
    assert out and out[0].action.name == "CREATE"
    assert ctx._run_plan.feature_category_links == {"p1": ["f1"]}
