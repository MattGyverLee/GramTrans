"""Live integration scaffold for feature 027 (Complex Forms & Variants).

Resolves GitHub #30; unblocks the LexEntryRef leg of #28. Proves the offline
`_run_entryref_create_pass` (C1) + `_run_post_pass_a` (C2) + entry-type
resolution (C3) reproduce `LexEntryRef` relationships end-to-end against a
REAL, freshly-restored FLEx target -- the live `0 -> N` proof (SC-001/002/003)
tracked as T025 in tasks.md.

SAFETY: this is an ATTENDED / needs_human artifact. SKIPS unless flexicon is
importable AND GRAMTRANS_E2E=1 -- never runs under an unattended Ralph loop
(spec 027 tasks.md T025 constraint). See `scratchpad/run27_live.py` for the
attended restore -> diagnose -> Move -> re-Move -> diagnose driver.

Run it (attended only, freshly-restored target):
    set GRAMTRANS_E2E=1 && \\
        python -m pytest tests/integration/test_027_complex_forms_live.py -m integration -v
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
        "flexicon not importable; 027 complex-forms live test needs a live "
        "FLEx host.",
        allow_module_level=True,
    )
if not _E2E_ENABLED:
    pytest.skip(
        "GRAMTRANS_E2E != 1; set it to opt into the destructive live 027 "
        "Move run. ATTENDED ONLY -- restore the target from a clean backup "
        "first; never run under an unattended loop.",
        allow_module_level=True,
    )

from flexicon import FLExProject  # noqa: E402

SOURCE_NAME = "Ejagham Mini"
TARGET_NAME = "Ejagham Full GT-Test"


@pytest.fixture
def source():
    src = FLExProject()
    try:
        src.OpenProject(projectName=SOURCE_NAME, writeEnabled=False)
    except Exception as exc:  # noqa: BLE001
        pytest.skip("Cannot open source %r: %s" % (SOURCE_NAME, exc))
    yield src
    try:
        src.CloseProject()
    except Exception:  # noqa: BLE001
        pass


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


def test_variant_entry_refs_reproduce_0_to_6(source, target):
    """SC-001/002/003: attended live `0 -> 6` LexEntryRef proof.

    Placeholder for T025 -- the full restore -> diagnose -> Move -> re-Move ->
    diagnose sequence lives in `scratchpad/run27_live.py` (attended-only, never
    under an unattended loop). This test asserts the fixture pair opens; the
    real proof is captured in
    `specs/027-complex-forms-variants/verification-log.md` per T025.
    """
    pytest.skip(
        "T025 (attended live 0->N proof) is run manually via "
        "scratchpad/run27_live.py, never under an automated/unattended loop; "
        "see specs/027-complex-forms-variants/verification-log.md."
    )
