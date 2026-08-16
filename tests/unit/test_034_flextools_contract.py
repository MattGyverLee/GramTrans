"""T008 / FR-021, FR-016, SC-013 — the FlexTools path is unchanged.

The regression gate's centrepiece. Feature 034 adds a second host; this file
is the standing proof that adding it did not move anything the *first* host
stands on: the module still imports, FlexTools still finds all six `FTM_*`
metadata keys, `MainFunction` still takes its three positional arguments, and
nothing on the shared side has learned to import the shell.

Written at the start of the feature with only the assertions that are true
*today*, so the gate is green from the first commit and every later red is a
real regression. T023 and T035 add the exception-1 and exception-3 assertions
as those exceptions land.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src" / "gramtrans"
_ENTRY = _SRC / "gramtrans.py"
_LIB = _SRC / "Lib"


# ---------------------------------------------------------------------------
# The import + metadata contract
# ---------------------------------------------------------------------------

def _entry_module():
    """Import the FlexTools entry module, failing loudly rather than skipping.

    A skip here would make the regression gate green on a machine that cannot
    load the module at all, which is precisely the failure the gate exists to
    catch. `flextoolslib` and `pyflexicon` are therefore hard requirements of
    the gate environment, not optional extras.
    """
    import gramtrans.gramtrans as entry

    return entry


def test_entry_module_imports():
    assert _entry_module() is not None


def test_docs_carries_all_six_ftm_keys_with_their_current_values():
    entry = _entry_module()
    from flextoolslib import (
        FTM_Description,
        FTM_Help,
        FTM_ModifiesDB,
        FTM_Name,
        FTM_Synopsis,
        FTM_Version,
    )

    docs = entry.docs
    for key in (FTM_Name, FTM_Version, FTM_ModifiesDB, FTM_Synopsis, FTM_Help,
                FTM_Description):
        assert key in docs, f"FlexTools metadata key {key!r} is missing from docs"

    # The five scalars are pinned exactly: they are what FlexTools renders in
    # its module list, so a change to any of them is a change a user sees.
    assert docs[FTM_Name] == "GramTrans — Additive Grammar Transfer"
    assert docs[FTM_ModifiesDB] is True
    assert docs[FTM_Synopsis] == (
        "Copy grammar pieces from a toy source project into the host target."
    )
    assert docs[FTM_Help] == ""
    # Version tracks __version__ rather than a literal, so a deliberate bump
    # is not a false red — but the two must not drift apart.
    assert docs[FTM_Version] == entry.__version__
    assert isinstance(entry.__version__, str) and entry.__version__

    # The description is prose and legitimately edited; only its presence is
    # part of the host contract.
    assert isinstance(docs[FTM_Description], str) and docs[FTM_Description].strip()


def test_main_function_accepts_three_positional_arguments():
    entry = _entry_module()
    sig = inspect.signature(entry.MainFunction)
    positional = [
        p.name
        for p in sig.parameters.values()
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    assert positional == ["project", "report", "modifyAllowed"], (
        "FlexTools calls MainFunction(project, report, modifyAllowed) positionally; "
        f"got {positional}"
    )
    for name in positional:
        assert sig.parameters[name].default is inspect.Parameter.empty, (
            f"{name} must stay required — a default would let a mis-wired host "
            "call MainFunction with fewer arguments and get a silent no-op"
        )


def test_default_source_project_and_headless_fallback_still_exist():
    """Exception list, "Explicitly not changed": these stay put.

    FR-005 is a *reachability* requirement on the standalone, not a demand to
    delete FlexTools behaviour. Removing them would be a shared-code change
    that is not on the plan's exception list.
    """
    entry = _entry_module()
    assert entry.DEFAULT_SOURCE_PROJECT == "Ejagham Mini"
    assert callable(entry._headless_phase0)


# ---------------------------------------------------------------------------
# FR-016 — the import direction
# ---------------------------------------------------------------------------

def _shared_python_files():
    yield _ENTRY
    yield from sorted(_LIB.rglob("*.py"))


def _imported_names(tree: ast.AST):
    """Every dotted name a module pulls in, from both import forms."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            # `from . import x` has module=None; level>0 is a relative import,
            # which cannot reach `gramtrans.standalone` from under Lib/ without
            # naming it, so the module string is the whole story here.
            base = node.module or ""
            yield base
            for alias in node.names:
                yield f"{base}.{alias.name}" if base else alias.name


@pytest.mark.parametrize(
    "path", list(_shared_python_files()), ids=lambda p: str(p.relative_to(_SRC))
)
def test_shared_code_never_imports_the_standalone_shell(path: Path):
    """FR-016: the dependency runs shell -> shared, never the reverse.

    Checked by AST rather than by grep so a mention in a docstring or comment
    (there are several, deliberately) does not register as an import.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = [
        name
        for name in _imported_names(tree)
        if name == "gramtrans.standalone" or name.startswith("gramtrans.standalone.")
    ]
    assert not offenders, (
        f"{path.relative_to(_REPO_ROOT)} imports {offenders} — shared code must "
        "not depend on the standalone shell (FR-016)"
    )


def test_the_scan_actually_covers_the_shared_tree():
    """Guard against the parametrisation silently collapsing to zero files."""
    files = list(_shared_python_files())
    assert _ENTRY in files
    assert len(files) > 20, f"expected the whole Lib/ tree, scanned only {len(files)}"
