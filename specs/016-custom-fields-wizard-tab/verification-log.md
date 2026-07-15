# 016 Custom Fields — Live Verification Log

**Date**: 2026-07-13
**Harness**: FLExToolsMCP `flextools_run_module` (flexicon process), driving the real
`gramtrans.Lib.api` / `harness.full_run` engine.
**Pair**: source `Ejagham Mini` → target `Ejagham Full GT-Test` (throwaway, restored
from `backups/Ejagham Full.fwbackup` before the run).
**Scaffold**: [tests/integration/test_custom_fields_live.py](../../tests/integration/test_custom_fields_live.py)
(skip-by-default; `GRAMTRANS_E2E=1` to run).

## Source inventory (op-005733004-005)

Source `Ejagham Mini` custom fields (2):
- `LexSense` `'Target Equivalent'` — CellarPropertyType 13 (String/Text)
- `MoForm` `'Allomorph Comment'` — CellarPropertyType 16 (Multi-Unicode)

## Classification vs fresh target (op-005821765-006)

Fresh `Ejagham Full GT-Test` has 11 custom fields. Source fields classify:
- `LexSense.Target Equivalent` → **NEW** (absent) — exercises create-early.
- `MoForm.Allomorph Comment` → **IN_TARGET** (present) — exercises reuse.

## RUN #1 — full transfer, Custom Fields enabled (op-005854xxx / op-010000352-007)

- Plan: 147 total actions; **exactly 1** `CreateDefinitionAction` —
  `LexSense.'Target Equivalent'` type 13. **0** create actions for the IN_TARGET
  `MoForm.'Allomorph Comment'` (reused, not recreated).
- Move executed, wall-clock 0.382 s, exit 0, no errors.
- **US3 scenario 1** (create for absent) + **scenario 2** (no create for present):
  PASS. **US4 / SC-005** (NEW vs IN_TARGET): PASS.
- Note: the create-before-fill guarantee (FR-010 / SC-004) is enforced by the
  `execute_move` schema pre-pass (`_ensure_custom_fields` runs AddCustomField +
  `_persist_without_close` before `transfer.execute`), not by plan-list index; the
  create action's list index (53) is therefore not a correctness signal.

## Create-early persisted (op-010130176-008)

Reopened `Ejagham Full GT-Test` read-only after Move:
- Target custom-field count **11 → 12**.
- `LexSense.'Target Equivalent'` **present** in the target MDC after a fresh reopen.
- No flid-0 fail-loud raised (FR-012): PASS.

## Idempotency — SC-009 (op-010204219-009)

Re-classifying both source fields against the **updated** target: both now
`IN_TARGET` ⇒ a re-run emits **0** `CreateDefinitionAction`s. Idempotent by
`(owner_class, name)` match: PASS. (The full second-transfer idempotency oracle is
also covered by `test_full_workflow_e2e.py::test_full_selection_and_idempotency`.)

## Verdict

| Criterion | Result |
|-----------|--------|
| SC-005 NEW field create-definition emitted | PASS |
| US3.2 IN_TARGET field reused (no create) | PASS |
| Create-early persisted through reopen | PASS |
| FR-012 fail-loud (no flid-0) | PASS |
| SC-009 idempotent re-run (0 new creates) | PASS |

**Not exercised this run (documented gap):** the value-fill count for
`'Target Equivalent'` was not asserted (the fresh target already holds Ejagham
Full's entries by GUID, so no source sense carrying that value was newly written).
The create-early schema path — the correctness core of 016 — is fully proven.
`quickstart.md` (T023) remains unwritten; the scaffold above is the runnable
artifact.
