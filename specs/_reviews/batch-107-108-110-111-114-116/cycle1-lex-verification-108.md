# Cycle1 live verification -- PR #122 (#108)

Worktree HEAD c61105f. FLEXLIBS_REQUIRE_LIVE=1, PYTHONPATH=GramTrans-fix-108/src.
Imports: gramtrans = D:\Github\_Projects\_LEX\GramTrans-fix-108\src\gramtrans\__init__.py;
flexicon = D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py (working tree, not site-packages).
Projects: source "Mbugwe Lizzie" READ-ONLY; written: GT-Sandbox-108 only.

1. [PASS] Source SHA-256 before = db195e04e8963ab4ab2d849f3ff955932fbe9ed52c90fb568da033ce60a7ff0c (matches expected).
2. [PASS] test_issue108_features_rs_repair_live.py -s: 1 passed (41s); all 4 runs (14 drops, 6 repairs, 0 writes, 1 repair) asserted inside the test.
3. [PASS] Label gap closed (scratch copy in scratchpad/verif108/test_scratch108.py, uncommitted; added print+assert only): all 14 run-1 FeaturesRS DroppedItemRecords (report and plan) have non-empty owner_label and item_name, human-readable, not GUIDs. Examples: owner 'Noun agreement' / item 'Bantu noun class'; owner 'Infl' / 'polarity'; owner 'Phon' / 'labial'. Scratch test: 1 passed.
4. [PASS] Mutation: call at categories.py:3448 replaced by `pass` -> test FAILED at run 2 (categories.py repair absent; Ms NOUN_AGR members == [X_MS only] vs expected [CLASS, NUMBER, X_MS]; test line 302). Reverted via git checkout; `git status --short` clean.
5. [PASS] Source SHA after (post-mutation too) = db195e04...a7ff0c, unchanged. GT-Sandbox-108 is restored from "Target 2026-07-06 0218.fwbackup" by the test's autouse fixture (also on the failing mutation run).

Verdict: PASS -- APPROVE.
