"""T012 part 3 — one module may read FieldWorks globals, and this enforces it.

`standalone/fwglobals.py` is the sole permitted reader of ``FWCodeDir``,
``FWProjectsDir``, ``FWExecutable``, ``FWShortVersion``, ``FWLongVersion`` and
``FW_SUPPORTED_VERSIONS``. Everywhere else in `src/gramtrans/` and `build/`,
naming one of those symbols is a hard failure.

Why a test and not a review habit: the failure mode is silent. A reader that
gets a stale or empty value does not crash — it reports "FieldWorks not
detected" on a perfectly working machine, which sends the user off to
reinstall software they already have. Wired into the regression gate
(`.github/workflows/regression.yml`), so it guards phases 3-6 as they are
written rather than auditing them afterwards.

The ban covers all three ways to reach the symbols:

1. attribute reads   — ``flexicon.FWCodeDir``, ``flexicon.code.FLExGlobals.FWCodeDir``
2. name imports      — ``from flexicon import FWCodeDir``
3. dynamic reads     — ``getattr(flexicon, "FWCodeDir")``
4. the symbol as a bare string literal — which is how `fwglobals.py` itself
   spells its reads (``_read("FWCodeDir")``), and therefore also how a module
   trying to slip past rules 1-3 would spell one.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCANNED_ROOTS = (_REPO_ROOT / "src" / "gramtrans", _REPO_ROOT / "build")

# The one file allowed to name them, repo-relative and POSIX-separated.
_SOLE_ACCESSOR = "src/gramtrans/standalone/fwglobals.py"

_BANNED_NAMES = frozenset(
    {
        "FWCodeDir",
        "FWProjectsDir",
        "FWExecutable",
        "FWShortVersion",
        "FWLongVersion",
        "FW_SUPPORTED_VERSIONS",
    }
)


#: Directories under a scanned root that are not ours to police.
#:
#: `build/` is a tracked source tree AND the place PyInstaller writes its
#: throwaway venv and output. Once a build has run, `build/.venv-build/Lib/
#: site-packages/` holds flexicon, flexlibs and flextoolslib — which read the
#: FieldWorks globals directly, because that is their job. Scanning them turned
#: the ban into seven failures about other people's code. The rule is about
#: **our** modules; generated and vendored trees are excluded by name.
_NOT_OURS = {"__pycache__", ".venv-build", "dist", "site-packages"}


def _python_files():
    seen = []
    for root in _SCANNED_ROOTS:
        if root.is_dir():
            seen.extend(sorted(root.rglob("*.py")))
    return [
        p for p in seen
        if not (_NOT_OURS & set(p.parts))
        # `build/build/` is PyInstaller's work directory; the repo's own
        # sources never sit two `build` levels deep.
        and p.parts.count("build") < 2
    ]


def _rel(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _violations(tree: ast.AST):
    """Every banned read in one module, as (kind, symbol, lineno) triples."""
    found = []
    for node in ast.walk(tree):
        # 1. `<anything>.FWCodeDir` — catches both the package re-export and
        #    the module attribute, which is the point: even the *correct* read
        #    belongs in exactly one file.
        if isinstance(node, ast.Attribute) and node.attr in _BANNED_NAMES:
            found.append(("attribute", node.attr, node.lineno))

        # 2. `from flexicon import FWCodeDir` / `from ... import FWCodeDir as x`
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in _BANNED_NAMES:
                    found.append(("import-from", alias.name, node.lineno))

        # 3. `getattr(flexicon, "FWCodeDir")` and any getattr whose literal
        #    second argument starts with FW — a dynamic escape hatch is still
        #    an escape hatch.
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
            and node.args[1].value.startswith("FW")
        ):
            found.append(("getattr", node.args[1].value, node.lineno))

        # 4. The bare symbol as a string literal. `_read("FWCodeDir")` is how
        #    the accessor spells its own reads, and `name = "FWCodeDir";
        #    getattr(g, name)` is how a module would spell one to dodge rule 3.
        #    Exact equality, so a docstring that *mentions* FWCodeDir in a
        #    sentence is not a match.
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in _BANNED_NAMES
        ):
            found.append(("string-literal", node.value, node.lineno))
    return found


@pytest.mark.parametrize("path", _python_files(), ids=_rel)
def test_only_fwglobals_reads_the_fieldworks_globals(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = _violations(tree)

    if _rel(path) == _SOLE_ACCESSOR:
        # The accessor is not merely permitted to read them — it is supposed
        # to. An "accessor" that stopped reading them would mean some other
        # path had quietly taken over.
        assert found, (
            f"{_SOLE_ACCESSOR} is the sole accessor but names none of "
            f"{sorted(_BANNED_NAMES)} — has the read moved elsewhere?"
        )
        return

    assert not found, (
        f"{_rel(path)} reads FieldWorks globals directly: "
        + ", ".join(f"{kind} {sym!r} at line {ln}" for kind, sym, ln in found)
        + f". Go through {_SOLE_ACCESSOR} instead — a direct read that comes "
        "back empty reports 'FieldWorks not detected' on a healthy machine."
    )


def test_the_scan_covers_the_shell_and_the_build_tree():
    """A parametrisation that collapses to nothing would pass silently."""
    scanned = {_rel(p) for p in _python_files()}
    assert _SOLE_ACCESSOR in scanned, "the sole accessor itself was not scanned"
    assert any(p.startswith("src/gramtrans/Lib/") for p in scanned)
    assert "src/gramtrans/gramtrans.py" in scanned


def test_the_ban_would_actually_fire():
    """Prove the matcher catches all three forms, so a green run means something."""
    sample = (
        "import flexicon\n"
        "a = flexicon.FWProjectsDir\n"
        "from flexicon import FWCodeDir\n"
        "b = getattr(flexicon, 'FWShortVersion')\n"
        "c = flexicon.code.FLExGlobals.FWLongVersion\n"
        "name = 'FWExecutable'\n"
    )
    found = _violations(ast.parse(sample))
    kinds = {kind for kind, _, _ in found}
    assert kinds == {"attribute", "import-from", "getattr", "string-literal"}
    # 'FWShortVersion' counts twice on line 4 — once as the getattr argument
    # and once as a banned string literal. Both are the same defect; the
    # message lists both rather than pretending one of them is not there.
    assert len(found) == 6


def test_a_clean_module_is_not_flagged():
    """And that it does not fire on the imports the module legitimately makes."""
    sample = (
        "import flexicon\n"
        "from flexicon import FLExProject, POSOperations\n"
        "p = flexicon.AllProjectNames()\n"
    )
    assert _violations(ast.parse(sample)) == []


# ---------------------------------------------------------------------------
# T012 part 2 — loud, not false
#
# The AST ban stops a *new* direct reader appearing. These cover the other
# half: what the accessor does when a value is missing anyway. It must never
# be mistaken for "FieldWorks is not installed", because that message sends a
# user with a working install off to reinstall it.
# ---------------------------------------------------------------------------

def test_reading_before_initialisation_is_a_runtime_error_not_a_missing_install():
    from gramtrans.standalone import fwglobals

    fwglobals.reset_for_tests()
    try:
        with pytest.raises(fwglobals.FieldWorksRuntimeUnavailable):
            fwglobals.projects_dir()
        assert not fwglobals.is_initialized()
    finally:
        fwglobals.reset_for_tests()


def test_a_none_global_after_initialisation_maps_to_fr033_never_fr031(monkeypatch):
    from gramtrans.standalone import fwglobals

    flex_globals = pytest.importorskip("flexicon.code.FLExGlobals")
    monkeypatch.setattr(flex_globals, "FWProjectsDir", None, raising=False)
    fwglobals.mark_initialized()
    try:
        with pytest.raises(fwglobals.FieldWorksRuntimeUnavailable):
            fwglobals.projects_dir()
        # The distinction is the entire point of the two types.
        assert not issubclass(
            fwglobals.FieldWorksRuntimeUnavailable, fwglobals.FieldWorksNotDetected
        )
    finally:
        fwglobals.reset_for_tests()


def test_an_empty_string_global_is_also_loud():
    from gramtrans.standalone import fwglobals

    flex_globals = pytest.importorskip("flexicon.code.FLExGlobals")
    original = flex_globals.FWCodeDir
    flex_globals.FWCodeDir = "   "
    fwglobals.mark_initialized()
    try:
        with pytest.raises(fwglobals.FieldWorksRuntimeUnavailable):
            fwglobals.code_dir()
    finally:
        flex_globals.FWCodeDir = original
        fwglobals.reset_for_tests()


def test_accessors_read_live_module_state_not_an_import_time_snapshot():
    """The R1 discipline, stated as behaviour rather than as a code rule.

    flexicon 4.3.1's package re-exports happen to be populated (see the
    `fwglobals` docstring), so this does not fail today for the reason R1
    predicted. It still has to hold: an accessor wired to a name bound at
    import would not see this change.
    """
    from gramtrans.standalone import fwglobals

    flex_globals = pytest.importorskip("flexicon.code.FLExGlobals")
    original = flex_globals.FWProjectsDir
    flex_globals.FWProjectsDir = r"D:\Relocated\Projects"
    fwglobals.mark_initialized()
    try:
        assert fwglobals.projects_dir() == r"D:\Relocated\Projects"
    finally:
        flex_globals.FWProjectsDir = original
        fwglobals.reset_for_tests()
