"""T033 / FR-019: same-source-and-target refusal.

Unlike the other integration scaffolds in this directory, the FR-019 guard in
``api.bind_target`` runs BEFORE any flexicon/LCM open (it is a pure
name/path comparison on the stub), so this test needs no FlexTools host and
runs in the ordinary unit-inclusive suite. It is still tagged ``integration``
for topic grouping, but it does not skip.

Corresponds to quickstart.md Scenario D.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib.api import (
    SameProjectError,
    TargetCandidate,
    bind_target,
    initialize_run,
)

pytestmark = pytest.mark.integration


_SOURCE_NAME = "Ejagham Mini"
_SOURCE_PATH = r"C:\ProgramData\SIL\FieldWorks\Projects\Ejagham Mini"


def _stub():
    """A RunContextStub for a source; host_handle is never touched by the
    FR-019 guard, so a placeholder object is fine."""
    return initialize_run(
        object(),
        source_project_name=_SOURCE_NAME,
        source_project_path=_SOURCE_PATH,
    )


def test_bind_target_same_name_raises() -> None:
    """bind_target refuses when the target NAME equals the source name
    (FR-019, first guard branch) — no LCM open attempted."""
    stub = _stub()
    choice = TargetCandidate(
        project_name=_SOURCE_NAME,
        project_path=r"C:\somewhere\else\Ejagham Mini",
    )
    with pytest.raises(SameProjectError):
        bind_target(stub, choice)


def test_bind_target_same_path_raises() -> None:
    """bind_target refuses when a differently-named candidate resolves to the
    same on-disk PATH as the source (FR-019, second guard branch)."""
    stub = _stub()
    choice = TargetCandidate(
        project_name="A Different Name",
        # Same path, trailing-slash + case variation to exercise normcase/rstrip.
        project_path=_SOURCE_PATH.upper() + "\\",
    )
    with pytest.raises(SameProjectError):
        bind_target(stub, choice)


def test_bind_target_distinct_project_passes_the_fr019_guard() -> None:
    """A genuinely distinct target clears the FR-019 guard. We assert the
    refusal does NOT fire; the subsequent LCM open is out of scope here
    (it raises TargetUnavailable without a host, which is the *next* stage)."""
    from gramtrans.Lib.api import TargetUnavailable

    stub = _stub()
    choice = TargetCandidate(
        project_name="Ejagham Full GT-Test",
        project_path=r"C:\ProgramData\SIL\FieldWorks\Projects\Ejagham Full GT-Test",
    )
    # Past the guard, bind_target tries to open the target. Without a live
    # host/flexicon that surfaces as TargetUnavailable — crucially NOT
    # SameProjectError. If flexicon *is* present the open may raise something
    # else; either way SameProjectError must not be raised.
    try:
        bind_target(stub, choice)
    except SameProjectError:  # pragma: no cover - would be an FR-019 defect
        pytest.fail("FR-019 guard wrongly refused a distinct target")
    except TargetUnavailable:
        pass  # expected without a live target
    except Exception:  # noqa: BLE001 - any non-FR019 open error is acceptable here
        pass
