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


def fieldworks_installed() -> bool:
    """True when the FieldWorks registry entry flexicon looks for exists."""
    try:
        import winreg
    except ImportError:  # not Windows
        return False
    key = r"SOFTWARE\SIL\FieldWorks\9"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, key) as k:
                if winreg.QueryValueEx(k, "RootCodeDir")[0]:
                    return True
        except OSError:
            continue
    return False


def block_flextoolslib_without_fieldworks() -> bool:
    """Make `import flextoolslib` raise ImportError when FieldWorks is absent.

    flextoolslib's import runs `from flexlibs import ...`; with no FieldWorks
    that fails, and flextoolslib reports the failure through a MODAL
    `MessageBox.Show`, which blocks forever on a headless runner (#72: the CI
    gate hung in collection at flextoolslib/code/FLExTools.py line 94, reached
    from tests/unit/test_ws_path_fidelity.py importing gramtrans.gramtrans).
    A `None` entry in sys.modules turns that into a plain ImportError, which
    the tests that guard the import already handle. Returns True if blocked.
    """
    if fieldworks_installed() or "flextoolslib" in sys.modules:
        return False
    sys.modules["flextoolslib"] = None
    return True
