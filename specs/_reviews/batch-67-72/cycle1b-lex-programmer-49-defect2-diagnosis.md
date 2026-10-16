# Issue #49 Defect 2 diagnosis (plan level, read-only)

Worktree: GramTrans-batch-67-72. Default set from gramtrans.py:527-532.

## Root cause per category

* ENTRY, SENSE, MSA, ALLOMORPH: never dispatched, by construction.
  - The legacy path that owned them (`_plan_layer3_verb_affixes_inner`, preview.py:2982) is gated off by `_VERB_VERTICAL_ENABLED = False` (preview.py:1141, 1143).
  - They are not in `_LEAF_DISPATCH_CATEGORIES` (preview.py:1266-1308) and not in `LEAF_CATEGORIES` (categories.py:16103). Their entries now ride inside AFFIXES/STEMS.
  - The loop does `except KeyError: continue` (preview.py:1317-1319), which is the silent drop. `is_on(cat)` at 1314 is true for them, yet nothing plans.
  - The default set contains neither AFFIXES nor STEMS, so the lexicon (2,015 entries) has no planner at all. This is a category-gate mismatch, not a pick-shape issue. pos_picks is irrelevant to them.
* POS:
  - With EMPTY pos_picks it plans zero by design (`pos_enumerate_source`, categories.py:1285-1296: empty picks returns ()).
  - It also returns () when GRAM_CATEGORIES is on (1298).
  - With all 26 picks it DOES plan. Measured below.
  - `build_run_plan` wraps enumerate in `except Exception: pieces = []` (preview.py:1322-1323), so an enumerate error would also yield silent zero.
  - If the original run still showed zero with picks, suspect the caller not forwarding picks (pos_picks is falsy-collapsed at gramtrans.py:536) or a target already holding the POSes.

## Measured repro (Ngoreme FLEx source, Ngoreme Target opened read-only, no execute)

Script: C:/Users/thoua/AppData/Local/Temp/claude/D--Github--Projects--LEX-GramTrans/395e22ef-141a-4354-a0a2-33d43d25d628/scratchpad/repro49.py

```
cats = {c: True for c in (POS, AFFIX_TEMPLATES, SLOTS, ENTRY, SENSE, MSA, ALLOMORPH, PH_ENVIRONMENT)}
sel = Selection(categories=cats, include_closure=True, pos_picks=picks, enable_overwrite=True, interactive_merge=True)
plan = build_run_plan(ctx, sel, WSMapping(), src, tgt)
```

* picks empty: POS 0, ENTRY/SENSE/MSA/ALLOMORPH 0, slots 19 skip, templates 13 skip, ph_environment 9 overwrite.
* picks=26: POS 26 overwrite (this Target is already populated), ENTRY/SENSE/MSA/ALLOMORPH still 0.
* Neither run has an entry in plan.skips or plan.dropped_items for the four lexicon categories.

## Proposed fix

1. Resolve ENTRY/SENSE/MSA/ALLOMORPH explicitly. Either:
   - (a) map them to AFFIXES (and STEMS) in the default set, i.e. change the gramtrans.py:527 default to AFFIXES, STEMS, GRAM_CATEGORIES, etc.; or
   - (b) have `build_run_plan` expand them to AFFIXES/STEMS before dispatch.
   Pick (a)/(b) with lex-lead; (b) fixes every caller.
2. Make the POS-empty-picks case explicit: either enumerate all POS when picks are empty and GRAM_CATEGORIES is off, or emit the record below.

## Where to add the "planned nothing because X" record

* preview.py:1317-1319: on `KeyError`, append a `DroppedItemRecord` or `Skip` with a new reason such as `CATEGORY_NOT_PLANNABLE_DIRECTLY` and detail "ENTRY is planned via AFFIXES/STEMS; neither selected".
* preview.py:1322-1323: on `except Exception`, record the exception text instead of `pieces = []`.
* After the loop at 1327: if `pieces` is empty for an `is_on` category, emit one category-level skip with the reason (empty picks / GRAM_CATEGORIES shadowing, categories.py:1285-1298).
* gramtrans.py:~540: the `[Phase 2] Plan:` log should list the categories that planned nothing.
