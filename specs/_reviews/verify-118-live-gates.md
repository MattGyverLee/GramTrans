# Issue #118 - Target-writing live gates on post-#106 main

Base: origin/main a7dd0b1 | Date: 2026-11-01 | Project written: `Target` ONLY
(restored from `backups/Target 2026-07-06 0218.fwbackup`; each test restores it itself).
Command per file: `FLEXLIBS_REQUIRE_LIVE=1 GRAMTRANS_E2E=1 python -m pytest <file> -q -rA`
Target claimed via the lockout skill (team verify-118) for the whole run, released after a final restore.

## Results

| Gate (tests/integration/) | Result |
|---|---|
| test_issue16_phoneme_env_update_live.py | 1 FAIL as found (stale test shim), 1 PASS after shim fix (see below) |
| test_issue185_sweep_report_live.py | 5 passed |
| test_issue191_category_update_live.py | 3 passed |
| test_issue45_untitled_texts_live.py | 1 passed |
| test_issue48_create_guid_live.py | 5 passed |
| test_issue49_default_set_live.py | 1 passed (354 s) |
| test_issue67_owner_pos_live.py | 2 passed |
| test_issue87_residue_idempotent_live.py | 1 passed |
| test_ws_followups_live.py | 2 passed |
| test_028_affix_msenv_live.py | 1 SKIPPED by design (T019 is attended/manual only) |

Totals: 21 passed, 1 failed-then-fixed (test defect), 1 skipped-by-design.

## Failure found: test_issue16 (test drift, not a product defect)
`_UpdateRecorder` in the test monkeypatches `transfer.apply_update_semantic` with
`_apply(src, tgt, ops, obj, ws_map=None)`. Product code now passes `report_sink=`
(issue #50 plumbing), so the shim raised
`TypeError: ... _apply() got an unexpected keyword argument 'report_sink'`,
which `_execute_update_semantic` swallowed and reported as an environment UPDATE
failure. Fix: shim accepts and forwards `**kw`. After the fix, live read-back:
pre-UPDATE diverged `('QQ16', '/_QQ16')` -> post-UPDATE `('j', '/_[V]')`
(phoneme BasicIPASymbol + environment StringRepresentation restored from source);
re-run plans 0 actions (no perpetual churn). This is unrelated to #106.

## #106-specific observations
* #185 gate: lazy LexRefType create with a forced LexReference failure reports the
  drop ("create failed: forced LexReference create failure" and "lexical relation
  type was not created ... empty type was removed") -- i.e. the newly-reported
  drop path works; no unexplained new drops appeared in any other gate.
* #48 gate: `Create(Guid)` duplicate-GUID errors are raised with the hint text for
  phoneme / PhSimpleContextNC / IFsComplexFeature factories.
* #67: stem_names skipped (owner POS absent) = 1, expected.
* No count rebaselines were needed in any run gate.

## NOT run (gap, why #118 is not closed)
The issue also lists `test_object_census.py` and the 038 tally tests
(`test_038_two_mode_and_tallies.py` and siblings). Those write `Ngoreme Target` /
`Ejagham W Target` (and need `Ngoreme FLEx` / `Ejagham W Mini` sources), not `Target`.
The task rule forbids writing any project other than `Target`, so they were not run
and the post-#106 delta on them (issue text predicts none) remains unmeasured.
Likewise the other `tests/integration` suites target `Ejagham Full GT-Test` or
`GT-Sandbox-*` projects. They need a human decision (or a Target-based port) to run.
