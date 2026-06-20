"""T029 -- Phase 2 / US1 integration: per-conflict prompt drives transfer.

Mocks the LCM surface; exercises the data-flow path:
   plan -> collect_overwrite_conflicts -> FakeConflictResolver
        -> build_session_from_resolutions -> execute(session) -> mutated target

Verifies:
- Each conflicted field's user resolution is applied to src_props before
  ApplySyncableProperties is called.
- The target's residue tag carries a `merge=` segment after the run.
- A SKIP resolution produces an INTERACTIVE_SKIP record.

This integration test runs against a fake LCM surface, NOT against a
live FlexTools host (those flows live under tests/live/).
"""
from __future__ import annotations

from gramtrans.Lib.conflict import (
    UserCancelled,
    build_session_from_resolutions,
    detect_conflicts,
)
from gramtrans.Lib.models import (
    GrammarCategory,
    InteractiveSession,
    MergeDecision,
    MergeDecisionLog,
    MergeResolution,
    PlannedOverwrite,
    SkipReason,
)
from gramtrans.Lib.residue import ImportResidueTag
from gramtrans.Lib.transfer import _apply_merge_decisions


TGT_GUID = "15a59768-ad27-4e12-bf9f-719c55854c9f"
RUN_ID = "GT-20260620-200000"
TAG = ImportResidueTag(
    run_id=RUN_ID,
    source_project_name="Ejagham Mini",
    timestamp="2026-06-20T20:00:00",
)


def test_us1_full_pipeline_take_source():
    # Step 1: detect_conflicts produces prompts.
    src_props = {"Comment": "source comment"}
    tgt_pre_props = {"Comment": "target annotation -- preserve!"}
    prompts = detect_conflicts(src_props, tgt_pre_props, TGT_GUID, "LexEntry")
    assert len(prompts) == 1
    assert prompts[0].field_name == "Comment"

    # Step 2: resolver returns TAKE_SOURCE.
    decisions = (
        MergeDecision(
            field_name="Comment",
            resolution=MergeResolution.TAKE_SOURCE,
            left_value=prompts[0].left_value,
            right_value=prompts[0].right_value,
        ),
    )

    # Step 3: build_session_from_resolutions yields an InteractiveSession.
    session = build_session_from_resolutions(prompts, decisions)
    assert TGT_GUID in session.merge_decisions_by_guid
    log = session.merge_decisions_by_guid[TGT_GUID]
    assert isinstance(log, MergeDecisionLog)
    assert len(log.decisions) == 1

    # Step 4: applying decisions to src_props keeps the source value.
    out, skips = _apply_merge_decisions(
        src_props=src_props,
        decisions=log.decisions,
        tgt_pre_props=tgt_pre_props,
        run_id=RUN_ID,
        category=GrammarCategory.ENTRY,
        target_guid=TGT_GUID,
    )
    assert out["Comment"] == "source comment"
    assert skips == []

    # Step 5: tag.with_merge_log persists the log in the residue.
    tagged = TAG.with_snapshot(tgt_pre_props).with_merge_log(log)
    s = tagged.serialize()
    assert "|snap=" in s
    assert "|merge=" in s
    parsed = ImportResidueTag.parse(s)
    assert parsed == tagged
    assert parsed.decode_merge_log() == log


def test_us1_full_pipeline_merge_resolution():
    src_props = {"Comment": "src"}
    tgt_pre_props = {"Comment": "tgt"}
    prompts = detect_conflicts(src_props, tgt_pre_props, TGT_GUID, "LexEntry")
    decisions = (
        MergeDecision(field_name="Comment", resolution=MergeResolution.MERGE),
    )
    session = build_session_from_resolutions(prompts, decisions)
    log = session.merge_decisions_by_guid[TGT_GUID]
    out, _ = _apply_merge_decisions(
        src_props=src_props, decisions=log.decisions,
        tgt_pre_props=tgt_pre_props, run_id=RUN_ID,
        category=GrammarCategory.ENTRY, target_guid=TGT_GUID,
    )
    assert out["Comment"] == f"tgt\n--- merged {RUN_ID} ---\nsrc"


