"""Feature 038 -- T034 (the FsFeatStrucType closure edge) and T035 (the
pythonnet 2-arg factory trap).

T034. An `IFsFeatStruc` references three things it does not own: the
`IFsFeatStrucType` named by its `TypeRA`, and the `IFsClosedFeature` /
`IFsSymFeatVal` named by each `FeatureSpecsOC` entry's `FeatureRA`/`ValueRA`.
The 038 census measured ~2,083 MSAs restored by the affix path, every one of
them carrying a `TypeRA` that the target's empty `MsFeatureSystemOA.TypesOC`
cannot satisfy -- an unsatisfiable reference on a write reported as successful,
which constitution Principle I forbids. These tests pin down WHERE the edge is
emitted (the owning side), WHICH category the far endpoint is filed under (by
walking BOTH feature systems, since `IFsFeatStrucType` is owned only by
`IFsFeatureSystem.TypesOC`), and that the shape is a ref tuple rather than a
bare guid.

T035. The `Create(Guid, owner)` overload is declared on the LCM INTERFACE;
`ServiceLocator.GetService` returns the CONCRETE factory, whose `Create`
pythonnet cannot bind to two arguments. The previous "try 2-arg, fall back to
1-arg" shape therefore raised and swallowed a `TypeError` on every single
create. These tests assert the 1-arg call is the ONLY call -- an assertion the
old code could not pass, and that a "does the object come out right" test
cannot make, since the swallowed path reached the same end state.

COVERAGE HONESTY. Everything below runs against duck-typed fakes or against
the module source. The live-LCM behaviour these fakes stand in for -- pythonnet
refusing the 2-arg bind, `ICmObject.Cache.LangProject.{Ms,Ph}FeatureSystemOA`
being reachable from an arbitrary piece, `IFsClosedValue` being the only
interface that exposes `ValueRA` -- is asserted by reading, not by execution.
"""
from __future__ import annotations

import ast
import inspect
import io
import sys
import types

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.models import DependencyKind, GrammarCategory


# ===========================================================================
# Duck-typed fakes. Deliberately attribute-only: `_feat_struc_deps` probes
# every slot with `getattr`, so an absent slot must be indistinguishable from
# a real MSA subclass that does not declare it.
# ===========================================================================

class _Obj:
    """Anything with a GUID -- a struct type, a feature defn, a value.

    `owner` models `ICmObject.Owner`, which T089 made load-bearing: an
    `IFsSymFeatVal` is owned by the `IFsClosedFeature` whose `ValuesOC` holds
    it, and that owner is the endpoint the closure edge now names. It is
    OPTIONAL so an owner-less fake still stands in for the malformed case the
    production code has to survive.
    """

    def __init__(self, guid: str, owner=None) -> None:
        self.guid = guid
        if owner is not None:
            self.Owner = owner


class _Spec:
    """One `FeatureSpecsOC` entry (an `IFsClosedValue`)."""

    def __init__(self, feature=None, value=None, nested=None) -> None:
        self.FeatureRA = feature
        self.ValueRA = value
        if nested is not None:
            self.ValueOA = nested  # IFsComplexValue's nested IFsFeatStruc


class _Struc:
    """An `IFsFeatStruc`."""

    def __init__(self, type_ra=None, specs=()) -> None:
        self.TypeRA = type_ra
        self.FeatureSpecsOC = list(specs)


class _MSA:
    def __init__(self, **slots) -> None:
        for name, value in slots.items():
            setattr(self, name, value)


class _Entry:
    def __init__(self, guid: str, msas=(), cache=None) -> None:
        self.guid = guid
        self.MorphoSyntaxAnalysesOC = list(msas)
        if cache is not None:
            self.Cache = cache


class _System:
    def __init__(self, types_oc=()) -> None:
        self.TypesOC = list(types_oc)


class _LangProject:
    def __init__(self, ms_types=(), ph_types=()) -> None:
        self.MsFeatureSystemOA = _System(ms_types)
        self.PhFeatureSystemOA = _System(ph_types)


class _Cache:
    def __init__(self, ms_types=(), ph_types=()) -> None:
        self.LangProject = _LangProject(ms_types, ph_types)


TYPE_G = "11111111-1111-1111-1111-111111111111"
FEAT_G = "22222222-2222-2222-2222-222222222222"
VAL_G = "33333333-3333-3333-3333-333333333333"
POS_G = "44444444-4444-4444-4444-444444444444"
NESTED_TYPE_G = "55555555-5555-5555-5555-555555555555"


def _full_struc(type_guid=TYPE_G):
    """The well-formed shape: `FsClosedFeature.ValuesOC` owns the value, so
    the spec's `ValueRA.Owner` IS its `FeatureRA` (T089)."""
    feature = _Obj(FEAT_G)
    return _Struc(
        type_ra=_Obj(type_guid),
        specs=[_Spec(feature=feature, value=_Obj(VAL_G, owner=feature))],
    )


