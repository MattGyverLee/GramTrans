# Issue #186 — lex-lead cycle 1 (final)

## Diagnosis

Open P0/P1 queue: no P0; sole open P1 is #22 (conflict-mode rework — feature-scale, not a point fix). Selected **#186** (P3 bug, no open PR).

When Move lazily creates a missing `LexRefType` after structural guards (`_evaluate_lexical_relation`), a factory failure in `_create_target_lex_ref_type` appended a type-keyed drop **and** the caller appended `_append_type_not_found` (relation-keyed). `_append_dropped_once` keys differ, so users saw **two** records for one failure. Preview never attempts the create and only records `pending_types`, so it correctly emits no drop on this path (out of scope for #186 acceptance).

## Resolution

- Add `record_failure=False` on the lazy-create call so the create helper logs but does not append.
- Keep a single per-relation record via `_append_type_not_found` (matches existing `test_move_type_create_failure_drops_relation_without_member_records`).
- Direct `_resolve_target_lex_ref_type(..., allow_create=True)` callers still get the type-keyed record (default `record_failure=True`).

## Verification

- `test_issue186_lazy_type_create_failure_emits_one_drop_record` (new)
- `test_move_type_create_failure_drops_relation_without_member_records`
- `test_a_create_failure_is_reported_not_raised`

**Verdict: GO** — closes #186.
