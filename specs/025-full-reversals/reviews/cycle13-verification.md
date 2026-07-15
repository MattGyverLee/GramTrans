# Cycle 13 Verification -- P0 sub-entry sense-loss fix (offline re-check)

**Date:** 2026-07-13
**Worktree:** D:\Github\_Projects\_LEX\GramTrans-025-full-reversals
**Branch/Commit:** 025-full-reversals @ 9d1266b9905aa639cd681b167a6eb8ed1257ae59
**Scope:** Offline re-check only. No live Move run (Target dirty, awaiting -restore).
**Status:** PASS

## Executive Summary

All 5 verification items PASS. The 3 new regression tests pass at HEAD, the
tripwire genuinely reproduces the exact pre-fix bug (sub-entry SensesRS=0)
when the fix is temporarily reverted, the full unit suite matches the
programmer's claimed summary exactly (1508 passed / 1 pre-existing unrelated
failure / no new failures), the top-level entry path is confirmed untouched
by the diff, and the worktree is restored clean at 9d1266b.

## Item 1 -- Regression tests pass at 9d1266b

Location: `tests/unit/test_reversal_category_resolve.py` (lines 663, 711, 754).

Exact test names:
- `test_sub_entry_single_sense_is_linked_not_silently_dropped` (line 663) --
  sub-entry with exactly 1 linked sense -> SensesRS must have exactly 1
  member after `apply_reversals` (the core bug, was 0 pre-fix).
- `test_sub_entry_multi_sense_links_all_n` (line 711) -- sub-entry with N=2
  linked senses -> SensesRS must have exactly 2 members (guards the
  `remaining_senses` slice arithmetic).
- `test_sub_entry_zero_sense_stays_zero_and_top_level_unaffected` (line 754)
  -- 0-sense sub-entry stays 0 (no spurious link introduced by the fix);
  top-level 1-sense entry stays 1; top-level 2-sense entry stays 2
  (regression guard on the already-correct top-level contract).

Run:
```
python -m pytest tests/unit/test_reversal_category_resolve.py -v -k "sub_entry"
```
Result:
```
test_sub_entry_single_sense_is_linked_not_silently_dropped PASSED
test_sub_entry_multi_sense_links_all_n PASSED
test_sub_entry_zero_sense_stays_zero_and_top_level_unaffected PASSED
3 passed, 8 deselected in 0.34s
```

**Status:** PASS

## Item 2 -- TRIPWIRE (genuine RED)

Temporarily edited `src/gramtrans/Lib/reversals.py`'s `_create_sub_entry` to
remove the `first_sense` link (reverting the fix's own diff hunk):

```diff
     _set_reversal_form_alt(new_sub, target, primary_ws_id, primary_text)
-    if first_sense is not None:
-        _link_remaining_senses(new_sub, [first_sense])
+    # TRIPWIRE: reverted linking of first_sense to reproduce live bug
     return new_sub
```

Re-ran the same 3 tests. Result:

```
FAILED test_sub_entry_single_sense_is_linked_not_silently_dropped
  AssertionError: expected the sub-entry's single linked sense to survive
  apply_reversals, got [] (silently dropped pre-fix)
  assert 0 == 1

FAILED test_sub_entry_multi_sense_links_all_n
  assert 1 == 2
  (lost exactly the FIRST of the 2 senses -- matches the fix's own docstring
  claim: "pre-fix this lost exactly the FIRST of the N senses")

PASSED test_sub_entry_zero_sense_stays_zero_and_top_level_unaffected
  (correctly still green -- top-level path and the 0-sense case are
  untouched by this revert, exactly as expected)

2 failed, 1 passed, 8 deselected in 1.40s
```

This is genuine RED reproducing the exact live bug signature (SensesRS
count 0 for the 1-sense case; loses exactly sense #1 for the N=2 case,
leaving N-1). Not a fabricated/trivial failure -- it isolates precisely the
`_create_sub_entry` sense-linking gap the fix closes.

Restored the file via `git checkout -- src/gramtrans/Lib/reversals.py`,
re-ran the 3 tests: all 3 PASS again (confirmed above/re-verified).

**Status:** PASS (tripwire confirmed genuinely RED pre-fix, GREEN post-restore)

## Item 3 -- Full unit suite fresh

```
python -m pytest tests/unit -q
```

Exact summary line:
```
1 failed, 1508 passed, 9 skipped, 14 xfailed, 14 xpassed in 12.08s
```

The single failure:
```
FAILED tests/unit/test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos
AssertionError: assert 0 == 1 (pos_actions empty)
```

This matches the programmer's own commit-message claim exactly ("1508
passed / same 1 pre-existing failure ... unrelated, not touched"). No new
failures found. This is the ONLY failing test in the suite; it is
pre-existing and unrelated to feature 025 / this fix (wizard POS-grammar
wiring, not reversals).

**Status:** PASS -- matches programmer's claimed summary exactly, no new
failures.

## Item 4 -- Top-level entry path unaffected (diff read)

Read `git show 9d1266b -- src/gramtrans/Lib/reversals.py`. The diff touches
only:
- `_create_sub_entry`'s signature (adds `first_sense` param) and body (adds
  the `if first_sense is not None: _link_remaining_senses(new_sub,
  [first_sense])` call) + its docstring.
- `_apply_one_entry`'s docstring (comment-only) and the sub-entry branch's
  call site (`_create_sub_entry(..., first_sense, ...)`), passing the new
  argument through.

`_create_top_level_entry` itself (function body, signature, and its
existing `target.ReversalEntries.Create(target_index, primary_text,
first_sense)` call which already linked `first_sense` at create time) is
**not touched anywhere in the diff** -- zero lines changed in that
function. The `if parent_target_entry is None:` branch in `_apply_one_entry`
that calls it is likewise unchanged (only docstring prose around it
changed). The `remaining_senses = target_senses[1:] if first_sense is not
None else target_senses` slice logic itself is also unchanged -- the fix
works by making the sub-entry branch's create-time linking behavior match
the top-level branch's pre-existing behavior, not by changing the shared
slice arithmetic.

**Status:** PASS -- confirmed top-level path is byte-for-byte unchanged by
this fix; only the sub-entry creation path (and its call site) changed.

## Item 5 -- Worktree clean, HEAD at 9d1266b

```
git status --porcelain=v1 -b
## 025-full-reversals
git rev-parse HEAD
9d1266b9905aa639cd681b167a6eb8ed1257ae59
```

No pending changes (tripwire edit was reverted via `git checkout --`).

**Status:** PASS

## Final Assessment

**Overall Status:** PASS

All 5 verification items confirmed. The cycle-13 fix (`_create_sub_entry`
now threading and linking `first_sense`) is correctly implemented, covered
by 3 targeted regression tests that genuinely fail without the fix
(tripwire-confirmed), does not touch or regress the top-level entry
sense-linking path, and introduces no new failures in the 1508-test unit
suite (the sole failure is the known pre-existing, unrelated
`test_plan_emits_pos_action_for_picked_pos`).

**Recommendation:** APPROVE.

No live Move was run (per task scope -- Target is dirty and awaiting
-restore). This verification is offline-only, matching the programmer's own
unit-test-level claims; it does not re-validate the live 9/10-sub-entries
sampling finding against a live FLEx project.

---
**Verified By:** Verification Agent
**Date:** 2026-07-13
