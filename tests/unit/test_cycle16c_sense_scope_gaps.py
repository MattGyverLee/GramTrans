"""Sense-scope-gap fidelity tests.

History: cycle-17 (feature 024) parked LexSense.{AppendixesRC,
ThesaurusItemsRC, PicturesOS} as unconditional never-silent DROP_REPORTED
gaps (correcting an earlier ruling that had SILENTLY excluded them --
SC-003/FR-010 forbid silent loss).

Feature 030 promotes the first two to COPIED:

- `LexSense.AppendixesRC` -> **link-by-GUID** (`categories._resolve_sense_
  appendixes`). `LexAppendix` is a bespoke owned class in `LexDb.AppendixesOC`
  (only `ContentsOA : IStText`), NOT a possibility list. If the target
  already owns the appendix by GUID it is LINKed; an appendix the target does
  not own is DROP_REPORTED (never created, its owned IStText never
  reproduced). Contract: `contracts/appendix-link-by-guid.md`.

- `LexSense.ThesaurusItemsRC` -> **dynamic-owner resolver**
  (`categories._resolve_sense_thesaurus_items` ->
  `references.resolve_thesaurus_item`). Discovers the owning
  `ICmPossibilityList` by walking `.Owner`, mirrors it to the target by
  owner-class+OwningFlid (never by list GUID -- those differ per project),
  then create/link/updates via the 024 resolver. An item whose owning list
  can't be discovered/mirrored is DROP_REPORTED. Contract:
  `contracts/thesaurus-dynamic-owner.md`.

- `LexSense.PicturesOS` stays an unconditional DROP_REPORTED gap (029) -- it
  is the sole remaining `_SENSE_SCOPE_GAP_FIELDS` row.

Both fields are vacuous-live across every available project, so CREATE-path
proof (B-create/B-nested) is deferred to the constructed-fixture live pass
(quickstart.md Part 2); the offline fakes here cover discovery, mirroring,
link, drop-on-failure, empty-source non-destructiveness, dedup, and
Move/Preview parity.
"""
from __future__ import annotations

import sys
import types

from gramtrans.Lib import categories
from gramtrans.Lib import references
from gramtrans.Lib.models import DroppedItemRecord


WS_EN = 100


# ============================================================================
# Small shared fakes
# ============================================================================

class _FakeMultiString:
    """Fake ICmMultiString -- `_multistring_dict`'s `_data`-dict fallback."""

    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})


class _FakeColl:
    """Fake LCM reference collection: `.Add`, iteration, `len` -- enough for
    `_collection_already_has` + the resolvers' `.Add` writes."""

    def __init__(self, items=()):
        self._items = list(items)

    def Add(self, item):
        self._items.append(item)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)


class _FakeGuidObj:
    def __init__(self, guid, name=""):
        self.Guid = guid
        self.guid = guid
        self.Name = _FakeMultiString({WS_EN: name} if name else {})


class _FakeAppendix:
    """Fake ILexAppendix -- no `.Name` (only `ContentsOA`), so
    `references._item_label` must fail soft to ""."""

    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid


class _FakePicture:
    """Fake ICmPicture -- no `.Name` (only `Caption`/`Description`)."""

    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid


class _FakePossItem(_FakeGuidObj):
    """Fake ICmPossibility thesaurus item: `.Owner` -> its owning list,
    `.SubPossibilitiesOS`/`.OwningPossibility` for the resolver's walks."""

    def __init__(self, guid, name="", owner=None):
        super().__init__(guid, name)
        self.Owner = owner
        self.SubPossibilitiesOS = []
        self.OwningPossibility = None


class _FakePossList(_FakeGuidObj):
    """Fake ICmPossibilityList: duck-types as a list via `PossibilitiesOS`
    (a `CmPossibility` has `SubPossibilitiesOS`, not `PossibilitiesOS`)."""

    def __init__(self, guid, name="", items=(), flid=0, owner=None):
        super().__init__(guid, name)
        self.PossibilitiesOS = list(items)
        self.OwningFlid = flid
        self.Owner = owner


class _FakeTarget:
    """Fake target FLExProject surface the 030 resolvers duck-type against:
    `appendixes` (Section A scan) and `possibility_lists` (Section B Name
    mirror)."""

    def __init__(self, appendixes=(), possibility_lists=()):
        self.appendixes = list(appendixes)
        self.possibility_lists = list(possibility_lists)


