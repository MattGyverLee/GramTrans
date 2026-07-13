# Contract: Read-Only Inflection-Feature Diagnosis

**Feature**: 031-fix-inflection-feature-linking (User Story 3)

A read-only diagnostic that characterizes a target project's inflection features. It
MUST NOT write to the target under any circumstance.

## Invocation

A standalone read-only helper (e.g. `debug/diag_infl_features.py`) run against a target
project (default `Ejagham Full GT-Test`), or an equivalent FLExTools MCP read module.

## Output report (structure)

| Field | Meaning |
|---|---|
| `total_features` | Count of `IFsClosedFeature` in `MsFeatureSystemOA.FeaturesOC`. |
| `total_values` | Count of `IFsSymFeatVal` across all features. |
| `nameless_features` | Features whose `Name` is empty in the default analysis WS. |
| `nameless_values` | Values whose `Name` is empty in the default analysis WS. |
| `orphaned_features` | Features referenced by **zero** `IPartOfSpeech.InflectableFeatsRC`. |
| `linked_features` | Features referenced by **at least one** POS. |
| `feature_name_ws_map` | For a sampled named feature: which target WS handle actually carries the name (evidence for R2). |
| `duplicate_guid_groups` | Any features/values sharing a GUID (should be empty). |

## Contract assertions

- **READ-ONLY**: 0 modifications to the target; no UoW/commit is opened. Verifiable by
  comparing the target `.fwdata` mtime / a pre/post object-count snapshot.
- **COMPLETE**: every feature is classified as exactly one of `linked` or `orphaned`.
- **EVIDENCE**: the report quantifies Defect 1 (`orphaned_features > 0` before the fix)
  and Defect 2 (`nameless_features`/`nameless_values > 0`, and/or the WS-handle mismatch
  in `feature_name_ws_map`).

## Acceptance mapping

- SC-005: report produced with 0 target modifications.
- US3 AS-1: `nameless_features` + `nameless_values` reported.
- US3 AS-2: `orphaned_features` vs `linked_features` reported.
