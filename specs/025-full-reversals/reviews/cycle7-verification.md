# Cycle 7 Verification -- feature 025-full-reversals

Worktree: D:\Github\_Projects\_LEX\GramTrans-025-full-reversals @ 930fe7c (clean, confirmed via `git status`/`git log -1` after all RED probes were reverted with `git checkout --`).

## 1. test_preview_no_writes.py::test_build_run_plan_never_creates_config_view_directories

GUARDS INVARIANT: **yes**

`_FakeProject` in this test now sets `src.ProjectFolder`/`tgt.ProjectFolder` to real `tmp_path` subdirs (`src_dir`/`tgt_dir`, both `mkdir()`-ed), so `config_views._project_dir` succeeds via the `ProjectFolder` duck-type branch -- it does NOT raise `ValueError`, so `build_run_plan`'s `except Exception` fail-soft swallow is never hit; `plan_config_views` genuinely runs. The test also monkeypatches `config_views_mod.os.makedirs` with a spy.

RED evidence: temporarily changed `config_views.plan_config_views` to call `resolve_config_dirs` (the directory-creating wrapper) instead of `compute_config_dirs` (the pure one). Result: **FAILED** -- `makedirs_calls` had 6 entries (Dictionary/ConfigurationSettings/ReversalIndex dirs created under BOTH SourceProject and TargetProject tmp dirs), i.e. `assert makedirs_calls == []` failed exactly as designed. Reverted via `git checkout -- src/gramtrans/Lib/config_views.py`.

## 2. test_preview_surfacing.py (3 tests)

GUARDS INVARIANT: **yes** (2 of 3; the 3rd is an intentional no-op check)

- `test_render_preview_extra_lines_empty_plan_yields_nothing` -- trivial no-op guard; passes regardless of wiring bug (not meant to catch it).
- `test_render_preview_extra_lines_surfaces_reversal_add_and_config_view_dispositions` -- asserts exact rendered text for reversal Add + config-view Add/Skip.
- `test_render_preview_extra_lines_is_reversal_lines_then_config_view_lines` -- asserts composition order (reversal lines before config-view lines).

RED evidence: temporarily replaced `render_preview_extra_lines`'s body with `return ()`. Result: the two substantive tests **FAILED** (`AssertionError: assert 'Reversal index [en] (Add):' in ''` and `StopIteration` from the order test finding no "Reversal index" line at all); the empty-plan test still passed (expected, since it's a no-op assertion). Reverted via `git checkout -- src/gramtrans/Lib/preview.py`.

## 3. test_reversal_category_resolve.py::test_decide_reversal_category_pins_source_to_none

GUARDS INVARIANT: **yes**

RED evidence: temporarily changed the `decide_reference` call in `reversals.py` (~line 343) from `source=None` to `source=src_pos` (a real source object). Result: **FAILED** -- `AssertionError: _decide_reversal_category must call references.decide_reference with source=None; observed source=<...._FakePossibility object ...>`. Reverted via `git checkout -- src/gramtrans/Lib/reversals.py`.

## Full suite (clean, post-revert)

`python -m pytest -q` at 930fe7c: **1522 passed, 1 failed, 76 skipped, 14 xfailed, 14 xpassed**.

The 1 failure is `tests/unit/test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos` -- pre-existing, untouched by this cycle's work (matches the expected identity in the task brief).

Note: the brief's expected total was "1499 passed / 1 failed"; actual is 1522 passed (same single pre-existing failure). Discrepancy in the passed-count is likely a stale baseline figure in the dispatch instructions, not a regression -- the failing test's identity matches exactly and no other test differs from a clean run.

## Worktree state

`git status --short` -- empty (clean). `git log --oneline -1` -- `930fe7c fix(025): P0-1 Preview read-only config-view dirs, P0-2 surface reversal+config-view plan, harden source=None`. Confirmed back at the required commit with no residual diff.
