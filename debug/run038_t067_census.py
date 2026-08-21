"""Feature 038 Phase 7 (US3) census driver -- T067's post-registration run.

T067's own wording is "confirm the edge is correct against a live pair, add it
to `CLOSURE_EDGES_VERIFIED` ..., THEN run a census". `debug/audit038_closure_
edges.py` did the confirming, read-only, over two corpora. This does the
census, and it answers a different question from the audit's.

THE QUESTION. Registering a row turns one producer's output loose on real
plans: `preview._walk_verified_closure` stops short-circuiting, the walk runs,
and `preview._materialise_closure_edges` RAISES on any edge no registry row
authorises. So the two things that have to be measured against a live database
are (1) that a real full-copy plan now carries the edges, and (2) that it
carries nothing ELSE that it did not carry before -- because Phase 7's later
tasks (T070 marking pulled-in items, T072 making them deselectable) have not
landed, so at this point registration is supposed to add EDGES to the plan and
change no decision.

HOW IT ANSWERS (2). It builds the SAME plan twice against the same freshly
restored target -- once with the shipped registry and once with
`CLOSURE_EDGES_VERIFIED` emptied -- and compares the composition. Both plans
come out of `harness.full_run.run_full_transfer(..., preview_only=True)`, the
same function the transfer itself uses, precisely so nothing but the registry
differs between them. A hand-rolled second plan builder could not promise that.

AND IT DOES IT TWICE, UNDER TWO SELECTIONS, BECAUSE THE FIRST RUN OF THIS
DRIVER MEASURED THE WRONG ONE. A FULL COPY carries **zero** closure edges with
the registry live, and that is CORRECT rather than a defect: `closure.walk`'s
seed semantics say an item the user picked directly is never "pulled in by"
another, and `preview._materialise_closure_edges` builds edges only out of
`pulled_in_by`. In a full copy every POS and every `FsFeatStrucType` is already
a seed in its own right (measured: 10 `gram_categories` actions + 2 overwrites
over 13 source POSes, 6 `feature_struct_types` actions), so there is nothing
left to pull in and nothing for closure to contribute. A driver that only
measured a full copy would therefore report a correctly-registered edge as
inert -- which is what the first version of this file did, and is the same
class of instrument error as the one T088's journal records.

The selection that can actually see the edges is Phase 7's own Independent
Test: "select only affixes, run a preview, and confirm the dependent categories
... appear in the plan". So the driver runs BOTH: the full copy (where the
claim is composition-invariance) and an AFFIXES-ONLY selection (where the claim
is that the edges are there at all, with `origin="pulled_in"`).

Then it runs the transfer for real and runs the census gate, so the artifact is
comparable with `_snapshots/census-038-mbugwe-phase6.json` -- the T063/T064 run
over the same source, the same backup and the same full-copy selection, with
the registry EMPTY. That pair is the census diff registration is entitled to
be judged on.

WHY A DRIVER AND NOT A TEST. Same reason as `run038_phase6_live.py`: it
restores and rewrites a project and takes minutes. Run once here, COMMIT the
measurement, and let `tests/integration/test_038_closure_edge_audit.py` assert
against the recorded numbers.

Usage (writes to a THROWAWAY target, restored first):

    python debug/run038_t067_census.py

`GT038_T067_TARGET` overrides the target project name. The target is restored
from `backups/Target 2026-07-06 0218.fwbackup` before the run, so the
measurement is repeatable and no real language data is in the blast radius
(CLAUDE.md's restore-before-write rule). The SOURCE is opened read-only.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "tests" / "integration"))

SOURCE = os.environ.get("GT038_T067_SOURCE", "Mbugwe LizzieHC practice")
TARGET = os.environ.get("GT038_T067_TARGET", "GT038 T067 Target")
BACKUP = _REPO / "backups" / "Target 2026-07-06 0218.fwbackup"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
SNAPSHOT = (_REPO / "tests" / "integration" / "_snapshots"
            / "closure-registration-038-t067.json")
CENSUS_SNAPSHOT = (_REPO / "tests" / "integration" / "_snapshots"
                   / "census-038-t067-registered.json")
_SCRATCH = _REPO / "scratchpad" / "038_t067"


def _affixes_only_exclude():
    """Everything except AFFIXES, for `build_full_selection(exclude=...)`.

    Phase 7's Independent Test in tasks.md, expressed as a selection: "select
    only affixes, run a preview, and confirm the dependent categories, slots
    and templates appear in the plan". This is the ONLY selection under which a
    registered closure edge is observable at all -- see the module docstring.
    """
    from gramtrans.Lib.models import GrammarCategory
    return frozenset(c for c in GrammarCategory
                     if c is not GrammarCategory.AFFIXES)


def _composition(plan) -> dict:
    """Everything a plan DECIDES, bucketed by category.

    Deliberately not a hash of the whole plan: the comparison has to be
    readable when it fails, and "AFFIXES actions 110 -> 109" is a finding
    while "digest changed" is not.
    """
    def cat(x):
        c = getattr(x, "category", None)
        return getattr(c, "value", None) or str(c)

    def tally(items):
        out: dict = {}
        for item in items or ():
            key = cat(item)
            out[key] = out.get(key, 0) + 1
        return out

    return {
        "actions": tally(plan.actions),
        "skips": tally(plan.skips),
        "overwrites": tally(plan.overwrites),
        "excluded_lossy": len(plan.excluded_lossy or ()),
        "dropped_items": len(plan.dropped_items or ()),
        "enrichments": len(plan.enrichments or ()),
        "process_rules": len(plan.process_rules or ()),
        "actions_total": len(plan.actions or ()),
        "skips_total": len(plan.skips or ()),
        "overwrites_total": len(plan.overwrites or ()),
    }


def _closure_summary(plan) -> dict:
    """`plan.closure_edges` reduced to per-`DependencyKind` counts.

    `verified_by` is carried too, because the point of FR-018 is that an edge
    in a plan can name the evidence that let it in -- and an edge whose
    `verified_by` came out empty would be a registry validated at build time
    and then lost on the way to the plan.
    """
    by_kind: dict = {}
    for edge in plan.closure_edges or ():
        name = getattr(edge.kind, "name", str(edge.kind))
        row = by_kind.setdefault(name, {
            "edges": 0,
            "origins": {},
            "far_categories": {},
            "verified_by_nonempty": True,
        })
        row["edges"] += 1
        row["origins"][edge.origin] = row["origins"].get(edge.origin, 0) + 1
        far = getattr(edge.dependency[0], "value", str(edge.dependency[0]))
        row["far_categories"][far] = row["far_categories"].get(far, 0) + 1
        if not edge.verified_by:
            row["verified_by_nonempty"] = False
    pulled_in = {edge.dependency for edge in (plan.closure_edges or ())
                 if edge.origin == "pulled_in"}
    return {
        "total_edges": len(plan.closure_edges or ()),
        "by_kind": by_kind,
        "distinct_pulled_in_refs": len(pulled_in),
        "pulled_in_by_category": {
            k: v for k, v in sorted(
                _tally(getattr(ref[0], "value", str(ref[0]))
                       for ref in pulled_in).items())
        },
    }


def _tally(values) -> dict:
    out: dict = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


def main() -> int:
    from harness import full_run
    from harness.restore import restore_target
    from gramtrans import census_cli
    from gramtrans.Lib import categories as _cats

    registry = dict(_cats.CLOSURE_EDGES_VERIFIED)
    if not registry:
        print("[FAIL] CLOSURE_EDGES_VERIFIED is EMPTY -- there is nothing for "
              "a post-registration census to measure. Run this AFTER the "
              "registration, not instead of it.")
        return 1
    print("[INFO] registry holds %d row(s): %s"
          % (len(registry), ", ".join(sorted(k.name for k in registry))))

    target_path = str(PROJECTS_ROOT / TARGET / (TARGET + ".fwdata"))

    # ---- 1. a clean, known target
    print("[INFO] restoring %r from %s" % (TARGET, BACKUP.name))
    restore_target(TARGET, BACKUP)

    _SCRATCH.mkdir(parents=True, exist_ok=True)
    baseline_path = _SCRATCH / "t067-starter.json"
    print("[INFO] capturing the starter baseline")
    code = census_cli.main([
        "capture-baseline", "--project", TARGET, "--out", str(baseline_path),
    ])
    if code != 0:
        print("[ERROR] capture-baseline exited %s" % code)
        return code

    # ---- 2. the same plan, twice, differing ONLY in the registry
    print("[INFO] PREVIEW 1/4: full copy, registry LIVE (no write)")
    plan_live, _ = full_run.run_full_transfer(
        SOURCE, TARGET, target_path,
        exclude=frozenset(), ws_mapping_mode="full", preview_only=True,
    )
    live = {"composition": _composition(plan_live),
            "closure": _closure_summary(plan_live)}

    print("[INFO] PREVIEW 2/4: full copy, registry EMPTIED (the pre-T067 behaviour)")
    _cats.CLOSURE_EDGES_VERIFIED = {}
    try:
        plan_empty, _ = full_run.run_full_transfer(
            SOURCE, TARGET, target_path,
            exclude=frozenset(), ws_mapping_mode="full", preview_only=True,
        )
        empty = {"composition": _composition(plan_empty),
                 "closure": _closure_summary(plan_empty)}
    finally:
        _cats.CLOSURE_EDGES_VERIFIED = registry

    same = live["composition"] == empty["composition"]
    print("[INFO] plan composition unchanged by registration: %s" % same)
    print("[INFO] closure edges  registered=%d  unregistered=%d"
          % (live["closure"]["total_edges"], empty["closure"]["total_edges"]))

    # ---- 2b. the AFFIXES-ONLY selection -- Phase 7's Independent Test, and
    # the only selection under which a registered edge is observable (see the
    # module docstring on seed semantics).
    narrow_exclude = _affixes_only_exclude()
    print("[INFO] PREVIEW 3/4: AFFIXES ONLY, registry LIVE (no write)")
    plan_nlive, _ = full_run.run_full_transfer(
        SOURCE, TARGET, target_path,
        exclude=narrow_exclude, ws_mapping_mode="full", preview_only=True,
    )
    narrow_live = {"composition": _composition(plan_nlive),
                   "closure": _closure_summary(plan_nlive)}

    print("[INFO] PREVIEW 4/4: AFFIXES ONLY, registry EMPTIED")
    _cats.CLOSURE_EDGES_VERIFIED = {}
    try:
        plan_nempty, _ = full_run.run_full_transfer(
            SOURCE, TARGET, target_path,
            exclude=narrow_exclude, ws_mapping_mode="full", preview_only=True,
        )
        narrow_empty = {"composition": _composition(plan_nempty),
                        "closure": _closure_summary(plan_nempty)}
    finally:
        _cats.CLOSURE_EDGES_VERIFIED = registry

    narrow_same = narrow_live["composition"] == narrow_empty["composition"]
    print("[INFO] AFFIXES-only composition unchanged by registration: %s"
          % narrow_same)
    print("[INFO] AFFIXES-only closure edges  registered=%d  unregistered=%d"
          % (narrow_live["closure"]["total_edges"],
             narrow_empty["closure"]["total_edges"]))

    # ---- 3. the transfer, with the registry live, and the census gate
    print("[INFO] transferring %r -> %r (this takes minutes)" % (SOURCE, TARGET))
    report_path = str(_REPO / "_run_reports" / "038-t067-census-report.json")
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    plan, report = full_run.run_full_transfer(
        SOURCE, TARGET, target_path,
        exclude=frozenset(), ws_mapping_mode="full",
        report_path=report_path,
    )
    transferred = {"composition": _composition(plan),
                   "closure": _closure_summary(plan)}

    print("[INFO] running the census")
    census_path = _SCRATCH / "t067-census.json"
    census_code = census_cli.main([
        "run",
        "--source", SOURCE,
        "--destination", TARGET,
        "--baseline", str(baseline_path),
        "--destination-freshly-created",
        "--run-report", report_path,
        "--out", str(census_path),
    ])
    print("[INFO] census run exit code = %s" % census_code)
    gate_code = None
    if census_path.is_file():
        CENSUS_SNAPSHOT.write_text(census_path.read_text(encoding="utf-8"),
                                   encoding="utf-8")
        print("[OK] wrote %s" % CENSUS_SNAPSHOT)
        gate_code = census_cli.main(["gate", "--artifact", str(census_path)])
        print("[INFO] gate exit code = %s" % gate_code)

    payload = {
        "task": "T067",
        "source": SOURCE,
        "destination": TARGET,
        "backup": BACKUP.name,
        "registered": sorted(k.name for k in registry),
        "full_copy": {
            "registry_live": live,
            "registry_empty": empty,
            "composition_unchanged_by_registration": same,
            # 0 edges here is CORRECT, not inert -- every far endpoint is
            # itself a seed in a full copy, and walk() never records a seed as
            # pulled in. See the module docstring.
            "closure_edges_expected": 0,
        },
        "affixes_only": {
            "registry_live": narrow_live,
            "registry_empty": narrow_empty,
            "composition_unchanged_by_registration": narrow_same,
        },
        "transfer_plan": transferred,
        "plan_composition_unchanged_by_registration": same and narrow_same,
        "census": {
            "run_exit_code": census_code,
            "gate_exit_code": gate_code,
            "artifact": CENSUS_SNAPSHOT.name,
            "comparable_pre_registration_artifact":
                "census-038-mbugwe-phase6.json",
        },
        "report": {
            "run_id": getattr(report, "run_id", ""),
        },
    }
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print("[OK] wrote %s" % SNAPSHOT)

    print()
    print("       CLOSURE EDGES, BY SELECTION")
    print("       " + "-" * 64)
    for label, block in (("full copy", live), ("affixes only", narrow_live)):
        print("       %-14s %5d edge(s), %d distinct pulled-in ref(s) %s"
              % (label, block["closure"]["total_edges"],
                 block["closure"]["distinct_pulled_in_refs"],
                 block["closure"]["pulled_in_by_category"]))
        for name in sorted(block["closure"]["by_kind"]):
            row = block["closure"]["by_kind"][name]
            print("           %-24s %5d  far=%s  origins=%s"
                  % (name, row["edges"], row["far_categories"], row["origins"]))

    failures = []
    if not same:
        failures.append(
            "full-copy plan composition CHANGED: %r vs %r"
            % (live["composition"], empty["composition"]))
    if not narrow_same:
        failures.append(
            "affixes-only plan composition CHANGED: %r vs %r"
            % (narrow_live["composition"], narrow_empty["composition"]))
    if live["closure"]["total_edges"] != 0:
        failures.append(
            "a FULL COPY produced %d closure edge(s); seed semantics say it "
            "must produce none, so either walk() or the seed set moved"
            % live["closure"]["total_edges"])
    if narrow_live["closure"]["total_edges"] == 0:
        failures.append(
            "the AFFIXES-ONLY plan carries NO closure edges -- the registered "
            "rows are inert under the one selection that can observe them")
    if narrow_empty["closure"]["total_edges"] != 0:
        failures.append(
            "the AFFIXES-ONLY plan carries %d closure edge(s) with the "
            "registry EMPTY, so the edges are not coming from the registry"
            % narrow_empty["closure"]["total_edges"])
    for kind in sorted(narrow_live["closure"]["by_kind"]):
        if not narrow_live["closure"]["by_kind"][kind]["verified_by_nonempty"]:
            failures.append(
                "%s reached the plan with an EMPTY verified_by" % kind)

    if failures:
        print()
        for line in failures:
            print("[FAIL] %s" % line)
        return 1
    print()
    print("[OK]   registration adds %d closure edge(s) to an affixes-only "
          "plan (%d distinct pulled-in refs), 0 to a full copy as seed "
          "semantics require, and changes no decision in either."
          % (narrow_live["closure"]["total_edges"],
             narrow_live["closure"]["distinct_pulled_in_refs"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
