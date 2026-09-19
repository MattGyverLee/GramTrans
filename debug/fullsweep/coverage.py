"""Feature 035 -- Group J: THE COVERAGE FLOOR (T044 of
specs/035-fullsweep-fidelity/tasks.md Phase 5, Wave 3).

Source: spec.md FR-133..FR-137, research D-07, data-model.md section 10
(``CoverageFloor``), and the artifact ``coverage`` block of
contracts/artifact-schema.md.

WHAT THIS MODULE EXISTS TO PREVENT
----------------------------------
FR-137 names the defect verbatim: "we compared zero appendices and found zero
mismatches" reading as a pass. Every other module here measures things; this one
measures the SHAPE OF WHAT WAS NEVER MEASURED, and makes that shape loud,
countable, and permanent.

The mechanism is an intersection, not an assertion. A git-tracked floor
(``contracts/coverage-floor.json``) enumerates every in-scope class. A run
intersects it with the MEASURED corpus survey. A class the survey found zero
instances of corpus-wide lands in ``never_attempted``, reports
``NOT-EVALUATED``, and its guards report ``not-evaluated`` -- which FR-109 then
turns into ``VACUOUS`` for any run that claimed that class was clean.

THREE DISCIPLINES THAT LOOK LIKE PARANOIA AND ARE NOT
-----------------------------------------------------
1. ``survey=None`` makes EVERY class ``never_attempted``, not zero classes.
   An unmeasured corpus is not a corpus with nothing in it. This mirrors
   ``guards.RunContext``'s rule that a ``None`` input yields ``not-evaluated``
   rather than a cheerful zero.

2. A class in ``never_attempted`` can NEVER also be in ``attempted_and_clean``,
   even when its findings count is zero -- FR-136's two buckets are separately
   counted and are never collapsed into one zero-mismatch figure.

3. Allowlisting a floor-absent class is REFUSED, not merely discouraged
   (``assert_not_allowlistable``). Research D-07: the allowlist is the wrong
   instrument because an allowlist entry expires (FR-118) and is capped
   (FR-122), whereas a structural coverage gap does neither.

WHY THE ABSENCES ARE MEASURED RATHER THAN LISTED BY HAND
--------------------------------------------------------
``scan_class_presence`` reads each project's ``.fwdata`` as a text stream and
counts ``<rt class="X">`` rows. It never opens a project through LCM, never
takes a lock, and never writes -- so it is admissible under the Group B
read-only discipline without re-implementing ``prescan_type_coverage``'s
project-opening rules. The floor shipped in ``contracts/`` was produced by this
function; ``class-presence-survey.md`` records the run.

That measurement corrected the recorded coverage limit. Research D-07 says
"appendix, stratum, and one phonological-rule subclass"; the scan names the
third as ``PhSegmentRule``, and shows the sibling one would have guessed --
``PhMetathesisRule`` -- is PRESENT (4 instances across 4 projects).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

from .moves import HarnessError

_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACTS_DIR = _ROOT / "specs" / "035-fullsweep-fidelity" / "contracts"
COVERAGE_FLOOR_NAME = "coverage-floor.json"

SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# FR-136: four buckets, separately counted, NEVER collapsed
# ---------------------------------------------------------------------------

BUCKET_ATTEMPTED_AND_CLEAN = "attempted_and_clean"
BUCKET_ATTEMPTED_WITH_FINDINGS = "attempted_with_findings"
BUCKET_NEVER_ATTEMPTED = "never_attempted"
BUCKET_REACHABLE_ONLY_THROUGH_EXCLUDED = "reachable_only_through_excluded"

COVERAGE_BUCKETS: tuple[str, ...] = (
    BUCKET_ATTEMPTED_AND_CLEAN,
    BUCKET_ATTEMPTED_WITH_FINDINGS,
    BUCKET_NEVER_ATTEMPTED,
    BUCKET_REACHABLE_ONLY_THROUGH_EXCLUDED,
)

#: The two buckets that are NOT a measurement of anything. A class in either
#: reports ``NOT-EVALUATED`` and its guards report ``not-evaluated``.
UNMEASURED_BUCKETS: frozenset = frozenset(
    {BUCKET_NEVER_ATTEMPTED, BUCKET_REACHABLE_ONLY_THROUGH_EXCLUDED}
)

#: The per-class status token. Deliberately the same spelling
#: ``compare.DEPTH_NOT_EVALUATED`` uses, so one grep finds every place the
#: sweep admits it could not look.
STATUS_NOT_EVALUATED = "NOT-EVALUATED"
STATUS_CLEAN = "CLEAN"
STATUS_DIVERGED = "DIVERGED"

#: The per-class guard token, matching ``guards._VALID_GUARD_RESULTS``.
GUARDS_NOT_EVALUATED = "not-evaluated"
GUARDS_PASS = "pass"
GUARDS_FAIL = "fail"

# ---------------------------------------------------------------------------
# Reasons. A ``never_attempted`` entry always names WHY, per artifact-schema.md
# ("never_attempted": [{ "class": "...", "reason": "absent-corpus-wide" }]).
# ---------------------------------------------------------------------------

REASON_ABSENT_CORPUS_WIDE = "absent-corpus-wide"
REASON_SURVEY_NOT_MEASURED = "corpus-survey-not-measured"
REASON_NOT_IN_SURVEY = "class-missing-from-corpus-survey"
REASON_REACHABLE_ONLY_THROUGH_EXCLUDED = "reachable-only-through-excluded-category"
REASON_PRESENT_BUT_NEVER_COMPARED = "present-corpus-wide-but-zero-comparisons-performed"

#: FR-132: a pinned expectation the measurement contradicts is a finding, never
#: a silent tolerance. Recorded, and the class stays NOT-EVALUATED until the
#: floor file is deliberately updated.
CONTRADICTION_ABSENT_CLASS_NOW_PRESENT = "floor-says-absent-but-survey-found-instances"
CONTRADICTION_CLASS_NOT_ON_FLOOR = "survey-found-a-class-the-floor-does-not-enumerate"


class CoverageFloorError(HarnessError):
    """The floor contract itself is malformed or self-contradictory."""


class CoverageAllowlistRefused(HarnessError):
    """FR-133..FR-137 / research D-07: a structural coverage gap is not
    allowlistable. Raised rather than returned, because the caller asked for
    something the contract forbids."""


# ---------------------------------------------------------------------------
# The tracked floor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AbsentClass:
    """One MEASURED corpus-wide absence, with the evidence that established it."""

    class_name: str
    reason: str = REASON_ABSENT_CORPUS_WIDE
    detail: str = ""
    measured: Mapping = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "class": self.class_name,
            "reason": self.reason,
            "detail": self.detail,
            "measured": dict(self.measured),
        }


@dataclass(frozen=True)
class CoverageFloor:
    """``contracts/coverage-floor.json``, parsed.

    ``in_scope_classes`` is the roster the run intersects the survey with.
    ``excluded_not_measurable`` holds classes deliberately kept OFF that roster
    with a recorded reason -- today the two abstract LCM bases, which have no
    factory and therefore cannot have an instance in any project. Keeping them
    off the roster is not the same as omitting them: an unexplained omission
    would be exactly the invisible gap this module exists to prevent, so the
    reason travels in the contract.
    """

    schema_version: int
    in_scope_classes: tuple
    known_absent_corpus_wide: tuple  # tuple[AbsentClass, ...]
    excluded_not_measurable: Mapping = field(default_factory=dict)
    path: Optional[Path] = None

    @property
    def known_absent_names(self) -> frozenset:
        return frozenset(a.class_name for a in self.known_absent_corpus_wide)

    def absent_entry(self, class_name: str) -> Optional[AbsentClass]:
        for a in self.known_absent_corpus_wide:
            if a.class_name == class_name:
                return a
        return None

    def assert_not_allowlistable(self, class_name: str) -> None:
        """FR-133..FR-137 + research D-07. A class that is absent corpus-wide is
        a STRUCTURAL coverage gap; the loss allowlist expires (FR-118) and is
        capped (FR-122), so it is the wrong instrument and the request is
        refused outright."""
        if class_name in self.known_absent_names:
            entry = self.absent_entry(class_name)
            raise CoverageAllowlistRefused(
                "[FR-137] %r is absent corpus-wide (%s) and MUST report %s. A "
                "structural coverage gap does not expire, so it is not "
                "allowlistable: an allowlist entry would expire (FR-118) and "
                "count against the cap (FR-122) while the gap remained. Close "
                "the gap by adding a project that carries the class, or leave "
                "it NOT-EVALUATED."
                % (class_name, entry.detail or entry.reason, STATUS_NOT_EVALUATED)
            )

    def as_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "in_scope_classes": list(self.in_scope_classes),
            "excluded_not_measurable": [
                {"class": c, "reason": r} for c, r in sorted(self.excluded_not_measurable.items())
            ],
            "known_absent_corpus_wide": [a.as_dict() for a in self.known_absent_corpus_wide],
        }


def load_coverage_floor(path: Optional[Path] = None) -> CoverageFloor:
    """Read and VALIDATE the tracked floor.

    An empty roster raises. The floor is the only thing standing between a
    never-attempted class and a silent zero, so a floor that enumerates nothing
    is a harness defect, not a permissive default.
    """
    p = Path(path) if path is not None else (DEFAULT_CONTRACTS_DIR / COVERAGE_FLOOR_NAME)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CoverageFloorError(
            "[FR-136] the coverage floor %s does not exist. Without it no run can "
            "distinguish \"attempted and clean\" from \"never attempted\"." % p
        ) from exc
    except json.JSONDecodeError as exc:
        raise CoverageFloorError("[FR-136] the coverage floor %s is not valid JSON: %s" % (p, exc)) from exc

    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        raise CoverageFloorError(
            "[FR-136] coverage floor %s declares schema_version %r; this reader "
            "implements %r. A silently-read newer contract is how a coverage gap "
            "becomes invisible." % (p, version, SCHEMA_VERSION)
        )

    in_scope = tuple(raw.get("in_scope_classes") or ())
    if not in_scope:
        raise CoverageFloorError(
            "[FR-136] coverage floor %s enumerates ZERO in-scope classes. An empty "
            "floor makes every absence invisible, which is the defect FR-137 names." % p
        )
    dupes = sorted({c for c in in_scope if list(in_scope).count(c) > 1})
    if dupes:
        raise CoverageFloorError(
            "[FR-136] coverage floor %s lists %r more than once" % (p, dupes)
        )

    excluded = {}
    for row in raw.get("excluded_not_measurable") or ():
        name, reason = row.get("class"), (row.get("reason") or "").strip()
        if not name:
            raise CoverageFloorError("[FR-136] an excluded_not_measurable row has no class name")
        if not reason:
            raise CoverageFloorError(
                "[FR-136] %r is excluded from the in-scope roster with no recorded "
                "reason. An unexplained omission is an invisible coverage gap." % name
            )
        excluded[name] = reason

    absent = []
    for row in raw.get("known_absent_corpus_wide") or ():
        name = row.get("class")
        if not name:
            raise CoverageFloorError("[FR-136] a known_absent_corpus_wide row has no class name")
        absent.append(AbsentClass(
            class_name=name,
            reason=row.get("reason") or REASON_ABSENT_CORPUS_WIDE,
            detail=row.get("detail") or "",
            measured=row.get("measured") or {},
        ))

    floor = CoverageFloor(
        schema_version=version, in_scope_classes=in_scope,
        known_absent_corpus_wide=tuple(absent), excluded_not_measurable=excluded, path=p,
    )

    # Self-consistency: an absence recorded for a class the roster does not
    # carry is a statement about nothing.
    stray = sorted(floor.known_absent_names - set(in_scope))
    if stray:
        raise CoverageFloorError(
            "[FR-136] coverage floor %s records %r as absent corpus-wide but does "
            "not list them among in_scope_classes -- an absence outside the roster "
            "is never intersected and therefore never reported" % (p, stray)
        )
    overlap = sorted(set(in_scope) & set(excluded))
    if overlap:
        raise CoverageFloorError(
            "[FR-136] coverage floor %s lists %r as BOTH in-scope and "
            "not-measurable" % (p, overlap)
        )
    return floor


# ---------------------------------------------------------------------------
# The measured survey (read-only, LCM-free)
# ---------------------------------------------------------------------------

#: One serialized LCM object row in a ``.fwdata`` file.
_RT_ROW = re.compile(rb'<rt\s+class="([A-Za-z0-9]+)"')

#: The disposable target pool, refused as a survey input for the same reason
#: ``corpus.py`` refuses it as a source (FR-002): its contents are this
#: harness's own writes, not corpus evidence.
_TARGET_POOL = re.compile(r"Target[0-9]*")


def scan_class_presence(
    projects_root: Path,
    *,
    classes: Optional[Iterable[str]] = None,
    projects: Optional[Iterable[str]] = None,
) -> dict:
    """Count ``<rt class="X">`` rows per class across every project on disk.

    READ-ONLY BY CONSTRUCTION: opens each ``.fwdata`` as a binary text stream,
    never through LCM, never taking a lock, never writing. That is what makes it
    admissible under Group B without duplicating ``prescan_type_coverage``'s
    project-opening discipline -- it does not open a project at all.

    Line-oriented on purpose: a chunked read can split ``<rt class="...` across
    a buffer boundary and undercount, and an undercount here manufactures a
    corpus-wide absence out of nothing.

    Returns ``{"projects_scanned": int, "skipped": [...],
    "instances": {class: n}, "projects_with": {class: n}}``. A class in
    ``classes`` with no row at all is present in ``instances`` with 0, so the
    caller never has to distinguish "absent" from "not asked about".

    ``projects`` (T045b) narrows the scan to the named projects. Without it
    this function aggregates CORPUS-WIDE, which is the right shape for the
    coverage survey it was written for and the wrong one for FR-098: "is this
    class present in the SOURCE of this transfer" cannot be answered by a
    count that summed eighty-four other projects into it. A named project the
    root does not contain is reported in ``missing`` rather than silently
    contributing nothing -- an absence that is really a typo must not read as
    a corroborated empty.

    The ``Target[0-9]*`` refusal still applies and still takes precedence: the
    disposable pool's contents are this harness's own writes, so they are
    never corpus evidence, however explicitly they are asked for.
    """
    root = Path(projects_root)
    wanted = set(classes) if classes is not None else None
    only = set(projects) if projects is not None else None
    instances: dict = {c: 0 for c in (wanted or ())}
    projects_with: dict = {c: 0 for c in (wanted or ())}
    scanned: list = []
    skipped: list = []

    for fwdata in sorted(root.glob("*/*.fwdata")):
        project = fwdata.parent.name
        if _TARGET_POOL.fullmatch(project):
            skipped.append(project)
            continue
        if only is not None and project not in only:
            continue
        scanned.append(project)
        here: dict = {}
        with fwdata.open("rb") as fh:
            for line in fh:
                m = _RT_ROW.search(line)
                if m is None:
                    continue
                cls = m.group(1).decode("ascii")
                if wanted is not None and cls not in wanted:
                    continue
                here[cls] = here.get(cls, 0) + 1
        for cls, n in here.items():
            instances[cls] = instances.get(cls, 0) + n
            projects_with[cls] = projects_with.get(cls, 0) + 1

    return {
        "projects_scanned": len(scanned),
        "projects": sorted(scanned),
        "skipped": sorted(skipped),
        # Named but not found on disk. Empty unless ``projects`` was given.
        # A caller asking about a project that is not there gets told so,
        # because a corroborating count of zero from a project that was never
        # opened is not a corroboration.
        "missing": sorted(only - set(scanned) - set(skipped)) if only else [],
        "instances": instances,
        "projects_with": projects_with,
    }


# ---------------------------------------------------------------------------
# The intersection
# ---------------------------------------------------------------------------


@dataclass
class ClassCoverage:
    """One in-scope class's coverage disposition for one run."""

    class_name: str
    bucket: str
    status: str
    guards: str
    reason: str = ""
    source_instances: Optional[int] = None
    comparisons_performed: Optional[int] = None
    findings: int = 0

    def __post_init__(self) -> None:
        if self.bucket not in COVERAGE_BUCKETS:
            raise CoverageFloorError(
                "[FR-136] %r is not one of the coverage buckets %r"
                % (self.bucket, list(COVERAGE_BUCKETS))
            )
        if self.bucket in UNMEASURED_BUCKETS:
            # Discipline 2, asserted rather than trusted: an unmeasured bucket
            # whose status said CLEAN is precisely FR-137's named defect.
            if self.status != STATUS_NOT_EVALUATED or self.guards != GUARDS_NOT_EVALUATED:
                raise CoverageFloorError(
                    "[FR-136/FR-137] %s is in the unmeasured bucket %r but reports "
                    "status=%r guards=%r; an unmeasured class MUST report %r / %r"
                    % (self.class_name, self.bucket, self.status, self.guards,
                       STATUS_NOT_EVALUATED, GUARDS_NOT_EVALUATED)
                )
            if not self.reason:
                raise CoverageFloorError(
                    "[FR-136] %s is unmeasured with no recorded reason" % self.class_name
                )

    @property
    def evaluated(self) -> bool:
        return self.bucket not in UNMEASURED_BUCKETS

    def as_dict(self) -> dict:
        return {
            "class": self.class_name,
            "bucket": self.bucket,
            "status": self.status,
            "guards": self.guards,
            "reason": self.reason,
            "source_instances": self.source_instances,
            "comparisons_performed": self.comparisons_performed,
            "findings": self.findings,
        }


