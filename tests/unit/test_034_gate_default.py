"""T006 / FR-017, SC-013 — the FlexTools default gate is satisfied, silently.

`AlwaysSatisfiedGate` is the thing that makes feature 034 invisible to
FlexTools. If it ever grows a dialog, a prompt, an import, or a `False`
return, every FlexTools user gets a new step in a flow that used to have none.
These tests are deliberately paranoid about that.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

from gramtrans.Lib.gate import (
    FLEXTOOLS_FINISH_SUBTITLE,
    AlwaysSatisfiedGate,
    ConfirmationGate,
    resolve_gate,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"

# The `_PageFinish` subtitle exactly as FlexTools users read it today, copied
# here by hand on purpose. `Lib/gate.py` holds the same string; comparing the
# two is what turns "someone edited the wizard's subtitle" into a red gate
# rather than a silent behaviour change for the other host (SC-013).
_TODAYS_SUBTITLE = (
    "Click 'Execute Move' to write all planned actions to the target project. "
    "This is the only write point -- changes can be undone in FLEx with Ctrl+Z."
)


def test_confirm_returns_true_for_any_target_name():
    gate = AlwaysSatisfiedGate()
    assert gate.confirm("anything") is True
    assert gate.confirm("") is True
    assert gate.confirm("Ejagham Full GT-Test") is True


def test_finish_page_subtitle_is_byte_identical_to_todays_literal():
    assert AlwaysSatisfiedGate().finish_page_subtitle() == _TODAYS_SUBTITLE
    assert FLEXTOOLS_FINISH_SUBTITLE == _TODAYS_SUBTITLE


def test_default_gate_satisfies_the_structural_protocol():
    assert isinstance(AlwaysSatisfiedGate(), ConfirmationGate)


def test_resolve_gate_maps_none_to_the_default_and_passes_others_through():
    assert isinstance(resolve_gate(None), AlwaysSatisfiedGate)

    class _Other:
        def confirm(self, target_project_name):
            return False

        def finish_page_subtitle(self):
            return "x"

    other = _Other()
    assert resolve_gate(other) is other


def test_gate_module_imports_nothing_heavy():
    """`Lib/gate.py` must not drag in PyQt6, flexicon or the engine.

    The wizard constructs its default gate during page construction, and the
    self-check has to be able to reason about the gate on a machine where
    FieldWorks is missing — that is the whole point of FR-036. A stray import
    here would make the default gate un-constructible in exactly the
    situations it needs to work.
    """
    import ast

    import gramtrans.Lib.gate as gate_mod

    tree = ast.parse(Path(gate_mod.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    # AST, not grep: the docstring names PyQt6 and flexicon on purpose, to say
    # why they are absent. Only real imports count.
    roots = {name.split(".")[0] for name in imported}
    for forbidden in ("PyQt6", "flexicon", "flextoolslib"):
        assert forbidden not in roots, f"Lib/gate.py must not import {forbidden}"
    assert not any(name.startswith("gramtrans.standalone") for name in imported)
    assert roots <= {"typing", "__future__"}, f"unexpected imports in Lib/gate.py: {roots}"


def test_default_gate_constructs_and_confirms_with_no_qapplication():
    """Runs in a *subprocess* with PyQt6 blocked at the import hook.

    Asserting "no QApplication exists" in-process is worthless — the rest of
    the unit suite may already have built one, and a gate that quietly reached
    for `QtWidgets` would find it. Poisoning the import is the only honest
    version of this check.
    """
    script = textwrap.dedent(
        """
        import sys

        class _Block:
            def find_module(self, name, path=None):
                return self if name == "PyQt6" or name.startswith("PyQt6.") else None
            def load_module(self, name):
                raise ImportError("PyQt6 is blocked for this test")
            # PEP 451 surface, for import systems that prefer it.
            def find_spec(self, name, path=None, target=None):
                if name == "PyQt6" or name.startswith("PyQt6."):
                    raise ImportError("PyQt6 is blocked for this test")
                return None

        sys.meta_path.insert(0, _Block())

        from gramtrans.Lib.gate import AlwaysSatisfiedGate
        gate = AlwaysSatisfiedGate()
        assert gate.confirm("Some Target") is True
        assert "Ctrl+Z" in gate.finish_page_subtitle()
        assert "PyQt6" not in sys.modules, "constructing the default gate imported PyQt6"
        print("OK")
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        env={**_env_with_src()},
    )
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    assert "OK" in proc.stdout


def _env_with_src():
    import os

    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(_SRC) + (os.pathsep + existing if existing else "")
    return env
