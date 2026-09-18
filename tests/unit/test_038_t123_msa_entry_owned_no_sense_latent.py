"""LATENT PATTERN PIN -- NOT a T123(a) regression test.

T123(a) is a DIFFERENT, already-diagnosed and already-fixed defect: a
natural-key match inside `_walk_lex_entry_closure`'s per-sense loop that
used to skip a create and leave a sense's `MorphoSyntaxAnalysisRA` dangling
null (destination-side GUID diff, `omoona`/e2cd79ef-...; fixed by
`_create_via_wrapper_or_reuse` / `_find_reusable_target_msa`, landed in the
task immediately before this one). This file tests a SEPARATE, hardening-only
guard and asserts NOTHING about T123(a)'s -1.

WHAT THIS PINS: `_walk_lex_entry_closure`'s per-sense loop enumerates a
source entry's MSAs only via `src_sense.MorphoSyntaxAnalysisRA`, while
`_entry_pos_deps` and `_iter_all_msas` (elsewhere in `Lib/categories.py`)
both treat `LexEntry.MorphoSyntaxAnalysesOC` as the enumeration basis for an
entry's MSAs. An entry-owned MSA with no referencing source sense would fall
through the per-sense loop entirely and never be created at all.

MEASURED EMPTY on the only corpus this has been checked against
(`Ngoreme FLEx`, read-only ops `op-102227585-005` / `op-102255766-006`:
entry-owned MSA count equals distinct sense-referenced MSA count, 2090 =
2090, in every one of the four MSA classes -- see
`specs/038-transfer-fidelity-gaps/reviews/cycle6-verification-msa-naming.md`).
This guard (`_create_entry_owned_msas_without_sense`) exists for CONSISTENCY
with the two enumerators above and as a backstop against a corpus this
engine has not yet seen, not because a loss was observed here. Pinning it
prevents a future refactor from silently reintroducing the gap on some other
corpus where the population is NOT empty.

Exercises `_create_entry_owned_msas_without_sense` directly (the same
host-free, duck-fake approach `test_038_t123_msa_naturalkey_reuse.py` and
`test_038_null_pos_msa.py` use for `_create_msa_for_closure` -- the
enclosing `_walk_lex_entry_closure` is LCM-bound end-to-end and is only
exercised under a live host / the integration suite)."""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from gramtrans.Lib import categories
import gramtrans.Lib.categories as _cat_mod
import gramtrans.Lib.residue as _residue_mod


class _Entry:
    def __init__(self, guid, owned_msas=()):
        self.guid = guid
        self.MorphoSyntaxAnalysesOC = list(owned_msas)


@pytest.fixture(autouse=True)
def _host_free(monkeypatch):
    """Mirrors `test_038_t123_msa_naturalkey_reuse.py`'s `_host_free`."""
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
    """Stand in for `_create_msa_with_guid`: always succeeds, preserving the
    source GUID. `new_sense=None` (the hardening shape) must not be dropped
    silently -- the spy asserts the caller passed exactly that."""
    calls: list = []

    def _spy(target, new_entry, new_sense, subclass, src_guid, pos_fields):
        assert new_sense is None, (
            "the no-referencing-sense pass must call the create leg with "
            "new_sense=None, never invent a stand-in sense")
        calls.append({"subclass": subclass, "src_guid": src_guid})
        made = SimpleNamespace(guid=src_guid, ClassName=subclass,
                               StratumRA=None, **pos_fields)
        new_entry.MorphoSyntaxAnalysesOC.append(made)
        return made

    monkeypatch.setattr(_cat_mod, "_create_msa_with_guid", _spy)
    return calls


