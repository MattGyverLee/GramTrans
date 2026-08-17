"""Feature 035 -- full-corpus, double-Move fidelity sweep (EXECUTABLE SKELETON).

Standalone CLI. NOT a plugin-host module; run it directly with
``python debug/run_fullcopy_sweep.py ...``.

SCOPE OF THIS FILE (per the feature-035 dispatch brief, 2026-08-18): build
everything the spec has already settled -- Group A (corpus enumeration),
Group B (write safety), Group C (parallel target pool), Group D (double-move
and idempotency), Group K (artifact/provenance), Group L (batched, gated,
fix-forward execution) -- and leave the COMPARATOR / VERDICT TAXONOMY
(spec.md Groups E, F, G, H, and the identity-substitution rules of Group P)
as an explicit, documented extension point. That taxonomy is still in review
(cycle3-amendments.md / cycle3-safety-amendments.md are not yet folded into
spec.md's settled requirement groups) and MUST NOT be invented here. See
``compare_objects`` below for the pluggable seam.

Reused rather than reinvented (per instructions):
  * ``debug/prescan_type_coverage.py`` -- corpus enumeration
    (``_enumerate``/``_walk_flex_projects``), the anchored
    ``^Target[0-9]*$`` refusal pattern, its ``_fingerprint`` helper shape, and
    its subprocess-isolation driver pattern.
  * ``tests/integration/harness/restore.py`` -- ``restore_target`` (see the
    HAZARD note on ``ExclusiveTargetClaim`` and ``self_heal_stale_lock``
    below: it unconditionally deletes ``*.lock`` and rmtrees settings dirs
    for WHATEVER name it is given, so this driver never calls it without
    first passing every name through ``assert_destination_safe``).
  * ``tests/integration/harness/full_run.py`` -- ``build_full_selection`` and
    ``run_full_transfer``. This driver ALWAYS calls
    ``build_full_selection(exclude=frozenset())`` -- an explicit EMPTY
    exclusion set -- because ``full_run``'s own default excludes
    ``GrammarCategory.STEMS`` and the user has explicitly decided stems are
    required for this sweep. The resulting coverage set is recorded in every
    artifact (Group K, FR-142).
  * ``debug/audit_guid_preservation.py`` -- the ``AllInstances`` identity-keyed
    inventory shape (``{class_name: {guid, ...}}``), reused here as
    ``census_project``.

WRITE SAFETY (Group B) is the highest-severity section of this file. See
``assert_destination_safe`` -- the single choke-point every restore call and
every write-enabled-open call in this driver goes through, computed fresh
from the literal value about to be used, never cached or inherited from an
enumeration helper (FR-013/FR-014/FR-015).

NO SILENT ANYTHING (per the dispatch brief): every recorded exception below
carries its ``traceback.format_exc()``; there is no bare ``except: pass`` in
this file; a project's per-project artifact is written even on an unhandled
failure (best-effort, itself never silently swallowed); the driver's exit
code is non-zero if anything failed.

ASCII-only console output (Windows-terminal safe).
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Optional, Sequence

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT / "src", _ROOT / "tests" / "integration", _ROOT / "debug"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Reused, not reinvented (see module docstring).
import prescan_type_coverage as prescan          # noqa: E402
import audit_guid_preservation as guid_audit     # noqa: E402

# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------

DEFAULT_PROJECTS_ROOT = r"C:\ProgramData\SIL\FieldWorks\Projects"

# Reuse prescan's exact anchored pattern text (not just its intent) as the
# sweep's own narrowest allowlist. FR-011: the sweep supplies the narrowest
# allowlist sufficient for ITS OWN disposable targets, never a shared default.
DEFAULT_ALLOWLIST: tuple[str, ...] = (prescan._TARGET_RE.pattern,)

# FR-006/FR-002: directories that are never a source, by construction, and
# the recorded reason for each.
SWEEP_OWN_ADDITIONAL_WORKING_DIRS: dict[str, str] = {
    # This machine's Ejagham-Mini -> Ejagham-Full-GT-Test additional working
    # directory, used by this repo's other live-parity harnesses (see
    # STATUS.md). It matches the project-on-disk rule and must be excluded
    # by name, not merely by being outside the enumeration root (it is
    # INSIDE the projects root).
    "Ejagham Full GT-Test": (
        "the repo's own additional working directory for prior harness "
        "runs, not a sweep source (FR-006)"
    ),
}

# FR-004: exact spelling the known-good regression set must use, and the
# empty-shell decoy it must never admit.
CANARY_PROJECTS = ("Ejagham Mini", "Esperanto", "Mbugwe LizzieHC practice")
FORBIDDEN_SHELL_DECOY = "Mbugwe Lizzie HCPractice"  # empty shell, no data file

# FR-028/FR-030: PROVISIONAL per-worker memory model. Single-observation
# regression (see specs/035-fullsweep-fidelity/probe-results-live.md): a
# roughly fixed ~190 MB per-process floor (CLR + LCM/FLEx assembly load)
# plus ~1.9 MB of additional RSS per 1 MB of on-disk fwdata. NOT settled
# physics -- replace with observed peak-RSS-per-project once actuals exist
# (FR-030 requires preferring observed actuals over this model wherever
# they exist).
MEM_MODEL_FLOOR_MB_PROVISIONAL = 190.0
MEM_MODEL_SLOPE_MB_PER_MB_PROVISIONAL = 1.9
MEM_MODEL_RESERVE_MB_DEFAULT = 512.0

DEFAULT_ARTIFACTS_DIR = _ROOT / "specs" / "035-fullsweep-fidelity" / "artifacts"
DEFAULT_RUNTIME_DIR = _ROOT / "scratchpad" / "035_sweep"  # ephemeral, gitignored

VALID_LEDGER_STATUSES = ("pending", "running", "passed", "failed", "skipped")
VALID_RUN_INTENTS = ("baseline", "gate")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class WriteSafetyError(RuntimeError):
    """Group B violation. MUST abort the WHOLE run, never just one project."""


class SourceTamperError(RuntimeError):
    """Group B, FR-022: an unexplained fingerprint delta on a SOURCE. MUST
    abort the whole worker pool and escalate to a human."""


class HarnessError(RuntimeError):
    """A structural defect in the sweep's own measurement (e.g. a written
    class absent from the idempotency comparison, FR-046) -- distinct from an
    ordinary project fidelity failure."""


# ===========================================================================
# GROUP B -- WRITE SAFETY (the highest-severity section of this file)
# ===========================================================================

def resolve_projects_root(projects_root: Optional[str] = None) -> Path:
    """FR-017: resolve the projects collection from exactly ONE authority.

    Same env-var-then-Windows-default resolution used by
    ``prescan_type_coverage``, ``restore.py`` and ``full_run.py`` elsewhere in
    this repo, so the sweep's restore side and write side can never disagree
    about where "the projects collection" is.
    """
    root = projects_root or os.environ.get("GRAMTRANS_PROJECTS_ROOT") or DEFAULT_PROJECTS_ROOT
    p = Path(root)
    if not p.is_dir():
        raise WriteSafetyError(
            "[FR-017] projects root does not exist or is not a directory: %r" % (str(p),)
        )
    return p.resolve()


def _reject_unsafe_name_shape(name) -> None:
    """FR-018: a bare single name only -- no separator, drive, relative
    component, or empty string, checked BEFORE any allowlist match."""
    if name is None or name == "":
        raise WriteSafetyError("[FR-018] destination name is empty")
    if not isinstance(name, str):
        raise WriteSafetyError("[FR-018] destination name is not a string: %r" % (name,))
    # Path(name).name strips any separator, drive designator, or leading
    # relative-path component; if that transformation changes anything, the
    # original was not a bare single name.
    if Path(name).name != name or name in (".", ".."):
        raise WriteSafetyError(
            "[FR-018] destination %r is not a single bare name (contains a "
            "path separator, drive designator, or relative-path component)" % (name,)
        )


def assert_name_allowlisted(name: str, allowlist: Sequence[str]) -> None:
    """FR-011/FR-012: deny-by-default, anchored FULL-match only.

    ``allowlist`` is a parameter, never a constant baked into this function
    (FR-011) -- other legitimate callers write to differently-named
    disposable targets. An empty or absent allowlist MUST raise, never
    silently admit or deny (FR-011). Matching is ``re.fullmatch`` only --
    never ``search``/``match``/``startswith``/``in`` -- so a name that merely
    begins with, ends with, or contains an allowlisted pattern is refused
    (FR-012; this is what keeps ``Target.pre025bak`` / ``Target.pre029bak``
    archived-evidence directories un-writable even though they begin with
    ``Target``).
    """
    if not allowlist:
        raise WriteSafetyError(
            "[FR-011] allowlist is empty or absent -- refusing to authorize ANY "
            "destination. The caller must supply an explicit, narrow allowlist "
            "of its own disposable targets."
        )
    _reject_unsafe_name_shape(name)
    for pattern in allowlist:
        try:
            m = re.fullmatch(pattern, name)
        except re.error as exc:
            raise WriteSafetyError(
                "[FR-011] allowlist entry %r is not a valid regular expression: %s"
                % (pattern, exc)
            ) from exc
        if m is not None:
            return
    raise WriteSafetyError(
        "[FR-011/FR-012] destination %r does not fully match any entry in the "
        "allowlist %r (anchored full-match required; prefix/substring/glob/"
        "case-insensitive matching is forbidden)" % (name, tuple(allowlist))
    )


def assert_destination_safe(
    name: str,
    *,
    source_name,
    frozen_sources,
    allowlist: Sequence[str],
    projects_root: Optional[str] = None,
) -> Path:
    """THE write-safety choke point (Group B).

    Call this at BOTH boundaries required by FR-013:
      (a) the moment a project is selected as a restore destination, before
          any directory for it is created;
      (b) immediately before any write-enabled open, computed from the value
          actually about to be used -- never a flag computed once and read
          twice.

    Every argument is REQUIRED (no defaults for ``source_name`` /
    ``frozen_sources`` / ``allowlist``) so that FR-015 ("no assertion may be
    skipped because an input it compares is absent") cannot be satisfied by
    quietly omitting the comparison: passing ``None`` explicitly is a loud
    failure here, not a bypass.

    Returns the resolved destination ``Path`` on success. Raises
    ``WriteSafetyError`` on ANY violation; callers MUST let that exception
    propagate all the way out and abort the entire run (Group B is explicit
    that a violation aborts the WHOLE run, not just one project/worker).
    """
    assert_name_allowlisted(name, allowlist)

    if source_name is None:
        raise WriteSafetyError(
            "[FR-015] source_name was omitted (None) -- a write-safety check "
            "with no source to compare against is a bypass, not a pass"
        )
    if name == source_name:
        raise WriteSafetyError(
            "[FR-016] destination %r equals its own assigned source -- refusing" % (name,)
        )

    if frozen_sources is None:
        raise WriteSafetyError(
            "[FR-015] frozen_sources manifest was omitted (None) -- the "
            "manifest-wide check of FR-016 cannot be skipped"
        )
    if name in frozen_sources:
        raise WriteSafetyError(
            "[FR-016] destination %r appears in the run's frozen source "
            "manifest -- refusing regardless of the worker's current pairing "
            "(catches a mis-ordered pairing / stale retry, not just today's "
            "assignment)" % (name,)
        )

    root = resolve_projects_root(projects_root)
    dest = (root / name).resolve()
    if dest.parent != root:
        raise WriteSafetyError(
            "[FR-017] resolved destination %r is not a direct child of the "
            "single-authority projects root %r" % (str(dest), str(root))
        )
    return dest


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


# ===========================================================================
# GROUP A -- CORPUS AND ENUMERATION
# ===========================================================================

@dataclass
class CorpusEntry:
    project: str
    path: str
    fwdata_mb: float
    admitted: bool
    reason: str


def enumerate_corpus(projects_root: Optional[str] = None) -> list[CorpusEntry]:
    """FR-001..FR-009: derive the source corpus at runtime.

    Reuses ``prescan_type_coverage._enumerate`` (which already reuses the
    engine's own project-on-disk rule and already refuses the disposable
    ``Target[0-9]*`` pattern) and layers on this sweep's own additional
    exclusion: its additional working directory (FR-006/FR-002).
    """
    if projects_root is not None:
        os.environ["GRAMTRANS_PROJECTS_ROOT"] = projects_root
    rows = prescan._enumerate()
    out: list[CorpusEntry] = []
    for r in rows:
        name = r["project"]
        admitted = r["disposition"] == "scan"
        reason = r["reason"]
        if admitted and name in SWEEP_OWN_ADDITIONAL_WORKING_DIRS:
            admitted = False
            reason = SWEEP_OWN_ADDITIONAL_WORKING_DIRS[name]
        if admitted and name == FORBIDDEN_SHELL_DECOY:
            # FR-004 belt-and-suspenders: never admit this exact name even if
            # a future disk state somehow gives it a data file.
            admitted = False
            reason = "FR-004: forbidden decoy name, never admitted regardless of disk state"
        out.append(CorpusEntry(project=name, path=r["path"], fwdata_mb=r["fwdata_mb"],
                                admitted=admitted, reason=reason))
    return out


def freeze_source_manifest(corpus: list[CorpusEntry]) -> tuple[str, ...]:
    """FR-035: freeze the admitted source list ONCE before any worker starts."""
    return tuple(sorted(e.project for e in corpus if e.admitted))


# ===========================================================================
# GROUP B (continued) -- SOURCE TAMPER GUARD (fingerprint + classification)
# ===========================================================================

@dataclass(frozen=True)
class SourceFingerprint:
    """FR-020: exactly five recorded fields."""
    size: Optional[int]
    mtime_ns: Optional[int]
    content_sha256: Optional[str]
    data_model_version: Optional[int]
    sharing_settings_sha256: Optional[str]
    sharing_enabled: Optional[bool]  # recorded per FR-010, never used to exclude
    error: str = ""


def _sha256_file(path: Path, chunk_size: int = 1 << 20) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _data_model_version(fwdata_path: Path) -> Optional[int]:
    """Best-effort, cheap version read: the fwdata root element's own
    ``version="..."`` attribute, from the first few KB only (FR-021 forbids
    hashing/reading the whole directory as a fingerprint measure, and reading
    the whole multi-hundred-MB file just for this would be wasteful; the
    version attribute is at the very top of the XML)."""
    try:
        with open(fwdata_path, "rb") as fh:
            head = fh.read(4096)
        text = head.decode("utf-8", errors="replace")
        m = re.search(r'\bversion\s*=\s*"(\d+)"', text)
        return int(m.group(1)) if m else None
    except OSError:
        return None


def _sharing_settings_fingerprint(proj_dir: Path) -> tuple[Optional[str], Optional[bool]]:
    """PROVISIONAL resolution of FR-020's "sharing-settings file" and FR-010's
    "does this source have project sharing enabled" flag.

    No single, unambiguously-named "sharing settings file" was identified in
    flexicon/LCM source during this skeleton's construction (see the
    dispatch session's research: FLEx's "Share project contents with programs
    on this computer" checkbox did not resolve to one named file on disk).
    As a documented, honest stand-in: this hashes the SORTED
    (relative_path, size) listing of the project's ``SharedSettings/``
    directory (present on every project inspected during construction), and
    treats a non-empty ``SharedSettings/`` as the sharing-enabled proxy.

    TODO(035-sharing-settings): confirm the true on-disk sharing-settings
    file/flag against FieldWorks/liblcm source before this proxy is trusted
    for anything beyond the recording FR-010 requires. Never used here to
    EXCLUDE a source -- only recorded, per FR-010.
    """
    d = proj_dir / "SharedSettings"
    if not d.is_dir():
        return None, False
    try:
        entries = sorted(
            (str(p.relative_to(d)).replace("\\", "/"), p.stat().st_size)
            for p in d.rglob("*") if p.is_file()
        )
    except OSError:
        return None, None
    if not entries:
        return None, False
    h = hashlib.sha256(json.dumps(entries, sort_keys=True).encode("utf-8")).hexdigest()
    return h, True


def capture_fingerprint(project_name: str, projects_root: Optional[str] = None) -> SourceFingerprint:
    """FR-020: capture a source's fingerprint. Read-only; touches only the
    data file's own stat/bytes and the SharedSettings listing -- never a
    whole-directory hash (FR-021 forbids that; a read-only open legitimately
    touches lock files, WS-store logs, Temp, and shared-settings areas, and a
    whole-directory hash would false-alarm on every run)."""
    root = resolve_projects_root(projects_root)
    proj_dir = root / project_name
    fwdata = proj_dir / ("%s.fwdata" % project_name)
    try:
        st = fwdata.stat()
        size, mtime_ns = st.st_size, st.st_mtime_ns
    except OSError as exc:
        return SourceFingerprint(None, None, None, None, None, None,
                                  error="data file stat failed: %s" % exc)
    content_hash = _sha256_file(fwdata)
    version = _data_model_version(fwdata)
    sharing_hash, sharing_enabled = _sharing_settings_fingerprint(proj_dir)
    return SourceFingerprint(size, mtime_ns, content_hash, version,
                              sharing_hash, sharing_enabled)


def capture_source_manifest(
    source_names: Sequence[str], projects_root: Optional[str] = None,
) -> dict[str, SourceFingerprint]:
    """FR-020: capture every source's fingerprint ONCE, before any worker
    starts, into a single recorded manifest. A per-worker just-in-time
    pre-fingerprint is forbidden (it would baseline damage another worker has
    already done)."""
    return {name: capture_fingerprint(name, projects_root) for name in source_names}


FINGERPRINT_VERDICT_UNCHANGED = "UNCHANGED"
FINGERPRINT_VERDICT_MIGRATION = "MIGRATION_FINDING"
FINGERPRINT_VERDICT_UNEXPLAINED_WRITE = "UNEXPLAINED_WRITE_ABORT"
FINGERPRINT_VERDICT_HASH_ONLY = "HASH_ONLY_CHANGE_ABORT"
FINGERPRINT_VERDICT_SHARING_CHANGED = "SHARING_SETTINGS_CHANGED_ABORT"
FINGERPRINT_VERDICT_SOURCE_MISSING = "SOURCE_DATA_FILE_MISSING_ABORT"


def classify_fingerprint_delta(before: SourceFingerprint, after: SourceFingerprint) -> str:
    """FR-022: classify a fingerprint delta. Each class has ONE mandated
    response; this function returns the classification label only -- the
    caller (the per-project loop / the pool driver) is responsible for
    actually acting on an *_ABORT label by aborting the whole pool and
    escalating to a human. Never silently ignored."""
    if after.size is None and after.error:
        return FINGERPRINT_VERDICT_SOURCE_MISSING

    if before.sharing_settings_sha256 != after.sharing_settings_sha256:
        return FINGERPRINT_VERDICT_SHARING_CHANGED

    hash_changed = before.content_sha256 != after.content_sha256
    size_changed = before.size != after.size
    mtime_changed = before.mtime_ns != after.mtime_ns

    if not hash_changed and not size_changed and not mtime_changed:
        return FINGERPRINT_VERDICT_UNCHANGED

    if hash_changed and not size_changed and not mtime_changed:
        # Hash differs while size+timestamp are identical: not a migration,
        # a write that reached the source, or the filesystem lying.
        return FINGERPRINT_VERDICT_HASH_ONLY

    if hash_changed and size_changed and mtime_changed:
        # "the file still parses" is approximated here by: we could still
        # read a data-model version out of it post-use. A full-fidelity
        # parse check is deferred (see TODO below).
        parses = after.data_model_version is not None
        if parses and before.data_model_version is not None \
                and after.data_model_version > before.data_model_version:
            return FINGERPRINT_VERDICT_MIGRATION
        return FINGERPRINT_VERDICT_UNEXPLAINED_WRITE

    # Any other partial-change shape (e.g. size+mtime changed but hash did
    # not, which should be impossible for a real content change) is itself
    # suspicious; fail closed toward the more severe classification rather
    # than inventing a sixth bucket.
    # TODO(035-parse-check): replace the data-model-version proxy above with
    # an actual "does this file still parse as valid LCM XML" check once a
    # cheap one is available; today's proxy can't distinguish "did not parse"
    # from "no version attribute found".
    return FINGERPRINT_VERDICT_UNEXPLAINED_WRITE


# ===========================================================================
# GROUP C -- PARALLEL TARGET POOL
# ===========================================================================

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


# ===========================================================================
# GROUP D -- DOUBLE-MOVE AND IDEMPOTENCY
# ===========================================================================

def census_project(project_name: str) -> dict[str, set]:
    """FR-043/FR-044: a per-class object inventory keyed by identity (GUID),
    reusing the exact ``AllInstances`` shape ``audit_guid_preservation.py``
    already proved out (``{class_name: {guid, ...}}``). Opens read-only."""
    return dict(guid_audit.inventory_all(project_name))


def written_classes(before: dict[str, set], after: dict[str, set]) -> dict[str, dict]:
    """FR-045: the set of classes the FIRST transfer is observed to have
    written, computed as the after-minus-before delta -- never a hand-picked
    list. Returns {class: {"new": [...], "removed": [...]}} for every class
    where the identity SET actually changed (new members, missing members,
    or both)."""
    out: dict[str, dict] = {}
    for cls in set(before) | set(after):
        b, a = before.get(cls, set()), after.get(cls, set())
        new, removed = a - b, b - a
        if new or removed:
            out[cls] = {"new": sorted(new), "removed": sorted(removed)}
    return out


@dataclass
class IdempotencyResult:
    written_class_set: tuple[str, ...]
    unchanged_classes: tuple[str, ...]
    diverged_classes: dict  # class -> {"only_after_1": [...], "only_after_2": [...]}
    passed: bool
    harness_error: str = ""


def check_idempotency(
    after_first: dict[str, set], after_second: dict[str, set], written: dict[str, dict],
) -> IdempotencyResult:
    """FR-045/FR-046/FR-047/FR-048/FR-049.

    Idempotency is measured EXACTLY over ``written`` (the class set the first
    transfer is observed to have touched, per ``written_classes`` above) --
    never a fixed, hand-picked counter list. If the second transfer's
    inventory shows a changed class that is absent from ``written``, that is
    a harness error (FR-046), not a quiet pass, because FR-049 makes that
    shape structurally impossible for a correct measurement.
    """
    written_set = set(written)
    diverged: dict = {}
    for cls in set(after_first) | set(after_second):
        a1, a2 = after_first.get(cls, set()), after_second.get(cls, set())
        if a1 == a2:
            continue
        only_1, only_2 = a1 - a2, a2 - a1
        diverged[cls] = {"only_after_1": sorted(only_1), "only_after_2": sorted(only_2)}
        if cls not in written_set:
            return IdempotencyResult(
                written_class_set=tuple(sorted(written_set)),
                unchanged_classes=(), diverged_classes=diverged, passed=False,
                harness_error=(
                    "[FR-046/FR-049] class %r changed between the first and "
                    "second transfer's inventories but was not in the set of "
                    "classes the first transfer is recorded to have written -- "
                    "this measurement is structurally invalid" % (cls,)
                ),
            )
    unchanged = tuple(sorted(written_set - set(diverged)))
    return IdempotencyResult(
        written_class_set=tuple(sorted(written_set)),
        unchanged_classes=unchanged, diverged_classes=diverged,
        passed=not diverged,
    )


# ===========================================================================
# GROUP E/F/G/H PLUGGABLE SEAM -- NOT BUILT HERE (still in review)
# ===========================================================================

def compare_objects(source_inventory: dict, target_inventory: dict) -> list[dict]:
    """EXTENSION POINT for the field-level fidelity comparator.

    Deliberately NOT the taxonomy from spec.md Groups E (field-level
    semantics), F (vacuity guards), G (verdict/exit model), H (loss
    allowlist), or the identity-substitution rules of Group P -- those are
    still in review as of 2026-08-18 (cycle3-amendments.md and
    cycle3-safety-amendments.md have not yet been folded into spec.md's
    settled requirement groups) and inventing them here would hardcode a
    taxonomy this feature does not yet have authority to hardcode.

    Contract for the eventual real implementation:
        source_inventory / target_inventory: ``{class_name: {guid, ...}}``,
            the same identity-keyed shape ``census_project`` returns.
        Returns: ``list[dict]`` "findings". Per FR-145 (settled, Group K),
            every real finding MUST eventually carry AT LEAST:
                {"class": str, "category": str | None, "field": str | None,
                 "source_value": Any, "target_value": Any,
                 "verdict": str, "guid": str}
            -- but the legal ``verdict`` vocabulary (RESOLVED / DANGLING /
            SILENTLY_UNSET / LOST-BUT-ACCOUNTED / RESOLVED-BY-EQUIVALENCE for
            links; DISTORTED / EXPECTED_DIVERGENT / etc. for field content;
            the five FR-094..FR-099 vacuity guards; the allowlist-consumption
            accounting of Group H) is exactly what has not been settled.

    TODO(035-verdict-taxonomy): replace this stub once Groups E-P leave
    review. Until then this performs ONLY the total-accounting
    presence/absence reconciliation that the identity-keyed census already
    gives for free -- no taxonomy decision required for that much: a source
    GUID is either present in the target's post-transfer inventory for its
    class, or it is not.

    ``run_one_project`` (below) takes this function as an injectable
    parameter (default: this stub) so a future comparator can be wired in
    without touching the driver's control flow.
    """
    findings: list[dict] = []
    for cls, src_guids in source_inventory.items():
        tgt_guids = target_inventory.get(cls, set())
        for g in sorted(src_guids - tgt_guids):
            findings.append({
                "class": cls, "category": None, "field": None,
                "source_value": g, "target_value": None,
                "verdict": "NOT_YET_CLASSIFIED_MISSING_FROM_TARGET",
                "guid": g,
            })
    return findings


# ===========================================================================
# GROUP K -- ARTIFACT AND PROVENANCE
# ===========================================================================

def _run_git(args: list[str], cwd: Path) -> str:
    cp = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    if cp.returncode != 0:
        raise RuntimeError("git %s failed in %s: %s" % (" ".join(args), cwd, cp.stderr.strip()))
    return cp.stdout.strip()


def _git_revision(repo_dir: Path) -> dict:
    """Returns {"sha": str, "dirty": bool} or {"sha": None, "error": str}."""
    try:
        sha = _run_git(["rev-parse", "HEAD"], repo_dir)
        status = _run_git(["status", "--porcelain"], repo_dir)
        return {"sha": sha, "dirty": bool(status.strip()), "error": ""}
    except Exception as exc:  # noqa: BLE001 -- recorded, never silent
        return {"sha": None, "dirty": None, "error": "%s: %s" % (type(exc).__name__, exc)}


def gramtrans_revision() -> dict:
    """FR-138: this driver's own source-revision identity + dirty flag."""
    return _git_revision(_ROOT)


def flexicon_revision() -> dict:
    """FR-139/FR-157: the transfer engine dependency's revision identity --
    a git SHA, NOT its version string (per this repo's CLAUDE.md: "flexicon
    reports a version string that is not reliably bumped when its runtime
    behavior changes"; also independently observed live, see
    probe-results-live.md's "undoable default" finding)."""
    try:
        import flexicon
        pkg_dir = Path(flexicon.__file__).resolve().parent
    except Exception as exc:  # noqa: BLE001
        return {"sha": None, "dirty": None,
                "error": "could not import flexicon: %s: %s" % (type(exc).__name__, exc)}
    d = pkg_dir
    for _ in range(6):
        if (d / ".git").exists():
            return _git_revision(d)
        if d.parent == d:
            break
        d = d.parent
    return {"sha": None, "dirty": None,
            "error": "no .git found walking up from %s" % pkg_dir}


def revision_pair() -> dict:
    return {"gramtrans": gramtrans_revision(), "flexicon": flexicon_revision()}


@dataclass
class ProjectArtifact:
    """Group K durable, per-project artifact. Every field required by the
    settled FR-138..FR-151 stamps is present; findings/detail lists are
    NEVER truncated here (FR-144 -- truncation is a console-only concern)."""
    project: str
    run_intent: str                    # FR-188/FR-166: "baseline" | "gate"
    revision_pair: dict                # FR-157
    dirty_gramtrans: Optional[bool]    # FR-138
    coverage_categories: list          # FR-142 (the categories actually run)
    phases_completed: list = field(default_factory=list)  # FR-150
    source_fingerprint_before: dict = field(default_factory=dict)
    source_fingerprint_after: dict = field(default_factory=dict)
    fingerprint_verdict: str = ""      # FR-022 classification
    census_before: dict = field(default_factory=dict)      # class -> sorted [guid,...]
    census_after_first: dict = field(default_factory=dict)
    census_after_second: dict = field(default_factory=dict)
    written_classes: dict = field(default_factory=dict)
    idempotency: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)           # compare_objects() output
    status: str = "running"            # FR-156 ledger vocabulary
    reason: str = ""
    errors: list = field(default_factory=list)             # [{phase, error, traceback}]
    started_at: float = 0.0
    finished_at: float = 0.0


