# Cycle 2 -- live verification, issue #87 (fix-87 @ 6c06a0e)
Target only written; gramtrans.__file__ = worktree src, flexicon = D:/.../flexicon (not site-packages). Mbugwe LizzieHC practice read-only.

## Verdict: [FAIL] -- Texts re-stamp fixed, but PartOfSpeech is still re-stamped on re-run

### A. Issue45 test -- [PASS] on fix, but negative control NOT reproduced
- Fix: 3 untitled Texts, 3 [GT-Tag] lines (one run id, one each); run1 vs run2 fwdata diff = 0 lines.
- main (d9f55c9) src: diff run1/run2 = 0 lines on two attempts (3 tags run1, same 3 in run2). Programmer's 18-line "before" did NOT reproduce here, so this test alone does not prove it detects the bug (run 2 plans 0 actions for these texts).

### B. Broad idempotency (Mbugwe LizzieHC practice -> Target, twice, TEXTS(4 picks)+POS+AFFIXES+ENTRY+SENSE+MSA+ALLOMORPH+GRAM_CATEGORIES+INFLECTION_FEATURES) -- [FAIL]
Run 1: 204 actions. Run 2: 0 actions, yet file changed. Evidence: scratchpad/b_run1.fwdata, b_run2.fwdata, cmp.py.
- Fix src: diff 747 lines. Texts/Wordforms: NOT re-stamped (good). 11 [GT-Tag] lines replaced by run-2 id on PartOfSpeech objects not created/updated by run 2 (run1 tag GT-...114327 -> run2 GT-...114343):
  093264d7-06c3-42e1-bc4d-5a965ce63887, 0a63fb15-ccf8-432f-8816-a330d26010f6, 1ed7c604-79b4-4198-96f1-9643f2eb0369, 30d07580-5052-4d91-bc24-469b8b2d7df9, 64e3b502-90f5-4df0-9212-65f6e5c96c30, 6df1c8ee-5530-4180-99e8-be2afab0f60d, 86ff66f6-0774-407a-a0dc-3eeaf873daf7, b85e4cf4-414a-44bc-85ae-027c91e42bc4, d32dff62-4117-4762-a887-96478406769b, d99458f4-63e1-4f09-909b-f7ae9d10a254, e680330e-2b41-4bec-b96b-514743c47cae.
  (One carries a snap= baseline line, so run-1 undo snapshot is lost.) Replaced, not appended. Four other POS changed without tag change.
- Baseline main src: same POS re-stamps PLUS the 4 Texts gained a 2nd tag line (11d03154, 1e12bccc, 2eb48397, 3ad7802c); 771 diff lines. So fix removes the Text part only.
- Non-tag diffs (same on both src, pre-existing, not #87): run 2 creates 17 objects (10 MoInflAffixSlot, 7 MoInflAffixTemplate) with plan.actions==0, and modifies ~98-102 MoInflAffMsa (slot links), 47 FsFeatStruc lines added. Template/slot path is not idempotent; separate issue.
- Culprit site not in programmer's audit: POS stamping path on run 2 (likely categories POS/affix-template closure).

### C. Target restored from "Target 2026-07-06 0218.fwbackup"; sha256 13c5a96fba560ae86b29893798f5bcf1cd0d631d19d36f50bef9a1ecfad74c7f