def test_entry_owned_msa_with_no_referencing_sense_is_still_created__latent(
        guid_create_spy, monkeypatch):
    """LATENT PATTERN PIN. One entry, two senses' worth of source MSAs: an
    entry-level `MorphoSyntaxAnalysesOC` of 2, where only ONE guid is already
    accounted for in `msa_by_src_guid` (as if the per-sense loop had already
    processed the sense that referenced it) and the other has NO referencing
    sense anywhere. Asserts both MSAs arrive on `new_entry` and the
    unreferenced one's GUID is identity-preserved -- never a claim about
    T123(a)."""
    shared_pos = SimpleNamespace(guid="c46c8242-8b3a-4021-9aed-2da8517438b5")
    monkeypatch.setattr(_cat_mod, "_resolve_target_pos",
                        lambda *a, **k: shared_pos)

    referenced_guid = "13b8f64f-0000-0000-0000-000000000001"
    unreferenced_guid = "8617b725-efc1-4f6d-935c-c6c87081c7cb"
    src_msa_referenced = SimpleNamespace(
        guid=referenced_guid, ClassName="MoStemMsa",
        PartOfSpeechRA=shared_pos, StratumRA=None)
    src_msa_unreferenced = SimpleNamespace(
        guid=unreferenced_guid, ClassName="MoStemMsa",
        PartOfSpeechRA=shared_pos, StratumRA=None)

    src_entry = _Entry(
        "e2cd79ef-2ee5-4d56-ae54-9210060bcdae",
        owned_msas=[src_msa_referenced, src_msa_unreferenced])

    # Simulates the state left behind by `_walk_lex_entry_closure`'s
    # per-sense loop: the FIRST source MSA already has a target object (its
    # sense referenced it), pre-registered in both places that loop would
    # have populated them.
    already_created = SimpleNamespace(
        guid=referenced_guid, ClassName="MoStemMsa",
        PartOfSpeechRA=shared_pos, StratumRA=None)
    new_entry = _Entry("new-entry-guid", owned_msas=[already_created])
    msa_by_src_guid = {referenced_guid: already_created}

    ctx = SimpleNamespace(target_handle=SimpleNamespace(
        Cache=SimpleNamespace(DefaultAnalWs=1)))
    dropped: list = []

    categories._create_entry_owned_msas_without_sense(
        src_entry, new_entry, ctx, None, {}, msa_by_src_guid, dropped)

    assert dropped == [], "a clean create is not a loss"
    # The already-processed guid must not be re-created (no double-create).
    assert len(guid_create_spy) == 1
    assert guid_create_spy[0]["src_guid"] == unreferenced_guid

    assert len(new_entry.MorphoSyntaxAnalysesOC) == 2, (
        "both the sense-referenced MSA (already present) and the "
        "no-referencing-sense MSA (created by this pass) must be on "
        "new_entry.MorphoSyntaxAnalysesOC")
    guids_on_entry = {m.guid for m in new_entry.MorphoSyntaxAnalysesOC}
    assert guids_on_entry == {referenced_guid, unreferenced_guid}

    # Identity-preserved: the created object's guid is the SOURCE guid, not
    # a freshly minted one.
    created = next(m for m in new_entry.MorphoSyntaxAnalysesOC
                   if m.guid == unreferenced_guid)
    assert created.guid == src_msa_unreferenced.guid
    assert msa_by_src_guid[unreferenced_guid] is created


def test_already_processed_guid_is_never_recreated__latent(guid_create_spy):
    """Companion pin: when EVERY entry-owned MSA is already in
    `msa_by_src_guid` (the ordinary, measured-on-corpus case), this pass is a
    no-op -- zero create calls, zero drops, entry unchanged."""
    shared_pos = SimpleNamespace(guid="c46c8242-8b3a-4021-9aed-2da8517438b5")
    only_guid = "13b8f64f-0000-0000-0000-000000000001"
    src_msa = SimpleNamespace(
        guid=only_guid, ClassName="MoStemMsa",
        PartOfSpeechRA=shared_pos, StratumRA=None)
    src_entry = _Entry("e2cd79ef-2ee5-4d56-ae54-9210060bcdae",
                       owned_msas=[src_msa])

    already_created = SimpleNamespace(
        guid=only_guid, ClassName="MoStemMsa",
        PartOfSpeechRA=shared_pos, StratumRA=None)
    new_entry = _Entry("new-entry-guid", owned_msas=[already_created])
    msa_by_src_guid = {only_guid: already_created}

    ctx = SimpleNamespace(target_handle=SimpleNamespace(
        Cache=SimpleNamespace(DefaultAnalWs=1)))
    dropped: list = []

    categories._create_entry_owned_msas_without_sense(
        src_entry, new_entry, ctx, None, {}, msa_by_src_guid, dropped)

    assert dropped == []
    assert guid_create_spy == []
    assert new_entry.MorphoSyntaxAnalysesOC == [already_created]
