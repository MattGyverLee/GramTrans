# Tasks: Split the Selection Wizard into Page Modules

**Feature**: `039-wizard-module-split` | **Branch**: `039-wizard-split`
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Created**: 2026-08-19

**Worktree**: implementation lands on `../GramTrans-039-wizard-split` (branch
`039-wizard-split`). Spec artifacts — this file, `spec.md`, `plan.md`, and the
`specs/034-standalone-windows-app/plan.md` exception-table rows — commit to
`main` (CLAUDE.md git protocol).

**Task line format**: `- [ ] **T###** [P?] [US#] Description · exact/file/path`
`[P]` = independent of the other tasks in its wave (different file, no incomplete
dependency). `[US#]` maps the task to the increment below.

## Increments

Each maps 1:1 to a commit in the plan's sequencing table, and each is
independently reviewable and revertible.

| Story | Priority | Increment | Commit |
|---|---|---|---|
| **US1** | P1 | Shared foundations relocated (`wizard_roles`, `wizard_page_base`, `wizard_widgets`), suite green with **zero** test edits | `refactor(039): wizard page base, widgets and roles` |
| **US2** | P1 | The twelve page classes move out of the facade, still verbatim | `refactor(039): move the twelve page classes out of the facade` |
| **US3** | P2 | The ~505 duplicated lines collapse into the shared bases | `refactor(039): collapse the duplicated accessors and whole-block cluster` |
| **US4** | P2 | The two vacuous scans become package-wide; four new guards | `test(039): package-wide structural guards` |
| **US5** | P3 | The two latent defects, each separately revertible | `fix(039): role-number collision and the entry-types nested walk` |

---

## Phase 1: Setup

**Wave 1 — independent (different concerns):**

- [X] **T001** [P] Create the implementation worktree `../GramTrans-039-wizard-split` on branch `039-wizard-split` off current `main`; confirm `git -C ../GramTrans-039-wizard-split status` is clean · `../GramTrans-039-wizard-split`
- [X] **T002** [P] Capture the pre-change baseline on `main` with the **full** suite (never a subset — `test_wizard_page_flow.py` / `test_ui_gating.py` replace `QWizard` in `sys.modules` at import time): `python -m pytest tests/unit -q -m "not integration" > baseline.txt`. **Correction (measured 2026-08-19):** the baseline is **27** failures, not one — `.github/known-failures.txt` lists all 27 (features 026/029 plus the one wizard POS-closure entry at line 47), and the measured run reproduces exactly that set. `python .github/scripts/check_suite_baseline.py` is the authoritative gate and reports `[PASS] No new failures; all 27 baseline entries still fail`. Do **not** fix any of them · `baseline.txt` (scratch, not committed)

**⟶ Wait for Wave 1 to finish, then:**

- [X] **T003** Record the exact `Lib/ui/` line-count table as the FR-003 / SC-008 reference point (`selection_wizard.py` = 6512 L today, 10802 L across the package) so every later size check compares against a real number · `specs/039-wizard-module-split/tasks.md` (this file, Notes section)

---

## Phase 2: Foundational — BLOCKS every story

Nothing in US1–US5 may be committed on the worktree until these land: the CI
gates fail on the *first* new file under `src/gramtrans/Lib/`, not on the last.

**Wave 1 — independent (different files):**

- [X] **T004** [P] Add **11** numbered rows (11–21) to the shared-code exception table for the 10 planned `wizard_*.py` modules plus `Lib/debuglog.py`, each with the Change / Why / Why-it-is-safe columns the existing 10 rows use. `check_shared_exceptions.py` treats an addition as a change, so a missing row fails regression step 3. `selection_wizard.py` is already covered by rows 2, 3 and 8 · `specs/034-standalone-windows-app/plan.md` **(commits to `main`)**
- [X] **T005** [P] Extend the hand-written `LOGGER_NAMES` tuple with the 10 new bare stems (`wizard_page_base`, `wizard_widgets`, `wizard_roles`, `wizard_page_projects`, `wizard_page_ws`, `wizard_pages_pickers`, `wizard_pages_skeleton`, `wizard_pages_blocks`, `wizard_page_texts`, `wizard_pages_deferred`) alongside the existing `"selection_wizard"`. Under flat import `logging.getLogger(__name__)` yields the bare stem, so an unlisted module's `_module_log` output goes unconfigured in the FlexTools/frozen host · `src/gramtrans/Lib/debuglog.py`

