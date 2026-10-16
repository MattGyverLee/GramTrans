# Cycle 1 - lex-programmer - #67 (closes #36)

Worktree GramTrans-batch-67-72, commit caaf000 (not pushed). `import gramtrans` resolves to MAIN checkout; used PYTHONPATH=<worktree>/src. flexicon -> D:/Github/_Projects/_LEX/flexicon.

## Registry rows added (CLOSURE_EDGES_VERIFIED, 8 -> 11)
- STEM_NAME_TO_POS: STEM_NAMES -> GRAM_CATEGORIES, stem_names_pos_dependencies
- INFLECTION_CLASS_TO_POS: INFLECTION_CLASSES -> GRAM_CATEGORIES, inflection_classes_pos_dependencies
- POS_INFLECTABLE_FEAT_TO_POS: POS_INFLECTABLE_FEATS -> GRAM_CATEGORIES, pos_inflectable_feats_pos_dependencies
Also: `_closure_piece_key` - tuple pieces (pos, obj) were un-findable by the walker (`_guid_str_from(tuple)` is ""); now keyed by compound "pos::obj" like the plan's source_guid.

## NOT registered (FR-018)
EXCEPTION_FEATURES -> POS: NO_DATA on every corpus (Mbugwe Lizzie, Mbugwe LizzieHC practice, Ejagham Mini; also Esperanto, Ejagham Full probed, snapshots not kept). No DependencyKind member added. Producer wrapper + audit candidate kept; a test pins it unregistered.

## Audit verdicts (LizzieHC / Ejagham Mini / Mbugwe Lizzie)
- STEM_NAME_TO_POS: NO_DATA / NO_DATA / CONFIRMED (1 edge, 1 POS). Floor 1, SINGLE-CORPUS stated.
- INFLECTION_CLASS_TO_POS: CONFIRMED (5 edges / 2 POS) / NO_DATA / NO_DATA. Floor 1.
- POS_INFLECTABLE_FEAT_TO_POS: CONFIRMED 14/7, 13/6, 6/3. Floor 3.
- EXCEPTION_FEATURE_TO_POS: NO_DATA x3.
All: foreign 0, unresolved 0, unkeyed_pieces 0.
Caveat: "Mbugwe LizzieHC practice" data has drifted since Aug (AFFIX 144 -> 229). I kept its old snapshot and merged only the new rows, so existing pinned counts hold. The Ejagham Mini snapshot was regenerated (pure additions). New corpus snapshot: closure-edge-audit-038-mbugwe-lizzie.json.

## Pinned count
test_038_closure.py: `== 11` (lookup keys also pinned); test_038_foundational set updated; `_REGISTERED`, `_MIN_CONFIRMING_CORPORA` updated.

## Cycle check
Registered graph test: GRAM_CATEGORIES is never a registered source; DFS finds no cycle; FEATURE_STRUCT_TYPES/INFLECTION_FEATURES (POS's raw outward targets) are not sources of any row; a walk seeded with POS + stem name terminates.

## Tests
test_issue36 tripwire replaced with walk tests through closure_dependencies_for (stem names, inflection classes, inflectable feats), plus unregistered exception-features, narrow-row and cycle tests.

## Live (Target restored from "Target 2026-07-06 0218.fwbackup", FLEXLIBS_REQUIRE_LIVE=1; tests/integration/test_issue67_owner_pos_live.py, both PASS)
- Positive: Target before had neither. After: POS 923e5aed-d84a-48b0-9b7a-331c1336864a and stem name c1724868-9eeb-4e32-a5f7-f01e752d5260 both present under source GUIDs. Report: gram_categories added=1 closure_pulled_in=1; stem_names added=1; total 2; engine attempted=2 succeeded=2; added == real delta in Target.
- Negative (closure registry emptied): no POS planned; stem_names added=0 skipped=1 (DEPENDENCY_UNRESOLVED), total_added 0; neither GUID in Target.
Target restored after each test. Only Target written.

## Suites
Unit: 5045 passed / 81 skipped / 14 xfailed (was 5039). 038 audit tests: 94 pass, 1 fail (test_every_link_in_the_chain_declares_whether_it_is_reproducible: fails identically on the pre-change tree - drifted census artifact).

SHAs: caaf000 (this); 09f9619 (#68/#70/#71).
