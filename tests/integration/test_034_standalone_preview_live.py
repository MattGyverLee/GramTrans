"""T015 / SC-002, SC-004 — the standalone previews exactly what FlexTools previews.

The parity claim this feature rests on: a user who switches hosts gets the same
answer. Run live against `Ejagham Mini` -> `Ejagham Full GT-Test`, because the
thing being compared is a real plan over real LCM data — a stub pair would
compare two mocks agreeing with each other.

**What differs between the two paths, and nothing else.** Both reach
`gt_api.compute_preview` with the same `Selection` and the same `WSMapping`.
The only difference is how the `RunContextStub` was built:

* FlexTools style — `initialize_run(host_handle, source_project_name=...)`
  with no `projects_root`, so `list_target_candidates` falls back to the
  hard-coded `C:\\ProgramData\\SIL\\FieldWorks\\Projects` literal;
* standalone style — `HostSession` opens the source itself and injects
  `fwglobals.projects_dir()`, the location FieldWorks actually records (FR-001).

That is precisely the surface shared-code exception 4 touches, so it is
precisely the surface a parity test has to cover. Everything downstream of
`compute_preview` is shared code that neither host varies.

SC-004 rides along: the target's `.fwdata` is hashed before and after. A
Preview that writes anything is a Principle III violation, not a test failure
to explain away.

Marked `integration`: needs FieldWorks, the two projects, and both closed in
FLEx. Excluded from the CI gate (a hosted runner has no FieldWorks) — this is
the evidence T029 records for SC-002.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

SOURCE_PROJECT = "Ejagham Mini"
TARGET_PROJECT = "Ejagham Full GT-Test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fwdata(projects_root: str, name: str) -> Path:
    return Path(projects_root) / name / f"{name}.fwdata"


def _the_selection():
    """One selection, used by both paths. The Phase-0 verb vertical."""
    from gramtrans.Lib.models import GrammarCategory, Selection

    return Selection(
        categories={
            GrammarCategory.POS: True,
            GrammarCategory.AFFIX_TEMPLATES: True,
            GrammarCategory.SLOTS: True,
        },
        include_closure=True,
    )


def _plan_fingerprint(plan):
    """The comparable content of a plan: what it would add, and what it skips.

    Deliberately not the plan object itself — `run_id` and `started_at` differ
    between two runs by construction, and comparing them would make the test
    fail for the one reason that means nothing.
    """
    actions = sorted(
        (a.category.value, str(a.source_guid), a.summary) for a in plan.actions
    )
    skips = sorted(
        (s.category.value, str(s.source_guid), s.reason.value, s.detail)
        for s in plan.skips
    )
    return {"actions": actions, "skips": skips}


def _report_fingerprint(report):
    """Per-category counts from a preview RunReport, host-independent."""
    return {
        cat.value: (
            r.added,
            r.skipped,
            getattr(r, "closure_pulled_in", 0),
            getattr(r, "overwritten", 0),
        )
        for cat, r in report.per_category.items()
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def flex():
    """flexicon, initialised once, with `fwglobals` told about it."""
    from gramtrans.standalone import fwglobals

    flexicon = fwglobals.probe()
    flexicon.FLExInitialize()
    fwglobals.mark_initialized()
    yield flexicon
    # Deliberately **no** `FLExCleanup()` here.
    #
    # It is process-global, not per-session: it calls `Sldr.Cleanup()`, which
    # throws `InvalidOperationException` when the SLDR is already down, and
    # every `HostSession.release()` in this module has already taken it down.
    # Calling it a second time raised that exception and then produced a
    # `Windows fatal exception: access violation` during interpreter shutdown —
    # a double teardown of the CLR side, not a leak in anything under test.
    #
    # Production is unaffected: one session per process, one cleanup. This is
    # nevertheless why `HostSession.release()` wraps `FLExCleanup()` in
    # try/except — that guard is load-bearing, not boilerplate.
    fwglobals.reset_for_tests()


@pytest.fixture(scope="module")
def projects_root(flex):
    from gramtrans.standalone import fwglobals

    root = fwglobals.projects_dir()
    for name in (SOURCE_PROJECT, TARGET_PROJECT):
        if not _fwdata(root, name).is_file():
            pytest.skip(f"{name!r} not present under {root}")
    return root


# ---------------------------------------------------------------------------
# The parity run
# ---------------------------------------------------------------------------

def _preview_through(stub, target_name, projects_root):
    """Shared tail: pick the target, bind it, compute the preview, report it."""
    from gramtrans.Lib import api as gt_api
    from gramtrans.Lib.models import RunMode
    from gramtrans.Lib.report import RunReport

    candidates = gt_api.list_target_candidates(stub)
    chosen = next((c for c in candidates if c.project_name == target_name), None)
    assert chosen is not None, (
        f"{target_name!r} was not offered as a target. Candidates: "
        f"{[c.project_name for c in candidates]}"
    )

    context = gt_api.bind_target(stub, chosen)
    try:
        state, plan = gt_api.compute_preview(context, _the_selection(), None)
        assert state is gt_api.PreviewState.PREVIEW_READY
        report = RunReport.build_from_plan(plan, RunMode.PREVIEW)
        return _plan_fingerprint(plan), _report_fingerprint(report), candidates
    finally:
        target = getattr(context, "target_handle", None)
        if target is not None:
            target.CloseProject()


def test_standalone_and_flextools_previews_are_equivalent(flex, projects_root):
    """SC-002 parity, and SC-004 no-write, in one live run of each path."""
    from gramtrans.Lib import api as gt_api
    from gramtrans.standalone import fwglobals
    from gramtrans.standalone.app import HostSession

    target_fwdata = _fwdata(projects_root, TARGET_PROJECT)
    before = _sha256(target_fwdata)

    # --- Path A: the FlexTools host. It hands the module an already-open
    # source project and nothing else; the stub carries no projects_root, so
    # the historical literal applies.
    source_a = flex.FLExProject()
    source_a.OpenProject(projectName=SOURCE_PROJECT, writeEnabled=False)
    try:
        stub_a = gt_api.initialize_run(
            source_a,
            source_project_name=SOURCE_PROJECT,
            source_project_path=str(Path(projects_root) / SOURCE_PROJECT),
        )
        assert getattr(stub_a, "projects_root", "") == "", (
            "the FlexTools path must not set projects_root — that is what keeps "
            "its candidate list identical (exception 4)"
        )
        plan_a, report_a, candidates_a = _preview_through(
            stub_a, TARGET_PROJECT, projects_root
        )
    finally:
        source_a.CloseProject()

    # --- Path B: the standalone. HostSession opens the source itself, from a
    # deliberate choice, and injects the registry-derived projects root.
    session = HostSession()
    session.start()
    try:
        session.bind_source(SOURCE_PROJECT)
        stub_b = session.build_stub()
        assert stub_b.projects_root == fwglobals.projects_dir(), (
            "the standalone must inject the location FieldWorks records (FR-001)"
        )
        plan_b, report_b, candidates_b = _preview_through(
            stub_b, TARGET_PROJECT, projects_root
        )
    finally:
        session.release()

    # --- Parity.
    assert plan_a == plan_b, "the two hosts planned different transfers"
    assert report_a == report_b, "the two hosts reported different counts"
    assert sorted(c.project_name for c in candidates_a) == sorted(
        c.project_name for c in candidates_b
    ), "the two hosts offered different target lists"
    assert SOURCE_PROJECT not in [c.project_name for c in candidates_b], (
        "the chosen source must not be offered as a target (US1 scenario 3)"
    )
    assert plan_a["actions"], "the fixture pair planned no actions — parity of two "
    "empty plans proves nothing; check the projects"

    # --- SC-004: a Preview writes nothing.
    assert _sha256(target_fwdata) == before, (
        f"{TARGET_PROJECT}.fwdata changed during a Preview — Principle III violation"
    )


def test_the_session_releases_both_projects_on_every_exit_path(flex, projects_root):
    """FR-013 / SC-005 — including the paths nobody remembers to test.

    Verified against the **`.fwdata.lock` file**, which LCM creates on open and
    removes on close. Measured on this machine: the lock appears for a
    *read-only* open too, and disappears on `CloseProject()`. That makes its
    absence exactly the property the user cares about — FLEx will open the
    project again.

    Deliberately *not* verified by re-opening the project write-enabled in this
    process: LCM keeps per-process state that makes a second write-open of an
    already-used project fail even when every handle has been closed and the
    lock file is gone. That check would report a leak that is not there.
    """
    from gramtrans.standalone.app import HostSession

    lock = Path(projects_root) / SOURCE_PROJECT / f"{SOURCE_PROJECT}.fwdata.lock"

    def _released() -> bool:
        return not lock.exists()

    assert _released(), (
        f"{SOURCE_PROJECT} was already locked before the test started — close "
        "it in FLEx, or delete the stale .lock file if no FieldWorks process "
        "is running"
    )

    # 1. Normal close.
    session = HostSession()
    session.start()
    session.bind_source(SOURCE_PROJECT)
    assert lock.exists(), "the source was not actually opened"
    session.release()
    assert _released(), "normal close left the source locked"

    # 2. release() called twice — idempotent, not a second failure.
    session.release()
    assert session.state.value == "released"
    assert _released()

    # 3. A failure between bind and release.
    session = HostSession()
    session.start()
    session.bind_source(SOURCE_PROJECT)
    try:
        raise RuntimeError("simulated mid-run failure")
    except RuntimeError:
        session.release()
    assert _released(), "a failed run left the source locked"

    # 4. The context-manager path, which is what `__main__`'s `finally` is.
    with HostSession() as session:
        session.start()
        session.bind_source(SOURCE_PROJECT)
    assert _released(), "the context-manager exit left the source locked"


def test_another_process_can_open_the_source_after_release(flex, projects_root):
    """SC-005, end to end: the check a user would actually run.

    A subprocess is the only honest version of "FLEx can open it again" —
    in-process, LCM's own caching muddies the answer (see the test above).
    """
    import subprocess
    import sys
    import textwrap

    from gramtrans.standalone.app import HostSession

    session = HostSession()
    session.start()
    session.bind_source(SOURCE_PROJECT)
    session.release()

    script = textwrap.dedent(
        f"""
        import flexicon
        flexicon.FLExInitialize()
        p = flexicon.FLExProject()
        p.OpenProject(projectName={SOURCE_PROJECT!r}, writeEnabled=True)
        p.CloseProject()
        print("REOPENED")
        """
    )
    env = dict(os.environ)
    src = str(Path(__file__).resolve().parents[2] / "src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, env=env
    )
    assert "REOPENED" in proc.stdout, (
        "a fresh process could not open the source after release: "
        f"stdout={proc.stdout!r} stderr={proc.stderr[-2000:]!r}"
    )


def test_the_injected_root_is_what_fieldworks_records(flex, projects_root):
    """FR-001, stated as the thing a relocated install would break."""
    from gramtrans.standalone import fwglobals

    recorded = fwglobals.projects_dir()
    assert recorded
    assert os.path.isdir(recorded)
    assert _fwdata(recorded, SOURCE_PROJECT).is_file()
