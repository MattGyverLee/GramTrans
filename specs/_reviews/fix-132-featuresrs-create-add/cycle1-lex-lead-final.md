# Issue #132 — struct-type create FeaturesRS.Add never-silent — lex-lead cycle 1 (final)

## Issue selection

No open **P0** bugs. The only open **P1** without a PR is **#22** (conflict-mode epic — not a bounded fix). Selected **#132** (P2 never-silent audit; issue closed) — **create-time `FeaturesRS.Add` failures** on `feature_struct_types_execute_action` and `phon_feat_types_execute_action`. No open PR covered this site (draft PRs address other #132 tails).

## Diagnosis

When a member defn resolved in the target but `FeaturesRS.Add()` raised, both create paths logged a warning and continued. With `context._dropped` attached (normal Move), nothing entered the run report — a Principle I violation distinct from the deferred-member case (repair pass drops those in Preview/Move).

## Resolution

- Add `_features_rs_add_failed_drop` / `_record_features_rs_add_failure`.
- Call from both create paths after the existing warning when `_dropped` is present.
- Docstrings note the drop contract.

## Verification

- `tests/unit/test_issue132_featuresrs_create_add.py`
- Existing `tests/unit/test_categories_feature_struct_types.py` happy paths unchanged

**Verdict: GO** — refs #132.