@dataclass
class CoverageReport:
    """The artifact's ``coverage`` block, plus the contradictions FR-132 forbids
    tolerating silently."""

    project: str = ""
    classes: tuple = ()  # tuple[ClassCoverage, ...]
    contradictions: tuple = ()
    survey_measured: bool = False
    floor_path: Optional[str] = None

    def bucket(self, name: str) -> tuple:
        if name not in COVERAGE_BUCKETS:
            raise CoverageFloorError("[FR-136] unknown coverage bucket %r" % (name,))
        return tuple(c for c in self.classes if c.bucket == name)

    def counts(self) -> dict:
        """FR-136: separately counted, one key per bucket, never summed into a
        single zero-mismatch figure."""
        out = {b: 0 for b in COVERAGE_BUCKETS}
        for c in self.classes:
            out[c.bucket] += 1
        return out

    @property
    def not_evaluated(self) -> tuple:
        return tuple(c for c in self.classes if not c.evaluated)

    @property
    def reports_clean(self) -> bool:
        """False whenever ANY in-scope class went unmeasured.

        This is the one-line answer to FR-137: a reduced-coverage run never
        reports the same success status as a full-coverage run, and no later
        change may "fix" this by making it return True with a gap open.
        """
        return bool(self.classes) and not self.not_evaluated and not self.contradictions

    def status_for(self, class_name: str) -> str:
        for c in self.classes:
            if c.class_name == class_name:
                return c.status
        raise CoverageFloorError(
            "[FR-136] %r is not on the coverage floor, so this run has no coverage "
            "statement about it at all" % (class_name,)
        )

    def assert_no_unmeasured_class_reports_clean(self) -> None:
        """FR-136/FR-137 re-asserted over the assembled report, not just per
        class -- the same belt-and-braces shape ``guards.not_evaluated_guard_block``
        uses, because this invariant is the whole point of the module."""
        clean_names = {c.class_name for c in self.bucket(BUCKET_ATTEMPTED_AND_CLEAN)}
        leaked = sorted(clean_names & {c.class_name for c in self.not_evaluated})
        if leaked:
            raise CoverageFloorError(
                "[FR-137] %r appear in BOTH attempted_and_clean and an unmeasured "
                "bucket. \"Zero mismatches observed\" is not \"passed\"." % (leaked,)
            )

    def as_dict(self) -> dict:
        """The artifact ``coverage`` block of contracts/artifact-schema.md."""
        self.assert_no_unmeasured_class_reports_clean()
        return {
            "project": self.project,
            "floor": self.floor_path,
            "survey_measured": self.survey_measured,
            "counts": self.counts(),
            "reports_clean": self.reports_clean,
            BUCKET_ATTEMPTED_AND_CLEAN: [c.class_name for c in self.bucket(BUCKET_ATTEMPTED_AND_CLEAN)],
            BUCKET_ATTEMPTED_WITH_FINDINGS: [
                c.class_name for c in self.bucket(BUCKET_ATTEMPTED_WITH_FINDINGS)
            ],
            BUCKET_NEVER_ATTEMPTED: [
                {"class": c.class_name, "reason": c.reason}
                for c in self.bucket(BUCKET_NEVER_ATTEMPTED)
            ],
            BUCKET_REACHABLE_ONLY_THROUGH_EXCLUDED: [
                {"class": c.class_name, "reason": c.reason}
                for c in self.bucket(BUCKET_REACHABLE_ONLY_THROUGH_EXCLUDED)
            ],
            "contradictions": [dict(x) for x in self.contradictions],
            "per_class": [c.as_dict() for c in self.classes],
        }


