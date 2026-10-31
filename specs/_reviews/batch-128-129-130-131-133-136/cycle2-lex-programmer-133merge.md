# fix-133 merge of origin/main (cycle 2)

## Deviation: merge already done upstream
`git fetch` showed origin/fix-133-pos-inflfeats-single-writer had moved to 971c3b3
("Merge origin/main into fix-133...", author copilot-swe-agent[bot]) -- it merges
f3618dc + b50b1bd (#151). My local trial merge conflicted identically (1 marker,
transfer.py 328-411), so I aborted, fast-forwarded to 971c3b3, verified its
resolution, and confirmed `git merge origin/main` = "Already up to date".
No new commit; nothing to push. HEAD = origin branch head = **971c3b32f873b97338a0904ff16aeda144d3cf1a**.

## 1. Resolved hunk (transfer.py)
No conflict markers remain anywhere in src/gramtrans/Lib. Both helpers kept:
`_ensure_infl_feature_links` transfer.py:328 (latch `_did_infl_feature_link_ensure`, :342)
and `_ensure_entryref_passes` :367 (latches `_did_entryref_create_pass`, `_did_post_pass_a`, :393-394).
All three latch names distinct. Both call sites present.

## 2. Final post-loop order (transfer.py)
:1016 _ensure_infl_feature_links (#133)
:1018 _ensure_171_subpass
:1026 _ensure_owner_feat_strucs
:1030 _ensure_matched_nc_segments
:1034 _ensure_entryref_passes (#128)
:1038 _ensure_complex_feature_type_ra
:1042 _ensure_struct_type_features_rs

Reasoning: the #133 pass only adds target FsFeatDefn refs to POS.InflectableFeatsRC,
keyed by POS/feature GUID. Both endpoints are created by the leaf loop, which has
finished by then. None of the later helpers create or repair POS or feature
defns: 171 and owner_feat_strucs fill MSA-side structures, TypeRA and struct-type
FeaturesRS repair struct-type internals, and entryref touches lexemes only.
_run_171_subpass does not write InflectableFeatsRC. The #133 call placement before
_ensure_171_subpass is therefore correct, with no reorder needed. #128's call
sits after all lexeme creation, which is also correct.

## 3. Semantic read (categories.py / models.py)
No interaction. #128 keys (`summary_tss`, `summary_src_ws_ids`) are stashed in the
entry-ref binding record (categories.py ~5753) and consumed at ~12618 by
`_tss_remap_ws_runs` (:12502) / `_merge_entryref_value_fields` (:12533, call
sites :12781, :12825). #133 `_stash_feature_category_links` (:5759) writes
`plan.feature_category_links` (models.py:3649) and `_run_infl_feature_link_pass`
(:13024) reads it; separate data structures and functions. models.py differs only
by #128's comment lines. #131 (semantic-domain create text) is in unrelated
create paths. Note: `EnrichedCollection.deferred` surfaced only as the
`deferred=1` report token in live output; the grep found no overlap with #128/#131 code.

## 4. Env
gramtrans -> D:\Github\_Projects\_LEX\GramTrans-fix-133\src\gramtrans\__init__.py
flexicon  -> D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py (not site-packages)

## 5. Unit
`pytest tests/unit -q`: **5432 passed, 80 skipped, 14 xfailed**. Expected 5411 + 21
(#131 file + #133 file together = 21 tests: 5411+21 = 5432). The "+19/+8" estimate
double-counted; the 5411 baseline excludes both. No deviation unexplained.

## 6. Live (GT-Sandbox-133 only, FLEXLIBS_REQUIRE_LIVE=1)
`tests/integration/test_issue133_pos_inflfeats_live.py`: **2 passed in 24.19s**.
Key lines: plan 27 actions (17 gram_categories, 10 inflection_features);
0-action re-run: `plan.actions=0 link_rows=1 reported_writes=1`; enrich line
`InflectableFeatsRC: added=0 already_present=1 deferred=1`; "child left to the
single InflectableFeatsRC writer (link pass)". No other live test run.

## FLExToolsMCP
Not used (no flexicon/liblcm lookup was needed).
