"""Feature 038 T123 acceptance line (a): THE ROOT CAUSE.

`_walk_lex_entry_closure`'s MSA create-and-wire block used to live entirely
inside its `for src_sense in src_entry.SensesOS` loop -- TOP-LEVEL senses
only. A SUBSENSE's own MSA was therefore never created/wired there; it fell
through to `_create_entry_owned_msas_without_sense` (the cycle-8 hardening
backstop), which finds the guid unclaimed and creates it with
`new_sense=None` BY DESIGN. Entry-owned MSA counts still balanced and
nothing was ever reported dropped, because nothing failed -- the subsense's
`MorphoSyntaxAnalysisRA` was just silently left null. Measured live on
`omoona` (Ngoreme), entry e2cd79ef-2ee5-4d56-ae54-9210060bcdae, subsense
'small child' (3081d6f8-...) under 'child' (885182d0-...). See
specs/038-transfer-fidelity-gaps/reviews/cycle12-mainsession-t123a-root-cause.md.

CYCLE 11's PIN WAS INSUFFICIENT (necessary but not sufficient, per Rule 5):
it drove `_create_msa_for_closure` directly -- a path production DOES take
for a top-level sense, but never took for a subsense, because nothing ever
called it for one. A test that is falsifiable against its own commit but
never reaches the code path production takes for the real defect predicts
nothing. This file's tests must therefore prove they exercise the
REACHABILITY question -- "is a subsense's MSA visited at all" -- not just
the create-once-per-guid question cycle 11 already covers.

WHAT THIS FILE DRIVES, and why. `_walk_lex_entry_closure` itself is
LCM-bound end-to-end (unconditional `from SIL.LCModel import
ILexEntryFactory, ILexDb, ILexSenseFactory, ICmObject` at its own top) and
is documented (see `test_038_t123_msa_entry_owned_no_sense_latent.py`,
`test_038_t123_msa_naturalkey_reuse.py`) as exercised only under a live host
/ the integration suite -- no existing unit test calls it directly
(confirmed: `grep -n "_walk_lex_entry_closure(" tests/unit/*.py` returns
nothing outside this closure's own definition). This file instead drives
the EXACT sequence `_walk_lex_entry_closure` now runs at its subsense-wiring
call site, using the real, unmodified functions:

    1. `owned.walk_owned_children(src_sense, new_sense, ctx, tag,
       resolver_cache, dropped)` -- REAL, unmodified. Creates every subsense
       reachable from `src_sense` (recurse=True leg, `owned.OWNED_OBJECT_MAP`)
       and registers each into `ctx._copy_set`. Already proven host-free-
       drivable by `tests/unit/test_subsense_copy_set.py`; the fakes below
       mirror that file's.
    2. `categories._wire_subsense_msas(src_sense, src_entry, new_entry, ctx,
       tag, identity_remap, msa_by_src_guid, dropped, copy_set)` -- NEW,
       this fix. Looks up each subsense via `copy_set` (never creates one)
       and hands it to `_create_and_wire_sense_msa`.
    3. `categories._create_and_wire_sense_msa(...)` -- NEW, this fix (the
       per-sense MSA create-and-wire logic extracted verbatim from the old
       inline block, called both for the top-level sense and for every
       subsense).

Confirmed this is `_walk_lex_entry_closure`'s ACTUAL call sequence by
reading `src/gramtrans/Lib/categories.py` directly: the sense loop (~line
8306) calls `_owned.walk_owned_children(src_sense, new_sense, ...)`
immediately followed by `_wire_subsense_msas(src_sense, src_entry,
new_entry, context, tag, identity_remap, msa_by_src_guid, dropped,
copy_set)` (~line 8341), and later in the SAME loop iteration calls
`_create_and_wire_sense_msa(src_sense, new_sense, src_entry, new_entry,
context, tag, identity_remap, msa_by_src_guid, dropped, s_guid=s_guid)`
(~line 8380) for the top-level sense itself -- this file's tests (b)/(c)
call the two functions in that identical order to mirror it exactly.

Host-free: duck fakes, modeled on `tests/unit/test_subsense_copy_set.py`
(owned-walk shapes) and `tests/unit/test_038_t123_msa_naturalkey_reuse.py`
(MSA create/wire shapes).
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from gramtrans.Lib import categories, owned
import gramtrans.Lib.categories as _cat_mod
import gramtrans.Lib.residue as _residue_mod


WS_EN = 100
_TAG = "tag-t123a-subsense-msa"


# ============================================================================
# Fakes -- source side (mirrors test_subsense_copy_set.py's _FakeSourceSense)
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
    """Fake ILexSense: `SensesOS` is the recursive sub-sense leg
    `owned.walk_owned_children` reproduces; `MorphoSyntaxAnalysisRA` is the
    field `_create_and_wire_sense_msa` reads."""

    def __init__(self, guid, gloss="", sub_senses=(), msa=None):
        self.Guid = guid
        self.guid = guid
        self.Gloss = _FakeMultiString({WS_EN: gloss} if gloss else {})
        self.SensesOS = list(sub_senses)
        self.SenseTypeRA = None
        self.MorphoSyntaxAnalysisRA = msa


# ============================================================================
# Fakes -- target side
# ============================================================================

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
        self.MorphoSyntaxAnalysisRA = None


class _FakeSenseFactory:
    """OWNER_TAKING: `ILexSenseFactory.Create(Guid, ILexSense owner)`
    (sub-senses) -- same MCP-confirmed shape `test_owned_object_walk.py` /
    `test_subsense_copy_set.py` use."""

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


class _Entry:
    def __init__(self, guid):
        self.guid = guid
        self.MorphoSyntaxAnalysesOC = []


# ============================================================================
# Fakes -- project / context (mirrors test_subsense_copy_set.py's _FakeProject,
# minus the lexical-relation plumbing this file doesn't need)
# ============================================================================

class _FakeProject:
    def __init__(self, factories=None):
        self.Cache = SimpleNamespace(DefaultAnalWs=WS_EN)
        self.Examples = _FakeSyncOps()
        self.Senses = _FakeSyncOps()
        self._factories = dict(factories or {})
        self._factories.setdefault("ILexSenseFactory", _FakeSenseFactory())

    def GetService(self, name):
        return self._factories[name]


class _FakeContext:
    def __init__(self, source_handle, target_handle, copy_set=None):
        self.source_handle = source_handle
        self.target_handle = target_handle
        self._ws_map = {}
        self._copy_set = copy_set if copy_set is not None else {}


# ============================================================================
# MSA-side host-free scaffolding (mirrors test_038_t123_msa_naturalkey_reuse.py)
# ============================================================================

@pytest.fixture(autouse=True)
def _host_free(monkeypatch):
    """Make the MSA closure importable and residue-free host-side; also lets
    `owned.py`'s `_owner_class_name`/`_resolve_service_type` degrade to the
    duck-typed hasattr/string-key fallbacks this file's fakes rely on."""
    fake = types.ModuleType("SIL.LCModel")
    fake.ICmObject = lambda obj: SimpleNamespace(
        Guid=getattr(obj, "guid", ""),
        ClassName=getattr(obj, "ClassName", None),
    )
    fake.ILexEntry = lambda obj: obj
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    original = sys.modules.get("SIL.LCModel")
    sys.modules["SIL.LCModel"] = fake
    monkeypatch.setattr(
        _cat_mod, "_guid_str_from",
        lambda obj: str(getattr(obj, "guid", "")).lower())
    monkeypatch.setattr(
        _cat_mod, "_cast_msa_concrete", lambda obj: obj)
    monkeypatch.setattr(
        _residue_mod, "apply_residue", lambda *a, **k: None)
    yield
    if original is None:
        sys.modules.pop("SIL.LCModel", None)
    else:
        sys.modules["SIL.LCModel"] = original


