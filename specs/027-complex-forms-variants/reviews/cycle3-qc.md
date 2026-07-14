# QC Report — Cycle 3, Feature 027 (Complex Forms & Variants) US2/US3

**Date:** 2026-07-13
**Quality Score:** 83/100
**Status:** ⚠️ CONDITIONAL (two P1 findings — neither breaks runtime correctness for the
happy path, but both undercut this feature's own "never-silent" audit guarantee)

> NOTE: persisted by the main session on behalf of lex-qc (this agent's toolset was
> Read/Grep/Glob only and could not write — same situation as cycle-2). Body verbatim
> from the cycle-3 QC run against worktree `027-complex-forms-variants` @ `da06a5c`.
> `git show` was unavailable (no Bash tool); review conducted by reading the worktree
> files directly plus cross-referencing the associated test files, `research.md`, and
> `tests/verification/fidelity_census.py`.

## 1. C3 three-way disposition (T015) — PASS

`_run_entryref_create_pass` (`categories.py:5026-5168`) routes `VariantEntryTypesRS`
(RefType==0 only), `ComplexEntryTypesRS` (RefType==1 only, `type_skip` set correctly at
5152-5156), and `ShowComplexFormsInRS` (always, never gated on RefType) through the
generic `_apply_reference_fields("LexEntryRef", type_src, new_ref_typed, ...)` dispatch
(5162-5166), which in turn calls `references.decide_reference`/`apply_reference` per
`references.field_specs_for("LexEntryRef")` — the 3 new rows added at
`references.py:189-209`. All four dispositions are correctly wired and independently
proven against the real production entry point (`categories._run_entryref_create_pass`,
not just `decide_reference`/`apply_reference` in isolation) by
`tests/unit/test_027_entry_type_resolve.py`:
- absent → CREATE incl. ancestor chain, GUID preserved
  (`test_absent_variant_type_creates_with_guid_preserved`, references.py:1070-1169)
- diverged custom → UPDATE, links same object, no duplicate
  (`test_diverged_custom_variant_type_updates_and_links_same_object`)
- diverged shared/GOLD → LINK existing + exactly 1 `DroppedItemRecord`, source never
  overwrites the existing item's Name
  (`test_diverged_shared_gold_variant_type_links_and_reports`)
- identical → LINK only, 0 creates, 0 drops
  (`test_identical_variant_type_links_only_no_create_no_report`)

RefType routing (`test_complex_form_ref_resolves_complex_types_not_variant_types`) and
the "always resolves" ShowComplexFormsInRS case
(`test_show_complex_forms_in_always_resolves_regardless_of_ref_type`) are both covered.
Concept↔GUID identity is preserved end-to-end: created items carry the source's own
GUID (`references.py:1076-1077`, `DotNetGuid.Parse(anc_guid)` then
`factory.Create(parsed_guid)`), and existing-target lookup is by GUID equality
(`_find_in_possibility_list`, references.py:609-629). Unresolved cases (target list
absent, unmapped `ItemClsid`) correctly degrade to `DroppedItemRecord` rather than
raising (references.py:696-710, 1048-1065), never silently.

## 2. Principle-I GOLD GUID-remap (T014) — PASS, genuinely enforced (not just tested)

Verified the invariant is enforced in production code, not merely asserted by the test:
- CREATE path (`apply_reference`'s CREATE arm, references.py:1008-1169) never consults
  `IsProtected` at all — it always parses and reuses the ancestor's own source GUID
  (`_guid_str(anc)` → `DotNetGuid.Parse` → `factory.Create(parsed_guid)`), so a
  GOLD/reserved item absent from target is created with its GUID preserved
  unconditionally, matching `test_gold_reserved_entry_type_guid_remapped_at_creation`
  (test_027_entry_type_resolve.py:447-466).
- LINK-never-overwrite path: `decide_reference`'s diverged branch
  (references.py:738-768) checks `protection._is_protected(target_item)` — a
  diverged+protected item is LINKed to the SAME existing object (never mutated) plus
  exactly one `DroppedItemRecord`; a diverged+non-protected (custom) item is UPDATEd.
  `apply_reference`'s LINK/REPORT_DROPPED arms (890-904) only `setattr`, never touch
  the existing item's own fields. Matches
  `test_gold_reserved_existing_target_item_linked_never_overwritten`
  (test_027_entry_type_resolve.py:469-493), which explicitly asserts the pre-existing
  GOLD object's `Name` is untouched after a diverged-source Move.

## 3. C4 drop-policy flip (T020) — PASS, double-bookkeeping correctly cleared

`_report_dropped_entry_refs` (categories.py:4420-4451) now reports a `LexEntryRef` only
when `_entry_ref_is_reproducible(ref)` is False (categories.py:4410-4417) — i.e. at
least one Component/PrimaryLexemesRS member fails `_affix_type_of(m)[0]`. A ref whose
members are ALL STEMS/AFFIXES-eligible is silently skipped here because C1/C2 will
reproduce it; a ref with 0 components/primaries is trivially "reproducible." Entry-type
divergence/unresolved-item reporting for C3 is explicitly NOT this function's concern
(comment at categories.py:4362-4366) — that's reported once, independently, by
`_apply_reference_fields`'s own dropped-record path inside `_run_entryref_create_pass`,
so no double-booking between the two mechanisms. Called identically (same two
positional args, `src_entry, dropped`) from both `_walk_lex_entry_closure` (Move,
categories.py:4612) and `_plan_entry_reference_decisions` (Preview,
categories.py:3620). Move/Preview parity for the flipped policy is explicitly proven
by `test_move_and_preview_drop_sets_identical_under_new_policy`
(tests/unit/test_027_never_silent.py:229-253), and the flip itself by
`test_in_closure_ref_yields_zero_dropped_records` /
`test_mixed_refs_report_only_the_out_of_closure_one` (same file). Order-independence
(the create-then-wire tail runs once, after the full closure walk) is correctly handled
by using a static intrinsic-eligibility predicate rather than an "already on target"
check — this is a deliberate, well-reasoned design choice (see P1 finding below for its
one real edge case).

## 4. P1 DRY fold (`_safe_add_to_owner`) — PASS

`categories.py:5140` now calls `_safe_add_to_owner(new_ref, entry_refs,
"ILexEntryRefFactory", ref_guid)` — the exact fix cycle-2's QC report recommended,
replacing the prior inline `entry_refs.Add(new_ref)` + duplicated raise. `references.py`
also has its own independent (not calling into categories.py) but behaviorally
identical `_add_to_owner` (references.py:792-804) — a deliberate cross-module mirror,
not a DRY violation, since `references.py` cannot import `categories.py` (reverse
dependency direction) and is used for the possibility-list CREATE arm's owner-Add. The
untested branch cycle-2 flagged is now covered:
`test_entryref_create_pass_add_failure_raises_orphan_risk_runtimeerror`
(tests/unit/test_027_entryref_reproduction.py:444-463) confirms `Create()` succeeding
+ `Add()` failing raises `RuntimeError` matching "Orphan risk", proving the fold didn't
silently drop the guard.

## 5. New ReferenceFieldSpec rows + 5118 factory arm — PASS, consistent

The 3 new rows (`references.py:189-209`, `owner_class="LexEntryRef"`) follow the exact
shape of every other row: `SEQUENCE` cardinality (matches the `RS` suffix convention),
`target_list_path` lambdas resolved off `_lp(target).LexDbOA.*`, `hierarchical=True` for
`VariantEntryTypesRS`/`ComplexEntryTypesRS` (matches the live-confirmed `Depth=127`
comment) and `False` for `ShowComplexFormsInRS` (matches every other
`PublicationTypesOA`-backed row already in the table). The `5118: ILexEntryTypeFactory`
entry (references.py:1041-1047) is correctly placed alongside the other 4 confirmed
`ItemClsid` mappings, with an accurate audit-trail comment. Minor (P2, not blocking):
the parametrized regression suite in `tests/unit/test_reference_create_paths.py`
(`_ITEM_CLSID_FACTORY_CASES`, lines 258-263) still only lists `(66, 26, 5042, 7)` — it
was not extended to include `(5118, "ILexEntryTypeFactory")` for symmetry. Not a real
coverage gap since `test_027_entry_type_resolve.py`'s tests already exercise the 5118
factory dispatch end-to-end through the real `_run_entryref_create_pass` entry point
(arguably better coverage than the isolated parametrize table), but the omission is a
minor DRY/consistency nit worth a one-line follow-up.

## P0 — none

## P1 — Findings

### P1-a: `_entry_ref_is_reproducible` ignores actual leaf-pick selection scope
(categories.py:4410-4417, 4520 call site context)

`_entry_ref_is_reproducible` classifies a Component/PrimaryLexemesRS member as
"in closure" using only `_affix_type_of(m)[0]` — an INTRINSIC shape test (has
`LexemeFormOA` + `MorphTypeRA`). But `affixes_enumerate_source`/(the STEMS twin)
(categories.py:5435-5458, 5825ff) can narrow the actual copy scope to a
`selection.leaf_picks_for(...)` subset — i.e. an entry can be intrinsically
STEMS/AFFIXES-*eligible* yet NOT actually selected for THIS run. `research.md`'s own
Decision 5 (specs/027-complex-forms-variants/research.md:69-80) describes the intended
signal as "all in the **copy closure**," which is a run-scoped concept — but the
implementation only checks type-level eligibility, not run-scoped selection
membership, and `_report_dropped_entry_refs(src_entry, dropped)`'s signature doesn't
even receive `context`/`selection`, so it structurally cannot check pick membership.
Net effect: when a user runs a leaf-pick-narrowed transfer and a `LexEntryRef`
references a component excluded from the pick set, `_entry_ref_is_reproducible`
wrongly says "reproducible," so `_report_dropped_entry_refs` emits NO
`DroppedItemRecord` for it — meaning `compute_fidelity_by_guid` (categories.py:3283-3305)
will report FULL fidelity for that owning entry. This is *not* a completely silent
loss overall: `_run_post_pass_a` (categories.py:5219-5231) independently emits
`Skip(DEPENDENCY_UNRESOLVED)` when it can't resolve the same component at wiring time —
but that's a different reporting channel (RunPlan skips, not `dropped_items`/fidelity
census), so the per-object fidelity status this feature exists to compute is wrong in
this scenario. Recommend either (a) explicitly documenting this as a known limitation
of the "in closure" heuristic (Decision 5 addendum), or (b) threading the run's actual
selection/pick-set through so `_entry_ref_is_reproducible` can check real membership,
not just type eligibility.

### P1-b: `tests/verification/fidelity_census.py` is stale/materially incorrect for the
entire `LexEntry.EntryRefsOS` / `LexEntryRef.*` field family post-027

This file is explicitly the project's "closed map the census verifies against" for the
never-silent completeness guarantee (per `references.py`'s own module docstring,
lines 12-15). Its `CLASSIFICATION` entries for this exact field family were NOT updated
alongside C1-C4:
- `("LexEntry", "EntryRefsOS")` (fidelity_census.py:350-362) still says "no
  `ILexEntryRefFactory` create site exists anywhere in `Lib/*.py`" — false as of this
  cycle (`_run_entryref_create_pass` uses `ILexEntryRefFactory` at categories.py:5122).
  Its "Subsumes LexEntryRef.{..., VariantEntryTypesRS, ComplexEntryTypesRS,
  ShowComplexFormsInRS}" note is also now false — those 3 fields get their own
  independent CREATE/UPDATE/LINK/REPORT_DROPPED disposition via C3, not a blanket
  "subsumed by the parent drop" treatment.
