# Issue #132 — phon-rule stratum RA — lex-lead cycle 1 (final)

## Diagnosis

**Issue selection:** No open **P0** bugs. The only open **P1** without a PR is **#22** (conflict-mode epic — not a bounded fix). Selected **#132** (P2 never-silent audit; issue closed, batched acceptance) — **`PhRegularRule.InitialStratumRA` / `FinalStratumRA`** immediate and deferred wiring (impl-111 §5 HIGH list, "phon-rule constraint and stratum references"; constraint RS covered by open PR #262).

When strata were already present in the target, `_phon_rule_apply_body` assigned resolved stratum objects inside `except (AttributeError, TypeError): pass`. The deferred drain used `print` only on failure. Move could finish with rules missing stratum references and **no** `DroppedItemRecord` — violating Principle I / FR-010.

## Resolution

- Add `_try_wire_phon_rule_stratum_ra`: warning log + deduped `DroppedItemRecord` on assignment failure or failed read-back.
- Route immediate wiring and `_drain_phon_rule_stratum_wiring` through the helper (`context._dropped` on the drain path).

## Verification

- `tests/unit/test_issue132_phon_rule_stratum_ra.py` (3 tests, host-free)

**Verdict: GO** — refs #132.
