# Implementation Plan: Split the Selection Wizard into Page Modules

**Branch**: `039-wizard-split` | **Spec**: [spec.md](spec.md) | **Created**: 2026-08-19

**Worktree**: `../GramTrans-039-wizard-split` (per CLAUDE.md: spec artifacts to
`main`, implementation on a worktree).

## Structure Decision

The safety-critical cluster **does not move**. `selection_wizard.py` keeps
`SelectionWizard`, `flow()`, the `page_*` accessors, `MIN_WINDOW_WIDTH`,
`_PageFinish` (the single write point), `_PagePreview`, and all plan-assembly
functions. That leaves `test_036_finish_guard.py`, `test_plan_slot_guard.py`,
`test_034_move_gate_live.py`, `test_034_flextools_contract.py` and most of
`test_wizard_page_order.py` **untouched** — the tests guarding the live LCM write
are exactly the ones not worth rewriting for a refactor (FR-002).

The *pages* move out. They are the bulk and they hold all of the duplication.

## Target module layout

All new files in `src/gramtrans/Lib/ui/`, all prefixed `wizard_` (FR-008).

| Module | Contents | ~lines |
|---|---|---|
| `selection_wizard.py` | Facade + shell. Module docstring, `MIN_WINDOW_WIDTH/HEIGHT`, `SelectionWizard`, `_PagePreview`, `_PageFinish`, `_safe_compute_wizard_plan` / `_compute_wizard_plan` / `_set_`+`_take_plan_failure_reason`, `_phonology_excluded_lossy_for` + `_phonology_nc_or_phoneme_trimmed` + `_kl010_notice`, `_entry_types_missing_ref_for`, `_safe_path`, `_count_says_content`, and the re-export block | ~1750 |
| `wizard_page_base.py` | `_FlowPage` (moves verbatim — it has **zero** external references), `_ProjectHandlesMixin`, `_PickDerivedMixin`, `_BlockPage` | ~420 |
| `wizard_widgets.py` | `_page_progress`, `_source_counts_of`, `_operation_failed_note`, `_show_failure_row`, `_make_tree_pane_splitter`, `_item_views_of`, `_elide_over_narrow_columns`, `_set_item_text_with_tooltip`, `_carry_full_values_in_tooltips`, `_make_group_item`, `_count_affixes_in_node`, `_TREE_PANE_MIN_WIDTH`, `_PREVIEW_PANE_MIN_WIDTH` | ~330 |
| `wizard_roles.py` | Every `Qt.ItemDataRole.UserRole + N` constant in one renumbered, collision-free block, plus `_STATUS_LABELS`, `_RULES_STATUS_LABELS`, `_CF_LEVEL_LABELS` | ~100 |
| `wizard_page_projects.py` | `_PageProjects` | ~430 |
| `wizard_page_ws.py` | `_PageWritingSystems`, `_enumerate_active_ws_ids`, `_enumerate_ws_by_kind` | ~500 |
| `wizard_pages_pickers.py` | `_PageItemPicker`, `_PageStemPicker` (share `_make_group_item` and the affix roles) | ~860 |
| `wizard_pages_skeleton.py` | `_PageSkeleton`, `_PageGramDeps` (both derive from affix/stem picks; share `_STATUS_LABELS`) | ~890 |
| `wizard_pages_blocks.py` | The four Model-B "independent block" pages on `_BlockPage`: `_PageCustomFields`, `_PageRules`, `_PagePhonology`, `_PageEntryTypes` | ~810 |
| `wizard_page_texts.py` | `_PageTexts` | ~200 |
| `wizard_pages_deferred.py` | Constructed for back-compat but absent from `flow()`: `_PageScopeConflict`, plus its exclusive constants `_allowed_modes`, `_CONFLICT_LABELS`, `_SCOPE_LABELS`, `_SCHEMA_CATEGORIES`, `_GOLD_RESERVED`, `_CUSTOM_FIELDS_ONLY`, `_CATEGORY_TOGGLES` | ~230 |

The grouping follows `specs/wizard-selection-roadmap.md`'s own two selection
models: Model B (independent block, wholesale NONE/ALL) becomes
`wizard_pages_blocks.py`; Model A (item-derived) becomes
`wizard_pages_pickers.py` + `wizard_pages_skeleton.py`. The four pages carrying
the duplicated whole-block cluster **are** exactly the Model-B pages, so
`_BlockPage` is domain-justified rather than merely DRY-motivated.

