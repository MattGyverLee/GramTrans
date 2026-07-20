# Cycle 3 Verification — full-copy-engine-defects (offline)

**Status:** PASS

## Targeted tests
`pytest tests/unit/test_texts_fullcopy_defects.py tests/unit/test_text_structure_walk.py tests/unit/test_text_markup_tags.py tests/unit/test_owned_object_walk.py tests/verification/fidelity_census.py -q`
→ **148 passed, 0 failed** (worktree `fullcopy-defects`, commits 844f465 + aeab54b).

## Full offline suite
`pytest tests/ -q`:
- Worktree: **27 failed, 1970 passed**, 72 skipped, 14 xfailed, 14 xpassed.
- `main` (same command, same commit set minus these two): **27 failed, 1961 passed**, identical skip/xfail/xpass counts.
- The 27 failing test IDs are byte-identical between worktree and main (test_029_picture_asset_copy×3, test_029_sense_picture_reproduction×2, test_adjacent_data×6, test_analysis_idempotency×3, **test_analysis_verdict×1**, test_human_eval_gate×5, test_morph_bundle_wiring×4, test_residue_tagging_026×2, test_segment_alignment×1, test_wizard_pos_grammar_wiring×1). Note: the task's cited bucket list omits `test_analysis_verdict.py::test_approve_and_deny_verdicts_reproduced`, but it is pre-existing on `main` too — not a regression, just an omission in the cited list.
- **Zero new failures.** The +9 pass delta (1970 vs 1961) is exactly the new/rewritten unit tests (8 in `test_texts_fullcopy_defects.py` + 1 net from the `test_owned_object_walk.py` Case‑1 rewrite).

## Fix-guards confirmed (via diff of commit 844f465/aeab54b, reasoning from old code)
1. **FIX1** (`test_resolve_or_create_reuses_existing_text_on_name_collision`): pre-fix code called `text_ops.Create(plan.title or "(untitled)", None)` unconditionally; `FakeTextOps.Create` raises on a name collision → old code would return `None` + a "text create failed" drop, failing the test's `result is existing` / `dropped == []` assertions. Guard confirmed.
2. **FIX2** (`test_untitled_text_matches_existing_target_by_fingerprint`): pre-fix `_text_disposition` gated the title fallback on `find is not None and title` with no fingerprint branch at all — an empty title fell straight through to `CREATE, None`. Test asserts `UPDATE` + `target_guid == "tgt-diff-guid"`; fails without the fix. Guard confirmed.
3. **FIX3** (`test_blank_paragraph_reports_distinct_reason_when_raw_create_unavailable`): pre-fix `_create_paragraph` did not exist — the loop called `para_ops.Create(target_text, "", ws_handle)` directly. `FakeParagraphOps.Create` doesn't raise on empty content, so old code would push `("para", "")` into `target.Paragraphs.created`, violating the test's explicit `("para", "") not in target.Paragraphs.created` assertion. Guard confirmed.
4. **owned.py finding #3** (`test_owned_object_walk.py`, rewritten Case 1): now a negative fixture asserting `ICmTranslationFactory`/`_FakeTranslationFactory` is never invoked and `TranslationsOC` stays empty — directly proves the deleted `OWNED_OBJECT_MAP` row is gone and not silently re-added.

## `scratchpad/run_fullcopy_live.py` per-category wiring (static read only, not executed)
`_summarize()` reads `report.per_category` as `dict[GrammarCategory, CategoryReport]` via `.added`/`.skipped` attrs and derives keys via `getattr(cat, "name", ...)`. Confirmed against `Lib/report.py:130-160` (`per_category_final` construction) and `Lib/models.py:1395-1420` (FR-018 invariant) — the shape matches exactly. The per-category JSON breakdown (`{"TEXTS": {"added": N, "skipped": N}, ...}`) plus `plan_report_gaps`/`dropped_breakdown` will populate correctly when a human runs it live; wiring is correct.

## Recommendation
APPROVE. No blockers. One documentation nit: cycle-plan text listing pre-existing failure buckets should add `test_analysis_verdict.py` to stay accurate (cosmetic only).
