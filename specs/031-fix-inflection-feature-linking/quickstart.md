# Quickstart / Validation Guide: Inflection-Feature Linking Fix

**Feature**: 031-fix-inflection-feature-linking | **Date**: 2026-07-13

How to validate the fix end-to-end. Offline unit tests prove logic; the live pair proves
the LCM behavior. See [data-model.md](data-model.md) and
[contracts/](contracts/) for details referenced below.

## Prerequisites

- flexicon installed editable: `pip install -e D:/Github/_Projects/_LEX/flexlibs2`
- Reference projects available to FlexTools: source **Ejagham Mini**, target **Ejagham
  Full GT-Test**.
- A **clean** target: restore `Ejagham Full GT-Test` from a pre-transfer backup (the
  fix is prevention-only, FR-011 — do not validate against the already-polluted target).
- No FLEx GUI open on the target; no `.lock` present.

## Step 0 — Read-only diagnosis (US3, before any fix)

Run the diagnosis against the current (possibly polluted) target to capture the "before"
evidence — see [contracts/diagnosis-report.md](contracts/diagnosis-report.md).

Expected (pre-fix): `orphaned_features > 0` (Defect 1) and `nameless_features` /
`nameless_values > 0` or a WS-handle mismatch in `feature_name_ws_map` (Defect 2).
**Assert 0 modifications to the target.**

## Step 1 — Offline unit tests (logic)

Run the unit suite (from a worktree, not `main`):

```powershell
python -m pytest tests/unit/test_031_infl_feature_linking.py `
                 tests/unit/test_categories_inflection_features.py -q
```

Covers, with mocked LCM handles:
- **US1 / C1+C2**: plan gathers `(pos, feature)` links from source `InflectableFeatsRC`;
  preview shows one **Link** row per pair; the wiring post-pass adds each feature to the
  target POS `InflectableFeatsRC`, idempotently; a missing endpoint yields a reported
  `Skip(DEPENDENCY_UNRESOLVED)`, never a write.
- **US2 / C3**: name/abbr/desc are written via the target WS handle (ws-mapped), so a
  transferred feature/value is never nameless; a feature present by feature-level GUID
  is not re-created.
- **US2 / C4**: feature rows classify against the feature-level GUID set (a present
  feature reads `in_target`, not `new`).

## Step 2 — Live Preview (non-destructive)

Transfer Grammar Ejagham Mini → clean Ejagham Full GT-Test in **Preview** mode with
`Grammatical Categories` + `Inflection Features` selected.

Verify:
- Preview lists the transferred features **and** a distinct **Link** row per
  feature→category association (SC-004 / VR-5).
- No target writes occur (object counts unchanged vs Step 0 clean baseline).

## Step 3 — Live Move (first run)

Run the same transfer in **Move** mode.

Verify in FieldWorks:
- Open a lexical entry whose category carries the features (e.g. a Noun): the
  transferred features (e.g. `class`, `number`) are **selectable** (SC-001 / US1 AS-1).
- The transferred features and values display with proper **names** — no bare-GUID rows
  (SC-002 / US1 AS-2 / VR-2).
- Re-run the diagnosis: `orphaned_features == 0` for the transferred set;
  `nameless_features == 0`.

## Step 4 — Live re-run (idempotency, SC-003)

Snapshot the feature/value/link inventory (counts + GUIDs), then run the **identical
Move** again against the same target.

Verify:
- 0 new features, 0 new values, 0 new `InflectableFeatsRC` memberships (SC-003 / US2).
- 0 nameless/duplicate records introduced (VR-1/VR-3).
- Preview on the second run shows the features and links as already-present
  (`SKIP`/already-linked), not `NEW`/`Link`.

## Evidence to capture (quality gate)

- Pre/post diagnosis reports (Step 0 vs Step 3/4).
- Pre/post Import Residue / `[GT-Tag]` markers on created features.
- Screenshot or object dump showing features selectable on a lexical entry.

## Done when

- All offline tests green.
- Live Steps 2–4 pass against the clean reference pair.
- Success criteria SC-001…SC-005 all demonstrated with attached evidence.