### Why there are no circular imports

Every cross-page read already goes through `self.wizard()` → a named
`SelectionWizard.page_*()` accessor → a duck-typed method call. **No page class
references `SelectionWizard` or any sibling page class by name.** `_FlowPage.nextId`
likewise only touches `wizard.flow()` and `wizard.flow_page_id(attr)`. The import
graph is therefore strictly one-directional: facade → page modules →
base/widgets/roles.

`_PagePreview` and `_PageFinish` stay in the facade precisely because they *do*
call facade-level functions (`_safe_compute_wizard_plan`,
`_take_plan_failure_reason`). Keeping `_phonology_excluded_lossy_for` and
`_entry_types_missing_ref_for` there too means their three `monkeypatch.setattr(sw, ...)`
sites need no change at all.

### House conventions for each new module

Copy the pattern from `page_header.py` and `stats_panel.py`:

- Discursive module docstring: one-line summary with an ID citation on line 1
  (`"""...(feature 039, T0NN)."""`), then a "Why this module exists" section and a
  "What is deliberately absent" note. Per FR-010, existing rationale comments move
  **verbatim** with their code.
- `from __future__ import annotations`, then stdlib, then `from PyQt6 import ...`
  (unguarded — Qt is never conditional here).
- The dual-mode guard, in **both** branches (FR-007):
  ```python
  if __package__:
      from ..models import GrammarCategory
      from .wizard_page_base import _FlowPage, _ProjectHandlesMixin
  else:
      from models import GrammarCategory  # type: ignore
      from wizard_page_base import _FlowPage, _ProjectHandlesMixin  # type: ignore
  ```
- No `__all__` (there is none anywhere in `Lib/`), no `Lib/ui/__init__.py`
  re-export. 75-dash section dividers. `# noqa: N802 -- Qt naming` on Qt overrides.
- ruff has `I` (isort) and `F` on with `ignore = []` and no per-file-ignores, so
  the facade's re-export block needs `# noqa: F401` on each line.

## Deduplication (FR-004)

### `_ProjectHandlesMixin` — saves ~235 lines

`_get_source` and `_get_target` are byte-identical across `_PageStemPicker`,
`_PageSkeleton`, `_PageGramDeps`, `_PageCustomFields`, `_PageRules`,
`_PagePhonology`, `_PageTexts` (and `_PageItemPicker`, which differs only in local
variable names and a comment). Lift one copy into the mixin.

**One genuine divergence, preserved as an explicit override.**
`_PageEntryTypes._get_source` (`selection_wizard.py:4925`) skips the context and
reads `wizard._host` directly:

```python
def _get_source(self):
    wizard = self.wizard()
    if wizard is None:
        return None
    return getattr(wizard, "_host", None)
```

That looks like a defect — it ignores a source handle bound on step 1 via
`context.source_handle` — but changing it changes behaviour. Keep it as a
documented override and raise it as a follow-up question. Do not silently
normalise it inside a refactor.

`_get_affix_picks`/`_get_stem_picks` are byte-equivalent in `_PageSkeleton` and
`_PageGramDeps` → `_PickDerivedMixin` (~30 lines).

### `_BlockPage` — saves ~240 lines

Seven methods — `_on_whole_block_clicked`, `_set_all_items`,
`_refresh_whole_block`, `_on_item_changed`, `_has_any_item`, `_all_items_checked`,
`whole_block_on` — are **identical** across all four block pages (differences
confined to docstring wording, `_g`/`_grp`/`group` loop names, and one line wrap).
The cluster depends on exactly three attributes: `self._tree`,
`self._whole_block`, `self._mirroring`.

The eighth, `_iter_item_rows`, differs only in which role constant it keys on →
make it a `_kind_role` class attribute on the base, with `_PageEntryTypes`
overriding the method for its nested walk.

**Not** pulled into the base: the four collect APIs have genuinely different
contracts — `leaf_item_picks() -> dict`, `collect_rules_picks() -> Optional[frozenset]`
(`None` means transfer-all), `collect_phonology_picks() -> dict[GrammarCategory, set]`,
`collect_entry_type_picks() -> dict`. Only `_PagePhonology` and `_PageEntryTypes`
have `deselected_needed_guids()`.

