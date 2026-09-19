"""Feature 038 T045 -- the EXECUTOR half of owned-collection enrichment.

T040/T041 pinned the PLAN (`tests/unit/test_038_enrichment.py`); T043/T044 made
it honest. This module pins what happens when the plan is executed: the
children actually land in the destination, add-only, GUID preserved, and the
outcome is reported as `disposition=UPDATE` with per-collection counts.

Everything here is HERMETIC -- no FLEx project is opened, no LCM/pythonnet is
imported. The fakes are the same idiom `test_038_enrichment.py` and
`test_017_gold_reserved_edit_copy.py` use, extended with the two things a
WRITE path needs that a read-only planner did not: an owning collection that
can be `.Add()`-ed to, and a service locator that hands out factories.

The four properties under test, each traceable to a rule the task named:

* FR-021 ADD-ONLY. A pre-existing destination child is never removed, never
  reordered, and never written into. The executor's guarantee is structural
  (it only creates and appends), so the tests assert on OBJECT IDENTITY of the
  pre-existing members, not merely on counts.
* SC-008 IDEMPOTENCE. A second run reports every child `already_present`,
  because matching goes through T044's `_match_collection_child` (GUID first,
  then the R1 roster key) rather than blindly appending.
* SC-010 NO FIFTH OUTCOME. Every source child lands in exactly one of `added`
  / `already_present` / `dropped`, and a drop is unconstructible without its
  `DroppedItemRecord` (enforced in `models.EnrichedCollection`).
* THE CAST. All seven collections report `requires_cast: true` live. An uncast
  `getattr` sees nothing and would report the collection empty -- writing
  nothing while claiming success. `test_the_cast_is_what_finds_the_collection`
  is the direct pin for that, modelled on the flexicon 4.5.0 `FeaturesOA`
  failure CLAUDE.md records.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib import categories, transfer
from gramtrans.Lib.models import (
    DroppedItemRecord,
    EnrichedCollection,
    EnrichmentRecord,
    GrammarCategory,
    PlannedOverwrite,
    POS_OWNED_COLLECTION_FIELDS,
)


WS_EN = 100
WS_FR = 101

#: The six collections whose children this pass CREATES. `InflectableFeatsRC`
#: is excluded because it is a REFERENCE collection -- it links an existing
#: target feature and creates nothing (see `_add_reference_collection_member`).
CREATING_FIELDS = tuple(
    f for f in POS_OWNED_COLLECTION_FIELDS if f != "InflectableFeatsRC"
)


# ============================================================================
# Fakes
# ============================================================================

class _FakeTsString:
    def __init__(self, text):
        self.Text = text or None


class _FakeMultiString:
    def __init__(self, data=None):
        self._data = dict(data or {})

    def get_String(self, ws_handle):
        return _FakeTsString(self._data.get(ws_handle))

    def set_String(self, ws_handle, value):
        self._data[ws_handle] = getattr(value, "Text", value)

    def text(self, ws_handle):
        return self._data.get(ws_handle)


class _FakeWsObj:
    def __init__(self, ws_id, handle):
        self.Id = ws_id
        self.Handle = handle


class _FakeWritingSystems:
    def __init__(self, ws_list):
        self._ws = list(ws_list)

    def GetAll(self):
        return list(self._ws)


_WS_LIST = [_FakeWsObj("en", WS_EN), _FakeWsObj("fr", WS_FR)]


class _FakeChild:
    """One owned-collection child. `Name`/`Abbreviation`/`Description` exist on
    every child so the scalar copy has somewhere to land."""

    def __init__(self, guid, name=None, abbr=None, desc=None, class_name=None):
        self.guid = guid
        self.Guid = guid
        self.Name = _FakeMultiString({WS_EN: name} if name else {})
        self.Abbreviation = _FakeMultiString({WS_EN: abbr} if abbr else {})
        self.Description = _FakeMultiString({WS_EN: desc} if desc else {})
        if class_name is not None:
            self.ClassName = class_name

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"<_FakeChild {self.guid}>"


class _FakeOwningCollection:
    """An LCM owning collection/sequence: iterable, with `.Add()` that APPENDS.

    Appending is the whole point -- it is what makes the write order-preserving
    for `AffixTemplatesOS`/`SubPossibilitiesOS` and membership-only for the
    five unordered ones.
    """

    def __init__(self, members=()):
        self._members = list(members)

    def Add(self, obj):
        self._members.append(obj)

    def __iter__(self):
        return iter(self._members)

    def __len__(self):
        return len(self._members)

    def __getitem__(self, index):
        return self._members[index]


class _FakePOS:
    """A POS exposing all seven owned collections directly (already "cast")."""

    def __init__(self, guid, name_en=None, **collections):
        self.guid = guid
        self.Guid = guid
        self.ClassName = "PartOfSpeech"
        self.Name = _FakeMultiString({WS_EN: name_en} if name_en else {})
        self.Abbreviation = _FakeMultiString()
        self.Description = _FakeMultiString()
        unknown = set(collections) - set(POS_OWNED_COLLECTION_FIELDS)
        assert not unknown, f"not a POS owned collection: {sorted(unknown)}"
        for field_name in POS_OWNED_COLLECTION_FIELDS:
            setattr(self, field_name,
                    _FakeOwningCollection(collections.get(field_name, ())))

    def collection(self, field_name):
        return getattr(self, field_name)


class _BareProxy:
    """A base-interface proxy: the seven collections are NOT visible on it.

    This is the live shape `_pos_owned_collection`/`_pos_writable_collection`
    guard against -- pythonnet resolves attributes against the STATIC wrapper
    type, so on a base proxy an uncast read is None. `_concrete` is what a
    successful cast returns.
    """

    def __init__(self, concrete):
        self._concrete = concrete
        self.guid = concrete.guid
        self.Guid = concrete.Guid
        self.ClassName = "PartOfSpeech"


class _FakeFactory:
    """A `Create(guid)` factory. Records every GUID it was handed so a test can
    prove the create was GUID-PRESERVING rather than identity-minting."""

    def __init__(self, name, fail=False):
        self.name = name
        self.fail = fail
        self.created_guids: list = []
        self.bare_creates = 0

    def Create(self, *args):
        if self.fail:
            raise RuntimeError(f"{self.name}: factory refused the create")
        if not args:
            self.bare_creates += 1
            self.created_guids.append(None)
            return _FakeChild("minted-identity")
        guid = args[0]
        self.created_guids.append(guid)
        child = _FakeChild(str(guid))
        if len(args) > 1:            # OWNER_TAKING: the factory attaches it
            owner = args[1]
            getattr(owner, "SubPossibilitiesOS").Add(child)
        return child


class _FakeOps:
    def __init__(self, items=(), props=None):
        self._items = list(items)
        self._props = dict(props or {})
        self.applied: list = []

    def GetAll(self, recursive=True):
        return list(self._items)

    def GetSyncableProperties(self, obj):
        return dict(self._props)

    def ApplySyncableProperties(self, obj, props, ws_map=None, **kwargs):
        self.applied.append((obj, props))
        return len(props)


class _FakeCache:
    DefaultAnalWs = WS_EN


class _FakeProject:
    def __init__(self, pos_items=(), factories=None, objects_by_guid=None,
                 props=None):
        self.POS = _FakeOps(pos_items, props=props)
        self.WritingSystems = _FakeWritingSystems(_WS_LIST)
        self.Cache = _FakeCache()
        self._factories = dict(factories or {})
        self._objects = dict(objects_by_guid or {})
        self.service_requests: list = []

    def GetService(self, name):
        self.service_requests.append(name)
        if name in self._factories:
            return self._factories[name]
        raise KeyError(name)

    def get_object_by_guid(self, guid):
        return self._objects.get(str(guid).lower())


class _Sink:
    def __init__(self):
        self.info: list = []
        self.warning: list = []

    def Info(self, msg):
        self.info.append(msg)

    def Warning(self, msg):
        self.warning.append(msg)

    def all(self):
        return self.info + self.warning


# ============================================================================
# Harness
# ============================================================================

@pytest.fixture(autouse=True)
def _patch_guid(monkeypatch):
    """The fakes carry a plain string `guid`; the production helper reads a
    .NET Guid. Same monkeypatch the 017/T040 tests use."""
    monkeypatch.setattr(categories, "_guid_str_from",
                        lambda o: str(getattr(o, "guid", "") or "").lower())


@pytest.fixture(autouse=True)
def _offline_tsstrings(monkeypatch):
    """Keep the ITsString helpers on their OFFLINE branch.

    `categories._tss_read_text` / `_tss_make_string` are SIL-optional: they use
    the real `ITsString` / `TsStringUtils` when `SIL.LCModel` imports and duck
    types otherwise. That "otherwise" is not stable across a pytest SESSION --
    an earlier, unrelated test can trigger pythonnet's CLR bootstrap, after
    which `SIL.LCModel` is importable process-wide and `ITsString(fake)` raises
    on a duck-typed double. `owned._get_owned_factory`'s docstring records the
    same three-environment hazard for the service locator.

    Pinning the offline branch here makes this module hermetic in the strong
    sense: the same result whether it runs alone or after a CLR-touching file.
    """
    monkeypatch.setattr(categories, "_tss_read_text",
                        lambda tss: getattr(tss, "Text", tss))
    monkeypatch.setattr(categories, "_tss_make_string",
                        lambda text, handle: text)


#: interface name -> the collection it creates children for.
_FACTORY_FOR_FIELD = {
    "AffixSlotsOC": "IMoInflAffixSlotFactory",
    "AffixTemplatesOS": "IMoInflAffixTemplateFactory",
    "SubPossibilitiesOS": "IPartOfSpeechFactory",
    "StemNamesOC": "IMoStemNameFactory",
    "InflectionClassesOC": "IMoInflClassFactory",
    "ReferenceFormsOC": "IFsFeatStrucFactory",
}


def _all_factories(fail=()):
    return {
        name: _FakeFactory(name, fail=(field in fail))
        for field, name in _FACTORY_FOR_FIELD.items()
    }


def _overwrite(src_guid, collections, label="Verb"):
    """A `PlannedOverwrite` shaped exactly as `_plan_gold_reserved_edit`
    produces one: write_mode="merge" carrying a projected `EnrichmentRecord`."""
    return PlannedOverwrite(
        category=GrammarCategory.GRAM_CATEGORIES,
        source_guid=src_guid,
        target_guid=src_guid,
        match_via="guid",
        write_mode="merge",
        summary=f"Merge {src_guid}",
        enrichment=EnrichmentRecord(
            object_class="PartOfSpeech",
            source_guid=src_guid,
            target_guid=src_guid,
            label=label,
            collections=tuple(
                EnrichedCollection(field_name=f, added=n, already_present=0)
                for f, n in collections
            ),
        ),
    )


def _run(src_pos, tgt_pos, collections, *, factories=None,
         objects_by_guid=None, dropped=None, planned_action_guids=frozenset(),
         sink=None):
    """Execute the enrichment for one matched POS pair; return
    `(measured_record, sink, source, target)`."""
    source = _FakeProject([src_pos])
    target = _FakeProject(
        [tgt_pos],
        factories=_all_factories() if factories is None else factories,
        objects_by_guid=objects_by_guid,
    )
    sink = sink if sink is not None else _Sink()
    measured = transfer._enrich_owned_collections(
        _overwrite(src_pos.guid, collections),
        src_pos, tgt_pos, source, target, sink,
        ws_map={}, dropped=dropped,
        planned_action_guids=planned_action_guids,
    )
    return measured, sink, source, target


def _row(measured, field_name) -> EnrichedCollection:
    by_name = {c.canonical_field_name: c for c in measured.collections}
    assert field_name in by_name, (
        f"{field_name} missing from the measured record {sorted(by_name)}"
    )
    return by_name[field_name]


# ============================================================================
# The write actually happens -- for every collection that has a factory
# ============================================================================

@pytest.mark.parametrize("field_name", CREATING_FIELDS)
def test_a_missing_child_is_created_and_counted_added(field_name):
    """The plan said the destination lacks a child; the executor writes it.

    Parametrised over all six creating collections because covering five of
    six leaves a whole collection silently unwritten -- the same shape as the
    G3 defect this feature exists to close.
    """
    child = _FakeChild("child-1", name="Nominal slot")
    src_pos = _FakePOS("pos-1", name_en="Verb", **{field_name: [child]})
    tgt_pos = _FakePOS("pos-1", name_en="Verb")

    measured, _sink, _src, _tgt = _run(src_pos, tgt_pos, [(field_name, 1)])

    row = _row(measured, field_name)
    assert (row.added, row.already_present, row.dropped) == (1, 0, 0)
    written = list(tgt_pos.collection(field_name))
    assert len(written) == 1, (
        f"{field_name} was reported added=1 but the destination collection "
        f"holds {len(written)} member(s) -- reporting a write that did not "
        f"happen is the defect, not a rounding error"
    )
    assert categories._guid_str_from(written[0]) == "child-1"


def test_the_created_child_keeps_the_source_guid():
    """GUID-PRESERVING CREATES ONLY (CLAUDE.md).

    A bare `Create()` mints a new identity, so the next run cannot recognise
    the child and SC-008 idempotence is unreachable. The fake factory records
    every argument it was handed; the create must have carried the GUID.
    """
    child = _FakeChild("aaaa-bbbb-cccc", name="Slot")
    src_pos = _FakePOS("pos-1", AffixSlotsOC=[child])
    tgt_pos = _FakePOS("pos-1")
    factories = _all_factories()

    _run(src_pos, tgt_pos, [("AffixSlotsOC", 1)], factories=factories)

    slot_factory = factories["IMoInflAffixSlotFactory"]
    assert slot_factory.created_guids == ["aaaa-bbbb-cccc"]
    assert slot_factory.bare_creates == 0, (
        "a bare Create() regenerates identity -- CLAUDE.md's floor note: a "
        "too-low flexicon makes the guid= kwarg raise, which the _safe/except "
        "wrappers swallow into a generic drop"
    )


def test_the_created_child_gets_its_scalars():
    child = _FakeChild("child-1", name="Agreement", abbr="agr", desc="a slot")
    src_pos = _FakePOS("pos-1", StemNamesOC=[child])
    tgt_pos = _FakePOS("pos-1")

    _run(src_pos, tgt_pos, [("StemNamesOC", 1)])

    new_child = list(tgt_pos.collection("StemNamesOC"))[0]
    assert new_child.Name.text(WS_EN) == "Agreement"
    assert new_child.Abbreviation.text(WS_EN) == "agr"
    assert new_child.Description.text(WS_EN) == "a slot"


# ============================================================================
# FR-021 -- add-only: never remove, never reorder, never overwrite
# ============================================================================

def test_pre_existing_members_keep_their_identity_and_their_order():
    """The non-destructiveness assertion, on object identity rather than count.

    `AffixTemplatesOS` is an ordered SEQUENCE where index is meaning, so this
    checks the three pre-existing templates are still the same objects at the
    same indices and the new one arrived AFTER them.
    """
    keep = [_FakeChild(f"keep-{i}", name=f"T{i}") for i in range(3)]
    src_children = [_FakeChild(f"keep-{i}", name=f"T{i}") for i in range(3)]
    src_children.append(_FakeChild("new-1", name="T-new"))
    src_pos = _FakePOS("pos-1", AffixTemplatesOS=src_children)
    tgt_pos = _FakePOS("pos-1", AffixTemplatesOS=keep)

    measured, sink, _src, _tgt = _run(src_pos, tgt_pos, [("AffixTemplatesOS", 1)])

    after = list(tgt_pos.collection("AffixTemplatesOS"))
    assert after[:3] == keep, (
        "enrichment reordered or replaced pre-existing members; on an ordered "
        "owning sequence the index IS the data (FR-021)"
    )
    assert len(after) == 4
    assert categories._guid_str_from(after[3]) == "new-1"
    row = _row(measured, "AffixTemplatesOS")
    assert (row.added, row.already_present, row.dropped) == (1, 3, 0)
    assert not [w for w in sink.warning if "ADD-ONLY VIOLATED" in w]


def test_a_pre_existing_child_is_never_written_into():
    """`already_present` means LEFT ALONE, not "merged field by field".

    The destination child carries a name that DIFFERS from source. Enrichment
    is add-only: it must not touch it. (Overwriting divergent child fields
    would be a different disposition than the one this path implements.)
    """
    existing = _FakeChild("child-1", name="Destination wording")
    incoming = _FakeChild("child-1", name="Source wording")
    src_pos = _FakePOS("pos-1", InflectionClassesOC=[incoming])
    tgt_pos = _FakePOS("pos-1", InflectionClassesOC=[existing])

    measured, _sink, _src, _tgt = _run(
        src_pos, tgt_pos, [("InflectionClassesOC", 0)])

    assert existing.Name.text(WS_EN) == "Destination wording"
    row = _row(measured, "InflectionClassesOC")
    assert (row.added, row.already_present, row.dropped) == (0, 1, 0)


def test_an_empty_source_collection_never_blanks_a_populated_destination():
    """Principle IV, restated for a collection: an empty source proposes
    nothing. The destination keeps every member it had."""
    keep = [_FakeChild("keep-1"), _FakeChild("keep-2")]
    src_pos = _FakePOS("pos-1")                       # every collection empty
    tgt_pos = _FakePOS("pos-1", StemNamesOC=keep)

    measured, _sink, _src, _tgt = _run(src_pos, tgt_pos, [("StemNamesOC", 0)])

    assert list(tgt_pos.collection("StemNamesOC")) == keep
    row = _row(measured, "StemNamesOC")
    assert (row.added, row.already_present, row.dropped) == (0, 0, 0)


def test_check_add_only_reports_a_removal_and_a_reorder():
    """The runtime guard itself. It cannot undo a bad write -- it exists so a
    violation is loud rather than a silently reordered template sequence."""
    a, b = _FakeChild("a"), _FakeChild("b")
    sink = _Sink()
    assert transfer._check_add_only("AffixTemplatesOS", [a, b],
                                    _FakeOwningCollection([a, b, _FakeChild("c")]),
                                    sink, "pos-1") is True
    assert sink.warning == []

    sink = _Sink()
    assert transfer._check_add_only("AffixTemplatesOS", [a, b],
                                    _FakeOwningCollection([a]),
                                    sink, "pos-1") is False
    assert any("never remove" in w for w in sink.warning)

    sink = _Sink()
    assert transfer._check_add_only("AffixTemplatesOS", [a, b],
                                    _FakeOwningCollection([b, a]),
                                    sink, "pos-1") is False
    assert any("never reorder" in w for w in sink.warning)


# ============================================================================
# SC-008 -- idempotence
# ============================================================================

@pytest.mark.parametrize("field_name", CREATING_FIELDS)
def test_a_second_run_reports_already_present_not_added(field_name):
    """SC-008. Run the SAME enrichment twice against the SAME destination.

    Run 2 must find every child by GUID (T044's rule, routed through
    `_match_collection_child`) and add nothing. A second `added` here would
    mean the destination gains a duplicate on every re-run.
    """
    children = [_FakeChild("c-1", name="One"), _FakeChild("c-2", name="Two")]
    src_pos = _FakePOS("pos-1", **{field_name: children})
    tgt_pos = _FakePOS("pos-1")
    factories = _all_factories()

    first, _s1, _src, _tgt = _run(src_pos, tgt_pos, [(field_name, 2)],
                                  factories=factories)
    assert (_row(first, field_name).added,
            _row(first, field_name).already_present) == (2, 0)
    assert len(list(tgt_pos.collection(field_name))) == 2

    second, _s2, _src2, _tgt2 = _run(src_pos, tgt_pos, [(field_name, 2)],
                                     factories=factories)

    row = _row(second, field_name)
    assert (row.added, row.already_present, row.dropped) == (0, 2, 0), (
        "SC-008: a re-run must recognise the children it wrote last time. "
        f"Got added={row.added}, already_present={row.already_present}"
    )
    assert len(list(tgt_pos.collection(field_name))) == 2, (
        "the destination gained duplicates on the second run"
    )


# ============================================================================
# SC-010 -- no fifth outcome: a child that cannot be added is REPORTED
# ============================================================================

def test_a_failed_create_is_reported_never_lost():
    """`EnrichedCollection` refuses `dropped` without a `DroppedItemRecord`, so
    this asserts the executor actually builds one rather than discarding the
    child (which would show up as a quietly smaller source_child_count)."""
    child = _FakeChild("child-1", name="Slot")
    src_pos = _FakePOS("pos-1", AffixSlotsOC=[child])
    tgt_pos = _FakePOS("pos-1")
    dropped: list = []

    measured, sink, _src, _tgt = _run(
        src_pos, tgt_pos, [("AffixSlotsOC", 1)],
        factories=_all_factories(fail=("AffixSlotsOC",)),
        dropped=dropped,
    )

    row = _row(measured, "AffixSlotsOC")
    assert (row.added, row.already_present, row.dropped) == (0, 0, 1)
    assert row.source_child_count == 1, "the child must be accounted for once"
    assert len(row.dropped_records) == 1
    record = row.dropped_records[0]
    assert isinstance(record, DroppedItemRecord)
    assert record.field_name == "AffixSlotsOC"
    assert record.item_guid == "child-1"
    assert record.reason, "a drop with no reason is not a report (SC-010)"
    assert dropped == list(row.dropped_records), (
        "the drop must also reach the run-wide collector so it lands in the "
        "report's dropped-items section"
    )
    assert any("child not added" in w for w in sink.warning)


def test_a_collection_with_no_factory_is_reported_not_silently_skipped():
    """`ReferenceFormsOC` ships with a factory in `POS_OWNED_COLLECTION_SPECS`;
    a collection whose factory the TARGET does not expose still has to be
    reported rather than vanish."""
    child = _FakeChild("child-1")
    src_pos = _FakePOS("pos-1", ReferenceFormsOC=[child])
    tgt_pos = _FakePOS("pos-1")

    measured, _sink, _src, _tgt = _run(
        src_pos, tgt_pos, [("ReferenceFormsOC", 1)], factories={},
    )

    row = _row(measured, "ReferenceFormsOC")
    assert row.dropped == 1
    assert row.dropped_records[0].reason


def test_the_measured_record_is_an_enrichment_never_a_creation():
    """FR-022. `was_created` is unconstructible as True, and the executor must
    not try -- an enriched object existed before the run."""
    src_pos = _FakePOS("pos-1", StemNamesOC=[_FakeChild("c-1")])
    tgt_pos = _FakePOS("pos-1")

    measured, _sink, _src, _tgt = _run(src_pos, tgt_pos, [("StemNamesOC", 1)])

    assert measured.was_created is False
    assert measured.object_class == "PartOfSpeech"
    assert measured.source_guid == "pos-1"


# ============================================================================
# InflectableFeatsRC -- a REFERENCE collection links, it never creates
# ============================================================================

def test_a_reference_collection_links_the_existing_target_feature():
    feature = _FakeChild("feat-1", name="Tense")
    target_feature = _FakeChild("feat-1", name="Tense")
    src_pos = _FakePOS("pos-1", InflectableFeatsRC=[feature])
    tgt_pos = _FakePOS("pos-1")
    factories = _all_factories()

    measured, _sink, _src, _tgt = _run(
        src_pos, tgt_pos, [("InflectableFeatsRC", 1)],
        factories=factories, objects_by_guid={"feat-1": target_feature},
    )

    linked = list(tgt_pos.collection("InflectableFeatsRC"))
    assert linked == [target_feature], (
        "a reference collection must link the object that is already in the "
        "target, never create a second one"
    )
    assert _row(measured, "InflectableFeatsRC").added == 1
    assert all(f.created_guids == [] for f in factories.values()), (
        "no factory may be called for a reference collection"
    )


def test_an_unresolvable_reference_is_dropped_with_a_reason():
    feature = _FakeChild("feat-1", name="Tense")
    src_pos = _FakePOS("pos-1", InflectableFeatsRC=[feature])
    tgt_pos = _FakePOS("pos-1")

    measured, _sink, _src, _tgt = _run(
        src_pos, tgt_pos, [("InflectableFeatsRC", 1)], objects_by_guid={},
    )

    row = _row(measured, "InflectableFeatsRC")
    assert (row.added, row.dropped) == (0, 1)
    assert "absent from the target" in row.dropped_records[0].reason
    assert list(tgt_pos.collection("InflectableFeatsRC")) == []


# ============================================================================
# Deferral -- a child with its own PlannedAction is not double-created
# ============================================================================

def test_a_child_with_its_own_planned_action_is_deferred():
    """Five of the seven collections hold children that are ALSO independently
    enumerated items of another category. The overwrite loop runs BEFORE leaf
    dispatch, so creating here would pre-empt the richer dedicated path (whose
    own `_target_has_guid` guard would then make it a silent no-op).

    Deferred, therefore -- and counted `added`, because the child DOES land
    this run. Counting it `dropped` would report a loss that never happens.
    """
    child = _FakeChild("sub-1", name="Transitive verb")
    src_pos = _FakePOS("pos-1", SubPossibilitiesOS=[child])
    tgt_pos = _FakePOS("pos-1")
    factories = _all_factories()

    measured, sink, _src, _tgt = _run(
        src_pos, tgt_pos, [("SubPossibilitiesOS", 1)],
        factories=factories, planned_action_guids=frozenset({"sub-1"}),
    )

    row = _row(measured, "SubPossibilitiesOS")
    assert (row.added, row.already_present, row.dropped) == (1, 0, 0)
    assert list(tgt_pos.collection("SubPossibilitiesOS")) == [], (
        "the dedicated PlannedAction owns this create; writing it here would "
        "win the race and turn the richer path into a no-op"
    )
    assert factories["IPartOfSpeechFactory"].created_guids == []
    assert any("deferred" in m for m in sink.info)


# ============================================================================
# The cast -- rule 3, the flexicon 4.5.0 trap
# ============================================================================

def test_the_cast_is_what_finds_the_collection(monkeypatch):
    """All seven report `requires_cast: true`. On a base-interface proxy the
    UNCAST read is None, which is indistinguishable from "empty" -- so an
    uncast executor writes nothing and reports success. That is exactly how
    flexicon 4.5.0's `FeaturesOA` wiring was 100% dead while every test passed
    (CLAUDE.md).

    The proxy here hides all seven; only the `IPartOfSpeech` cast exposes them.
    """
    concrete = _FakePOS("pos-1", AffixSlotsOC=[_FakeChild("existing")])
    proxy = _BareProxy(concrete)

    # Uncast: invisible. This is the state that must NEVER be read as "empty".
    assert getattr(proxy, "AffixSlotsOC", None) is None

    monkeypatch.setattr(
        categories, "_cast_lcm",
        lambda obj, iface: (obj._concrete
                            if isinstance(obj, _BareProxy)
                            and iface in ("IPartOfSpeech", "ICmPossibility",
                                          "IMoInflClass")
                            else obj),
    )

    receiver, spelling, live = transfer._pos_writable_collection(
        proxy, "AffixSlotsOC")

    assert live is not None, (
        "the cast-resolution probe failed to reach AffixSlotsOC through the "
        "declared IPartOfSpeech interface -- an uncast miss would be reported "
        "as an empty collection and silently write nothing"
    )
    assert receiver is concrete
    assert spelling == "AffixSlotsOC"
    assert list(live) == list(concrete.collection("AffixSlotsOC"))


@pytest.mark.parametrize("field_name", POS_OWNED_COLLECTION_FIELDS)
def test_every_collection_declares_a_cast(field_name):
    """The cast table is not duplicated in transfer.py -- it is read from
    `categories._POS_OWNED_COLLECTION_CASTS`. This pins that all seven have an
    entry, so no collection silently falls back to the uncast read alone."""
    casts = categories._POS_OWNED_COLLECTION_CASTS
    assert casts.get(field_name), (
        f"{field_name} declares no interface cast; per FLExToolsMCP all seven "
        f"report requires_cast: true"
    )
    assert "IPartOfSpeech" in casts[field_name]


def test_the_writable_accessor_agrees_with_the_planner_accessor():
    """One cast policy, two accessors. The executor's accessor exists only to
    return the LIVE collection instead of a snapshot; it must never disagree
    with the planner's about WHETHER the field is reachable or under WHICH
    spelling, or the plan and the write would see different data."""
    pos = _FakePOS("pos-1", ReferenceFormsOC=[_FakeChild("rf-1")])
    for field_name in POS_OWNED_COLLECTION_FIELDS:
        planner_spelling, planner_children = categories._pos_owned_collection(
            pos, field_name)
        _receiver, exec_spelling, live = transfer._pos_writable_collection(
            pos, field_name)
        assert planner_spelling == exec_spelling
        assert (planner_children is None) == (live is None)
        if live is not None:
            assert list(live) == planner_children


# ============================================================================
# The report line
# ============================================================================

def test_the_outcome_is_reported_as_update_with_per_collection_counts():
    src_pos = _FakePOS(
        "pos-1",
        AffixSlotsOC=[_FakeChild("s-1"), _FakeChild("s-2")],
        StemNamesOC=[_FakeChild("n-1")],
    )
    tgt_pos = _FakePOS("pos-1", StemNamesOC=[_FakeChild("n-1")])

    _measured, sink, _src, _tgt = _run(
        src_pos, tgt_pos, [("AffixSlotsOC", 2), ("StemNamesOC", 0)])

    lines = [m for m in sink.info if "disposition=UPDATE" in m]
    assert len(lines) == 1, f"expected one UPDATE line, got {sink.info}"
    line = lines[0]
    assert "AffixSlotsOC: added=2 already_present=0 dropped=0" in line
    assert "StemNamesOC: added=0 already_present=1 dropped=0" in line
    assert "gram_categories" in line


def test_nothing_is_reported_when_there_is_no_enrichment_to_execute():
    src_pos = _FakePOS("pos-1")
    tgt_pos = _FakePOS("pos-1")
    bare = PlannedOverwrite(
        category=GrammarCategory.GRAM_CATEGORIES,
        source_guid="pos-1", target_guid="pos-1",
        match_via="guid", write_mode="merge", summary="scalars only",
    )
    sink = _Sink()
    assert transfer._enrich_owned_collections(
        bare, src_pos, tgt_pos, _FakeProject(), _FakeProject(), sink) is None
    assert sink.all() == []


# ============================================================================
# End to end through `_execute_update_semantic`
# ============================================================================

def _update_semantic(src_pos, tgt_pos, collections, *, props=None,
                     enrichments=None, dropped=None):
    source = _FakeProject([src_pos], props=props)
    target = _FakeProject([tgt_pos], factories=_all_factories(), props=props)
    sink = _Sink()
    from gramtrans.Lib.residue import ImportResidueTag
    tag = ImportResidueTag(run_id="GT-20260820-000000",
                           source_project_name="Src",
                           timestamp="2026-08-20T00:00:00")
    transfer._execute_update_semantic(
        _overwrite(src_pos.guid, collections),
        source, target, sink, tag, ws_map={},
        dropped=dropped, enrichments=enrichments,
    )
    return sink, target


def test_the_update_skip_exit_still_runs_the_collection_pass():
    """THE STEP-ORDER TEST, and the one that would regenerate defect G3 if it
    failed.

    `compute_disposition` only ever compares GetSyncableProperties, which
    carries none of the seven owned collections. Here the scalars are
    byte-identical -- disposition SKIP -- while the destination is missing a
    whole collection. A `return` on that SKIP would write nothing while the
    plan correctly said UPDATE.
    """
    src_pos = _FakePOS("pos-1", AffixSlotsOC=[_FakeChild("s-1", name="Slot")])
    tgt_pos = _FakePOS("pos-1")
    enrichments: list = []

    sink, _target = _update_semantic(
        src_pos, tgt_pos, [("AffixSlotsOC", 1)],
        props={"Name": "Verb"}, enrichments=enrichments,
    )

    assert any("UPDATE-SKIP" in m for m in sink.info), (
        "precondition: the scalar half must have taken its SKIP exit"
    )
    assert len(list(tgt_pos.collection("AffixSlotsOC"))) == 1, (
        "the scalar SKIP suppressed the owned-collection write -- defect G3 "
        "one layer down"
    )
    assert len(enrichments) == 1
    assert _row(enrichments[0], "AffixSlotsOC").added == 1


def test_the_measured_record_reaches_the_collector():
    src_pos = _FakePOS("pos-1", StemNamesOC=[_FakeChild("n-1", name="Abs")])
    tgt_pos = _FakePOS("pos-1")
    enrichments: list = []
    dropped: list = []

    _sink, _target = _update_semantic(
        src_pos, tgt_pos, [("StemNamesOC", 1)],
        props={"Name": "Verb"}, enrichments=enrichments, dropped=dropped,
    )

    assert [r.source_guid for r in enrichments] == ["pos-1"]
    assert dropped == []
    assert _row(enrichments[0], "StemNamesOC").added == 1


def test_a_non_pos_category_never_enriches():
    """The seven collections are POS-only. A merge overwrite for one of the
    five other categories that share `_plan_gold_reserved_edit` must not be
    routed through the collection pass."""
    src_pos = _FakePOS("pos-1", StemNamesOC=[_FakeChild("n-1")])
    tgt_pos = _FakePOS("pos-1")
    ow = PlannedOverwrite(
        category=GrammarCategory.SEMANTIC_DOMAINS,
        source_guid="pos-1", target_guid="pos-1",
        match_via="guid", write_mode="merge", summary="s",
        enrichment=EnrichmentRecord(
            object_class="CmSemanticDomain", source_guid="pos-1",
            target_guid="pos-1", label="dom",
            collections=(EnrichedCollection(field_name="StemNamesOC", added=1),),
        ),
    )
    sink = _Sink()
    assert transfer._enrich_owned_collections(
        ow, src_pos, tgt_pos, _FakeProject(), _FakeProject(), sink) is None
    assert list(tgt_pos.collection("StemNamesOC")) == []
