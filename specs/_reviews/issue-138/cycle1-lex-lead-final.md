# Issue #138 — lex-lead cycle 1 (final)

## Diagnosis

Open P0/P1 without an open PR: none (#22 is the sole open P1 epic; #171 has PR #200). Selected **#138** (P3 umbrella, no open PR) — cycle-3 follow-up from the owner comment on the issue.

When a struct-type `FeaturesRS` repair raises after one or more successful `Insert` calls, Move correctly reports a `Skip(DEPENDENCY_UNRESOLVED)` naming the inserts, but `_struct_type_features_rs_writes` stayed at zero. The target **did** change (partial repair), so the live gate tally under-counted writes and disagreed with mutation evidence. Preview already used the phrase "reordered in target, left as-is" for the REORDERED row while Move inlined the same words in a longer Skip detail — duplicated string, not a single source of truth.

## Resolution

- On the repair `except` path, increment `writes` when `inserted` is non-empty (issue #138 partial-repair tally).
- Add `FEATURES_RS_REORDERED_NOTE` in `categories.py` and use it for both Move Skip detail and Preview's REORDERED label.

## Verification

- `tests/unit/test_issue108_features_rs_repair.py::TestInsertOnly::test_insert_failure_mid_repair_loses_nothing_and_detail_accurate` (expects `_struct_type_features_rs_writes == 1`)
- Full `test_issue108_features_rs_repair.py` module

**Verdict: GO** — refs #138 (partial repair write count + shared reorder wording).
