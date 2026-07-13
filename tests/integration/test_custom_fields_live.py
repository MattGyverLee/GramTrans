"""Live integration tests for the Custom Fields wizard tab (spec 016, T024).

Covers US3 (create-early / fill-later) + US4 (NEW vs IN_TARGET) + SC-009
(idempotency) against the real project pair Ejagham Mini -> Ejagham Full GT-Test.

SAFETY: the whole module SKIPS unless BOTH:
  - ``flexicon`` is importable, AND
  - the env flag ``GRAMTRANS_E2E=1`` is set.
So it never runs by accident (it restores and mutates a real project).

Run it:
    set GRAMTRANS_E2E=1 && \
        python -m pytest tests/integration/test_custom_fields_live.py -m integration -v

Prerequisites: FieldWorks 9 installed; source "Ejagham Mini" and a target
"Ejagham Full GT-Test" restorable from a repo ``backups/*.fwbackup``; the
target CLOSED in FLEx. See tests/integration/harness/README.md.

VERIFIED LIVE 2026-07-13 (see specs/016-custom-fields-wizard-tab/verification-log.md):
Against Ejagham Mini -> a fresh restore of Ejagham Full GT-Test, the source's two
custom fields classify as:
  - LexSense 'Target Equivalent'  -> NEW       (absent from target)  -> 1 create action
  - MoForm   'Allomorph Comment'  -> IN_TARGET (present in target)    -> 0 create actions
A full transfer (Custom Fields enabled) emitted exactly ONE CreateDefinitionAction
(for 'Target Equivalent', CellarPropertyType 13 / String), the target custom-field
count went 11 -> 12, the field survived a fresh reopen (create-early persisted), and
a re-run re-classifies both fields IN_TARGET => 0 new creates (idempotent).
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_FLEXICON_PRESENT = importlib.util.find_spec("flexicon") is not None
_E2E_ENABLED = os.environ.get("GRAMTRANS_E2E") == "1"

if not _FLEXICON_PRESENT:
    pytest.skip(
        "flexicon not importable; custom-fields live test needs a live FLEx host.",
        allow_module_level=True,
    )
if not _E2E_ENABLED:
    pytest.skip(
        "GRAMTRANS_E2E != 1; set it to opt into the destructive live custom-fields run.",
        allow_module_level=True,
    )

import sys  # noqa: E402

_THIS_DIR = str(Path(__file__).parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from harness import full_run, restore  # noqa: E402

from flexicon import FLExProject  # noqa: E402
from gramtrans.Lib import categories as C  # noqa: E402
from gramtrans.Lib.models import CreateDefinitionAction  # noqa: E402

SOURCE_NAME = "Ejagham Mini"
TARGET_NAME = "Ejagham Full GT-Test"
TARGET_PATH = r"C:\ProgramData\SIL\FieldWorks\Projects\Ejagham Full GT-Test"

# The source custom field known to be ABSENT from a fresh Ejagham Full target.
NEW_FIELD_OWNER = "LexSense"
NEW_FIELD_NAME = "Target Equivalent"


def _restore_fresh():
    try:
        backup = restore.newest_backup()
        restore.restore_target(TARGET_NAME, backup_path=backup)
    except restore.RestoreError as exc:
        pytest.skip(str(exc))


def _target_cf_names():
    tgt = FLExProject()
    tgt.OpenProject(projectName=TARGET_NAME, writeEnabled=False)
    try:
        return {(r.owner_class, r.name) for r in C._enumerate_custom_fields(tgt)}
    finally:
        tgt.CloseProject()


def test_create_early_and_idempotent():
    """A NEW source custom field is created (create-early), persists on reopen,
    and a re-run emits zero new create actions (SC-005, SC-009)."""
    _restore_fresh()

    before = _target_cf_names()
    assert (NEW_FIELD_OWNER, NEW_FIELD_NAME) not in before, (
        "[SETUP] Expected %r absent from a fresh target; got %r"
        % (NEW_FIELD_NAME, sorted(before))
    )

    # Run #1: full transfer with Custom Fields enabled (build_full_selection).
    plan1, _report1 = full_run.run_full_transfer(SOURCE_NAME, TARGET_NAME, TARGET_PATH)
    creates = [a for a in plan1.actions if isinstance(a, CreateDefinitionAction)]
    names = {(a.owner_class, a.field_name) for a in creates}
    assert (NEW_FIELD_OWNER, NEW_FIELD_NAME) in names, (
        "[FAIL] No create-definition action for the NEW field %r; got %r"
        % (NEW_FIELD_NAME, sorted(names))
    )
    # 'Allomorph Comment' (MoForm) is IN_TARGET -> no create action for it.
    assert ("MoForm", "Allomorph Comment") not in names, (
        "[FAIL] Emitted a create action for an IN_TARGET field (should reuse)."
    )

    # Create-early persisted: the field is present after a fresh reopen.
    after = _target_cf_names()
    assert (NEW_FIELD_OWNER, NEW_FIELD_NAME) in after, (
        "[FAIL] NEW custom field %r not present after Move+reopen (create-early "
        "did not persist)." % NEW_FIELD_NAME
    )

    # Idempotency (SC-009): re-run over the same (un-restored) target -> 0 creates.
    plan2, _report2 = full_run.run_full_transfer(SOURCE_NAME, TARGET_NAME, TARGET_PATH)
    creates2 = [a for a in plan2.actions if isinstance(a, CreateDefinitionAction)]
    assert creates2 == [], (
        "[FAIL] Second run planned %d create-definition action(s); expected 0 "
        "(idempotent by (owner_class, name) match)." % len(creates2)
    )
