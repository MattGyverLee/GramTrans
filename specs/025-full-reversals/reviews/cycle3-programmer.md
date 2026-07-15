# Cycle 3 — Programmer report: US2 reversal-category resolution (T021-T027)

**Commit:** `d84fc0b` on branch `025-full-reversals`, worktree
`D:\Github\_Projects\_LEX\GramTrans-025-full-reversals` (parent `48b2d75`).

**Files touched (absolute worktree paths):**
- `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\src\gramtrans\Lib\reversals.py`
- `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\tests\unit\test_reversal_category_resolve.py`

## RED evidence

Stashed only `reversals.py` (keeping the new test file) and ran
`pytest tests/unit/test_reversal_category_resolve.py -q` against the US1
`_resolve_reversal_category_link_if_present` stub:

```
FAILED test_create_path_returns_ancestor_chain_top_down_guids_preserved
FAILED test_diverged_custom_returns_update_non_destructive
FAILED test_diverged_protected_reports_dropped_and_links_existing
FAILED test_absent_category_list_on_existing_index_reports_dropped
FAILED test_absent_category_list_when_target_index_not_yet_created
FAILED test_shared_reversal_category_created_at_most_once_across_entries
6 failed, 1 passed in 0.35s
```

`test_target_list_binds_to_index_never_to_lang_project` (the T021 LINK case)
passed even under the stub — expected, since the US1 stub's own LINK-if-present
logic already reads `target_index_ref.PartsOfSpeechOA` correctly and never
touches `LangProject`. It still locks a real invariant (the R5 tripwire) and
is kept; the other 6 are the genuinely discriminating RED evidence for
CREATE/UPDATE/REPORT_DROPPED/caching, which the stub never implemented.

## T025/T026/T027 as-built