class _FakeSourceSense(_FakeGuidObj):
    def __init__(self, guid, gloss="", appendixes=(), thesaurus_items=(),
                 pictures=()):
        self.Guid = guid
        self.guid = guid
        self.ClassName = "LexSense"
        self.Gloss = _FakeMultiString({WS_EN: gloss} if gloss else {})
        self.AppendixesRC = list(appendixes)
        self.ThesaurusItemsRC = list(thesaurus_items)
        self.PicturesOS = list(pictures)
        self.ExamplesOS = []
        self.SensesOS = []
        self.ExtendedNoteOS = []


class _FakeTargetSense:
    """Fake created target sense with writable collections (Move mode)."""

    def __init__(self):
        self.AppendixesRC = _FakeColl()
        self.ThesaurusItemsRC = _FakeColl()


class _FakeSourceEntry(_FakeGuidObj):
    def __init__(self, guid, senses=()):
        self.Guid = guid
        self.guid = guid
        self.SensesOS = list(senses)
        self.LexemeFormOA = None
        self.AlternateFormsOS = []


# ============================================================================
# Scope-gap reporter -- feature 029 (PicturesOS) and 030 (AppendixesRC /
# ThesaurusItemsRC) each reproduce their field, so NOTHING remains an
# unconditional DROP_REPORTED scope gap here.
# ============================================================================

def test_picture_no_longer_reported_by_scope_gap_function():
    """T006: after wiring the 029 seam, `_report_dropped_sense_scope_gaps`
    emits NO drop for `PicturesOS` (a sense owning only pictures produces an
    empty drop set from this function -- the pictures route through the new
    seam instead)."""
    pic1 = _FakePicture("pic-1")
    pic2 = _FakePicture("pic-2")
    pic3 = _FakePicture("pic-3")
    sense = _FakeSourceSense("sense-3", pictures=[pic1, pic2, pic3])

    dropped: list = []
    categories._report_dropped_sense_scope_gaps(sense, dropped)

    assert dropped == []
    assert "PicturesOS" not in dict(categories._SENSE_SCOPE_GAP_FIELDS)


def test_sense_with_no_scope_gap_fields_emits_nothing():
    sense = _FakeSourceSense("sense-4")

    dropped: list = []
    categories._report_dropped_sense_scope_gaps(sense, dropped)

    assert dropped == []


def test_report_dropped_sense_scope_gaps_no_longer_touches_appendix_or_thesaurus():
    """The unconditional reporter emits nothing now -- pictures are reproduced
    by the 029 seam and appendix/thesaurus by their own 030 resolvers."""
    sense = _FakeSourceSense(
        "sense-x", appendixes=[_FakeAppendix("a")],
        thesaurus_items=[_FakePossItem("t", name="T")])
    dropped: list = []
    categories._report_dropped_sense_scope_gaps(sense, dropped)
    assert dropped == []


# ============================================================================
# Section A -- AppendixesRC link-by-GUID (contracts/appendix-link-by-guid.md)
# ============================================================================

def test_A_link_present_by_guid_no_drop():
    tgt_ap = _FakeAppendix("ap-G")
    target = _FakeTarget(appendixes=[tgt_ap])
    sense = _FakeSourceSense("s", appendixes=[_FakeAppendix("ap-G")])
    new_sense = _FakeTargetSense()
    dropped: list = []
    categories._resolve_sense_appendixes(sense, new_sense, target, dropped)
    assert dropped == []
    assert list(new_sense.AppendixesRC) == [tgt_ap]  # linked the target's own


def test_A_absent_drops_and_never_creates():
    target = _FakeTarget(appendixes=[])  # target owns no appendix
    sense = _FakeSourceSense("s", appendixes=[_FakeAppendix("ap-G")])
    new_sense = _FakeTargetSense()
    dropped: list = []
    categories._resolve_sense_appendixes(sense, new_sense, target, dropped)
    assert len(dropped) == 1
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.field_name == "AppendixesRC"
    assert rec.item_guid == "ap-g"
    assert "not created" in rec.reason
    assert len(new_sense.AppendixesRC) == 0  # nothing linked
    assert target.appendixes == []           # nothing created


