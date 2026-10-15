"""Helpers for the root conftest's `_no_leaked_host_stubs` guard; see the
comment there. Kept in a module of their own so tests can import them
(`import conftest` resolves to tests/unit/conftest.py, not the root one)."""
from __future__ import annotations

import sys
import types

HOST_ROOTS = ("SIL", "System")


def host_entries() -> dict:
    return {
        k: v for k, v in sys.modules.items()
        if k in HOST_ROOTS or k.startswith(("SIL.", "System."))
    }


def restore_host_stubs(before: dict) -> list:
    """Undo every stub `SIL`/`System` entry added or swapped in since
    `before` was taken. Returns the names it touched."""
    touched = []
    for name, mod in list(host_entries().items()):
        if type(mod) is not types.ModuleType or before.get(name) is mod:
            continue
        if name in before:
            sys.modules[name] = before[name]
        else:
            del sys.modules[name]
        touched.append(name)
    return touched
