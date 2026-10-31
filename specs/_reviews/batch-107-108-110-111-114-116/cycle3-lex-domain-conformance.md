# Cycle 3: LEX domain conformance check (batch 107-108-110-111-114-116)

> Saved by the main session: lex-domain has no Write/Bash tool and returned this text verbatim.

Method: read the worktree code directly and fetched the PR pages from github.com. Bash was unavailable, so I did not run `git show` or `gh`. No FLEx project was opened. I did not run any tests.

**Q1 (#108): PASS**
- `_classify_struct_type_features_rs` returns REPAIR only when a resolvable source member is missing from the target sequence.
- A complete sequence in a different order returns REORDERED. That writes nothing, and Preview shows "SKIP (reordered in target, left as-is)". Move emits the same Skip (categories.py:3463-3469).
- `_rewrite_features_rs` is insert-only, with no RemoveAt. Target-only members are never removed, and each is reported as Skip(NEEDS_MANUAL).
- PR #122 now says "The earlier 'rebuild to source order' premise (RemoveAt + Insert) is withdrawn: the repair is now insert-only." It also documents the REORDERED Skip in Preview and Move. The first commit message still mentions RemoveAt/Insert, which is history only.
- Ordering sense: each missing member goes after its nearest present source predecessor, else before its nearest present successor, else at the start. In the feature-structure editor that keeps the shared features in the user's own order. A new feature lands next to its source neighbour, so I would expect a FLEx user to find the result sensible. Target-only features can sit between the neighbours, but that is the user's own layout and is not disturbed.
- Not verified: the test coverage for Q1.

**Q2 (#114): PASS**
- `_merge_entryref_value_fields(existing=True)` treats a source `HideMinorEntry` of 0 as unset, so only 1 over 0 merges.
- The INV-1 call site passes `existing=True` (categories.py:12187-12189). The CREATE call site does not (12231), so 0 stays data on created refs.
- `test_rerun_hide_minor_entry_source_zero_is_unset_target_one_stays` covers target 1 / source 0 staying 1, with no write and no drop. A companion test covers source 1 overwriting target 0.
- PR #124 lists #127 as a residual risk: the INV-1 merge on existing refs is not shown in Preview. It also lists #128: the merge only runs on a run with at least one STEMS action.

**Q4 (#116): PASS**
- The resolver cache is not primed. preview.py:2024-2026 adds the line "(Later references to an item created earlier in this run show as create; Move links them.)", but only when a create row is present.
- The wording is plain, and "create" and "link" are the labels the rows already use. The one gap is "this run", which a user may not link to the Preview-then-Move pair. Consider "...earlier in this transfer".
