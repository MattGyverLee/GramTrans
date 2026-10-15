# Cycle 3 programmer report (PR #82)

Commit: see `git log -1` on fix-ws-followups (pushed, no force).

Files: tests/integration/test_ws_followups_live.py, src/gramtrans/Lib/{ws_mapping,api,preview,report}.py,
tests/unit/test_ws_followups_75_80.py, tests/unit/test_038_enrichment_report.py.

Inactive-state setup: after restore, open Target (write), `WritingSystemOperations.Create('es','Spanish',
is_vernacular=False)` (store + AnalysisWss + CurAnalysisWss), then in a write transaction set
`lp.CurAnalysisWss` without 'es' (es stays on AnalysisWss and in the store). Close, reopen. The es.ldml
copy staging and donor-project copying are removed. No disk-LDML fallback.

Observed before Move (asserted in the test): Exists('es') False; ExistsInStore('es') True; 'es' not in
GetAll(); 1 definition. Preview: exactly one info "will activate stored writing system", nothing written.
After Move: es in GetAll, Exists True, still 1 definition, single es.ldml, no failure record.
flexicon Exists/ExistsInStore/Create semantics match real-FLEx inactive state: no discrepancy.
(Looked up via source grep; FLExToolsMCP tools were not available in this subagent.)

P2s: (1) ws_mapping.require_ws_store_support, called up front in preflight_ws_creates and
api._ensure_writing_systems; new unit test covers all-active tags on a no-ExistsInStore ops, Preview+Move.
(2) preview.py comment rewritten. (3) report.py uses models.merge_dropped_records; new unit test for
info->warning upgrade.

Results: tests/unit: 5022 passed, 81 skipped, 14 xfailed, 0 failed. Live (FLEXLIBS_REQUIRE_LIVE=1, Target only,
restored before and after): 2 passed (test_preflight_and_move_create_and_skip_live,
test_stored_but_inactive_ws_is_activated_live). A faulthandler stack dump printed in the pytest output
before the results; tests still passed.
