# Tasks: Wizard UI Polish Pass

**Feature**: 036-wizard-ui-polish
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Data model**: [data-model.md](data-model.md) | **Contracts**: [contracts/](contracts/)
**Size**: normal (no `size` recorded in `.spec-context.json` → full phased list)

Eight presentation-layer stories on the existing PyQt6 `QWizard`. FR-045 governs
every task: for an identical set of selections the objects transferred and their
content must be byte-identical before and after, so each edit to a module on the
transfer path (`Lib/selection.py`, `Lib/merge_preview.py`) is additive and
default-off.

**Story order is not strict priority order, and that is deliberate** (plan
"Phase notes"): US2 renumbers the top of every page and US6/US8 build the header
onto that numbered flow, so US2 lands before the header stories; and the cheap
O(1) count layer that US1 needs for its totals is the same layer US2's
`has_content` predicates read, so it is built once in Phase 2 rather than twice.

**Test convention**: Qt tests run headless via the existing harness
(`QT_QPA_PLATFORM=offscreen`, the `qapp` fixture, `GRAMTRANS_NO_THEME=1` where the
theme must be off) — `tests/conftest.py:38`, `tests/unit/test_014_pane_display.py:15-29`.
No new testing technology is introduced (spec assumption). Test tasks are written
to **fail first**.

---

## Phase 1: Setup

**Wave 1 — single task:**

- [ ] **T001** Add the shared offscreen geometry harness — build the wizard at a given window width and text scale, walk the visible widgets of a page, and return their rects so a test can assert non-intersection, non-clipping, and absence of a horizontal scrollbar · `tests/unit/_ui_geometry.py`

Used by US3 (SC-005), US6 (SC-005a) and US8 (SC-009); built once here so the
900 px × largest-text-scale case is expressed one way in all three.

---

## Phase 2: Foundational (BLOCKS US1 and US2)

The Qt-free progress contract and the cheap-count layer. `Lib/progress.py` must
stay importable without a `QApplication`, exactly as `Lib/merge_preview.py` is
(contracts/progress-sink.md).

**Wave 1 — single task (tests first):**

- [ ] **T002** Failing unit tests for the Qt-free progress surface: `PROGRESS_THRESHOLD_MS == 500` and declared in exactly one place (FR-019a), `predicted_ms(total_units, units_per_second)`, `warrants_indicator(None, rate) is False` (FR-014d), `NullSink` methods are no-ops, `reporting()` calls `end` through a normal exit *and* through an exception (FR-020), `end` is idempotent, `tick` never raises after `end`, and `SourceCounts` returns `None` (conservative "unknown") rather than raising when a count is unavailable · `tests/unit/test_036_progress_sink.py`

**⟶ Wait for Wave 1 to finish, then:**

- [ ] **T003** Create the Qt-free progress module: `PROGRESS_THRESHOLD_MS = 500`, the `ProgressSink` Protocol (`begin`/`tick`/`end`), `NullSink`, `predicted_ms`, `warrants_indicator`, and the `reporting` context manager · `src/gramtrans/Lib/progress.py`

**⟶ Wait for T003 (same file), then:**

- [ ] **T004** Add the cheap source-count cache to the same module: `SourceCounts`, filled once when a source binds, exposing `LexiconNumberOfEntries()`, `TextsNumberOfTexts()` and possibility-list `.Count` values (custom fields, phoneme sets / natural classes / phonological rules, variant & complex-form types, ad-hoc prohibitions). O(1) reads only — never a counting pass (FR-014d) — and `None` when a count cannot be had cheaply · `src/gramtrans/Lib/progress.py`

**Checkpoint**: `import gramtrans.Lib.progress` succeeds with no `QApplication`;
T002 is green; one count layer exists for both US1 totals and US2 predicates.

---

## Phase 3: User Story 2 — Pick the projects as a step of their own (P1)

**Goal**: Project selection is a step of its own, writing systems the step after
it; every page shown carries a consecutive number and **no total**; a page with
nothing to decide drops out of the run, except the Affix and Stem pickers.

**Independent Test**: Walk the wizard end to end — step 1 asks only for projects,
step 2 only for writing systems, every shown page carries a number, the numbers
ascend by one. Then walk it against a project that leaves a skip-eligible page
empty and confirm the numbers still ascend by one with no gap.

### Tests

**Wave 1 — independent (different files):**

