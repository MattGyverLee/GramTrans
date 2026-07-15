"""Live integration tests for the per-item disposition model (spec 022, T029).

Exercises the UPDATE / OVERWRITE write semantics and the SKIP/UPDATE/OVERWRITE
disposition computation against a REAL target object (a POS on Ejagham Full
GT-Test), using the actual conflict.py functions + the flexicon fork's
GetSyncableProperties / ApplySyncableProperties.

SAFETY: SKIPS unless flexicon is importable AND GRAMTRANS_E2E=1.

Run it:
    set GRAMTRANS_E2E=1 && \
        python -m pytest tests/integration/test_conflict_live.py -m integration -v

VERIFIED LIVE 2026-07-13 (see specs/022-disposition-model/verification-log.md):
On target POS 'Adverb' (Name multistring diverged; Description emptied in source):
  - compute_disposition(identical, UPDATE)  -> SKIP        (SC-004)
  - compute_disposition(diverged,  UPDATE)  -> UPDATE
  - compute_disposition(diverged,  OVERWRITE)-> OVERWRITE
  - apply_update_semantic wrote 1 field (Name); Description (empty source) was
    PRESERVED, not blanked                                 (SC-002, the safety core)

LIVE FINDING (SC-003 destructive-blank does NOT reproduce for multistrings):
the fork's _apply_props_loop skips empty multistring values unconditionally
(`if not text: continue`, BaseOperations.py:291), so the OVERWRITE (source-wins)
path CANNOT blank a target multistring alt from an empty source -- it behaves
non-destructively there, identical to UPDATE. Direct set_String("") DOES blank,
so the capability exists; the write path guards against it. See the verification
log + the tracked follow-up. ``test_overwrite_empty_source_multistring`` documents
this as xfail(strict) so a future fork change that restores blanking flips it red.
"""
from __future__ import annotations

import importlib.util
import os

import pytest

pytestmark = pytest.mark.integration

_FLEXICON_PRESENT = importlib.util.find_spec("flexicon") is not None
_E2E_ENABLED = os.environ.get("GRAMTRANS_E2E") == "1"

if not _FLEXICON_PRESENT:
    pytest.skip(
        "flexicon not importable; 022 disposition live test needs a live FLEx host.",
        allow_module_level=True,
    )
if not _E2E_ENABLED:
    pytest.skip(
        "GRAMTRANS_E2E != 1; set it to opt into the destructive live 022 run.",
        allow_module_level=True,
    )

from flexicon import FLExProject, POSOperations  # noqa: E402
from SIL.LCModel.Core.Text import TsStringUtils  # noqa: E402

from gramtrans.Lib.conflict import (  # noqa: E402
    ItemDisposition,
    _is_empty,
    apply_update_semantic,
    compute_disposition,
)
from gramtrans.Lib.models import ConflictMode  # noqa: E402

TARGET_NAME = "Ejagham Full GT-Test"


@pytest.fixture
def target():
    tgt = FLExProject()
    try:
        tgt.OpenProject(projectName=TARGET_NAME, writeEnabled=True)
    except Exception as exc:  # noqa: BLE001
        pytest.skip("Cannot open target %r write-enabled: %s" % (TARGET_NAME, exc))
    yield tgt
    try:
        tgt.CloseProject()
    except Exception:  # noqa: BLE001
        pass


def _pos_with_name_and_desc(ops):
    for p in list(ops.GetAll(recursive=True)):
        pr = ops.GetSyncableProperties(p)
        if pr.get("Name") and not _is_empty(pr.get("Description")):
            return p, pr
    return None, None


def test_disposition_skip_update_overwrite(target):
    """SC-004 + disposition vocabulary: identical -> SKIP; diverged -> UPDATE /
    OVERWRITE per intent."""
    ops = POSOperations(target)
    pos, tgt_props = _pos_with_name_and_desc(ops)
    if pos is None:
        pytest.skip("No target POS with Name + non-empty Description.")

    src_diverged = dict(tgt_props)
    src_diverged["Name"] = {k: v + " [SRC]" for k, v in tgt_props["Name"].items()}

    assert compute_disposition(dict(tgt_props), tgt_props, ConflictMode.UPDATE) is ItemDisposition.SKIP
    assert compute_disposition(src_diverged, tgt_props, ConflictMode.UPDATE) is ItemDisposition.UPDATE
    assert compute_disposition(src_diverged, tgt_props, ConflictMode.OVERWRITE) is ItemDisposition.OVERWRITE


def test_update_is_non_destructive(target):
    """SC-002 (the safety core): UPDATE writes a diverged non-empty source field
    but preserves a target field the source leaves empty (never blanks)."""
    ops = POSOperations(target)
    pos, tgt_props = _pos_with_name_and_desc(ops)
    if pos is None:
        pytest.skip("No target POS with Name + non-empty Description.")
    orig_name = tgt_props["Name"]
    orig_desc = tgt_props["Description"]

    src_props = dict(tgt_props)
    src_props["Name"] = {k: v + " [SRC]" for k, v in orig_name.items()}  # diverged
    src_props["Description"] = {"en": ""}  # empty source -> must be preserved

    try:
        written = apply_update_semantic(src_props, tgt_props, ops, pos)
        after = ops.GetSyncableProperties(pos)
        assert written == 1, "[FAIL] expected exactly 1 field written (Name)"
        assert after.get("Name") == src_props["Name"], "[FAIL] Name not updated"
        assert after.get("Description") == orig_desc, (
            "[FAIL] UPDATE blanked a target field from an empty source (destructive!)"
        )
    finally:
        ops.ApplySyncableProperties(pos, {"Name": orig_name, "Description": orig_desc})


@pytest.mark.xfail(
    strict=True,
    reason="LIVE FINDING: the fork's _apply_props_loop skips empty multistring "
    "values (BaseOperations.py:291 `if not text: continue`), so OVERWRITE cannot "
    "blank a target multistring alt from an empty source. UPDATE and OVERWRITE are "
    "behaviorally identical for the empty-source multistring case. See "
    "specs/022-disposition-model/verification-log.md.",
)
def test_overwrite_empty_source_multistring_blanks(target):
    """SC-003 (destructive contrast) as SPEC'd -- currently xfail live for
    multistrings. A future fork change that writes empty alts flips this red."""
    ops = POSOperations(target)
    pos, tgt_props = _pos_with_name_and_desc(ops)
    if pos is None:
        pytest.skip("No target POS with Name + non-empty Description.")
    h = target.GetDefaultAnalysisWSHandle()
    prop = getattr(pos, "Description")
    orig = prop.get_String(h).Text
    try:
        # OVERWRITE (source-wins) with an explicitly empty 'en' alt.
        ops.ApplySyncableProperties(pos, {"Description": {"en": ""}}, fill_gaps=False)
        assert _is_empty(ops.GetSyncableProperties(pos).get("Description")), (
            "OVERWRITE did not blank the target Description from an empty source"
        )
    finally:
        if orig:
            prop.set_String(h, TsStringUtils.MakeString(orig, h))
