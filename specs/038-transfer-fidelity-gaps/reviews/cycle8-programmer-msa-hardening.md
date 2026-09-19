# Cycle 8 — MSA entry-owned/no-referencing-sense hardening

HARDENING ONLY -- T123(a) is diagnosed and fixed elsewhere; this guard
claims nothing against it. T123(a)'s -1 (`omoona`, e2cd79ef-..., missing MSA
8617b725-...) is a natural-key create-skip that left a sense's
`MorphoSyntaxAnalysisRA` null, fixed in the task immediately before this one
via `_create_via_wrapper_or_reuse` / `_find_reusable_target_msa`.

Tree: `D:\Github\_Projects\_LEX\GramTrans-038-transfer-fidelity-gaps`
(`038-transfer-fidelity-gaps`). HEAD unchanged, **not committed**:
`5cf155c39b3b78ddea9333d65b469aaf1ba603b0`. All edits are additional
uncommitted worktree diffs on top of the pre-existing ones (LexEntryType fix,
natural-key MSA fix, census/models work).

## What landed, in `src/gramtrans/Lib/categories.py`

- `_create_msa_with_guid` (~9732): `new_sense` is now optional. When None
  (the hardening shape), the entry-owned MSA is still created, added to
  `new_entry.MorphoSyntaxAnalysesOC`, and given its POS fields; only the
  sense-wiring line is skipped (previously an unconditional attribute-set
  that would `AttributeError` on `None`).
- `_create_entry_owned_msas_without_sense` (new, ~10132–10197): walks
  `src_entry.MorphoSyntaxAnalysesOC` after the per-sense loop, skips any
  guid already in `msa_by_src_guid`, and creates the remainder directly via
  `_create_msa_for_closure(src_msa, None, ...)` -- reusing the existing
  create/POS/GUID machinery rather than duplicating it. Failures are
  reported via `_report_dropped_msa`, never swallowed.
- Call site in `_walk_lex_entry_closure`, inserted between the end of the
  per-sense `for` loop and `return new_entry` (~8296–8309, function itself
  at 8038; `return new_entry` now at 8310).

Both the call site and the new function's docstrings carry the MEASURED
EMPTY label (`Ngoreme FLEx`, op-102227585-005/-006: entry-owned = distinct
sense-referenced in all four MSA classes, 2090 = 2090) and name T123(a)'s
real cause/fix by function name, per the task's labelling requirement.

## Test

`tests/unit/test_038_t123_msa_entry_owned_no_sense_latent.py` (new, 2
tests), module-docstring-labelled LATENT PATTERN PIN, never a T123(a)
regression test:
- `test_entry_owned_msa_with_no_referencing_sense_is_still_created__latent`
  -- one entry, entry-owned MSA list of 2 where only one guid is
  pre-accounted-for (simulating one sense having already referenced it);
  asserts both arrive on `new_entry`, no re-create of the already-processed
  guid, and the unreferenced one's GUID is identity-preserved.
- `test_already_processed_guid_is_never_recreated__latent` -- ordinary
  (measured) case, all guids already accounted for: no-op, zero creates.

## Counts

`tests/unit/ -q`: **3894 passed, 79 skipped, 14 xfailed** (comparand 3892 +
2 new = 3894; skip/xfail unchanged). Full unit dir, not bare `pytest tests/`.
No live writes, no transfer, no FLEx opens this session.
