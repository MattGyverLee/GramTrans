"""Feature 035 -- Group F: THE VACUITY GUARD REGISTRY.

Registered as the not-evaluated spine in T014 (Phase 2); the fifteen guards
implemented for real in T033 (Phase 4).

Source: contracts/guards.md (FR-093..FR-109).

Fifteen guards, keyed by their EXACT spec names (verbatim -- do not rename,
recase, or pluralize). The registry is the single source of truth: the
artifact's ``guards`` block is written FROM the registry keys, and FR-109's
completeness rule is enforced as a set-equality assertion between registry
keys and block keys -- never a hand-maintained checklist.

THE INVARIANT THAT MATTERS MOST. Every guard returns ``not-evaluated`` when
the measurement it depends on is absent from the ``RunContext`` -- never
``pass``. That is what makes ``not_evaluated_guard_block`` (and through it
``artifact.write_skipped_artifact``) honest for a project that never ran: an
empty context yields fifteen ``not-evaluated`` results and therefore
``VACUOUS``, and that postcondition is asserted rather than trusted.

The distinction is deliberate throughout: **absent** input means the guard
could not look (``not-evaluated``), while **present but unsatisfactory** input
means the guard looked and the answer was no (``fail``). Collapsing the two
would turn "we did not measure" into "we measured nothing wrong", which is the
exact failure mode this whole feature exists to eliminate.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence

# ---------------------------------------------------------------------------
# GuardResult / RunContext
# ---------------------------------------------------------------------------

_VALID_GUARD_RESULTS = ("pass", "fail", "not-evaluated")

DEFAULT_CONTRACTS_DIR = (
    Path(__file__).resolve().parents[2] / "specs" / "035-fullsweep-fidelity" / "contracts"
)
ENGINE_BUG_SIGNATURES_NAME = "engine-bug-signatures.json"
NEGATIVE_CONTROLS_NAME = "negative-controls.json"


@dataclass(frozen=True)
class GuardResult:
    """contracts/guards.md "Callable contract": ``guard`` (the exact key),
    ``result`` (``pass`` / ``fail`` / ``not-evaluated``), ``message`` (str),
    ``evidence`` (JSON-serializable object naming what the guard actually
    read).

    A guard that CANNOT be evaluated returns ``not-evaluated``. It MUST
    NEVER return ``pass`` in that case -- enforced here by construction, not
    left to caller discipline.
    """
    guard: str
    result: str
    message: str = ""
    evidence: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.result not in _VALID_GUARD_RESULTS:
            raise ValueError(
                "[guards.md] GuardResult.result must be one of %r, got %r"
                % (_VALID_GUARD_RESULTS, self.result)
            )

    def as_dict(self) -> dict:
        return {"result": self.result, "message": self.message, "evidence": self.evidence}


@dataclass
class RunContext:
    """Everything the fifteen guards read, for one project.

    Every measurement field defaults to ``None``, meaning "not measured". A
    guard whose input is ``None`` returns ``not-evaluated``. Nothing here
    defaults to an empty container, because an empty container reads as a
    successful measurement of nothing -- e.g. an empty accessor-counter dict
    would let ACCESSOR-INTEGRITY report all-zeros and pass a project it never
    opened.
    """

    project: str = ""
    extra: dict = field(default_factory=dict)

    # -- Group D, the double move (FR-043..FR-050) -------------------------
    census_baseline: Optional[dict] = None
    census_after_first: Optional[dict] = None
    census_after_second: Optional[dict] = None
    written: Optional[dict] = None
    idempotency: Optional[object] = None
    planned_action_count: Optional[int] = None

    # -- the accounting plane (FR-091..FR-097) ------------------------------
    accounting: Optional[object] = None

    # -- coverage and comparison bookkeeping (FR-095, FR-096) --------------
    enabled_categories: Optional[Sequence[str]] = None
    measured_categories: Optional[Sequence[str]] = None
    excluded_categories: Optional[Sequence[dict]] = None
    comparisons: Optional[dict] = None

    # -- distortion detectors (FR-098, FR-099, FR-102) ---------------------
    empty_measurements: Optional[Sequence[dict]] = None
    unhandled_subtypes: Optional[Sequence[dict]] = None
    extras: Optional[Sequence[dict]] = None

    # -- plan conservation (FR-101) ----------------------------------------
    plan_conservation: Optional[dict] = None

    # -- harness integrity (FR-103, FR-104, FR-105, FR-108) ---------------
    accessor_counters: Optional[dict] = None
    handle_operations: Optional[Sequence[dict]] = None
    truncation: Optional[dict] = None
    close_operations: Optional[Sequence[dict]] = None

    # -- artifact completeness (FR-106) ------------------------------------
    corpus_projects: Optional[Sequence[str]] = None
    artifacts_present: Optional[dict] = None

    # -- engine-bug refusal (FR-107) ---------------------------------------
    drop_reasons: Optional[Sequence[str]] = None
    engine_bug_signatures: Optional[dict] = None


# ---------------------------------------------------------------------------
# Contract constants
# ---------------------------------------------------------------------------

#: FR-103's four counters, all of which must be zero.
ACCESSOR_COUNTERS: tuple[str, ...] = (
    "unreadable_identifiers",
    "unreadable_names",
    "enumeration_failures",
    "skipped_source_objects",
)

#: FR-105 / data-model section 7: both must be zero in the DURABLE artifact.
#: Console truncation is legal and is not read here.
TRUNCATION_COUNTERS: tuple[str, ...] = ("dropped_breakdown_omitted", "detail_omitted")

#: FR-106's six required artifact contents.
ARTIFACT_REQUIRED_FIELDS: tuple[str, ...] = (
    "driver_revision",
    "capability_fingerprint",
    "baseline_identity",
    "diagnostic_level",
    "excluded_categories",
    "guards",
)

#: FR-098: these two outcomes stay DISTINCT and must never be folded together.
EMPTY_OUTCOME_ABSENT_OR_NULL = "absent-or-null"
EMPTY_OUTCOME_PRESENT_BUT_EMPTY = "present-but-empty"
EMPTY_OUTCOMES: tuple[str, ...] = (
    EMPTY_OUTCOME_ABSENT_OR_NULL, EMPTY_OUTCOME_PRESENT_BUT_EMPTY,
)

#: FR-101 counters that account for a planned action.
#:
#: FR-101 is written as "planned == added + skipped". Against the real
#: ``RunReport`` that identity does not close on its own: ``overwrites`` is a
#: separate plan tuple with its own ``overwritten`` counter, and
#: ``closure_pulled_in`` / ``excluded_lossy`` are separate again. Rather than
#: silently choosing a formula, the accounted counters are named HERE, in one
#: place, and every counter the context supplies but this tuple omits is
#: reported in the guard's evidence so a mismatch is diagnosable instead of
#: mysterious. Widening this tuple is a deliberate, reviewable edit.
PLAN_ACCOUNTED_COUNTERS: tuple[str, ...] = ("added", "skipped")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _not_evaluated(name: str, what: str) -> GuardResult:
    """The only way a guard reports "I could not look"."""
    return GuardResult(
        guard=name, result="not-evaluated",
        message="cannot be evaluated: %s was not measured" % what,
        evidence={"missing": what},
    )


def _counts_by_class(census: dict) -> dict:
    return {cls: len(ids) for cls, ids in census.items()}


def guard_module_hash(guard_name: str, *, module_path: Optional[Path] = None) -> str:
    """FR-180: the staleness signal for a guard's negative control is a content
    hash of the module the guard's own logic lives in.

    All fifteen guards live in this module today, so they share its hash. The
    signature takes the guard name so a later split into per-guard modules does
    not change any call site.
    """
    path = Path(__file__) if module_path is None else Path(module_path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return "sha256:%s" % digest


def load_engine_bug_signatures(
    path: Optional[Path] = None, *, contracts_dir: Optional[Path] = None,
) -> dict:
    """Read ``engine-bug-signatures.json`` (FR-107)."""
    if path is None:
        base = DEFAULT_CONTRACTS_DIR if contracts_dir is None else Path(contracts_dir)
        path = base / ENGINE_BUG_SIGNATURES_NAME
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_negative_controls(
    path: Optional[Path] = None, *, contracts_dir: Optional[Path] = None,
) -> dict:
    """Read the durable negative-control artifact (FR-180). A missing file is
    reported as an empty control set rather than raising, because FR-180's
    answer to "no control" is ``not-evaluated``, not a crash."""
    if path is None:
        base = DEFAULT_CONTRACTS_DIR if contracts_dir is None else Path(contracts_dir)
        path = base / NEGATIVE_CONTROLS_NAME
    path = Path(path)
    if not path.exists():
        return {"schema_version": 1, "controls": []}
    return json.loads(path.read_text(encoding="utf-8"))


def negative_control_result(guard_name: str, controls: Optional[dict] = None) -> str:
    """FR-180: is ``guard_name`` admissible as passing evidence?

    Returns ``"pass"`` when a control is recorded AND its stored module hash
    still matches the guard's module; ``"not-evaluated"`` when the control is
    missing, or stale because the guard's source changed since it was recorded.
    Never returns ``"fail"`` -- this answers "may this guard be believed", not
    "did the guard find a problem".
    """
    if controls is None:
        controls = load_negative_controls()
    recorded = [c for c in controls.get("controls", []) if c.get("guard") == guard_name]
    if not recorded:
        return "not-evaluated"
    current = guard_module_hash(guard_name)
    for control in recorded:
        if control.get("guard_module_hash") == current:
            return "pass"
    return "not-evaluated"


# ---------------------------------------------------------------------------
# The fifteen guards (FR-094..FR-108)
# ---------------------------------------------------------------------------


def guard_baseline_delta(ctx: RunContext) -> GuardResult:
    """FR-094. Fails as VACUOUS. All FOUR parts, conjunctively."""
    name = "BASELINE-DELTA"
    if ctx.census_baseline is None or ctx.census_after_first is None:
        return _not_evaluated(name, "the baseline and post-first-transfer censuses")
    if ctx.planned_action_count is None:
        return _not_evaluated(name, "the planned-action count")

    before, after = ctx.census_baseline, ctx.census_after_first
    b_counts, a_counts = _counts_by_class(before), _counts_by_class(after)

    newly_present: dict = {}
    for cls in set(before) | set(after):
        gained = set(after.get(cls, set())) - set(before.get(cls, set()))
        if gained:
            newly_present[cls] = sorted(gained)
    new_count = sum(len(v) for v in newly_present.values())

    lowered = [
        cls for cls in set(b_counts) | set(a_counts)
        if a_counts.get(cls, 0) < b_counts.get(cls, 0)
    ]
    higher = [
        cls for cls in set(b_counts) | set(a_counts)
        if a_counts.get(cls, 0) > b_counts.get(cls, 0)
    ]
    threshold = ctx.planned_action_count / 2.0

    parts = {
        "newly_present_non_empty": bool(newly_present),
        "no_label_count_lowered": not lowered,
        "at_least_one_label_higher": bool(higher),
        "new_count_at_least_half_planned": new_count >= threshold,
    }
    evidence = {
        "parts": parts,
        "new_object_count": new_count,
        "planned_action_count": ctx.planned_action_count,
        "half_planned_threshold": threshold,
        "labels_lowered": sorted(lowered),
        "labels_higher": sorted(higher),
        "newly_present_by_class": {k: len(v) for k, v in newly_present.items()},
    }
    failed = [k for k, ok in parts.items() if not ok]
    if failed:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-094] the first transfer produced no measurable "
                    "non-trivial change; failing part(s): %r -- the run proved "
                    "nothing" % (failed,),
            evidence=evidence,
        )
    return GuardResult(guard=name, result="pass",
                       message="the first transfer produced measurable change",
                       evidence=evidence)


def guard_comparisons_performed(ctx: RunContext) -> GuardResult:
    """FR-095. Fails as VACUOUS, per category."""
    name = "COMPARISONS-PERFORMED"
    if ctx.comparisons is None:
        return _not_evaluated(name, "per-category comparison counts")

    vacuous = []
    for category, rec in sorted(ctx.comparisons.items()):
        source_objects = rec.get("source_objects", 0)
        if source_objects < 1:
            continue
        if rec.get("comparisons_performed", 0) < 1 or rec.get("objects_compared", 0) < 1:
            vacuous.append({
                "category": category,
                "source_objects": source_objects,
                "comparisons_performed": rec.get("comparisons_performed", 0),
                "objects_compared": rec.get("objects_compared", 0),
            })
    evidence = {"categories_examined": len(ctx.comparisons), "vacuous_categories": vacuous}
    if vacuous:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-095] %d category(ies) have source objects but performed "
                    "zero comparisons" % len(vacuous),
            evidence=evidence,
        )
    return GuardResult(guard=name, result="pass",
                       message="every category with source objects compared something",
                       evidence=evidence)


def guard_category_coverage(ctx: RunContext) -> GuardResult:
    """FR-096. Fails as COVERAGE_REDUCED -- never a silent gap."""
    name = "CATEGORY-COVERAGE"
    if ctx.enabled_categories is None or ctx.measured_categories is None:
        return _not_evaluated(name, "the enabled and measured category sets")
    if ctx.excluded_categories is None:
        return _not_evaluated(name, "the excluded-category record")

    enabled = set(ctx.enabled_categories)
    measured = set(ctx.measured_categories)
    excluded_named = {e.get("category") for e in ctx.excluded_categories}
    unrecorded_exclusions = [
        e.get("category") for e in ctx.excluded_categories if not e.get("reason")
    ]
    unmeasured = sorted(enabled - measured - excluded_named)

    evidence = {
        "enabled_count": len(enabled),
        "measured_count": len(measured),
        "excluded": sorted(x for x in excluded_named if x),
        "enabled_but_unmeasured": unmeasured,
        "exclusions_missing_a_reason": unrecorded_exclusions,
    }
    if unmeasured:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-096] %d enabled category(ies) were never measured and "
                    "were not recorded as excluded: %r" % (len(unmeasured), unmeasured),
            evidence=evidence,
        )
    if unrecorded_exclusions:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-096] excluded category(ies) %r carry no recorded reason -- "
                    "every exclusion must be explicit" % (unrecorded_exclusions,),
            evidence=evidence,
        )
    return GuardResult(guard=name, result="pass",
                       message="the measured set covers every enabled category",
                       evidence=evidence)


def guard_total_accounting(ctx: RunContext) -> GuardResult:
    """FR-097. Fails as UNEXPLAINED_LOSS."""
    name = "TOTAL-ACCOUNTING"
    if ctx.accounting is None:
        return _not_evaluated(name, "the object-level accounting plane")

    acc = ctx.accounting
    unaccounted = list(getattr(acc, "unaccounted", ()))
    overflows = list(getattr(acc, "allowlist_overflows", ()))
    evidence = {
        "counts": acc.counts() if hasattr(acc, "counts") else {},
        "total": getattr(acc, "total", 0),
        "unaccounted_count": len(unaccounted),
        "unaccounted": [a.as_dict() for a in unaccounted[:50]],
        "allowlist_overflows": overflows,
    }
    if unaccounted or overflows:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-097] %d source object(s) landed in no explaining bucket "
                    "and %d allowlist entr(ies) exceeded their cap -- being "
                    "reported is never itself an explanation"
                    % (len(unaccounted), len(overflows)),
            evidence=evidence,
        )
    return GuardResult(guard=name, result="pass",
                       message="every in-scope source object is in exactly one "
                               "explaining bucket",
                       evidence=evidence)


def guard_empty_corroboration(ctx: RunContext) -> GuardResult:
    """FR-098. Fails as a run failure (contracts/guards.md pins no single token;
    see the recorded concern). Absent-or-null and present-but-empty stay
    DISTINCT recorded outcomes."""
    name = "EMPTY-CORROBORATION"
    if ctx.empty_measurements is None:
        return _not_evaluated(name, "the empty-source measurements")

    uncorroborated, undistinguished = [], []
    for rec in ctx.empty_measurements:
        if rec.get("corroborating_count") is None:
            uncorroborated.append(rec.get("category") or rec.get("class"))
        if rec.get("outcome") not in EMPTY_OUTCOMES:
            undistinguished.append({
                "subject": rec.get("category") or rec.get("class"),
                "outcome": rec.get("outcome"),
            })
    evidence = {
        "measurements": len(ctx.empty_measurements),
        "uncorroborated": uncorroborated,
        "outcome_not_one_of_the_two_distinct_states": undistinguished,
        "distinct_outcomes": list(EMPTY_OUTCOMES),
    }
    if uncorroborated:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-098] %d empty source measurement(s) were never "
                    "corroborated by an independent count"
                    % len(uncorroborated),
            evidence=evidence,
        )
    if undistinguished:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-098] %d measurement(s) did not record which of the two "
                    "distinct empty outcomes applied -- 'absent or null' must "
                    "never collapse into 'present but empty'" % len(undistinguished),
            evidence=evidence,
        )
    return GuardResult(guard=name, result="pass",
                       message="every empty measurement is independently "
                               "corroborated and distinctly classified",
                       evidence=evidence)


def guard_unhandled_subtype(ctx: RunContext) -> GuardResult:
    """FR-099. Named and counted, or a harness error -- never reduced to an
    absent/empty value that compares equal."""
    name = "UNHANDLED-SUBTYPE"
    if ctx.unhandled_subtypes is None:
        return _not_evaluated(name, "the unhandled-subtype outcomes")

    reduced, unnamed = [], []
    for rec in ctx.unhandled_subtypes:
        if rec.get("reduced_to_equal_comparison"):
            reduced.append(rec.get("subtype"))
        if not rec.get("outcome_name") or rec.get("count") is None:
            unnamed.append(rec.get("subtype"))
    evidence = {
        "subtypes": len(ctx.unhandled_subtypes),
        "reduced_to_an_equal_comparison": reduced,
        "missing_a_named_counted_outcome": unnamed,
    }
    if reduced:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-099] %d unhandled subtype(s) were reduced to an "
                    "absent/empty value that compares equal: %r" % (len(reduced), reduced),
            evidence=evidence,
        )
    if unnamed:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-099] %d unhandled subtype(s) lack a named, counted "
                    "outcome: %r" % (len(unnamed), unnamed),
            evidence=evidence,
        )
    return GuardResult(guard=name, result="pass",
                       message="every unhandled subtype is named and counted",
                       evidence=evidence)


def guard_idempotency_in_written_classes(ctx: RunContext) -> GuardResult:
    """FR-100. Fails as NON_IDEMPOTENT. Measured over the DERIVED class set."""
    name = "IDEMPOTENCY-IN-WRITTEN-CLASSES"
    if ctx.idempotency is None:
        return _not_evaluated(name, "the idempotency comparison")
    if ctx.census_after_first is None or ctx.census_after_second is None:
        return _not_evaluated(name, "both post-transfer censuses")

    idem = ctx.idempotency
    harness_error = getattr(idem, "harness_error", "") or ""
    diverged = dict(getattr(idem, "diverged_classes", {}) or {})

    second_additions: dict = {}
    for cls in set(ctx.census_after_first) | set(ctx.census_after_second):
        gained = (set(ctx.census_after_second.get(cls, set()))
                  - set(ctx.census_after_first.get(cls, set())))
        if gained:
            second_additions[cls] = sorted(gained)
    added_count = sum(len(v) for v in second_additions.values())

    evidence = {
        "written_class_set": list(getattr(idem, "written_class_set", ()) or ()),
        "unchanged_classes": list(getattr(idem, "unchanged_classes", ()) or ()),
        "diverged_classes": diverged,
        "second_transfer_added_by_class": {k: len(v) for k, v in second_additions.items()},
        "second_transfer_added_count": added_count,
        "harness_error": harness_error,
    }
    if harness_error:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-046/FR-100] the idempotency measurement is structurally "
                    "invalid: %s" % harness_error,
            evidence=evidence,
        )
    if diverged:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-100] %d class(es) in the derived written set changed "
                    "between the two censuses: %r"
                    % (len(diverged), sorted(diverged)),
            evidence=evidence,
        )
    if added_count:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-100] the second transfer added %d new object(s); an "
                    "idempotent second move adds zero" % added_count,
            evidence=evidence,
        )
    return GuardResult(guard=name, result="pass",
                       message="no class in the derived written set changed and "
                               "the second transfer added nothing",
                       evidence=evidence)


def guard_plan_conservation(ctx: RunContext) -> GuardResult:
    """FR-101. Fails as UNEXPLAINED_LOSS. Per category AND in total, in BOTH
    directions -- neither more accounted for than planned nor fewer."""
    name = "PLAN-CONSERVATION"
    if ctx.plan_conservation is None:
        return _not_evaluated(name, "the plan-conservation counters")

    per_category = ctx.plan_conservation.get("per_category")
    total = ctx.plan_conservation.get("total")
    if per_category is None or total is None:
        return _not_evaluated(name, "the per-category and total conservation counters")

    def _accounted(rec: dict) -> int:
        return sum(int(rec.get(k, 0)) for k in PLAN_ACCOUNTED_COUNTERS)

    def _unfolded(rec: dict) -> dict:
        return {
            k: v for k, v in rec.items()
            if k not in PLAN_ACCOUNTED_COUNTERS and k != "planned" and v
        }

    discrepancies = []
    for category, rec in sorted(per_category.items()):
        planned, accounted = int(rec.get("planned", 0)), _accounted(rec)
        if planned != accounted:
            discrepancies.append({
                "category": category, "planned": planned, "accounted": accounted,
                "direction": "more accounted than planned" if accounted > planned
                             else "fewer accounted than planned",
                "counters_not_folded_in": _unfolded(rec),
            })
    t_planned, t_accounted = int(total.get("planned", 0)), _accounted(total)
    total_ok = t_planned == t_accounted

    evidence = {
        "accounted_counters": list(PLAN_ACCOUNTED_COUNTERS),
        "total": {"planned": t_planned, "accounted": t_accounted},
        "total_counters_not_folded_in": _unfolded(total),
        "per_category_discrepancies": discrepancies,
    }
    if discrepancies or not total_ok:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-101] planned actions do not equal accounted actions: "
                    "%d category discrepanc(ies), total planned=%d accounted=%d"
                    % (len(discrepancies), t_planned, t_accounted),
            evidence=evidence,
        )
    return GuardResult(guard=name, result="pass",
                       message="planned equals accounted per category and in total",
                       evidence=evidence)


def guard_no_extra(ctx: RunContext) -> GuardResult:
    """FR-102. Fails as UNEXPLAINED_LOSS.

    A second instance of a tool-owned-identity class (FR-183) is unexplained
    loss and is NEVER allowlistable, however the entry is written -- so that
    check is made before, and independently of, the allowlist check.
    """
    name = "NO-EXTRA"
    if ctx.extras is None:
        return _not_evaluated(name, "the newly-present-object records")

    tool_owned_duplicates, untraceable = [], []
    for rec in ctx.extras:
        if rec.get("tool_owned_duplicate"):
            tool_owned_duplicates.append({
                "class": rec.get("class"), "id": rec.get("id"),
                "allowlisted_anyway": bool(rec.get("allowlisted")),
            })
            continue
        if not rec.get("traceable_to_source") and not rec.get("allowlisted"):
            untraceable.append({"class": rec.get("class"), "id": rec.get("id")})
    evidence = {
        "extras_examined": len(ctx.extras),
        "tool_owned_second_instances": tool_owned_duplicates,
        "untraceable_and_not_allowlisted": untraceable,
    }
    if tool_owned_duplicates:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-102/FR-183] %d second instance(s) of a tool-owned-identity "
                    "class are present; these are unexplained loss and are never "
                    "allowlistable as target-native additions"
                    % len(tool_owned_duplicates),
            evidence=evidence,
        )
    if untraceable:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-102] %d newly-present object(s) trace to no source object "
                    "and are not allowlisted" % len(untraceable),
            evidence=evidence,
        )
    return GuardResult(guard=name, result="pass",
                       message="every newly-present object traces to a source "
                               "object or an explicit allowlist entry",
                       evidence=evidence)


def guard_accessor_integrity(ctx: RunContext) -> GuardResult:
    """FR-103. Fails as HARNESS_ERROR. All four counters must be zero."""
    name = "ACCESSOR-INTEGRITY"
    if ctx.accessor_counters is None:
        return _not_evaluated(name, "the accessor counters")

    missing = [c for c in ACCESSOR_COUNTERS if c not in ctx.accessor_counters]
    if missing:
        return _not_evaluated(name, "accessor counter(s) %r" % (missing,))

    nonzero = {c: ctx.accessor_counters[c] for c in ACCESSOR_COUNTERS
               if ctx.accessor_counters[c]}
    evidence = {
        "counters": {c: ctx.accessor_counters[c] for c in ACCESSOR_COUNTERS},
        "nonzero": nonzero,
        "failed_accessors": list(ctx.accessor_counters.get("failed_accessors", ())),
    }
    if nonzero:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-103] accessor integrity is broken: %r must all be zero; "
                    "no measurement may be defaulted to empty or zero" % (nonzero,),
            evidence=evidence,
        )
    return GuardResult(guard=name, result="pass",
                       message="every declared accessor resolved with all four "
                               "counters at zero",
                       evidence=evidence)


def guard_handle_integrity(ctx: RunContext) -> GuardResult:
    """FR-104. Fails as HARNESS_ERROR, recording the operation attempted
    together with the failure's type and message."""
    name = "HANDLE-INTEGRITY"
    if ctx.handle_operations is None:
        return _not_evaluated(name, "the project-handle operation log")

    failures = []
    for op in ctx.handle_operations:
        if op.get("ok"):
            continue
        failures.append({
            "operation": op.get("operation"),
            "error_type": op.get("error_type"),
            "error_message": op.get("error_message"),
        })
    evidence = {"operations": len(ctx.handle_operations), "failures": failures}
    if failures:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-104] %d project-handle or auxiliary-service operation(s) "
                    "failed; this project's measurements cannot be substituted "
                    "with empty, zero, or default values" % len(failures),
            evidence=evidence,
        )
    return GuardResult(guard=name, result="pass",
                       message="every handle operation a measurement depends on "
                               "succeeded",
                       evidence=evidence)


