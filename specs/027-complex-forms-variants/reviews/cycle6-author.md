# Cycle 6 — lex-author (original-intent / integration-consistency) review

**Feature:** 027 Complex Forms & Variants · **Gate:** T027 merge · **HEAD:** worktree `34be1ad`
**Score: 8/10 — CONCERNS, not merge-blocking**

> Note: this report was authored by the main session on behalf of lex-author, which
> lacked a Write tool in its session and returned findings inline.

## Verified compliant

1. **Target-resolution + cast idiom (issue #28 layers 1+2).** Every new C1/C2/C3/17.1
   site in `Lib/categories.py` routes through `_resolve_target_by_guid`
   ([categories.py:5249](../../../../GramTrans-027-complex-forms-variants/src/gramtrans/Lib/categories.py#L5249))
   then `_cast_lcm` ([categories.py:5281](../../../../GramTrans-027-complex-forms-variants/src/gramtrans/Lib/categories.py#L5281)).
   No direct `get_object_by_guid` / live-object bypass. The fake-repo fallback path is
   exercised by `_FakeLiveTarget` (no `get_object_by_guid`) in
   `tests/unit/test_027_entryref_reproduction.py:425`.
2. **024 reuse surface.** Container ownership uses `_safe_add_to_owner`
   (`categories.py:5140`) for the new `EntryRefsOS` add — no inline `Add`+raise.
   Entry-type resolution routes through the shared
   `_apply_reference_fields`/`decide_reference`/`apply_reference` resolver
   (`categories.py:5162`), not a bespoke path — the **P1-DRY fold from da06a5c held**.
3. **STEMS-tail ordering.** `_run_tail_once` (`categories.py:5392`) gates
   `_run_entryref_create_pass` then `_run_post_pass_a` to fire exactly once, on the
   *last* STEMS action — all closure entries exist first. Correct.

## Top concern (design-consistency, follow-up)

**Preview/Move lockstep is broken for the new C3 sub-pass specifically.**
`_run_entryref_create_pass` (`categories.py:5026`, called only from
`stems_execute_action` at `categories.py:5916`) both creates `LexEntryRef` containers
**and** resolves `VariantEntryTypesRS`/`ComplexEntryTypesRS`/`ShowComplexFormsInRS`
via `_apply_reference_fields` — but there is **no Preview-mode decide-only twin**,
unlike every other pass in this file
(`_decide_reference_fields`/`_apply_reference_fields`,
`plan_all_lexical_relations`/`reproduce_all_lexical_relations`,
`config_views.plan_config_views`/`apply_config_views`). `preview.py` only gathers
`entryref_create_bindings` read-only (lines 173-179) but never *decides* them, so any
CREATE of a novel EntryType/Publication item — or any REPORT_DROPPED — made by C3 is
invisible to the user until after Move has already written it.

- **Not a correctness bug:** Move itself is correct and idempotent.
- **Is a Principle III consistency gap:** narrower "preview shows everything before
  write" coverage than the rest of the codebase enforces.
- **Recommendation:** post-merge follow-up task to add a C3 Preview decide-only twin
  (mirror the `_decide_reference_fields`/`_apply_reference_fields` split the rest of
  the module uses), so C3's entry-type CREATE/REPORT decisions surface in Preview.
