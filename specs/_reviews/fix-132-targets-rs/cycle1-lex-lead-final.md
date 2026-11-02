# Issue #132 — lex-lead cycle 1 (final)

## Diagnosis

**Issue selection:** No open **P0** bugs. The only open **P1** without an open PR is **#22** (conflict-mode epic — not a bounded fix). Selected **#132** (P2 never-silent audit; issue closed, acceptance still lists open sites) — **`LexReference.TargetsRS` silent `.Add` swallow** on the lexical-relation reproduce path.

`reproduce_lexical_relation` and `_rebuild_targets_rs_in_source_order` wrapped `TargetsRS.Add` in `except (AttributeError, TypeError): pass`. When Create succeeded but the ordered sequence rejected a member (pythonnet / LCM binding gaps), Move could finish with a partial or empty `TargetsRS` and **no** `DroppedItemRecord — the same swallow pattern batch 2 fixed for `GenresRC` (#183) and that open PR #243 extends to generic reference collections.

## Resolution

- Added `_try_add_lex_rel_targets_rs_member`: warning log + `DroppedItemRecord` on `TargetsRS.Add` failure (deduped via `_append_dropped_once`).
- Routed the create-path member loop and the cache-hit rebuild path through the helper; rebuild outer failures also emit one relation-level drop.

## Verification

- `tests/unit/test_issue132_lexrel_targets_rs_add.py` (new)

**Verdict: GO** — refs #132.
