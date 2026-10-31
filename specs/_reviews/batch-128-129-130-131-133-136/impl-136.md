# impl-136 -- sub-sense appendix/thesaurus/picture refs (PR #148, closes #136)

Branch fix-136-subsense-refs (worktree GramTrans-fix-136), commit 17a2128, based on 23e5356 (origin/main had no newer commits at merge time).

## Env check
gramtrans = D:\Github\_Projects\_LEX\GramTrans-fix-136\src\gramtrans\__init__.py
flexicon  = D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py

## Root cause
Top-level senses get AppendixesRC / ThesaurusItemsRC / PicturesOS handling from the sense loops in
categories._walk_lex_entry_closure (Move) and _plan_entry_reference_decisions (Preview):
_resolve_sense_appendixes, _resolve_sense_thesaurus_items, _report_dropped_sense_scope_gaps, and
pictures.reproduce_sense_pictures / plan_sense_picture_decisions. Sub-senses reach only
owned._apply_full_sense_reference_fields / _plan_full_sense_reference_decisions, which called only
_apply_reference_fields / _decide_reference_fields (none of the three fields are in REFERENCE_FIELD_MAP).

## Fix (src/gramtrans/Lib/owned.py only)
Both owned.py functions now additionally call the SAME five categories/pictures entry points the
top-level loops call (Move passes new_child; Preview passes None and returns the records, incl. the
picture plan records). They run once per recursed sub-sense, so any depth is covered. No resolver was
edited or duplicated. references.py and pictures.py untouched (no overlap with #129).
Unresolvable refs flow into `dropped` via the existing resolvers (DroppedItemRecord).

## Tests
Unit (tests/unit/test_issue136_subsense_refs.py, 4 new, 3 fail without the fix):
- Move: sub + sub-sub AppendixesRC/ThesaurusItemsRC applied, picture seam reached for both, absent appendix dropped.
- Preview: LINK / REPORT_DROPPED decisions for sub + sub-sub, picture plan reached, drops equal.
- Unresolvable thesaurus on a sub-sense -> DroppedItemRecord in both modes.
- Sub-sense with no refs: no drops (unchanged).
Full suite: 5388 passed / 80 skipped / 14 xfailed  (delta vs 5384/80/14: +4 passed, 0 regressions).

## Live proof (FLEXLIBS_REQUIRE_LIVE=1) tests/integration/test_issue136_subsense_refs_live.py
Names pinned: GT-Src-136 -> GT-Sandbox-136, restored from "Target 2026-07-06 0218.fwbackup"; write
guard asserts only those two names; GT-Src-42 never opened.
Fixture: entry > top sense > sub-sense > sub-sub-sense. Sub: AppendixesRC [present, absent],
ThesaurusItemsRC [C (source-only, CREATE), E (existing, LINK)], PicturesOS (PNG via Senses.AddPicture).
Sub-sub: AppendixesRC [present], ThesaurusItemsRC [C], PicturesOS.
Result: 5 passed (9 s).
- Preview wrote nothing; decisions for sub + sub-sub present (appendix link, absent report_dropped, thesaurus create/link); drop for absent appendix listed.
- Move: sub + sub-sub carry present appendix and C (CmPossibility, created with source GUID) by GUID; sub also E; absent appendix reported as dropped (exactly one).
- Pictures: authoring was easy (Senses.AddPicture), so PicturesOS has LIVE coverage: 1 picture each on sub and sub-sub in the target.
- Negative control: with src stashed, 4 of 5 live tests fail.
- Observed (not mine): a TypeError "Apply syncable properties" warning during thesaurus CREATE = #129's known Description bug.

## Triage of the other #136 sites (none was previously tracked; #126-#139 checked)
| Site | Issue | Label |
|---|---|---|
| bare plan_all_lexical_relations, preview.py:1495 | #141 (new) | P1 |
| PLAN_TIME_PENDING LexRefType not recorded | #142 (new) | P2 |
| reference_decisions unrendered/unserialized | #143 (new) | P2 |
| ReversalDecision.pos_decision / text_plans unrendered | #144 (new) | P2 |
| FlexTools-module Preview paths skip render_preview_extra_lines | #145 (new) | P2 |
| unprimed cache re-shows CREATE; per-sense picture dedup pictures.py:770 | #146 (new) | P1 |
| no row cap on sense-list renderer | #147 (new) | P2 |
#126 (POS owned children Preview) and #127 (LexEntryRef merge Preview) are adjacent but different sites; not commented.

## Git
PR #148 opened against main, body has "Closes #136" and the triage list; NOT merged.
Report not committed on main.