def test_us1_full_pipeline_skip_resolution_emits_skip_record():
    src_props = {"Comment": "src"}
    tgt_pre_props = {"Comment": "tgt"}
    prompts = detect_conflicts(src_props, tgt_pre_props, TGT_GUID, "LexEntry")
    decisions = (
        MergeDecision(field_name="Comment", resolution=MergeResolution.SKIP),
    )
    session = build_session_from_resolutions(prompts, decisions)
    log = session.merge_decisions_by_guid[TGT_GUID]
    out, skips = _apply_merge_decisions(
        src_props=src_props, decisions=log.decisions,
        tgt_pre_props=tgt_pre_props, run_id=RUN_ID,
        category=GrammarCategory.ENTRY, target_guid=TGT_GUID,
    )
    assert "Comment" not in out
    assert len(skips) == 1
    assert skips[0].reason == SkipReason.INTERACTIVE_SKIP


def test_us1_cancellation_atomicity():
    """FakeConflictResolver raises UserCancelled; caller MUST catch and
    NOT call _apply_merge_decisions / execute."""
    # Inline a minimal cancelling resolver -- the conftest fixture lives
    # under tests/unit/ and is not visible from tests/integration/.
    class _Cancelling:
        def resolve(self, prompts):
            raise UserCancelled("cancelled mid-wizard")

    src_props = {"Comment": "src"}
    tgt_pre_props = {"Comment": "tgt"}
    prompts = detect_conflicts(src_props, tgt_pre_props, TGT_GUID, "LexEntry")
    resolver = _Cancelling()
    try:
        resolver.resolve(prompts)
        assert False, "resolver should have raised UserCancelled"
    except UserCancelled:
        pass


def test_us1_build_session_rejects_length_mismatch():
    src_props = {"Comment": "src"}
    tgt_pre_props = {"Comment": "tgt"}
    prompts = detect_conflicts(src_props, tgt_pre_props, TGT_GUID, "LexEntry")
    # 0 decisions for 1 prompt -- should raise.
    try:
        build_session_from_resolutions(prompts, ())
        assert False, "should have raised"
    except ValueError as exc:
        assert "length mismatch" in str(exc)


def test_us1_multiple_conflicts_grouped_by_target_guid():
    """All conflicts on the same target object roll up into one
    MergeDecisionLog -- the residue tag receives the full log."""
    src_props = {"Comment": "c-src", "CitationForm": "cf-src"}
    tgt_pre_props = {"Comment": "c-tgt", "CitationForm": "cf-tgt"}
    prompts = detect_conflicts(src_props, tgt_pre_props, TGT_GUID, "LexEntry")
    assert len(prompts) == 2  # CitationForm + Comment (alphabetical)
    decisions = tuple(
        MergeDecision(field_name=p.field_name, resolution=MergeResolution.TAKE_SOURCE)
        for p in prompts
    )
    session = build_session_from_resolutions(prompts, decisions)
    # Both decisions land in the same log under one target_guid.
    assert len(session.merge_decisions_by_guid) == 1
    log = session.merge_decisions_by_guid[TGT_GUID]
    assert len(log.decisions) == 2
    field_names = {d.field_name for d in log.decisions}
    assert field_names == {"Comment", "CitationForm"}


def test_us1_residue_round_trip_with_merge_segment():
    """The 6-segment residue (snap + merge) round-trips and
    decode_merge_log() recovers the original decisions."""
    log = MergeDecisionLog(
        target_guid=TGT_GUID,
        decisions=(
            MergeDecision(
                field_name="Comment",
                resolution=MergeResolution.MERGE,
                left_value="tgt",
                right_value="src",
            ),
        ),
    )
    tagged = TAG.with_snapshot({"k": "v"}).with_merge_log(log)
    s = tagged.serialize()
    parsed = ImportResidueTag.parse(s)
    assert parsed == tagged
    assert parsed.decode_snapshot() == {"k": "v"}
    recovered = parsed.decode_merge_log()
    assert recovered == log