def _atomic_write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    os.replace(str(tmp), str(path))


def flush_artifact(artifact: ProjectArtifact, artifacts_dir: Path) -> Path:
    """FR-150: flush after every phase, so a crash leaves a partial artifact
    naming the last completed phase, never no evidence at all."""
    out = artifacts_dir / ("%s.json" % re.sub(r"[^A-Za-z0-9._ -]", "_", artifact.project))
    _atomic_write_json(out, asdict(artifact))
    return out


# ===========================================================================
# GROUP L -- LEDGER (batched, gated, fix-forward execution)
# ===========================================================================

class Ledger:
    """FR-156: a durable, per-project status ledger surviving restarts,
    tracked in git (default path lives under specs/035-fullsweep-fidelity/,
    which this repo's CLAUDE.md workflow commits to main -- never a
    gitignored scratch path)."""

    def __init__(self, path: Path = DEFAULT_ARTIFACTS_DIR / "ledger.json"):
        self.path = path
        self._data: dict = {}
        self.load()

    def load(self) -> None:
        if self.path.is_file():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self._data = {}

    def save(self) -> None:
        _atomic_write_json(self.path, self._data)

    def set_status(self, project: str, status: str, *, reason: str = "",
                   revision_pair: Optional[dict] = None) -> None:
        if status not in VALID_LEDGER_STATUSES:
            raise ValueError("invalid ledger status %r" % (status,))
        self._data[project] = {
            "status": status, "reason": reason,
            "revision_pair": revision_pair or {},
            "updated_at": time.time(),
        }
        self.save()

    def get(self, project: str) -> Optional[dict]:
        return self._data.get(project)

    def all(self) -> dict:
        return dict(self._data)


