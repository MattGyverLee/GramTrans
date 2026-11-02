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

---

## From main (c488491): report reorder Skip after insert-only FeaturesRS repair

Open P0/P1 without an open PR: none (#22 is the sole open P1 epic). Selected **#138** (P3 umbrella) — cycle-3 follow-up from the owner comment: *a sequence that is missing a member and is also reordered gets inserts with no REORDERED note*.

The struct-type `FeaturesRS` Move pass uses insert-only repair (`FEATURES_RS_REPAIR`). When shared members were already out of source order, inserting missing GUIDs could mutate the target (`writes += 1`) while the classifier had only reported REPAIR — not `FEATURES_RS_REORDERED`. The run report therefore showed a successful repair with no `reordered in target, left as-is` Skip, even though the sequence still disagreed with source order (see `test_missing_inserted_beside_reordered_shared_members`).

## Resolution

After a successful repair rewrite, re-run `_classify_struct_type_features_rs` on the same type. When the post-repair outcome is `FEATURES_RS_REORDERED`, append the same `NEEDS_MANUAL` Skip detail shape as the pure-reorder path (including `FEATURES_RS_REORDERED_NOTE`).

## Verification

- `tests/unit/test_issue108_features_rs_repair.py::TestInsertOnly::test_missing_inserted_beside_reordered_shared_members`
- Full `tests/unit/test_issue108_features_rs_repair.py` module

**Verdict: GO** — refs #138 (repair + reorder note on Move).