def test_A_partial_links_present_drops_absent():
    tgt_ap = _FakeAppendix("ap-1")
    target = _FakeTarget(appendixes=[tgt_ap])
    sense = _FakeSourceSense(
        "s", appendixes=[_FakeAppendix("ap-1"), _FakeAppendix("ap-2")])
    new_sense = _FakeTargetSense()
    dropped: list = []
    categories._resolve_sense_appendixes(sense, new_sense, target, dropped)
    assert list(new_sense.AppendixesRC) == [tgt_ap]
    assert [r.item_guid for r in dropped] == ["ap-2"]


def test_A_empty_source_no_write_no_drop():
    target = _FakeTarget(appendixes=[_FakeAppendix("ap-G")])
    sense = _FakeSourceSense("s", appendixes=[])
    new_sense = _FakeTargetSense()
    dropped: list = []
    categories._resolve_sense_appendixes(sense, new_sense, target, dropped)
    assert dropped == []
    assert len(new_sense.AppendixesRC) == 0


def test_A_shared_appendix_linked_once_per_sense_no_dup():
    tgt_ap = _FakeAppendix("ap-G")
    target = _FakeTarget(appendixes=[tgt_ap])
    sense = _FakeSourceSense(
        "s", appendixes=[_FakeAppendix("ap-G"), _FakeAppendix("ap-G")])
    new_sense = _FakeTargetSense()
    dropped: list = []
    categories._resolve_sense_appendixes(sense, new_sense, target, dropped)
    # idempotent Add via _collection_already_has -> single member, no dup
    assert list(new_sense.AppendixesRC) == [tgt_ap]
    assert dropped == []


def test_A_preview_new_sense_none_records_same_drops_no_write():
    target = _FakeTarget(appendixes=[])
    sense = _FakeSourceSense("s", appendixes=[_FakeAppendix("ap-G")])
    dropped: list = []
    categories._resolve_sense_appendixes(sense, None, target, dropped)
    assert [r.item_guid for r in dropped] == ["ap-g"]


# ============================================================================
# Section B -- ThesaurusItemsRC dynamic-owner (contracts/thesaurus-dynamic-owner.md)
# ============================================================================

def test_B_discover_owning_list_walks_owner_to_list():
    lst = _FakePossList("list-G", name="MyList")
    item = _FakePossItem("item-1", name="Animal", owner=lst)
    assert references.discover_owning_possibility_list(item) is lst


def test_B_discover_returns_none_when_no_owning_list():
    item = _FakePossItem("orphan", name="Nowhere", owner=None)
    assert references.discover_owning_possibility_list(item) is None


def test_B_mirror_by_name_hit_and_miss():
    src_list = _FakePossList("src", name="Custom Thesaurus", flid=42, owner=object())
    tgt_list = _FakePossList("tgt", name="Custom Thesaurus")
    target_hit = _FakeTarget(possibility_lists=[tgt_list])
    assert references.mirror_possibility_list_to_target(src_list, target_hit) is tgt_list
    target_miss = _FakeTarget(possibility_lists=[_FakePossList("o", name="Other")])
    assert references.mirror_possibility_list_to_target(src_list, target_miss) is None


def test_B_nolist_drops_never_raises():
    item = _FakePossItem("orphan", name="X", owner=None)
    sense = _FakeSourceSense("s", thesaurus_items=[item])
    new_sense = _FakeTargetSense()
    dropped: list = []
    categories._resolve_sense_thesaurus_items(
        sense, new_sense, _FakeTarget(), {}, dropped, tag=None)
    assert len(dropped) == 1
    assert dropped[0].field_name == "ThesaurusItemsRC"
    assert "not found on source" in dropped[0].reason
    assert len(new_sense.ThesaurusItemsRC) == 0


def test_B_nomirror_drops_never_raises():
    src_list = _FakePossList("src", name="Custom", flid=42, owner=object())
    item = _FakePossItem("item-1", name="Animal", owner=src_list)
    sense = _FakeSourceSense("s", thesaurus_items=[item])
    new_sense = _FakeTargetSense()
    target = _FakeTarget(possibility_lists=[])  # no equivalent list
    dropped: list = []
    categories._resolve_sense_thesaurus_items(
        sense, new_sense, target, {}, dropped, tag=None)
    assert len(dropped) == 1
    assert "no equivalent in target" in dropped[0].reason
    assert len(new_sense.ThesaurusItemsRC) == 0


