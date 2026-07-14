"""Unit tests for feature 027 (Complex Forms & Variants), US2/US3: three-way
entry-type / publication reference resolution (`VariantEntryTypesRS`,
`ComplexEntryTypesRS`, `ShowComplexFormsInRS`), contract C3.

Resolves GitHub #30; unblocks the LexEntryRef leg of #28. Reuses feature 024's
`references.decide_reference`/`apply_reference` three-way disposition
(absent -> create incl. ancestor chain; diverged custom -> update; diverged
shared/GOLD -> link + report; identical -> link). See:
- specs/027-complex-forms-variants/contracts/entryref-reproduction.md (C3)
- specs/027-complex-forms-variants/research.md (Decision 4)

T013-T014 (RED-before-GREEN): these tests exercise C3 through the actual
production integration point, `categories._run_entryref_create_pass` --
authored BEFORE that function resolved entry-type/publication fields at all,
so every populated-type-list assertion here MUST fail first (the target list
stays empty / nothing gets linked) until the T015 GREEN change lands. See the
programmer's cycle-3 report for the confirmed RED-proof line per test.

Live target-list paths (confirmed via a read-only probe against Ejagham Mini,
`scratchpad/probe_c3_lists.py` -- FLExToolsMCP is not exposed to this
session; see the cycle-3 report's deviation note): `LexDbOA.
VariantEntryTypesOA` / `.ComplexEntryTypesOA` (`ICmPossibilityList`,
`ItemClsid=5118` = `LexEntryType`, `Depth=127`), `.PublicationTypesOA`
(`ItemClsid=7` = generic `CmPossibility`, `Depth=1`).
"""
from __future__ import annotations

import sys
import types

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.models import RunContext
from gramtrans.Lib.residue import ImportResidueTag


WS_EN = 100

# C3's CREATE arm calls `residue.apply_residue` on every freshly-created
# entry-type/publication item -- needs a real tag (`.serialize()`), not the
# bare `tag=None` C1-only tests use (C1 itself never touches residue).
_TAG = ImportResidueTag.make(
    run_id="GT-20260713-000000", source_project_name="Src", timestamp="2026-07-13T00:00:00")


# ============================================================================
# Fakes -- multistrings, possibility/type items, lists, LexDb/Cache/target
# ============================================================================

class _FakeTsString:
    def __init__(self, text: str = "") -> None:
        self.Text = text


class _FakeMultiString:
    """Fake ICmMultiString -- `_data` dict fallback (`_multistring_dict`)
    PLUS `get_String`/`set_String` (`residue.apply_carrier_b`'s Description
    write path, exercised by the CREATE arm's `apply_residue` call)."""

    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})

    def get_String(self, ws):
        return _FakeTsString(self._data.get(ws, ""))

    def set_String(self, ws, text) -> None:
        self._data[ws] = text


class _FakeEntryType:
    """Fake `ILexEntryType` possibility item (variant/complex-form type).
    `is_protected` mirrors live `IsProtected` (True for a GOLD/reserved
    item -- `protection._is_protected` reads this attribute verbatim)."""

    def __init__(self, guid: str, name: str = "", is_protected: bool = False) -> None:
        self.Guid = guid
        self.guid = guid
        self.Name = _FakeMultiString({WS_EN: name} if name else {})
        self.Abbreviation = _FakeMultiString()
        self.Description = _FakeMultiString()
        self.IsProtected = is_protected
        self.SubPossibilitiesOS = []
        self.OwningPossibility = None
        self.ClassName = "LexEntryType"


class _FakePublicationType(_FakeEntryType):
    """Fake generic `ICmPossibility` publication-type item (ItemClsid 7)."""

    def __init__(self, guid: str, name: str = "", is_protected: bool = False) -> None:
        super().__init__(guid, name, is_protected)
        self.ClassName = "CmPossibility"