def classify_coverage(
    floor: CoverageFloor,
    *,
    survey: Optional[Mapping] = None,
    comparisons: Optional[Mapping] = None,
    findings_by_class: Optional[Mapping] = None,
    reachable_only_through_excluded: Sequence[str] = (),
    project: str = "",
) -> CoverageReport:
    """Intersect the tracked floor with the MEASURED survey (FR-133..FR-137).

    ``survey``: ``{class_name: instance_count}`` corpus-wide, or the richer dict
    ``scan_class_presence`` returns (its ``instances`` key is used). **None**
    means the survey was not measured -- every class then lands in
    ``never_attempted``, because an unmeasured corpus is not an empty one.

    ``comparisons``: ``{class_name: comparisons_performed}`` for this run. A
    class the survey found instances of but which this run compared zero times
    is NOT clean: it is ``never_attempted`` with
    ``present-corpus-wide-but-zero-comparisons-performed``. Omit the mapping
    entirely (None) and no class is demoted on this ground -- the caller has
    said nothing about comparisons, so nothing is inferred from silence.

    ``findings_by_class``: ``{class_name: n}``; a measured class with findings
    lands in ``attempted_with_findings``, never in ``attempted_and_clean``.

    ``reachable_only_through_excluded``: FR-137's second clause -- classes whose
    subject matter is reachable only through a category this run excluded. Also
    ``NOT-EVALUATED``, in their own bucket so the two causes stay legible.
    """
    instances: Optional[Mapping]
    if survey is None:
        instances = None
    elif "instances" in survey and isinstance(survey.get("instances"), Mapping):
        instances = survey["instances"]
    else:
        instances = survey

    excluded_reach = set(reachable_only_through_excluded)
    unknown_reach = sorted(excluded_reach - set(floor.in_scope_classes))
    if unknown_reach:
        raise CoverageFloorError(
            "[FR-137] %r were reported as reachable-only-through-an-excluded-category "
            "but are not on the coverage floor" % (unknown_reach,)
        )

    contradictions: list = []
    rows: list = []

    for cls in floor.in_scope_classes:
        absent_pin = floor.absent_entry(cls)
        n = None if instances is None else int(instances.get(cls, 0) or 0)

        # FR-132: the pinned absence and the measurement disagree. Recorded,
        # and the class STAYS not-evaluated until the floor is deliberately
        # updated -- "never silently tolerated" cuts both ways.
        if absent_pin is not None and n:
            contradictions.append({
                "class": cls,
                "kind": CONTRADICTION_ABSENT_CLASS_NOW_PRESENT,
                "floor_says": REASON_ABSENT_CORPUS_WIDE,
                "survey_found": n,
                "action": "update contracts/%s deliberately (FR-132); until then this "
                          "class stays %s" % (COVERAGE_FLOOR_NAME, STATUS_NOT_EVALUATED),
            })

        if cls in excluded_reach:
            rows.append(ClassCoverage(
                class_name=cls, bucket=BUCKET_REACHABLE_ONLY_THROUGH_EXCLUDED,
                status=STATUS_NOT_EVALUATED, guards=GUARDS_NOT_EVALUATED,
                reason=REASON_REACHABLE_ONLY_THROUGH_EXCLUDED,
                source_instances=n,
            ))
            continue

        if instances is None:
            rows.append(ClassCoverage(
                class_name=cls, bucket=BUCKET_NEVER_ATTEMPTED,
                status=STATUS_NOT_EVALUATED, guards=GUARDS_NOT_EVALUATED,
                reason=REASON_SURVEY_NOT_MEASURED, source_instances=None,
            ))
            continue

        if absent_pin is not None or n == 0:
            reason = REASON_ABSENT_CORPUS_WIDE if absent_pin is not None else (
                REASON_ABSENT_CORPUS_WIDE if cls in instances else REASON_NOT_IN_SURVEY
            )
            rows.append(ClassCoverage(
                class_name=cls, bucket=BUCKET_NEVER_ATTEMPTED,
                status=STATUS_NOT_EVALUATED, guards=GUARDS_NOT_EVALUATED,
                reason=reason, source_instances=n,
            ))
            continue

        performed = None if comparisons is None else int(comparisons.get(cls, 0) or 0)
        if performed is not None and performed < 1:
            rows.append(ClassCoverage(
                class_name=cls, bucket=BUCKET_NEVER_ATTEMPTED,
                status=STATUS_NOT_EVALUATED, guards=GUARDS_NOT_EVALUATED,
                reason=REASON_PRESENT_BUT_NEVER_COMPARED,
                source_instances=n, comparisons_performed=0,
            ))
            continue

        found = 0 if findings_by_class is None else int(findings_by_class.get(cls, 0) or 0)
        rows.append(ClassCoverage(
            class_name=cls,
            bucket=BUCKET_ATTEMPTED_WITH_FINDINGS if found else BUCKET_ATTEMPTED_AND_CLEAN,
            status=STATUS_DIVERGED if found else STATUS_CLEAN,
            guards=GUARDS_FAIL if found else GUARDS_PASS,
            reason="", source_instances=n, comparisons_performed=performed, findings=found,
        ))

    if instances is not None:
        for cls in sorted(set(instances) - set(floor.in_scope_classes)
                          - set(floor.excluded_not_measurable)):
            if not instances.get(cls):
                continue
            contradictions.append({
                "class": cls,
                "kind": CONTRADICTION_CLASS_NOT_ON_FLOOR,
                "survey_found": int(instances[cls]),
                "action": "add it to contracts/%s in_scope_classes, or record why it is "
                          "not measurable" % COVERAGE_FLOOR_NAME,
            })

    report = CoverageReport(
        project=project, classes=tuple(rows), contradictions=tuple(contradictions),
        survey_measured=instances is not None,
        floor_path=str(floor.path) if floor.path else None,
    )
    report.assert_no_unmeasured_class_reports_clean()
    return report


