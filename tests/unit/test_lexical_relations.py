"""Write-first unit tests for the T031 lexical-relation reproduce path
(feature 024 US3, FR-008) -- `categories.reproduce_lexical_relation`.

Contract: spec.md FR-008 ("reproduce lexical relations for a copied entry
when that entry participates as a member of the relation, preserving the
relation's mapping/tree/pair structure and only the members actually
copied"); data-model.md's `ILexRefType.MembersOC`/`.MappingType` +
`IMoAlloAdhocProhib...` confirmed-surfaces list; research.md R6's "mirrors
the lexical-relation partial-member rule" cross-reference.

CONFIRMED-LIVE surface (MCP, 2026-07-11/12): `ILexReferenceFactory.Create
(Guid, ILexRefType owner)` -- OWNER_TAKING (the new `ILexReference` is owned
by, and the factory itself adds it to, `owner.MembersOC`). Reproduce: find/
resolve the matching target `ILexRefType` by GUID, `Create(guid,
targetType)`, populate `ILexReference.TargetsRS` (ORDERED) with COPIED
members ONLY. `ILexRefType.MappingType` (Int32) gives the relation's
structural kind (tree/pair/sequence/collection) -- preserve structure;
report members not in the copy set (never silently include or drop).

Function under test (NOT YET IMPLEMENTED -- T031, categories.py, per
tasks.md): `categories.reproduce_lexical_relation(src_relation, ctx, tag,
resolver_cache, dropped) -> new_relation | None`. This is the PER-RELATION
leg of T031 (mirrors `owned.reproduce_allomorph_hung_data`'s per-allomorph
granularity) -- discovering every relation a given copied entry/sense
participates in is a separate concern this file does not test.

Copy-set convention (same fixture design as `test_allomorph_hung_data.py`):
`ctx._copy_set` is a `dict[str_guid, already_copied_target_object]` --
membership via `in`, value gives the real copied target object to point
`TargetsRS` at.

MappingType constants: `_MAPPING_TYPE_COLLECTION`/`_MAPPING_TYPE_PAIR` below
are now the REAL, MCP-verified `LexRefTypeTags.MappingTypes` .NET enum
values (T031 implementation cycle correction -- the original values (100/200)
were arbitrary placeholder sentinels, out of scope for the write-first
cycle that authored this file). Authoritative mapping (int -> name): 0
kmtSenseCollection, 1 kmtSensePair, 2 kmtSenseAsymmetricPair, 3 kmtSenseTree,
4 kmtSenseSequence, 5 kmtEntryCollection, 6 kmtEntryPair, 7
kmtEntryAsymmetricPair, 8 kmtEntryTree, 9 kmtEntrySequence, 10
kmtEntryOrSenseCollection, 11 kmtEntryOrSensePair, 12
kmtEntryOrSenseAsymmetricPair, 13 kmtEntryOrSenseTree, 14
kmtEntryOrSenseSequence, 15 kmtSenseUnidirectional, 16
kmtEntryUnidirectional, 17 kmtEntryOrSenseUnidirectional. `_MAPPING_TYPE_
COLLECTION` = 10 (kmtEntryOrSenseCollection, open-ended -- no minimum
member count); `_MAPPING_TYPE_PAIR` = 11 (kmtEntryOrSensePair, exactly 2
members required). PAIR-family (1,2,6,7,11,12) and TREE-family (3,8,13)
values drive `categories._evaluate_lexical_relation`'s partial-member
policy; COLLECTION/SEQUENCE/UNIDIRECTIONAL values are all open-ended and
share the same "reproduce with whatever was copied" treatment as the
COLLECTION value exercised here.
"""
from __future__ import annotations

from gramtrans.Lib import categories


# ============================================================================
# Small fakes
# ============================================================================

class _FakeGuidObj:
    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid


class _FakeOwningCollection:
    def __init__(self, items=()) -> None:
        self._items = list(items)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __getitem__(self, idx):
        return self._items[idx]

    def __contains__(self, item):
        return item in self._items

    def Add(self, item):
        self._items.append(item)


class _FakeMember(_FakeGuidObj):
    """Fake ILexEntry/ILexSense `TargetsRS` member -- only GUID matters for
    the resolver's copy-set membership check."""


class _FakeLexRefType(_FakeGuidObj):
    """Fake ILexRefType -- `.MembersOC` (owns `ILexReference` instances,
    the OWNER_TAKING create target) + `.MappingType` (structural
    cardinality sentinel; see module docstring)."""

    def __init__(self, guid, mapping_type, members=()):
        super().__init__(guid)
        self.MappingType = mapping_type
        self.MembersOC = _FakeOwningCollection(members)


