"""Feature 035 -- ``debug/fullsweep`` package: the public surface promoted out
of the ``debug/run_fullcopy_sweep.py`` monolith (T001 of
specs/035-fullsweep-fidelity/tasks.md Phase 1).

This package holds the six mechanical groups the monolith already implemented
at commit 8c72bdc:

  * ``corpus``  -- Group A: runtime enumeration, exclusion record, frozen manifest
  * ``safety``  -- Group B: write-safety choke point + source tamper guard
  * ``pool``    -- Group C: parallel target pool, exclusive claim, memory/
                   concurrency gates
  * ``moves``   -- Group D: double-move loop support, idempotency measurement
  * ``artifact``-- Group K: per-project artifact + provenance/revision stamping
  * ``batch``   -- Group L: status ledger, corpus status summary

``debug/run_fullcopy_sweep.py`` is now a thin CLI entry point over this
package. The field-level comparator (Groups E/F/G/H/P, still in review) and
the per-project double-move loop (``run_one_project``) remain in the driver,
not here -- they are not among the six groups this package promotes.

This module performs, ONCE, the same ``sys.path`` bootstrap the monolith did
at import time, so the "reused, not reinvented" sibling debug scripts
(``prescan_type_coverage``, ``audit_guid_preservation``) remain importable by
their existing bare names from every submodule below.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT / "src", _ROOT / "tests" / "integration", _ROOT / "debug"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from .corpus import *  # noqa: F401,F403,E402
from .safety import *  # noqa: F401,F403,E402
from .pool import *  # noqa: F401,F403,E402
from .moves import *  # noqa: F401,F403,E402
from .artifact import *  # noqa: F401,F403,E402 -- includes the driver version/SHA
                          # stamping helpers (gramtrans_revision, flexicon_revision,
                          # revision_pair), re-exported from this one place.
from .batch import *  # noqa: F401,F403,E402

from . import corpus, safety, pool, moves, artifact, batch  # noqa: F401,E402