def guard_no_truncation(ctx: RunContext) -> GuardResult:
    """FR-105. Fails as HARNESS_ERROR. Zero omissions in the DURABLE artifact."""
    name = "NO-TRUNCATION"
    if ctx.truncation is None:
        return _not_evaluated(name, "the artifact truncation counters")

    missing = [c for c in TRUNCATION_COUNTERS if c not in ctx.truncation]
    if missing:
        return _not_evaluated(name, "truncation counter(s) %r" % (missing,))

    omitted = {c: ctx.truncation[c] for c in TRUNCATION_COUNTERS if ctx.truncation[c]}
    evidence = {
        "counters": {c: ctx.truncation[c] for c in TRUNCATION_COUNTERS},
        "omitted": omitted,
    }
    if omitted:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-105] the durable artifact omits %r -- truncation in the "
                    "durable artifact is itself a harness error" % (omitted,),
            evidence=evidence,
        )
    return GuardResult(guard=name, result="pass",
                       message="the durable artifact omits no drop-reason bucket "
                               "and no detail row",
                       evidence=evidence)


def guard_artifact_integrity(ctx: RunContext) -> GuardResult:
    """FR-106. Fails as INCOMPLETE. An artifact for EVERY corpus project."""
    name = "ARTIFACT-INTEGRITY"
    if ctx.corpus_projects is None or ctx.artifacts_present is None:
        return _not_evaluated(name, "the corpus project list and artifact index")

    missing_artifacts, incomplete = [], []
    for project in ctx.corpus_projects:
        record = ctx.artifacts_present.get(project)
        if not record:
            missing_artifacts.append(project)
            continue
        absent = [f for f in ARTIFACT_REQUIRED_FIELDS if not record.get(f)]
        if absent:
            incomplete.append({"project": project, "missing_fields": absent})
    evidence = {
        "corpus_project_count": len(ctx.corpus_projects),
        "artifacts_found": len(ctx.artifacts_present),
        "missing_artifacts": missing_artifacts,
        "incomplete_artifacts": incomplete,
        "required_fields": list(ARTIFACT_REQUIRED_FIELDS),
    }
    if missing_artifacts:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-106] %d corpus project(s) have no artifact: %r"
                    % (len(missing_artifacts), missing_artifacts),
            evidence=evidence,
        )
    if incomplete:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-106] %d artifact(s) are missing required content"
                    % len(incomplete),
            evidence=evidence,
        )
    return GuardResult(guard=name, result="pass",
                       message="every corpus project has a complete artifact",
                       evidence=evidence)


