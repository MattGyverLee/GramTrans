# Cycle 2 — Verification Report: Feature 027 (Complex Forms & Variants), US1 MVP

**Worktree**: `../GramTrans-027-complex-forms-variants` @ `e8686c3`. Git status
clean at end of verification (scratch neuter edits made and fully reverted).

## Item 1 — RED-before-GREEN genuine: **PASS**

Read all 9 tests in `test_027_entryref_reproduction.py` — they call
`categories._run_entryref_create_pass(ctx, target, tag=None)` directly against
duck-typed fakes (no mocking of the function itself), asserting on real
side-effects (`factory.create_log`, `entry.EntryRefsOS` contents, `RefType`,
`Skip`/`DroppedItemRecord` shape).

Spot-proved via temporary scratch edits to
`src/gramtrans/Lib/categories.py` (restored after each check; `git status`
clean throughout, confirmed via `git status --short` after restore):

1. **Full neuter** (renamed `_run_entryref_create_pass` def to
   `..._NEUTERED`): all 9 tests go RED with
   `AttributeError: module 'gramtrans.Lib.categories' has no attribute
   '_run_entryref_create_pass'` — includes the 3 named key tests
   (`test_entryref_create_pass_uncast_bare_entry_reproduces_zero`,
   `..._casts_bare_entry_reproduces_n`, `..._resolves_entry_via_live_repo_fallback`).
2. **Surgical neuter** (removed only the `_cast_lcm(target_entry, "ILexEntry")`
   line at `categories.py:5047`, function otherwise intact): re-ran the full
   file — result `1 failed, 8 passed`. The ONE failure was exactly
   `test_entryref_create_pass_casts_bare_entry_reproduces_n`, with the
   *semantically correct* failure mode predicted by its own docstring —
   `AssertionError: Skip(... 'EntryRefsOS unavailable on target entry
   entry-1')` instead of `[]`, i.e. 0 reproduced instead of N. This proves the
   test is a genuine tripwire on the #28-layer-2 cast fix specifically, not an
   accidental AttributeError-catcher.

No fixture/import bugs found; tests exercise real production behavior.

## Item 2 — Offline suite green modulo known baseline fail: **PASS**

```
python -m pytest tests/unit -q
1 failed, 1555 passed, 9 skipped, 14 xfailed, 14 xpassed in 12.07s
FAILED tests/unit/test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos
```
Matches expected exactly. STATUS.md (main repo) documents this same failure
as pre-existing baseline across many prior checkpoints (`241dbeb`, `c3f89bf`,
`cb88b00`, etc.) — confirmed non-regression, not introduced by 027.

## Item 3 — Integration scaffold skips cleanly: **PASS**

```
python -m pytest tests/integration/test_027_complex_forms_live.py -q
1 skipped in 0.09s
```
Exit 0, no collection errors.

## Item 4 — T011 create-then-wire tests: **PASS**

```
python -m pytest tests/unit/test_phase3c_post_pass_a.py -q
27 passed in 0.48s
```
The 3 new tests (`test_create_then_wire_full_flow`,
`..._preserves_source_order`, `..._idempotent_rerun`) each call
`_run_entryref_create_pass` then `_run_post_pass_a` directly in sequence
(`_run_create_then_wire` helper, lines 758-763) against the SAME target/entry
object graph, and assert C2's wiring (`ComponentLexemesRS.add_log`) landed on
the SAME container C1 created (`entry.EntryRefsOS`'s single member) — this is
genuine C1-then-C2 integration proof, not independently-mocked calls.

## Findings

No P0/P1 blockers found. One item to flag for the record (not a defect,
already disclosed by the programmer in cycle1 report item 3): C4 (drop-policy
flip) is not yet implemented, so reproduced refs are currently double-booked
(created AND still reported dropped) until Phase 6 — expected interim state,
out of this spurt's scope.

**Overall: PASS.** All 4 verification items confirmed independently.

---
**Verified By:** Verification Agent
**Date:** 2026-07-13
