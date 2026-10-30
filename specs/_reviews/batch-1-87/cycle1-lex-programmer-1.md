# Cycle 1 -- lex-programmer -- issue #1 (deriv MSA POS deps)

Worktree D:/Github/_Projects/_LEX/GramTrans-fix-1, branch fix-1-deriv-msa-pos, commit 8793ba8 (closes #1). Not merged, not pushed.
Note: `import gramtrans` resolves to the MAIN checkout by default; all runs used PYTHONPATH=<worktree>/src (verified).

## Repro verdict: #1 as filed does NOT reproduce on HEAD
Live read-only probe, Esperanto: 68 affix entries, 30 with an MoDerivAffMsa. Ground truth (IMoDerivAffMsa cast) has From/To POS on all 30;
affixes_dependencies emitted every From/To guid as (GRAM_CATEGORIES, guid) for 30/30, 0 mismatches. `_entry_pos_deps` already
casts (T088) and loops PartOfSpeechRA/From/To. Introduced by b473136e / widened in 88b81554 (git log -S FromPartOfSpeechRA).
Baseline Ejagham Full GT-Test: could not open ("in use by another program") -- NOT probed; inflectional-only, code path unchanged.

## Sweep
| site | verdict | evidence |
|---|---|---|
| categories._entry_pos_deps / affixes_dependencies | OK | 30/30 live; new unit tests lock it |
| categories.py ~10386 move side | OK (read) | reads From+To, aborts if either null, passes both to _create_msa_with_guid -> setattr and to CreateDerivAff. Live write unverified (see below) |
| fingerprints.msa_label_from_obj (L183) | LIVE DEFECT, fixed | Esperanto sense MSAs, label empty uncast: 15270 stem, 41 infl, 32 deriv, 12 unclass (all). After fix: 14907/41/32/2 non-empty; remaining 363 stem/10 unclass have null POS legitimately |
| matcher.fingerprint_for_msa (L156) | Intended/unreachable | docstring is IMoInflAffMsa-only; FINGERPRINT_FNS[MSA] has no live caller (preview uses inline _msa_fingerprint filtered on MoInflAffMsa; natural-key matcher is a different path). Live: pos_guid "" for 31/31 deriv if it were called. Left unchanged, so NO match-key change |
| preview._msa_fingerprint / transfer / selection | Intended | Infl-specific by design; selection.py:875 already handles From/To (not changed) |

## Diff / behaviour change
src/gramtrans/Lib/fingerprints.py: msa_label_from_obj casts via categories._cast_to_concrete (lazy import, fail-soft) and labels deriv as "From>To".
BEHAVIOUR CHANGE (display only, merge_preview "Grammatical Info" via _msa_label_for_gather; NOT a match key): label was "" for every MSA, now e.g. "n", or "Root>v" for deriv "igi". Matching behaviour unchanged (matcher.py untouched).
New tests/unit/test_issue1_deriv_msa_pos_base_typed.py (7): base-typed fake (POS attrs raise AttributeError until cast, ClassName MoDerivAffMsa); both edges emitted; null From/To skipped; label tests. The 2 label tests fail pre-fix, the 5 dep tests pass pre-fix (regression locks).

## Tests
Unit: 5074 passed, 81 skipped, 14 xfailed (incl. 7 new).
Integration (FLEXLIBS_REQUIRE_LIVE=1): full suite NOT run (nearly every module restores/writes Target, held by another agent). Ran read-only subset (closure_edge_audit, affix_pos_picker_live, skeleton_deps_live, same_project_refused, gold_inviolable, 034_move_gate_live): 122 passed / 1 failed / 20 skipped. The 1 failure (test_038_closure_edge_audit::test_every_link_in_the_chain_declares_whether_it_is_reproducible, census snapshot drift) is pre-existing: fails identically with my change stashed. Delta vs 767/30/75 baseline not computable (subset only); no new failure. Skipped, deferred to lex-verification: all Target-writing modules (013_merge, 027, 028, 038_*_live write ones, e2e_all_categories, full_workflow_e2e, guid_preservation, issue45/48/49/67, phase3c, phonology, ws_followups, target_preserved).

## Live-write verification for next cycle
1. tests/integration/harness/restore.py: restore Target from backups/"Target 2026-07-06 0218.fwbackup".
2. Run full_run harness Esperanto -> Target with the affixes category selected (incl. derivational picks, e.g. "igi") under FLEXLIBS_REQUIRE_LIVE=1.
3. Read Target: every MoDerivAffMsa whose source had From/To must have FromPartOfSpeechRA and ToPartOfSpeechRA both non-null, GUID == target-resolved source From/To POS (e.g. igi: Root -> v); count of deriv MSAs in Target == created count (30 entries / 31 MSAs in source); no deriv MSA with either null; run report has no owner-POS-unresolved skip for deriv affixes.
