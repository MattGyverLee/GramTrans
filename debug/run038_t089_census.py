"""Feature 038 -- T089's OWN census. The axis is the PRODUCER, not the registry.

WHY THIS DRIVER EXISTS AT ALL, AND WHY IT IS NOT `run038_closure_census.py`.

T089's task text is explicit that the fix "is a live-behaviour change and must
not be folded into a registration ... it changes `affixes_dependencies`' output
for every caller, so it needs its own census." `run038_closure_census.py`
cannot supply that. Its two plans differ only in whether
`CLOSURE_EDGES_VERIFIED` is populated, so it answers "what did REGISTERING this
row change?" -- a question about a registry that T089 does not touch. The
question T089 raises is the other one: with the registry held FIXED, what did
re-pointing the `ValueRA` edge change in the plans this repo already builds?

So the axis here is `categories._value_defn_ref`, monkeypatched back to the
pre-T089 identity (`lambda value, declared_feature: value`, i.e. "emit the
value's own guid"). That single patch reverts BOTH sites the fix touches --
`_feat_struc_deps`, which serves AFFIXES / STEMS / GRAM_CATEGORIES / PHONEMES /
NATURAL_CLASSES-adjacent structures, and `variant_types_dependencies` -- because
both call the module-global helper. Patching the helper rather than restating
the old code is deliberate: a hand-copied "before" implementation could drift
from what was actually replaced, and then the census would be measuring a
third behaviour that never shipped.

WHAT THE MEASUREMENT IS EXPECTED TO SHOW, AND WHY THAT IS NOT A FORMALITY.

The expectation is ZERO plan difference, and the reason is structural: of the
five producers the fix reaches, only `affixes_feat_struc_type_dependencies`
appears in `CLOSURE_EDGES_VERIFIED` at all, and it is NARROWED to
FEATURE_STRUCT_TYPES -- the far category the `TypeRA` arrow lands in, which the
fix does not touch. `MSA_TO_INFL_FEATURE` is the row T089 unblocks and is NOT
registered, so `closure_dependencies_for` never calls its producer.

A structural argument is exactly the kind of claim this feature has repeatedly
watched fail on live data (T088: a producer everyone could read and nobody had
run; flexicon 4.5.0: a gate that was unconditionally False while 1467 tests
passed). So it is measured rather than asserted, and the driver FAILS if the
plans differ -- a difference would mean some consumer reaches the ValueRA edge
by a path the registry does not describe, which is a finding worth more than
the fix.

The producer-level change IS large and is recorded here too, from the audit
snapshots rather than re-measured: on `Mbugwe LizzieHC practice`
`MSA_TO_INFL_FEATURE` went 206 edges over 34 distinct far GUIDs (4 enumerable,
30 owned symbolic values) to 99 over 4 (4 enumerable, 0 owned); on `Ejagham
Mini` 34 over 10 (2 / 8) to 17 over 2 (2 / 0). That is the point of the fix and
it is deliberately NOT the thing this driver checks -- `debug/
audit038_closure_edges.py` measured it over two corpora and its snapshots are
what `tests/integration/test_038_closure_edge_audit.py` asserts.

WHY A DRIVER AND NOT A TEST. Same reason as its siblings: it restores and
rewrites a project and takes minutes. Run once, COMMIT the measurement, and let
the integration suite assert against the recorded numbers.

Usage (writes to a THROWAWAY target, restored first):

    python debug/run038_t089_census.py

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

#: The census artifact this run must reproduce ROW FOR ROW. T076's is the
#: right comparand and the only one that is: it is the most recent full-copy
#: census over the same source, the same backup and the same selection, and
#: the ONLY code difference between the two runs is T089's. The older
#: `-t067-`/`-t068-`/`-t069-` chain is not usable for this -- T102 measured it
#: as already behind the instrument (3 changed rows, 2 changed totals, from
#: T087 and T099), so a comparison against it would fail for drift that has
#: nothing to do with this task and say nothing about the fix.
COMPARE_CENSUS_TO = "census-038-t076-registered.json"

#: Selections to measure the plan under. A FULL COPY is the unconditional
#: case -- every far endpoint is its own seed, so the closure is empty and any
#: difference at all is the fix leaking into the seed set. AFFIXES-only is the
#: one selection that can observe the registered AFFIXES rows, and it is the
#: selection through which the fix's producers are actually reachable. The
#: other categories the fix touches (GRAM_CATEGORIES, PHONEMES, STEMS,
#: VARIANT_TYPES) have NO row in `CLOSURE_EDGES_VERIFIED` naming them as a
#: source, so `closure_dependencies_for` never calls their producers and there
#: is no selection under which they could reach a plan today. That is recorded
#: in the artifact rather than left as an unstated gap.
_SELECTIONS = (
    ("full copy", None),
    ("AFFIXES only", "AFFIXES"),
)


def _only(category_name: str):
    """Everything except `category_name`, for `build_full_selection(exclude=)`."""
    from gramtrans.Lib.models import GrammarCategory
    keep = getattr(GrammarCategory, category_name)
    return frozenset(c for c in GrammarCategory if c is not keep)


def _composition(plan) -> dict:
    """Everything a plan DECIDES, bucketed by category.

    Same shape as `run038_closure_census._composition`, and deliberately not a
    hash: the comparison has to be readable when it fails.
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
    """`plan.closure_edges` reduced to per-`DependencyKind` counts, plus the
    distinct pulled-in refs the fix could in principle have moved."""
    by_kind: dict = {}
    for edge in plan.closure_edges or ():
        name = getattr(edge.kind, "name", str(edge.kind))
        row = by_kind.setdefault(name, {"edges": 0, "far_categories": {}})
        row["edges"] += 1
        far = getattr(edge.dependency[0], "value", str(edge.dependency[0]))
        row["far_categories"][far] = row["far_categories"].get(far, 0) + 1
    pulled = sorted({"%s|%s" % (getattr(e.dependency[0], "value",
                                        str(e.dependency[0])), e.dependency[1])
                     for e in (plan.closure_edges or ())
                     if e.origin == "pulled_in"})
    return {
        "total_edges": len(plan.closure_edges or ()),
        "by_kind": by_kind,
        "distinct_pulled_in_refs": len(pulled),
        "pulled_in_refs": pulled,
    }


