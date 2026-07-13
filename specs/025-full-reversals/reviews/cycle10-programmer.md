# Cycle 10 -- Programmer report: T037 Finding 1 + Finding 2 fixes

**Worktree:** `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals`
**Branch:** `025-full-reversals`
**Commit:** `b8d325d495567132a46305f24dbcb4c7cdf20c9a`
(`fix(025): T037 Finding 1+2 -- never-silent WS-fingerprint TypeError + Preview/Move ws_map parity`)

Strict TDD followed for both findings: each new test was run against
pre-fix code and confirmed RED for the exact reported reason before the
fix was applied, then confirmed GREEN after.

---

## Finding 1 (never-silent violation, shared 024 code)

### Finding 1(a) -- `references.py` mixed int/str key TypeError

**File:** `src/gramtrans/Lib/references.py`, function `_multistring_dict`
(originally lines ~289-343; now ~289-361 after the added comments/docstring).

**Root cause confirmed exactly as described:** both key-construction sites
inside `_multistring_dict` --

- the `StringCount`/`GetStringFromIndex` branch (was line 326):
  `key = handle_to_id.get(wh, wh) if handle_to_id else wh`
- the `_data` dict branch (was line 341): same pattern

-- fell back to the **raw int handle** `wh` whenever `handle_to_id` was
supplied but did not contain an entry for that handle. This produced a
snapshot dict with mixed `int`/`str` keys, and
`divergence_fingerprint`'s resolver branch
(`tuple(sorted(snapshot.items()))`, `references.py:505`) then raised
`TypeError: '<' not supported between instances of 'int' and 'str'`
whenever comparison had to order an `int` key against a `str` key.

**Fix (both occurrences changed identically):**

```python
key = (handle_to_id.get(wh) or str(wh)) if handle_to_id else wh
```

An absent handle now stringifies (`str(wh)`) instead of staying a bare
`int`, so the resolver branch's output is **always** consistently
str-keyed. The **no-resolver branch** (`handle_to_id is None`) is
completely untouched -- the `else wh` arm is unchanged, preserving the
raw-handle shape `_item_label` and `divergence_fingerprint`'s own
no-resolver positional fallback rely on, per the function's own docstring
(lines 484-496, unchanged).

Docstring for `_multistring_dict` (lines ~289-320) updated to document the
stringify-fallback contract and cite the exact TypeError this fixes.

**New/changed test:**
`tests/unit/test_reference_ws_resolution.py::test_divergence_fingerprint_does_not_raise_when_resolver_missing_a_handle`

- Builds a `source_project` whose `WritingSystems.GetAll()` registers only
  `"en"` (handle 1001), but the source **item**'s `Name` multistring
  populates a *second* alt under handle `1003` -- a handle absent from
  that project's own resolver entirely (the live corpus condition).
- Confirmed RED before the fix: raised exactly
  `TypeError: '<' not supported between instances of 'int' and 'str'` at
  `references.py:505` (captured verbatim in the pre-fix pytest run).
- Post-fix (GREEN): asserts `divergence_fingerprint(...)` does not raise,
  the `"Name"` field's snapshot pairs are **all str-keyed**
  (`{"en": "Water", "1003": "Orphan"}`), and `sorted(...)` over that dict
  succeeds and is deterministic.
- All 7 pre-existing tests in that file (`(a)`-`(e)` write-first
  regression contract, both no-resolver and threaded-resolver variants)
  still pass unchanged.

### Finding 1(b) -- silent catch-all in `categories.py`

**File:** `src/gramtrans/Lib/categories.py`,
`_plan_entry_reference_decisions` (function starts ~3349; except clause
was lines 3480-3488, now ~3480-3512 after the fix).

