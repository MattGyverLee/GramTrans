"""T033b / FR-020: target lock / read-only / unavailable detection.

FR-020 requires that a target which cannot be opened for exclusive write is
surfaced by ``api.bind_target`` as a ``TargetUnavailable`` (a clean, UI-showable
error) BEFORE any write — never as a raw flexicon/OS exception, and never
deferred to ``execute_move``.

The wrapping mechanism (open failure -> TargetUnavailable) is testable without
a live host by pointing bind_target at a target that cannot be opened: with
flexicon absent the import guard raises TargetUnavailable; with flexicon present
the OpenProject failure is caught and re-raised as TargetUnavailable. Either
way the contract holds, so ``test_unopenable_target_raises_target_unavailable``
runs in the ordinary suite.

The specific "target currently open in FLEx / directory ACL read-only"
scenarios need a real host + a deliberately-locked project, so they remain
host-gated skips.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib.api import (
    TargetCandidate,
    TargetUnavailable,
    bind_target,
    initialize_run,
)

pytestmark = pytest.mark.integration


def _source_stub():
    return initialize_run(
        object(),
        source_project_name="Ejagham Mini",
        source_project_path=r"C:\ProgramData\SIL\FieldWorks\Projects\Ejagham Mini",
    )


def test_unopenable_target_raises_target_unavailable() -> None:
    """FR-020 error-wrapping contract: a distinct target that cannot be opened
    surfaces as TargetUnavailable (not a raw exception), before any write."""
    stub = _source_stub()
    choice = TargetCandidate(
        project_name="No Such GramTrans Target",
        project_path=r"C:\ProgramData\SIL\FieldWorks\Projects\No Such GramTrans Target",
    )
    with pytest.raises(TargetUnavailable):
        bind_target(stub, choice)


@pytest.mark.skip(
    reason="Requires a live FLEx host with the target 'Ejagham Full GT-Test' "
    "simultaneously OPEN in FLEx (holding the LCM lock). Run manually under the "
    "host. bind_target must raise TargetUnavailable naming the project."
)
def test_target_open_in_flex_yields_target_unavailable() -> None:  # pragma: no cover
    """FR-020: a target held open for write by FLEx itself is refused at
    bind_target with a TargetUnavailable that names the project."""
    ...


@pytest.mark.skip(
    reason="Requires a live host + setting the target's project directory ACL "
    "read-only (icacls) before the run. Run manually. bind_target must surface "
    "the read-only open failure as TargetUnavailable, not a raw OSError."
)
def test_read_only_project_directory_yields_target_unavailable() -> None:  # pragma: no cover
    """FR-020: a read-only target directory surfaces as TargetUnavailable."""
    ...
