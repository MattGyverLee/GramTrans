"""Live integration scaffold for feature 028 (Affix-Allomorph Morphosyntax).

Proves the offline reproduce legs (`owned.reproduce_moaffix_msenv_data` +
`_plan_moaffix_msenv_decisions`) reproduce the four `MoAffixAllomorph`/
`MoAffixForm` morphosyntactic-environment fields (`MsEnvPartOfSpeechRA`,
`InflectionClassesRC`, `MsEnvFeaturesOA`, `PositionRS`) end-to-end against a
REAL, freshly-restored FLEx target -- the live `0 -> N` proof (SC-001/002/003/
005) tracked as T019 in tasks.md.

SAFETY: this is an ATTENDED / needs_human artifact. SKIPS unless flexicon is
importable AND GRAMTRANS_E2E=1 -- never runs under an unattended loop (spec 028
tasks.md T019 constraint). Ejagham Mini/Full are VACUOUS for these four fields
(0/106 allomorphs populate any), so the live proof needs a CONSTRUCTED fixture
on a disposable source (mirrors feature 027's constructed complex-form proof).

The attended restore -> fixture -> Preview -> Move -> re-Move -> forced-drop
sequence is driven manually (template: `scratchpad/run031_live.py`, which 028's
MsEnvFeaturesOA leg reuses for closed-feature resolution). Evidence is captured
in `specs/028-affix-allomorph-morphosyntax/verification-log.md`.

Run it (attended only, freshly-restored target):
    set GRAMTRANS_E2E=1 && \\
        python -m pytest tests/integration/test_028_affix_msenv_live.py -m integration -v
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
        "flexicon not importable; 028 affix-MsEnv live test needs a live "
        "FLEx host.",
        allow_module_level=True,
    )
if not _E2E_ENABLED:
    pytest.skip(
        "GRAMTRANS_E2E != 1; set it to opt into the destructive live 028 "
        "Move run. ATTENDED ONLY -- restore the target from a clean backup "
        "and build the constructed fixture first; never run under an "
        "unattended loop.",
        allow_module_level=True,
    )

# Disposable source (restore from backups/Ejagham Mini.fwbackup, then add the
# constructed affix fixture) and target (restore from the clean Target backup).
SOURCE_NAME = "Ejagham028Src"
TARGET_NAME = "Target"


def test_affix_msenv_fields_reproduce_0_to_n():
    """SC-001/002/003/005: attended live `0 -> N` affix-MsEnv proof.

    Placeholder for T019 -- the full restore -> fixture -> Preview -> Move ->
    re-Move -> forced-drop sequence is run manually (attended-only, never under
    an unattended loop; Ejagham corpora are vacuous for these four fields so a
    constructed fixture is required). The real proof is captured in
    `specs/028-affix-allomorph-morphosyntax/verification-log.md` per T019.
    """
    pytest.skip(
        "T019 (attended live 0->N proof) is run manually against a constructed "
        "fixture, never under an automated/unattended loop; see "
        "specs/028-affix-allomorph-morphosyntax/verification-log.md."
    )