@pytest.fixture
def guid_create_spy(monkeypatch):
    """Stand in for `_create_msa_with_guid`: ALWAYS succeeds, preserving the
    source GUID and wiring the sense -- the GUID-preserving path's happy
    case, same as `test_038_t123_msa_naturalkey_reuse.py`'s fixture of the
    same name."""
    calls: list = []

    def _spy(target, new_entry, new_sense, subclass, src_guid, pos_fields):
        calls.append({"subclass": subclass, "src_guid": src_guid})
        made = SimpleNamespace(guid=src_guid, ClassName=subclass,
                               StratumRA=None, **pos_fields)
        new_entry.MorphoSyntaxAnalysesOC.append(made)
        if new_sense is not None:
            new_sense.MorphoSyntaxAnalysisRA = made
        return made

    monkeypatch.setattr(_cat_mod, "_create_msa_with_guid", _spy)
    return calls


@pytest.fixture(autouse=True)
def _resolve_pos(monkeypatch):
    shared_pos = SimpleNamespace(guid="c46c8242-8b3a-4021-9aed-2da8517438b5")
    monkeypatch.setattr(_cat_mod, "_resolve_target_pos",
                        lambda *a, **k: shared_pos)


def _msa(guid):
    return SimpleNamespace(
        guid=guid, ClassName="MoStemMsa",
        PartOfSpeechRA=SimpleNamespace(
            guid="c46c8242-8b3a-4021-9aed-2da8517438b5"),
        StratumRA=None)


