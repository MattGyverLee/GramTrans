# impl-110: GitHub issue #110, TypeRA write count undercounts when the struct-type already exists in the target

- Branch: `fix-110-typera-single-writer` (worktree `D:/Github/_Projects/_LEX/GramTrans-fix-110`, based on origin/main `c088d16`)
- Commit: `ce672ad` (the fix, unit tests and live gate). The message ends with `closes #110`.
- PR: https://github.com/MattGyverLee/GramTrans/pull/121 (not merged)
- Verdict: [OK] Fixed the way the issue preferred: there is now one writer and one count. Verified live with a pinned mutation check.

## 1. Root cause

The #37 change (PR #105) left two writers of `IFsComplexFeature.TypeRA`:

1. `inflection_features_execute_action`, complex branch. It wired `TypeRA` at create time whenever the target `MsFeatureSystemOA.TypesOC` already held the struct-type.
2. The post-loop tail `transfer._ensure_complex_feature_type_ra` -> `categories._run_complex_feature_type_ra_pass`. It counts its writes in `_complex_type_ra_writes` and logs `TypeRA wired`.

Preview's `render_complex_feature_type_refs` classifies each edge before Move, using the same classifier as the tail. When the type already existed, Preview showed "Wire". Then the create path wrote first, and the tail saw `ALREADY_WIRED` and counted nothing.

Measured live before the fix: **2 Wire rows, 0 reported writes**. The data was correct; the report was wrong.

## 2. Why the tail can own TypeRA (no path where it does not run)

- `inflection_features_execute_action` has one dispatch site: `bundle["execute_action"]` in the leaf loop at `transfer.py:773`. Nothing else in `src/` calls it.
- `_ensure_complex_feature_type_ra` runs unconditionally after that loop (`transfer.py:874`). Its only gates are `_run_plan`, which `execute()` always sets at `transfer.py:624`, and its own latch.
- The edge comes from `_stash_complex_feature_type_ref`. That is called first in `inflection_features_plan_action`, and every executed action went through `plan_action` (leaf loop or closure pull-in).

## 3. Changes

### `src/gramtrans/Lib/categories.py`
- `inflection_features_execute_action`, FsComplexFeature branch: removed the `TypeRA` lookup and write, and the "deferred" info log (24 lines). A comment now points to the tail as the only writer.
- That function's docstring is updated to match.
- Two comments in the FEATURE_STRUCT_TYPES banner pointed at the removed code. Both are reworded.
- Not touched: the tail, the classifier, the stash, and the area where the #108 agent is working (FeaturesRS repair).

### `tests/unit/test_categories_inflection_features.py`
- Pinned test `test_execute_action_complex_feature_creates_object_not_skipped`: now asserts `TypeRA is None` even when the target type is present.
- New `test_preexisting_struct_type_move_writes_equal_preview_wire_rows`:
  - the target already holds the struct-type
  - Preview render -> 1 Wire row
  - `execute_action` creates the feature with no TypeRA
  - the tail runs -> `_complex_type_ra_writes == len(wire_rows) == 1`, and the feature is wired to the target type

### `tests/integration/test_issue110_type_ra_single_writer_live.py` (new, 2 live tests)
- `test_preexisting_struct_types_writes_equal_wire_rows`:
  - seed run with FEATURE_STRUCT_TYPES only
  - run 2 with features and types
  - run 3, which must be idempotent
- `test_mutation_create_path_second_writer_undercounts`: puts the old create-path write back by wrapping `LEAF_CATEGORIES[INFLECTION_FEATURES]["execute_action"]`, then asserts the defect appears: 2 Wire rows, 0 writes, data still correct.
- The reported count is read from the tail's own `_complex_type_ra_writes`, captured by wrapping `_run_complex_feature_type_ra_pass`. The `TypeRA wired` log lines are also counted.

## 4. Unit suite

| | passed | skipped | xfailed |
|---|---|---|---|
| before (origin/main c088d16) | 5294 | 80 | 14 |
| after | 5295 | 80 | 14 |

The +1 is the new acceptance test. No regressions.

**Unit mutation check.** I stashed `categories.py` (old code) and re-ran the file:
- the flipped pinned test FAILS (TypeRA is the type)
- the new test FAILS with `assert 0 == 1`
- I then restored the stash.

## 5. Live evidence (`FLEXLIBS_REQUIRE_LIVE=1`)

**Environment**
- `PYTHONPATH` was set to the worktree `src`.
- The log prints `gramtrans=D:\Github\_Projects\_LEX\GramTrans-fix-110\src\gramtrans\__init__.py` and `flexicon=D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py`.

**Source**
- Read-only MCP probes, in the assigned order:
  - `Mbugwe Lizzie FLExTrans` qualifies, but has only 1 FsComplexFeature with TypeRA.
  - `Mbugwe LizzieHC practice 2026` has 2, so it is the source used:
    - `49eaca04` subject agreement -> `2b491f35`
    - `df4a248b` noun agreement -> `0a6c2f79`
- No private source copy was needed.

