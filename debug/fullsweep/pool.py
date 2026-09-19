"""Feature 035 -- Group C: PARALLEL TARGET POOL. Moved unchanged out of the
``debug/run_fullcopy_sweep.py`` monolith (T004/T009 of
specs/035-fullsweep-fidelity/tasks.md Phase 1).

Covers the target pool, the OS-level exclusive claim on a destination, the
stale-lock self-heal, the per-worker memory admission model, and the
concurrency-trial gate.
"""
from __future__ import annotations

import ctypes
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from .artifact import DEFAULT_ARTIFACTS_DIR
from .safety import WriteSafetyError, _reject_unsafe_name_shape

DEFAULT_RUNTIME_DIR = Path(__file__).resolve().parents[2] / "scratchpad" / "035_sweep"  # ephemeral, gitignored

MEM_MODEL_FLOOR_MB_PROVISIONAL = 190.0
MEM_MODEL_SLOPE_MB_PER_MB_PROVISIONAL = 1.9
MEM_MODEL_RESERVE_MB_DEFAULT = 512.0


def assert_distinct_target_pool(target_pool: Sequence[str], frozen_sources) -> None:
    """FR-034 last sentence: the configured destination pool MUST itself be a
    set of distinct, individually admitted names, and none may collide with a
    frozen source name."""
    if not target_pool:
        raise WriteSafetyError("[FR-034] target pool is empty")
    seen = set()
    for t in target_pool:
        _reject_unsafe_name_shape(t)
        if t in seen:
            raise WriteSafetyError(
                "[FR-034] target pool contains a duplicate destination: %r" % (t,)
            )
        seen.add(t)
        if frozen_sources and t in frozen_sources:
            raise WriteSafetyError(
                "[FR-034] target-pool entry %r collides with a frozen source name" % (t,)
            )