# ===========================================================================
# T034 -- the enum member exists and names the relationship
# ===========================================================================

def test_dependency_kind_member_exists() -> None:
    """FR-018 keys the allowlist by relationship, so the relationship needs a
    name before it can ever be switched on independently."""
    assert DependencyKind.MSA_TO_FEAT_STRUC_TYPE.value == "msa_to_feat_struc_type"


def test_t034s_edge_is_registered_for_exactly_one_of_its_four_sources() -> None:
    """T034 emitted the `TypeRA` arrow from FOUR kinds of owner -- MSAs (via
    AFFIXES and STEMS), `IPartOfSpeech.DefaultFeaturesOA`, `IPhPhoneme` and
    `IPhNCFeatures` -- and deliberately registered NONE of them, because
    `verified_by` must name a real audit and none existed.

    T067 audited ONE of them: the AFFIXES producer, on two live corpora. So
    exactly one row exists, and the others are still unregistered -- which is
    not a technicality but the mechanism: `DependencyKind` keys are unique, so
    a second source would need its own member and therefore its own audit.

    STEMS is asserted absent explicitly. It shares `_entry_feat_struc_deps`
    with AFFIXES and would very likely audit identically, and "would likely
    audit identically" is precisely the reasoning FR-018 refuses to accept.
    """
    row = categories.CLOSURE_EDGES_VERIFIED[
        DependencyKind.MSA_TO_FEAT_STRUC_TYPE]
    assert row["category"] is GrammarCategory.AFFIXES
    assert row["dependency_category"] is GrammarCategory.FEATURE_STRUCT_TYPES
    assert row["producer"] is categories.affixes_feat_struc_type_dependencies
    # The evidence has to name the audit, not gesture at one.
    assert "audit038_closure_edges" in row["verified_by"]
    assert "Mbugwe LizzieHC practice" in row["verified_by"]
    assert "Ejagham Mini" in row["verified_by"]

    # Unregistered sources contribute nothing, by the same mechanism as before
    # T067: `closure_dependencies_for` never calls an unregistered producer.
    dep_fn = categories.closure_dependencies_for(context=None)
    for category in (GrammarCategory.STEMS, GrammarCategory.GRAM_CATEGORIES,
                     GrammarCategory.PHONEMES):
        assert dep_fn(category, TYPE_G) == ()


def test_both_halves_of_the_feat_struc_helper_are_now_registered() -> None:
    """`_entry_feat_struc_deps` emits TWO relationships -- the `TypeRA` arrow
    and the `FeatureSpecsOC` -> `FeatureRA`/`ValueRA` arrows -- and as of
    T104 both are registered, under SEPARATE `DependencyKind`s.

    THIS TEST ASSERTED THE OPPOSITE UNTIL 2026-08-22 and was inverted
    deliberately, so read what changed. The asymmetry it pinned was real and
    is the whole reason T067 needed narrow producers: the INFLECTION_FEATURES
    half was live and narrow, but its far endpoints were mostly `IFsSymFeatVal`
    symbolic values that `inflection_features_enumerate_source` never yields
    (it walks `FeatureGetAll()`, the DEFNS), so a pulled-in ref naming one
    could be neither planned (FR-015) nor deselected (FR-016).

    T089 removed the cause rather than the check: each `ValueRA` edge now
    names the feature that OWNS the value, which is the piece that IS
    enumerated and whose `execute_action` co-creates the value. T104 then ran
    the registration census and registered the row.

    What replaces the old assertion is STRICTER than it, not weaker. "Not
    registered" is satisfied by a row that is missing for any reason at all,
    including a producer that was quietly deleted. This version pins that both
    halves are present, that they are DISTINCT kinds, and that they point at
    different far categories -- which is the property that actually keeps one
    half's evidence from being read as the other's.
    """
    registry = categories.CLOSURE_EDGES_VERIFIED
    assert DependencyKind.MSA_TO_FEAT_STRUC_TYPE in registry
    assert DependencyKind.MSA_TO_INFL_FEATURE in registry

    type_row = registry[DependencyKind.MSA_TO_FEAT_STRUC_TYPE]
    infl_row = registry[DependencyKind.MSA_TO_INFL_FEATURE]
    # Same source category, different far category, different producer. All
    # three clauses matter: two rows on AFFIXES are legal only while their
    # far categories differ, and a shared producer would mean one audit was
    # being spent twice.
    assert type_row["category"] == infl_row["category"] \
        == GrammarCategory.AFFIXES
    assert type_row["dependency_category"] \
        == GrammarCategory.FEATURE_STRUCT_TYPES
    assert infl_row["dependency_category"] \
        == GrammarCategory.INFLECTION_FEATURES
    assert type_row["producer"] is not infl_row["producer"]


# ===========================================================================
# T034 -- the MSA side (AFFIXES / STEMS)
# ===========================================================================

