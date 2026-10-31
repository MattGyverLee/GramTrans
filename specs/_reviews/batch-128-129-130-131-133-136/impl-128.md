# impl-128 -- LexEntryRef value merge on 0-action re-runs; Summary keeps runs

- Branch: fix-128-entryref-postpass-summary (worktree GramTrans-fix-128), base origin/main 23e5356
- Commit: c70448c "fix(entryref): value merge + C2 wiring on 0-action re-runs; Summary keeps runs (closes #128)"
- origin/main merged: already up to date (no re-run needed)
- PR: https://github.com/MattGyverLee/GramTrans/pull/140 (body has "Closes #128"; NOT merged)
- Verdict: READY FOR REVIEW. Unit green, live gate green, negative control confirms the gate bites.

## Defect and trace
1. `stems_execute_action` is the only caller of `_run_entryref_create_pass` (C1, incl. the
   INV-1 value-merge arm) and `_run_post_pass_a` (C2), via `_run_tail_once`. A run with no STEMS
   action never executes the tail, so a source edit to an existing ref never lands. Bindings
   are stashed at PLAN time (`_stash_entry_bindings` runs before the ALREADY_PRESENT skip), so
   they are complete even with 0 actions -- only the execute-side trigger was missing.
2. `_stash_entry_bindings` stored Summary as `{ws_id: text}`; `_merge_entryref_value_fields`
   wrote `TsStringUtils.MakeString(text, handle)`, dropping every run property.
3. Census note cited categories.py:4435/5041/5014 (now 8559/12662/12385).

## Fix
- transfer.py: new `_ensure_entryref_passes(exec_ctx, target, tag, exec_skips)`, called after
  the leaf loop next to the other `_ensure_*` safety nets (#37/#108 idiom). Runs C1 then C2,
  reuses the tail's latches (`_did_entryref_create_pass`, `_did_post_pass_a`) so it is a no-op
  when the STEMS tail already ran; never raises. With no lexicon in scope the bindings are
  empty and both passes are no-ops. Also fires for AFFIXES-only runs (previously no tail at all).
- categories.py: `_multistring_tss_by_ws_id` + record keys `summary_tss` and
  `summary_src_ws_ids` (stash); new `_tss_remap_ws_runs` clones the source ITsString
  (`GetBldr`) and, per run, rewrites ktptWs/ktptBaseWs source handle -> WS id -> ws_map ->
  target handle (fallback: the alternative's own target handle, never a raw source handle).
  `_merge_entryref_value_fields` writes that string when the destination is a live .NET
  multistring, else the old plain-text path (offline fakes). Merge decision is still
  `conflict._merge_delta`: empty source never blanks, target-only alt untouched, equal text not
  rewritten. Read-back and DroppedItemRecord behaviour unchanged.
- Machinery search: `_copy_multistrings_ws_mapped` and flexicon's BaseOperations helper both
  write `MakeString(text, handle)` (text only); there is no "Tier A" run-preserving ITsString
  code in transfer.py/conflict.py (those hits are the update-gate tier). So a new helper was
  required. NOTE: FLExToolsMCP was not callable in this subagent session; flexicon was checked
  by grep and behaviour was verified live instead.
- models.py: binding-shape comment updated. fidelity_census.py: symbols/lines refreshed and
  HideMinorEntry/Summary (now COPIED, #114/#128) mentioned; Summary row notes ITsString copy.

## Tests and unit delta
- New tests/unit/test_issue128_entryref_postpass.py (12 tests): runs/props/embedded WS kept and
  translated per run; ws_map per run; unmapped run WS falls back to alt handle; source not
  mutated; merge writes a tss; never blanks / never removes target-only alt; idempotent second
  merge; 0-action re-run merges edited Hide+Summary; second pass 0 writes; no-op when tail
  already ran; no-op with no lexicon; never raises.
- `python -m pytest tests/unit -q`: 5396 passed / 80 skipped / 14 xfailed
  (baseline 5384/80/14 => +12 passed, no regressions).

## Live proof (FLEXLIBS_REQUIRE_LIVE=1)
Projects written: GT-Src-128 (source) and GT-Sandbox-128 (target) only, both restored via
`restore_target(name, backup_path=<repo>/backups/Target 2026-07-06 0218.fwbackup)`.
Command: `PYTHONPATH=<worktree>/src FLEXLIBS_REQUIRE_LIVE=1 python -m pytest
tests/integration/test_issue128_entryref_postpass_live.py -x -q -s` -> 1 passed (~10 s).
- Source authored: stem + complex form, ref Summary(en) with 6 runs: plain, bold, plain,
  named style "Emphasized Text", plain, embedded etu-WS run; plus an etu alternative.
- Move 1: 2 actions, 0 value drops; target Summary runs/props/WS ids == source.
- Source edited (HideMinorEntry 0->1, Summary text changed). Move 2: 0 actions (2 skips,
  already present), 0 drops; target hide=1 and edited Summary with bold/style/etu runs intact.
- Move 3: 0 actions, 0 drops, target LexEntryRef XML byte-identical (0 writes).
- Negative control: with the `_ensure_entryref_passes` call disabled, Move 2 fails with
  "HideMinorEntry edit did not land on a 0-action run" (assert 0 == 1). Call restored.

## Env check
```
D:\Github\_Projects\_LEX\GramTrans-fix-128\src\gramtrans\__init__.py D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py
```

## Risks and out-of-scope
- Idempotence/merge compare TEXT only: a source edit that changes only run formatting (same
  text) is not propagated, consistent with `_merge_delta`. Formatting on a first copy and on
  any text change is preserved.
- Other WS-bearing run props (e.g. font-feature strings) are cloned verbatim; only the two int
  WS props are remapped.
- AFFIXES-only runs now also reach C1/C2 (previously never). Intended by "any run whose scope
  includes the lexicon"; bindings are empty when neither category is in scope.
- C3 (entry-type refs) still runs only on the CREATE arm; not changed.
- #127: `_run_entryref_create_pass` NOT modified (only its callers/inputs). 
- Unrelated git status noise on main (spec-context files, csvs) untouched.

## Files touched
- src/gramtrans/Lib/transfer.py
- src/gramtrans/Lib/categories.py
- src/gramtrans/Lib/models.py
- tests/verification/fidelity_census.py
- tests/unit/test_issue128_entryref_postpass.py (new)
- tests/integration/test_issue128_entryref_postpass_live.py (new)
