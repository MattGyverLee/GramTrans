# Cycle 7 — Programmer report (doc/comment/census-only closure of 2 carry-forwards)

## Files touched

Worktree (`GramTrans-027-complex-forms-variants`):
- `src/gramtrans/Lib/categories.py` — 3 doc/comment edits (`_entry_ref_is_reproducible`
  docstring caveat re: leaf-pick run-scope gap; stale "Cycle-16 lead adjudication" comment
  above `_report_dropped_entry_refs` call; `_run_entryref_create_pass` C3 docstring
  "GUID-remapped" → "GUID-preserved (not reassigned)"). No logic lines changed (diff
  reviewed line-by-line: only comment/docstring text).
- `tests/verification/fidelity_census.py` — reworded the `("LexEntry","EntryRefsOS")` row
  and all 5 `("LexEntryRef", *)` rows: create-site now points at
  `_create_entryref_container`/`_run_entryref_create_pass` (categories.py 5014/5041,
  `ILexEntryRefFactory` 5026-5031) instead of the stale "no create site exists" claim;
  corrected stale line-number citations for `_report_dropped_entry_refs` (4435, was 4060)
  and `_walk_lex_entry_closure` (4535, was 4089). Bucket stayed `DROP_REPORTED` (still
  correct — residual not-reproducible refs are still reported).
- `tests/unit/test_027_entry_type_resolve.py` — T014 header comment + docstring wording
  "GUID-remap-at-create"/"remapped 1:1" → "GUID-preserved-at-create (not reassigned)".
  `references.py` grepped for "GUID-remapped"/"remapped at creation" — no matches, no
  edit needed.

Main (`GramTrans`, specs are spec-artifacts on main):
- `specs/027-complex-forms-variants/research.md` — added a "Documented limitation
  (deferred post-merge)" addendum under Decision 5 describing the leaf-pick run-scope gap.
- `specs/027-complex-forms-variants/contracts/entryref-reproduction.md` — C3 body + Test
  obligations line: "GUID-remapped" → "GUID-preserved, not reassigned".

## Prove

- Targeted suite: `pytest tests/unit/test_027_entryref_reproduction.py
  tests/unit/test_027_entry_type_resolve.py tests/unit/test_027_never_silent.py
  tests/unit/test_phase3c_post_pass_a.py -q` → **60 passed** (unchanged). Also ran
  `tests/verification/fidelity_census.py` directly → 86 passed (census guard tests still
  green after the reword).
- Byte-compile: `python -m py_compile categories.py fidelity_census.py references.py` →
  clean, no errors.
- `git diff --stat` (worktree): 3 files, 102(+)/44(-) — categories.py, fidelity_census.py,
  test_027_entry_type_resolve.py only. `git diff --stat` (main): 2 files — research.md,
  entryref-reproduction.md only. No unexpected files in either checkout.

## Confirmation

No run-scoped selection-threading logic was changed anywhere. All edits are
documentation/comment/docstring/census-note text; the leaf-pick scope gap remains
open and documented (not fixed) per the assignment's explicit constraint.
