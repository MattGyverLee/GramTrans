# Issue #138 — lex-lead cycle 2 (final)

## Diagnosis

Open P0/P1 without an open PR: none (#22 is feature-scale). Selected **#138** (P3 umbrella) — cycle-3 QC P2 from `cycle3-lex-qc-108.md`: when a struct-type `FeaturesRS` has both a **missing** member and **shared members already out of source order**, Move correctly repairs by insert-only (no `REORDERED` Skip). Preview Repair rows did not say that existing shared members stay in target order.

## Resolution

- Add `_features_rs_present_shared_order_differs` and document the combined case in the ORDERING POLICY banner.
- Append `; shared members already {FEATURES_RS_REORDERED_NOTE}` on Preview Repair rows and Move repair `log.info` when that helper is true.
- No classifier outcome change; no new Skip.

## Verification

- `tests/unit/test_issue108_features_rs_repair.py::TestIssue138` (two new tests)
- Full `tests/unit/test_issue108_features_rs_repair.py`

**Verdict: GO** — refs #138 (missing + reordered observability).
