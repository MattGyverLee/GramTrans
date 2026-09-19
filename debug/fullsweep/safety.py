"""Feature 035 -- Group B: WRITE SAFETY (the highest-severity section of this
package). Moved unchanged out of the ``debug/run_fullcopy_sweep.py`` monolith
(T003/T009 of specs/035-fullsweep-fidelity/tasks.md Phase 1).

WRITE SAFETY is the highest-severity section of this driver. See
``assert_destination_safe`` -- the single choke-point every restore call and
every write-enabled-open call in this driver goes through, computed fresh
from the literal value about to be used, never cached or inherited from an
enumeration helper (FR-013/FR-014/FR-015).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

import prescan_type_coverage as prescan  # noqa: E402 -- reused, not reinvented

DEFAULT_PROJECTS_ROOT = r"C:\ProgramData\SIL\FieldWorks\Projects"

# Reuse prescan's exact anchored pattern text (not just its intent) as the
# sweep's own narrowest allowlist. FR-011: the sweep supplies the narrowest
# allowlist sufficient for ITS OWN disposable targets, never a shared default.
DEFAULT_ALLOWLIST: tuple[str, ...] = (prescan._TARGET_RE.pattern,)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class WriteSafetyError(RuntimeError):
    """Group B violation. MUST abort the WHOLE run, never just one project."""


class SourceTamperError(RuntimeError):
    """Group B, FR-022: an unexplained fingerprint delta on a SOURCE. MUST
    abort the whole worker pool and escalate to a human."""


class EvidenceProvenanceError(RuntimeError):
    """FR-149: a verdict input (the driver itself, a roster, an allowlist, a
    capability fingerprint, or the ledger) is not under version control, or
    is excluded by an ignore rule. A verdict produced from such an input is
    NOT ADMISSIBLE EVIDENCE, so this is a provenance failure -- distinct
    from ``WriteSafetyError`` (nothing unsafe was attempted) and from
    ``SourceTamperError`` (no source changed). ``errors.classify_exception``
    maps it to ``PROVENANCE``, which FR-175 aborts the whole run on."""


# ===========================================================================
# GROUP B (continued) -- T019: THE ASSERTION LEDGER (FR-024) AND THE TWO
# INDEPENDENT BOUNDARIES (FR-013)
# ===========================================================================

#: The five assertions ``assert_destination_safe`` evaluates, named so that a
#: skipped one is VISIBLE in the artifact rather than inferred from the
#: absence of a failure (FR-024 last sentence).
ASSERTION_NAME_SHAPE = "name-shape"              # FR-018
ASSERTION_ALLOWLIST = "allowlist-fullmatch"      # FR-011/FR-012
ASSERTION_SOURCE_DISTINCT = "source-distinct"    # FR-016 (this worker's pairing)
ASSERTION_MANIFEST_WIDE = "manifest-wide"        # FR-016 (whole frozen manifest)
ASSERTION_ROOT_CONTAINMENT = "root-containment"  # FR-017

REQUIRED_ASSERTIONS: tuple[str, ...] = (
    ASSERTION_NAME_SHAPE,
    ASSERTION_ALLOWLIST,
    ASSERTION_SOURCE_DISTINCT,
    ASSERTION_MANIFEST_WIDE,
    ASSERTION_ROOT_CONTAINMENT,
)

#: FR-013: the two boundaries, evaluated INDEPENDENTLY. Boundary (b) is
#: deliberately NOT named "write-enabled open" -- FR-013 forbids describing
#: it that way, because a settings rewrite can precede that open along an
#: existing code path, so an assertion placed at the open would sit after
#: the first irreversible write.
BOUNDARY_RESTORE = "restore-destination-selected"   # FR-013(a)
BOUNDARY_FIRST_WRITE = "first-byte-beneath-target"  # FR-013(b)

BOUNDARIES: tuple[str, ...] = (BOUNDARY_RESTORE, BOUNDARY_FIRST_WRITE)


@dataclass
class AssertionLedger:
    """FR-024: a per-project record that each write-safety assertion was IN
    FACT evaluated, at which boundary, against which literal values.

    This is an evidence recorder, never a memo: nothing in this module ever
    reads the ledger to decide whether to SKIP an assertion. Recording that
    an assertion passed at boundary (a) can therefore never satisfy boundary
    (b) -- which is exactly what FR-013's "a defect that skips one MUST NOT
    be able to skip the other" requires.
    """
    project: str = ""
    records: list = field(default_factory=list)

    def record(self, assertion: str, boundary: str, **evidence) -> None:
        self.records.append({
            "assertion": assertion, "boundary": boundary, "evidence": evidence,
        })

    def evaluated(self, boundary: str) -> set:
        return {r["assertion"] for r in self.records if r["boundary"] == boundary}

    def boundaries_evaluated(self) -> set:
        return {r["boundary"] for r in self.records}

    def as_list(self) -> list:
        return list(self.records)


def _record(ledger, assertion: str, boundary: str, **evidence) -> None:
    """Internal: a no-op when no ledger was supplied, so the choke point stays
    usable from a bare call site. The ABSENCE of a ledger is never treated as
    "the assertion was performed" anywhere -- see
    ``assert_boundary_fully_evaluated``, which fails on a missing ledger."""
    if ledger is not None:
        ledger.record(assertion, boundary, **evidence)


def assert_boundary_fully_evaluated(ledger, boundary: str) -> None:
    """FR-024: all five assertions must have been evaluated at ``boundary``.

    A missing ledger, or a ledger with nothing recorded for the boundary, is
    a FAILURE -- never a pass. FR-015's principle applied to the evidence
    itself: an absent record is not an absent violation.
    """
    if ledger is None:
        raise WriteSafetyError(
            "[FR-024] no assertion ledger was kept for boundary %r -- a run "
            "that cannot show its assertions were evaluated has not shown "
            "they were" % (boundary,)
        )
    if boundary not in BOUNDARIES:
        raise WriteSafetyError(
            "[FR-013] unknown write-safety boundary %r -- must be one of %r"
            % (boundary, BOUNDARIES)
        )
    missing = sorted(set(REQUIRED_ASSERTIONS) - ledger.evaluated(boundary))
    if missing:
        raise WriteSafetyError(
            "[FR-024] boundary %r did not evaluate every required write-safety "
            "assertion; missing=%r (a silently skipped assertion must be "
            "visible here, not inferred from the absence of a failure)"
            % (boundary, missing)
        )


def assert_both_boundaries_evaluated(ledger) -> None:
    """FR-013: BOTH boundaries must be independently evaluated for a project.

    Called at the end of a project's run so a defect that removed one of the
    two call sites is a loud failure rather than a silently narrower guard.
    """
    for boundary in BOUNDARIES:
        assert_boundary_fully_evaluated(ledger, boundary)


def assert_restore_boundary(
    name: str, *, source_name, frozen_sources, allowlist: Sequence[str],
    projects_root: Optional[str] = None, ledger=None,
) -> Path:
    """FR-013(a): the moment a project is SELECTED as a restore destination,
    before any directory for it is created.

    A full, independent evaluation -- it shares no cached flag, no memo, and
    no early return with ``assert_first_write_boundary``.
    """
    return assert_destination_safe(
        name, source_name=source_name, frozen_sources=frozen_sources,
        allowlist=allowlist, projects_root=projects_root,
        ledger=ledger, boundary=BOUNDARY_RESTORE,
    )


def assert_first_write_boundary(
    name: str, *, source_name, frozen_sources, allowlist: Sequence[str],
    projects_root: Optional[str] = None, ledger=None,
) -> Path:
    """FR-013(b)/FR-014: the first byte written anywhere beneath that
    project's own directory, by whichever code path reaches that point
    first -- computed from the values THIS site is about to use.

    Deliberately a separate function from ``assert_restore_boundary``, with
    its own complete evaluation: FR-014 forbids inheriting the assertion
    from whatever enumerated or selected the candidate, and FR-013 forbids
    one boundary's result satisfying the other.
    """
    return assert_destination_safe(
        name, source_name=source_name, frozen_sources=frozen_sources,
        allowlist=allowlist, projects_root=projects_root,
        ledger=ledger, boundary=BOUNDARY_FIRST_WRITE,
    )


# ===========================================================================
# GROUP B (continued) -- T019: FR-149 TRACKEDNESS
# ===========================================================================

#: FR-149's own enumeration: "The sweep's own code, and every roster,
#: allowlist, capability expectation, and ledger its verdict depends on".
EVIDENCE_KIND_DRIVER = "driver"
EVIDENCE_KIND_ROSTER = "roster"
EVIDENCE_KIND_ALLOWLIST = "allowlist"
EVIDENCE_KIND_CAPABILITY = "capability-expectation"
EVIDENCE_KIND_LEDGER = "ledger"

EVIDENCE_KINDS: tuple[str, ...] = (
    EVIDENCE_KIND_DRIVER, EVIDENCE_KIND_ROSTER, EVIDENCE_KIND_ALLOWLIST,
    EVIDENCE_KIND_CAPABILITY, EVIDENCE_KIND_LEDGER,
)


def _git(args, cwd: Path):
    import subprocess
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def is_tracked(path, repo_root: Optional[Path] = None) -> tuple:
    """Return ``(tracked: bool, reason: str)`` for ``path``.

    Tracked means BOTH: git knows the path (``git ls-files --error-unmatch``
    succeeds) AND no ignore rule excludes it (``git check-ignore`` does not
    match). FR-149 names both conditions -- "MUST be under version control
    and MUST NOT be excluded by any ignore rule" -- because a file can be
    committed and still sit under a later-added ignore rule, at which point
    the next contributor's checkout silently does not have it.
    """
    p = Path(path)
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]
    cp = _git(["ls-files", "--error-unmatch", "--", str(p)], root)
    if cp.returncode != 0:
        return False, "not under version control (git ls-files: %s)" % (
            (cp.stderr or cp.stdout).strip() or "no such tracked path")
    ignored = _git(["check-ignore", "-q", "--", str(p)], root)
    if ignored.returncode == 0:
        return False, "excluded by a gitignore rule"
    return True, ""


def assert_tracked(path, *, kind: str, repo_root: Optional[Path] = None) -> None:
    """FR-149: refuse to treat an untracked or ignored input as admissible
    evidence.

    Raises ``EvidenceProvenanceError`` -- NOT ``WriteSafetyError``: nothing
    unsafe was attempted, the run simply cannot claim what it is about to
    claim. ``errors.classify_exception`` maps this to ``PROVENANCE``, one of
    FR-175's four whole-run abort codes.
    """
    if kind not in EVIDENCE_KINDS:
        raise ValueError("[FR-149] unknown evidence kind %r -- must be one of %r"
                          % (kind, EVIDENCE_KINDS))
    tracked, reason = is_tracked(path, repo_root)
    if not tracked:
        raise EvidenceProvenanceError(
            "[FR-149] %s %r is %s. A verdict produced by an untracked driver, "
            "roster, allowlist, capability expectation, or ledger is NOT "
            "admissible evidence -- track it (and remove the ignore rule) "
            "before this run may claim anything." % (kind, str(path), reason)
        )


def assert_evidence_base_tracked(paths_by_kind: dict, repo_root: Optional[Path] = None) -> dict:
    """FR-149 over a whole evidence base: ``{kind: [path, ...]}``. Returns the
    per-path trackedness record for the artifact; raises on the FIRST
    untracked entry, so a run cannot proceed part-way on inadmissible
    evidence."""
    record = {}
    for kind, paths in paths_by_kind.items():
        for path in paths:
            assert_tracked(path, kind=kind, repo_root=repo_root)
            record[str(path)] = {"kind": kind, "tracked": True}
    return record


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
    ledger: "Optional[AssertionLedger]" = None,
    boundary: str = "",
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
    _reject_unsafe_name_shape(name)
    _record(ledger, ASSERTION_NAME_SHAPE, boundary, destination=name)
    assert_name_allowlisted(name, allowlist)
    _record(ledger, ASSERTION_ALLOWLIST, boundary, destination=name,
            allowlist=tuple(allowlist))

    if not source_name:
        raise WriteSafetyError(
            "[FR-015] source_name was omitted or falsy (%r) -- a write-safety "
            "check with no source to compare against is a bypass, not a pass. "
            "FR-015 names 'absent, empty, or otherwise falsy' explicitly: an "
            "empty string must fail here, not slip past a None-only test"
            % (source_name,)
        )
    if name == source_name:
        raise WriteSafetyError(
            "[FR-016] destination %r equals its own assigned source -- refusing" % (name,)
        )
    _record(ledger, ASSERTION_SOURCE_DISTINCT, boundary, destination=name,
            source=source_name)

    if not frozen_sources:
        raise WriteSafetyError(
            "[FR-015] frozen_sources manifest was omitted or empty (%r) -- the "
            "manifest-wide check of FR-016 cannot be skipped. An empty manifest "
            "makes the 'destination is not any source' test vacuously true, "
            "which is precisely the self-disabling guard FR-015 forbids"
            % (frozen_sources,)
        )
    if name in frozen_sources:
        raise WriteSafetyError(
            "[FR-016] destination %r appears in the run's frozen source "
            "manifest -- refusing regardless of the worker's current pairing "
            "(catches a mis-ordered pairing / stale retry, not just today's "
            "assignment)" % (name,)
        )
    _record(ledger, ASSERTION_MANIFEST_WIDE, boundary, destination=name,
            manifest_size=len(frozen_sources))

    root = resolve_projects_root(projects_root)
    dest = (root / name).resolve()
    if dest.parent != root:
        raise WriteSafetyError(
            "[FR-017] resolved destination %r is not a direct child of the "
            "single-authority projects root %r" % (str(dest), str(root))
        )
    _record(ledger, ASSERTION_ROOT_CONTAINMENT, boundary, destination=name,
            resolved=str(dest), root=str(root))
    return dest


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