def test_B_link_present_in_mirrored_list():
    # Target's equivalent list already holds an identical item -> LINK (no
    # CREATE, so no LCM factory needed: exercisable in fakes).
    tgt_item = _FakePossItem("item-1", name="Animal")
    tgt_list = _FakePossList("tgt", name="Thes", items=[tgt_item])
    src_list = _FakePossList("src", name="Thes", flid=42, owner=object())
    src_item = _FakePossItem("item-1", name="Animal", owner=src_list)
    sense = _FakeSourceSense("s", thesaurus_items=[src_item])
    new_sense = _FakeTargetSense()
    target = _FakeTarget(possibility_lists=[tgt_list])
    dropped: list = []
    categories._resolve_sense_thesaurus_items(
        sense, new_sense, target, {}, dropped, tag=None)
    assert dropped == []
    assert list(new_sense.ThesaurusItemsRC) == [tgt_item]


def test_B_empty_source_no_write_no_drop():
    sense = _FakeSourceSense("s", thesaurus_items=[])
    new_sense = _FakeTargetSense()
    dropped: list = []
    categories._resolve_sense_thesaurus_items(
        sense, None, _FakeTarget(), {}, dropped, tag=None)
    assert dropped == []


def _install_fake_lcm_for_owner_flid(monkeypatch):
    """Inject a fake `SIL.LCModel` exposing identity-cast `ICmObject`/
    `ICmPossibilityList`/`ILangProject`/`ILexDb` so `_target_list_by_owner_flid`
    (the PRIMARY owner+flid matcher) resolves against fakes instead of a live
    LCM host. Mirrors the `_install_fake_lcm` pattern in
    `tests/unit/test_reference_create_paths.py`. Reverted automatically by
    `monkeypatch` at test teardown -- never leaks into other tests."""

    class _IdentityCast:
        def __new__(cls, obj):
            return obj

    class ICmObject(_IdentityCast):
        pass

    class ICmPossibilityList(_IdentityCast):
        pass

    class ILangProject(_IdentityCast):
        pass

    class ILexDb(_IdentityCast):
        pass

    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.ICmObject = ICmObject
    fake_lcm.ICmPossibilityList = ICmPossibilityList
    fake_lcm.ILangProject = ILangProject
    fake_lcm.ILexDb = ILexDb

    monkeypatch.setitem(
        sys.modules, "SIL", sys.modules.get("SIL") or types.ModuleType("SIL")
    )
    monkeypatch.setitem(sys.modules, "SIL.LCModel", fake_lcm)
    return fake_lcm


class _FakeOwnerFlidLexDb:
    def __init__(self, hvo):
        self.Hvo = hvo


class _FakeOwnerFlidLangProject:
    def __init__(self, lexdb):
        self.LexDbOA = lexdb


class _FakeDomainDataByFlid:
    """Fake `Cache.DomainDataByFlid` -- only `get_ObjectProp` is exercised
    by `_target_list_by_owner_flid`."""

    def __init__(self, table):
        self._table = table  # {(owner_hvo, flid): list_hvo}

    def get_ObjectProp(self, hvo, flid):
        return self._table.get((hvo, flid))


class _FakeObjectRepository:
    def __init__(self, objects):
        self._objects = objects  # {hvo: obj}

    def GetObject(self, hvo):
        return self._objects[hvo]


class _FakeServiceLocator:
    def __init__(self, repo):
        self.ObjectRepository = repo


class _FakeOwnerFlidCache:
    def __init__(self, lang_project, domain_data, service_locator):
        self.LangProject = lang_project
        self.DomainDataByFlid = domain_data
        self.ServiceLocator = service_locator


class _FakeOwnerFlidTarget:
    def __init__(self, cache):
        self.Cache = cache


