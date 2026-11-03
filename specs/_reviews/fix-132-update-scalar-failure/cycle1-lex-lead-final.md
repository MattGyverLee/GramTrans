# fix-132 UPDATE scalar failure — lex-lead cycle 1 (final)

## Diagnosis

**Issue selection:** No open **P0/P1** bugs without an open PR (#22 is feature-scale; #130 closed). Selected **#132** (P2 never-silent audit; closed umbrella, batched acceptance) — **`_execute_update_semantic` scalar half** (distinct from open PR **#276**, which covers the enrichment `except` path only).

When `apply_update_semantic`, `compute_disposition`, or object resolution raised inside the scalar `try`, Move logged via `_log.exception` and emitted a `report_sink.Warning` but did **not** append a `DroppedItemRecord` when `dropped` was wired. Preview/planning could still show UPDATE intent while the Move report had no matching failure row — the same never-silent gap closed for enrichment in flight on **#276**.

## Resolution

- Add `_record_update_scalar_failure`: one owner-level `DroppedItemRecord` with `field_name="(scalar UPDATE)"` when the collector is present.
- Call from the scalar `except` path in `_execute_update_semantic` (does not replace per-field drops from `apply_update_semantic` read-back).

## Verification

```bash
PYTHONPATH=src python3 -m pytest tests/unit/test_issue132_update_scalar_failure.py -q
```

**Verdict: GO** — refs **#132**.
