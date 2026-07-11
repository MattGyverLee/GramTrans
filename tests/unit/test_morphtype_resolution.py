"""Unit tests for `_resolve_target_morph_type` (allomorph MorphTypeRA re-wiring).

Regression coverage for the morph-type-loss bug: flexicon's generic
`ApplySyncableProperties` emits `MorphTypeRA` as a GUID string and its apply-loop
silently drops object-reference properties, so the closure walker
(`_walk_entry_allomorphs`) must re-wire the reference explicitly by resolving the
source GUID against the target's global MorphTypes list. This exercises the pure
resolver host-free (lowercase `.guid` fakes, matching the sibling Phase 3c tests).
"""
from __future__ import annotations

from types import SimpleNamespace

from gramtrans.Lib import categories


class _MT:
    """Morph-type fake: lowercase `.guid` (so `_guid_str_from` works host-free)
    plus an optional nested `SubPossibilitiesOS`."""

    def __init__(self, guid: str, subs=None) -> None:
        self.guid = guid
        self.SubPossibilitiesOS = subs or []


def _target_with_morph_types(possibilities):
    """Build a duck-typed target exposing
    Cache.LangProject.LexDbOA.MorphTypesOA.PossibilitiesOS."""
    return SimpleNamespace(
        Cache=SimpleNamespace(
            LangProject=SimpleNamespace(
                LexDbOA=SimpleNamespace(
                    MorphTypesOA=SimpleNamespace(PossibilitiesOS=possibilities)
                )
            )
        )
    )


def test_resolves_flat_morph_type_by_guid():
    stem = _MT("11111111-1111-1111-1111-111111111111")
    suffix = _MT("22222222-2222-2222-2222-222222222222")
    target = _target_with_morph_types([stem, suffix])

    assert categories._resolve_target_morph_type(
        target, "22222222-2222-2222-2222-222222222222"
    ) is suffix


def test_resolves_nested_sub_possibility():
    leaf = _MT("33333333-3333-3333-3333-333333333333")
    parent = _MT("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", subs=[leaf])
    target = _target_with_morph_types([parent])

    assert categories._resolve_target_morph_type(
        target, "33333333-3333-3333-3333-333333333333"
    ) is leaf


def test_missing_guid_returns_none():
    target = _target_with_morph_types([_MT("11111111-1111-1111-1111-111111111111")])
    assert categories._resolve_target_morph_type(
        target, "99999999-9999-9999-9999-999999999999"
    ) is None


def test_empty_guid_returns_none():
    target = _target_with_morph_types([_MT("11111111-1111-1111-1111-111111111111")])
    assert categories._resolve_target_morph_type(target, "") is None


def test_missing_morph_types_list_returns_none():
    # Target that raises AttributeError walking to MorphTypesOA -> None, not crash.
    target = SimpleNamespace(Cache=SimpleNamespace(LangProject=object()))
    assert categories._resolve_target_morph_type(
        target, "11111111-1111-1111-1111-111111111111"
    ) is None


# --- StatusRA sibling (same bug class, resolved against LangProject.StatusOA) ---

def _target_with_status(possibilities):
    return SimpleNamespace(
        Cache=SimpleNamespace(
            LangProject=SimpleNamespace(
                StatusOA=SimpleNamespace(PossibilitiesOS=possibilities)
            )
        )
    )


def test_resolves_status_by_guid():
    confirmed = _MT("cccccccc-cccc-cccc-cccc-cccccccccccc")
    tentative = _MT("dddddddd-dddd-dddd-dddd-dddddddddddd")
    target = _target_with_status([confirmed, tentative])
    assert categories._resolve_target_status(
        target, "dddddddd-dddd-dddd-dddd-dddddddddddd"
    ) is tentative


def test_status_missing_guid_returns_none():
    target = _target_with_status([_MT("cccccccc-cccc-cccc-cccc-cccccccccccc")])
    # Custom/unknown status guid does not resolve -> None (reference left unset).
    assert categories._resolve_target_status(
        target, "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    ) is None


def test_status_missing_list_returns_none():
    target = SimpleNamespace(Cache=SimpleNamespace(LangProject=object()))
    assert categories._resolve_target_status(
        target, "cccccccc-cccc-cccc-cccc-cccccccccccc"
    ) is None
