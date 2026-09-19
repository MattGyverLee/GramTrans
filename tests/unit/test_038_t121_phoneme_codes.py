"""Feature 038 T121: `PhCode` had no transfer path at all.

THE MEASUREMENT. The destination reads **25 codes on all three sanctioned
pairs** -- exactly the starter baseline -- against sources holding 43 / 89 / 79.
Not one `PhCode` was ever created, on any pair. The cause is named in
`contracts/fidelity-census.md` CP-4 and re-confirmed against flexicon 4.5.2 by
T117: `PhonemeOperations.GetSyncableProperties` returns exactly
`['BasicIPASymbol', 'Description', 'Features', 'FeaturesGuid', 'Name']`, with
`CodesOS` absent, and `ApplySyncableProperties` has no code handling. Nothing
carried codes, and before this task `grep` found no `AddCode` / `CodesOS` write
anywhere in `src/`.

TWO SCOPE CONSTRAINTS, BOTH OF WHICH A NAIVE LOOP GETS WRONG.

1. THE ENRICHMENT HALF IS MANDATORY. The loss covers phonemes this run
   CREATED *and* phonemes MATCHED to the target's 23-phoneme starter
   inventory. A matched phoneme never reaches `phonemes_execute_action` at all
   -- it plans as a natural-key `PlannedOverwrite` -- so a create-path-only fix
   leaves the starter half exactly as it was.

2. TWO OF THE DESTINATION'S 25 CODES BELONG TO `PhBdryMarker`, NOT
   `PhPhoneme`. Measured live on `Ejagham W Mini`: 43 codes = 41 on
   `PhPhoneme` + 2 on `PhBdryMarker`, both under the SAME field
   (`PhTerminalUnit.Codes`, flid 5090003), different runtime owner. Those 2 are
   already MATCHED 2 -> 2 and a phoneme-scoped loop that treats the class as
   one thing would duplicate them.

ROUTE. T117 chose flexicon's `AddCode` to avoid an upstream dependency. That
reasoning holds and this keeps it in-tree -- but `AddCode` MINTS a fresh
identity, and GUID loss is a defect in this codebase unless justified. Probed
live on LCM 11.0.0: `SIL.LCModel.DomainImpl.PhCodeFactory` exposes BOTH
`Create()` and `Create(Guid)`, so `_create_with_guid` works here as it does
everywhere else. Same conclusion as T117, better road.

Host-free: duck fakes only.
"""
from __future__ import annotations

import inspect
import types

from gramtrans.Lib import categories
from gramtrans.Lib.models import GrammarCategory


class _Obj:
    def __init__(self, guid):
        self.guid = guid


class _Code:
    def __init__(self, guid, rep=""):
        self.guid = guid
        self.Representation = _MultiString(rep)


class _MultiString:
    def __init__(self, text=""):
        self._by_handle = {1: text} if text else {}

    def get_String(self, handle):  # noqa: N802 -- mirrors the LCM API
        return self._by_handle.get(handle, "")

    def set_String(self, handle, value):  # noqa: N802
        self._by_handle[handle] = value


class _AddList(list):
    def Add(self, item):  # noqa: N802
        self.append(item)


class _SrcPhoneme:
    def __init__(self, guid, codes=()):
        self.guid = guid
        self.CodesOS = list(codes)


class _TgtPhoneme:
    def __init__(self, guid, codes=()):
        self.guid = guid
        self.CodesOS = _AddList(codes)


class _WS:
    def __init__(self, handle, ws_id):
        self.Handle = handle
        self.Id = ws_id


class _Handle:
    """Duck project handle. No `Cache`, so `_lcm_factory`-style live paths are
    not taken; `_create_with_guid` is monkeypatched by the tests that need it."""

    def __init__(self, phonemes=(), registry=None, ws=(("1", "en"),)):
        self.Phonemes = types.SimpleNamespace(GetAll=lambda: list(phonemes))
        self.WritingSystems = types.SimpleNamespace(
            GetAll=lambda: [_WS(int(h), i) for h, i in ws])
        self._registry = registry or {}

    def get_object_by_guid(self, guid):
        return self._registry.get(guid)


def _context(source, target):
    return types.SimpleNamespace(source_handle=source, target_handle=target,
                                 _run_plan=None)