class _FakeNewLexReference(_FakeGuidObj):
    def __init__(self, guid):
        super().__init__(guid)
        self.TargetsRS = _FakeOwningCollection()


class _FakeLexReferenceFactory:
    """OWNER_TAKING: `ILexReferenceFactory.Create(Guid, ILexRefType owner)`
    (confirmed live via MCP) -- adds the new `ILexReference` to
    `owner.MembersOC` itself. Rejects the wrong shape (a non-`ILexRefType`
    owner, i.e. anything lacking `MembersOC`) so a wrongly-shaped caller
    fails loudly instead of silently doing the wrong thing."""

    def __init__(self):
        self.create_calls = []

    def Create(self, guid, owner):
        if not hasattr(owner, "MembersOC"):
            raise TypeError(
                "ILexReferenceFactory.Create(guid, owner) expects owner to "
                f"be an ILexRefType (MembersOC); got {owner!r}"
            )
        self.create_calls.append((guid, owner))
        new_rel = _FakeNewLexReference(guid)
        owner.MembersOC.Add(new_rel)
        return new_rel


class _FakeSourceLexReference(_FakeGuidObj):
    """Fake ILexReference -- `.Owner` is the SOURCE `ILexRefType`;
    `.TargetsRS` is the ORDERED member sequence (confirmed live, per
    data-model.md)."""

    def __init__(self, guid, owner_type, targets=()):
        super().__init__(guid)
        self.Owner = owner_type
        self.TargetsRS = list(targets)


class _FakeTargetList:
    """Fake ICmPossibilityList (`lp.LexDbOA.ReferencesOA`) -- flat is
    sufficient for these fixtures (real `ILexRefType`s ARE tree-shaped in
    FLEx, but GUID-equality lookup doesn't need to exercise that nesting
    here)."""

    def __init__(self, items=()):
        self.PossibilitiesOS = list(items)


class _FakeLexDb:
    def __init__(self, references_oa):
        self.ReferencesOA = references_oa


class _FakeLangProject:
    def __init__(self, references_oa):
        self.LexDbOA = _FakeLexDb(references_oa)


class _FakeCache:
    def __init__(self, lang_project):
        self.LangProject = lang_project


class _FakeProject:
    def __init__(self, ref_types=(), factories=None):
        self.Cache = _FakeCache(_FakeLangProject(_FakeTargetList(ref_types)))
        self._factories = factories or {}
        self.requested_services = []

    def GetService(self, name):
        self.requested_services.append(name)
        return self._factories[name]


class _FakeContext:
    def __init__(self, source_handle, target_handle, copy_set=None):
        self.source_handle = source_handle
        self.target_handle = target_handle
        self._ws_map = {}
        self._copy_set = copy_set if copy_set is not None else {}


_TAG = "tag-lexical-relations"

# See module docstring -- real, MCP-verified LexRefTypeTags.MappingTypes values.
_MAPPING_TYPE_COLLECTION = 10  # kmtEntryOrSenseCollection -- no minimum member count
_MAPPING_TYPE_PAIR = 11        # kmtEntryOrSensePair -- exactly 2 members required


# ============================================================================
# All members copied -> reproduced, TargetsRS ordered + full, MappingType
# structure preserved (via the matching target ILexRefType).
# ============================================================================

def test_lexical_relation_reproduced_with_all_copied_members_and_mapping_type_preserved():
    rel_guid = "rel-guid-1"
    type_guid = "type-guid-1"

    m_a_src, m_b_src, m_c_src = (
        _FakeMember("m-a"), _FakeMember("m-b"), _FakeMember("m-c"))
    m_a_new, m_b_new, m_c_new = (
        _FakeMember("m-a"), _FakeMember("m-b"), _FakeMember("m-c"))

    src_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)
    src_rel = _FakeSourceLexReference(
        rel_guid, src_type, targets=[m_a_src, m_b_src, m_c_src])

    target_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)
    factory = _FakeLexReferenceFactory()
    target = _FakeProject(ref_types=[target_type],
                           factories={"ILexReferenceFactory": factory})
    source = _FakeProject(ref_types=[src_type])
    ctx = _FakeContext(source, target, copy_set={
        "m-a": m_a_new, "m-b": m_b_new, "m-c": m_c_new,
    })
    dropped: list = []
    resolver_cache: dict = {}

    new_rel = categories.reproduce_lexical_relation(
        src_rel, ctx, _TAG, resolver_cache, dropped)

    assert new_rel is not None
    assert new_rel.Guid == rel_guid
    assert list(new_rel.TargetsRS) == [m_a_new, m_b_new, m_c_new]
    assert new_rel in list(target_type.MembersOC)
    assert dropped == []


