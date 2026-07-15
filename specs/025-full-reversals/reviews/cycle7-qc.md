# QC Gate Re-Check — Cycle 7 (feature 025-full-reversals)

**Date:** 2026-07-12 | **Worktree:** `025-full-reversals` @ `930fe7c` | **Verdict: both P0s CLOSED**

Bounded re-check of the two cycle-6 P0 fixes only. Settled-green items 1/2/5 (cycle 5) not relitigated. Read-only; no live-MCP.

## P0-1 (config_views Preview must be READ-ONLY) — **CLOSED**
- `compute_config_dirs` (config_views.py:122-138) is pure path arithmetic (`os.path.join`/`os.path.abspath` only) — no `os.makedirs`, no FS writes.
- `resolve_config_dirs` (config_views.py:141-160) is the only `os.makedirs` wrapper in the module and has **zero** call sites elsewhere in config_views.py (only a self-reference in its own docstring + one prose mention in `_project_dir`'s docstring at line 96 — not a call).
- `plan_config_views` (config_views.py:350-351) calls `compute_config_dirs(src_project)` and `compute_config_dirs(tgt_project)` — both sides, zero directory creation during the decision pass.
- `apply_config_views` (config_views.py:400, 405) is the only place `os.makedirs` runs, at Move time (per-file, right before ADD/OVERWRITE copy).
- `preview.py:325-334` comment correctly references `compute_config_dirs` (not `resolve_config_dirs`); docstrings in both files now explicitly disclaim directory creation during the decision pass.

## P0-2 (reversal + config-view plan surfaced in Preview before Move) — **CLOSED**
- `render_preview_extra_lines` (preview.py:489-505) composes `render_reversal_decisions(plan)` + `render_config_view_records(plan)`.
- `main_window.py._on_preview` (line 296-297) calls `render_preview_extra_lines(plan)` and passes the result into `self._stats.set_report(report, extra_lines)` — genuinely reached on every Preview click. Principle III now holds: the reversal Add/Link plan AND config-view Add/Overwrite/Skip list are shown before Move.
- `main_window.py._on_move` (line 340) calls `set_report(report)` with no second arg; `StatsPanel.set_report` (stats_panel.py:105) defaults `extra_lines: Sequence[str] = ()` — Move path unaffected.
- `categories.py::reproduce_reversal_entries` docstring (4019-4037) now names the real call path and notes the prior false claim; `models.py::RunPlan.reversal_decisions`/`.config_view_records` docstrings (710-723, 724-739) name the real `_on_preview` -> `render_preview_extra_lines` -> `set_report(extra_lines=...)` chain.

## Verdict
Both P0 blockers from cycle 5 are CLOSED. QC gate is GREEN pending the verification RED-ness spot-check (cycle7-verification.md).

**Reviewed By:** lex-qc (cycle 7)
Files (all @ 930fe7c): config_views.py, preview.py, ui/main_window.py, ui/stats_panel.py, categories.py, models.py.
