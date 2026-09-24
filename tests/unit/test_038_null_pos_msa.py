"""T043b -- a null part of speech is a STATE the source holds, not a failure.

The defect this locks down was measured twice before anyone joined the two
measurements together:

* T038's live gate, `Ejagham Mini` -> `GT038 Phase4 Target`: `MoStemMsa`
  164 -> 162. Exactly **2 of 164** source stem MSAs carry a null
  `PartOfSpeechRA`, and both were dropped. Confirmed independently by
  read-only `.fwdata` parsing and by the 2 matching `DroppedItemRecord`s;
  `164 - 2 = 162` closes with no residue.
* The Ngoreme pair, at scale 9, asserted since
  `test_038_two_mode_and_tallies.py::test_the_in_scope_residue_is_small_and_named`
  against a committed snapshot.

A null `PartOfSpeechRA` is **legal** in FLEx -- it is what Category =
`<Not Sure>` looks like, and the source project demonstrates it. So dropping it
is the engine declining to reproduce a state the source legitimately holds:
real content loss (FR-002), not a dependency failure.

The guard existed for exactly one reason: the flexicon wrapper fallback
(`MSAOperations.CreateStem` and friends) raises `FP_NullParameterError` on a
null POS and aborts the whole affix closure. The fix therefore routes the null
through the GUID-preserving `_create_msa_with_guid` path -- which applies POS by
`setattr`, where `None` is harmless -- and skips the wrapper for that case.

What must NOT change: a POS that is *set on the source and unresolvable in the
target* is a genuine dependency failure and is still dropped and reported, and
`MoInflAffMsa` / `MoDerivAffMsa` keep the stricter guard because an
inflectional or derivational affix with no category cannot be interpreted.
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
# Fakes
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

    Reaching one on a null POS is the live `FP_NullParameterError` abort, so a
    test that trips this trap has reproduced the defect.
    """
    def _boom(*_a, **_k):
        raise AssertionError(
            "the flexicon MSA wrapper was reached -- it rejects a null POS and "
            "aborts the whole affix closure; T043b must skip it for that case")

    msa_ops = SimpleNamespace(
        CreateStem=_boom if boobytrap_wrapper else (lambda *a, **k: None),
        CreateInflAff=_boom,
        CreateDerivAff=_boom,
        CreateUnclassifiedAffix=_boom if boobytrap_wrapper else (
            lambda *a, **k: None),
    )
    target = SimpleNamespace(Cache=SimpleNamespace(DefaultAnalWs=1),
                             MSA=msa_ops)
    ctx = SimpleNamespace(target_handle=target, source_handle=SimpleNamespace(),
                          _ws_map=None)
    return ctx, target


@pytest.fixture
def guid_create_spy(monkeypatch):
    """Stand in for `_create_msa_with_guid`, recording the POS fields it got.

    The GUID-preserving path is the one that CAN carry a null POS (it applies
    POS by `setattr`), so this spy is where the fix is observable.
    """
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


def _run(src_msa, *, dropped=None, boobytrap=True):
    ctx, _t = _ctx_and_target(boobytrap_wrapper=boobytrap)
    entry = _Entry("11111111-0000-0000-0000-000000000001")
    sense = _Sense()
    out = categories._create_msa_for_closure(
        src_msa, sense, entry, ctx, None, {},
        dropped=dropped, src_entry=entry)
    return out, entry, sense


# ============================================================================
# The fix: a legal null POS is reproduced, not dropped
# ============================================================================

@pytest.mark.parametrize("subclass", ["MoStemMsa", "MoUnclassifiedAffixMsa"])
def test_null_pos_is_reproduced_not_dropped(subclass, guid_create_spy):
    """The T038 defect, host-free: 2 of 164 stem MSAs looked like this."""
    src = SimpleNamespace(guid="aaaaaaaa-0000-0000-0000-00000000000a",
                          ClassName=subclass, PartOfSpeechRA=None,
                          StratumRA=None)
    dropped: list = []

    out, entry, sense = _run(src, dropped=dropped)

    assert out is not None, f"{subclass} with a legal null POS was dropped"
    assert dropped == [], "a legal source state must not be reported as a loss"
    assert len(guid_create_spy) == 1
    # The null is REPRODUCED -- not defaulted, not invented.
    assert guid_create_spy[0]["pos_fields"] == {"PartOfSpeechRA": None}
    assert guid_create_spy[0]["src_guid"] == src.guid
    assert sense.MorphoSyntaxAnalysisRA is out
    assert entry.MorphoSyntaxAnalysesOC == [out]


