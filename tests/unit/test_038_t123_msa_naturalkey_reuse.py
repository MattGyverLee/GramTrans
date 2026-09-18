"""Feature 038 T123 acceptance line (a): a second source MSA that shares a
natural key (same subclass + POS + content) with an already-created MSA on
the SAME entry must never be silently skipped, and the sense that referenced
it must never end up with a null `MorphoSyntaxAnalysisRA`.

THE DEFECT, measured live (`Ngoreme FLEx` -> `GT038 T124 Ngoreme`, entry
`omoona`/e2cd79ef-...): two source `MoStemMsa` on one entry are IDENTICAL in
every syncable property (same `PartOfSpeechRA`, same feature structure) and
differ ONLY by GUID -- one per sense ('child' -> 13b8f64f-..., 'small child'
-> 8617b725-efc1-4f6d-935c-c6c87081c7cb). The destination arrived with ONE
MSA (13b8f64f) and the SECOND sense's `MorphoSyntaxAnalysisRA` null; the
second source GUID is absent from the project entirely, and NO
`DroppedItemRecord` was ever written for it -- a silent loss, not a reported
one.

THE MECHANISM (`Lib/categories.py`): `_create_msa_for_closure`'s flexicon
wrapper fallback (`target.MSA.CreateStem`/`CreateInflAff`/`CreateDerivAff`/
`CreateUnclassifiedAffix`) used to be called BARE -- no try/except -- as the
leg reached whenever the GUID-preserving `_create_msa_with_guid` path is
unavailable. The wrapper has its own duplicate-avoidance behaviour and can
refuse to mint a second, content-identical MSA on the same entry; unguarded,
that refusal propagated as an uncaught exception all the way out of
`_walk_lex_entry_closure`'s per-sense loop (which itself had no try/except
either) to `Lib/transfer.py`'s per-ACTION swallow-and-record handler --
recorded only as a generic `LeafExecutionFailure`, never as a
`DroppedItemRecord`, and aborting every UNPROCESSED sibling on the same
entry (further senses, allomorphs, entry-refs) along with it.

THE FIX has two halves, tested separately below:
  (a) a second source MSA with a DISTINCT guid still gets its own,
      independent create attempt and its own, distinct target object --
      the existing per-guid cache in `_walk_lex_entry_closure` is not
      touched by content similarity;
  (b) when a create leg genuinely cannot land a NEW object (the wrapper
      raises), `_create_via_wrapper_or_reuse` first tries
      `_find_reusable_target_msa` -- an existing MSA on the SAME entry that
      matches by subclass + POS fields -- and only reports a drop when
      nothing matches. Either way `_create_msa_for_closure` never lets an
      exception escape, and its caller (`_walk_lex_entry_closure`) always
      wires whatever it returns onto the sense, so no sense whose source
      counterpart had an MSA is left dangling.

Host-free: duck fakes only, mirroring `tests/unit/test_038_null_pos_msa.py`'s
`_host_free` fixture (the established pattern for testing
`_create_msa_for_closure` directly, since `_walk_lex_entry_closure` itself is
LCM-bound and exercised only under a live host / the integration suite).
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from gramtrans.Lib import categories
import gramtrans.Lib.categories as _cat_mod
import gramtrans.Lib.residue as _residue_mod


# ============================================================================
# Fakes (mirrors test_038_null_pos_msa.py)
# ============================================================================

class _Entry:
    def __init__(self, guid):
        self.guid = guid
        self.MorphoSyntaxAnalysesOC = []


class _Sense:
    def __init__(self):
        self.MorphoSyntaxAnalysisRA = None


@pytest.fixture(autouse=True)
def _host_free(monkeypatch):
    """Make the MSA closure importable and residue-free host-side."""
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


def _ctx_and_target(*, boobytrap_wrapper=True):
    """A target whose flexicon MSA wrappers are booby-trapped.

    Reaching one and having it RAISE is the shape T123(a) reproduces live --
    a real wrapper refusing to mint a second content-identical MSA. A test
    that trips this trap and still comes out with a non-null referent has
    reproduced the fix."""
    def _boom(*_a, **_k):
        raise RuntimeError(
            "flexicon MSA wrapper refused a duplicate-content create -- "
            "the T123(a) shape: the caller must reuse or report, never crash")

    msa_ops = SimpleNamespace(
        CreateStem=_boom if boobytrap_wrapper else (lambda *a, **k: None),
        CreateInflAff=_boom,
        CreateDerivAff=_boom,
        CreateUnclassifiedAffix=_boom,
    )
    target = SimpleNamespace(Cache=SimpleNamespace(DefaultAnalWs=1),
                             MSA=msa_ops)
    ctx = SimpleNamespace(target_handle=target, source_handle=SimpleNamespace(),
                          _ws_map=None)
    return ctx, target


@pytest.fixture
def guid_create_spy(monkeypatch):
    """Stand in for `_create_msa_with_guid`: ALWAYS succeeds, preserving the
    source GUID and wiring the sense -- exactly what the real GUID-preserving
    path does when nothing prevents it. This is the "both halves arrive"
    happy path: two calls sharing one `new_entry` must not collapse onto one
    object just because their content is identical."""
    calls: list = []

    def _spy(target, new_entry, new_sense, subclass, src_guid, pos_fields):
        calls.append({"subclass": subclass, "src_guid": src_guid,
                      "pos_fields": dict(pos_fields)})
        made = SimpleNamespace(guid=src_guid, ClassName=subclass,
                               StratumRA=None, **pos_fields)
        new_entry.MorphoSyntaxAnalysesOC.append(made)
        new_sense.MorphoSyntaxAnalysisRA = made
        return made

    monkeypatch.setattr(_cat_mod, "_create_msa_with_guid", _spy)
    return calls


def _create(src_msa, sense, entry, ctx, dropped):
    return categories._create_msa_for_closure(
        src_msa, sense, entry, ctx, None, {}, dropped=dropped,
        src_entry=entry)


# ============================================================================
# (a) two content-identical, GUID-distinct MSAs on one entry: BOTH arrive
# ============================================================================

def test_two_content_identical_msas_both_arrive_under_their_own_guid(
        guid_create_spy, monkeypatch):
    """The `omoona` shape, on the happy path: nothing prevents the
    GUID-preserving create from landing both objects, so both must land --
    the per-entry cache lives on the REAL source guid, never on content."""
    shared_pos = SimpleNamespace(guid="c46c8242-8b3a-4021-9aed-2da8517438b5")
    # POS resolution is exercised elsewhere (test_038_pos_natural_key_call_site_sweep.py
    # etc.); fixing it here keeps this test scoped to the MSA-identity
    # question it is actually about.
    monkeypatch.setattr(_cat_mod, "_resolve_target_pos",
                        lambda *a, **k: shared_pos)
    ctx, _t = _ctx_and_target()
    entry = _Entry("e2cd79ef-2ee5-4d56-ae54-9210060bcdae")

    sense_child = _Sense()
    msa_child = SimpleNamespace(
        guid="13b8f64f-0000-0000-0000-000000000001",
        ClassName="MoStemMsa", PartOfSpeechRA=shared_pos, StratumRA=None)
    sense_small = _Sense()
    msa_small = SimpleNamespace(
        guid="8617b725-efc1-4f6d-935c-c6c87081c7cb",
        ClassName="MoStemMsa", PartOfSpeechRA=shared_pos, StratumRA=None)

    dropped: list = []
    out_child = _create(msa_child, sense_child, entry, ctx, dropped)
    out_small = _create(msa_small, sense_small, entry, ctx, dropped)

    assert dropped == [], "both creates succeed; nothing should be reported"
    assert out_child is not None and out_small is not None
    assert out_child is not out_small, (
        "two DISTINCT source guids must never collapse onto one target "
        "object just because their content matches")
    assert out_child.guid == msa_child.guid
    assert out_small.guid == msa_small.guid
    # `_create_msa_with_guid` wires the sense internally on success -- the
    # same wiring `_walk_lex_entry_closure` relies on / repeats defensively.
    assert sense_child.MorphoSyntaxAnalysisRA is out_child
    assert sense_small.MorphoSyntaxAnalysisRA is out_small
    assert entry.MorphoSyntaxAnalysesOC == [out_child, out_small]
    assert len(guid_create_spy) == 2


# ============================================================================
# (b) the reuse case: the create leg fails, an existing match is reused
# ============================================================================

def test_wrapper_raise_reuses_an_existing_match_instead_of_going_null(
        monkeypatch):
    """T123(a) half 2 -- the half that is easy to lose.

    No `guid_create_spy` here: the real `_create_msa_with_guid` degrades to
    None in this fake environment (no live `SIL.LCModel` factories), exactly
    as it does live when the GUID-preserving path is unavailable. The
    wrapper fallback is booby-trapped to RAISE (the observed live shape: a
    flexicon wrapper refusing a duplicate-content create). An MSA that
    already matches by subclass + POS already sits on the entry -- as if an
    earlier sense's create had already landed it. The fix must REUSE it
    rather than report a drop or, worse, let the sense end up null."""
    tgt_pos = SimpleNamespace(guid="c46c8242-8b3a-4021-9aed-2da8517438b5")
    monkeypatch.setattr(_cat_mod, "_resolve_target_pos",
                        lambda *a, **k: tgt_pos)

    ctx, _t = _ctx_and_target(boobytrap_wrapper=True)
    entry = _Entry("e2cd79ef-2ee5-4d56-ae54-9210060bcdae")
    existing = SimpleNamespace(
        guid="13b8f64f-0000-0000-0000-000000000001",
        ClassName="MoStemMsa", PartOfSpeechRA=tgt_pos, StratumRA=None)
    entry.MorphoSyntaxAnalysesOC.append(existing)

    sense = _Sense()
    src = SimpleNamespace(
        guid="8617b725-efc1-4f6d-935c-c6c87081c7cb",
        ClassName="MoStemMsa",
        PartOfSpeechRA=SimpleNamespace(
            guid="c46c8242-8b3a-4021-9aed-2da8517438b5"),
        StratumRA=None)
    dropped: list = []

    out = _create(src, sense, entry, ctx, dropped)

    assert out is existing, (
        "the create leg failed; the fix must REUSE the matching MSA already "
        "on the entry rather than report a drop or return None")
    assert dropped == [], "a successful reuse is not a loss"
    # Mirrors `_walk_lex_entry_closure`'s own unconditional post-call wiring
    # (`new_sense.MorphoSyntaxAnalysisRA = new_msa` whenever `new_msa` is not
    # None) -- the caller-side half of the never-null guarantee.
    sense.MorphoSyntaxAnalysisRA = out
    assert sense.MorphoSyntaxAnalysisRA is not None
    assert sense.MorphoSyntaxAnalysisRA is existing


def test_wrapper_raise_with_no_match_anywhere_reports_rather_than_crashes(
        monkeypatch):
    """No existing MSA to reuse: this must be a REPORTED drop, never an
    uncaught exception (which is what used to abort the rest of the entry's
    closure -- `_create_via_wrapper_or_reuse` never lets one escape)."""
    tgt_pos = SimpleNamespace(guid="c46c8242-8b3a-4021-9aed-2da8517438b5")
    monkeypatch.setattr(_cat_mod, "_resolve_target_pos",
                        lambda *a, **k: tgt_pos)

    ctx, _t = _ctx_and_target(boobytrap_wrapper=True)
    entry = _Entry("e2cd79ef-2ee5-4d56-ae54-9210060bcdae")  # nothing owned yet
    sense = _Sense()
    src = SimpleNamespace(
        guid="8617b725-efc1-4f6d-935c-c6c87081c7cb",
        ClassName="MoStemMsa",
        PartOfSpeechRA=SimpleNamespace(
            guid="c46c8242-8b3a-4021-9aed-2da8517438b5"),
        StratumRA=None)
    dropped: list = []

    out = _create(src, sense, entry, ctx, dropped)

    assert out is None
    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.item_guid == src.guid
    assert "create wrapper raised" in rec.reason
    assert "MSA not transferred" in rec.reason


def test_reuse_requires_matching_pos_not_just_matching_subclass(
        monkeypatch):
    """`_find_reusable_target_msa` must not reuse an MSA of the right
    SUBCLASS but the WRONG part of speech -- that would silently reassign a
    sense's grammatical category rather than reproduce it."""
    tgt_pos = SimpleNamespace(guid="c46c8242-8b3a-4021-9aed-2da8517438b5")
    wrong_pos = SimpleNamespace(guid="ffffffff-0000-0000-0000-0000000000ff")
    monkeypatch.setattr(_cat_mod, "_resolve_target_pos",
                        lambda *a, **k: tgt_pos)

    ctx, _t = _ctx_and_target(boobytrap_wrapper=True)
    entry = _Entry("e2cd79ef-2ee5-4d56-ae54-9210060bcdae")
    mismatched = SimpleNamespace(
        guid="13b8f64f-0000-0000-0000-000000000001",
        ClassName="MoStemMsa", PartOfSpeechRA=wrong_pos, StratumRA=None)
    entry.MorphoSyntaxAnalysesOC.append(mismatched)

    sense = _Sense()
    src = SimpleNamespace(
        guid="8617b725-efc1-4f6d-935c-c6c87081c7cb",
        ClassName="MoStemMsa",
        PartOfSpeechRA=SimpleNamespace(
            guid="c46c8242-8b3a-4021-9aed-2da8517438b5"),
        StratumRA=None)
    dropped: list = []

    out = _create(src, sense, entry, ctx, dropped)

    assert out is None, "a POS mismatch must never be silently reused"
    assert len(dropped) == 1