def _make_ctx_and_new(src_sense_top):
    """Wire up the fakes and run the REAL `owned.walk_owned_children` for
    `src_sense_top` (step 1 of the sequence this file drives). Returns
    (ctx, new_entry, new_sense_top)."""
    source_handle = _FakeProject()
    target_handle = _FakeProject()
    ctx = _FakeContext(source_handle, target_handle)
    new_entry = _Entry("e2cd79ef-2ee5-4d56-ae54-9210060bcdae")
    new_sense_top = _NewSense("new-top")
    resolver_cache: dict = {}
    dropped: list = []
    owned.walk_owned_children(
        src_sense_top, new_sense_top, ctx, _TAG, resolver_cache, dropped)
    return ctx, new_entry, new_sense_top, dropped


# ============================================================================
# (a) one top-level sense, one subsense, subsense carries its OWN distinct
#     MSA -> the subsense's destination referent must be non-null and point
#     at its own source MSA's guid, with no duplicate MSA created.
# ============================================================================

def test_subsense_own_msa_is_created_and_wired(guid_create_spy):
    sub_guid = "3081d6f8-0000-0000-0000-000000000002"
    top_guid = "885182d0-0000-0000-0000-000000000001"
    msa_sub = _msa("8617b725-efc1-4f6d-935c-c6c87081c7cb")

    src_sub = _FakeSourceSense(sub_guid, gloss="small child", msa=msa_sub)
    src_top = _FakeSourceSense(top_guid, gloss="child", sub_senses=(src_sub,))
    src_entry = _Entry("e2cd79ef-2ee5-4d56-ae54-9210060bcdae")

    ctx, new_entry, new_sense_top, dropped = _make_ctx_and_new(src_top)
    new_sub = new_sense_top.SensesOS[0]
    assert ctx._copy_set[sub_guid] is new_sub, (
        "precondition: owned.walk_owned_children must have already "
        "registered the subsense into copy_set before the MSA wiring walk "
        "runs -- production relies on this ordering")

    msa_by_src_guid: dict = {}
    identity_remap: dict = {}
    categories._wire_subsense_msas(
        src_top, src_entry, new_entry, ctx, _TAG, identity_remap,
        msa_by_src_guid, dropped, ctx._copy_set)

    assert dropped == [], "a clean create/wire is not a loss"
    assert new_sub.MorphoSyntaxAnalysisRA is not None, (
        "THE regression: a subsense's MSA must be created and wired, not "
        "left null")
    assert new_sub.MorphoSyntaxAnalysisRA.guid == msa_sub.guid
    assert len(guid_create_spy) == 1
    assert guid_create_spy[0]["src_guid"] == msa_sub.guid
    assert msa_by_src_guid == {msa_sub.guid: new_sub.MorphoSyntaxAnalysisRA}


# ============================================================================
# (b) two senses at DIFFERENT depths (top-level + subsense) referencing the
#     SAME source MSA -> exactly one MSA created, both referents non-null
#     and identical.
# ============================================================================

