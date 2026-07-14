# Cycle 6 — lex-domain (LexEntryRef reproduction semantics) review

**Feature:** 027 Complex Forms & Variants · **Gate:** T027 merge · **HEAD:** worktree `34be1ad`
**Score: 91/100 — APPROVED** (conditional on one already-tracked open item)

> Note: authored by the main session on behalf of lex-domain, which lacked a Write
> tool in its session and returned findings inline.

## 1. RefType semantics — PASS
`_LEX_ENTRY_REF_KIND_BY_TYPE = {0: "variant", 1: "complex-form"}` (categories.py:4372)
matches LCM convention. C1's `type_skip` (categories.py:5152-5156) excludes
`VariantEntryTypesRS` when `RefType != 0` and `ComplexEntryTypesRS` when `RefType != 1`;
`ShowComplexFormsInRS` always attempted. `references.py` REFERENCE_FIELD_MAP (189-209)
routes `VariantEntryTypesRS -> LexDbOA.VariantEntryTypesOA`,
`ComplexEntryTypesRS -> LexDbOA.ComplexEntryTypesOA`,
`ShowComplexFormsInRS -> LexDbOA.PublicationTypesOA` — no cross-wiring. Confirmed by the
negative test `test_complex_form_ref_resolves_complex_types_not_variant_types`
(tests/unit/test_027_entry_type_resolve.py:509).

## 2. C3 three-way disposition — PASS
`decide_reference`/`apply_reference` (references.py:666-820+) implement the contract
table exactly: absent → CREATE with full ancestor chain (`_ancestor_chain`,
unconditional — correctly not gated on the static `hierarchical` flag, since per-project
`Depth` can disagree); identical → LINK; diverged + not `IsProtected` → UPDATE; diverged
+ `IsProtected` → LINK + REPORT_DROPPED (never auto-mutates shared/GOLD — matches
constitution v7.0.0). All four legs exercised for both RefTypes. Component/primary-subset
order preservation (independent per-field ordering, genuine subset) strictly tested —
good fidelity: reproduction copies the source's own FLEx invariant verbatim rather than
re-deriving it.

## 3. Principle I (GOLD/reserved) — PASS (terminology nit)
`test_gold_reserved_entry_type_guid_remapped_at_creation` and
`test_gold_reserved_existing_target_item_linked_never_overwritten` (557-603) confirm: an
absent GOLD item is created via `factory.Create(parsed_guid)` **preserving** the source's
reserved GUID (not minting new), and an existing target GOLD item is linked with its
Name/text left untouched even when the source drifted. **Nit:** contract/docstring
phrase "GUID-remapped at creation" is a misnomer — the GUID is *preserved* 1:1, not
remapped. Code comments (references.py:1030-1037, test docstring:559) already clarify;
documentation-wording only.

## 4. Never-silent (C4) — CONDITIONAL PASS (open, already-tracked)
`_report_dropped_entry_refs`/`_entry_ref_is_reproducible` (categories.py:4410-4451) emit
0 for an in-closure ref and exactly 1 per un-reproduced ref. **But** (P1-a, already in
`reviews/cycle3-qc.md:126-152`) `_entry_ref_is_reproducible` tests only *intrinsic*
STEMS/AFFIXES eligibility (`_affix_type_of`), not run-scoped leaf-pick selection
membership. On a leaf-pick-narrowed transfer, a component excluded from the pick set but
structurally lexeme-shaped is misclassified "reproducible," so C4 emits **zero** drop
records for it (a `Skip(DEPENDENCY_UNRESOLVED)` still fires from `_run_post_pass_a`, but
on a different channel than the fidelity-census/dropped-items path this feature exists to
keep accurate). Domain-relevant: after a partial (leaf-pick) transfer a user could be
told an entry has full EntryRefsOS fidelity when it doesn't. Correctly folded forward as
an explicit open item against `feature_complete` (not silently dropped) — but must be
resolved (fix, or documented-limitation note in research.md/contract) before final
approval.

## MCP / live-verification flag
The C3 target-list shapes relied on (`VariantEntryTypesOA`/`ComplexEntryTypesOA` =
`ItemClsid=5118`/`Depth=127`; `PublicationTypesOA` = `ItemClsid=7`/`Depth=1`) rest on a
cited read-only probe (`scratchpad/probe_c3_lists.py`) that **does not exist on disk** in
either repo — confirmed absent by search; recorded in `.crew-handoff.json`
`open_items.mcp_deviation`. **Must-confirm-live at T025:** re-verify these three
attribute names / ItemClsids / Depths via FLExToolsMCP against Ejagham Mini before
treating C3's CREATE-arm factory dispatch as fully proven.

## Recommendations
1. Resolve or explicitly document the leaf-pick scope gap (P1-a) before `feature_complete`.
2. Reword contract C3 / docstrings "GUID-remapped at creation" → "GUID-preserved (not
   reassigned) at creation".
3. At T025, re-confirm the 5118/Depth=127 and 7/Depth=1 shapes via FLExToolsMCP (original
   probe artifact unrecoverable).
