"""Write-first tests locking a FR-009 accuracy gap (feature 024, QC P1):

DEFECT: `Lib/owned.py`'s recursive sub-sense leg (`OWNED_OBJECT_MAP`'s
`LexSense.SensesOS` row, ``recurse=True`` -- `_copy_one_owned_child` /
`walk_owned_children`) creates a copy of a source sub-sense but never
registers it into ``ctx._copy_set``. Only `Lib/categories.py`'s
entry/top-level-sense registration sites do that (`_plan_entry_reference_
decisions` ~categories.py:3390/3394/3425, `_walk_lex_entry_closure`
~categories.py:3949/3953/4022). Effect:

  (a) A lexical relation whose SOLE `TargetsRS` member is a copied
      sub-sense can never be reproduced: `_evaluate_lexical_relation`
      (categories.py ~3558-3563) checks `ctx._copy_set` membership, and the
      sub-sense's GUID is never there -- even when discovery/reproduction
      is driven directly against the sub-sense's own GUID (isolating the
      copy-set root cause here from the separate, narrower "nothing calls
      `_reproduce_lex_relations_for_member` for a sub-sense's own GUID at
      all" wiring gap in `_walk_lex_entry_closure`/`_plan_entry_reference_
      decisions`), the relation is refused ("relation reduced to zero
      copied members; not reproduced").

  (b) A relation that ALSO includes a copied top-level entry/sense reports
      the copied sub-sense as "member not in copy set" (categories.py
      ~3563/3634, `DroppedItemRecord` reason "lexical-relation member not
      in copy set") -- an INACCURATE report for an item that WAS in fact
      faithfully reproduced.

Fakes are modeled on `tests/unit/test_owned_object_walk.py` (sense/
sub-sense/owned-walk shapes: `_FakeSourceSense`, `_NewSense`,
`_FakeSenseFactory`, `_FakeProject`, `_FakeContext`) and
`tests/unit/test_lexical_relations.py` (lexical-relation shapes:
`_FakeLexRefType`/`_FakeLexReferenceFactory`/`_FakeSourceLexReference`,
`ILexRefType.MappingType` real, MCP-confirmed enum ints -- 10
kmtEntryOrSenseCollection is used throughout: open-ended, no minimum member
count, so the PAIR/TREE structural-minimum branches of
`_evaluate_lexical_relation` never interfere with isolating this defect).

Both tests below MUST FAIL against current code (write-first, RED). Do NOT
implement the fix in this file.
"""
from __future__ import annotations

from gramtrans.Lib import categories, owned


WS_EN = 100
_TAG = "tag-subsense-copy-set"
_MAPPING_TYPE_COLLECTION = 10  # kmtEntryOrSenseCollection -- open-ended, no minimum


# ============================================================================
# Sense / sub-sense fakes (modeled on test_owned_object_walk.py)
# ============================================================================

class _FakeMultiString:
    def __init__(self, data=None):
        self._data = dict(data or {})

    def get_String(self, ws_handle):
        class _Ts:
            def __init__(self, text):
                self.Text = text
        return _Ts(self._data.get(ws_handle))


class _FakeSourceSense:
    """Fake ILexSense -- same shape as test_owned_object_walk.py's
    `_FakeSourceSense`: `SensesOS` is the recursive sub-sense leg the walk
    (`OWNED_OBJECT_MAP`'s `recurse=True` row) reproduces."""

    def __init__(self, guid, gloss="", examples=(), sub_senses=()):
        self.Guid = guid
        self.guid = guid
        self.Gloss = _FakeMultiString({WS_EN: gloss} if gloss else {})
        self.ExamplesOS = list(examples)
        self.SensesOS = list(sub_senses)
        self.SenseTypeRA = None


class _FakeOwningCollection:
    def __init__(self, items=()):
        self._items = list(items)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __getitem__(self, idx):
        return self._items[idx]

    def Add(self, item):
        self._items.append(item)


class _NewSense:
    def __init__(self, guid="new-sense-guid"):
        self.Guid = guid
        self.guid = guid
        self.ExamplesOS = _FakeOwningCollection()
        self.SensesOS = _FakeOwningCollection()
        self.SenseTypeRA = None