@pytest.mark.parametrize("slot", [
    "InflFeatsOA",     # IMoInflAffMsa, IMoDerivStepMsa
    "MsFeaturesOA",    # IMoStemMsa, IMoDerivStepMsa
    "FromMsFeaturesOA",  # IMoDerivAffMsa
    "ToMsFeaturesOA",    # IMoDerivAffMsa
])
def test_affixes_emit_type_and_feature_edges_for_every_msa_slot(slot) -> None:
    """All four owning-atomic `IFsFeatStruc` slots an MSA subclass can carry
    are probed. Missing one would silently drop the edge for that MSA kind --
    e.g. covering only `InflFeatsOA` would leave every `IMoStemMsa` unguarded."""
    entry = _Entry("aff-1", msas=[_MSA(**{slot: _full_struc()})])
    deps = categories.affixes_dependencies(entry)

    assert (GrammarCategory.FEATURE_STRUCT_TYPES, TYPE_G) in deps
    assert (GrammarCategory.INFLECTION_FEATURES, FEAT_G) in deps
    # T089: the value's OWNING feature, not the value. `IFsSymFeatVal` is not
    # something `inflection_features_enumerate_source` yields, so an edge
    # naming one could be neither planned (FR-015) nor deselected (FR-016).
    assert (GrammarCategory.INFLECTION_FEATURES, VAL_G) not in deps


def test_affixes_keep_the_pos_edge_and_append_the_new_ones() -> None:
    """The struct-type edges are ADDITIVE: E4's POS edge is unchanged and
    still comes first, so nothing that consumed `affixes_dependencies` before
    sees its existing edges move."""
    entry = _Entry("aff-1", msas=[
        _MSA(PartOfSpeechRA=_Obj(POS_G), InflFeatsOA=_full_struc()),
    ])
    deps = categories.affixes_dependencies(entry)
    assert deps[0] == (GrammarCategory.GRAM_CATEGORIES, POS_G)
    assert (GrammarCategory.FEATURE_STRUCT_TYPES, TYPE_G) in deps[1:]


def test_affix_edges_are_deduplicated_across_msas() -> None:
    """Two MSAs sharing one struct type must yield ONE edge -- the closure
    walk would otherwise revisit the same ref and inflate `pulled_in_by`."""
    entry = _Entry("aff-1", msas=[
        _MSA(InflFeatsOA=_full_struc()),
        _MSA(MsFeaturesOA=_full_struc()),
    ])
    deps = categories.affixes_dependencies(entry)
    assert deps.count((GrammarCategory.FEATURE_STRUCT_TYPES, TYPE_G)) == 1
    assert len(deps) == len(set(deps))


def test_stems_emit_the_same_msa_edges_alongside_strata() -> None:
    """`IMoStemMsa.MsFeaturesOA` is an `IFsFeatStruc` exactly as an affix
    MSA's is, so STEMS must not be the category where the edge goes missing."""
    entry = _Entry("stem-1", msas=[
        _MSA(MsFeaturesOA=_full_struc(), StratumRA=_Obj("strat-1")),
    ])
    deps = categories.stems_dependencies(entry)
    assert (GrammarCategory.FEATURE_STRUCT_TYPES, TYPE_G) in deps
    assert (GrammarCategory.INFLECTION_FEATURES, FEAT_G) in deps
    assert (GrammarCategory.INFLECTION_FEATURES, VAL_G) not in deps  # T089
    assert (GrammarCategory.STRATA, "strat-1") in deps


def test_msa_with_no_feature_structure_emits_nothing_new() -> None:
    """The common case. An MSA carrying no feature structure must not gain a
    phantom edge -- `IMoUnclassifiedAffixMsa` has no such slot at all."""
    entry = _Entry("aff-1", msas=[_MSA(PartOfSpeechRA=_Obj(POS_G))])
    assert categories.affixes_dependencies(entry) == (
        (GrammarCategory.GRAM_CATEGORIES, POS_G),
    )


# ===========================================================================
# T089 -- the ValueRA edge names the feature that OWNS the value
#
# `inflection_features_enumerate_source` walks `FeatureGetAll()` -- the feature
# DEFNS -- and `inflection_features_dependencies` records that the values are
# "co-created in execute_action, not separately planned". So an edge naming an
# `IFsSymFeatVal` has no `PlannedAction`, no FR-015 row and no FR-016
# checkbox, and the closure promise fails on it SILENTLY.
#
# Measured before the fix (`debug/audit038_closure_edges.py`, read-only,
# two corpora): 30 of 34 distinct far GUIDs on `Mbugwe LizzieHC practice` and
# 8 of 10 on `Ejagham Mini` were owned symbolic values.
#
# COVERAGE HONESTY, same as this file's header. `ICmObject.Owner` being
# readable on a base-typed proxy WITHOUT a cast -- the property that makes
# T088's defect inapplicable here -- is asserted by reading LCM's declaration,
# not by execution; the fakes below expose `Owner` directly. What these tests
# DO establish is the branch structure of `_value_defn_ref` and that no value
# guid survives into an edge.
# ===========================================================================

