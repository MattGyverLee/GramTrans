# cycle2 programmer: planned-link render

Branch `fix-146-planned-link-render`, worktree D:/Github/_Projects/_LEX/GramTrans-fix-146-render. Local only, not pushed.
- Base origin/main 91faad5
- Merge f045f01 (fix-146-preview-cache-picture-dedup @1888dee, --no-ff)
- Render commit 24f85b2

## Merge conflicts with fix-146
None. The merge was clean (12 files, auto-merged).

## Constants (src/gramtrans/Lib/preview.py, module level)
- PLANNED_LINK_ROW_SUFFIX = " -- links to the item created above in this run"
- SENSE_LIST_LINK_EXISTING_LINE = "    {label}  {field}: {n} item{n_s} already in the target  ({m} sense{m_s})"
- SENSE_LIST_LINK_PLANNED_LINE = "    {label}  {field}: {n} item{n_s} created by this run, linked from later references  ({m} sense{m_s})"
- REVERSAL_TEXT_NEW_IN_RUN_NOTE = "    (New in this run: created once, and the other references link to it.)"

## Behaviour
- #147 itemized: a planned Link row (any decision for that GUID has planned=True) gets the suffix.
- #147 collapse: split per field into existing and planned lines. N excludes planned items. A line is omitted when its count is 0. The trigger is still more than 25 total Link rows.
- #147: the stale "Later references ... show as create" note is removed, and the docstring is updated.
- #144: the "Created once" note is replaced. The new note fires when a Create row has a planned Link row for the same GUID.
- Cap value (25) and the "+N more" format are untouched.

## Deviations and judgment calls (please review)
1. **Dropped suffix.** The collapse lines no longer carry " -- itemized list collapsed above 25 rows". The approved wording has no suffix, so I followed it exactly. The old suffix is gone from the 147 unit tests and the live test.
2. **First line omitted when N == 0.** The brief only said to omit the second line when K == 0. I also omit the existing-items line when N == 0, to avoid "0 items already in the target". Easy to revert.
3. **No single-owner variant of the #144 note.** A Create row with planned Links always has at least 2 owners. A "created once" variant without "the other references link to it" would therefore be unreachable, so I did not add a dead constant. The note shows only when planned Links exist.
4. **#144 planned Link rows get the itemized suffix too.** This is not explicitly approved. Without it, #144's planned Link row would read like an existing-item link, the same lie the ruling fixes. The row is `Link  'Noun' {p-new}  (1 reversal entry) -- links to the item created above in this run`. It is a one-line revert.

## Before and after
Before: the "before" text is derived from the old code paths, not a captured run.

Sense list (26 existing links, 3 planned links, 1 Create), BEFORE (a planned link was counted as existing):
```
  Sense appendix / thesaurus references:
    Create  ThesaurusItemsRC 'n0' {n0}  (1 sense)
    Link  ThesaurusItemsRC: 29 items already in the target  (4 senses) -- itemized list collapsed above 25 rows
    (Later references to an item created earlier in this run show as create; Move links them.)
```
AFTER (real output):
```
  Sense appendix / thesaurus references:
    Create  ThesaurusItemsRC 'n0' {n0}  (1 sense)
    Link  ThesaurusItemsRC: 26 items already in the target  (3 senses)
    Link  ThesaurusItemsRC: 3 items created by this run, linked from later references  (2 senses)
```

Reversal (Create plus one planned Link, same GUID). BEFORE (the "Created once" note never fired, because count was 1):
```
  Reversal categories (each reversal index's own category list):
    Create  'Noun' {p-new}  (1 reversal entry)
    Link  'Noun' {p-new}  (1 reversal entry)
```
AFTER (real output):
```
  Reversal categories (each reversal index's own category list):
    Create  'Noun' {p-new}  (1 reversal entry)
    Link  'Noun' {p-new}  (1 reversal entry) -- links to the item created above in this run
    (New in this run: created once, and the other references link to it.)
```

## Tests
- Copied tests/unit/test_integ_141_147_planned_link_render.py from integ-141-147. It now imports the constants.
- Added 3 negative controls:
  - an existing Link has no planned label;
  - K == 0 omits the second collapse line;
  - the collapse N excludes planned items.
- #144 `test_reversal_pos_recurses_sub_entries_and_aggregates` now builds the real shape (CREATE plus planned LINKs). Added 2 more #144 negative controls: a Create without planned Links shows no note, and an existing Link shows no label or note.
- Updated the stale wording asserted in the 116, 147 unit, and 147 live tests (the live test is not run).
- Full unit suite, excluding test_034_gate_default: **5479 passed, 80 skipped, 14 xfailed, 0 failed.**
