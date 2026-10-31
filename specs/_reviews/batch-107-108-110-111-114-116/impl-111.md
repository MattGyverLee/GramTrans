# impl-111: GitHub issue #111, MSA->slot wiring reported LINKED without reading `SlotsRC` back

- Branch: `fix-111-slotsrc-readback` (worktree `D:/Github/_Projects/_LEX/GramTrans-fix-111`, based on origin/main c088d16)
- Commits: `a95f4cd` (the read-back fix) and `8394e4a` (WRITE_FAILED also emits a Skip per unwritten slot, matching SLOT_MISSING). Both say `closes #111`.
- PR: https://github.com/MattGyverLee/GramTrans/pull/120 (not merged)
- Verdict: [OK] Fixed. Unit tests are green (+12, 0 regressions). The live #31 gate passes against `GT-Sandbox-111`: 128/128 LINKED with 128 pairs present. The live mutation check now reports `WRITE_FAILED 128` instead of `LINKED 128`.

## 1. Defect and trace

- **No-op Add (the reported defect).** `categories._run_171_subpass` emitted `AffixSlotLinkRecord(LINKED)` once every referenced slot *resolved* in the target. Nothing read `IMoInflAffMsa.SlotsRC` back afterwards. A `SlotsRC.Add` that did nothing was therefore reported as success. The pre-fix unit run confirms this: with a no-op Add, the outcome is `LINKED`.
- **Raising Add (traced, previously untraced).** No exception handler sat around the Add, so a raise escaped the whole pass. What happened next depended on how the pass had been reached:
  - *Template-tail path.* The pass is reached through `_run_tail_once` from `affix_templates_execute_action`. The raise reached the leaf-dispatch `except Exception` in `transfer.py` and was recorded as a `LeafExecutionFailure` against the **last affix template**, an object that had actually been written. Every MSA after the raising one got no record, so SC-003's denominator shrank silently. `_wire_msa_infl_feats` and `_wire_prod_restrictions` did not run. The safety net could not retry either, because `_did_171_subpass` had already been latched.
  - *Safety-net path.* The pass is reached through `transfer._ensure_171_subpass`, which uses `except Exception: _log.exception(...); return`. The failure appeared only as a log line, with nothing in the run report. The pre-fix unit run shows this path: "17.1 sub-pass safety net FAILED (swallowed)".

## 2. Fix

