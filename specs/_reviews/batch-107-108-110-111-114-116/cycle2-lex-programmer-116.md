# Cycle 2 programmer report: #116 (PR #123)

Merged origin/main (merge commit 5f10754, no conflicts). Never rebased/force-pushed.

Diff:
- src/gramtrans/Lib/categories.py `_thesaurus_new_ancestors` (~8485-8520): whole body now inside try; on any error returns () and logs a warning (gramtrans.Lib.categories). Docstring's "never raises" is now true.
- src/gramtrans/Lib/preview.py `render_sense_list_reference_decisions`: docstring note plus a pane footer line (only when a Create row exists): "Later references to an item created earlier in this run show as create; Move links them." Resolver cache not primed. No other user-facing doc for the pane found.
- Row cap left as follow-up.
- tests/unit/test_issue116_preview_sense_list_decisions.py: new test_new_ancestors_never_raises_when_lookup_raises (raising cache probe: Move still reaches apply_reference, new_ancestors == (); raising lookup returns ()); render test updated for footer line.

Validation:
- flexicon resolves to D:\Github\_Projects\_LEX\flexicon.
- tests/unit: 5305 passed, 80 skipped, 14 xfailed. Census: no separate census test target found in tests; unit suite includes census-related tests, all green.
- Live (FLEXLIBS_REQUIRE_LIVE=1, GT42_TARGET_NAME=GT-Sandbox-116) test_issue42_appendix_thesaurus_live.py: 8 passed, 1 xfailed (strict). A pytest-exit traceback printed after the summary (interpreter shutdown), result lines are clean.
- GT-Src-42 was snapshotted first; the live run modified it (GT-Src-42.bak differed), so it was restored from the snapshot; diff -r confirms byte-identical.

New HEAD: e518a9b (pushed to origin/fix-116-preview-create-link).
