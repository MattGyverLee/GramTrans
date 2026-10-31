# impl-116: GitHub issue #116, Preview now shows the 030 appendix/thesaurus CREATE/LINK decisions (FR-008)

- **Branch:** `fix-116-preview-create-link`
  - Worktree: `D:/Github/_Projects/_LEX/GramTrans-fix-116`
  - Based on origin/main `c088d16`
- **Commits:**
  - `4f297a6`: the fix and the tests. Ends with `closes #116` and the Co-Authored-By line.
  - `68db9b1`: test strings only. It points the xfail reason at PR #123 and documents the `GT42_TARGET_NAME` override in the module docstring.
- **PR:** https://github.com/MattGyverLee/GramTrans/pull/123 (open, not merged)
- **Verdict:** [OK] Preview now records and renders the CREATE and LINK decisions, not just the drops. This is proven live: Preview's decisions equal Move's for every item. The new rows also exposed one pre-existing CREATE fidelity defect (section 6, item 1). It is not fixed here. I was not allowed to file it as an issue.

## 1. Change

- **`Lib/categories.py`: both resolvers now return their decisions.** `_resolve_sense_appendixes` and `_resolve_sense_thesaurus_items` return a `tuple[ReferenceDecisionRecord, ...]`, one record per source reference, in both modes. Move's call site ignores the return value.
  - The appendix resolver returns LINK when the target owns the appendix, and REPORT_DROPPED otherwise. The label is the existing `_appendix_label`. The comment that caused the bug ("Preview: present-by-GUID needs no record") is gone.
  - The thesaurus resolver returns the `decide_reference` action (CREATE/LINK/UPDATE/REPORT_DROPPED). It goes through `_reference_decision_record` when a spec exists. When there is no spec (the owning list could not be resolved) it builds a REPORT_DROPPED row directly.
  - The Preview sense loop now does `records.extend(...)` on both calls. The drop side effect is unchanged.
- **`Lib/categories.py`: new helper `_thesaurus_new_ancestors`.** It lists the ancestors a CREATE will also create. The rule matches the CREATE loop in `apply_reference`: an ancestor is skipped if it is in `resolver_cache` or already in the target list.
- **`Lib/models.py`: new field.** `ReferenceDecisionRecord.new_ancestors: tuple = ()`. It is additive. Each entry is an `(item_name, item_guid)` pair, ordered root to leaf.
- **`Lib/preview.py`: new renderer.** `render_sense_list_reference_decisions(plan)` is appended to `render_preview_extra_lines`, which `ui/main_window.py._on_preview` displays.
  - It shows one row per distinct (field, action, item), with a count of the senses that reference it.
  - CREATE rows name any new ancestors.
  - Not-transferred rows point to the dropped-items list.
- **How 024 rows render: they don't.** I checked how the 024 reference decisions render, as the task asked. `PlannedAction.reference_decisions` has no reader in any renderer, report serializer, UI or `gramtrans.py`. So "the same way 024 does" would have left the new rows invisible. The new renderer covers only the two 030 fields, because rendering the whole tuple would add one owned-object CREATE row per example or pronunciation.

## 2. Unit tests

- New file: `tests/unit/test_issue116_preview_sense_list_decisions.py`, 10 tests.
  - The appendix resolver returns LINK and drop records, identically in Preview and Move.
  - The thesaurus resolver returns CREATE with a new ancestor, CREATE under an existing ancestor, and LINK. An ancestor already in the cache is not listed. An unresolvable list gives a drop record. LINK rows are identical in Preview and Move.
  - The Preview sense loop puts the records into `_plan_entry_reference_decisions`. This is the #116 regression guard.
  - Rendering: the row format, deduplication with a sense count, filtering of other fields, and wiring into `render_preview_extra_lines`.
- Full unit suite. Before ran on a detached origin/main worktree, after ran on the branch, both with `PYTHONPATH` set to that tree's `src`:

| | passed | skipped | xfailed |
|---|---|---|---|
| before (origin/main `c088d16`) | 5294 | 80 | 14 |
| after (`4f297a6`) | 5304 | 80 | 14 |

The delta is +10: the 10 new tests. There are no regressions.

## 3. Live proof (`FLEXLIBS_REQUIRE_LIVE=1`)

- **Driver:** `tests/integration/test_issue42_appendix_thesaurus_live.py`, extended. The target is now `os.environ.get("GT42_TARGET_NAME", "GT-Sandbox-42")`, so the default is unchanged.
- **Run:**
  ```
  set FLEXLIBS_REQUIRE_LIVE=1, GT42_TARGET_NAME=GT-Sandbox-116, PYTHONPATH=<worktree>/src
  python -m pytest tests/integration/test_issue42_appendix_thesaurus_live.py -v -s
  ```
