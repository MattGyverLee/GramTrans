"""T013 / FR-001 — the projects root is injectable, and FlexTools never notices.

`list_target_candidates` has always defaulted to a hard-coded
`C:\\ProgramData\\SIL\\FieldWorks\\Projects`. That is right on a default
install and wrong on a relocated one, so the standalone injects what
FieldWorks itself records (`FWProjectsDir`, via `standalone/fwglobals.py`).

Both halves are load-bearing and both are tested here:

* the **injected** half — a set `stub.projects_root` wins;
* the **unchanged** half — a stub carrying the default `""` still resolves to
  the existing literal, which is what keeps the FlexTools candidate list
  identical (shared-code exception 4). That assertion must pass *before* T016
  lands as well as after, because before T016 the field does not exist and the
  literal is the only behaviour there is.
"""
from __future__ import annotations

import os
from pathlib import Path

from gramtrans.Lib import api as gt_api

# The literal `list_target_candidates` has always defaulted to. Spelled out
# here rather than imported, so a change to it is a deliberate two-file edit.
_HISTORICAL_DEFAULT = r"C:\ProgramData\SIL\FieldWorks\Projects"


def _make_projects_tree(root: Path, names) -> None:
    """A directory that looks like a FLEx projects root: <name>/<name>.fwdata."""
    for name in names:
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.fwdata").write_text("<!-- fixture -->", encoding="utf-8")


def _stub(**kwargs):
    """A `RunContextStub` with only the fields this test cares about set."""
    fields = {
        "source_handle": object(),
        "source_project_name": "",
        "source_project_path": "",
        "run_id": "GT-20260817-000000",
        "started_at": "2026-08-17T00:00:00",
    }
    fields.update(kwargs)
    return gt_api.RunContextStub(**fields)


# ---------------------------------------------------------------------------
# The injected half
# ---------------------------------------------------------------------------

def test_stub_projects_root_is_used_when_set(tmp_path):
    _make_projects_tree(tmp_path, ["Alpha", "Beta"])

    stub = _stub(projects_root=str(tmp_path))
    names = [c.project_name for c in gt_api.list_target_candidates(stub)]

    assert names == ["Alpha", "Beta"]


def test_stub_projects_root_beats_the_positional_default(tmp_path):
    """A relocated root wins even against an explicitly-passed one.

    `stub.projects_root or projects_root` is the shape the contract fixes; this
    pins the precedence so a later refactor cannot silently invert it.
    """
    relocated = tmp_path / "relocated"
    other = tmp_path / "other"
    _make_projects_tree(relocated, ["Relocated"])
    _make_projects_tree(other, ["Other"])

    stub = _stub(projects_root=str(relocated))
    names = [c.project_name for c in gt_api.list_target_candidates(stub, str(other))]

    assert names == ["Relocated"]


def test_the_source_is_still_excluded_from_an_injected_root(tmp_path):
    """Injection must not cost us the source-exclusion FR-002 depends on."""
    _make_projects_tree(tmp_path, ["Source", "Target"])

    by_name = _stub(projects_root=str(tmp_path), source_project_name="Source")
    assert [c.project_name for c in gt_api.list_target_candidates(by_name)] == ["Target"]

    by_path = _stub(
        projects_root=str(tmp_path),
        source_project_path=str(tmp_path / "Source"),
    )
    assert [c.project_name for c in gt_api.list_target_candidates(by_path)] == ["Target"]


# ---------------------------------------------------------------------------
# The FlexTools-unchanged half
# ---------------------------------------------------------------------------

def test_empty_projects_root_falls_back_to_the_historical_literal(monkeypatch, tmp_path):
    """A stub with the default `""` resolves to the literal, as it always has.

    Proven by pointing the *literal* at a fixture tree via the positional
    parameter: with `projects_root` empty, the positional value is what gets
    walked — which is exactly the code path the FlexTools call takes, since it
    passes nothing and gets the real default.
    """
    _make_projects_tree(tmp_path, ["Gamma"])

    stub = _stub(projects_root="")
    names = [c.project_name for c in gt_api.list_target_candidates(stub, str(tmp_path))]

    assert names == ["Gamma"]


def test_the_signature_default_is_still_the_programdata_literal():
    """The FlexTools path passes nothing, so the default *is* the behaviour."""
    import inspect

    default = inspect.signature(gt_api.list_target_candidates).parameters[
        "projects_root"
    ].default
    assert default == _HISTORICAL_DEFAULT


def test_a_stub_built_the_flextools_way_carries_the_empty_default():
    """`initialize_run` without `projects_root=` must yield the fallback state.

    This is the assertion that makes exception 4 "additive": the FlexTools
    caller does not pass the new keyword, so its stub has to come out with the
    field empty and take the literal.
    """
    stub = gt_api.initialize_run(object(), source_project_name="Whatever")
    assert getattr(stub, "projects_root", "") == ""


def test_a_missing_root_is_an_empty_list_not_an_error(tmp_path):
    stub = _stub(projects_root=str(tmp_path / "does-not-exist"))
    assert gt_api.list_target_candidates(stub) == []


def test_directories_without_an_fwdata_file_are_not_candidates(tmp_path):
    _make_projects_tree(tmp_path, ["Real"])
    (tmp_path / "NotAProject").mkdir()
    (tmp_path / "loose.txt").write_text("x", encoding="utf-8")

    stub = _stub(projects_root=str(tmp_path))
    assert [c.project_name for c in gt_api.list_target_candidates(stub)] == ["Real"]


def test_candidate_paths_point_inside_the_injected_root(tmp_path):
    _make_projects_tree(tmp_path, ["Alpha"])

    stub = _stub(projects_root=str(tmp_path))
    (cand,) = gt_api.list_target_candidates(stub)

    assert os.path.normcase(cand.project_path) == os.path.normcase(
        str(tmp_path / "Alpha")
    )
