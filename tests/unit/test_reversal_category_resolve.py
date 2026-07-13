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
    def __init__(self, ws_map: dict | None = None, copy_set: dict | None = None) -> None:
        self._ws_map = dict(ws_map or {})
        self._copy_set = dict(copy_set or {})


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
        self.SubentriesOS = _FakeApplyCollection()


class _FakeApplySettableMultiString:
    def set_string(self, ws_id, text) -> None:
        pass


class _FakeReversalEntriesOps:
    def __init__(self) -> None:
        self.created: list = []

    def Create(self, index, form, sense):
        entry = _FakeApplyReversalEntry()
        if sense is not None:
            # Mirrors the real `ReversalIndexEntryOperations.Create(index,
            # form, sense)` wrapper: the single `sense` param IS linked onto
            # SensesRS as part of Create (research.md R1) -- without this
            # the fake would silently diverge from live behavior and the
            # top-level single/multi-sense regression assertions below
            # would be meaningless.
            entry.SensesRS.Add(sense)
        self.created.append(entry)
        return entry


class _FakeSubEntryFactory:
    """Fake `IReversalIndexEntryFactory` -- the raw-factory fallback
    `_create_sub_entry` uses (no parent-entry overload on the
    `ReversalIndexEntryOperations` wrapper)."""

    def __init__(self) -> None:
        self.create_calls = 0

    def Create(self):
        self.create_calls += 1
        return _FakeApplyReversalEntry()


class _FakeApplyTarget:
    def __init__(self) -> None:
        self.Cache = _FakeCmCache()
        self.PossibilityLists = _FakePossibilityListsOps()
        self.ReversalEntries = _FakeReversalEntriesOps()
        self.factory = _FakeApplyFactory()
        self.requested_factory_keys: list = []
        self.sub_entry_factory = _FakeSubEntryFactory()
        self.requested_service_keys: list = []

    def GetFactory(self, key):
        self.requested_factory_keys.append(key)
        return self.factory

    def GetService(self, key):
        self.requested_service_keys.append(key)
        return self.sub_entry_factory


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


# ============================================================================
# Hardening (feature 025 cycle-6 remediation): pin source=None
# ============================================================================

def test_decide_reversal_category_pins_source_to_none(monkeypatch):
    """`_decide_reversal_category` MUST call `references.decide_reference`
    with `source=None` -- deliberate (see that function's own
    "*** DEVIATION ***" docstring section): threading a real source
    project reintroduces a spurious-UPDATE bug because the source and
    target sides would then use structurally DIFFERENT fingerprint shapes
    (`references.py:513-528` -- Id-keyed pairs vs. the target index's
    positional fallback), so byte-identical content could never compare
    equal. No test guarded this before; this spies on `references.
    decide_reference` (via `reversals.references`, the module attribute
    `_decide_reversal_category` actually calls through) and fails if a
    future refactor threads a real source project instead of `None`."""
    guid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    source_pos = _FakePossibility(guid, name="Noun")
    target_pos = _FakePossibility(guid, name="Noun")
    sense = _FakeSense("s1")
    entry = _FakeReversalEntry("e1", senses=[sense], pos=source_pos)
    src_idx = _FakeReversalIndex("src-idx", "en", entries=[entry])
    tgt_idx = _FakeReversalIndex(
        "tgt-idx", "en", pos_list=_FakeTargetList([target_pos]))

    src = _FakeProject(ws_list=[_FakeWS("en", 1)], indexes=[src_idx])
    target = _FakeProject(ws_list=[_FakeWS("en", 10)], indexes=[tgt_idx])
    ctx = _FakeCtx()
    dropped: list = []

    real_decide_reference = reversals.references.decide_reference
    observed_sources: list = []

    def _spy_decide_reference(*args, **kwargs):
        observed_sources.append(kwargs.get("source", "MISSING-KWARG"))
        return real_decide_reference(*args, **kwargs)

    monkeypatch.setattr(reversals.references, "decide_reference", _spy_decide_reference)

    decisions = reversals.plan_reversals({"s1"}, src, target, ctx, {}, dropped)

    assert len(observed_sources) == 1, (
        f"expected decide_reference invoked exactly once for the "
        f"PartOfSpeechRA field, got {observed_sources!r}"
    )
    assert observed_sources[0] is None, (
        "_decide_reversal_category must call references.decide_reference "
        f"with source=None; observed source={observed_sources[0]!r}"
    )
    # Sanity: the walk still produced its normal LINK outcome (spy is
    # transparent, not just intercepting).
    assert len(decisions) == 1
    assert decisions[0].pos_decision.action == ReferenceAction.LINK


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


