"""Unit tests for the Part A reversal closure walk (`Lib/reversals.py`).

User Story 1 (T009-T013): `plan_reversals`'s decision-only behavior --
entry discovery/closure scope (R3), the per-writing-system index gate (R4),
the partial-`SensesRS`-member report (R3 / 024 FR-008), the non-destructive
`ReversalForm` alt copy (R6 / 024 FR-007), and `SubentriesOS` recursion
(R6). `apply_reversals` (the Move-mode write path, T016) does not exist yet
at this point in the TDD cycle and is NOT exercised here -- every assertion
below is against `plan_reversals`'s pure decision output
(`ReversalDecision`/`DroppedItemRecord`), matching this repo's established
"decision pass first, write pass second" split (`references.decide_reference`
/`apply_reference`, `owned.plan_owned_object_decisions`/`walk_owned_children`).

Fake style: mirrors `test_owned_object_walk.py`'s `_FakeMultiString`
(handle-keyed `_data` dict, `get_String` only) and `test_reference_resolver.py`'s
GUID-bearing possibility/target-list fakes, plus a minimal writing-system
repo fake (`.WritingSystems.GetAll()` -> `{Id, Handle}` descriptors) matching
`ws_mapping.py`'s own `_enumerate_ws` / `references._project_handle_to_id`
resolver contract.
"""
from __future__ import annotations

from gramtrans.Lib import reversals


# ============================================================================
# Fakes
# ============================================================================

class _FakeTsString:
    def __init__(self, text):
        self.Text = text or None


class _FakeMultiString:
    """Fake ICmMultiString: per-handle text storage (mirrors
    test_owned_object_walk.py's `_FakeMultiString`)."""

    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})

    def get_String(self, ws_handle):
        return _FakeTsString(self._data.get(ws_handle))


