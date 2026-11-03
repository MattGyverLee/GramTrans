# Issue #132 — OVERWRITE reference Clear never-silent — lex-lead cycle 1 (final)

## Issue selection

Open **P0/P1** without an open PR: none (#22 is feature-scale). Selected **#132** (P2 never-silent audit; issue closed, acceptance batches continue) — **`_apply_reference_fields` OVERWRITE `Clear()` swallow** on the `clear_before_add=True` path (feature 024 US2 FIX 3).

Open PR **#243** closed batch-2 `.Add` failures; this site is the paired **`.Clear()`** before the first `.Add` on OVERWRITE-only call sites in `transfer._execute_overwrite`.

## Diagnosis

When `clear_before_add=True`, the first resolved member for a collection field calls `owner_coll.Clear()` inside `except (AttributeError, TypeError): pass`. A binding failure left the stale target members in place while subsequent `.Add()` calls union-rebuilt on top — wrong replace semantics — and **no** `DroppedItemRecord` reached the Move report (Principle III / #132 acceptance).

## Resolution

- Track `clear_failed_fields`; on Clear failure log, emit one enriched `DroppedItemRecord` (`reference collection Clear failed during OVERWRITE`), and skip all further `.Add()` attempts for that field in the same pass.
- Successful Clear behavior unchanged; ADD/closure paths (`clear_before_add=False`) untouched.

## Verification

- `tests/unit/test_issue132_ref_collection_add.py::test_apply_reference_fields_records_drop_when_overwrite_clear_raises` (new)
- Full `tests/unit/test_issue132_ref_collection_add.py`

**Verdict: GO** — refs #132 (OVERWRITE Clear never-silent).