def test_B_owner_flid_primary_matcher_hit_wins_over_name_fallback(monkeypatch):
    """QC-P1 (cycle-2): the PRIMARY dynamic-owner matcher
    (`_target_list_by_owner_flid`, owner-class + `OwningFlid`) must resolve
    BEFORE the Name fallback. Every other Section B fake sets `owner=object()`
    so only the Name-match path was proven offline -- the authoritative
    owner+flid path was only live-proven. This builds a minimal owner+flid
    duck-typed shape (`ICmObject`/`ILangProject`/`ILexDb` identity-cast,
    `Cache.DomainDataByFlid.get_ObjectProp` + `Cache.ServiceLocator.
    ObjectRepository.GetObject`) so the resolver hits the owner+flid branch.
    The Name-fallback candidate is a DIFFERENT list object (also named
    "Thes") registered on `target.possibility_lists`, so this test FAILS if
    the resolver silently falls through to the Name match instead of the
    owner+flid hit."""
    _install_fake_lcm_for_owner_flid(monkeypatch)

    FLID = 5005
    LEXDB_HVO = 42
    LIST_HVO = 777

    owner_flid_list = _FakePossList("owner-flid-list", name="Thes")
    name_fallback_list = _FakePossList("name-fallback-list", name="Thes")

    lexdb = _FakeOwnerFlidLexDb(LEXDB_HVO)
    lang_project = _FakeOwnerFlidLangProject(lexdb)
    domain_data = _FakeDomainDataByFlid({(LEXDB_HVO, FLID): LIST_HVO})
    service_locator = _FakeServiceLocator(
        _FakeObjectRepository({LIST_HVO: owner_flid_list}))
    cache = _FakeOwnerFlidCache(lang_project, domain_data, service_locator)
    target = _FakeOwnerFlidTarget(cache)
    # The Name-fallback surface is ALSO present, so this test would still
    # find A hit via Name if the owner+flid path were (wrongly) skipped.
    target.possibility_lists = [name_fallback_list]

    src_owner = types.SimpleNamespace(ClassName="LexDb")
    src_list = _FakePossList("src-list", name="Thes", flid=FLID, owner=src_owner)

    result = references.mirror_possibility_list_to_target(src_list, target)

    assert result is owner_flid_list
    assert result is not name_fallback_list


def test_B_shared_item_across_senses_resolves_to_same_target_no_dup():
    # Two senses reference the same item; each resolves (LINKs) to the SAME
    # existing target item with no duplication (G-B6). (The resolver cache
    # short-circuits only the CREATE path, which needs a live LCM factory and
    # is proven in the constructed-fixture live pass, not here.)
    tgt_item = _FakePossItem("item-1", name="Animal")
    tgt_list = _FakePossList("tgt", name="Thes", items=[tgt_item])
    src_list = _FakePossList("src", name="Thes", flid=42, owner=object())
    target = _FakeTarget(possibility_lists=[tgt_list])
    cache: dict = {}
    for sense_guid in ("s1", "s2"):
        src_item = _FakePossItem("item-1", name="Animal", owner=src_list)
        sense = _FakeSourceSense(sense_guid, thesaurus_items=[src_item])
        new_sense = _FakeTargetSense()
        dropped: list = []
        categories._resolve_sense_thesaurus_items(
            sense, new_sense, target, cache, dropped, tag=None)
        assert list(new_sense.ThesaurusItemsRC) == [tgt_item]
        assert dropped == []
    assert len(tgt_list.PossibilitiesOS) == 1  # never duplicated in the list


# ============================================================================
# Move + Preview parity for the promoted fields + PicturesOS
# ============================================================================

def test_move_and_preview_drop_sets_identical_for_sense_scope_gaps():
    """The Move sense loop (new_sense set) and the Preview sense loop
    (new_sense=None) must produce the identical scope-gap drop set. Here every
    field is UNRESOLVABLE (target owns nothing), so both modes drop the two
    030-routed fields (appendix + thesaurus); pictures are reproduced by the
    029 seam (not this reporter), so they are NOT in this drop set. The Move
    writes go nowhere but the drop sets coincide (FR-008)."""
    ap = _FakeAppendix("ap-parity")
    src_list = _FakePossList("src", name="Custom", flid=42, owner=object())
    ti = _FakePossItem("thes-parity", name="Parity", owner=src_list)
    pic = _FakePicture("pic-parity")
    target = _FakeTarget(appendixes=[], possibility_lists=[])

    def _run(new_sense):
        d: list = []
        s = _FakeSourceSense(
            "sense-parity", gloss="w", appendixes=[ap],
            thesaurus_items=[ti], pictures=[pic])
        categories._resolve_sense_appendixes(s, new_sense, target, d)
        categories._resolve_sense_thesaurus_items(
            s, new_sense, target, {}, d, tag=None)
        categories._report_dropped_sense_scope_gaps(s, d)
        return sorted((r.field_name, r.item_guid, r.reason) for r in d)

    move = _run(_FakeTargetSense())
    preview = _run(None)
    assert move == preview
    assert len(move) == 2  # appendix + thesaurus dropped (030); picture
    # is reproduced by the 029 seam, so it is NOT in the scope-gap drop set.
    assert {f for f, _, _ in move} == {
        "AppendixesRC", "ThesaurusItemsRC"}