# ============================================================================
# P0 regression (T037 Phase-2 cycle-12 Finding 1, cycle-13 fix): a reversal
# SUB-entry's own linked senses were silently dropped. `_apply_one_entry`
# always slices `remaining_senses = target_senses[1:] if first_sense is not
# None else target_senses` on the assumption the create call already linked
# `first_sense` -- true for `_create_top_level_entry` (`ReversalEntries.
# Create(index, form, sense)` links it), but FALSE for `_create_sub_entry`
# (raw `IReversalIndexEntryFactory.Create()` + `parent.SubentriesOS.Add(...)`
# links NOTHING). A sub-entry with exactly 1 linked sense therefore ended up
# with SensesRS EMPTY (live proof: 9/10 sampled sub-entries had senses=0
# where Preview predicted 1). These tests lock the fix: `_create_sub_entry`
# now also consumes `first_sense` (mirroring the top-level contract) so the
# SAME `remaining_senses` slice is correct for both branches.
# ============================================================================

def test_sub_entry_single_sense_is_linked_not_silently_dropped():
    """THE BUG, Test A: a sub-entry with exactly 1 linked (copied) sense
    must end up with exactly 1 member in SensesRS after apply_reversals.
    Pre-fix this asserted 0 (the sense was silently dropped, no exception,
    no DroppedItemRecord)."""
    target_index = _FakeApplyReversalIndex(_FakePosList())
    target = _FakeApplyTarget()
    sense = _FakeSense("s-sub")

    top_decision = ReversalDecision(
        source_entry_guid="e-top",
        target_index_ref=target_index,
        target_ws_id="en",
        pos_decision=None,
        linked_sense_guids=(),
        reversal_form_alts={"en": "topform"},
        sub_entry_decisions=(
            ReversalDecision(
                source_entry_guid="e-sub",
                target_index_ref=target_index,
                target_ws_id="en",
                pos_decision=None,
                linked_sense_guids=("s-sub",),
                reversal_form_alts={"en": "subform"},
            ),
        ),
    )

    ctx = _FakeCtx(copy_set={"s-sub": sense})
    resolver_cache: dict = {}
    dropped: list = []
    tag = _make_import_residue_tag()

    reversals.apply_reversals([top_decision], target, ctx, tag, resolver_cache, dropped)

    top_entries = target.ReversalEntries.created
    assert len(top_entries) == 1
    sub_entries = list(top_entries[0].SubentriesOS)
    assert len(sub_entries) == 1
    sub_entry = sub_entries[0]
    linked = list(sub_entry.SensesRS)
    assert len(linked) == 1, (
        f"expected the sub-entry's single linked sense to survive "
        f"apply_reversals, got {linked!r} (silently dropped pre-fix)"
    )
    assert linked[0] is sense


