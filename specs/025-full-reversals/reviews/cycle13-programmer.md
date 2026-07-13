# Cycle 13 -- Programmer report: T037 Phase-2 P0 sub-entry sense-loss fix

**Commit:** `9d1266b` on branch `025-full-reversals` (worktree
`D:\Github\_Projects\_LEX\GramTrans-025-full-reversals`), parent `b8d325d`.

## The bug (recap, confirmed)

`src/gramtrans/Lib/reversals.py::_apply_one_entry` (original lines ~807-839):

```python
target_senses = [...]
first_sense = target_senses[0] if target_senses else None
...
if parent_target_entry is None:
    new_entry = _create_top_level_entry(target, target_index, primary_text, first_sense, decision, dropped)
else:
    new_entry = _create_sub_entry(target, parent_target_entry, primary_ws_id, primary_text, decision, dropped)
...
remaining_senses = target_senses[1:] if first_sense is not None else target_senses
_link_remaining_senses(new_entry, remaining_senses)
```

`remaining_senses = target_senses[1:]` unconditionally assumed the create
call already linked `first_sense`. True for `_create_top_level_entry`
(`target.ReversalEntries.Create(target_index, primary_text, first_sense)` --
the flexicon wrapper links the sense as part of `Create`), but FALSE for
`_create_sub_entry`, whose old signature `(target, parent_entry,
primary_ws_id, primary_text, decision, dropped)` never received
`first_sense` at all -- its body (raw `IReversalIndexEntryFactory.Create()`
+ `parent.SubentriesOS.Add(...)` + `_set_reversal_form_alt(...)`) links no
sense whatsoever. A sub-entry with exactly one linked sense: `target_senses
= [s]`, `first_sense = s`, `remaining_senses = []` -- the one sense is
silently dropped (no exception, no `DroppedItemRecord`). Live proof (cycle-12
report, section 6): 9/10 sampled sub-entries had `senses=0` where Preview
predicted 1.

## Files / lines changed

- `src/gramtrans/Lib/reversals.py`
  - `_create_sub_entry` (was ~622-661, now ~622-680): added a `first_sense`
    parameter (new signature: `(target, parent_entry, primary_ws_id,
    primary_text, first_sense, decision, dropped)`); after
    `_set_reversal_form_alt(new_sub, ...)`, added:
    ```python
    if first_sense is not None:
        _link_remaining_senses(new_sub, [first_sense])
    ```
    Reuses the module's SINGLE existing sense-linking mechanism
    (`_link_remaining_senses`'s `coll.Add(sense)` on `SensesRS`) -- no new
    linking path invented, matching the top-level branch's structural
    outcome.
  - `_apply_one_entry` call site (~828-830): now passes `first_sense`
    through to `_create_sub_entry`.
  - Docstrings updated on both `_create_sub_entry` and `_apply_one_entry`
    to document the fix and why the existing `remaining_senses` slice at
    the bottom of `_apply_one_entry` is now correct for BOTH branches
    (that line itself is unchanged -- the fix is entirely in making
    `_create_sub_entry` consume `first_sense` the same way
    `_create_top_level_entry` does, not in changing the slice logic).

- `tests/unit/test_reversal_category_resolve.py`
  - Fake-side additions needed to exercise the sub-entry apply path (this
    file already had the `apply_reversals`-side fakes for top-level
    entries; the sub-entry path had no coverage at all, which is why the
    unit suite missed the bug):
    - `_FakeReversalEntriesOps.Create` now actually appends `sense` onto
      the created entry's `SensesRS` when non-`None` (previously ignored
      it entirely -- without this even the TOP-LEVEL assertions would have
      been meaningless, since the fake never modeled the live
      `ReversalIndexEntryOperations.Create(index, form, sense)` wrapper's
      real side effect).
    - New `_FakeSubEntryFactory` (`.Create()` -> fresh
      `_FakeApplyReversalEntry`) plus `_FakeApplyTarget.GetService(key)`
      returning it -- models `owned._get_owned_factory(target,
      "IReversalIndexEntryFactory")`'s `target.GetService(...)` call.
    - `_FakeApplyReversalEntry` gained a `SubentriesOS` (`_FakeApplyCollection`)
      so a created sub-entry can be asserted-on via
      `parent.SubentriesOS.Add(...)`.
    - `_FakeCtx` gained an optional `copy_set` constructor arg, stored as
      `._copy_set` (read by `_apply_one_entry` via
      `getattr(ctx, "_copy_set", None)`).

## New tests

All three added to `tests/unit/test_reversal_category_resolve.py`:

1. **`test_sub_entry_single_sense_is_linked_not_silently_dropped`** (Test A,
   the core regression) -- a sub-entry with exactly 1 linked sense must end
   with exactly 1 member in `SensesRS`.
