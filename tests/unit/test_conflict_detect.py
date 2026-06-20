"""T019 -- detect_conflicts producer tests.

Spec: contracts/conflict-prompt.md (FR-201, FR-216).
"""
from __future__ import annotations

from gramtrans.Lib.conflict import detect_conflicts
from gramtrans.Lib.models import (
    MergeDecision,
    MergeDecisionLog,
    MergeResolution,
)


GUID = "15a59768-ad27-4e12-bf9f-719c55854c9f"


def test_identical_values_suppressed_fr216():
    src = {"Comment": "same", "CitationForm": "x"}
    tgt = {"Comment": "same", "CitationForm": "x"}
    assert detect_conflicts(src, tgt, GUID, "LexEntry") == ()


def test_missing_key_on_either_side_suppressed():
    """If a key is only on one side, Phase 1 source-wins or
    target-preserved applies -- no conflict."""
    src = {"Comment": "src-only", "Shared": "A"}
    tgt = {"Shared": "A", "TgtOnly": "tgt-only"}
    assert detect_conflicts(src, tgt, GUID, "LexEntry") == ()


def test_single_string_conflict_emits_prompt():
    src = {"Comment": "new"}
    tgt = {"Comment": "old"}
    prompts = detect_conflicts(src, tgt, GUID, "LexEntry")
    assert len(prompts) == 1
    p = prompts[0]
    assert p.target_guid == GUID
    assert p.target_class_name == "LexEntry"
    assert p.field_name == "Comment"
    assert p.left_value == "old"
    assert p.right_value == "new"
    assert p.prior_decision is None
    assert p.merge_eligible is True


def test_multiple_conflicts_sorted_by_field_name():
    src = {"Zebra": "z2", "Apple": "a2", "Mango": "m2"}
    tgt = {"Zebra": "z1", "Apple": "a1", "Mango": "m1"}
    prompts = detect_conflicts(src, tgt, GUID, "LexEntry")
    assert [p.field_name for p in prompts] == ["Apple", "Mango", "Zebra"]


def test_scalar_conflict_marks_not_merge_eligible():
    src = {"HomographNumber": 2}
    tgt = {"HomographNumber": 1}
    prompts = detect_conflicts(src, tgt, GUID, "LexEntry")
    assert len(prompts) == 1
    assert prompts[0].merge_eligible is False


def test_bool_conflict_marks_not_merge_eligible():
    src = {"DoNotPublishInRC": True}
    tgt = {"DoNotPublishInRC": False}
    prompts = detect_conflicts(src, tgt, GUID, "LexEntry")
    assert len(prompts) == 1
    assert prompts[0].merge_eligible is False


def test_multistring_dict_conflict_is_merge_eligible():
    src = {"Form": {"en": "src", "fr": "fr-src"}}
    tgt = {"Form": {"en": "tgt", "fr": "fr-src"}}
    prompts = detect_conflicts(src, tgt, GUID, "MoAffixAllomorph")
    assert len(prompts) == 1
    assert prompts[0].merge_eligible is True


def test_list_conflict_is_merge_eligible():
    src = {"Tags": ["a", "b", "c"]}
    tgt = {"Tags": ["a", "b"]}
    prompts = detect_conflicts(src, tgt, GUID, "LexEntry")
    assert len(prompts) == 1
    assert prompts[0].merge_eligible is True


def test_prior_log_attaches_prior_decision():
    src = {"Comment": "new"}
    tgt = {"Comment": "old"}
    prior = MergeDecisionLog(
        target_guid=GUID,
        decisions=(
            MergeDecision(
                field_name="Comment",
                resolution=MergeResolution.MERGE,
                left_value="old",
                right_value="new",
                prior_run_id="GT-20260101-120000",
            ),
        ),
    )
    prompts = detect_conflicts(src, tgt, GUID, "LexEntry", prior_log=prior)
    assert prompts[0].prior_decision is not None
    assert prompts[0].prior_decision.resolution == MergeResolution.MERGE
    assert prompts[0].prior_decision.prior_run_id == "GT-20260101-120000"


def test_prior_log_with_no_matching_field_leaves_prior_decision_none():
    src = {"Comment": "new"}
    tgt = {"Comment": "old"}
    prior = MergeDecisionLog(
        target_guid=GUID,
        decisions=(
            MergeDecision(field_name="UnrelatedField", resolution=MergeResolution.SKIP),
        ),
    )
    prompts = detect_conflicts(src, tgt, GUID, "LexEntry", prior_log=prior)
    assert prompts[0].prior_decision is None


def test_non_dict_inputs_return_empty():
    assert detect_conflicts(None, {}, GUID, "LexEntry") == ()
    assert detect_conflicts({}, None, GUID, "LexEntry") == ()
    assert detect_conflicts("not a dict", {}, GUID, "LexEntry") == ()


def test_empty_inputs_return_empty():
    assert detect_conflicts({}, {}, GUID, "LexEntry") == ()