class ExclusiveTargetClaim:
    """FR-034: an OS-level exclusive claim on a destination, created
    atomically, held for the worker's entire project, and living OUTSIDE the
    projects collection so a ``restore_target`` call can never remove it and
    it is never mistaken for project content.

    Identifier reuse (a crash-and-restart, or a stale pool record) is the
    named failure mode FR-034 calls out, so a PID match alone is not trusted:
    a pre-existing claim file is only ever removed here after confirming the
    PID it names is not alive (the same staleness test ``self_heal_stale_lock``
    uses for a project's own ``.lock`` file, below).
    """

    def __init__(self, target_name: str, runtime_dir: Path = DEFAULT_RUNTIME_DIR):
        _reject_unsafe_name_shape(target_name)
        self.target_name = target_name
        self._dir = runtime_dir / "claims"
        self._path = self._dir / ("%s.claim" % target_name)
        self._acquired = False

    def acquire(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"pid": os.getpid(), "target": self.target_name,
                               "acquired_at": time.time()}).encode("utf-8")
        for attempt in (1, 2):
            try:
                fd = os.open(str(self._path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if attempt == 2:
                    raise WriteSafetyError(
                        "[FR-034] could not acquire exclusive claim on %r after "
                        "clearing one stale claim -- another live worker may hold "
                        "it" % (self.target_name,)
                    )
                self._clear_if_stale()
                continue
            else:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(payload)
                self._acquired = True
                return

    def _clear_if_stale(self) -> None:
        try:
            existing = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 -- recorded, not silent
            raise WriteSafetyError(
                "[FR-034] existing claim file %r is unreadable/corrupt (%s); "
                "refusing to guess whether it is stale" % (str(self._path), exc)
            ) from exc
        pid = existing.get("pid")
        if pid is not None and _pid_is_alive(int(pid)):
            raise WriteSafetyError(
                "[FR-034] destination %r is already claimed by a LIVE process "
                "(pid=%s) -- refusing to proceed" % (self.target_name, pid)
            )
        self._path.unlink()  # confirmed dead owner; safe to clear

    def assert_held(self) -> None:
        """FR-034: the exclusive claim MUST be held for the ENTIRE duration of
        that worker's project. Acquiring it and then losing it (a sweep of
        the runtime dir, an operator deleting the claim, another process
        clearing it as stale) silently readmits a second worker onto this
        destination, which invalidates BOTH workers' results.

        Call this at every write boundary, not only at acquisition: the
        failure mode is the claim disappearing MID-project, which an
        acquisition-time check cannot see.
        """
        if not self._acquired:
            raise WriteSafetyError(
                "[FR-034] exclusive claim on %r was never acquired by this "
                "process -- refusing to treat the destination as owned"
                % (self.target_name,)
            )
        if not self._path.is_file():
            raise WriteSafetyError(
                "[FR-034] exclusive claim file %r has DISAPPEARED while this "
                "worker still holds the destination -- another worker may now "
                "be admitted onto %r; aborting"
                % (str(self._path), self.target_name)
            )
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 -- recorded, never silent
            raise WriteSafetyError(
                "[FR-034] exclusive claim file %r is unreadable/corrupt (%s) "
                "while held" % (str(self._path), exc)
            ) from exc
        if payload.get("pid") != os.getpid() or payload.get("target") != self.target_name:
            raise WriteSafetyError(
                "[FR-034] exclusive claim on %r is no longer OURS (file names "
                "pid=%r target=%r; we are pid=%r) -- another process has taken "
                "the destination; aborting"
                % (self.target_name, payload.get("pid"), payload.get("target"),
                   os.getpid())
            )

    def release(self) -> None:
        if self._acquired:
            try:
                self._path.unlink()
            except FileNotFoundError:
                pass
        self._acquired = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False


def _pid_is_alive(pid: int) -> bool:
    """Best-effort liveness check (Windows). Returns False only when we can
    positively confirm the process is gone; on ambiguity, treat as alive
    (FR-040: "where ownership cannot be determined, treat the lock as live")."""
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        pass
    PROCESS_QUERY_LIMITED = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
    if not handle:
        return False
    ctypes.windll.kernel32.CloseHandle(handle)
    return True


def self_heal_stale_lock(target_dir: Path, target_name: str) -> Optional[str]:
    """FR-040: self-heal a stale ``*.lock`` left by a crashed prior attempt on
    a DESTINATION that has ALREADY passed ``assert_destination_safe`` --
    never on a source. Returns a human-readable note of what happened, or
    None if there was no lock to consider.

    A lock is confirmed stale only when the owning PID recorded in the lock's
    JSON payload (``{"PID": ..., "ProcessName": ...}``, the observed
    ``SimpleFileLock``/Palaso.IO.FileLock shape) is no longer alive, OR is
    alive but running under a different process image than the one recorded
    (PID reuse). Where ownership cannot be determined at all, this function
    raises rather than guesses (fail toward "live").
    """
    lock_path = target_dir / ("%s.fwdata.lock" % target_name)
    if not lock_path.is_file():
        return None
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 -- recorded, not silent
        raise WriteSafetyError(
            "[FR-040] lock file %r is unreadable/corrupt (%s); refusing to "
            "guess whether its owner is alive" % (str(lock_path), exc)
        ) from exc
    pid = payload.get("PID")
    if pid is None:
        raise WriteSafetyError(
            "[FR-040] lock file %r has no PID field; ownership cannot be "
            "determined -- treating as LIVE and aborting" % (str(lock_path),)
        )
    alive = _pid_is_alive(int(pid))
    if alive:
        # PID reuse cannot be distinguished from a genuinely live owner without
        # a process-name check; best-effort only (psutil, if present).
        same_identity = True
        try:
            import psutil
            proc = psutil.Process(int(pid))
            recorded_name = payload.get("ProcessName")
            same_identity = (recorded_name is None) or (proc.name() == recorded_name) \
                or (recorded_name in proc.name()) or (proc.name() in str(recorded_name))
        except ImportError:
            pass
        except Exception:  # noqa: BLE001 -- process vanished mid-check etc.
            same_identity = False
        if same_identity:
            raise WriteSafetyError(
                "[FR-040] lock owner pid=%s on %r is ALIVE -- refusing to "
                "remove the lock; another process believes it owns this "
                "target" % (pid, str(lock_path))
            )
    lock_path.unlink()
    return "removed stale lock (recorded pid=%s, confirmed not-alive-as-recorded)" % (pid,)


def default_target_pool(n_workers: int) -> tuple[str, ...]:
    """FR-025/FR-027: N disposable targets, all restorable from the SAME
    single archived backup (``restore_target`` renames the archived fwdata to
    match whatever destination name it is given, so one backup seeds any
    number of targets). Names are drawn from the sweep's own
    ``DEFAULT_ALLOWLIST`` pattern by construction.

    NOTE: raising ``n_workers`` above 1 additionally requires the FR-032
    concurrency-trial gate (see ``assert_concurrency_gate_satisfied``) --
    this function only names the pool, it does not authorize using more than
    one member of it concurrently.
    """
    if n_workers < 1:
        raise WriteSafetyError("[FR-031] n_workers must be >= 1")
    pool = ["Target"] + ["Target%d" % i for i in range(2, n_workers + 1)]
    return tuple(pool)


CONCURRENCY_TRIAL_ARTIFACT = DEFAULT_ARTIFACTS_DIR / "concurrency-trial.json"


def predicted_footprint_mb(fwdata_mb: float) -> float:
    """FR-028/FR-030: PROVISIONAL per-worker memory prediction."""
    return MEM_MODEL_FLOOR_MB_PROVISIONAL + MEM_MODEL_SLOPE_MB_PER_MB_PROVISIONAL * fwdata_mb


def free_memory_mb() -> Optional[float]:
    """Measured free physical memory (Windows), never core count (FR-028)."""
    class _MEMSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]
    stat = _MEMSTATUSEX()
    stat.dwLength = ctypes.sizeof(_MEMSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
        return None
    return stat.ullAvailPhys / (1024.0 * 1024.0)


class MemoryShortfall(RuntimeError):
    """Raised to signal 'wait or admit fewer workers' -- explicitly NOT a
    WriteSafetyError/SourceTamperError; the two must never share an error
    path (a memory wait is an operational retry, a safety abort never is)."""


def assert_memory_admits(fwdata_mb: float, reserve_mb: float = MEM_MODEL_RESERVE_MB_DEFAULT) -> None:
    predicted = predicted_footprint_mb(fwdata_mb)
    free = free_memory_mb()
    if free is None:
        raise MemoryShortfall(
            "[FR-028] could not measure free physical memory; refusing to "
            "admit (fail toward waiting, not toward guessing free RAM)"
        )
    if free < predicted + reserve_mb:
        raise MemoryShortfall(
            "[FR-028] predicted footprint %.0f MB + reserve %.0f MB exceeds "
            "measured free memory %.0f MB" % (predicted, reserve_mb, free)
        )


# ===========================================================================
# GROUP C (continued) -- T021: POOL INTEGRITY (FR-025..FR-041, SC-012)
# ===========================================================================

#: FR-030: the memory model is PROVISIONAL, and MUST be recorded as such
#: WHEREVER IT IS USED OR DOCUMENTED -- not only in prose. Every admission
#: decision this module returns carries this stamp, so an artifact can never
#: contain a memory number without the caveat attached to it.
MEMORY_MODEL_STAMP: dict = {
    "status": "PROVISIONAL",
    "floor_mb": MEM_MODEL_FLOOR_MB_PROVISIONAL,
    "slope_mb_per_mb": MEM_MODEL_SLOPE_MB_PER_MB_PROVISIONAL,
    "derivation": (
        "slope derived from a SINGLE large-project observation -- a one-point "
        "regression that establishes an order of magnitude, NOT a validated "
        "coefficient. Never restate this model anywhere as settled physics."
    ),
    "supersedes": (
        "FR-030: once observed actuals exist for a project, or for a data-size "
        "range, the admission check MUST prefer them over this prediction."
    ),
}

#: FR-029: there is NO rule about which named or size-ranked projects may run
#: together, and this emptiness is asserted rather than merely documented. A
#: largest-two exclusion rule is simultaneously too strict and too weak, and
#: silently stops meaning anything when the corpus changes.
NAMED_PROJECT_ADMISSION_RULES: tuple = ()

assert NAMED_PROJECT_ADMISSION_RULES == (), (
    "[FR-029] admission must be scheduled on measured free memory alone; no "
    "named-project or size-rank pairing rule may exist here"
)


def memory_model_stamp() -> dict:
    """FR-030: the PROVISIONAL stamp, for embedding wherever a memory number
    from this model is reported."""
    return dict(MEMORY_MODEL_STAMP)


@dataclass
class AdmissionDecision:
    """What ``decide_admission`` measured, with the FR-030 stamp attached and
    the FR-030 observed-actuals preference recorded explicitly."""
    project: str
    fwdata_mb: float
    predicted_mb: float
    source: str                 # "observed-actual" | "provisional-model"
    free_mb: object
    reserve_mb: float
    admitted: bool
    reason: str = ""
    model: dict = field(default_factory=memory_model_stamp)

    def as_dict(self) -> dict:
        return {
            "project": self.project, "fwdata_mb": self.fwdata_mb,
            "predicted_mb": self.predicted_mb, "prediction_source": self.source,
            "free_mb": self.free_mb, "reserve_mb": self.reserve_mb,
            "admitted": self.admitted, "reason": self.reason,
            "memory_model": self.model,
        }


def decide_admission(
    project: str, fwdata_mb: float, *,
    reserve_mb: float = MEM_MODEL_RESERVE_MB_DEFAULT,
    observed_actuals: Optional[dict] = None,
) -> AdmissionDecision:
    """FR-028/FR-029/FR-030: decide admission from MEASURED FREE MEMORY only.

    ``observed_actuals`` maps a project name to an observed peak per-worker
    footprint in MB. FR-030 requires that, once such an actual exists, the
    admission check PREFER it over the model's prediction -- so it is
    consulted first and the choice is recorded in ``source``.

    Never consults core count (FR-028) and never consults a named-project or
    size-rank pairing rule (FR-029): the only inputs are this project's own
    data-file size, the observed actual if one exists, and measured free
    memory.
    """
    actual = (observed_actuals or {}).get(project)
    if actual is not None:
        predicted, source = float(actual), "observed-actual"
    else:
        predicted, source = predicted_footprint_mb(fwdata_mb), "provisional-model"
    free = free_memory_mb()
    if free is None:
        return AdmissionDecision(
            project=project, fwdata_mb=fwdata_mb, predicted_mb=predicted,
            source=source, free_mb=None, reserve_mb=reserve_mb, admitted=False,
            reason=("could not measure free physical memory; failing toward "
                    "waiting, not toward guessing free RAM"),
        )
    admitted = free >= predicted + reserve_mb
    return AdmissionDecision(
        project=project, fwdata_mb=fwdata_mb, predicted_mb=predicted, source=source,
        free_mb=free, reserve_mb=reserve_mb, admitted=admitted,
        reason="" if admitted else (
            "predicted %.0f MB (%s) + reserve %.0f MB exceeds measured free "
            "memory %.0f MB" % (predicted, source, reserve_mb, free)),
    )


def assert_memory_admits_project(
    project: str, fwdata_mb: float, *,
    reserve_mb: float = MEM_MODEL_RESERVE_MB_DEFAULT,
    observed_actuals: Optional[dict] = None,
) -> AdmissionDecision:
    """``decide_admission`` plus the FR-177 raise. Returns the decision (for
    the artifact) when admitted; raises ``MemoryShortfall`` -- never a
    ``WriteSafetyError`` -- when not."""
    decision = decide_admission(project, fwdata_mb, reserve_mb=reserve_mb,
                                 observed_actuals=observed_actuals)
    if not decision.admitted:
        raise MemoryShortfall("[FR-028] %s: %s" % (project, decision.reason))
    return decision


# ---------------------------------------------------------------------------
# FR-032/SC-012: the concurrency gate needs a PRESENT AND VALID trial artifact
# ---------------------------------------------------------------------------

#: Fields a concurrency-trial artifact must carry to be VALID. Presence of a
#: file is not enough (SC-012 says "a present, VALID concurrency-trial
#: artifact"): an empty or truncated file must not unlock concurrency.
CONCURRENCY_TRIAL_REQUIRED_FIELDS: tuple[str, ...] = (
    "schema_version", "max_workers_demonstrated", "host_service", "recorded_at",
)


def concurrency_trial_path() -> Path:
    """Read the module-level artifact path AT CALL TIME.

    Deliberately a function: ``debug/fullsweep/__init__.py`` re-exports
    ``CONCURRENCY_TRIAL_ARTIFACT`` by ``import *``, which BINDS A COPY onto
    the package namespace. A test that patches the package-level copy
    therefore does not affect what this module reads. Routing every read
    through this function -- and having the tests patch
    ``fullsweep.pool.CONCURRENCY_TRIAL_ARTIFACT`` -- makes the patched value
    and the value actually consulted the same object.
    """
    return CONCURRENCY_TRIAL_ARTIFACT


def read_concurrency_trial(path: Optional[Path] = None) -> Optional[dict]:
    """Return the trial artifact's payload, or None when absent. Raises when
    present-but-unreadable: a corrupt trial artifact must not read as
    'no trial' (which is merely refusing) nor as 'trial passed'."""
    p = Path(path) if path is not None else concurrency_trial_path()
    if not p.is_file():
        return None
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 -- recorded, never silent
        raise WriteSafetyError(
            "[FR-032] concurrency-trial artifact %r exists but is "
            "unreadable/corrupt (%s) -- refusing to infer anything from it"
            % (str(p), exc)
        ) from exc
    if not isinstance(payload, dict):
        raise WriteSafetyError(
            "[FR-032] concurrency-trial artifact %r is not a JSON object" % (str(p),)
        )
    return payload


def assert_concurrency_gate_satisfied(n_workers: int, path: Optional[Path] = None) -> None:
    """FR-031/FR-032/FR-033 + SC-012: the default worker count is 1; anything
    higher requires a PRESENT AND VALID recorded concurrency-trial artifact
    that demonstrates at least the requested worker count.

    No such artifact exists as of this checkpoint, so this refuses -- a
    named, explicit gate, not an assumed capability. FR-033: concurrency
    having worked in practice is never a substitute for the gate.
    """
    if n_workers < 1:
        raise WriteSafetyError("[FR-031] n_workers must be >= 1")
    if n_workers <= 1:
        return
    p = Path(path) if path is not None else concurrency_trial_path()
    payload = read_concurrency_trial(p)
    if payload is None:
        raise WriteSafetyError(
            "[FR-032] --workers %d requested, but no recorded concurrency-trial "
            "artifact exists at %r. Concurrent opens against the host database "
            "service are UNMEASURED for safety; this is an explicit gate, not "
            "an assumed capability. Run and record a concurrency trial first."
            % (n_workers, str(p))
        )
    missing = [f for f in CONCURRENCY_TRIAL_REQUIRED_FIELDS if f not in payload]
    if missing:
        raise WriteSafetyError(
            "[FR-032/SC-012] concurrency-trial artifact %r is present but NOT "
            "VALID: missing required field(s) %r. A file's mere existence does "
            "not unlock concurrency." % (str(p), missing)
        )
    demonstrated = payload.get("max_workers_demonstrated")
    if not isinstance(demonstrated, int) or demonstrated < n_workers:
        raise WriteSafetyError(
            "[FR-032/FR-033] concurrency-trial artifact %r demonstrates "
            "max_workers=%r, which does not authorize --workers %d. The trial's "
            "findings bound the permissible range; they are never a licence to "
            "exceed it." % (str(p), demonstrated, n_workers)
        )
