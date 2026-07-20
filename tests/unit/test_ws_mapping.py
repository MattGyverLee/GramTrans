"""T028: WS-mapping validation (spec.md FR-011, contracts/module-ui.md).

These tests cover the pure-Python validator in `Lib/ws_mapping.py`. The
materialization step (creating WSs in the target when `create_in_target=True`)
is integration-level and lives under `tests/integration/`.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib.models import WSChoice, WSKind, WSMapping, WSMappingEntry
from gramtrans.Lib.ws_mapping import (
    WSMappingIncomplete,
    WSMappingOverspecified,
    default_ws_choices,
    detect_ws_mismatches,
    fold_choices_into_ws_mapping,
    is_complete,
    required_ws_set,
    validate,
)


def _entry(src: str, tgt: str, kind: WSKind = WSKind.VERNACULAR,
           create: bool = False) -> WSMappingEntry:
    return WSMappingEntry(
        source_ws_id=src,
        source_ws_kind=kind,
        target_ws_id=tgt,
        create_in_target=create,
    )


def test_complete_mapping_passes() -> None:
    m = WSMapping(entries=(_entry("seh", "seh"), _entry("en", "en", WSKind.ANALYSIS)))
    required = required_ws_set([("seh", WSKind.VERNACULAR), ("en", WSKind.ANALYSIS)])
    # Should not raise.
    validate(m, required)
    assert is_complete(m, required) is True


def test_incomplete_mapping_raises_with_missing_attribute() -> None:
    m = WSMapping(entries=(_entry("seh", "seh"),))
    required = required_ws_set([
        ("seh", WSKind.VERNACULAR),
        ("seh-fonipa", WSKind.VERNACULAR),
        ("en", WSKind.ANALYSIS),
    ])
    with pytest.raises(WSMappingIncomplete) as excinfo:
        validate(m, required)
    assert excinfo.value.missing == frozenset({
        ("seh-fonipa", WSKind.VERNACULAR),
        ("en", WSKind.ANALYSIS),
    })


def test_is_complete_returns_false_when_missing() -> None:
    m = WSMapping(entries=())
    required = required_ws_set([("seh", WSKind.VERNACULAR)])
    assert is_complete(m, required) is False


def test_kind_mismatch_treated_as_missing() -> None:
    """A mapping entry that maps `en` as VERNACULAR does NOT satisfy a
    requirement for `en` as ANALYSIS — different (id, kind) pairs."""
    m = WSMapping(entries=(_entry("en", "en", WSKind.VERNACULAR),))
    required = required_ws_set([("en", WSKind.ANALYSIS)])
    with pytest.raises(WSMappingIncomplete) as excinfo:
        validate(m, required)
    assert ("en", WSKind.ANALYSIS) in excinfo.value.missing


def test_overspecified_permissive_by_default() -> None:
    """Extras are tolerated when `strict_overspec` is False (default)."""
    m = WSMapping(entries=(_entry("seh", "seh"), _entry("seh-fonipa", "seh-fonipa")))
    required = required_ws_set([("seh", WSKind.VERNACULAR)])
    # Should not raise.
    validate(m, required)
    assert is_complete(m, required) is True


def test_overspecified_strict_raises() -> None:
    m = WSMapping(entries=(_entry("seh", "seh"), _entry("seh-fonipa", "seh-fonipa")))
    required = required_ws_set([("seh", WSKind.VERNACULAR)])
    with pytest.raises(WSMappingOverspecified) as excinfo:
        validate(m, required, strict_overspec=True)
    assert ("seh-fonipa", WSKind.VERNACULAR) in excinfo.value.extras


def test_empty_required_with_empty_mapping_passes() -> None:
    """A selection that touches zero WSs (e.g., transferring only objects
    with no string fields) needs no mapping."""
    m = WSMapping(entries=())
    required = required_ws_set([])
    validate(m, required)
    assert is_complete(m, required) is True


# ============================================================================
# Feature 032 US4 (T025) -- related-languages default correspondence
# ============================================================================

class _FakeWS:
    def __init__(self, id_, vernacular=True):
        self.Id = id_
        self.Handle = 0
        self.IsVernacular = vernacular


class _FakeWSCollection:
    def __init__(self, wses):
        self._wses = wses

    def GetAll(self):
        return list(self._wses)


class _FakeProject:
    def __init__(self, ws_list):
        self.WritingSystems = _FakeWSCollection(ws_list)


def _v(id_):
    return _FakeWS(id_, vernacular=True)


def _a(id_):
    return _FakeWS(id_, vernacular=False)


def test_default_prefills_primary_and_every_sub_clean_pair() -> None:
    """SC-004 / FR-012 / FR-013: a related-languages pair pre-fills
    primary->primary and every sub->sub by subtag suffix (incl.
    eja-fonipa->abc-fonipa across differing base subtags), and the resulting
    mapping confirms with NO manual edits."""
    source = _FakeProject([_v("eja"), _v("eja-fonipa"), _v("eja-Latn"), _a("en")])
    target = _FakeProject([_v("abc"), _v("abc-fonipa"), _v("abc-Latn"), _a("en")])

    choices = default_ws_choices(source, target)
    mapped = {c.source_ws_id: c.target_ws_id for c in choices}
    assert mapped == {
        "eja": "abc",              # primary -> primary (FR-012)
        "eja-fonipa": "abc-fonipa",  # sub -> sub by -fonipa suffix (FR-013)
        "eja-Latn": "abc-Latn",      # sub -> sub by -Latn suffix
    }
    # FR-014: every default is a real MAP to a concrete target WS; never CREATE/SKIP.
    assert all(c.choice == WSChoice.MAP for c in choices)

    # Confirms with no manual edits: folding the defaults satisfies every
    # required (mismatched) source WS.
    required = required_ws_set(
        (m.source_ws_id, m.source_ws_kind) for m in detect_ws_mismatches(source, target)
    )
    mapping = fold_choices_into_ws_mapping(choices, WSMapping(entries=()))
    assert is_complete(mapping, required) is True


def test_default_omits_identity_present_analysis_ws() -> None:
    """An analysis WS already present in the target by identity is not a
    mismatch and gets no default row."""
    source = _FakeProject([_v("eja"), _a("en")])
    target = _FakeProject([_v("abc"), _a("en")])
    choices = default_ws_choices(source, target)
    assert [c.source_ws_id for c in choices] == ["eja"]
