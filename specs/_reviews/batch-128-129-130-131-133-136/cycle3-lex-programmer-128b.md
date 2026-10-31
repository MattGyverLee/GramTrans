# Cycle 3 programmer: #128 AFFIXES-only tests (PR #154)

Worktree GramTrans-fix-128b, branch fix-128-affixes-only-test (from f8096a3). Test-only; src/ untouched.

## Added
- tests/integration/test_issue128_affixes_only_live.py (GT-Src-128 -> GT-Sandbox-128, both restored from the 07-06 backup; FLEXLIBS_REQUIRE_LIVE=1).
- tests/unit/test_issue128_affixes_only.py (2 tests: AFFIXES-only plan; latches).

## Live asserts (all passed first run, no defect, no xfail)
Plan categories == {AFFIXES}. stemA pre-seeded via a STEMS-only move; stemB and an out-of-scope stem owner never transferred.
- (a) the out-of-scope owner stays absent; C1 creates no entry.
- (b) created entries are only the two affixes; no stem entry created.
- (c) target ref components == {stemA, affix comp}; absent stemB not wired.
- (d) ref Summary runs and second-WS alternative equal the source.
- (e) C1 and C2 each called once per execute (counting wrappers). A second AFFIXES-only move plans 0 actions, calls each once, leaves the ref XML byte-identical.
Note: a live absent-owner C1 skip cannot occur (affix owners are always created first), so the absent-owner skip is covered at unit level only.

## QC P2-3 number
2 STEMS-categorised DEPENDENCY_UNRESOLVED skips of 2 total skips. They come from one absent component (stemB), reported under both ComponentLexemesRS and ShowComplexFormsInRS. They go into report.skips; `leaf_execution_failures` stayed empty. The count scales as (absent components x 2 fields) per affix ref, so it can be noisy for a large lexicon, but it does not touch the failure counter. Whether any summary tally counts report.skips as failures was not checked.

## Runs
- Full unit suite: 5421 passed, 80 skipped, 14 xfailed.
- Existing #128 live test + new live test: 2 passed. A pythonnet traceback printed at interpreter shutdown after the tests passed (not investigated).

PR: https://github.com/MattGyverLee/GramTrans/pull/154 (not merged, no issues filed).