def test_sub_entry_multi_sense_links_all_n():
    """Test B: a sub-entry with N>1 linked senses ends with exactly N in
    SensesRS -- guards the `remaining_senses` slice arithmetic for the
    multi-sense sub-entry case (pre-fix this lost exactly the FIRST of the
    N senses, since `_create_sub_entry` never linked it and the slice
    assumed it already was)."""
    target_index = _FakeApplyReversalIndex(_FakePosList())
    target = _FakeApplyTarget()
    sense1 = _FakeSense("s-sub-1")
    sense2 = _FakeSense("s-sub-2")

    top_decision = ReversalDecision(
        source_entry_guid="e-top",
        target_index_ref=target_index,
        target_ws_id="en",
        pos_decision=None,
        linked_sense_guids=(),
        reversal_form_alts={"en": "topform"},
        sub_entry_decisions=(
            ReversalDecision(
                source_entry_guid="e-sub",
                target_index_ref=target_index,
                target_ws_id="en",
                pos_decision=None,
                linked_sense_guids=("s-sub-1", "s-sub-2"),
                reversal_form_alts={"en": "subform"},
            ),
        ),
    )

    ctx = _FakeCtx(copy_set={"s-sub-1": sense1, "s-sub-2": sense2})
    resolver_cache: dict = {}
    dropped: list = []
    tag = _make_import_residue_tag()

    reversals.apply_reversals([top_decision], target, ctx, tag, resolver_cache, dropped)

    sub_entry = list(target.ReversalEntries.created[0].SubentriesOS)[0]
    linked = list(sub_entry.SensesRS)
    assert len(linked) == 2
    assert sense1 in linked and sense2 in linked


def test_sub_entry_zero_sense_stays_zero_and_top_level_unaffected():
    """Test C: a 0-sense sub-entry stays 0 (no spurious link introduced by
    the fix), and top-level entries with 1 and with 2 linked senses still
    end with exactly 1 / 2 -- `_create_top_level_entry`'s existing,
    already-correct contract must not regress."""
    target_index = _FakeApplyReversalIndex(_FakePosList())
    target = _FakeApplyTarget()

    top_decision_zero_sub = ReversalDecision(
        source_entry_guid="e-top-a",
        target_index_ref=target_index,
        target_ws_id="en",
        pos_decision=None,
        linked_sense_guids=(),
        reversal_form_alts={"en": "topform-a"},
        sub_entry_decisions=(
            ReversalDecision(
                source_entry_guid="e-sub-zero",
                target_index_ref=target_index,
                target_ws_id="en",
                pos_decision=None,
                linked_sense_guids=(),
                reversal_form_alts={"en": "subform-zero"},
            ),
        ),
    )

    sense_top1 = _FakeSense("s-top-1")
    top_decision_one = ReversalDecision(
        source_entry_guid="e-top-b",
        target_index_ref=target_index,
        target_ws_id="en",
        pos_decision=None,
        linked_sense_guids=("s-top-1",),
        reversal_form_alts={"en": "topform-b"},
    )

    sense_top2a = _FakeSense("s-top-2a")
    sense_top2b = _FakeSense("s-top-2b")
    top_decision_two = ReversalDecision(
        source_entry_guid="e-top-c",
        target_index_ref=target_index,
        target_ws_id="en",
        pos_decision=None,
        linked_sense_guids=("s-top-2a", "s-top-2b"),
        reversal_form_alts={"en": "topform-c"},
    )

    ctx = _FakeCtx(copy_set={
        "s-top-1": sense_top1,
        "s-top-2a": sense_top2a,
        "s-top-2b": sense_top2b,
    })
    resolver_cache: dict = {}
    dropped: list = []
    tag = _make_import_residue_tag()

    reversals.apply_reversals(
        [top_decision_zero_sub, top_decision_one, top_decision_two],
        target, ctx, tag, resolver_cache, dropped,
    )

    created = target.ReversalEntries.created
    assert len(created) == 3
    entry_zero_sub_parent, entry_one, entry_two = created

    sub_entry_zero = list(entry_zero_sub_parent.SubentriesOS)[0]
    assert len(list(sub_entry_zero.SensesRS)) == 0

    assert len(list(entry_one.SensesRS)) == 1
    assert list(entry_one.SensesRS)[0] is sense_top1

    linked_two = list(entry_two.SensesRS)
    assert len(linked_two) == 2
    assert sense_top2a in linked_two and sense_top2b in linked_two