def corpus_status_summary(ledger: Ledger, current_pair: dict) -> dict:
    """FR-157/FR-158: separate currently-valid passes from STALE ones; never
    report a single unqualified "all green" unless every pass shares the
    current driver-and-dependency revision pair."""
    valid, stale, other = [], [], []
    for name, row in ledger.all().items():
        if row.get("status") != "passed":
            other.append(name)
            continue
        if row.get("revision_pair") == current_pair:
            valid.append(name)
        else:
            stale.append(name)
    return {
        "currently_valid_passes": sorted(valid),
        "stale_passes": sorted(stale),
        "other": sorted(other),
        "all_green": bool(valid) and not stale and not other,
    }


# ===========================================================================
# PER-PROJECT DOUBLE-MOVE LOOP (Groups B/D/K wired together)
# ===========================================================================

def run_one_project(
    source_name: str,
    *,
    target_name: str,
    frozen_sources: tuple,
    allowlist: Sequence[str],
    run_intent: str,
    backup_path=None,
    projects_root: Optional[str] = None,
    artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR,
    comparator: Callable[[dict, dict], list] = compare_objects,
) -> ProjectArtifact:
    """FR-043: restore -> census -> Move #1 -> census -> Move #2 -> census ->
    restore, for exactly one project, with the write-safety choke point
    re-evaluated at every restore/write boundary (never cached)."""
    if run_intent not in VALID_RUN_INTENTS:
        raise ValueError("run_intent must be one of %r" % (VALID_RUN_INTENTS,))

    from harness import restore as restore_mod  # lazy: harness package on sys.path
    from harness import full_run

    artifact = ProjectArtifact(
        project=source_name, run_intent=run_intent, revision_pair=revision_pair(),
        dirty_gramtrans=None, coverage_categories=[], started_at=time.time(),
    )
    rp = artifact.revision_pair
    artifact.dirty_gramtrans = rp.get("gramtrans", {}).get("dirty")

    root = resolve_projects_root(projects_root)
    target_path = str(root / target_name)

    src_fp_before = capture_fingerprint(source_name, projects_root)
    artifact.source_fingerprint_before = asdict(src_fp_before)
    flush_artifact(artifact, artifacts_dir)

    try:
        # ---- boundary (a): restore, first pass -------------------------
        dest = assert_destination_safe(
            target_name, source_name=source_name, frozen_sources=frozen_sources,
            allowlist=allowlist, projects_root=projects_root,
        )
        self_heal_stale_lock(dest, target_name)
        restore_mod.restore_target(target_name, backup_path=backup_path,
                                    projects_root=str(root))
        artifact.phases_completed.append("restore_initial")
        flush_artifact(artifact, artifacts_dir)

        census_before = census_project(target_name)
        artifact.census_before = {k: sorted(v) for k, v in census_before.items()}
        artifact.phases_completed.append("census_before")
        flush_artifact(artifact, artifacts_dir)

        selection = full_run.build_full_selection(exclude=frozenset())
        artifact.coverage_categories = sorted(c.value for c, on in selection.categories.items() if on)

        # ---- boundary (b): re-asserted immediately before the write-
        # enabled open that run_full_transfer performs internally, computed
        # fresh from the literal target_name about to be used -----------
        assert_destination_safe(
            target_name, source_name=source_name, frozen_sources=frozen_sources,
            allowlist=allowlist, projects_root=projects_root,
        )
        plan1, report1 = full_run.run_full_transfer(source_name, target_name, target_path)
        artifact.phases_completed.append("first_transfer")
        flush_artifact(artifact, artifacts_dir)

        census_after_1 = census_project(target_name)
        artifact.census_after_first = {k: sorted(v) for k, v in census_after_1.items()}
        artifact.phases_completed.append("census_after_first")
        flush_artifact(artifact, artifacts_dir)

        written = written_classes(census_before, census_after_1)
        artifact.written_classes = written

        assert_destination_safe(
            target_name, source_name=source_name, frozen_sources=frozen_sources,
            allowlist=allowlist, projects_root=projects_root,
        )
        plan2, report2 = full_run.run_full_transfer(source_name, target_name, target_path)
        artifact.phases_completed.append("second_transfer")
        flush_artifact(artifact, artifacts_dir)

        census_after_2 = census_project(target_name)
        artifact.census_after_second = {k: sorted(v) for k, v in census_after_2.items()}
        artifact.phases_completed.append("census_after_second")
        flush_artifact(artifact, artifacts_dir)

        idem = check_idempotency(census_after_1, census_after_2, written)
        artifact.idempotency = asdict(idem)
        if idem.harness_error:
            raise HarnessError(idem.harness_error)

        source_inventory = census_project(source_name)
        artifact.findings = comparator(source_inventory, census_after_2)

        artifact.status = "passed" if (idem.passed and not artifact.findings) else "failed"
        artifact.reason = "" if artifact.status == "passed" else (
            idem.harness_error or "unresolved findings (see .findings) / idempotency divergence"
        )
    except Exception as exc:  # noqa: BLE001 -- recorded loudly, never swallowed
        artifact.status = "failed"
        artifact.reason = "%s: %s" % (type(exc).__name__, exc)
        artifact.errors.append({
            "phase": artifact.phases_completed[-1] if artifact.phases_completed else "setup",
            "error": artifact.reason,
            "traceback": traceback.format_exc(),
        })
        raise
    finally:
        # FR-050: restore the target to baseline and write the artifact even
        # on an unhandled failure.
        try:
            dest = assert_destination_safe(
                target_name, source_name=source_name, frozen_sources=frozen_sources,
                allowlist=allowlist, projects_root=projects_root,
            )
            self_heal_stale_lock(dest, target_name)
            restore_mod.restore_target(target_name, backup_path=backup_path,
                                        projects_root=str(root))
            artifact.phases_completed.append("restore_final")
        except Exception as exc:  # noqa: BLE001 -- recorded, not swallowed
            artifact.errors.append({
                "phase": "restore_final", "error": "%s: %s" % (type(exc).__name__, exc),
                "traceback": traceback.format_exc(),
            })

        src_fp_after = capture_fingerprint(source_name, projects_root)
        artifact.source_fingerprint_after = asdict(src_fp_after)
        verdict = classify_fingerprint_delta(src_fp_before, src_fp_after)
        artifact.fingerprint_verdict = verdict
        if verdict not in (FINGERPRINT_VERDICT_UNCHANGED, FINGERPRINT_VERDICT_MIGRATION):
            artifact.status = "failed"
            artifact.reason = ("SOURCE TAMPER GUARD: %s -- %s" % (verdict, artifact.reason)).strip(" -")

        artifact.finished_at = time.time()
        flush_artifact(artifact, artifacts_dir)

    return artifact