def test_the_value_edge_collapses_onto_its_owning_feature() -> None:
    """The well-formed case, and the whole measured effect: the value's owner
    IS the spec's `FeatureRA`, so the edge set gets SMALLER rather than
    re-pointed -- 30 endpoints collapsing onto the 4 that already existed."""
    entry = _Entry("aff-1", msas=[_MSA(InflFeatsOA=_full_struc())])
    infl = [d for d in categories.affixes_dependencies(entry)
            if d[0] is GrammarCategory.INFLECTION_FEATURES]
    assert infl == [(GrammarCategory.INFLECTION_FEATURES, FEAT_G)]


def test_the_owner_is_read_even_when_the_spec_declares_no_feature() -> None:
    """`Owner` is consulted FIRST, not as a fallback, and this is the case
    that proves it: a spec with a `ValueRA` and a null `FeatureRA` still
    yields a plannable defn. Falling back to `FeatureRA` alone would drop it.
    """
    owner = _Obj(FEAT_G)
    struc = _Struc(specs=[_Spec(value=_Obj(VAL_G, owner=owner))])
    entry = _Entry("aff-1", msas=[_MSA(InflFeatsOA=struc)])
    deps = categories.affixes_dependencies(entry)
    assert deps == ((GrammarCategory.INFLECTION_FEATURES, FEAT_G),)


def test_a_value_whose_owner_is_unreadable_falls_back_to_the_declared_feature() -> None:
    """An owner-less fake stands in for a value whose `Owner` read fails. The
    spec's own `FeatureRA` is the declared feature for that value, so it is
    the correct fallback -- and it is already emitted, which makes the fallback
    a de-duplicated no-op rather than a second edge."""
    struc = _Struc(specs=[_Spec(feature=_Obj(FEAT_G), value=_Obj(VAL_G))])
    entry = _Entry("aff-1", msas=[_MSA(InflFeatsOA=struc)])
    assert categories.affixes_dependencies(entry) == (
        (GrammarCategory.INFLECTION_FEATURES, FEAT_G),
    )


def test_a_value_with_neither_an_owner_nor_a_feature_yields_no_edge() -> None:
    """The absence of a plannable endpoint, not the dropping of one. Emitting
    the value guid here is precisely the defect: it would put a ref nothing
    can enumerate back into the plan. Measured 0 occurrences on both corpora.
    """
    struc = _Struc(specs=[_Spec(value=_Obj(VAL_G))])
    entry = _Entry("aff-1", msas=[_MSA(InflFeatsOA=struc)])
    assert categories.affixes_dependencies(entry) == ()


def test_two_values_of_one_feature_yield_one_edge() -> None:
    """The de-duplication the collapse makes necessary. A `+sg` / `-pl`
    constraint used to be two distinct value guids and is now one feature
    guid; without de-duplication the closure walk would count it twice and
    inflate `pulled_in_by`."""
    feature = _Obj(FEAT_G)
    struc = _Struc(specs=[
        _Spec(feature=feature, value=_Obj(VAL_G, owner=feature)),
        _Spec(feature=feature, value=_Obj("99999999-9999-9999-9999-999999999999",
                                          owner=feature)),
    ])
    entry = _Entry("aff-1", msas=[_MSA(InflFeatsOA=struc)])
    assert categories.affixes_dependencies(entry) == (
        (GrammarCategory.INFLECTION_FEATURES, FEAT_G),
    )


def test_the_narrow_infl_feature_producer_emits_no_value_guid() -> None:
    """The producer the registry would consult (`MSA_TO_INFL_FEATURE`). T089
    is what blocked its registration, so the assertion belongs on it directly
    and not only on the composite."""
    entry = _Entry("aff-1", msas=[_MSA(InflFeatsOA=_full_struc())])
    assert categories.affixes_infl_feature_dependencies(entry) == (
        (GrammarCategory.INFLECTION_FEATURES, FEAT_G),
    )


def test_the_variant_type_sibling_names_the_owning_feature_too() -> None:
    """`variant_types_dependencies` carried the same defect independently and
    is fixed by the same helper. It is UNREGISTERED, so this changes no plan
    -- what it changes is that its own registration will not hit T089's
    refusal later."""
    feature = _Obj(FEAT_G)
    vt = _MSA(guid="vt-1", InflFeatsOA=_Struc(
        specs=[_Spec(feature=feature, value=_Obj(VAL_G, owner=feature))]))
    assert categories.variant_types_dependencies(vt) == (
        (GrammarCategory.INFLECTION_FEATURES, FEAT_G),
    )


# ===========================================================================
# T034 -- the POS side (GRAM_CATEGORIES)
# ===========================================================================

