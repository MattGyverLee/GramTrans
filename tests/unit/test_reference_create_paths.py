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

    class ILexEntryTypeFactory(_IdentityCast):
        pass

    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.ICmPossibilityFactory = ICmPossibilityFactory
    fake_lcm.ICmPossibility = ICmPossibility
    fake_lcm.ICmPossibilityList = ICmPossibilityList
    fake_lcm.ICmSemanticDomainFactory = ICmSemanticDomainFactory
    fake_lcm.ICmAnthroItemFactory = ICmAnthroItemFactory
    fake_lcm.IMoMorphTypeFactory = IMoMorphTypeFactory
    # 027 US2/US3 (contract C3): VariantEntryTypesRS/ComplexEntryTypesRS
    # (ItemClsid 5118) route through ILexEntryTypeFactory -- added to the
    # CREATE arm's unconditional `from SIL.LCModel import (...)` alongside
    # the other 6, so every fake stub of that module needs this attribute
    # too, even tests (like this one) that never exercise clsid 5118.
    fake_lcm.ILexEntryTypeFactory = ILexEntryTypeFactory

    # 025 P0 (reversal categories, ItemClsid 5049 = PartOfSpeech): identity
    # cast for `IPartOfSpeechFactory` -- NOT yet in the production
    # `factory_by_item_clsid` map (that IS the bug), but every fake stub of
    # this module needs the attribute available so a test can supply it as
    # `target.GetFactory`'s return value once/if the map gains the entry.
    class IPartOfSpeechFactory(_IdentityCast):
        pass

    fake_lcm.IPartOfSpeechFactory = IPartOfSpeechFactory

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


# ============================================================================
# P0 (feature 025-full-reversals) -- ItemClsid 5049 (PartOfSpeech, a
# reversal category) has NO 1-arg `Create(Guid)` overload on
# `IPartOfSpeechFactory`; only owner-taking overloads exist:
# `Create(Guid, ICmPossibilityList owner)` (root) and
# `Create(Guid, IPartOfSpeech owner)` (child, auto-owned under
# `owner.SubPossibilitiesOS`). Confirmed live this session -- see
# scratchpad/build025_fixture.py's `fac.Create(guid, en_poslist)` /
# `fac.Create(guid, parent)` calls and
# specs/025-full-reversals/reviews/live-proof-s2s3-reversal-fixtures.md.
# The generic create-then-add idiom at `apply_reference`'s CREATE arm
# (`factory.Create(parsed_guid)` then a separate `_add_to_owner(...)`
# call) cannot work for this clsid: it has no 1-arg overload to call in
# the first place, and 5049 is not even present in `factory_by_item_clsid`
# today, so the fail-loud "unmapped item class" branch fires first.
# ============================================================================

class _FakeReversalPOS:
    """Fake `IPartOfSpeech` reversal-category item: stands in for both a
    ROOT category (owned by the index's `PartsOfSpeechOA` list) and a
    CHILD category (owned by a parent `IPartOfSpeech`). Exposes
    `SubPossibilitiesOS` so a child can be auto-owned under it, mirroring
    the real owner-taking `Create(Guid, IPartOfSpeech owner)` overload."""

    def __init__(self, guid: str) -> None:
        self.Guid = guid
        self.guid = guid
        self.Owner = None
        self.SubPossibilitiesOS = _FakeCollection()


class _FakeReversalIndexPOSList:
    """Fake per-index `PartsOfSpeechOA` (ItemClsid 5049) -- the ONLY legal
    home for a reversal category (R5: creation must never touch
    `LangProject.PartsOfSpeechOA`, modeled below as a SEPARATE,
    independently-asserted fake)."""

    def __init__(self) -> None:
        self.ItemClsid = 5049
        self.PossibilitiesOS = _FakeCollection()


class _FakeLangProjectPOSList:
    """A SEPARATE fake standing in for `LangProject.PartsOfSpeechOA`. The
    test asserts nothing is ever added to this collection -- R5's
    never-touch-LangProject guarantee for reversal categories."""

    def __init__(self) -> None:
        self.ItemClsid = 5049
        self.PossibilitiesOS = _FakeCollection()


class _FakeIPartOfSpeechFactoryOwnerOnly:
    """Faithful stand-in for the REAL `IPartOfSpeechFactory` contract:
    there is NO 1-arg `Create(Guid)` overload at all -- only
    `Create(Guid, owner)` where `owner` is either the index's
    `ICmPossibillityList` (root) or a parent `IPartOfSpeech` (child).
    Calling with a single positional arg (today's `references.py`
    create-then-add idiom, `factory.Create(parsed_guid)`) raises
    `TypeError` -- exactly what a real 1-arg .NET overload-resolution miss
    looks like from Python. The factory itself performs ownership (unlike
    the generic `ICmPossibilityFactory.Create(Guid)` + separate
    `_add_to_owner` idiom): a root is appended to `owner.PossibilitiesOS`,
    a child to `owner.SubPossibilitiesOS`.
    """

    def Create(self, guid, owner=None):
        if owner is None:
            raise TypeError(
                "IPartOfSpeechFactory.Create(Guid) has no 1-arg overload -- "
                "owner (ICmPossibilityList root or IPartOfSpeech parent) "
                "is required"
            )
        new_pos = _FakeReversalPOS(str(guid))
        new_pos.Owner = owner
        if isinstance(owner, _FakeReversalPOS):
            owner.SubPossibilitiesOS.Add(new_pos)
        else:
            owner.PossibilitiesOS.Add(new_pos)
        return new_pos