def guard_no_engine_bug_as_loss(ctx: RunContext) -> GuardResult:
    """FR-107. Fails as UNEXPLAINED_LOSS, never allowlistable (FR-121).

    Note the deliberate asymmetry with the loss allowlist: the allowlist
    REFUSES patterns (FR-116, one entry must not stretch to two failure modes),
    while this roster is regex-matched on purpose -- it is trying to catch a
    family of engine bugs, not excuse one.

    Absent roster => ``not-evaluated`` (nothing could be read). Present but
    empty => ``fail``: FR-107 says an empty or implementer-chosen set does not
    satisfy the guard, and the file was readable, so the guard did look.
    """
    name = "NO-ENGINE-BUG-AS-LOSS"
    if ctx.drop_reasons is None:
        return _not_evaluated(name, "the observed drop reasons")
    if ctx.engine_bug_signatures is None:
        return _not_evaluated(name, "the engine-bug signature roster")

    roster = ctx.engine_bug_signatures
    signatures = roster.get("signatures") or []
    has_mandatory_minimum = any(s.get("mandatory_minimum_member") for s in signatures)

    if not signatures:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-107] the engine-bug signature roster is empty; an empty "
                    "or implementer-chosen set does not satisfy this guard",
            evidence={"signature_count": 0},
        )
    if not has_mandatory_minimum:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-107] the roster carries no mandatory-minimum member (a "
                    "loss reason referencing an internal task, ticket, issue, "
                    "probe, or TODO identifier)",
            evidence={"signature_count": len(signatures)},
        )

    matches = []
    for reason in ctx.drop_reasons:
        for sig in signatures:
            pattern = sig.get("pattern")
            if not pattern:
                continue
            if re.search(pattern, reason, re.IGNORECASE):
                matches.append({"reason": reason, "signature_id": sig.get("id"),
                                "kind": sig.get("kind")})
                break
    evidence = {
        "signature_count": len(signatures),
        "drop_reasons_examined": len(ctx.drop_reasons),
        "matches": matches,
    }
    if matches:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-107/FR-121] %d drop reason(s) match the engine-bug "
                    "signature roster; these are unexplained loss and are never "
                    "allowlistable" % len(matches),
            evidence=evidence,
        )
    return GuardResult(guard=name, result="pass",
                       message="no drop reason matches an engine-bug signature",
                       evidence=evidence)


