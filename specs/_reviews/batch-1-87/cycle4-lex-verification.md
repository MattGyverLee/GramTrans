# Cycle 4 live verification (batch-1-87, fix-87 @ 44e09d9)

(Saved by the main session: the verifier's thread had no Write tool.)

Live, FLEXLIBS_REQUIRE_LIVE=1; only Target written (restored first/last). flexicon = D:/Github/_Projects/_LEX/flexicon; pytest/scripts use fix-87 src (conftest forces tree). Scripts/outputs in session scratchpad: c4v/, c4e.py, c4_int.txt.

- **a. [PASS]** test_issue87_residue_idempotent_live.py on fix-87: 1 passed (exit-time native crash trace is known teardown noise).
- **b. [PASS]** Negative control (fix-1 = main 3a86bb0 without #87): FAIL "run 2 re-stamped objects it did not create/change" (POS 093264d7, 0a63fb15, 1ed7c604, 30d07580, ...; Texts 11d03154, 1e12bccc, 2eb48397, 3ad7802c). Copy deleted; `git status --short` clean in fix-1.
- **c. [PASS]** Integration -rf on fix-87: 30 failed / 768 passed / 75 skipped. Exact-ID diff vs 30-ID baseline (comm on sorted IDs): ADDED none, REMOVED none.
- **d. [PASS]** Genuine update (u_run.py: run 1 204 actions; rename POS 093264d7 and 86ff66f6 to "TEST_edited"; run 2): Name restored ("Distal demonstrative", "Verb"); run-1 tag line kept and a new tag line with snap= appended (093264d7: 1 tag -> 2, second has snap=; 86ff66f6: 2 tags, both snap=).
- **e. [PASS, vacuous]** Mbugwe fwdata read-only scan: 0 Descriptions end in newline/CR in any class (POS 13, PhPhoneme 43, FsClosedFeature 25, FsFeatStrucType 5, FsComplexFeature 2, Text 1, ...). No live run-2 trailing-newline UPDATE case exists; that invariant is covered by unit tests only.

Final: Target restored; sha256 13c5a96fba560ae86b29893798f5bcf1cd0d631d19d36f50bef9a1ecfad74c7f (matches). No source edits, commits, pushes. **Verdict: APPROVE.**