- [ ] **T005** [P] [US2] New flow/numbering test: numbers consecutive from 1 on a full run **and** on a skipping run (SC-003, SC-003a); no page title matches `of \d+` (SC-003b, FR-009a); a skippable page whose `has_content()` is true is never dropped (FR-009c); the Affix and Stem pickers are shown when the source has none (FR-009d); `_PageScopeConflict` and `_PagePreview` are absent from `flow()`, never added, and carry no step number (FR-011); the declaration is the single source of order and skip eligibility (FR-010) · `tests/unit/test_036_wizard_flow_numbering.py`
- [ ] **T006** [P] [US2] Extend the accessor table with `page_writing_systems()` and keep `page_project_ws()` pointing at the projects page · `tests/unit/test_wizard_page_order.py`
- [ ] **T007** [P] [US2] Update the asserted subtitle literal to the post-split projects page, preserving the host-difference assertion (source picked vs host-supplied) · `tests/unit/test_034_flextools_contract.py`
- [ ] **T008** [P] [US2] Update the asserted subtitle literal for the same reason · `tests/unit/test_034_step1_source_picker.py`

### Implementation

Every task below edits the one 5,204-line module, so each is its own wave — they
are sequential by construction, not by choice.

**⟶ Wait for the test wave, then:**

- [ ] **T009** [US2] Add the ordered `flow()` declaration — 12 entries of `(attr, short_title, skippable, has_content)` per data-model §1 — and drive page registration from it, replacing the unconditional `addPage` block at `:5003-5013`. Order and skip eligibility only: no positions, no length any page can display (FR-010) · `src/gramtrans/Lib/ui/selection_wizard.py`

**⟶ Then:**

- [ ] **T010** [US2] Split `_PageProjectWS` into `_PageProjects` (binding + `context()`, keeps the `page_project_ws()` accessor and its 23 call sites) and `_PageWritingSystems` (the two WS tables, `ws_mapping()`, `selected_ws_ids()`, reached through a new `page_writing_systems()`), populating on `initializePage` from the two bound handles and repopulating from scratch each entry so releasing a project cannot leave stale rows; move `_compute_wizard_plan`'s single `ws_mapping()` read to the new accessor (FR-006, FR-007) · `src/gramtrans/Lib/ui/selection_wizard.py`

**⟶ Then:**

- [ ] **T011** [US2] Refuse advancing off step 1 until both a source and a target are bound, with the reason visible on the page rather than only in the disabled Next (FR-008) · `src/gramtrans/Lib/ui/selection_wizard.py`

**⟶ Then:**

- [ ] **T012** [US2] Assign each page's number on entry as (pages shown before it in this run) + 1 and render `Step {i}: {short_title}`; delete the twelve `Step N of 10` literals at `:293,948,1494,1745,1892,2405,2734,3116,3434,3898,4252,4427,4719`; emit no total anywhere (FR-009, FR-009a) · `src/gramtrans/Lib/ui/selection_wizard.py`

**⟶ Then:**

- [ ] **T013** [US2] Override `QWizardPage.nextId()` to walk `flow()` forward and return the first entry that is either not skippable or whose `has_content()` is true, so the next page is resolved *before* navigation (FR-009b); leave Back to Qt's own visited-page stack · `src/gramtrans/Lib/ui/selection_wizard.py`

**⟶ Then:**

- [ ] **T014** [US2] Wire the `has_content` predicates: source-derived pages (Custom Fields, Phonology, Lexical-Entry Types, Rules, Texts) read the `SourceCounts` cache filled at bind (T004); Morphology Skeleton and Grammatical Dependencies use the cheap proxy "no affix and no stem picked" (`len(picks)`), never an inventory build; unknown ⇒ `True` (show), so a non-empty page can never be skipped, and `nextId()` stays cheap enough for Qt to call it on every `completeChanged` (FR-009c, FR-009d, D5b) · `src/gramtrans/Lib/ui/selection_wizard.py`

**⟶ Then:**

- [ ] **T015** [US2] Remove the stale step-number literals from the two retained-but-excluded pages — `_PageScopeConflict`'s `"Step 3 of 5"` and `_PagePreview`'s title — and confirm neither is in `flow()` nor added to the wizard, so permanent exclusion and per-run skipping use the same mechanism (FR-011) · `src/gramtrans/Lib/ui/selection_wizard.py`

**Checkpoint**: US2 is independently functional — the flow is declared, numbered
by the walk, skips empty pages conservatively, and shows no total. SC-003,
SC-003a, SC-003b and SC-004 are checkable here.

