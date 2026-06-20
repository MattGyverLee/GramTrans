"""T026: WSMapping 1:1 invariant (data-model.md E3)."""

from __future__ import annotations

import pytest

from gramtrans.Lib.models import WSKind, WSMapping, WSMappingEntry


def _entry(src: str, tgt: str, kind: WSKind = WSKind.VERNACULAR) -> WSMappingEntry:
    return WSMappingEntry(source_ws_id=src, source_ws_kind=kind, target_ws_id=tgt)


def test_one_to_one_mapping_passes() -> None:
    m = WSMapping(entries=(_entry("seh", "seh"), _entry("en", "en", WSKind.ANALYSIS)))
    assert m.required_for("seh") == _entry("seh", "seh")
    assert m.required_for("nonexistent") is None


def test_two_sources_to_one_target_rejected() -> None:
    with pytest.raises(ValueError, match="not 1:1"):
        WSMapping(entries=(_entry("seh", "shared"), _entry("seh-fonipa", "shared")))


def test_create_in_target_flag_preserved() -> None:
    entries = (
        WSMappingEntry(
            source_ws_id="seh-fonipa",
            source_ws_kind=WSKind.VERNACULAR,
            target_ws_id="seh-fonipa",
            create_in_target=True,
        ),
    )
    m = WSMapping(entries=entries)
    assert m.entries[0].create_in_target is True
