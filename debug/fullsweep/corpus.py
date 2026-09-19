"""Feature 035 -- Group A: CORPUS AND ENUMERATION. Moved unchanged out of the
``debug/run_fullcopy_sweep.py`` monolith (T002/T009 of
specs/035-fullsweep-fidelity/tasks.md Phase 1).

Reused rather than reinvented (per instructions):
  * ``debug/prescan_type_coverage.py`` -- corpus enumeration
    (``_enumerate``/``_walk_flex_projects``), the anchored
    ``^Target[0-9]*$`` refusal pattern, its ``_fingerprint`` helper shape, and
    its subprocess-isolation driver pattern.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import prescan_type_coverage as prescan  # noqa: E402 -- reused, not reinvented

# FR-006/FR-002: directories that are never a source, by construction, and
# the recorded reason for each.
SWEEP_OWN_ADDITIONAL_WORKING_DIRS: dict[str, str] = {
    # This machine's Ejagham-Mini -> Ejagham-Full-GT-Test additional working
    # directory, used by this repo's other live-parity harnesses (see
    # STATUS.md). It matches the project-on-disk rule and must be excluded
    # by name, not merely by being outside the enumeration root (it is
    # INSIDE the projects root).
    "Ejagham Full GT-Test": (
        "the repo's own additional working directory for prior harness "
        "runs, not a sweep source (FR-006)"
    ),
}

# FR-004: exact spelling the known-good regression set must use, and the
# empty-shell decoy it must never admit.
CANARY_PROJECTS = ("Ejagham Mini", "Esperanto", "Mbugwe LizzieHC practice")
FORBIDDEN_SHELL_DECOY = "Mbugwe Lizzie HCPractice"  # empty shell, no data file


@dataclass
class CorpusEntry:
    project: str
    path: str
    fwdata_mb: float
    admitted: bool
    reason: str


def enumerate_corpus(projects_root: Optional[str] = None) -> list[CorpusEntry]:
    """FR-001..FR-009: derive the source corpus at runtime.

    Reuses ``prescan_type_coverage._enumerate`` (which already reuses the
    engine's own project-on-disk rule and already refuses the disposable
    ``Target[0-9]*`` pattern) and layers on this sweep's own additional
    exclusion: its additional working directory (FR-006/FR-002).
    """
    if projects_root is not None:
        os.environ["GRAMTRANS_PROJECTS_ROOT"] = projects_root
    rows = prescan._enumerate()
    out: list[CorpusEntry] = []
    for r in rows:
        name = r["project"]
        admitted = r["disposition"] == "scan"
        reason = r["reason"]
        if admitted and name in SWEEP_OWN_ADDITIONAL_WORKING_DIRS:
            admitted = False
            reason = SWEEP_OWN_ADDITIONAL_WORKING_DIRS[name]
        if admitted and name == FORBIDDEN_SHELL_DECOY:
            # FR-004 belt-and-suspenders: never admit this exact name even if
            # a future disk state somehow gives it a data file.
            admitted = False
            reason = "FR-004: forbidden decoy name, never admitted regardless of disk state"
        out.append(CorpusEntry(project=name, path=r["path"], fwdata_mb=r["fwdata_mb"],
                                admitted=admitted, reason=reason))
    return out


def freeze_source_manifest(corpus: list[CorpusEntry]) -> tuple[str, ...]:
    """FR-035: freeze the admitted source list ONCE before any worker starts."""
    return tuple(sorted(e.project for e in corpus if e.admitted))
