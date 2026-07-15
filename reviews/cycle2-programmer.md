# Programmer Report — cycle 2 (#28 msa-slot-wiring-v2)

**New commit hash (after amend):** `95cfb81c571d9b2448c2dee12db7c1fff99a1101`
(was `aa7788b`)

## Task A — converge to single producer
Removed the dead duck-only `msa_slot_bindings` branch of `_stash_entry_bindings`
in `src/gramtrans/Lib/categories.py`, formerly lines **2948-2954** (the
`msa_map = _binding_map(...)` block writing via `_guid_str_from`). Replaced
with a docstring NOTE explaining the removal. Left the `lexentry_ref_bindings`
/ `entryref_create_bindings` branches untouched.

Confirmed exactly **one** producer remains: `_populate_msa_slot_bindings`
(preview.py:801, duck fallback preview.py:918), consumed by `_run_171_subpass`
(categories.py:4956).

Two pre-existing unit tests broke as a direct, in-scope consequence of the
removal (they asserted `plan_action`-level stashing that no longer happens
now that the sole producer runs once in `preview.build_run_plan`, not per
AFFIXES/STEMS `plan_action` call):
- `tests/unit/test_categories_affixes.py::test_plan_action_stashes_msa_slot_binding`
- `tests/unit/test_categories_stems.py::test_plan_action_stashes_msa_slot_bindings_when_nonempty`

Renamed both to `test_plan_action_does_not_stash_msa_slot_binding(s)`,
updated assertions to `== {}`, and documented the architecture shift
(coverage for the real producer already lives in
`test_preview_msa_slot_bindings.py`).

**Test results:**
- `test_preview_msa_slot_bindings.py`: **10 passed**
- Targeted categories/preview modules (10 files): **101 passed, 4 skipped,
  2 xfailed, 14 xpassed, 0 failed**
- Full `tests/unit`: **1590 passed, 1 failed, 9 skipped, 14 xfailed, 14 xpassed**
  — the 1 failure is the documented pre-existing baseline
  `test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos`,
  untouched per instructions.
- `py_compile` on `categories.py` + `preview.py`: clean.

## Task B — commit-message pattern-audit gate
Amended `aa7788b` -> `95cfb81` via `git commit --amend -F <msg>`. Added a
"Cycle-2" paragraph (test-count summary + rename note) plus a corrected
**Pattern audit** table, row 1 now showing the single producer:

| Binding | Producer | Consumer | Status |
|---|---|---|---|
| `msa_slot_bindings` | preview.py:801 `_populate_msa_slot_bindings` (single producer; duck fallback preview.py:918) | categories.py:4956 `_run_171_subpass` | FIXED — dead duplicate producer removed; exactly one producer remains |
| `lexentry_ref_bindings` | categories.py `_stash_entry_bindings` (AFFIXES/STEMS) | categories.py tail pass | PRODUCED (027) — verified, untouched |
| `entryref_create_bindings` | categories.py `_stash_entry_bindings`, same sites | categories.py post-pass A | PRODUCED (027) — verified, untouched |
| `feature_category_links` | categories.py `_stash_feature_category_links` | `_run_infl_feature_link_pass` | PRODUCED (031) — verified, untouched |

Closing line: "No consumer-only bindings remain."

No new commit created; diff was additive elsewhere (categories.py note +
two test renames), amend only.