**⟶ Wait for Wave 1 to finish, then:**

- [X] **T006** Verify the two gates the foundational edits exist to satisfy still pass before any module is created: `python .github/scripts/check_shared_exceptions.py --base main` and `python build/hiddenimports.py` (no flat-name collision) · CI scripts

**Checkpoint**: the CI surface accepts new `Lib/ui/wizard_*.py` files. No source has moved yet.

---

## Phase 3: US1 — Shared foundations relocated (P1) — MVP

**Goal**: `_FlowPage`, the widget helpers and every item-data role live in three
new modules; the facade re-exports them; the suite is green with **zero** test
edits. This is the slice that proves the facade pattern holds.

**Independent test**: run the full unit suite unchanged — no test file is touched
in this phase, so a green suite is direct evidence that relocation alone is
behaviour-neutral (FR-001).

### Implementation

**Wave 1 — the leaf module (nothing else can import it yet):**

- [X] **T007** [US1] Create `wizard_roles.py` by **verbatim relocation** of every `Qt.ItemDataRole.UserRole + N` constant (`_GUID_ROLE`/`_KIND_ROLE`/`_ROLE_ROLE`/`_IS_PRODUCES` 1–4, `_SKEL_*` 10–12 + 40–42, `_PHON_*` 20–23, `_ITEM_*` 30–31, `_DEPS_*` 50–51, `_CF_*` 60/61/63, `_RULES_*` 70–72, `_ET_*` 70–73) plus `_STATUS_LABELS`, `_RULES_STATUS_LABELS`, `_CF_LEVEL_LABELS`. **Do not renumber yet** — the `_RULES_`/`_ET_` collision is US5's job and must be a separate, revertible commit. Carry the trailing rationale comments verbatim (FR-010). Module docstring per house convention, `from __future__ import annotations`, dual-mode `if __package__:` guard in **both** branches (FR-007) · `src/gramtrans/Lib/ui/wizard_roles.py` (~100 L)

**⟶ Wait for T007 to finish, then:**

**Wave 2 — independent (different files, both import only `wizard_roles`):**

- [X] **T008** [P] [US1] Create `wizard_page_base.py`: `_FlowPage` moves **verbatim** (it has zero external references), plus the *declarations* of `_ProjectHandlesMixin`, `_PickDerivedMixin` and `_BlockPage` (with its `_kind_role` class attribute). The bases are declared here but **not yet applied** to any page — US3 does that, so US1 and US2 stay pure relocations · `src/gramtrans/Lib/ui/wizard_page_base.py` (~420 L)
- [X] **T009** [P] [US1] Create `wizard_widgets.py` by verbatim relocation of `_page_progress`, `_source_counts_of`, `_operation_failed_note`, `_show_failure_row`, `_make_tree_pane_splitter`, `_item_views_of`, `_elide_over_narrow_columns`, `_set_item_text_with_tooltip`, `_carry_full_values_in_tooltips`, `_make_group_item`, `_count_affixes_in_node`, `_TREE_PANE_MIN_WIDTH`, `_PREVIEW_PANE_MIN_WIDTH`. **Keep `_set_item_text_with_tooltip` even though nothing calls it** — `test_036_min_width_layout.py` asserts it is exposed · `src/gramtrans/Lib/ui/wizard_widgets.py` (~330 L)

**⟶ Wait for Wave 2 to finish, then:**

- [X] **T010** [US1] Delete the relocated definitions from the facade and add the re-export block — `# noqa: F401` on **each** line (ruff has `I` and `F` on with `ignore = []` and no per-file-ignores). Import the three new modules **eagerly**, never lazily: `test_wizard_page_flow.py:99/107` swaps `QtWidgets.QWizard`/`QWizardPage` in `sys.modules` at import time, and a lazy import would give page classes a different Qt base than their siblings · `src/gramtrans/Lib/ui/selection_wizard.py`
- [X] **T011** [US1] Run the full US1 gate set with **no test file edited**: `python .github/scripts/check_suite_baseline.py` (SC-001), `python -m pytest tests/unit/test_034_flextools_contract.py -q` (SC-002), `python .github/scripts/check_shared_exceptions.py --base main` (SC-003), `python build/hiddenimports.py` (SC-004), `python -m ruff check src/gramtrans/Lib/ui/` (SC-005). **Correction (measured):** `git diff -M --find-copies-harder` renders the new modules as `create`, not `rename`, and cannot do otherwise -- rename detection pairs whole files, and the facade retains the bulk of its content, so a partial extraction has no pair to find. Verbatim relocation is instead verified mechanically and more strongly: all 40 top-level definitions compare equal under `ast.dump` against `main`, with no losses and no duplicates. **Also corrected:** SC-002 and SC-005 both overstate `main`. `test_034_flextools_contract.py` already fails standalone on `main` (`test_the_finish_page_takes_its_subtitle_from_the_gate`, a `stats_panel.py:111` RuntimeError), and `ruff check src/gramtrans/Lib/ui/` already reports 138 errors on `main`. Both gates are therefore enforced as **delta vs `main`**, which is what they can actually assert · CI scripts