def test_gram_categories_emit_default_features_edges() -> None:
    """`IPartOfSpeech.DefaultFeaturesOA` carries the same references an MSA's
    does; a POS is a leaf for OWNERSHIP, not for REFERENCE."""
    pos = _MSA(guid=POS_G, DefaultFeaturesOA=_full_struc())
    deps = categories.gram_categories_dependencies(pos)
    assert set(deps) == {
        (GrammarCategory.FEATURE_STRUCT_TYPES, TYPE_G),
        # T089: two edges, not three -- the value collapses onto its owner.
        (GrammarCategory.INFLECTION_FEATURES, FEAT_G),
    }


def test_gram_categories_without_default_features_stay_empty() -> None:
    """The overwhelmingly common POS. Regression guard for
    `test_categories_gram_categories.py::test_dependencies_returns_empty_tuple`."""
    assert categories.gram_categories_dependencies(_Obj(POS_G)) == ()


# ===========================================================================
# T034 -- the phonological twin (PHONEMES / NATURAL_CLASSES)
# ===========================================================================

def test_phonemes_emit_phon_feat_types_not_feature_struct_types() -> None:
    """An `IPhPhoneme`'s `FeaturesOA` lives in the PHONOLOGICAL feature
    system. Filing its `TypeRA` under FEATURE_STRUCT_TYPES would send the
    closure walk looking in `MsFeatureSystemOA.TypesOC`, where the GUID does
    not exist -- the far-endpoint guess the closure registry banner refuses."""
    phoneme = _MSA(guid="ph-1", FeaturesOA=_full_struc())
    deps = categories.phonemes_dependencies(phoneme)
    assert set(deps) == {
        (GrammarCategory.PHON_FEAT_TYPES, TYPE_G),
        # T089 applies to the phonological twin for the same reason:
        # `phonological_features_enumerate_source` walks `PhonFeatures` (the
        # DEFNS) and `phonological_features_execute_action` co-creates the
        # values, so a value guid is unplannable on this side too. One helper
        # fixes both because both go through `_feat_struc_deps`.
        (GrammarCategory.PHONOLOGICAL_FEATURES, FEAT_G),
    }


def test_phoneme_without_features_stays_empty() -> None:
    assert categories.phonemes_dependencies(_Obj("ph-2")) == ()


@pytest.fixture()
def _fake_lcmodel(monkeypatch):
    """`natural_classes_dependencies` gates its whole body behind
    `from SIL.LCModel import ...`; identity casts let the duck-typed fakes
    through, mirroring `test_categories_phonology.py`'s existing helper."""
    identity = lambda x: x  # noqa: E731
    fake = types.ModuleType("SIL.LCModel")
    for name in ("IPhNCSegments", "IPhNCFeatures", "IFsClosedValue", "ICmObject"):
        setattr(fake, name, identity)
    sil = types.ModuleType("SIL")
    sil.LCModel = fake
    monkeypatch.setitem(sys.modules, "SIL", sil)
    monkeypatch.setitem(sys.modules, "SIL.LCModel", fake)
    return fake


def test_natural_classes_add_the_type_ra_ref_to_their_bare_guids(_fake_lcmodel) -> None:
    """The feature/value guids this producer already returned are only HALF
    the structure's references. The `TypeRA` ref is appended as a REF TUPLE on
    purpose: a bare guid here would be indistinguishable from a feature/value
    guid, and one `dependency_category` on the registry entry would file it
    under PHONOLOGICAL_FEATURES instead of PHON_FEAT_TYPES."""
    class _Ref:
        def __init__(self, guid):
            self.Guid = guid

    struc = _Struc(type_ra=_Ref(TYPE_G),
                   specs=[_Spec(feature=_Ref(FEAT_G), value=_Ref(VAL_G))])
    nc = _MSA(FeaturesOA=struc)

    deps = categories.natural_classes_dependencies(nc)
    assert (GrammarCategory.PHON_FEAT_TYPES, TYPE_G) in deps
    assert FEAT_G in deps and VAL_G in deps


def test_natural_classes_without_a_type_ra_are_unchanged(_fake_lcmodel) -> None:
    """Feature 037's measured behaviour must survive untouched: a PhNCFeatures
    item still yields exactly its FeatureRA/ValueRA guids when TypeRA is
    unset."""
    class _Ref:
        def __init__(self, guid):
            self.Guid = guid

    nc = _MSA(FeaturesOA=_Struc(specs=[_Spec(feature=_Ref(FEAT_G),
                                             value=_Ref(VAL_G))]))
    assert set(categories.natural_classes_dependencies(nc)) == {FEAT_G, VAL_G}


# ===========================================================================
# T034 -- both feature systems are walked to classify the far endpoint
# ===========================================================================