class _FakeRefSeq:
    """Owning/reference sequence stand-in: records Add calls, iterable."""

    def __init__(self, initial=()) -> None:
        self._items = list(initial)

    def Add(self, obj) -> None:
        self._items.append(obj)

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)


class _FakePossibilityList:
    def __init__(self, items=(), item_clsid: int = 5118) -> None:
        self.PossibilitiesOS = _FakeRefSeq(items)
        self.ItemClsid = item_clsid


class _FakeCreatedRef:
    def __init__(self, guid) -> None:
        self.guid = guid
        self.Guid = guid
        self.RefType = None
        self.ComponentLexemesRS = _FakeRefSeq()
        self.PrimaryLexemesRS = _FakeRefSeq()
        self.VariantEntryTypesRS = _FakeRefSeq()
        self.ComplexEntryTypesRS = _FakeRefSeq()
        self.ShowComplexFormsInRS = _FakeRefSeq()


class _FakeEntryRefFactory:
    def Create(self, guid):
        return _FakeCreatedRef(guid)


class _FakeTypeFactory:
    """Fake `ILexEntryTypeFactory`: `Create(guid)` makes a fresh, unowned
    entry-type item; the CREATE arm itself Adds it into the right list."""

    def Create(self, guid):
        return _FakeEntryType(guid)


class _FakePublicationTypeFactory:
    """Fake `ICmPossibilityFactory` for the publication-types list."""

    def Create(self, guid):
        return _FakePublicationType(guid)


class _FakeLexDb:
    def __init__(self, variant_types=(), complex_types=(), publication_types=()) -> None:
        self.VariantEntryTypesOA = _FakePossibilityList(variant_types, item_clsid=5118)
        self.ComplexEntryTypesOA = _FakePossibilityList(complex_types, item_clsid=5118)
        self.PublicationTypesOA = _FakePossibilityList(publication_types, item_clsid=7)


class _FakeLangProject:
    def __init__(self, lexdb: _FakeLexDb) -> None:
        self.LexDbOA = lexdb


class _FakeCache:
    def __init__(self, lexdb: _FakeLexDb) -> None:
        self.LangProject = _FakeLangProject(lexdb)
        self.DefaultAnalWs = WS_EN


class _FakeTargetEntry:
    def __init__(self, guid: str, entry_refs=()) -> None:
        self.guid = guid
        self.EntryRefsOS = _FakeRefSeq(entry_refs)


class _FakeTarget:
    """Target project handle: entry lookup + factory dispatch + a bare
    `PossibilityLists` (WS-resolver best-effort no-op -- absent `.project`
    just makes `_resolve_target_ws_by_id` return `{}`, never raises)."""

    def __init__(self, entries_by_guid, lexdb: _FakeLexDb) -> None:
        self._entries = dict(entries_by_guid)
        self.Cache = _FakeCache(lexdb)
        self.PossibilityLists = object()
        self._ref_factory = _FakeEntryRefFactory()
        self._type_factory = _FakeTypeFactory()
        self._pub_factory = _FakePublicationTypeFactory()

    def get_object_by_guid(self, guid):
        return self._entries.get(guid)

    def GetFactory(self, iface_token):
        # Read the already-installed stub straight from `sys.modules` --
        # NOT a fresh `import SIL.LCModel` statement, which pythonnet's CLR
        # meta-path finder can intercept once the real `flexicon` package
        # has been imported anywhere in the same process (bypassing this
        # offline stub even though `sys.modules["SIL.LCModel"]` still holds
        # it) -- the exact hazard `categories._cast_lcm`'s own docstring
        # documents and works around the same way.
        lcm = sys.modules["SIL.LCModel"]
        if iface_token is lcm.ILexEntryRefFactory:
            return self._ref_factory
        if iface_token is lcm.ILexEntryTypeFactory:
            return self._type_factory
        if iface_token is lcm.ICmPossibilityFactory:
            return self._pub_factory
        raise AssertionError(f"unexpected GetFactory token: {iface_token!r}")