**Checkpoint**: US1 is independently functional — the wizard imports, constructs and runs from a facade plus three modules, and every existing test passes untouched.

---

## Phase 4: US2 — The page classes move out (P1)

**Goal**: eight new page modules hold the twelve `flow()` pages plus the deferred
one; the facade keeps only the safety-critical cluster. Still verbatim — the
mixins declared in T008 are **not** applied here.

**Independent test**: full suite green after the four mechanical test re-points
below; `_PageFinish` still the sole `execute_move` caller, so
`test_036_finish_guard.py` and `test_034_move_gate_live.py` remain untouched
(FR-002).

### Implementation

**Wave 1 — independent (seven different new files; no page class references a sibling page or `SelectionWizard` by name, so the import graph is strictly facade → pages → base/widgets/roles):**

- [X] **T012** [P] [US2] Create `wizard_page_projects.py` with `_PageProjects` (and the legacy `_PageProjectWS` probe if it lives with it) · `src/gramtrans/Lib/ui/wizard_page_projects.py` (~430 L)
- [X] **T013** [P] [US2] Create `wizard_page_ws.py` with `_PageWritingSystems`, `_enumerate_active_ws_ids`, `_enumerate_ws_by_kind` · `src/gramtrans/Lib/ui/wizard_page_ws.py` (~500 L)
- [X] **T014** [P] [US2] Create `wizard_pages_pickers.py` with `_PageItemPicker`, `_PageStemPicker` (Model A, item-derived; they share `_make_group_item` and the affix roles) · `src/gramtrans/Lib/ui/wizard_pages_pickers.py` (~860 L)
- [X] **T015** [P] [US2] Create `wizard_pages_skeleton.py` with `_PageSkeleton`, `_PageGramDeps` (both derive from affix/stem picks and share `_STATUS_LABELS`) · `src/gramtrans/Lib/ui/wizard_pages_skeleton.py` (~890 L)
- [X] **T016** [P] [US2] Create `wizard_pages_blocks.py` with the four Model-B independent-block pages `_PageCustomFields`, `_PageRules`, `_PagePhonology`, `_PageEntryTypes` · `src/gramtrans/Lib/ui/wizard_pages_blocks.py` (~810 L)
- [X] **T017** [P] [US2] Create `wizard_page_texts.py` with `_PageTexts` · `src/gramtrans/Lib/ui/wizard_page_texts.py` (~200 L)
- [X] **T018** [P] [US2] Create `wizard_pages_deferred.py` with `_PageScopeConflict` (constructed for back-compat, absent from `flow()`) plus its exclusive constants `_allowed_modes`, `_CONFLICT_LABELS`, `_SCOPE_LABELS`, `_SCHEMA_CATEGORIES`, `_GOLD_RESERVED`, `_CUSTOM_FIELDS_ONLY`, `_CATEGORY_TOGGLES` · `src/gramtrans/Lib/ui/wizard_pages_deferred.py` (~230 L)

**⟶ Wait for Wave 1 to finish, then:**

