# Contract: Feature → Category Link (planned action + wiring post-pass)

**Feature**: 031-fix-inflection-feature-linking

Internal contract for the new feature→category linkage. No external/public API changes;
these are the internal seams other transfer code and tests depend on.

## C1 — Plan-time: link gathering

**When**: during Preview plan-building, while `GRAM_CATEGORIES` and/or
`INFLECTION_FEATURES` are enabled in the selection.

**Behavior**:
- For each Part of Speech in scope (created or matched), read source
  `IPartOfSpeech.InflectableFeatsRC`.
- For each referenced `IFsClosedFeature` that is in the transfer scope, record a link
  binding `(target_pos_guid, feature_guid)` on the run-plan.
- Emit one **preview row** per link with proposed action **Link** (Principle III action
  vocabulary), labelled with the POS name and feature name.

**Contract assertions**:
- COUNT: number of link rows in Preview == number of `(pos, feature)` pairs in source
  `InflectableFeatsRC` restricted to in-scope endpoints.
- NO-WRITE: gathering performs zero writes to the target (Preview default).
- DEDUP: a `(pos, feature)` pair already present in the **target's** `InflectableFeatsRC`
  is shown as `SKIP`/already-linked, not `Link`.

## C2 — Move-time: wiring post-pass

**Signature** (mirrors `_run_post_pass_a(context, target, tag=None) -> list[Skip]`):

```
def _run_infl_feature_link_pass(context, target, tag=None) -> list[Skip]:
    ...
```

**Registration**: invoked exactly once per `execute()` via `_run_tail_once` on the last
executed action of the relevant category (after both `GRAM_CATEGORIES` and
`INFLECTION_FEATURES` actions have executed).

**Behavior** per `(target_pos_guid, feature_guid)` binding:
1. Resolve `target_pos` = in-plan POS, else `target.get_object_by_guid(target_pos_guid)`.
   If unresolved → `Skip(category=GRAM_CATEGORIES, reason=DEPENDENCY_UNRESOLVED)`.
2. Resolve `target_feat` = in-plan feature, else `target.get_object_by_guid(feature_guid)`.
   If unresolved → `Skip(reason=DEPENDENCY_UNRESOLVED)`.
3. Cast `target_pos` to `IPartOfSpeech`; take `InflectableFeatsRC`.
4. Membership guard: if `target_feat` (by identity or GUID-equality) is already in the
   collection → no-op (idempotent).
5. Otherwise `InflectableFeatsRC.Add(target_feat)`.

**Contract assertions**:
- IDEMPOTENT: running the pass twice adds the feature at most once (VR-3).
- DEFERRED-NOT-DANGLING: a missing endpoint yields a reported `Skip`, never a write
  (VR-4).
- ORDER-INDEPENDENT: correctness does not depend on whether the POS or the feature was
  created first (post-pass runs after both).
- REPORTED: every emitted `Skip` surfaces in the post-run statistics panel (no silent
  skips).

## C3 — Name/abbreviation/description copy (WS-mapped)

**Applies to**: `inflection_features_execute_action` for both the feature and its values.

**Behavior**: `Name`, `Abbreviation`, `Description` are written to the target object
using the **target** writing-system handle obtained by mapping each source WS through
the `WSMapping` (`ws_mapping`) passed into the executor — never the raw source handle.
Preferred implementation is the flexicon Operations `ApplySyncableProperties(...,
ws_map=ws_mapping)` surface (same call the POS path uses), falling back to explicit
handle translation only if that surface is unavailable for `IFsClosedFeature` /
`IFsSymFeatVal`.

**Contract assertions**:
- NON-NULL-NAME: after execute, the feature and each value have a non-empty `Name` in
  the target default analysis WS (VR-2).
- WS-FIDELITY: a source string in WS *X* lands in target WS *X* (by Id), not on a
  wrong/absent handle (Principle I).

## C4 — Feature-level dedup / status classification

**Applies to**: `_gather_target_infl_feat_guids` (and callers in `selection.py`).

**Behavior**: expose two GUID sets — a **feature-level** set (feature `.Guid`) and a
**value-level** set (value `.Guid`). Feature rows (`depth=0`) classify against the
feature-level set; value rows (`depth=1`) against the value-level set.

**Contract assertions**:
- A feature present in the target by feature GUID is classified `in_target` (not `new`)
  on re-run.
- Plan `ADD` is produced only for features whose feature-level GUID is absent from the
  target (no duplicate creates) — VR-1.
