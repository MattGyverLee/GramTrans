# impl-147 -- sense-list reference-decision renderer row cap (issue #147, P2)

- Branch: fix-147-sense-list-row-cap (worktree D:/Github/_Projects/_LEX/GramTrans-fix-147), based on origin/main b50b1bd
- Commit: 8555463 (Closes #147). Merged origin/main f8096a3 (docs only) as bd8047d, then pushed.
- PR: https://github.com/MattGyverLee/GramTrans/pull/153 (not merged)
- Verdict: READY FOR REVIEW. Unit suite +10 passed with 0 regressions. Live Preview gate green (2 passed).

## Root cause
`preview.render_sense_list_reference_decisions` (#116, preview.py ~2059) appended one line per distinct
(field, action, item) with no limit. A lexicon with hundreds of linked appendixes or thesaurus items
therefore produced hundreds of Preview-pane lines, most of them LINK rows (no change to the target).

## Fix (src/gramtrans/Lib/preview.py only; edits confined to the #116 block)
- New module constant `SENSE_LIST_REF_ROW_CAP = 25`. It matches `merge_preview._LIST_ITEM_LIMIT`, the
  other Preview list cap. The cap applies per action kind (create / update / link / not transferred),
  not to the section as a whole, so LINK volume can never crowd CREATE or not-transferred rows out of the pane.
- New reusable helper `_capped_rows(lines, cap, noun, indent="    ", suffix="")`. It returns at most
  `cap` lines plus, only when rows were held back, `    ... and N more <noun> not shown here (T total<suffix>)`.
  The count comes from the same sequence it slices. The wording follows `report._rows`. `report._rows`
  itself is not reused because its suffix promises "the run-report JSON artifact lists all of them",
  which is false for Preview extra lines. The helper sits next to the renderer and has no other
  callers, so #144 can pick it up.
- Create / Update / Not-transferred rows are capped by `_capped_rows`. The Not-transferred more-line
  adds `; the dropped-items list names every one`, which is true: `report.render_text_summary`'s
  "Dropped references" section is uncapped. Create and Update rows have no other complete list, so
  their more-line gives only the count.
- LINK rows: at or under the cap they are itemized exactly as before. Above the cap they collapse to
  one line per field:
  `    Link  <Field>: N items already in the target  (M senses) -- itemized list collapsed above 25 rows`
  where N is the number of distinct items and M is the union of the owning senses.
- The docstring documents the cap. `render_preview_extra_lines` and every other renderer are untouched.

### Design choice: threshold collapse instead of unconditional LINK collapse
The brief preferred collapsing every LINK row to a count. I collapse LINK rows only above the cap:
- The #116 comment above `_SENSE_LIST_REF_FIELDS` says the section exists partly so users see that
  LINKed appendixes are shared project-level objects. That information is worth keeping on small runs.
- Below the cap the output is byte-identical to before. As a result the #116 unit test
  (`test_render_itemizes_create_link_and_drop_rows`, which asserts itemized Link rows) and the shared
  live test `tests/integration/test_issue42_appendix_thesaurus_live.py:573` (which asserts
  `Link  AppendixesRC 'Appendix 42-PRESENT...`) needed no edits.
- Above the cap a per-field count says more than "the first 25 rows sorted by field". A sorted slice
  would show only AppendixesRC rows and hide that thesaurus links exist.
- Nothing disappears without a count: every held-back row is counted on a more-line or a collapsed
  count line.
- Worst-case section size: header, plus 3 x (25 + 1) for create/update/drop, plus at most 2 link
  lines, plus the footer, for at most 82 lines whatever the lexicon size. The unit test asserts 81
  because its plan has only one LINK field.

## Swept sites / consumers
- Existing cap conventions: `report._rows` / `_CONSOLE_MAX_ROWS = 20` (console only, JSON-artifact
  wording); `merge_preview._LIST_ITEM_LIMIT = 25` / `_bounded_list`; `categories.py:17024` "(+N more)".
  None of them is a Preview-extra-lines helper, so the new one is local. Other preview.py renderers
  (reversal, config-view, feature-category, TypeRA, FeaturesRS) are also uncapped but are out of
  scope here; I did not edit them because #144 and #141 are touching that area.
- Consumers: `ui/main_window._on_preview` calls `render_preview_extra_lines`, which passes the lines
  to `stats_panel.set_report(extra_lines)`, which only runs `setPlainText("\n".join(...))`. No code
  parses the lines. Tests that use the output: the #116 unit test (passes unchanged), the #42 live test
  (substring match, unchanged below the cap), and `test_preview_surfacing.py` (passes).
  gramtrans.py does not call this renderer (#145's subject).

## Tests and unit delta
- New `tests/unit/test_issue147_sense_list_row_cap.py`, 10 tests:
  - the constant is sane
  - the helper's exact counts and suffix
  - CREATE at cap+7: 25 rows, one more-line, shown + omitted = total, footer kept, size = cap+3
  - exactly cap rows: no more-line
  - drop over the cap: more-line points at the dropped-items list
  - UPDATE over the cap
  - LINK over the cap in two fields: two collapsed lines, M != N (owner union tested)
  - LINK at the cap: still itemized
  - LINK flood of cap+5 next to 2 CREATE and 1 drop: exact full output
  - 20,000-record plan: bounded line count and omitted total equals 3 x (n - cap)
- RED: with the src change stashed, the new file fails at import because `SENSE_LIST_REF_ROW_CAP`
  does not exist.
- `python -m pytest tests/unit -q` (PYTHONPATH=worktree/src):
  - with the fix: 5428 passed / 1 failed / 80 skipped / 14 xfailed
  - same tree with the change stashed: 5418 passed / 1 failed / 80 skipped / 14 xfailed
  - delta: +10 passed, 0 regressions
  - The single failure, `test_034_gate_default::test_default_gate_constructs_and_confirms_with_no_qapplication`
    ("constructing the default gate imported PyQt6"), is pre-existing and fails identically without
    my change. It is not related to preview.py.
- Baseline note: the brief's 5392 baseline is stale. origin/main b50b1bd now runs 5418 passing tests.

## Live proof (FLEXLIBS_REQUIRE_LIVE=1)
New `tests/integration/test_issue147_sense_list_row_cap_live.py`:
- Names are pinned: GT-Src-147 -> GT-Sandbox-147, both restored from `Target 2026-07-06 0218.fwbackup`.
  A write guard allows writes to GT-Src-147 only. The sandbox is a file copy and is only read.
  Both projects are restored again afterwards.
- Fixture:
  - 30 appendixes created before the fork, so they are shared (LINK).
  - 28 new DomainTypes items created after the fork (CREATE).
  - 2 appendixes created after the fork (dropped).
  - All of these spread over 10 senses of one entry.
- Run: STEMS-only Preview, no Move. Result: 2 passed in 6.7 s.
  - `test_preview_wrote_nothing`: the sandbox .fwdata bytes are unchanged.
  - The plan's `reference_decisions` hold all 30 link, 28 create and 2 report_dropped records, so the
    cap affects rendering only.
- Rendered section (31 lines, abridged):
```
  Sense appendix / thesaurus references:
    Create  ThesaurusItemsRC 'GT147 new item 27' {331271d4-...}  (1 sense)
    ... (25 Create rows total)
    Create  ThesaurusItemsRC 'GT147 new item 14' {f0e91642-...}  (1 sense)
    ... and 3 more Create rows not shown here (28 total)
    Link  AppendixesRC: 30 items already in the target  (10 senses) -- itemized list collapsed above 25 rows
    Not transferred  AppendixesRC 'GT147 source-only appendix 0' {910668d2-...}  (1 sense) -- see dropped items for the reason
    Not transferred  AppendixesRC 'GT147 source-only appendix 1' {c929bfae-...}  (1 sense) -- see dropped items for the reason
    (Later references to an item created earlier in this run show as create; Move links them.)
```
- Every count matches what was authored: 25 + 3 = 28 creates; 30 links over 10 senses; 2 drops.
- Not run: `test_issue42_appendix_thesaurus_live.py`, because it writes GT-Src-42, which is not my
  project. Its assertions are below the cap and therefore byte-identical by construction.

## Env check
```
flexicon  = D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py
gramtrans = D:\Github\_Projects\_LEX\GramTrans-fix-147\src\gramtrans\__init__.py   (PYTHONPATH=worktree/src; also printed by the live test)
```

## Risks
- Large runs no longer itemize every CREATE item. Items 26 and later are counted but not named in
  the pane, and no other surface lists the CREATE set in full. This is acceptable under never-silent,
  because the count is explicit. If the user must see every new item, a follow-up could add these
  records to the run-report JSON (#143 covers `reference_decisions` serialization).
- The more-line says "Create rows" / "Not transferred rows" (label plus "rows"), so there is no
  pluralization logic for N = 1 ("1 more Update rows").
- Merge proximity: the new constant and helper sit between `_SENSE_LIST_REF_LABELS` and the renderer.
  #144 appends to `render_preview_extra_lines` right below, which is a different hunk, so a textual
  conflict is unlikely.

## Files touched
- src/gramtrans/Lib/preview.py
- tests/unit/test_issue147_sense_list_row_cap.py (new)
- tests/integration/test_issue147_sense_list_row_cap_live.py (new)
