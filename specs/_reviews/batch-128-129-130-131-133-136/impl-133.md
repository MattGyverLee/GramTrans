# impl-133 -- POS InflectableFeatsRC: one writer, one count

Issue #133 (P2). Branch `fix-133-pos-inflfeats-single-writer` (worktree
`GramTrans-fix-133`), PR https://github.com/MattGyverLee/GramTrans/pull/152 (not merged).
origin/main merged in (picked up #130) before push.

## 1. Env check
```
gramtrans -> D:\Github\_Projects\_LEX\GramTrans-fix-133\src\gramtrans\__init__.py
flexicon  -> D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py
```
Deviation: FLExToolsMCP is not exposed to this agent; source/sandbox reads were done with
read-only flexicon opens (same as the existing live tests).

## 2. Writer inventory
Before (4 code paths touching InflectableFeatsRC, 3 writers):
| site | wrote? | counted? |
|---|---|---|
| transfer `_add_reference_collection_member` (enrichment, `live.Add`) | yes, unchecked | `added += 1` before link pass |
| categories `pos_inflectable_feats_execute_action` | yes, unchecked Add | returned feat = "added" |
| categories `_run_infl_feature_link_pass` | yes, skips existing | no counter, no read-back, never on 0-action run |
| preview `_target_pos_infl_feat_guids` | read | used `get_object_by_guid` (absent live) -> all "Link" |

After (1 writer):
| site | role |
|---|---|
| `_run_infl_feature_link_pass` | SOLE writer; skip existing, Add, read back, count only confirmed |
| enrichment | no write; missing child -> `EnrichedCollection.deferred` (new field, in `source_child_count`) |
| `pos_inflectable_feats_execute_action` | records (pos, feat) intent into `feature_category_links`; returns `ActionOutcome.skipped(recorded=True)` so leaf `added` never claims it |
| preview helper | read-only, POS via preview's `_target_pos_for_source_guid` (POS.GetAll GUID scan + natural key) |

## 3. Changes
- categories.py: link pass rewritten (read-back via `_infl_feat_in_collection`; failed/no-op
  Add -> WRITE_FAILED `DroppedItemRecord` on `context._dropped` + Skip; absent feature ->
  dependency drop + Skip; count accumulated in `context._infl_feature_link_writes`).
  `_stash_feature_category_links` no longer gated on INFLECTION_FEATURES.
  `inflection_features_execute_action` no longer anchors the pass (`_run_tail_once` removed;
  the `finally:` is now a no-op comment).
- transfer.py: new `_ensure_infl_feature_links` (own latch, never raises) called post-leaf-loop
  before `_ensure_171_subpass`; runs on 0-action runs. Enrichment region edits as scoped
  (`_add_reference_collection_member` deleted, deferral branch, report line shows `deferred=`).
  Two small additions outside the 3074-3253 region (ensure helper near :372, call near :941);
  disjoint from #130's `_execute_overwrite` (merge was clean).
- preview.py: helper fixed; `render_feature_category_links` now yields `Link` /
  `SKIP (already linked)` / `DROP (feature absent from target)` so Preview never promises a Link
  Move cannot make; feature presence = planned INFLECTION_FEATURES action or resolvable in target.
- models.py: `EnrichedCollection.deferred` (default 0).

## 4. Deferral rule (documented in the pass docstring)
Feature exists in target by GUID (or is created this run) -> linked, whatever the selection.
Absent -> reported dependency drop (DroppedItemRecord, field InflectableFeatsRC) + Skip; never
silently deferred. A later run links it once the feature exists.

## 5. Tests
Unit: `python -m pytest tests/unit -q` -> **5403 passed, 80 skipped, 14 xfailed**
(baseline 5384/80/14: +19 passed, 0 new skips/xfails; after merging origin/main).
- New `tests/unit/test_133_pos_inflfeats_single_writer.py` (13): count == confirmed writes and
  existing pairs skipped; second run 0; no-op Add and raising Add -> drop, not counted; absent
  feature -> drop; execute_action no Add; enrichment has no writer; no tail on the feature action;
  0-action `_ensure` links + latch; Preview helper against fake lacking `get_object_by_guid`;
  Preview Link rows == Move writes; Preview does not promise Link for absent feature.
- Updated tests that encoded the old behaviour: test_031 `test_no_gathering_when_features_not_in_scope`
  -> `test_gathers_even_when_features_not_selected`; test_038_enrichment_executor (2 reference
  collection tests -> deferred, no write); test_categories_pos_inflectable_feats (2 execute_action
  tests -> intent only).

## 6. Live proof (FLEXLIBS_REQUIRE_LIVE=1)
`tests/integration/test_issue133_pos_inflfeats_live.py`, 2 passed. Source `Mbugwe LizzieHC practice`
(read-only; probe: 7 POS with populated InflectableFeatsRC, 14 pairs). Target `GT-Sandbox-133`
restored from `Target 2026-07-06 0218.fwbackup`; TARGET_NAME pinned (assert) before each write; the
only fixture write removes pairs in GT-Sandbox-133. Not run: Target-writing suites, #110/#108 live tests.
```
run1 (POS+features seed): actions=27 link_rows=14 reported_writes=14 pass_calls=1 sandbox pairs=14
removed 5 pairs in sandbox
run2 (POS only; POS+features present): plan.actions=0 link_rows=5 skip_rows=9 reported_writes=5
   Preview Link rows 5 == Move writes 5 == read-back relinked 5; all 14 source pairs present
run3 (0 actions): link_rows=0 reported_writes=0, sandbox unchanged
0-action test: remove 1 pair -> plan.actions=0, link_rows=1, reported_writes=1, read-back confirms
```
Run 2 also exercises the old ~3217 deferral case (INFLECTION_FEATURES unselected, features present by GUID).

## 7. Caveats
- `_run_tail_once` removal means the link pass now fires only post-loop; any caller invoking
  `inflection_features_execute_action` alone no longer gets links (no test depended on it).
- Preview `DROP` row for an absent feature relies on `_resolve_target_by_guid`; offline fakes need
  `get_object_by_guid` for feature presence (planned INFLECTION_FEATURES actions also count).
- Not run: live write to a source-POS-reuse-by-natural-key case (Mbugwe/starter POS GUIDs matched).
