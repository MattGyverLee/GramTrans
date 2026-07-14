# QC Report — Cycle 5 (US3 spurt: T016/T017/T018)

**Date:** 2026-07-13
**Worktree:** d:/Github/_Projects/_LEX/GramTrans-027-complex-forms-variants
**Commit:** ec40a32 (diff base da06a5c)
**Quality Score:** 94/100
**Status:** PASS

## Pattern-Audit Gate
- Applicability: **N/A** — this is a feature/US3 test spurt (test(027): US3 spurt), not a bugfix commit; no `closes #N`/`fixes #N` against a `bug`-labelled issue. Programmer report cites "Resolves GitHub #30" (a feature epic), not a bug.
- Gate status: **N/A (not a bugfix cycle)** — justified above, no further action required.

## Scope note
Per the brief, cycle-3's open P1s (P1a_leafpick_scope, P1bc_fidelity_census) are
explicitly NOT re-litigated here — they remain folded-forward against
`feature_complete`, not this US3 gate. All findings below are new to this cycle.

---

## A. Test quality — the two new test files

### test_027_entryref_reproduction.py (T016)

Read in full (`d:/Github/_Projects/_LEX/GramTrans-027-complex-forms-variants/tests/unit/test_027_entryref_reproduction.py`).

`test_entryref_create_pass_complex_form_primary_subset_order_preserved`
(lines 360–401) is **not** a shallow smoke check. It genuinely pins:
- **Subset membership**: N=3 components (`lex-a, lex-b, lex-c`), M=2 primary
  subset (`lex-c, lex-a` — excludes `lex-b`). The assertion
  `assert list(new_ref.PrimaryLexemesRS) == [lex_c, lex_a]` (line 401) is a
  strict list-equality, not a membership/superset check — it would fail if
  `lex_b` leaked in, proving the exclusion is real, not incidental.
- **Independent source order per field**: primaries are listed in a
  *different relative order* than components (`c, a` vs `a, b, c`), and both
  `ComponentLexemesRS` (line 398) and `PrimaryLexemesRS` (line 401) are
  checked against their own authored order — this rules out "wire everything
  in component order" bugs.
- **Overlap across fields**: `lex_a` and `lex_c` appear in *both*
  `ComponentLexemesRS` and `PrimaryLexemesRS`. Because each field owns its
  own `_FakeRefSeq` (via `_FakeCreatedRef.__init__`, lines 118–128 in the
  sibling file / equivalent shape here), this exercises that membership
  guards are per-field, not shared — a real regression class this shape
  would catch if `_run_post_pass_a`'s per-field `already` check (categories.py:5233–5236)
  were ever refactored to share state across fields.
- The test runs C1 then C2 in the real STEMS-tail order (`_run_entryref_create_pass`
  then `_run_post_pass_a`, lines 391–392) over the *same* ctx/target — an
  end-to-end create-then-wire check, not an isolated-unit check.

This is a genuinely new combination: the existing sibling test in
`test_phase3c_post_pass_a.py` (`test_create_then_wire_preserves_source_order`,
lines 798–817) only exercises component-order preservation with an *empty*
`PrimaryLexemesRS`; it never exercises a non-trivial, differently-ordered
primary subset. T016 closes a real, previously-unexercised combination
(RefType=1 + strict subset + divergent relative order + field overlap).

**Fakes fidelity vs. the RefType=0 counterparts they mirror:**
- `_FakeLexeme` (lines 332–337) is a guid-only fake, structurally identical
  to `_FakeObj` in `test_phase3c_post_pass_a.py` (lines 64–68) — faithful,
  if renamed (see P2 below).
- `_ctx_create_and_wire` (lines 340–357) is a near-verbatim copy of
  `test_phase3c_post_pass_a.py`'s `_ctx_create_and_wire` (lines 742–755),
  correctly carrying both `entryref_create_bindings` and
  `lexentry_ref_bindings` plus `in_plan_entries={}` so C1->C2 can run in
  sequence — matches the "STEMS-tail order" contract exactly as claimed in
  the programmer's report and the file's own header comment (lines 24–29).

### test_027_entry_type_resolve.py (T017)

The four new tests (`test_absent_complex_type_creates_with_guid_preserved`,
`test_diverged_custom_complex_type_updates_and_links_same_object`,
`test_diverged_shared_gold_complex_type_links_and_reports`,
`test_identical_complex_type_links_only_no_create_no_report`, lines
405–503) are line-for-line structural mirrors of T013's
`VariantEntryTypesRS` matrix (lines 295–393), and each assertion set is
substantive, not shallow:
- **absent -> CREATE**: checks GUID preservation (`linked[0].guid ==
  "src-ctype-1"`, line 423) *and* that the item actually landed in
  `lexdb.ComplexEntryTypesOA.PossibilitiesOS` (lines 426–427) — proves a
  real CREATE, not a phantom link.