def guard_clean_close(ctx: RunContext) -> GuardResult:
    """FR-108. Fails as HARNESS_ERROR. A close failure or timeout invalidates
    every measurement that follows it for that project."""
    name = "CLEAN-CLOSE"
    if ctx.close_operations is None:
        return _not_evaluated(name, "the project-close operation log")

    failures = []
    for op in ctx.close_operations:
        if op.get("ok") and not op.get("timed_out"):
            continue
        failures.append({
            "operation": op.get("operation"),
            "timed_out": bool(op.get("timed_out")),
            "error_message": op.get("error_message"),
            "measurements_after_this_close": op.get("followed_by", []),
        })
    evidence = {"closes": len(ctx.close_operations), "failures": failures}
    if failures:
        return GuardResult(
            guard=name, result="fail",
            message="[FR-108] %d project close(s) failed or timed out; every "
                    "measurement taken after such a close is invalid"
                    % len(failures),
            evidence=evidence,
        )
    return GuardResult(guard=name, result="pass",
                       message="every close completed before any reopen or census",
                       evidence=evidence)


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

#: contracts/guards.md "Registry keys" table, verbatim, in the table's order.
GUARD_NAMES: tuple[str, ...] = (
    "BASELINE-DELTA",
    "COMPARISONS-PERFORMED",
    "CATEGORY-COVERAGE",
    "TOTAL-ACCOUNTING",
    "EMPTY-CORROBORATION",
    "UNHANDLED-SUBTYPE",
    "IDEMPOTENCY-IN-WRITTEN-CLASSES",
    "PLAN-CONSERVATION",
    "NO-EXTRA",
    "ACCESSOR-INTEGRITY",
    "HANDLE-INTEGRITY",
    "NO-TRUNCATION",
    "ARTIFACT-INTEGRITY",
    "NO-ENGINE-BUG-AS-LOSS",
    "CLEAN-CLOSE",
)

