"""Feature 038 Phase 7 (US3) census driver -- T068 / T069 registrations.

`debug/run038_t067_census.py` is this file's ancestor and stays where it is:
it is the committed record of T067's run, and rewriting it would destroy the
artifact its `verified_by` names. What is generalised here is the SELECTION.

WHY A SELECTION PARAMETER IS THE WHOLE DIFFERENCE. T067's driver hard-coded
"affixes only" because that was T067's relationship. The lesson underneath it
is not about affixes at all: a FULL COPY cannot observe a closure edge, because
`closure.walk` never records a seed as pulled in and in a full copy every far
endpoint is already a seed in its own right. So each registration has to be
measured under the ONE selection that can see it -- the selection that turns
its far endpoints into non-seeds. For T068 that is SLOTS-only (the owning POSes
are then not selected, so they can be pulled in); for T069 it is
AFFIX_TEMPLATES-only (POSes and slots both).

WHAT IT MEASURES, per task:

  1. FULL COPY, registry live vs emptied. Claim: **0** closure edges either
     way (seed semantics), and the plan's composition -- every action, skip,
     overwrite, excluded-lossy, dropped item, enrichment and process-rule
     record, bucketed by category -- IDENTICAL. T070 (marking pulled-in items)
     and T072 (deselecting them) have not landed, so at this stage a
     registration must add EDGES and change no decision.

  2. NARROW SELECTION, registry live vs emptied. Claim: the registered edges
     are THERE, every one `origin="pulled_in"` with a non-empty `verified_by`,
     and **0** with the registry emptied. That second column is load-bearing:
     without it "the plan has N edges" is satisfied by any code path that
     produces closure edges, including one that ignores
     `CLOSURE_EDGES_VERIFIED` entirely -- the fall-through FR-018 forbids.

  3. THE CENSUS. A real full transfer with the registry live, then the census
     gate, so the artifact is row-for-row comparable with the PREVIOUS task's
     census over the same source, the same backup and the same full-copy
     selection. A census artifact alone says only "this transfer lost these
     objects"; the question a registration raises is whether it lost DIFFERENT
     ones, and only the comparison answers that.

Both plans in each pair come out of
`harness.full_run.run_full_transfer(..., preview_only=True)` -- the same
function the transfer uses -- precisely so nothing but the registry differs. A
hand-rolled second plan builder could not promise that.

WHY A DRIVER AND NOT A TEST. It restores and rewrites a project and takes
minutes. Run once here, COMMIT the measurement, and let
`tests/integration/test_038_closure_edge_audit.py` assert against the recorded
numbers.

Usage (writes to a THROWAWAY target, restored first):

    python debug/run038_closure_census.py T068
    python debug/run038_closure_census.py T069

`GT038_CENSUS_TARGET` overrides the target project name and
`GT038_CENSUS_SOURCE` the source. The target is restored from
`backups/Target 2026-07-06 0218.fwbackup` before the run, so the measurement is
repeatable and no real language data is in the blast radius (CLAUDE.md's
restore-before-write rule). The SOURCE is opened read-only.
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

#: Per task: which category the narrow selection keeps, which
#: `DependencyKind`s the registration is expected to put in that plan, and
#: which earlier census artifact this run must reproduce row for row.
#:
#: `expect_kinds` is declared rather than discovered on purpose. A driver that
#: simply reported whatever kinds it found would pass on a registration that
#: silently switched on a relationship nobody audited -- and for T069 it would
#: also hide the TRANSITIVE step, where the pulled-in slots are themselves
#: walked and contribute `SLOT_TO_POS` edges from T068's row.
_TASKS = {
    "T068": {
        "select": "SLOTS",
        "expect_kinds": ("SLOT_TO_POS",),
        "compare_census_to": "census-038-t067-registered.json",
    },
    "T069": {
        "select": "AFFIX_TEMPLATES",
        "expect_kinds": ("TEMPLATE_TO_POS", "TEMPLATE_TO_SLOT",
                         "SLOT_TO_POS"),
        "compare_census_to": "census-038-t068-registered.json",
    },
}


def _only(category_name: str):
    """Everything except `category_name`, for `build_full_selection(exclude=)`.

    The narrow selection is not a convenience: it is the only selection under
    which a registered closure edge exists at all (see the module docstring).
    """
    from gramtrans.Lib.models import GrammarCategory
    keep = getattr(GrammarCategory, category_name)
    return frozenset(c for c in GrammarCategory if c is not keep)


def _composition(plan) -> dict:
    """Everything a plan DECIDES, bucketed by category.

    Deliberately not a hash of the whole plan: the comparison has to be
    readable when it fails, and "SLOTS actions 19 -> 18" is a finding while
    "digest changed" is not.
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


