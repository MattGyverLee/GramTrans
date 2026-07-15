"""T031: Pre-existing target objects preserved across a Move (SC-004).

Rewritten from the original fictional-API scaffold to drive the REAL engine
through the shared live harness. Mirrors the guard + harness pattern from
``test_full_workflow_e2e.py``.

COVERAGE NOTE: the harness exposes count-level inventory
(``full_run.reopen_and_count``), not a per-object byte snapshot. This module
therefore verifies the count-level SC-004 guarantee — a Move only ADDS; it
never destroys pre-existing objects (every counted collection grows or stays
equal, and the target grows overall). The byte-level "no pre-existing field
changed" guarantee needs an object-snapshot harness helper that does not exist
yet; when it lands, add the diff assertion here.

SAFETY: SKIPS unless ``flexicon`` importable AND ``GRAMTRANS_E2E=1`` (restores
+ mutates a real target).
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_FLEXICON_PRESENT = importlib.util.find_spec("flexicon") is not None
_E2E_ENABLED = os.environ.get("GRAMTRANS_E2E") == "1"

if not _FLEXICON_PRESENT:
    pytest.skip("flexicon not importable; needs a live FLEx host.", allow_module_level=True)
if not _E2E_ENABLED:
    pytest.skip("GRAMTRANS_E2E != 1; opt into the destructive live E2E run.", allow_module_level=True)

_THIS_DIR = str(Path(__file__).parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from harness import full_run, restore  # noqa: E402

SOURCE_NAME = "Ejagham Mini"
TARGET_NAME = "Ejagham Full GT-Test"
TARGET_PATH = r"C:\ProgramData\SIL\FieldWorks\Projects\Ejagham Full GT-Test"


def test_move_only_adds_never_destroys() -> None:
    """SC-004 (count level): after a full Move, no counted collection in the
    target shrinks and the target grows overall."""
    try:
        backup = restore.newest_backup()
        restore.restore_target(TARGET_NAME, backup_path=backup)
    except restore.RestoreError as exc:
        pytest.skip(str(exc))

    before = full_run.reopen_and_count(TARGET_NAME)
    assert before, "baseline inventory empty; no accessor resolved"

    plan, report = full_run.run_full_transfer(SOURCE_NAME, TARGET_NAME, TARGET_PATH)
    assert plan is not None and report is not None

    after = full_run.reopen_and_count(TARGET_NAME)
    assert after, "post-run inventory empty"

    # No pre-existing collection lost members.
    for label, before_n in before.items():
        assert after.get(label, 0) >= before_n, (
            f"SC-004: '{label}' count shrank {before_n} -> {after.get(label)} "
            f"(a Move must never destroy pre-existing objects)"
        )
    # And the transfer actually grew the target.
    assert full_run.total_count(after) > full_run.total_count(before), (
        f"target did not grow: before={before} after={after}"
    )
