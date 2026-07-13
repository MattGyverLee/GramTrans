"""Unit tests for reversal-category (`PartOfSpeechRA`) resolution against
the per-index `PartsOfSpeechOA` list (`Lib/reversals.py`).

User Story 2 (T021-T024): target-list binding (the resolver reads the
TARGET REVERSAL INDEX's own `PartsOfSpeechOA`, never `LangProject.
PartsOfSpeechOA`), the CREATE path (custom category absent from the target
index, ancestor chain preserved top-down), the diverged dispositions
(UPDATE for custom, REPORT_DROPPED+LINK-existing for shared/protected), and
the absent-list + shared-cache guarantees (contracts/
reversal-category-resolution.md).

Fake style: mirrors `test_reversal_walk.py`'s `_FakeReversalEntry`/
`_FakeReversalIndex`/`_FakeProject` (US1) plus `test_reference_resolver.py`'s
GUID-bearing possibility/target-list fakes (024) -- both established
patterns this module reuses wholesale rather than reinventing.
"""
from __future__ import annotations

import sys
import types

from gramtrans.Lib import reversals
from gramtrans.Lib.models import (
    ReferenceAction,
    ReferenceDecision,
    ReversalDecision,
)


# ============================================================================
# Fakes (plan-side -- mirrors test_reversal_walk.py + test_reference_resolver.py)
# ============================================================================

WS_EN = 100


class _FakeTsString:
    def __init__(self, text):
        self.Text = text or None


class _FakeMultiString:
    """Fake ICmMultiString: per-handle text storage."""

    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})

    def get_String(self, ws_handle):
        return _FakeTsString(self._data.get(ws_handle))


class _FakePossibility:
    """Duck-typed ICmPossibility: Guid, Owner/OwningPossibility (parent item,
    or None at top level), Name/Abbreviation multistrings, IsProtected --
    the SAME fake shape `test_reference_resolver.py`'s decide_reference
    tests already use."""

    def __init__(self, guid, name="", abbr="", is_protected=False, owner=None):
        self.Guid = guid
        self.guid = guid
        self.Name = _FakeMultiString({WS_EN: name} if name else {})
        self.Abbreviation = _FakeMultiString({WS_EN: abbr} if abbr else {})
        self.IsProtected = is_protected
        self.Owner = owner
        self.OwningPossibility = owner


class _FakeTargetList:
    """Fake ICmPossibilityList: a flat container the resolver searches by
    GUID (`references._find_in_possibility_list` walks `.PossibilitiesOS`)."""

    def __init__(self, items=()) -> None:
        self.PossibilitiesOS = list(items)


class _FakeWS:
    def __init__(self, ws_id: str, handle: int) -> None:
        self.Id = ws_id
        self.Handle = handle


class _FakeWSRepo:
    def __init__(self, ws_list) -> None:
        self._ws_list = list(ws_list)

    def GetAll(self):
        return list(self._ws_list)


class _FakeReversalIndexesOps:
    def __init__(self, indexes=()) -> None:
        self._indexes = list(indexes)

    def GetAll(self):
        return list(self._indexes)


class _FakeProject:
    """Minimal project handle: `.WritingSystems.GetAll()` +
    `.ReversalIndexes.GetAll()` -- used for BOTH source and target, matching
    `test_reversal_walk.py`'s own fake."""

    def __init__(self, ws_list, indexes=()) -> None:
        self.WritingSystems = _FakeWSRepo(ws_list)
        self.ReversalIndexes = _FakeReversalIndexesOps(indexes)


class _PoisonedLangProject:
    """T021 tripwire: `LangProject.PartsOfSpeechOA` must NEVER be read by
    reversal-category resolution -- only the target INDEX's own
    `PartsOfSpeechOA` is the correct target list (research R5). Accessing
    this property at all is itself the test failure."""

    @property
    def PartsOfSpeechOA(self):
        raise AssertionError(
            "LangProject.PartsOfSpeechOA was read by reversal-category "
            "resolution -- it must resolve against the target REVERSAL "
            "INDEX's own PartsOfSpeechOA instead (R5)"
        )


class _PoisonedCache:
    def __init__(self) -> None:
        self.LangProject = _PoisonedLangProject()


class _FakeSense:
    def __init__(self, guid: str) -> None:
        self.Guid = guid
        self.guid = guid


class _FakeReversalEntry:
    def __init__(self, guid, senses=(), form_alts=None, pos=None, subentries=()) -> None:
        self.Guid = guid
        self.guid = guid
        self.SensesRS = list(senses)
        self.ReversalForm = _FakeMultiString(form_alts or {})
        self.PartOfSpeechRA = pos
        self.SubentriesOS = list(subentries)


