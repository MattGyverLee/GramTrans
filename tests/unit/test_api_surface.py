"""T058 partial: Lib/api.py UI ↔ engine surface — unit-testable parts.

Tests cover the pure-Python paths that don't need a live LCM:
- `initialize_run` produces a valid RunContextStub with `GT-`-prefixed run_id.
- `list_target_candidates` filters out the source by path/name.
- `bind_target` raises SameProjectError for matching source/target.
- `compute_preview` returns NEEDS_WS_MAPPING when ws_mapping is None.

Tests that touch `bind_target`'s real flexlibs2 open or `execute_move` belong
under tests/integration/ and require the FlexTools host.
"""
from __future__ import annotations

import os
import tempfile

import pytest

from gramtrans.Lib.api import (
    PreviewState,
    RequiredWSMapping,
    RunContextStub,
    SameProjectError,
    TargetCandidate,
    bind_target,
    compute_preview,
    initialize_run,
    list_target_candidates,
)
from gramtrans.Lib.models import (
    GrammarCategory,
    RunContext,
    Selection,
    WSMapping,
)


# ============================================================================
# initialize_run
# ============================================================================

def test_initialize_run_makes_gt_prefixed_run_id() -> None:
    stub = initialize_run(
        host_handle=object(),
        source_project_name="Ejagham Mini",
        source_project_path="/path/to/src",
    )
    assert isinstance(stub, RunContextStub)
    assert stub.source_project_name == "Ejagham Mini"
    assert stub.source_project_path == "/path/to/src"
    assert stub.run_id.startswith("GT-")
    assert len(stub.run_id) == len("GT-YYYYMMDD-HHMMSS")
    # run_id must match started_at (E5 invariant pre-check)
    import datetime
    parsed = datetime.datetime.fromisoformat(stub.started_at)
    assert parsed.strftime("GT-%Y%m%d-%H%M%S") == stub.run_id


# ============================================================================
# list_target_candidates
# ============================================================================

def _make_fake_projects(root: str, names: list) -> None:
    for n in names:
        d = os.path.join(root, n)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{n}.fwdata"), "w") as f:
            f.write("")


def test_list_target_candidates_returns_all_when_no_match(tmp_path) -> None:
    _make_fake_projects(str(tmp_path), ["Alpha", "Beta", "Gamma"])
    stub = initialize_run(object(), source_project_name="NotInList",
                          source_project_path=str(tmp_path / "NotInList"))
    candidates = list_target_candidates(stub, projects_root=str(tmp_path))
    names = sorted(c.project_name for c in candidates)
    assert names == ["Alpha", "Beta", "Gamma"]


def test_list_target_candidates_excludes_source_by_name(tmp_path) -> None:
    _make_fake_projects(str(tmp_path), ["Alpha", "Beta", "Gamma"])
    stub = initialize_run(object(), source_project_name="Beta",
                          source_project_path=str(tmp_path / "Beta"))
    names = [c.project_name for c in list_target_candidates(stub, projects_root=str(tmp_path))]
    assert "Beta" not in names
    assert set(names) == {"Alpha", "Gamma"}


def test_list_target_candidates_ignores_directories_without_fwdata(tmp_path) -> None:
    """A folder without a matching .fwdata file is not a FLEx project."""
    os.makedirs(str(tmp_path / "NotAProject"), exist_ok=True)
    _make_fake_projects(str(tmp_path), ["Alpha"])
    stub = initialize_run(object(), source_project_name="Other",
                          source_project_path="")
    names = [c.project_name for c in list_target_candidates(stub, projects_root=str(tmp_path))]
    assert names == ["Alpha"]


def test_list_target_candidates_returns_empty_for_nonexistent_root() -> None:
    stub = initialize_run(object(), source_project_name="X")
    candidates = list_target_candidates(stub, projects_root="/no/such/path/here")
    assert candidates == []


# ============================================================================
# bind_target — pre-flexlibs2 path
# ============================================================================

def test_bind_target_raises_on_same_project_by_name() -> None:
    stub = initialize_run(object(), source_project_name="Twin",
                          source_project_path="/p/Twin")
    choice = TargetCandidate(project_name="Twin", project_path="/p/Twin")
    with pytest.raises(SameProjectError, match="same project"):
        bind_target(stub, choice)


def test_bind_target_raises_on_same_project_by_path() -> None:
    stub = initialize_run(object(), source_project_name="A",
                          source_project_path="/p/A")
    choice = TargetCandidate(project_name="B", project_path="/p/A")  # same dir
    with pytest.raises(SameProjectError, match="same project"):
        bind_target(stub, choice)


# ============================================================================
# compute_preview — two-stage call
# ============================================================================

def _ctx() -> RunContext:
    return RunContext(
        source_handle=object(),
        source_project_name="S",
        source_project_path="/s",
        target_handle=object(),
        target_project_name="T",
        target_project_path="/t",
        run_id="GT-20260619-160000",
        started_at="2026-06-19T16:00:00",
    )


def test_compute_preview_returns_needs_ws_mapping_when_none() -> None:
    sel = Selection(categories={GrammarCategory.POS: True})
    state, payload = compute_preview(_ctx(), sel, ws_mapping=None)
    assert state is PreviewState.NEEDS_WS_MAPPING
    assert isinstance(payload, RequiredWSMapping)


def test_target_candidate_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        TargetCandidate(project_name="", project_path="/x")
