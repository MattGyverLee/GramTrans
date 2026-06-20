"""T022 -- _apply_merge_decisions executor-side filter tests.

Spec: research.md R3 (FR-202..205).
"""
from __future__ import annotations

from gramtrans.Lib.models import (
    GrammarCategory,
    MergeDecision,
    MergeResolution,
    SkipReason,
)
from gramtrans.Lib.transfer import _apply_merge_decisions


RUN_ID = "GT-20260620-180000"
GUID = "15a59768-ad27-4e12-bf9f-719c55854c9f"


def _call(src, tgt, decisions):
    return _apply_merge_decisions(
        src_props=src,
        decisions=decisions,
        tgt_pre_props=tgt,
        run_id=RUN_ID,
        category=GrammarCategory.ENTRY,
        target_guid=GUID,
    )


def test_take_source_leaves_value_unchanged():
    src = {"Comment": "src"}
    tgt = {"Comment": "tgt"}
    decisions = [MergeDecision(field_name="Comment", resolution=MergeResolution.TAKE_SOURCE)]
    out, skips = _call(src, tgt, decisions)
    assert out == {"Comment": "src"}
    assert skips == []


def test_keep_target_drops_key():
    src = {"Comment": "src", "Other": "x"}
    tgt = {"Comment": "tgt"}
    decisions = [MergeDecision(field_name="Comment", resolution=MergeResolution.KEEP_TARGET)]
    out, skips = _call(src, tgt, decisions)
    assert "Comment" not in out
    assert out["Other"] == "x"  # untouched keys preserved
    assert skips == []


def test_merge_replaces_with_deterministic_combination():
    src = {"Comment": "right"}
    tgt = {"Comment": "left"}
    decisions = [MergeDecision(field_name="Comment", resolution=MergeResolution.MERGE)]
    out, skips = _call(src, tgt, decisions)
    assert out["Comment"] == f"left\n--- merged {RUN_ID} ---\nright"
    assert skips == []


def test_merge_on_scalar_falls_back_to_take_source():
    """Scalars are not merge-eligible; the filter silently keeps src value."""
    src = {"HomographNumber": 2}
    tgt = {"HomographNumber": 1}
    decisions = [MergeDecision(field_name="HomographNumber", resolution=MergeResolution.MERGE)]
    out, skips = _call(src, tgt, decisions)
    assert out["HomographNumber"] == 2  # source preserved
    assert skips == []


def test_skip_drops_key_and_emits_skip_record():
    src = {"Comment": "src"}
    tgt = {"Comment": "tgt"}
    decisions = [MergeDecision(field_name="Comment", resolution=MergeResolution.SKIP)]
    out, skips = _call(src, tgt, decisions)
    assert "Comment" not in out
    assert len(skips) == 1
    assert skips[0].reason == SkipReason.INTERACTIVE_SKIP
    assert skips[0].category == GrammarCategory.ENTRY
    assert skips[0].source_guid == GUID


def test_edit_custom_replaces_with_user_value():
    src = {"Comment": "src"}
    tgt = {"Comment": "tgt"}
    decisions = [
        MergeDecision(
            field_name="Comment",
            resolution=MergeResolution.EDIT_CUSTOM,
            custom_value="user-typed",
        )
    ]
    out, skips = _call(src, tgt, decisions)
    assert out["Comment"] == "user-typed"
    assert skips == []


def test_multiple_decisions_all_applied():
    src = {"A": "src-a", "B": "src-b", "C": "src-c", "D": "src-d", "E": "src-e"}
    tgt = {"A": "tgt-a", "B": "tgt-b", "C": "tgt-c", "D": "tgt-d", "E": "tgt-e"}
    decisions = [
        MergeDecision(field_name="A", resolution=MergeResolution.TAKE_SOURCE),
        MergeDecision(field_name="B", resolution=MergeResolution.KEEP_TARGET),
        MergeDecision(field_name="C", resolution=MergeResolution.MERGE),
        MergeDecision(field_name="D", resolution=MergeResolution.SKIP),
        MergeDecision(
            field_name="E", resolution=MergeResolution.EDIT_CUSTOM, custom_value="EE",
        ),
    ]
    out, skips = _call(src, tgt, decisions)
    assert out["A"] == "src-a"
    assert "B" not in out
    assert RUN_ID in out["C"]
    assert "D" not in out
    assert out["E"] == "EE"
    assert len(skips) == 1
    assert skips[0].detail.endswith(f"'D' on {GUID[:8]}")


def test_returns_new_dict_does_not_mutate_input():
    src = {"X": "a"}
    tgt = {"X": "b"}
    decisions = [MergeDecision(field_name="X", resolution=MergeResolution.KEEP_TARGET)]
    out, _ = _call(src, tgt, decisions)
    assert out is not src
    assert "X" in src  # input unchanged


def test_empty_decisions_returns_unchanged():
    src = {"A": "1", "B": "2"}
    tgt = {"A": "9"}
    out, skips = _call(src, tgt, [])
    assert out == src
    assert skips == []


def test_non_dict_src_passes_through():
    out, skips = _apply_merge_decisions(
        src_props=None,
        decisions=[MergeDecision(field_name="X", resolution=MergeResolution.SKIP)],
        tgt_pre_props={},
        run_id=RUN_ID,
        category=GrammarCategory.ENTRY,
        target_guid=GUID,
    )
    assert out is None
    assert skips == []
