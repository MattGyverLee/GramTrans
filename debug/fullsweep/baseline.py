"""Feature 035 -- Group M: BASELINE PROVENANCE AND CONTAINMENT (T020 of
specs/035-fullsweep-fidelity/tasks.md Phase 3 / US4).

Source: spec.md Section M (FR-169..FR-174).

What this module exists to prevent, in the spec's own terms:

  * FR-170 -- a recency-based baseline default silently repointed at a REAL
    project's archive by an archiving step that ran before the sweep. The
    restore would succeed, the destination would be renamed to the
    disposable target's name, and every subsequent fidelity comparison would
    run against a secret clone of a real project. There is therefore NO
    newest-archive fallback anywhere in this module, and the pinned hash is
    a REQUIRED argument, never a default.
  * FR-169/FR-171 -- an archive whose own member paths carry absolute or
    parent-relative components, directing a write outside the destination
    while every NAME assertion passes.
  * FR-172 -- a resumed sweep inferring "this destination is usable" from
    the mere existence of its directory, after a worker was killed mid-
    restore and left rubble.
  * FR-173 -- residue from project N contaminating project N+1's "before"
    state.
  * FR-174 -- a baseline restored under a new name carrying an ABSOLUTE
    linked-files or configuration location pointing at the project it was
    archived from, so additive asset/config writes land in a real project
    where a data-file-only fingerprint can never see them.

This module NEVER calls ``harness.restore.restore_target`` and never imports
``harness.restore.newest_backup``: that helper has a newest-archive glob
default and unconditionally removes ``*.lock``/settings directories for
whatever name it is handed. The restore performed here is its pinned,
contained replacement.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from .safety import (
    WriteSafetyError,
    AssertionLedger,
    assert_restore_boundary,
)


class BaselineError(WriteSafetyError):
    """A baseline provenance or containment violation.

    A subclass of ``WriteSafetyError`` on purpose: FR-175 puts containment
    and provenance trips in the same whole-run-abort class as write safety,
    and every existing call site that already lets ``WriteSafetyError``
    propagate out of the worker therefore handles these correctly too.
    """


#: FR-172: the durable restore evidence file, written INSIDE the destination
#: (it describes that destination's current contents, so it must travel with
#: them) and therefore explicitly added to FR-173's expected file set.
RESTORE_EVIDENCE_NAME = ".gramtrans-035-restore.json"

#: Zip top-level entries that are backup metadata rather than live project
#: content -- same set ``harness/restore.py`` skips, named here so this
#: module has no import dependency on it.
BACKUP_METADATA_TOP_DIRS = frozenset({"BackupSettings"})


# ===========================================================================
# FR-170: the pinned baseline
# ===========================================================================

@dataclass(frozen=True)
class PinnedBaseline:
    """FR-170: a baseline archive identified EXPLICITLY by path and pinned by
    content hash. Both are required; neither has a default."""
    archive: Path
    sha256: str

    def as_dict(self) -> dict:
        return {"archive": str(self.archive), "sha256": self.sha256}


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def pin_baseline(archive_path, sha256: str) -> PinnedBaseline:
    """FR-170: identify a baseline explicitly and verify its content hash.

    Both arguments are REQUIRED. ``sha256`` being absent, empty, or falsy is
    a failure, never a "skip the check" (FR-015's principle, applied to the
    baseline): a run that cannot name and hash its baseline does not start.
    """
    if not archive_path:
        raise BaselineError(
            "[FR-170] no baseline archive was named. The sweep MUST NEVER "
            "select a baseline by recency, by directory scan, or by any other "
            "implicit rule -- there is no newest-archive fallback."
        )
    if not sha256 or not isinstance(sha256, str):
        raise BaselineError(
            "[FR-170] baseline %r was named without a pinned SHA-256 (%r). A "
            "run that cannot hash its baseline does not start."
            % (str(archive_path), sha256)
        )
    expected = sha256.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise BaselineError(
            "[FR-170] pinned baseline hash %r is not a 64-character hex "
            "SHA-256 digest" % (sha256,)
        )
    archive = Path(archive_path)
    if not archive.is_file():
        raise BaselineError(
            "[FR-170] pinned baseline archive does not exist: %r" % (str(archive),)
        )
    actual = sha256_file(archive)
    if actual != expected:
        raise BaselineError(
            "[FR-170] pinned baseline hash MISMATCH for %r: expected %s, "
            "measured %s. Refusing -- the archive on disk is not the archive "
            "this run was authorized to restore from."
            % (str(archive), expected, actual)
        )
    return PinnedBaseline(archive=archive.resolve(), sha256=expected)


# ===========================================================================
# FR-169/FR-171: archive shape and per-item containment
# ===========================================================================

def _is_escaping_member(member: str) -> bool:
    """True when a zip member name carries an ABSOLUTE or PARENT-RELATIVE
    component. Both separator conventions are checked, because a zip written
    on Windows can carry backslashes that ``PurePosixPath`` would treat as an
    ordinary filename character."""
    norm = member.replace("\\", "/")
    if norm.startswith("/") or norm.startswith("//"):
        return True
    if re.match(r"^[A-Za-z]:", norm):          # drive designator
        return True
    parts = [seg for seg in norm.split("/") if seg not in ("", ".")]
    return any(seg == ".." for seg in parts)


def assert_item_contained(dest_root: Path, item_path: Path) -> Path:
    """FR-169: prove, from the item's FULLY RESOLVED destination, that it
    lies beneath the destination project's own fully resolved directory.

    Independent of every NAME check by construction: it resolves the actual
    path this write is about to use. ``Path.resolve()`` is called on both
    sides so a symlink, a junction, or an ``..`` surviving an earlier join
    cannot slip past a lexical prefix comparison.
    """
    root = Path(dest_root).resolve()
    resolved = Path(item_path).resolve()
    if resolved == root:
        raise BaselineError(
            "[FR-169] restore item resolves to the destination root itself "
            "(%r), not to an item beneath it" % (str(resolved),)
        )
    try:
        resolved.relative_to(root)
    except ValueError:
        raise BaselineError(
            "[FR-169] restore item %r resolves OUTSIDE the destination "
            "project directory %r -- aborting before any byte is written"
            % (str(resolved), str(root))
        ) from None
    return resolved


@dataclass(frozen=True)
class BaselineShape:
    """What ``assert_baseline_shape`` proved, recorded for the artifact."""
    top_level_data_file: str
    member_count: int
    members: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        return {"top_level_data_file": self.top_level_data_file,
                "member_count": self.member_count,
                "members": list(self.members)}


def assert_baseline_shape(
    pinned: PinnedBaseline, *, destination_name: str,
    expected_baseline_identity: Optional[str] = None,
) -> BaselineShape:
    """FR-171, evaluated BEFORE the restore removes anything.

    Asserts, in order:
      1. the archive contains EXACTLY ONE top-level data file;
      2. its name corresponds either to ``destination_name`` or to a
         separately declared ``expected_baseline_identity``;
      3. NO member carries an absolute or parent-relative destination.

    A mismatch raises, and every caller in this module evaluates this before
    its first removal -- FR-171's ordering is load-bearing, because the
    destructive steps of a restore include removals whose contents exist in
    no archive.
    """
    if not zipfile.is_zipfile(pinned.archive):
        raise BaselineError(
            "[FR-171] pinned baseline %r is not a valid zip/.fwbackup archive"
            % (str(pinned.archive),)
        )
    with zipfile.ZipFile(pinned.archive) as z:
        members = [m for m in z.namelist() if not m.replace("\\", "/").endswith("/")]

    escaping = sorted(m for m in members if _is_escaping_member(m))
    if escaping:
        raise BaselineError(
            "[FR-171] pinned baseline %r contains %d member(s) with an "
            "absolute or parent-relative destination: %r -- aborting before "
            "the first removal" % (str(pinned.archive), len(escaping), escaping[:10])
        )

    top_level_data = [
        m for m in members
        if "/" not in m.replace("\\", "/") and m.lower().endswith(".fwdata")
    ]
    if len(top_level_data) != 1:
        raise BaselineError(
            "[FR-171] pinned baseline %r must contain EXACTLY ONE top-level "
            "data file; found %d (%r)"
            % (str(pinned.archive), len(top_level_data), sorted(top_level_data))
        )
    archived = top_level_data[0]
    archived_stem = archived[: -len(".fwdata")]
    permitted = {destination_name}
    if expected_baseline_identity:
        permitted.add(expected_baseline_identity)
    if archived_stem not in permitted:
        raise BaselineError(
            "[FR-171] pinned baseline's top-level data file is %r, which "
            "corresponds to neither the declared destination %r nor a "
            "declared expected baseline identity %r. Refusing: an archive of "
            "some OTHER project restored under the disposable target's name "
            "is exactly the secret-clone accident FR-170/FR-171 exist to stop."
            % (archived, destination_name, expected_baseline_identity)
        )
    return BaselineShape(top_level_data_file=archived, member_count=len(members),
                         members=tuple(sorted(members)))


# ===========================================================================
# FR-174: linked-files / configuration location containment
# ===========================================================================

#: Elements in a restored data file that name a location the host will later
#: write assets or configuration into. Read from the RESTORED file, because
#: FR-174's failure mode is a baseline carrying the location of the project
#: it was archived FROM.
LOCATION_ELEMENTS: tuple[str, ...] = ("LinkedFilesRootDir",)


def _extract_declared_locations(fwdata_path: Path, scan_bytes: int = 1 << 20) -> dict:
    """Best-effort read of the declared location elements from the head of a
    data file. Returns ``{element: raw_value}`` for whatever was found.

    Deliberately a HEAD scan rather than a full XML parse: these elements sit
    in the LangProject block near the top, and a full parse of a
    multi-hundred-megabyte file before every restore would be wasteful. A
    value that is not found is reported as ABSENT (see
    ``assert_declared_locations_contained``), never as "contained".
    """
    found: dict = {}
    try:
        with open(fwdata_path, "rb") as fh:
            head = fh.read(scan_bytes)
    except OSError as exc:
        raise BaselineError(
            "[FR-174] could not read the restored data file %r to check its "
            "declared linked-files/configuration locations: %s"
            % (str(fwdata_path), exc)
        ) from exc
    text = head.decode("utf-8", errors="replace")
    for element in LOCATION_ELEMENTS:
        m = re.search(r"<%s>(.*?)</%s>" % (element, element), text, re.DOTALL)
        if m is None:
            m = re.search(r'<%s\b[^>]*\bval\s*=\s*"([^"]*)"' % element, text)
        if m is not None:
            found[element] = m.group(1).strip()
    return found


def assert_declared_locations_contained(
    dest_dir: Path, project_name: str, *, extra_locations: Sequence = (),
) -> dict:
    """FR-174: before ANY action that copies assets or configuration into a
    destination, assert that the destination's resolved linked-files
    location, and the resolved location of any configuration directory the
    sweep writes into, lie beneath that destination project's own directory.

    Returns ``{element: {"declared":..., "resolved":..., "contained": True}}``
    for the artifact. An ABSENT element is recorded as absent and treated as
    "the host default, beneath the project" -- which is what an absent
    element means -- while a PRESENT one pointing elsewhere aborts.
    """
    dest_dir = Path(dest_dir).resolve()
    fwdata = dest_dir / ("%s.fwdata" % project_name)
    if not fwdata.is_file():
        raise BaselineError(
            "[FR-174] cannot check declared locations: %r does not exist"
            % (str(fwdata),)
        )
    record: dict = {}
    declared = _extract_declared_locations(fwdata)
    for element in LOCATION_ELEMENTS:
        raw = declared.get(element)
        if raw in (None, ""):
            record[element] = {"declared": None, "resolved": None,
                               "contained": True, "note": "absent -- host default"}
            continue
        candidate = Path(raw)
        resolved = candidate if candidate.is_absolute() else (dest_dir / candidate)
        assert_item_contained(dest_dir, resolved)
        record[element] = {"declared": raw, "resolved": str(Path(resolved).resolve()),
                           "contained": True}
    for extra in extra_locations:
        assert_item_contained(dest_dir, Path(extra))
        record[str(extra)] = {"declared": str(extra),
                              "resolved": str(Path(extra).resolve()),
                              "contained": True}
    return record


# ===========================================================================
# FR-172/FR-173: restore evidence and post-restore file-set equality
# ===========================================================================

def _relative_file_set(root: Path) -> set:
    out = set()
    for p in Path(root).rglob("*"):
        if p.is_file():
            out.add(str(p.relative_to(root)).replace("\\", "/"))
    return out


def expected_file_set(shape: BaselineShape, project_name: str) -> set:
    """FR-173: the set of files that MUST be present beneath the destination
    after a restore -- the pinned baseline's contents (with the archived data
    file renamed to the destination's own name, and backup-metadata top dirs
    excluded, exactly as the extraction does) PLUS the FR-172 restore
    evidence."""
    expected = set()
    for member in shape.members:
        norm = member.replace("\\", "/")
        top = norm.split("/", 1)[0]
        if top in BACKUP_METADATA_TOP_DIRS:
            continue
        if "/" not in norm and norm.lower().endswith(".fwdata"):
            expected.add("%s.fwdata" % project_name)
        else:
            expected.add(norm)
    expected.add(RESTORE_EVIDENCE_NAME)
    return expected


def write_restore_evidence(
    dest_dir: Path, *, pinned: PinnedBaseline, destination_name: str,
    shape: BaselineShape,
) -> Path:
    """FR-172: durable evidence recording the pinned baseline's content hash,
    the destination name, and the identity of the process that performed the
    restore."""
    payload = {
        "schema_version": 1,
        "destination": destination_name,
        "baseline": pinned.as_dict(),
        "baseline_shape": shape.as_dict(),
        "performed_by": {"pid": os.getpid(), "executable": _executable_name()},
        "performed_at": time.time(),
    }
    path = Path(dest_dir) / RESTORE_EVIDENCE_NAME
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    os.replace(str(tmp), str(path))
    return path


def _executable_name() -> str:
    import sys
    return Path(sys.executable).name


def read_restore_evidence(dest_dir: Path) -> Optional[dict]:
    path = Path(dest_dir) / RESTORE_EVIDENCE_NAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 -- recorded, never silent
        raise BaselineError(
            "[FR-172] restore evidence %r exists but is unreadable/corrupt "
            "(%s) -- treating the destination as rubble, not as usable"
            % (str(path), exc)
        ) from exc


def destination_is_usable(dest_dir: Path, *, pinned: PinnedBaseline,
                          destination_name: str) -> bool:
    """FR-172: a resumed iteration MUST either FIND AND VALIDATE the restore
    evidence, or restore unconditionally.

    Inferring usability from directory existence is forbidden, so this
    returns False for a directory that merely exists. Note the caller
    discipline FR-172 also mandates: recovery is idempotent per project --
    always restore first, never resume mid-transfer -- so this predicate is
    an evidence check, not a permission to skip a restore mid-run.
    """
    evidence = read_restore_evidence(dest_dir)
    if evidence is None:
        return False
    return (evidence.get("destination") == destination_name
            and evidence.get("baseline", {}).get("sha256") == pinned.sha256)


@dataclass
class RestoreResult:
    destination: str
    baseline: dict
    shape: dict
    evidence_path: str
    extracted: int
    residue_delta: dict
    declared_locations: dict

    def as_dict(self) -> dict:
        return {
            "destination": self.destination, "baseline": self.baseline,
            "shape": self.shape, "evidence_path": self.evidence_path,
            "extracted": self.extracted, "residue_delta": self.residue_delta,
            "declared_locations": self.declared_locations,
        }


def restore_from_pinned_baseline(
    destination_name: str,
    *,
    pinned: PinnedBaseline,
    source_name,
    frozen_sources,
    allowlist: Sequence[str],
    projects_root: Optional[str] = None,
    expected_baseline_identity: Optional[str] = None,
    tolerated_residue: Sequence[str] = (),
    ledger: Optional[AssertionLedger] = None,
) -> RestoreResult:
    """The pinned, contained restore. Replaces ``harness.restore_target`` for
    this sweep. Ordering is the requirement, not an implementation detail:

      1. FR-013(a)/FR-023 -- the write-safety choke point, BEFORE any
         directory is created and before any removal;
      2. FR-171 -- archive shape proven, BEFORE the first removal;
      3. FR-169 -- every member's fully resolved destination proven beneath
         the destination directory, BEFORE any byte is written;
      4. the removals, then the extraction;
      5. FR-174 -- declared linked-files/configuration locations proven
         contained, BEFORE anything copies assets or configuration in;
      6. FR-172 -- durable restore evidence;
      7. FR-173 -- post-restore file-set equality, with any tolerated
         residue declared by the caller and the observed delta RECORDED.
    """
    # ---- 1. write safety, before anything exists or is removed -----------
    dest_dir = assert_restore_boundary(
        destination_name, source_name=source_name, frozen_sources=frozen_sources,
        allowlist=allowlist, projects_root=projects_root, ledger=ledger,
    )

    # ---- 2. archive shape, before the first removal ----------------------
    shape = assert_baseline_shape(
        pinned, destination_name=destination_name,
        expected_baseline_identity=expected_baseline_identity,
    )

    # ---- 3. per-item containment, before any byte is written -------------
    planned: list = []
    with zipfile.ZipFile(pinned.archive) as z:
        for member in z.namelist():
            norm = member.replace("\\", "/")
            if norm.endswith("/"):
                continue
            top = norm.split("/", 1)[0]
            if top in BACKUP_METADATA_TOP_DIRS:
                continue
            if "/" not in norm and norm.lower().endswith(".fwdata"):
                target = dest_dir / ("%s.fwdata" % destination_name)
            else:
                target = dest_dir / norm
            assert_item_contained(dest_dir, target)
            planned.append((member, target))

        # ---- 4. removals, then extraction --------------------------------
        dest_dir.mkdir(parents=True, exist_ok=True)
        for lock in dest_dir.glob("*.lock"):
            assert_item_contained(dest_dir, lock)
            lock.unlink()
        old_fwdata = dest_dir / ("%s.fwdata" % destination_name)
        if old_fwdata.exists():
            assert_item_contained(dest_dir, old_fwdata)
            old_fwdata.unlink()
        for sub in ("WritingSystemStore", "ConfigurationSettings", "SharedSettings"):
            d = dest_dir / sub
            if d.is_dir():
                assert_item_contained(dest_dir, d)
                shutil.rmtree(d)

        extracted = 0
        for member, target in planned:
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(member) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            extracted += 1

    fwdata = dest_dir / ("%s.fwdata" % destination_name)
    if not fwdata.is_file():
        raise BaselineError(
            "[FR-171] restore completed but %r is missing -- the pinned "
            "baseline had no top-level data file after extraction "
            "(%d members written)" % (str(fwdata), extracted)
        )

    # ---- 5. FR-174, before anything copies assets/configuration in -------
    declared_locations = assert_declared_locations_contained(dest_dir, destination_name)

    # ---- 6. FR-172 durable evidence --------------------------------------
    evidence_path = write_restore_evidence(
        dest_dir, pinned=pinned, destination_name=destination_name, shape=shape,
    )

    # ---- 7. FR-173 file-set equality -------------------------------------
    residue_delta = assert_post_restore_file_set(
        dest_dir, shape, destination_name, tolerated_residue=tolerated_residue,
    )

    return RestoreResult(
        destination=destination_name, baseline=pinned.as_dict(), shape=shape.as_dict(),
        evidence_path=str(evidence_path), extracted=extracted,
        residue_delta=residue_delta, declared_locations=declared_locations,
    )


def assert_post_restore_file_set(
    dest_dir: Path, shape: BaselineShape, destination_name: str,
    *, tolerated_residue: Sequence[str] = (),
) -> dict:
    """FR-173: the set of files present beneath the destination MUST EQUAL the
    pinned baseline's contents plus the FR-172 restore evidence.

    Residue is tolerated only where the caller DECLARES it, and the observed
    delta is returned for recording in that project's own artifact either
    way -- never ignored. Missing files are never tolerable: they mean the
    restore did not put back what it claimed to.
    """
    expected = expected_file_set(shape, destination_name)
    actual = _relative_file_set(Path(dest_dir))
    tolerated = set(tolerated_residue)
    unexpected = sorted(actual - expected)
    missing = sorted(expected - actual)
    untolerated = sorted(set(unexpected) - tolerated)
    delta = {
        "expected_count": len(expected), "actual_count": len(actual),
        "unexpected": unexpected, "missing": missing,
        "tolerated_residue": sorted(tolerated),
        "untolerated_residue": untolerated,
    }
    if missing or untolerated:
        raise BaselineError(
            "[FR-173] post-restore file set does not equal the pinned "
            "baseline's contents plus the restore evidence. missing=%r "
            "untolerated_residue=%r (tolerated=%r). Residue left in place "
            "lets one project's linked assets and orphaned evidence leak "
            "into the next project's baseline."
            % (missing[:20], untolerated[:20], sorted(tolerated))
        )
    return delta