def assert_allowlist_respects_floor(
    floor: CoverageFloor, allowlisted_classes: Iterable[str]
) -> None:
    """Refuse an allowlist that tries to excuse a structural coverage gap.

    Called with whatever class names the loss allowlist names, so the refusal
    happens at load time rather than after a run has already reported a
    reduced-coverage pass as a pass.
    """
    for cls in allowlisted_classes:
        floor.assert_not_allowlistable(cls)


# ===========================================================================
# T045e -- THE CLASS -> CATEGORY JOIN
# ===========================================================================
#
# ``guards.guard_comparisons_performed`` keys its counters on CATEGORY. Every
# plane-2 surface in this package -- ``census_fields``, ``classify_coverage``,
# ``coverage-floor.json``'s ``in_scope_classes`` -- keys on CLASS. Without a
# join the category-keyed guard input cannot be produced at all, which is why
# COMPARISONS-PERFORMED and CATEGORY-COVERAGE have been reporting
# ``not-evaluated`` and sinking every run to VACUOUS under FR-109.
#
# The join is a TRACKED CONTRACT, not a dict in this file, and it is SHARED
# with feature 038's per-class census: both instruments read
# ``contracts/class-category-map.json``. A second copy living here would be a
# mapping that can disagree with 038's without either instrument being able to
# notice -- precisely the class of silent divergence this feature exists to
# catch.
#
# TWO TRAPS, BOTH LIVE
# --------------------
# 1. ``classify_coverage``'s own ``comparisons`` parameter is
#    ``{class_name: int}``. The guard's ``ctx.comparisons`` is
#    ``{category: {source_objects, comparisons_performed, objects_compared}}``.
#    They are different objects that happen to share a name. Wiring one into
#    the other type-checks, runs, and produces a confidently wrong answer.
#    ``project_comparisons_to_categories`` is the ONLY sanctioned bridge, and
#    it takes class-keyed input and returns category-keyed output.
#
# 2. The projection REPLICATES a multi-category class into each of its
#    categories; it does not partition. ``LexEntry`` is created under both
#    AFFIXES and STEMS, so both are credited with it. That is right for the
#    question COMPARISONS-PERFORMED asks ("did this category compare
#    anything?") and WRONG for any total -- summing the projection
#    double-counts. The returned provenance names every replicated class so a
#    later reader cannot mistake the one for the other.
#
# WHAT AN EMPTY ``categories`` LIST MEANS
# ---------------------------------------
# Ten in-scope classes belong to no category: the post-pass classes
# (``LexReference``, ``ReversalIndex``, ``ReversalIndexEntry``), the reference
# CREATE-arm classes (``CmPossibility``, ``CmAnthroItem``, ``MoMorphType``),
# and the never-created referenced-only classes (``LexRefType``,
# ``LexAppendix``, ``PhBdryMarker``, ``PunctuationForm``). Each carries a
# non-null ``unmapped_reason``, and the projection returns them as
# ``unattributable`` rather than dropping them, so the caller reports them
# not-evaluated at the category plane instead of letting them vanish into a
# clean tally. Nine categories symmetrically carry no in-scope class; for them
# zero comparisons is CORRECT, and reporting them as measured would be the
# FR-137 defect in the other direction.

