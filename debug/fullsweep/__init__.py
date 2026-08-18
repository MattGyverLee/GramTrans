"""Feature 035 -- ``debug/fullsweep`` package: the public surface promoted out
of the ``debug/run_fullcopy_sweep.py`` monolith (T001 of
specs/035-fullsweep-fidelity/tasks.md Phase 1).

This package holds the six mechanical groups the monolith already implemented
at commit 8c72bdc, plus the Phase 2 taxonomy spine (T011-T014,
specs/035-fullsweep-fidelity/tasks.md) added on top of it:

  * ``corpus``  -- Group A: runtime enumeration, exclusion record, frozen manifest
  * ``safety``  -- Group B: write-safety choke point + source tamper guard
  * ``pool``    -- Group C: parallel target pool, exclusive claim, memory/
                   concurrency gates
  * ``moves``   -- Group D: double-move loop support, idempotency measurement
  * ``artifact``-- Group K: per-project artifact + provenance/revision stamping
                   (extended in Phase 2 with the six-name phase vocabulary,
                   intent normalization, and the always-written SKIPPED
                   artifact -- T013)
  * ``batch``   -- Group L: status ledger, corpus status summary
  * ``errors``  -- Group N: failure taxonomy, abort scope, the cross-worker
                   out-of-collection abort flag (T011)
  * ``verdict`` -- Group G: the ten verdicts, severity ordering, corpus
                   aggregation (T012)
  * ``guards``  -- Group F: the fifteen-guard registry (T014)
  * ``identity``-- FR-183..FR-187: tool-owned identity, evaluation state vs
                   agent identity, the natural-key basis and its roster, and the
                   IDENTITY-SUBSTITUTION remap record (T028)

``debug/run_fullcopy_sweep.py`` is now a thin CLI entry point over this
package. The field-level comparator's REAL logic (Groups E/H/P, still in
review) remains a stub in the driver; the per-project double-move loop
(``run_one_project``) also remains in the driver, wired to this package's
guard registry and verdict model (T016) so an unimplemented sweep reports
``VACUOUS`` end to end.

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
from .errors import *  # noqa: F401,F403,E402 -- Group N: failure taxonomy, abort scope
from .verdict import *  # noqa: F401,F403,E402 -- Group G: verdicts, severity, aggregation
from .guards import *  # noqa: F401,F403,E402 -- Group F: the fifteen-guard registry
from .baseline import *  # noqa: F401,F403,E402 -- Group M: baseline pinning/containment (T020)
from .preflight import *  # noqa: F401,F403,E402 -- Group I: capability preflight (T022)
from .identity import *  # noqa: F401,F403,E402 -- identity rules FR-183..FR-187 (T028)
from .allowlist import *  # noqa: F401,F403,E402 -- loss-reason allowlist, FR-115..FR-117 (T032)
from .compare import *  # noqa: F401,F403,E402 -- object-level accounting plane, FR-097 (T031)

from . import (corpus, safety, pool, moves, artifact, batch, errors, verdict,  # noqa: F401,E402
               guards, baseline, preflight, identity, allowlist, compare)

# NOTE for tests and callers: ``import *`` above BINDS A COPY of each module
# global onto this package namespace. Patching ``fullsweep.NAME`` therefore
# does NOT change what the defining module reads. Patch the DEFINING module
# (``fullsweep.pool.CONCURRENCY_TRIAL_ARTIFACT``, not
# ``fullsweep.CONCURRENCY_TRIAL_ARTIFACT``) -- the submodules are re-exported
# on the line above precisely so that is always possible.
