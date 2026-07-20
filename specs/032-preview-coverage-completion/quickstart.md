# Quickstart & Validation Guide: Preview Coverage Completion

**Feature**: 032-preview-coverage-completion

This guide proves the feature end-to-end. Per SC-008, US1–US4 are validated by **offline
tests + a read-only live-render proof**; US5 by a **read-only probe**. No destructive Move
is required, so no attended `needs_human` gate applies.

## Prerequisites

- Repo at `d:\Github\_Projects\_LEX\GramTrans`; work performed on a feature worktree
  (`../GramTrans-032-preview-coverage-completion` on branch
  `032-preview-coverage-completion`) per the Git Workflow Protocol.
- Python 3 env with `pip install -e D:/Github/_Projects/_LEX/flexlibs2` (dist
  `pyflexicon>=4.1`).
- For live steps: FieldWorks projects `Ejagham Mini` (source) and `Ejagham Full GT-Test`
  (target), plus `Esperanto` / `Mbugwe Lizzie HCPractice` as read-only cross-checks,
  reachable via FLExToolsMCP.

## Offline validation (US1–US4)

Run the unit suite (no FLEx required):

```powershell
python -m pytest tests/unit/test_merge_preview_props.py `
                 tests/unit/test_merge_preview_html.py `
                 tests/unit/test_merge_preview_enrichment.py `
                 tests/unit/test_merge_preview_qt_free.py `
                 tests/unit/test_ws_mapping.py `
                 tests/unit/test_ws_mapping_detect.py `
                 tests/unit/test_032_preview_coverage.py -v
```

Expected:

- **SC-001**: each of the eight categories (Writing System, Complex Form Type, Ad hoc/
  Compound rule, Text, Phon Feature, Phon Rule, Slot, Natural Class) returns a non-empty
  props dict and non-blank HTML for a populated fixture item.
- **SC-003**: the Natural Class regression test shows Members/Features **absent before**
  the fix commit and **present after** on the same data (the fix is load-bearing).
- **SC-004**: a clean related-languages WS pair pre-fills primary→primary and every
  sub→sub (suffix match, incl. `eja-fonipa`→`abc-fonipa`) and confirms with no manual
  edits; an ambiguous/absent pair leaves the row unresolved with confirm gated.
- **SC-005 / FR-010**: `test_preview_no_writes.py` still passes — no preview writes.
- **SC-007**: `test_merge_preview_qt_free.py` passes — render core imports no PyQt.

## Read-only live-render proof (US1–US4, SC-008)

With `GRAMTRANS_E2E=1` and `flexicon` importable, run the read-only render pass over real
projects (extends `tests/integration/test_e2e_all_categories.py` and
`test_phase2_us2_ws_wizard.py`):

```powershell
$env:GRAMTRANS_E2E=1
python -m pytest tests/integration/test_e2e_all_categories.py `
                 tests/integration/test_phase2_us2_ws_wizard.py -v
```

Or via FLExToolsMCP directly: open `Ejagham Mini` → `Ejagham Full GT-Test`, render the
preview pane for one item in each of the eight categories, and assert category-appropriate
content (not blank, not error). Exercise the WS mapping step and confirm the defaults
pre-fill. **No Move is executed.**

Expected: **SC-002** — for each category a reviewer can tell what would transfer without
leaving GramTrans to open FieldWorks.

## Read-only probe (US5, SC-006)

```powershell
python debug/probe_adhoc_loss.py   # read-only; writes nothing to any project
```

Expected: an evidence artifact (what reproduced vs lost) + written root cause + scope
decision (follow-up-feature recommendation OR documented known limitation). If in-scope
loss is confirmed, verify it surfaces via the post-run report (never-silent, FR-017).

## Definition of Done

- [ ] All offline tests above pass (SC-001, SC-003, SC-004, SC-005, SC-007).
- [ ] Read-only live-render proof shows non-blank panes for all eight categories and WS
      default pre-fill (SC-002, SC-008) — no Move performed.
- [ ] US5 probe yields root cause + scope decision; any in-scope loss is never-silent
      (SC-006).
- [ ] No changes to `Lib/preview.py` / `Lib/transfer.py` write paths; render core stays
      Qt-free.

See [contracts/](contracts/) for the props, WS-default, and probe contracts, and
[data-model.md](data-model.md) for per-category field shapes.