def _make_ctx() -> RunContext:
    return RunContext(
        source_handle=object(),
        source_project_name="Src",
        source_project_path="/src",
        target_handle=object(),
        target_project_name="Tgt",
        target_project_path="/tgt",
        run_id="GT-20260713-000000",
        started_at="2026-07-13T00:00:00",
    )


def _ref_record(ref_guid, ref_type=0, variant_entry_types=(), complex_entry_types=(),
                show_complex_forms_in=()):
    return {
        "ref_guid": ref_guid,
        "ref_type": ref_type,
        "components": [],
        "primaries": [],
        "variant_entry_types": list(variant_entry_types),
        "complex_entry_types": list(complex_entry_types),
        "show_complex_forms_in": list(show_complex_forms_in),
    }


def _ctx_create(entryref_create_bindings) -> RunContext:
    ctx = _make_ctx()
    plan = types.SimpleNamespace(
        entryref_create_bindings={
            k: list(v) for k, v in entryref_create_bindings.items()
        },
        identity_remap={},
    )
    object.__setattr__(ctx, "_run_plan", plan)
    object.__setattr__(ctx, "_dropped", [])
    return ctx


# ============================================================================
# SIL.LCModel / System stubs -- ALL interfaces the C1 create path AND the
# C3 generic resolver's CREATE arm import unconditionally.
# ============================================================================

def _install_module(name, module):
    original = sys.modules.get(name)
    sys.modules[name] = module
    return original


def _restore_module(name, original):
    if original is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = original


@pytest.fixture
def _stub_lcm_full():
    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.ILexEntryRefFactory = lambda raw: raw
    fake_lcm.ICmObjectRepository = object()
    for iface in ("ILexEntry", "ILexEntryRef", "ICmPossibility", "ICmPossibilityList"):
        setattr(fake_lcm, iface, (lambda raw: raw))
    for iface in ("ICmPossibilityFactory", "ICmSemanticDomainFactory",
                  "ICmAnthroItemFactory", "IMoMorphTypeFactory",
                  "ILexEntryTypeFactory"):
        setattr(fake_lcm, iface, (lambda raw: raw))
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    original_lcm = _install_module("SIL.LCModel", fake_lcm)

    fake_system = types.ModuleType("System")
    fake_system.Guid = type(
        "FakeGuid", (), {"Parse": staticmethod(lambda s: s)}
    )
    original_system = _install_module("System", fake_system)

    yield

    _restore_module("SIL.LCModel", original_lcm)
    _restore_module("System", original_system)


# ============================================================================
# T013 -- three-way disposition over VariantEntryTypesRS (RefType==0)
# ============================================================================

def test_absent_variant_type_creates_with_guid_preserved(_stub_lcm_full) -> None:
    """Source variant-type item absent from target -> CREATE incl. ancestor
    chain (single-element here: a top-level item), GUID preserved onto the
    new target item, linked into the ref's VariantEntryTypesRS, 0 drops."""
    entry = _FakeTargetEntry("entry-1")
    lexdb = _FakeLexDb(variant_types=[])  # absent
    target = _FakeTarget({"entry-1": entry}, lexdb)
    src_vtype = _FakeEntryType("src-vtype-1", name="Dialectal Variant")
    ctx = _ctx_create({"entry-1": [_ref_record(
        "ref-1", ref_type=0, variant_entry_types=[src_vtype])]})

    skips = categories._run_entryref_create_pass(ctx, target, tag=_TAG)

    assert skips == []
    assert ctx._dropped == []
    new_ref = list(entry.EntryRefsOS)[0]
    linked = list(new_ref.VariantEntryTypesRS)
    assert len(linked) == 1
    assert linked[0].guid == "src-vtype-1"  # GUID preserved (Principle I)
    # The created item actually landed in the target's own list, not just on
    # the ref -- proves CREATE (not a phantom link to nothing).
    assert len(lexdb.VariantEntryTypesOA.PossibilitiesOS) == 1
    assert list(lexdb.VariantEntryTypesOA.PossibilitiesOS)[0] is linked[0]


