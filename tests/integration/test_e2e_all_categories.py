"""T030: Full-categories transfer + SC-001 timing (quickstart Scenario A).

Rewritten to drive the REAL engine through the shared live harness
(``tests/integration/harness``) rather than the fictional API the original
scaffold referenced. Mirrors the guard + harness pattern established by
``test_full_workflow_e2e.py``.

SAFETY: the whole module SKIPS unless BOTH ``flexicon`` is importable AND the
env flag ``GRAMTRANS_E2E=1`` is set, because it restores and mutates a real
target project. Run it:

    set GRAMTRANS_E2E=1 && pytest tests/integration/test_e2e_all_categories.py -m integration -v

Prerequisites: FieldWorks 9 installed, source "Ejagham Mini" + target
"Ejagham Full GT-Test" present (target CLOSED in FLEx), a *.fwbackup in the
repo ``backups/`` dir. See tests/integration/harness/README.md.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

# --- Module-level guards: skip cleanly (never error) when prereqs absent. ----
_FLEXICON_PRESENT = importlib.util.find_spec("flexicon") is not None
_E2E_ENABLED = os.environ.get("GRAMTRANS_E2E") == "1"

if not _FLEXICON_PRESENT:
    pytest.skip(
        "flexicon not importable; full-categories E2E needs a live FLEx host.",
        allow_module_level=True,
    )
if not _E2E_ENABLED:
    pytest.skip(
        "GRAMTRANS_E2E != 1; set it to opt into the destructive live E2E run.",
        allow_module_level=True,
    )

# Imports below only reached when the guards pass.
_THIS_DIR = str(Path(__file__).parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from harness import full_run, restore  # noqa: E402

from gramtrans.Lib.models import GrammarCategory, SkipReason  # noqa: E402

SOURCE_NAME = "Ejagham Mini"
TARGET_NAME = "Ejagham Full GT-Test"
TARGET_PATH = r"C:\ProgramData\SIL\FieldWorks\Projects\Ejagham Full GT-Test"

# SC-001 benchmark ceilings.
_MAX_PIECES = 100
_MAX_SECONDS = 300.0


@pytest.fixture(scope="module")
def transfer():
    """Restore a clean target, run one full transfer, yield ``(plan, report)``.

    Module-scoped so the (expensive) restore + Move happens once for all the
    assertions below. Skips — rather than errors — if the backup or projects
    are not present on this machine.
    """
    try:
        backup = restore.newest_backup()
        restore.restore_target(TARGET_NAME, backup_path=backup)
    except restore.RestoreError as exc:
        pytest.skip(str(exc))
    plan, report = full_run.run_full_transfer(SOURCE_NAME, TARGET_NAME, TARGET_PATH)
    assert plan is not None and report is not None
    return plan, report


def test_preview_produces_actions(transfer) -> None:
    """Scenario A steps 3-8: an all-categories transfer plans at least one
    action (Ejagham Mini is non-empty)."""
    plan, _ = transfer
    assert len(plan.actions) > 0, "full transfer planned zero actions"


def test_move_counts_match_preview_counts(transfer) -> None:
    """Scenario A steps 9-11 / SC-002: for every category, the RunReport's
    ``added`` count equals the number of PlannedActions the plan carried for
    that category — the no-silent-loss invariant, end to end."""
    plan, report = transfer
    for cat in GrammarCategory:
        planned = sum(1 for a in plan.actions if a.category == cat)
        stat = report.per_category.get(cat)
        added = stat.added if stat is not None else 0
        assert added == planned, (
            f"Category {cat.name}: plan had {planned} actions but report "
            f"recorded {added} added"
        )


def test_move_wall_clock_under_five_minutes(transfer) -> None:
    """SC-001: a <=100-piece benchmark Move completes in under 5 minutes."""
    plan, report = transfer
    assert len(plan.actions) <= _MAX_PIECES, (
        f"Ejagham Mini planned {len(plan.actions)} pieces, exceeding the "
        f"SC-001 benchmark ceiling of {_MAX_PIECES}"
    )
    assert report.wall_clock_seconds < _MAX_SECONDS, (
        f"SC-001 violated: Move took {report.wall_clock_seconds:.1f}s "
        f"(limit {_MAX_SECONDS:.0f}s)"
    )


def test_no_dangling_ref_skips_and_fr018_balance(transfer) -> None:
    """Scenario A step 13: no dangling-reference skips (SC-003) and the plan/
    report item counts balance (FR-018 no silent drops)."""
    plan, report = transfer

    # A dangling reference in the target surfaces as a DEPENDENCY_UNRESOLVED
    # skip (the accidental hard-fail reason); SC-003 requires zero of them.
    dangling = [s for s in report.skips if s.reason == SkipReason.DEPENDENCY_UNRESOLVED]
    assert dangling == [], f"SC-003: unresolved-dependency skips after Move: {dangling}"

    total_added = sum(v.added for v in report.per_category.values())
    total_skipped = sum(v.skipped for v in report.per_category.values())
    assert total_added + total_skipped == len(plan.actions) + len(plan.skips), (
        "FR-018: plan/report item counts do not balance"
    )
