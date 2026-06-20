"""T020 -- _deterministic_merge semantics tests (research.md R4)."""
from __future__ import annotations

import pytest

from gramtrans.Lib.conflict import _deterministic_merge, _MergeNotEligible


RUN_ID = "GT-20260620-180000"


def test_string_merge_uses_separator_with_run_id():
    out = _deterministic_merge("left", "right", RUN_ID)
    assert out == f"left\n--- merged {RUN_ID} ---\nright"
    # The run_id appears literally so re-merging produces distinguishable output
    assert RUN_ID in out


def test_string_merge_is_deterministic_same_inputs_same_output():
    a = _deterministic_merge("x", "y", RUN_ID)
    b = _deterministic_merge("x", "y", RUN_ID)
    assert a == b


def test_dict_multistring_merge_per_key():
    """Dict-shaped multistrings recurse per writing system."""
    left = {"en": "EN-left", "fr": "fr-only"}
    right = {"en": "EN-right", "de": "de-only"}
    out = _deterministic_merge(left, right, RUN_ID)
    assert set(out.keys()) == {"en", "fr", "de"}
    assert out["en"] == f"EN-left\n--- merged {RUN_ID} ---\nEN-right"
    assert out["fr"] == "fr-only"  # left-only passes through
    assert out["de"] == "de-only"  # right-only passes through


def test_list_merge_is_set_union_preserving_order():
    out = _deterministic_merge(["a", "b"], ["b", "c"], RUN_ID)
    assert out == ["a", "b", "c"]


def test_tuple_merge_returns_tuple():
    out = _deterministic_merge(("a", "b"), ("b", "c"), RUN_ID)
    assert out == ("a", "b", "c")
    assert isinstance(out, tuple)


def test_set_merge_returns_set():
    out = _deterministic_merge({"a", "b"}, {"b", "c"}, RUN_ID)
    assert out == {"a", "b", "c"}
    assert isinstance(out, set)


def test_int_scalar_rejected():
    with pytest.raises(_MergeNotEligible):
        _deterministic_merge(1, 2, RUN_ID)


def test_bool_scalar_rejected():
    with pytest.raises(_MergeNotEligible):
        _deterministic_merge(True, False, RUN_ID)


def test_none_rejected():
    with pytest.raises(_MergeNotEligible):
        _deterministic_merge(None, "x", RUN_ID)
    with pytest.raises(_MergeNotEligible):
        _deterministic_merge("x", None, RUN_ID)


def test_already_merged_value_remerges_with_new_run_id():
    """research.md R4 idempotency: a re-merge embeds the new run_id,
    so the user can distinguish nested merges in audit."""
    once = _deterministic_merge("a", "b", "GT-20260101-000000")
    twice = _deterministic_merge(once, "c", "GT-20260202-000000")
    # The original separator survives; new separator embeds new run_id.
    assert "GT-20260101-000000" in twice
    assert "GT-20260202-000000" in twice


def test_mixed_types_fallback_to_repr_merge():
    """A list vs a string falls back to repr-based string concat."""
    out = _deterministic_merge(["a", "b"], "string", RUN_ID)
    assert isinstance(out, str)
    assert RUN_ID in out
