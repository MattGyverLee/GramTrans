# impl-108: GitHub issue #108, repairing struct-type FeaturesRS left incomplete when the type was created before its member features

- Branch: `fix-108-featuresrs-repair`
  - Worktree: `D:/Github/_Projects/_LEX/GramTrans-fix-108`
  - Based on origin/main `c088d16`
- Commit: `c61105f`. Its message ends `closes #108`, followed by the Co-Authored-By trailer.
- PR: https://github.com/MattGyverLee/GramTrans/pull/122 (not merged)
- Verdict: [OK] Fixed and proven live in both feature systems. That covers:
  - the repair to source order
  - a third run that writes nothing
  - target-only members kept and reported
  - a manual reorder repaired
  - two mutation checks, both of which fail as expected

## 1. Root cause

- `feature_struct_types_execute_action` and `phon_feat_types_execute_action` wire `FeaturesRS` only while they create the type.
  - If a member's defn is not in the target at that moment, it is skipped.
  - The only trace was a log warning ("no target counterpart in FeaturesOC -- skipping member").
- From then on, `*_plan_action` returns `ALREADY_PRESENT_BY_GUID` for the type on every run. Nothing ever revisits the sequence.
- The issue comment reproduces this naturally. A STEMS/AFFIXES run with closure pulls struct-types through the registered `MSA_TO_FEAT_STRUC_TYPE` edge.
  - It does not pull their member defns.
  - The type -> defn edge (`feature_struct_types_dependencies`) exists but is not in `CLOSURE_EDGES_VERIFIED`. FR-018 needs an audit-backed `verified_by` row first, so registering it is out of scope.
- A `_run_tail_once` tail cannot fix this. In the re-run that has to do the repair, both the type and the features already exist, so neither category plans an action and the tail never fires. This is the same reasoning as #37.

## 2. Changes

All new code is in its own functions. **No `_complex_type_ra` / `_classify_complex_type_ra` / `_ensure_complex_feature_type_ra` symbol was touched**, so the #110 rebase should be clean.

### `src/gramtrans/Lib/categories.py`

A new block, `struct-type FeaturesRS repair pass (issue #108)`, sits after `phon_feat_types_execute_action`, away from the TypeRA block. Its banner states the ordering policy. It contains:

- `STRUCT_TYPE_FEATURE_SYSTEMS`: `ms` -> (MsFeatureSystemOA, FEATURE_STRUCT_TYPES, INFLECTION_FEATURES); `ph` -> (PhFeatureSystemOA, PHON_FEAT_TYPES, PHONOLOGICAL_FEATURES).
- The `FEATURES_RS_*` outcomes: `complete`, `repair`, `create_wired`, `type_absent`.
- `gather_struct_type_feature_refs(context, selection, actions)`, used by Preview.
  - A system is in scope when its types or features category is on, or when either has a planned action. A closure pull-in plans types while leaving the category off.
  - Within a system, a type is recorded if it is in the target `TypesOC` by GUID or is planned for create.
  - Each record holds the type label and the members as `(guid, label)` pairs in source order. Move needs the labels for its drop records.
- `_classify_struct_type_features_rs(...)`: read-only, with one classifier serving both Preview and Move. Preview counts this run's planned creates as present.
- `_rewrite_features_rs`: an in-place `RemoveAt` + `Insert` that touches only slots that are out of place.
- `plan_struct_type_features_rs_drops`: adds the projected drops to Preview.
- `_run_struct_type_features_rs_pass`: the Move pass. It:
  - repairs each type, logging one `FeaturesRS repaired` line per type
  - puts a `DroppedItemRecord` on `context._dropped` for each unresolvable member
  - adds a `Skip(NEEDS_MANUAL)` for each target-only member
  - turns a failed rewrite into `Skip(DEPENDENCY_UNRESOLVED)` instead of raising
  - stores the write count as `_struct_type_features_rs_writes`
- The create-path "skipping member" warnings in both executors now say "member deferred to the FeaturesRS repair pass (issue #108)". The create-path wiring itself is unchanged.

### `src/gramtrans/Lib/models.py`

- Adds `RunPlan.struct_type_feature_refs: dict`. It is placed after `category_notes`, not next to the #37 field, to avoid conflicts.

### `src/gramtrans/Lib/preview.py`

