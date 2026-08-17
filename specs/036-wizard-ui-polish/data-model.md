# Data Model: Wizard UI Polish Pass

**Feature**: 036-wizard-ui-polish

Presentation-layer entities only. Nothing here is persisted, and nothing here
enters a transfer plan (FR-045). "Existing" rows are recorded because the feature
reshapes them; "new" rows are introduced by it.

## 1. WizardStep (new — the declared flow, FR-009..FR-011)

One ordered declaration in `Lib/ui/selection_wizard.py`. It fixes the *order* and
each page's skip eligibility; it does **not** fix positions, because a position
depends on which pages a given run actually shows.

| Field | Type | Rules |
|---|---|---|
| `attr` | `str` | The wizard's page attribute (`"_page_projects"`, …). Present exactly once. |
| `short_title` | `str` | Human title without the number, e.g. `"Projects"`. Non-empty. |
| `skippable` | `bool` | May the page drop out when it has nothing to decide (FR-009c)? `False` for the Affix and Stem pickers by mandate (FR-009d), and for Projects, Writing Systems and Finish because they always ask something. |
| `has_content` | `callable \| None` | The cheap emptiness predicate. `None` ⟺ `skippable is False`. Must be O(1)-ish and **conservative**: `True` when unsure. |

Derived at navigation time, never stored per page:

- `position` = (pages shown before this one in this run) + 1. Assigned on entry.
- **No total.** Nothing derives one, nothing displays one (FR-009a).
- rendered title = `f"Step {position}: {short_title}"`.

**Declared order (12 entries, up from an 11-page flow numbered 1..10 with one
page unnumbered). A run shows a subset; `Skippable` is what may drop out:**

| Order | `attr` | `short_title` | Skippable | Cheap emptiness check |
|---|---|---|---|---|
| 1 | `_page_projects` | Projects | no | — |
| 2 | `_page_writing_systems` | Writing Systems | no | — |
| 3 | `_page_custom_fields` | Custom Fields | yes | source custom-field count |
| 4 | `_page_phonology` | Phonology | yes | phoneme-set / NC / rule list `.Count` |
| 5 | `_page_items` | Affix Picker | **no** (FR-009d) | — |
| 6 | `_page_stems` | Stem Picker | **no** (FR-009d) | — |
| 7 | `_page_skeleton` | Morphology Skeleton | yes | no affix and no stem picked |
| 8 | `_page_gram_deps` | Grammatical Dependencies | yes | no affix and no stem picked |
| 9 | `_page_entry_types` | Lexical-Entry Types | yes | variant / complex-form type list `.Count` |
| 10 | `_page_rules` | Rules | yes | ad-hoc prohibition list `.Count` |
| 11 | `_page_texts` | Texts | yes | `TextsNumberOfTexts()` |
| 12 | `_page_finish` | Finish / Move | no | — |

Rows 3-4 and 9-11 are decided from **source** counts, so they resolve as soon as
a source is bound. Rows 7-8 are selection-dependent and are re-decided each time
the operator advances — which is why the predicate is the cheap proxy "nothing was
picked at all" and not "the inventory would come back empty". Building the
inventory to find out is the expensive walk US1 exists to cover, and FR-009c
forbids paying for it here. A page whose proxy says "maybe" is shown; if its
inventory then comes back empty it says so and keeps its number (spec edge case).

**Excluded from the declaration entirely, and therefore never numbered
(FR-011)**: `_PageScopeConflict` (carries a stale `"Step 3 of 5"` today) and
`_PagePreview` (`"Preview (inactive)"`). Both are retained in the codebase and
never added to the wizard; their step-number literals are removed, not
renumbered. Permanent exclusion and per-run skipping use the same mechanism, so
neither kind of absent page can acquire a number it never shows.

### Navigation (FR-009b)