class _FakeReversalIndex:
    def __init__(self, guid, writing_system, entries=(), pos_list=None) -> None:
        self.Guid = guid
        self.guid = guid
        self.WritingSystem = writing_system
        self.EntriesOC = list(entries)
        self.PartsOfSpeechOA = pos_list


class _FakeCtx:
    def __init__(self, ws_map: dict | None = None) -> None:
        self._ws_map = dict(ws_map or {})


# ============================================================================
# T021 -- target-list binding (R5): resolves against the INDEX's own
# PartsOfSpeechOA, LangProject.PartsOfSpeechOA is never touched
# ============================================================================

def test_target_list_binds_to_index_never_to_lang_project():
    guid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    source_pos = _FakePossibility(guid, name="Noun")
    target_pos = _FakePossibility(guid, name="Noun")  # identical -> LINK
    sense = _FakeSense("s1")
    entry = _FakeReversalEntry("e1", senses=[sense], pos=source_pos)
    src_idx = _FakeReversalIndex("src-idx", "en", entries=[entry])
    tgt_idx = _FakeReversalIndex(
        "tgt-idx", "en", pos_list=_FakeTargetList([target_pos]))

    src = _FakeProject(ws_list=[_FakeWS("en", 1)], indexes=[src_idx])
    target = _FakeProject(ws_list=[_FakeWS("en", 10)], indexes=[tgt_idx])
    target.Cache = _PoisonedCache()  # tripwire -- see class docstring
    ctx = _FakeCtx()
    dropped = []

    decisions = reversals.plan_reversals({"s1"}, src, target, ctx, {}, dropped)

    assert len(decisions) == 1
    pos_decision = decisions[0].pos_decision
    assert pos_decision is not None
    assert pos_decision.action == ReferenceAction.LINK
    assert pos_decision.target_item is target_pos
    assert pos_decision.dropped is None


# ============================================================================
# T022 -- CREATE path: custom category absent from target index, ancestor
# chain top-down, GUIDs preserved
# ============================================================================

def test_create_path_returns_ancestor_chain_top_down_guids_preserved():
    root = _FakePossibility("root-guid", name="Root", owner=None)
    leaf = _FakePossibility("leaf-guid", name="Leaf", owner=root)
    sense = _FakeSense("s1")
    entry = _FakeReversalEntry("e1", senses=[sense], pos=leaf)
    src_idx = _FakeReversalIndex("src-idx", "en", entries=[entry])
    tgt_idx = _FakeReversalIndex("tgt-idx", "en", pos_list=_FakeTargetList([]))

    src = _FakeProject(ws_list=[_FakeWS("en", 1)], indexes=[src_idx])
    target = _FakeProject(ws_list=[_FakeWS("en", 10)], indexes=[tgt_idx])
    ctx = _FakeCtx()
    dropped = []

    decisions = reversals.plan_reversals({"s1"}, src, target, ctx, {}, dropped)

    assert len(decisions) == 1
    pos_decision = decisions[0].pos_decision
    assert pos_decision.action == ReferenceAction.CREATE
    assert pos_decision.ancestors_to_create == (root, leaf)
    assert pos_decision.dropped is None


# ============================================================================
# T023 -- diverged dispositions: UPDATE (custom) vs REPORT_DROPPED+LINK
# (shared/protected)
# ============================================================================

def test_diverged_custom_returns_update_non_destructive():
    guid = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    source_pos = _FakePossibility(guid, name="Verb", is_protected=False)
    target_pos = _FakePossibility(guid, name="Verbe", is_protected=False)
    sense = _FakeSense("s1")
    entry = _FakeReversalEntry("e1", senses=[sense], pos=source_pos)
    src_idx = _FakeReversalIndex("src-idx", "en", entries=[entry])
    tgt_idx = _FakeReversalIndex(
        "tgt-idx", "en", pos_list=_FakeTargetList([target_pos]))

    src = _FakeProject(ws_list=[_FakeWS("en", 1)], indexes=[src_idx])
    target = _FakeProject(ws_list=[_FakeWS("en", 10)], indexes=[tgt_idx])
    ctx = _FakeCtx()
    dropped = []

    decisions = reversals.plan_reversals({"s1"}, src, target, ctx, {}, dropped)

    pos_decision = decisions[0].pos_decision
    assert pos_decision.action == ReferenceAction.UPDATE
    assert pos_decision.target_item is target_pos
    assert pos_decision.dropped is None
    assert not any(r.field_name == "PartOfSpeechRA" for r in dropped)