---

## Phase 4: User Story 1 — Know the wizard is working, not hung (P1)

**Goal**: Every wait names what is loading, states how much there is where that is
cheaply knowable, appears *before* the work when a count predicts a wait past
500 ms, appears after 500 ms otherwise, keeps the window repainting, and never
flashes for fast work.

**Independent Test**: Drive the wizard against a project large enough for a
perceptible wait on a page that enumerates grammar. The indicator is on screen
when the work begins, states the total, advances throughout, names the operation,
and is gone when the page is ready.

### Tests

**Wave 1 — single task (extends the Phase 2 file):**

- [ ] **T016** [US1] Add the Qt-sink cases: `deferred()` shows nothing for work that finishes first (FR-019, SC-001a), `immediate()` is on screen before the work starts (FR-014a, SC-001b), a `begin` while an indicator is up re-labels it and `end` restores the outer label (FR-021), overrunning `total` degrades to indeterminate rather than showing over 100%, a failure path still dismisses (FR-020), and the indicator is drawn from the active palette rather than hard-coded colour · `tests/unit/test_036_progress_sink.py`

### Implementation

**⟶ Wait for T016, then — Wave 2 — independent (different files):**

- [ ] **T017** [P] [US1] Create the Qt sink: `QtProgressSink` (one modal indicator for the whole application, no cancel affordance, `tick` advances the bar *and* pumps the event loop with throttling so a million-tick walk does not live in the event loop, overrun ⇒ indeterminate, nested labels on a stack with one dialog), plus `deferred()` using `setMinimumDuration(PROGRESS_THRESHOLD_MS)` and `immediate()` (FR-014a/b, FR-017, FR-018, FR-021, SC-002) · `src/gramtrans/Lib/ui/progress_indicator.py`
- [ ] **T018** [P] [US1] Add one keyword-only `progress=None` parameter to each of the seven inventory builders and tick from *inside* each walk at `:655,1237,1588,2628,3070,3403,3728` — no positional signature changes, and `progress=None` runs exactly as today and returns the identical inventory (FR-022, FR-045) · `src/gramtrans/Lib/selection.py`
- [ ] **T019** [P] [US1] Declare the per-operation `units_per_second` calibration table — the only per-operation number, with the 500 ms threshold left untouched (FR-019a, data-model §3) · `src/gramtrans/Lib/progress.py`

**⟶ Wait for Wave 2 to finish, then (all three edit the wizard module, so each is its own wave):**

- [ ] **T020** [US1] Wire operations 3–11 of the FR-023 table (custom fields, phonology, affixes, stems, skeleton, dependencies, entry types, rules, texts): in each page's `initializePage`, take the cheap total from `SourceCounts`, use `immediate()` when `warrants_indicator(total, rate)` and `deferred()` otherwise, and pass the sink into the builder with the operator-facing label from contracts/progress-sink.md (FR-014, FR-014c, FR-015, FR-016) · `src/gramtrans/Lib/ui/selection_wizard.py`

**⟶ Then:**

- [ ] **T021** [US1] Wire operations 1–2 — binding the source and the target project — through `deferred()` with no total, indeterminate but visibly animating (FR-014b, FR-017) · `src/gramtrans/Lib/ui/selection_wizard.py`

**⟶ Then:**

- [ ] **T022** [US1] Wire operations 12–13 — dry-run plan assembly (total = selected categories) and the execute-move write (total = plan actions) — and make every one of the thirteen paths dismiss its indicator on failure *and* surface the failure as a message, so no indicator outlives its operation (FR-020, FR-023) · `src/gramtrans/Lib/ui/selection_wizard.py`

**Checkpoint**: US1 is independently functional — all thirteen FR-023 operations
report, the window repaints throughout, and fast work shows nothing.

---

## Phase 5: User Story 3 — Fit the wizard on the screen you actually have (P2)

**Goal**: The window narrows to 900 px with nothing clipped, overlapped, or
reflowed, and no horizontal scrollbar.

**Independent Test**: Shrink the window to the floor; every control stays visible,
reachable, and side-by-side panes stay side by side.

### Tests

**Wave 1 — single task:**

