# impl-146 -- Preview resolver-cache priming on planned CREATE + run-wide picture dedup (issue #146, P1)

- Branch: fix-146-preview-cache-picture-dedup (worktree D:/Github/_Projects/_LEX/GramTrans-fix-146), based on origin/main b50b1bd
- Commits: c4e7cbb (closes #146) + texts follow-up (`fix(texts): rebind plan-carried planned LINKs`, refs #146); origin/main
  (717d7bf) merged, branch head e5ea12e, pushed
- PR: https://github.com/MattGyverLee/GramTrans/pull/160 (not merged)
- Verdict: READY FOR REVIEW. Unit suite green (+17). Live gate green (5 passed, 2 xfailed). The 2 xfails are the texts genre
  scenario, which is blocked by a pre-existing flexicon `Texts.GetGenre` bug (see Risks). The RED control reproduced the defect
  live without the fix.

## Root-cause trace
1. Cache priming. `references.decide_reference` short-circuits to LINK only on a cache hit. Only Move's `apply_reference` CREATE
   arm writes the cache (`cache[anc_guid] = new_obj`, references.py ~1285, for every chain member not already in the target).
   Preview never calls `apply_reference`, so its per-run `_resolver_cache` (preview.py:1311) stayed empty. The second sense's
   reference to the same source-only item was re-decided against the target, found absent, and shown as CREATE again. Move LINKs it.
   Live RED (fix stashed): Preview rows s1 thesaurus=create, s2 thesaurus=create. Move created C once.
2. Picture dedup. `pictures.plan_sense_picture_decisions` built `seen_hashes = set()` per call, which means per sense. Move's
   `_asset_cache(ctx)` is per run. Live RED: s2's picture (same content as s1's, a different source file name `gt146_red_1.png`,
   because AddPicture copies the file twice in the source) was shown as create. Move copied the red image once.

## Fix
- references.py: `PLANNING_CACHE_KEY`, `PlannedCreate(planned_by)`, `mark_planning_cache`, `is_planning_cache`,
  `is_planned_create`, `_record_planned_create`. On the CREATE arm, only when the cache is marked, every chain member that is
  neither cached nor in the target list gets `PlannedCreate(leaf_guid)`. This is exactly the set Move's CREATE arm caches. Existing
  ancestors are reused but not cached, same as in Move. A placeholder hit returns `LINK` with `target_item=None`, so the
  placeholder never leaks. `apply_reference` is untouched.
- Why the cache is marked and not primed on every CREATE: Move's `reproduce_reversal_entries` runs `plan_reversals`
  (decide-only) over the Move cache before applying. An unconditional placeholder there would be picked up by
  `cache.get(anc_guid) or ...` in the CREATE arm. Only Preview's cache is marked.
- preview.py: one hook in `build_run_plan` (`_mark_planning_cache(_resolver_cache)`). Nothing else in preview.py changed.
- categories.py `_thesaurus_new_ancestors`: a cached ancestor is skipped unless it is a placeholder planned by THIS decision's
  leaf. This keeps the #116 "(and its parent P)" display, and still hides ancestors an earlier leaf already planned (which Move
  created already). Move's cache holds only real objects, so Move's behaviour is unchanged.
- Plan-carried decisions (texts.py): Move's texts leg does not re-decide. It applies the genre/tag `ReferenceDecision`s built
  during Preview (`plan.text_plans`, transfer.py:1059 -> `texts.apply_texts`). After priming, the second text sharing a new
  genre/tag would carry LINK with `target_item=None`, and Move's LINK arm would apply that as a no-op (the link would be lost).
  New `references.rebind_planned_link(decision, target, spec, cache, source)` re-decides ONLY such placeholder LINKs against
  Move's own unmarked cache right before apply. It yields LINK -> the item Move's first CREATE cached, or CREATE again if that
  create failed (the same as pre-#146). It is used in `texts._apply_genres` and `texts._apply_segment_tags`.
  `apply_reference` itself is still untouched.
- pictures.py: `_planned_asset_hashes(resolver_cache)` keeps the set in the run's resolver cache (Preview-only function, so Move's
  `_asset_cache` is untouched). A call-local set is used when no dict is passed.

### Swept sites (Preview planning that must mirror a Move per-run dedup/cache)
1. references.py `decide_reference` (~760): FIXED. Covers every Preview caller that shares the run cache:
   categories.py `_decide_reference_fields` (6790), `_resolve_sense_thesaurus_items` -> `resolve_thesaurus_item` (8909/1623),
   owned.py `_plan_child_ref_decisions` (937), texts.py `_decide_segment_tags` (386) / `_decide_genres` (518),
   reversals.py `_decide_reversal_category` (344, via `plan_reversal_decisions`).
