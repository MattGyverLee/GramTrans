"""T024: Regression tests for apply_carrier_b direct-attribute access.

Bug fixed 2026-06-19: the old code cast obj to ICmPossibility before accessing
.Description, which raises TypeError for IMoInflAffixTemplate and other
grammar-piece interfaces that expose .Description directly but are not
ICmPossibility-castable. Fix uses getattr(obj, "Description") instead.

These tests exercise apply_carrier_b without any LCM/FlexTools imports by
using duck-typed fakes.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib.residue import ImportResidueTag, apply_carrier_b


TAG = ImportResidueTag.make(
    run_id="GT-20260619-140000",
    source_project_name="Ejagham Mini",
    timestamp="2026-06-19T14:00:00",
)
WS = "ws-handle"


class _FakeMultiString:
    """Fake LCM multistring that records set_String calls."""

    def __init__(self, initial_text: str = "") -> None:
        self._text = initial_text
        self.set_calls: list[tuple] = []

    def get_String(self, ws):  # noqa: N802 — mirrors LCM naming
        return self

    @property
    def Text(self) -> str:
        return self._text

    def set_String(self, ws, value: str) -> None:  # noqa: N802
        self.set_calls.append((ws, value))
        self._text = value


class _FakeObjWithDescription:
    """Duck-typed stand-in for an LCM object that exposes .Description."""

    def __init__(self, initial_text: str = "") -> None:
        self.Description = _FakeMultiString(initial_text)


class _FakeObjWithoutDescription:
    """Duck-typed stand-in for an LCM object that has no .Description."""

    pass


# ---------------------------------------------------------------------------
# Test 1: direct attribute access — no ICmPossibility cast required
# ---------------------------------------------------------------------------

def test_apply_carrier_b_writes_to_obj_description_via_direct_attribute() -> None:
    """apply_carrier_b writes via direct .Description access, not ICmPossibility cast."""
    fake = _FakeObjWithDescription()
    apply_carrier_b(fake, ws=WS, tag=TAG)

    ms = fake.Description
    assert len(ms.set_calls) == 1, "set_String should be called exactly once"

    _, written_value = ms.set_calls[0]
    expected_suffix = f"[GT-Tag]: {TAG.serialize()}"
    assert written_value.endswith(expected_suffix), (
        f"Written value should end with tag line; got: {written_value!r}"
    )


# ---------------------------------------------------------------------------
# Test 2: TypeError when object has no Description attribute
# ---------------------------------------------------------------------------

def test_apply_carrier_b_raises_typeerror_when_obj_has_no_description() -> None:
    """apply_carrier_b raises TypeError for objects without .Description."""
    fake = _FakeObjWithoutDescription()
    with pytest.raises(TypeError, match="has no Description attribute"):
        apply_carrier_b(fake, ws=WS, tag=TAG)


# ---------------------------------------------------------------------------
# Test 3: existing prose is preserved, tag appended after blank-line separator
# ---------------------------------------------------------------------------

def test_apply_carrier_b_preserves_existing_description_prose() -> None:
    """Existing Description text is kept; tag is appended after a blank line."""
    existing_prose = "Existing prose here."
    fake = _FakeObjWithDescription(initial_text=existing_prose)
    apply_carrier_b(fake, ws=WS, tag=TAG)

    _, written_value = fake.Description.set_calls[0]
    expected = f"Existing prose here.\n\n[GT-Tag]: {TAG.serialize()}"
    assert written_value == expected, (
        f"Expected exact value {expected!r}, got {written_value!r}"
    )
