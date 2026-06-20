"""T062: Residue tag readable + parseable in target — integration scaffolds against Ejagham Mini -> Ejagham Full GT-Test."""
from __future__ import annotations

import pytest

# All integration tests are marked so unit-only runs skip them:
#   pytest -m 'not integration'
# The marker is registered in pyproject.toml.
pytestmark = pytest.mark.integration


def test_every_added_object_has_readable_residue_tag() -> None:
    """US2 Acceptance 3 / FR-010 / Q5: every object added by Move has a non-empty residue tag readable from the target.

    Requires:
    - FlexTools host running this test (not raw pytest from CLI).
    - Ejagham Mini at C:\\ProgramData\\SIL\\FieldWorks\\Projects\\Ejagham Mini
    - Ejagham Full GT-Test freshly restored from backups/Ejagham Full.fwbackup

    Asserts: for every source_guid in the RunPlan's actions list, the
    corresponding object in the target has a non-empty residue carrier
    (LiftResidue for classes that support Carrier A, or a Description line
    prefixed with '[GT-Tag]:' for classes using Carrier B per data-model.md E5
    / research.md R11).  An empty or missing tag on any added object is a
    FR-010 violation.
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
        from gramtrans.Lib.residue import read_residue_carrier  # noqa: F401

        ctx = initialize_run(source_project_name="Ejagham Mini")
        bind_target(ctx, target_name="Ejagham Full GT-Test")
        preview_result = compute_preview(ctx, categories=list(GrammarCategory), include_closure=True)
        execute_move(ctx, plan=preview_result.plan)

        for action in preview_result.plan.actions:
            guid_str = str(action.source_guid)
            target_obj = ctx.target_project.get_object_by_guid(guid_str)
            assert target_obj is not None, f"FR-010: added object {guid_str} not found in target"

            raw_tag = read_residue_carrier(target_obj)
            assert raw_tag, (
                f"FR-010: added object {guid_str} ({action.category.name}) "
                f"has no residue tag in target"
            )


def test_residue_tag_parse_round_trips() -> None:
    """FR-010 / Q5 round-trip: ImportResidueTag.parse() succeeds for every tag written by Move, and fields are populated.

    Requires:
    - FlexTools host running this test (not raw pytest from CLI).
    - Ejagham Mini at C:\\ProgramData\\SIL\\FieldWorks\\Projects\\Ejagham Mini
    - Ejagham Full GT-Test freshly restored from backups/Ejagham Full.fwbackup

    Asserts: for every added object in the target, the raw residue string read
    from its carrier field:
    1. Parses without raising via ImportResidueTag.parse(raw_tag).
    2. The parsed tag's run_id matches the run context's run_id.
    3. The parsed tag's source_project_name equals 'Ejagham Mini'.
    4. The parsed tag's iso_timestamp is a non-empty ISO-8601 string.
    This verifies the serialize/parse contract end-to-end on live LCM data
    (not just the unit-level round-trip in tests/unit/test_residue_format.py).
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
        from gramtrans.Lib.residue import ImportResidueTag, read_residue_carrier  # noqa: F401

        ctx = initialize_run(source_project_name="Ejagham Mini")
        bind_target(ctx, target_name="Ejagham Full GT-Test")
        preview_result = compute_preview(ctx, categories=list(GrammarCategory), include_closure=True)
        report = execute_move(ctx, plan=preview_result.plan)

        for action in preview_result.plan.actions:
            guid_str = str(action.source_guid)
            target_obj = ctx.target_project.get_object_by_guid(guid_str)
            raw_tag = read_residue_carrier(target_obj)

            parsed = ImportResidueTag.parse(raw_tag)
            assert parsed is not None, (
                f"T062: ImportResidueTag.parse() returned None for object "
                f"{guid_str} ({action.category.name}). Raw: {raw_tag!r}"
            )
            assert parsed.run_id == report.run_id, (
                f"T062: run_id mismatch on {guid_str}: "
                f"tag has {parsed.run_id!r}, report has {report.run_id!r}"
            )
            assert parsed.source_project_name == "Ejagham Mini", (
                f"T062: source_project_name wrong on {guid_str}: {parsed.source_project_name!r}"
            )
            assert parsed.iso_timestamp, (
                f"T062: iso_timestamp empty on {guid_str}"
            )
