"""Feature 038 Phase 7 (US3) live driver -- T070 / T071 / T072.

`debug/run038_closure_census.py` stays exactly as it is: it is the committed
record of the T068 and T069 registrations, and one of its central claims is
`plan_composition_unchanged_by_registration`, which its own docstring says is
true only "at this stage" because "T070 (marking pulled-in items) and T072
(deselecting them) have not landed". THIS DRIVER MEASURES THE MOMENT THAT
CLAIM STOPS HOLDING, so it must not overwrite the artifact that recorded it.

WHAT CHANGES, AND WHAT MUST NOT. After T070 a registration is no longer
edges-only: under a selection narrow enough for a far endpoint to be a
non-seed, the plan gains ACTIONS for the pulled-in objects, each marked
`pulled_in_by`. Under a FULL COPY nothing changes at all -- every far endpoint
is already a seed, `walk` records no seed as pulled in, so there are no edges
and nothing to pull. That asymmetry is the safety property this driver pins:
the feature that makes a narrow selection complete must leave a full copy
byte-identical.

FOUR MEASUREMENTS, all against `Mbugwe LizzieHC practice` (read-only source)
and a THROWAWAY target restored from a known backup first:

  A. NARROW (AFFIX_TEMPLATES-only), registry LIVE vs EMPTIED. The live plan
     must gain actions in the pulled-in categories; the emptied one must gain
     none. The second column is what rules out a code path that pulls items in
     without consulting `CLOSURE_EDGES_VERIFIED` -- the FR-018 fall-through.

  B. NARROW, registry live, with every pulled-in GUID in
     `Selection.excluded_deps` -- what T072's wizard wiring puts there. The
     composition must return to A's emptied column, and each suppressed item
     must appear as a `DEPENDENCY_DESELECTED` skip rather than vanish.

  C. FULL COPY, registry LIVE vs EMPTIED. Composition identical, 0 edges,
     0 pulled-in actions. The regression guard.

  D. THE ARRIVAL. A real narrow transfer into the restored target, with a
     whole-project class census captured before and after. This is the only
     measurement that answers FR-014 as a linguist would ask it: after
     transferring templates alone, are the parts of speech and slots they
     need actually IN the target? Before T070 the answer was no, by
     construction -- the plan named them and transferred none.

Usage (writes to a THROWAWAY target, restored first):

    python debug/run038_pull_in_census.py

`GT038_CENSUS_TARGET` overrides the target project name, `GT038_CENSUS_SOURCE`
the source. Restore-before-write per CLAUDE.md, so no real language data is in
the blast radius and the measurement is repeatable.
"""
from __future__ import annotations

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

#: The same narrow selection T069 measured, so the two artifacts are directly
#: comparable: AFFIX_TEMPLATES-only turns POSes and slots into non-seeds.
NARROW = "AFFIX_TEMPLATES"

#: The LCM classes the pulled-in categories land in, for measurement D.
_ARRIVAL_CLASSES = ("PartOfSpeech", "MoInflAffixSlot", "MoInflAffixTemplate")


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


def _composition(plan) -> dict:
    return {
        "actions": _tally(plan.actions),
        "skips": _tally(plan.skips),
        "overwrites": _tally(plan.overwrites),
        "excluded_lossy": len(plan.excluded_lossy or ()),
        "dropped_items": len(plan.dropped_items or ()),
        "enrichments": len(plan.enrichments or ()),
        "process_rules": len(plan.process_rules or ()),
        "actions_total": len(plan.actions or ()),
        "skips_total": len(plan.skips or ()),
        "overwrites_total": len(plan.overwrites or ()),
    }


