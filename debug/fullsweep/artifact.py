"""Feature 035 -- Group K: ARTIFACT AND PROVENANCE. Moved unchanged out of the
``debug/run_fullcopy_sweep.py`` monolith (T006/T009 of
specs/035-fullsweep-fidelity/tasks.md Phase 1).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ARTIFACTS_DIR = _ROOT / "specs" / "035-fullsweep-fidelity" / "artifacts"


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

    # ---- T013 additions (Phase 2 taxonomy spine, FR-138..FR-151/FR-188) ----
    phase_reached: Optional[str] = None                     # FR-150, six-name vocabulary

    # ---- T019/T020/T024 additions (Phase 3 / US4) ----------------------
    assertions: list = field(default_factory=list)          # FR-024: each assertion, per boundary
    assertions_complete: Optional[bool] = None              # FR-013: both boundaries evaluated
    baseline: dict = field(default_factory=dict)            # FR-170: pinned archive + hash
    restore_evidence: dict = field(default_factory=dict)    # FR-172/FR-173 (initial restore)
    restore_evidence_final: dict = field(default_factory=dict)  # FR-172/FR-173 (final restore)
    excluded_categories: list = field(default_factory=list)  # FR-142: explicit, possibly empty
    diagnostic_level: str = ""                              # recorded, never setdefault-ed
    preflight: dict = field(default_factory=dict)           # FR-124/FR-126: capability check
    guards: dict = field(default_factory=dict)              # FR-109/FR-143: all fifteen keys
    verdict: str = ""                                       # machine token, verdict.py
    exit_code: Optional[int] = None                         # verdict.exit_code_for(verdict)

    # ---- T035 additions (Phase 4 / US1, FR-160/FR-161/SC-005) ----------
    #: The engine's own never-silent drop channel (``RunReport.dropped_items``),
    #: per transfer, keyed "first"/"second". FR-161's acceptance criterion is
    #: stated in terms of drop-reason CLASSES and their counts, so a run that
    #: does not record them cannot be compared against the historical numbers
    #: at all -- and the reports were previously discarded the moment the
    #: transfer returned. Never truncated here (FR-144).
    drops: dict = field(default_factory=dict)

    # ---- T045a additions (Phase 5 / US2 wave 3b) ------------------------
    #: FR-093 plane 1: the object-level accounting block, from
    #: ``compare.ObjectAccounting.as_dict()``. Structurally separate from
    #: ``findings`` (the field/link verdict plane) and asserted so by
    #: ``compare.assert_object_plane_only``.
    accounting: dict = field(default_factory=dict)

    #: FR-135: every excluded category WITH its recorded reason.
    #: ``excluded_categories`` above stays a plain list[str] for the artifact
    #: schema; this carries the reason, because "explicit and recorded" is not
    #: satisfied by a bare name.
    excluded_category_records: list = field(default_factory=list)

    #: FR-109 diagnostics: which guard inputs this run actually measured. A
    #: VACUOUS verdict is only actionable if a reader can see WHICH input was
    #: missing, instead of being told that fifteen guards declined to answer.
    guard_inputs_measured: list = field(default_factory=list)

    # ---- T045f additions (Phase 5 / US2 wave 3b): plane 2's home --------
    # FR-093 keeps the two accounting planes structurally separate.
    # ``accounting`` above is plane 1 (object presence/absence) and
    # ``compare.assert_object_plane_only`` REFUSES field-plane keys there.
    # Until now that assertion had nowhere to send them: the field plane was
    # computed (compare.py's T039-T043 rules, coverage.py's report) and then
    # dropped on the floor. These five fields are where it lands instead.

    #: FR-069..FR-084: the field-plane comparison rules' output -- per-class,
    #: per-rule verdict tallies plus the comparison records themselves. A
    #: finding in ``findings`` says WHAT differed; this block says which rule
    #: judged it and how many comparisons that rule actually performed, which
    #: is what separates "clean" from "never looked" (FR-137).
    comparisons: dict = field(default_factory=dict)

    #: FR-085..FR-090: one ``compare.LinkResult.as_dict()`` per classified
    #: reference, in the five-verdict vocabulary and no sixth. Never
    #: truncated here (FR-144) -- truncation is a console-only concern.
    link_findings: list = field(default_factory=list)

    #: FR-189/SC-017: structural depth and per-parent degree. See
    #: ``depth_block``.
    depth: dict = field(default_factory=dict)

    #: FR-136/FR-137: ``coverage.CoverageReport.as_dict()``. The three
    #: buckets stay separately counted and an unmeasured class never reports
    #: the status a measured one does.
    coverage: dict = field(default_factory=dict)

    #: FR-052/FR-066: THIS feature's own field census -- the per-class
    #: engine-omitted property set and its growth since the previous run --
    #: plus a REFERENCE to feature 038's plane-1 census artifact. Never a
    #: second copy of that artifact's rows. See ``census_block``.
    census: dict = field(default_factory=dict)

    # ---- T045a(c) additions: what plane 2 was MEASURED UNDER -------------

    #: FR-071/FR-135: the writing-system mapping this run's transfers used,
    #: and that plane 2's comparison therefore mirrors -- its mode plus the
    #: resolved ``mapped`` / ``to_create`` / ``skip_records`` sets. Recorded
    #: because a comparison is only interpretable against the mapping it was
    #: made under: the same target content is "lost" under one mapping and
    #: "never declared" under another.
    writing_system_mapping: dict = field(default_factory=dict)

    #: What the plane-2 gather could and could not read, per project: the
    #: classes it measured, the ones whose flexicon accessor RAISED, the ones
    #: with no dispatch at all, and the cost (field reads, seconds). A
    #: coverage hole nobody prints is indistinguishable from no hole, and this
    #: is where the two are told apart. ``measured: false`` plus ``error``
    #: means plane 2 did not run at all -- the guards then report
    #: ``not-evaluated``, which is the honest consequence, not a silent zero.
    field_plane: dict = field(default_factory=dict)


def summarize_drops(report) -> dict:
    """T035/FR-161: the drop channel of one transfer, as recorded evidence.

    Returns per-reason counts AND the full record list. The counts are what
    FR-161's acceptance criterion is written against (two named classes at
    exactly zero, a named residual list matching); the records are what makes
    a non-zero count auditable instead of merely a number. Both, because a
    count with no records cannot be checked and records with no count summary
    cannot be compared against the historical figures.

    A report with an EMPTY drop channel and a report that was never asked to do
    the work that produces drops are indistinguishable from the counts alone,
    so ``planned_actions`` and ``planned_skips`` travel with them: zero drops
    out of zero planned actions is not the same measurement as zero drops out
    of many, and FR-161's "exactly zero" is only meaningful in the second case.
    """
    dropped = tuple(getattr(report, "dropped_items", ()) or ())
    by_reason: dict = {}
    records = []
    for rec in dropped:
        reason = getattr(rec, "reason", "") or ""
        by_reason[reason] = by_reason.get(reason, 0) + 1
        records.append({
            "owner_kind": getattr(rec, "owner_kind", None),
            "owner_guid": getattr(rec, "owner_guid", None),
            "owner_label": getattr(rec, "owner_label", None),
            "field_name": getattr(rec, "field_name", None),
            "item_name": getattr(rec, "item_name", None),
            "item_guid": getattr(rec, "item_guid", None),
            "reason": reason,
        })
    per_category = getattr(report, "per_category", {}) or {}
    return {
        "total": len(records),
        "by_reason": dict(sorted(by_reason.items(), key=lambda kv: (-kv[1], kv[0]))),
        "records": records,
        "planned_actions": sum(getattr(r, "added", 0) for r in per_category.values()),
        "planned_skips": len(getattr(report, "skips", ()) or ()),
    }


# ---------------------------------------------------------------------------
# T013: artifact document shape additions -- phase vocabulary, intent
# normalization, the always-written SKIPPED artifact, and the no-truncation
# rule (FR-138..FR-151, FR-188).
# ---------------------------------------------------------------------------

#: FR-146/FR-150: the six-name phase vocabulary, contracts/artifact-schema.md
#: verbatim. Do not rename, recase, reorder, or extend without updating that
#: contract first.
PHASES: tuple[str, ...] = (
    "restore", "transfer_1", "census_1", "transfer_2", "census_2", "restore_final",
)

#: FR-188: the artifact's stored (normalized) intent spellings.
INTENT_BASELINE = "BASELINE"
INTENT_GATE = "GATE"
VALID_INTENTS: tuple[str, ...] = (INTENT_BASELINE, INTENT_GATE)

#: FR-151/FR-188: the status a project that the run never attempted gets,
#: so corpus-level status is always derived from a real artifact document,
#: never a ledger entry with nothing backing it.
STATUS_SKIPPED = "SKIPPED"


def normalize_intent(intent: str) -> str:
    """FR-188: normalize a caller-facing intent spelling (``"baseline"`` /
    ``"gate"``, case-insensitively) to the artifact's stored form
    (``"BASELINE"`` / ``"GATE"``). Raises on anything else -- an artifact's
    intent is never left ambiguous, and a ``BASELINE`` artifact is never
    admissible toward the FR-166 corpus claim, whatever it contains."""
    if not isinstance(intent, str):
        raise ValueError("[FR-188] intent must be a string, got %r" % (intent,))
    token = intent.strip().upper()
    if token not in VALID_INTENTS:
        raise ValueError(
            "[FR-188] intent must be one of %r (case-insensitive), got %r"
            % (VALID_INTENTS, intent)
        )
    return token


def assert_valid_phase(phase: str) -> None:
    """FR-146: every phase-scoped record names one of the six phases,
    verbatim -- never a hand-typed variant."""
    if phase not in PHASES:
        raise ValueError(
            "[FR-146] phase %r is not one of the six-name vocabulary %r" % (phase, PHASES)
        )


def advance_phase(
    artifact: "ProjectArtifact", phase: str, artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR,
) -> Path:
    """FR-146/FR-150: validate ``phase`` against the six-name vocabulary,
    record it as the document's ``phase_reached``, and flush -- so a crash
    mid-run leaves a partial document naming the last phase actually
    reached, never an undifferentiated whole-project failure."""
    assert_valid_phase(phase)
    artifact.phase_reached = phase
    return flush_artifact(artifact, artifacts_dir)


def console_truncate(items: list, max_items: Optional[int] = None) -> tuple[list, int]:
    """FR-105/FR-144: the no-truncation rule. Truncation is legal ONLY for a
    console summary, and only when the omitted count is stated alongside it
    -- the artifact document itself (``flush_artifact``) NEVER truncates a
    list. Callers must pass the FULL, untruncated list into
    ``ProjectArtifact`` fields, and reserve this helper for print
    statements only.

    Returns ``(items_to_print, omitted_count)``.
    """
    if max_items is None or len(items) <= max_items:
        return list(items), 0
    return list(items[:max_items]), len(items) - max_items


def write_skipped_artifact(
    project: str, *, reason: str, run_intent: str,
    artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR,
) -> Path:
    """FR-151/FR-188: a project the run never attempted MUST STILL get a
    written artifact naming it ``SKIPPED``, so corpus-level status
    (ARTIFACT-INTEGRITY, guards.md) is always derived from a real document,
    never a ledger entry with nothing backing it. Carries the normalized
    intent and the fifteen-guard block filled with ``not-evaluated`` (a
    project that never ran cannot have evaluated anything) -- which, per
    guards.md's FR-109 meta-rule, makes the run's verdict ``VACUOUS``
    (exit code 4).
    """
    # Local import: avoids a load-order dependency between the sibling
    # modules T013/T014 add to this package in the same wave.
    from .guards import not_evaluated_guard_block
    from .verdict import exit_code_for

    normalized_intent = normalize_intent(run_intent)
    artifact = ProjectArtifact(
        project=project, run_intent=normalized_intent, revision_pair=revision_pair(),
        dirty_gramtrans=None, coverage_categories=[],
        status=STATUS_SKIPPED, reason=reason,
        started_at=time.time(), finished_at=time.time(),
    )
    artifact.phase_reached = None
    artifact.guards = not_evaluated_guard_block()
    artifact.verdict = "VACUOUS"
    artifact.exit_code = exit_code_for("VACUOUS")
    return flush_artifact(artifact, artifacts_dir)


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
# T045f -- PLANE 2's ARTIFACT HOME
# (FR-052/FR-066, FR-069..FR-090, FR-136/FR-137, FR-145, FR-189)
#
# Contract: specs/035-fullsweep-fidelity/contracts/artifact-schema.md.
#
# The rules that PRODUCE this output are pure functions in compare.py and
# coverage.py, and every one of them already returns a record with an
# ``as_dict()``. What was missing was somewhere on the document to put the
# result -- so the field plane was being computed and discarded, and a run
# could only ever report the object plane. These helpers are the one place
# plane-2 output reaches ``ProjectArtifact``.
#
# FR-093's separation runs in BOTH directions and is asserted in both:
# ``compare.assert_object_plane_only`` keeps field-plane keys out of
# ``accounting``, and ``record_field_plane`` re-asserts it every time it
# writes, so folding a field block into the object block fails at the write
# rather than in a reader's head.
# ===========================================================================

#: The artifact fields that carry plane-2 output. Named as a tuple so the
#: serializability check below cannot drift out of step with the dataclass.
FIELD_PLANE_ARTIFACT_FIELDS: tuple = (
    "comparisons", "link_findings", "depth", "coverage", "census",
)


def assert_artifact_json_serializable(name: str, block) -> None:
    """FR-145: refuse a block ``flush_artifact`` could only write as a repr.

    ``_atomic_write_json`` passes ``default=str``, which is right for a stray
    ``Path`` or ``datetime`` and badly wrong for a record object: a
    ``LinkResult`` stored raw would land in the document as
    ``"LinkResult(verdict='SILENTLY_UNSET', ...)"`` -- a string that LOOKS
    like evidence, cannot be read by any consumer, and fails no test. So the
    strict check happens here, at the point of record, where the caller that
    still holds the object can be told to call ``as_dict()``.
    """
    from .moves import HarnessError
    try:
        json.dumps(block, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise HarnessError(
            "[FR-145] the artifact's %r block is not JSON-serializable (%s: %s). "
            "flush_artifact writes with default=str, so this would be recorded as "
            "a repr string and read downstream as evidence. Store the record's "
            "as_dict(), not the record." % (name, type(exc).__name__, exc)
        ) from exc


def _as_dicts(records, what: str) -> list:
    """Coerce a sequence of plane-2 records to plain dicts, refusing anything
    that is neither. Accepts records (``as_dict()``) and dicts, because both
    call shapes are legitimate; rejects everything else rather than letting
    ``default=str`` stringify it later."""
    from .moves import HarnessError
    out = []
    for rec in records or ():
        if hasattr(rec, "as_dict"):
            out.append(rec.as_dict())
        elif isinstance(rec, dict):
            out.append(dict(rec))
        else:
            raise HarnessError(
                "[FR-145] %s carries a %s, which is neither a record with "
                "as_dict() nor a dict" % (what, type(rec).__name__)
            )
    return out


def depth_block(results) -> dict:
    """FR-189/SC-017: the artifact's ``depth`` block from
    ``compare.StructuralDepthResult`` records.

    Three dispositions are kept apart on purpose, because collapsing any two
    of them is the failure FR-137 names:

    * ``vacuous_classes`` -- the target's maximum depth is BELOW the source's,
      so any per-parent agreement further down was measured over nesting the
      target never reached. Agreement there is not evidence.
    * ``not_evaluated_classes`` -- the corpus itself never nested this class
      deeper than one level, so the run has no depth statement about it at
      all. Distinct from a clean pass, and never reported as one.
    * ``per_parent_degree_findings`` -- a real disagreement, which FAILS.
    """
    max_nesting: dict = {}
    degree_findings: list = []
    vacuous: list = []
    not_evaluated: list = []
    per_class: list = []
    for r in sorted(results or (), key=lambda r: r.class_name):
        per_class.append(r.as_dict())
        max_nesting[r.class_name] = {
            "source": r.source_max_depth, "target": r.target_max_depth,
        }
        for parent_id, src_children, tgt_children in r.degree_mismatches:
            degree_findings.append({
                "class": r.class_name,
                "parent_source_id": parent_id,
                "source_children": src_children,
                "target_children": tgt_children,
            })
        if not r.evaluated:
            not_evaluated.append(r.class_name)
        elif r.target_max_depth < r.source_max_depth:
            vacuous.append(r.class_name)
    return {
        "max_nesting_depth": max_nesting,
        "per_parent_degree_findings": degree_findings,
        "vacuous_classes": vacuous,
        "not_evaluated_classes": not_evaluated,
        "classes_compared": len(per_class),
        "per_class": per_class,
    }


#: What a plane-1 census reference may NOT carry. Named here so the refusal
#: below can say why it is refused rather than silently dropping it.
CENSUS_REFERENCE_FORBIDDEN_KEYS: frozenset = frozenset({"classes", "rows", "per_class"})


def assert_census_is_reference_only(ref: dict) -> None:
    """The 038 cut, asserted: this feature REFERENCES 038's census, it does
    not carry a copy.

    Two censuses of the same run that can disagree is worse than one census,
    because a reader then has to work out which is authoritative -- and the
    copy is the one that goes stale silently. Path plus content hash is the
    whole reference.
    """
    from .moves import HarnessError
    intruders = sorted(CENSUS_REFERENCE_FORBIDDEN_KEYS & set(ref or {}))
    if intruders:
        raise HarnessError(
            "[038 cut] the plane-1 census reference must carry a path and a "
            "content hash, never the census itself; found %r. 038's artifact "
            "is the one authoritative copy of those rows." % (intruders,)
        )


def plane1_census_reference(path) -> dict:
    """A reference to feature 038's plane-1 census artifact: where it is and
    exactly which bytes were read, so a later reader can tell whether the
    census this run was gated against is the one still on disk.

    Never raises for a missing or malformed document. An absent census is a
    fact about the run that belongs ON the artifact -- recorded as
    ``present: false`` with the reason -- not an exception that loses the rest
    of the evidence. Its consequence (a plane-1 input that did not arrive,
    hence a guard that cannot answer) is the guard block's job to report, not
    this function's.
    """
    p = Path(path)
    ref: dict = {
        "path": str(p), "present": False, "content_hash": None,
        "schema_version": None, "census_id": None, "taken_at": None,
        "class_row_count": None, "verdict": None, "error": "",
    }
    try:
        raw = p.read_bytes()
    except OSError as exc:
        ref["error"] = "could not read %s: %s: %s" % (p, type(exc).__name__, exc)
        return ref
    ref["present"] = True
    ref["content_hash"] = "sha256:" + hashlib.sha256(raw).hexdigest()
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        ref["error"] = "%s is not valid JSON: %s" % (p, exc)
        return ref
    if not isinstance(doc, dict):
        ref["error"] = "%s is a %s, not a census document" % (p, type(doc).__name__)
        return ref
    ref["schema_version"] = doc.get("schema_version")
    ref["census_id"] = doc.get("census_id") or doc.get("run_id")
    ref["taken_at"] = doc.get("taken_at")
    ref["verdict"] = doc.get("verdict")
    rows = doc.get("classes")
    if not isinstance(ref["schema_version"], int) or not isinstance(rows, list):
        # The same refusal census_cli.load_artifact makes, for the same
        # reason: pointing confidently at a stranger's JSON is worse than
        # pointing at nothing.
        ref["error"] = (
            "%s has no integer schema_version and/or no `classes` array, so it "
            "is not a census artifact" % p
        )
        return ref
    ref["class_row_count"] = len(rows)
    return ref


def census_block(
    field_census=None, *, omitted_growth=None, cost=None, plane1_reference=None,
) -> dict:
    """The artifact's ``census`` block: FR-052/FR-066's FIELD census, which is
    this feature's own, plus a reference to 038's OBJECT census.

    The two are different measurements and the block keeps them visibly
    different. 038 counts objects; it is count-only and structurally cannot
    see whether a correctly-counted object arrived with its fields intact.
    That question is what ``field_census`` answers and what nothing else in
    either feature measures.

    ``omitted_properties_per_class`` is the recorded decision made concrete:
    the per-class set of properties the engine's own ``GetSyncableProperties``
    surface does not carry, published on EVERY artifact rather than derived on
    demand -- because a coverage gap nobody prints is indistinguishable from
    no gap.
    """
    block: dict = {
        "omitted_properties_per_class": (
            field_census.omitted_by_class() if field_census is not None else {}
        ),
        "omitted_growth_since_previous_run": dict(omitted_growth or {}),
        "cost": dict(cost or {}),
        "field_census": field_census.as_dict() if field_census is not None else {},
        "field_census_measured": field_census is not None,
    }
    ref = dict(plane1_reference or {
        "present": False, "error": "no plane-1 census reference recorded",
    })
    assert_census_is_reference_only(ref)
    block["plane1_reference"] = ref
    return block


def record_field_plane(
    artifact: "ProjectArtifact", *, comparisons=None, link_findings=None,
    depth=None, coverage=None, census=None,
) -> None:
    """The ONE place plane-2 output lands on a ``ProjectArtifact``.

    Every argument is optional and ``None`` means "this run did not measure
    it", which leaves the field at its empty default rather than writing an
    empty block that would read as a measured zero. Passing an explicitly
    empty container is a different statement -- measured, and empty -- and is
    honored as such.

    Re-asserts FR-093 on every write: the object plane must still be free of
    field-plane keys afterwards. Writing plane 2 is exactly the moment someone
    would be tempted to fold a finding into ``accounting``.
    """
    from .compare import assert_object_plane_only

    if comparisons is not None:
        artifact.comparisons = dict(comparisons)
    if link_findings is not None:
        artifact.link_findings = _as_dicts(link_findings, "link_findings")
    if depth is not None:
        artifact.depth = dict(depth)
    if coverage is not None:
        artifact.coverage = dict(coverage)
    if census is not None:
        assert_census_is_reference_only(census.get("plane1_reference") or {})
        artifact.census = dict(census)

    for name in FIELD_PLANE_ARTIFACT_FIELDS:
        assert_artifact_json_serializable(name, getattr(artifact, name))
    assert_object_plane_only(artifact.accounting)