def test_move_and_preview_parity_for_link_success_thesaurus_item():
    """Verification-parity gap (cycle-2): the Section B Move==Preview parity
    check above only exercises the DROP branch. This covers the LINK-SUCCESS
    branch -- target already owns the matching item (via the Name-mirrored
    list, same B-link fake setup as `test_B_link_present_in_mirrored_list`)
    -- so Move and Preview must agree on the link decision (both produce an
    empty drop set), differing only in that Preview never writes."""
    tgt_item = _FakePossItem("item-1", name="Animal")
    tgt_list = _FakePossList("tgt", name="Thes", items=[tgt_item])
    target = _FakeTarget(possibility_lists=[tgt_list])

    def _run(new_sense):
        src_list = _FakePossList("src", name="Thes", flid=42, owner=object())
        src_item = _FakePossItem("item-1", name="Animal", owner=src_list)
        sense = _FakeSourceSense("s", thesaurus_items=[src_item])
        dropped: list = []
        categories._resolve_sense_thesaurus_items(
            sense, new_sense, target, {}, dropped, tag=None)
        return dropped

    move_target_sense = _FakeTargetSense()
    move_dropped = _run(move_target_sense)
    preview_dropped = _run(None)

    assert move_dropped == preview_dropped == []
    # Move actually links the resolved target item; Preview's non-write is
    # already implicit (new_sense=None never raised above).
    assert list(move_target_sense.ThesaurusItemsRC) == [tgt_item]


# ============================================================================
# Issue #42 -- deferred 030 P2 polish
# ============================================================================

# ---- #42a: `hierarchical` derived from the live list `Depth`, not hardcoded --

class _FakeDepthList(_FakePossList):
    """`_FakePossList` plus the live `CmPossibilityList.Depth` the derivation
    reads (LCM Integer, min 0 / max 127)."""

    def __init__(self, guid, depth, **kw):
        super().__init__(guid, **kw)
        self.Depth = depth


def test_42a_thesaurus_spec_hierarchical_derived_from_depth_flat():
    """`Depth == 1` is FLEx's flat list (liblcm `prf.Depth = 1`) -> the
    synthetic spec must report `hierarchical=False`, not the old hardcoded
    True."""
    spec = references.build_thesaurus_spec(_FakeDepthList("flat", 1))
    assert spec.hierarchical is False
    assert spec.field_name == "ThesaurusItemsRC"


def test_42a_thesaurus_spec_hierarchical_derived_from_depth_tree():
    """`Depth == 127` is FLEx's unbounded tree (liblcm `AnthroListOA.Depth =
    127`) -> hierarchical."""
    assert references.build_thesaurus_spec(
        _FakeDepthList("tree", 127)).hierarchical is True


def test_42a_thesaurus_spec_hierarchical_conservative_when_depth_unknown():
    """`Depth == 0` (seen on real projects for never-set lists), an absent
    `Depth`, and a non-numeric `Depth` all stay hierarchical -- the
    conservative reading AND the value 030 hardcoded, so nothing regresses."""
    assert references.build_thesaurus_spec(
        _FakeDepthList("unset", 0)).hierarchical is True
    assert references.build_thesaurus_spec(
        _FakePossList("no-depth-attr")).hierarchical is True
    assert references.build_thesaurus_spec(
        _FakeDepthList("junk", "not-a-number")).hierarchical is True


def test_42a_derivation_does_not_change_the_create_ancestor_decision():
    """Guard on the reason the hardcode was harmless: `decide_reference`'s
    CREATE-ancestor chain is driven by the live `OwningPossibility` walk, NOT
    by `spec.hierarchical`. A flat-Depth list must therefore still produce the
    same decision as a tree-Depth one for the same item."""
    def _decide(depth):
        tgt_list = _FakeDepthList("tgt", depth, name="Thes", items=[])
        src_item = _FakePossItem("only-item", name="Animal")
        spec = references.build_thesaurus_spec(tgt_list)
        return references.decide_reference(src_item, _FakeTarget(), spec, {})

    flat, tree = _decide(1), _decide(127)
    assert flat.action == tree.action
    assert [_guid_of(a) for a in flat.ancestors_to_create] == \
           [_guid_of(a) for a in tree.ancestors_to_create]


def _guid_of(obj):
    return getattr(obj, "Guid", None)