assert len(GUARD_NAMES) == 15, "guards.md defines exactly fifteen guards"


#: FR-109: the single source of truth. The artifact's guards block is written
#: FROM these keys.
GUARD_REGISTRY: dict[str, Callable[[RunContext], GuardResult]] = {
    "BASELINE-DELTA": guard_baseline_delta,
    "COMPARISONS-PERFORMED": guard_comparisons_performed,
    "CATEGORY-COVERAGE": guard_category_coverage,
    "TOTAL-ACCOUNTING": guard_total_accounting,
    "EMPTY-CORROBORATION": guard_empty_corroboration,
    "UNHANDLED-SUBTYPE": guard_unhandled_subtype,
    "IDEMPOTENCY-IN-WRITTEN-CLASSES": guard_idempotency_in_written_classes,
    "PLAN-CONSERVATION": guard_plan_conservation,
    "NO-EXTRA": guard_no_extra,
    "ACCESSOR-INTEGRITY": guard_accessor_integrity,
    "HANDLE-INTEGRITY": guard_handle_integrity,
    "NO-TRUNCATION": guard_no_truncation,
    "ARTIFACT-INTEGRITY": guard_artifact_integrity,
    "NO-ENGINE-BUG-AS-LOSS": guard_no_engine_bug_as_loss,
    "CLEAN-CLOSE": guard_clean_close,
}

