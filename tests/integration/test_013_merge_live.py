"""Live integration test for the SIMILAR-resolution MERGE write mode (spec 013,
T-S3c / T-S1).

Feature 013 adds a ``merge`` (target-preserving, fill-the-gaps) entry-level write
mode alongside the existing ``overwrite`` (source-wins) mode. Both are implemented
in the flexicon fork's shared ``ApplySyncableProperties`` loop via the ``fill_gaps``
kwarg (BaseOperations._apply_props_loop):

  - fill_gaps=True  (MERGE)     : a WS alt is written ONLY when the target alt is
                                  empty/whitespace-only; a non-empty target alt is
                                  preserved (target wins on conflict). FR-007a.
  - fill_gaps=False (OVERWRITE) : source wins on every non-empty source alt. FR-007.

This module exercises the write mode against a REAL target object end-to-end (the
T-S1 live-verify risk: the multistring emptiness predicate). The planner-level
SIMILAR threading (identity_remap seeding, _plan_identity_remap_children,
fingerprint_with_owner owner override) is covered by the unit suite
(test_013_fill_gaps.py, test_013_executor_merge.py).

SAFETY: SKIPS unless flexicon is importable AND GRAMTRANS_E2E=1.

Run it:
    set GRAMTRANS_E2E=1 && \
        python -m pytest tests/integration/test_013_merge_live.py -m integration -v

VERIFIED LIVE 2026-07-13 (see specs/013-similar-resolution-transfer/verification-log.md):
On a target POS 'Adverb' (Ejagham Full GT-Test) with a non-empty Description:
  (A) MERGE + non-empty target + different source -> target PRESERVED (source did not win)
  (B) MERGE + empty target     + non-empty source -> target FILLED from source
  (C) OVERWRITE + non-empty target + different source -> source WINS
The fork's fill_gaps emptiness predicate is ``(existing.Text or "").strip()``
(BaseOperations.py:306), exactly as T-S1 specified.
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
        "flexicon not importable; 013 merge live test needs a live FLEx host.",
        allow_module_level=True,
    )
if not _E2E_ENABLED:
    pytest.skip(
        "GRAMTRANS_E2E != 1; set it to opt into the destructive live 013 merge run.",
        allow_module_level=True,
    )

from flexicon import FLExProject, POSOperations  # noqa: E402
from SIL.LCModel.Core.Text import TsStringUtils  # noqa: E402

from gramtrans.Lib.conflict import _is_empty  # noqa: E402

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


def _pos_with_description(ops):
    for p in list(ops.GetAll(recursive=True)):
        if not _is_empty(ops.GetSyncableProperties(p).get("Description")):
            return p
    return None


def test_merge_write_mode_fill_gaps_vs_overwrite(target):
    """FR-007 / FR-007a: MERGE preserves non-empty target and fills gaps;
    OVERWRITE is source-wins (the destructive contrast)."""
    ops = POSOperations(target)
    pos = _pos_with_description(ops)
    if pos is None:
        pytest.skip("No target POS with a non-empty Description to exercise.")
    h = target.GetDefaultAnalysisWSHandle()
    prop = getattr(pos, "Description")
    orig = prop.get_String(h).Text
    assert orig, "[SETUP] chosen POS Description came back empty"

    try:
        # (A) MERGE conflict -> target preserved.
        ops.ApplySyncableProperties(
            pos, {"Description": {"en": "MERGE_SHOULD_NOT_WIN"}}, fill_gaps=True
        )
        assert prop.get_String(h).Text == orig, (
            "[FAIL] MERGE overwrote a non-empty target alt (should preserve)."
        )

        # (B) MERGE gap-fill -> empty target filled from source.
        prop.set_String(h, TsStringUtils.MakeString("", h))
        assert _is_empty(ops.GetSyncableProperties(pos).get("Description"))
        ops.ApplySyncableProperties(
            pos, {"Description": {"en": "FILLED_BY_MERGE"}}, fill_gaps=True
        )
        assert prop.get_String(h).Text == "FILLED_BY_MERGE", (
            "[FAIL] MERGE did not fill an empty target alt from a non-empty source."
        )

        # (C) OVERWRITE contrast -> source wins on a non-empty target.
        ops.ApplySyncableProperties(
            pos, {"Description": {"en": "OVERWRITTEN"}}, fill_gaps=False
        )
        assert prop.get_String(h).Text == "OVERWRITTEN", (
            "[FAIL] OVERWRITE did not win over a non-empty target alt."
        )
    finally:
        # Restore the original description so the throwaway target stays tidy.
        prop.set_String(h, TsStringUtils.MakeString(orig, h))
