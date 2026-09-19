"""T090 -- a `.fwdata.lock` file is a claim about a PROCESS, not about a file.

`debug/audit038_closure_edges.py` opened its source project read-only through
`harness.full_run._open_source_readonly` and returned without ever closing it.
flexicon takes the Palaso file lock on ANY open -- its own `OpenProject`
docstring says the project "must be closed with `CloseProject()` to save any
changes, AND RELEASE THE LOCK", with no read-only exemption -- so every run of
that driver left a `<project>.fwdata.lock` behind naming a PID that had since
exited.

`test_038_phon_empty_drop_live._open_or_skip` treated the PRESENCE of that file
as "locked by FieldWorks" and skipped. Measured effect: with two such files
present `tests/integration` reported **77 skipped**; after removing them, **75
skipped and 2 more passed** -- four live assertions across two parametrisations.
So running a Phase 7 driver made the NEXT suite run quieter, in a way that reads
as green.

Nothing in this module, and nothing in the code it pins, DELETES a lock file. A
fixture that removed one could not tell a stale lock from a live FieldWorks
session, and stealing a lock from a running FLEx is exactly the blast radius
CLAUDE.md's restore-before-write rule exists to avoid. The classification is
asymmetric for the same reason: only a PID that is DEFINITIVELY gone yields
`LOCK_STALE`; "running", "cannot tell", "no PID" and "unreadable" all fall to
the refuse-to-measure side.

Every test here runs against `tmp_path`. No live project is opened, so this file
is a real pin on a host with no FieldWorks at all.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_THIS_DIR = str(Path(__file__).parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from harness import full_run  # noqa: E402

# `Skipped` derives from BaseException, so a `pytest.raises(Exception)`
# would let it through and the test would REPORT AS SKIPPED instead of
# passing -- a green-looking non-measurement, which is the very shape
# T090 is about.
try:  # pragma: no cover -- import shim only
    from _pytest.outcomes import Skipped
except ImportError:  # pragma: no cover
    Skipped = pytest.skip.Exception  # type: ignore[attr-defined]

import test_038_phon_empty_drop_live as phon_live  # noqa: E402


#: A PID high enough to be outside the range Windows or Linux hands out here.
#: `_pid_is_running` is asked to prove it dead, and the assertion below checks
#: it actually did rather than falling through to "cannot tell".
_DEAD_PID = 999_999


def _make_project(root: Path, name: str) -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / (name + ".fwdata")).write_text("<not really>", encoding="utf-8")
    return d


def _write_lock(root: Path, name: str, payload) -> Path:
    d = _make_project(root, name)
    path = d / (name + ".fwdata.lock")
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _palaso(pid: int, process_name: str = "python") -> dict:
    """The exact shape T090 measured on disk."""
    return {
        "__type": "FileLockContent:#Palaso.IO.FileLock",
        "PID": pid,
        "ProcessName": process_name,
        "Timestamp": 639229653865809336,
    }


# ---------------------------------------------------------------------------
# _pid_is_running -- the probe that must never be os.kill on Windows
# ---------------------------------------------------------------------------

class TestPidLiveness:
    def test_this_process_is_running(self):
        assert full_run._pid_is_running(os.getpid()) is True

    def test_a_pid_nobody_holds_is_definitively_gone(self):
        assert full_run._pid_is_running(_DEAD_PID) is False

    @pytest.mark.parametrize("pid", [None, 0, -1])
    def test_a_nonsense_pid_is_undeterminable_not_dead(self, pid):
        """`None` is the refuse-to-measure answer. It must NOT be `False`:
        `False` is the only value that unlocks a project."""
        assert full_run._pid_is_running(pid) is None

    def test_the_probe_did_not_kill_this_process(self):
        """The point of not using `os.kill(pid, 0)` on Windows.

        CPython implements `os.kill` there through `TerminateProcess`, so the
        POSIX liveness idiom would terminate the process it is asking about.
        Asking about ourselves and then continuing to execute is the assertion.
        """
        assert full_run._pid_is_running(os.getpid()) is True
        assert full_run._pid_is_running(os.getpid()) is True


# ---------------------------------------------------------------------------
# read_project_lock -- classification, and what each class permits
# ---------------------------------------------------------------------------

class TestReadProjectLock:
    def test_no_lock_file_is_absent_and_opens(self, tmp_path):
        _make_project(tmp_path, "P")
        lock = full_run.read_project_lock("P", projects_root=tmp_path)
        assert lock.state == full_run.LOCK_ABSENT
        assert lock.blocks_open is False
        assert lock.pid is None

    def test_a_live_pid_holds_the_project(self, tmp_path):
        _write_lock(tmp_path, "P", _palaso(os.getpid()))
        lock = full_run.read_project_lock("P", projects_root=tmp_path)
        assert lock.state == full_run.LOCK_HELD
        assert lock.blocks_open is True
        assert lock.pid == os.getpid()
        assert "running" in lock.detail

    def test_a_dead_pid_is_stale_and_opens(self, tmp_path):
        """THE regression. Before T090 this case was indistinguishable from
        the one above, and cost four live assertions per driver run."""
        _write_lock(tmp_path, "P", _palaso(_DEAD_PID))
        lock = full_run.read_project_lock("P", projects_root=tmp_path)
        assert lock.state == full_run.LOCK_STALE
        assert lock.blocks_open is False
        assert lock.pid == _DEAD_PID
        assert lock.process_name == "python"
        assert "STALE" in lock.detail

    @pytest.mark.parametrize(
        "payload, why",
        [
            ("not json at all", "unparseable"),
            ({"__type": "FileLockContent:#Palaso.IO.FileLock"}, "no PID key"),
            ({"PID": "not a number", "ProcessName": "python"}, "PID not an int"),
            ({"PID": None, "ProcessName": "python"}, "PID explicitly null"),
        ],
    )
    def test_a_lock_we_cannot_read_is_never_assumed_stale(
            self, tmp_path, payload, why):
        """The asymmetry, stated as a test: every failure to understand the
        file lands on the side that refuses to open, because the other side
        steals a lock from a running FieldWorks."""
        _write_lock(tmp_path, "P", payload)
        lock = full_run.read_project_lock("P", projects_root=tmp_path)
        assert lock.state == full_run.LOCK_UNREADABLE, why
        assert lock.blocks_open is True, why

    def test_an_undeterminable_pid_blocks_rather_than_opens(
            self, tmp_path, monkeypatch):
        monkeypatch.setattr(full_run, "_pid_is_running", lambda pid: None)
        _write_lock(tmp_path, "P", _palaso(_DEAD_PID))
        lock = full_run.read_project_lock("P", projects_root=tmp_path)
        assert lock.state == full_run.LOCK_UNREADABLE
        assert lock.blocks_open is True

    def test_only_held_and_unreadable_block(self):
        """`blocks_open` is the whole contract; pin the mapping directly so a
        new state cannot be added silently on the permissive side."""
        def _mk(state):
            return full_run.ProjectLock(state, None, None, None, "")

        assert _mk(full_run.LOCK_HELD).blocks_open is True
        assert _mk(full_run.LOCK_UNREADABLE).blocks_open is True
        assert _mk(full_run.LOCK_STALE).blocks_open is False
        assert _mk(full_run.LOCK_ABSENT).blocks_open is False

    @pytest.mark.parametrize("pid", [os.getpid(), _DEAD_PID])
    def test_classifying_never_removes_the_lock_file(self, tmp_path, pid):
        """T090's explicit instruction: do NOT close this by deleting lock
        files. Held and stale alike, the file is still there afterwards and
        its bytes are unchanged."""
        path = _write_lock(tmp_path, "P", _palaso(pid))
        before = path.read_bytes()
        full_run.read_project_lock("P", projects_root=tmp_path)
        assert path.is_file()
        assert path.read_bytes() == before

    def test_projects_root_env_is_honoured(self, tmp_path, monkeypatch):
        monkeypatch.setenv(full_run.PROJECTS_ROOT_ENV, str(tmp_path))
        _write_lock(tmp_path, "P", _palaso(_DEAD_PID))
        assert full_run.read_project_lock("P").state == full_run.LOCK_STALE


# ---------------------------------------------------------------------------
# source_readonly -- the pairing the two drivers did not have
# ---------------------------------------------------------------------------

class _FakeHandle:
    def __init__(self):
        self.closed = 0

    def CloseProject(self):  # noqa: N802 -- flexicon's spelling
        self.closed += 1


class TestSourceReadonlyCloses:
    def test_closes_on_the_normal_path(self, monkeypatch):
        handle = _FakeHandle()
        monkeypatch.setattr(full_run, "_open_source_readonly",
                            lambda name: handle)
        with full_run.source_readonly("P") as h:
            assert h is handle
            assert handle.closed == 0
        assert handle.closed == 1

    def test_closes_when_the_body_raises(self, monkeypatch):
        """The path `audit038_closure_edges.py` did not have at all: it had no
        try/finally, so any exception mid-audit leaked the lock too."""
        handle = _FakeHandle()
        monkeypatch.setattr(full_run, "_open_source_readonly",
                            lambda name: handle)
        with pytest.raises(ValueError):
            with full_run.source_readonly("P"):
                raise ValueError("boom")
        assert handle.closed == 1

    def test_a_failing_close_is_reported_not_swallowed(
            self, monkeypatch, capsys):
        class _Stuck(_FakeHandle):
            def CloseProject(self):  # noqa: N802
                raise RuntimeError("LCM said no")

        monkeypatch.setattr(full_run, "_open_source_readonly",
                            lambda name: _Stuck())
        with full_run.source_readonly("P"):
            pass
        out = capsys.readouterr().out
        assert "[WARN]" in out and "lock file may" in out


# ---------------------------------------------------------------------------
# _open_or_skip -- report a stale lock, refuse a live one
# ---------------------------------------------------------------------------

class _RefusingProject:
    """Stands in for `flexicon.FLExProject` so no live project is touched.

    Its `OpenProject` always raises, so reaching it produces the "could not
    open" skip -- which is how these tests tell "the lock gate let me past"
    from "the lock gate stopped me" without opening anything.
    """

    def OpenProject(self, **kwargs):  # noqa: N802
        raise RuntimeError("no such project (deliberate)")


@pytest.fixture
def _phon_env(tmp_path, monkeypatch):
    """Point the live-phonology module at `tmp_path` and stub out flexicon."""
    monkeypatch.setattr(phon_live, "PROJECTS_ROOT", tmp_path)
    _make_project(tmp_path, "P")

    import gramtrans.Lib.flexinit as flexinit
    monkeypatch.setattr(flexinit, "ensure_flex_initialized", lambda: None)
    flexicon = pytest.importorskip(
        "flexicon", reason="flexicon absent; _open_or_skip cannot be exercised")
    monkeypatch.setattr(flexicon, "FLExProject", _RefusingProject)
    return tmp_path


class TestOpenOrSkip:
    def test_a_live_lock_is_still_a_refusal(self, _phon_env):
        _write_lock(_phon_env, "P", _palaso(os.getpid()))
        with pytest.raises(Skipped) as excinfo:
            phon_live._open_or_skip("P")
        msg = str(getattr(excinfo.value, "msg", excinfo.value))
        assert "is locked" in msg
        assert "running" in msg

    def test_a_stale_lock_is_measured_not_skipped(self, _phon_env, capsys):
        """The behaviour change. It gets PAST the lock gate -- proven by the
        skip it does reach being the open failure, not the lock refusal --
        and it says out loud that the lock was stale."""
        _write_lock(_phon_env, "P", _palaso(_DEAD_PID))
        with pytest.raises(Skipped) as excinfo:
            phon_live._open_or_skip("P")
        msg = str(getattr(excinfo.value, "msg", excinfo.value))
        assert "is locked" not in msg
        assert "could not open" in msg
        assert "STALE" in capsys.readouterr().out

    def test_a_stale_lock_survives_the_attempt(self, _phon_env):
        """`_open_or_skip` reports the stale lock; it does not tidy it away."""
        path = _write_lock(_phon_env, "P", _palaso(_DEAD_PID))
        with pytest.raises(Skipped):
            phon_live._open_or_skip("P")
        assert path.is_file()

    def test_an_unreadable_lock_is_a_refusal(self, _phon_env):
        _write_lock(_phon_env, "P", "not json at all")
        with pytest.raises(Skipped) as excinfo:
            phon_live._open_or_skip("P")
        assert "is locked" in str(getattr(excinfo.value, "msg", excinfo.value))

    def test_no_lock_reaches_the_open_unchanged(self, _phon_env):
        with pytest.raises(Skipped) as excinfo:
            phon_live._open_or_skip("P")
        assert "could not open" in str(
            getattr(excinfo.value, "msg", excinfo.value))

    def test_a_missing_fwdata_still_skips_first(self, _phon_env):
        with pytest.raises(Skipped) as excinfo:
            phon_live._open_or_skip("NoSuchProject")
        assert "not on this machine" in str(
            getattr(excinfo.value, "msg", excinfo.value))


# ---------------------------------------------------------------------------
# The drivers that produced the stale locks in the first place
# ---------------------------------------------------------------------------

class TestDriversPairTheirOpens:
    """T090 half (a). A driver that opens and returns leaves the lock behind,
    so the fix has to be visible in the driver source, not only in the reader.

    Read statically: importing these modules pulls in flexicon and, in
    `audit038`'s case, `SIL.LCModel`.
    """

    _DEBUG = Path(__file__).resolve().parents[2] / "debug"

    def test_audit038_opens_through_the_closing_context_manager(self):
        src = (self._DEBUG / "audit038_closure_edges.py").read_text(
            encoding="utf-8")
        assert "full_run.source_readonly(SOURCE)" in src
        assert "full_run._open_source_readonly(" not in src

    def test_probe_adhoc_loss_closes_both_handles(self):
        src = (self._DEBUG / "probe_adhoc_loss.py").read_text(encoding="utf-8")
        assert src.count(".CloseProject()") == 2
        assert src.count(".OpenProject(") == 2

    def test_no_debug_driver_opens_without_a_paired_close(self):
        """The sweep. A driver may open a project only if the same file also
        closes it, delegates to `run_full_transfer` / `census.read_project`
        (both of which close in a `finally`), or uses `source_readonly`."""
        offenders = []
        for path in sorted(self._DEBUG.glob("*.py")):
            src = path.read_text(encoding="utf-8", errors="replace")
            opens = ("OpenProject(" in src
                     or "_open_source_readonly(" in src)
            if not opens:
                continue
            closes = ("CloseProject(" in src
                      or "source_readonly(" in src
                      or "run_full_transfer(" in src
                      or "read_project(" in src)
            if not closes:
                offenders.append(path.name)
        assert offenders == [], (
            "these drivers open a FLEx project and never release its lock, "
            "which turns the next tests/integration run's live coverage into "
            "skips: " + ", ".join(offenders))
