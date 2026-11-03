# fix-132 late `_ensure_*` safety nets — lex-lead cycle 1 (final)

**Issue**: #132 (P2 bug, never-silent audit; closed umbrella, remaining sites)  
**Also refs**: #134 (`_ensure_late_rule_refs`), #15 / spec 041 (`_ensure_ref_repoint`)

## Diagnosis

Open P0/P1 without an open PR: none (#22 is feature-scale). Selected **#132**
batch follow-up — post-loop `_ensure_*` gaps.

PR #209 (batch 1) wired seven post-loop safety nets to `LeafExecutionFailure`.
Issues **#134** and **#15** added `_ensure_late_rule_refs` and
`_ensure_ref_repoint` afterward; their `except` paths still only called
`_log.exception`. A Move could finish with `leaf_failed == 0` while late
phon-rule/adhoc repair or opt-in stale-reference re-point never ran, and the
`leaf_failed` tally was incremented **before** these two calls — so even a
future wiring mistake on the counter would miss them.

## Resolution

- Add optional `post_pass_failures=` to both helpers; on raise, append
  `_record_post_pass_failure` with stable ids `post-pass:late-rule-refs` and
  `post-pass:ref-repoint`.
- Pass `_leaf_execution_failures` from `execute()` and move the post-pass
  `leaf_failed += …` increment to after both calls (same window as batch 1).

## Verification

- Extended `tests/unit/test_132_ensure_post_pass_failures.py` (parametrize)
- Full module `pytest tests/unit/test_132_ensure_post_pass_failures.py`

**Verdict: GO** — refs #132 (late ensure never-silent reporting).
