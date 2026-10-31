# impl-144 -- Preview renders reversal-entry category + text genre/tag decisions (issue #144, P2)

- Branch: fix-144-preview-pos-text-decisions (worktree D:/Github/_Projects/_LEX/GramTrans-fix-144), based on origin/main b50b1bd
- Commit: 57474d7 (Closes #144); origin/main (f8096a3, docs-only) merged as 04c2998; pushed
- PR: https://github.com/MattGyverLee/GramTrans/pull/159 (not merged)
- Verdict: READY FOR REVIEW. Unit suite green (+13), live gate green (6 passed). One adjacent defect found and NOT fixed
  (text genres are silently never transferred -- see Follow-ups); the follow-up issue could NOT be filed from this session
  (`gh issue create` was denied by the permission classifier) -- draft text is below.

## Ground truth: what Move does (read code, then confirmed live before writing any renderer)
- Reversal `pos_decision`: built by `reversals._decide_reversal_category` -> `references.decide_reference` against the
  reversal INDEX's own `PartsOfSpeechOA` (not LangProject POS). Move recomputes the same walk
  (`categories.reproduce_reversal_entries`) and `_apply_pos_decision` runs `apply_reference` with a spec closed over
  `target_index.PartsOfSpeechOA`: CREATE (+ancestors, GUID-preserving, once per run via the shared cache) / UPDATE / LINK set
  `PartOfSpeechRA`; REPORT_DROPPED writes nothing (drop already in `dropped_items`); `None` = source entry has no category,
  nothing written.
- Segment tags: `_decide_segment_tags` -> CREATE/LINK/REPORT_DROPPED against `TextMarkupTagsOA`. Move
  (`_apply_segment_tags`) skips REPORT_DROPPED, otherwise resolves/creates the possibility and creates an `ITextTag` -- BUT only
  inside paragraphs Move creates: `_apply_paragraphs` returns early for a target text that already has paragraphs, so a
  matched (UPDATE) text gets no tags.
- Genres: `_decide_genres` / `_apply_genres`. Live, the plan carries NO genre decision (see Follow-ups), so Move writes none.

## Fix (src/gramtrans/Lib/preview.py only, additive)
- New `render_reversal_and_text_decisions(plan)` + private helpers `_ref_decision_rows`, `_render_ref_decision_section`,
  `_iter_reversal_pos_decisions`, constants `_REF_DECISION_ROW_CAP = 25`, `_REF_DECISION_LABELS`.
- Three sections: "Reversal categories (each reversal index's own category list)" (recurses `sub_entry_decisions`, skips
  `pos_decision is None`), "Text genres" (per text), "Text markup tags" (per tag). Rows aggregated per (action, item GUID):
  `Create / Update / Link / Not transferred  '<name>' {<guid>}  (<n> <owners>)` -- same vocabulary/order as the #116 renderer.
  Name/GUID from `source_item` (a CREATE has no `target_item`); CREATE row names the ancestor chain
  ("-- under 'X' (created too if absent)"); Not-transferred rows point at dropped items.
- Notes that keep Preview == Move: "(Created once; the other references link to it.)" when a CREATE row counts >1 owner (Preview's
  cache is not populated by CREATE; Move's is); and for any UPDATE text that has tag decisions: "(N text(s) already in the target:
  tags are added only if the target text has no paragraphs yet; Move leaves an existing text's structure as-is.)".
- Cap: 25 rows per section, then "+N more" (own helper; #147 renderer untouched).
- `render_preview_extra_lines`: ONE appended line `+ tuple(render_reversal_and_text_decisions(plan))`; docstring and the
  other renderers untouched. gramtrans.py untouched (#145 wires the seam).

### Swept sites (RunPlan / decision fields computed but never rendered in Preview)
Fixed here: `ReversalDecision.pos_decision`, `TextTransferPlan.genre_decisions`, `SegmentPlan.tag_decisions`.
Follow-ups (not the same trivial shape, or owned elsewhere):
1. `TextTransferPlan` itself: disposition (ADD/UPDATE), title, paragraph/segment counts -- no per-text Preview line at all (texts
   appear only in the post-Move report counts). Medium.
2. `AnalysisPlan.category_decision` / `MorphBundlePlan` decisions under `SegmentPlan.analyses` (wordform analyses' CategoryRA,
   morph refs) -- not rendered. Medium.
3. `SegmentPlan.notes`: Move reports every note as a DroppedItemRecord at APPLY time (`_apply_segment_notes`); Preview never shows
   that loss -- a Preview/Move asymmetry in `dropped_items`. Small, but a texts.py change.
4. `RunPlan.msa_slot_bindings`, `msa_infl_feat_bindings`, `msa_feat_struc_bindings`, `lexentry_ref_bindings`,
   `entryref_create_bindings`: consumed by Move (categories.py / transfer.py), not rendered. Possibly overlapping #141/#142
   (lexical relations / entry refs) -- left alone.
5. `RunPlan.conflicts`: no consumer anywhere in src (dead field?).
OUT of scope as instructed: #143 (`PlannedAction.reference_decisions`).

## Follow-ups (found live, NOT fixed): text genres silently never transferred -- issue NOT filed (permission denied)
Draft issue title: "Text genres silently never transferred: GetGenre raises live, and _apply_genres setattr's a reference collection".
1. Decide side: `texts._decide_genres` calls `source.Texts.GetGenre(text)`; live it raises
   `AttributeError: 'ILcmReferenceCollection[ICmPossibility]' object has no attribute 'FirstOrDefault'` for every text that HAS a
   genre (flexicon `TextOperations.GetGenre` uses a LINQ extension pythonnet does not expose). Swallowed -> `genre_decisions == ()`,
   no DroppedItemRecord. `Texts.GetGenres(text)` works live (and returns all genres; GetGenre was first-only anyway).
2. Apply side: `_apply_genres` passes `owner_obj=target_text` to `apply_reference`, whose LINK/CREATE/UPDATE arms
   `setattr(owner_obj, "GenresRC", item)` -- a reference COLLECTION; fails, swallowed by `_safe`. Fixing (1) alone would make
   Preview say "Create/Link genre" while Move creates the possibility and links it to no text. Model: categories'
   collection pattern (owner_obj=None, then `coll.Add` if absent).
3. `tests/unit/_fakes_texts.FakeTextOps.GetGenre` returns a list -- a shape the real API lacks, which hid (1) offline.
Live evidence: source texts A (source-only genre) and B (shared genre) -> `genre_decisions == ()`; after Move both target texts'
`GenresRC` empty, source-only genre absent from the target `GenreListOA`, no drop reported. Possibly also a flexicon issue for
`TextOperations.GetGenre`. Once fixed, #144's renderer needs no change (it already renders `genre_decisions`), and the live
test's genre check is written as Preview==Move AGREEMENT, so it keeps holding.

## Tests and unit delta
- New tests/unit/test_issue144_preview_pos_text_decisions.py (13): empty plan -> (); no-category reversal entries -> no row
  (negative control); pos Create/Update/Link/Not-transferred + order; sub-entry recursion + aggregation + "created once" note;
  ancestor chain; genre Create/Link with text counts; no genre/tags -> (); tag Create/Link/Not-transferred; UPDATE-text note;
  section order; 25-row cap + "+7 more"; lines present in `render_preview_extra_lines`; `texts.plan_texts` (fakes) -> render.
- No shared test file edited; no existing test broke.
- `python -m pytest tests/unit -q` (PYTHONPATH=worktree src): 5432 passed / 80 skipped / 14 xfailed.
  Baseline measured on this worktree at b50b1bd (== origin/main at start): 5419 / 80 / 14 -- NOT the 5392 in the brief (main had
  moved since that number). Delta: +13 passed (exactly the new file), skipped/xfailed unchanged, 0 failed.
- ruff: no new finding class in preview.py beyond the file's existing `List`/`Tuple` (UP006) style; new test files match the
  #136 live test's style (UP031 % formatting).

## Live proof (FLEXLIBS_REQUIRE_LIVE=1; wrote ONLY GT-Src-144 and GT-Sandbox-144, both restored from
`Target 2026-07-06 0218.fwbackup` and restored again in teardown; write guard asserts the names)
tests/integration/test_issue144_pos_text_decisions_live.py: 6 passed in 12.6s.
Fixture (authored via flexicon/LCM in GT-Src-144): shared reversal category forked into the sandbox; then source-only reversal
category "GT144 new revpos", entry gtfixonefortyfour + sense with reversal entries A (new category), B (shared category),
C (no category); source-only genre + source-only markup tag (under 'Syntax-Descriptive'); texts A (new genre; new + shared tag),
B (shared genre), C (nothing). Selection: STEMS + TEXTS (text_picks = A,B,C).
- Run 1 Preview lines (target unchanged by Preview -- fwdata bytes identical):
  ```
    Reversal categories (each reversal index's own category list):
      Create  'GT144 new revpos' {8d285d12-...}  (1 reversal entry)
      Link  'GT144 shared revpos' {a976ac46-...}  (1 reversal entry)
    Text markup tags:
      Create  'GT144 new tag' {2ff6d519-...}  (1 tag) -- under 'Syntax-Descriptive' (created too if absent)
      Link  'Adjective Phrase' {c234cae2-...}  (1 tag)
  ```
  After Move: target index has new_pos (source GUID) + shared_pos; entries revA->new_pos, revB->shared_pos, revC->None
  (negative control: no row, no category); new tag in target `TextMarkupTagsOA`; text A tags == {new_tag, shared_tag};
  texts B, C no tags (negative control). Genres: no Preview row and no genre on any target text (agreement; see Follow-ups).
- Run 2: Preview has no reversal rows (`reversal_decisions == ()` -- entry/sense already present, nothing in copy set; no
  re-add), tags show Link/Link + the "1 text already in the target ... structure as-is" note; Move changes nothing: post-state
  identical to run 1 (idempotent; tag count still 2).
- Before/after: the same fixture on pre-fix code (scratch ground-truth run) rendered only the reversal "Add entry" lines and
  the config-view line via `render_preview_extra_lines` -- none of the category/tag rows above.
- Note: pytest's faulthandler prints "Windows fatal exception: access violation" during `FLExInitialize` (handled SEH in
  pythonnet init, same as other live tests); all 6 tests pass.

## Env check
```
python -c "import flexicon; print(flexicon.__file__)"  -> D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py
(PYTHONPATH=worktree/src) gramtrans.__file__           -> D:\Github\_Projects\_LEX\GramTrans-fix-144\src\gramtrans\__init__.py
live run [LIVE] line: gramtrans=D:\Github\_Projects\_LEX\GramTrans-fix-144\src\gramtrans\__init__.py
                      flexicon=D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py
```
WARNING: without PYTHONPATH, `import gramtrans` resolves to the MAIN checkout (D:\Github\_Projects\_LEX\GramTrans\src) -- an
editable install there. All runs above set PYTHONPATH to the worktree's src.

## Shared-stash incident (disclosed)
Before the coordinator's warning arrived I ran one `git stash` / `git stash pop` pair ~1s apart (02:33:17) to compare ruff
counts. Verified afterwards that it did not touch anyone else's work: my stash commit 57982dbe holds only my preview.py
change (+134), and the tree after the pop held only my hunks (no #146 files), so the pop applied my own entry. Branch check:
`git diff origin/main --stat` = preview.py +134, the two new test files; nothing else. The stash list is now EMPTY; #146's
stashes are dangling and recoverable: latest is 2a68c8cf (02:34:03, "WIP on fix-146-preview-cache-picture-dedup":
categories.py, owned.py, pictures.py, preview.py, references.py), earlier 5a41cbcf (02:33:00, same content). Recover with
`git stash apply 2a68c8cf` if #146 lost it. I did not drop either.

## Risks
- Merge: the only shared-code edit is one appended line in `render_preview_extra_lines` (plus a new block just above it, after
  `render_sense_list_reference_decisions`). #147 edits that renderer and #141/#142 may append to the same tuple -> trivial
  textual conflict possible; resolution is keep all appended calls.
- The tag "already in the target" note is computed from `disposition == UPDATE`; a matched text that has NO paragraphs in the
  target would actually get tags, so the note is phrased conditionally ("added only if the target text has no paragraphs yet")
  rather than as "no tags".
- Reversal rows reflect Preview's `_copy_set` (placeholders); Move recomputes against the settled copy set. Live they agreed;
  a divergence would come from the copy set itself, not this renderer.
- Genre rows will start appearing as soon as the genre follow-up lands; nothing to change here.

## Files touched
- src/gramtrans/Lib/preview.py
- tests/unit/test_issue144_preview_pos_text_decisions.py (new)
- tests/integration/test_issue144_pos_text_decisions_live.py (new)