**Write target**
- Only `GT-Sandbox-110`, restored with `harness.restore.restore_target` from `backups/Target 2026-07-06 0218.fwbackup` before and after each test.
- No other project was written.

**Source integrity**

| Project | SHA-256 before | After probes and all live runs |
|---|---|---|
| Mbugwe Lizzie FLExTrans | `59b94f0b...db762f6` | OK (unchanged) |
| Mbugwe LizzieHC practice 2026 | `d1b7eb78...189eea5` | OK (unchanged) |

**Results (fixed code): 2 passed in 26.1s**

| Run | Selection | Preview TypeRA rows | Reported writes | `TypeRA wired` log | Read-back |
|---|---|---|---|---|---|
| seed | FEATURE_STRUCT_TYPES | - | - | - | both types present, 0 complex features |
| 2 | INFLECTION_FEATURES + FEATURE_STRUCT_TYPES | 2 x Wire | **2** | 2 | both features wired; both match the source by GUID |
| 3 | same | 2 x SKIP (already wired) | **0** | 0 | unchanged |

**Mutation runs**
- **Pinned live mutation test** (old create-path write restored): wire_rows=2, reported_writes=0, wired_log=0, and the data is still correct. PASS, meaning the defect was reproduced.
- **One-off run of the main live test against the stashed old `categories.py`**: FAILED with `AssertionError: assert 0 == 2` at `writes == len(wire_rows)`. Reverted with `git stash pop`, and the diff was confirmed back to the fix.

**Not run:** the #37 live test (`test_issue37_complex_type_ra_live.py`). It is pinned to `Mbugwe Lizzie` and `GT-Sandbox-37`, and both belong to other agents. Its scenarios still hold under this change:
- With a fresh target, the create path never wired anything, because the type did not exist yet.
- Its repair and pre-fix tests rely only on the tail.

Its unit counterpart (`tests/unit/test_issue37_complex_type_ra.py`) passes.

## 6. Pattern audit

Sweep: "a target reference written by both a create path and a tail pass whose count Preview promises". Run with the Explore agent over `categories.py`, `transfer.py` and `preview.py`. The full list is in the PR body. Siblings were not fixed here, to keep the diff tight.

- **[HIGH]** `transfer.py:3074`: POS `InflectableFeatsRC`. For a matched POS, enrichment (`_execute_update_semantic`) writes and counts a pair before leaf dispatch. `_run_infl_feature_link_pass` then finds it present, while Preview also shows a "Link" row. Same shape as #110.
- **[MED]** `categories.py:3328`: `pos_inflectable_feats_execute_action` does an unchecked `.Add` and counts it as added, after the INFLECTION_FEATURES tail may already have written the pair. A double count.
- **[MED]** `categories.py:12337`: `_run_infl_feature_link_pass` has no counter and no shared classifier. It is anchored only by `_run_tail_once`, so a 0-action re-run never fires it (the #37 shape).
- **[MED]** `preview.py:1862`: `_target_pos_infl_feat_guids` uses `get_object_by_guid`, which the live FLExProject lacks. Every pair renders as "Link".
- **[MED]** `owned.py:1883` together with `categories.py:11602`: `MsEnvFeaturesOA` has two writers. This is a fidelity issue (TypeRA left null on an existing structure), not a count issue.
- **[LOW]** `SlotsRC` is also written by the MSA overwrite path and by `_create_inflaff_msa_*`. The latter is unreachable (`_VERB_VERTICAL_ENABLED = False`).

Cleared: 171-subpass SlotsRC, `_wire_msa_infl_feats`, `_wire_owner_feat_strucs` (Ms/From/To), `_ensure_matched_nc_segments`, entryref C1/C2, `_wire_phoneme_codes`, `_wire_phoneme_features` (counts filled and already separately, which is correct), stratum drain, `_wire_prod_restrictions`, and the type `FeaturesRS` (written only at create time).

I have not verified the sibling findings myself; they are the sweep agent's static reading. The HIGH and the first MED (POS InflectableFeatsRC) look worth their own issue.

## 7. Residual risks and follow-ups

1. **Picks asymmetry, pre-existing from #37 and left unchanged.**
   - `_stash_complex_feature_type_ref` honours `leaf_picks_for(INFLECTION_FEATURES)`, but `inflection_features_enumerate_source` does not filter by picks.
   - Nothing in `selection.py` or `ui/` produces INFLECTION_FEATURES picks today, so nothing can trigger it.
   - If picks are ever produced, a feature created outside the picks, including one pulled in by closure, would get no TypeRA edge from the tail. Before this change the create path covered that case, but only when the type already existed.
   - Fix the stash/enumerate pair together if picks arrive.
2. **Merge order with #108.** The #108 agent is adding a FeaturesRS repair pass near this code. The diff only removes lines inside `inflection_features_execute_action` and edits comments, so a conflict with #108 is unlikely, and it would be textual if it happens.
3. **The live gate pins source facts.** It pins 2 complex features in `Mbugwe LizzieHC practice 2026`. If that project is edited, the gate fails loudly.
4. **No Preview/Move count assertion in production.** The count equality is enforced only by tests. Nothing checks at runtime that Move's writes match Preview's Wire rows.
