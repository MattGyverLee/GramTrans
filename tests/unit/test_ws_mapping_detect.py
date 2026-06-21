"""T032 -- detect_ws_mismatches + fold_choices_into_ws_mapping tests.

Spec: contracts/ws-wizard.md.
"""
from __future__ import annotations

from gramtrans.Lib.models import (
    WSChoice,
    WSKind,
    WSMapping,
    WSMappingChoice,
    WSMappingEntry,
    WSMismatch,
)
from gramtrans.Lib.ws_mapping import (
    detect_ws_mismatches,
    fold_choices_into_ws_mapping,
    _similarity_rank,
)


# ----------------------------------------------------------------------------
# Fake project surfaces
# ----------------------------------------------------------------------------

class _FakeWS:
    def __init__(self, id_, handle=0, vernacular=True):
        self.Id = id_
        self.Handle = handle
        self.IsVernacular = vernacular


class _FakeWSCollection:
    def __init__(self, wses):
        self._wses = wses

    def GetAll(self):
        return list(self._wses)


class _FakeProject:
    def __init__(self, ws_list):
        self.WritingSystems = _FakeWSCollection(ws_list)


def _v(id_, handle=0):
    return _FakeWS(id_, handle, vernacular=True)


def _a(id_, handle=0):
    return _FakeWS(id_, handle, vernacular=False)


# ============================================================================
# detect_ws_mismatches
# ============================================================================

def test_no_mismatch_when_identical():
    src = _FakeProject([_v("ko-Hang"), _a("en")])
    tgt = _FakeProject([_v("ko-Hang"), _a("en")])
    assert detect_ws_mismatches(src, tgt) == ()


def test_single_mismatch_returned():
    src = _FakeProject([_v("ko-x-Latn"), _a("en")])
    tgt = _FakeProject([_v("ko-Hang"), _a("en")])
    mismatches = detect_ws_mismatches(src, tgt)
    assert len(mismatches) == 1
    m = mismatches[0]
    assert m.source_ws_id == "ko-x-Latn"
    assert m.source_ws_kind == WSKind.VERNACULAR
    # ko-Hang is the only ko-* candidate; should be first
    assert m.target_ws_candidates[0] == "ko-Hang"


def test_multiple_mismatches_sorted_by_source_id():
    src = _FakeProject([_v("zzz-Custom"), _v("aaa-Custom"), _v("mmm-Custom"), _v("en")])
    tgt = _FakeProject([_v("en")])
    mismatches = detect_ws_mismatches(src, tgt)
    assert [m.source_ws_id for m in mismatches] == ["aaa-Custom", "mmm-Custom", "zzz-Custom"]


def test_candidates_sorted_by_similarity():
    src = _FakeProject([_v("ko-x-Latn")])
    tgt = _FakeProject([
        _v("fr"),         # rank 3 (unrelated)
        _v("ko-Hang"),    # rank 1 (same primary lang)
        _v("koh-Z"),      # rank 2 (same first 3 chars)
        _v("en"),         # rank 3
    ])
    mismatches = detect_ws_mismatches(src, tgt)
    assert len(mismatches) == 1
    candidates = mismatches[0].target_ws_candidates
    # ko-Hang should appear first (rank 1), koh-Z second (rank 2)
    assert candidates[0] == "ko-Hang"
    assert candidates[1] == "koh-Z"


def test_analysis_kind_preserved():
    src = _FakeProject([_a("xyz-temp")])
    tgt = _FakeProject([])
    mismatches = detect_ws_mismatches(src, tgt)
    assert len(mismatches) == 1
    assert mismatches[0].source_ws_kind == WSKind.ANALYSIS


def test_no_target_ws_yields_empty_candidates():
    src = _FakeProject([_v("ko-x-Latn")])
    tgt = _FakeProject([])
    mismatches = detect_ws_mismatches(src, tgt)
    assert mismatches[0].target_ws_candidates == ()


