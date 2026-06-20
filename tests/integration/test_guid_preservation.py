"""T034: R6 GUID preservation — integration scaffolds against Ejagham Mini -> Ejagham Full GT-Test."""
from __future__ import annotations

import pytest

# All integration tests are marked so unit-only runs skip them:
#   pytest -m 'not integration'
# The marker is registered in pyproject.toml.
pytestmark = pytest.mark.integration


def test_every_planned_guid_appears_in_target_unchanged() -> None:
    """R6: every source_guid from the RunPlan's actions appears in the target with that exact GUID after Move.

    Requires:
    - FlexTools host running this test (not raw pytest from CLI).
    - Ejagham Mini at C:\\ProgramData\\SIL\\FieldWorks\\Projects\\Ejagham Mini
    - Ejagham Full GT-Test freshly restored from backups/Ejagham Full.fwbackup

    Asserts: for every PlannedAction in the RunPlan, the target project contains
    an object whose GUID string equals str(action.source_guid).  No GUID
    remapping is expected for the Ejagham pair (identity_remap must be empty);
    if identity_remap is non-empty the test fails with an informative message
    listing the remapped pairs so the R6 assumption can be investigated.
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

        assert preview_result.plan.identity_remap == {}, (
            f"R6: unexpected identity_remap entries on the Ejagham pair: "
            f"{preview_result.plan.identity_remap}"
        )

        execute_move(ctx, plan=preview_result.plan)

        target_guids: set = ctx.target_project.all_object_guids()
        for action in preview_result.plan.actions:
            guid_str = str(action.source_guid)
            assert guid_str in target_guids, (
                f"R6: planned GUID {guid_str} ({action.category.name}) not found in target after Move"
            )


def test_no_identity_remap_entries_on_ejagham_pair() -> None:
    """R6 identity_remap: the RunPlan produced for the Ejagham pair carries no identity_remap entries.

    Requires:
    - FlexTools host running this test (not raw pytest from CLI).
    - Ejagham Mini at C:\\ProgramData\\SIL\\FieldWorks\\Projects\\Ejagham Mini
    - Ejagham Full GT-Test freshly restored from backups/Ejagham Full.fwbackup

    Asserts: preview_result.plan.identity_remap is an empty dict.  An
    identity_remap entry would mean a GUID collision was detected — the target
    already holds an object with that GUID — and the planner assigned a new
    GUID.  This MUST NOT happen on a freshly-restored target (the throwaway was
    never written to before the restore).  If this test fails, the restore
    procedure or the collision-detection logic needs investigation.
    """
    pytest.skip(
        "Integration test — requires FlexTools host. "
        "Run via FlexTools MCP `flextools_run_module` or under the host directly."
    )

    if False:
        from gramtrans.Lib.api import bind_target, compute_preview, initialize_run  # noqa: F401
        from gramtrans.Lib.models import GrammarCategory  # noqa: F401

        ctx = initialize_run(source_project_name="Ejagham Mini")
        bind_target(ctx, target_name="Ejagham Full GT-Test")
        preview_result = compute_preview(ctx, categories=list(GrammarCategory), include_closure=True)

        assert preview_result.plan.identity_remap == {}, (
            f"R6: identity_remap non-empty on freshly-restored target — "
            f"GUID collisions detected: {list(preview_result.plan.identity_remap.keys())}"
        )