def main(argv) -> int:
    from harness import full_run
    from harness.restore import restore_target
    from gramtrans import census_cli
    from gramtrans.Lib import categories as _cats

    registry = dict(_cats.CLOSURE_EDGES_VERIFIED)
    registered = sorted(k.name for k in registry)
    print("[INFO] registry holds %d row(s): %s"
          % (len(registry), ", ".join(registered)))
    if "MSA_TO_INFL_FEATURE" in {k.name for k in registry}:
        print("[FAIL] MSA_TO_INFL_FEATURE is REGISTERED. T089 is the fix, not "
              "the registration -- its own task text forbids folding the two "
              "together, and with the row live this driver would be measuring "
              "both changes at once and able to attribute neither.")
        return 1

    #: The pre-T089 helper, verbatim: emit the value's OWN guid.
    def _pre_t089(value, declared_feature):
        return value

    snapshot = _SNAPS / "closure-producer-038-t089.json"
    census_snapshot = _SNAPS / "census-038-t089-fixed.json"
    scratch = _REPO / "scratchpad" / "038_t089"
    target_path = str(PROJECTS_ROOT / TARGET / (TARGET + ".fwdata"))

    # ---- 1. a clean, known target
    print("[INFO] restoring %r from %s" % (TARGET, BACKUP.name))
    restore_target(TARGET, BACKUP)

    scratch.mkdir(parents=True, exist_ok=True)
    baseline_path = scratch / "t089-starter.json"
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
        print("[INFO] PREVIEW %s, producer FIXED (T089)" % label)
        after = _preview(exclude)
        print("[INFO] PREVIEW %s, producer PRE-T089" % label)
        original = _cats._value_defn_ref
        _cats._value_defn_ref = _pre_t089
        try:
            before = _preview(exclude)
        finally:
            _cats._value_defn_ref = original
        same_comp = after["composition"] == before["composition"]
        same_clos = after["closure"] == before["closure"]
        print("[INFO]   composition unchanged by the fix: %s" % same_comp)
        print("[INFO]   closure unchanged by the fix:     %s" % same_clos)
        print("[INFO]   closure edges  fixed=%d  pre=%d"
              % (after["closure"]["total_edges"],
                 before["closure"]["total_edges"]))
        return {"pre_t089": before, "fixed": after,
                "composition_unchanged_by_fix": same_comp,
                "closure_unchanged_by_fix": same_clos}

    # ---- 2. the same plan twice, differing ONLY in the producer
    pairs: dict = {}
    for label, keep in _SELECTIONS:
        pairs[label] = _pair(label,
                             frozenset() if keep is None else _only(keep))

    # ---- 3. the transfer, fixed producer, and the census gate
    print("[INFO] transferring %r -> %r (this takes minutes)"
          % (SOURCE, TARGET))
    report_path = str(_REPO / "_run_reports" / "038-t089-census-report.json")
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    plan, report = full_run.run_full_transfer(
        SOURCE, TARGET, target_path,
        exclude=frozenset(), ws_mapping_mode="full",
        report_path=report_path,
    )
    transferred = {"composition": _composition(plan),
                   "closure": _closure_summary(plan)}

    print("[INFO] running the census")
    census_path = scratch / "t089-census.json"
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
    census_matches_prior = None
    if census_path.is_file():
        census_snapshot.write_text(census_path.read_text(encoding="utf-8"),
                                   encoding="utf-8")
        print("[OK] wrote %s" % census_snapshot)
        gate_code = census_cli.main(["gate", "--artifact", str(census_path)])
        print("[INFO] gate exit code = %s" % gate_code)
        prior = _SNAPS / COMPARE_CENSUS_TO
        if prior.is_file():
            census_matches_prior = _rows_equal(prior, census_path)
            print("[INFO] census rows match %s: %s"
                  % (COMPARE_CENSUS_TO, census_matches_prior))

    payload = {
        "task": "T089",
        "axis": "categories._value_defn_ref (pre-T089 identity vs fixed)",
        "source": SOURCE,
        "destination": TARGET,
        "backup": BACKUP.name,
        "registered": registered,
        "msa_to_infl_feature_registered": False,
        # From `debug/audit038_closure_edges.py`'s two snapshots, quoted rather
        # than re-measured: the producer change the plans below do NOT see.
        "producer_change_recorded_by_the_audit": {
            "Mbugwe LizzieHC practice": {
                "before": {"edges": 206, "distinct_far_guids": 34,
                           "resolved_as_piece": 4,
                           "resolved_as_owned_value": 30,
                           "verdict": "REFUSED_FAR_ENDPOINT_NOT_ENUMERABLE"},
            },
            "Ejagham Mini": {
                "before": {"edges": 34, "distinct_far_guids": 10,
                           "resolved_as_piece": 2,
                           "resolved_as_owned_value": 8,
                           "verdict": "REFUSED_FAR_ENDPOINT_NOT_ENUMERABLE"},
            },
            "after": "see closure-edge-audit-038-*.json, re-run 2026-08-22",
        },
        "selections": pairs,
        "transfer_plan": transferred,
        "plan_unchanged_by_fix": all(
            p["composition_unchanged_by_fix"] and p["closure_unchanged_by_fix"]
            for p in pairs.values()),
        "census": {
            "run_exit_code": census_code,
            "gate_exit_code": gate_code,
            "artifact": census_snapshot.name,
            "comparable_prior_artifact": COMPARE_CENSUS_TO,
            "rows_match_prior": census_matches_prior,
        },
        "report": {"run_id": getattr(report, "run_id", "")},
    }
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print("[OK] wrote %s" % snapshot)

    failures = []
    for label, pair in pairs.items():
        if not pair["composition_unchanged_by_fix"]:
            failures.append(
                "%s: the plan's COMPOSITION changed. T089 re-points an edge "
                "whose relationship is unregistered, so no plan should move; "
                "a move means a consumer reaches the ValueRA edge by a path "
                "the registry does not describe. fixed=%r pre=%r"
                % (label, pair["fixed"]["composition"],
                   pair["pre_t089"]["composition"]))
        if not pair["closure_unchanged_by_fix"]:
            failures.append(
                "%s: the plan's CLOSURE changed. fixed=%r pre=%r"
                % (label, pair["fixed"]["closure"],
                   pair["pre_t089"]["closure"]))
    if census_matches_prior is False:
        failures.append(
            "the census does not reproduce %s row for row. The fix changes no "
            "registered edge, so the transfer it produces must be the same "
            "transfer -- a differing row is either the fix reaching the "
            "writer or drift in something else that landed since."
            % COMPARE_CENSUS_TO)
    elif census_matches_prior is None:
        print("[INFO] %s absent -- the row-for-row comparison did NOT run, "
              "and this artifact therefore rests on the plan pairs alone"
              % COMPARE_CENSUS_TO)

    if failures:
        print()
        for line in failures:
            print("[FAIL] %s" % line)
        return 1
    print()
    print("[OK]   T089: the producer changed (206->99 / 34->17 edges over the "
          "two audited corpora) and NO plan did, under either selection, with "
          "the registry held fixed at %d row(s)." % len(registry))
    return 0


