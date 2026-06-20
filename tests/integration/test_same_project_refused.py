"""T033: FR-019 same-source-and-target refusal — integration scaffold against Ejagham Mini."""
from __future__ import annotations

import pytest

# All integration tests are marked so unit-only runs skip them:
#   pytest -m 'not integration'
# The marker is registered in pyproject.toml.
pytestmark = pytest.mark.integration


def test_bind_target_with_same_project_raises() -> None:
    """FR-019: bind_target() raises SameProjectError when target name matches the source project name.

    Requires:
    - FlexTools host running this test (not raw pytest from CLI).
    - Ejagham Mini at C:\\ProgramData\\SIL\\FieldWorks\\Projects\\Ejagham Mini

    Asserts: calling api.bind_target(ctx, target_name='Ejagham Mini') when the
    source is also 'Ejagham Mini' raises gramtrans.Lib.api.SameProjectError
    (or the equivalent exception surfaced by the FR-019 guard in bind_target).
    No LCM open is attempted; no write is performed.

    Corresponds to quickstart.md Scenario D steps 1-3.
    """
    pytest.skip(
        "Integration test — requires FlexTools host. "
        "Run via FlexTools MCP `flextools_run_module` or under the host directly."
    )

    if False:
        from gramtrans.Lib.api import SameProjectError, bind_target, initialize_run  # noqa: F401

        ctx = initialize_run(source_project_name="Ejagham Mini")
        with pytest.raises(SameProjectError):
            bind_target(ctx, target_name="Ejagham Mini")