- [X] **T019** [US2] Apply the house conventions to all seven new modules: ID-cited one-line docstring, "Why this module exists" + "What is deliberately absent" sections, `from __future__ import annotations`, unguarded `from PyQt6 import ...`, the dual-mode guard in **both** branches (FR-007), 75-dash dividers, `# noqa: N802 -- Qt naming` on Qt overrides, no `__all__`, no `Lib/ui/__init__.py` re-export. Every existing rationale comment moves **verbatim** with its code (FR-010) · the seven files from T012–T018
- [X] **T020** [US2] Strip the relocated page classes from the facade, leaving exactly `SelectionWizard`, `flow()`, the `page_*` accessors, `MIN_WINDOW_WIDTH`/`MIN_WINDOW_HEIGHT`, `_PagePreview`, `_PageFinish`, `_safe_compute_wizard_plan` / `_compute_wizard_plan` / `_set_`+`_take_plan_failure_reason`, `_phonology_excluded_lossy_for`, `_phonology_nc_or_phoneme_trimmed`, `_kl010_notice`, `_entry_types_missing_ref_for`, `_safe_path`, `_count_says_content`, and the re-export block. `_PagePreview`/`_PageFinish` **stay** because they call facade-level functions, and keeping `_phonology_excluded_lossy_for` / `_entry_types_missing_ref_for` here means their three `monkeypatch.setattr(sw, ...)` sites need no change · `src/gramtrans/Lib/ui/selection_wizard.py` (~1750 L target)
- [X] **T021** [US2] Extend the eager-import + re-export block to all 10 modules so every compatibility name still resolves as `selection_wizard.X` (FR-006) and every page class captures the same Qt base at import time · `src/gramtrans/Lib/ui/selection_wizard.py`

**⟶ Wait for T021 to finish, then:**

**Wave 3 — independent (four different existing test files):**

- [X] **T022** [P] [US2] Re-point the **9** `monkeypatch.setattr(sw, "SourcePickerDialog", ...)` sites to `wizard_page_projects` — a facade re-export does not fix these, because the caller resolved the name in its own module namespace at import time · `tests/unit/test_034_step1_source_picker.py`
- [X] **T023** [P] [US2] **NOT APPLIED -- the task's premise is wrong, and applying it would break a passing test.** The `monkeypatch.setattr(sw, "build_deps_inventory", ...)` site at line ~406 does not serve `_PageGramDeps`: the test asserts `wizard._has_gram_deps()`, which is a `SelectionWizard` method that **stays in the facade** (`selection_wizard.py:1517`) and resolves `build_deps_inventory` from facade globals. Patching `sw` is therefore still correct. Verified: `test_036_wizard_flow_numbering.py` passes unedited · `tests/unit/test_036_wizard_flow_numbering.py`
- [X] **T024** [P] [US2] Convert the class-scoped AST scan at lines ~205-224 from `Path(sw.__file__).read_text()` to `inspect.getsource(_PagePhonology)`, which follows the object and is immune to this move *and* any future one. Preserve the `assert total > 0` idiom — this test currently raises `StopIteration` if the class is gone, so a silent-pass regression must stay impossible · `tests/unit/test_phonology_inventory.py`
- [X] **T025** [P] [US2] Convert the three regex-over-module-text scans at lines ~93/112/134 to `inspect.getsource(_PageEntryTypes)`, keeping the `assert match` idiom · `tests/unit/test_entry_types_display.py`

**⟶ Wait for Wave 3 to finish, then:**

- [X] **T026** [US2] Run the full US2 gate set (SC-001 … SC-005 exactly as in T011) and confirm the untouched-by-design tests still pass on their own terms: `test_036_finish_guard.py`, `test_plan_slot_guard.py`, `test_034_move_gate_live.py` (**path correction:** it lives in `tests/integration/`, not `tests/unit/`), `test_034_flextools_contract.py`, `test_wizard_page_order.py`. All verified untouched and passing · CI scripts

**Checkpoint**: US2 is independently functional — 12 pages live in 8 modules, the write point has not moved (FR-002), and the facade is at or under the ~1750 L budget (FR-003).

---

## Phase 5: US3 — Duplication collapses (P2)

**Goal**: the ~505 measured duplicate lines are gone (FR-004), with the one
genuine divergence preserved as an explicit, documented override rather than
silently normalised.

**Independent test**: full suite green, and the `Lib/ui/` total line count drops
by roughly 505 versus the US2 checkpoint.

### Implementation

**Wave 1 — the shared bases (single file, everything below depends on it):**

