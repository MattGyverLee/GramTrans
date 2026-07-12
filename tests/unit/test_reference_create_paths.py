"""Write-first CREATE-path regression tests (feature 024 resolver hardening).

Two CREATE-path bugs in `references.py` were confirmed live on LCM (Ejagham
Mini, this session) but are NOT caught by the existing 7 tests in
`tests/unit/test_reference_resolver.py`, whose fakes never modeled the
Owner-vs-list / ItemClsid boundary these bugs live on:

- BUG 2a (`_ancestor_chain` boundary): on live LCM, a TOP-LEVEL
  `ICmPossibility`'s `.Owner` is the owning `ICmPossibilityList` (ClassID 8),
  which ALSO exposes a `.Guid` -- so `_ancestor_chain`'s stop condition
  (`owner is None or not hasattr(owner, "Guid")`) does not stop there; it
  walks INTO the list. `.OwningPossibility` is the reliable signal (`None`
  at top level, the parent possibility for a sub-item) but the current code
  only falls back to it when `.Owner` is `None`, which never happens here.

- BUG 2b (typed factory by `ItemClsid`): `apply_reference`'s CREATE arm
  always requests the generic `ICmPossibilityFactory` regardless of the
  target list's `ItemClsid`, so an item created in a typed list (e.g.
  ItemClsid 66 = CmSemanticDomain) is created wrong-classed (a bare clsid-7
  CmPossibility) instead of via the type-matched factory.

A third test locks a related gating bug: the CREATE ancestor walk must be
driven DYNAMICALLY by `OwningPossibility`, not gated on the field map's
static `hierarchical` flag (some projects grow a real tree under a field
the map calls flat, e.g. UsageTypesRC).

Do NOT implement fixes here -- this file only records the write-first
regression contract (contracts/reference-resolver.md). Every test below is
expected to FAIL against the current `references.py`.
"""
from __future__ import annotations

import sys
import types

import pytest

from gramtrans.Lib import references
from gramtrans.Lib.models import (
    ReferenceAction,
    ReferenceCardinality,
    ReferenceDecision,
    ReferenceFieldSpec,
)

_WS_EN = 100


# ============================================================================
# BUG 2a -- `_ancestor_chain` must stop at the owning list, never walk into it
# ============================================================================

class _FakePossibilityList:
    """Fake `ICmPossibilityList` (ClassID 8): the container a TOP-LEVEL
    `ICmPossibility`'s `.Owner` resolves to on live LCM. Confirmed live on
    Ejagham Mini this session: the list itself ALSO exposes `.Guid` -- that
    is the crux of bug 2a. A real `ICmPossibilityList` has no
    `OwningPossibility` surface at all; deliberately absent here (not even
    `None`) so `getattr(..., "OwningPossibility", None)` falls back to the
    default, matching the live shape.
    """

    def __init__(self, guid: str) -> None:
        self.Guid = guid
        self.Owner = None


class _FakeHierPossibility:
    """Fake `ICmPossibility` distinguishing `.Owner` (parent possibility OR
    the owning list -- both possibility-*shaped* since both have `.Guid`)
    from `.OwningPossibility` (the parent possibility, or `None` at top
    level) -- the live LCM shape bug 2a exploits.
    """

    def __init__(self, guid: str, owner, owning_possibility) -> None:
        self.Guid = guid
        self.Owner = owner
        self.OwningPossibility = owning_possibility


def test_ancestor_chain_stops_at_owning_list_never_includes_it():
    """BUG 2a: a 2-level hierarchy -- `parent` (top-level, under
    `fake_list`) -> `leaf` (child of `parent`). Expected root->leaf chain:
    `(parent, leaf)`, and `fake_list` must NEVER appear in it.

    Dry trace against current code: `_ancestor_chain(leaf)` appends `parent`
    (has `.Guid`), then reads `parent.Owner` = `fake_list` -- which ALSO
    `hasattr(..., "Guid")` -- so the loop does NOT stop; it appends
    `fake_list` too and only stops on the next iteration (`fake_list.Owner`
    is `None` and `fake_list` has no `OwningPossibility`). Today's result is
    `(fake_list, parent, leaf)`, not `(parent, leaf)`.
    """
    fake_list = _FakePossibilityList("11111111-list-list-list-111111111111")
    parent = _FakeHierPossibility(
        "22222222-2222-2222-2222-222222222222",
        owner=fake_list,
        owning_possibility=None,  # top-level: no owning possibility
    )
    leaf = _FakeHierPossibility(
        "33333333-3333-3333-3333-333333333333",
        owner=parent,
        owning_possibility=parent,
    )

    chain = references._ancestor_chain(leaf)

    assert fake_list not in chain, (
        f"_ancestor_chain walked into the owning CmPossibilityList: {chain!r}"
    )
    assert chain == (parent, leaf)


# ============================================================================
# BUG 2b -- CREATE must request the type-matched factory by ItemClsid
# ============================================================================

