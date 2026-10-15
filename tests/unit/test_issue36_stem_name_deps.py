"""Issue #36: stem names are owned per-POS, so they must yield an owner-POS edge."""
from types import SimpleNamespace

from gramtrans.Lib import closure
from gramtrans.Lib.categories import (
    CLOSURE_EDGES_VERIFIED,
    exception_features_dependencies,
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


def test_stem_names_not_registered_as_verified_closure_category():
    """TRIPWIRE. The STEM_NAMES -> POS edge is correct but latent:
    `closure_dependencies_for` only consults CLOSURE_EDGES_VERIFIED. Registering
    it must be a deliberate FR-018 change backed by live audit evidence, and
    whoever does so must update this test."""
    assert CLOSURE_EDGES_VERIFIED
    for kind, row in CLOSURE_EDGES_VERIFIED.items():
        for field, value in row.items():
            assert value != GrammarCategory.STEM_NAMES, (
                f"{kind}.{field}: STEM_NAMES registered; follow-up "
                "'register owner-POS closure edges' must update this test"
            )
            if isinstance(value, str):
                assert value != getattr(
                    GrammarCategory.STEM_NAMES, "value", GrammarCategory.STEM_NAMES
                ), (kind, field)