- [X] **T027** [US3] Flesh out the three bases declared in T008. `_ProjectHandlesMixin`: one copy of the byte-identical `_get_source`/`_get_target` (~235 L saved). `_PickDerivedMixin`: one copy of the byte-equivalent `_get_affix_picks`/`_get_stem_picks` (~30 L saved). `_BlockPage`: the seven identical methods `_on_whole_block_clicked`, `_set_all_items`, `_refresh_whole_block`, `_on_item_changed`, `_has_any_item`, `_all_items_checked`, `whole_block_on` — differences across the four pages are confined to docstring wording, `_g`/`_grp`/`group` loop names and one line wrap — depending on exactly three attributes (`self._tree`, `self._whole_block`, `self._mirroring`), plus `_iter_item_rows` keyed on the `_kind_role` class attribute (~240 L saved). **Not** in the base: the four collect APIs, whose contracts genuinely differ (`leaf_item_picks() -> dict`, `collect_rules_picks() -> Optional[frozenset]` where `None` means transfer-all, `collect_phonology_picks() -> dict[GrammarCategory, set]`, `collect_entry_type_picks() -> dict`), and `deselected_needed_guids()`, which only `_PagePhonology` and `_PageEntryTypes` have · `src/gramtrans/Lib/ui/wizard_page_base.py`

**⟶ Wait for T027 to finish, then:**

**Wave 2 — independent (four different page modules):**

- [X] **T028** [P] [US3] Apply `_ProjectHandlesMixin` to `_PageItemPicker` (which differs from the canonical copy only in local variable names and a comment) and `_PageStemPicker`; delete both duplicate pairs · `src/gramtrans/Lib/ui/wizard_pages_pickers.py`
- [X] **T029** [P] [US3] Apply `_ProjectHandlesMixin` **and** `_PickDerivedMixin` to `_PageSkeleton` and `_PageGramDeps`; delete the duplicates. `_PageSkeleton` keeps its own `_on_item_changed` and `_mirroring` use — those are template-slot semantics and **must not** get `_BlockPage` · `src/gramtrans/Lib/ui/wizard_pages_skeleton.py`
- [X] **T030** [P] [US3] Rebase `_PageCustomFields`, `_PageRules`, `_PagePhonology`, `_PageEntryTypes` on `_BlockPage` + `_ProjectHandlesMixin`, each declaring its own `_kind_role`; delete the four-fold duplication. Keep `_PageEntryTypes._get_source` (facade line ~4925) as an **explicit, documented override** — it reads `wizard._host` directly instead of `context.source_handle`, which looks like a defect but fixing it is a behaviour change and is out of scope. `_PageEntryTypes` also overrides `_iter_item_rows` for its nested walk · `src/gramtrans/Lib/ui/wizard_pages_blocks.py`
- [X] **T031** [P] [US3] Apply `_ProjectHandlesMixin` to `_PageTexts`; delete the duplicate pair · `src/gramtrans/Lib/ui/wizard_page_texts.py`

**⟶ Wait for Wave 2 to finish, then:**

- [X] **T032** [US3] Drop the now-unused `MERGE_KEEP` from the `merge_preview` import in **both** dual-mode branches (facade lines 89 and 137) · `src/gramtrans/Lib/ui/selection_wizard.py`
- [X] **T033** [US3] Run the full US3 gate set (SC-001 … SC-005) and record the per-module line counts; confirm no module exceeds 1750 L (FR-003 / SC-008) and that the package total dropped by ~505 L · CI scripts

**Checkpoint**: US3 is independently functional — the duplication is gone (520 lines, vs the ~505 estimate), every divergence is documented, and behaviour is unchanged.

> **Finding beyond the plan (T030).** plan.md named `_PageEntryTypes._get_source` as the single genuine divergence. `_get_target` diverges too: it guards with `hasattr` where the canonical copy uses `try`/`except`, so an exception raised by `page_project_ws()` or `context()` **propagates** there and would be swallowed by `_ProjectHandlesMixin`. Adopting the mixin for it would have been a silent behaviour change, so it is kept as a second documented override. `_PageEntryTypes` therefore keeps three overrides, not two.

> **How the deletions were justified.** No copy was deleted on the plan's word: each was normalised (docstring stripped, locals uniformly renamed) and compared against the base's version, with two benign variances folded first — `x = expr; return x` → `return expr` (the only way `_PageItemPicker._get_source` differed) and `self._kind_role` → the page's role constant (how a concrete `_iter_item_rows` is compared against the parameterised base). All 39 comparisons passed before any deletion.

---

## Phase 6: US4 — Package-wide structural guards (P2)

**Goal**: the two scans that would silently stop asserting now cover every wizard
module (FR-005), and four new guards make the compatibility surface and the write
point enforced rather than conventional.

