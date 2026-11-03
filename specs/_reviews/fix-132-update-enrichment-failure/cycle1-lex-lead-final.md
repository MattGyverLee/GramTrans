# fix-132 UPDATE enrichment pass failure — lex-lead cycle 1 (final)

**Issue**: #132 (P2 bug, never-silent audit; closed umbrella, remaining sites)  
**Scope**: `_execute_update_semantic` owned-collection enrichment `except` path (impl-111 §5 HIGH list sibling).

## Diagnosis

Open P0/P1 without an open PR: none (#22 is feature-scale). Selected **#132**
follow-up — whole-pass enrichment failure reporting.

When `_enrich_owned_collections` raised inside `_execute_update_semantic`, Move
logged and emitted a `report_sink.Warning` but appended **no**
`DroppedItemRecord` when `dropped` was wired. Per-child enrichment drops were
already recorded inside `_enrich_one_collection`; a pass-level raise (before or
after partial work) left the run report empty for that failure while Preview
could still show planned enrichment deltas — the same “log-only swallow” shape
#132 batch 1 closed on post-loop `_ensure_*` nets.

## Resolution

- Add `_record_enrichment_pass_failure` and call it from the enrichment
  `except` path when `dropped` is not None (one owner-level record naming the
  exception; does not replace per-collection drops when the pass returns).

## Verification

- `tests/unit/test_issue132_update_enrichment_failure.py` (new)
- `tests/unit/test_038_enrichment_executor.py` (unchanged happy paths)

**Verdict: GO** — refs #132 (UPDATE enrichment pass never-silent).
