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
    default_ws_choices,
    detect_ws_mismatches,
    fold_choices_into_ws_mapping,
    is_complete,
    required_ws_set,
    _similarity_rank,
    _subtag_suffix,
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


# ============================================================================
# Feature 032 US4 (T026 / T029) -- ambiguity / no-correspondence -> unresolved
# ============================================================================

def _required(source, target):
    return required_ws_set(
        (m.source_ws_id, m.source_ws_kind) for m in detect_ws_mismatches(source, target)
    )


def _assert_row_gated(source, target, unresolved_src_id):
    """The unresolved source WS gets no default and keeps confirmation gated:
    folding the (non-CREATE/SKIP) defaults still leaves is_complete False."""
    choices = default_ws_choices(source, target)
    assert unresolved_src_id not in {c.source_ws_id for c in choices}
    # FR-014: a default is never CREATE/SKIP.
    assert all(c.choice == WSChoice.MAP for c in choices)
    mapping = fold_choices_into_ws_mapping(choices, WSMapping(entries=()))
    assert is_complete(mapping, _required(source, target)) is False


def test_subtag_suffix_relative_to_primary_base():
    assert _subtag_suffix("eja-fonipa", "eja") == "-fonipa"
    assert _subtag_suffix("eja", "eja") == ""
    # differing base language: suffix is everything after this id's own base
    assert _subtag_suffix("def-fonipa", "abc") == "-fonipa"


def test_default_target_no_primary_vernacular_leaves_primary_unresolved():
    """FR-015: target with no primary vernacular -> primary row unresolved."""
    source = _FakeProject([_v("eja"), _v("eja-fonipa")])
    target = _FakeProject([_a("en")])  # no vernacular WS at all
    assert default_ws_choices(source, target) == ()
    _assert_row_gated(source, target, "eja")


def test_default_no_target_sub_sharing_suffix_leaves_sub_unresolved():
    """FR-015: no target sub shares the source sub's suffix -> row unresolved
    (primary still pre-fills)."""
    source = _FakeProject([_v("eja"), _v("eja-fonipa")])
    target = _FakeProject([_v("abc"), _v("abc-Latn")])  # no -fonipa sub
    mapped = {c.source_ws_id: c.target_ws_id for c in default_ws_choices(source, target)}
    assert mapped == {"eja": "abc"}  # primary maps, sub does not
    _assert_row_gated(source, target, "eja-fonipa")


def test_default_multiple_target_subs_sharing_suffix_are_ambiguous():
    """FR-015: >1 target sub shares the suffix -> not unambiguous -> unresolved."""
    source = _FakeProject([_v("eja"), _v("eja-fonipa")])
    # abc-fonipa and def-fonipa both reduce to the -fonipa suffix -> ambiguous.
    target = _FakeProject([_v("abc"), _v("abc-fonipa"), _v("def-fonipa")])
    mapped = {c.source_ws_id: c.target_ws_id for c in default_ws_choices(source, target)}
    assert mapped == {"eja": "abc"}
    _assert_row_gated(source, target, "eja-fonipa")


def test_default_never_create_or_skip():
    """FR-014: even when a source WS has no correspondence, the defaulter never
    substitutes a CREATE or SKIP disposition -- it simply omits the row."""
    source = _FakeProject([_v("eja"), _v("eja-fonipa")])
    target = _FakeProject([_v("abc")])  # primary only, no subs
    for c in default_ws_choices(source, target):
        assert c.choice == WSChoice.MAP
