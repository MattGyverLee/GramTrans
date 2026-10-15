# PR #73 cycle 2 -- lex-programmer

Commit: bb7208e on fix-ws-path-followup (pushed). Draft PR: #79 (not merged).
Worktree: D:\Github\_Projects\_LEX\GramTrans-ws-followup. flexicon resolves to D:\Github\_Projects\_LEX\flexicon.

## Files changed
- src/gramtrans/Lib/config_views.py (tag-tokenised simultaneous rewrite; scoping; dedupe; unapplied-rename drops; reversal filename rename)
- src/gramtrans/Lib/api.py (exc_info, no silent handlers, programming errors propagate, inactive-WS report entry)
- src/gramtrans/Lib/reversals.py (reason text)
- tests/unit/test_ws_path_followup.py (new)
- tests/unit/test_ws_path_fidelity.py (phase2 test imports to module level, skipif guard)
- tests/unit/test_reversal_walk.py, test_unified_dropped_channel.py, test_preview_move_ws_map_parity.py (reason text updated)

## Fix notes
1. Rewrite is text-based but tag-tokenised and quote-aware (byte-faithful elsewhere); handles `>` in values, single/double quotes. Only Option children of WritingSystemOptions plus the root writingSystem= are edited. Unapplied renames become ConfigView drops.
2. Collisions: first Option kept, enabled if either was; note recorded as ConfigView record.
3. Reversal target file renamed to <newws>.fwdictconfig; .gtbak behaviour kept.
4. Reason now "writing system '<ws>' absent in target" (empty/unmapped source ws keeps "not mapped"). Three existing tests were updated.
5. AttributeError/TypeError/NameError re-raised in the two drop-converting handlers; all swallow handlers log (debug/warning with exc_info).
6. Stored-but-inactive WS now a WritingSystem report entry ("stored but not active -- activate in FLEx and re-run"); the active-list-unreadable + Exists() fallback also emits an entry ("not verifiably active"). Caveat: that fallback can flag a WS that is actually active.
7. Done (skipif guard if host imports fail).
8. DEFERRED: DroppedItemRecord has no severity, compute_preview does not carry these records, and WS-create happens at Move time. Filed #78.

## Tests
`pytest tests/unit tests/verification -p no:randomly`: 5086 passed, 81 skipped, 14 xfailed, 0 failed.
New tests cover: swap, chain, Option outside WSO, single quotes/`>`/magic, collision, plan-level collision report, unapplied rename, reversal filename + gtbak, reason text, AttributeError/TypeError/NameError propagation, genuine failure still a drop.
Not run: live-LCM verification (no write-path to LCM changed beyond error propagation).

## Issues filed
#75 WSChoice dual-module identity; #76 drop owner/item guid inconsistency + missing dedupe; #77 lazy `from api import` fallback; #78 Preview severity plumbing (item 8).