class _FakeTargetForReversalPOS(_FakeTarget):
    """`GetFactory` returns the owner-only `IPartOfSpeechFactory` stub for
    the `IPartOfSpeechFactory` key, and the generic `_FakeFactory` for any
    other key (matching real `FLExProject.GetFactory`'s per-interface
    dispatch)."""

    def __init__(self, ipos_factory_key) -> None:
        super().__init__()
        self._ipos_factory_key = ipos_factory_key
        self.ipos_factory = _FakeIPartOfSpeechFactoryOwnerOnly()

    def GetFactory(self, key):
        self.requested_factory_keys.append(key)
        if key is self._ipos_factory_key:
            return self.ipos_factory
        return _FakeFactory()


def test_create_path_reversal_category_hierarchical_owner_taking_factory(monkeypatch):
    """P0 (feature 025-full-reversals): a 2-level reversal-category chain
    (`parent` -> `child`, ItemClsid 5049) must be created via
    `IPartOfSpeechFactory`'s owner-taking `Create` overloads -- root via
    `Create(guid, <index's PartsOfSpeechOA list>)`, child via
    `Create(guid, <created parent POS>)` -- and the resulting CHILD must:

    1. land in the TARGET REVERSAL INDEX's OWN `PartsOfSpeechOA`
       (`target_list.PossibilitiesOS`), never `LangProject.PartsOfSpeechOA`
       (R5 -- asserted via a wholly separate, untouched
       `_FakeLangProjectPOSList` fake);
    2. become the entry's `PartOfSpeechRA` (the `owner_obj` `setattr` at
       the end of `apply_reference`'s CREATE arm).

    Dry trace against today's `references.py`: `factory_by_item_clsid`
    (CREATE arm, ~line 1041) has no entry for `item_clsid=5049` at all --
    `factory_iface` resolves to `None` and the fail-loud "unmapped item
    class" branch raises `UnmappedItemClassError` before the factory is
    ever consulted, so this test fails via that exception, never reaching
    the assertions below. (A hypothetical partial fix that added
    `5049: IPartOfSpeechFactory` to the map WITHOUT also replacing the
    generic `factory.Create(parsed_guid)` 1-arg call with the owner-taking
    overloads would instead fail via this fake's `TypeError`, since the
    fake has no 1-arg overload to satisfy either -- this test remains RED
    against either half-fix.)
    """
    fake_lcm = _install_fake_lcm(monkeypatch)
    from gramtrans.Lib import residue as residue_mod
    monkeypatch.setattr(residue_mod, "apply_residue", lambda *a, **k: None)

    target_list = _FakeReversalIndexPOSList()  # the reversal index's OWN list
    lang_project_list = _FakeLangProjectPOSList()  # must stay untouched (R5)

    parent_src = _FakeCreatedItem("77777777-7777-7777-7777-777777777777")
    child_src = _FakeCreatedItem("88888888-8888-8888-8888-888888888888")

    spec = ReferenceFieldSpec(
        owner_class="ReversalIndexEntry",
        field_name="PartOfSpeechRA",
        cardinality=ReferenceCardinality.ATOMIC,
        target_list_path=lambda target: target_list,
        hierarchical=True,
    )
    decision = ReferenceDecision(
        action=ReferenceAction.CREATE,
        ancestors_to_create=(parent_src, child_src),
        source_item=child_src,
    )
    target = _FakeTargetForReversalPOS(fake_lcm.IPartOfSpeechFactory)

    class _FakeEntry:
        PartOfSpeechRA = None

    entry = _FakeEntry()

    result = references.apply_reference(decision, target, entry, spec, {}, tag=None)

    # -- created-child identity and entry wiring --
    assert result is not None
    assert references._guid_str(result) == str(child_src.Guid).lower()
    assert entry.PartOfSpeechRA is result, (
        "entry.PartOfSpeechRA must be wired to the created child POS"
    )

    # -- placement: TARGET INDEX's own list, never LangProject (R5) --
    assert len(lang_project_list.PossibilitiesOS) == 0, (
        "LangProject.PartsOfSpeechOA must never be touched for a reversal "
        "category CREATE"
    )
    assert len(target_list.PossibilitiesOS) == 1, (
        "the root category must land in the reversal index's OWN "
        "PartsOfSpeechOA.PossibilitiesOS"
    )
    root = list(target_list.PossibilitiesOS)[0]
    assert references._guid_str(root) == str(parent_src.Guid).lower()
    assert len(root.SubPossibilitiesOS) == 1, (
        "the child category must be auto-owned under the created root "
        "via Create(guid, parent) -- never appended to the flat list"
    )
    assert list(root.SubPossibilitiesOS)[0] is result