# ===========================================================================
# CLI
# ===========================================================================

def _cmd_list(args) -> int:
    corpus = enumerate_corpus(args.projects_root)
    admitted = [e for e in corpus if e.admitted]
    excluded = [e for e in corpus if not e.admitted]
    print("[INFO] admitted sources: %d" % len(admitted))
    for e in admitted:
        print("  %-38s %8.2f MB" % (e.project, e.fwdata_mb))
    print("[INFO] excluded: %d" % len(excluded))
    for e in excluded:
        print("  %-38s %s" % (e.project, e.reason))
    return 0


def _cmd_project(args) -> int:
    """Worker mode: run the full double-move loop for exactly ONE project,
    in THIS process (intended to be launched as a subprocess by the batch
    driver, per FR-026/FR-037/FR-038 -- one OS process, one log file, per
    project)."""
    corpus = enumerate_corpus(args.projects_root)
    frozen = freeze_source_manifest(corpus)
    if args.source not in frozen:
        print("[ERROR] %r is not in the frozen admitted-source manifest" % args.source)
        return 2
    allowlist = tuple(args.allowlist) if args.allowlist else DEFAULT_ALLOWLIST
    try:
        artifact = run_one_project(
            args.source, target_name=args.target, frozen_sources=frozen,
            allowlist=allowlist, run_intent=args.intent,
            backup_path=args.backup, projects_root=args.projects_root,
            artifacts_dir=Path(args.artifacts_dir),
        )
    except (WriteSafetyError, SourceTamperError) as exc:
        # These MUST abort the whole run -- re-raise after making that loud.
        print("[ABORT-WHOLE-RUN] %s: %s" % (type(exc).__name__, exc))
        raise
    print("[RESULT] %s -> %s" % (args.source, artifact.status))
    return 0 if artifact.status == "passed" else 1


