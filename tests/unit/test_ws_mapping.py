"""T028: WS-mapping validation (spec.md FR-011, contracts/module-ui.md).

These tests cover the pure-Python validator in `Lib/ws_mapping.py`. The
materialization step (creating WSs in the target when `create_in_target=True`)
is integration-level and lives under `tests/integration/`.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib.models import WSKind, WSMapping, WSMappingEntry
from gramtrans.Lib.ws_mapping import (
    WSMappingIncomplete,
    WSMappingOverspecified,
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
