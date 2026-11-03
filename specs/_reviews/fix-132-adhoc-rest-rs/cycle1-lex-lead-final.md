# Issue #132 — adhoc RestOf*RS Add never-silent — lex-lead cycle 1 (final)

## Diagnosis

**Issue selection:** No open **P0/P1** bugs without an open PR (#22 is feature-scale). Selected **#132** (P2 never-silent audit; issue closed, batched acceptance) — **`MoAlloAdhocProhib.RestOfAllosRS` / `MoMorphAdhocProhib.RestOfMorphsRS`** `.Add` swallow on the adhoc/compound create path (impl-111 §5 RA/RS list; distinct from merged StratumRA batch #246 and open NC/slot/feat-struc PRs).

After GUID resolution, `adhoc_compound_rules_execute_action` wrapped each `.Add()` in `except (AttributeError, TypeError): pass`. Move could finish with a created prohibition missing secondary allomorphs/morphemes and **no** `DroppedItemRecord` — same SC-003 never-silent gap as `TargetsRS` / sense-list batches.

## Resolution

- Added `_try_add_adhoc_rest_rs_member`: warning log + deduped `DroppedItemRecord` on missing collection or `Add` failure.
- Routed both RestOf* loops through the helper; `FirstAllomorphRA` / `FirstMorphemeRA` RA wiring unchanged (separate batch if needed).

## Verification

- `tests/unit/test_issue132_adhoc_rest_rs_add.py` (new, 2 tests)

**Verdict: GO** — refs #132.
