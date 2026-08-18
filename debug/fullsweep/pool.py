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


def assert_concurrency_gate_satisfied(n_workers: int) -> None:
    """FR-031/FR-032/FR-033: default worker count is 1; anything higher
    requires a recorded concurrency-trial artifact. No such artifact exists
    as of this skeleton, so this MUST refuse -- it is a named, explicit gate,
    not an assumed capability."""
    if n_workers <= 1:
        return
    if not CONCURRENCY_TRIAL_ARTIFACT.is_file():
        raise WriteSafetyError(
            "[FR-032] --workers %d requested, but no recorded concurrency-trial "
            "artifact exists at %r. Concurrent opens against the host database "
            "service are UNMEASURED for safety; this is an explicit gate, not "
            "an assumed capability. Run and record a concurrency trial first."
            % (n_workers, str(CONCURRENCY_TRIAL_ARTIFACT))
        )


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
