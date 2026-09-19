"""Feature 038 Phase 6 (US5) live acceptance driver -- T063 / T064.

Transfers `Mbugwe LizzieHC practice` (the ONLY sanctioned project with affix
process rules: 18 `MoAffixProcess`, 124 `MoAffixAllomorph`, 137
`MoStemAllomorph`, `ContextsOS=93`) into a target restored blank, then counts
the destination class by class and writes a snapshot the integration test
asserts against.

WHY A DRIVER AND NOT A TEST. A live run restores and rewrites a project and
takes minutes; `tests/integration/test_038_two_mode_and_tallies.py` and
`test_object_census.py::TestMeasuredCensusSnapshots` already establish the
discipline -- run once here, COMMIT the measurement, and let the test assert
against the recorded numbers. A unit-suite invocation may not rewrite a FLEx
project by surprise.

WHAT IT PROVES (create-path contract section 5, layer (c)). A downgrade shows
as `MoAffixProcess 0` with `MoAffixAllomorph` inflated by exactly the rule
count -- the +13/+1 excess signature that exposed the original defect. So both
halves are required, and the per-member counts are required too, because a
correctly-classed rule with an empty `OutputOS` would satisfy both totals while
having lost everything that makes it a rule.

Usage (writes to a THROWAWAY target, restored first):

    python debug/run038_phase6_live.py

Set `GT038_PHASE6_TARGET` to override the target project name. The target is
restored from `backups/Target 2026-07-06 0218.fwbackup` before every run, so
the measurement is repeatable and no real language data is in the blast radius
(CLAUDE.md's restore-before-write rule).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "tests" / "integration"))

SOURCE = "Mbugwe LizzieHC practice"
TARGET = os.environ.get("GT038_PHASE6_TARGET", "GT038 Phase6 Target")
BACKUP = _REPO / "backups" / "Target 2026-07-06 0218.fwbackup"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
#: Snapshot basenames, overridable so a LATER pass can re-measure without
#: overwriting an earlier pass's committed artifact.
#:
#: T102 is the reason this is a knob and not a constant.
#: `census-038-mbugwe-phase6.json` is one link in a chain of pairwise equality
#: comparisons (`test_038_closure_edge_audit.py` compares it row by row
#: against the `-t067-`, `-t068-` and `-t069-` artifacts to prove that
#: registering a closure edge moved no object count). T076 DOES move counts --
#: that is the whole point of it -- so overwriting this link would turn three
#: passing tests red for a reason unrelated to what they assert, which is
#: exactly the drift T102 says not to cause. T077 therefore writes its own
#: pair and leaves T063's evidence standing as the BEFORE.
_SNAP_SUFFIX = os.environ.get("GT038_PHASE6_SNAPSHOT_SUFFIX", "")
SNAPSHOT = (_REPO / "tests" / "integration" / "_snapshots"
            / ("process-rules-038%s-mbugwe.json" % _SNAP_SUFFIX))
CENSUS_SNAPSHOT = (_REPO / "tests" / "integration" / "_snapshots"
                   / ("census-038%s-mbugwe-phase6.json" % _SNAP_SUFFIX))
_SCRATCH = _REPO / "scratchpad" / "038_census"

#: Every class in the process-rule graph, plus the two allomorph classes the
#: downgrade would inflate. Counted in BOTH projects so the snapshot records a
#: delta rather than a bare destination total -- a destination total alone
#: cannot distinguish "transferred" from "was already there".
COUNTED_CLASSES = (
    "MoAffixProcess",
    "MoAffixAllomorph",
    "MoStemAllomorph",
    "MoInsertPhones",
    "MoCopyFromInput",
    "MoModifyFromInput",
    "MoInsertNC",
    "PhVariable",
    "PhSimpleContextSeg",
    "PhSimpleContextNC",
    "PhSimpleContextBdry",
    "PhSequenceContext",
    "PhIterationContext",
    "PhPhoneme",
    "PhNCSegments",
    "PhNCFeatures",
)


def _count_classes(project) -> dict:
    """`{class_name: count}` over the whole project, exact-class."""
    from gramtrans.Lib import census as _census
    counts = {}
    for class_name in COUNTED_CLASSES:
        try:
            counts[class_name] = sum(
                1 for _ in _census.objects_in_class(project, class_name))
        except Exception as exc:  # noqa: BLE001 -- record, never guess
            counts[class_name] = "ERROR: %s: %s" % (type(exc).__name__, exc)
    return counts


def _rule_shapes(project) -> list:
    """Per-rule member census: `[{guid, inputs: {...}, outputs: {...}}, ...]`.

    This is what tells an empty-`OutputOS` shell from a real rule, which the
    project-wide totals cannot do on their own.
    """
    from gramtrans.Lib import census as _census
    from gramtrans.Lib.categories import _cast_lcm, _guid_str_from, _class_name_of
    shapes = []
    for rule in _census.objects_in_class(project, "MoAffixProcess"):
        cast = _cast_lcm(rule, "IMoAffixProcess")
        inputs, outputs = {}, {}
        for member in list(getattr(cast, "InputOS", None) or ()):
            key = _class_name_of(member) or "(unknown)"
            inputs[key] = inputs.get(key, 0) + 1
        for step in list(getattr(cast, "OutputOS", None) or ()):
            key = _class_name_of(step) or "(unknown)"
            outputs[key] = outputs.get(key, 0) + 1
        shapes.append({
            "guid": _guid_str_from(rule),
            "inputs": inputs,
            "outputs": outputs,
            "input_total": sum(inputs.values()),
            "output_total": sum(outputs.values()),
        })
    shapes.sort(key=lambda r: r["guid"])
    return shapes


def main() -> int:
    from harness import full_run
    from harness.restore import restore_target

    print("[INFO] restoring %r from %s" % (TARGET, BACKUP.name))
    restore_target(TARGET, BACKUP)

    print("[INFO] counting the SOURCE (read-only): %r" % SOURCE)
    src = full_run._open_source_readonly(SOURCE)
    try:
        source_counts = _count_classes(src)
        source_shapes = _rule_shapes(src)
    finally:
        try:
            src.CloseProject()
        except Exception:  # noqa: BLE001
            pass
    print("[INFO] source MoAffixProcess = %s" % source_counts["MoAffixProcess"])

    target_path = str(PROJECTS_ROOT / TARGET / (TARGET + ".fwdata"))
    # T064: the destination's OWN starter baseline, captured from the
    # freshly restored project BEFORE anything is written. A census without
    # one is BASELINE_MISSING (exit 4) and there is deliberately no flag that
    # turns that into a pass.
    _SCRATCH.mkdir(parents=True, exist_ok=True)
    baseline_path = _SCRATCH / "phase6-starter.json"
    print("[INFO] capturing the starter baseline")
    from gramtrans import census_cli
    code = census_cli.main([
        "capture-baseline",
        "--project", TARGET,
        "--out", str(baseline_path),
    ])
    if code != 0:
        print("[ERROR] capture-baseline exited %s" % code)
        return code

    print("[INFO] counting the DESTINATION before the transfer")
    before = full_run._open_source_readonly(TARGET)
    try:
        before_counts = _count_classes(before)
    finally:
        try:
            before.CloseProject()
        except Exception:  # noqa: BLE001
            pass

    print("[INFO] transferring %r -> %r (this takes minutes)" % (SOURCE, TARGET))
    report_path = str(_REPO / "_run_reports"
                      / ("038-phase6%s-mbugwe-report.json" % _SNAP_SUFFIX))
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    _plan, report = full_run.run_full_transfer(
        SOURCE, TARGET, target_path,
        exclude=frozenset(),          # a FULL copy -- stems included
        ws_mapping_mode="full",
        report_path=report_path,
    )

    print("[INFO] counting the DESTINATION after the transfer")
    after = full_run._open_source_readonly(TARGET)
    try:
        after_counts = _count_classes(after)
        after_shapes = _rule_shapes(after)
    finally:
        try:
            after.CloseProject()
        except Exception:  # noqa: BLE001
            pass

    rules = list(getattr(report, "process_rules", ()) or ())
    payload = {
        "source": SOURCE,
        "destination": TARGET,
        "backup": BACKUP.name,
        "source_counts": source_counts,
        "before_counts": before_counts,
        "after_counts": after_counts,
        "delta": {
            k: (after_counts[k] - before_counts[k])
            for k in COUNTED_CLASSES
            if isinstance(after_counts.get(k), int)
            and isinstance(before_counts.get(k), int)
        },
        "source_rule_shapes": source_shapes,
        "after_rule_shapes": after_shapes,
        "report": {
            "run_id": getattr(report, "run_id", ""),
            "process_rules_total": len(rules),
            "process_rules_reproduced": sum(1 for r in rules if r.reproduced),
            "process_rules_not_reproduced": [
                {
                    "source_guid": r.source_guid,
                    "reason": r.not_reproducible_reason,
                }
                for r in rules if not r.reproduced
            ],
        },
    }
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print("[OK] wrote %s" % SNAPSHOT)

    print("[INFO] MoAffixProcess  delta = %s (source %s)"
          % (payload["delta"].get("MoAffixProcess"),
             source_counts["MoAffixProcess"]))
    print("[INFO] MoAffixAllomorph delta = %s (source %s)"
          % (payload["delta"].get("MoAffixAllomorph"),
             source_counts["MoAffixAllomorph"]))
    print("[INFO] rules reproduced = %s / %s"
          % (payload["report"]["process_rules_reproduced"],
             payload["report"]["process_rules_total"]))

    # T064 -- the census gate, predicate P4.
    print("[INFO] running the census gate")
    census_path = _SCRATCH / "phase6-census.json"
    code = census_cli.main([
        "run",
        "--source", SOURCE,
        "--destination", TARGET,
        "--baseline", str(baseline_path),
        "--destination-freshly-created",
        "--run-report", report_path,
        "--out", str(census_path),
    ])
    print("[INFO] census run exit code = %s" % code)
    if census_path.is_file():
        CENSUS_SNAPSHOT.write_text(
            census_path.read_text(encoding="utf-8"), encoding="utf-8")
        print("[OK] wrote %s" % CENSUS_SNAPSHOT)
        gate = census_cli.main(["gate", "--artifact", str(census_path),
                                "--phase", "4"])
        print("[INFO] gate --phase 4 exit code = %s" % gate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