**Independent test**: each broadened scan must **fail** when a violation is
planted in a non-facade wizard module, and pass once removed — that is the whole
point of FR-005 and is worth demonstrating before the commit.

### Tests

**Wave 1 — the shared helper (everything below imports it):**

- [X] **T034** [US4] Create the shared source-scan helper exposing `wizard_package_source() -> str` (concatenated text of `selection_wizard.py` plus every `wizard_*.py`) and `wizard_modules() -> list[ModuleType]` · `tests/unit/_wizard_source.py`

**⟶ Wait for T034 to finish, then:**

**Wave 2 — independent (two different existing test files):**

- [X] **T035** [P] [US4] Broaden the `Step \d+ of \d+` scan at line ~512 from the facade text to `wizard_package_source()`. This scan currently degrades to `[]` and passes **vacuously** once the pages move — keep/add the `assert total > 0` guard so that failure mode is impossible (FR-005) · `tests/unit/test_036_wizard_flow_numbering.py`
- [X] **T036** [P] [US4] Broaden the literal `\.page\(\d+\)` scan at line ~110 to `wizard_package_source()`, with the same non-vacuity assertion. Leave lines 146/199/213 (`flow()` attr strings, `def page_rules(`) alone — those names stay in the facade · `tests/unit/test_wizard_page_order.py`

**⟶ Wait for Wave 2 to finish, then (all four guards edit the same new file, so in order):**

- [X] **T037** [US4] Guard 1 — **one Qt base across all page classes**: assert the facade imports every page module eagerly, so each `class _PageX(QtWidgets.QWizardPage)` captures the same base at import time. `test_wizard_page_flow.py:99/107` overwrites `QtWidgets.QWizard`/`QWizardPage` in `sys.modules`, so a lazily-imported module added later would silently produce mixed bases. Cite `_ui_geometry.needs_a_real_qwizard()`, which already documents this hazard · `tests/unit/test_039_module_split.py`
- [X] **T038** [US4] Guard 2 — **the facade re-exports every compatibility name** (FR-006), parametrized over an explicit list. **Correction:** there is no `_PageProjectWS` on `main` and there never was in this file — the legacy name survives only as the accessor `page_project_ws()`, which nine `_get_source`/`_get_target` implementations call. The real surface, measured on `main`, is **154 names** including **14** page classes; the list is those 154 less the one sanctioned removal (`MERGE_KEEP`, T032), which is separately asserted **absent**. A guard-on-the-guard fails if the list is ever trimmed below 140, so shrinking it cannot quietly weaken the check · `tests/unit/test_039_module_split.py`
- [X] **T039** [US4] Guard 3 — **no `UserRole + N` offset is claimed by two role constants** across `wizard_roles.py`. Expect this to **fail** on arrival (`_RULES_*` and `_ET_*` both sit at 70/71/72); T041 is what makes it pass. Land it red-then-green rather than writing the guard after the fix · `tests/unit/test_039_module_split.py`
- [X] **T040** [US4] Guard 4 — **one write point package-wide**: exactly one function across all wizard modules calls `.execute_move` (FR-002). This complements, and does not replace, the in-file AST scan at `test_036_finish_guard.py:623`, which stays as-is · `tests/unit/test_039_module_split.py`

**Checkpoint**: US4 is independently functional — the structural invariants hold across the package, and none of them can pass vacuously.

---

## Phase 7: US5 — The two latent defects (P3)

**Goal**: retire both defects the file size was concealing. Two separate commits
inside this phase so each is revertible independently of the split.

**Independent test**: guard 3 (T039) flips from red to green; the new nested-count
test pins the changed tristate behaviour.

### Implementation

**Wave 1 — independent (two different files, two different defects):**

- [X] **T041** [P] [US5] **Defect 1 — role collision.** Renumber `_ET_GUID_ROLE`/`_ET_KIND_ROLE`/`_ET_CAT_ROLE`/`_ET_STATUS_ROLE` off `UserRole + 70..73` (colliding with `_RULES_GUID_ROLE`/`_RULES_KIND_ROLE`/`_RULES_STATUS_ROLE` at 70/71/72) onto the next free block, `UserRole + 80..83`. Safe because `test_032_preview_pane_wiring.py` *imports* the constants rather than hardcoding their numeric values. Confirm T039 now passes · `src/gramtrans/Lib/ui/wizard_roles.py`
- [X] **T042** [P] [US5] **Defect 2 — the discarded recursive generator.** In `_PageEntryTypes._iter_item_rows`, change the bare `_walk(child, False)` call to `yield from _walk(child, False)` and delete the permanently-true `if in_group_item or True`. **This changes behaviour**: rows under a nested group start being counted, which moves the whole-block tristate on nested entry-type trees · `src/gramtrans/Lib/ui/wizard_pages_blocks.py`