`_PageSkeleton` also has an `_on_item_changed` and uses `_mirroring`, but for
template-slot semantics — unrelated. It does not get `_BlockPage`.

### The two latent defects — each its own commit

1. **Role collision.** Renumber `_ET_*` off `UserRole + 70..73` in
   `wizard_roles.py`. Safe: `test_032_preview_pane_wiring.py` *imports* the
   constants rather than hardcoding their numeric values.
2. **`_PageEntryTypes._iter_item_rows`.** `yield from _walk(child, False)`, and
   delete `if in_group_item or True`. **This changes behaviour** — rows under a
   nested group start being counted, which moves the whole-block tristate on
   nested entry-type trees. Land it separately, with a test pinning the new
   counts, so it is revertible independently of the split.

Also drop the unused `MERGE_KEEP` import. Keep `_set_item_text_with_tooltip` even
though nothing calls it — `test_036_min_width_layout.py` asserts it is exposed.

## Test-suite work

This is the substance of the feature, not an afterthought.

**New shared helper `tests/unit/_wizard_source.py`** exposing
`wizard_package_source() -> str` (concatenated text of `selection_wizard.py` plus
every `wizard_*.py`) and `wizard_modules() -> list[ModuleType]`. Then:

- **Broaden the two silently-weakening scans** to the package (FR-005) —
  `test_036_wizard_flow_numbering.py:512` (`Step \d+ of \d+`) and
  `test_wizard_page_order.py:110` (`\.page\(\d+\)`). Both currently cannot see a
  violation introduced in any other UI module.
- **Convert the two class-scoped source scans to `inspect.getsource`** —
  `test_phonology_inventory.py:205-224` (AST scan of `_PagePhonology`) and
  `test_entry_types_display.py:93/112/134` (regex over the `_PageEntryTypes`
  body). `inspect.getsource(cls)` follows the object, making these immune to this
  move *and* any future one. Preferred over re-pointing at a module path.
- **Re-point 10 monkeypatch sites** to the module whose globals the caller now
  reads: `test_034_step1_source_picker.py` ×9 (`sw` → `wizard_page_projects` for
  `SourcePickerDialog`) and `test_036_wizard_flow_numbering.py:406`
  (`sw` → `wizard_pages_skeleton` for `build_deps_inventory`).

**Four new guard tests** in `tests/unit/test_039_module_split.py`:

1. **One Qt base across all page classes.** `test_wizard_page_flow.py:99/107`
   overwrites `QtWidgets.QWizard`/`QWizardPage` in `sys.modules` at import time;
   each new module's `class _PageX(QtWidgets.QWizardPage)` captures whichever base
   is installed at *that module's* import moment. The facade importing all page
   modules eagerly keeps this consistent — assert it, because a lazy import added
   later would silently produce mixed bases. (See `_ui_geometry.needs_a_real_qwizard()`
   for the existing documentation of this hazard.)
2. **The facade re-exports every compatibility name** (FR-006), parametrized over
   an explicit list, so a future move cannot silently drop one.
3. **No `UserRole + N` offset is claimed by two role constants** — retires defect 1
   permanently.
4. **One write point package-wide**: exactly one function across all wizard modules
   calls `.execute_move`. Complements the in-file scan at
   `test_036_finish_guard.py:623`, which stays as-is.

Preserve the `assert total > 0` / `assert match` idiom already used in this suite —
a structural test that can pass vacuously is the failure mode this whole section
exists to prevent.

## Housekeeping CI will otherwise fail on (FR-009)

1. **`.github/scripts/check_shared_exceptions.py`** (regression workflow step 3)
   diffs `main...HEAD`, collects every changed file under `src/gramtrans/Lib/`, and
   fails unless each appears as a numbered row in
   `specs/034-standalone-windows-app/plan.md`'s exception table. Its docstring is
   explicit: *"Additions count as changes."* The table has 10 rows today →
   **add 11**: the 10 new `wizard_*.py` files plus `Lib/debuglog.py`.
   `selection_wizard.py` is already covered by rows 2, 3 and 8.
2. **`src/gramtrans/Lib/debuglog.py:47` `LOGGER_NAMES`** is a hand-written tuple
   containing `"selection_wizard"`. Under flat import `logging.getLogger(__name__)`
   yields the bare stem, so each new module needs an entry or its `_module_log`
   output goes unconfigured in the FlexTools/frozen host.

