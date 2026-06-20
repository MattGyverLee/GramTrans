"""T023: serialize/parse round-trip for ImportResidueTag (data-model.md E5)."""

from __future__ import annotations

import pytest

from gramtrans.Lib.residue import ImportResidueTag


VALID = ImportResidueTag(
    run_id="GT-20260619-140000",
    source_project_name="Ejagham Mini",
    timestamp="2026-06-19T14:00:00",
)


def test_serialize_format() -> None:
    assert VALID.serialize() == (
        "GT|GT-20260619-140000|Ejagham Mini|2026-06-19T14:00:00"
    )


def test_round_trip_carrier_a() -> None:
    s = VALID.serialize()
    parsed = ImportResidueTag.parse(s)
    assert parsed == VALID


def test_round_trip_carrier_b() -> None:
    # Carrier B layout: existing prose, blank line, marker line.
    description_value = (
        "Existing user prose about this category.\n"
        "Could be multi-line.\n"
        "\n"
        f"[GT-Tag]: {VALID.serialize()}"
    )
    parsed = ImportResidueTag.parse(description_value)
    assert parsed == VALID


def test_parse_returns_none_for_garbage() -> None:
    assert ImportResidueTag.parse("") is None
    assert ImportResidueTag.parse("not a tag") is None
    assert ImportResidueTag.parse("GT|wrong|format") is None


def test_run_id_must_match_pattern() -> None:
    with pytest.raises(ValueError):
        ImportResidueTag(
            run_id="bad",
            source_project_name="x",
            timestamp="2026-06-19T14:00:00",
        )


def test_run_id_must_match_timestamp() -> None:
    with pytest.raises(ValueError):
        ImportResidueTag(
            run_id="GT-20260619-140000",
            source_project_name="x",
            timestamp="2030-01-01T00:00:00",
        )


def test_carrier_b_picks_last_marker_when_multiple_runs_present() -> None:
    # Two runs have appended; the second is the most recent.
    earlier = "GT|GT-20260101-090000|EarlierProj|2026-01-01T09:00:00"
    later = VALID.serialize()
    value = (
        "User prose\n"
        "\n"
        f"[GT-Tag]: {earlier}\n"
        f"[GT-Tag]: {later}"
    )
    parsed = ImportResidueTag.parse(value)
    assert parsed == VALID
