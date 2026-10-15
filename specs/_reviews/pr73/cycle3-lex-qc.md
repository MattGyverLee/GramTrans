# PR #79 cycle 3 -- lex-qc (delta bb7208e..7cd69fb) -- 90/100, APPROVE
Static read only (reviewer had Read/Grep/Glob only; transcribed by main session).
Main-session pytest on 7cd69fb: `pytest tests/unit tests/verification -p no:randomly` -> 5091 passed, 81 skipped, 14 xfailed, 0 failed.

(1) WritingSystemAndParaOptions consistent: rewrite (config_views.py:440,458) and _scan_missing_refs (:555) share `_WS_OPTION_PARENTS` (:335). Flat id->id map without writingSystemType scoping is correct (keyed on WS id). Ejagham Full GT-Test ReversalIndex/en.fwdictconfig: only WritingSystemOptions + root writingSystem=; no other WS-bearing element found. WritingSystemAndParaOptions shape from programmer's arz-flex check (not repeated).
(2) TypeError narrowing (api.py:811-814, 979-990) acceptable: only TypeError containing "no method matches" -> per-WS failure; everything else re-raises. Message coupling to pythonnet fails loud if wording changes; a genuine TypeError with that phrase would be masked (unlikely).
(3) Tests good: test_ws_path_followup.py:194,205,212; test_ensure_writing_systems.py:172,188; propagation still covered at test_ws_path_followup.py:149-171.

P0: none. P1: none.
P2:
- api.py:814 substring match brittle -- comment pinning pythonnet version or match on exception type/__cause__.
- Add a WritingSystemAndParaOptions collision-merge test (mirrors test_ws_path_followup.py:70).
- Reversal filename collision deferred to #80 (acceptable).