**⟶ Wait for T042 to finish, then:**

- [X] **T043** [US5] Add a test pinning the **new** nested-group row counts and the resulting whole-block tristate at empty / partial / full, so the behaviour change is asserted rather than assumed · `tests/unit/test_entry_types_display.py`
- [X] **T044** [US5] Run the full gate set (SC-001 … SC-005). SC-001 is the sharp one here: `check_suite_baseline.py` fails both on a new failure **and** on a baseline entry that starts passing · CI scripts

**Checkpoint**: US5 is independently functional and separately revertible — reverting it leaves US1–US4 intact.

---

## Phase 8: Polish & cross-cutting validation

**Wave 1 — independent (four different documentation files):**

- [X] **T045** [P] Update the recorded `selection_wizard.py 6512 L` fact at line ~181 to the post-split figure · `specs/038-transfer-fidelity-gaps/plan.md` **(commits to `main`)**
- [X] **T046** [P] Re-point the five unchecked tasks that target `selection_wizard.py` by line number (T008–T010, T015) to their new module and line · `specs/020-conflict-mode-field-merge/tasks.md` **(commits to `main`)**
- [X] **T047** [P] Re-point T072, which targets `selection_wizard.py` by line number · `specs/038-transfer-fidelity-gaps/tasks.md` **(commits to `main`)**
- [X] **T048** [P] Record the follow-up question raised by T030 — should `_PageEntryTypes._get_source` go through `context.source_handle` like the other eight pages, instead of reading `wizard._host`? — as an explicit open item rather than leaving it only in a code comment · `specs/039-wizard-module-split/spec.md` **(commits to `main`)**

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 — independent (four different validation surfaces):**

- [ ] **T049** [P] **SC-006 — flat import mode**, the FlexTools and frozen-bundle path that pytest never exercises: `python -c "import site,os; d=r'src/gramtrans/Lib'; site.addsitedir(d); site.addsitedir(os.path.join(d,'ui')); import selection_wizard as sw; print(sw.SelectionWizard, len([n for n in dir(sw) if n.startswith('_Page')]))"` — the wizard must import **and construct**, not merely import · flat-mode smoke
- [ ] **T050** [P] **SC-008 — size budget**: `wc -l src/gramtrans/Lib/ui/*.py`; no module exceeds 1750 L (FR-003) · `src/gramtrans/Lib/ui/`
- [ ] **T051** [P] **SC-001 … SC-005 final sweep** on the complete branch: `check_suite_baseline.py`, `pytest tests/unit/test_034_flextools_contract.py -q` standalone, `check_shared_exceptions.py --base main`, `build/hiddenimports.py`, `ruff check src/gramtrans/Lib/ui/`. Compare **full-suite** runs only — subset runs give different results because of the `sys.modules` Qt swap · CI scripts
- [ ] **T052** [P] Confirm commits 1–3 read as pure relocations under `git diff -M --find-copies-harder` (moved hunks rendered as renames wherever possible) · git history

**⟶ Wait for Wave 2 to finish, then:**

- [ ] **T053** **SC-007 — live smoke, last.** A refactor that keeps every test green can still break the window. Launch the real wizard with `run_gui_harness.py` and walk all 12 pages against the read-only `Ejagham Mini` source, confirming: step numbering is consecutive with **no** `of N` total; each page's header renders with the theme strip following it; tree/preview splitters hold at a 900 px window; block-page tristate is correct at empty / partial / full. **Preview only — no Move.** Never point this at `Esperanto`, and never at `Ngoreme Target` or `Ejagham W Target`, which STATUS.md records as freshly verified clean; if a Move is wanted, restore the throwaway `Target` first via `tests/integration/harness/restore.py` · `run_gui_harness.py`
- [ ] **T054** Merge `039-wizard-split` back to `main` and remove the worktree · git

---

## Dependencies & Execution Order

**Phase order**: Setup (T001–T003) → Foundational (T004–T006) → US1 (T007–T011) →
US2 (T012–T026) → US3 (T027–T033) → US4 (T034–T040) → US5 (T041–T044) →
Polish (T045–T054).