- `build_run_plan` runs the gather and the projected drops right after `_scope_msa_slot_bindings`, which comes after the closure pull-in.
  - Both steps are fail-soft and log on error.
  - The result is passed into `RunPlan`.
- New `render_struct_type_features_rs`, appended to `render_preview_extra_lines`. Its rows are:
  - `Repair`
  - `SKIP (already complete)`
  - `Wire at create`
  - `REPORT (member feature unavailable)`
  - `REPORT (target-only member kept)`

### `src/gramtrans/Lib/transfer.py`

- New `_ensure_struct_type_features_rs(exec_ctx, target, exec_skips)`. It has its own latch `_did_struct_type_features_rs` and never raises.
- `execute()` calls it right after `_ensure_complex_feature_type_ra`.

### Ordering policy

`S` is the set of source members that resolve in the target, in source order. `C` is the target's current sequence.

- **COMPLETE (no write)** when every member of `S` is in `C`, and `C` restricted to `S` equals `S`. Duplicates are compared by first occurrence. Target-only members may sit anywhere.
- **Otherwise REPAIR**: rewrite to `D = S + (target-only members, in their existing order)`.
- **Target-only members are never removed.** Each is reported as `Skip(NEEDS_MANUAL)` on every run in scope.
- **Rebuild, not append.** For source `[A,B]` with create-time target `[B]`, append gives `[B,A]`. The rewrite moves only what is out of place, so a complete sequence is never written.

## 3. Live evidence (`FLEXLIBS_REQUIRE_LIVE=1`)

Test: `tests/integration/test_issue108_features_rs_repair_live.py`, **1 passed (31s)**. Log: `C:\Users\thoua\AppData\Local\Temp\claude\d--Github--Projects--LEX-GramTrans\9f84e243-5237-484f-a4c9-1d675dd0f416\scratchpad\run108_1.log`.

Setup:
- `gramtrans` resolved to `D:\Github\_Projects\_LEX\GramTrans-fix-108\src\gramtrans`, and `flexicon` to `D:\Github\_Projects\_LEX\flexicon\flexicon`. Both are printed in the log.
- Source `Mbugwe Lizzie` was opened read-only. Its `.fwdata` SHA-256 was `db195e04e8963ab4ab2d849f3ff955932fbe9ed52c90fb568da033ce60a7ff0c` both before the MCP probe and after the live run. The test also asserts this.
- The only project written was `GT-Sandbox-108`, restored from `Target 2026-07-06 0218.fwbackup` before and after the run. The name is asserted before each fixture write.

Source facts (read-only MCP probe): 5 MS types with 12 member slots, and 1 Ph type (`Phon`: long, labial) with 2 slots.

| Step | Selection | Preview | Move | Target after |
|---|---|---|---|---|
| Pre | - | - | - | no types |
| Run 1 | FEATURE_STRUCT_TYPES, PHON_FEAT_TYPES | 6 `Wire at create`, 14 REPORT (member unavailable) | 0 repairs; 14 `FeaturesRS` drops in `report.dropped_items` (and 14 in `plan.dropped_items`) | all 6 types, every `FeaturesRS` = [] |
| Fixture | sandbox write | - | - | target-only closed feature X in `0a6c2f79` (ms), Y in `0ea53dd6` (ph) |
| Run 2 | + INFLECTION_FEATURES, PHONOLOGICAL_FEATURES | 6 `Repair`, 2 REPORT (target-only kept) | 6 repairs; 0 drops; NEEDS_MANUAL skips for `0a6c2f79`, `0ea53dd6` | every type = source order by GUID; X / Y kept last |
| Run 3 | same | 0 Repair, 6 `SKIP (already complete)` | **0 writes**; target-only still reported | unchanged |
| Run 4 | same, after manually swapping the first two members of `2b491f35` | 1 Repair | 1 repair | `2b491f35` = [number, Bantu noun class, person] again |

`RemoveAt`/`Insert` on `ILcmReferenceSequence` had no precedent in the codebase. They work live through pythonnet: run 2 uses them for insertion and run 4 for reordering.

