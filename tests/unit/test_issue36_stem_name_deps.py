"""Issues #36 / #67: per-POS owned objects yield an owner-POS edge, and (since
#67) the registered closure walker actually follows it."""
from types import SimpleNamespace

import pytest

from gramtrans.Lib import closure
from gramtrans.Lib.categories import (
    CLOSURE_EDGES_VERIFIED,
    LEAF_CATEGORIES,
    closure_dependencies_for,
    exception_features_dependencies,
    gram_categories_dependencies,
    pos_inflectable_feats_dependencies,
    stem_names_dependencies,
)
from gramtrans.Lib.models import GrammarCategory

POS_GUID = "11111111-2222-3333-4444-555555555555"
SN_GUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_owner_yields_exactly_one_pos_edge():
    piece = SimpleNamespace(Owner=SimpleNamespace(guid=POS_GUID))
    assert stem_names_dependencies(piece) == (
        (GrammarCategory.GRAM_CATEGORIES, POS_GUID),
    )


def test_no_owner_yields_nothing():
    assert stem_names_dependencies(SimpleNamespace(Owner=None)) == ()
    assert stem_names_dependencies(SimpleNamespace()) == ()


def test_owner_without_guid_yields_nothing():
    assert stem_names_dependencies(SimpleNamespace(Owner=SimpleNamespace())) == ()


def test_stem_name_only_selection_pulls_in_and_orders_owner_pos_first():
    piece = SimpleNamespace(Owner=SimpleNamespace(guid=POS_GUID))
    pos_ref = (GrammarCategory.GRAM_CATEGORIES, POS_GUID)
    sn_ref = (GrammarCategory.STEM_NAMES, SN_GUID)

    def deps(category, guid):
        if category == GrammarCategory.STEM_NAMES:
            return stem_names_dependencies(piece)
        return ()

    order, pulled = closure.walk([sn_ref], deps)
    assert set(order) == {pos_ref, sn_ref}
    assert pulled[pos_ref] == (sn_ref,)
    assert closure.topological(order, pulled)[0] == pos_ref


VAL_GUID = "99999999-8888-7777-6666-555555555555"


def test_pos_inflectable_feats_yields_owner_pos_edge():
    piece = (POS_GUID, SimpleNamespace(guid=VAL_GUID))
    assert pos_inflectable_feats_dependencies(piece) == (
        (GrammarCategory.GRAM_CATEGORIES, POS_GUID),
    )


def test_pos_inflectable_feats_none_owner_falls_back_to_empty():
    assert pos_inflectable_feats_dependencies((None, object())) == ()
    assert pos_inflectable_feats_dependencies((POS_GUID,)) == ()
    assert pos_inflectable_feats_dependencies(None) == ()


def test_exception_features_yields_owner_pos_edge():
    piece = (POS_GUID, SimpleNamespace(guid=VAL_GUID))
    assert exception_features_dependencies(piece) == (
        (GrammarCategory.GRAM_CATEGORIES, POS_GUID),
    )


def test_exception_features_none_owner_falls_back_to_empty():
    assert exception_features_dependencies((None, object())) == ()
    assert exception_features_dependencies((POS_GUID,)) == ()
    assert exception_features_dependencies(None) == ()


# ---------------------------------------------------------------------------
# Issue #67: positive walk tests THROUGH closure_dependencies_for
# ---------------------------------------------------------------------------

IC_GUID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
EXC_VAL_GUID = "12121212-3434-5656-7878-909090909090"


def _install_pieces(monkeypatch, category, pieces):
    bundle = dict(LEAF_CATEGORIES[category])
    bundle["enumerate_source"] = lambda context, selection: list(pieces)
    monkeypatch.setitem(LEAF_CATEGORIES, category, bundle)


def _owned(guid):
    return SimpleNamespace(guid=guid, Owner=SimpleNamespace(guid=POS_GUID))


POS_REF = (GrammarCategory.GRAM_CATEGORIES, POS_GUID)