def _pulled_in_members(plan) -> dict:
    """Every plan member carrying a `pulled_in_by`, bucketed by category.

    Reads the SAME field `report.build_from_plan` counts into
    `CategoryReport.closure_pulled_in`, so a number here that the run report
    does not also show would mean the mark stopped travelling.
    """
    rows: dict = {}
    for item in list(plan.actions or ()) + list(plan.overwrites or ()):
        if not getattr(item, "pulled_in_by", ()):
            continue
        row = rows.setdefault(_cat(item), {"count": 0, "guids": [],
                                           "pullers_named": True})
        row["count"] += 1
        row["guids"].append(str(item.source_guid).lower())
        if not item.pulled_in_by:
            row["pullers_named"] = False
    for row in rows.values():
        row["guids"] = sorted(row["guids"])
    return rows


def _closure_summary(plan) -> dict:
    by_kind: dict = {}
    for edge in plan.closure_edges or ():
        name = getattr(edge.kind, "name", str(edge.kind))
        row = by_kind.setdefault(name, {"edges": 0, "deselected": 0,
                                        "origins": {}})
        row["edges"] += 1
        row["deselected"] += 1 if edge.deselected else 0
        row["origins"][edge.origin] = row["origins"].get(edge.origin, 0) + 1
    pulled_in = {edge.dependency for edge in (plan.closure_edges or ())
                 if edge.origin == "pulled_in"}
    return {
        "total_edges": len(plan.closure_edges or ()),
        "by_kind": by_kind,
        "distinct_pulled_in_refs": len(pulled_in),
        "pulled_in_refs": sorted(str(ref[1]).lower() for ref in pulled_in),
    }


def _ordering_ok(plan, pulled_categories) -> dict:
    """Is every pulled-in member positioned before the members that need it?

    `transfer.execute` walks `plan.actions` in order, so a dependency planned
    after its dependent is created after it -- the same "arrives wired to
    nothing" failure FR-014 exists to prevent, one layer down.
    """
    first_narrow = None
    last_pulled = {}
    for i, action in enumerate(plan.actions or ()):
        cat = _cat(action)
        if cat == NARROW.lower() and first_narrow is None:
            first_narrow = i
        if getattr(action, "pulled_in_by", ()):
            last_pulled[cat] = i
    return {
        "first_selected_member_index": first_narrow,
        "last_pulled_in_index_by_category": last_pulled,
        "every_pulled_in_member_precedes_the_selection": (
            first_narrow is not None
            and all(i < first_narrow for i in last_pulled.values())
        ),
    }


def _deselection_skips(plan) -> dict:
    from gramtrans.Lib.models import SkipReason
    rows = [s for s in (plan.skips or ())
            if s.reason == SkipReason.DEPENDENCY_DESELECTED]
    return {
        "count": len(rows),
        "by_category": _tally(rows),
        "guids": sorted(str(s.source_guid).lower() for s in rows),
        "every_skip_names_its_puller": all(
            "needed by" in (s.detail or "") for s in rows),
    }


def _class_counts(baseline_path: Path) -> dict:
    data = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    return {row["class"]: row["count"] for row in data.get("entries", ())}


