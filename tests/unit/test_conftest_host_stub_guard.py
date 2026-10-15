"""The root conftest's `_no_leaked_host_stubs` guard (see its comment).

A stub `SIL` left in `sys.modules` makes the next first import of
flextoolslib raise "'SIL' is not a package" behind a modal MessageBox that
hangs the run (#72). These tests drive the guard's helper directly so they
do not depend on test ordering.
"""
from __future__ import annotations

import sys
import types

import _host_stub_guard as guard


def test_added_stub_is_removed(monkeypatch):
    monkeypatch.delitem(sys.modules, "SIL.GuardProbe", raising=False)
    before = guard.host_entries()
    sys.modules["SIL.GuardProbe"] = types.ModuleType("SIL.GuardProbe")

    assert guard.restore_host_stubs(before) == ["SIL.GuardProbe"]
    assert "SIL.GuardProbe" not in sys.modules


def test_swapped_entry_is_restored(monkeypatch):
    original = types.ModuleType("System.GuardProbe")
    monkeypatch.setitem(sys.modules, "System.GuardProbe", original)
    before = guard.host_entries()
    sys.modules["System.GuardProbe"] = types.ModuleType("System.GuardProbe")

    guard.restore_host_stubs(before)
    assert sys.modules["System.GuardProbe"] is original


def test_non_stub_module_is_kept(monkeypatch):
    class _ClrLike(types.ModuleType):
        """Stands in for pythonnet's CLR.ModuleObject: not exactly ModuleType."""

    monkeypatch.delitem(sys.modules, "SIL.GuardReal", raising=False)
    before = guard.host_entries()
    real = _ClrLike("SIL.GuardReal")
    sys.modules["SIL.GuardReal"] = real
    try:
        assert guard.restore_host_stubs(before) == []
        assert sys.modules["SIL.GuardReal"] is real
    finally:
        sys.modules.pop("SIL.GuardReal", None)


def test_unrelated_modules_are_ignored(monkeypatch):
    monkeypatch.delitem(sys.modules, "SILENT_probe", raising=False)
    before = guard.host_entries()
    sys.modules["SILENT_probe"] = types.ModuleType("SILENT_probe")
    try:
        assert guard.restore_host_stubs(before) == []
    finally:
        sys.modules.pop("SILENT_probe", None)
