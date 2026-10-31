# cycle1-lex-qc-146: PR #160 (issue #146), head e5ea12e

> Saved by the main session verbatim from the lex-qc hand-back (that agent had no Write/Bash tool; static read of worktree
> files, no tests or `git diff` run).

**Score: 72/100. Recommendation: FIX ISSUES (one P1) before merge.**

## Findings

**P1: the sweep missed a plan-carried decision consumer.**
- `wordforms.resolve_or_report_category` (wordforms.py:507-544) calls `decide_reference` on the marked Preview cache.
- Reached from texts.py:593 `plan_analyses`, which receives Preview's `_resolver_cache` (preview.py:1622).
- The first analysis with an absent POS gets CREATE, downgraded to REPORT_DROPPED -- but `decide_reference` has already
  primed `PlannedCreate(POS)` in the cache.
- Every later analysis with the same POS gets LINK with `target_item=None`, returned with no DroppedItemRecord
  (wordforms.py:542-544).
- Move's `_apply_category` (wordforms.py:1058-1063) then does nothing (`target_item` None, action LINK).
- Before this PR each such analysis produced a REPORT_DROPPED plus a drop record; now only the first does, so drops are
  undercounted in Preview and the Move report. Breaks Principle I (never silent) and Preview/Move parity.
- Move's data outcome is unchanged (category stays unset either way); the loss is in reporting.
- impl-146 item 10 says only texts.py:926 and 973 apply Preview-built decisions; wordforms.py:1058 is a third, unrebound.
- Fix: in `resolve_or_report_category`, treat a LINK with `target_item=None` (planned create) like CREATE and emit
  REPORT_DROPPED with a drop record -- or call `decide_reference` there on a throwaway copy of the cache. Add a unit test.

**P2: texts.py:976-977.** `rebind_planned_link` is wrapped in `_safe(...) or decision`; if the rebind raises, the code falls
back to the placeholder LINK with `target_item=None`, `apply_reference` no-ops, `possibility` stays None and the loop
`continue`s (984-985) with no drop record. Same swallow in `_apply_genres` (927-931; `_safe` logs at debug only). Emit a
DroppedItemRecord on rebind failure.

**P2: xfail guard in the live test.** Keyed on whether the fixture's `Texts.GetGenre(texts[0])` probe raises (live test
332-335, 413-422), not the exception text as impl-146 says; imperative `pytest.xfail`, so never XPASS. If #161 is fixed
GramTrans-side (reading `IText.GenresRC` directly), `GetGenre` still raises and the test stays xfailed, leaving the rebind
path untested live. Probe what `texts._decide_genres` actually calls, or use `@pytest.mark.xfail(strict=True)`.

**P2: tests miss a rebind exception, and the wordforms path has no test.** See answers 3 and 7.

## Answers

**1. Move consumers of plan-carried decisions.**
- Re-decided in the same Move pass (unaffected): categories.py:6721 (via `_call_apply_reference`), 6951, 8971; owned.py:428,
  611; reversals.py:935 (Move recomputes the plan on its own unmarked cache, transfer.py:1083).
- Rebound via `rebind_planned_link`: texts.py:927-928 (genres), 976-978 (tags).
- NOT rebound: wordforms.py:1054-1063 (P1).
- `.target_item` reads outside references.py: texts.py:983 (segment-tag fallback, after the rebind); wordforms.py:1058.
- apply_reference's LINK and REPORT_DROPPED arms (references.py:1029-1043) tolerate a None `target_item` as a silent no-op --
  the exact failure mode for any missed consumer.

**2. Unmarked-cache invariant: holds.** Move creates a fresh `{}` at transfer.py:488, attached to `exec_ctx` at 742, passed at
643, 1049, 1068, 1083. `mark_planning_cache` is called only at preview.py:1318. No other marking found;
`categories._get_resolver_cache` only reads `context._resolver_cache`. Not enforced by an assert -- a one-line guard in
`apply_reference` (raise if the cache is marked) would make a future leak loud.

**3. Failed first CREATE in Move.** `rebind_planned_link` (references.py:754-767) re-runs `decide_reference` on Move's cache;
a failed create never caches, so it returns CREATE again -- correct. `test_rebind_planned_link_resolves_against_move_cache`
(line 356) covers hit->LINK and miss->CREATE. Not covered: the rebind itself raising (P2).

**4. Order dependence.** Within an entry (senses, allomorphs) the live test asserts first-is-CREATE. Possible divergence: a
POS / inflection feature created by a separate category action (out of scope per impl-146); entry order differing between
the Preview plan walk and Move's leaf dispatch; shared items across entries when Move's dispatch is not in plan order. Texts:
Preview plans last (preview.py:1622), Move applies after the lexical leg (transfer.py:1066) -- consistent; genre and tag
lists are disjoint. Move not caching UPDATE (noted in impl-146) is a separate defect.

**5. `_apply_segment_tags` fallback.** texts.py:983 reads `decision.target_item` after the rebind. Silent no-op only when:
the rebind raised; the rebound decision is CREATE and apply failed (presumably drops elsewhere); REPORT_DROPPED (reported at
plan time). Residual hole: rebind-raises (P2).

**6. Site #9 (preview.py:336-364, `_overwrite_reference_decisions` passes `resolver_cache={}`).** Follow-up, not P1: the
cache is unmarked, so no placeholder leaks; behaviour is the pre-#146 over-reporting. Fixing needs a RunContext threaded
through 3 call sites (3552, 3576, 3590) in a file other open PRs edit. Gate it on the P1 above.

**7. Test quality.** Negative controls are real: distinct items -> CREATE, CREATE (line 89); distinct files -> 2 picture
copies (221); unmarked cache stays CREATE and empty (77); msenv negative control. impl-146 reports 11 of the first 15 tests
fail without the src fix and the texts test fails without the texts.py change (not re-run). Gaps: wordforms category (P1),
rebind exception, Move-apply-asserts-unmarked-cache. Live genre xfail not robust to a GramTrans-side fix.

## Follow-up issue proposals (not filed)
1. Wordforms category: planned-create LINK with `target_item=None` loses the drop record -- the P1; fix in this PR.
2. `references.apply_reference` should raise or log loudly on a LINK with None `target_item` from a Preview decision, and on
   a marked cache.
3. Preview `_overwrite_reference_decisions` run-wide cache (site #9).
4. flexicon `Texts.GetGenre` raises on `FirstOrDefault` and `_decide_genres` swallows it (#161): GramTrans fallback to
   `GenresRC` plus a DroppedItemRecord; make the live xfail strict and keyed to it.
5. Make the `rebind_planned_link` failure path in texts.py report a drop.

**Reviewed by:** QC Agent.