assert set(GUARD_REGISTRY) == set(GUARD_NAMES), (
    "the registry must name exactly the fifteen contract guards"
)


def run_all_guards(ctx: RunContext, registry: Optional[dict] = None) -> dict[str, GuardResult]:
    """Invoke every guard in ``registry`` (default: ``GUARD_REGISTRY``) over
    ``ctx``, returning ``{guard_name: GuardResult}``."""
    registry = GUARD_REGISTRY if registry is None else registry
    return {name: fn(ctx) for name, fn in registry.items()}


def guard_block_as_dict(results: dict) -> dict:
    """``{guard_name: GuardResult}`` -> the plain-dict shape the artifact
    JSON's ``guards`` block stores."""
    return {name: r.as_dict() for name, r in results.items()}


def not_evaluated_guard_block(registry: Optional[dict] = None) -> dict:
    """Convenience for a project that never ran (the SKIPPED-artifact path,
    ``artifact.write_skipped_artifact``): every guard, not-evaluated, as a
    ready-to-serialize dict.

    The postcondition is ASSERTED, not assumed. An empty ``RunContext``
    measures nothing, so every guard must report ``not-evaluated``; if a future
    guard ever returned ``pass`` on no input, this path would silently mint a
    passing guard for a project that was never opened. That is exactly the
    degradation FR-109 forbids, so it fails loudly here instead.
    """
    results = run_all_guards(RunContext(), registry)
    leaked = {n: r.result for n, r in results.items() if r.result != "not-evaluated"}
    if leaked:
        raise ValueError(
            "[FR-109] guard(s) %r reported a result other than not-evaluated for "
            "a project that was never measured; a guard with no input MUST NOT "
            "report pass or fail" % (leaked,)
        )
    return guard_block_as_dict(results)


def assert_guard_block_complete(guards_block: dict, registry: Optional[dict] = None) -> None:
    """FR-109 meta-rule: ``set(registry.keys()) == set(artifact["guards"].keys())``.

    Callers MUST call this BOTH before the verdict is computed and again
    before the artifact is flushed (guards.md meta-rule) -- pass the same
    ``guards_block`` both times; this function does not itself track which
    call site it is.
    """
    registry = GUARD_REGISTRY if registry is None else registry
    registry_keys = set(registry)
    block_keys = set(guards_block)
    if registry_keys != block_keys:
        missing = sorted(registry_keys - block_keys)
        extra = sorted(block_keys - registry_keys)
        raise ValueError(
            "[FR-109] guards block is not complete: missing=%r extra=%r"
            % (missing, extra)
        )


# ---------------------------------------------------------------------------
# T034 -- the negative-control regime (FR-178..FR-181)
# ---------------------------------------------------------------------------