- **diverged custom -> UPDATE+LINK same object**: `linked[0] is existing`
  (line 449) plus no-duplicate check on `PossibilitiesOS` length (line 452).
- **diverged shared/GOLD -> LINK+report, never mutated**: checks the linked
  object identity, that `existing.Name` was never overwritten (line 474),
  no duplicate created, *and* the `DroppedItemRecord`'s `field_name` is
  literally `"ComplexEntryTypesRS"` (line 478) — this is a real regression
  guard: if the CREATE/dispatch code accidentally hard-strung
  `"VariantEntryTypesRS"` into the report anywhere, this would catch it.
- **identical -> LINK only, no create/report**: symmetric to T013.

Also verified: the pre-existing routing test
`test_complex_form_ref_resolves_complex_types_not_variant_types` (lines
509–529, one of programmer's "5 affected tests") independently confirms
`VariantEntryTypesOA.PossibilitiesOS` is "never touched" (line 529) for a
RefType=1 ref even when a variant-type item is (implausibly) present on the
same record — a real negative-path assertion, not just absence-of-error.

**Fakes fidelity**: `_FakeEntryType`/`_FakeLexDb`/`_FakeTarget` etc. are
shared as-is within the same file between T013 and T017 (no duplication
introduced — T017 reuses T013's existing fixtures verbatim), which is the
correct approach here.

### Duplicated logic that should be shared (P2, not blocking)

The trio `_FakeRefSeq` / `_FakeTargetEntry` / `_ctx_create_and_wire` (plus a
guid-only fake object, named `_FakeObj` in one file and `_FakeLexeme` in
another) now exists in near-identical form across three test files:
- `test_027_entryref_reproduction.py` (this cycle's new `_FakeLexeme`
  lines 332–337, `_ctx_create_and_wire` lines 340–357)
- `test_phase3c_post_pass_a.py` (`_FakeObj` lines 64–68, `_ctx_create_and_wire`
  lines 742–755)
- `test_027_entry_type_resolve.py` (its own `_FakeRefSeq`/`_FakeTargetEntry`,
  lines 96–171, structurally parallel but with extra fields for the
  possibility-list machinery)

This is incremental — the pattern predates this cycle — but this cycle did
add a third near-identical `_ctx_create_and_wire`/guid-fake pair rather than
importing/sharing the existing one from `test_phase3c_post_pass_a.py`.
**Recommendation (non-blocking):** extract a shared
`tests/unit/_fixtures_lexentry_ref.py` (or similar) housing
`_FakeRefSeq`, a single guid-only fake (`_FakeGuidObj`), and
`_ctx_create_and_wire`, and have all three files import from it. Low
priority — purely a maintenance/DRY concern, no functional risk.

---

## B. T018 "no production code needed" claim — verified genuine

Read directly (not just the programmer's citations):
- `categories.py:5026–5168` (`_run_entryref_create_pass`)
- `categories.py:5174–5240` (`_run_post_pass_a`)
- `references.py:150–229` (`REFERENCE_FIELD_MAP`, LexEntryRef rows)
- `references.py:1000–1070` (CREATE arm's typed-factory-by-`ItemClsid` dispatch)
- `references.py:288–294` (`field_specs_for`)
- `categories.py:2934–2989` (`_stash_entry_bindings`, the binding-producer feeding both C1 and C2)

**Finding: the claim holds. No coverage/behavior gap found.**

1. **`ComplexEntryTypesRS` resolves against `LexDbOA.ComplexEntryTypesOA`,
   not `VariantEntryTypesOA`** — confirmed at `references.py:196–201`
   (`ComplexEntryTypesRS` -> `_lp(target).LexDbOA.ComplexEntryTypesOA`),
   distinct from `VariantEntryTypesRS` -> `.VariantEntryTypesOA` at
   `references.py:189–194`. These are two different list objects on the
   fake (`_FakeLexDb.__init__`, `test_027_entry_type_resolve.py:150–154`)
   and two different live LCM properties — genuinely parametric, not an
   accidental alias.

2. **Both share the same `ItemClsid=5118` -> `ILexEntryTypeFactory` CREATE
   arm** — confirmed at `references.py:1041–1049`
   (`factory_by_item_clsid = {..., 5118: ILexEntryTypeFactory, ...}`,
   looked up via `getattr(target_list, "ItemClsid", None)` — i.e. keyed off
   the *target list's* clsid, which is 5118 for both `VariantEntryTypesOA`
   and `ComplexEntryTypesOA`). This is genuinely list-shape-driven, not
   RefType-driven, so it correctly generalizes.

3. **The RefType gate is the *only* RefType-aware code, and it lives
   entirely in `categories.py`, not `references.py`** —
   `references.field_specs_for("LexEntryRef")` (line 288–294) returns *all
   three* rows (`VariantEntryTypesRS`, `ComplexEntryTypesRS`,
   `ShowComplexFormsInRS`) unconditionally; the RefType exclusion happens
   only via `categories.py:5152–5156`'s `type_skip` set (`ref_type != 0` ->
   skip variant, `ref_type != 1` -> skip complex), passed as
   `skip_fields=type_skip` into the shared `_apply_reference_fields` call
   at `categories.py:5162–5166`. This is a clean, minimal, single-point
   RefType branch — exactly the "parametric parity" claimed, not an
   accidental pass-through.

4. **The primary SUBSET (M-of-N) is correctly wired independently of
   components — the generic loop does NOT assume `primaries == components`.**
   Traced the full path:
   - `_stash_entry_bindings` (`categories.py:2960–2971`) reads
     `ComponentLexemesRS`/`PrimaryLexemesRS` off the *source* ref into two
     **separate** lists (`comp`, `prim`), with no coupling — a ref with 3
     components and a 2-element primary subset in the source produces
     exactly that shape in `plan.lexentry_ref_bindings`.
   - `_run_post_pass_a`'s wiring loop (`categories.py:5215–5239`) iterates
     `for field_name in ("ComponentLexemesRS", "PrimaryLexemesRS")` and for
     each, pulls `ref_dict.get(field_name, [])` — i.e., each field's own
     list, added onto that field's own live `seq` object
     (`getattr(target_ref, field_name, None)`, line 5216) with a
     **per-field** membership guard (line 5233–5236, scoped to that `seq`
     only). There is no shared/aggregate guard across fields, no
     "if components present, mirror into primaries" logic anywhere.
   - This is exactly what T016's new test exercises and pins (subset,
     divergent order, cross-field overlap) — and the programmer's
     tripwire-genuineness proof (disabling the `"PrimaryLexemesRS"` leg of
     the loop tuple, confirming the exact test fails with
     `assert [] == [<FakeLexeme>]`) independently corroborates this from
     the runtime side, not just static reading.

**Conclusion:** T018's "parity already exists, no new code needed" is a
correct, well-evidenced finding, not a rationalization to skip work. Both
angles the brief asked me to scrutinize — the `ComplexEntryTypesRS` ->
`ComplexEntryTypesOA` (not `VariantEntryTypesOA`) resolution, and the
primary-subset-vs-components independence — check out against the actual
code, not just the tests.

---

## Findings summary

| ID | Severity | Description | Location |
|----|----------|--------------|----------|
| P2-1 | P2 | Cross-file duplication of `_FakeRefSeq`/guid-only fake/`_ctx_create_and_wire` across 3 test files; this cycle added a third near-identical copy rather than sharing | `tests/unit/test_027_entryref_reproduction.py:332-357` vs `tests/unit/test_phase3c_post_pass_a.py:64-68,742-755` |
| P2-2 | P2 | Same conceptual fake named `_FakeObj` in one file, `_FakeLexeme` in another — harmless but adds cross-file diff friction | `tests/unit/test_027_entryref_reproduction.py:332` vs `tests/unit/test_phase3c_post_pass_a.py:64` |
| — | none | T017 does not add a ComplexEntryTypesRS-specific analogue of T014's GUID-remap/"GOLD linked never overwritten" tests | informational only — same dispatch code already pinned for VariantEntryTypesRS by T014, reasonable scope cut, no action needed |

No P0 or P1 issues found this cycle.

## Section scores
- Code Quality (tests only, no production diff): 24/25 — clear, well-documented, faithful mirrors; minor DRY debt (P2-1/P2-2).
- Standards Compliance: 25/25 — naming/organization consistent with existing 027 test conventions; docstrings explicit about contract/decision references.
- Error Handling / Edge Cases: 24/25 — subset/order/overlap edge case thoroughly covered by the one new T016 test; three-way disposition matrix (absent/diverged-custom/diverged-GOLD/identical) fully covered by T017.
- Best Practices: 21/25 — genuine RED-substitute tripwire proof documented in lieu of literal RED-before-GREEN (reasonable given genuine pre-existing parity); the cross-file fixture duplication (P2-1) is the only ding here.

## Final Assessment
**Overall Score:** 94/100
**Recommendation:** APPROVE

---
**Reviewed By:** QC Agent
