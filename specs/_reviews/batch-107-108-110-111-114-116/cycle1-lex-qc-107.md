# cycle1-lex-qc-107 (PR #125, HEAD f0bd7bb)

> Saved by the main session: lex-qc has no Write tool and returned this text verbatim.

Score 84/100. Verdict: FIX-ISSUES (minor).

Gates: pattern-audit PASS (sweep present). Live-LCM PASS for the #87 repro (pre/post object diffs plus a mutation check); the #31 assertion is unrun.

1. A shell POS with only a Warning is not acceptable under the never-silent rule. **P1**, transfer.py:811-821 and 3408. The exception path and the source-not-found path bypass `dropped`, so run 1 leaves a shell POS with nothing in the run report. That is the #107 symptom. Add a `DroppedItemRecord` or Skip with detail per failed collection, and keep the POS create successful.
2. Deferral is identical. Both call `_enrich_one_collection` with the same `_planned_action_guids`, built at line 491 from plan.actions. Same matcher, same GUID-preserving create, so no double-create. **P2**: the source lookup is an O(n) scan per created POS.
3. Merge risk with #120 is low to medium. The new test is appended at the end, but the "Deliberately NOT asserted" note (lines 31-34) now contradicts it. **P1**: update the note in this PR, or have whichever PR merges last do it, and merge the docstring editor last. The new test's live run on Ngoreme is pending, so the #31 claim is unproven.
4. The zero-diff rewrite of test_issue87 is intended and only slightly brittle. It turns the residue allowlist into a hard idempotency contract. **P2**: keep an empty, named, issue-referenced exclusion hook so unrelated #87 churn does not fail #107. Also guard `GT_ISSUE87_TARGET` to sandbox names only.
5. The HIGH sibling at categories.py:17161 is plausible but I could not confirm it. `_resolve_rule_rc_item` resolves `InputPOSesRC` against the target's `pos_by_guid`, so a POS that does not exist yet returns None and goes to `_report_dropped_rule_ref`. That is a recorded drop, not a silent one. I could not confirm that PHONOLOGICAL_RULES runs before GRAM_CATEGORIES (no ordering constant found by grep). **P2**: file it as a separate issue.

Other findings:
- **P1**: impl-107.md section 4.1 documents a Principle III preview-visibility gap. Children of a created POS are written without appearing in the Preview plan. Track it as an issue; it does not block this PR.
- **P2**: impl-107.md sections 4.4 and 4.5 list two follow-ups. A sub-POS without its own action gets scalars only, and a template created by enrichment has no slot references.