#: contracts/guards.md "Fails as" column: the specific failing verdict each
#: guard exists to produce (FR-179).
#:
#: TWO ENTRIES ARE THIS MODULE'S CHOICE, NOT THE CONTRACT'S. guards.md gives
#: `EMPTY-CORROBORATION` the non-token phrase "run failure" and
#: `UNHANDLED-SUBTYPE` the phrase "named/counted outcome or HARNESS_ERROR",
#: and verdict-exit-model.md omits both from its assignment table. A durable
#: control record has to name a real machine token, so:
#:   * EMPTY-CORROBORATION -> VACUOUS. An uncorroborated empty reading means
#:     the sweep measured nothing and called it empty, which is precisely the
#:     vacuity Section F exists to catch.
#:   * UNHANDLED-SUBTYPE -> HARNESS_ERROR. Its fail condition is the
#:     comparator silently reducing a subtype it cannot handle to a value that
#:     compares equal -- a defect in the instrument, not in the data.
#: Both are flagged for ratification into contracts/guards.md.
GUARD_FAILURE_VERDICT: dict[str, str] = {
    "BASELINE-DELTA": "VACUOUS",
    "COMPARISONS-PERFORMED": "VACUOUS",
    "CATEGORY-COVERAGE": "COVERAGE_REDUCED",
    "TOTAL-ACCOUNTING": "UNEXPLAINED_LOSS",
    "EMPTY-CORROBORATION": "VACUOUS",              # contract-silent, chosen here
    "UNHANDLED-SUBTYPE": "HARNESS_ERROR",          # contract-silent, chosen here
    "IDEMPOTENCY-IN-WRITTEN-CLASSES": "NON_IDEMPOTENT",
    "PLAN-CONSERVATION": "UNEXPLAINED_LOSS",
    "NO-EXTRA": "UNEXPLAINED_LOSS",
    "ACCESSOR-INTEGRITY": "HARNESS_ERROR",
    "HANDLE-INTEGRITY": "HARNESS_ERROR",
    "NO-TRUNCATION": "HARNESS_ERROR",
    "ARTIFACT-INTEGRITY": "INCOMPLETE",
    "NO-ENGINE-BUG-AS-LOSS": "UNEXPLAINED_LOSS",
    "CLEAN-CLOSE": "HARNESS_ERROR",
}

#: A roster built inline for the NO-ENGINE-BUG-AS-LOSS control, so the control
#: exercises the MATCH path rather than the empty-roster path. Using the
#: tracked roster would prove only that an empty file fails.
_CONTROL_ENGINE_BUG_ROSTER = {
    "schema_version": 1,
    "signatures": [
        {
            "id": "EBS-CONTROL",
            "pattern": r"(?:\bTODO\b|\bFIXME\b|\bT\d{3}\b|#\d+)",
            "kind": "internal-identifier leak",
            "mandatory_minimum_member": True,
        }
    ],
}

_COMPLETE_ARTIFACT_RECORD = {f: "present" for f in ARTIFACT_REQUIRED_FIELDS}


def _seeded_context(guard_name: str) -> RunContext:
    """Build a RunContext carrying a deliberately seeded defect for
    ``guard_name`` (FR-179).

    Each context is minimal and targets exactly one guard's fail condition, so
    a control that fires proves THAT guard can fail rather than that something
    somewhere went wrong. Modules are imported lazily to keep this module free
    of import-order coupling.
    """
    from . import compare as compare_mod
    from . import moves as moves_mod

    if guard_name == "BASELINE-DELTA":
        # Seeded defect: the first transfer changed nothing at all.
        return RunContext(
            project="negative-control",
            census_baseline={"LexEntry": {"g1"}},
            census_after_first={"LexEntry": {"g1"}},
            planned_action_count=10,
        )

    if guard_name == "COMPARISONS-PERFORMED":
        # Seeded defect: a category with source objects compared nothing.
        return RunContext(
            project="negative-control",
            comparisons={"pos": {"source_objects": 5, "comparisons_performed": 0,
                                 "objects_compared": 0}},
        )

    if guard_name == "CATEGORY-COVERAGE":
        # Seeded defect: an enabled category silently never measured.
        return RunContext(
            project="negative-control",
            enabled_categories=["pos", "sense"],
            measured_categories=["pos"],
            excluded_categories=[],
        )

    if guard_name == "TOTAL-ACCOUNTING":
        # Seeded defect: one source object dropped with no allowlist entry
        # (the illustrative control in rosters.md section 8).
        acc = compare_mod.ObjectAccounting(project="negative-control")
        acc.assign("LexEntry", "g1", compare_mod.BUCKET_TRANSFERRED)
        acc.assign("LexEntry", "g2", compare_mod.BUCKET_UNACCOUNTED,
                   detail=compare_mod.UNACCOUNTED_DROPPED_NOT_ALLOWLISTED)
        return RunContext(project="negative-control", accounting=acc)

    if guard_name == "EMPTY-CORROBORATION":
        # Seeded defect: an empty source reading with no independent count.
        return RunContext(
            project="negative-control",
            empty_measurements=[{"category": "pos", "corroborating_count": None,
                                 "outcome": EMPTY_OUTCOME_ABSENT_OR_NULL}],
        )

    if guard_name == "UNHANDLED-SUBTYPE":
        # Seeded defect: an unhandled subtype reduced to a value comparing equal.
        return RunContext(
            project="negative-control",
            unhandled_subtypes=[{"subtype": "IPhonRuleFeat",
                                 "outcome_name": "not-applicable",
                                 "count": 1,
                                 "reduced_to_equal_comparison": True}],
        )

    if guard_name == "IDEMPOTENCY-IN-WRITTEN-CLASSES":
        # Seeded defect: the second transfer wrote again.
        after_first = {"LexEntry": {"g1"}}
        after_second = {"LexEntry": {"g1", "g2"}}
        written = moves_mod.written_classes({"LexEntry": set()}, after_first)
        idem = moves_mod.check_idempotency(after_first, after_second, written)
        return RunContext(
            project="negative-control",
            census_after_first=after_first,
            census_after_second=after_second,
            written=written,
            idempotency=idem,
        )

    if guard_name == "PLAN-CONSERVATION":
        # Seeded defect: two planned actions vanish from the accounting.
        rec = {"planned": 5, "added": 2, "skipped": 1}
        return RunContext(
            project="negative-control",
            plan_conservation={"per_category": {"pos": dict(rec)}, "total": dict(rec)},
        )

    if guard_name == "NO-EXTRA":
        # Seeded defect: a SECOND instance of a tool-owned-identity class,
        # allowlisted on purpose -- FR-102 says the allowlist must not rescue it.
        return RunContext(
            project="negative-control",
            extras=[{"class": "CmAgent", "id": "dup-1",
                     "tool_owned_duplicate": True, "allowlisted": True,
                     "traceable_to_source": False}],
        )

    if guard_name == "ACCESSOR-INTEGRITY":
        # Seeded defect: an accessor that could not read an identifier.
        counters = {c: 0 for c in ACCESSOR_COUNTERS}
        counters["unreadable_identifiers"] = 3
        counters["failed_accessors"] = ["ILexEntryRepository.AllInstances"]
        return RunContext(project="negative-control", accessor_counters=counters)

    if guard_name == "HANDLE-INTEGRITY":
        # Seeded defect: a project handle that failed to reopen.
        return RunContext(
            project="negative-control",
            handle_operations=[{"operation": "reopen", "ok": False,
                                "error_type": "FdoDataMigrationException",
                                "error_message": "seeded control failure"}],
        )

    if guard_name == "NO-TRUNCATION":
        # Seeded defect: the durable artifact omitted drop-reason buckets.
        return RunContext(
            project="negative-control",
            truncation={"dropped_breakdown_omitted": 3, "detail_omitted": 0},
        )

    if guard_name == "ARTIFACT-INTEGRITY":
        # Seeded defect: a corpus project with no artifact at all.
        return RunContext(
            project="negative-control",
            corpus_projects=["Ejagham Mini", "Esperanto"],
            artifacts_present={"Ejagham Mini": dict(_COMPLETE_ARTIFACT_RECORD)},
        )

    if guard_name == "NO-ENGINE-BUG-AS-LOSS":
        # Seeded defect: a drop reason leaking an internal task identifier.
        return RunContext(
            project="negative-control",
            drop_reasons=["skipped pending TODO(035-verdict-taxonomy)"],
            engine_bug_signatures=_CONTROL_ENGINE_BUG_ROSTER,
        )

    if guard_name == "CLEAN-CLOSE":
        # Seeded defect: a close that timed out before a later census.
        return RunContext(
            project="negative-control",
            close_operations=[{"operation": "close", "ok": False, "timed_out": True,
                               "error_message": "seeded control timeout",
                               "followed_by": ["census_2"]}],
        )

    raise ValueError("no seeded defect is defined for guard %r" % (guard_name,))


