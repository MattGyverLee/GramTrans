"""Unit tests for US2 -- nothing is blanked in the target (feature 024, T018).

Covers:
- FR-006: the object-reference fields collected for transfer but historically
  DROPPED during application (`SenseTypeRA`, `DoNotPublishInRC`,
  `DoNotShowMainEntryInRC`) must actually be carried from a populated source
  onto the target -- an overwrite-style copy must not leave them blank.
- FR-007/SC-002: an empty/unset source reference must NEVER blank an already-
  populated target field. Neither `references.decide_reference` nor
  `references.apply_reference` accept a conflict-mode parameter at all, so
  this non-destructive guarantee is mode-invariant BY CONSTRUCTION -- it holds
  identically whether the surrounding category copy is nominally running
  under ADD_NEW / LINK / UPDATE / OVERWRITE. The tests below exercise the
  resolver directly (`decide_reference`/`apply_reference`, mirroring
  `tests/unit/test_reference_resolver.py`'s fake/stub style) for the
  mode-invariance claim, plus `categories._apply_reference_fields` -- the
  actual Move-mode dispatcher these three fields route through (T016/T019)
  -- to confirm the wiring holds end-to-end, not just at the bare resolver
  function level.

No live project is required anywhere in this file.
"""
from __future__ import annotations

import types

from gramtrans.Lib import categories, references
from gramtrans.Lib.models import (
    ReferenceAction,
    ReferenceCardinality,
    ReferenceFieldSpec,
)

# ============================================================================
# Fakes -- modeled on tests/unit/test_reference_resolver.py's
# _FakeTsString / _FakeMultiString / _FakePossibility / _FakeTargetList
# pattern.
# ============================================================================

WS_EN = 100


class _FakeTsString:
    def __init__(self, text):
        self.Text = text or None


class _FakeMultiString:
    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})

    def get_String(self, ws_handle):
        return _FakeTsString(self._data.get(ws_handle))


class _FakePossibility:
    """Duck-typed ICmPossibility: Guid, Name/Abbreviation, IsProtected,
    Owner/OwningPossibility (top-level -> None)."""

    def __init__(self, guid, name="", is_protected=False):
        self.Guid = guid
        self.guid = guid
        self.Name = _FakeMultiString({WS_EN: name} if name else {})
        self.Abbreviation = _FakeMultiString({})
        self.IsProtected = is_protected
        self.Owner = None
        self.OwningPossibility = None


class _FakeTargetList:
    """Fake ICmPossibilityList: flat GUID-searchable container."""

    def __init__(self, items=()) -> None:
        self.PossibilitiesOS = list(items)


class _FakeCollection:
    """Fake FDO owning/reference collection: `.Add()` + iteration, mirroring
    the real `DoNotPublishInRC`/`DoNotShowMainEntryInRC` surface
    `categories._apply_reference_fields` writes through (`owner_coll.Add(...)`,
    never `.Clear()`)."""

    def __init__(self, items=()) -> None:
        self.items = list(items)

    def Add(self, item) -> None:
        self.items.append(item)

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)


def _atomic_spec(field_name: str, target_list) -> ReferenceFieldSpec:
    return ReferenceFieldSpec(
        owner_class="LexSense",
        field_name=field_name,
        cardinality=ReferenceCardinality.ATOMIC,
        target_list_path=lambda target: target_list,
        hierarchical=False,
    )


def _collection_spec(field_name: str, target_list) -> ReferenceFieldSpec:
    return ReferenceFieldSpec(
        owner_class="LexSense",
        field_name=field_name,
        cardinality=ReferenceCardinality.COLLECTION,
        target_list_path=lambda target: target_list,
        hierarchical=False,
    )


_TARGET = object()  # opaque target handle; unused by the fakes above


# ============================================================================
# FR-006, bare resolver level -- a populated source SenseTypeRA/
# DoNotPublishInRC/DoNotShowMainEntryInRC actually lands on the target,
# rather than being dropped (the historical bug: these three fields were
# never wired at all pre-024, so the field stayed blank regardless of what
# the source held).
# ============================================================================