class _FakeSenseFactory:
    """OWNER_TAKING: `ILexSenseFactory.Create(Guid, ILexSense owner)`
    (sub-senses) -- same MCP-confirmed shape `test_owned_object_walk.py`
    proves live for `OwnedCreateKind.OWNER_TAKING`."""

    def __init__(self):
        self.create_calls = []

    def Create(self, guid, owner):
        if not hasattr(owner, "SensesOS"):
            raise TypeError(
                "ILexSenseFactory.Create(guid, owner) expects owner to be "
                f"an ILexSense (SensesOS); got {owner!r}"
            )
        self.create_calls.append((guid, owner))
        new_s = _NewSense(guid)
        owner.SensesOS.Add(new_s)
        return new_s


class _FakeSyncOps:
    def GetSyncableProperties(self, obj):
        return {"_marker": getattr(obj, "Guid", None)}

    def ApplySyncableProperties(self, obj, props, ws_map=None):
        pass


# ============================================================================
# Lexical-relation fakes (modeled on test_lexical_relations.py)
# ============================================================================

class _FakeGuidObj:
    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid


class _FakeLexRefType(_FakeGuidObj):
    """Fake ILexRefType -- `.MembersOC` (owns `ILexReference` instances) +
    `.MappingType` (real LexRefTypeTags.MappingTypes int)."""

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
    `owner.MembersOC` itself."""

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
    `.TargetsRS` is the ORDERED member sequence."""

    def __init__(self, guid, owner_type, targets=()):
        super().__init__(guid)
        self.Owner = owner_type
        self.TargetsRS = list(targets)


# ============================================================================
# Project / context fakes (modeled on both files)
# ============================================================================

class _FakeTargetList:
    """Fake ICmPossibilityList: flat container searched by GUID."""

    def __init__(self, items=()):
        self.PossibilitiesOS = list(items)


class _FakeLexDb:
    def __init__(self, references_oa):
        self.ReferencesOA = references_oa
        self.SenseTypesOA = _FakeTargetList()
        self.TranslationTagsOA = _FakeTargetList()
        self.LanguagesOA = _FakeTargetList()
        self.PublicationTypesOA = _FakeTargetList()


class _FakeLangProject:
    def __init__(self, references_oa):
        self.LexDbOA = _FakeLexDb(references_oa)


class _FakeCache:
    def __init__(self, lang_project):
        self.LangProject = lang_project
        self.DefaultAnalWs = WS_EN


class _FakeProject:
    """Fake FLExProject-shaped handle: `Cache.LangProject...` (both the
    lexical-relation type list AND the owned-walk's per-class sync-ops
    namespaces), plus the owned-child/lex-reference factories exposed via
    `GetService` (the LCM service-locator idiom)."""

    def __init__(self, ref_types=(), factories=None):
        self.Cache = _FakeCache(_FakeLangProject(_FakeTargetList(ref_types)))
        self.Examples = _FakeSyncOps()
        self.Translations = _FakeSyncOps()
        self.Pronunciations = _FakeSyncOps()
        self.Etymology = _FakeSyncOps()
        self.Senses = _FakeSyncOps()
        self._factories = dict(factories or {})
        self._factories.setdefault("ILexSenseFactory", _FakeSenseFactory())
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


# ============================================================================
# Test 1 -- relation whose SOLE member is a copied sub-sense
# ============================================================================