def test_diverged_protected_reports_dropped_and_links_existing():
    guid = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    source_pos = _FakePossibility(guid, name="Verb", is_protected=True)
    target_pos = _FakePossibility(guid, name="Verbe", is_protected=True)
    sense = _FakeSense("s1")
    entry = _FakeReversalEntry("e1", senses=[sense], pos=source_pos)
    src_idx = _FakeReversalIndex("src-idx", "en", entries=[entry])
    tgt_idx = _FakeReversalIndex(
        "tgt-idx", "en", pos_list=_FakeTargetList([target_pos]))

    src = _FakeProject(ws_list=[_FakeWS("en", 1)], indexes=[src_idx])
    target = _FakeProject(ws_list=[_FakeWS("en", 10)], indexes=[tgt_idx])
    ctx = _FakeCtx()
    dropped = []

    decisions = reversals.plan_reversals({"s1"}, src, target, ctx, {}, dropped)

    pos_decision = decisions[0].pos_decision
    assert pos_decision.action == ReferenceAction.REPORT_DROPPED
    assert pos_decision.target_item is target_pos  # LINK existing

    pos_drops = [r for r in dropped if r.field_name == "PartOfSpeechRA"]
    assert len(pos_drops) == 1
    assert pos_drops[0].owner_kind == "ReversalIndexEntry"
    assert pos_drops[0].owner_guid == "e1"
    assert pos_drops[0].item_guid == guid
    assert pos_drops[0].reason  # non-empty


# ============================================================================
# T024 -- absent-list + caching
# ============================================================================

def test_absent_category_list_on_existing_index_reports_dropped():
    guid = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    source_pos = _FakePossibility(guid, name="Adj")
    sense = _FakeSense("s1")
    entry = _FakeReversalEntry("e1", senses=[sense], pos=source_pos)
    src_idx = _FakeReversalIndex("src-idx", "en", entries=[entry])
    tgt_idx = _FakeReversalIndex("tgt-idx", "en", pos_list=None)  # list absent

    src = _FakeProject(ws_list=[_FakeWS("en", 1)], indexes=[src_idx])
    target = _FakeProject(ws_list=[_FakeWS("en", 10)], indexes=[tgt_idx])
    ctx = _FakeCtx()
    dropped = []

    decisions = reversals.plan_reversals({"s1"}, src, target, ctx, {}, dropped)

    pos_decision = decisions[0].pos_decision
    assert pos_decision.action == ReferenceAction.REPORT_DROPPED
    assert pos_decision.target_item is None

    pos_drops = [r for r in dropped if r.field_name == "PartOfSpeechRA"]
    assert len(pos_drops) == 1
    assert pos_drops[0].owner_kind == "ReversalIndexEntry"
    assert pos_drops[0].owner_guid == "e1"
    assert pos_drops[0].reason == "target reversal category list absent"


def test_absent_category_list_when_target_index_not_yet_created():
    """Index absent entirely (to-create WS, no matching target index yet)
    -- `target_index_ref` is `None`, and `spec.target_list_path(None)`
    would raise `AttributeError` if it were ever called; the guard must
    intercept this BEFORE calling `decide_reference` at all."""
    guid = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    source_pos = _FakePossibility(guid, name="Adj")
    sense = _FakeSense("s1")
    entry = _FakeReversalEntry("e1", senses=[sense], pos=source_pos)
    src_idx = _FakeReversalIndex("src-idx", "en", entries=[entry])

    src = _FakeProject(ws_list=[_FakeWS("en", 1)], indexes=[src_idx])
    target = _FakeProject(ws_list=[_FakeWS("en", 10)])  # no matching index
    ctx = _FakeCtx()
    dropped = []

    decisions = reversals.plan_reversals({"s1"}, src, target, ctx, {}, dropped)

    assert len(decisions) == 1
    assert decisions[0].target_index_ref is None
    pos_decision = decisions[0].pos_decision
    assert pos_decision.action == ReferenceAction.REPORT_DROPPED
    assert pos_decision.target_item is None

    pos_drops = [r for r in dropped if r.field_name == "PartOfSpeechRA"]
    assert len(pos_drops) == 1
    assert pos_drops[0].reason == "target reversal category list absent"


# ============================================================================
# T024 (cont.) -- shared resolver_cache: a category used by K entries is
# CREATEd at most once (apply-side; mirrors test_reference_create_paths.py's
# SIL.LCModel/System monkeypatch pattern for apply_reference's CREATE arm)
# ============================================================================

def _install_fake_lcm(monkeypatch) -> types.ModuleType:
    """Inject a fake `SIL.LCModel` + `System` so `apply_reference`'s CREATE
    arm (real `from SIL.LCModel import ...` / `from System import Guid`
    local imports) resolves against fakes instead of a live LCM host.
    Verbatim pattern from `test_reference_create_paths.py`."""

    class _IdentityCast:
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


class _FakeApplyCollection:
    def __init__(self, items=()) -> None:
        self._items = list(items)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def Add(self, item):
        self._items.append(item)


class _FakePosList:
    def __init__(self, item_clsid: int = 7, items=()) -> None:
        self.ItemClsid = item_clsid
        self.PossibilitiesOS = _FakeApplyCollection(items)