def test_sense_type_ra_populated_source_lands_on_target_not_blanked():
    """ATOMIC field: source SenseTypeRA resolves (LINK, same-GUID-identical)
    and must be set onto the owner -- never left blank."""
    guid = "aaaaaaaa-0000-0000-0000-aaaaaaaaaaaa"
    source_item = _FakePossibility(guid, name="Idiom")
    target_item = _FakePossibility(guid, name="Idiom")
    spec = _atomic_spec("SenseTypeRA", _FakeTargetList([target_item]))
    new_obj = types.SimpleNamespace(SenseTypeRA=None)

    decision = references.decide_reference(source_item, _TARGET, spec, {})
    assert decision.action == ReferenceAction.LINK

    resolved = references.apply_reference(
        decision, _TARGET, new_obj, spec, {}, tag=None,
    )

    assert resolved is target_item
    assert new_obj.SenseTypeRA is target_item, (
        "FR-006: a populated source SenseTypeRA must land on the target, "
        "not be dropped/left blank"
    )


def test_do_not_publish_in_rc_populated_source_lands_on_target_not_blanked():
    """COLLECTION field: source DoNotPublishInRC member resolves (LINK) and
    must be Added onto the owner's collection -- never left empty."""
    guid = "bbbbbbbb-0000-0000-0000-bbbbbbbbbbbb"
    source_item = _FakePossibility(guid, name="Vernacular")
    target_item = _FakePossibility(guid, name="Vernacular")
    spec = _collection_spec("DoNotPublishInRC", _FakeTargetList([target_item]))

    decision = references.decide_reference(source_item, _TARGET, spec, {})
    assert decision.action == ReferenceAction.LINK

    # COLLECTION fields are applied with owner_obj=None (apply_reference does
    # no setattr for these); the caller (_apply_reference_fields) does the
    # `.Add()` itself -- mirrored here directly.
    resolved = references.apply_reference(
        decision, _TARGET, None, spec, {}, tag=None,
    )
    owner_coll = _FakeCollection()
    if resolved is not None:
        owner_coll.Add(resolved)

    assert list(owner_coll) == [target_item], (
        "FR-006: a populated source DoNotPublishInRC member must land on "
        "the target collection, not be dropped"
    )


def test_do_not_show_main_entry_in_rc_populated_source_lands_on_target_not_blanked():
    guid = "cccccccc-0000-0000-0000-cccccccccccc"
    source_item = _FakePossibility(guid, name="Web")
    target_item = _FakePossibility(guid, name="Web")
    spec = _collection_spec("DoNotShowMainEntryInRC", _FakeTargetList([target_item]))

    decision = references.decide_reference(source_item, _TARGET, spec, {})
    assert decision.action == ReferenceAction.LINK

    resolved = references.apply_reference(
        decision, _TARGET, None, spec, {}, tag=None,
    )
    owner_coll = _FakeCollection()
    if resolved is not None:
        owner_coll.Add(resolved)

    assert list(owner_coll) == [target_item], (
        "FR-006: a populated source DoNotShowMainEntryInRC member must land "
        "on the target collection, not be dropped"
    )


# ============================================================================
# FR-007/SC-002, bare resolver level -- an empty/unset source reference must
# NEVER blank an already-populated target field. `decide_reference`/
# `apply_reference` take no conflict-mode parameter, so this is exercised
# once per cardinality and is mode-invariant by construction: nothing in
# either function's signature or body branches on ADD_NEW/LINK/UPDATE/
# OVERWRITE at all.
# ============================================================================


