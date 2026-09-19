"""Feature 038 -- the before/after the whole feature is actually judged on.

Every census this feature has run since Phase 6 was measured against `Mbugwe
LizzieHC practice`, because that is the corpus the phase gates were tuned on.
The DEFECT TABLE in `census-evidence.md` section 0 -- the one that justified
the feature existing -- was measured on two entirely different pairs:
`Ejagham W Mini` -> `Ejagham W Target` and `Ngoreme FLEx` -> `Ngoreme Target`.
Comparing a Mbugwe run to that table answers a question nobody asked.

This driver closes that gap the only way it can be closed: run the SAME two
sources through the CURRENT branch into freshly restored throwaway targets,
census each with the same shared starter baseline the pre-fix censuses used,
and diff the result class by class against the committed pre-fix artifact.

WHAT IS AND IS NOT HELD CONSTANT.

  * Held constant: the source projects, the class list, the starter baseline
    (`specs/038-transfer-fidelity-gaps/contracts/starter-baseline.json`), and
    the census instrument.
  * NOT held constant, and it must be said rather than smoothed over: the
    pre-fix targets were produced by an older transfer into a project whose
    own starting content is not the backup used here. The census subtracts the
    same starter baseline from both sides, so the NET per-class counts are
    comparable; the raw destination totals are not.
  * `Ngoreme FLEx` HAS DRIFTED since the pre-fix census was taken
    (`MoStemMsa` 1949 -> 1952, digest 052243ea... -> 2707b2f3...). The source
    column of the after-run is therefore measured live and will not match the
    before column exactly. Small, and reported rather than corrected.

NEITHER PRE-FIX TARGET IS TOUCHED. `Ngoreme Target` in particular is pinned in
`tests/integration/test_object_census.py` as "irreplaceable evidence of a
ruined transfer: it must never be write-enabled or restored". This driver
writes only to `GT038 <pair> After`, restored from a known backup first.

Usage:

    python debug/run038_before_after_pairs.py ejagham
    python debug/run038_before_after_pairs.py ngoreme

Add `--compare-only` to re-diff the already-committed censuses without
restoring, transferring or re-censusing anything.

Add `--no-census` to stop after the transfer, leaving every committed census
untouched. Use it when the question is answered by the run report alone -- T108
asks only whether `process_rules[*].input_contexts[*].co_created_shared` is
populated, and a census would neither help nor be comparable to a `before`
taken on a different destination. It is REFUSED on a target whose digest a
committed census records (`_EVIDENCE_TARGETS`).

Add `--tag NAME` to write the after-census and the diff under a task-tagged
name (`census-038-NAME-<pair>.json`, `before-after-038-NAME-<pair>.json`)
instead of the plain `-after` name. Without it, a re-run OVERWRITES the
committed `census-038-<pair>-after.json` in place -- which is how a committed
measurement quietly becomes a different measurement under the same filename.
The `t091`/`t094` artifacts already in `_snapshots` are exactly this shape and
were produced by hand; the flag makes them reproducible.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "tests" / "integration"))

BACKUP = _REPO / "backups" / "Target 2026-07-06 0218.fwbackup"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
_SNAPS = _REPO / "tests" / "integration" / "_snapshots"

#: The starter baseline BOTH pre-fix censuses were measured against. Using a
#: different one would move every net count and make the diff meaningless.
_BASELINE = (
    _REPO.parent / "GramTrans" / "specs" / "038-transfer-fidelity-gaps"
    / "contracts" / "starter-baseline.json"
)

_PAIRS = {
    "ejagham": {
        "source": "Ejagham W Mini",
        "target": "GT038 Ejagham After",
        "before": "census-038-ejagham.json",
    },
    "ngoreme": {
        "source": "Ngoreme FLEx",
        "target": "GT038 Ngoreme After",
        "before": "census-038-ngoreme.json",
    },
    # T108: the same Ejagham source into a DIFFERENT throwaway target, on
    # purpose. T107's committed censuses are asserted to hash to `GT038
    # Ejagham After` as it now stands (`TestT107TheBoundaryContextCreatePath::
    # test_these_artifacts_are_the_ones_that_now_reproduce`), so a re-run into
    # that project would drift T107's own evidence off its recorded digests --
    # the T102 failure T107 already had to edit T078's table for, one link
    # further on again. Added BESIDE `ejagham` rather than by editing its
    # target in place, so the pair that produced the committed before/after
    # diff stays runnable and reproducible.
    "ejagham-t108": {
        "source": "Ejagham W Mini",
        "target": "GT038 T108 Target",
        "before": "census-038-ejagham.json",
    },
}

#: Never write to these, whatever else changes.
_FORBIDDEN_TARGETS = {"Ngoreme Target", "Ejagham W Target", "Esperanto"}

#: Targets that are LIVE EVIDENCE for a committed artifact: a census on disk
#: records their `.fwdata` digest and a test asserts the file still hashes to
#: it. Re-transferring one does not corrupt anything, but it silently turns a
#: committed measurement into a description of a project that no longer
#: exists. Runs that only need a run report (`--no-census`) must therefore not
#: land in one -- refused rather than warned, because the damage is invisible
#: until an unrelated test goes red.
_EVIDENCE_TARGETS = {"GT038 Ejagham After", "GT038 Phase6 Target"}


def _rows(artifact: dict) -> dict:
    return {r["class"]: r for r in artifact.get("classes", ())}


def _net(row) -> int:
    if row is None:
        return 0
    v = row.get("destination_count_net")
    return 0 if v is None else int(v)


def main(argv) -> int:
    pair = (argv[1] if len(argv) > 1 else os.environ.get("GT038_PAIR", "")).lower()
    if pair not in _PAIRS:
        print("[FAIL] usage: python debug/run038_before_after_pairs.py "
              "{%s}" % "|".join(sorted(_PAIRS)))
        return 2
    spec = _PAIRS[pair]
    source, target = spec["source"], spec["target"]
    if target in _FORBIDDEN_TARGETS:
        print("[FAIL] refusing to write to %r" % target)
        return 1

    before_path = _SNAPS / spec["before"]
    if not before_path.is_file():
        print("[FAIL] no pre-fix census at %s" % before_path)
        return 1
    if not _BASELINE.is_file():
        print("[FAIL] no starter baseline at %s" % _BASELINE)
        return 1

    from harness import full_run
    from harness.restore import restore_target
    from gramtrans import census_cli

    tag = ""
    if "--tag" in argv:
        i = argv.index("--tag")
        if i + 1 >= len(argv):
            print("[FAIL] --tag needs a name")
            return 2
        tag = argv[i + 1].strip().lower()

    scratch = _REPO / "scratchpad" / ("038_after_" + (tag or pair))
    scratch.mkdir(parents=True, exist_ok=True)
    target_path = str(PROJECTS_ROOT / target / (target + ".fwdata"))
    after_path = (_SNAPS / ("census-038-%s-%s.json" % (tag, pair)) if tag
                  else _SNAPS / ("census-038-%s-after.json" % pair))

    # T108: a run whose whole question lives in the run report -- was the
    # shared `PhPhonData.ContextsOS` context CO-CREATED here, or already
    # there? -- needs the transfer and nothing after it. Censusing anyway
    # would answer a question nobody asked and add a second artifact to keep
    # current, and (worse) would have to be pointed at a `before` census of a
    # different destination.
    no_census = "--no-census" in argv

    compare_only = "--compare-only" in argv
    if no_census and compare_only:
        print("[FAIL] --no-census and --compare-only are mutually exclusive: "
              "one skips the census, the other re-diffs two of them")
        return 2
    if no_census and target in _EVIDENCE_TARGETS:
        print("[FAIL] refusing to re-transfer %r: a committed census records "
              "its .fwdata digest and a test asserts the file still hashes "
              "to it. Add a pair with its own throwaway target instead."
              % target)
        return 1

    if compare_only:
        # The diff is pure post-processing over two committed artifacts, so it
        # must be reproducible without a 50-second transfer and a restore.
        # Without this, correcting a presentation bug in the tables below
        # would mean re-running the measurement -- and a measurement re-run to
        # fix a display bug is how committed numbers quietly drift.
        if not after_path.is_file():
            print("[FAIL] --compare-only needs a committed after-census at %s"
                  % after_path)
            return 1
        print("[INFO] %s: --compare-only, re-diffing committed artifacts"
              % pair)

    if not compare_only:
        print("[INFO] %s: %r -> %r (throwaway, restored first)"
              % (pair, source, target))
        restore_target(target, BACKUP)

    report_path = str(_REPO / "_run_reports"
                      / ("038-%s-%s-report.json" % (tag or "after", pair)))
    report = None
    if not compare_only:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        print("[INFO] full transfer on the CURRENT branch (this takes a while)")
        _plan, report = full_run.run_full_transfer(
            source, target, target_path,
            exclude=frozenset(), ws_mapping_mode="full",
            report_path=report_path,
        )

        if no_census:
            print("[OK] --no-census: transfer only, nothing censused and no "
                  "committed census touched.")
            print("[OK] run report at %s" % report_path)
            print("     derive with: python "
                  "debug/derive038_t108_shared_context.py %s" % report_path)
            return 0

        census_path = scratch / ("%s-%s-census.json" % (pair, tag or "after"))
        print("[INFO] census")
        census_code = census_cli.main([
            "run",
            "--source", source,
            "--destination", target,
            "--baseline", str(_BASELINE),
            "--destination-freshly-created",
            "--run-report", report_path,
            "--out", str(census_path),
        ])
        print("[INFO] census run exit code = %s" % census_code)
        if not census_path.is_file():
            print("[FAIL] no census artifact produced")
            return 1
        after_path.write_text(census_path.read_text(encoding="utf-8"),
                              encoding="utf-8")
        print("[OK] wrote %s" % after_path)

    before = json.loads(before_path.read_text(encoding="utf-8"))
    after = json.loads(after_path.read_text(encoding="utf-8"))
    b_rows, a_rows = _rows(before), _rows(after)

    fixed, still_short, regressed, unchanged_ok = [], [], [], []
    not_evaluated = []
    for cls in sorted(set(b_rows) | set(a_rows)):
        b, a = b_rows.get(cls), a_rows.get(cls)
        bv = (b or {}).get("verdict_class")
        av = (a or {}).get("verdict_class")
        row = {
            "class": cls,
            "source_before": (b or {}).get("source_count"),
            "source_after": (a or {}).get("source_count"),
            "dest_before": _net(b), "dest_after": _net(a),
            "diff_before": (b or {}).get("difference"),
            "diff_after": (a or {}).get("difference"),
            "verdict_before": bv, "verdict_after": av,
        }
        # NOT_EVALUATED is not a shortfall and must not be listed as one.
        # `CmAnthroItem` is the live example: the restored backup omits the
        # anthropology list that the shared starter baseline carries, so the
        # row nets negative and the census declines to evaluate it. It
        # contributes 0 to `total_shortfall` and 0 to `unexplained_shortfall`
        # and is counted under `classes_not_evaluated`, so filing it beside
        # real losses reads as a regression that the totals do not contain.
        if av == "NOT_EVALUATED":
            not_evaluated.append(row)
        elif bv != "MATCHED" and av == "MATCHED":
            fixed.append(row)
        elif bv == "MATCHED" and av not in ("MATCHED", None):
            regressed.append(row)
        elif av not in ("MATCHED", None):
            still_short.append(row)
        else:
            unchanged_ok.append(row)

    payload = {
        "pair": pair,
        "source": source,
        "destination": target,
        "backup": BACKUP.name,
        "before_artifact": spec["before"],
        "after_artifact": after_path.name,
        "starter_baseline": str(_BASELINE),
        "totals_before": before.get("totals"),
        "totals_after": after.get("totals"),
        "verdict_before": [before.get("verdict"), before.get("exit_code")],
        "verdict_after": [after.get("verdict"), after.get("exit_code")],
        "fixed": fixed,
        "regressed": regressed,
        "still_short": still_short,
        "not_evaluated": not_evaluated,
        "counts": {"fixed": len(fixed), "regressed": len(regressed),
                   "still_short": len(still_short),
                   "not_evaluated": len(not_evaluated),
                   "matched_both": len(unchanged_ok)},
        # Preserved across --compare-only: re-diffing a committed
        # measurement must not blank the run that produced it.
        "run_id": (getattr(report, "run_id", "") if report is not None
                   else ((after.get("transfer_run") or {}).get("run_id") or "")),
    }
    out = (_SNAPS / ("before-after-038-%s-%s.json" % (tag, pair)) if tag
           else _SNAPS / ("before-after-038-%s.json" % pair))
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print("[OK] wrote %s" % out)

    def _table(label, rows):
        print()
        print("       %s (%d)" % (label, len(rows)))
        if not rows:
            print("         (none)")
            return
        print("       %-26s %18s %18s" % ("class", "before", "after"))
        for r in rows:
            print("       %-26s %7s -> %-8s %7s -> %-8s" % (
                r["class"], r["source_before"], r["dest_before"],
                r["source_after"], r["dest_after"]))

    print()
    print("  ==== %s: PRE-FIX vs THIS BRANCH ====" % pair.upper())
    print("       verdict  %s -> %s"
          % (payload["verdict_before"], payload["verdict_after"]))
    for k in ("classes_matched", "classes_shortfall", "total_shortfall",
              "unexplained_shortfall", "duplicate_extra_objects"):
        print("       %-24s %10s -> %-10s"
              % (k, (before.get("totals") or {}).get(k),
                 (after.get("totals") or {}).get(k)))
    _table("FIXED -- was not MATCHED, now MATCHED", fixed)
    _table("REGRESSED -- was MATCHED, now is not", regressed)
    _table("STILL SHORT", still_short)
    _table("NOT EVALUATED -- contributes 0 to either shortfall total",
           not_evaluated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