def _plan(overwrites=(), remap=None):
    return types.SimpleNamespace(
        overwrites=tuple(overwrites), identity_remap=remap or {},
        ws_mapping=None, actions=())


class _Overwrite:
    def __init__(self, source_guid, target_guid,
                 category=GrammarCategory.PHONEMES):
        self.category = category
        self.source_guid = source_guid
        self.target_guid = target_guid


def _fake_create_with_guid(monkeypatch):
    """Stand in for `_create_with_guid`, which needs a live LCM factory.
    Records what it was asked to create so the GUID claim is checkable."""
    seen = []

    def _fake(factory_iface, owner_collection, guid_str, target):
        code = _Code(guid_str)
        owner_collection.Add(code)
        seen.append(guid_str)
        return code, True

    monkeypatch.setattr(categories, "_create_with_guid", _fake)
    monkeypatch.setattr(categories, "IPhCodeFactory_ref", lambda: object())
    return seen


# --------------------------------------------------------------------------
# The create half
# --------------------------------------------------------------------------

def test_codes_transfer_to_a_created_phoneme(monkeypatch):
    seen = _fake_create_with_guid(monkeypatch)
    src = _Handle([_SrcPhoneme("p1", [_Code("c1", "[p]"), _Code("c2", "[ph]")])])
    tgt_phon = _TgtPhoneme("p1")
    tgt = _Handle(registry={"p1": tgt_phon})

    skips = categories._wire_phoneme_codes(_context(src, tgt), tgt, None)

    assert skips == []
    assert [c.guid for c in tgt_phon.CodesOS] == ["c1", "c2"]
    assert seen == ["c1", "c2"]          # GUID-preserved, source GUIDs


# --------------------------------------------------------------------------
# The enrichment half -- the one a create-path-only fix would miss
# --------------------------------------------------------------------------

def test_codes_transfer_to_a_starter_matched_phoneme(monkeypatch):
    """The destination reads exactly the 23-phoneme starter baseline on all
    three pairs. A phoneme matched to a starter carries the STARTER's GUID, so
    a source-GUID lookup cannot find it -- only the run's PlannedOverwrite can.
    This is the half that makes the measured number move."""
    seen = _fake_create_with_guid(monkeypatch)
    src = _Handle([_SrcPhoneme("src-a", [_Code("c1", "[a]")])])
    starter = _TgtPhoneme("starter-a")
    tgt = _Handle(registry={"starter-a": starter})
    ctx = _context(src, tgt)
    ctx._run_plan = _plan(overwrites=[_Overwrite("src-a", "starter-a")])

    skips = categories._wire_phoneme_codes(ctx, tgt, None)

    assert skips == []
    assert [c.guid for c in starter.CodesOS] == ["c1"]
    assert seen == ["c1"]


def test_identity_remap_is_honoured(monkeypatch):
    _fake_create_with_guid(monkeypatch)
    src = _Handle([_SrcPhoneme("p1", [_Code("c1", "[p]")])])
    minted = _TgtPhoneme("minted")
    tgt = _Handle(registry={"minted": minted})
    ctx = _context(src, tgt)
    ctx._run_plan = _plan(remap={"p1": "minted"})

    categories._wire_phoneme_codes(ctx, tgt, None)
    assert [c.guid for c in minted.CodesOS] == ["c1"]


# --------------------------------------------------------------------------
# The boundary-marker trap
# --------------------------------------------------------------------------

def test_the_pass_walks_phonemes_not_terminal_units():
    """`PhCode` is owned via `PhTerminalUnit.Codes`, and `PhTerminalUnit` has
    TWO concrete subclasses. This pass reads `source.Phonemes.GetAll()`, so a
    `PhBdryMarker`'s codes are UNREACHABLE from here -- the trap is avoided by
    construction rather than by a filter someone can later delete.

    Asserted on the source text because the alternative -- a PhCode-repository
    loop -- would pass every behavioural test above and still be one edit away
    from duplicating the 2 matched boundary-marker codes."""
    body = inspect.getsource(categories._wire_phoneme_codes)
    assert "source.Phonemes.GetAll()" in body
    assert "IPhCodeRepository" not in body
    assert "PhBdryMarker" not in body.split('"""')[2]   # not in the CODE
    assert "PhBdryMarker" in body                        # but IS in the docstring