def test_the_wrapper_is_never_asked_to_swallow_a_null_pos(guid_create_spy):
    """The booby-trapped wrapper in `_ctx_and_target` is the whole point.

    `MSAOperations.CreateStem(sense, None)` raises FP_NullParameterError live
    and takes the entire affix closure down with it -- which is the only reason
    the over-broad guard ever existed.
    """
    src = SimpleNamespace(guid="bbbbbbbb-0000-0000-0000-00000000000b",
                          ClassName="MoStemMsa", PartOfSpeechRA=None,
                          StratumRA=None)
    out, _e, _s = _run(src, dropped=[])
    assert out is not None


def test_guid_path_unavailable_on_a_null_pos_reports_rather_than_invents():
    """No `_create_msa_with_guid` spy here, so that path returns None.

    With the wrapper unusable, the only honest outcomes are "report" or
    "invent a POS". Principle I / FR-010 requires the former.
    """
    src = SimpleNamespace(guid="cccccccc-0000-0000-0000-00000000000c",
                          ClassName="MoStemMsa", PartOfSpeechRA=None,
                          StratumRA=None)
    dropped: list = []

    out, _e, _s = _run(src, dropped=dropped)

    assert out is None
    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.item_name == "MoStemMsa"
    assert rec.field_name == "MorphoSyntaxAnalysesOC"
    assert "empty on source" in rec.reason
    assert "rejects a null part of speech" in rec.reason


# ============================================================================
# What must NOT change
# ============================================================================

def test_unresolvable_pos_is_still_a_reported_drop(guid_create_spy):
    """POS SET on source, absent from target: a real dependency failure."""
    src = SimpleNamespace(
        guid="dddddddd-0000-0000-0000-00000000000d", ClassName="MoStemMsa",
        PartOfSpeechRA=SimpleNamespace(
            guid="99999999-0000-0000-0000-000000000099"),
        StratumRA=None)
    dropped: list = []

    out, _e, _s = _run(src, dropped=dropped)

    assert out is None, "an unresolvable POS must still drop"
    assert guid_create_spy == [], "nothing may be created for it"
    assert len(dropped) == 1
    assert "not resolvable in target" in dropped[0].reason


@pytest.mark.parametrize("subclass,fields", [
    ("MoInflAffMsa", {"PartOfSpeechRA": None}),
    ("MoDerivAffMsa", {"FromPartOfSpeechRA": None, "ToPartOfSpeechRA": None}),
])
def test_inflectional_and_derivational_affixes_keep_the_guard(
        subclass, fields, guid_create_spy):
    """An affix that inflects or derives with NO category cannot be
    interpreted, so for these two a null POS stays a dependency failure."""
    src = SimpleNamespace(guid="eeeeeeee-0000-0000-0000-00000000000e",
                          ClassName=subclass, StratumRA=None, **fields)
    dropped: list = []

    out, _e, _s = _run(src, dropped=dropped)

    assert out is None
    assert guid_create_spy == []
    assert len(dropped) == 1
    assert "is empty on source" in dropped[0].reason


def test_an_invisible_pos_slot_is_not_mistaken_for_a_legal_null(
        guid_create_spy):
    """The pythonnet trap, and the one way this fix could have gone wrong.

    An uncast, base-interface-typed MSA HIDES its subclass-only slots, so a
    failed `_cast_msa_concrete` also reads POS as empty. Treating that as a
    legal null would convert a loud, reported dependency failure into silent
    content loss -- so emptiness is only trusted when the slot is present.
    """
    src = SimpleNamespace(guid="ffffffff-0000-0000-0000-00000000000f",
                          ClassName="MoStemMsa", StratumRA=None)
    assert not hasattr(src, "PartOfSpeechRA")
    dropped: list = []

    out, _e, _s = _run(src, dropped=dropped)

    assert out is None, "a hidden slot must not be reproduced as a null POS"
    assert guid_create_spy == []
    assert len(dropped) == 1
