# Cycle 3 live verification -- fix-batch-67-72, tested HEAD 1627e811 (+ test-only 664b381 pushed)

Env: FLEXLIBS_REQUIRE_LIVE=1, PYTHONPATH=worktree/src, flexicon -> D:/Github/_Projects/_LEX/flexicon. Writes to Target only,
restored from "Target 2026-07-06 0218.fwbackup" before/after every test; final sha 13c5a96f... (baseline). Serial. Sources read-only.

| # | Item | Result |
|---|------|--------|
| 1 | #67 owner-POS pos+neg (pos: 2 added; neg: 0 added, 1 Skip DEPENDENCY_UNRESOLVED) | PASS 2/2 |
| 2 | #49/#68 added == found-by-GUID (Ngoreme->Target, 71 actions): templates 13/13, slots 19/19, pos 21/21, ph_environment 9/9; entry/sense/msa/allomorph 0/0; leaf_failed=0 | PASS |
| 3 | #70/#71 duplicate-GUID message, one line each (IPhPhonemeFactory, IPhSimpleContextNCFactory, IFsComplexFeatureFactory) | PASS 5/5 |
| 4 | #45 untitled texts (Mbugwe Lizzie, 44 texts/32 untitled; 3 transferred) | PASS |
| a | #45 name format "(untitled text) 0543896a" / "...07c6e20b" / "...13661350"; per_category[TEXTS].added = 3 (run 1), 0 (run 2); target new-by-GUID 3 / 0; paragraphs 22/1/9 == source | PASS |
| b | Target sha change on run 2 (see below) | benign-by-design, see verdict |
| c | Stems with missing source entry -> skipped, not added | PASS (unit-level) |
| d | tests/integration: 767 passed / 30 failed / 75 skipped (identical to cycle 2) | PASS (no regression) |

## (b) Run-2 sha change
Snapshots of Target.fwdata after run 1 and run 2 (new test hook GT_SNAP_DIR). Object set identical (10598 objects, 0 added/removed).
File differs by 17 diff lines, ALL in the 3 `Text` objects (the ones run 1 created): each gained a second residue line in its
Description/Run: `[GT-Tag]: GT|GT-20261015-170915|Mbugwe Lizzie|<ts>` appended after run 1's `GT-...170911` line.
No name, paragraph, DateModified, or other class changed.
Verdict: NOT an unintended data write, and not corruption -- it is the residue tagger stamping already-present Texts with run 2's
tag. It is however a (minor) idempotency gap: re-running tags pre-existing texts as if this run touched them, and tags accumulate.
Recommend a follow-up issue (tag only objects the run created/updated); not a blocker for #45.

## (c) Evidence used
Unit-level: tests/unit/test_issue68_action_outcomes.py::test_stems_missing_source_entry_is_skipped and
::test_stems_declined_closure_is_skipped (11 passed in file). A live missing-source case is impractical. (Live neg #67 case above also
showed stem_names added=0 skipped=1.)

## (d) Failure classification (30 failed)
- 29 in tests/integration/test_object_census.py (T078/T081/T101/T107/T108) = the 29 pre-existing census failures of
  cycle3-lex-verification-census-base.md (count matches; census gates a missing run report / drifted baselines).
- 1 test_038_closure_edge_audit::test_every_link_in_the_chain_declares_whether_it_is_reproducible (known).
- Regressions outside these: none. 75 skips unchanged (opt-in E2E / host-only / drifted anchors); under REQUIRE_LIVE these are
  flagged, not passed, and none relate to #45/#49/#67/#68.
Note: "Windows fatal exception: access violation" at FLExInitialize is known pythonnet noise.

Verdict: PASS. Commit 664b381 (test-only hook) pushed to fix-batch-67-72, no force.