def main(argv) -> int:
    import dataclasses as _dc

    from harness import full_run
    from harness.restore import restore_target

    from gramtrans import census_cli
    from gramtrans.Lib import categories as _cats

    registry = dict(_cats.CLOSURE_EDGES_VERIFIED)
    if not registry:
        print("[FAIL] CLOSURE_EDGES_VERIFIED is EMPTY -- there is nothing to "
              "pull in. Run this AFTER the registrations, not instead.")
        return 1
    print("[INFO] registry holds %d row(s): %s"
          % (len(registry), ", ".join(sorted(k.name for k in registry))))

    snapshot = _SNAPS / "closure-pull-in-038-t070.json"
    scratch = _REPO / "scratchpad" / "038_t070"
    scratch.mkdir(parents=True, exist_ok=True)
    target_path = str(PROJECTS_ROOT / TARGET / (TARGET + ".fwdata"))

    print("[INFO] restoring %r from %s" % (TARGET, BACKUP.name))
    restore_target(TARGET, BACKUP)

    pre_baseline = scratch / "t070-pre.json"
    print("[INFO] capturing the pre-transfer class census")
    code = census_cli.main([
        "capture-baseline", "--project", TARGET, "--out", str(pre_baseline)])
    if code != 0:
        print("[ERROR] capture-baseline exited %s" % code)
        return code

    def _preview(exclude, transform=None):
        plan, _ = full_run.run_full_transfer(
            SOURCE, TARGET, target_path,
            exclude=exclude, ws_mapping_mode="full", preview_only=True,
            selection_transform=transform,
        )
        return plan

    def _measure(plan) -> dict:
        return {
            "composition": _composition(plan),
            "closure": _closure_summary(plan),
            "pulled_in_members": _pulled_in_members(plan),
            "ordering": _ordering_ok(plan, ()),
            "deselection_skips": _deselection_skips(plan),
        }

    narrow_exclude = _only(NARROW)

    # ---- A. narrow, registry live vs emptied
    print("[INFO] A: PREVIEW %s ONLY, registry LIVE" % NARROW)
    a_live = _measure(_preview(narrow_exclude))
    print("[INFO] A: PREVIEW %s ONLY, registry EMPTIED" % NARROW)
    _cats.CLOSURE_EDGES_VERIFIED = {}
    try:
        a_empty = _measure(_preview(narrow_exclude))
    finally:
        _cats.CLOSURE_EDGES_VERIFIED = registry

    pulled_guids = sorted(
        g for row in a_live["pulled_in_members"].values() for g in row["guids"])

    # ---- B. narrow, registry live, every pulled-in GUID deselected
    print("[INFO] B: PREVIEW %s ONLY, registry LIVE, %d GUID(s) deselected"
          % (NARROW, len(pulled_guids)))

    def _deselect_all(selection):
        return _dc.replace(selection, excluded_deps=frozenset(pulled_guids))

    b = _measure(_preview(narrow_exclude, _deselect_all))

    # ---- C. full copy, registry live vs emptied (the regression guard)
    print("[INFO] C: PREVIEW full copy, registry LIVE")
    c_live = _measure(_preview(frozenset()))
    print("[INFO] C: PREVIEW full copy, registry EMPTIED")
    _cats.CLOSURE_EDGES_VERIFIED = {}
    try:
        c_empty = _measure(_preview(frozenset()))
    finally:
        _cats.CLOSURE_EDGES_VERIFIED = registry

    # ---- D. the arrival: a real narrow transfer, censused before and after
    print("[INFO] D: transferring %r -> %r, %s ONLY (this writes)"
          % (SOURCE, TARGET, NARROW))
    report_path = str(_REPO / "_run_reports" / "038-t070-pull-in-report.json")
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    plan, report = full_run.run_full_transfer(
        SOURCE, TARGET, target_path,
        exclude=narrow_exclude, ws_mapping_mode="full",
        report_path=report_path,
    )
    post_baseline = scratch / "t070-post.json"
    print("[INFO] capturing the post-transfer class census")
    census_cli.main([
        "capture-baseline", "--project", TARGET, "--out", str(post_baseline)])

    before = _class_counts(pre_baseline)
    after = _class_counts(post_baseline)
    arrival = {
        cls: {"before": before.get(cls, 0), "after": after.get(cls, 0),
              "arrived": after.get(cls, 0) - before.get(cls, 0)}
        for cls in _ARRIVAL_CLASSES
    }

    per_cat = {}
    for cat, rpt in (getattr(report, "per_category", {}) or {}).items():
        if rpt.closure_pulled_in:
            per_cat[getattr(cat, "value", str(cat))] = rpt.closure_pulled_in

    # ---- E. the SAME transfer with the registry emptied -- D's "before"
    #
    # Without this column measurement D says only "objects arrived", which is
    # satisfied by any code path that creates them, including one that ignores
    # the registry. It is also the only way to state the pre-T070 loss as a
    # number rather than a deduction. A second restore is what makes the two
    # runs comparable: the same backup, the same source, the same selection,
    # and NOTHING different but the registry.
    print("[INFO] E: restoring %r again for the registry-emptied transfer"
          % TARGET)
    restore_target(TARGET, BACKUP)
    e_report_path = str(_REPO / "_run_reports"
                        / "038-t070-pull-in-report-registry-empty.json")
    print("[INFO] E: transferring %s ONLY with the registry EMPTIED" % NARROW)
    _cats.CLOSURE_EDGES_VERIFIED = {}
    try:
        e_plan, e_report = full_run.run_full_transfer(
            SOURCE, TARGET, target_path,
            exclude=narrow_exclude, ws_mapping_mode="full",
            report_path=e_report_path,
        )
    finally:
        _cats.CLOSURE_EDGES_VERIFIED = registry
    e_post = scratch / "t070-post-registry-empty.json"
    census_cli.main([
        "capture-baseline", "--project", TARGET, "--out", str(e_post)])
    after_empty = _class_counts(e_post)
    for cls in _ARRIVAL_CLASSES:
        arrival[cls]["after_without_pull_in"] = after_empty.get(cls, 0)
        arrival[cls]["arrived_without_pull_in"] = (
            after_empty.get(cls, 0) - before.get(cls, 0))

    payload = {
        "task": "T070/T071/T072",
        "source": SOURCE,
        "destination": TARGET,
        "backup": BACKUP.name,
        "narrow_selection": NARROW,
        "registered": sorted(k.name for k in registry),
        "A_narrow_registry_live": a_live,
        "A_narrow_registry_empty": a_empty,
        "A_pull_in_requires_the_registry": (
            not a_empty["pulled_in_members"]
            and bool(a_live["pulled_in_members"])),
        "B_narrow_all_deselected": b,
        "B_deselection_restores_the_unregistered_composition": (
            b["composition"]["actions"] == a_empty["composition"]["actions"]),
        "C_full_copy_registry_live": c_live,
        "C_full_copy_registry_empty": c_empty,
        "C_full_copy_unchanged_by_the_pull_in": (
            c_live["composition"] == c_empty["composition"]
            and not c_live["pulled_in_members"]),
        "D_arrival_in_target": arrival,
        "D_run_report_closure_pulled_in": per_cat,
        "E_registry_empty_transfer": {
            "composition": _composition(e_plan),
            "run_id": getattr(e_report, "run_id", ""),
        },
        "report": {"run_id": getattr(report, "run_id", "")},
    }
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print("[OK] wrote %s" % snapshot)

    print()
    print("       T070 -- PULLED-IN MEMBERS, %s ONLY" % NARROW)
    print("       %-24s %8s %8s %8s" % ("category", "live", "empty", "desel"))
    cats = sorted(set(a_live["pulled_in_members"])
                  | set(a_empty["pulled_in_members"])
                  | set(b["pulled_in_members"]))
    for cat in cats:
        print("       %-24s %8d %8d %8d" % (
            cat,
            a_live["pulled_in_members"].get(cat, {}).get("count", 0),
            a_empty["pulled_in_members"].get(cat, {}).get("count", 0),
            b["pulled_in_members"].get(cat, {}).get("count", 0)))
    print()
    print("       T071/T072 -- DESELECTION")
    print("       skips(DEPENDENCY_DESELECTED) = %d, edges marked deselected "
          "= %d of %d" % (
              b["deselection_skips"]["count"],
              sum(r["deselected"] for r in b["closure"]["by_kind"].values()),
              b["closure"]["total_edges"]))
    print()
    print("       D/E -- WHAT ACTUALLY ARRIVED IN THE TARGET")
    print("       %-24s %8s %10s %10s"
          % ("class", "baseline", "with T070", "without"))
    for cls, row in arrival.items():
        print("       %-24s %8d %10d %10d"
              % (cls, row["before"], row["after"],
                 row.get("after_without_pull_in", -1)))
    print()
    print("       C -- full copy unchanged: %s"
          % payload["C_full_copy_unchanged_by_the_pull_in"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
