"""Feature 035 -- Group K: ARTIFACT AND PROVENANCE. Moved unchanged out of the
``debug/run_fullcopy_sweep.py`` monolith (T006/T009 of
specs/035-fullsweep-fidelity/tasks.md Phase 1).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
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