def test_both_feature_systems_are_walked_and_ownership_wins() -> None:
    """`IFsFeatStrucType` is owned ONLY by `IFsFeatureSystem.TypesOC`, and a
    LangProject holds two systems. When the piece's cache makes the ownership
    walk possible, ownership -- not the caller's structural expectation --
    decides the category. Here an MSA-borne TypeRA guid is actually owned by
    `PhFeatureSystemOA`, and the edge must be filed under PHON_FEAT_TYPES."""
    cache = _Cache(ms_types=[_Obj("other-type")], ph_types=[_Obj(TYPE_G)])
    entry = _Entry("aff-1", msas=[_MSA(InflFeatsOA=_full_struc())], cache=cache)
    deps = categories.affixes_dependencies(entry)
    assert (GrammarCategory.PHON_FEAT_TYPES, TYPE_G) in deps
    assert (GrammarCategory.FEATURE_STRUCT_TYPES, TYPE_G) not in deps


def test_ms_ownership_is_honoured_too() -> None:
    """The mirror of the above -- the walk is not a Ph-only special case."""
    cache = _Cache(ms_types=[_Obj(TYPE_G)], ph_types=[])
    phoneme = _MSA(guid="ph-1", FeaturesOA=_full_struc(), Cache=cache)
    deps = categories.phonemes_dependencies(phoneme)
    assert (GrammarCategory.FEATURE_STRUCT_TYPES, TYPE_G) in deps


def test_unreachable_cache_falls_back_to_the_structural_expectation() -> None:
    """A `*_dependencies(piece)` producer gets the piece and nothing else, so
    a piece with no reachable cache (every duck-typed fake, and any wrapper
    that does not forward `Cache`) cannot be classified by ownership. The
    fallback is the caller's own side, which is correct for every attested
    shape."""
    assert categories._feat_struc_type_categories(_Obj("x")) == {}
    entry = _Entry("aff-1", msas=[_MSA(InflFeatsOA=_full_struc())])
    assert (GrammarCategory.FEATURE_STRUCT_TYPES, TYPE_G) in \
        categories.affixes_dependencies(entry)


def test_an_unreadable_feature_system_does_not_break_the_producer() -> None:
    """Enumeration is best-effort: a producer that raises is treated by
    `closure_dependencies_for` as contributing no edges at all, so a single
    unreadable system must not cost the whole entry its edges."""
    class _Exploding:
        @property
        def TypesOC(self):
            raise RuntimeError("unreadable")

    cache = _Cache()
    cache.LangProject.MsFeatureSystemOA = _Exploding()
    entry = _Entry("aff-1", msas=[_MSA(InflFeatsOA=_full_struc())], cache=cache)
    assert (GrammarCategory.FEATURE_STRUCT_TYPES, TYPE_G) in \
        categories.affixes_dependencies(entry)


# ===========================================================================
# T034 -- nested complex values, and the recursion cap
# ===========================================================================

def test_nested_complex_value_structures_contribute_their_edges() -> None:
    """`IFsComplexValue.ValueOA` is itself an `IFsFeatStruc` with its own
    `TypeRA`. Stopping at depth 0 would leave a nested structure's struct type
    unsatisfiable exactly as the flat case was."""
    nested = _Struc(type_ra=_Obj(NESTED_TYPE_G))
    struc = _Struc(type_ra=_Obj(TYPE_G), specs=[_Spec(nested=nested)])
    entry = _Entry("aff-1", msas=[_MSA(InflFeatsOA=struc)])
    deps = categories.affixes_dependencies(entry)
    assert (GrammarCategory.FEATURE_STRUCT_TYPES, TYPE_G) in deps
    assert (GrammarCategory.FEATURE_STRUCT_TYPES, NESTED_TYPE_G) in deps


def test_a_self_referential_structure_terminates() -> None:
    """LCM does not structurally forbid a cycle, and a dependency producer
    that hangs the closure walk is strictly worse than one that
    under-reports."""
    struc = _Struc(type_ra=_Obj(TYPE_G))
    struc.FeatureSpecsOC = [_Spec(nested=struc)]
    entry = _Entry("aff-1", msas=[_MSA(InflFeatsOA=struc)])
    deps = categories.affixes_dependencies(entry)  # must return, not hang
    assert deps == ((GrammarCategory.FEATURE_STRUCT_TYPES, TYPE_G),)


# ===========================================================================
# T034 -- the type side's own outward edge (FeaturesRS)
# ===========================================================================

def test_feature_struct_types_yield_their_features_rs_members() -> None:
    """`FeaturesRS` is a REFERENCE sequence into `MsFeatureSystemOA.FeaturesOC`,
    which INFLECTION_FEATURES transfers.
    `feature_struct_types_execute_action` already logs "no target counterpart
    in FeaturesOC -- skipping member" when a member is missing, i.e. it ships a
    partially wired type; this is the edge that would prevent that."""
    struct_type = _MSA(guid=TYPE_G, FeaturesRS=[_Obj(FEAT_G), _Obj(VAL_G)])
    assert categories.feature_struct_types_dependencies(struct_type) == (
        (GrammarCategory.INFLECTION_FEATURES, FEAT_G),
        (GrammarCategory.INFLECTION_FEATURES, VAL_G),
    )


