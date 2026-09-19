"""Read-only, LIVE-EXECUTION smoke test for T045d
(specs/035-fullsweep-fidelity/tasks.md) -- ``debug/fullsweep/field_dispatch.py``'s
``build_field_source``, the live ``field_source(cls, guid)`` reader
``debug/fullsweep/census.py``'s ``census_fields`` requires.

Mirrors ``debug/probe_field_census_api.py``'s pattern: this script is the
live half of a feature whose pytest suite (``tests/unit/test_035_field_dispatch.py``)
is deliberately offline-only (no FLEx project, no LCM). A reader that has
never executed against live LCM is not done, so this script is what proves
it -- it opens a project, runs ``census.census_fields`` end to end over a
handful of in-scope classes via the real dispatch table, and prints the
counts and the three-mandated-class unreachable status.

SAFETY (read-only by construction):
  * ``OpenProject`` is always called with ``writeEnabled=False``; there is no
    flag to change this.
  * No Save/Commit/Undo/Redo/mutating operation class is imported or used.
  * Unlike ``debug/probe_field_census_api.py``, this script does NOT carry a
    ``^Target([0-9]+)?$`` project-name refusal -- T045d's task text calls
    that refusal out as a trap not to inherit, since the sweep's whole job is
    reading a project named ``Target<N>``. This script only ever opens the
    hardcoded default (``Ejagham Mini``) unless a caller explicitly names a
    different project, and even then only ever read-only.

Usage
-----
    python debug/probe_field_dispatch_t045d.py [--project "Ejagham Mini"]
"""
from __future__ import annotations

import argparse
import sys


def _open_readonly(name: str):
    import flexicon
    flexicon.FLExInitialize()
    try:
        from SIL.WritingSystems import Sldr  # noqa: PLC0415
        if not Sldr.IsInitialized:
            Sldr.Initialize(True)
    except Exception:  # noqa: BLE001 -- SLDR init is best-effort
        pass
    from flexicon import FLExProject  # noqa: PLC0415
    proj = FLExProject()
    proj.OpenProject(projectName=name, writeEnabled=False)
    return proj


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="Ejagham Mini")
    args = parser.parse_args(argv)

    # sys.path bootstrap so `debug.fullsweep` is importable when run as a
    # bare script (mirrors debug/fullsweep/__init__.py's own bootstrap).
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from debug.fullsweep import census, field_dispatch as fd  # noqa: PLC0415

    proj = _open_readonly(args.project)
    try:
        print("=== OPEN === project=%r" % (args.project,))

        # --- 1. the mandatory-hole classes: never crash, never fabricate ---
        print("\n=== Mandatory unreachable-class handling ===")
        for cls in sorted(fd.MANDATORY_UNREACHABLE_CLASSES):
            assert not fd.is_dispatchable(cls)
            print("  %-20s is_dispatchable=False (reason on file)" % cls)
        field_source = fd.build_field_source(proj)
        for cls in sorted(fd.MANDATORY_UNREACHABLE_CLASSES):
            try:
                field_source(cls, "00000000-0000-0000-0000-000000000000")
                print("  %-20s UNEXPECTED: did not raise" % cls)
                return 1
            except fd.UnreachableClassError as exc:
                print("  %-20s raised UnreachableClassError (expected): %s"
                      % (cls, str(exc)[:80] + "..."))

        # --- 2. a real corpus survey over a handful of dispatchable classes -
        print("\n=== Smoke census over a handful of live classes ===")
        smoke_classes = ["PartOfSpeech", "LexEntry", "LexSense", "PhPhoneme",
                          "PhEnvironment", "WfiWordform"]
        objects_by_class = {}
        for cls in smoke_classes:
            accessor_name = fd.CLASS_TO_ACCESSOR[cls]
            ops = getattr(proj, accessor_name)
            items = list(ops.GetAll())[:5]
            objects_by_class[cls] = [str(it.Guid) for it in items]
            print("  %-14s accessor=%-10s sampled=%d" % (cls, accessor_name, len(items)))

        roster = census.load_expected_divergent()
        successes = {}
        failures = {}
        for cls, guids in objects_by_class.items():
            try:
                c = census.census_fields({cls: guids}, field_source=field_source,
                                          roster=roster)
                successes[cls] = c
            except census.CensusContractError as exc:
                failures[cls] = str(exc)

        print("\n--- results ---")
        for cls, c in successes.items():
            cov = c.coverage[cls]
            print("  %-14s OK   model=%3d syncable=%2d omitted=%2d compared=%2d objects=%d"
                  % (cls, len(cov.model_fields), len(cov.syncable_fields),
                     len(cov.engine_omitted), len(cov.compared), len(c.values.get(cls, {}))))
        for cls, msg in failures.items():
            print("  %-14s FAILED (CensusContractError): %s" % (cls, msg[:120]))

        print("\nsuccess_count=%d failure_count=%d" % (len(successes), len(failures)))
        return 0
    finally:
        proj.CloseProject()
        print("\n=== CLOSED ===")


if __name__ == "__main__":
    sys.exit(main())
