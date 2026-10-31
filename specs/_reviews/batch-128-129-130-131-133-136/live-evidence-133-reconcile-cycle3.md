# Issue #133 cycle 3 -- live evidence (deferred-pair reconciliation)

Branch fix-133-pos-inflfeats-single-writer (PR #152), run 2026-10-31.
Command: `FLEXLIBS_REQUIRE_LIVE=1 python -m pytest tests/integration/test_issue133_pos_inflfeats_live.py -v -s`
flexicon resolved to the editable tree: D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py
gramtrans resolved to the worktree D:\Github\_Projects\_LEX\GramTrans-fix-133\src\gramtrans.
Source (read-only): Mbugwe LizzieHC practice. Only project written: GT-Sandbox-133,
restored from "Target 2026-07-06 0218.fwbackup" before and after every test.
Result: 3 passed in 26.67s.

## Output lines (from the run log)

    [LIVE] source pairs=14 over 7 POS
    [LIVE] run1: actions=27 link_rows=14 reported_writes=14 pass_calls=1 sandbox pairs=14
    [LIVE] run2: plan.actions=0 link_rows=5 skip_rows=9 reported_writes=5 pass_calls=1
    [LIVE] run3: plan.actions=0 link_rows=0 reported_writes=0 pass_calls=1
    [LIVE] 0-action: plan.actions=0 (POS/feature creates=0) link_rows=1 reported_writes=1
    [LIVE] source pairs=14, features not in sandbox=10/10
    [LIVE] reconcile: absent pairs=14 drops=14 writes=0 features before=0 after=0

## What the new case proves (test_reconciliation_pos_only_run_reports_every_deferred_pair)

POS selected, INFLECTION_FEATURES not selected, target holds none of the 10
source features. 17 POS were created (#107 path); their 14 InflectableFeatsRC
children were deferred by enrichment. The link pass could link none, and all
14 pairs surfaced as DroppedItemRecord (field InflectableFeatsRC) in the run
report: 14 of 14, none vanished. Zero links were written to absent features.
The feature set was identical before and after (no FsFeatDefn created or
edited -- domain boundary). `_feature_guids` was validated by the seed test,
which asserts it reads >= 10 features after INFLECTION_FEATURES transfers.
