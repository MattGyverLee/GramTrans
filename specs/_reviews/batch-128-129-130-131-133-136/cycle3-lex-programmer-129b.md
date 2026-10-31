# Cycle 3 programmer report: #129 follow-up (fallback relocation)

PR: https://github.com/MattGyverLee/GramTrans/pull/158 (not merged)
Branch: fix-129-fallback-relocation, worktree D:/Github/_Projects/_LEX/GramTrans-fix-129b
Head SHA: d88dc4a764bb58ee7be49b8af284e758bfe3764b (base f8096a3)

## Implemented (src/gramtrans/Lib/references.py)
1. All source WSs absent + fallback writes: per-WS drops replaced by ONE record whose reason starts "relocated:" (source WS X -> target default analysis WS Y).
2. Best alt's source WS is vernacular (via source.WritingSystems.GetVernacular()), or the vernacular set cannot be read: fallback skipped, plain drops kept, field empty.
3. Y = target default analysis WS via ops.project.GetDefaultAnalysisWSHandle() mapped through target_ws_by_id. Unresolvable -> skip, keep drops. `_wrap_plain_text` no longer falls back to first dict entry (new helper `_default_analysis_ws_id`).
4. Legacy `source is None` branch: ruling 3 applies (via `_wrap_plain_text`). Rulings 1-2 cannot: no source WS identity, and no per-WS drops are recorded there. Documented in a comment.
5. P2-4: owner_guid/owner_label filled (new `_owner_ids(owner_obj)`) on the drop/relocated records and the ApplySyncableProperties-failure record.

Tooling: FLExToolsMCP not used; read flexicon source directly (WritingSystemOperations.GetVernacular, FLExProject.GetDefaultAnalysisWSHandle).

## Tests
tests/unit/test_issue129_create_arm_multistring.py: +6 tests (relocated, vernacular-skip, unresolvable-default-skip, unknown-vernacular-skip, no-first-entry wrap, owner on failure record). 11 pass there.

Unit suite: 5425 passed / 80 skipped / 14 xfailed. Measured main f8096a3 baseline = 5419/80/14 (the "5411" figure was ee365b3); delta is exactly +6 new tests.

Live (FLEXLIBS_REQUIRE_LIVE=1, GT42_TARGET_NAME=GT-Sandbox-129): GT-Sandbox-129 explicitly restored from "Target 2026-07-06 0218.fwbackup" first (the module also rebuilds it from the GT-Src-42 fork and restores at teardown). Result: 9 passed, no xfail. A pytest/pythonnet traceback dump appeared at interpreter exit only; result line was clean. Only GT-Sandbox-129 and the harness-managed GT-Src-42 were written.

No live case added for the relocation record: the existing fixture only has default-analysis names, so it never hits the all-WS-absent path.

## Follow-up candidates (not filed)
- Live fixture with a source-only analysis WS to exercise the relocated: record end to end.
- Dedup key (owner_guid, field_name, item_guid) excludes reason: a relocated record for Name can collapse with a drop for Abbreviation/Description on the same item (same field_name = ThesaurusItemsRC). Consider including the item field in the key or reason.
- Report rendering: surface "relocated:" records separately from losses.
- Other `owner_guid=""` sites in references.py (lines ~724, 779, 1025, 1120, 1599) still empty.
- The UPDATE arm and legacy branch cannot classify vernacular without source WS identity.