@pytest.mark.parametrize("category,guid,piece", [
    (GrammarCategory.STEM_NAMES, SN_GUID, _owned(SN_GUID)),
    (GrammarCategory.INFLECTION_CLASSES, IC_GUID, _owned(IC_GUID)),
    # Tuple pieces are keyed by the compound plan guid "pos::obj".
    (GrammarCategory.POS_INFLECTABLE_FEATS, POS_GUID + "::" + VAL_GUID,
     (POS_GUID, SimpleNamespace(guid=VAL_GUID))),
])
def test_registered_walk_pulls_in_owner_pos(monkeypatch, category, guid, piece):
    """A one-category selection reaches the owner POS through the REGISTERED
    walker (issue #67); before the registry rows this returned ()."""
    _install_pieces(monkeypatch, category, [piece])
    deps = closure_dependencies_for(SimpleNamespace(source_handle=None))
    assert deps(category, guid) == (POS_REF,)
    seed = (category, guid)
    order, pulled = closure.walk([seed], deps)
    assert set(order) == {seed, POS_REF}
    assert pulled[POS_REF] == (seed,)
    assert closure.topological(order, pulled)[0] == POS_REF


def test_exception_features_is_not_walked_because_it_is_unregistered(monkeypatch):
    """No audited corpus holds an exception-feature value (NO_DATA), so FR-018
    keeps this edge unregistered. This is the one remaining latent owner-POS
    edge; flip this test deliberately when audit evidence exists."""
    guid = POS_GUID + "::" + EXC_VAL_GUID
    _install_pieces(monkeypatch, GrammarCategory.EXCEPTION_FEATURES,
                    [(POS_GUID, SimpleNamespace(guid=EXC_VAL_GUID))])
    deps = closure_dependencies_for(SimpleNamespace(source_handle=None))
    assert deps(GrammarCategory.EXCEPTION_FEATURES, guid) == ()


def test_registered_pos_rows_are_narrow_and_explicit():
    for cat in (GrammarCategory.STEM_NAMES, GrammarCategory.INFLECTION_CLASSES,
                GrammarCategory.POS_INFLECTABLE_FEATS):
        rows = [r for r in CLOSURE_EDGES_VERIFIED.values()
                if r["category"] == cat]
        assert len(rows) == 1, cat
        assert rows[0]["dependency_category"] == GrammarCategory.GRAM_CATEGORIES
        assert rows[0]["verified_by"]


def test_owner_pos_rows_introduce_no_cycle():
    """The registered category graph stays acyclic: GRAM_CATEGORIES is never a
    registered SOURCE (so POS has no outgoing walk edges), and everything the
    unregistered `gram_categories_dependencies` points at is a category that is
    not a source of any owner-POS row either."""
    graph: dict = {}
    for row in CLOSURE_EDGES_VERIFIED.values():
        graph.setdefault(row["category"], set()).add(row["dependency_category"])

    assert GrammarCategory.GRAM_CATEGORIES not in graph

    state: dict = {}

    def visit(node):
        if state.get(node) == 1:
            raise AssertionError("cycle through " + repr(node))
        if state.get(node) == 2:
            return
        state[node] = 1
        for nxt in graph.get(node, ()):
            visit(nxt)
        state[node] = 2

    for node in list(graph):
        visit(node)

    # POS's own (unregistered) outgoing arrows: only these two far categories,
    # neither of which is a source of a registered row.
    pos_far = {GrammarCategory.FEATURE_STRUCT_TYPES,
               GrammarCategory.INFLECTION_FEATURES}
    produced = gram_categories_dependencies(
        SimpleNamespace(DefaultFeaturesOA=None))
    assert produced == ()
    assert not (pos_far & set(graph))


def test_walk_with_owner_pos_terminates_when_pos_is_also_selected(monkeypatch):
    """Selecting the POS together with its owned items must not loop."""
    _install_pieces(monkeypatch, GrammarCategory.STEM_NAMES, [_owned(SN_GUID)])
    deps = closure_dependencies_for(SimpleNamespace(source_handle=None))
    order, pulled = closure.walk(
        [POS_REF, (GrammarCategory.STEM_NAMES, SN_GUID)], deps)
    assert set(order) == {POS_REF, (GrammarCategory.STEM_NAMES, SN_GUID)}
    assert closure.topological(order, pulled)[0] == POS_REF