def _tally(values) -> dict:
    out: dict = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


def _closure_summary(plan) -> dict:
    """`plan.closure_edges` reduced to per-`DependencyKind` counts.

    `verified_by` is carried too, because the point of FR-018 is that an edge
    in a plan can name the evidence that let it in -- and an edge whose
    `verified_by` came out empty would be a registry validated at build time
    and then losing its evidence on the way to the plan, silently.
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
        "pulled_in_by_category": dict(sorted(
            _tally(getattr(ref[0], "value", str(ref[0]))
                   for ref in pulled_in).items())),
    }


def main(argv) -> int:
    task = (argv[1] if len(argv) > 1 else os.environ.get(
        "GT038_CENSUS_TASK", "")).upper()
    if task not in _TASKS:
        print("[FAIL] usage: python debug/run038_closure_census.py "
              "{%s}" % "|".join(sorted(_TASKS)))
        return 2
    spec = _TASKS[task]

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
    print("[INFO] %s: registry holds %d row(s): %s"
          % (task, len(registry), ", ".join(sorted(k.name for k in registry))))
    missing = [k for k in spec["expect_kinds"]
               if k not in {kind.name for kind in registry}]
    if missing:
        print("[FAIL] %s expects %s in the registry; missing: %s"
              % (task, ", ".join(spec["expect_kinds"]), ", ".join(missing)))
        return 1

    snapshot = _SNAPS / ("closure-registration-038-%s.json" % task.lower())
    census_snapshot = _SNAPS / ("census-038-%s-registered.json" % task.lower())
    scratch = _REPO / "scratchpad" / ("038_%s" % task.lower())
    target_path = str(PROJECTS_ROOT / TARGET / (TARGET + ".fwdata"))

    # ---- 1. a clean, known target
    print("[INFO] restoring %r from %s" % (TARGET, BACKUP.name))
    restore_target(TARGET, BACKUP)

    scratch.mkdir(parents=True, exist_ok=True)
    baseline_path = scratch / ("%s-starter.json" % task.lower())
    print("[INFO] capturing the starter baseline")
    code = census_cli.main([
        "capture-baseline", "--project", TARGET, "--out", str(baseline_path),
    ])
    if code != 0:
        print("[ERROR] capture-baseline exited %s" % code)
        return code

    def _preview(exclude):
        plan, _ = full_run.run_full_transfer(
            SOURCE, TARGET, target_path,
            exclude=exclude, ws_mapping_mode="full", preview_only=True,
        )
        return {"composition": _composition(plan),
                "closure": _closure_summary(plan)}

    def _pair(label, exclude):
        print("[INFO] PREVIEW %s, registry LIVE (no write)" % label)
        live = _preview(exclude)
        print("[INFO] PREVIEW %s, registry EMPTIED" % label)
        _cats.CLOSURE_EDGES_VERIFIED = {}
        try:
            empty = _preview(exclude)
        finally:
            _cats.CLOSURE_EDGES_VERIFIED = registry
        same = live["composition"] == empty["composition"]
        print("[INFO]   composition unchanged by registration: %s" % same)
        print("[INFO]   closure edges  live=%d  empty=%d"
              % (live["closure"]["total_edges"],
                 empty["closure"]["total_edges"]))
        return {"registry_live": live, "registry_empty": empty,
                "composition_unchanged_by_registration": same}

    # ---- 2. the same plan twice, differing ONLY in the registry
    full = _pair("full copy", frozenset())
    full["closure_edges_expected"] = 0
    narrow = _pair("%s ONLY" % spec["select"], _only(spec["select"]))

    # ---- 3. the transfer, registry live, and the census gate
    print("[INFO] transferring %r -> %r (this takes minutes)"
          % (SOURCE, TARGET))
    report_path = str(_REPO / "_run_reports"
                      / ("038-%s-census-report.json" % task.lower()))
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    plan, report = full_run.run_full_transfer(
        SOURCE, TARGET, target_path,
        exclude=frozenset(), ws_mapping_mode="full",
        report_path=report_path,
    )
    transferred = {"composition": _composition(plan),
                   "closure": _closure_summary(plan)}

    print("[INFO] running the census")
    census_path = scratch / ("%s-census.json" % task.lower())
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
        census_snapshot.write_text(census_path.read_text(encoding="utf-8"),
                                   encoding="utf-8")
        print("[OK] wrote %s" % census_snapshot)
        gate_code = census_cli.main(["gate", "--artifact", str(census_path)])
        print("[INFO] gate exit code = %s" % gate_code)

    payload = {
        "task": task,
        "source": SOURCE,
        "destination": TARGET,
        "backup": BACKUP.name,
        "narrow_selection": spec["select"],
        "expected_kinds": list(spec["expect_kinds"]),
        "registered": sorted(k.name for k in registry),
        # 0 edges under a full copy is CORRECT, not inert -- every far
        # endpoint is itself a seed there, and walk() never records a seed as
        # pulled in. See the module docstring.
        "full_copy": full,
        "narrow": narrow,
        "transfer_plan": transferred,
        "plan_composition_unchanged_by_registration": (
            full["composition_unchanged_by_registration"]
            and narrow["composition_unchanged_by_registration"]),
        "census": {
            "run_exit_code": census_code,
            "gate_exit_code": gate_code,
            "artifact": census_snapshot.name,
            "comparable_prior_artifact": spec["compare_census_to"],
        },
        "report": {"run_id": getattr(report, "run_id", "")},
    }
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print("[OK] wrote %s" % snapshot)

    print()
    print("       CLOSURE EDGES, BY SELECTION")
    print("       " + "-" * 64)
    for label, block in (("full copy", full["registry_live"]),
                         ("%s only" % spec["select"].lower(),
                          narrow["registry_live"])):
        print("       %-18s %5d edge(s), %d distinct pulled-in ref(s) %s"
              % (label, block["closure"]["total_edges"],
                 block["closure"]["distinct_pulled_in_refs"],
                 block["closure"]["pulled_in_by_category"]))
        for name in sorted(block["closure"]["by_kind"]):
            row = block["closure"]["by_kind"][name]
            print("           %-22s %5d  far=%s  origins=%s"
                  % (name, row["edges"], row["far_categories"],
                     row["origins"]))

    failures = []
    if not full["composition_unchanged_by_registration"]:
        failures.append("full-copy plan composition CHANGED: %r vs %r"
                        % (full["registry_live"]["composition"],
                           full["registry_empty"]["composition"]))
    if not narrow["composition_unchanged_by_registration"]:
        failures.append("%s-only plan composition CHANGED: %r vs %r"
                        % (spec["select"], narrow["registry_live"]["composition"],
                           narrow["registry_empty"]["composition"]))
    if full["registry_live"]["closure"]["total_edges"] != 0:
        failures.append(
            "a FULL COPY produced %d closure edge(s); seed semantics say it "
            "must produce none, so either walk() or the seed set moved"
            % full["registry_live"]["closure"]["total_edges"])
    nlive = narrow["registry_live"]["closure"]
    if nlive["total_edges"] == 0:
        failures.append(
            "the %s-ONLY plan carries NO closure edges -- the registered "
            "row(s) are inert under the one selection that can observe them"
            % spec["select"])
    if narrow["registry_empty"]["closure"]["total_edges"] != 0:
        failures.append(
            "the %s-ONLY plan carries %d closure edge(s) with the registry "
            "EMPTY, so the edges are not coming from the registry"
            % (spec["select"],
               narrow["registry_empty"]["closure"]["total_edges"]))
    if set(nlive["by_kind"]) != set(spec["expect_kinds"]):
        failures.append(
            "the %s-ONLY plan carries kinds %s; %s expects exactly %s"
            % (spec["select"], sorted(nlive["by_kind"]), task,
               sorted(spec["expect_kinds"])))
    for kind, row in sorted(nlive["by_kind"].items()):
        if not row["verified_by_nonempty"]:
            failures.append("%s reached the plan with an EMPTY verified_by"
                            % kind)
        if row["origins"].get("chosen"):
            failures.append(
                "%s carries %d edge(s) with origin='chosen' -- the seed set "
                "leaked into the closure"
                % (kind, row["origins"]["chosen"]))

    if failures:
        print()
        for line in failures:
            print("[FAIL] %s" % line)
        return 1
    print()
    print("[OK]   %s: registration adds %d closure edge(s) to a %s-only plan "
          "(%d distinct pulled-in refs), 0 to a full copy as seed semantics "
          "require, and changes no decision in either."
          % (task, nlive["total_edges"], spec["select"].lower(),
             nlive["distinct_pulled_in_refs"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