**Fix:** the `except (AttributeError, TypeError, KeyError) as exc:` clause
(exception *types caught* are unchanged, per the finding's scope) now, in
addition to the existing warning log:

1. Safely re-extracts `entry_guid` via a nested `try/except Exception`
   around `_guid_str_from(src_entry)` (the same call the log line used
   **unprotected** before -- hardened so a guid-extraction failure inside
   the handler itself can never mask the original exception with a new
   traceback).
2. Safely reads `dropped = getattr(context, "_dropped", None)` (also
   guarded).
3. When `dropped is not None`, appends via the module's existing
   `_append_dropped_once` helper (same dedup convention as every other
   `DroppedItemRecord` emission site in this file) a record:
   - `owner_kind="LexEntry"`
   - `owner_guid=entry_guid`, `owner_label=""`
   - `field_name="EntryReferenceDecisions"` (synthetic marker -- not a
     real LCM field name, since the failure is at the whole-entry
     reference-decision-planning level, not one specific field)
   - `item_name=""`, `item_guid=entry_guid`
   - `reason=f"reference-decision planning failed: {type(exc).__name__}: {exc}"`
4. Still `return ()` (fail-soft return value unchanged; the fix is
   entirely in the reporting side-channel).

**New test:**
`tests/unit/test_cycle16_drop_reporting.py::test_plan_entry_reference_decisions_catchall_emits_dropped_record`

- Co-located with this file's existing `_plan_entry_reference_decisions`
  Move/Preview parity tests (`_FakeSourceEntry`, `_FakeRunContext`
  fixtures reused as-is).
- Monkeypatches `categories._get_resolver_cache` to raise a `TypeError`
  (the first call the try body makes after `dropped` is established),
  forcing the except handler.
- Confirmed RED before the fix: `preview_dropped == []` (silent, as
  reported).
- Post-fix (GREEN): asserts exactly one `DroppedItemRecord` lands in
  `ctx._dropped`, with `owner_kind == "LexEntry"`, `owner_guid ==
  item_guid == "entry-guid-catchall"`, and `reason` containing both
  `"TypeError"` and the forced exception message.
- All 10 pre-existing tests in that file still pass unchanged.

### Finding 1 semantic flag for lex-domain

Per the task's explicit request: stringifying an unresolved int handle
(`str(wh)`, e.g. `"1003"`) as the fallback key **could theoretically
collide** with a genuinely-resolved writing-system Id string that happens
to be the literal digit string `"1003"`. In practice every real LCM
writing-system Id observed (via FLExToolsMCP against live projects) is an
ICU/BCP-47-style locale tag (`"en"`, `"es-419"`, `"koh"`, etc.) -- never a
bare decimal-digit string -- so this is believed to be a non-issue for any
real corpus. However, **nothing in the LCM writing-system model
structurally forbids** a custom WS Id that happens to be all-digits, and
if such a project ever existed, a source item populating BOTH (a) a
genuinely-resolved WS whose Id is literally `"1003"` AND (b) an
*unrelated* unresolved raw handle that also happens to equal `1003`
would produce a **false key collision** in the snapshot dict (the second
write would silently overwrite the first under the same str key `"1003"`)
-- turning what should be two distinct fingerprint entries into one,
which could mask a genuine divergence between them. This is flagged here
per your instruction rather than silently papered over; no corpus
evidence of an all-digit WS Id has been found, and no code change was
made to further guard against it (would require a sentinel prefix, e.g.
`f"~unresolved~{wh}"`, which changes the fingerprint's external string
shape and was out of scope for this fix). Recommend lex-domain confirm
whether an all-digit custom WS Id is a real possibility in this
ecosystem; if so, a follow-up should adopt a collision-proof sentinel
format for the fallback key.

---

## Finding 2 (Preview/Move parity, 025's own code)

**File:** `src/gramtrans/Lib/preview.py`, `build_run_plan` (signature at
line 112, already receiving `ws_mapping: WSMapping`).

**Fix:**
1. Imported `to_ws_map_dict` from `.ws_mapping` (both `__package__` and
   fallback-import branches, mirroring `transfer.py`'s own import
   convention exactly -- same helper, no reinvention).
2. Immediately before the `plan_reversal_decisions(...)` call (was line
   318, now further down after the added comment block), added:
   ```python
   object.__setattr__(context, '_ws_map', to_ws_map_dict(ws_mapping))
   ```
   This mirrors `transfer.execute`'s own convention exactly
   (`transfer.py:182` computes `ws_map = to_ws_map_dict(getattr(plan,
   "ws_mapping", None))`; `transfer.py:353` attaches it via
   `object.__setattr__(exec_ctx, '_ws_map', ws_map)`), placed early enough
   that `plan_reversal_decisions` -> `reversals.plan_reversals`'s
   `getattr(ctx, "_ws_map", None) or {}` read (`reversals.py:443`) -- and
   any other reversal-path reader -- now sees the real mapping instead of
   always falling back to `{}` (identity).

**New tests (new file):**
`tests/unit/test_preview_move_ws_map_parity.py` (fixtures combine
`test_categories_stems.py`'s minimal STEMS entry/sense/handle fakes with
`test_reversal_walk.py`'s reversal-index/WS-repo fakes, per this
codebase's established per-file fixture convention):

1. `test_build_run_plan_populates_ws_map_and_reversal_walk_resolves_mapped_ws`
   -- one copied stem entry/sense, one source reversal index keyed by
   `"koh"`, a non-identity `WSMapping` (`"koh" -> "gez"`), target
   registers `"gez"` (not `"koh"`). Confirmed RED before the fix:
   `context._ws_map` was `None`. Post-fix (GREEN): asserts
   `context._ws_map == {"koh": "gez"}`, exactly one reversal decision with
   `target_ws_id == "gez"`, and no `"writing system not mapped"` drop.
2. `test_preview_and_move_resolve_same_target_ws_for_reversal_index` --
   re-derives a Move-style context using the SAME `to_ws_map_dict` helper
   and the SAME fully-settled `copy_set` Preview's leaf-dispatch loop just
   assembled (`context._copy_set`, mutated in place by `build_run_plan`),
   calls `reversals.plan_reversals` directly against it, and asserts
   Preview's and this Move-style re-derivation's `target_ws_id` are
   identical (`"gez"` both). Confirmed RED before the fix (`plan.reversal_
   decisions` was empty, `len() == 0` vs expected `1`, because the index
   was silently dropped for "writing system not mapped" under the
   still-identity `ws_map`).

---

## Pytest summary (offline unit suite, `tests/unit`)

**Before (clean `HEAD` `1a1849c`, verified via `git stash push -u` /
`git stash pop` round-trip so the true pre-existing baseline could be
isolated from my own uncommitted work):**

```
1 failed, 1501 passed, 9 skipped, 14 xfailed, 14 xpassed in 7.58s
```
(the 1 failure is `test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos`
-- the documented pre-existing, non-025 failure, unchanged/untouched.)

**After (all fixes + new tests applied, commit `b8d325d`):**

```
1 failed, 1505 passed, 9 skipped, 14 xfailed, 14 xpassed in 8.91s
```
Same single pre-existing failure, **+4 passed** (exactly the 4 new tests
added: 1 in `test_reference_ws_resolution.py`, 1 in
`test_cycle16_drop_reporting.py`, 2 in the new
`test_preview_move_ws_map_parity.py`), **zero other regressions**.

Note: the task brief's stated baseline ("1524 passed / 1 pre-existing
failure") did not match either the `HEAD`-clean run or any intermediate
state observed in this session -- the worktree's actual current `HEAD`
(`1a1849c`, "Phase 6 Polish T034-T036") evidently already carries more
tests than whatever snapshot the 1524 figure was recorded against. The
`git stash`-isolated clean-`HEAD` baseline above (1501 passed/1 failed) is
the authoritative pre-my-work number for this worktree state, and the
delta against it (+4 passed, 0 regressions, same 1 pre-existing failure)
is the number that matters for this report.

---

## Files changed

- `src/gramtrans/Lib/references.py` -- Finding 1(a) fix + docstring update.
- `src/gramtrans/Lib/categories.py` -- Finding 1(b) fix
  (`_plan_entry_reference_decisions` except clause).
- `src/gramtrans/Lib/preview.py` -- Finding 2 fix (`build_run_plan`
  `context._ws_map` threading).
- `tests/unit/test_reference_ws_resolution.py` -- new Finding 1(a)
  regression test.
- `tests/unit/test_cycle16_drop_reporting.py` -- new Finding 1(b)
  regression test.
- `tests/unit/test_preview_move_ws_map_parity.py` -- new file, Finding 2
  regression + parity tests (2 tests).