def test_relation_with_sole_subsense_member_is_reproduced():
    """A lexical relation whose only `TargetsRS` member is a sub-sense
    created via the recursive `SensesOS` leg must be reproduced once that
    sub-sense is copied: the sub-sense's own GUID must land in
    `ctx._copy_set` (so discovery/reproduction driven by that GUID finds
    it a member), and `_reproduce_lex_relations_for_member` must create the
    target relation with the sub-sense's copied counterpart in `TargetsRS`
    -- with no false "not in copy set" report.

    FAILS TODAY: `walk_owned_children`'s recursive sub-sense leg never
    registers the newly-created sub-sense into `ctx._copy_set`. Both
    assertions below fail as a result: the copy-set membership check
    directly, and the relation-reproduction check because
    `_evaluate_lexical_relation` sees ZERO copied members for this relation
    (its sole member is the never-registered sub-sense) and refuses to
    reproduce it at all ("relation reduced to zero copied members; not
    reproduced") -- `target_type.MembersOC` stays empty rather than gaining
    the reproduced relation.
    """
    type_guid = "type-guid-sub1"
    rel_guid = "rel-guid-sub1"

    sub1 = _FakeSourceSense("sub-1", gloss="sub sense")
    src_sense = _FakeSourceSense("top-sense-1", gloss="top sense", sub_senses=(sub1,))
    new_sense = _NewSense("new-top-sense-1")

    src_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)
    src_rel = _FakeSourceLexReference(rel_guid, src_type, targets=[sub1])
    src_type.MembersOC.Add(src_rel)

    target_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)
    rel_factory = _FakeLexReferenceFactory()

    source_handle = _FakeProject(ref_types=[src_type])
    target_handle = _FakeProject(
        ref_types=[target_type], factories={"ILexReferenceFactory": rel_factory})

    ctx = _FakeContext(source_handle, target_handle, copy_set={})
    resolver_cache: dict = {}
    dropped: list = []

    # Reproduce the owned sub-sense (the recursive SensesOS leg).
    owned.walk_owned_children(
        src_sense, new_sense, ctx, _TAG, resolver_cache, dropped)
    new_sub1 = new_sense.SensesOS[0]

    # Root-cause assertion: the copied sub-sense must be a copy-set member.
    assert "sub-1" in ctx._copy_set
    assert ctx._copy_set["sub-1"] is new_sub1

    # Effect assertion: discovery/reproduction driven by the sub-sense's own
    # GUID must find and reproduce the relation.
    categories._reproduce_lex_relations_for_member(
        sub1, ctx, _TAG, resolver_cache, dropped)

    new_rels = list(target_type.MembersOC)
    assert len(new_rels) == 1
    assert list(new_rels[0].TargetsRS) == [new_sub1]
    assert not any("not in copy set" in getattr(r, "reason", "") for r in dropped)


# ============================================================================
# Test 2 -- relation with a copied top-level sense AND a copied sub-sense
# ============================================================================

def test_relation_with_sense_and_subsense_members_reproduces_without_false_drop():
    """A relation whose `TargetsRS` includes both a copied top-level sense
    and a copied sub-sense must reproduce with BOTH members present in
    `TargetsRS`, and must NOT report the sub-sense as "member not in copy
    set" -- it WAS copied (via the recursive `SensesOS` leg), just never
    registered.

    FAILS TODAY: the sub-sense is copied by `walk_owned_children` but never
    lands in `ctx._copy_set`. `_evaluate_lexical_relation` therefore treats
    it as a genuinely missing member: `TargetsRS` ends up with only the
    top-level sense (not both members), and a `DroppedItemRecord` (reason
    "lexical-relation member not in copy set") is falsely appended for the
    sub-sense -- an inaccurate report for an item that was, in fact,
    faithfully reproduced.
    """
    type_guid = "type-guid-both"
    rel_guid = "rel-guid-both"

    sub1 = _FakeSourceSense("sub-2", gloss="sub sense two")
    src_sense = _FakeSourceSense(
        "top-sense-2", gloss="top sense two", sub_senses=(sub1,))
    new_sense = _NewSense("new-top-sense-2")

    src_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)
    src_rel = _FakeSourceLexReference(rel_guid, src_type, targets=[src_sense, sub1])
    src_type.MembersOC.Add(src_rel)

    target_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)
    rel_factory = _FakeLexReferenceFactory()

    source_handle = _FakeProject(ref_types=[src_type])
    target_handle = _FakeProject(
        ref_types=[target_type], factories={"ILexReferenceFactory": rel_factory})

    # Top-level sense already registered into the copy set -- matches
    # production's own convention (categories.py registers the entry/each
    # top-level sense into `ctx._copy_set` BEFORE discovering/reproducing
    # any relation it participates in as a member).
    ctx = _FakeContext(
        source_handle, target_handle, copy_set={"top-sense-2": new_sense})
    resolver_cache: dict = {}
    dropped: list = []

    owned.walk_owned_children(
        src_sense, new_sense, ctx, _TAG, resolver_cache, dropped)
    new_sub1 = new_sense.SensesOS[0]

    categories._reproduce_lex_relations_for_member(
        src_sense, ctx, _TAG, resolver_cache, dropped)

    new_rels = list(target_type.MembersOC)
    assert len(new_rels) == 1
    assert list(new_rels[0].TargetsRS) == [new_sense, new_sub1]
    assert not any(
        r.item_guid == "sub-2" and "not in copy set" in r.reason for r in dropped
    )