def test_unset_source_sense_type_ra_never_blanks_populated_target():
    """ATOMIC: source's SenseTypeRA is None (unset) -- decide_reference must
    return None (contract: no-op) and apply_reference must never touch the
    owner's field, leaving its pre-existing populated value untouched,
    regardless of which conflict mode (ADD_NEW/LINK/UPDATE/OVERWRITE) the
    surrounding copy nominally runs under -- neither function consults mode
    at all."""
    existing_target_value = _FakePossibility("existing-guid", name="Already Set")
    new_obj = types.SimpleNamespace(SenseTypeRA=existing_target_value)
    spec = _atomic_spec("SenseTypeRA", _FakeTargetList([]))

    decision = references.decide_reference(None, _TARGET, spec, {})
    assert decision is None, "an unset source item must yield no decision at all"

    resolved = references.apply_reference(
        decision, _TARGET, new_obj, spec, {}, tag=None,
    )

    assert resolved is None
    assert new_obj.SenseTypeRA is existing_target_value, (
        "FR-007: an unset source SenseTypeRA must never blank the target's "
        "existing populated value"
    )


def test_unset_source_do_not_publish_in_rc_never_blanks_populated_target():
    """COLLECTION: source has NO DoNotPublishInRC members at all -- the
    owner's pre-existing populated collection must remain exactly as it was
    (categories._apply_reference_fields never calls `.Clear()`; an empty
    source simply yields zero iterations, zero `.Add()` calls)."""
    existing_member = _FakePossibility("existing-pub-guid", name="Already Set")
    owner_coll = _FakeCollection([existing_member])
    src_obj = types.SimpleNamespace(DoNotPublishInRC=[])  # unset/empty on source

    spec = _collection_spec("DoNotPublishInRC", _FakeTargetList([]))
    items = categories._iter_reference_items(spec, src_obj)
    assert items == [], "an empty source collection must yield zero items to resolve"
    # No items -> _apply_reference_fields's inner loop never runs -> no .Add()
    # calls at all; the pre-existing collection is provably untouched.

    assert list(owner_coll) == [existing_member], (
        "FR-007: an empty source DoNotPublishInRC must never blank the "
        "target's existing populated collection"
    )


# ============================================================================
# T019 wiring confirmation -- categories._apply_reference_fields (the actual
# Move-mode dispatcher) routes SenseTypeRA/DoNotPublishInRC/
# DoNotShowMainEntryInRC through the resolver end-to-end, not just at the
# bare references.py function level. A minimal fake target exposes ONLY the
# two possibility lists these three fields need
# (`Cache.LangProject.LexDbOA.SenseTypesOA` / `.PublicationTypesOA`); every
# other LexSense reference field is excluded via `skip_fields` so the fake
# doesn't need to model AnthroListOA/StatusOA/SemanticDomainListOA/etc.
# ============================================================================

_OTHER_LEXSENSE_FIELDS = frozenset({
    "UsageTypesRC", "DomainTypesRC", "AnthroCodesRC", "DialectLabelsRS",
    "StatusRA", "SemanticDomainsRC", "PublishIn",
})


class _FakeLexDb:
    def __init__(self, sense_types_list, publication_types_list) -> None:
        self.SenseTypesOA = sense_types_list
        self.PublicationTypesOA = publication_types_list


class _FakeLangProject:
    def __init__(self, lex_db) -> None:
        self.LexDbOA = lex_db


class _FakeCache:
    def __init__(self, lang_project) -> None:
        self.LangProject = lang_project


class _FakeTargetProject:
    """Minimal fake target FLExProject: only `.Cache.LangProject.LexDbOA.
    {SenseTypesOA,PublicationTypesOA}` -- the exact accessor path
    `references._lp(target).LexDbOA.SenseTypesOA`/`.PublicationTypesOA`
    reads (see references.py's REFERENCE_FIELD_MAP)."""

    def __init__(self, sense_types_list, publication_types_list) -> None:
        self.Cache = _FakeCache(
            _FakeLangProject(_FakeLexDb(sense_types_list, publication_types_list))
        )