def test_phon_feat_types_file_their_members_under_the_phon_category() -> None:
    struct_type = _MSA(guid=TYPE_G, FeaturesRS=[_Obj(FEAT_G)])
    assert categories.phon_feat_types_dependencies(struct_type) == (
        (GrammarCategory.PHONOLOGICAL_FEATURES, FEAT_G),
    )


def test_type_side_producers_never_emit_the_inbound_type_ra_edge() -> None:
    """Direction matters. `closure.walk` walks OUTWARD from what the user
    selected, so an arrow emitted from the type's own producer would never
    pull the type in on behalf of the MSA that needs it. A struct type with no
    FeaturesRS therefore has no edges at all, even though plenty of MSAs point
    at it."""
    assert categories.feature_struct_types_dependencies(_Obj(TYPE_G)) == ()
    assert categories.phon_feat_types_dependencies(_Obj(TYPE_G)) == ()


# ===========================================================================
# T035 -- 1-arg Create(Guid) THEN Add(), never the 2-arg overload
# ===========================================================================

_FS_FACTORY_CREATE_SITES = (
    "inflection_features_execute_action",
    "feature_struct_types_execute_action",
    "phon_feat_types_execute_action",
)


def _create_call_arities(func_name: str):
    """Every `<something>.Create(...)` positional arity inside one function of
    Lib/categories.py, read from the source. Static rather than dynamic
    because these branches need a live LCM host to run end to end."""
    source = io.open(inspect.getsourcefile(categories), encoding="utf-8").read()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return [
                len(call.args)
                for call in ast.walk(node)
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "Create"
            ]
    raise AssertionError(func_name + " not found in Lib/categories.py")


@pytest.mark.parametrize("func_name", _FS_FACTORY_CREATE_SITES)
def test_no_two_arg_create_survives_at_any_fs_factory_site(func_name) -> None:
    """The 2-arg `Create(Guid, owner)` overload is declared on the LCM
    INTERFACE only; `GetService` hands back the CONCRETE factory, which
    pythonnet cannot bind to two arguments. Keeping the attempt "first" bought
    nothing and cost a swallowed exception per created object."""
    arities = _create_call_arities(func_name)
    assert arities, func_name + " makes no factory Create call at all"
    assert all(n == 1 for n in arities), (
        func_name + " still calls Create with " + repr(arities) + " args"
    )


def test_closed_feature_create_is_called_exactly_once_with_one_argument(
        _patch_lcm_for_execute) -> None:
    """The assertion the old code could not pass. A "did the object come out
    right" test cannot distinguish the two shapes -- the swallowed 2-arg
    attempt reached the same end state -- so the call LOG is what is checked,
    and the object must land in FeaturesOC via `_safe_add_to_owner`."""
    fake_lcm, sl, feat_sys, factories = _patch_lcm_for_execute
    result = _run_closed_feature_execute(fake_lcm, sl, feat_sys)

    closed = factories["closed"]
    assert [len(args) for args in closed.calls] == [1], closed.calls
    assert list(feat_sys.FeaturesOC) == [result], "1-arg create must be followed by Add()"


def test_symbolic_value_create_is_called_exactly_once_with_one_argument(
        _patch_lcm_for_execute) -> None:
    """The value loop ran the swallowed 2-arg attempt once PER VALUE, so this
    is where the removed path cost the most."""
    fake_lcm, sl, feat_sys, factories = _patch_lcm_for_execute
    result = _run_closed_feature_execute(fake_lcm, sl, feat_sys)

    values = factories["value"]
    assert [len(args) for args in values.calls] == [1], values.calls
    assert len(result.ValuesOC) == 1, "1-arg value create must be followed by Add()"


def test_complex_feature_create_is_called_exactly_once_with_one_argument(
        _patch_lcm_for_execute) -> None:
    """`IFsComplexFeatureFactory` was singled out in three comments as the one
    factory with a working 2-arg overload. It never had one -- the call was
    failing and being swallowed like the others."""
    fake_lcm, sl, feat_sys, factories = _patch_lcm_for_execute
    result = _run_complex_feature_execute(fake_lcm, sl, feat_sys)

    complex_factory = factories["complex"]
    assert [len(args) for args in complex_factory.calls] == [1], complex_factory.calls
    assert list(feat_sys.FeaturesOC) == [result]


# --- offline execute harness for the three T035 sites ----------------------

class _RecordingFactory:
    """Records the arity of every `Create` call. It deliberately ACCEPTS any
    arity: a factory that rejected the 2-arg form would make the old
    swallowed-exception code pass this test too."""

    def __init__(self, obj) -> None:
        self._obj = obj
        self.calls: list = []

    def Create(self, *args):
        self.calls.append(args)
        return self._obj


class _OC(list):
    def Add(self, obj) -> None:
        self.append(obj)


