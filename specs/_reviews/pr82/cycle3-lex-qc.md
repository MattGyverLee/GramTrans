# QC cycle 3 -- PR #82 (1061e34) -- delta review

Score: 95/100. Recommendation: APPROVE. No P0/P1.

(Saved by the main session; lex-qc had no Write tool.)

## Checks
- Fixture OK: test_ws_followups_live.py:79-93 calls `ops.Create(es)` (AnalysisWss + CurAnalysisWss) inside writable Target, then removes `es` from CurAnalysisWss inside `ops._TransactionCM`, so it is on the all-list but not the current list. It closes and reopens (105-107) and asserts the setup (ExistsInStore True, Exists False, 1 definition). `_restore()` runs before and after; only TARGET_NAME is opened. The hand-copied es.ldml staging is gone, so no loose LDML is left. `_store_files()` is read-only and asserts a single es.ldml after Move.
- Floor check OK: `require_ws_store_support` (ws_mapping.py:694) is called once before the per-tag loop in both `preflight_ws_creates` (:784) and `api._ensure_writing_systems` (:942). It runs before `active_ws_ids`, so it fires even when every tag is active, and is not repeated per tag. The per-tag guard in `ws_create_state` (:732) is now only a backstop.
- report.py OK: :341 uses `merge_dropped_records`, keyed on `dropped_identity` (unchanged for records with both GUIDs). The first record is kept; info is upgraded to warning in either order (models.py:3861-3883).
- Tests: the floor test (test_ws_followups_75_80.py:415) covers Preview and Move against an all-active target whose ops lack ExistsInStore -- behavioural. `test_enrichment_dedupe_upgrades_info_to_warning` (test_038_enrichment_report.py:478) is behavioural. The live test asserts re-queried values (GetAll, definition count, store files).

## P2
- test_038_enrichment_report.py:478 -- only info-then-warning is covered at report level; add the reverse order (executor warning, enrichment info). The logic itself is covered by test_ws_followups_75_80.py:198.
- test_ws_followups_live.py:205 -- stray double-space backslash continuation before `==`; parses, but wrap in parentheses.
- No pre/post-state evidence artifact at specs/<feature>/evidence/live-<task>.md; the cycle-3 programmer report states FLEXLIBS_REQUIRE_LIVE=1, 2 passed, Target restored. Confirm the artifact, or the live gate is formally unmet.
- The faulthandler stack dump in the live output deserves a one-line explanation. (Main-session note: this is the pythonnet first-chance access violation inside flexicon FLExInit.FLExInitialize, which also prints in the existing test_issue48_create_guid_live.py run; the tests pass after it.)

Reviewed by: lex-qc