CLASS_CATEGORY_MAP_NAME = "class-category-map.json"

#: The create arms that are not a ``GrammarCategory``. A class reachable only
#: through one of these has no category to be credited to.
CREATE_ARM_REFERENCE = "reference-create-arm"

#: ``category_dispatch`` values. ``phase0-unused`` is the one that means a full
#: run never dispatches the category at all.
DISPATCH_LEAF = "leaf"
DISPATCH_DEDICATED_HOOK = "dedicated-hook"
DISPATCH_PRE_PASS = "pre-pass"
DISPATCH_PHASE0_UNUSED = "phase0-unused"

_VALID_DISPATCH = frozenset(
    {DISPATCH_LEAF, DISPATCH_DEDICATED_HOOK, DISPATCH_PRE_PASS, DISPATCH_PHASE0_UNUSED}
)

#: Sentinel distinguishing "caller did not discriminate by feature system" from
#: "caller asked for the entry whose feature system is None". ``None`` is a
#: REAL key here -- 67 of the 71 entries carry it -- so it cannot double as
#: "unspecified".
_ANY_FEATURE_SYSTEM = object()


class ClassCategoryMapError(HarnessError):
    """The class -> category contract is malformed, incomplete against the
    coverage floor, or was asked a question it has no recorded answer to."""