- [ ] **T023** [P] [US3] New min-width layout test built on the T001 harness: `minimumWidth() == MIN_WINDOW_WIDTH == 900` and `minimumHeight()` unchanged at 680 (FR-029); tree-and-preview pages keep both panes at the floor with neither collapsed (FR-029a); over-narrow column content is elided with an ellipsis and carries its full value in a tooltip, and no page acquires a horizontal scrollbar (FR-029b); nothing is clipped or overlapped, and the navigation buttons stay fully visible, at both the default and the largest supported text scale (FR-030, FR-031, FR-032, SC-005) · `tests/unit/test_036_min_width_layout.py`

### Implementation

**⟶ Wait for T023, then:**

- [ ] **T024** [US3] Declare `MIN_WINDOW_WIDTH = 900` as the single project-wide value and apply it at `:4947`, replacing `QSize(1100, 680)` with the new floor and the unchanged height (FR-029) · `src/gramtrans/Lib/ui/selection_wizard.py`

**⟶ Then:**

- [ ] **T025** [US3] In `_make_tree_pane_splitter` — the one place every such page builds its splitter — make the splitter non-collapsible and set pane minimums that sum below 900 so both panes survive the floor without reflowing, stacking, or hiding either one (FR-029a) · `src/gramtrans/Lib/ui/selection_wizard.py`

**⟶ Then:**

- [ ] **T026** [US3] Set `Qt.TextElideMode.ElideRight` on the views and columns that cannot fit at the floor and carry the full value in a tooltip, with horizontal scrollbars left off (FR-029b, FR-030) · `src/gramtrans/Lib/ui/selection_wizard.py`

**Checkpoint**: US3 is independently functional — the window reaches 900 px and
every page survives it at the largest text scale.

---

## Phase 6: User Story 4 — Read the affix list in a slot preview (P2)

**Goal**: Each list entry is its own line with no added quoting, form and gloss
separated by space, empty lists explicitly empty, capped lists disclosing the
true total.

**Independent Test**: Select a populated slot on the Morphology Skeleton page and
read the affix list — one affix per line, no punctuation that is not linguistic
data.

### Tests

**Wave 1 — independent (different files):**

- [ ] **T027** [P] [US4] New preview list-field test: `FieldDiff.multiline` defaults `False` and every scalar field renders byte-identically to today (FR-045); a list-valued field emits one entry per line (FR-033); no programmatic quoting is added (FR-033); apostrophes and quote marks inside an entry — glottal stops, ejectives, orthographic apostrophes — are preserved exactly (FR-034); an affix label separates form from gloss by whitespace with no added punctuation (FR-035); an empty list-valued field renders `(none)` (FR-036); a capped list states the cap and the true total (FR-037) · `tests/unit/test_036_preview_list_fields.py`
- [ ] **T028** [P] [US4] Update the truncation-note expectation to the disclosed form (`showing 25 of 41 affixes`) rather than a bare "truncated" · `tests/unit/test_032_preview_coverage.py`

### Implementation

**⟶ Wait for the test wave, then (one file, so a chain):**

- [ ] **T029** [US4] Add `multiline: bool = False` to `FieldDiff` and set it `True` only where the source value was a `list`/`tuple`/`set`/`frozenset`, leaving every existing construction and every scalar field unchanged (FR-045) · `src/gramtrans/Lib/merge_preview.py`

**⟶ Then:**

- [ ] **T030** [US4] Render sequence members with `str(item)` instead of `repr(item)` at all three sites — `_added_segments`, `_segments_for_sequence`, and the LINK-only sibling at `:322,341,346,521` (FR-033, FR-034) · `src/gramtrans/Lib/merge_preview.py`

**⟶ Then:**

- [ ] **T031** [US4] Teach the segment renderer at `:717-757` to emit one entry per line for a `multiline` field instead of concatenating segments into a single HTML line, with no bullet or other added punctuation (FR-033) · `src/gramtrans/Lib/merge_preview.py`

**⟶ Then:**

- [ ] **T032** [US4] Separate form from gloss in `_affix_msa_label` at `:2583-2586` with a wide gap instead of wrapping the gloss in `'...'` (FR-035) · `src/gramtrans/Lib/merge_preview.py`

**⟶ Then:**

- [ ] **T033** [US4] Render an empty list-valued field as an explicit `(none)` note rather than a blank or a punctuation artifact, and change the `_LIST_ITEM_LIMIT` (25, unchanged) truncation note at `:2071,2604-2607` to state the cap *and* the true total (FR-036, FR-037) · `src/gramtrans/Lib/merge_preview.py`