def test_diverged_custom_variant_type_updates_and_links_same_object(_stub_lcm_full) -> None:
    """Target already has a matching-GUID, NON-protected (custom) item whose
    Name diverges from source -> UPDATE, then LINK that SAME existing
    object (no duplicate created), 0 drops (UPDATE is not a report path)."""
    entry = _FakeTargetEntry("entry-2")
    existing = _FakeEntryType("vtype-2", name="Old Name", is_protected=False)
    lexdb = _FakeLexDb(variant_types=[existing])
    target = _FakeTarget({"entry-2": entry}, lexdb)
    src_vtype = _FakeEntryType("vtype-2", name="New Name")
    ctx = _ctx_create({"entry-2": [_ref_record(
        "ref-2", ref_type=0, variant_entry_types=[src_vtype])]})

    skips = categories._run_entryref_create_pass(ctx, target, tag=_TAG)

    assert skips == []
    assert ctx._dropped == []
    new_ref = list(entry.EntryRefsOS)[0]
    linked = list(new_ref.VariantEntryTypesRS)
    assert len(linked) == 1
    assert linked[0] is existing  # same object -- linked, not replaced
    # No duplicate: the target list still holds exactly the one pre-existing
    # item (UPDATE never creates a second item for the same GUID).
    assert len(lexdb.VariantEntryTypesOA.PossibilitiesOS) == 1


def test_diverged_shared_gold_variant_type_links_and_reports(_stub_lcm_full) -> None:
    """Target has a matching-GUID, PROTECTED (shared/GOLD) item whose Name
    diverges from source -> LINK the existing item (never auto-mutated) +
    exactly 1 DroppedItemRecord reporting the divergence (FR-003/005)."""
    entry = _FakeTargetEntry("entry-3")
    existing = _FakeEntryType("vtype-gold-3", name="GOLD Name", is_protected=True)
    lexdb = _FakeLexDb(variant_types=[existing])
    target = _FakeTarget({"entry-3": entry}, lexdb)
    src_vtype = _FakeEntryType("vtype-gold-3", name="Divergent Name")
    ctx = _ctx_create({"entry-3": [_ref_record(
        "ref-3", ref_type=0, variant_entry_types=[src_vtype])]})

    skips = categories._run_entryref_create_pass(ctx, target, tag=_TAG)

    assert skips == []
    new_ref = list(entry.EntryRefsOS)[0]
    linked = list(new_ref.VariantEntryTypesRS)
    assert len(linked) == 1
    assert linked[0] is existing  # linked to the existing GOLD item...
    assert existing.Name._data.get(WS_EN) == "GOLD Name"  # ...never overwritten
    assert len(lexdb.VariantEntryTypesOA.PossibilitiesOS) == 1  # no duplicate
    assert len(ctx._dropped) == 1
    rec = ctx._dropped[0]
    assert rec.field_name == "VariantEntryTypesRS"
    assert rec.item_guid == "vtype-gold-3"
    assert "diverged" in rec.reason


def test_identical_variant_type_links_only_no_create_no_report(_stub_lcm_full) -> None:
    """Target already has a matching-GUID item with IDENTICAL Name -> LINK
    only: 0 new items created, 0 drops."""
    entry = _FakeTargetEntry("entry-4")
    existing = _FakeEntryType("vtype-4", name="Same Name", is_protected=False)
    lexdb = _FakeLexDb(variant_types=[existing])
    target = _FakeTarget({"entry-4": entry}, lexdb)
    src_vtype = _FakeEntryType("vtype-4", name="Same Name")
    ctx = _ctx_create({"entry-4": [_ref_record(
        "ref-4", ref_type=0, variant_entry_types=[src_vtype])]})

    skips = categories._run_entryref_create_pass(ctx, target, tag=_TAG)

    assert skips == []
    assert ctx._dropped == []
    new_ref = list(entry.EntryRefsOS)[0]
    linked = list(new_ref.VariantEntryTypesRS)
    assert len(linked) == 1
    assert linked[0] is existing
    assert len(lexdb.VariantEntryTypesOA.PossibilitiesOS) == 1