2. **`test_sub_entry_multi_sense_links_all_n`** (Test B) -- a sub-entry with
   2 linked senses must end with exactly 2 in `SensesRS` (guards the
   `remaining_senses` slice arithmetic for the multi-sense sub case).
3. **`test_sub_entry_zero_sense_stays_zero_and_top_level_unaffected`**
   (Test C) -- a 0-sense sub-entry stays at 0 (no spurious link introduced
   by the fix), and top-level entries with 1 and with 2 linked senses still
   end with exactly 1 / 2 (no regression of the already-correct top-level
   contract).

### RED (before the fix) -- captured via `git stash`/pre-fix run

- `test_sub_entry_single_sense_is_linked_not_silently_dropped`:
  ```
  AssertionError: expected the sub-entry's single linked sense to survive
  apply_reversals, got [] (silently dropped pre-fix)
  assert 0 == 1
   +  where 0 = len([])
  ```
  Confirms the sense count was exactly 0 pre-fix, matching the live 9/10
  finding -- failing for the right reason.
- `test_sub_entry_multi_sense_links_all_n`:
  ```
  assert 1 == 2
   +  where 1 = len([<test_reversal_category_resolve._FakeSense object at ...>])
  ```
  Confirms the multi-sense sub-entry lost exactly its first linked sense
  pre-fix (the slice always drops index 0 regardless of whether the create
  call actually linked it) -- also failing for the right reason.
- `test_sub_entry_zero_sense_stays_zero_and_top_level_unaffected`: PASSED
  pre-fix (expected -- it is a no-regression guard, not itself a
  reproduction of the bug; 0-sense and top-level paths were never broken).

### GREEN (after the fix)

All three PASS; full `test_reversal_category_resolve.py` +
`test_reversal_walk.py` run: 16 passed, 0 failed.

## Mechanism used to link the sub-entry's first sense

`_create_sub_entry` now calls `_link_remaining_senses(new_sub, [first_sense])`
immediately after `_set_reversal_form_alt(new_sub, ...)`, when `first_sense
is not None`. `_link_remaining_senses` is the module's ONE existing
sense-linking primitive (`entry.SensesRS.Add(sense)`, with a best-effort
`sense in coll` de-dupe check); no new code path was written for this --
the sub-entry's `SensesRS` ends up populated through the exact same
`.Add()` call every other "link a copied sense" site in this module uses,
so its structural shape after apply is identical to a top-level entry's.

Fail-soft posture: mirrored `_link_remaining_senses`'s own existing
tolerance (`try/except (AttributeError, TypeError): pass` around `.Add()`)
rather than inventing a new `DroppedItemRecord` path for this specific call
-- consistent with how `_create_top_level_entry` treats a `None`/failed
`first_sense` argument to `Create(...)` today (no separate drop record for
the sense component; only the broader "create failed" / "no form to create
from" cases produce `DroppedItemRecord`s in this module, and those are
unaffected here). No exception can propagate from either branch's sense
linking.

## Top-level linking unchanged (confirmation)

`_create_top_level_entry`'s signature, body, and the
`target.ReversalEntries.Create(target_index, primary_text, first_sense)`
call are byte-for-byte unchanged. `test_sub_entry_zero_sense_stays_zero_and_top_level_unaffected`
explicitly re-asserts the 1-sense and 2-sense top-level cases end with
exactly 1 / 2 members in `SensesRS` post-fix, and
`test_shared_reversal_category_created_at_most_once_across_entries` (a
pre-existing top-level apply test) still passes unmodified. Live-validated
top-level cases (foot/leg/palm frond, 2 senses) are structurally the same
code path exercised here and are not touched by this change.

## Full-suite before/after

Both runs via `python -m pytest tests/unit -q` in the worktree.

- **Before** (`git stash` back to `b8d325d`, i.e. pre-fix, pre-new-tests):
  `1 failed, 1505 passed, 9 skipped, 14 xfailed, 14 xpassed`. The 1 failure
  is `test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos`
  (documented pre-existing, unrelated to this fix, not touched).
- **After** (this commit, `9d1266b`): `1 failed, 1508 passed, 9 skipped,
  14 xfailed, 14 xpassed`. Same single pre-existing failure, byte-identical
  assertion (`assert 0 == 1` on `pos_actions`), untouched. +3 passed = the
  3 new regression tests. No new failures, no skip/xfail/xpass count drift.

## Commit hash

`9d1266b` on branch `025-full-reversals`.

## Scope confirmation

Only the sub-entry sense-linking bug and its regression tests were touched.
Finding 2 (`categories.py` `_run_post_pass_a` `get_object_by_guid`) and
Finding 3 (024 backlog) were NOT touched, per dispatch scope. No live Move
was run; the Target project was not touched.