**Checkpoint**: US4 is independently functional — SC-006 is checkable and no
stored data was touched.

---

## Phase 7: User Story 5 — Trust the Finish page's guard rail (P2)

**Goal**: Execute is unavailable until a successful dry run of the *current*
selections, says why when it is unavailable, and no stale dry-run result is
presented as current.

**Independent Test**: Reach Finish (Execute disabled and explained), dry-run
(enabled), go back, change a selection, return (disabled again, prior result no
longer shown as current).

### Tests

**Wave 1 — single task:**

- [ ] **T034** [P] [US5] The FR-038..FR-044 matrix as one test module: Execute disabled on construction and on every page entry (FR-038); the disabled state explains that a dry run is required (FR-039) or that the run is read-only (FR-044); no affordance on the page reaches a write while Execute is disabled (FR-040, SC-007); any selection change after a successful dry run re-disables Execute and the prior report stops being presented as current (FR-041); a dry run that produces no plan leaves Execute disabled and states the failure (FR-042); a completed Execute leaves Execute disabled (FR-043). The already-met halves (FR-038, FR-040, FR-042, FR-043, the read-only refusal) are covered as regression, which is the evidence the story asks for · `tests/unit/test_036_finish_guard.py`

### Implementation

**⟶ Wait for T034, then:**

- [ ] **T035** [US5] State the reason on the disabled Execute control at `:4726-4731,4774-4775` — a dry run is required, or the run is read-only — so a dead button is never unexplained (FR-039, FR-044) · `src/gramtrans/Lib/ui/selection_wizard.py`

**⟶ Then:**

- [ ] **T036** [US5] Clear the displayed dry-run report (the `StatsPanel` content) in `_PageFinish.initializePage` alongside the already-cleared `_cached_plan`, so a stale result is never left on screen as current (FR-041) · `src/gramtrans/Lib/ui/selection_wizard.py`

**Checkpoint**: US5 is independently functional — the Preview-before-Mutate gate
is tighter than before and SC-007 is checkable.

---

## Phase 8: User Story 6 — A title bar and chrome that speak to the operator (P3)

**Goal**: The title names the tool with no internal phase label; the zoom and
colour-mode controls sit in a laid-out per-page header, labelled `Zoom:`, with no
letter-A glyphs, never overlapping the title, the description, or page content.

**Independent Test**: Read the title bar (no phase label); confirm the controls
are present, labelled, and non-overlapping at every supported width and text
scale.

Depends on Phase 3: the header is installed on the pages the declared flow shows.

### Tests

**Wave 1 — single task:**

- [ ] **T037** [P] [US6] New header/controls test on the T001 harness: `windowTitle()` identifies the application and matches no `Phase`/`3c` designation (FR-001, SC-010); `header.description_label().wordWrap() is True` and its text is `page.subTitle()` (FR-012); `header.controls_slot()` reserves its own space so a description at any wrapped height cannot run under the controls, asserted as geometry non-intersection at 900 px × the largest text scale with the wizard's longest description (FR-004, FR-013a, SC-005a); the zoom label reads exactly `"Zoom:"` (FR-002); the increase/decrease buttons read `"+"`/`"-"` with no letter-A glyph (FR-003); the percentage readout, its click-to-100% reset, the `Dark Mode`/`Light Mode` toggle and the `ZoomIn`/`ZoomOut`/`Ctrl+0` shortcuts all survive and each shortcut is registered exactly once (FR-005) · `tests/unit/test_036_page_header_layout.py`

### Implementation

**⟶ Wait for T037, then — Wave 2 — independent (different files):**

- [ ] **T038** [P] [US6] Create the laid-out header widget: a word-wrapping `QLabel` for the description plus a controls slot on the right, exposing `description_label()` and `controls_slot()`, reserving separate space by layout rather than by positioning (FR-004, FR-012) · `src/gramtrans/Lib/ui/page_header.py`
- [ ] **T039** [P] [US6] In `ThemeCornerBar` at `:843-947,872-890`: add the visible `"Zoom:"` label, relabel the buttons `"-"` and `"+"` (dropping the `A-`/`A+` glyphs), and remove the self-positioning — `reposition()` and the `raise_()` over page content go away, since the bar is now laid out by its host (FR-002, FR-003, FR-004) · `src/gramtrans/Lib/ui/theme.py`

**⟶ Wait for Wave 2 to finish, then (one file, so a chain):**