class _FakeWS:
    """Fake writing-system descriptor -- `.Id`/`.Handle` per
    `ws_mapping._enumerate_ws` / `references._project_handle_to_id`."""

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
    `.ReversalIndexes.GetAll()` -- used for BOTH source and target in these
    tests (source additionally supplies real indexes; target's index list
    is only consulted by `_find_target_index`, empty in every US1 test
    below since none of them exercise an EXISTING target index)."""

    def __init__(self, ws_list, indexes=()) -> None:
        self.WritingSystems = _FakeWSRepo(ws_list)
        self.ReversalIndexes = _FakeReversalIndexesOps(indexes)


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
    """Minimal plan-time context -- only `_ws_map` is read by
    `plan_reversals` (mirrors `getattr(ctx, "_ws_map", None)` used
    throughout `owned.py`/`categories.py`)."""

    def __init__(self, ws_map: dict | None = None) -> None:
        self._ws_map = dict(ws_map or {})


# ============================================================================
# T009 -- entry discovery / closure scope (R3)
# ============================================================================

def test_entry_discovery_closure_scope():
    """plan_reversals gathers ONLY entries whose SensesRS intersects the
    copied-sense set; an index with no such entries is excluded from the
    plan (R0.1/R3)."""
    sense_copied = _FakeSense("s-copied")
    sense_other = _FakeSense("s-other")
    entry_in_scope = _FakeReversalEntry("e-in", senses=[sense_copied])
    entry_out_of_scope = _FakeReversalEntry("e-out", senses=[sense_other])
    idx_with_scope = _FakeReversalIndex(
        "idx1", "en", entries=[entry_in_scope, entry_out_of_scope])
    idx_without_scope = _FakeReversalIndex(
        "idx2", "fr", entries=[entry_out_of_scope])

    src = _FakeProject(
        ws_list=[_FakeWS("en", 1), _FakeWS("fr", 2)],
        indexes=[idx_with_scope, idx_without_scope],
    )
    target = _FakeProject(ws_list=[_FakeWS("en", 10), _FakeWS("fr", 11)])
    ctx = _FakeCtx()
    dropped = []

    decisions = reversals.plan_reversals(
        {"s-copied"}, src, target, ctx, {}, dropped)

    guids = {d.source_entry_guid for d in decisions}
    assert guids == {"e-in"}
    # idx_without_scope is excluded silently (no qualifying entries) -- this
    # is NOT a WS-mapping failure, so no ReversalIndex-owner_kind drop.
    assert not any(r.owner_kind == "ReversalIndex" for r in dropped)


# ============================================================================
# T010 -- writing-system gate (R4)
# ============================================================================

def test_ws_gate_unmapped_index_dropped():
    """A source index whose WritingSystem cannot be mapped to a target
    analysis WS produces exactly ONE DroppedItemRecord (owner_kind
    'ReversalIndex', reason 'writing system not mapped') and is skipped."""
    sense_copied = _FakeSense("s1")
    entry = _FakeReversalEntry("e1", senses=[sense_copied])
    idx = _FakeReversalIndex("idx1", "koh", entries=[entry])

    src = _FakeProject(ws_list=[_FakeWS("koh", 1)], indexes=[idx])
    target = _FakeProject(ws_list=[_FakeWS("en", 10)])  # "koh" absent
    ctx = _FakeCtx()  # no ws_map entry either -- identity fallback also fails
    dropped = []

    decisions = reversals.plan_reversals(
        {"s1"}, src, target, ctx, {}, dropped)

    assert decisions == []
    ws_drops = [r for r in dropped if r.owner_kind == "ReversalIndex"]
    assert len(ws_drops) == 1
    assert ws_drops[0].reason == "writing system not mapped"


# ============================================================================
# T011 -- partial SensesRS (R3 / 024 FR-008)
# ============================================================================

def test_partial_senses_rs_reports_each_omitted_member():
    """An entry linking both copied and non-copied senses is planned with
    only the copied links; each omitted member yields one DroppedItemRecord
    (owner_kind 'ReversalIndexEntry', reason 'member not in copy set')."""
    sense_copied = _FakeSense("s-copied")
    sense_drop_a = _FakeSense("s-drop-a")
    sense_drop_b = _FakeSense("s-drop-b")
    entry = _FakeReversalEntry(
        "e1", senses=[sense_copied, sense_drop_a, sense_drop_b])
    idx = _FakeReversalIndex("idx1", "en", entries=[entry])

    src = _FakeProject(ws_list=[_FakeWS("en", 1)], indexes=[idx])
    target = _FakeProject(ws_list=[_FakeWS("en", 10)])
    ctx = _FakeCtx()
    dropped = []

    decisions = reversals.plan_reversals(
        {"s-copied"}, src, target, ctx, {}, dropped)

    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.linked_sense_guids == ("s-copied",)

    member_drops = [
        r for r in dropped
        if r.owner_kind == "ReversalIndexEntry" and r.field_name == "SensesRS"
    ]
    assert {r.item_guid for r in member_drops} == {"s-drop-a", "s-drop-b"}
    assert all(r.reason == "member not in copy set" for r in member_drops)
    # Mirrored onto the decision itself.
    assert {r.item_guid for r in decision.dropped_sense_members} == {
        "s-drop-a", "s-drop-b",
    }


# ============================================================================
# T012 -- ReversalForm non-destructive copy (R6 / 024 FR-007)
# ============================================================================

def test_reversal_form_non_destructive_alts():
    """Populated source alternatives are captured per mapped WS; an empty
    source alt is simply ABSENT from `reversal_form_alts`, so a later write
    pass can never blank a populated target alt for that WS (there is
    nothing to write)."""
    sense = _FakeSense("s1")
    # handle 1 = "en" (populated), handle 2 = "fr" (present but empty).
    entry = _FakeReversalEntry(
        "e1", senses=[sense], form_alts={1: "run", 2: ""})
    idx = _FakeReversalIndex("idx1", "en", entries=[entry])

    src = _FakeProject(
        ws_list=[_FakeWS("en", 1), _FakeWS("fr", 2)], indexes=[idx])
    target = _FakeProject(ws_list=[_FakeWS("en", 10), _FakeWS("fr", 11)])
    ctx = _FakeCtx()  # identity mapping: en->en, fr->fr
    dropped = []

    decisions = reversals.plan_reversals(
        {"s1"}, src, target, ctx, {}, dropped)

    assert len(decisions) == 1
    alts = decisions[0].reversal_form_alts
    assert alts == {"en": "run"}
    assert "fr" not in alts


# ============================================================================
# T013 -- SubentriesOS recursion (R6)
# ============================================================================

def test_subentries_recursion_builds_tree():
    """A source entry with nested sub-entries produces a recursive
    ReversalDecision tree; each sub-entry carries its own form and links."""
    sense_top = _FakeSense("s-top")
    sense_sub = _FakeSense("s-sub")
    sub_entry = _FakeReversalEntry(
        "e-sub", senses=[sense_sub], form_alts={1: "running"})
    top_entry = _FakeReversalEntry(
        "e-top", senses=[sense_top], form_alts={1: "run"},
        subentries=[sub_entry])
    idx = _FakeReversalIndex("idx1", "en", entries=[top_entry])

    src = _FakeProject(ws_list=[_FakeWS("en", 1)], indexes=[idx])
    target = _FakeProject(ws_list=[_FakeWS("en", 10)])
    ctx = _FakeCtx()
    dropped = []

    decisions = reversals.plan_reversals(
        {"s-top", "s-sub"}, src, target, ctx, {}, dropped)

    assert len(decisions) == 1
    top_decision = decisions[0]
    assert top_decision.source_entry_guid == "e-top"
    assert top_decision.reversal_form_alts == {"en": "run"}
    assert len(top_decision.sub_entry_decisions) == 1

    sub_decision = top_decision.sub_entry_decisions[0]
    assert sub_decision.source_entry_guid == "e-sub"
    assert sub_decision.reversal_form_alts == {"en": "running"}
    assert sub_decision.linked_sense_guids == ("s-sub",)


# ============================================================================
# _set_reversal_form_alt -- the write branches on the OBJECT, not the process
# ============================================================================
#
# Regression guard for the liveness-test bug class: a helper must not decide
# "live LCM or duck-typed fake?" by asking whether an `SIL.*` import
# succeeds. That describes the PROCESS -- and any run that has imported
# flexicon (pythonnet + the SIL assemblies) makes it succeed for every
# object, fake ones included. These tests force the assemblies to be loaded
# when they can be, which is exactly the condition under which the old code
# reached for `TsStringUtils.MakeString` and wrote a real .NET `ITsString`
# into a pure-Python fake.

def _force_sil_loaded():
    """True once pythonnet + the SIL assemblies are importable in-process.

    Mirrors what `test_013_fill_gaps.py` does to the whole session as a side
    effect of its own import. When the host is absent this returns False and
    the tests below still assert the host-free contract, which the old code
    ALSO got wrong (a silent `except ImportError: return`)."""
    try:
        import flexicon.code.BaseOperations  # noqa: F401
        from SIL.LCModel.Core.Text import TsStringUtils  # noqa: F401
    except Exception:  # noqa: BLE001 -- host-free is a legal state
        return False
    return True


class _FakeLcmShapedMultiString:
    """Duck-typed multistring exposing the LCM-style `set_String` and NOT
    the lowercase `set_string` -- the dominant fake shape in this suite
    (test_013_fill_gaps, test_residue_carriers, test_029_*, and a dozen
    more). This is the shape the old code fell through to the live path
    for."""

    def __init__(self) -> None:
        self.calls: list = []

    def set_String(self, ws, value) -> None:  # noqa: N802 -- mirrors LCM
        self.calls.append((ws, value))


class _FakeEntryWithForm:
    def __init__(self, ms) -> None:
        self.ReversalForm = ms


class _ExplodingTarget:
    """A target whose `WSHandle` raises. A duck-typed write must never
    consult it: reaching the live path at all is the bug."""

    def WSHandle(self, ws_id):  # noqa: N802
        raise AssertionError(
            "live path taken for a duck-typed ReversalForm -- the helper "
            "branched on the process, not the object")


def test_lcm_shaped_fake_gets_plain_text_never_a_dotnet_tsstring():
    """The write lands, keyed by WS id, carrying a plain `str`.

    Two failures at once in the old code when the assemblies were loaded:
    it consulted `target.WSHandle` (here: an assertion) and it built a real
    `ITsString`. `TsStringUtils.MakeString('run', handle)` SUCCEEDS for a
    plain Python string, so nothing raised -- the fake was silently
    poisoned with a .NET object."""
    _force_sil_loaded()
    ms = _FakeLcmShapedMultiString()

    reversals._set_reversal_form_alt(
        _FakeEntryWithForm(ms), _ExplodingTarget(), "en", "run")

    assert ms.calls == [("en", "run")]
    assert type(ms.calls[0][1]) is str


def test_lowercase_fake_setter_still_wins():
    """The Id-keyed `set_string` shape this module's own fakes use keeps
    priority over the LCM-shaped fallback."""
    _force_sil_loaded()

    class _Both:
        def __init__(self):
            self.lower = []
            self.upper = []

        def set_string(self, ws_id, text):
            self.lower.append((ws_id, text))

        def set_String(self, ws, value):  # noqa: N802
            self.upper.append((ws, value))

    ms = _Both()
    reversals._set_reversal_form_alt(
        _FakeEntryWithForm(ms), _ExplodingTarget(), "en", "run")

    assert ms.lower == [("en", "run")]
    assert ms.upper == []


def test_absent_and_unwritable_forms_never_raise():
    """`ReversalForm` absent, or present with no setter at all, stays a
    silent no-op -- the helper's documented "never raises" contract."""
    _force_sil_loaded()

    class _NoForm:
        ReversalForm = None

    class _Inert:
        pass

    reversals._set_reversal_form_alt(_NoForm(), _ExplodingTarget(), "en", "run")
    reversals._set_reversal_form_alt(
        _FakeEntryWithForm(_Inert()), _ExplodingTarget(), "en", "run")