@dataclass(frozen=True)
class ClassCategoryEntry:
    """One row of ``class-category-map.json``.

    ``owning_feature_system`` is the same discriminator feature 038's census
    ``classRow`` carries, and for the same reason: a FieldWorks project has two
    feature systems, both own ``FsFeatStrucType`` and ``FsClosedFeature``, and
    the two halves map to DIFFERENT categories
    (``feature_struct_types`` / ``phon_feat_types`` and
    ``inflection_features`` / ``phonological_features``). Summing them into one
    row would let a shortfall in one system be masked by a surplus in the
    other. Keying on the same pair both instruments key on is what keeps the
    join single-valued.
    """

    class_name: str
    owning_feature_system: Optional[str]
    categories: tuple
    also_created_via: tuple
    unmapped_reason: Optional[str]
    inventory_tables: tuple
    qualifier: Optional[str]

    @property
    def mapped(self) -> bool:
        return bool(self.categories)

    def as_dict(self) -> dict:
        return {
            "class": self.class_name,
            "owning_feature_system": self.owning_feature_system,
            "categories": list(self.categories),
            "also_created_via": list(self.also_created_via),
            "unmapped_reason": self.unmapped_reason,
            "inventory_tables": list(self.inventory_tables),
            "qualifier": self.qualifier,
        }


@dataclass(frozen=True)
class CategoryGap:
    """A category that creates no class on the coverage floor, with the reason.

    FR-137 in the category direction: zero comparisons for one of these is
    correct and must never be read as coverage, and equally must never be read
    as a gap to be closed.
    """

    category: str
    reason: str
    detail: str = ""

    def as_dict(self) -> dict:
        return {"category": self.category, "reason": self.reason, "detail": self.detail}


@dataclass(frozen=True)
class ClassCategoryMap:
    """``contracts/class-category-map.json``, parsed and validated."""

    schema_version: int
    entries: tuple
    category_vocabulary: tuple
    category_dispatch: Mapping
    categories_without_in_scope_class: tuple  # tuple[CategoryGap, ...]
    unmapped_class_reasons: Mapping = field(default_factory=dict)
    categoryless_reasons: Mapping = field(default_factory=dict)
    path: Optional[Path] = None

    # -- lookups ------------------------------------------------------------

    @property
    def class_names(self) -> frozenset:
        return frozenset(e.class_name for e in self.entries)

    @property
    def categoryless(self) -> frozenset:
        return frozenset(g.category for g in self.categories_without_in_scope_class)

    def entries_for(self, class_name: str) -> tuple:
        rows = tuple(e for e in self.entries if e.class_name == class_name)
        if not rows:
            raise ClassCategoryMapError(
                "[FR-136] %r has no row in %s, so this map has no statement about "
                "which category creates it. Returning an empty category set here "
                "would be the invisible default FR-135 forbids -- add the class to "
                "the contract, with an unmapped_reason if no category creates it."
                % (class_name, CLASS_CATEGORY_MAP_NAME)
            )
        return rows

    def categories_for(self, class_name: str, owning_feature_system=_ANY_FEATURE_SYSTEM) -> tuple:
        """The categories that CREATE ``class_name``.

        An empty tuple is a real answer here, but only for a class whose row
        carries an ``unmapped_reason`` -- ``unmapped_reason_for`` returns it.
        An unknown class RAISES rather than returning empty, because the two
        are not the same fact and a caller that cannot tell them apart will
        report a gap as a clean.
        """
        rows = self.entries_for(class_name)
        if owning_feature_system is not _ANY_FEATURE_SYSTEM:
            rows = tuple(e for e in rows if e.owning_feature_system == owning_feature_system)
            if not rows:
                raise ClassCategoryMapError(
                    "[FR-136] %r has no row in %s for owning_feature_system %r. The "
                    "contract splits this class by feature system, so an unmatched "
                    "discriminator is a caller bug, not an empty result."
                    % (class_name, CLASS_CATEGORY_MAP_NAME, owning_feature_system)
                )
        out: list = []
        for e in rows:
            for c in e.categories:
                if c not in out:
                    out.append(c)
        return tuple(out)

    def unmapped_reason_for(self, class_name: str) -> Optional[str]:
        """The recorded reason ``class_name`` belongs to no category, or None
        when it does belong to at least one."""
        rows = self.entries_for(class_name)
        if any(e.mapped for e in rows):
            return None
        return rows[0].unmapped_reason

    def classes_for(self, category: str) -> tuple:
        """Every in-scope class the given category creates.

        A category outside the vocabulary RAISES. A category in the vocabulary
        but carrying no class returns an empty tuple -- ``is_categoryless``
        says which of the two an empty result is.
        """
        if category not in self.category_vocabulary:
            raise ClassCategoryMapError(
                "[FR-136] %r is not a GrammarCategory in %s's category_vocabulary. "
                "The vocabulary is closed on purpose: a typo'd category that "
                "silently matched nothing would report zero classes and zero "
                "findings, which reads as clean."
                % (category, CLASS_CATEGORY_MAP_NAME)
            )
        return tuple(sorted({e.class_name for e in self.entries if category in e.categories}))

    def is_categoryless(self, category: str) -> bool:
        """True when the contract records that this category creates no class on
        the coverage floor. Zero comparisons is then CORRECT, not a gap."""
        if category not in self.category_vocabulary:
            raise ClassCategoryMapError(
                "[FR-136] %r is not a GrammarCategory in %s's category_vocabulary"
                % (category, CLASS_CATEGORY_MAP_NAME)
            )
        return category in self.categoryless

    def gap_for(self, category: str) -> Optional[CategoryGap]:
        for g in self.categories_without_in_scope_class:
            if g.category == category:
                return g
        return None

    @property
    def unmapped_classes(self) -> tuple:
        """``((class_name, reason), ...)`` for every class no category creates."""
        seen: dict = {}
        for e in self.entries:
            if not e.mapped and e.class_name not in seen:
                seen[e.class_name] = e.unmapped_reason
        return tuple(sorted(seen.items()))

    @property
    def multi_category_classes(self) -> tuple:
        """Classes more than one category can create -- the rows the projection
        REPLICATES rather than partitions."""
        out: list = []
        for name in sorted(self.class_names):
            cats = self.categories_for(name)
            if len(cats) > 1:
                out.append((name, cats))
        return tuple(out)

    # -- validation ---------------------------------------------------------

    def assert_covers_floor(self, floor: CoverageFloor) -> None:
        """The map and the floor must name exactly the same classes.

        Same discipline as 038's ``derivation_check``: coverage is PROVEN on
        every load rather than asserted once. A class on the floor and off the
        map cannot be attributed to any category, and a class on the map and
        off the floor is being measured against a roster that does not contain
        it -- both are silent holes, so both raise.
        """
        mapped = self.class_names
        in_scope = frozenset(floor.in_scope_classes)
        missing = sorted(in_scope - mapped)
        extra = sorted(mapped - in_scope)
        if missing or extra:
            raise ClassCategoryMapError(
                "[FR-136] %s and %s disagree on the class roster: %d on the floor "
                "with no mapping (%r), %d mapped but not on the floor (%r). Until "
                "they agree, no category-keyed measurement derived from a "
                "class-keyed one can be trusted."
                % (CLASS_CATEGORY_MAP_NAME, COVERAGE_FLOOR_NAME,
                   len(missing), missing, len(extra), extra)
            )

    def as_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "path": str(self.path) if self.path else None,
            "class_count": len(self.class_names),
            "entry_count": len(self.entries),
            "category_vocabulary": list(self.category_vocabulary),
            "categories_with_classes": sorted(
                c for c in self.category_vocabulary if not self.is_categoryless(c)
            ),
            "categories_without_in_scope_class": [
                g.as_dict() for g in self.categories_without_in_scope_class
            ],
            "unmapped_classes": [
                {"class": c, "reason": r} for c, r in self.unmapped_classes
            ],
            "multi_category_classes": [
                {"class": c, "categories": list(cats)} for c, cats in self.multi_category_classes
            ],
        }


