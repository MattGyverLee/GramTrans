"""Feature 035 -- Group L: LEDGER (batched, gated, fix-forward execution).
Moved unchanged out of the ``debug/run_fullcopy_sweep.py`` monolith
(T007/T009 of specs/035-fullsweep-fidelity/tasks.md Phase 1).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from .artifact import DEFAULT_ARTIFACTS_DIR, _atomic_write_json

VALID_LEDGER_STATUSES = ("pending", "running", "passed", "failed", "skipped")


class Ledger:
    """FR-156: a durable, per-project status ledger surviving restarts,
    tracked in git (default path lives under specs/035-fullsweep-fidelity/,
    which this repo's CLAUDE.md workflow commits to main -- never a
    gitignored scratch path)."""

    def __init__(self, path: Path = DEFAULT_ARTIFACTS_DIR / "ledger.json"):
        self.path = path
        self._data: dict = {}
        self.load()

    def load(self) -> None:
        if self.path.is_file():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self._data = {}

    def save(self) -> None:
        _atomic_write_json(self.path, self._data)

    def set_status(self, project: str, status: str, *, reason: str = "",
                   revision_pair: Optional[dict] = None) -> None:
        if status not in VALID_LEDGER_STATUSES:
            raise ValueError("invalid ledger status %r" % (status,))
        self._data[project] = {
            "status": status, "reason": reason,
            "revision_pair": revision_pair or {},
            "updated_at": time.time(),
        }
        self.save()

    def get(self, project: str) -> Optional[dict]:
        return self._data.get(project)

    def all(self) -> dict:
        return dict(self._data)


def corpus_status_summary(ledger: Ledger, current_pair: dict) -> dict:
    """FR-157/FR-158: separate currently-valid passes from STALE ones; never
    report a single unqualified "all green" unless every pass shares the
    current driver-and-dependency revision pair."""
    valid, stale, other = [], [], []
    for name, row in ledger.all().items():
        if row.get("status") != "passed":
            other.append(name)
            continue
        if row.get("revision_pair") == current_pair:
            valid.append(name)
        else:
            stale.append(name)
    return {
        "currently_valid_passes": sorted(valid),
        "stale_passes": sorted(stale),
        "other": sorted(other),
        "all_green": bool(valid) and not stale and not other,
    }