2. categories.py:8871 `_thesaurus_new_ancestors`: ADJUSTED (see above).
3. pictures.py:770 `plan_sense_picture_decisions`: FIXED.
4. owned.py:1612 `_plan_msenv_pos_ra`: FIXED. Same shape: CREATE per allomorph, while Move dedups via `_MSENV_POS_RESOLVED_KEY`.
   Uses a new `_MSENV_POS_PLANNED_KEY` set. `resolver_cache` is an optional trailing kwarg.
5. owned.py:1711 `_plan_inflection_classes_rc`: FIXED. Same shape as 4, with `_MSENV_INFLCLASS_PLANNED_KEY`.
6. owned.py:2251 `_plan_aprs_for_allomorph_decisions`: already run-wide (`_APR_PLANNED_KEY`). OK.
7. categories.py:8043 `plan_lexical_relation_decision`: already run-wide (`_LEXREL_PLANNED_KEY`). OK.
8. reversals.py:647 `_ensure_target_index` (Move `_INDEX_CREATED_KEY`): Preview renders index Add/Link grouped per WS
   (preview.py `render_reversal_decisions`), so it is already run-wide. OK.
9. NOT FIXED: preview.py:364 `_overwrite_reference_decisions` passes `resolver_cache={}` per call (OVERWRITE rows,
   SenseTypeRA / DoNotPublishInRC / DoNotShowMainEntryInRC). Move's overwrite executor shares the run cache (transfer.py:643).
   This is the same bug class, but the caller `_plan_layer3_verb_affixes_inner` has no RunContext. Threading the run cache through
   its 3 call sites means restructuring preview.py while #141/#142/#144/#147 are editing it. Recommend a follow-up issue.
