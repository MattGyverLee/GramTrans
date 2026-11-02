# Issue #132 — compound/adhoc StratumRA never-silent — lex-lead cycle 1 (final)

## Issue selection

No open **P0** bugs. The only open **P1** without a PR is **#22** (conflict-mode epic — not a bounded fix). Selected **#132** (P2 never-silent audit; issue closed) — **adhoc/compound morph rule `StratumRA` silent miss** on the create path. Open PR **#245** covers the shared `_wire_stratum` helper for stem MSAs and affix templates only; **MoEndoCompound / MoExoCompound / adhoc** rules still used duplicated inline wiring that swallowed a missing stratum with no report line.

## Diagnosis

FR-336 requires stratum references to resolve against Phase 3a strata or be reported. `adhoc_compound_rules_execute_action` wired `StratumRA` in a local `try/except` loop identical to the pre-fix `_wire_stratum`: success when the GUID matched, **no Skip** when the target lacked the stratum. Move could finish with a created rule whose `StratumRA` stayed null and the run report showed nothing — the same never-silent gap batch 2 is closing elsewhere on #132.

## Resolution

- Extend `_wire_stratum` to append `Skip(DEPENDENCY_UNRESOLVED)` to `context._exec_skips` when the source names a missing stratum (same contract as PR #245).
- Route **compound/adhoc** create through `_wire_stratum` with `GrammarCategory.ADHOC_COMPOUND_RULES`.
- Pass `context` from stem-MSA closure (`_closure_category`) and affix-template execute (explicit category + `source_guid`).

## Verification

- `tests/unit/test_issue132_stratum_unresolved_skip.py` — helper + compound execute paths

**Verdict: GO** — refs #132.
