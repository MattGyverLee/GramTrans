"""Package-wide source access for the wizard's structural guards (feature 039, T034).

Why this module exists
----------------------
Several tests in this suite assert over the wizard's own **source text** rather
than over its behaviour, because the thing they are guarding is a literal that
must not exist -- a hard-coded `Step 3 of 5`, a cross-page `\\.page(4)`. A
run-time walk cannot see a literal on a page that run never navigated to, which
is exactly how `Step 3 of 5` survived on `_PageScopeConflict` for four features.

Before feature 039 those scans read `Path(selection_wizard.__file__).read_text()`
and that was the whole wizard. After the split it is one module out of eleven,
and a scan pointed at it would find nothing to complain about while a violation
sat in `wizard_pages_blocks.py` -- passing **vacuously**, which is worse than
failing, because a green test is read as evidence.

`wizard_package_source()` is what those scans should read instead. It concatenates
the facade and every `wizard_*.py` beside it, so a violation anywhere in the
package is visible, and the scan gets stronger as the package grows rather than
weaker.

The non-vacuity rule
--------------------
A scan built on this helper must also assert that it *found* something to look
at -- `assert modules`, `assert total > 0`, `assert match`. This suite already
uses that idiom (`test_036_finish_guard.py` carries `assert total > 0`), and it
is the difference between "no violations exist" and "no source was read".
"""
from __future__ import annotations

import pathlib
import types

_UI = pathlib.Path(__file__).resolve().parents[2] / "src" / "gramtrans" / "Lib" / "ui"

#: The facade, plus every module the split moved code into. Ordered so the
#: concatenation is stable run to run (a diff in a failure message should be
#: about the code, not about dict ordering).
FACADE_NAME = "selection_wizard"


def wizard_module_paths() -> list[pathlib.Path]:
    """Every file whose text a wizard structural guard should cover."""
    paths = [_UI / (FACADE_NAME + ".py")]
    paths += sorted(_UI.glob("wizard_*.py"))
    missing = [p for p in paths if not p.is_file()]
    if missing:
        raise AssertionError(
            "wizard source missing: %s -- the guards read these files, so a "
            "renamed or deleted module must be a loud failure, not a silently "
            "shorter scan" % ", ".join(p.name for p in missing)
        )
    return paths


def wizard_package_source() -> str:
    """The concatenated text of the facade and every `wizard_*.py` module.

    Each file is preceded by a `# === <name> ===` banner so a regex match can be
    attributed to a file when a guard reports an offender.
    """
    parts = []
    for p in wizard_module_paths():
        parts.append("# === %s ===\n%s" % (p.name, p.read_text(encoding="utf-8")))
    text = "\n".join(parts)
    assert text.strip(), "wizard package source is empty -- the scan read nothing"
    return text


def wizard_modules() -> list[types.ModuleType]:
    """The imported wizard modules, facade first.

    Imported through the facade so the eager-import chain is what puts them in
    `sys.modules` -- which is also the property `test_039_module_split.py` guard
    1 asserts, since it is what keeps every page class on one Qt base.
    """
    import importlib

    from gramtrans.Lib.ui import selection_wizard  # noqa: F401  (the chain)

    mods = []
    for p in wizard_module_paths():
        mods.append(importlib.import_module("gramtrans.Lib.ui." + p.stem))
    assert len(mods) > 1, (
        "expected the facade plus at least one wizard_* module; got %d"
        % len(mods)
    )
    return mods


def source_of(module_name: str) -> str:
    """The text of one wizard module, by bare stem."""
    for p in wizard_module_paths():
        if p.stem == module_name:
            return p.read_text(encoding="utf-8")
    raise AssertionError("no wizard module named %r" % module_name)
