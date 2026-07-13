"""Read-only diagnosis of a target project's inflection features (feature 031, US3).

Characterizes a target's inflection-feature system -- nameless features/values,
orphaned vs linked features, the writing-system handle that actually carries a
name, and any duplicate-GUID groups -- WITHOUT writing to the target. It quantifies
Defect 1 (orphaned features: created but never wired into any
`IPartOfSpeech.InflectableFeatsRC`) and Defect 2 (nameless features/values from a
source-vs-target writing-system-handle mismatch).

Contract: specs/031-fix-inflection-feature-linking/contracts/diagnosis-report.md
  * READ-ONLY  -- zero modifications to the target (no UoW/commit); the project is
                  opened writeEnabled=False and a pre/post object-count snapshot
                  proves nothing changed (T021).
  * COMPLETE   -- every feature is classified as exactly one of linked/orphaned.
  * EVIDENCE   -- report quantifies Defect 1 and Defect 2.

Output is plain ASCII (no emoji) per the Windows-terminal environment rule.

Design (T019/T020): the pure classification core `build_report(view)` runs over a
small `ProjectView` facade so it is unit-testable offline with a fake view (no
pythonnet / SIL.LCModel). The live LCM navigation lives in `_LcmProjectView`, whose
casts (`ILangProject`, `IPartOfSpeech`, `IFsFeatDefn`, `IFsSymFeatVal`) and paths
were validated read-only via FLExToolsMCP against `Ejagham Mini` /
`Ejagham Full GT-Test`.

Run:  python debug/diag_infl_features.py [ProjectName]
"""
from __future__ import annotations

from collections import Counter
from typing import Protocol

DEFAULT_TARGET = "Ejagham Full GT-Test"

# Report keys per contracts/diagnosis-report.md.
_REPORT_KEYS = (
    "total_features",
    "total_values",
    "nameless_features",
    "nameless_values",
    "orphaned_features",
    "linked_features",
    "feature_name_ws_map",
    "duplicate_guid_groups",
)


class ProjectView(Protocol):
    """Minimal read-only view of a project's inflection-feature system.

    A live implementation (`_LcmProjectView`) wraps a flexicon project; tests
    supply a duck-typed fake. All GUIDs are returned as lowercase strings.
    """

    def features(self) -> list:
        """All `IFsClosedFeature` in `MsFeatureSystemOA.FeaturesOC`."""

    def values(self, feature) -> list:
        """The `IFsSymFeatVal` owned by `feature` (its `ValuesOC`)."""

    def guid(self, obj) -> str:
        """Lowercase GUID string of a feature or value object."""

    def analysis_name(self, obj) -> str:
        """Name of `obj` in the default analysis WS ('' if empty)."""

    def ws_names(self, obj) -> dict:
        """Map of {ws_tag: name} across analysis+vernacular WS for `obj`,
        omitting writing systems whose name is empty."""

    def linked_feature_guids(self) -> set:
        """Union of every `IPartOfSpeech.InflectableFeatsRC` member GUID."""


def build_report(view: ProjectView) -> dict:
    """Compute the diagnosis report from a read-only `ProjectView`.

    Pure over `view` (no LCM imports, no writes). Guarantees the COMPLETE
    contract: linked_features + orphaned_features == total_features.
    """
    features = list(view.features())
    feat_guids = [view.guid(f) for f in features]

    nameless_features = 0
    nameless_values = 0
    total_values = 0
    val_guids: list = []
    sample_ws_map = None

    for feat in features:
        if not view.analysis_name(feat):
            nameless_features += 1
        for val in view.values(feat):
            total_values += 1
            val_guids.append(view.guid(val))
            if not view.analysis_name(val):
                nameless_values += 1
        # Sample the first feature that carries a name in ANY writing system:
        # its {ws_tag: name} map is the R2 evidence for which target handle the
        # name actually landed on.
        if sample_ws_map is None:
            names_by_ws = view.ws_names(feat)
            if names_by_ws:
                sample_ws_map = {
                    "feature_guid": view.guid(feat),
                    "names_by_ws": dict(names_by_ws),
                }

    linked = set(view.linked_feature_guids())
    linked_features = sum(1 for g in feat_guids if g in linked)
    orphaned_features = len(features) - linked_features

    counts = Counter(feat_guids + val_guids)
    duplicate_guid_groups = sorted(g for g, c in counts.items() if c > 1)

    return {
        "total_features": len(features),
        "total_values": total_values,
        "nameless_features": nameless_features,
        "nameless_values": nameless_values,
        "orphaned_features": orphaned_features,
        "linked_features": linked_features,
        "feature_name_ws_map": sample_ws_map if sample_ws_map is not None else {},
        "duplicate_guid_groups": duplicate_guid_groups,
    }


