"""T034 / R6: GUID preservation.

Rewritten from the original fictional-API scaffold. The original asserted
``plan.identity_remap == {}`` for the Ejagham pair — that is WRONG: per R6 and
STATUS.md, GUID preservation holds only where the LCM factory accepts a
``Create(Guid, ...)`` overload (POS / LexEntry / LexSense / leaf categories).
The affix MSAs and allomorphs CANNOT preserve their GUID (the flexicon
factories expose no Guid overload), so those get fresh target GUIDs that are
captured in ``plan.identity_remap`` (FR-012). identity_remap is therefore
EXPECTED to be non-empty on the Ejagham pair, not empty.

What this module checks (from the plan alone, so it runs via the existing
harness): identity_remap is well-formed and disjoint from the preserved set.
Verifying that each preserved GUID actually resolves in the reopened target
needs a harness reopen-and-fetch-object helper (``get_object_by_guid`` on a
freshly reopened handle) that does not exist yet — see the skipped test below.

SAFETY: SKIPS unless ``flexicon`` importable AND ``GRAMTRANS_E2E=1``.
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


def test_identity_remap_is_well_formed() -> None:
    """R6/FR-012: identity_remap maps each remapped source GUID (a planned
    action's source_guid) to a DISTINCT fresh target GUID, and every remapped
    source is itself a planned action (nothing invented out of thin air)."""
    try:
        backup = restore.newest_backup()
        restore.restore_target(TARGET_NAME, backup_path=backup)
    except restore.RestoreError as exc:
        pytest.skip(str(exc))

    plan, _ = full_run.run_full_transfer(SOURCE_NAME, TARGET_NAME, TARGET_PATH)
    remap = plan.identity_remap

    planned_src_guids = {str(a.source_guid) for a in plan.actions}
    for src_guid, tgt_guid in remap.items():
        assert src_guid in planned_src_guids, (
            f"identity_remap key {src_guid!r} is not a planned source GUID"
        )
        assert tgt_guid and tgt_guid != src_guid, (
            f"identity_remap[{src_guid!r}] = {tgt_guid!r} is empty or not a remap"
        )
    # Fresh target GUIDs must be unique (no two source objects collapsed).
    tgt_guids = list(remap.values())
    assert len(tgt_guids) == len(set(tgt_guids)), (
        f"identity_remap produced duplicate target GUIDs: {tgt_guids}"
    )
    # Preserved GUIDs = planned actions NOT in the remap. R6 expects the
    # preserved set to dominate (only affix MSAs/allomorphs remap).
    preserved = planned_src_guids - set(remap.keys())
    assert preserved, "no GUIDs were preserved — R6 preservation path never fired"


@pytest.mark.skip(
    reason="Verifying each preserved GUID resolves in the reopened target needs "
    "a harness reopen-and-fetch helper (get_object_by_guid on a fresh read-only "
    "handle); full_run only exposes count-level reopen_and_count today. Add the "
    "helper, then assert target presence of every preserved source_guid here."
)
def test_every_preserved_guid_present_in_reopened_target() -> None:  # pragma: no cover
    ...
