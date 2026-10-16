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

from _host_stub_guard import (  # noqa: E402
    block_flextoolslib_without_fieldworks as _block_flextoolslib,
    host_entries as _host_entries,
    restore_host_stubs as _restore_host_stubs,
)

# Runs at conftest import, i.e. before any test module is collected. See the
# helper's docstring: without FieldWorks, importing flextoolslib raises a modal
# MessageBox that hangs a headless runner forever (#72).
FLEXTOOLSLIB_BLOCKED = _block_flextoolslib()


@_pytest.fixture(autouse=True)
def _no_leaked_host_stubs():
    before = _host_entries()
    yield
    _restore_host_stubs(before)


# ---------------------------------------------------------------------------
# Hosted CI runners have no FieldWorks (#72).
#
# With no FieldWorks registry entry, `import flexicon` raises
# "64bit FieldWorks 9 not found", and flextoolslib cannot import at all (see
# FLEXTOOLSLIB_BLOCKED above). Tests that need the real LCM stack therefore
# cannot run there. Rather than baselining ~75 permanent failures in
# .github/known-failures.txt (a list that rots), such tests are SKIPPED, and
# only when FieldWorks is genuinely absent. On any machine that has FieldWorks
# this whole block is inert, so the live gates keep their full strength.
#
#   * tests/integration/ needs live projects / run reports on disk;
#   * a failure/error whose message is the FieldWorks-not-found / flextoolslib-
#     blocked symptom is converted to a skip (it is the environment, not the
#     code under test);
#   * _FW_ONLY_TESTS: tests that only fail on such a machine through a
#     secondary symptom (an introspection dict carrying {'error': ...}).
#     This includes the test_035 capability-fingerprint pins: they compare
#     against the local editable flexicon (an unrelated rev) and
#     test_a_site_packages_resolution_fails_the_preflight forbids a
#     site-packages flexicon -- which is exactly what CI installs from PyPI --
#     so they cannot pass against PyPI pyflexicon, with or without FieldWorks.
# ---------------------------------------------------------------------------
from _host_stub_guard import fieldworks_installed as _fieldworks_installed  # noqa: E402

_NO_FIELDWORKS = not _fieldworks_installed()
_FW_SYMPTOMS = ("FieldWorks 9 not found", "import of flextoolslib halted")
_FW_ONLY_TESTS = frozenset({
    "test_035_sweep_safety.py::test_a_changed_default_is_reported_as_a_field_level_difference",
    "test_035_sweep_safety.py::test_seven_grammar_overrides_are_declared_and_the_eighth_is_a_recorded_retirement",
    "test_035_sweep_safety.py::test_the_dead_lexicon_accessor_must_not_resolve",
    "test_035_sweep_safety.py::test_the_guid_preserving_create_surface_is_pinned_and_present",
    "test_034_prereq_report.py::test_detection_reads_the_live_module_attribute",
    "test_034_fwglobals_only.py::test_accessors_read_live_module_state_not_an_import_time_snapshot",
})


def pytest_collection_modifyitems(config, items):
    if not _NO_FIELDWORKS:
        return
    for item in items:
        nodeid = item.nodeid.replace("\\", "/")
        if nodeid.startswith("tests/integration/"):
            item.add_marker(_pytest.mark.skip(
                reason="needs live FieldWorks projects; none on this machine (#72)"))
        elif nodeid.split("/")[-1].split("[")[0] in _FW_ONLY_TESTS:
            item.add_marker(_pytest.mark.skip(
                reason="needs a live flexicon/FieldWorks; none on this machine (#72)"))


@_pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    if not _NO_FIELDWORKS:
        return
    report = outcome.get_result()
    if report.outcome != "failed" or call.excinfo is None:
        return
    text = str(call.excinfo.value)
    if any(sym in text for sym in _FW_SYMPTOMS):
        report.outcome = "skipped"
        report.longrepr = (str(item.path), item.location[1] or 0,
                           "Skipped: no FieldWorks on this machine (#72): " + text[:200])
