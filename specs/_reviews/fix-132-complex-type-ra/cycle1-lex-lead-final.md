# Issue #132 — complex-feature TypeRA tail never-silent — lex-lead cycle 1 (final)

## Bug selection (automation)

- Open **P0:** none.
- Open **P1 without PR:** only **#22** (conflict-mode epic; not a single bounded fix).
- **Chosen:** **#132** (P2 never-silent audit; issue closed, batched acceptance) — post-loop **`IFsComplexFeature.TypeRA`** assignment in `_run_complex_feature_type_ra_pass` (`impl-111` §5 HIGH list: complex-feature TypeRA tail).

## Diagnosis

When `_classify_complex_type_ra` returned `TYPE_RA_WIRE`, Move assigned `TypeRA` with a bare setattr and incremented `_complex_type_ra_writes` without read-back. If pythonnet/LCM rejected the write (or accepted it without persisting on the feature), the pass could finish with a null `TypeRA`, zero Skip, and an inflated write tally — the same never-silent gap already closed on `InflectableFeatsRC` (#133) and other #132 batches. A raising setattr escaped to `_ensure_complex_feature_type_ra`, which only logged a `LeafExecutionFailure` without per-edge reporting.

## Resolution

- Add `_complex_type_ra_readback_matches` and `_try_wire_complex_feature_type_ra`: warning log, optional `DroppedItemRecord` on `context._dropped`, read-back confirmation before counting a write.
- Route the `TYPE_RA_WIRE` arm through the helper; failed wires emit `Skip(NOT_REPRODUCIBLE)` with `WRITE_FAILED` detail (endpoints resolved, write did not land).

## Verification

```bash
PYTHONPATH=src python3 -m pytest tests/unit/test_issue132_complex_type_ra_wire.py tests/unit/test_issue37_complex_type_ra.py -q
```

**Verdict: GO** — refs **#132**.
