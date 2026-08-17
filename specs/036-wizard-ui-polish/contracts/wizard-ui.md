# Contract: wizard UI surface

**Feature**: 036-wizard-ui-polish

The identifiers a test or a consumer codes against. Strings the spec pinned are
reproduced here **exactly** — `"Zoom:"`, `900`, `500` — and are the contract.

## Window (FR-001, FR-029, FR-032)

| Identifier | Value / rule |
|---|---|
| `SelectionWizard.windowTitle()` | Identifies the application and its purpose. Contains no internal development phase, milestone or iteration designation — no `"Phase"`, no `"3c"` (FR-001, SC-010). |
| `MIN_WINDOW_WIDTH` | `900` — one declared value for the wizard as a whole, not negotiated per page (FR-029). |
| `SelectionWizard.minimumWidth()` | `== MIN_WINDOW_WIDTH` |
| `SelectionWizard.minimumHeight()` | Unchanged from today (`680`). |

## Flow and numbering (FR-006..FR-011)

| Identifier | Rule |
|---|---|
| `SelectionWizard.flow()` | The declared order: `(attr, short_title, skippable, has_content)` per entry. Declares order and skip eligibility only — **not** positions, and no length that any page displays. |
| `SelectionWizard.page_project_ws()` | The **projects** page (step 1). Retains this name; owns `context()`. |
| `SelectionWizard.page_writing_systems()` | New. The writing-systems page (step 2); owns `ws_mapping()` and `selected_ws_ids()`. |
| every other `page_*()` accessor | Unchanged names, unchanged returns. |
| `page.title()` for every page shown | `f"Step {i}: {short_title}"` — a number, **no total** (FR-009, FR-009a). No page title matches `of \d+` (SC-003b). |
| `i` | Pages shown before this one in this run, plus one. Assigned on entry; consecutive from 1 across the sequence actually shown, on a skipping run as on a full one (SC-003, SC-003a). |
| `page.nextId()` | Walks `flow()` forward and returns the first entry that is not skippable or whose `has_content()` is true (FR-009b, FR-009c). Must be cheap: Qt may call it on every `completeChanged`. |
| `has_content()` for a skippable page | Conservative — `True` when unsure. May cause an empty page to be shown; must never cause a non-empty page to be skipped (FR-009c). |
| Affix Picker, Stem Picker | `skippable is False`. Always shown, and state plainly when the project has none (FR-009d). |
| a shown page that turns out empty | Keeps its number and says it has nothing to decide. Never retro-actively un-numbered. |
| `_PageScopeConflict.title()`, `_PagePreview.title()` | Carry no step number; neither page is in `flow()` nor added to the wizard (FR-011). |
| step-1 advance gate | Refused until both source and target are bound, with the reason visible on the page (FR-008). |

## Page header (FR-004, FR-012, FR-013, FR-013a)

Each page in the flow owns one header widget at the top of its layout.

| Identifier | Rule |
|---|---|
| `page.header()` | The header widget. Laid out — never floating, never `raise_()`ed over content. |
| `header.description_label()` | `QLabel` with `wordWrap() is True`. Text is `page.subTitle()` (FR-012). Wraps to a second line rather than truncating; reserves no blank second line when the text fits. |
| `header.controls_slot()` | Where the view controls sit. Reserves its own space, so a description grown to any wrapped height cannot run underneath them (FR-004). |
| `QWizard.WizardOption.IgnoreSubTitles` | Set on the wizard: Qt stops drawing the subtitle, the header draws it instead. `page.subTitle()` remains the string of record. |
| every step description | Fits two lines at the default window width and default text scale (FR-013). May wrap further at 900 px or a raised text scale, absorbed without clipping (FR-013a). |

## View controls (FR-002, FR-003, FR-005)

| Identifier | Value / rule |
|---|---|
| zoom label text | `"Zoom:"` — visible, and preceding the zoom control (FR-002). |
| decrease button text | `"-"`. No letter-A glyph (FR-003). |
| increase button text | `"+"`. No letter-A glyph (FR-003). |
| percentage readout | Unchanged: `"{percent}%"`, click resets to 100%. |
| colour-mode button text | Unchanged: `"Dark Mode"` / `"Light Mode"`. |
| keyboard shortcuts | Unchanged and registered exactly once: `ZoomIn`, `ZoomOut`, `Ctrl+0` (FR-005). |
| control instances | Exactly one control strip exists; it is moved into the current page's header slot on page change (FR-005). |

## Dark palette accents (FR-024..FR-028)

| Identifier | Rule |
|---|---|
| `DARK_PALETTE.alternate_base` | Green tint, distinguishable from `base` at a glance (FR-025). |
| `DARK_PALETTE.button`, `.button_hover`, `.button_pressed` | Green accent family (FR-024). |
| `DARK_PALETTE.focus` | Green (FR-024). |
| `DARK_PALETTE.highlight` | **Blue, unchanged** (`#2F6FD0`) (FR-024a). |
| `DARK_PALETTE.diff_added` and every semantic token | Unchanged, and measurably distant from the accent green (FR-027). |
| `LIGHT_PALETTE` | Unchanged in every member (spec: green is dark-mode only). |
| `_CONTRAST_PAIRS` | Existing pairs and thresholds retained; gains `("button_text", "button", 4.5)`, `("focus", "window", 4.5)`, `("text", "alternate_base", 7.0)` (FR-026). |
| `_DISTANCE_FLOORS` | New: `("focus", "diff_added", 25)`, `("highlight", "alternate_base", 25)`, `("alternate_base", "base", 4)`, as CIE-Lab ΔE76 (SC-008a). |

## Preview list fields (FR-033..FR-037)

| Identifier | Rule |
|---|---|
| `FieldDiff.multiline` | New, defaults `False`. `True` for a field whose source value was a list/tuple/set/frozenset. |
| rendering of a `multiline` field | One entry per line (FR-033). |
| sequence member text | `str(item)` — no programmatic quoting added (FR-033). |
| quote/apostrophe characters within an entry | Preserved exactly (FR-034). |
| affix label | Form and gloss separated by whitespace or alignment; no added punctuation between them (FR-035). |
| empty list-valued field | Rendered as explicitly empty — `(none)` — not as a blank or a punctuation artifact (FR-036). |
| `_LIST_ITEM_LIMIT` | `25`, unchanged. |
| truncation note | States the cap **and** the true total, e.g. `showing 25 of 41 affixes` (FR-037). Never a bare "truncated". |

## Finish page (FR-038..FR-044)

| Identifier | Rule |
|---|---|
| dry-run control | Present and always enabled; label unchanged. |
| Execute control | Disabled on construction and on every page entry (FR-038). |
| Execute enablement | Requires all of: a cached plan from a successful dry run, `modify_allowed`, and no completed Execute this session (FR-038, FR-043, FR-044). |
| disabled-state explanation | States that a dry run is required (FR-039), or that the run is read-only (FR-044). |
| page entry | Clears the cached plan **and** the displayed dry-run report, so no stale result is presented as current (FR-041). |
| a failed dry run | Leaves Execute disabled and states the failure (FR-042). |
| any path to a write while Execute is disabled | None exists (FR-040, SC-007). |