- All 5 `("LexEntryRef", field)` rows (fidelity_census.py:622-662) still classify
  `ComponentLexemesRS`, `PrimaryLexemesRS`, `VariantEntryTypesRS`, `ComplexEntryTypesRS`,
  `ShowComplexFormsInRS` as `Bucket.DROP_REPORTED` with the note "no LexEntryRef is ever
  created, so this field cannot exist independently of that drop" — this is precisely
  the behavior 027 changed. `ComponentLexemesRS`/`PrimaryLexemesRS` are now reproduced
  in-closure by C1/C2; `VariantEntryTypesRS`/`ComplexEntryTypesRS`/`ShowComplexFormsInRS`
  now get a real `COPIED`-shaped disposition (CREATE/UPDATE/LINK) via C3, only falling
  to `DROP_REPORTED` in the REPORT_DROPPED (diverged-protected or unresolved) sub-case.
- Line-number citations throughout these entries (e.g. "categories.py:4060",
  "categories.py:4089+") no longer match the current file (`_report_dropped_entry_refs`
  is now at 4420, `_walk_lex_entry_closure` at 4520) — stale even mechanically.

This is a documentation-only issue (no runtime behavior is wrong), but it directly
undermines the audit trail this feature's own contract depends on — a future
agent/reviewer trusting this file would materially misjudge what 027 actually
reproduces vs. drops. Recommend a follow-up commit updating these
`CLASSIFICATION` entries (bucket + site + note + line refs) to describe the current
C1-C4 disposition before this feature is considered fully landed.