# ---- #42b: lookup FAILURE is distinguished from genuine target absence ------

class _ExplodingAppendixTarget:
    """Target whose `Cache` access raises a NON-expected exception (stand-in
    for a live COM/LCM failure), so `_iter_target_appendixes` must take the
    record-and-log branch rather than the quiet return."""

    class _Boom(Exception):
        pass

    @property
    def Cache(self):
        raise _ExplodingAppendixTarget._Boom("COM failure reading LexDb")


def test_42b_appendix_lookup_failure_reason_says_unknown_not_absent(
        caplog, monkeypatch):
    """A raising `AppendixesOC` scan must NOT be reported with the
    "no LexAppendix with this GUID in target" text -- that asserts absence the
    code never established. The drop is still emitted (never-silent) and the
    exception is logged with a traceback. (The fake `SIL.LCModel` is installed
    so the scan gets PAST the import and reaches the raising `Cache` -- without
    it the ImportError is the expected/quiet shape instead.)"""
    _install_fake_lcm_for_owner_flid(monkeypatch)
    sense = _FakeSourceSense("s", appendixes=[_FakeAppendix("ap-G")])
    dropped: list = []
    with caplog.at_level("WARNING"):
        categories._resolve_sense_appendixes(
            sense, _FakeTargetSense(), _ExplodingAppendixTarget(), dropped)

    assert len(dropped) == 1                       # never silent
    reason = dropped[0].reason
    assert "UNKNOWN" in reason
    assert "not confirmed absent" in reason
    assert "no LexAppendix with this GUID" not in reason
    assert "COM failure reading LexDb" in reason   # real cause surfaced
    logged = [r for r in caplog.records if "AppendixesOC" in r.getMessage()]
    assert logged and logged[0].exc_info is not None   # traceback attached


def test_42b_appendix_genuine_absence_keeps_the_absent_wording():
    """The ordinary "target simply does not own it" case must keep its original
    reason -- the #42b split must not relabel every drop as UNKNOWN."""
    sense = _FakeSourceSense("s", appendixes=[_FakeAppendix("ap-G")])
    dropped: list = []
    categories._resolve_sense_appendixes(
        sense, _FakeTargetSense(), _FakeTarget(appendixes=[]), dropped)

    assert len(dropped) == 1
    assert "no LexAppendix with this GUID" in dropped[0].reason
    assert "UNKNOWN" not in dropped[0].reason


def test_42b_expected_lookup_shapes_stay_quiet(caplog):
    """A target with no `Cache` at all (AttributeError -- the offline/fake
    shape) is EXPECTED: it must return the absent wording with no warning
    logged, so the new branch does not spam the log for normal unit-test and
    offline usage."""
    sense = _FakeSourceSense("s", appendixes=[_FakeAppendix("ap-G")])
    dropped: list = []
    with caplog.at_level("WARNING"):
        categories._resolve_sense_appendixes(
            sense, _FakeTargetSense(), object(), dropped)

    assert len(dropped) == 1
    assert "no LexAppendix with this GUID" in dropped[0].reason
    assert caplog.records == []


class _ExplodingFlidTarget:
    """Target whose owner+flid lookup raises a non-expected exception."""

    class _Boom(Exception):
        pass

    def __init__(self):
        self.possibility_lists = []   # Name fallback present but finds nothing

    @property
    def Cache(self):
        raise _ExplodingFlidTarget._Boom("COM failure reading DomainDataByFlid")


def test_42b_thesaurus_mirror_failure_reason_says_unknown_not_absent(monkeypatch):
    """Same split on the Section B side: when the owner+flid mirror raises, the
    thesaurus drop reason must not claim the target has no equivalent list."""
    _install_fake_lcm_for_owner_flid(monkeypatch)
    src_list = _FakePossList("src", name="Thes", flid=5005,
                             owner=types.SimpleNamespace(ClassName="LexDb"))
    item = _FakePossItem("t-1", name="Animal", owner=src_list)
    sense = _FakeSourceSense("s", thesaurus_items=[item])
    dropped: list = []

    categories._resolve_sense_thesaurus_items(
        sense, _FakeTargetSense(), _ExplodingFlidTarget(), {}, dropped, tag=None)

    assert len(dropped) == 1
    reason = dropped[0].reason
    assert "UNKNOWN" in reason and "not confirmed absent" in reason
    assert "has no equivalent in target" not in reason
    assert "COM failure reading DomainDataByFlid" in reason