def test_shared_msa_across_depths_creates_exactly_one(guid_create_spy):
    sub_guid = "3081d6f8-0000-0000-0000-000000000002"
    top_guid = "885182d0-0000-0000-0000-000000000001"
    shared_msa_src = _msa("13b8f64f-0000-0000-0000-000000000099")

    # Same source MSA object/guid referenced by BOTH the top-level sense and
    # its subsense -- the "two senses at different depths share one MSA"
    # shape.
    src_sub = _FakeSourceSense(sub_guid, gloss="small child", msa=shared_msa_src)
    src_top = _FakeSourceSense(
        top_guid, gloss="child", sub_senses=(src_sub,), msa=shared_msa_src)
    src_entry = _Entry("e2cd79ef-2ee5-4d56-ae54-9210060bcdae")

    ctx, new_entry, new_sense_top, dropped = _make_ctx_and_new(src_top)
    new_sub = new_sense_top.SensesOS[0]

    msa_by_src_guid: dict = {}
    identity_remap: dict = {}
    # Production order: subsense MSA wiring runs BEFORE the top-level
    # sense's own MSA wiring within one sense-loop iteration (categories.py
    # ~8331-8380) -- mirrored exactly here.
    categories._wire_subsense_msas(
        src_top, src_entry, new_entry, ctx, _TAG, identity_remap,
        msa_by_src_guid, dropped, ctx._copy_set)
    categories._create_and_wire_sense_msa(
        src_top, new_sense_top, src_entry, new_entry, ctx, _TAG,
        identity_remap, msa_by_src_guid, dropped, s_guid=top_guid)

    assert dropped == []
    assert len(guid_create_spy) == 1, (
        "one source MSA guid shared by two senses at different depths must "
        "be created exactly ONCE")
    assert new_sub.MorphoSyntaxAnalysisRA is not None
    assert new_sense_top.MorphoSyntaxAnalysisRA is not None
    assert new_sub.MorphoSyntaxAnalysisRA is new_sense_top.MorphoSyntaxAnalysisRA, (
        "both referring senses must be wired to the SAME target MSA object"
    )
    assert msa_by_src_guid == {shared_msa_src.guid: new_sub.MorphoSyntaxAnalysisRA}


# ============================================================================
# (c) a sense whose SOURCE counterpart has no MSA -> still ends null; a
#     sibling subsense WITH an MSA must not leak an MSA onto it.
# ============================================================================

def test_subsense_with_no_source_msa_stays_null(guid_create_spy):
    sub_with_guid = "3081d6f8-0000-0000-0000-000000000002"
    sub_without_guid = "aaaaaaaa-0000-0000-0000-000000000003"
    top_guid = "885182d0-0000-0000-0000-000000000001"
    msa_sub = _msa("8617b725-efc1-4f6d-935c-c6c87081c7cb")

    src_sub_with = _FakeSourceSense(sub_with_guid, gloss="small child", msa=msa_sub)
    src_sub_without = _FakeSourceSense(sub_without_guid, gloss="child (bare)", msa=None)
    src_top = _FakeSourceSense(
        top_guid, gloss="child", sub_senses=(src_sub_with, src_sub_without))
    src_entry = _Entry("e2cd79ef-2ee5-4d56-ae54-9210060bcdae")

    ctx, new_entry, new_sense_top, dropped = _make_ctx_and_new(src_top)
    new_sub_with = new_sense_top.SensesOS[0]
    new_sub_without = new_sense_top.SensesOS[1]

    msa_by_src_guid: dict = {}
    identity_remap: dict = {}
    categories._wire_subsense_msas(
        src_top, src_entry, new_entry, ctx, _TAG, identity_remap,
        msa_by_src_guid, dropped, ctx._copy_set)

    assert dropped == []
    assert new_sub_with.MorphoSyntaxAnalysisRA is not None
    assert new_sub_without.MorphoSyntaxAnalysisRA is None, (
        "a sense whose SOURCE counterpart has no MSA must still end null -- "
        "the invariant is a DELTA (source: 13 legitimate nulls), never an "
        "absolute")
    assert len(guid_create_spy) == 1, (
        "only the subsense that actually has a source MSA may trigger a "
        "create")
