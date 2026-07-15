# Cycle 6 Programmer Report — feature 025-full-reversals remediation

Worktree: `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals`, branch `025-full-reversals`.
Commit: `930fe7c`.

## P0-1: config_views Preview must be read-only

File: `src/gramtrans/Lib/config_views.py`. Added a pure `compute_config_dirs(project)`
(path computation only, no `os.makedirs`, never touches the filesystem — line ~72).
`resolve_config_dirs` (line ~91) is now a thin makedirs-wrapper around it, with no
remaining call site in this module (`apply_config_views` already does its own per-file
`os.makedirs` at Move time — unchanged). `plan_config_views` (line ~319) now calls
`compute_config_dirs` for both `src_project` and `tgt_project` instead of
`resolve_config_dirs`, so the Preview decision pass creates zero directories on either
tree. Updated the module banner and both function docstrings to state the decision
pass creates no directories. Also corrected the stale cross-reference comment in
`preview.py` (~line 325) that named `resolve_config_dirs`.

Test: `tests/unit/test_preview_no_writes.py::test_build_run_plan_never_creates_config_view_directories`
— new `_FakeProject.ProjectFolder` pointing at a real tmp dir so `_project_dir` succeeds
(previously short-circuited to `ValueError` → swallowed, the QC-flagged coverage gap).
Spies on `config_views.os.makedirs`. Failing before fix: `makedirs` called 6 times,
creating `ConfigurationSettings/{Dictionary,ReversalIndex}` under BOTH tmp dirs
including source. Passing after fix: zero `makedirs` calls, no `ConfigurationSettings`
under either tree.

## P0-2: surface reversal + config-view plan in Preview

Added `render_preview_extra_lines(plan)` in `preview.py` (~line 442), composing
`render_reversal_decisions(plan) + render_config_view_records(plan)` (each already
`()`-safe for an empty plan). Wired `main_window._on_preview` (~line 285) to call it
and pass the result into `StatsPanel.set_report(report, extra_lines)` — new optional
param (`stats_panel.py`), rendered in a new hidden-when-empty panel section
("Reversals & configuration views (Preview)"). Move's `set_report(report)` call
(line 340) is unaffected (default `extra_lines=()`). Corrected the now-accurate
docstrings at `categories.py::reproduce_reversal_entries` (~4019) and
`models.py::RunPlan.reversal_decisions`/`.config_view_records` (~718, 729) to name
the real call path instead of the previously-false "already shown to the user" claim.

Test: new file `tests/unit/test_preview_surfacing.py` (3 tests) — empty-plan no-op,
reversal Add/Link + config-view Add/Overwrite/Skip line surfacing (asserts exact
rendered text), and composition order. Failing before fix: `ImportError:
cannot import name 'render_preview_extra_lines'`. Passing after fix: all 3 green.

## Hardening: pin source=None

Added `tests/unit/test_reversal_category_resolve.py::test_decide_reversal_category_pins_source_to_none`
— spies on `reversals.references.decide_reference` via `plan_reversals`, asserts
`source=None`. Sanity-verified the test actually guards the invariant: temporarily
patched `reversals.py` line 343 to pass `source=src_pos`, confirmed the new test fails
with a clear assertion message, then reverted (`git checkout --`) before committing.

## Suite counts

Targeted files: all green. Full suite: **1499 passed, 1 failed** (same pre-existing
`test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos`,
untouched) — baseline 1494/1 plus 5 new passing tests (1 P0-1 + 3 P0-2 + 1 hardening).

## Deviations from brief

None. Out-of-scope items (P1-1, P1-2, source=None asymmetry, T021 tripwire, unified
dropped_items channel) were not touched; no live-MCP run performed.
