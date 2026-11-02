# Issue #135 — lex-lead cycle 1 (PhMetathesisRule structure)

## Diagnosis

Open P0/P1 without an open PR: none (#22 is feature-scale). Selected **#135** (P2 fidelity epic, no open PR) — **`PhMetathesisRule` structural fields** (audit name `PhMetathesisRule.StrucChange` in impl-114).

`_phon_rule_apply_body` returned immediately after flat sync + `Disabled` for every non-`PhRegularRule` class. `PhMetathesisRule` therefore arrived as an empty shell: correct GUID and scalars from flexicon sync, but **no `StrucDescOS` context cells** and **no metathesis switch indices** (`LeftSwitchIndex` / `LeftSwitchLimit` / `RightSwitchIndex` / `RightSwitchLimit`). flexicon's `GetSyncableProperties` never carries owned context trees (same gap as regular rules' RHS), and the switch indices are not in that dict either.

Secondary fix (same PR): `reproduce_lexical_relation`'s cache-hit branch rebuilt `TargetsRS` but did not re-run issue #135 `LexReference.Name` / `Comment` copy — only the create path did.

## Resolution

- Treat `PhMetathesisRule` like `PhRegularRule` for the shared **StrucDescOS** deep-copy path (constraint pre-pass + per-cell create/wire), but **skip** the `RightHandSidesOS` loop.
- Copy the four metathesis switch-index scalars explicitly after casting to `IPhMetathesisRule`.
- On lexrel cache hit, call `_copy_supplemental_scalars("LexReference", ...)` after `_rebuild_targets_rs_in_source_order`.

## Verification

- `tests/unit/test_categories_phonology.py` (new metathesis StrucDesc + switch-index test)
- `tests/unit/test_issue135_lexrel_cache_hit_scalars.py` (new)
- `tests/unit/test_categories_phonology.py` (existing Disabled tests unchanged)

**Verdict: GO** — refs #135 (metathesis rule structure + lexrel cache-hit scalars).
