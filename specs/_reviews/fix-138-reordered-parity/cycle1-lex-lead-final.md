# Issue #138 — lex-lead cycle 1 (Preview/Move REORDERED wording)

## Diagnosis

Open P0/P1 without an open PR: none (#22 is feature-scale). Selected **#138** (P3 umbrella, no open PR) — cycle-3 QC P2 from `cycle3-lex-qc-108.md`: Preview's REORDERED row used `SKIP (reordered in target, left as-is)` while Move emitted a longer `Skip.detail` sentence ending with the same note. Linguists comparing Preview to the Move report saw two different phrasings for the same classifier outcome.

## Resolution

- Add `features_rs_reordered_skip_detail` and `features_rs_reordered_after_repair_skip_detail` in `categories.py` (shared with Move).
- Preview `render_struct_type_features_rs` prints `SKIP ({detail})` using the same helper Move uses for pure REORDERED Skips.
- Live test row filter updated to match the unified prefix.

## Verification

- `tests/unit/test_issue108_features_rs_repair.py::TestInsertOnly::test_preview_row_for_reordered_matches_move`
- Full `tests/unit/test_issue108_features_rs_repair.py`

**Verdict: GO** — refs #138 (Preview/Move REORDERED text parity).