def load_class_category_map(path: Optional[Path] = None) -> ClassCategoryMap:
    """Read and VALIDATE the tracked class -> category join.

    Every check here exists because its absence would produce a confidently
    wrong category-keyed number rather than an error: an unknown category in a
    class row, a row that is neither mapped nor explained, a reason token with
    no definition, or a vocabulary member that is neither carried by a class
    nor recorded as carrying none.
    """
    p = Path(path) if path is not None else (DEFAULT_CONTRACTS_DIR / CLASS_CATEGORY_MAP_NAME)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ClassCategoryMapError(
            "[FR-136] the class -> category map %s does not exist. Without it the "
            "category-keyed guards (COMPARISONS-PERFORMED, CATEGORY-COVERAGE) have "
            "no input and FR-109 sinks the run to VACUOUS." % p
        ) from exc
    except json.JSONDecodeError as exc:
        raise ClassCategoryMapError(
            "[FR-136] the class -> category map %s is not valid JSON: %s" % (p, exc)
        ) from exc

    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ClassCategoryMapError(
            "[FR-136] %s declares schema_version %r; this reader implements %r. A "
            "silently-read newer contract is how a coverage gap becomes invisible."
            % (p, version, SCHEMA_VERSION)
        )

    vocabulary = tuple(raw.get("category_vocabulary") or ())
    if not vocabulary:
        raise ClassCategoryMapError(
            "[FR-136] %s declares an EMPTY category_vocabulary. The vocabulary is "
            "what makes an unrecognised category an error instead of a silent miss." % p
        )
    vocab_set = set(vocabulary)
    if len(vocab_set) != len(vocabulary):
        raise ClassCategoryMapError("[FR-136] %s lists a category twice in category_vocabulary" % p)

    unmapped_reasons = dict(raw.get("unmapped_class_reasons") or {})
    categoryless_reasons = dict(raw.get("categoryless_reasons") or {})

    dispatch = dict(raw.get("category_dispatch") or {})
    bad_dispatch = sorted(k for k, v in dispatch.items() if v not in _VALID_DISPATCH)
    if bad_dispatch:
        raise ClassCategoryMapError(
            "[FR-136] %s gives %r a category_dispatch value outside %r"
            % (p, bad_dispatch, sorted(_VALID_DISPATCH))
        )
    undispatched = sorted(vocab_set - set(dispatch))
    if undispatched:
        raise ClassCategoryMapError(
            "[FR-136] %s records no category_dispatch for %r. A category whose "
            "dispatch is unknown cannot be reported as measured OR as not "
            "dispatched." % (p, undispatched)
        )

    entries: list = []
    for row in raw.get("classes") or ():
        name = row.get("class")
        if not name:
            raise ClassCategoryMapError("[FR-136] %s has a class row with no 'class' name" % p)
        cats = tuple(row.get("categories") or ())
        reason = row.get("unmapped_reason")
        unknown = sorted(set(cats) - vocab_set)
        if unknown:
            raise ClassCategoryMapError(
                "[FR-136] %s maps %r to %r, which are not in category_vocabulary"
                % (p, name, unknown)
            )
        if bool(cats) == bool(reason):
            raise ClassCategoryMapError(
                "[FR-136] %r in %s has categories=%r and unmapped_reason=%r. Exactly "
                "one must be present: a class with no category MUST say why, and a "
                "class with a category must not also claim to be unmapped. An "
                "unexplained empty list is the invisible default FR-135 forbids."
                % (name, p, list(cats), reason)
            )
        if reason is not None and reason not in unmapped_reasons:
            raise ClassCategoryMapError(
                "[FR-136] %r in %s cites unmapped_reason %r, which is not defined in "
                "unmapped_class_reasons. An undefined reason token is an unreviewable "
                "excuse." % (name, p, reason)
            )
        entries.append(ClassCategoryEntry(
            class_name=name,
            owning_feature_system=row.get("owning_feature_system"),
            categories=cats,
            also_created_via=tuple(row.get("also_created_via") or ()),
            unmapped_reason=reason,
            inventory_tables=tuple(row.get("inventory_tables") or ()),
            qualifier=row.get("qualifier"),
        ))

    if not entries:
        raise ClassCategoryMapError(
            "[FR-136] %s maps ZERO classes. An empty map makes every category "
            "report zero comparisons, which reads as clean." % p
        )

    keys = [(e.class_name, e.owning_feature_system) for e in entries]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    if dupes:
        raise ClassCategoryMapError(
            "[FR-136] %s lists (class, owning_feature_system) %r more than once. That "
            "pair is the join key feature 038's census shares; a duplicate makes the "
            "join multi-valued and the category attribution ambiguous." % (p, dupes)
        )

    gaps: list = []
    for row in raw.get("categories_without_in_scope_class") or ():
        cat, reason = row.get("category"), (row.get("reason") or "").strip()
        if cat not in vocab_set:
            raise ClassCategoryMapError(
                "[FR-136] %s records %r as carrying no class, but it is not in "
                "category_vocabulary" % (p, cat)
            )
        if not reason:
            raise ClassCategoryMapError(
                "[FR-136] %s records %r as carrying no in-scope class with NO reason. "
                "An unexplained categoryless category is indistinguishable from a "
                "forgotten one." % (p, cat)
            )
        if reason not in categoryless_reasons:
            raise ClassCategoryMapError(
                "[FR-136] %r in %s cites categoryless reason %r, which is not defined "
                "in categoryless_reasons" % (cat, p, reason)
            )
        gaps.append(CategoryGap(category=cat, reason=reason, detail=row.get("detail") or ""))

    carried = {c for e in entries for c in e.categories}
    declared_empty = {g.category for g in gaps}
    both = sorted(carried & declared_empty)
    if both:
        raise ClassCategoryMapError(
            "[FR-136] %s both maps a class to %r and declares it as carrying no "
            "in-scope class" % (p, both)
        )
    unaccounted = sorted(vocab_set - carried - declared_empty)
    if unaccounted:
        raise ClassCategoryMapError(
            "[FR-136] %s leaves %r neither carrying a class nor recorded as carrying "
            "none. Silence about a category is what lets 'we compared zero and found "
            "zero mismatches' read as a pass (FR-137)." % (p, unaccounted)
        )

    return ClassCategoryMap(
        schema_version=version,
        entries=tuple(entries),
        category_vocabulary=vocabulary,
        category_dispatch=dispatch,
        categories_without_in_scope_class=tuple(gaps),
        unmapped_class_reasons=unmapped_reasons,
        categoryless_reasons=categoryless_reasons,
        path=p,
    )


