# Cycle 2 verification, issue #1 (branch fix-1-deriv-msa-pos @ 8793ba8)

Setup: gramtrans resolves to the worktree src; flexicon resolves to D:/Github/_Projects/_LEX/flexicon (not site-packages). FLEXLIBS_REQUIRE_LIVE=1. Only Target was written.

## A. Full integration suite: PASS
Target restored first. Result: 30 failed / 767 passed / 75 skipped, the same counts as main. The failures are the same families as baseline: test_038_closure_edge_audit::test_every_link_in_the_chain_declares_whether_it_is_reproducible, plus 29 in test_object_census.py (T078, T081, T101, T107, T108). The census ones fail with "no run report ... _run_reports/038-t126-ngoreme-report.json". I compared by count and family. I had no per-test list from main, so the set is not diffed test by test. No new family appeared.

## B. Deriv-MSA write check: PASS
Target restored, then Esperanto -> Target with AFFIXES only (via full_run.run_full_transfer, exclude = all other categories).
- Report: AFFIXES 68 added, 0 skipped. Dependencies also added: 5 gram categories, 7 inflection features, 3 feature-struct types.
- AFFIX_TEMPLATES (a tail category): 40 DEPENDENCY_UNRESOLVED skips. These are slot dependencies, not owner-POS skips, and are outside #1.
- No owner-POS-unresolved skip for deriv affixes.
- Target was re-read read-only after the run. Source has 31 MoDerivAffMsa; Target has 31, every GUID present, none skipped.
- Null side in Target: 0. Source non-null sides: 62; all 62 are non-null in Target.
- Each target POS exists in Target and its abbreviation equals the source POS abbreviation. 36 of the 62 sides are GUID-identical. The other 26 point at Target's own pre-existing equivalent POS (n, adj and similar), which is the intended target-resolved behaviour.
- Examples: -igi Root>v, -iĝi Root>v, -ino Root>n (the target n has a different GUID than the source n, same abbreviation).
- Display: msa_label_from_obj on live Esperanto deriv MSAs gives "Root>n", "Root>n", "VRoot>adv". merge_preview delegates to this function, so the "Grammatical Info" label now shows From>To. I did not drive the Qt pane itself.

## C. Ejagham Full GT-Test baseline probe: INCONCLUSIVE
The project opened read-only (a lock file exists, but opening was not blocked). A preview_only run with an AFFIXES-only selection produced 0 actions on both the worktree and main, with identical signatures. That is not a meaningful comparison, so there is no evidence of change, but the probe did not exercise affixes_dependencies. This does not bear on #1's write side.

## D. Restore: DONE
Target restored from "Target 2026-07-06 0218.fwbackup".
Target.fwdata sha256: 13c5a96fba560ae86b29893798f5bcf1cd0d631d19d36f50bef9a1ecfad74c7f

Verdict: "closes #1" stands. The write path preserves From/To POS on every deriv MSA, and the display fix is confirmed.