### P1-c (minor duplicate of P1-b, in production code, not just the census): stale
comment at the Move call site (categories.py:4608-4611)

`_walk_lex_entry_closure`'s call to `_report_dropped_entry_refs` still carries the
cycle-16-era comment "EntryRefsOS is never reproduced (no `ILexEntryRefFactory` create
site)" — same factual staleness as P1-b, just duplicated inline. Low effort to fix
(3-line comment update) but worth folding into the same follow-up so the two don't
drift independently again.

## P2 — Style/consistency (non-blocking)

- **categories.py:5086** — `source = getattr(context, "source_handle", None)` uses a
  defensive `getattr` fallback, which is exactly the pattern this cycle's own
  documentation (categories.py:3605-3609) says was deliberately REMOVED elsewhere
  ("removing the Preview-vs-Move inconsistency of a defensive `getattr` fallback that
  could silently mask a genuinely missing field") in favor of direct `context.
  source_handle` access, since `source_handle` is a required, non-Optional
  `TransferContext`/`RunContext` field. Not a functional bug (the field is always
  present in practice), but inconsistent with the norm this same cycle established at
  two other call sites (categories.py:3610, 4606). Recommend `context.source_handle`
  direct access here too for consistency.
- **`_OWNER_LABEL_FIELD`** (categories.py:3217-3221) has no entry for `"LexEntryRef"` —
  every `DroppedItemRecord` produced by C3's dispatch (owner_guid=ref_guid) carries a
  permanently-blank `owner_label`. Cosmetic only (the report is still correctly keyed
  by GUID/field/reason); worth a one-line addition if a human-readable report ever
  wants to show *which* ref a C3 divergence belongs to.
- **test_reference_create_paths.py:258-263** — `_ITEM_CLSID_FACTORY_CASES` wasn't
  extended to include `(5118, "ILexEntryTypeFactory")`; effectively covered elsewhere
  (test_027_entry_type_resolve.py) but leaves the "one table, one test" pattern
  incomplete for this one case.

## Error Degradation: PASS

Every new code path degrades to `Skip`/`DroppedItemRecord` rather than crashing:
absent target list, unmapped `ItemClsid` (fail-loud `UnmappedItemClassError` caught and
converted at `_call_apply_reference`, categories.py:3346-3352), `ILexEntryRefFactory`/
interface unavailable (categories.py:5122-5138), and orphan-risk Add failure (now via
`_safe_add_to_owner`, correctly re-raised as `RuntimeError` and NOT swallowed at
`_call_apply_reference`, categories.py:3353-3374 — logged + recorded, matching cycle-2's
verified convention).

## Style/Naming/Complexity

Consistent with established file conventions throughout (`_run_*_pass`, `type_skip`
naming, `SimpleNamespace` synthetic-item idiom for reusing the generic dispatch without
a bespoke C3 code path). Docstrings are extensive and accurately describe the CURRENT
behavior in `categories.py`/`references.py` themselves (only the separate
`fidelity_census.py` verification module and one duplicate inline comment have drifted
— see P1-b/P1-c). No dead code found in the reviewed sections.

## Final Assessment

**Overall Score:** 83/100
**Recommendation:** CONDITIONAL — the core T014/T015/T020/P1-DRY/spec-row work is
correct, well-tested against real production entry points (not just isolated
decide_reference/apply_reference calls), and closes the cycle-2 P1 cleanly. Two P1
findings should be resolved before this is called fully landed: (a) the
fidelity_census.py staleness (P1-b/P1-c) — low-effort, high audit-trail value, should
land before/alongside this feature's completion; (b) the leaf-pick "in closure" scope
gap (P1-a) — at minimum needs an explicit documented-limitation note in research.md/
the C4 contract, ideally a follow-up to thread real selection scope through. Neither
blocks the US1/US2/US3 happy-path functionality itself, which is solid.

---
**Reviewed By:** QC Agent (cycle 3)