class _FakeCollection:
    """Minimal iterable + `.Add`-able stand-in for `PossibilitiesOS` --
    supports both `_find_in_possibility_list`'s iteration and
    `_add_to_owner`'s `.Add(new_obj)`."""

    def __init__(self, items=()) -> None:
        self._items = list(items)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def Add(self, item):
        self._items.append(item)


class _FakeTypedTargetList:
    """Fake target-side `ICmPossibilityList` carrying `.ItemClsid` -- the
    schema property naming the concrete C# subtype its items must be.
    ALL confirmed live on Ejagham Mini this session:
    66 = CmSemanticDomain, 26 = CmAnthroItem, 5042 = MoMorphType,
    7 = generic CmPossibility (SenseTypes/Usage/DomainTypes/Dialect/
    Publication/Languages/Status/TranslationTags)."""

    def __init__(self, item_clsid: int) -> None:
        self.ItemClsid = item_clsid
        self.PossibilitiesOS = _FakeCollection()


class _FakeCreatedItem:
    """Stand-in for whatever `factory.Create(guid)` returns, and also for
    the single leaf `source_item` being created (so `_guid_str` finds a
    `.Guid` to parse)."""

    def __init__(self, guid: str) -> None:
        self.Guid = guid
        self.guid = guid


class _FakeFactory:
    """Stand-in for the object `target.GetFactory(key)` returns; only
    `.Create(guid)` is exercised by the CREATE path."""

    def Create(self, guid):
        return _FakeCreatedItem(str(guid))


class _FakePossibilityListsOps:
    """Stand-in for `target.PossibilityLists` -- only
    `ApplySyncableProperties` is exercised by the CREATE path (wrapped in a
    try/except in `apply_reference`, but must not raise unexpectedly)."""

    def ApplySyncableProperties(self, item, props):
        pass


class _FakeCmCache:
    def __init__(self) -> None:
        self.DefaultAnalWs = 999


class _FakeTarget:
    """Records every factory-interface key `apply_reference` requests via
    `GetFactory` -- the CREATE-path factory-selection recorder bug 2b needs."""

    def __init__(self) -> None:
        self.Cache = _FakeCmCache()
        self.PossibilityLists = _FakePossibilityListsOps()
        self.requested_factory_keys: list = []

    def GetFactory(self, key):
        self.requested_factory_keys.append(key)
        return _FakeFactory()


def _install_fake_lcm(monkeypatch) -> types.ModuleType:
    """Inject a fake `SIL.LCModel` + `System` so `apply_reference`'s CREATE
    arm (real `from SIL.LCModel import ...` / `from System import Guid`
    local imports) resolves against fakes instead of a live LCM host.
    Mirrors the identity-cast pattern already used by
    tests/unit/test_categories_stem_names.py and
    tests/unit/test_categories_phonology.py.
    """

    class _IdentityCast:
        """A fake .NET interface type: casting an object to it is a no-op,
        just like a real COM QueryInterface cast when the underlying object
        already satisfies the interface."""

        def __new__(cls, obj):
            return obj

    class ICmPossibilityFactory(_IdentityCast):
        pass

    class ICmPossibility(_IdentityCast):
        pass

    class ICmPossibilityList(_IdentityCast):
        pass

    class ICmSemanticDomainFactory(_IdentityCast):
        pass

    class ICmAnthroItemFactory(_IdentityCast):
        pass

    class IMoMorphTypeFactory(_IdentityCast):
        pass

    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.ICmPossibilityFactory = ICmPossibilityFactory
    fake_lcm.ICmPossibility = ICmPossibility
    fake_lcm.ICmPossibilityList = ICmPossibilityList
    fake_lcm.ICmSemanticDomainFactory = ICmSemanticDomainFactory
    fake_lcm.ICmAnthroItemFactory = ICmAnthroItemFactory
    fake_lcm.IMoMorphTypeFactory = IMoMorphTypeFactory

    fake_system = types.ModuleType("System")
    fake_system.Guid = types.SimpleNamespace(Parse=lambda s: s)

    monkeypatch.setitem(
        sys.modules, "SIL", sys.modules.get("SIL") or types.ModuleType("SIL")
    )
    monkeypatch.setitem(sys.modules, "SIL.LCModel", fake_lcm)
    monkeypatch.setitem(sys.modules, "System", fake_system)

    return fake_lcm


_ITEM_CLSID_FACTORY_CASES = (
    (66, "ICmSemanticDomainFactory"),
    (26, "ICmAnthroItemFactory"),
    (5042, "IMoMorphTypeFactory"),
    (7, "ICmPossibilityFactory"),
)


