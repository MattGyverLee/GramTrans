# Cycle 3 -- lex-programmer -- #133 (PR #152)

New head: 69b5577 (branch fix-133-pos-inflfeats-single-writer, pushed; PR #152 body updated via REST: "Closes #133" + "Pattern audit").
Diff vs 971c3b3: 5 files, +665/-225 (categories.py 475 mostly a dedent, models.py 7, transfer.py 88, live test +45, new unit test +275).
Tooling: FLExToolsMCP not needed (no new flexicon/liblcm lookups; all logic is in-repo). flexicon resolves to D:\Github\_Projects\_LEX\flexicon\flexicon (editable tree, not site-packages).

## Done
P1-1 Reconciliation: enrichment now appends (src POS guid, feature guid) to a per-run `_deferred_infl_pairs` (threaded as `deferred_pairs=` through `_enrich_one_collection`, `_enrich_owned_collections`, `_execute_update_semantic`, `_fill_created_pos_collections`; attached to exec_ctx). The pass records settled pairs (linked / already linked / dropped) in `_infl_pairs_settled`. `categories._reconcile_deferred_infl_pairs` drops every remainder with a cause-naming reason. `_ensure_infl_feature_links` calls it on all paths: (a) pair not in map (leaf-pick / closure-created POS), (b) `_run_plan` None, (c) pass raises (also mid-pass), plus POS-unresolvable.
P1-2/3 Tests (13 new, tests/unit/test_133_deferred_reconciliation.py): created-POS chain (written + absent-feature drop), loss paths a/b/c, mid-pass raise, POS-unresolvable, idempotence, domain boundary (INFLECTION_FEATURES off: no feature factory requested, feature object not edited, link pass has no creation surface).
P2s: WRITE_FAILED Skip now POS_INFLECTABLE_FEATS / NOT_REPRODUCIBLE; absent feature reported once (drop; Skip only if no drop collector); dead `finally: pass` removed (try body dedented); stale `_run_tail_once` comments fixed (categories, models); `_ensure_entryref_passes` import guarded, failure logged + recorded as a DroppedItemRecord.

## Unit counts
5445 passed / 80 skipped / 14 xfailed (baseline 5432/80/14). Delta +13 passed = the 13 new tests; skipped/xfailed unchanged. No existing test needed changing.

## Live (FLEXLIBS_REQUIRE_LIVE=1)
3 passed in 26.67s. GT-Sandbox-133 only (restored from Target 2026-07-06 0218.fwbackup), source Mbugwe LizzieHC practice read-only. Existing cases unchanged (run2 5 Link == 5 writes; run3 0; 0-action links 1). New case: POS-only run, no features in target: 14/14 deferred pairs reported as drops, 0 links, feature set unchanged (0 -> 0; reader validated by seed-run assertion >= 10).
Evidence (committed to main dc0df674, pushed): D:/Github/_Projects/_LEX/GramTrans/specs/_reviews/batch-128-129-130-131-133-136/live-evidence-133-reconcile-cycle3.md

## Follow-up candidates
- POS-unresolved and InflectableFeatsRC-unavailable paths in the pass emit a per-POS Skip but no per-pair drop; a deferred pair there is reported by reconciliation, a non-deferred stashed pair only by the Skip (possible double report for deferred ones).
- Preview P2s from Q7 untouched: "Link" shown when planned feature create fails in Move, or POS absent and unplanned.
- `_resolve_target_by_guid` still has no type check (Q8 P2).
- Add that raises after partial apply still counts if read-back finds the pair (Q6 P2).
- Closure-created POS never enter the link map: now reported, but arguably should be linked.
- Reconciliation drops land in `_dropped` only if the collector exists; no secondary channel.
- main worktree has unrelated dirty files; only the evidence file was committed there.