# ---------------------------------------------------------------------------
# The bridge: class-keyed measurements -> the category-keyed guard input
# ---------------------------------------------------------------------------


def project_comparisons_to_categories(
    cmap: ClassCategoryMap,
    *,
    source_objects: Optional[Mapping] = None,
    comparisons_performed: Optional[Mapping] = None,
    objects_compared: Optional[Mapping] = None,
) -> Optional[dict]:
    """Turn three CLASS-keyed measurements into ``guards.RunContext.comparisons``.

    This is the ONLY sanctioned bridge between the two ``comparisons`` shapes
    named at the top of this section, and it is deliberately not called
    ``comparisons`` anything on its input side.

    Returns ``None`` -- never ``{}`` -- when ``source_objects`` was not
    measured, so ``guard_comparisons_performed`` reports ``not-evaluated``
    rather than passing over an empty mapping. That is FR-109's whole
    discipline, and the empty dict is the exact value that would break it.

    The result is::

        {
          "comparisons": {category: {source_objects, comparisons_performed,
                                     objects_compared, classes}},
          "unattributable": [{class, reason, source_objects}],
          "categoryless_categories": [...],
          "replicated_classes": [...],
        }

    ``comparisons`` is ready to hand to ``RunContext(comparisons=...)``.
    ``unattributable`` holds the measured classes no category creates: the
    caller MUST report these at the class plane, because the category plane has
    no place to put them and dropping them would hide real findings. Categories
    the contract records as carrying no class are omitted from ``comparisons``
    entirely rather than emitted as zeros -- a fabricated zero for one of them
    is a measurement claim about something that was never measurable.

    ``replicated_classes`` names the multi-category classes counted into more
    than one category. Per-category totals are therefore NOT a partition and
    MUST NOT be summed.
    """
    if source_objects is None:
        return None

    performed = comparisons_performed or {}
    compared = objects_compared or {}

    def _n(m: Mapping, k: str) -> int:
        return int(m.get(k, 0) or 0)

    measured_classes = sorted(
        set(source_objects) | set(performed) | set(compared)
    )

    unknown = sorted(c for c in measured_classes if c not in cmap.class_names)
    if unknown:
        raise ClassCategoryMapError(
            "[FR-136] the run measured %r, which %s does not map. A measured class "
            "with no category cannot be attributed, and silently discarding it "
            "would hide whatever it found." % (unknown, CLASS_CATEGORY_MAP_NAME)
        )

    out: dict = {}
    unattributable: list = []
    replicated: list = []

    for cls in measured_classes:
        cats = cmap.categories_for(cls)
        if not cats:
            unattributable.append({
                "class": cls,
                "reason": cmap.unmapped_reason_for(cls),
                "source_objects": _n(source_objects, cls),
                "comparisons_performed": _n(performed, cls),
                "objects_compared": _n(compared, cls),
            })
            continue
        if len(cats) > 1:
            replicated.append({"class": cls, "categories": list(cats)})
        for cat in cats:
            rec = out.setdefault(cat, {
                "source_objects": 0,
                "comparisons_performed": 0,
                "objects_compared": 0,
                "classes": [],
            })
            rec["source_objects"] += _n(source_objects, cls)
            rec["comparisons_performed"] += _n(performed, cls)
            rec["objects_compared"] += _n(compared, cls)
            rec["classes"].append(cls)

    for rec in out.values():
        rec["classes"].sort()

    return {
        "comparisons": out,
        "unattributable": unattributable,
        "categoryless_categories": sorted(cmap.categoryless),
        "replicated_classes": replicated,
    }


def categories_reachable_only_through_excluded(
    cmap: ClassCategoryMap, excluded_categories: Iterable[str]
) -> tuple:
    """Classes every one of whose creating categories this run excluded.

    Feeds ``classify_coverage``'s ``reachable_only_through_excluded``, which is
    FR-137's second clause. A class with two creating categories is only
    reachable-only-through-excluded when BOTH are excluded -- ``LexEntry`` is
    still reachable with STEMS off because AFFIXES also creates it, whereas
    ``LexEntryRef`` is not, since STEMS is the only category that creates one
    (object-inventory.md G3).

    Classes belonging to no category are NOT returned: their unreachability has
    a different cause, recorded as ``unmapped_reason``, and folding the two
    together would attribute a permanent structural hole to a per-run exclusion.
    """
    excluded = set(excluded_categories)
    unknown = sorted(excluded - set(cmap.category_vocabulary))
    if unknown:
        raise ClassCategoryMapError(
            "[FR-136] %r were reported as excluded categories but are not in %s's "
            "category_vocabulary" % (unknown, CLASS_CATEGORY_MAP_NAME)
        )
    out: list = []
    for name in sorted(cmap.class_names):
        cats = cmap.categories_for(name)
        if cats and set(cats) <= excluded:
            out.append(name)
    return tuple(out)