class _MultiString:
    def __init__(self) -> None:
        self._by_ws: dict = {}

    def get_String(self, ws):
        return self._by_ws.get(ws, "")

    def set_String(self, ws, value) -> None:
        self._by_ws[ws] = value

    @property
    def AvailableWritingSystemIds(self):
        return list(self._by_ws)


class _NewFeat:
    def __init__(self) -> None:
        self.Name = _MultiString()
        self.Abbreviation = _MultiString()
        self.Description = _MultiString()
        self.ValuesOC = _OC()
        self.TypeRA = None


@pytest.fixture()
def _patch_lcm_for_execute(monkeypatch):
    """Inject a fake `SIL.LCModel` / `System` so
    `inflection_features_execute_action`'s internal imports resolve without a
    pythonnet host, and no-op residue so no real WS handle is needed. Mirrors
    `test_categories_inflection_features.py::_patch_lcm_b1`."""
    fake_lcm = types.ModuleType("SIL.LCModel")
    for name in ("IFsClosedFeatureFactory", "IFsSymFeatValFactory",
                 "IFsComplexFeatureFactory"):
        setattr(fake_lcm, name, object())
    for name in ("IFsClosedFeature", "IFsSymFeatVal", "IFsComplexFeature"):
        setattr(fake_lcm, name, lambda x: x)

    fake_system = types.ModuleType("System")
    fake_system.Guid = type("Guid", (), {"Parse": staticmethod(lambda s: s)})

    injected = {
        "SIL": types.ModuleType("SIL"),
        "SIL.LCModel": fake_lcm,
        "System": fake_system,
    }
    originals = {key: sys.modules.get(key) for key in injected}
    sys.modules.update(injected)

    import gramtrans.Lib.residue as _res_mod
    monkeypatch.setattr(_res_mod, "apply_carrier_b", lambda *a, **k: None)
    monkeypatch.setattr(categories, "_run_tail_once", lambda *a, **k: None)

    factories = {
        "closed": _RecordingFactory(_NewFeat()),
        "value": _RecordingFactory(_NewFeat()),
        "complex": _RecordingFactory(_NewFeat()),
    }

    class _SL:
        def GetService(self, iface):
            return {
                id(fake_lcm.IFsClosedFeatureFactory): factories["closed"],
                id(fake_lcm.IFsSymFeatValFactory): factories["value"],
                id(fake_lcm.IFsComplexFeatureFactory): factories["complex"],
            }[id(iface)]

    feat_sys = types.SimpleNamespace(FeaturesOC=_OC(), TypesOC=[])

    yield fake_lcm, _SL(), feat_sys, factories

    for key, orig in originals.items():
        if orig is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = orig


def _execute(src_feat, sl, feat_sys):
    from gramtrans.Lib.models import PlannedAction, RunContext, WSMapping

    cache = types.SimpleNamespace(
        DefaultAnalWs=1,
        ServiceLocator=sl,
        LangProject=types.SimpleNamespace(MsFeatureSystemOA=feat_sys),
    )

    class _Ops:
        def __init__(self, feature):
            self._feature = feature

        def FeatureGetAll(self):
            return [self._feature]

        def GetSyncableProperties(self, obj):
            return {}

        def ApplySyncableProperties(self, obj, props, ws_map=None):
            return None

    source = types.SimpleNamespace(InflectionFeatures=_Ops(src_feat))
    target = types.SimpleNamespace(InflectionFeatures=_Ops(src_feat), Cache=cache)

    ctx = RunContext(
        source_handle=source, source_project_name="s", source_project_path="/s",
        target_handle=target, target_project_name="t", target_project_path="/t",
        run_id="GT-20260819-000000", started_at="2026-08-19T00:00:00",
    )
    object.__setattr__(ctx, "_exec_skips", [])
    action = PlannedAction(
        category=GrammarCategory.INFLECTION_FEATURES,
        source_guid=FEAT_G, intended_target_guid=FEAT_G, summary="t035",
    )
    return categories.inflection_features_execute_action(
        action, ctx, WSMapping(), tag=None)


def _run_closed_feature_execute(fake_lcm, sl, feat_sys):
    src_val = types.SimpleNamespace(guid=VAL_G, Name=_MultiString(),
                                    Abbreviation=_MultiString(),
                                    Description=_MultiString())
    src_feat = types.SimpleNamespace(
        guid=FEAT_G, ClassName="FsClosedFeature", ValuesOC=[src_val],
        Name=_MultiString(), Abbreviation=_MultiString(),
        Description=_MultiString())
    return _execute(src_feat, sl, feat_sys)


def _run_complex_feature_execute(fake_lcm, sl, feat_sys):
    src_feat = types.SimpleNamespace(
        guid=FEAT_G, ClassName="FsComplexFeature", TypeRA=None,
        Name=_MultiString(), Abbreviation=_MultiString(),
        Description=_MultiString())
    return _execute(src_feat, sl, feat_sys)
