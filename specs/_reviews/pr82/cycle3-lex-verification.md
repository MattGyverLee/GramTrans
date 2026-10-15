# Cycle 3 verification (PR #82) -- overall PASS

HEAD 1061e34 on fix-ws-followups (matches origin; clean). Live run: yes, FLEXLIBS_REQUIRE_LIVE=1, Target only.

1. flexicon resolves to D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py (not site-packages); pip metadata pyflexicon 4.13.0 (no __version__ attr).
2. tests/unit: 5022 passed, 81 skipped, 14 xfailed, 0 failed.
3. Target restored from backups/Target 2026-07-06 0218.fwbackup (test fixture restore, 11 files) before and after. tests/integration/test_ws_followups_live.py: 2 passed (preflight_and_move_create_and_skip_live; stored_but_inactive_ws_is_activated_live).
4. Stored-inactive 'es' (all asserted in the test, verified by reading assertions, lines 173-206; no extra script needed):
   - Before Move: Exists('es') False; ExistsInStore('es') True; 'es' not in WritingSystems.GetAll(); 1 definition.
   - Preview: exactly one record (es, info) "will activate stored writing system"; active set, store files and definition count unchanged (nothing written).
   - Move: created == ['es']; es now in GetAll (re-queried) and Exists True; still exactly 1 definition; single es.ldml; failures == [].
5. grep src/ for WS_BLOCKED / "activate in FLEx and re-run": none.

Note: my own ad-hoc restore script failed on import (path); irrelevant, the test harness restored Target itself (log shows both restores DONE).

P0: none. P1: none.