`build/hiddenimports.py` needs **no** edit — it globs `LIB_DIR.rglob("*.py")` and
emits both flat and dotted names. Still run it to confirm no new flat-name collision.

Also update `specs/038-transfer-fidelity-gaps/plan.md:181`, which records
`selection_wizard.py 6512 L`.

## Sequencing — five commits on `039-wizard-split`

| # | Commit | Content |
|---|---|---|
| 1 | `refactor(039): wizard page base, widgets and roles` | Create `wizard_page_base.py`, `wizard_widgets.py`, `wizard_roles.py` by **verbatim relocation**. Facade re-exports. `debuglog` + exception-table rows. Suite green with no test edits. |
| 2 | `refactor(039): move the twelve page classes out of the facade` | Create the 8 page modules, still verbatim (mixins declared but not yet applied). Re-point the 10 monkeypatches and the 2 class-scoped source scans. |
| 3 | `refactor(039): collapse the duplicated accessors and whole-block cluster` | Apply `_ProjectHandlesMixin`, `_PickDerivedMixin`, `_BlockPage`. Delete the duplicates. `_PageEntryTypes._get_source` kept as a documented override. |
| 4 | `test(039): package-wide structural guards` | `_wizard_source.py`, broaden the 2 vacuous scans, add the 4 guard tests. |
| 5 | `fix(039): role-number collision and the entry-types nested walk` | The two latent defects, with tests. Separately revertible. |

Commits 1-3 must be reviewable as pure relocations — `git diff -M --find-copies-harder`
should render the moved hunks as renames wherever possible.

## Verification

Baseline first, on `main`, so the comparison is real:

```powershell
python -m pytest tests/unit -q -m "not integration" > baseline.txt
```

Expect one pre-existing failure —
`test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos`
is the documented baseline entry at `.github/known-failures.txt:47`. Do not "fix"
it here; the baseline checker fails on a baseline entry that starts passing.

After each commit:

```powershell
# SC-001. Fails on any new failure AND on any baseline entry that starts passing.
python .github/scripts/check_suite_baseline.py

# SC-002. The FlexTools contract, standalone (CI runs it as its own step).
python -m pytest tests/unit/test_034_flextools_contract.py -q

# SC-003. Shared-code exception table.
python .github/scripts/check_shared_exceptions.py --base main

# SC-004. Flat-name collisions for the new wizard_* stems.
python build/hiddenimports.py

# SC-005. isort + F401 are on with no per-file-ignores.
python -m ruff check src/gramtrans/Lib/ui/
```

`QT_QPA_PLATFORM=offscreen` and `GRAMTRANS_NO_THEME=1` need no manual setting —
the root `conftest.py` and the Qt test modules `setdefault` them.

**Two ordering hazards when running subsets.** `test_wizard_page_flow.py` and
`test_ui_gating.py` replace `QtWidgets.QWizard`/`QWizardPage` in `sys.modules` at
import time, which is why `_ui_geometry.needs_a_real_qwizard()` exists. Running
them alongside the geometry tests produces skips; running them alone produces
different results. **Always compare full-suite runs, never subset runs.**

**SC-006 — both import modes.** Package mode is what pytest exercises; flat mode
is the FlexTools and frozen path, and the entire `if __package__:` dual-branch
story lives there:

```powershell
python -c "import site,os; d=r'src/gramtrans/Lib'; site.addsitedir(d); site.addsitedir(os.path.join(d,'ui')); import selection_wizard as sw; print(sw.SelectionWizard, len([n for n in dir(sw) if n.startswith('_Page')]))"
```

**SC-007 — live smoke, last.** A refactor that keeps every test green can still
break the window. Launch the real wizard with `run_gui_harness.py` and walk all 12
pages against the read-only `Ejagham Mini` source, confirming: step numbering is
consecutive with no `of N`, each page's header renders and the theme strip moves
with it, tree/preview splitters hold at a 900 px window, and the block pages'
tristate behaves at empty / partial / full.

**Preview only — no Move.** If a Move is wanted, restore the throwaway `Target`
first via `tests/integration/harness/restore.py`. Never point this at `Esperanto`,
and never at `Ngoreme Target` or `Ejagham W Target`, which STATUS.md records as
freshly verified clean.