def test_42b_thesaurus_genuine_absence_keeps_the_absent_wording():
    """The plain no-equivalent-list case keeps its original reason."""
    src_list = _FakePossList("src", name="Custom", flid=42, owner=object())
    item = _FakePossItem("t-1", name="Animal", owner=src_list)
    sense = _FakeSourceSense("s", thesaurus_items=[item])
    dropped: list = []

    categories._resolve_sense_thesaurus_items(
        sense, _FakeTargetSense(), _FakeTarget(possibility_lists=[]), {},
        dropped, tag=None)

    assert len(dropped) == 1
    assert "has no equivalent in target" in dropped[0].reason
    assert "UNKNOWN" not in dropped[0].reason


def test_42b_name_fallback_still_wins_after_a_failed_primary_lookup(monkeypatch):
    """A raising owner+flid lookup must not short-circuit the Name fallback --
    a Name hit is a real answer, so there is NO drop at all even though an
    error was recorded along the way."""
    _install_fake_lcm_for_owner_flid(monkeypatch)
    tgt_item = _FakePossItem("t-1", name="Animal")
    tgt_list = _FakePossList("tgt", name="Thes", items=[tgt_item])
    target = _ExplodingFlidTarget()
    target.possibility_lists = [tgt_list]

    src_list = _FakePossList("src", name="Thes", flid=5005,
                             owner=types.SimpleNamespace(ClassName="LexDb"))
    item = _FakePossItem("t-1", name="Animal", owner=src_list)
    sense = _FakeSourceSense("s", thesaurus_items=[item])
    new_sense = _FakeTargetSense()
    dropped: list = []

    categories._resolve_sense_thesaurus_items(
        sense, new_sense, target, {}, dropped, tag=None)

    assert dropped == []
    assert list(new_sense.ThesaurusItemsRC) == [tgt_item]


# ---- #42c: appendix drops carry a human-legible label, not a bare GUID -----

class _FakeStTxtPara:
    def __init__(self, text):
        self.Contents = types.SimpleNamespace(Text=text)


class _FakeLabelledAppendix(_FakeAppendix):
    """`LexAppendix` shape with its ONLY real property, `ContentsOA : IStText`
    (`ParagraphsOS` -> `IStTxtPara.Contents.Text`)."""

    def __init__(self, guid, paragraphs=()):
        super().__init__(guid)
        self.ContentsOA = types.SimpleNamespace(
            ParagraphsOS=[_FakeStTxtPara(t) for t in paragraphs])


def test_42c_appendix_label_from_first_nonempty_paragraph():
    ap = _FakeLabelledAppendix("ap-1", paragraphs=["", "  ", "Appendix A: Loanwords"])
    assert categories._appendix_label(ap) == "Appendix A: Loanwords"


def test_42c_appendix_label_collapses_whitespace_and_truncates():
    long_text = "Verb  paradigms\tfor the  Ejagham noun classes, full listing"
    ap = _FakeLabelledAppendix("ap-2", paragraphs=[long_text + " and more here"])
    label = categories._appendix_label(ap)
    assert "  " not in label and "\t" not in label
    assert label.endswith("...")
    assert len(label) <= categories._APPENDIX_LABEL_MAX + 3
    assert label.startswith("Verb paradigms for the")


def test_42c_appendix_label_empty_when_no_contents():
    """No `ContentsOA`, an empty `ParagraphsOS`, and blank paragraph text all
    fail soft to "" -- the drop still carries the GUID."""
    assert categories._appendix_label(_FakeAppendix("ap-3")) == ""
    assert categories._appendix_label(_FakeLabelledAppendix("ap-4")) == ""
    assert categories._appendix_label(
        _FakeLabelledAppendix("ap-5", paragraphs=["", None])) == ""


def test_42c_appendix_drop_record_carries_the_label():
    """End-to-end: the dropped-item record for an appendix the target does not
    own is no longer identified by GUID alone."""
    sense = _FakeSourceSense(
        "s", appendixes=[_FakeLabelledAppendix("ap-G", paragraphs=["Loanwords"])])
    dropped: list = []
    categories._resolve_sense_appendixes(
        sense, _FakeTargetSense(), _FakeTarget(appendixes=[]), dropped)

    assert len(dropped) == 1
    assert dropped[0].item_name == "Loanwords"
    assert dropped[0].item_guid == "ap-g"