def _cmd_batch(args) -> int:
    """Driver mode skeleton: admits a batch of --batch-size projects,
    running each as an isolated subprocess (FR-026), gated by the memory
    admission check (FR-028) and the concurrency-trial gate (FR-032). This
    skeleton runs workers SERIALLY when --workers=1 (the FR-031 default);
    it refuses to do otherwise without a recorded concurrency-trial
    artifact (assert_concurrency_gate_satisfied)."""
    assert_concurrency_gate_satisfied(args.workers)
    corpus = enumerate_corpus(args.projects_root)
    frozen = freeze_source_manifest(corpus)
    allowlist = tuple(args.allowlist) if args.allowlist else DEFAULT_ALLOWLIST
    target_pool = default_target_pool(args.workers)
    assert_distinct_target_pool(target_pool, frozen)

    manifest_fp = capture_source_manifest(frozen, args.projects_root)
    print("[INFO] captured fingerprints for %d frozen sources" % len(manifest_fp))

    ledger = Ledger(Path(args.artifacts_dir) / "ledger.json")
    pending = [n for n in frozen if (ledger.get(n) or {}).get("status") != "passed"]
    if args.canary and args.canary not in pending:
        pending = [args.canary] + pending  # FR-159: canary re-runs every batch
    batch = pending[: args.batch_size]

    print("[INFO] batch of %d: %s" % (len(batch), ", ".join(batch)))
    exit_code = 0
    for i, source in enumerate(batch):
        target = target_pool[i % len(target_pool)]
        row = next((e for e in corpus if e.project == source), None)
        try:
            assert_memory_admits(row.fwdata_mb if row else 0.0)
        except MemoryShortfall as exc:
            print("[WAIT] %s: %s (admitting fewer workers / waiting is an "
                  "operational concern, NOT a safety abort)" % (source, exc))
            exit_code = exit_code or 3
            continue
        ledger.set_status(source, "running")
        worker_env = dict(os.environ)
        for ambient in ("GRAMTRANS_PROJECTS_ROOT",):
            worker_env.pop(ambient, None)
        worker_env["GRAMTRANS_PROJECTS_ROOT"] = str(resolve_projects_root(args.projects_root))
        cmd = [sys.executable, str(Path(__file__).resolve())]
        if args.projects_root:
            cmd += ["--projects-root", args.projects_root]
        cmd += ["--artifacts-dir", args.artifacts_dir, "--runtime-dir", args.runtime_dir,
                "project", "--source", source, "--target", target, "--intent", args.intent]
        log_dir = Path(args.runtime_dir) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / ("%s.log" % re.sub(r"[^A-Za-z0-9._ -]", "_", source))
        with ExclusiveTargetClaim(target, Path(args.runtime_dir)):
            with open(log_path, "w", encoding="utf-8") as logf:
                cp = subprocess.run(cmd, env=worker_env, stdout=logf, stderr=subprocess.STDOUT)
        status = "passed" if cp.returncode == 0 else "failed"
        ledger.set_status(source, status, reason="" if status == "passed" else
                           "worker exited %d; see %s" % (cp.returncode, log_path),
                           revision_pair=revision_pair())
        if status != "passed":
            exit_code = 1
        print("[BATCH] %-38s %s (see %s)" % (source, status, log_path))

    print("\n[INFO] batch complete; stopping for analysis before any further "
          "batch is admitted (FR-153).")
    return exit_code


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--projects-root")
    ap.add_argument("--artifacts-dir", default=str(DEFAULT_ARTIFACTS_DIR))
    ap.add_argument("--runtime-dir", default=str(DEFAULT_RUNTIME_DIR))
    ap.add_argument("--allowlist", nargs="*", default=None,
                     help="anchored regex patterns; default: this sweep's own "
                          "Target[0-9]* pool only")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="enumerate the corpus")
    p_list.set_defaults(func=_cmd_list)

    p_project = sub.add_parser("project", help="worker mode: run one project")
    p_project.add_argument("--source", required=True)
    p_project.add_argument("--target", required=True)
    p_project.add_argument("--backup", default=None)
    p_project.add_argument("--intent", required=True, choices=VALID_RUN_INTENTS)
    p_project.set_defaults(func=_cmd_project)

    p_batch = sub.add_parser("batch", help="driver mode: admit and run one batch")
    p_batch.add_argument("--batch-size", type=int, default=3)
    p_batch.add_argument("--workers", type=int, default=1)
    p_batch.add_argument("--canary", default=CANARY_PROJECTS[0])
    p_batch.add_argument("--intent", required=True, choices=VALID_RUN_INTENTS)
    p_batch.set_defaults(func=_cmd_batch)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