def test_boundary_marker_codes_are_untouched(monkeypatch):
    """A boundary marker in the target keeps exactly the codes it had."""
    _fake_create_with_guid(monkeypatch)
    bdry = _TgtPhoneme("bdry-1", [_Code("bc1", "#")])
    src = _Handle([_SrcPhoneme("p1", [_Code("c1", "[p]")])])
    tgt_phon = _TgtPhoneme("p1")
    tgt = _Handle(registry={"p1": tgt_phon, "bdry-1": bdry})

    categories._wire_phoneme_codes(_context(src, tgt), tgt, None)

    assert [c.guid for c in bdry.CodesOS] == ["bc1"]


# --------------------------------------------------------------------------
# Discipline: idempotency, scoping, never-silent
# --------------------------------------------------------------------------

def test_is_idempotent(monkeypatch):
    _fake_create_with_guid(monkeypatch)
    src = _Handle([_SrcPhoneme("p1", [_Code("c1", "[p]")])])
    tgt_phon = _TgtPhoneme("p1")
    tgt = _Handle(registry={"p1": tgt_phon})
    ctx = _context(src, tgt)

    categories._wire_phoneme_codes(ctx, tgt, None)
    categories._wire_phoneme_codes(ctx, tgt, None)

    assert [c.guid for c in tgt_phon.CodesOS] == ["c1"]


def test_a_phoneme_absent_from_the_destination_is_not_a_loss(monkeypatch):
    """T074's scoping. A source phoneme with no destination counterpart is one
    this run never transferred, not a lost code."""
    _fake_create_with_guid(monkeypatch)
    src = _Handle([_SrcPhoneme("p1", [_Code("c1", "[p]")])])
    tgt = _Handle(registry={})

    assert categories._wire_phoneme_codes(_context(src, tgt), tgt, None) == []


def test_a_failed_create_is_reported_not_swallowed(monkeypatch):
    """`_create_with_guid` fails LOUD on a GUID it cannot preserve. A code is a
    leaf, so the pass must not abort the whole inventory over one -- but it
    must not go quiet either."""
    def _boom(*a, **k):
        raise RuntimeError("Factory does not support Create(Guid)")
    monkeypatch.setattr(categories, "_create_with_guid", _boom)
    monkeypatch.setattr(categories, "IPhCodeFactory_ref", lambda: object())

    src = _Handle([_SrcPhoneme("p1", [_Code("c1", "[p]"), _Code("c2", "[b]")])])
    tgt_phon = _TgtPhoneme("p1")
    tgt = _Handle(registry={"p1": tgt_phon})

    skips = categories._wire_phoneme_codes(_context(src, tgt), tgt, None)

    assert len(skips) == 2                     # one per code, never silent
    assert all(s.category is GrammarCategory.PHONEMES for s in skips)
    assert "c1" in skips[0].source_guid


def test_a_phoneme_with_no_codes_is_a_no_op(monkeypatch):
    _fake_create_with_guid(monkeypatch)
    src = _Handle([_SrcPhoneme("p1", [])])
    tgt_phon = _TgtPhoneme("p1")
    tgt = _Handle(registry={"p1": tgt_phon})

    assert categories._wire_phoneme_codes(_context(src, tgt), tgt, None) == []
    assert list(tgt_phon.CodesOS) == []


# --------------------------------------------------------------------------
# Wiring
# --------------------------------------------------------------------------

def test_execute_action_registers_the_tail_pass():
    """A pass nothing calls is this codebase's known failure mode
    (`phonological_rules_dependencies`: written, correct, dead)."""
    body = inspect.getsource(categories.phonemes_execute_action)
    assert "_run_tail_once" in body
    assert "_wire_phoneme_codes" in body
    assert "_did_phoneme_codes" in body


def test_representation_is_copied_ws_mapped():
    """Handles are per-project and NOT portable: writing a source handle into
    the target throws inside XMLBackendProvider.Commit and discards the ENTIRE
    unit of work (T024g). The copy must go through the WS-mapping helper."""
    body = inspect.getsource(categories._wire_phoneme_codes)
    assert "_copy_multistrings_ws_mapped" in body
    assert '"Representation"' in body
