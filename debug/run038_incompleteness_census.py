"""Feature 038 Phase 7 (US3) live driver -- T073.

WHAT THIS MEASURES. T070/T071 put the pulled-in dependencies in the plan and
made them refusable, and T071 wrote `ClosureEdge.deselected` -- 53 of 53 edges
under a full deselection. Nothing read it: `RunPlan.incompleteness`,
`RunReport.incompleteness`, `has_incomplete_items`,
`report._incompleteness_json` and the console's "Items arriving INCOMPLETE"
block all existed, wired to each other, fed by an empty tuple. FR-017 -- "when
a dependency is deselected or cannot be satisfied, every item left incomplete
as a result MUST be reported" -- was therefore unmet at the only surface a
linguist reads.

THIS DRIVER WRITES NOTHING. Every measurement is `preview_only=True`: FR-017
is a PLAN-TIME determination (Principle III -- Preview decides, Move obeys), so
the records exist before anything is written and can be measured without
writing. The target is still restored first, because "is this dependency
already in the destination" is one of the facts the records depend on, and a
target left in whatever state the last driver put it in makes that fact
unrepeatable.

FIVE MEASUREMENTS, source `Mbugwe LizzieHC practice` (read-only), target the
throwaway restored from a known backup:

  P0. NARROW (AFFIX_TEMPLATES-only), registry live, NOTHING deselected. The
      quiet case: every dependency is pulled in and satisfied, so a correct
      implementation reports nothing. An always-on warning is indistinguishable
      from no warning.

  P1. NARROW, every pulled-in GUID deselected -- T072's wizard wiring at full
      refusal. This is the headline: 53 edges, and the number of items that
      ARRIVE INCOMPLETE as a result.

  P2. NARROW, only the pulled-in PARTS OF SPEECH deselected. The two-hop case:
      the slots still arrive, and they arrive incomplete. P1 cannot show this
      (a deselected slot does not arrive at all) and it is the shape T069's
      census warned Phase 7 to expect.

  P3. FULL COPY, registry live. 0 edges, therefore 0 records. The regression
      guard: the mechanism that completes a narrow selection must change the
      case every existing caller uses by nothing at all.

  P4. THE SURFACES. For P1, does the record reach `RunReport.incompleteness`,
      `has_incomplete_items`, the snapshot JSON, and the console block?

Plus two accounting facts the records are only trustworthy with:

  * LABEL QUALITY -- how many records name their items ("Verb") rather than
    falling back to the ref ("gram_categories bbbbbbbb"). A record the reader
    cannot act on is not a report (SC-010).
  * ALREADY-IN-THE-DESTINATION -- how many P1 records name a dependency that
    P0 shows is ALREADY in the target. Those are OVER-reports: the reference
    resolves against the existing object, so the dependent is not incomplete.
    T073 cannot tell, because T071 (correctly) suppresses the deselected ref
    BEFORE its planner runs, so no `ALREADY_PRESENT_BY_*` skip exists to read.
    Measured here and filed as its own task rather than fixed inside this one.

Usage (no writes, but restores the throwaway target first):

    python debug/run038_incompleteness_census.py T093

T093 (2026-08-24) RE-RUNS THIS DRIVER AGAINST THE SAME PAIR to measure the
repair of the over-report the last bullet above filed, and writes its own
artifact -- `incompleteness-038-t093.json` -- rather than overwriting T073's.
Re-measuring a committed artifact in place is the drift T102 filed: the BEFORE
stops existing and every comparison against it turns red for a reason
unrelated to what it asserts. Passing `T073` therefore refuses to overwrite an
existing artifact unless `GT038_OVERWRITE_T073` is set.

`GT038_CENSUS_TARGET` / `GT038_CENSUS_SOURCE` override the projects.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "tests" / "integration"))

SOURCE = os.environ.get("GT038_CENSUS_SOURCE", "Mbugwe LizzieHC practice")
TARGET = os.environ.get("GT038_CENSUS_TARGET", "GT038 Closure Target")
BACKUP = _REPO / "backups" / "Target 2026-07-06 0218.fwbackup"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
_SNAPS = _REPO / "tests" / "integration" / "_snapshots"

#: The same narrow selection T069 and T070 measured, so the three artifacts
#: are directly comparable: AFFIX_TEMPLATES-only turns POSes and slots into
#: non-seeds, and a FULL COPY cannot observe a closure edge at all.
NARROW = "AFFIX_TEMPLATES"


def _only(category_name: str):
    from gramtrans.Lib.models import GrammarCategory
    keep = getattr(GrammarCategory, category_name)
    return frozenset(c for c in GrammarCategory if c is not keep)


def _cat(x):
    c = getattr(x, "category", None)
    return getattr(c, "value", None) or str(c)


def _tally(items):
    out: dict = {}
    for item in items or ():
        key = _cat(item)
        out[key] = out.get(key, 0) + 1
    return out


def _ref_key(pair) -> str:
    return getattr(pair[0], "value", str(pair[0])) + ":" + str(pair[1]).lower()


def _is_fallback_label(label, pair) -> bool:
    """Did `_pull_in_label` fail to find a Name and fall back to the ref?"""
    expected = (getattr(pair[0], "value", str(pair[0]))
                + " " + str(pair[1])[:8])
    return label == expected


def _incompleteness_summary(plan) -> dict:
    records = list(plan.incompleteness or ())
    by_cause: dict = {}
    by_pair: dict = {}
    fallback_labels = 0
    fallback_refs = set()
    for rec in records:
        by_cause[rec.cause] = by_cause.get(rec.cause, 0) + 1
        key = getattr(rec.incomplete_item[0], "value",
                      str(rec.incomplete_item[0]))
        row = by_pair.setdefault(key, {})
        dep = getattr(rec.missing_dependency[0], "value",
                      str(rec.missing_dependency[0]))
        row[dep] = row.get(dep, 0) + 1
        if _is_fallback_label(rec.incomplete_label, rec.incomplete_item):
            fallback_labels += 1
            fallback_refs.add(_ref_key(rec.incomplete_item))
        if _is_fallback_label(rec.missing_label, rec.missing_dependency):
            fallback_labels += 1
            fallback_refs.add(_ref_key(rec.missing_dependency))
    return {
        "records": len(records),
        "by_cause": by_cause,
        "by_category_pair": by_pair,
        "distinct_incomplete_items": len(
            {_ref_key(r.incomplete_item) for r in records}),
        "distinct_missing_dependencies": len(
            {_ref_key(r.missing_dependency) for r in records}),
        "every_record_has_a_consequence": all(r.consequence for r in records),
        "labels_total": 2 * len(records),
        "labels_falling_back_to_the_ref": fallback_labels,
        "distinct_refs_with_no_resolvable_name": sorted(fallback_refs),
        "sample": [
            {
                "incomplete": _ref_key(r.incomplete_item),
                "incomplete_label": r.incomplete_label,
                "missing": _ref_key(r.missing_dependency),
                "missing_label": r.missing_label,
                "cause": r.cause,
                "consequence": r.consequence,
            }
            for r in records[:3]
        ],
    }


def _closure_summary(plan) -> dict:
    by_kind: dict = {}
    for edge in plan.closure_edges or ():
        name = getattr(edge.kind, "name", str(edge.kind))
        row = by_kind.setdefault(name, {"edges": 0, "deselected": 0})
        row["edges"] += 1
        row["deselected"] += 1 if edge.deselected else 0
    return {
        "total_edges": len(plan.closure_edges or ()),
        "by_kind": by_kind,
        "edges_marked_deselected": sum(
            1 for e in (plan.closure_edges or ()) if e.deselected),
    }


def _arriving(plan) -> set:
    out = set()
    for item in list(plan.actions or ()) + list(plan.overwrites or ()):
        out.add(_ref_key((item.category, item.source_guid)))
    return out


def _pulled_in_refs(plan) -> dict:
    """Every pulled-in ref in this plan, and HOW it reached the destination:
    `add` (new object), `overwrite` (already there, being enriched) or
    `already_present` (already there, nothing to write)."""
    from gramtrans.Lib.models import SkipReason
    refs = {_ref_key(e.dependency) for e in (plan.closure_edges or ())
            if e.origin == "pulled_in"}
    how: dict = {}
    for action in plan.actions or ():
        key = _ref_key((action.category, action.source_guid))
        if key in refs and getattr(action, "pulled_in_by", ()):
            how[key] = "add"
    for ow in plan.overwrites or ():
        key = _ref_key((ow.category, ow.source_guid))
        if key in refs and getattr(ow, "pulled_in_by", ()):
            how[key] = "overwrite"
    present = (SkipReason.ALREADY_PRESENT_BY_GUID,
               SkipReason.ALREADY_PRESENT_BY_IDENTITY)
    for skip in plan.skips or ():
        key = _ref_key((skip.category, skip.source_guid))
        if key in refs and skip.reason in present:
            how[key] = "already_present"
    return {
        "count": len(refs),
        "how": {k: how.get(k, "unplanned") for k in sorted(refs)},
    }


#: T093 re-runs this driver against the same pair to measure the repair, and
#: writes its own artifact rather than overwriting T073's. T102 filed what
#: happens when a committed artifact is re-measured in place: the artifacts
#: that compare against it turn red for a reason unrelated to what they
#: assert, and the BEFORE stops existing. `T073` stays the before.
_TASKS = {"T073", "T093"}


def main(argv) -> int:
    task = (argv[0] if argv else "T073").upper()
    if task not in _TASKS:
        print("[FAIL] unknown task %r; expected one of %s"
              % (task, ", ".join(sorted(_TASKS))))
        return 2

    from harness import full_run
    from harness.restore import restore_target

    from gramtrans.Lib import categories as _cats
    from gramtrans.Lib import report as report_mod
    from gramtrans.Lib.models import GrammarCategory, RunMode

    registry = dict(_cats.CLOSURE_EDGES_VERIFIED)
    if not registry:
        print("[FAIL] CLOSURE_EDGES_VERIFIED is EMPTY -- with no verified "
              "relationship there are no edges and nothing can be reported "
              "incomplete. Run this AFTER the registrations.")
        return 1
    print("[INFO] registry holds %d row(s): %s"
          % (len(registry), ", ".join(sorted(k.name for k in registry))))

    snapshot = _SNAPS / ("incompleteness-038-%s.json" % task.lower())
    before_path = _SNAPS / "incompleteness-038-t073.json"
    if task == "T073" and snapshot.exists() and not os.environ.get(
            "GT038_OVERWRITE_T073"):
        print("[FAIL] %s already exists and is T093's BEFORE. Re-measuring it "
              "in place destroys the only record of the pre-repair behaviour "
              "and turns every artifact-to-artifact comparison red for a "
              "reason unrelated to what it asserts (T102). Run `T093`, or set "
              "GT038_OVERWRITE_T073=1 if you really mean it."
              % snapshot.name)
        return 2
    target_path = str(PROJECTS_ROOT / TARGET / (TARGET + ".fwdata"))

    print("[INFO] restoring %r from %s (nothing below writes; the restore is "
          "so the destination's contents are a known quantity)"
          % (TARGET, BACKUP.name))
    restore_target(TARGET, BACKUP)

    def _preview(exclude, transform=None):
        plan, _ = full_run.run_full_transfer(
            SOURCE, TARGET, target_path,
            exclude=exclude, ws_mapping_mode="full", preview_only=True,
            selection_transform=transform,
        )
        return plan

    narrow = _only(NARROW)

    # ---- P0: narrow, nothing deselected -- the quiet case
    print("[INFO] P0: PREVIEW %s ONLY, registry LIVE, nothing deselected"
          % NARROW)
    p0 = _preview(narrow)
    p0_refs = _pulled_in_refs(p0)
    pulled_guids = sorted(
        {str(e.dependency[1]).lower() for e in (p0.closure_edges or ())
         if e.origin == "pulled_in"})
    pos_guids = sorted(
        {str(e.dependency[1]).lower() for e in (p0.closure_edges or ())
         if e.origin == "pulled_in"
         and e.dependency[0] is GrammarCategory.GRAM_CATEGORIES})

    # ---- P1: narrow, everything deselected
    print("[INFO] P1: PREVIEW %s ONLY, %d pulled-in GUID(s) deselected"
          % (NARROW, len(pulled_guids)))
    p1 = _preview(narrow, lambda s: _dc.replace(
        s, excluded_deps=frozenset(pulled_guids)))

    # ---- P2: narrow, only the parts of speech deselected (the two-hop case)
    print("[INFO] P2: PREVIEW %s ONLY, %d POS GUID(s) deselected"
          % (NARROW, len(pos_guids)))
    p2 = _preview(narrow, lambda s: _dc.replace(
        s, excluded_deps=frozenset(pos_guids)))

    # ---- P3: full copy -- the regression guard
    print("[INFO] P3: PREVIEW full copy, registry LIVE")
    p3 = _preview(frozenset())

    # ---- P4: do the records reach the surfaces a user reads?
    rpt = report_mod.RunReport.build_from_plan(p1, RunMode.PREVIEW)
    payload_json = json.loads(rpt.to_snapshot_json())
    console = "\n".join(report_mod.render_text_summary(rpt))
    surfaces = {
        "run_report_records": len(rpt.incompleteness or ()),
        "has_incomplete_items": bool(rpt.has_incomplete_items),
        "snapshot_json_records": len(payload_json.get("incompleteness", [])),
        "console_block_present": "Items arriving INCOMPLETE" in console,
        "console_states_a_cause": "(deselected)" in console,
    }

    # ---- the over-report the records cannot currently avoid
    already_there = {
        k for k, how in p0_refs["how"].items()
        if how in ("overwrite", "already_present")
    }
    over_reported = [
        _ref_key(r.missing_dependency) for r in (p1.incompleteness or ())
        if _ref_key(r.missing_dependency) in already_there
    ]

    measured = {
        "P0_nothing_deselected": {
            "closure": _closure_summary(p0),
            "incompleteness": _incompleteness_summary(p0),
            "pulled_in_refs": p0_refs,
            "arriving_items": len(_arriving(p0)),
        },
        "P1_everything_deselected": {
            "closure": _closure_summary(p1),
            "incompleteness": _incompleteness_summary(p1),
            "deselected_guids": len(pulled_guids),
            "skips": _tally([
                s for s in (p1.skips or ())
                if getattr(s.reason, "name", "") == "DEPENDENCY_DESELECTED"]),
        },
        "P2_only_the_parts_of_speech_deselected": {
            "closure": _closure_summary(p2),
            "incompleteness": _incompleteness_summary(p2),
            "deselected_guids": len(pos_guids),
        },
        "P3_full_copy": {
            "closure": _closure_summary(p3),
            "incompleteness": _incompleteness_summary(p3),
        },
        "P4_surfaces_for_P1": surfaces,
        "T093_dependencies_already_in_the_destination": {
            "refs_already_there": sorted(already_there),
            "P1_records_naming_one_of_them": len(over_reported),
            "note": (
                "each of these is an OVER-report: the dependency already "
                "exists in the destination, so the dependent's reference "
                "resolves and it is not incomplete. T071 suppresses a "
                "deselected ref before its planner runs, so no "
                "ALREADY_PRESENT_BY_* skip exists for T073 to read."
            ) if task == "T073" else (
                "T093 asks the refused dependency's OWN plan_action whether "
                "the destination already has it and keeps nothing but that "
                "verdict -- no plan member, no skip, so T071's composition is "
                "unchanged. A ref listed in refs_already_there must now name "
                "0 records; the ones that remain are dependencies that really "
                "are absent."
            ),
        },
    }

    if task != "T073" and before_path.exists():
        before = json.loads(before_path.read_text(encoding="utf-8"))
        b_measured = before.get("measured", {})

        def _rec(blob, key):
            return blob.get(key, {}).get("incompleteness", {}).get("records")

        b_over = b_measured.get(
            "T093_dependencies_already_in_the_destination", {})
        measured["T093_before_and_after"] = {
            "before_artifact": before_path.name,
            "before_task": before.get("task"),
            "P1_records": {
                "before": _rec(b_measured, "P1_everything_deselected"),
                "after": _rec(measured, "P1_everything_deselected"),
            },
            "P1_records_naming_a_dependency_already_there": {
                "before": b_over.get("P1_records_naming_one_of_them"),
                "after": len(over_reported),
            },
            "P2_records": {
                "before": _rec(b_measured,
                               "P2_only_the_parts_of_speech_deselected"),
                "after": _rec(measured,
                              "P2_only_the_parts_of_speech_deselected"),
            },
            "refs_already_there": {
                "before": b_over.get("refs_already_there"),
                "after": sorted(already_there),
            },
            "deselection_skips_P1": {
                "before": b_measured.get(
                    "P1_everything_deselected", {}).get("skips"),
                "after": measured["P1_everything_deselected"]["skips"],
            },
            "note": (
                "the skip row is here because the repair had to leave it "
                "alone: a refused dependency is still refused and still "
                "carries DEPENDENCY_DESELECTED. Only the INCOMPLETENESS "
                "records move."
            ),
        }

    claims = {
        "P0_a_satisfied_closure_reports_nothing":
            measured["P0_nothing_deselected"]["incompleteness"]["records"]
            == 0,
        "P1_every_arriving_item_that_lost_a_dependency_is_reported":
            measured["P1_everything_deselected"]["incompleteness"]["records"]
            > 0,
        "P1_records_are_fewer_than_edges_because_a_non_arriving_item_is_not_incomplete":
            measured["P1_everything_deselected"]["incompleteness"]["records"]
            < measured["P1_everything_deselected"]["closure"]["total_edges"],
        "P2_a_pulled_in_item_can_itself_arrive_incomplete":
            any(k == "slots" for k in measured[
                "P2_only_the_parts_of_speech_deselected"][
                    "incompleteness"]["by_category_pair"]),
        "P3_a_full_copy_reports_nothing":
            measured["P3_full_copy"]["closure"]["total_edges"] == 0
            and measured["P3_full_copy"]["incompleteness"]["records"] == 0,
        "P4_the_record_reaches_every_surface":
            all(bool(v) for v in surfaces.values()),
        "T093_no_record_names_a_dependency_already_in_the_destination":
            len(over_reported) == 0,
        "every_record_carries_a_consequence": all(
            measured[k]["incompleteness"]["every_record_has_a_consequence"]
            for k in ("P0_nothing_deselected", "P1_everything_deselected",
                      "P2_only_the_parts_of_speech_deselected",
                      "P3_full_copy")),
    }

    out = {
        "task": task,
        "source": SOURCE,
        "destination": TARGET,
        "backup": BACKUP.name,
        "narrow_selection": NARROW,
        "registered": sorted(k.name for k in registry),
        "wrote_nothing": True,
        "measured": measured,
        "claims": claims,
    }
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print("[OK] wrote %s" % snapshot)

    print()
    print("       T073 -- ITEMS ARRIVING INCOMPLETE")
    print("       %-34s %7s %7s %s" % ("case", "edges", "records", "by cause"))
    for key in ("P0_nothing_deselected", "P1_everything_deselected",
                "P2_only_the_parts_of_speech_deselected", "P3_full_copy"):
        row = measured[key]
        print("       %-34s %7d %7d %s" % (
            key, row["closure"]["total_edges"],
            row["incompleteness"]["records"],
            row["incompleteness"]["by_cause"]))
    print()
    print("       LABELS falling back to the ref (P1): %d of %d"
          % (measured["P1_everything_deselected"]["incompleteness"][
                 "labels_falling_back_to_the_ref"],
             measured["P1_everything_deselected"]["incompleteness"][
                 "labels_total"]))
    print("       T093 over-reports (dependency already in target): %d"
          % len(over_reported))
    if "T093_before_and_after" in measured:
        ba = measured["T093_before_and_after"]
        print("       T093 before -> after: P1 records %s -> %s, "
              "over-reports %s -> %s, P2 records %s -> %s"
              % (ba["P1_records"]["before"], ba["P1_records"]["after"],
                 ba["P1_records_naming_a_dependency_already_there"]["before"],
                 ba["P1_records_naming_a_dependency_already_there"]["after"],
                 ba["P2_records"]["before"], ba["P2_records"]["after"]))
    print()
    for name, ok in sorted(claims.items()):
        print("       [%s] %s" % ("OK" if ok else "FAIL", name))

    # T090: a driver that leaves a `<project>.fwdata.lock` behind makes
    # `test_038_phon_empty_drop_live.py::_open_or_skip` read a live
    # FieldWorks lock and SKIP, which is a suite that got quieter, not
    # greener. Report what is on disk so this run cannot do that silently.
    locks = sorted(p.name for p in PROJECTS_ROOT.glob("*/*.fwdata.lock"))
    print()
    print("       locks on disk after this run: %s" % (locks or "none"))
    return 0 if all(claims.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
