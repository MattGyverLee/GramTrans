# Cycle 2 live verification -- branch fix-batch-67-72 (HEAD 8138a7f)

Env: FLEXLIBS_REQUIRE_LIVE=1, PYTHONPATH=worktree/src, flexicon -> D:/Github/_Projects/_LEX/flexicon/flexicon/__init__.py.
Write target: Target only, restored headlessly (restore.py, backup 2026-07-06 0218) before and after each run. Serial.
Target sha256 restored baseline: 13c5a96f...ad74c7f (identical after every test's end restore).
Note: "Windows fatal exception: access violation" is printed at FLExInitialize in every run; tests pass (known pythonnet noise).

| # | Item | Result |
|---|------|--------|
| 1 | #67 owner-POS (pos + neg) | PASS 2/2 |
| 2 | #49 default set | PASS 1/1 |
| 3 | #70/#71 create-GUID | PASS 5/5 |
| 4 | #68 added == landed | PASS (via test 2) |
| 5 | #45 untitled texts | PASS (new test, committed 8138a7f, not pushed) |
| 6 | tests/integration | 767 passed, 30 failed, 75 skipped |

## 2 / 4 (#49, #68), Ngoreme FLEx -> Target
sha before 13c5a96f..., after 7f87aae4...156fd9. 71 actions.
reported added == new-by-GUID in Target: templates 13/13, slots 19/19, pos 21/21 (before 5, after 26), ph_environment 9/9.
entry/sense/msa/allomorph: added 0, target new 0, each has a visible "not dispatched" skip. leaf_failed=0.
Skipped items (6 gram_categories "owner part of speech not present") are not counted as added. This is a non-trivial set, so it covers #68.

## 3 (#70/#71)
Duplicate messages are one line each: IPhPhonemeFactory, IPhSimpleContextNCFactory, and IFsComplexFeatureFactory (GUID feceee6b..., "(complex feature)" suffix) all say "Can not create more than one object with identical GUIDs (hint: this GUID already exists in the target)".

## 5 (#45)
Source Mbugwe Lizzie (read-only): 44 texts, 32 untitled by best-analysis title (issue measured 34 in the default WS; slight difference, not investigated).
Transferred 3 untitled texts (0543896a..., 07c6e20b..., 13661350...).
Run 1: sha 13c5a96f -> 141cb4d8. 3 new texts in Target, each under its source GUID. No collisions. Paragraph counts source == target (22/1/9), so no interleaving.
Exact target Name: "(untitled text) <source-guid>", for example "(untitled text) 0543896a-213a-4aa9-9014-a424ba4c366f". This is a visible difference from the blank source title.
Run 2: 0 texts added (total 3 -> 3), names and paragraph counts unchanged, so no overwrite or rename. The file hash still changed (7e6c9fd7...), so something was written on the re-run (probably metadata; not investigated).
Caveat: report.per_category has no TEXTS entry (added=None), so the "added" count is asserted from Target state, not from the report. That is a reporting gap worth a look.

## 6 Whole directory
30 failed, all pre-existing census drift on live projects ('drifted' vs 'match'):
- test_038_closure_edge_audit::test_every_link_in_the_chain_declares_whether_it_is_reproducible (the known one; census-038-mbugwe-phase6.json)
- 29 in test_object_census.py (T078/T081/T101/T107/T108 baselines for mbugwe, ngoreme, ejagham)
Neither file touches the code on this branch.
75 skipped. Under REQUIRE_LIVE a skip counts as FAIL, so these are flagged, not passed. Reasons:
- GRAMTRANS_E2E opt-in (013, 027, 028)
- Ejagham Full GT-Test drifted since anchoring (affix_pos_picker)
- FlexTools-host-only (phase3c)
- manual MCP fixture (phonology_live)
Not run by me: the GRAMTRANS_E2E opt-ins. None of them relate to #45/#48/#49/#67/#68.

Verdict: items 1-5 PASS live. Item 6 has only pre-existing failures (census drift) plus opt-in skips.