#: One-line description of each seeded defect, recorded in the artifact so a
#: reader can see WHAT was seeded without re-reading the code.
SEEDED_DEFECT_DESCRIPTIONS: dict[str, str] = {
    "BASELINE-DELTA": "first transfer changed nothing while 10 actions were planned",
    "COMPARISONS-PERFORMED": "a category with 5 source objects performed 0 comparisons",
    "CATEGORY-COVERAGE": "an enabled category was never measured and never recorded as excluded",
    "TOTAL-ACCOUNTING": "drop one source object with no allowlist entry",
    "EMPTY-CORROBORATION": "an empty source measurement with no independent corroborating count",
    "UNHANDLED-SUBTYPE": "an unhandled subtype reduced to a value that compares equal",
    "IDEMPOTENCY-IN-WRITTEN-CLASSES": "the second transfer added a new object in a written class",
    "PLAN-CONSERVATION": "5 planned actions accounted for as 2 added + 1 skipped",
    "NO-EXTRA": "a second instance of a tool-owned-identity class, allowlisted on purpose",
    "ACCESSOR-INTEGRITY": "an accessor reporting 3 unreadable identifiers",
    "HANDLE-INTEGRITY": "a project handle that failed to reopen",
    "NO-TRUNCATION": "the durable artifact omitted 3 drop-reason buckets",
    "ARTIFACT-INTEGRITY": "a corpus project with no artifact written",
    "NO-ENGINE-BUG-AS-LOSS": "a drop reason leaking an internal task identifier",
    "CLEAN-CLOSE": "a project close that timed out before a later census",
}


@dataclass
class NegativeControlOutcome:
    """One guard's demonstration. ``unfalsifiable`` is FR-181's finding: the
    seeded defect did not make the guard fail, which is a defect in the SWEEP,
    never evidence that the guard is robust."""

    guard: str
    seeded_defect: str
    result: str
    verdict_produced: str
    guard_module_hash: str
    unfalsifiable: bool = False
    message: str = ""

    def as_record(self, recorded_at: str) -> dict:
        """rosters.md section 8 record shape."""
        return {
            "guard": self.guard,
            "seeded_defect": self.seeded_defect,
            "verdict_produced": self.verdict_produced,
            "guard_module_hash": self.guard_module_hash,
            "recorded_at": recorded_at,
        }


def run_negative_controls(
    registry: Optional[dict] = None,
) -> tuple[NegativeControlOutcome, ...]:
    """FR-178/FR-179: run one seeded defect per guard and record what happened.

    FR-181: a guard whose seeded defect does NOT produce a failure is reported
    as ``unfalsifiable`` rather than quietly recorded as demonstrated.
    """
    registry = GUARD_REGISTRY if registry is None else registry
    out = []
    for guard_name in GUARD_NAMES:
        fn = registry[guard_name]
        ctx = _seeded_context(guard_name)
        res = fn(ctx)
        unfalsifiable = res.result != "fail"
        out.append(NegativeControlOutcome(
            guard=guard_name,
            seeded_defect=SEEDED_DEFECT_DESCRIPTIONS[guard_name],
            result=res.result,
            verdict_produced=GUARD_FAILURE_VERDICT[guard_name],
            guard_module_hash=guard_module_hash(guard_name),
            unfalsifiable=unfalsifiable,
            message=res.message,
        ))
    return tuple(out)


def write_negative_controls(
    outcomes: Sequence[NegativeControlOutcome],
    *,
    path: Optional[Path] = None,
    contracts_dir: Optional[Path] = None,
    recorded_at: str,
) -> Path:
    """Write the durable, tracked negative-control artifact (FR-180).

    ADDITIVE across phases: T044/T045 append the field-plane guards' controls
    to this same file, so existing records for guards not in ``outcomes`` are
    preserved and a re-run replaces only its own guards' records.

    ``recorded_at`` is passed in rather than read from the clock so the writer
    stays deterministic and testable.
    """
    if path is None:
        base = DEFAULT_CONTRACTS_DIR if contracts_dir is None else Path(contracts_dir)
        path = base / NEGATIVE_CONTROLS_NAME
    path = Path(path)

    existing = {}
    if path.exists():
        try:
            prior = json.loads(path.read_text(encoding="utf-8"))
            for rec in prior.get("controls", []):
                if rec.get("guard"):
                    existing[rec["guard"]] = rec
        except (ValueError, OSError):
            existing = {}

    for outcome in outcomes:
        existing[outcome.guard] = outcome.as_record(recorded_at)

    payload = {
        "schema_version": 1,
        "controls": [existing[k] for k in sorted(existing)],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path