- **Resolved modules (printed in the log):**
  - `[LIVE] gramtrans=D:\Github\_Projects\_LEX\GramTrans-fix-116\src\gramtrans\__init__.py`
  - `[LIVE] flexicon=D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py`
  - `[LIVE] source=GT-Src-42 target=GT-Sandbox-116`
- **Result:** **8 passed, 1 xfailed.** That is the 6 original #42 tests plus 2 new ones, and 1 new strict xfail (section 6, item 1). Final log: `C:\Users\thoua\AppData\Local\Temp\claude\d--Github--Projects--LEX-GramTrans\9f84e243-5237-484f-a4c9-1d675dd0f416\scratchpad\live_final.log`. An earlier green run's log, `live_green.log`, holds the full printed decision rows.

### What the new tests check

How Move's decisions were captured: the two resolvers were wrapped for the duration of each Move, and the records returned in Move mode (`new_sense` set) were collected. This only observes; Move still discards them.

`test_preview_create_link_decisions_match_move` checks five things:

1. **Preview shows exactly the rows the issue asks for**, as (owner, field, action, item, new_ancestors):
   - s1: `AP link A-PRESENT`, `AP report_dropped A-ABSENT`, `TH create C (+P)`
   - s2: `AP link A-PRESENT`, `TH create C (+P)`, `TH create C2`, `TH link E`, `TH create D`
2. **Item level:** Preview and Move reach the same decision for every item. For each (field, item), the first decision and its ancestors are identical.
3. **Row level:** Preview and Move cover the same (owner, field, item) sequence. The only difference allowed is a Preview CREATE where Move LINKs an item it created earlier in the same run. Live, that difference is exactly one row: (s2, C). Preview says `create`; Move says `link`, because its resolver cache already holds the C it created for s1. Both create one C.
4. **Ground truth:**
   - Preview's CREATE items plus their new ancestors are `{P, C, C2, D}`.
   - Each of these was absent before Move 1 and present after it, in an independent read-only reopen.
   - The LINK targets E and A-PRESENT existed before Move 1 and are now on the senses.
5. **Move 2:** for s3, Preview's rows equal Move 2's rows exactly.
   - A-PRESENT is LINK.
   - C and D are neither CREATE nor drop.

`test_preview_pane_renders_create_and_link_rows` checks the live pane text:

```
    Create  ThesaurusItemsRC 'GT42 semdom child' {524cfcdc-e8b1-4bda-b03d-d3da086fa125}  (1 sense)
    Create  ThesaurusItemsRC 'GT42 child' {b310df5c-...}  (2 senses) -- also creates ancestor(s) 'GT42 parent' {fc04b728-...}
    Create  ThesaurusItemsRC 'GT42 child of existing' {cc2874a8-...}  (1 sense)
    Link  AppendixesRC 'Appendix 42-PRESENT: shared appendix linked by GUID in both...' {71a71deb-...}  (2 senses)
    Link  ThesaurusItemsRC 'anatomy' {b0add746-...}  (1 sense)
    Not transferred  AppendixesRC 'Appendix 42-ABSENT: only the source owns this one so it must...' {83a21590-...}  (1 sense) -- see dropped items for the reason
```

### Mutation check (not committed)

- **Mutation:** I reverted only the two `records.extend(...)` lines in the Preview loop to bare calls. That is the pre-fix behaviour.
- **Live result:** 2 failed, 6 passed, 1 xfailed. The two failures were `test_preview_create_link_decisions_match_move` ("Preview recorded no 030 decisions (issue #116 regression)") and `test_preview_pane_renders_create_and_link_rows`.
- **The old test cannot see the defect.** The old drop-only test `test_preview_writes_nothing_and_drops_match_move` still PASSED under the mutation.
- **Unit result:** the new unit test `test_preview_sense_loop_folds_030_decisions_into_reference_decisions` also failed.
- **Revert:** `git checkout -- src/gramtrans/Lib/categories.py`. The tree was clean afterwards, and the re-run was green (8 passed, 1 xfailed).
- **Log:** `C:\Users\thoua\AppData\Local\Temp\claude\d--Github--Projects--LEX-GramTrans\9f84e243-5237-484f-a4c9-1d675dd0f416\scratchpad\live_mutation.log`

### Project hygiene

- **Writes:** `GT-Sandbox-116` only. The test restores it from `Target 2026-07-06 0218.fwbackup` at the start and the end of the run. One extra diagnostic probe ran on it too (section 6, item 1); that probe restored it before and after.
- **GT-Src-42: my assignment called it READ-ONLY, but the #42 test writes to it by design.** The test builds the fixture inside it ("author-then-fork") and restores it at the end. The project as found contained no fixture: it was the post-restore state of the earlier #42 run. I resolved the conflict like this:
  - `.fwdata` SHA-256 before the runs: `13c5a96fba560ae86b29893798f5bcf1cd0d631d19d36f50bef9a1ecfad74c7f`.
  - `.fwdata` SHA-256 after the final run's restore: the same `13c5a96f...74c7f`.
  - The `.bak` differed after the restore. So I copied back the full-directory snapshot I took before the runs. `diff -r` shows the directory is now byte-identical to its pre-run state.