**Mutation checks.** Neither was committed; each was reverted with `git checkout` and `git status` was clean afterwards.
1. I replaced the `_ensure_struct_type_features_rs(...)` call in `execute()` with `pass`. Result: FAILED at run 1, where the Move report had 0 `FeaturesRS` drops instead of the expected 14. Log: `...\scratchpad\run108_mut.log`.
2. I replaced only `_rewrite_features_rs(...)` with `pass`. Result: FAILED at run 2, where `0a6c2f79` was `[X]` instead of `[e49c7be8, bd1d7f21, X]`. Log: `...\scratchpad\run108_mut2.log`.

## 4. Tests

- Unit baseline on unmodified `c088d16`: **5294 passed, 80 skipped, 14 xfailed**.
- After the change: **5317 passed, 80 skipped, 14 xfailed**. That is +23, all from the new `tests/unit/test_issue108_features_rs_repair.py`, and nothing regressed. The new tests cover:
  - classifier: complete, target-only anywhere still complete, missing -> repair with target-only last, out-of-order -> repair, unresolved reported, planned features count as present, absent vs planned type, Ph system read from `PhFeatureSystemOA`
  - Move pass: empty sequence filled in source order, rebuild-not-append, target-only preserved and reported, second run writes nothing, drop record field values, Ph category on the skip, absent type ignored
  - post-loop `_ensure`: runs with zero actions, latches, folds skips
  - Preview: gather scope (present or planned only, closure-pulled with the category off, system out of scope), Repair rows == Move writes, `Wire at create` is not a Repair, Preview drops == Move drops, empty refs render nothing
- Every command used `PYTHONPATH=D:/Github/_Projects/_LEX/GramTrans-fix-108/src`.

## 5. Pattern audit and residual risks

- The pattern audit used the `sweep-pattern` skill, with an Explore agent sweeping `src/gramtrans/Lib`. It is recorded in full in the PR body.
  - Bug class: a reference wired only in the create path, whose owner is later ALREADY_PRESENT and so never revisited.
  - The siblings it reports are **not verified and not fixed** here. I recommend triage into separate issues.
- **HIGH** siblings the sweep reports:
  - `MoMorphAdhocProhib.FirstMorphemeRA` / `RestOfMorphsRS` (categories.py ~5244/5256): ADHOC_COMPOUND_RULES dispatches before STEMS, and the miss is silent.
  - `MoAlloAdhocProhib.FirstAllomorphRA` / `RestOfAllosRS` (~5215/5229): same ordering gap.
  - The LexEntryRef component, primary and show-in reference sequences post-pass (~12497): anchored on the STEMS `_run_tail_once`, with no post-loop `_ensure`.
- **MED** siblings it reports:
  - `PhoneEnvRC`, `PositionRS`, `StemNameRA` (owned.py)
  - compound-rule MSA `PartOfSpeechRA`; rule and template `StratumRA`
  - template slot sequences
  - `PhNCSegments.SegmentsRC` when the class is present by GUID
  - `PhNCFeatures` specs
  - `_wire_phoneme_features`, anchored to the last PHONEMES action
  - `LexReference.TargetsRS`
- **Closure edge, type -> member defns:** not registered (FR-018). A closure-only run still lands types without members. That gap is now a reported drop and is repaired by any later run that has features selected or present in the target.
  - **#109 (the reverse edge, features -> struct-types):** not touched. Nothing here pulls types when only features are selected; a features-only run repairs only types that are already in the target.
- **Scope of the pass:** in a system that is in scope, the pass revisits every source type already present in the target, not only the ones selected.
  - This is intentional. A STEMS/AFFIXES closure run followed by an INFLECTION_FEATURES-only run therefore repairs the types.
  - A side effect: a target-only member keeps getting a NEEDS_MANUAL skip on every such run, by design ("never silently").
- **Phonological `FsComplexFeature` / TypeRA:** unaffected and still unsupported (see impl-37).
- **Rebase:** #110 changes `_ensure_complex_feature_type_ra` and the TypeRA block. My only touch point near it is a new call line placed just after `_ensure_complex_feature_type_ra(...)` in `execute()`. A conflict, if any, would be trivial.
- **Drop-record labels not checked live:** the live gate asserts the drop records' GUIDs only. It does not check that `owner_label` and `item_name` are non-empty.
  - Both come from `references._item_label`, which reads `.Name`.
  - If that returns `""` for a live `IMultiUnicode`, the report lines would show bare GUIDs.
  - Unit tests cover the plumbing only.
- **Sandbox state:** `GT-Sandbox-108` is restored again after the test, so it is left at the backup state.
