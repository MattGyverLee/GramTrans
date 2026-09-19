"""Feature 035 -- full-corpus, double-Move fidelity sweep (EXECUTABLE SKELETON).

Standalone CLI. NOT a plugin-host module; run it directly with
``python debug/run_fullcopy_sweep.py ...``.

THIN CLI ENTRY POINT (T008, specs/035-fullsweep-fidelity/tasks.md Phase 1):
this file used to hold the sweep's six mechanical implementation groups
directly; they have been promoted, unchanged, into the ``debug/fullsweep``
package (see ``debug/fullsweep/__init__.py`` for the map). What remains here:

  * the per-project double-move loop (``run_one_project``), wiring Groups
    B/D/K together for exactly one project;
  * plane 1, the object-level reconciliation (``reconcile_project_objects``),
    a thin adapter over ``fullsweep.compare.reconcile_objects``;
  * the measurement-to-guard wiring (``build_run_context``,
    ``MEASURABLE_RUN_CONTEXT_FIELDS``, ``UNMEASURED_RUN_CONTEXT_FIELDS``);
  * the CLI itself (``list`` / ``project`` / ``batch`` subcommands), with
    every existing flag spelling preserved exactly.

SCOPE UPDATE, 2026-08-19 (T045a). The verdict taxonomy is no longer in review:
the ratified spec settled Groups E/F/G/H and Group P, ``fullsweep.compare``
implements both accounting planes (T031, T036-T043), and ``fullsweep.guards``
carries real pass/fail logic for all fifteen guards (T033). The
``compare_objects`` stub that stood in for that taxonomy is GONE -- it emitted
one ``NOT_YET_CLASSIFIED_MISSING_FROM_TARGET`` row per absent GUID and populated
no accounting block, so TOTAL-ACCOUNTING could only report ``not-evaluated``.

The one thing still missing is plane 2's LIVE FIELD READ: ``census.census_fields``
needs a ``field_source(cls, guid)`` over live LCM objects before ``comparisons``
and ``measured_categories`` can be measured. Until that lands, this driver's
payload comparator is ``payload_never_compared``, which returns None for every
object -- and FR-097 makes "present under a matching identity with no payload
comparison performed" unexplained loss, so those objects are REPORTED as
unverified rather than assumed equal. See ``UNMEASURED_RUN_CONTEXT_FIELDS`` for
the full, per-field list of what is still unmeasured and why.

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
    ``run_full_transfer``. This driver resolves its exclusion set ONCE, into
    ``GrammarCategory`` MEMBERS (``resolve_excluded_categories``), and hands the
    same set to the recorded selection AND to both transfers. It never relies on
    ``full_run``'s own STEMS-excluding default: the user has explicitly decided
    stems are required for this sweep (FR-134), and an exclusion expressed as a
    default argument is what FR-135 forbids. The resulting coverage set is
    recorded in every artifact (Group K, FR-142).

    Before T045a this comment was accurate about intent and wrong about
    behaviour twice over -- see ``resolve_excluded_categories`` for both defects.
  * ``debug/audit_guid_preservation.py`` -- the ``AllInstances`` identity-keyed
    inventory shape (``{class_name: {guid, ...}}``), reused here as
    ``census_project``.

WRITE SAFETY (Group B) is the highest-severity section of this driver's
dependency package. See ``debug.fullsweep.safety.assert_destination_safe`` --
the single choke-point every restore call and every write-enabled-open call
in this driver goes through, computed fresh from the literal value about to
be used, never cached or inherited from an enumeration helper
(FR-013/FR-014/FR-015).

NO SILENT ANYTHING (per the dispatch brief): every recorded exception below
carries its ``traceback.format_exc()``; there is no bare ``except: pass`` in
this file; a project's per-project artifact is written even on an unhandled
failure (best-effort, itself never silently swallowed); the driver's exit
code is non-zero if anything failed.

ASCII-only console output (Windows-terminal safe).
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Optional, Sequence

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "src", _ROOT / "tests" / "integration", _ROOT / "debug"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from debug.fullsweep import *  # noqa: F401,F403,E402 -- the package's public surface

VALID_RUN_INTENTS = ("baseline", "gate")

# ---------------------------------------------------------------------------
# T024 CLI surface constants (contracts/sweep-cli.md)
# ---------------------------------------------------------------------------

#: CHANGED DEFAULT (research D-10): per-run result artifacts are EVIDENCE, not
#: reviewed source, so they move out of the tracked spec folder into the
#: gitignored runtime dir. What stays tracked is exactly what FR-149 names --
#: the driver, the rosters, the allowlist, the capability fingerprint, the
#: negative-control artifact and the ledger.
DEFAULT_ARTIFACTS_DIR = DEFAULT_RUNTIME_DIR / "artifacts"

#: FR-149 tracked inputs.
DEFAULT_CONTRACTS_DIR = _ROOT / "specs" / "035-fullsweep-fidelity" / "contracts"
DEFAULT_LEDGER_PATH = _ROOT / "specs" / "035-fullsweep-fidelity" / "ledger.json"

#: ``--diagnostic-level`` is set explicitly and recorded; it is NEVER
#: setdefault-ed from the environment, because a level silently inherited
#: from an operator's shell makes two runs incomparable while both look
#: configured.
DIAGNOSTIC_LEVELS = ("quiet", "normal", "verbose")


# ===========================================================================
# CATEGORY RESOLUTION (T045a part a -- FR-134, FR-135, FR-136)
# ===========================================================================

def resolve_excluded_categories(spec: Sequence[str]) -> tuple:
    """Turn ``--exclude-categories`` strings into ``(members, records)``.

    ``members`` is a frozenset of ``GrammarCategory`` MEMBERS, which is what
    ``build_full_selection`` compares against. ``records`` is the FR-135 field:
    one ``{"category": value, "reason": str}`` per exclusion.

    TWO DEFECTS THIS FUNCTION EXISTS TO CLOSE, both live before T045a:

    1. ``run_one_project`` built its exclusion as ``frozenset(exclude_categories)``
       -- a set of *strings* -- and passed it to ``build_full_selection``, whose
       body tests ``if cat not in exclude`` against enum MEMBERS. A string never
       equals a member, so the exclusion was a silent no-op: the recorded
       ``coverage_categories`` always listed every category no matter what the
       operator asked to exclude.
    2. ``run_full_transfer`` then built its OWN selection with no arguments,
       inheriting ``build_full_selection``'s STEMS-excluding default. So the
       transfer excluded STEMS while the artifact claimed STEMS was covered --
       FR-136's "MUST NOT allow a reader to mistake" defect, in the strongest
       form available: the artifact described a run that did not happen.

    An unknown category name RAISES. Ignoring it is how (1) stayed invisible for
    a whole live batch, and FR-135's "explicit, recorded" cannot be satisfied by
    a name the harness silently discarded.

    A reason may be attached as ``NAME=reason``. Supplying none leaves the reason
    empty, which makes CATEGORY-COVERAGE FAIL rather than pass -- FR-135 requires
    every exclusion to be explicit, and "the operator did not say why" is a
    recorded fact, not a detail to fill in on their behalf.
    """
    from gramtrans.Lib.models import GrammarCategory

    by_value = {c.value: c for c in GrammarCategory}
    by_name = {c.name: c for c in GrammarCategory}
    members, records, unknown = set(), [], []
    for raw in spec or ():
        token = str(raw).strip()
        if not token:
            continue
        name, _, reason = token.partition("=")
        name, reason = name.strip(), reason.strip()
        member = by_value.get(name) or by_name.get(name.upper())
        if member is None:
            unknown.append(name)
            continue
        members.add(member)
        records.append({"category": member.value, "reason": reason})
    if unknown:
        raise HarnessError(
            "[FR-135] --exclude-categories names %r, which are not "
            "GrammarCategory members. A name the harness cannot resolve is "
            "silently NOT excluded, so the artifact would record coverage the "
            "run did not have. Valid values: %s"
            % (sorted(unknown), ", ".join(sorted(by_value)))
        )
    return frozenset(members), records


def plan_conservation_counters(plan, report) -> dict:
    """FR-101's per-category and total counters, read off the plan and report.

    ``planned`` is counted from the PLAN's own action rows, and ``added`` /
    ``skipped`` from the REPORT's per-category record -- two independent
    surfaces, which is the point: a conservation check that read both sides from
    the same object could not detect a discrepancy.

    Every other counter the report carries travels through untouched.
    ``guards.PLAN_ACCOUNTED_COUNTERS`` decides which ones close the identity and
    reports the rest in its evidence, so widening the formula stays a deliberate
    edit there rather than a quiet reshaping here.
    """
    def _cat(x):
        c = getattr(x, "category", None)
        return getattr(c, "value", None) or str(c)

    planned_by_cat: dict = {}
    for action in getattr(plan, "actions", ()) or ():
        key = _cat(action)
        planned_by_cat[key] = planned_by_cat.get(key, 0) + 1

    per_category: dict = {}
    for category, rec in (getattr(report, "per_category", {}) or {}).items():
        key = getattr(category, "value", None) or str(category)
        row = {"planned": planned_by_cat.get(key, 0)}
        for counter in ("added", "skipped", "closure_pulled_in", "overwritten",
                        "excluded_lossy", "interactive_resolved", "interactive_skipped"):
            row[counter] = int(getattr(rec, counter, 0) or 0)
        per_category[key] = row
    # A category the plan planned for but the report never mentioned still has
    # to be accounted for; omitting it would hide the very gap FR-101 checks.
    for key, planned in planned_by_cat.items():
        per_category.setdefault(key, {"planned": planned, "added": 0, "skipped": 0})

    total = {"planned": sum(r["planned"] for r in per_category.values())}
    for counter in ("added", "skipped", "closure_pulled_in", "overwritten",
                    "excluded_lossy", "interactive_resolved", "interactive_skipped"):
        total[counter] = sum(r.get(counter, 0) for r in per_category.values())
    return {"per_category": per_category, "total": total}


def observed_drop_reasons(drops_block: dict) -> list:
    """Every drop reason the engine reported, across both transfers.

    NO-ENGINE-BUG-AS-LOSS matches its roster against these. Duplicates are kept:
    the guard counts matches, and collapsing identical reasons would understate
    how many objects an engine-bug signature actually claimed.
    """
    reasons: list = []
    for phase in ("first", "second"):
        block = (drops_block or {}).get(phase) or {}
        for record in block.get("records") or ():
            reason = record.get("reason")
            if reason:
                reasons.append(reason)
    return reasons


# ===========================================================================
# PLANE 1 -- OBJECT-LEVEL RECONCILIATION (T045a part b)
#
# This replaces the ``compare_objects`` stub. The stub emitted one
# ``NOT_YET_CLASSIFIED_MISSING_FROM_TARGET`` finding per absent source GUID and
# populated no accounting block at all, so TOTAL-ACCOUNTING could only ever
# report ``not-evaluated``. Its TODO said the verdict taxonomy was still in
# review; the ratified spec settled it, and ``fullsweep.compare.reconcile_objects``
# implements it (T031).
#
# FR-091 is the load-bearing ordering here: the WALK detects loss, and drop
# records only ever EXPLAIN it. So the reconciliation is driven by the source
# census, and ``drops`` is consulted only once an object is already known to be
# absent -- never the other way round.
# ===========================================================================

#: FR-097 requires a payload comparison for every object present under a
#: matching identity. Plane 2 (the field census) is what performs it; until it is
#: wired, NO comparison happens, and this callback says so by returning None for
#: every object rather than a cheerful True.
#:
#: ``reconcile_objects`` turns None into
#: ``unaccounted: present-under-matching-identity-but-never-compared``, which
#: fails TOTAL-ACCOUNTING. That is the correct reading of FR-097 -- "an object
#: merely present under a matching identity with no payload comparison performed
#: ... is unexplained loss and MUST fail the run" -- and it is a far more useful
#: answer than the stub's silence, because it names how many objects are
#: unverified instead of implying there are none.
def payload_never_compared(class_name: str, source_id: str, target_id: str):
    """The honest no-op payload comparator: no comparison was performed."""
    return None


def drop_records_from_artifact(drops_block: dict) -> tuple:
    """Rebuild ``compare.DropRecord``s from the artifact's recorded drop channel.

    Keyed on ``item_guid``, not ``item_name``: ``reconcile_objects`` matches a
    drop against a source IDENTIFIER, and a label would match nothing (or, worse,
    the wrong object -- labels are not unique).
    """
    out: list = []
    for phase in ("first", "second"):
        block = (drops_block or {}).get(phase) or {}
        for record in block.get("records") or ():
            item = record.get("item_guid")
            if not item:
                # An unidentified drop cannot be attributed to a source object.
                # It is still evidence, and ``observed_drop_reasons`` still feeds
                # it to NO-ENGINE-BUG-AS-LOSS; it simply cannot explain a
                # specific absence, which is a fact about the engine's record,
                # not something to paper over with a synthetic identifier.
                continue
            out.append(DropRecord(
                owner=str(record.get("owner_guid") or ""),
                field_name=str(record.get("field_name") or ""),
                item=str(item).lower(),
                reason=str(record.get("reason") or ""),
            ))
    return tuple(out)


def findings_from_accounting(accounting) -> list:
    """FR-145 finding rows for every object the reconciliation could not explain.

    One row per unaccounted object, carrying the bucket's own detail string as
    the verdict -- so a reader sees WHICH of FR-097's failure modes applied
    (dropped-with-no-allowlist-entry, present-but-never-compared, absent-with-no-
    explanation, over-cap) instead of the stub's single undifferentiated token.
    """
    findings: list = []
    for item in accounting.unaccounted:
        findings.append({
            "class": item.class_name,
            "category": None,
            "field": None,
            "source_value": item.source_id,
            "target_value": item.target_id,
            "verdict": item.detail or UNACCOUNTED_ABSENT_NO_EXPLANATION,
            "guid": item.source_id,
        })
    return findings


#: Every ``RunContext`` field ``run_one_project`` is able to measure today, and
#: therefore every field ``build_run_context`` will pass through. A field NOT on
#: this tuple is one no per-project measurement exists for yet; it stays None and
#: its guard reports ``not-evaluated``.
#:
#: This tuple is the deliberate, reviewable line between "measured" and "not
#: measured". Adding a name here without also depositing it into ``measured`` is
#: harmless (absent key -> None -> not-evaluated); depositing a key that is NOT
#: named here is a defect, and ``build_run_context`` raises on it rather than
#: silently discarding a measurement the run paid for.
MEASURABLE_RUN_CONTEXT_FIELDS: tuple = (
    "census_baseline",
    "census_after_first",
    "census_after_second",
    "written",
    "idempotency",
    "planned_action_count",
    "plan_conservation",
    "accounting",
    "enabled_categories",
    "measured_categories",   # plane 2, deposited since T045a(c)
    "excluded_categories",
    "comparisons",           # plane 2, deposited since T045a(c)
    "drop_reasons",
    "engine_bug_signatures",
)

#: WAS "named measurable but not yet deposited". T045a(c) deposits both: the
#: live field read (``fieldplane.gather_field_plane_side`` ->
#: ``census.census_fields`` with ``field_dispatch.build_field_source``) now
#: runs inside ``run_one_project``, and its per-class counters are projected
#: onto categories through ``coverage.project_comparisons_to_categories``.
#:
#: The tuple is KEPT, and kept EMPTY, deliberately: it is the place a future
#: "measurable in principle, not deposited yet" field goes, and deleting it
#: would make the next such field's absence invisible again.
PENDING_PLANE_2_FIELDS: tuple = ()

#: The guard inputs ``run_one_project`` has NO measurement for, with the reason.
#: Recorded here, in code, so "why is this run still VACUOUS?" has a written
#: answer instead of requiring an archaeology session through fifteen guards.
UNMEASURED_RUN_CONTEXT_FIELDS: dict = {
    "empty_measurements": "plane 2 has to record, per empty source collection, "
                          "which of FR-098's two distinct outcomes applied and "
                          "the independent corroborating count",
    "unhandled_subtypes": "plane 2 has to name and count each subtype the engine "
                          "did not handle (FR-099)",
    "extras": "the reverse walk -- target objects absent from the source, with "
              "traceable_to_source and tool_owned_duplicate decided per object "
              "(FR-102/FR-183)",
    "accessor_counters": "audit_guid_preservation.inventory_all currently "
                         "swallows a per-object read failure with "
                         "`except Exception: continue`, so the four FR-103 "
                         "counters are not merely unmeasured -- they are "
                         "actively discarded at the point they occur",
    "handle_operations": "no project-handle operation log exists (FR-104)",
    "truncation": "the durable artifact writer keeps no omission counters, so "
                  "FR-105's two zeros cannot be asserted -- and hardcoding them "
                  "to 0 would be a claim, not a measurement",
    "close_operations": "CloseProject outcomes are not logged; both inventory_all "
                        "and run_full_transfer close inside a bare except "
                        "(FR-108)",
    "corpus_projects": "corpus-level, not per-project: only the batch driver "
                       "knows the frozen project list (FR-106)",
    "artifacts_present": "corpus-level, as above -- an artifact index over the "
                         "whole run",
}


def build_run_context(project: str, measured: dict) -> RunContext:
    """Build the guard context from what this run ACTUALLY measured.

    The one rule: a key present in ``measured`` is passed through; a key absent
    keeps ``RunContext``'s ``None`` default and its guard reports
    ``not-evaluated``. Nothing here substitutes an empty container for a missing
    measurement -- per ``RunContext``'s docstring, an empty accessor-counter dict
    would let ACCESSOR-INTEGRITY report all-zeros and pass a project it never
    opened.

    A key that is not a known measurable field raises. Silently dropping it would
    reproduce, one level up, exactly the bug this function was written to fix: a
    measurement taken and then never handed to the guard that needed it.
    """
    unknown = sorted(set(measured) - set(MEASURABLE_RUN_CONTEXT_FIELDS))
    if unknown:
        raise HarnessError(
            "[FR-109] %r were measured but are not named in "
            "MEASURABLE_RUN_CONTEXT_FIELDS, so no guard would ever see them. "
            "Add them to that tuple (and check the field spelling against "
            "guards.RunContext) rather than letting the measurement be "
            "discarded." % (unknown,)
        )
    return RunContext(
        project=project,
        **{k: v for k, v in measured.items()},
    )


def reconcile_project_objects(
    source_inventory: dict,
    target_before: dict,
    target_after: dict,
    *,
    project: str,
    drops: Sequence = (),
    matcher=None,
    roster=None,
    remap=None,
    payload_equal: Callable = payload_never_compared,
):
    """Plane 1 for one project: ``(ObjectAccounting, findings)``.

    Thin on purpose. Every rule lives in ``fullsweep.compare.reconcile_objects``
    and ``fullsweep.identity``; this function only supplies the project's
    measurements and shapes the findings list the artifact carries.
    """
    accounting = reconcile_objects(
        source_inventory, target_before, target_after,
        project=project, payload_equal=payload_equal,
        roster=roster, remap=remap, matcher=matcher, drops=drops,
    )
    return accounting, findings_from_accounting(accounting)


# ===========================================================================
# PLANE 2, WIRED (T045a part c -- FR-051/FR-052/FR-066, FR-069..FR-090, FR-189)
# ===========================================================================

def build_field_plane(
    artifact,
    *,
    source_name: str,
    target_name: str,
    contracts_dir: Path,
    gather_side: Callable,
    ws_mapping_mode: str,
    max_objects_per_class: Optional[int],
    natural_key_roster,
    drops: Sequence = (),
):
    """Read both projects' field planes and return the payload comparator
    ``reconcile_objects`` will call -- or ``None``, with the reason recorded.

    A failure here is recorded and NOT re-raised. That is deliberate and it is
    not the "no silent anything" rule bending: the failure lands in
    ``artifact.errors`` with its traceback AND in ``artifact.field_plane`` with
    ``measured: false``, and its consequence is that ``comparisons`` /
    ``measured_categories`` stay absent from ``measured``, so their guards
    report ``not-evaluated`` and FR-109 sinks the run to ``VACUOUS``. Aborting
    instead would throw away the plane-1 reconciliation, the drop channel and
    the idempotency measurement this run already paid for -- less evidence,
    and the same verdict.
    """
    record: dict = {"measured": False, "mode": ws_mapping_mode,
                    "max_objects_per_class": max_objects_per_class, "error": ""}
    try:
        divergent = load_expected_divergent(
            Path(contracts_dir) / "expected-divergent.json")
        cmap = load_class_category_map(
            Path(contracts_dir) / CLASS_CATEGORY_MAP_NAME)
        source_side = gather_side(source_name, roster=divergent,
                                  max_objects_per_class=max_objects_per_class)
        target_side = gather_side(target_name, roster=divergent,
                                  max_objects_per_class=max_objects_per_class)
        ws_mapping = build_ws_mapping_for_mode(
            ws_mapping_mode,
            source_tags=source_side.ws_tags,
            target_tags=target_side.ws_tags,
            source_default_vernacular=source_side.default_vernacular,
            target_default_vernacular=target_side.default_vernacular,
        )
        # Both sides' holes, kept apart by side: "the source class could not be
        # read" and "the target class could not be read" have different causes
        # and different fixes, and a merged list hides which one happened.
        unreadable = {c: "source: %s" % why
                      for c, why in source_side.unreadable_classes.items()}
        for cls, why in target_side.unreadable_classes.items():
            if cls in unreadable:
                unreadable[cls] = unreadable[cls] + " | target: %s" % why
            else:
                unreadable[cls] = "target: %s" % why
        comparator = FieldPlaneComparator(
            source_census=source_side.census,
            target_census=target_side.census,
            ws_mapping=ws_mapping,
            source_ws_keys=source_side.ws_keys,
            target_ws_keys=target_side.ws_keys,
            source_handle_to_tag=source_side.handle_to_tag,
            target_handle_to_tag=target_side.handle_to_tag,
            target_ws_tags=target_side.ws_tags,
            natural_key_roster=natural_key_roster,
            # FR-085: no identity-remap record is produced on this path yet, so
            # a link whose owning class is on the natural-key roster is REFUSED
            # rather than resolved by identifier comparison, which that rule
            # forbids outright. The refusal is counted and published.
            remap_record=None,
            drops=drops,
            category_for=cmap.categories_for,
            unreadable_classes=unreadable,
            source_side=source_side,
            target_side=target_side,
            class_category_map=cmap,
        )
        record.update({
            "measured": True,
            "writing_system_mapping": ws_mapping.as_dict(),
            "source": source_side.as_dict(),
            "target": target_side.as_dict(),
        })
        artifact.writing_system_mapping = dict(
            {"mode": ws_mapping_mode}, **ws_mapping.as_dict())
        return comparator
    except Exception as exc:  # noqa: BLE001 -- recorded loudly, never swallowed
        record["error"] = "%s: %s" % (type(exc).__name__, exc)
        artifact.errors.append({
            "phase": "census_2", "error": record["error"],
            "traceback": traceback.format_exc(),
        })
        return None
    finally:
        artifact.field_plane = record


def record_plane_2_measurements(
    artifact,
    comparator,
    *,
    measured: dict,
    source_inventory: dict,
    contracts_dir: Path,
    excluded_records: Sequence[dict] = (),
    plane1_census_path: Optional[str] = None,
) -> None:
    """Put plane 2's output where the artifact and the guards read it.

    The CLASS plane and the CATEGORY plane are both written, from one
    measurement: ``artifact.comparisons`` keys on class (what was measured),
    ``RunContext.comparisons`` keys on category (what FR-095's guard reads).
    T045e's tracked join is the only bridge between them -- see the trap named
    in its task text: ``coverage.classify_coverage``'s own ``comparisons``
    parameter is a different object with the same name.
    """
    cmap = comparator.class_category_map
    performed, objects_compared = comparator.class_counters()
    known = set(cmap.class_names)
    source_objects = {c: len(v) for c, v in (source_inventory or {}).items()}

    # A class the run measured that the tracked join does not map cannot be
    # attributed to a category -- and ``project_comparisons_to_categories``
    # RAISES on one rather than dropping it. So the projection is fed the
    # mapped subset and the remainder is published by name, at the class
    # plane, where it does have a home.
    outside = sorted(set(performed) - known)
    projection = project_comparisons_to_categories(
        cmap,
        source_objects={c: n for c, n in source_objects.items() if c in known},
        comparisons_performed={c: n for c, n in performed.items() if c in known},
        objects_compared={c: n for c, n in objects_compared.items() if c in known},
    )
    measured["comparisons"] = projection["comparisons"]
    # FR-096: a category is MEASURED when at least one comparison was
    # performed in it -- not when it merely appears in the projection. A
    # category with source objects and zero comparisons is exactly what
    # COMPARISONS-PERFORMED exists to fail, and counting it as measured here
    # would hide that from CATEGORY-COVERAGE as well.
    measured["measured_categories"] = sorted(
        cat for cat, rec in projection["comparisons"].items()
        if rec.get("comparisons_performed", 0) >= 1
    )

    comparisons = comparator.comparisons_block()
    comparisons["category_projection"] = {
        k: v for k, v in projection.items() if k != "comparisons"
    }
    comparisons["per_category"] = projection["comparisons"]
    comparisons["classes_outside_class_category_map"] = outside

    floor = load_coverage_floor(Path(contracts_dir) / COVERAGE_FLOOR_NAME)
    coverage_report = classify_coverage(
        floor,
        survey=source_objects,
        comparisons=performed,
        findings_by_class=comparator.findings_by_class(),
        reachable_only_through_excluded=categories_reachable_only_through_excluded(
            cmap, [r.get("category") for r in (excluded_records or ()) if r.get("category")]),
        project=artifact.project,
    )

    census = census_block(
        field_census=comparator.source_side.census,
        cost={"source": comparator.source_side.cost,
              "target": comparator.target_side.cost},
        plane1_reference=(plane1_census_reference(plane1_census_path)
                          if plane1_census_path else None),
    )

    record_field_plane(
        artifact,
        comparisons=comparisons,
        link_findings=comparator.link_findings(),
        depth=depth_block(depth_results(comparator.source_side,
                                        comparator.target_side)),
        coverage=coverage_report.as_dict(),
        census=census,
    )
    # FR-145: the field plane's findings join the object plane's in the one
    # findings list a reader looks at. They carry ``field`` and a rule token,
    # which is what tells the two apart without a second list to remember.
    artifact.findings = list(artifact.findings) + comparator.value_findings()


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
    pinned_baseline,
    exclude_categories: Sequence[str],
    diagnostic_level: str,
    projects_root: Optional[str] = None,
    artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR,
    contracts_dir: Path = DEFAULT_CONTRACTS_DIR,
    reconciler: Callable = reconcile_project_objects,
    payload_equal: Callable = payload_never_compared,
    allowlist_matcher=None,
    natural_key_roster=None,
    tolerated_residue: Sequence[str] = (),
    ws_mapping_mode: str = WS_MODE_FULL,
    plane1_census_path: Optional[str] = None,
    max_objects_per_class: Optional[int] = None,
    gather_side: Callable = gather_field_plane_side,
) -> ProjectArtifact:
    """FR-043: restore -> census -> Move #1 -> census -> Move #2 -> census ->
    restore, for exactly one project, with the write-safety choke point
    re-evaluated INDEPENDENTLY at each of FR-013's two boundaries (never
    cached, never inherited).

    ``pinned_baseline`` is a REQUIRED ``PinnedBaseline`` (T020): the restore
    goes through ``restore_from_pinned_baseline``, never through
    ``harness.restore_target``, so there is no newest-archive glob fallback
    on this path and every restored item's containment is proven before a
    byte is written.

    ``ws_mapping_mode`` (T045a(c)) is handed to BOTH transfers AND to the
    plane-2 comparison, from this one parameter, for the same reason the
    exclusion set is resolved once in T045a(a): a comparison made under a
    different writing-system mapping than the transfer used would report
    findings the run did not cause. It defaults to ``"full"`` -- every source
    writing system declared -- because this sweep is a FULL-copy sweep and
    FR-071 names the single-default-vernacular map as "the narrower default
    this exists to refuse". The chosen mode is recorded on every artifact
    (FR-135: never an invisible default argument).

    ``plane1_census_path`` points at feature 038's census artifact for this
    project. The artifact REFERENCES it by path and content hash (the 038
    cut); ``None`` records an absent reference WITH its reason rather than a
    silently missing block.

    ``max_objects_per_class`` caps the field census per class. ``None`` (the
    default) reads every object; any cap is an exclusion and is recorded as
    one.
    """
    if run_intent not in VALID_RUN_INTENTS:
        raise ValueError("run_intent must be one of %r" % (VALID_RUN_INTENTS,))
    if diagnostic_level not in DIAGNOSTIC_LEVELS:
        raise ValueError("diagnostic_level must be one of %r" % (DIAGNOSTIC_LEVELS,))
    if pinned_baseline is None:
        raise BaselineError(
            "[FR-170] run_one_project requires a pinned baseline. A run that "
            "cannot name and hash its baseline does not start."
        )

    from harness import full_run

    artifact = ProjectArtifact(
        project=source_name, run_intent=normalize_intent(run_intent), revision_pair=revision_pair(),
        dirty_gramtrans=None, coverage_categories=[], started_at=time.time(),
    )
    rp = artifact.revision_pair
    artifact.dirty_gramtrans = rp.get("gramtrans", {}).get("dirty")

    # T045a: resolved ONCE, here, and used for BOTH the recorded coverage set
    # and the transfer that actually runs. Resolving it twice is how the two
    # drifted apart (see resolve_excluded_categories).
    excluded_members, excluded_records = resolve_excluded_categories(exclude_categories)
    artifact.excluded_categories = [r["category"] for r in excluded_records]
    artifact.excluded_category_records = excluded_records
    artifact.diagnostic_level = diagnostic_level
    artifact.baseline = pinned_baseline.as_dict()
    if ws_mapping_mode not in WS_MODES:
        raise ValueError("ws_mapping_mode must be one of %r" % (WS_MODES,))
    artifact.writing_system_mapping = {"mode": ws_mapping_mode}

    # FR-024: the per-project record that each assertion was IN FACT
    # evaluated, at which boundary, against which literal values.
    ledger = AssertionLedger(project=source_name)

    # ---- T045a: the guard-input accumulator -----------------------------
    # The guards run in the ``finally`` below, so they must be able to read
    # whatever this run got as far as measuring -- including on a run that died
    # at the first transfer. Every measurement is deposited here the moment it is
    # taken; a key that never appears stays absent, and RunContext's own default
    # (None) then makes its guard report ``not-evaluated``.
    #
    # This dict is the WHOLE of T045a part (a). Before it, the finally block
    # called ``run_all_guards(RunContext(project=source_name))`` -- positionally
    # empty -- so all fifteen guards reported ``not-evaluated`` and FR-109 sank
    # every run to VACUOUS no matter how much it had measured. Batch 1 measured
    # the census triple, the written-class delta, idempotency and 210/27,929/879
    # drop reasons, and handed none of them to a single guard.
    measured: dict = {}

    # ---- T045a: the tracked rosters, read BEFORE any database is touched.
    # NO-ENGINE-BUG-AS-LOSS needs its signature roster; the reconciliation needs
    # the allowlist matcher and the natural-key roster. All three are read up
    # front so a malformed contract refuses the run instead of surfacing halfway
    # through a double move, with a target already written to.
    #
    # Note the deliberate asymmetry with the guard-input rule above: these
    # loaders RAISE on a missing or malformed file rather than yielding None. A
    # missing roster is not an unmeasured input -- it is a broken instrument, and
    # each loader's docstring says why treating it as "empty" would silently
    # change which losses count as explained.
    measured["engine_bug_signatures"] = load_engine_bug_signatures(
        contracts_dir=Path(contracts_dir))
    if allowlist_matcher is None:
        allowlist_matcher = LossAllowlistMatcher(
            entries=load_loss_allowlist(contracts_dir=Path(contracts_dir)))
    if natural_key_roster is None:
        natural_key_roster = NaturalKeyRoster.load(Path(contracts_dir))

    # FR-133..FR-137: allowlisting a structurally absent class is refused, and
    # refused HERE -- at load time, before a run can report a reduced-coverage
    # pass as a pass (T044).
    assert_allowlist_respects_floor(
        load_coverage_floor(Path(contracts_dir) / COVERAGE_FLOOR_NAME),
        {e.class_name for e in allowlist_matcher.entries if getattr(e, "class_name", None)},
    )

    root = resolve_projects_root(projects_root)
    target_path = str(root / target_name)

    src_fp_before = capture_fingerprint(source_name, projects_root)
    artifact.source_fingerprint_before = asdict(src_fp_before)
    flush_artifact(artifact, artifacts_dir)

    try:
        # ---- boundary (a): pinned, contained restore --------------------
        # assert_restore_boundary fires INSIDE restore_from_pinned_baseline,
        # before the archive is even opened and long before the first removal
        # (FR-023's load-bearing ordering).
        restored = restore_from_pinned_baseline(
            target_name, pinned=pinned_baseline, source_name=source_name,
            frozen_sources=frozen_sources, allowlist=allowlist,
            projects_root=projects_root, tolerated_residue=tolerated_residue,
            ledger=ledger,
        )
        artifact.restore_evidence = restored.as_dict()
        artifact.phases_completed.append("restore_initial")
        advance_phase(artifact, "restore", artifacts_dir)

        census_before = census_project(target_name)
        artifact.census_before = {k: sorted(v) for k, v in census_before.items()}
        measured["census_baseline"] = census_before
        artifact.phases_completed.append("census_before")
        flush_artifact(artifact, artifacts_dir)  # still within the "restore" phase (T013)

        # T045a: ONE selection object, built from the resolved enum members,
        # recorded here AND handed to both transfers below. Before this, the
        # recorded set and the executed set were computed independently and
        # disagreed (see resolve_excluded_categories).
        selection = full_run.build_full_selection(exclude=excluded_members)
        artifact.coverage_categories = sorted(c.value for c, on in selection.categories.items() if on)
        measured["enabled_categories"] = list(artifact.coverage_categories)
        measured["excluded_categories"] = excluded_records

        # ---- boundary (b): re-asserted immediately before the first byte
        # written beneath the target, computed fresh from the literal
        # target_name about to be used. An INDEPENDENT evaluation -- it
        # shares no flag with boundary (a) ------------------------------
        assert_first_write_boundary(
            target_name, source_name=source_name, frozen_sources=frozen_sources,
            allowlist=allowlist, projects_root=projects_root, ledger=ledger,
        )
        plan1, report1 = full_run.run_full_transfer(
            source_name, target_name, target_path, exclude=excluded_members,
            ws_mapping_mode=ws_mapping_mode)
        # FR-161/SC-005: the engine's drop channel is the ONLY place the two
        # historically dominant loss classes and the named residual list can be
        # read from. Recorded per transfer, before anything downstream can lose
        # the report object.
        artifact.drops["first"] = summarize_drops(report1)
        measured["planned_action_count"] = len(getattr(plan1, "actions", ()) or ())
        measured["plan_conservation"] = plan_conservation_counters(plan1, report1)
        measured["drop_reasons"] = observed_drop_reasons(artifact.drops)
        artifact.phases_completed.append("first_transfer")
        advance_phase(artifact, "transfer_1", artifacts_dir)

        census_after_1 = census_project(target_name)
        artifact.census_after_first = {k: sorted(v) for k, v in census_after_1.items()}
        measured["census_after_first"] = census_after_1
        artifact.phases_completed.append("census_after_first")
        advance_phase(artifact, "census_1", artifacts_dir)

        written = written_classes(census_before, census_after_1)
        artifact.written_classes = written
        measured["written"] = written

        assert_first_write_boundary(
            target_name, source_name=source_name, frozen_sources=frozen_sources,
            allowlist=allowlist, projects_root=projects_root, ledger=ledger,
        )
        plan2, report2 = full_run.run_full_transfer(
            source_name, target_name, target_path, exclude=excluded_members,
            ws_mapping_mode=ws_mapping_mode)
        artifact.drops["second"] = summarize_drops(report2)
        measured["drop_reasons"] = observed_drop_reasons(artifact.drops)
        artifact.phases_completed.append("second_transfer")
        advance_phase(artifact, "transfer_2", artifacts_dir)

        census_after_2 = census_project(target_name)
        artifact.census_after_second = {k: sorted(v) for k, v in census_after_2.items()}
        measured["census_after_second"] = census_after_2
        artifact.phases_completed.append("census_after_second")
        advance_phase(artifact, "census_2", artifacts_dir)

        idem = check_idempotency(census_after_1, census_after_2, written)
        artifact.idempotency = asdict(idem)
        measured["idempotency"] = idem
        if idem.harness_error:
            raise HarnessError(idem.harness_error)

        source_inventory = census_project(source_name)
        drop_records = drop_records_from_artifact(artifact.drops)

        # ---- plane 2: the FIELD plane (T045a part c) ---------------------
        # Built BEFORE the reconciliation because it IS the reconciliation's
        # payload comparator: ``reconcile_objects`` calls ``payload_equal``
        # for every pair it matched under an identity, and until this landed
        # the only comparator available was ``payload_never_compared``, which
        # answered None for all of them -- so every matched object was
        # reported "present-under-matching-identity-but-never-compared" and
        # ``comparisons`` / ``measured_categories`` were never measured at all.
        comparator = build_field_plane(
            artifact, source_name=source_name, target_name=target_name,
            contracts_dir=Path(contracts_dir), gather_side=gather_side,
            ws_mapping_mode=ws_mapping_mode,
            max_objects_per_class=max_objects_per_class,
            natural_key_roster=natural_key_roster, drops=drop_records,
        )

        # ---- plane 1: the object-level reconciliation (T045a part b) -----
        # FR-091: THIS walk detects loss. The drop channel recorded above is
        # consulted only to explain an absence the walk already found.
        if comparator is not None and payload_equal is payload_never_compared:
            # An explicitly injected comparator (tests, a caller that wants
            # plane 1 alone) still wins: substituting ours over the top would
            # make the parameter a lie.
            payload_equal = comparator.payload_equal
        accounting, findings = reconciler(
            source_inventory, census_before, census_after_2,
            project=source_name,
            drops=drop_records,
            matcher=allowlist_matcher, roster=natural_key_roster,
            payload_equal=payload_equal,
        )
        measured["accounting"] = accounting
        artifact.accounting = accounting.as_dict()
        assert_object_plane_only(artifact.accounting)   # FR-093: planes stay apart
        artifact.findings = findings

        # ---- plane 2's OUTPUT: onto the artifact, and into the guards -----
        if comparator is not None:
            record_plane_2_measurements(
                artifact, comparator, measured=measured,
                source_inventory=source_inventory,
                contracts_dir=Path(contracts_dir),
                excluded_records=excluded_records,
                plane1_census_path=plane1_census_path,
            )

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
        # on an unhandled failure. FR-172: recovery is idempotent per project
        # -- always restore, never resume mid-transfer.
        try:
            restored_final = restore_from_pinned_baseline(
                target_name, pinned=pinned_baseline, source_name=source_name,
                frozen_sources=frozen_sources, allowlist=allowlist,
                projects_root=projects_root, tolerated_residue=tolerated_residue,
                ledger=ledger,
            )
            artifact.restore_evidence_final = restored_final.as_dict()
            artifact.phases_completed.append("restore_final")
            artifact.phase_reached = "restore_final"
        except Exception as exc:  # noqa: BLE001 -- recorded, not swallowed
            artifact.errors.append({
                "phase": "restore_final", "error": "%s: %s" % (type(exc).__name__, exc),
                "traceback": traceback.format_exc(),
            })

        src_fp_after = capture_fingerprint(source_name, projects_root)
        artifact.source_fingerprint_after = asdict(src_fp_after)
        fp_verdict = classify_fingerprint_delta(src_fp_before, src_fp_after)
        artifact.fingerprint_verdict = fp_verdict
        if fp_verdict not in (FINGERPRINT_VERDICT_UNCHANGED, FINGERPRINT_VERDICT_MIGRATION):
            artifact.status = "failed"
            artifact.reason = ("SOURCE TAMPER GUARD: %s -- %s" % (fp_verdict, artifact.reason)).strip(" -")

        # ---- FR-024: the assertion record goes into the artifact, and both
        # FR-013 boundaries must have been independently evaluated. Recorded
        # BEFORE the check, so a run that failed the check still shows what
        # it did evaluate. -----------------------------------------------
        artifact.assertions = ledger.as_list()
        try:
            assert_both_boundaries_evaluated(ledger)
            artifact.assertions_complete = True
        except WriteSafetyError as exc:
            artifact.assertions_complete = False
            artifact.errors.append({
                "phase": artifact.phase_reached or "setup",
                "error": "%s: %s" % (type(exc).__name__, exc), "traceback": "",
            })
            artifact.status = "failed"
            artifact.reason = ("%s -- %s" % (exc, artifact.reason)).strip(" -")

        # ---- T016/T045a: wire measurements -> registry -> verdict -------
        # FR-109 meta-rule: asserted BOTH before the verdict is computed AND
        # again before the artifact is flushed.
        #
        # T045a: the context is built from ``measured``, so every guard whose
        # input this run actually took now reports pass or fail. Anything the run
        # did NOT measure is simply absent from the dict and keeps RunContext's
        # None default, which reports ``not-evaluated`` -- honestly. Handing a
        # guard an empty container instead would let it report all-zeros and pass
        # a project it never opened, which is the trap RunContext's own docstring
        # names and the reason the fields default to None rather than to {}.
        guard_results = run_all_guards(build_run_context(source_name, measured))
        artifact.guards = guard_block_as_dict(guard_results)
        artifact.guard_inputs_measured = sorted(measured)
        assert_guard_block_complete(artifact.guards)
        artifact.verdict = verdict_for_guard_results(guard_results)
        artifact.exit_code = exit_code_for(artifact.verdict)
        assert_guard_block_complete(artifact.guards)

        artifact.finished_at = time.time()
        flush_artifact(artifact, artifacts_dir)

    return artifact


# ===========================================================================
# CLI
# ===========================================================================

def _preflight_gate(args) -> Optional[int]:
    """FR-124/SC-008: performed ONCE at startup, BEFORE any restore or write.

    Returns an exit code when the run must refuse, or None to proceed. There
    is no third outcome: FR-132 forbids a best-effort degradation and FR-133
    forbids selecting a different runtime path around a mismatch.
    """
    result = run_preflight(Path(args.contracts_dir))
    if result.ok:
        return None
    print(format_diff_report(result, max_rows=getattr(args, "max_console_rows", None)))
    artifact_path = write_preflight_artifact(result, Path(args.artifacts_dir))
    print("[ARTIFACT] %s" % artifact_path)
    print("[REFUSED] capability preflight mismatch -- no project database was "
          "touched, no restore and no write attempted (SC-008).")
    return result.exit_code


def _pinned_baseline_from_args(args):
    """FR-170: build the pinned baseline from the caller's EXPLICIT --backup
    and --baseline-sha256. Absent both, the run has no baseline to pin and
    ``run_one_project`` refuses -- there is deliberately no fallback here
    that would select one."""
    if not getattr(args, "backup", None):
        return None
    return pin_baseline(args.backup, args.baseline_sha256)


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
        # T013/T016: a project this run never attempts (excluded from the
        # frozen admitted-source manifest) MUST STILL get a written
        # artifact naming it SKIPPED (FR-151/FR-188) -- never a bare CLI
        # error with nothing recorded to back it. No FLEx project is
        # opened on this path.
        reason = ("[FR-004/FR-006] %r is not in the frozen admitted-source "
                  "manifest -- no work attempted" % (args.source,))
        print("[SKIP] %s" % reason)
        artifact_path = write_skipped_artifact(
            args.source, reason=reason, run_intent=args.intent,
            artifacts_dir=Path(args.artifacts_dir),
        )
        print("[ARTIFACT] %s" % artifact_path)
        print("[RESULT] %s -> %s (verdict=VACUOUS, exit=%d)"
              % (args.source, STATUS_SKIPPED, exit_code_for("VACUOUS")))
        return exit_code_for("VACUOUS")
    allowlist = tuple(args.allowlist) if args.allowlist else DEFAULT_ALLOWLIST
    refused = _preflight_gate(args)
    if refused is not None:
        return refused
    try:
        artifact = run_one_project(
            args.source, target_name=args.target, frozen_sources=frozen,
            allowlist=allowlist, run_intent=args.intent,
            pinned_baseline=_pinned_baseline_from_args(args),
            exclude_categories=args.exclude_categories,
            diagnostic_level=args.diagnostic_level,
            projects_root=args.projects_root,
            artifacts_dir=Path(args.artifacts_dir),
            contracts_dir=Path(args.contracts_dir),
            ws_mapping_mode=args.ws_mapping_mode,
            plane1_census_path=args.plane1_census,
            max_objects_per_class=args.max_objects_per_class,
        )
    except (WriteSafetyError, SourceTamperError, EvidenceProvenanceError) as exc:
        # These MUST abort the whole run -- re-raise after making that loud.
        print("[ABORT-WHOLE-RUN] %s: %s" % (type(exc).__name__, exc))
        raise
    print("[RESULT] %s -> %s (verdict=%s, exit=%d)"
          % (args.source, artifact.status, artifact.verdict, artifact.exit_code))
    return artifact.exit_code


def compose_batch(frozen, ledger, *, only, batch_size, canary):
    """Decide WHICH sources this batch runs, and say where that came from.

    Two compositions, and the difference is recorded rather than inferred:

    * ``only`` -- FR-160: the caller dictates the batch, named source by named
      source, in the order given. Batch 1's composition is specified as exactly
      the three pilot projects with prior recorded historical results, so it
      must never be a by-product of corpus enumeration order or of whatever the
      ledger happens to hold. ``batch_size`` does NOT truncate an explicit
      composition -- a caller who names four sources and leaves the default
      size of three would otherwise silently measure three.
    * derived -- the ledger's not-yet-passed list, capped at ``batch_size``.

    ``canary`` is prepended when absent under EITHER composition: FR-159 wants
    it re-run in every batch regardless of its ledger status, and naming a
    composition is not a way around that. A no-op whenever the composition
    already contains it, as batch 1's does.

    Returns ``(batch, composition_label)`` and reads nothing but the ledger.
    """
    if only:
        batch = list(only)
        composition = "explicit (--only)"
    else:
        batch = [n for n in frozen if (ledger.get(n) or {}).get("status") != "passed"]
        if canary and canary not in batch:
            batch = [canary] + batch
        batch = batch[:batch_size]
        composition = "derived (ledger pending, size %d)" % batch_size
    if canary and canary not in batch:
        batch = [canary] + batch
    return batch, composition


def _cmd_batch(args) -> int:
    """Driver mode skeleton: admits a batch of --batch-size projects,
    running each as an isolated subprocess (FR-026), gated by the memory
    admission check (FR-028) and the concurrency-trial gate (FR-032). This
    skeleton runs workers SERIALLY when --workers=1 (the FR-031 default);
    it refuses to do otherwise without a recorded concurrency-trial
    artifact (assert_concurrency_gate_satisfied)."""
    refused = _preflight_gate(args)
    if refused is not None:
        return refused
    # FR-149: the driver, the capability expectation and the ledger this
    # verdict will depend on must be tracked and un-ignored BEFORE any work.
    assert_evidence_base_tracked({
        EVIDENCE_KIND_DRIVER: [Path(__file__).resolve()],
        EVIDENCE_KIND_CAPABILITY: [Path(args.contracts_dir) / "flexicon-capability.json"],
    })
    assert_concurrency_gate_satisfied(args.workers)
    corpus = enumerate_corpus(args.projects_root)
    frozen = freeze_source_manifest(corpus)
    allowlist = tuple(args.allowlist) if args.allowlist else DEFAULT_ALLOWLIST
    target_pool = default_target_pool(args.workers)
    assert_distinct_target_pool(target_pool, frozen)

    manifest_fp = capture_source_manifest(frozen, args.projects_root)
    print("[INFO] captured fingerprints for %d frozen sources" % len(manifest_fp))

    ledger = Ledger(Path(args.ledger))  # FR-149: tracked, not a runtime artifact
    batch, composition = compose_batch(
        frozen, ledger, only=args.only, batch_size=args.batch_size,
        canary=args.canary,
    )
    unknown = [n for n in batch if n not in frozen]

    print("[INFO] batch of %d, composition %s: %s"
          % (len(batch), composition, ", ".join(batch)))
    if unknown:
        # Not an abort: FR-151/FR-188 want every named-but-unattempted project
        # to reach a WRITTEN artifact saying SKIPPED, which the worker does.
        print("[WARN] not in the frozen admitted-source manifest, will be "
              "recorded SKIPPED rather than attempted: %s" % ", ".join(unknown))
    exit_code = 0
    for i, source in enumerate(batch):
        target = target_pool[i % len(target_pool)]
        row = next((e for e in corpus if e.project == source), None)
        try:
            assert_memory_admits_project(source, row.fwdata_mb if row else 0.0)
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
                "--contracts-dir", args.contracts_dir, "--ledger", args.ledger,
                "project", "--source", source, "--target", target, "--intent", args.intent,
                "--exclude-categories", ",".join(args.exclude_categories),
                "--diagnostic-level", args.diagnostic_level,
                "--ws-mapping-mode", args.ws_mapping_mode]
        if getattr(args, "max_objects_per_class", None) is not None:
            cmd += ["--max-objects-per-class", str(args.max_objects_per_class)]
        if args.backup:
            cmd += ["--backup", args.backup, "--baseline-sha256", args.baseline_sha256]
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


def _cmd_preflight(args) -> int:
    """T024/FR-124/SC-008: introspect the dependency against the pinned
    fingerprint and exit. Touches no database, performs no restore and no
    write. Exit 0 on match, 6 with a field-by-field diff on mismatch."""
    result = run_preflight(Path(args.contracts_dir))
    print(format_diff_report(result, max_rows=args.max_console_rows))
    artifact_path = write_preflight_artifact(result, Path(args.artifacts_dir))
    print("[ARTIFACT] %s" % artifact_path)
    return result.exit_code


class _ArgumentErrorExits5(argparse.ArgumentParser):
    """Contracts/sweep-cli.md, "Exit codes": there is no separate CLI-usage
    exit-code space. An argument error raises BEFORE any verdict exists and
    exits 5 (``HARNESS_ERROR``), since a run that could not be configured
    measured nothing.

    argparse's own default is exit 2, which collides with ``NON_IDEMPOTENT``
    -- a misconfigured invocation would otherwise be indistinguishable from a
    real second-transfer divergence in a batch driver reading exit codes.
    """

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("[HARNESS_ERROR] %s: %s\n" % (self.prog, message))
        raise SystemExit(exit_code_for("HARNESS_ERROR"))


def _split_categories(value: str) -> list:
    """``--exclude-categories`` is REQUIRED AND EXPLICIT, and may legitimately
    be EMPTY. An empty string therefore means "exclude nothing", stated
    deliberately -- never a default argument that silently excludes STEMS the
    way ``full_run.build_full_selection`` does on its own."""
    if value is None:
        raise argparse.ArgumentTypeError(
            "--exclude-categories must be given explicitly (pass '' to exclude "
            "nothing); it is never defaulted"
        )
    return [c.strip() for c in value.split(",") if c.strip()]


def _cmd_negative_controls(args) -> int:
    """T034: run the seeded-defect suite and write the durable negative-control
    artifact, stamping each guard's module content hash (FR-178..FR-181).

    Touches no database: every seeded defect is a hand-built ``RunContext``, so
    this subcommand is safe to run anywhere and needs no target project.
    """
    import datetime

    recorded_at = args.recorded_at or datetime.date.today().isoformat()
    outcomes = run_negative_controls()

    print("[INFO] seeded-defect suite: %d guard(s)" % len(outcomes))
    for o in outcomes:
        flag = "UNFALSIFIABLE" if o.unfalsifiable else "ok"
        print("  %-32s %-13s produced %-18s (%s)"
              % (o.guard, flag, o.verdict_produced, o.result))

    path = write_negative_controls(
        outcomes,
        contracts_dir=Path(args.contracts_dir),
        recorded_at=recorded_at,
    )
    print("[INFO] wrote %s" % path)

    # FR-181: a guard no constructible defect can fail is itself a defect in
    # the sweep. That is a harness error, not a passing run.
    unfalsifiable = [o.guard for o in outcomes if o.unfalsifiable]
    if unfalsifiable:
        print("[ERROR] %d guard(s) could not be made to fail by their seeded "
              "defect; per FR-181 this is a defect in the sweep, never evidence "
              "of robustness: %r" % (len(unfalsifiable), unfalsifiable))
        return exit_code_for("HARNESS_ERROR")
    print("[OK] every guard was demonstrated capable of failing")
    return 0


def main(argv=None) -> int:
    ap = _ArgumentErrorExits5(description=__doc__)
    ap.add_argument("--projects-root")
    ap.add_argument("--artifacts-dir", default=str(DEFAULT_ARTIFACTS_DIR),
                     help="per-run result artifacts (evidence, not reviewed source)")
    ap.add_argument("--runtime-dir", default=str(DEFAULT_RUNTIME_DIR))
    ap.add_argument("--allowlist", nargs="*", default=None,
                     help="anchored regex patterns; default: this sweep's own "
                          "Target[0-9]* pool only")
    # ---- T024 NEW globals -------------------------------------------------
    ap.add_argument("--contracts-dir", default=str(DEFAULT_CONTRACTS_DIR),
                     help="where the tracked rosters, allowlist and capability "
                          "fingerprint are read from")
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER_PATH),
                     help="the tracked per-project status ledger")
    ap.add_argument("--max-console-rows", type=int, default=None,
                     help="truncate CONSOLE listings only, always stating the "
                          "omitted count; the artifact never truncates (FR-144)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="enumerate the corpus")
    p_list.set_defaults(func=_cmd_list)

    p_preflight = sub.add_parser(
        "preflight", help="capability check: introspect the dependency against "
                          "the pinned fingerprint and exit (touches no database)")
    p_preflight.set_defaults(func=_cmd_preflight)

    p_project = sub.add_parser("project", help="worker mode: run one project")
    p_project.add_argument("--source", required=True)
    p_project.add_argument("--target", required=True)
    p_project.add_argument("--backup", default=None)
    p_project.add_argument("--baseline-sha256", default=None,
                            help="REQUIRED with --backup. A run that cannot name "
                                 "and hash its baseline does not start; there is "
                                 "no newest-archive glob fallback (FR-170)")
    p_project.add_argument("--intent", required=True, choices=VALID_RUN_INTENTS)
    p_project.add_argument("--exclude-categories", required=True,
                            type=_split_categories,
                            help="EXPLICIT, possibly empty (pass ''). A non-empty "
                                 "value forces COVERAGE_REDUCED")
    p_project.add_argument("--diagnostic-level", required=True,
                            choices=DIAGNOSTIC_LEVELS,
                            help="set explicitly and recorded; never setdefault "
                                 "from the environment")
    p_project.add_argument("--ws-mapping-mode", default=WS_MODE_FULL,
                            choices=WS_MODES, help="the writing-system mapping BOTH transfers run under and plane 2 compares under. 'full' declares every source writing system (mapped where the target has the tag, created where it does not); 'default-vernacular' declares only the source default vernacular, which FR-071 names as the narrower default it exists to refuse and which makes every other source writing system with content report unmapped-writing-system-with-no-skip-record")
    p_project.add_argument("--plane1-census", default=None, help="path to feature 038's census artifact for this project. The artifact REFERENCES it by path and sha256 content hash (the 038 cut); omitted records an absent reference with its reason, never a missing block")
    p_project.add_argument("--max-objects-per-class", type=int, default=None,
                            help='cap the field census at N objects per class. Omitted reads every object; any cap is an exclusion and is recorded as one on the artifact (FR-135)')
    p_project.set_defaults(func=_cmd_project)

    p_batch = sub.add_parser("batch", help="driver mode: admit and run one batch")
    p_batch.add_argument("--batch-size", type=int, default=3)
    p_batch.add_argument("--workers", type=int, default=1)
    p_batch.add_argument("--canary", default=CANARY_PROJECTS[0])
    p_batch.add_argument("--only", nargs="*", default=None, metavar="SOURCE",
                          help="FR-160: compose the batch from EXACTLY these "
                               "named sources, in this order, instead of "
                               "deriving it from the ledger's pending list. "
                               "--batch-size does not truncate it; --canary is "
                               "still prepended if absent (FR-159).")
    p_batch.add_argument("--intent", required=True, choices=VALID_RUN_INTENTS)
    p_batch.add_argument("--backup", default=None)
    p_batch.add_argument("--baseline-sha256", default=None)
    p_batch.add_argument("--exclude-categories", required=True,
                          type=_split_categories)
    p_batch.add_argument("--diagnostic-level", required=True,
                          choices=DIAGNOSTIC_LEVELS)
    p_batch.add_argument("--ws-mapping-mode", default=WS_MODE_FULL,
                          choices=WS_MODES, help="the writing-system mapping BOTH transfers run under and plane 2 compares under. 'full' declares every source writing system (mapped where the target has the tag, created where it does not); 'default-vernacular' declares only the source default vernacular, which FR-071 names as the narrower default it exists to refuse and which makes every other source writing system with content report unmapped-writing-system-with-no-skip-record")
    p_batch.add_argument("--max-objects-per-class", type=int, default=None,
                          help='cap the field census at N objects per class. Omitted reads every object; any cap is an exclusion and is recorded as one on the artifact (FR-135)')
    p_batch.set_defaults(func=_cmd_batch)

    p_controls = sub.add_parser(
        "negative-controls",
        help="run the seeded-defect suite and write the durable negative-control "
             "artifact, stamping each guard's module content hash (touches no "
             "database)")
    p_controls.add_argument("--recorded-at", default=None,
                            help="ISO date stamped onto each control record; "
                                 "defaults to today")
    p_controls.set_defaults(func=_cmd_negative_controls)

    args = ap.parse_args(argv)

    # FR-170: --baseline-sha256 is required WITH --backup. Enforced here rather
    # than by argparse because argparse has no native "required-with" relation;
    # routing it through ap.error() keeps the exit code at 5 (HARNESS_ERROR).
    if getattr(args, "backup", None) and not getattr(args, "baseline_sha256", None):
        ap.error("--baseline-sha256 is REQUIRED with --backup (FR-170: a "
                  "baseline is pinned by content hash by the caller; the sweep "
                  "never selects one by recency or directory scan)")

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
