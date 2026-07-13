"""Read-only diagnosis of a target project's inflection features (feature 031, US3).

Scaffold (T003): opens a target project READ-ONLY and prints an empty report
dict. The real walk (MsFeatureSystemOA.FeaturesOC; nameless/orphaned/linked
classification; WS-handle sampling; duplicate-GUID detection) is implemented in
T020/T021 per specs/031-fix-inflection-feature-linking/contracts/diagnosis-report.md.

CONTRACT: this helper MUST perform zero writes to the target (no UoW/commit).
Output is plain ASCII (no emoji) per the Windows-terminal environment rule.
"""
from __future__ import annotations

DEFAULT_TARGET = "Ejagham Full GT-Test"


def build_report() -> dict:
    """Return the (empty) diagnosis report skeleton.

    Keys per contracts/diagnosis-report.md. T020 fills these in from a
    read-only walk of the target's feature system.
    """
    return {
        "total_features": 0,
        "total_values": 0,
        "nameless_features": 0,
        "nameless_values": 0,
        "orphaned_features": 0,
        "linked_features": 0,
        "feature_name_ws_map": {},
        "duplicate_guid_groups": [],
    }


def main(project_name: str = DEFAULT_TARGET) -> dict:
    report = build_report()
    print("[INFO] read-only inflection-feature diagnosis (scaffold)")
    print("[INFO] target project: %s" % project_name)
    for key in sorted(report):
        print("  %-22s = %r" % (key, report[key]))
    return report


if __name__ == "__main__":
    main()