10. Move consumers of plan-carried `ReferenceDecision`s (grep of every `apply_reference(` caller): categories.py 6721/6951/8971
    and owned.py 428/611 decide in the same Move pass. reversals.py 935 runs in a Move-time recompute
    (`reproduce_reversal_entries` re-runs `plan_reversals` on Move's cache). Only texts.py 926 (genres) and 973 (tags) apply
    Preview-built decisions: FIXED with `rebind_planned_link`.
11. Per-call `missing_seen` sets in owned.py (1385/2291) are symmetric between Move and Preview (per APR). OK.

## Tests and unit delta
- New tests/unit/test_issue146_preview_cache_picture_dedup.py (17 tests):
  - planning cache: second reference -> LINK with `target_item=None`
  - unmarked (Move) cache: CREATE, CREATE and the cache stays empty
  - negative control: distinct items -> CREATE, CREATE
  - an existing ancestor is not planned; a real cached object still links
  - two senses sharing a thesaurus item: Preview rows == emulated-Move rows (create c (+P), link c, create c3 with no ancestors,
    link p), and Move creates one P/C/C3
  - pictures across two senses: CREATE, LINK, Move copies 1; negative control (distinct files): CREATE, CREATE, Move copies 2
  - full `_plan_entry_reference_decisions` walk with a marked cache: CREATE/CREATE then LINK/LINK
  - `build_run_plan` hook present
  - msenv POS / inflection class: CREATE then LINK, plus a negative control; legacy 3-arg signature still works
  - texts: `rebind_planned_link` (Move cache hit -> LINK to the real item; miss -> CREATE; real decisions pass through; no
    placeholder lands in the Move cache). `_apply_genres` for two texts sharing a genre: Move gets CREATE then a LINK to the created
    item. With texts.py reverted, the latter test fails.
  - Without the src fix, 11 of the first 15 fail.
- No shared test files edited. Existing #116/#029/#028 tests pass unchanged.
- `python -m pytest tests/unit -q` (PYTHONPATH=worktree src): 5436 passed / 80 skipped / 14 xfailed.
  Baseline measured on this worktree at b50b1bd before any edit: 5419/80/14. Delta: +17 passed (the new file); skipped/xfailed
  unchanged. (The brief's 5392 figure predates b50b1bd.) origin/main merges brought only docs.

## Live proof (FLEXLIBS_REQUIRE_LIVE=1; wrote ONLY GT-Src-146 and GT-Sandbox-146)
tests/integration/test_issue146_preview_cache_picture_dedup_live.py. Both projects are rebuilt from
`Target 2026-07-06 0218.fwbackup`. The target is forked from the source before the source-only fixture is authored. The write guard
asserts the target name is `GT-Sandbox-146` (module level and before every run). Source writes are allowed only for GT-Src-146.
Fixture: one entry with 3 senses. s1 and s2 both have ThesaurusItemsRC=[C] and a picture of red.png. s3 is the negative control:
[N] and blue.png. C and N are new children of a DomainTypes item present in both projects.
- GREEN, 5 passed:
  - Preview rows `[(1,Thes,create),(1,Pic,create),(2,Thes,link),(2,Pic,link),(3,Thes,create),(3,Pic,create)]`.
  - Preview did not write: fwdata bytes unchanged, target Pictures folder still empty.
  - Move: E's children +{C,N} exactly; target Pictures = {gt146_blue.png, gt146_red.png} (2 copies); s1 and s2 both ->
    Pictures\gt146_red.png; s3 -> Pictures\gt146_blue.png.
  - Move re-run: state identical (idempotent). Preview after Move: entry skipped (present), no rows.
- Texts scenario (same file, second module fixture): two texts share a new genre G, and a third uses H. Result: 2 XFAIL. The texts
  transfer, but NO genre is planned or written, because flexicon `Texts.GetGenre(text)` raises
  `AttributeError('ILcmReferenceCollection[ICmPossibility]' object has no attribute 'FirstOrDefault')`. `_decide_genres` swallows
  that into "no genres", even though the source `IText.GenresRC` holds G (probed live). The xfail is imperative and keyed on that
  exact exception, so the scenario becomes a real CREATE/LINK + both-texts-linked assertion once GetGenre works. The
  rebind path is unit-tested only.
- RED control (src fix stashed, same test): Preview rows were all create (s2 thesaurus=create, s2 picture=create), while Move still
  created C once and copied red once. Only `test_preview_create_then_link_for_shared_item_and_file` failed.
- Hermeticity note: `harness.restore.restore_target` leaves `LinkedFiles/` alone. A first RED attempt picked up the previous run's
  image files (Preview then said "reuse" for everything). The test now clears `LinkedFiles/Pictures` of its OWN two projects after
  restore and at teardown, and asserts the target Pictures folder starts empty. Both projects are restored and cleared at teardown.

## Env check
```
python -c "import flexicon; print(flexicon.__file__)"  -> D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py
PYTHONPATH=<worktree>/src python -c "import gramtrans; print(gramtrans.__file__)"
  -> D:\Github\_Projects\_LEX\GramTrans-fix-146\src\gramtrans\__init__.py
[LIVE] gramtrans=D:\Github\_Projects\_LEX\GramTrans-fix-146\src\gramtrans\__init__.py flexicon=D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py
```
Note: without PYTHONPATH, `import gramtrans` resolves to the MAIN checkout (D:\Github\_Projects\_LEX\GramTrans\src). Every run
above set PYTHONPATH explicitly.

## Risks
- NEW FINDING (pre-existing, not #146): flexicon `TextOperations.GetGenre` raises on live LCM (`FirstOrDefault` on a pythonnet
  `ILcmReferenceCollection`). `texts._decide_genres` swallows it, so every text's GenresRC is silently dropped in both Preview
  and Move, with no DroppedItemRecord. This violates Principle I. Recommend a flexicon issue plus a GramTrans fallback that reads
  `IText.GenresRC` directly and reports on failure.
- A Preview "planned" LINK carries `target_item=None`. Nothing outside references.py reads `.target_item` directly, except
  texts.py `_apply_segment_tags`' fallback, which now runs after the rebind. A future Move path that applies Preview-built
  decisions must call `rebind_planned_link` first; otherwise the placeholder LINK is a silent no-op.
- Correct parity depends on Preview walking references in the same order as Move (the first reference is the CREATE). The
  live test asserts that order for senses within an entry.
- Out of scope, unchanged: Move does not cache UPDATE either. A second reference to a diverged-unprotected item can show UPDATE
  twice in Preview, while Move's second decision depends on whether the first UPDATE made the fields identical. This is a
  different defect.
- Out of scope, unchanged: cross-path parity, e.g. an msenv POS that a separate POS category action also creates.
- Coordination: the preview.py change is 7 added lines at the `_resolver_cache` creation (~1311). There is no overlap with #141/#142
  (~1495, which use the same cache object), #144, #145 or #147.
- Stash note: `git stash` was used twice for RED checks in this worktree (each popped immediately; `git stash list` was
  empty afterwards). The texts RED check used a file copy, not stash. `git diff origin/main --stat` lists only the 8 #146 files.

## Files touched
- src/gramtrans/Lib/references.py
- src/gramtrans/Lib/preview.py
- src/gramtrans/Lib/categories.py
- src/gramtrans/Lib/pictures.py
- src/gramtrans/Lib/owned.py
- src/gramtrans/Lib/texts.py
- tests/unit/test_issue146_preview_cache_picture_dedup.py (new)
- tests/integration/test_issue146_preview_cache_picture_dedup_live.py (new)
