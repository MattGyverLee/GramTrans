# Verification Report — Feature 027 (Complex Forms & Variants), Cycle 6 (pre-merge gate)

**Date:** 2026-07-13
**Worktree:** d:\Github\_Projects\_LEX\GramTrans-027-complex-forms-variants
**Branch/Commit:** 027-complex-forms-variants @ 34be1ad600903bcca110f032c538f69a1319b1cd
**Status:** PASS

## Executive Summary

All six gate items PASS. No blockers found. Both tripwires reproduced genuine RED
failures and the worktree was restored byte-clean after each. Diff scope matches
the expected shape exactly (13 files, +2739/-42), with production changes confined
to the four expected `src/gramtrans/Lib/*.py` files. Worktree left clean.

**Recommendation:** APPROVE

## Item 1 — Full offline suite

Command: `python -m pytest tests/unit -q`

Result line:
```
1 failed, 1579 passed, 9 skipped, 14 xfailed, 14 xpassed in 8.69s
```

The single failure is `tests/unit/test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos`
— exactly the documented baseline fail. No other failures.

**Status:** PASS

## Item 2 — Targeted 027 suite

Command:
```
python -m pytest tests/unit/test_027_entryref_reproduction.py tests/unit/test_027_entry_type_resolve.py tests/unit/test_027_never_silent.py tests/unit/test_phase3c_post_pass_a.py -q
```

Result:
```
60 passed in 0.97s
```

**Status:** PASS

## Item 3 — Tripwire genuineness

### (a) C1 container-creation revert

Edit: inserted an early `return skips` at the top of `_run_entryref_create_pass`
(`src/gramtrans/Lib/categories.py`), right after `skips = []`, effectively disabling
all `LexEntryRef` container creation (the "create path -> return None/skip" revert).

Result: `python -m pytest tests/unit/test_027_entryref_reproduction.py tests/unit/test_027_never_silent.py -q`
→ **10 failed, 11 passed**. Failures include all `test_entryref_create_pass_*`
tests in `test_027_entryref_reproduction.py` (the C1 created-container tests, e.g.
`test_entryref_create_pass_creates_variant_container`,
`test_entryref_create_pass_multi_component_complex_form`,
`test_entryref_create_pass_complex_form_primary_subset_order_preserved`, etc.) and
`test_c5_preview_move_created_and_dropped_set_parity` in `test_027_never_silent.py`
(C5 created-set parity), which fails on `set(factory.create_log) == planned`
(created set now empty vs. expected 6 refs). Confirmed genuinely RED.

Restore: `git checkout -- .` → `git status -s` empty. Confirmed clean.

### (b) C4 flip revert

Edit: changed `_entry_ref_is_reproducible` (`src/gramtrans/Lib/categories.py`) to
unconditionally `return False` (was `return all(_affix_type_of(m)[0] for m in
members)`).

Result: `python -m pytest tests/unit/test_027_never_silent.py -q` →
**5 failed, 5 passed**. Failures: `test_in_closure_ref_yields_zero_dropped_records`
(T019 — the C4 policy-flip tripwire, now emits 1 dropped record instead of 0),
`test_mixed_refs_report_only_the_out_of_closure_one`,
`test_ref_with_zero_components_is_trivially_in_closure`, and both T021 C5 parity
tests — `test_c5_preview_move_created_and_dropped_set_parity` (dropped set now
contains 6 spurious records instead of `[]`) and
`test_c5_created_ref_set_is_disjoint_from_dropped_set` (drop-set GUIDs now
`{'ref-in','ref-out'}` instead of `{'ref-out'}`). Confirmed genuinely RED.

Restore: `git checkout -- .` → `git status -s` empty. Confirmed clean.

**Status:** PASS — both tripwires are genuine (fail when the fix is reverted,
restore cleanly).

## Item 4 — Diff scope

Command: `git diff --stat main...HEAD`

Result: **13 files changed, 2739 insertions(+), 42 deletions(-)** — matches
expected exactly.

Files touched:
- `debug/run27_live.py` (+279) — new live driver script (not production code)
- `src/gramtrans/Lib/categories.py` (+325/-…) — production, expected
- `src/gramtrans/Lib/models.py` (+24) — production, expected
- `src/gramtrans/Lib/preview.py` (+11) — production, expected
- `src/gramtrans/Lib/references.py` (+46/-…) — production, expected
- `tests/integration/test_027_complex_forms_live.py` (+91) — new test
- `tests/unit/test_027_entry_type_resolve.py` (+602) — new test
- `tests/unit/test_027_entryref_reproduction.py` (+547) — new test
- `tests/unit/test_027_never_silent.py` (+582) — new test
- `tests/unit/test_cycle16_drop_reporting.py` (+/-23) — existing test, small edit
- `tests/unit/test_phase3c_post_pass_a.py` (+235) — new test
- `tests/unit/test_reference_create_paths.py` (+9) — existing test, small edit
- `tests/unit/test_reversal_category_resolve.py` (+7) — existing test, small edit

Production code is confined to `categories.py`, `models.py`, `preview.py`,
`references.py` under `src/gramtrans/Lib/` — no unexpected production files.

**Status:** PASS

## Item 5 — Live driver byte-compile

Command: `python -m py_compile debug/run27_live.py` → succeeded with no
output/errors (byte-compiled cleanly). The script was NOT executed (T025 is
attended/needs_human, per instructions). The resulting `scratchpad/__pycache__`
artifact is git-ignored (confirmed via `git status -s` showing no new entries
after compilation).

**Status:** PASS

## Item 6 — Worktree cleanliness

`git status -s` empty at the end of verification (checked after each tripwire
restore and again as a final check). `git rev-parse HEAD` still
`34be1ad600903bcca110f032c538f69a1319b1cd` (unchanged).

**Status:** PASS

## Final Assessment

**Overall Status:** PASS

**Blockers:** None

**Recommendation:** APPROVE

---
**Verified By:** Verification Agent
**Date:** 2026-07-13