def test_apply_reference_fields_carries_populated_source_end_to_end():
    """FR-006 confirmation at the categories._apply_reference_fields level:
    a populated source SenseTypeRA + DoNotPublishInRC + DoNotShowMainEntryInRC
    all land on a fresh (blank) target sense -- proving the three fields are
    NOT skipped/discarded by the actual Move-mode dispatch."""
    sense_type_guid = "dddddddd-0000-0000-0000-dddddddddddd"
    pub_guid = "eeeeeeee-0000-0000-0000-eeeeeeeeeeee"
    hide_guid = "ffffffff-0000-0000-0000-ffffffffffff"

    src_sense_type = _FakePossibility(sense_type_guid, name="Idiom")
    tgt_sense_type = _FakePossibility(sense_type_guid, name="Idiom")
    src_pub = _FakePossibility(pub_guid, name="Vernacular")
    tgt_pub = _FakePossibility(pub_guid, name="Vernacular")
    src_hide = _FakePossibility(hide_guid, name="Web")
    tgt_hide = _FakePossibility(hide_guid, name="Web")

    target = _FakeTargetProject(
        sense_types_list=_FakeTargetList([tgt_sense_type]),
        publication_types_list=_FakeTargetList([tgt_pub, tgt_hide]),
    )

    src_obj = types.SimpleNamespace(
        SenseTypeRA=src_sense_type,
        DoNotPublishInRC=[src_pub],
        DoNotShowMainEntryInRC=[src_hide],
    )
    new_obj = types.SimpleNamespace(
        SenseTypeRA=None,
        DoNotPublishInRC=_FakeCollection(),
        DoNotShowMainEntryInRC=_FakeCollection(),
    )
    dropped: list = []

    categories._apply_reference_fields(
        "LexSense", src_obj, new_obj, target, None, {}, dropped,
        skip_fields=_OTHER_LEXSENSE_FIELDS,
    )

    assert new_obj.SenseTypeRA is tgt_sense_type, (
        "SenseTypeRA must be carried from a populated source, not dropped"
    )
    assert list(new_obj.DoNotPublishInRC) == [tgt_pub], (
        "DoNotPublishInRC must be carried from a populated source, not dropped"
    )
    assert list(new_obj.DoNotShowMainEntryInRC) == [tgt_hide], (
        "DoNotShowMainEntryInRC must be carried from a populated source, "
        "not dropped"
    )


def test_apply_reference_fields_never_blanks_populated_target_from_empty_source():
    """FR-007/SC-002 confirmation at the categories._apply_reference_fields
    level: an empty/unset source across all three fields must leave an
    already-populated target sense completely unchanged."""
    existing_sense_type = _FakePossibility("existing-st-guid", name="Already Set")
    existing_pub = _FakePossibility("existing-pub-guid", name="Already Set")
    existing_hide = _FakePossibility("existing-hide-guid", name="Already Set")

    target = _FakeTargetProject(
        sense_types_list=_FakeTargetList([]),
        publication_types_list=_FakeTargetList([]),
    )

    src_obj = types.SimpleNamespace(
        SenseTypeRA=None,             # unset on source
        DoNotPublishInRC=[],          # unset/empty on source
        DoNotShowMainEntryInRC=[],    # unset/empty on source
    )
    new_obj = types.SimpleNamespace(
        SenseTypeRA=existing_sense_type,
        DoNotPublishInRC=_FakeCollection([existing_pub]),
        DoNotShowMainEntryInRC=_FakeCollection([existing_hide]),
    )
    dropped: list = []

    categories._apply_reference_fields(
        "LexSense", src_obj, new_obj, target, None, {}, dropped,
        skip_fields=_OTHER_LEXSENSE_FIELDS,
    )

    assert new_obj.SenseTypeRA is existing_sense_type, (
        "FR-007: an unset source SenseTypeRA must never blank the target's "
        "existing populated value"
    )
    assert list(new_obj.DoNotPublishInRC) == [existing_pub], (
        "FR-007: an empty source DoNotPublishInRC must never blank the "
        "target's existing populated collection"
    )
    assert list(new_obj.DoNotShowMainEntryInRC) == [existing_hide], (
        "FR-007: an empty source DoNotShowMainEntryInRC must never blank "
        "the target's existing populated collection"
    )
    assert dropped == [], "no drops expected for this scenario"
