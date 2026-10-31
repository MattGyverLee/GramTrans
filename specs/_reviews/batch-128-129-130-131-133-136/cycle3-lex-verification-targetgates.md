# Cycle 3 Target-write live gates (main f8096a3)

Worktree GramTrans-verify-c3 @ f8096a3 (removed). PYTHONPATH=<wt>/src; flexicon -> D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py (not site-packages). Target restored from `backups/Target 2026-07-06 0218.fwbackup` (restore.py) before EACH module. All runs: `FLEXLIBS_REQUIRE_LIVE=1 python -m pytest <module(s)> -q -p no:cacheprovider`. tests/live_status.json absent in this tree, so run_mode not readable; live evidence is real LCM opens (file-lock error on Ngoreme, 197 s real-transfer run).

## Per-module result
| Module | Selection / result |
|---|---|
| test_object_census.py (alone) | 1st run: 499 passed, 1 failed, 39 skipped. Re-run whole file: **500 passed, 39 skipped** |
| test_038_*.py (7 files: affix_slot_links_live, closure_edge_audit, no_silent_skips, phon_empty_drop_live, process_rules_live, stale_lock, two_mode_and_tallies) | 221 passed, 1 failed |
| test_issue45_untitled_texts_live | 1 passed (faulthandler stack dump at exit, run still exit 0) |
| test_issue48_create_guid_live | 5 passed |
| test_issue49_default_set_live | 1 passed (197 s) |
| test_issue67_owner_pos_live | 2 passed |
| test_issue87_residue_idempotent_live | 1 passed |
| test_ws_followups_live | 2 passed |
| test_issue16_phoneme_env_update_live (default sandbox = Target) | 1 failed |
| test_028_affix_msenv_live | SKIP: needs GRAMTRANS_E2E=1, attended-only destructive; not forced |

Excluded (write target is not literal `Target`): 013/027/conflict/custom_fields/e2e_all/full_workflow/guid_preservation/target_preserved/034_* (Ejagham Full GT-Test); issue108/110/114/128/130/131/136/31/32/37/42 (GT-Sandbox-N; 128/130 are being written by other agents); 55/56 (GT055/GT056 Target); phonology/rules/affix_pos_picker/skeleton/gold/phase2/3c/same_project/residue/target_locked (read-only or fakes). Note: #131 and #136 live tests write GT-Sandbox-131/-136, not Target; I did not run them, so their gates are NOT paid here. #128/#130 likewise belong to the other agents.

## Failure classification (re-run at 23e5356, Target restored first)
| Test | Baseline 23e5356 | Class |
|---|---|---|
| census ...test_ngoreme_flex_is_a_different_and_larger_project_than_ngoreme | passes; also passes alone and in full file on f8096a3 | Transient: LcmFileLockedException on Ngoreme (another process held it). Not batch-caused. |
| 038_no_silent_skips ...test_every_report_field_is_classified (`category_notes` unclassified) | fails identically | Pre-existing; not introduced by the batch. |
| issue16 ...test_phoneme_env_update_end_to_end (`'BasicIPASymbol' in []`, recorder.written empty) | fails identically | Pre-existing. |

No batch-introduced failures. No tallies moved: the 038 two_mode_and_tallies tests passed, so no tally drift to explain. Census count differs from earlier selections (500/39 vs 503/5/29) only because selection/skips differ (ours is the whole file).

## Integrity (sha256 .fwdata, identical before and after)
- Mbugwe LizzieHC practice: 3fb29a294434f85301e2f2f75d704489cdf4495325252cfb0f8797137cd5436d
- Ngoreme: 6d35c9575fc6094089dff757da4f54f266aa5a0d7e4ea16cd1fd3bd64abe472d
- Esperanto: e9effa15262739d8fc11e2ce72f0a1b44c88cf7a1d8d5b5a669643aa16683189

Caveat: the census/038 modules write `Ngoreme Target`/`GT038 *` projects, not Target itself; Target was rewritten by the 8 literal-Target modules.