# ============================================================================
# Members not in copy set -> reported (never silently included or dropped),
# relation created with ONLY the copied members (unstructured collection
# type -- no minimum to violate).
# ============================================================================

def test_lexical_relation_members_not_in_copy_set_are_reported_and_excluded():
    rel_guid = "rel-guid-2"
    type_guid = "type-guid-2"

    m_a_src, m_b_src, m_c_src = (
        _FakeMember("m-a2"), _FakeMember("m-b2"), _FakeMember("m-c2"))
    m_a_new, m_b_new = (_FakeMember("m-a2"), _FakeMember("m-b2"))
    # m-c2 never copied.

    src_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)
    src_rel = _FakeSourceLexReference(
        rel_guid, src_type, targets=[m_a_src, m_b_src, m_c_src])

    target_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)
    factory = _FakeLexReferenceFactory()
    target = _FakeProject(ref_types=[target_type],
                           factories={"ILexReferenceFactory": factory})
    source = _FakeProject(ref_types=[src_type])
    ctx = _FakeContext(source, target, copy_set={"m-a2": m_a_new, "m-b2": m_b_new})
    dropped: list = []
    resolver_cache: dict = {}

    new_rel = categories.reproduce_lexical_relation(
        src_rel, ctx, _TAG, resolver_cache, dropped)

    assert new_rel is not None
    assert list(new_rel.TargetsRS) == [m_a_new, m_b_new]  # ordered, only copied
    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.item_guid == "m-c2"
    assert "not in copy set" in rec.reason


# ============================================================================
# Pair/tree relation reduced BELOW its structural minimum -- RULING NEEDED.
# ============================================================================

def test_lexical_relation_pair_type_reduced_below_minimum_members():
    """RULING NEEDED (domain reviewer, per task instructions): a PAIR-shaped
    relation type structurally requires exactly 2 members. When only 1 of 2
    is in the copy set, is the most-defensible behavior:

      (A) report + drop the WHOLE relation (mirrors the APR
          all-members-required rule in `test_allomorph_hung_data.py`: a
          structurally invalid partial record is arguably worse than an
          absent one -- a "pair" with one side is not a pair), or

      (B) still create a degenerate 1-member relation (mirrors the plain
          FR-008 partial-member rule exercised above for an unstructured
          collection type, applied uniformly regardless of MappingType)?

    This test currently encodes (A) as the more defensible default
    (Principle I: never silently misrepresent structure) -- no relation
    created, exactly one `DroppedItemRecord` describing the
    reduced-below-minimum condition, keyed to the RELATION itself (not one
    member). If the domain reviewer rules (B) instead, flip the assertion
    block marked below -- the fixture (1-of-2 members copied, PAIR
    MappingType) does not need to change either way.
    """
    rel_guid = "rel-guid-3"
    type_guid = "type-guid-3"

    m_a_src, m_b_src = (_FakeMember("m-a3"), _FakeMember("m-b3"))
    m_a_new = _FakeMember("m-a3")
    # m-b3 never copied.

    src_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_PAIR)
    src_rel = _FakeSourceLexReference(rel_guid, src_type, targets=[m_a_src, m_b_src])

    target_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_PAIR)
    factory = _FakeLexReferenceFactory()
    target = _FakeProject(ref_types=[target_type],
                           factories={"ILexReferenceFactory": factory})
    source = _FakeProject(ref_types=[src_type])
    ctx = _FakeContext(source, target, copy_set={"m-a3": m_a_new})
    dropped: list = []
    resolver_cache: dict = {}

    new_rel = categories.reproduce_lexical_relation(
        src_rel, ctx, _TAG, resolver_cache, dropped)

    # --- RULING (A) encoded here; flip to (B) if the domain reviewer rules
    # otherwise (see docstring) ---
    assert new_rel is None
    assert factory.create_calls == []
    assert list(target_type.MembersOC) == []
    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.item_guid == rel_guid  # the RELATION itself is dropped
    assert "below minimum" in rec.reason or "member not in copy set" in rec.reason
