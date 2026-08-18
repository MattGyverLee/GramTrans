"""Feature 035 -- Group K: ARTIFACT AND PROVENANCE. Moved unchanged out of the
``debug/run_fullcopy_sweep.py`` monolith (T006/T009 of
specs/035-fullsweep-fidelity/tasks.md Phase 1).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ARTIFACTS_DIR = _ROOT / "specs" / "035-fullsweep-fidelity" / "artifacts"


def _run_git(args: list[str], cwd: Path) -> str:
    cp = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    if cp.returncode != 0:
        raise RuntimeError("git %s failed in %s: %s" % (" ".join(args), cwd, cp.stderr.strip()))
    return cp.stdout.strip()


def _git_revision(repo_dir: Path) -> dict:
    """Returns {"sha": str, "dirty": bool} or {"sha": None, "error": str}."""
    try:
        sha = _run_git(["rev-parse", "HEAD"], repo_dir)
        status = _run_git(["status", "--porcelain"], repo_dir)
        return {"sha": sha, "dirty": bool(status.strip()), "error": ""}
    except Exception as exc:  # noqa: BLE001 -- recorded, never silent
        return {"sha": None, "dirty": None, "error": "%s: %s" % (type(exc).__name__, exc)}


def gramtrans_revision() -> dict:
    """FR-138: this driver's own source-revision identity + dirty flag."""
    return _git_revision(_ROOT)


def flexicon_revision() -> dict:
    """FR-139/FR-157: the transfer engine dependency's revision identity --
    a git SHA, NOT its version string (per this repo's CLAUDE.md: "flexicon
    reports a version string that is not reliably bumped when its runtime
    behavior changes"; also independently observed live, see
    probe-results-live.md's "undoable default" finding)."""
    try:
        import flexicon
        pkg_dir = Path(flexicon.__file__).resolve().parent
    except Exception as exc:  # noqa: BLE001
        return {"sha": None, "dirty": None,
                "error": "could not import flexicon: %s: %s" % (type(exc).__name__, exc)}
    d = pkg_dir
    for _ in range(6):
        if (d / ".git").exists():
            return _git_revision(d)
        if d.parent == d:
            break
        d = d.parent
    return {"sha": None, "dirty": None,
            "error": "no .git found walking up from %s" % pkg_dir}


def revision_pair() -> dict:
    return {"gramtrans": gramtrans_revision(), "flexicon": flexicon_revision()}


@dataclass
class ProjectArtifact:
    """Group K durable, per-project artifact. Every field required by the
    settled FR-138..FR-151 stamps is present; findings/detail lists are
    NEVER truncated here (FR-144 -- truncation is a console-only concern)."""
    project: str
    run_intent: str                    # FR-188/FR-166: "baseline" | "gate"
    revision_pair: dict                # FR-157
    dirty_gramtrans: Optional[bool]    # FR-138
    coverage_categories: list          # FR-142 (the categories actually run)
    phases_completed: list = field(default_factory=list)  # FR-150
    source_fingerprint_before: dict = field(default_factory=dict)
    source_fingerprint_after: dict = field(default_factory=dict)
    fingerprint_verdict: str = ""      # FR-022 classification
    census_before: dict = field(default_factory=dict)      # class -> sorted [guid,...]
    census_after_first: dict = field(default_factory=dict)
    census_after_second: dict = field(default_factory=dict)
    written_classes: dict = field(default_factory=dict)
    idempotency: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)           # compare_objects() output
    status: str = "running"            # FR-156 ledger vocabulary
    reason: str = ""
    errors: list = field(default_factory=list)             # [{phase, error, traceback}]
    started_at: float = 0.0
    finished_at: float = 0.0

    # ---- T013 additions (Phase 2 taxonomy spine, FR-138..FR-151/FR-188) ----
    phase_reached: Optional[str] = None                     # FR-150, six-name vocabulary

    # ---- T019/T020/T024 additions (Phase 3 / US4) ----------------------
    assertions: list = field(default_factory=list)          # FR-024: each assertion, per boundary
    assertions_complete: Optional[bool] = None              # FR-013: both boundaries evaluated
    baseline: dict = field(default_factory=dict)            # FR-170: pinned archive + hash
    restore_evidence: dict = field(default_factory=dict)    # FR-172/FR-173 (initial restore)
    restore_evidence_final: dict = field(default_factory=dict)  # FR-172/FR-173 (final restore)
    excluded_categories: list = field(default_factory=list)  # FR-142: explicit, possibly empty
    diagnostic_level: str = ""                              # recorded, never setdefault-ed
    preflight: dict = field(default_factory=dict)           # FR-124/FR-126: capability check
    guards: dict = field(default_factory=dict)              # FR-109/FR-143: all fifteen keys
    verdict: str = ""                                       # machine token, verdict.py
    exit_code: Optional[int] = None                         # verdict.exit_code_for(verdict)


# ---------------------------------------------------------------------------
# T013: artifact document shape additions -- phase vocabulary, intent
# normalization, the always-written SKIPPED artifact, and the no-truncation
# rule (FR-138..FR-151, FR-188).
# ---------------------------------------------------------------------------

