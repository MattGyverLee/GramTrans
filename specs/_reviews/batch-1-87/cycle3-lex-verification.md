# Cycle 3 live verification (batch-1-87)
Live, FLEXLIBS_REQUIRE_LIVE=1, Target only written (restored first). gramtrans.__file__ = fix-87 / fix-1 worktree src; flexicon = D:/Github/_Projects/_LEX/flexicon. Scripts/outputs: scratchpad/c3v/.

## Part 1 (#87, fix-87 @ 32cd022): [PASS]
a. Broad scenario (cycle-2 b_run.py, run1 204 actions, run2 0 actions): [GT-Tag] lines 46 vs 46, byte-identical set; 0 tag changes. All 11 cycle-2 POS GUIDs: 7 byte-identical; 4 (0a63fb15, 30d07580, 6df1c8ee, e680330e) differ ONLY by AffixSlots/AffixTemplates owner links = excluded template/slot defect. Remaining diffs, all excluded class: 10 new MoInflAffixSlot, 7 new MoInflAffixTemplate, 98 MoInflAffMsa (slot links), 8 PartOfSpeech owner-link-only (0a63fb15, 1c0d8047, 30d07580, 6df1c8ee, 98fe9318, e4832adb, e680330e, f0b222a1). Zero non-structural line changes on any object. (FsFeatStruc churn not observed this time.) No unexcluded diffs.
b. Run 1: each of 46 stamped objects has exactly 1 tag line (18 POS, 11 PhPhoneme, 8 FsClosedFeature, 4 Text, 3 FsFeatStrucType, 2 FsComplexFeature). GENUINE UPDATE now live-verified: after run 1 I renamed Target POS 093264d7 and 86ff66f6 to "TEST_edited" (flexicon SetName); run 2 restored the Name from source, KEPT the run-1 tag line, and appended a new tag with snap=. Decoded snap: {Abbreviation, CatalogSourceId, Description, Name:"TEST_edited"}, no nested GT-Tag. 86ff66f6 (run-1 snap= line) kept intact. Only extra diff: LangProject DateModified. Not unit-only any more.
c. New test test_issue87_residue_idempotent_live.py: fix-87 PASS (1 passed). Negative control in fix-1 (main w/o #87): FAIL, "run 2 re-stamped objects it did not create/change" (POS + 4 Texts: 11d03154, 1e12bccc, 2eb48397, 3ad7802c, plus 093264d7, 0a63fb15, 1ed7c604, 30d07580, ...). Copy deleted; `git status --short` clean in fix-1. Note: a native crash trace prints at interpreter exit after the PASS (pre-existing teardown noise, outcome unaffected).
d. Integration -rf: 30 failed / 768 passed / 75 skipped. Exact-ID diff vs 30-ID baseline: ADDED none, REMOVED none (comm on sorted IDs).

## Part 2 (main 3a86bb0 = fix-1 d27cc31): [PASS]
Integration -rf: 30 failed / 767 passed / 75 skipped (767 = 768 minus the #87 new test). Exact-ID diff vs baseline: ADDED none, REMOVED none. No differences attributable to #88/#89/#1.

## Final
Target restored; sha256 13c5a96fba560ae86b29893798f5bcf1cd0d631d19d36f50bef9a1ecfad74c7f (matches). No source edits, commits, pushes. Verdict APPROVE.
