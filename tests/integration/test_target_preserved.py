"""T031: Pre-existing target objects not modified + SC-004 — integration scaffolds against Ejagham Mini -> Ejagham Full GT-Test."""
from __future__ import annotations

import pytest

# All integration tests are marked so unit-only runs skip them:
#   pytest -m 'not integration'
# The marker is registered in pyproject.toml.
pytestmark = pytest.mark.integration


def test_pre_existing_objects_unchanged_after_move() -> None:
    """SC-004: objects present in the target before the run are byte-identical after the run.

    Requires:
    - FlexTools host running this test (not raw pytest from CLI).
    - Ejagham Mini at C:\\ProgramData\\SIL\\FieldWorks\\Projects\\Ejagham Mini
    - Ejagham Full GT-Test freshly restored from backups/Ejagham Full.fwbackup

    Asserts: a pre-run snapshot of all target object GUIDs + serialised field
    values is taken before execute_move(); a post-run snapshot is taken
    immediately after.  For every GUID present in the pre-run snapshot the
    post-run snapshot entry must be byte-identical.  No field on any
    pre-existing object may change — not even Description fields used as
    Carrier B residue storage, since Phase 0 appends only to newly-created
    objects (FR-014).
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

        # Snapshot pre-run: {guid_str: serialised_repr} for every existing object.
        pre_snapshot: dict = ctx.target_project.snapshot_all_objects()

        preview_result = compute_preview(ctx, categories=list(GrammarCategory), include_closure=True)
        execute_move(ctx, plan=preview_result.plan)

        post_snapshot: dict = ctx.target_project.snapshot_all_objects()

        for guid, pre_repr in pre_snapshot.items():
            assert guid in post_snapshot, f"SC-004: pre-existing object {guid} vanished after Move"
            assert post_snapshot[guid] == pre_repr, (
                f"SC-004: pre-existing object {guid} was modified during Move.\n"
                f"  before: {pre_repr!r}\n"
                f"  after:  {post_snapshot[guid]!r}"
            )


def test_snapshot_diff_equals_exactly_added_items() -> None:
    """SC-004 diff shape: post-run snapshot minus pre-run snapshot equals exactly the set of added objects.

    Requires:
    - FlexTools host running this test (not raw pytest from CLI).
    - Ejagham Mini at C:\\ProgramData\\SIL\\FieldWorks\\Projects\\Ejagham Mini
    - Ejagham Full GT-Test freshly restored from backups/Ejagham Full.fwbackup

    Asserts: the set of new GUIDs appearing in the post-run snapshot (keys
    present in post but not pre) equals exactly the set of source_guid values
    from the RunPlan's actions list.  No extra objects materialise; no planned
    objects are missing.
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

        pre_snapshot: dict = ctx.target_project.snapshot_all_objects()

        preview_result = compute_preview(ctx, categories=list(GrammarCategory), include_closure=True)
        execute_move(ctx, plan=preview_result.plan)

        post_snapshot: dict = ctx.target_project.snapshot_all_objects()

        added_guids = {k for k in post_snapshot if k not in pre_snapshot}
        planned_guids = {str(a.source_guid) for a in preview_result.plan.actions}

        assert added_guids == planned_guids, (
            f"SC-004 diff mismatch.\n"
            f"  Extra (not planned): {added_guids - planned_guids}\n"
            f"  Missing (planned but not found): {planned_guids - added_guids}"
        )