# ============================================================================
# T017 -- three-way disposition over ComplexEntryTypesRS (RefType==1),
# mirroring T013's VariantEntryTypesRS matrix exactly (absent -> create incl.
# ancestor chain; diverged custom -> update; diverged shared/GOLD -> link +
# report; identical -> link). Parametric parity with the VariantEntryTypesRS
# path: same generic `_apply_reference_fields` dispatch, same 5118
# (`LexEntryType`) factory arm -- only the RefType/target-list/field-name
# differ.
# ============================================================================

def test_absent_complex_type_creates_with_guid_preserved(_stub_lcm_full) -> None:
    """Source complex-type item absent from target -> CREATE incl. ancestor
    chain (single-element here: a top-level item), GUID preserved onto the
    new target item, linked into the ref's ComplexEntryTypesRS, 0 drops."""
    entry = _FakeTargetEntry("entry-c1")
    lexdb = _FakeLexDb(complex_types=[])  # absent
    target = _FakeTarget({"entry-c1": entry}, lexdb)
    src_ctype = _FakeEntryType("src-ctype-1", name="Compound")
    ctx = _ctx_create({"entry-c1": [_ref_record(
        "ref-c1", ref_type=1, complex_entry_types=[src_ctype])]})

    skips = categories._run_entryref_create_pass(ctx, target, tag=_TAG)

    assert skips == []
    assert ctx._dropped == []
    new_ref = list(entry.EntryRefsOS)[0]
    linked = list(new_ref.ComplexEntryTypesRS)
    assert len(linked) == 1
    assert linked[0].guid == "src-ctype-1"  # GUID preserved (Principle I)
    # The created item actually landed in the target's own list, not just on
    # the ref -- proves CREATE (not a phantom link to nothing).
    assert len(lexdb.ComplexEntryTypesOA.PossibilitiesOS) == 1
    assert list(lexdb.ComplexEntryTypesOA.PossibilitiesOS)[0] is linked[0]


def test_diverged_custom_complex_type_updates_and_links_same_object(_stub_lcm_full) -> None:
    """Target already has a matching-GUID, NON-protected (custom) item whose
    Name diverges from source -> UPDATE, then LINK that SAME existing
    object (no duplicate created), 0 drops (UPDATE is not a report path)."""
    entry = _FakeTargetEntry("entry-c2")
    existing = _FakeEntryType("ctype-2", name="Old Name", is_protected=False)
    lexdb = _FakeLexDb(complex_types=[existing])
    target = _FakeTarget({"entry-c2": entry}, lexdb)
    src_ctype = _FakeEntryType("ctype-2", name="New Name")
    ctx = _ctx_create({"entry-c2": [_ref_record(
        "ref-c2", ref_type=1, complex_entry_types=[src_ctype])]})

    skips = categories._run_entryref_create_pass(ctx, target, tag=_TAG)

    assert skips == []
    assert ctx._dropped == []
    new_ref = list(entry.EntryRefsOS)[0]
    linked = list(new_ref.ComplexEntryTypesRS)
    assert len(linked) == 1
    assert linked[0] is existing  # same object -- linked, not replaced
    # No duplicate: the target list still holds exactly the one pre-existing
    # item (UPDATE never creates a second item for the same GUID).
    assert len(lexdb.ComplexEntryTypesOA.PossibilitiesOS) == 1


