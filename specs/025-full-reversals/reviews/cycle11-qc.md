# QC Report — Cycle 11 (Findings 1 & 2 re-check)

**Date:** 2026-07-13
**Scope:** Read-only re-check of T037 Finding 1(a), 1(b), Finding 2 only.
**Commit:** b8d325d495567132a46305f24dbcb4c7cdf20c9a (025-full-reversals)

## Finding 1(a) — references.py `_multistring_dict` — CLOSED
- `references.py:341` (StringCount/GetStringFromIndex branch):
  `key = (handle_to_id.get(wh) or str(wh)) if handle_to_id else wh`
- `references.py:358` (`_data` dict branch): identical expression.
- Resolver branch (`handle_to_id` truthy): `.get(wh)` miss → `str(wh)`, never bare `int`. Output dict is all-str-keyed whenever a resolver is supplied, so `divergence_fingerprint`'s `tuple(sorted(snapshot.items()))` (`references.py:522`, resolver branch) cannot hit `TypeError: '<' not supported between int and str`.
- No-resolver branch (`else wh`) unchanged — raw handle preserved, confirmed via docstring lines 310-315 and code path at `references.py:524` (`_multistring_dict(ms)` with no second arg, `# {handle: text}, raw`).

## Finding 1(b) — categories.py `_plan_entry_reference_decisions` except clause — CLOSED
- `categories.py:3480` — caught types unchanged: `except (AttributeError, TypeError, KeyError) as exc:`.
- Guid re-extraction guarded (`categories.py:3493-3496`, own try/except, defaults to `""`).
- `_dropped` read guarded (`categories.py:3503-3506`, own try/except, defaults to `None`).
- Emit gated on `dropped is not None` (`categories.py:3507`), calls `_append_dropped_once(dropped, DroppedItemRecord(...))` (`categories.py:3508-3517`) — same dedup helper used elsewhere in this file.
- Record shape: `owner_kind="LexEntry"`, `field_name="EntryReferenceDecisions"` (synthetic marker), `reason=f"reference-decision planning failed: {type(exc).__name__}: {exc}"` — matches spec (type name + message).
- Function still `return ()` at `categories.py:3518` after the emit; existing warning log (`categories.py:3497-3502`) preserved alongside the new record — nothing masks the original exception.

## Finding 2 — preview.py/transfer.py `_ws_map` parity — CLOSED
- `to_ws_map_dict` imported in both branches: `preview.py:36` (`__package__` branch, `.ws_mapping`) and `preview.py:38` (fallback, `ws_mapping`) — matches `transfer.py:45`/`transfer.py:70`.
- `preview.py:329`: `object.__setattr__(context, '_ws_map', to_ws_map_dict(ws_mapping))` executes immediately **before** `plan_reversal_decisions(context, _resolver_cache, _dropped)` at `preview.py:335` — order confirmed correct.
- Same helper `transfer.execute` uses: `transfer.py:182` (`ws_map = to_ws_map_dict(getattr(plan, "ws_mapping", None))`) and attaches identically at `transfer.py:353` (`object.__setattr__(exec_ctx, '_ws_map', ws_map)`).
- Consumer confirmed: `reversals.py:443` — `ws_map = getattr(ctx, "_ws_map", None) or {}`, reached via `categories.plan_reversal_decisions` (`categories.py:4031-4045`) → `reversals.plan_reversals(...)`. Preview's `context` now carries the real mapping before this call, not `{}`.

## Final Assessment
**Recommendation:** APPROVE — both findings CLOSED, no residual issues in the audited scope.

---
**Reviewed By:** lex-qc (cycle 11)
