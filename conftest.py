"""Pytest configuration: add `src/` to sys.path so `import gramtrans` works
without an editable install in the host environment.

Also adds `tests/unit` to sys.path so helper modules (e.g. _fakes_affix)
can be imported directly by test files without a package structure.

Finally, pins the interface theme off for the whole suite -- see the comment on
`GRAMTRANS_NO_THEME` below.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SRC = Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_TESTS_UNIT = Path(__file__).parent / "tests" / "unit"
if str(_TESTS_UNIT) not in sys.path:
    sys.path.insert(0, str(_TESTS_UNIT))

# Keep the interface theme (Lib/ui/theme.py) out of the test session.
#
# `SelectionWizard.__init__` calls `install_theme()`, which mutates the SHARED
# QApplication palette, style and font -- and restores whatever text size the
# developer last picked in the real GUI from QSettings. Without this pin, a
# developer who had scaled the interface to 160% would run a different suite
# from CI: every Qt widget's font, and therefore any geometry-sensitive
# assertion, would shift under them. `install()` honours GRAMTRANS_NO_THEME by
# returning False and leaving the palette untouched, so wizard-construction
# tests stay hermetic.
#
# `setdefault`, not a plain assignment: `GRAMTRANS_NO_THEME=0` in the
# environment still lets someone deliberately run the suite themed. The theme's
# own tests do not need this off -- they exercise an un-installed ThemeManager.
os.environ.setdefault("GRAMTRANS_NO_THEME", "1")


# ---------------------------------------------------------------------------
# Stub `SIL` / `System` modules must not outlive the test that installed them.
#
# Many unit tests fake the .NET host by putting a plain `types.ModuleType`
# into `sys.modules` -- often via `sys.modules.setdefault("SIL", ...)`, which
# is never undone. A plain module has no `__path__`, so once it is left
# behind, any later FIRST import of `flextoolslib` / flexicon's `FLExInit`
# (`from SIL.FieldWorks... import ...`) fails with
#     No module named 'SIL.FieldWorks'; 'SIL' is not a package
# and flextoolslib reports that through a MODAL `MessageBox.Show` -- which
# blocks the pytest process until someone clicks OK, and blocks forever on a
# headless CI runner (#72). Whether it fires depends on test order, so a
# per-file or randomised run can trip it while the full ordered suite does not.
#
# This guard (helpers in tests/unit/_host_stub_guard.py) snapshots those entries before each test and, afterwards, removes
# or restores any that the test changed TO a plain stub. Real pythonnet
# namespaces are `CLR.ModuleObject`, never exactly `types.ModuleType`, so a
# test that genuinely loads the SIL assemblies keeps them. Module-scoped
# stubs installed before a test starts are part of its snapshot and survive.
# Autouse in the root conftest, so it is set up first and torn down last --
# after each test's own fixtures have had their chance to restore.
# ---------------------------------------------------------------------------
import pytest as _pytest

from _host_stub_guard import host_entries as _host_entries, restore_host_stubs as _restore_host_stubs  # noqa: E402


@_pytest.fixture(autouse=True)
def _no_leaked_host_stubs():
    before = _host_entries()
    yield
    _restore_host_stubs(before)
