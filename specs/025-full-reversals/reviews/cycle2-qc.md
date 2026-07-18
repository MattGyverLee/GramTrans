# Cycle 2 — QC review: Feature 025 P0 (reversal-category CREATE, clsid 5049)

**Date:** 2026-07-18 | **Agent:** lex-qc (read-only) | **Verdict: APPROVE — 95/100, PASS**

> Authored by the main session from lex-qc's inline report (the lex-qc subagent
> has no Write tool). Content is the QC agent's review.

Worktree: `D:/Github/_Projects/_LEX/GramTrans-025-fix-reversal-pos-create`
(branch `025-fix-reversal-pos-create`, fix commit `752a60c`).

## Pattern-audit gate — PASS
- Sweep present in the programmer artifact ("030 thesaurus dynamic-owner coverage").
- Spot-check confirmed via `reversals.py:706-777`: `_apply_pos_decision` builds a
  per-call `ReferenceFieldSpec` via `dataclasses.replace(base_spec,
  target_list_path=lambda _project, _idx=target_index: _idx.PartsOfSpeechOA)` and
  routes through the shared `apply_reference` CREATE arm, keyed only on
  `target_list.ItemClsid`. The 030 thesaurus path delegates to the SAME shared
  resolver, so the 5049 branch fires unconditionally regardless of caller — the
  programmer's "covered structurally" claim checks out.

## Correctness (references.py:1091-1105)
5049 correctly dispatches to `IPartOfSpeechFactory` via the owner-taking overload
(`factory.Create(parsed_guid, owner)`), bypassing `_add_to_owner` entirely — root
uses `ICmPossibilityList(target_list)`, child uses `parent_target_item`. Matches
the live-confirmed shape.

## Target isolation (R5)
`spec.target_list_path(target)` (line 1012) is always the per-index closure built in
`reversals.py:776` (`_idx.PartsOfSpeechOA`), never `LangProject.PartsOfSpeechOA`.

## Never-silent
Unmapped clsid still raises `UnmappedItemClassError` (1064-1079), untouched. No new
silent branches.

## Consistency (P2, no action this cycle)
The `if item_clsid == 5049` special-case (line 1091) is a bolted-on branch rather than
a generalized "owner-taking vs create-then-add" dispatch table, but the comment at
1042-1053 makes the divergence explicit and justified (no 1-arg overload exists for
`IPartOfSpeechFactory`). Acceptable for a P0 hotfix; worth a follow-up ticket if a
third owner-taking clsid ever appears.

## Test quality
`test_create_path_reversal_category_hierarchical_owner_taking_factory`
(`test_reference_create_paths.py:512-591`) is strong: `_FakeIPartOfSpeechFactoryOwnerOnly.Create`
(478-491) genuinely raises `TypeError` on a 1-arg call, so the test is RED against BOTH
the "no map entry" and "map entry but still 1-arg call" half-fixes. Asserts positive
placement (index's own list) AND negative (untouched separate `_FakeLangProjectPOSList`,
both clsid 5049, line 577) — a genuinely restrictive R5 regression guard.

## Issues
- P2: 5049 special-case is hand-rolled rather than table-driven (see above) — no action.
- No P0/P1 issues found.

**Recommendation: APPROVE.**