def test_diverged_shared_gold_complex_type_links_and_reports(_stub_lcm_full) -> None:
    """Target has a matching-GUID, PROTECTED (shared/GOLD) item whose Name
    diverges from source -> LINK the existing item (never auto-mutated) +
    exactly 1 DroppedItemRecord reporting the divergence (FR-003/005)."""
    entry = _FakeTargetEntry("entry-c3")
    existing = _FakeEntryType("ctype-gold-3", name="GOLD Name", is_protected=True)
    lexdb = _FakeLexDb(complex_types=[existing])
    target = _FakeTarget({"entry-c3": entry}, lexdb)
    src_ctype = _FakeEntryType("ctype-gold-3", name="Divergent Name")
    ctx = _ctx_create({"entry-c3": [_ref_record(
        "ref-c3", ref_type=1, complex_entry_types=[src_ctype])]})

    skips = categories._run_entryref_create_pass(ctx, target, tag=_TAG)

    assert skips == []
    new_ref = list(entry.EntryRefsOS)[0]
    linked = list(new_ref.ComplexEntryTypesRS)
    assert len(linked) == 1
    assert linked[0] is existing  # linked to the existing GOLD item...
    assert existing.Name._data.get(WS_EN) == "GOLD Name"  # ...never overwritten
    assert len(lexdb.ComplexEntryTypesOA.PossibilitiesOS) == 1  # no duplicate
    assert len(ctx._dropped) == 1
    rec = ctx._dropped[0]
    assert rec.field_name == "ComplexEntryTypesRS"
    assert rec.item_guid == "ctype-gold-3"
    assert "diverged" in rec.reason


def test_identical_complex_type_links_only_no_create_no_report(_stub_lcm_full) -> None:
    """Target already has a matching-GUID item with IDENTICAL Name -> LINK
    only: 0 new items created, 0 drops."""
    entry = _FakeTargetEntry("entry-c4")
    existing = _FakeEntryType("ctype-4", name="Same Name", is_protected=False)
    lexdb = _FakeLexDb(complex_types=[existing])
    target = _FakeTarget({"entry-c4": entry}, lexdb)
    src_ctype = _FakeEntryType("ctype-4", name="Same Name")
    ctx = _ctx_create({"entry-c4": [_ref_record(
        "ref-c4", ref_type=1, complex_entry_types=[src_ctype])]})

    skips = categories._run_entryref_create_pass(ctx, target, tag=_TAG)

    assert skips == []
    assert ctx._dropped == []
    new_ref = list(entry.EntryRefsOS)[0]
    linked = list(new_ref.ComplexEntryTypesRS)
    assert len(linked) == 1
    assert linked[0] is existing
    assert len(lexdb.ComplexEntryTypesOA.PossibilitiesOS) == 1


# ============================================================================
# RefType routing -- complex-form types + always-on publication types
# ============================================================================

def test_complex_form_ref_resolves_complex_types_not_variant_types(_stub_lcm_full) -> None:
    """RefType==1 -> ComplexEntryTypesRS resolves; VariantEntryTypesRS is
    skipped even when (implausibly) populated on the same record."""
    entry = _FakeTargetEntry("entry-5")
    lexdb = _FakeLexDb(complex_types=[], variant_types=[])
    target = _FakeTarget({"entry-5": entry}, lexdb)
    src_ctype = _FakeEntryType("src-ctype-5", name="Compound")
    src_vtype_should_be_ignored = _FakeEntryType("src-vtype-5", name="Ignored")
    ctx = _ctx_create({"entry-5": [_ref_record(
        "ref-5", ref_type=1,
        complex_entry_types=[src_ctype],
        variant_entry_types=[src_vtype_should_be_ignored],
    )]})

    categories._run_entryref_create_pass(ctx, target, tag=_TAG)

    new_ref = list(entry.EntryRefsOS)[0]
    assert len(list(new_ref.ComplexEntryTypesRS)) == 1
    assert list(new_ref.ComplexEntryTypesRS)[0].guid == "src-ctype-5"
    assert len(list(new_ref.VariantEntryTypesRS)) == 0
    assert len(lexdb.VariantEntryTypesOA.PossibilitiesOS) == 0  # never touched


