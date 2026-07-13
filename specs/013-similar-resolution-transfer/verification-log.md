# 013 SIMILAR-Resolution MERGE Write Mode — Live Verification Log

**Date**: 2026-07-13
**Harness**: FLExToolsMCP `flextools_run_module` (flexicon process).
**Target**: `Ejagham Full GT-Test` (throwaway; restored from
`backups/Ejagham Full.fwbackup` afterward).
**Scaffold**: [tests/integration/test_013_merge_live.py](../../tests/integration/test_013_merge_live.py)
(skip-by-default; `GRAMTRANS_E2E=1` to run).

## What was verified (T-S3c core + T-S1 live-verify risk)

Feature 013 adds the `merge` (target-preserving, fill-the-gaps) entry-level write
mode next to the existing `overwrite` (source-wins) mode. Both live in the flexicon
fork's shared `_apply_props_loop` (`BaseOperations.py`), selected by the `fill_gaps`
kwarg. The **live-verify risk** the spec flagged (Assumptions; T-S1) is the
multistring emptiness predicate — verified directly here.

### op-010931801-017 — write-mode behavior on a real object

Target POS `'Adverb'` (non-empty `Description` multistring), analysis WS `en`:

| Case | Call | Expected | Observed |
|------|------|----------|----------|
| A — MERGE conflict | `ApplySyncableProperties(pos, {Description:{en:"MERGE_SHOULD_NOT_WIN"}}, fill_gaps=True)` | non-empty target preserved | **preserved** ✓ |
| B — MERGE gap-fill | blank target, then `ApplySyncableProperties(..., {Description:{en:"FILLED_BY_MERGE"}}, fill_gaps=True)` | empty target filled from source | **filled** ✓ |
| C — OVERWRITE | `ApplySyncableProperties(..., {Description:{en:"OVERWRITTEN"}}, fill_gaps=False)` | source wins | **source won** ✓ |

Original description restored afterward (target left tidy).

### T-S1 predicate confirmed

The fork's fill_gaps multistring guard is
`if (existing.Text or "").strip(): continue` (BaseOperations.py:306) — exactly the
call form T-S1 specified (`.Text` may be `None` on an empty ITsString, hence the
`or ""` coercion before `.strip()`). Confirmed by direct `get_String(handle).Text`
reads returning `None` for a blanked alt (op-010650071-015).

## Verdict

| Criterion | Result |
|-----------|--------|
| FR-007a MERGE preserves non-empty target (target wins on conflict) | PASS |
| FR-007a MERGE fills empty/absent target from non-empty source | PASS |
| FR-007 OVERWRITE source-wins (contrast) | PASS |
| T-S1 multistring emptiness predicate | CONFIRMED (`(existing.Text or "").strip()`) |

## Scope note

The planner-level SIMILAR threading — `identity_remap` pre-seeding (FR-006),
`_plan_identity_remap_children` + `fingerprint_with_owner` owner override (FR-001/
FR-003), and the `_execute_layer3` identity-remap child-population branch (FR-008) —
is covered by the unit suite (`test_013_fill_gaps.py`, `test_013_executor_merge.py`,
`matcher.fingerprint_with_owner` unit test). This live run validates the new write
mode (the capability the spec called out as the live-verify risk) against real LCM
multistrings. A full planner→executor SIMILAR round-trip on a hand-seeded
`SimilarResolution(X,"merge",Y)` against a genuine similar-but-different-GUID affix
pair remains a nice-to-have; no such pair exists off-the-shelf in the Ejagham
corpus, so it would require seeding a fixture entry.