- [ ] **T040** [US6] Replace the window title at `:4942` — `"GramTrans -- Selection Wizard (Phase 3c)"` — with one that identifies the application and its purpose and carries no development phase, milestone, or iteration designation (FR-001) · `src/gramtrans/Lib/ui/selection_wizard.py`

**⟶ Then:**

- [ ] **T041** [US6] Set `QWizard.WizardOption.IgnoreSubTitles` and install a header at the top of every flow page's layout, keeping `setSubTitle(...)` as the string of record that the header renders (FR-004, FR-012) · `src/gramtrans/Lib/ui/selection_wizard.py`

**⟶ Then:**

- [ ] **T042** [US6] Keep exactly one `ThemeCornerBar` instance and reparent it into the current page's header slot on `currentIdChanged`, removing the old floating wiring at `:5020-5095` — one instance so `Ctrl+0`, `ZoomIn` and `ZoomOut` are never registered twelve times and resolved as ambiguous (FR-005, D8) · `src/gramtrans/Lib/ui/selection_wizard.py`

**Checkpoint**: US6 is independently functional — the controls are laid out, not
floating, and SC-005a and SC-010 are checkable.

---

## Phase 9: User Story 8 — Step descriptions that finish their sentence (P3)

**Goal**: A description too long for one line wraps instead of truncating, fits
two lines at the default width and scale, and absorbs a third line at the floor
or a raised scale without clipping or overlap.

**Independent Test**: Narrow the window and visit each step — nothing is cut off,
and a description that fits stays on one line with no blank second line reserved.

Depends on Phase 8: wrapping is a property of the header's description label.

### Tests

**Wave 1 — single task:**

- [ ] **T043** [P] [US8] Extend the header test: every step description fits two lines at the default width and default text scale (FR-013, SC-009); a description that fits stays on one line with no blank second line reserved (FR-012); a description that wraps pushes no page content off screen and overlaps nothing (FR-013a); at 900 px or a raised text scale a third line is permitted and absorbed without clipping (FR-013a, SC-009) · `tests/unit/test_036_page_header_layout.py`

### Implementation

**⟶ Wait for T043, then:**

- [ ] **T044** [US8] Shorten every `setSubTitle(...)` string that exceeds the two-line budget at the default width and default text scale — the budget is measured once at the default, not guaranteed at every size (FR-013) · `src/gramtrans/Lib/ui/selection_wizard.py`

**Checkpoint**: US8 is independently functional — SC-009 is checkable at both the
default and the floor.

---

## Phase 10: User Story 7 — Green accents in dark mode (P3)

**Goal**: Dark-mode striping, buttons and focus read green; the selection
highlight stays blue; every contrast floor still holds and the enforcement stays
automated.

**Independent Test**: Switch to dark mode and inspect a populated tree, a set of
buttons, and a selected row — green striping and buttons, blue selection, readable
throughout, contrast still measured automatically.

### Tests

**Wave 1 — single task:**

- [ ] **T045** [P] [US7] Extend the existing parametrised palette checks at `:519-553`: add an sRGB→CIE-Lab ΔE76 helper (a dozen lines of arithmetic, no new dependency); add the contrast pairs `("button_text","button",4.5)`, `("focus","window",4.5)`, `("text","alternate_base",7.0)` to `_CONTRAST_PAIRS` with every existing pair and threshold retained in both modes (FR-026, SC-008); add `_DISTANCE_FLOORS` — `("focus","diff_added",25)`, `("highlight","alternate_base",25)`, `("alternate_base","base",4)` (FR-025, FR-027, SC-008a); assert `highlight`/`highlighted_text` are unchanged and blue (FR-024a), that every semantic token including `diff_added` is unchanged (FR-027), that `LIGHT_PALETTE` is unchanged in every member (FR-028), and that both modes still define the identical field set · `tests/unit/test_theme_manager.py`

### Implementation

**⟶ Wait for T045, then:**

- [ ] **T046** [US7] Turn the dark scheme's accent family green — `alternate_base`, `button`, `button_hover`, `button_pressed`, `focus` (candidates in data-model §4) — leaving `highlight`, `highlighted_text`, every semantic token and the whole light palette untouched, and driving the focus ring from the new `focus` value (FR-024, FR-024a, FR-025, FR-028) · `src/gramtrans/Lib/ui/theme.py`

**Checkpoint**: US7 is independently functional — SC-008 and SC-008a hold as
measurements rather than as review.

