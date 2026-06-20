"""T030: Full-categories transfer + SC-001 timing — integration scaffolds against Ejagham Mini -> Ejagham Full GT-Test."""
from __future__ import annotations

import pytest

# All integration tests are marked so unit-only runs skip them:
#   pytest -m 'not integration'
# The marker is registered in pyproject.toml.
pytestmark = pytest.mark.integration


def test_main_window_shows_source_name() -> None:
    """Scenario A step 2: module launch shows 'Source: Ejagham Mini' in the main window header.

    Requires:
    - FlexTools host running this test (not raw pytest from CLI).
    - Ejagham Mini at C:\\ProgramData\\SIL\\FieldWorks\\Projects\\Ejagham Mini
    - Ejagham Full GT-Test freshly restored from backups/Ejagham Full.fwbackup

    Asserts: after MainWindow initialisation the source-label text contains
    'Ejagham Mini', confirming the host-project-as-source convention (spec Q2).
    """
    pytest.skip(
        "Integration test — requires FlexTools host. "
        "Run via FlexTools MCP `flextools_run_module` or under the host directly."
    )

    # --- body (never reached until host is wired) ---
    if False:
        from gramtrans.Lib.api import initialize_run, list_target_candidates  # noqa: F401

        ctx = initialize_run(source_project_name="Ejagham Mini")
        assert "Ejagham Mini" in ctx.source_project_name


def test_all_categories_toggle_and_preview() -> None:
    """Scenario A steps 3-8: all categories toggled ON, Preview returns PREVIEW_READY with non-zero planned counts.

    Requires:
    - FlexTools host running this test (not raw pytest from CLI).
    - Ejagham Mini at C:\\ProgramData\\SIL\\FieldWorks\\Projects\\Ejagham Mini
    - Ejagham Full GT-Test freshly restored from backups/Ejagham Full.fwbackup

    Asserts: compute_preview() returns status PREVIEW_READY and the resulting
    RunPlan contains at least one PlannedAction for each grammar category that
    has items in Ejagham Mini.  identity_remap must be empty (R6).
    """
    pytest.skip(
        "Integration test — requires FlexTools host. "
        "Run via FlexTools MCP `flextools_run_module` or under the host directly."
    )

    if False:
        from gramtrans.Lib.api import (  # noqa: F401
            bind_target,
            compute_preview,
            initialize_run,
        )
        from gramtrans.Lib.models import GrammarCategory, RunMode  # noqa: F401

        ctx = initialize_run(source_project_name="Ejagham Mini")
        bind_target(ctx, target_name="Ejagham Full GT-Test")
        result = compute_preview(ctx, categories=list(GrammarCategory), include_closure=True)
        assert result.status.name == "PREVIEW_READY"
        assert len(result.plan.actions) > 0
        assert result.plan.identity_remap == {}


def test_move_counts_match_preview_counts() -> None:
    """Scenario A steps 9-11: Move mode added counts equal the Preview 'would add' counts (SC-002 no-silent-loss).

    Requires:
    - FlexTools host running this test (not raw pytest from CLI).
    - Ejagham Mini at C:\\ProgramData\\SIL\\FieldWorks\\Projects\\Ejagham Mini
    - Ejagham Full GT-Test freshly restored from backups/Ejagham Full.fwbackup

    Asserts: for every GrammarCategory key, RunReport.per_category[cat].added
    (Move) equals the count of PlannedActions for that category from the Preview
    RunPlan — verifying FR-018 / SC-002 no-silent-drop invariant end-to-end.
    """
    pytest.skip(
        "Integration test — requires FlexTools host. "
        "Run via FlexTools MCP `flextools_run_module` or under the host directly."
    )

    if False:
        from gramtrans.Lib.api import (  # noqa: F401
            bind_target,
            compute_preview,
            execute_move,
            initialize_run,
        )
        from gramtrans.Lib.models import GrammarCategory  # noqa: F401

        ctx = initialize_run(source_project_name="Ejagham Mini")
        bind_target(ctx, target_name="Ejagham Full GT-Test")
        preview_result = compute_preview(ctx, categories=list(GrammarCategory), include_closure=True)
        report = execute_move(ctx, plan=preview_result.plan)

        for cat in GrammarCategory:
            preview_count = sum(
                1 for a in preview_result.plan.actions if a.category == cat
            )
            move_count = report.per_category[cat].added
            assert move_count == preview_count, (
                f"Category {cat.name}: preview said {preview_count} but Move added {move_count}"
            )


