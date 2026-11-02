# Issue #132 (batch 2) — lex-lead cycle 1 (final)

## Bug selection (automation)

- Open **P0:** none.
- Open **P1 without PR:** only #22 (conflict-mode epic; not a single bounded fix).
- **Chosen:** #132 remaining site — `_wire_stratum` (P2 never-silent audit, closed umbrella with open acceptance).

## Diagnosis

FR-336 and the Phase 3c contract require that when `MoStemMsa.StratumRA` or `IMoInflAffixTemplate.StratumRA` names a stratum absent from the target, Move reports `Skip(DEPENDENCY_UNRESOLVED)` rather than leaving a dangling reference with no report line. `_wire_stratum` only logged internally via swallowed exceptions and returned silently when the GUID lookup failed, so a successful MSA/template create could finish with `leaf_succeeded` while `StratumRA` stayed null — the same swallow pattern #132 batch 1 fixed on transfer post-loop `_ensure_*` nets.

## Resolution

- Extend `_wire_stratum` to append one `Skip(DEPENDENCY_UNRESOLVED)` to `context._exec_skips` when the source names a stratum the target does not hold (category from explicit kwarg, else `context._closure_category` set by `_walk_lex_entry_closure`).
- Pass `context` from the `MoStemMsa` create path; pass `context`, `AFFIX_TEMPLATES`, and template `source_guid` from affix-template execute.
- Unit tests pin wired vs missing vs absent-source-stratum behaviour.

## Verification

- `tests/unit/test_issue132_stratum_unresolved_skip.py`
- `PYTHONPATH=src python3 -m pytest tests/unit/test_issue132_stratum_unresolved_skip.py -q`

**Verdict: GO** — refs #132 (StratumRA unresolved reporting).
