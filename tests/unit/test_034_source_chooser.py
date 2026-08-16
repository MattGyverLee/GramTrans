"""T014 / FR-002, FR-004, FR-005 — no project is ever assumed.

The source chooser is the defining difference between this host and FlexTools.
FlexTools *supplies* the source — whatever project the user already had open.
The standalone has no such thing, so the source is **picked**, and the spec is
emphatic that it is never inferred, defaulted, remembered, or hard-coded.

Two halves, matching the two ways that can go wrong:

* **Reachability (FR-005)** — a hard-coded project name that no screen shows
  is still a hard-coded project name if some code path can reach it. Scanned
  statically over the whole shell.
* **The chooser itself (FR-002/FR-004)** — nothing pre-selected, advance
  disabled until a deliberate choice, nothing persisted, and the chosen source
  gone from the target list.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

# SC-007 convention: offscreen platform before Qt is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

PyQt6 = pytest.importorskip("PyQt6")

from PyQt6 import QtWidgets  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHELL = _REPO_ROOT / "src" / "gramtrans" / "standalone"


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _shell_modules():
    return [p for p in sorted(_SHELL.rglob("*.py")) if "__pycache__" not in p.parts]


# ===========================================================================
# FR-005 — reachability
# ===========================================================================

# Project names that appear in the repository today and must not appear in
# the shell. "Ejagham" covers both `Ejagham Mini` (the module's historical
# DEFAULT_SOURCE_PROJECT) and the GT-Test target.
_BANNED_SUBSTRINGS = ("DEFAULT_SOURCE_PROJECT", "Ejagham", "Sena 3", "Mbugwe")


def _string_constants(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value, node.lineno


def _named_identifiers(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            yield node.id, node.lineno
        elif isinstance(node, ast.Attribute):
            yield node.attr, node.lineno


@pytest.mark.parametrize(
    "path", _shell_modules(), ids=lambda p: p.relative_to(_REPO_ROOT).as_posix()
)
def test_no_shell_module_names_a_concrete_project(path: Path):
    """No project literal anywhere in the shell, in code *or* in prose.

    Prose counts here, unlike the FR-016 import scan: a docstring saying "for
    example, Ejagham Mini" is how a hard-coded default gets reintroduced by a
    reader who takes the example for a specification.
    """
    text = path.read_text(encoding="utf-8")
    hits = [b for b in _BANNED_SUBSTRINGS if b in text]
    assert not hits, (
        f"{path.relative_to(_REPO_ROOT).as_posix()} names {hits}. The standalone "
        "picks its source; it never assumes, defaults to, or illustrates one "
        "(FR-004/FR-005)."
    )


@pytest.mark.parametrize(
    "path", _shell_modules(), ids=lambda p: p.relative_to(_REPO_ROOT).as_posix()
)
def test_no_shell_module_can_reach_the_headless_fallback(path: Path):
    """FR-005/FR-006: `_headless_phase0` is unreachable from this host.

    It stays in `gramtrans.py` untouched — deleting it would be an unlisted
    shared-code change for FlexTools' benefit-free. What must hold is that
    nothing here calls it, and that the shell asserts PyQt6 at startup so
    `MainFunction` never takes that branch.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    reached = [
        (name, lineno)
        for name, lineno in _named_identifiers(tree)
        if name == "_headless_phase0"
    ]
    assert not reached, (
        f"{path.relative_to(_REPO_ROOT).as_posix()} references _headless_phase0 "
        f"at line(s) {[ln for _, ln in reached]} — the no-interface fallback must "
        "be unreachable from the standalone (FR-005, FR-006)."
    )


def test_the_reachability_scan_actually_covers_the_shell():
    names = {p.name for p in _shell_modules()}
    assert "__init__.py" in names
    assert "fwglobals.py" in names
    assert len(names) >= 2


def test_the_reachability_matcher_would_fire():
    """A green scan means nothing unless the matcher can go red."""
    tree = ast.parse("x = _headless_phase0\n")
    assert any(n == "_headless_phase0" for n, _ in _named_identifiers(tree))
    tree2 = ast.parse("NAME = 'Ejagham Mini'\n")
    assert any("Ejagham" in v for v, _ in _string_constants(tree2))