Foundational **blocks every story**: `check_shared_exceptions.py` fails on the
first new `Lib/` file, not the last, so T004/T005 must land before any module is
created.

**Story dependencies** are strictly linear and match the plan's five commits —
US2 moves classes that US1's bases and roles must already exist for; US3 applies
bases to modules US2 created; US4's helper scans modules US2/US3 produced; US5
edits files US1 and US2 created. Each story is nonetheless **independently
revertible** in reverse order.

**Waves per phase:**

| Phase | Waves |
|---|---|
| Setup | T001,T002 `[P]` ⟶ T003 |
| Foundational | T004,T005 `[P]` ⟶ T006 |
| US1 | T007 ⟶ T008,T009 `[P]` ⟶ T010 ⟶ T011 |
| US2 | T012–T018 `[P]` ⟶ T019 ⟶ T020 ⟶ T021 ⟶ T022–T025 `[P]` ⟶ T026 |
| US3 | T027 ⟶ T028–T031 `[P]` ⟶ T032 ⟶ T033 |
| US4 | T034 ⟶ T035,T036 `[P]` ⟶ T037 ⟶ T038 ⟶ T039 ⟶ T040 |
| US5 | T041,T042 `[P]` ⟶ T043 ⟶ T044 |
| Polish | T045–T048 `[P]` ⟶ T049–T052 `[P]` ⟶ T053 ⟶ T054 |

**Parallel opportunities.** The widest wave is US2's T012–T018: seven page modules
in seven files, genuinely independent because no page class references
`SelectionWizard` or a sibling page by name — every cross-page read already goes
through `self.wizard()` → a named `page_*()` accessor → a duck-typed call. US3's
T028–T031 and Polish's T045–T048 are similarly file-disjoint. T037–T040 all edit
`tests/unit/test_039_module_split.py` and are therefore **sequential**, not
parallel, despite being conceptually independent guards.

## Requirement coverage

| Requirement | Tasks |
|---|---|
| FR-001 Behaviour is unchanged | T007–T021, T027–T032, T011, T026, T033, T053 |
| FR-002 The write point does not move | T020, T026, T040 |
| FR-003 No module over ~1750 lines | T020, T033, T050 |
| FR-004 Exact duplication is removed | T027, T028, T029, T030, T031 |
| FR-005 Structural guards become package-wide | T034, T035, T036 |
| FR-006 The compatibility surface stays reachable | T010, T021, T038 |
| FR-007 Both import modes keep working | T007, T008, T009, T019, T049 |
| FR-008 New module names may not claim generic top-level names | T006, T012–T018, T051 |
| FR-009 CI gates are satisfied | T004, T005, T006, T051 |
| FR-010 Rationale comments survive | T007, T019, T030 |

## Notes

- **Line-count reference (T003), captured 2026-08-19 on `main`:**
  `selection_wizard.py` 6512 L; `Lib/ui/` total 10802 L across 15 files.
  Post-split targets: facade ~1750 L, no module over 1750 L (SC-008), package
  total down ~505 L from deduplication.
- **The role collision is real and currently latent:** `_RULES_GUID/KIND/STATUS`
  at `UserRole + 70/71/72` (facade lines 3778–3780) and `_ET_GUID/KIND/CAT/STATUS`
  at `70/71/72/73` (lines 4582–4585). Harmless today only because `_PageRules`
  and `_PageEntryTypes` own disjoint trees.
- **Always compare full-suite runs, never subset runs.**
  `test_wizard_page_flow.py` and `test_ui_gating.py` replace
  `QtWidgets.QWizard`/`QWizardPage` in `sys.modules` at import time — which is why
  `_ui_geometry.needs_a_real_qwizard()` exists. Running them alongside the
  geometry tests produces skips; running them alone produces different results.
- `QT_QPA_PLATFORM=offscreen` and `GRAMTRANS_NO_THEME=1` need no manual setting —
  the root `conftest.py` and the Qt test modules `setdefault` them.
- **Out of scope, deliberately:** feature 036's SC-001b progress-total mismatch
  (it touches `_page_progress` wiring, may belong in `Lib/selection.py`, and would
  confound the relocation diff); normalising `_PageEntryTypes._get_source`
  (T048 records it as a question); any change to `flow()`, page order, or the skip
  predicates.