Skipping is `QWizardPage.nextId()`, the supported Qt hook: it walks the
declaration forward from the current page and returns the first entry that is
either not skippable or whose `has_content` says yes. Qt calls `nextId()` to
decide whether Next is enabled, so it can fire on every `completeChanged` — hence
"cheap or cached" is a hard requirement on the predicates, and the source-derived
counts are cached once at bind rather than re-read.

Back navigation needs no work: Qt replays its own stack of visited pages, so an
operator returning through a run that skipped pages retraces exactly the pages
they saw.

State transition worth naming: the operator may go back and pick an affix after
Morphology Skeleton was skipped for having no picks. The page then re-enters the
flow and positions after it shift by one. That is correct — the flow genuinely
changed — and it is the second reason no total is displayed.

**State transition — the split (FR-006/FR-007/FR-008)**: `_PageProjectWS`
becomes two pages. The projects page owns binding and `context()` and keeps the
`page_project_ws()` accessor; the writing-systems page owns the tables,
`ws_mapping()` and `selected_ws_ids()` behind a new `page_writing_systems()`
accessor, and populates on `initializePage` from the two bound handles.
Advancing off step 1 stays gated by the existing `target_ready*` required field.
Releasing a bound project on step 1 must drop the WS row state that referred to
it (spec edge case), so the writing-systems page repopulates from scratch on
every entry rather than merging into stale rows.

## 2. ProgressReport (new — `Lib/progress.py`, Qt-free)

What the operator is shown during a wait. Created by the caller *before* the work
where a total is knowable, so the total is present on the first frame (FR-014c).

| Field | Type | Rules |
|---|---|---|
| `label` | `str` | Operator-facing name of the operation (FR-015). No internal vocabulary, no class names. |
| `total` | `int \| None` | Unit count when cheaply knowable, else `None` → indeterminate (FR-016/FR-017). |
| `completed` | `int` | Starts at 0; advanced by `tick`. Never displayed above `total`. |

Transitions: `begin` → (`tick`)\* → `end`. `end` is unconditional — success,
failure or abandonment all dismiss the indicator (FR-020); a failure is surfaced
separately as a message by the existing error path.

Degradation rule (spec edge case): if `completed` would exceed `total`, the
report drops to indeterminate rather than showing over 100% or a negative
remainder.

Declared constant, in one place and used twice (FR-019a):
`PROGRESS_THRESHOLD_MS = 500` — the elapsed-time fallback delay (FR-014b) and
the bar an anticipated wait must clear (FR-014a).

## 3. AnticipatedSize (new — `Lib/progress.py`)

The prediction input. Not a stored entity; a rule with two declared parts.

| Part | Rule |
|---|---|
| `total_units` | A count the caller already has or can get in O(1). Never obtained by a counting pass (FR-014d). |
| `units_per_second` | A per-operation calibration constant, measured once against the largest available test project. |

`predicted_ms = total_units / units_per_second * 1000`. The indicator is shown
before the work starts when `predicted_ms >= PROGRESS_THRESHOLD_MS`; otherwise
the elapsed-time fallback governs, and whichever fires first wins (spec edge
case: a fast-predicted operation that runs long is still caught).

Cheap counts available per operation (verified via FLExToolsMCP):

| Operation (FR-023) | Unit | Cheap total |
|---|---|---|
| Bind source project | — | none → indeterminate, elapsed-time trigger |
| Bind target project | — | none → indeterminate, elapsed-time trigger |
| Affix / stem / skeleton / dependency enumeration | lexical entry | `LexiconNumberOfEntries()` |
| Texts enumeration | text | `TextsNumberOfTexts()` |
| Phonology / rules / entry-types / custom-fields enumeration | list item | owning possibility list `.Count` |
| Dry-run plan assembly | category | number of selected categories |
| Execute-move write | plan action | `len(plan actions)` |

## 4. PaletteAccentSet (existing `Palette`, dark values reshaped — FR-024..FR-028)

