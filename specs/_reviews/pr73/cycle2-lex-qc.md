# PR #73 cycle 2 -- lex-qc (PR #79, bb7208e) -- 88/100
Static read only (reviewer had no shell/write; transcribed by main session).
Main-session pytest on bb7208e: `pytest tests/unit tests/verification -p no:randomly` -> 5086 passed, 81 skipped, 14 xfailed, 0 failed.

## Closure table
| Cycle-1 P1 | Status | Evidence |
|---|---|---|
| rewrite scoped to WritingSystemOptions | closed | config_views.py:433 parent check; root writingSystem= :424-432; test_ws_path_followup.py:46 |
| swap/chain corruption | closed | single tokenised pass `ws_renames.get(old)` :444; offset-applied edits :460-468; tests :33, :39 |
| quote styles / `>` in values | closed | `_TOKEN_RE` :303-307; test :57 |
| api.py silent handlers | closed | api.py:899, 912, 925, 938 log with exc_info |
| api.py programming errors -> drops | closed | `_PROGRAMMING_ERRORS` api.py:808 re-raised :884, :973; test_programming_error_in_create_propagates |

Collision dedupe correct (:376-399). Reversal rename .gtbak's existing target (:697-701), test :106. Only AttributeError/TypeError/NameError re-raised; .NET errors still drops (test_genuine_lcm_failure_is_still_a_drop). No new bare excepts.

## P0 / P1
None.

## P2
1. api.py:973 re-raises TypeError; pythonnet raises TypeError for "No method matches" overload errors -> a bad .NET call now aborts the Move. Comment or narrow.
2. Two source reversal files mapping to the same target name overwrite each other in one run; untested. Reversal filename swap untested.
3. `_plan_action` OSError -> OVERWRITE (safe).
4. Inactive-WS fallback can flag an actually-active WS (disclosed by programmer).
5. Severity plumbing deferred to #78; #75-#77 filed.
6. api.py `_ensure_writing_systems` is write-path; lex-lead to decide on live-gate evidence (live gate is running in parallel).

Recommendation: APPROVE (pytest confirmed by main session).
