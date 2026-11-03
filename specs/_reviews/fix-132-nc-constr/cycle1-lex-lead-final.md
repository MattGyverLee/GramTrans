# Issue #132 — phon-rule NC constraint RS Add — lex-lead cycle 1 (final)

## Diagnosis

Open P0/P1 without an open PR: none (#22 is feature-scale). Selected **#132** (P2 never-silent audit; issue closed, acceptance lists open sites) — **phon-rule `PhSimpleContextNC.PlusConstrRS` / `MinusConstrRS` wiring** (`impl-111` §5 RA/RS `except: pass` list).

Inside `_phon_rule_apply_body` → `_copy_context_cell`, constraint references are resolved and `.Add()`-ed onto the new NC cell. A failing `Add` (typical pythonnet `TypeError: No method matches given arguments`) was caught by the per-field `except (AttributeError, TypeError): pass`, so Move could finish with an NC context missing constraints and **no** `DroppedItemRecord` — the same swallow pattern batch 2 fixed for `GenresRC` and `LexReference.TargetsRS`.

Missing constraints after the pre-pass still raise `RuntimeError` (unchanged). This fix covers **resolved** constraints whose collection rejects the write.

## Resolution

- Add `_report_dropped_nc_constraint_rs` and call it from the `PlusConstrRS` / `MinusConstrRS` loop when `Add` raises `AttributeError` or `TypeError`.
- Leave outer getattr/duck-typing gaps on the same `except` set (unchanged).

## Verification

- `tests/unit/test_037_rule_context_copy.py::test_nc_plus_constr_rs_add_failure_emits_drop` (new)
- Full `tests/unit/test_037_rule_context_copy.py`

**Verdict: GO** — refs #132 (phon-rule constraint RS Add never-silent).
