"""Force-load guard for duck-typed-fake tests (issue #58).

A test that drives production code with duck-typed fakes must NOT make that
work by putting a fake `SIL.*` module into `sys.modules`. Such a stub makes the
test pass *around* a production branch keyed on the process ("can I import
SIL?") instead of the object ("is this a .NET object?"), and the test then
certifies the broken shape. That is how #55/#56/#57 stayed hidden.

The guard shape (first used in tests/unit/test_reversal_walk.py, 201d9cd):
FORCE-LOAD the real SIL assemblies when this machine has them -- the exact
condition under which a process-keyed branch mishandles a fake -- and assert
the fake is still handled correctly. That is order-independent: it no longer
matters whether an earlier module (test_013_fill_gaps) loaded flexicon as a
side effect. Host-free, `force_sil_loaded()` returns False and the same
assertions must still hold.
"""
from __future__ import annotations

import sys
import types

import pytest


def force_sil_loaded() -> bool:
    """Load pythonnet + the real SIL assemblies if available.

    Returns True when the real `SIL.LCModel` is importable in-process, False
    when the host is absent. Fails the calling test outright if `SIL.LCModel`
    resolves to a plain-module stub: a leaked stub would silently re-mask the
    defect this guard exists to expose.
    """
    try:
        import flexicon.code.BaseOperations  # noqa: F401
        from SIL.LCModel import IPartOfSpeech  # noqa: F401
    except Exception:  # noqa: BLE001 -- host-free is a legal state
        return False
    if type(sys.modules.get("SIL.LCModel")) is types.ModuleType:
        pytest.fail(
            "sys.modules['SIL.LCModel'] is a plain-module stub, not the real "
            "pythonnet namespace -- a stub leaked from another test (#58)")
    return True