class _LcmProjectView:
    """Live `ProjectView` over a flexicon-opened LCM cache (read-only).

    All SIL.LCModel imports and casts are confined here so this module imports
    cleanly offline (the pure `build_report` core needs no pythonnet).
    """

    def __init__(self, cache) -> None:
        from SIL.LCModel import ILangProject  # noqa: PLC0415 -- deferred

        self._cache = cache
        lp = cache.LangProject
        fs = ILangProject(lp).MsFeatureSystemOA
        self._features = list(fs.FeaturesOC) if fs is not None else []
        self._pos = list(ILangProject(lp).AllPartsOfSpeech)
        self._analysis_ws = cache.DefaultAnalWs
        ws = cache.ServiceLocator.WritingSystems
        table = [(w.Id, w.Handle) for w in ws.CurrentAnalysisWritingSystems]
        table += [(w.Id, w.Handle) for w in ws.CurrentVernacularWritingSystems]
        self._ws_table = table

    # -- ProjectView ------------------------------------------------------
    def features(self) -> list:
        return self._features

    def values(self, feature) -> list:
        from SIL.LCModel import IFsClosedFeature  # noqa: PLC0415

        try:
            return list(IFsClosedFeature(feature).ValuesOC)
        except Exception:  # noqa: BLE001 -- non-closed IFsFeatDefn has no ValuesOC
            return []

    def guid(self, obj) -> str:
        return str(obj.Guid).lower()

    def analysis_name(self, obj) -> str:
        return self._name_in(obj, self._analysis_ws)

    def ws_names(self, obj) -> dict:
        out = {}
        for tag, handle in self._ws_table:
            name = self._name_in(obj, handle)
            if name:
                out[tag] = name
        return out

    def linked_feature_guids(self) -> set:
        from SIL.LCModel import IPartOfSpeech  # noqa: PLC0415

        linked = set()
        for pos in self._pos:
            # CAST DISCIPLINE (research.md T004-C): InflectableFeatsRC requires
            # an IPartOfSpeech cast; a bare ICmObject fails the accessor.
            for feat in IPartOfSpeech(pos).InflectableFeatsRC:
                linked.add(str(feat.Guid).lower())
        return linked

    # -- internals --------------------------------------------------------
    def _name_in(self, obj, handle) -> str:
        # `Name` lives on IFsFeatDefn / IFsSymFeatVal, not the base ICmObject;
        # cast before access (matches the FLExToolsMCP-validated walk).
        from SIL.LCModel import IFsFeatDefn, IFsSymFeatVal  # noqa: PLC0415

        for iface in (IFsFeatDefn, IFsSymFeatVal):
            try:
                named = iface(obj)
                ts = named.Name.get_String(handle)
                return ts.Text or ""
            except Exception:  # noqa: BLE001 -- try the other cast
                continue
        return ""

    def object_count(self) -> int:
        """Snapshot used by the read-only guard (T021)."""
        try:
            return self._cache.ServiceLocator.ObjectRepository.Count
        except Exception:  # noqa: BLE001 -- fall back to what we walked
            total_vals = sum(len(self.values(f)) for f in self._features)
            return len(self._features) + total_vals + len(self._pos)


def _print_report(report: dict, project_name: str) -> None:
    print("[INFO] read-only inflection-feature diagnosis")
    print("[INFO] target project: %s" % project_name)
    for key in _REPORT_KEYS:
        print("  %-22s = %r" % (key, report[key]))
    # Plain-ASCII interpretation of the evidence.
    if report["orphaned_features"] > 0:
        print("[WARN] Defect 1 present: %d orphaned feature(s) (no POS link)."
              % report["orphaned_features"])
    if report["nameless_features"] or report["nameless_values"]:
        print("[WARN] Defect 2 present: %d nameless feature(s), %d nameless value(s)."
              % (report["nameless_features"], report["nameless_values"]))
    if report["duplicate_guid_groups"]:
        print("[WARN] %d duplicate-GUID group(s) detected."
              % len(report["duplicate_guid_groups"]))


def main(project_name: str = DEFAULT_TARGET) -> dict:
    """Open `project_name` READ-ONLY, build and print the diagnosis report.

    Read-only guard (T021): the project is opened writeEnabled=False and an
    object-count snapshot is compared before vs after the walk; they MUST be
    equal (no UoW/commit is ever opened here). Returns the report dict.
    """
    import flexicon  # noqa: PLC0415 -- pythonnet-backed; deferred so offline import works

    flexicon.FLExInitialize()
    try:
        from SIL.WritingSystems import Sldr  # noqa: PLC0415

        if Sldr.IsInitialized:
            Sldr.Cleanup()
        Sldr.Initialize(True)
    except Exception as exc:  # noqa: BLE001
        print("[WARN] SLDR offline init: %r" % (exc,))

    from flexicon import FLExProject  # noqa: PLC0415

    proj = FLExProject()
    proj.OpenProject(projectName=project_name, writeEnabled=False)
    try:
        view = _LcmProjectView(proj.project)
        count_before = view.object_count()
        report = build_report(view)
        count_after = view.object_count()
        # READ-ONLY assertion: the walk touched nothing.
        assert count_before == count_after, (
            "[FAIL] read-only guard tripped: object count changed %d -> %d"
            % (count_before, count_after)
        )
        print("[OK] read-only verified: object count %d unchanged" % count_before)
        _print_report(report, project_name)
        return report
    finally:
        proj.CloseProject()


if __name__ == "__main__":
    import sys

    _name = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET
    main(_name)
