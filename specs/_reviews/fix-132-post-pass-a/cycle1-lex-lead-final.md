# fix-132 post-pass A guarded Adds — lex-lead cycle 1

**Issue**: #132 (P2 bug, never-silent audit)  
**Scope**: batch — `_run_post_pass_a` unguarded `ComponentLexemesRS` /
`PrimaryLexemesRS` / `ShowComplexFormsInRS` `.Add` calls (impl-111 §5 HIGH list).

## Diagnosis

Open P0/P1 without an open PR: none (#22 is feature-scale). Selected **#132**
(closed umbrella, remaining sites) — post-pass A tail wiring.

`_run_post_pass_a` (`categories.py`) resolves each component lexeme then calls
`seq.Add(target_lex)` with no per-item guard. A single LCM/pythonnet raise
aborted the entire pass: later fields on the same ref, other refs on the entry,
and every subsequent entry in `lexentry_ref_bindings` were left unwired with
only a post-loop `_ensure_*` log line on the safety-net path (#132 acceptance
violation).

## Resolution

- Extract `_post_pass_a_seq_has_member` (shared idempotency + read-back).
- `_add_post_pass_a_ref_member` wraps each Add: logs failures, emits one
  `Skip(DEPENDENCY_UNRESOLVED)` when read-back shows the lexeme absent, and
  logs-only when Add raised but read-back shows the member (issue #111 parity).

## Verification

- `tests/unit/test_issue132_post_pass_a_add.py` (new)
- Existing `tests/unit/test_phase3c_post_pass_a.py` (unchanged behaviour on
  happy path)

**Verdict: GO** — refs #132 (post-pass A never-silent Adds).
