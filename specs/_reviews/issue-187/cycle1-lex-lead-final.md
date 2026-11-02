# Issue #187 — lex-lead cycle 1 (final)

## Diagnosis

Open P0/P1 without PR: none actionable (#22 is feature-scale). Selected **#187** (P3, no open PR).

Since #163, `_evaluate_lexical_relation` always calls `_resolve_target_lex_ref_type` with `plan_time=True` and performs lazy create via `_create_target_lex_ref_type` after structural guards. No production caller passed `allow_create=True`; the resolver’s leg-4 create duplicated that path and could confuse future edits (see #186’s note about dual drop surfaces on the old create leg).

## Resolution

- Remove the `allow_create` parameter and the Move-time create branch from `_resolve_target_lex_ref_type`; keep plan-time `PLAN_TIME_PENDING` prediction only.
- Retarget unit tests: create behaviour is exercised through `_create_target_lex_ref_type` and plan-time prediction, matching production.
- Add `test_issue187_no_allow_create_keyword_in_production_resolver`.

## Verification

- `tests/unit/test_038_t123_lexreftype_key_and_create.py`
- `tests/unit/test_issue187_allow_create_removed.py`
- `tests/unit/test_issue186_lazy_type_create_failure_emits_one_drop_record.py` (unchanged path)

**Verdict: GO** — closes #187.
