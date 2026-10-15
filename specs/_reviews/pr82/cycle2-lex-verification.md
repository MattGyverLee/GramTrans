# PR #82 cycle-2 live verification

Commit b22a99b (worktree GramTrans-ws-followups, branch fix-ws-followups).

1. flexicon: D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py, version 4.13.0 (not site-packages). pyproject: pyflexicon>=4.8.0. [PASS]
2. Unit: 5020 passed, 81 skipped, 14 xfailed, 0 failed. [PASS]
3. Live (FLEXLIBS_REQUIRE_LIVE=1, Target only, restored before/after): 1 passed, 1 failed, 0 skipped.
   - test_preflight_and_move_create_and_skip_live: PASSED (CREATE tag created and active, existing tag skipped, Preview preflight wrote nothing, predicted == [], failures == []).
   - test_stored_but_inactive_ws_is_activated_live: FAILED at setup assertion
     `ops.ExistsInStore('es') is True` ("staged LDML not in the store").
   Reproduced twice, and alone with -k stored. [FAIL]
   live_status.json: not written by this harness (none found); run was live (Target opened, restored 11 files).
4. Activate branch NOT exercised. Observed before Move: Exists('es') False (assert passed), ExistsInStore('es') False.
   Diagnostic: after restore + staging es.ldml (952 bytes) into Target\WritingSystemStore, files are en/es/etu.ldml,
   but ServiceLocator.WritingSystems.AllWritingSystems after OpenProject = ['en','etu'].
   flexicon's _GetWSByTag iterates AllWritingSystems, so ExistsInStore cannot see a hand-staged LDML in this setup.
   Preview-info record, post-Move activation, single-definition and no-failure assertions were never reached. [FAIL]
   Target restored afterwards (confirmed by teardown). 
5. grep src/ for WS_BLOCKED, "scans the whole LDML store", "activate in FLEx and re-run": none. [PASS]

Overall: FAIL (the mandatory stored-but-inactive scenario is unverified).

P1: test fixture staging does not produce a store-visible inactive WS; either the LDML must be staged so the
LCM store loads it (e.g. via an actual deactivate through flexicon, then ExistsInStore), or ExistsInStore/_GetWSByTag
needs a disk-store fallback. Needs a programmer decision on which side is wrong; also note it means the PR's
real-world activate path is still unproven live.
P0: none.