#: FR-146/FR-150: the six-name phase vocabulary, contracts/artifact-schema.md
#: verbatim. Do not rename, recase, reorder, or extend without updating that
#: contract first.
PHASES: tuple[str, ...] = (
    "restore", "transfer_1", "census_1", "transfer_2", "census_2", "restore_final",
)

#: FR-188: the artifact's stored (normalized) intent spellings.
INTENT_BASELINE = "BASELINE"
INTENT_GATE = "GATE"
VALID_INTENTS: tuple[str, ...] = (INTENT_BASELINE, INTENT_GATE)

#: FR-151/FR-188: the status a project that the run never attempted gets,
#: so corpus-level status is always derived from a real artifact document,
#: never a ledger entry with nothing backing it.
STATUS_SKIPPED = "SKIPPED"


def normalize_intent(intent: str) -> str:
    """FR-188: normalize a caller-facing intent spelling (``"baseline"`` /
    ``"gate"``, case-insensitively) to the artifact's stored form
    (``"BASELINE"`` / ``"GATE"``). Raises on anything else -- an artifact's
    intent is never left ambiguous, and a ``BASELINE`` artifact is never
    admissible toward the FR-166 corpus claim, whatever it contains."""
    if not isinstance(intent, str):
        raise ValueError("[FR-188] intent must be a string, got %r" % (intent,))
    token = intent.strip().upper()
    if token not in VALID_INTENTS:
        raise ValueError(
            "[FR-188] intent must be one of %r (case-insensitive), got %r"
            % (VALID_INTENTS, intent)
        )
    return token


def assert_valid_phase(phase: str) -> None:
    """FR-146: every phase-scoped record names one of the six phases,
    verbatim -- never a hand-typed variant."""
    if phase not in PHASES:
        raise ValueError(
            "[FR-146] phase %r is not one of the six-name vocabulary %r" % (phase, PHASES)
        )


def advance_phase(
    artifact: "ProjectArtifact", phase: str, artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR,
) -> Path:
    """FR-146/FR-150: validate ``phase`` against the six-name vocabulary,
    record it as the document's ``phase_reached``, and flush -- so a crash
    mid-run leaves a partial document naming the last phase actually
    reached, never an undifferentiated whole-project failure."""
    assert_valid_phase(phase)
    artifact.phase_reached = phase
    return flush_artifact(artifact, artifacts_dir)


def console_truncate(items: list, max_items: Optional[int] = None) -> tuple[list, int]:
    """FR-105/FR-144: the no-truncation rule. Truncation is legal ONLY for a
    console summary, and only when the omitted count is stated alongside it
    -- the artifact document itself (``flush_artifact``) NEVER truncates a
    list. Callers must pass the FULL, untruncated list into
    ``ProjectArtifact`` fields, and reserve this helper for print
    statements only.

    Returns ``(items_to_print, omitted_count)``.
    """
    if max_items is None or len(items) <= max_items:
        return list(items), 0
    return list(items[:max_items]), len(items) - max_items


def write_skipped_artifact(
    project: str, *, reason: str, run_intent: str,
    artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR,
) -> Path:
    """FR-151/FR-188: a project the run never attempted MUST STILL get a
    written artifact naming it ``SKIPPED``, so corpus-level status
    (ARTIFACT-INTEGRITY, guards.md) is always derived from a real document,
    never a ledger entry with nothing backing it. Carries the normalized
    intent and the fifteen-guard block filled with ``not-evaluated`` (a
    project that never ran cannot have evaluated anything) -- which, per
    guards.md's FR-109 meta-rule, makes the run's verdict ``VACUOUS``
    (exit code 4).
    """
    # Local import: avoids a load-order dependency between the sibling
    # modules T013/T014 add to this package in the same wave.
    from .guards import not_evaluated_guard_block
    from .verdict import exit_code_for

    normalized_intent = normalize_intent(run_intent)
    artifact = ProjectArtifact(
        project=project, run_intent=normalized_intent, revision_pair=revision_pair(),
        dirty_gramtrans=None, coverage_categories=[],
        status=STATUS_SKIPPED, reason=reason,
        started_at=time.time(), finished_at=time.time(),
    )
    artifact.phase_reached = None
    artifact.guards = not_evaluated_guard_block()
    artifact.verdict = "VACUOUS"
    artifact.exit_code = exit_code_for("VACUOUS")
    return flush_artifact(artifact, artifacts_dir)


def _atomic_write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    os.replace(str(tmp), str(path))


def flush_artifact(artifact: ProjectArtifact, artifacts_dir: Path) -> Path:
    """FR-150: flush after every phase, so a crash leaves a partial artifact
    naming the last completed phase, never no evidence at all."""
    out = artifacts_dir / ("%s.json" % re.sub(r"[^A-Za-z0-9._ -]", "_", artifact.project))
    _atomic_write_json(out, asdict(artifact))
    return out