`src/gramtrans/Lib/categories.py` (`_run_171_subpass`, plus the new helper `_slots_absent_on_readback`):
- The pre-Add membership check and the `SlotsRC.Add` sit in a per-slot `try`. A raise is collected on that MSA as `"<Type>: <msg>"`, and the pass continues to the next slot and the next MSA.
- After the slot loop, `SlotsRC` is read back once. A resolved slot that is absent (checked by identity or GUID) is unwritten.
- If the read-back itself raises, every resolved slot counts as unwritten. The read-back has verified nothing, so the MSA is never LINKED (the #101 rule).
- **Outcome precedence:** `WRITE_FAILED` > `SLOT_MISSING` > `LINKED`. There is still exactly one record per MSA. Each `WRITE_FAILED` also logs a `log.warning`.
- **Skips:** each unwritten slot also adds a `Skip(DEPENDENCY_UNRESOLVED)`, the same as `SLOT_MISSING` does, so the run's skip counters move and not only the FR-019 panel. The detail says the slot "resolved in target but is not in SlotsRC on read-back". A clean run gets no extra skips.

`src/gramtrans/Lib/models.py`:
- New `AffixSlotLinkOutcome.WRITE_FAILED`.
- New `AffixSlotLinkRecord` fields: `unwritten_slot_guids` and `detail`.
- Invariants: a `WRITE_FAILED` record must name its unwritten slots, and no other outcome may carry them. `WRITE_FAILED` may also carry `unresolved_slot_guids`, because one MSA can lose columns both ways at once.

`src/gramtrans/Lib/report.py`:
- `_affix_slot_link_block` lists `WRITE_FAILED` records in `failures`, adding the `unwritten_slot_guids` and `detail` keys.
- The console panel renders them as `[NOT LINKED] affix X: template column(s) ... are in the destination but not in its inflectional MSA ...'s slots after the write (<detail>)`.
- `linked_of_attempted` drops automatically.

The model followed is #101/#22's UPDATE read-back, which reads the target after the write, treats a value missing on read-back as not written, and reports it.

## 3. Tests

**Unit**
- New file `tests/unit/test_issue111_slotsrc_readback.py`, 12 tests. It covers:
  - the record invariants (3 tests);
  - a no-op Add, which gives `WRITE_FAILED` and appears in both the artifact and the console;
  - a raising Add, which is reported with its reason, while the next MSA is still LINKED;
  - a raising Add through `transfer._ensure_171_subpass`, which is no longer swallowed;
  - a raising read-back, which is not LINKED;
  - the unresolved + unwritten case, which gives one `WRITE_FAILED` record;
  - the unchanged happy path and idempotent path.
- **7 of the 12 fail on the pre-fix `categories.py`.** I checked this by stashing the fix and running the file.
- Full unit suite (`PYTHONPATH=<worktree>/src python -m pytest tests/unit`):

| | Passed | Skipped | xfailed | Failed |
|---|---|---|---|---|
| Before (origin/main c088d16) | 5294 | 80 | 14 | 0 |
| After | 5306 | 80 | 14 | 0 |

- The existing 17.1 suites (`test_038_affix_slot_links`, `test_categories_affix_templates`, `test_phase3c_post_pass_a`, `test_033_*`) are unchanged and pass. Their fakes append on `Add`, so the read-back finds the slots.

**Live test edit** (`tests/integration/test_issue31_msa_slot_live.py`, 2 lines): the target name now comes from `GT_ISSUE31_SANDBOX`, defaulting to `GT-Sandbox-31`. The guard changed from `== "GT-Sandbox-31"` to `startswith("GT-Sandbox-")`. Nothing else in the file changed, which keeps the merge with #107's addition easy.

## 4. Live verification (`FLEXLIBS_REQUIRE_LIVE=1`)

- Environment: `PYTHONPATH` set to the worktree `src`. `gramtrans` resolved to `GramTrans-fix-111\src\gramtrans\__init__.py`, and flexicon to `D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py`. Both are printed in the log.
- Source: `Ngoreme`, opened READ-ONLY. Its `.fwdata` SHA-256 was `6d35c9575fc6094089dff757da4f54f266aa5a0d7e4ea16cd1fd3bd64abe472d` before the first run, inside every run, and after the last run. It never changed.
- Target: `GT-Sandbox-111` is the only project written. The fixture restores it from `Target 2026-07-06 0218.fwbackup` at module start on each run.
- No other project was opened. I opened no project through FLExToolsMCP.

| Run | Link outcomes, Move 1 / Move 2 | Target pairs, baseline / post1 / post2 | Result |
|---|---|---|---|
| Clean | LINKED 128 / LINKED 128 | 0 / 128 / 128 | 7 passed |
| Mutation: `SlotsRC.Add` -> `pass` | **WRITE_FAILED 128 / WRITE_FAILED 128** | 0 / 0 / 0 | 3 failed, 4 passed |
| Clean, after the revert | LINKED 128 / LINKED 128 | 0 / 128 / 128 | 7 passed |
| After `8394e4a`: mutation again | WRITE_FAILED 128 / WRITE_FAILED 128 | 0 / 0 / 0 | 3 failed, 4 passed |
| After `8394e4a`: clean (final) | LINKED 128 / LINKED 128 | 0 / 128 / 128 | 7 passed |

- In the mutation run, `test_move1_report_is_all_linked` failed with `assert Counter({'WRITE_FAILED': 128}) == Counter({'LINKED': 128})`.
- The mutation log has 256 `"... resolved in the destination but are not in SlotsRC on read-back"` warnings, 128 per move.
- Before the fix, the same mutation produced `LINKED 128` (from the #31 report).
- The mutation was reverted by copying back a pre-mutation backup of the file. `grep MUTATION` finds 0 hits, and the committed diff contains no mutation.
- The live test does not render the console text summary, so the `[NOT LINKED]` rendering is proven by unit tests only. Live proof covers the `RunReport.affix_slot_links` records that the panel renders from.

Logs (scratchpad, not committed), all in `C:\Users\thoua\AppData\Local\Temp\claude\d--Github--Projects--LEX-GramTrans\9f84e243-5237-484f-a4c9-1d675dd0f416\scratchpad\`:
- `live_111_clean.log`
- `live_111_mutation.log`
- `live_111_clean2.log`
- `live_111_mutation2.log`
- `live_111_clean3.log` (the final run, on `8394e4a`)
- `unit_before_111.txt`
- `unit_after_111.txt`

## 5. Pattern audit (sweep-pattern via Explore; full list in the PR body)

None of these siblings is fixed here. Each needs its own report channel and its own live proof.
- **Closest sibling [HIGH]:** `transfer.py:~4204`, in `_execute_overwrite` (the OVERWRITE path).
  - It runs `SlotsRC.Clear()`, then `SlotsRC.Add` for each source slot, then reports Info "overwritten".
  - It has no read-back, and an unresolved slot is dropped silently.
  - No `try` surrounds it.
  - Because of the `Clear()`, a write that does not land *removes* membership the target already had.
- **[HIGH] Other passes with the same shape (no read-back; a raise is swallowed or blamed on another action):**
  - the complex-feature `TypeRA` tail (`categories.py:~2115`);
  - `_wire_matched_nc_segments` `SegmentsRC.Add` (`~14957`);
  - post-pass A, the `ComponentLexemesRS`/`PrimaryLexemesRS` Adds (`~12249`);
  - the InflectableFeats link pass (`~12416`);
  - the POS `InflectableFeatsRC` / `ExceptionFeaturesOC` Adds (`~3346` / `~3665`);
  - `_add_reference_collection_member` (`transfer.py:~3074`);
  - `_apply_reference_fields` (`~6590`);
  - the `_get_or_create_feat_struc` setattr (`~11679`).
- **[HIGH] Silent `RA`/`RS` writes behind `except ...: pass`, which leave no record:**
  - `_wire_stratum`;
  - the adhoc-rule and compound-rule references;
  - `LexReference.TargetsRS`;
  - `AppendixesRC` / `ThesaurusItemsRC`;
  - the template slot sequences;
  - the phon-rule constraint and stratum references;
  - `FeaturesRS`.
- **[MED] Raises are recorded, but a no-op write would still read as success.** The list is in the PR.
- **[MED, structural]** Inside `_run_171_subpass`, `_wire_msa_infl_feats` and `_wire_prod_restrictions` still have no per-item guard. A raise from either still reaches the log-only `_ensure_171_subpass` handler.
- **Follow-up:** all four `_ensure_*` safety nets in `transfer.py` (~208, 257, 317, 356) log and swallow, with no Skip, no `LeafExecutionFailure`, no Warning, and no retry.
- **Cleared:** the UPDATE path (`apply_update_semantic`, from #22/#101).

## 6. Residual risks and follow-ups
1. **File follow-up issues.**
   - The OVERWRITE `SlotsRC` path (highest priority, because of the `Clear()` data-loss direction).
   - Make the `_ensure_*` safety nets record a `LeafExecutionFailure` instead of only logging.
   - The tail passes (post-pass A, InflectableFeats, TypeRA, NC segments), which need per-item guards and read-back.
2. **`detail` is dropped when the read-back succeeds.** If an Add raises but the slot is present on read-back, the MSA is LINKED, and the error is not recorded. Read-back is treated as the source of truth. Arguably the error deserves a log line; today it has none.
3. **Crew cycle not run.** This is a write-path change, and the protocol's crew cycle (lex-lead/QC) was not run by this agent. The main session should decide whether lex-qc reviews PR #120 before merge.
4. **Sandbox left in post-run state.** `GT-Sandbox-111` holds the state left by the final clean run (128 pairs), so it can be inspected.
