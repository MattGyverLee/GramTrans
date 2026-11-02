"""One live test file per pytest process (#194).

Opening several FLEx projects from several live test modules in ONE process
crashes natively (pythonnet / LCM with multiple projects). Each file passes on
its own. This helper decides, from the collected node ids, whether a run would
mix live modules; the root conftest turns a mix into a usage error.
"""
from __future__ import annotations

import os

LIVE_ENV = "FLEXLIBS_REQUIRE_LIVE"
OVERRIDE_ENV = "GRAMTRANS_ALLOW_MULTI_LIVE"


def live_modules(nodeids):
    """Distinct live test files among ``nodeids`` (tests/integration/*_live.py)."""
    found = set()
    for nid in nodeids:
        path = nid.replace("\\", "/").split("::")[0]
        if path.startswith("tests/integration/") and path.endswith("_live.py"):
            found.add(path)
    return sorted(found)


def multi_live_error(nodeids, environ=None):
    """Return an error message when the run mixes live files, else None."""
    env = os.environ if environ is None else environ
    if env.get(LIVE_ENV) != "1" or env.get(OVERRIDE_ENV) == "1":
        return None
    mods = live_modules(nodeids)
    if len(mods) <= 1:
        return None
    return (
        "[ERROR] %d live test files in one pytest process (%s). Several live "
        "projects in one process crash natively (#194); run ONE live file per "
        "process, or set %s=1 to override."
        % (len(mods), ", ".join(mods), OVERRIDE_ENV)
    )