### T025 — `_decide_reversal_category` (replaces `_resolve_reversal_category_link_if_present`)
- Guard: `target_index_ref is None` OR `target_index_ref.PartsOfSpeechOA is None`
  both collapse to one hand-built `REPORT_DROPPED` with reason exactly
  `"target reversal category list absent"` (bypassing `decide_reference`
  entirely for this case, since calling it with a `None` index would crash
  in the spec's own lambda, and calling it with a present-but-empty-list index
  would instead produce 024's more generic `"target list absent"` reason).
- Every other case delegates wholesale to `references.decide_reference(src_pos,
  target_index_ref, spec, resolver_cache, source=None)` using
  `REVERSAL_FIELD_MAP["PartOfSpeechRA"].reference_spec` unchanged (per the
  "reuse it, don't build a second spec" instruction).
- Every dropped record (the guard's own, or one unpacked from
  `decision.dropped`) is enriched with the real `ReversalIndexEntry` identity
  (`owner_guid` = the entry's own GUID, `owner_label` = the entry's own
  `ReversalForm` text via a new `_entry_label_from_form_alts` helper) before
  being appended to the shared `dropped` collector.

**Deviation from the literal task text — `source=None`, not `source=src_project`:**
Threading a real source-project resolver into `decide_reference` while its
own `target` argument is index-shaped (no `.WritingSystems`) breaks identical-
content detection outright: `_fields_identical` builds the source-side
fingerprint in the genuinely Id-keyed shape (`((ws_id, text),)` tuples) but
the target-side falls back to the positional no-resolver shape (`(text,)`
tuples) — two structurally different tuple shapes that can never compare
equal, so LINK becomes unreachable and every identical-content case
spuriously resolves to UPDATE. Confirmed empirically: the first draft of
T021's test (with `source=src_project` threaded) failed with
`action == UPDATE` instead of `LINK` for byte-identical Name/Abbreviation
content. Fix: call `decide_reference(..., source=None)` for this field only,
keeping both sides on the same (less WS-sophisticated, but symmetric and
correct) positional fallback. Documented in-line in
`_decide_reversal_category`'s docstring under a "DEVIATION" heading.

### T026 — `_apply_pos_decision` (replaces the US1 LINK-only block in `_apply_one_entry`)
- Routes `decision.pos_decision` through `references.apply_reference`,
  passing the shared `resolver_cache` so CREATE's ancestor loop's own
  `cache.get(anc_guid) or _find_in_possibility_list(...)` check (024,
  unchanged) is what actually guarantees a shared reversal category is
  CREATEd at most once — no reversal-specific cache logic was added.
- `target_index` is now resolved **unconditionally** in `_apply_one_entry`
  (previously only for top-level entries) via the existing
  `_ensure_target_index` per-run cache, so a sub-entry's own `PartOfSpeechRA`
  resolves against the SAME per-index list its top-level ancestor already
  created/found — idempotent (cheap cache hit for every sub-entry after the
  first `_ensure_target_index` call in the tree).
- Any raw (`owner_guid=""`) `DroppedItemRecord` `apply_reference` appends via
  its own `dropped=` collector (the "source WS absent in target" case during
  UPDATE/CREATE), or one carried by `UnmappedItemClassError`, is captured via
  a before/after `len(dropped)` diff and enriched with the real entry
  identity — mirrors `categories._call_apply_reference`'s posture exactly.
- `protection._is_protected` is **not** called directly anywhere in
  `reversals.py` — it is used internally by `references.decide_reference`
  only, per the task's explicit "do not reimplement" instruction.

**Deviation from the literal task text — `target=target_project`, not
`target=target_index`, via a per-call `ReferenceFieldSpec`:**
`apply_reference`'s UPDATE arm reads `target.PossibilityLists`; its CREATE
arm reads `target.Cache` and `target.GetFactory(...)`. Checked against
`flexicon`'s own source: `GetFactory` is defined only on `FLExProject`
(`flexicon/code/FLExProject.py:315`), and `BaseOperations.__init__` stores
`self.project = project`, i.e. `PossibilityLists`' own WS-resolution helper
(`_resolve_target_ws_by_id`) is only reachable via a project handle. A bare
`IReversalIndex` object has neither `.PossibilityLists` nor `.GetFactory` —
passing `target=target_index` (literally matching the contract's
`target_list_path` wording) would make `apply_reference` raise
`AttributeError` inside its CREATE/UPDATE arms, caught by
`_apply_pos_decision`'s own fail-soft wrapper, silently turning **every**
CREATE/UPDATE into a total no-op in production (not even the LINK `setattr`
would be reached). Fix: pass `target=target_project` (`_apply_one_entry`'s
own `target` parameter — the real FLExProject), and build a per-call
`ReferenceFieldSpec` via `dataclasses.replace` off the static
`REVERSAL_FIELD_MAP["PartOfSpeechRA"].reference_spec`, overriding only
`target_list_path` to close over the already-resolved `target_index`
(ignoring whatever `apply_reference` itself passes as `target`). The
possibility list actually read/written is unchanged
(`target_index.PartsOfSpeechOA` — R5's "never touch `LangProject.
PartsOfSpeechOA`" guarantee holds); only the *signal value* threaded through
`apply_reference`'s own `target` parameter changes. LINK and REPORT_DROPPED
never read `target` inside `apply_reference` at all, so they are unaffected
either way. Documented in-line in `_apply_pos_decision`'s docstring under a
"DEVIATION" heading, including the exact flexicon source citation.

This also fixes `source=` threading on the apply side: with `target` now a
real project, `source=getattr(ctx, "source_handle", None)` gives
`apply_reference`'s UPDATE/CREATE arms a genuine per-project WS resolver for
Id-keyed multistring props (unlike the decide-side deviation above, this one
is symmetric and correct because BOTH `source` and `target` are now real
projects).

### T027 — unified reporting
No separate reversal report section was added — every `DroppedItemRecord`
this cycle produces (the plan-side guard/divergence records, and the
apply-side raw records) flows into the SAME `dropped` list threaded through
`plan_reversal_decisions`/`reproduce_reversal_entries`
(`Lib/categories.py`), which was already wired into `RunPlan.dropped_items`
in US1 (T018/T019) — confirmed by reading `Lib/preview.py`'s
`build_run_plan`/`render_reversal_decisions`, which explicitly documents
"Reversal `DroppedItemRecord`s are deliberately NOT duplicated here... they
already flow through the single unified 024 channel." No changes to
`preview.py` were needed or made.

## Caching test design note (T024's second half)

The plan-time-only half of T024 (absent-list + REPORT_DROPPED reason text)
is tested directly against `plan_reversals`. The "created at most once"
half is inherently an **apply-time** guarantee (decide-time alone never
populates the cache — only `apply_reference`'s CREATE arm does,
via `cache[anc_guid] = new_obj`), so it is tested by hand-building two
`ReversalDecision` objects that share one CREATE `ReferenceDecision` (same
ancestor GUID) and calling `apply_reversals` on both against one shared
`resolver_cache`, with a fake `SIL.LCModel`/`System` module injected
(verbatim monkeypatch pattern borrowed from
`test_reference_create_paths.py`). Assertion: the fake factory's `.Create`
is called exactly once, and both target entries end up with the identical
`PartOfSpeechRA` object.

## Final test counts

- `tests/unit/test_reversal_category_resolve.py`: **7 passed**.
- `tests/unit/test_reversal_walk.py` (US1, unmodified): 5 passed — no
  regression.
- `tests/unit/test_reference_resolver.py` +
  `test_reference_create_paths.py` + `test_reference_ws_resolution.py` +
  `test_reference_ws_keying.py` (024, unmodified): all pass alongside the
  above (34 total across these 6 files).
- Full suite (`python -m pytest tests/unit -q`): **1483 passed, 10 skipped,
  14 xfailed, 14 xpassed, 1 failed**. The 1 failure is
  `test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::
  test_plan_emits_pos_action_for_picked_pos` — confirmed via `git stash` to
  fail identically on the pre-change tree (parent commit `48b2d75`), i.e.
  the same pre-existing baseline failure noted in the cycle-2 handoff. No
  new failures anywhere in the suite.

## Scope adherence

US2 only. `config_views.py` (US3), Polish (T034-T037), and `Lib/ui/*` were
not touched. `test_reversal_walk.py` was not modified (still green,
untouched). The only files changed are `Lib/reversals.py` and the new
`tests/unit/test_reversal_category_resolve.py`.
