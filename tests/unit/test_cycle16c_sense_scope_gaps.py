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
# PicturesOS -- the sole remaining unconditional DROP_REPORTED scope gap
# ============================================================================

def test_pictures_emit_one_dropped_record_each():
    sense = _FakeSourceSense(
        "sense-pics", pictures=[_FakePicture("pic-1"), _FakePicture("pic-2")])
    dropped: list = []
    categories._report_dropped_sense_scope_gaps(sense, dropped)
    assert {r.item_guid for r in dropped} == {"pic-1", "pic-2"}
    assert all(r.field_name == "PicturesOS" for r in dropped)
    assert all("029-sense-pictures" in r.reason for r in dropped)


def test_report_dropped_sense_scope_gaps_no_longer_touches_appendix_or_thesaurus():
    """The unconditional reporter now covers PicturesOS only -- appendix and
    thesaurus are handled by their own 030 resolvers."""
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
    field is UNRESOLVABLE (target owns nothing), so both modes drop all three;
    the Move writes go nowhere but the drop sets coincide (FR-008)."""
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
    assert len(move) == 3  # appendix + thesaurus + picture all dropped
    assert {f for f, _, _ in move} == {
        "AppendixesRC", "ThesaurusItemsRC", "PicturesOS"}