def test_move_wall_clock_under_five_minutes() -> None:
    """Scenario A step 10 / SC-001: full Move of <=100 pieces completes in under 5 minutes (300 s).

    Requires:
    - FlexTools host running this test (not raw pytest from CLI).
    - Ejagham Mini at C:\\ProgramData\\SIL\\FieldWorks\\Projects\\Ejagham Mini (<=100 grammar pieces)
    - Ejagham Full GT-Test freshly restored from backups/Ejagham Full.fwbackup

    Asserts: RunReport.wall_clock_seconds < 300 and total actions <= 100 (the
    benchmark ceiling per SC-001).
    """
    pytest.skip(
        "Integration test — requires FlexTools host. "
        "Run via FlexTools MCP `flextools_run_module` or under the host directly."
    )

    if False:
        from gramtrans.Lib.api import (  # noqa: F401
            bind_target,
            compute_preview,
            execute_move,
            initialize_run,
        )
        from gramtrans.Lib.models import GrammarCategory  # noqa: F401

        ctx = initialize_run(source_project_name="Ejagham Mini")
        bind_target(ctx, target_name="Ejagham Full GT-Test")
        preview_result = compute_preview(ctx, categories=list(GrammarCategory), include_closure=True)
        assert len(preview_result.plan.actions) <= 100, "Ejagham Mini exceeds SC-001 benchmark ceiling"
        report = execute_move(ctx, plan=preview_result.plan)
        assert report.wall_clock_seconds < 300, (
            f"SC-001 violated: Move took {report.wall_clock_seconds:.1f}s (limit 300s)"
        )


def test_residue_tags_and_no_dangling_refs_after_move() -> None:
    """Scenario A step 12-13: post-Move verification — tags present, GUIDs preserved, no dangling refs, no GOLD mutation.

    Requires:
    - FlexTools host running this test (not raw pytest from CLI).
    - Ejagham Mini at C:\\ProgramData\\SIL\\FieldWorks\\Projects\\Ejagham Mini
    - Ejagham Full GT-Test freshly restored from backups/Ejagham Full.fwbackup

    Asserts:
    - Every added object in the target carries a parseable ImportResidueTag (E5/Q5).
    - Every source GUID from the RunPlan appears in the target unchanged (R6).
    - RunReport.skips contains no entry with reason DANGLING_REF (SC-003).
    - RunReport.per_category sums satisfy FR-018 (no silent drops).
    """
    pytest.skip(
        "Integration test — requires FlexTools host. "
        "Run via FlexTools MCP `flextools_run_module` or under the host directly."
    )

    if False:
        from gramtrans.Lib.api import (  # noqa: F401
            bind_target,
            compute_preview,
            execute_move,
            initialize_run,
        )
        from gramtrans.Lib.models import GrammarCategory, SkipReason  # noqa: F401
        from gramtrans.Lib.residue import ImportResidueTag  # noqa: F401

        ctx = initialize_run(source_project_name="Ejagham Mini")
        bind_target(ctx, target_name="Ejagham Full GT-Test")
        preview_result = compute_preview(ctx, categories=list(GrammarCategory), include_closure=True)
        report = execute_move(ctx, plan=preview_result.plan)

        dangling = [s for s in report.skips if s.reason == SkipReason.DANGLING_REF]
        assert dangling == [], f"SC-003: dangling refs found after Move: {dangling}"

        total_added = sum(v.added for v in report.per_category.values())
        total_skipped = sum(v.skipped for v in report.per_category.values())
        assert total_added + total_skipped == len(preview_result.plan.actions) + len(
            preview_result.plan.skips
        ), "FR-018: item count mismatch between plan and report"