---

## Phase 11: Polish & cross-cutting validation

**Wave 1 — independent (different targets):**

- [ ] **T047** [P] Live verification on the `Ejagham Mini` → `Ejagham Full GT-Test` pair (constitution gate): SC-001 (no wait past 500 ms without an active indicator, across all thirteen FR-023 operations), SC-001a (nothing appears for work under the threshold), SC-001b (the indicator precedes the work and its total matches the work performed), SC-002 (the OS never reports the wizard unresponsive across a full end-to-end run), and SC-011 (for an identical selection set, the objects transferred and their content are unchanged — the FR-045 equality check). Record the evidence · `specs/036-wizard-ui-polish/verification.md`

**⟶ Wait for T047, then:**

- [ ] **T048** Calibrate the `units_per_second` constants from the timings T047 measured, so every anticipated-cost prediction is auditable against a real run and the 500 ms threshold stays untouched (FR-014a, FR-019a) · `src/gramtrans/Lib/progress.py`

**⟶ Then:**

- [ ] **T049** Run the full offscreen suite and confirm every Success Criterion has an automated check that fails if the behaviour regresses: SC-003/003a/003b/004 (numbering), SC-005/005a (900 px and control/description separation), SC-006 (list legibility), SC-007 (no write without a dry run), SC-008/008a (palette measurements), SC-009 (description budget), SC-010 (title) · `tests/unit/`

**⟶ Then:**

- [ ] **T050** Record the session's validated work and the pickup state · `STATUS.md`

---

## Dependencies & Execution Order

**Phase order**: Setup (T001) → Foundational (T002-T004) → US2 (T005-T015) → US1
(T016-T022) → US3 (T023-T026) → US4 (T027-T033) → US5 (T034-T036) → US6
(T037-T042) → US8 (T043-T044) → US7 (T045-T046) → Polish (T047-T050).

**Cross-phase dependencies** (the only ones that are real):

- **Foundational blocks US1 and US2.** `Lib/progress.py` supplies both US1's
  totals and US2's `has_content` predicates; the count layer is built once
  (T004), not twice.
- **US2 precedes US6 and US8.** The header is installed on the pages the declared
  flow shows (T041 needs T009), and both stories edit the top of every page.
- **US6 precedes US8.** Wrapping is a property of the header's description label
  (T043/T044 need T038/T041).
- **US3, US4, US5 and US7 depend only on the phases before them**, and on nothing
  in each other. US4 and US7 touch files no other story touches
  (`merge_preview.py`, `theme.py`'s palette) and could be built at any point after
  Setup.
- **Polish depends on everything**, and T048 depends on T047's measurements.

**Wave restatement, per phase:**

- **Setup** — one wave: T001.
- **Foundational** — T002 (tests) → T003 (module) → T004 (count cache, same file).
- **US2** — T005-T008 in one wave (four different test files) → then T009 → T010 →
  T011 → T012 → T013 → T014 → T015, each its own wave because all seven edit
  `selection_wizard.py`.
- **US1** — T016 → then T017/T018/T019 in one wave (three different files) → then
  T020 → T021 → T022, sequential on `selection_wizard.py`.
- **US3** — T023 → T024 → T025 → T026, sequential on `selection_wizard.py`.
- **US4** — T027/T028 in one wave → then T029 → T030 → T031 → T032 → T033,
  sequential on `merge_preview.py`.
- **US5** — T034 → T035 → T036, sequential on `selection_wizard.py`.
- **US6** — T037 → then T038/T039 in one wave (`page_header.py`, `theme.py`) →
  then T040 → T041 → T042, sequential on `selection_wizard.py`.
- **US8** — T043 → T044.
- **US7** — T045 → T046.
- **Polish** — T047 → T048 → T049 → T050.

**Parallel opportunities**: the genuine ones are the test waves (T005-T008,
T027/T028) and the new-module wave in US1 (T017/T018/T019) and US6
(T038/T039). Everything else in this feature converges on
`src/gramtrans/Lib/ui/selection_wizard.py`, so its tasks are sequential by
construction — 26 of the 50 tasks edit that one 5,204-line module, which is the
main scheduling fact of this feature.

**Implementation note carried from the plan**: `Lib/selection.py` and
`Lib/merge_preview.py` are on the transfer path. `progress=None` means no sink and
no tick; `FieldDiff.multiline` defaults `False`. T047's SC-011 check is what
confirms that held.
