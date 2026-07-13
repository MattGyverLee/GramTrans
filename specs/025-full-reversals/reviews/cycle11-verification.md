# Cycle 11 Verification Report -- 025-full-reversals

**Worktree:** D:\Github\_Projects\_LEX\GramTrans-025-full-reversals
**Commit verified:** b8d325d495567132a46305f24dbcb4c7cdf20c9a (HEAD unmoved throughout)
**Date:** 2026-07-12/13

## 1. Fresh full offline suite

Exact pytest summary line, run clean on b8d325d:

```
1 failed, 1505 passed, 9 skipped, 14 xfailed, 14 xpassed in 8.18s
```
(Re-run twice for confidence; timings varied 8.18-9.33s, counts identical.)

**Reconciliation verdict: the programmer's numbers are correct for this
worktree state.** I independently re-derived the baseline by adding a
detached scratch worktree at parent commit `1a1849c` ("Phase 6 Polish
T034-T036") and running the same suite there:

```
1 failed, 1501 passed, 9 skipped, 14 xfailed, 14 xpassed in 10.45s
```

`b8d325d` adds exactly **+4 passed**, 0 regressions, same single
pre-existing failure -- matching the programmer's `git stash`-isolated
baseline claim (1501) and the after-fix claim (1505) exactly.

The **~1524 figure is stale/orphaned**: it does not correspond to any
commit on this worktree's ancestry (no match in `1a1849c`, `b8d325d`, or
any spec doc in this worktree; `1524` appears nowhere under
`GramTrans-025-full-reversals`). The programmer's own cycle10 report
already flagged this same discrepancy and reached the same conclusion --
whatever snapshot produced 1524 is not this worktree's `HEAD` lineage.
1501/1505 is authoritative for this worktree.

The single failure is confirmed exactly:
`test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos`
-- reproduced identically at both `1a1849c` and `b8d325d`, i.e. genuinely
pre-existing and unrelated to 025. No new failures exist.

## 2. +4 new tests confirmed present and passing

```
tests\test_cycle16_drop_reporting.py .              (1)
tests\test_preview_move_ws_map_parity.py ..          (2)
tests\test_reference_ws_resolution.py .              (1)
=== 4 passed, 1539 deselected ===
```
All 4 named tests found and green:
- test_divergence_fingerprint_does_not_raise_when_resolver_missing_a_handle
- test_plan_entry_reference_decisions_catchall_emits_dropped_record
- test_build_run_plan_populates_ws_map_and_reversal_walk_resolves_mapped_ws
- test_preview_and_move_resolve_same_target_ws_for_reversal_index

## 3. Tripwire proofs (genuine RED confirmed)

**Fix 1 -- `references.py::_multistring_dict`** (line ~341/358): reverted
`(handle_to_id.get(wh) or str(wh))` -> `(handle_to_id.get(wh) or wh)`.
Result: `test_divergence_fingerprint_does_not_raise_when_resolver_missing_a_handle`
went RED with exactly `TypeError: '<' not supported between instances of
'int' and 'str'` at `references.py:522` (`sorted(snapshot.items())`).
Restored via `git checkout --`; test GREEN again.

**Fix 2 -- `preview.py::build_run_plan`** (line 329): removed the
`object.__setattr__(context, '_ws_map', to_ws_map_dict(ws_mapping))` line.
Result: `test_build_run_plan_populates_ws_map_and_reversal_walk_resolves_mapped_ws`
went RED -- `context._ws_map` read back `None` instead of the mapped dict,
failing the assertion (with a secondary cascading `AttributeError:
'_FakeTargetProject' object has no attribute 'Cache'` in the reversal walk).
Restored via `git checkout --`; test GREEN again.

Both fixes are genuine, load-bearing, and correctly guarded.

## 4. Final worktree state

`git status --short` empty, `git diff --stat` empty, `HEAD` = `b8d325d`
(unmoved). Full suite re-confirmed clean:
`1 failed, 1505 passed, 9 skipped, 14 xfailed, 14 xpassed`. Scratch baseline
worktree removed (`git worktree remove --force`). No live Move was run.

**Status: PASS.**