def _rows_equal(prior_path: Path, current_path: Path):
    """Row-for-row equality of two census artifacts, ignoring run identity.

    Compares the per-class rows and the totals, NOT the whole document: a
    census carries its own run id, timestamps and source/destination paths,
    and demanding those match would make every comparison fail for reasons
    that are not findings.
    """
    #: Per-row fields that record HOW the row was reached rather than WHAT it
    #: measured. `notes` is free prose; the rest name documents and provenance
    #: that a re-run legitimately restates. Everything else -- every count,
    #: every verdict, `accounted_for`, both `unexplained_*` -- is compared.
    _IGNORED_ROW_FIELDS = ("notes",)

    def rows(path):
        doc = json.loads(path.read_text(encoding="utf-8"))
        out = {}
        for row in doc.get("classes", ()) or ():
            out[row.get("class")] = {k: v for k, v in row.items()
                                     if k not in _IGNORED_ROW_FIELDS}
        return out, doc.get("totals")

    prior_rows, prior_totals = rows(prior_path)
    cur_rows, cur_totals = rows(current_path)
    if prior_rows == cur_rows and prior_totals == cur_totals:
        return True
    only_prior = sorted(set(prior_rows) - set(cur_rows))
    only_cur = sorted(set(cur_rows) - set(prior_rows))
    changed = sorted(k for k in set(prior_rows) & set(cur_rows)
                     if prior_rows[k] != cur_rows[k])
    print("[INFO]   rows only in prior: %s" % (only_prior or "none"))
    print("[INFO]   rows only in this run: %s" % (only_cur or "none"))
    print("[INFO]   rows that differ: %s" % (changed or "none"))
    if prior_totals != cur_totals:
        print("[INFO]   totals differ: %r vs %r" % (prior_totals, cur_totals))
    return False


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