def test_none_source_returns_empty():
    """A None source has zero WSes -- nothing to mismatch against any target."""
    assert detect_ws_mismatches(None, _FakeProject([_v("en")])) == ()


def test_none_target_treats_every_source_ws_as_mismatch():
    """A None / empty target has no WSes -- every source WS is unmapped."""
    mismatches = detect_ws_mismatches(_FakeProject([_v("en"), _v("ko-Hang")]), None)
    assert len(mismatches) == 2
    assert all(m.target_ws_candidates == () for m in mismatches)


def test_similarity_rank_levels():
    assert _similarity_rank("ko-x-Latn", "ko-x-Latn") == 0
    assert _similarity_rank("ko-x-Latn", "ko-Hang") == 1
    assert _similarity_rank("koh-x-Latn", "koh-Hang") == 1  # same primary lang
    assert _similarity_rank("ko-x-Latn", "koh-Z") == 2  # 2-char prefix match
    assert _similarity_rank("ko-x-Latn", "fr") == 3


# ============================================================================
# fold_choices_into_ws_mapping
# ============================================================================

def test_fold_map_choice_creates_entry():
    base = WSMapping(entries=())
    choice = WSMappingChoice(
        source_ws_id="ko-x-Latn",
        source_ws_kind=WSKind.VERNACULAR,
        choice=WSChoice.MAP,
        target_ws_id="ko-Hang",
    )
    out = fold_choices_into_ws_mapping([choice], base)
    assert len(out.entries) == 1
    e = out.entries[0]
    assert e.source_ws_id == "ko-x-Latn"
    assert e.target_ws_id == "ko-Hang"
    assert e.create_in_target is False


def test_fold_create_choice_uses_identity_mapping():
    base = WSMapping(entries=())
    choice = WSMappingChoice(
        source_ws_id="xyz-temp",
        source_ws_kind=WSKind.VERNACULAR,
        choice=WSChoice.CREATE,
    )
    out = fold_choices_into_ws_mapping([choice], base)
    assert len(out.entries) == 1
    e = out.entries[0]
    assert e.source_ws_id == "xyz-temp"
    assert e.target_ws_id == "xyz-temp"
    assert e.create_in_target is True


def test_fold_skip_choice_does_not_create_entry():
    base = WSMapping(entries=())
    choice = WSMappingChoice(
        source_ws_id="dropped",
        source_ws_kind=WSKind.VERNACULAR,
        choice=WSChoice.SKIP,
    )
    out = fold_choices_into_ws_mapping([choice], base)
    assert out.entries == ()  # SKIP not folded


def test_fold_preserves_existing_entries():
    pre_existing = WSMappingEntry(
        source_ws_id="en",
        source_ws_kind=WSKind.ANALYSIS,
        target_ws_id="en",
        create_in_target=False,
    )
    base = WSMapping(entries=(pre_existing,))
    choice = WSMappingChoice(
        source_ws_id="ko-x-Latn",
        source_ws_kind=WSKind.VERNACULAR,
        choice=WSChoice.MAP,
        target_ws_id="ko-Hang",
    )
    out = fold_choices_into_ws_mapping([choice], base)
    assert len(out.entries) == 2
    assert pre_existing in out.entries


def test_fold_does_not_double_register():
    pre_existing = WSMappingEntry(
        source_ws_id="ko-x-Latn",
        source_ws_kind=WSKind.VERNACULAR,
        target_ws_id="ko-Hang",
        create_in_target=False,
    )
    base = WSMapping(entries=(pre_existing,))
    duplicate = WSMappingChoice(
        source_ws_id="ko-x-Latn",
        source_ws_kind=WSKind.VERNACULAR,
        choice=WSChoice.MAP,
        target_ws_id="ko-Hang",
    )
    out = fold_choices_into_ws_mapping([duplicate], base)
    assert len(out.entries) == 1