# ===========================================================================
# FR-002 / FR-004 — the chooser
# ===========================================================================

_PROJECTS = ["Alpha", "Beta", "Gamma"]


@pytest.fixture()
def chooser(qapp):
    from gramtrans.standalone.source_picker import SourcePickerDialog

    return SourcePickerDialog(list(_PROJECTS))


def test_the_list_is_populated_from_the_enumerated_projects(chooser):
    assert chooser.project_names() == _PROJECTS


def test_nothing_is_selected_on_construction(chooser):
    assert chooser.selected_project_name() is None


def test_the_advance_control_starts_disabled(chooser):
    assert chooser.advance_enabled() is False


def test_a_deliberate_choice_enables_the_advance_control(chooser):
    chooser.select_by_name("Beta")
    assert chooser.selected_project_name() == "Beta"
    assert chooser.advance_enabled() is True


def test_clearing_the_selection_re_disables_the_advance_control(chooser):
    chooser.select_by_name("Beta")
    assert chooser.advance_enabled() is True
    chooser.clear_selection()
    assert chooser.selected_project_name() is None
    assert chooser.advance_enabled() is False


def test_nothing_is_remembered_between_constructions(qapp):
    """No last-used memory: FR-004 has no "default" and no "previous"."""
    from gramtrans.standalone.source_picker import SourcePickerDialog

    first = SourcePickerDialog(list(_PROJECTS))
    first.select_by_name("Gamma")
    assert first.selected_project_name() == "Gamma"

    second = SourcePickerDialog(list(_PROJECTS))
    assert second.selected_project_name() is None
    assert second.advance_enabled() is False


def test_the_screen_warns_that_the_target_must_be_closed_even_for_a_preview(chooser):
    """FR-030, stated before selection, because `bind_target` opens the target
    write-enabled in *both* modes — so even a Preview needs it closed in FLEx."""
    text = chooser.guidance_text()
    lowered = text.lower()
    assert "close" in lowered or "closed" in lowered
    assert "preview" in lowered
    # Either the product's full name or the abbreviation users say out loud.
    assert "fieldworks" in lowered or "flex" in lowered


def test_an_empty_project_list_gets_its_own_message_not_an_empty_dialog(qapp):
    from gramtrans.standalone.source_picker import SourcePickerDialog

    dlg = SourcePickerDialog([])
    assert dlg.advance_enabled() is False
    assert dlg.is_empty() is True
    assert dlg.empty_message()


def test_an_unopenable_project_is_reported_by_name_and_the_rest_stay_selectable(qapp):
    """FR-034: one bad project does not take the dialog down with it."""
    from gramtrans.standalone.source_picker import SourcePickerDialog

    dlg = SourcePickerDialog(list(_PROJECTS))
    dlg.mark_unopenable("Beta", "the project is open in FLEx")

    assert "Beta" in dlg.unopenable_message()
    assert "the project is open in FLEx" in dlg.unopenable_message()
    # The rest of the list is untouched and still choosable.
    assert dlg.project_names() == _PROJECTS
    dlg.select_by_name("Gamma")
    assert dlg.selected_project_name() == "Gamma"
    assert dlg.advance_enabled() is True


# ===========================================================================
# US1 acceptance scenario 3 — the chosen source is not offered as a target
# ===========================================================================

def test_the_chosen_source_is_absent_from_the_target_candidates(tmp_path):
    from gramtrans.Lib import api as gt_api

    for name in _PROJECTS:
        d = tmp_path / name
        d.mkdir()
        (d / f"{name}.fwdata").write_text("<!-- fixture -->", encoding="utf-8")

    stub = gt_api.initialize_run(
        object(),
        source_project_name="Beta",
        source_project_path=str(tmp_path / "Beta"),
        projects_root=str(tmp_path),
    )
    names = [c.project_name for c in gt_api.list_target_candidates(stub)]

    assert "Beta" not in names
    assert names == ["Alpha", "Gamma"]