`Lib/ui/theme.py`'s `Palette` dataclass is unchanged in shape. The dark scheme's
accent members change; the selection members and every semantic member do not.

| Token | Today | Candidate | Note |
|---|---|---|---|
| `alternate_base` | `#23272D` | `#1F2A23` | Green tint, and a bigger step from `base` (FR-025) |
| `button` | `#2E333A` | `#26332B` | |
| `button_hover` | `#3A4048` | `#2F4235` | |
| `button_pressed` | `#454C55` | `#39503F` | |
| `focus` | `#7FB5FF` | `#6FD79B` | 2px focus ring (FR-024) |
| `highlight` | `#2F6FD0` | **unchanged** | Stays blue (FR-024a) |
| `highlighted_text` | `#FFFFFF` | **unchanged** | |
| `diff_added` | `#5FD48A` | **unchanged** | Must stay distinguishable from accent green (FR-027) |
| Light palette | — | **unchanged** | Green is dark-mode only (spec assumption) |

Candidates, not fixtures: the binding constraints are the automated checks
below, and any value that passes them satisfies the requirement.

Validation rules, all automated (FR-026, SC-008, SC-008a) in
`tests/unit/test_theme_manager.py`:

- Existing contrast pairs keep their thresholds, in both modes.
- **New** contrast pairs: `button_text`/`button` ≥ 4.5, `focus`/`window` ≥ 4.5,
  `text`/`alternate_base` ≥ 7.0.
- **New** colour-distance floors, CIE-Lab ΔE76 computed from sRGB in the test
  helper: `focus` vs `diff_added` ≥ 25, `highlight` vs `alternate_base` ≥ 25,
  `alternate_base` vs `base` ≥ 4.
- Both modes still define the identical field set (existing test).

## 5. PreviewListField (existing `FieldDiff`, one new field — FR-033..FR-037)

`Lib/merge_preview.py`'s `FieldDiff` gains one defaulted member, so every
existing construction and every scalar field renders byte-identically.

| Field | Type | Rules |
|---|---|---|
| `multiline` | `bool` | Defaults `False`. `True` only for a field whose source value was a list/tuple/set/frozenset. Renderer emits one entry per line. |

Rendering rules:

| Case | Today | After |
|---|---|---|
| List entries | `repr(item)`, concatenated with no separator | `str(item)`, one entry per line |
| Affix label | `-i2 'PST'` | `-i2` + wide gap + `PST` (FR-035) |
| Empty list-valued field | key omitted, or a blank value | explicit `(none)` note (FR-036) |
| Capped list (cap 25) | `"affix list truncated"` | states the cap and the true total, e.g. `showing 25 of 41 affixes` (FR-037) |
| Quote characters inside the data | preserved | preserved, unchanged (FR-034) |

## 6. DryRunResult (existing `_PageFinish._cached_plan` — FR-038..FR-044)

| Field | Type | Rules |
|---|---|---|
| `_cached_plan` | plan payload \| `None` | `None` on construction and on every page entry. Set only by a successful dry run. |
| `_move_done` | `bool` | Set after a completed Execute; Execute stays disabled thereafter (FR-043). |

Enablement is the conjunction of: a cached plan exists, the run is
write-permitted (`_modify_allowed`), and the plan has not already been executed.
Two additions close the verified gaps: the disabled control states its reason
(FR-039/FR-044), and page entry clears the displayed report as well as the
cached plan, so a stale result is never presented as current (FR-041).

## 7. Window geometry constants (existing — FR-029..FR-032)

| Constant | Today | After |
|---|---|---|
| minimum width | 1100 | **900**, one declared value |
| minimum height | 680 | unchanged |
| default size | 1300 × 760 | unchanged |
| tree:preview splitter | 3:2 stretch, collapsible | 3:2, **not** collapsible, pane minimums summing below 900 (FR-029a) |
| over-narrow column content | clipped | elided right, full value in a tooltip, no horizontal scrollbar (FR-029b) |