- **GT-Sandbox-42:** not touched. Its mtime is still 17:03 and its SHA is unchanged.
- **Other projects:** none were opened. No MCP `run_module` was used.

## 4. Pattern audit (sweep-pattern / Explore)

The full list is in the PR body. The main points:

- **[HIGH] Sub-senses never run the 030 resolvers or the 029 picture seam, in either mode.**
  - Move: `owned.py:747` / `:494`. Preview: `owned.py:1035` / `:960`.
  - A sub-sense's AppendixesRC, ThesaurusItemsRC and PicturesOS are therefore lost with **no** `DroppedItemRecord`.
  - This is a never-silent violation and needs its own issue.
- **[HIGH] `preview.py:1495`:** `plan_all_lexical_relations(...)` is called as a bare statement and its CREATE records are discarded. This is the same shape as #116, for LexReference.
- **[MED] Other computed decisions are never shown:**
  - the planned new LexRefType (`categories.py:7688`);
  - the process-rule `_plan_script` (`categories.py:6755`, marked deliberate);
  - all the 024, owned-child, picture, entry-ref-type and allomorph rows in `PlannedAction.reference_decisions` (never rendered or serialized);
  - `ReversalDecision.pos_decision`;
  - the decisions inside `text_plans`;
  - the FlexTools-module Preview paths, `gramtrans.py:390` and `:546`, never call `render_preview_extra_lines`, so the new rows show only through `ui/main_window.py`.
- **[MED] The Preview resolver cache is never primed.**
  - Preview reports a second reference to an item it plans to create as CREATE again, while Move LINKs it.
  - This affects every `_decide_reference_fields` caller and `owned._plan_child_ref_decisions`. It is [HIGH] for `pictures.py:770`, where the dedup set is per sense while Move's asset cache covers the whole run.
  - Within #116 it also means two new items under the same not-yet-created ancestor will each name that ancestor. The renderer's per-item deduplication hides the repeated CREATE for a shared item. The live test documents the one row where Preview and Move differ for this reason, instead of priming the cache in Preview. Priming it would be a 024-wide change, outside this lane.

## 5. Files

- `src/gramtrans/Lib/categories.py`, `src/gramtrans/Lib/models.py`, `src/gramtrans/Lib/preview.py`
- `tests/unit/test_issue116_preview_sense_list_decisions.py` (new)
- `tests/integration/test_issue42_appendix_thesaurus_live.py` (extended)

## 6. Residual risks and follow-ups

1. **Found pre-existing defect, live: items a run creates are judged "diverged" on the next run. NOT FILED; the `gh issue create` call was denied by permission.**
   - What happens:
     - Move 2 decides **UPDATE**, not LINK, for C and D, which Move 1 had just created from the same source.
     - Move 1 logs `Transaction 'Apply syncable properties': exception TypeError` four times, once per CREATE, with no drop record.
   - Probed live on GT-Sandbox-116 (restored afterwards):
     - `references.apply_reference`'s CREATE arm builds `create_props[f] = field_props if field_props else _best_text(field_ms)`.
     - For an empty source `Description` that is a plain `""`.
     - `BaseOperations._apply_props_loop` then does `setattr(item, "Description", "")` and raises `TypeError: property is read-only`.
     - The CREATE arm's `except (AttributeError, TypeError): pass` swallows it.
     - Results: `{"Description": ""}` and `{"Name": "plain"}` raise; dict-shaped values work.
     - Name and Abbreviation survive only because they come first in `_FINGERPRINT_FIELDS`.
   - Not confirmed: that this TypeError is what causes the UPDATE. `apply_residue` is another candidate.
   - Pinned by the strict xfail `test_items_created_by_move1_link_on_the_next_run`, which should flip to passing when this is fixed.
   - It is a write-path defect, so the fix needs the full crew cycle.
   - The issue text is drafted in the PR body. **Please file it.**
2. **Sub-sense 030/029 silent loss** (pattern audit, HIGH). Needs an issue.
3. **Lexical-relation CREATE records discarded in Preview** (`preview.py:1495`, HIGH). Needs an issue.
4. **024 `reference_decisions` rows are never rendered.** Rendering them needs a design decision, for example possibility-list CREATEs only, to keep the pane bounded.
5. **Live-test design caveat.** Move's decisions are captured by wrapping the module-level resolvers during each Move. This works because Move looks the functions up by global name in `categories`. If that call ever becomes a bound alias, the capture would return empty lists. The checks would then fail (item-level equality, and the s3 row equality in check 5) rather than pass vacuously.
6. **This run was STEMS-only on the constructed fixture.** No real project populates these fields (0 of 79 on record, per #42).
