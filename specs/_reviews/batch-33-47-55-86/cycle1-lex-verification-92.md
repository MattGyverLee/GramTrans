# Verification PR #92 (closes #55) - live write path

Imports: gramtrans -> D:\Github\_Projects\_LEX\GramTrans-fix-55\src (fix) / D:\Github\_Projects\_LEX\GramTrans\src (main, aa0d36f); flexicon -> D:\Github\_Projects\_LEX\flexicon\flexicon (pip metadata 4.13.0 >= 4.8.0). FLEXLIBS_REQUIRE_LIVE=1.
Projects written: ONLY "GT055 Review Target" (restored twice from Target 2026-07-06 0218.fwbackup). Ejagham Mini opened read-only.

- A. Unit suite: PASS - 5091 passed, 81 skipped, 14 xfailed.
- B. Live (fix): PASS - 1 passed. _is_dotnet_object(multistring) True (asserted); sink "filled 1 WS slot(s)", 0 warnings; variant type 01d4fbc1..., Name@en = 'Irregularly Inflected Form' as ITsString, ws handle 999000001 (target en handle, GetWsAtOffset matched); after CloseProject+reopen value persisted.
- C. Negative control (main): PASS - identical live output (1 slot, ITsString, handle 999000001, persisted). Live write does NOT differ between main and fix; consistent with the PR's claim that the bug is latent (only duck-typed targets with failed SIL import). This live test does not exercise the fixed branch; unit tests carry that.
- D. Worktree `git status --short`: PASS - clean (empty).

Scratch test: scratchpad/batch-33-47-55-86/live55/test_issue55_review.py (TARGET_NAME and harness sys.path changed only). Pytest printed a faulthandler stack dump on stderr (.NET teardown noise); results were PASSED.
Verdict: APPROVE (live behaviour unchanged; no regression).
