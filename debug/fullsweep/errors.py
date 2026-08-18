"""Feature 035 -- Group N: FAILURE TAXONOMY AND ABORT SCOPE (T011 of
specs/035-fullsweep-fidelity/tasks.md Phase 2).

Source: spec.md Section N (FR-174..FR-177).

This module says what a tripped assertion MEANS, distinct from Groups B
(``safety.py``), C (``pool.py``), and M/N's own text: a write-safety /
containment / provenance / pool-integrity trip aborts the ENTIRE run
(FR-175); an ordinary per-project transfer failure is that project's
terminal verdict and the run continues (FR-176); a memory shortfall
degrades and MUST NOT share an error path with either (FR-177). The
distinction is carried by a STABLE, MACHINE-CHECKABLE CODE -- never by
matching message text (FR-176 last sentence).
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# FR-176: stable identity codes. Categories are distinguished by CODE, never
# by matching message text.
# ---------------------------------------------------------------------------

FAILURE_CODE_WRITE_SAFETY = "WRITE_SAFETY"
FAILURE_CODE_CONTAINMENT = "CONTAINMENT"
FAILURE_CODE_PROVENANCE = "PROVENANCE"
FAILURE_CODE_POOL_INTEGRITY = "POOL_INTEGRITY"
FAILURE_CODE_PROJECT_FAILURE = "PROJECT_FAILURE"
FAILURE_CODE_MEMORY_SHORTFALL = "MEMORY_SHORTFALL"
FAILURE_CODE_HARNESS_DEFECT = "HARNESS_DEFECT"

ALL_FAILURE_CODES: tuple[str, ...] = (
    FAILURE_CODE_WRITE_SAFETY,
    FAILURE_CODE_CONTAINMENT,
    FAILURE_CODE_PROVENANCE,
    FAILURE_CODE_POOL_INTEGRITY,
    FAILURE_CODE_PROJECT_FAILURE,
    FAILURE_CODE_MEMORY_SHORTFALL,
    FAILURE_CODE_HARNESS_DEFECT,
)

#: FR-175: these four categories MUST abort the entire run, every sibling
#: worker included, left untouched for inspection. FR-177: MEMORY_SHORTFALL
#: MUST NOT share this path (nor may PROJECT_FAILURE -- FR-176 says a
#: per-project failure is that project's terminal verdict and the run
#: continues).
ABORT_WHOLE_RUN_CODES = frozenset({
    FAILURE_CODE_WRITE_SAFETY,
    FAILURE_CODE_CONTAINMENT,
    FAILURE_CODE_PROVENANCE,
    FAILURE_CODE_POOL_INTEGRITY,
})


@dataclass(frozen=True)
class PhaseFailure:
    """The phase-scoped failure record (T011). ``phase`` names whatever the
    caller was doing when the failure occurred -- the six-name artifact
    phase vocabulary (see ``artifact.PHASES``) where applicable, or a
    pre-project stage such as ``"setup"``/``"preflight"`` where the failure
    predates any project phase. This record does not itself constrain
    ``phase`` to the six-name vocabulary; ``artifact.assert_valid_phase``
    is the place that enforces that, for the narrower set of records the
    artifact schema requires it of (FR-146)."""
    phase: str
    code: str
    message: str
    evidence: dict = field(default_factory=dict)
    traceback: str = ""

    def __post_init__(self) -> None:
        if self.code not in ALL_FAILURE_CODES:
            raise ValueError(
                "[FR-176] unknown failure code %r -- must be one of %r"
                % (self.code, ALL_FAILURE_CODES)
            )

    def aborts_whole_run(self) -> bool:
        """FR-175 vs FR-176/FR-177: whether this failure's CODE (never its
        message text) means the entire run must stop."""
        return self.code in ABORT_WHOLE_RUN_CODES

    def as_dict(self) -> dict:
        return {
            "phase": self.phase, "code": self.code, "message": self.message,
            "evidence": self.evidence, "traceback": self.traceback,
        }


def classify_exception(exc: BaseException) -> str:
    """FR-176: map an exception to a stable failure CODE by its TYPE, never
    by inspecting or matching its message text.

    Imports the sibling modules lazily (not at module load time) so this
    module carries no hard import-order dependency on modules promoted
    independently of it in Phase 1.
    """
    from .safety import WriteSafetyError, SourceTamperError
    from .pool import MemoryShortfall
    try:
        from .moves import HarnessError as _HarnessDefect
    except Exception:  # pragma: no cover -- moves.py always present in this repo
        _HarnessDefect = ()  # type: ignore[assignment]

    if isinstance(exc, SourceTamperError):
        return FAILURE_CODE_PROVENANCE
    if isinstance(exc, WriteSafetyError):
        return FAILURE_CODE_WRITE_SAFETY
    if isinstance(exc, MemoryShortfall):
        return FAILURE_CODE_MEMORY_SHORTFALL
    if _HarnessDefect and isinstance(exc, _HarnessDefect):
        return FAILURE_CODE_HARNESS_DEFECT
    return FAILURE_CODE_PROJECT_FAILURE


def phase_failure_from_exception(
    exc: BaseException, *, phase: str, traceback_text: str = "", evidence: Optional[dict] = None,
) -> PhaseFailure:
    """Convenience: build a ``PhaseFailure`` from a caught exception using
    ``classify_exception`` for the code (FR-176)."""
    return PhaseFailure(
        phase=phase, code=classify_exception(exc), message="%s: %s" % (type(exc).__name__, exc),
        evidence=evidence or {}, traceback=traceback_text,
    )


# ---------------------------------------------------------------------------
# FR-175: the cross-worker, out-of-collection abort flag
# ---------------------------------------------------------------------------

#: Lives OUTSIDE the projects collection (under this repo's own gitignored
#: sweep scratch dir, alongside pool.py's ExclusiveTargetClaim files), so a
#: restore call can never remove it and it is never mistaken for project
#: content.
DEFAULT_ABORT_FLAG_PATH = (
    Path(__file__).resolve().parents[2] / "scratchpad" / "035_sweep" / "ABORT_WHOLE_RUN.json"
)


class WholeRunAborted(RuntimeError):
    """Raised by ``check_abort_between_projects`` when a sibling worker has
    tripped the shared abort flag. A distinct identity from
    ``WriteSafetyError``/``SourceTamperError``/etc. so the detection point
    itself is machine-checkable (FR-176), not a re-thrown copy of whatever
    tripped the flag originally."""


class WholeRunAbortFlag:
    """FR-175: the shared mechanism sibling workers check BETWEEN projects.
    A file-based flag, deliberately simple and durable across process
    restarts, living outside the projects collection.
    """

    def __init__(self, path: Path = DEFAULT_ABORT_FLAG_PATH):
        self.path = path

    def trip(self, failure: PhaseFailure, *, source_name: str = "") -> None:
        """Record the flag. Refuses to trip for a failure whose code is not
        in ``ABORT_WHOLE_RUN_CODES`` -- routing a project failure or a
        memory shortfall through this path is exactly the FR-177 conflation
        this taxonomy exists to prevent."""
        if not failure.aborts_whole_run():
            raise ValueError(
                "[FR-175/FR-177] refusing to trip the whole-run abort flag for "
                "failure code %r -- only %r may abort the whole run"
                % (failure.code, sorted(ABORT_WHOLE_RUN_CODES))
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tripped_at": time.time(), "source": source_name,
            "failure": failure.as_dict(),
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        os.replace(str(tmp), str(self.path))

    def is_tripped(self) -> bool:
        return self.path.is_file()

    def read(self) -> Optional[dict]:
        if not self.path.is_file():
            return None
        return json.loads(self.path.read_text(encoding="utf-8"))

    def clear(self) -> None:
        """Operator/harness-reset only -- never called automatically by a
        worker (a tripped run must be inspected, not self-healed)."""
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def check_abort_between_projects(flag: Optional[WholeRunAbortFlag] = None) -> None:
    """FR-175: call this between projects in the batch loop. Raises
    ``WholeRunAborted`` if a sibling has tripped the shared flag; the
    aborting worker's own destination is left untouched (callers must not
    attempt a restore/cleanup on the CURRENT project after this raises --
    that would touch the very evidence FR-175 requires preserved)."""
    flag = flag or WholeRunAbortFlag()
    payload = flag.read()
    if payload is None:
        return
    failure = payload.get("failure", {})
    raise WholeRunAborted(
        "[FR-175] whole-run abort flag is set (tripped_at=%s, source=%r, code=%s): %s"
        % (payload.get("tripped_at"), payload.get("source"),
           failure.get("code"), failure.get("message"))
    )