@pytest.mark.parametrize("item_clsid, expected_factory_name", _ITEM_CLSID_FACTORY_CASES)
def test_create_path_requests_typed_factory_by_item_clsid(
    monkeypatch, item_clsid, expected_factory_name,
):
    """BUG 2b: `apply_reference`'s CREATE arm must request the
    type-matched factory keyed off `target_list.ItemClsid`, not always the
    generic `ICmPossibilityFactory`.

    Dry trace against current code (item_clsid in {66, 26, 5042}):
    `apply_reference` never reads `target_list.ItemClsid` at all -- it
    always does `factory = ICmPossibilityFactory(target.GetFactory(
    ICmPossibilityFactory))`, so `target.requested_factory_keys[-1]` is
    always `fake_lcm.ICmPossibilityFactory`, never the expected typed
    factory -- the `assert requested is expected` line fails.
    (item_clsid == 7 is the one case where the generic factory IS correct;
    it passes both today and after the fix, documenting the no-op case.)
    """
    fake_lcm = _install_fake_lcm(monkeypatch)
    # `apply_reference`'s CREATE arm does `from .residue import apply_residue`
    # -- a LOCAL import resolved fresh from `gramtrans.Lib.residue`'s module
    # namespace at call time. Patching that module attribute (rather than
    # anything on `references`) is what actually intercepts it; this keeps
    # the test scoped to the factory-selection bug under test instead of
    # also having to fake a full Description/LiftResidue multistring surface.
    from gramtrans.Lib import residue as residue_mod
    monkeypatch.setattr(residue_mod, "apply_residue", lambda *a, **k: None)

    target_list = _FakeTypedTargetList(item_clsid)
    leaf = _FakeCreatedItem("44444444-4444-4444-4444-444444444444")

    spec = ReferenceFieldSpec(
        owner_class="LexSense",
        field_name="SemanticDomainsRC",
        cardinality=ReferenceCardinality.COLLECTION,
        target_list_path=lambda target: target_list,
        hierarchical=True,
    )
    decision = ReferenceDecision(
        action=ReferenceAction.CREATE,
        ancestors_to_create=(leaf,),
        source_item=leaf,
    )
    target = _FakeTarget()

    references.apply_reference(decision, target, None, spec, {}, tag=None)

    assert target.requested_factory_keys, "GetFactory was never called"
    requested = target.requested_factory_keys[-1]
    expected = getattr(fake_lcm, expected_factory_name)
    assert requested is expected, (
        f"ItemClsid={item_clsid}: apply_reference requested {requested!r}, "
        f"expected {expected_factory_name} ({expected!r})"
    )


# ============================================================================
# Ancestor walk must be driven by OwningPossibility, not the static
# `hierarchical` flag on the spec
# ============================================================================

class _FakeTsString:
    def __init__(self, text) -> None:
        self.Text = text or None


class _FakeMultiString:
    """Fake ICmMultiString: per-handle text storage (mirrors
    tests/unit/test_reference_resolver.py's `_FakeMultiString`)."""

    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})

    def get_String(self, ws_handle):
        return _FakeTsString(self._data.get(ws_handle))


class _FakeFlatSpecPossibility:
    """Minimal `decide_reference`-shaped fake matching
    tests/unit/test_reference_resolver.py's `_FakePossibility` (Guid/guid,
    Name multistring, IsProtected, Owner/OwningPossibility)."""

    def __init__(self, guid: str, name: str = "", owner=None) -> None:
        self.Guid = guid
        self.guid = guid
        self.Name = _FakeMultiString({_WS_EN: name} if name else {})
        self.Abbreviation = _FakeMultiString({})
        self.IsProtected = False
        self.Owner = owner
        self.OwningPossibility = owner


class _FakeFlatTargetList:
    def __init__(self, items=()) -> None:
        self.PossibilitiesOS = list(items)


def test_create_ancestor_walk_driven_by_owning_possibility_not_static_hierarchical_flag():
    """A nested source item under a spec statically flagged
    `hierarchical=False` (e.g. UsageTypesRC in REFERENCE_FIELD_MAP) must
    still yield its full ancestor chain if the source project actually grew
    a tree under that field (research note: UsageTypes Depth=127 in some
    projects) -- the walk must be driven DYNAMICALLY by `OwningPossibility`,
    never gated on the field map's static flag.

    Dry trace against current code: `decide_reference`'s CREATE branch does
    `ancestors = _ancestor_chain(source_item) if spec.hierarchical else
    (source_item,)`. Since `spec.hierarchical` is `False` here,
    `ancestors_to_create` is `(leaf,)` -- `_ancestor_chain` is never even
    called, so `parent` is silently dropped. The
    `assert decision.ancestors_to_create == (parent, leaf)` line fails
    (actual is `(leaf,)`).
    """
    parent = _FakeFlatSpecPossibility(
        "55555555-5555-5555-5555-555555555555", name="Parent", owner=None,
    )
    leaf = _FakeFlatSpecPossibility(
        "66666666-6666-6666-6666-666666666666", name="Leaf", owner=parent,
    )

    spec = ReferenceFieldSpec(
        owner_class="LexSense",
        field_name="UsageTypesRC",
        cardinality=ReferenceCardinality.COLLECTION,
        target_list_path=lambda target: _FakeFlatTargetList([]),
        hierarchical=False,  # statically flagged flat, per the field map
    )

    decision = references.decide_reference(leaf, object(), spec, {})

    assert decision.action == ReferenceAction.CREATE
    assert decision.ancestors_to_create == (parent, leaf), (
        "expected the full root->leaf chain (parent, leaf) even though "
        f"spec.hierarchical=False; got {decision.ancestors_to_create!r}"
    )