class _FakeSourcePos:
    """The shared to-create ancestor -- carries `.ClassName` so
    `residue.apply_residue`'s `class_name is None` branch (which would
    otherwise try a REAL `SIL.LCModel.ICmObject` cast) never fires."""

    def __init__(self, guid: str) -> None:
        self.Guid = guid
        self.guid = guid
        self.ClassName = "CmPossibility"


class _FakeDescMultiString:
    """Carrier-B `Description` fake -- `apply_residue`'s fallback carrier
    for a freshly-CREATEd possibility item (not a Carrier-A class)."""

    def __init__(self) -> None:
        self._data: dict = {}

    def get_String(self, ws):
        return _FakeTsString(self._data.get(ws))

    def set_String(self, ws, text) -> None:
        self._data[ws] = text


class _FakeCreatedPosItem:
    def __init__(self, guid: str) -> None:
        self.Guid = guid
        self.guid = guid
        self.Description = _FakeDescMultiString()


class _FakeApplyFactory:
    def __init__(self) -> None:
        self.create_calls: list = []

    def Create(self, guid):
        self.create_calls.append(str(guid))
        return _FakeCreatedPosItem(str(guid))


class _FakePossibilityListsOps:
    def ApplySyncableProperties(self, item, props, ws_map=None) -> None:
        pass


class _FakeCmCache:
    def __init__(self) -> None:
        self.DefaultAnalWs = 999


class _FakeApplyReversalEntry:
    def __init__(self) -> None:
        self.PartOfSpeechRA = None
        self.ReversalForm = _FakeApplySettableMultiString()
        self.SensesRS = _FakeApplyCollection()


class _FakeApplySettableMultiString:
    def set_string(self, ws_id, text) -> None:
        pass


class _FakeReversalEntriesOps:
    def __init__(self) -> None:
        self.created: list = []

    def Create(self, index, form, sense):
        entry = _FakeApplyReversalEntry()
        self.created.append(entry)
        return entry


class _FakeApplyTarget:
    def __init__(self) -> None:
        self.Cache = _FakeCmCache()
        self.PossibilityLists = _FakePossibilityListsOps()
        self.ReversalEntries = _FakeReversalEntriesOps()
        self.factory = _FakeApplyFactory()
        self.requested_factory_keys: list = []

    def GetFactory(self, key):
        self.requested_factory_keys.append(key)
        return self.factory


class _FakeApplyReversalIndex:
    def __init__(self, pos_list) -> None:
        self.PartsOfSpeechOA = pos_list


def _make_import_residue_tag():
    from gramtrans.Lib.residue import ImportResidueTag
    return ImportResidueTag(
        run_id="GT-20260101-000000",
        source_project_name="Test",
        timestamp="2026-01-01T00:00:00",
    )


def test_shared_reversal_category_created_at_most_once_across_entries(monkeypatch):
    """Contract guarantee: "a reversal category used by K entries is
    created at most once" -- two entries share the SAME to-create
    `PartOfSpeechRA` GUID (absent from the target index's `PartsOfSpeechOA`
    at decide time); applying both against the SAME `resolver_cache` must
    call the factory's `Create` exactly once, and both target entries must
    end up referencing the IDENTICAL created object."""
    _install_fake_lcm(monkeypatch)

    shared_guid = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    shared_pos = _FakeSourcePos(shared_guid)

    pos_list = _FakePosList(item_clsid=7)
    target_index = _FakeApplyReversalIndex(pos_list)
    target = _FakeApplyTarget()

    decision1 = ReversalDecision(
        source_entry_guid="e1",
        target_index_ref=target_index,
        target_ws_id="en",
        pos_decision=ReferenceDecision(
            action=ReferenceAction.CREATE,
            ancestors_to_create=(shared_pos,),
            source_item=shared_pos,
        ),
        reversal_form_alts={"en": "run"},
    )
    decision2 = ReversalDecision(
        source_entry_guid="e2",
        target_index_ref=target_index,
        target_ws_id="en",
        pos_decision=ReferenceDecision(
            action=ReferenceAction.CREATE,
            ancestors_to_create=(shared_pos,),
            source_item=shared_pos,
        ),
        reversal_form_alts={"en": "running"},
    )

    ctx = _FakeCtx()
    resolver_cache: dict = {}
    dropped: list = []
    tag = _make_import_residue_tag()

    reversals.apply_reversals(
        [decision1, decision2], target, ctx, tag, resolver_cache, dropped)

    assert len(target.factory.create_calls) == 1, (
        f"expected the shared category to be CREATEd exactly once, got "
        f"{target.factory.create_calls!r}"
    )
    created_entries = target.ReversalEntries.created
    assert len(created_entries) == 2
    assert created_entries[0].PartOfSpeechRA is not None
    assert created_entries[0].PartOfSpeechRA is created_entries[1].PartOfSpeechRA