def test_show_complex_forms_in_always_resolves_regardless_of_ref_type(_stub_lcm_full) -> None:
    """ShowComplexFormsInRS (publication types) resolves for a VARIANT ref
    (RefType==0) too -- "always", not gated on RefType."""
    entry = _FakeTargetEntry("entry-6")
    lexdb = _FakeLexDb(publication_types=[])
    target = _FakeTarget({"entry-6": entry}, lexdb)
    src_pub = _FakePublicationType("src-pub-6", name="Main Dictionary")
    ctx = _ctx_create({"entry-6": [_ref_record(
        "ref-6", ref_type=0, show_complex_forms_in=[src_pub])]})

    categories._run_entryref_create_pass(ctx, target, tag=_TAG)

    new_ref = list(entry.EntryRefsOS)[0]
    linked = list(new_ref.ShowComplexFormsInRS)
    assert len(linked) == 1
    assert linked[0].guid == "src-pub-6"
    assert len(lexdb.PublicationTypesOA.PossibilitiesOS) == 1


# ============================================================================
# T014 -- Principle-I GUID-preserved-at-create (not reassigned); existing
# GOLD item linked never overwritten (the same divergent-GOLD shape as
# above, restated to name the invariant explicitly per the task's own
# wording).
# ============================================================================

def test_gold_reserved_entry_type_guid_remapped_at_creation(_stub_lcm_full) -> None:
    """A GOLD/reserved-flagged source entry-type absent from the target is
    still created with its GUID PRESERVED (not reassigned -- 1:1 via
    factory.Create(parsed_guid), never a fresh random target GUID) --
    Principle I. CREATE does not consult `IsProtected` at all (protection
    only gates an EXISTING diverged target item); this proves the create
    path itself never mints a new identity for a reserved concept."""
    entry = _FakeTargetEntry("entry-7")
    lexdb = _FakeLexDb(variant_types=[])  # absent on target
    target = _FakeTarget({"entry-7": entry}, lexdb)
    src_gold_vtype = _FakeEntryType(
        "gold-vtype-well-known-guid", name="Dialectal Variant", is_protected=True)
    ctx = _ctx_create({"entry-7": [_ref_record(
        "ref-7", ref_type=0, variant_entry_types=[src_gold_vtype])]})

    categories._run_entryref_create_pass(ctx, target, tag=_TAG)

    created = list(lexdb.VariantEntryTypesOA.PossibilitiesOS)
    assert len(created) == 1
    assert created[0].guid == "gold-vtype-well-known-guid"


def test_gold_reserved_existing_target_item_linked_never_overwritten(_stub_lcm_full) -> None:
    """The target ALREADY has the GOLD item (by GUID) -- it must be LINKED
    (reused), never overwritten and never duplicated, even though the
    source's own copy of the same concept has diverged text."""
    entry = _FakeTargetEntry("entry-8")
    existing_gold = _FakeEntryType(
        "gold-vtype-existing", name="Canonical GOLD Name", is_protected=True)
    lexdb = _FakeLexDb(variant_types=[existing_gold])
    target = _FakeTarget({"entry-8": entry}, lexdb)
    src_gold_vtype = _FakeEntryType(
        "gold-vtype-existing", name="Some Other Project's Drifted Name",
        is_protected=True)
    ctx = _ctx_create({"entry-8": [_ref_record(
        "ref-8", ref_type=0, variant_entry_types=[src_gold_vtype])]})

    categories._run_entryref_create_pass(ctx, target, tag=_TAG)

    # Exactly one item on the target list -- the pre-existing GOLD object,
    # not a second copy.
    assert len(lexdb.VariantEntryTypesOA.PossibilitiesOS) == 1
    assert list(lexdb.VariantEntryTypesOA.PossibilitiesOS)[0] is existing_gold
    assert existing_gold.Name._data.get(WS_EN) == "Canonical GOLD Name"
    new_ref = list(entry.EntryRefsOS)[0]
    assert list(new_ref.VariantEntryTypesRS)[0] is existing_gold
