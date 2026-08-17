# Phase 0 Research: Wizard UI Polish Pass

**Feature**: 036-wizard-ui-polish
**Date**: 2026-08-17

Every decision below is bounded by FR-045: this feature may not change what
GramTrans enumerates, plans, or writes. Where a decision touches a module on the
transfer path (`Lib/selection.py`, `Lib/merge_preview.py`), the chosen shape is
the one that is additive and default-off, so an unchanged caller gets
byte-identical behaviour.

## Codebase findings the decisions rest on

| Finding | Where | Consequence |
|---|---|---|
| The wizard is a `QWizard` with **11 pages added** but titles that say "of 10", one page (`_PageTexts`) with no step number, and two retained-but-unadded pages (`_PageScopeConflict` "Step 3 of 5", `_PagePreview` "Preview (inactive)") | `selection_wizard.py:5003-5013`, `:293,948,1494,1745,1892,2405,2734,3116,3434,3898,4252,4427,4719` | US2 is a renumbering of a flow whose numbers are already wrong; the eleven "of N" claims are what FR-009a removes outright |
| Every page is added unconditionally and `nextId()` is never overridden, so the flow is fixed and no page can drop out | `selection_wizard.py:5003-5013` | Conditional pages (FR-009c) are new behaviour, not a change to existing behaviour — nothing today depends on the flow being fixed |
| Window title is `"GramTrans -- Selection Wizard (Phase 3c)"`; minimum size is `QSize(1100, 680)` | `selection_wizard.py:4942,4947` | US6 item 1 and US3 are one-line constants, plus the layout work behind them |
| The zoom / colour-mode strip (`ThemeCornerBar`) is **parented but not laid out**: it pins itself to the window's top-right in `reposition()` and `raise_()`es itself over the page | `theme.py:843-947`, `selection_wizard.py:5020-5095` | This *is* the overlap FR-004 exists to stop; the fix has to put it in a layout, not move it |
| Buttons are labelled `"A-"`, `"100%"`, `"A+"`, `"Dark Mode"`; there is no `"Zoom:"` label | `theme.py:872-890` | US6 items 2-3 |
| There is **no progress infrastructure at all**. `QProgressBar` is styled in the stylesheet and never instantiated; no `QThread`, no `QProgressDialog`, no `processEvents` on the wizard path | `theme.py:432-433`; absence across `Lib/ui/` | US1 is genuine construction, and it is the only story that is |
| Every page's `initializePage` calls a `build_*_inventory(source, target=...)` **synchronously on the UI thread**; the builders own the whole LCM walk internally | `selection_wizard.py:1012`, `selection.py:655,1237,1588,2628,3070,3403,3728` | Progress has to be reported *from inside* the walk; nothing outside it can see units go by |
| Sequence values in the preview are rendered with `repr(item)`, and an affix label already wraps its gloss in `'...'` | `merge_preview.py:322,341,346,521` and `:2583-2586` | The "quote soup" is two independent layers of added quoting; both are display-only |
| Segments render **concatenated with no separator** into one HTML line | `merge_preview.py:717-757` | One-affix-per-line needs a real list marker, not a smarter label |
| The slot affix list is capped at 25 and the truncation note does not say how many exist | `merge_preview.py:2071,2604-2607` | FR-037's disclosure gap is concrete and small |
| Contrast is already enforced automatically by a parametrised test over a declared `_CONTRAST_PAIRS` table | `tests/unit/test_theme_manager.py:519-553` | FR-026 "remains automated" means *extend this table*, not invent a mechanism |
| The Finish guard is real: Execute is disabled in `__init__` and again in `initializePage`, enabled only by a successful dry run, and gated on `_modify_allowed` | `selection_wizard.py:4726-4731,4774-4775` | US5 is verification plus two gaps (below) |
| Qt UI tests already run headless: `QT_QPA_PLATFORM=offscreen` + a `qapp` fixture, with the theme pinned off by `GRAMTRANS_NO_THEME=1` | `conftest.py:38`, `tests/unit/test_014_pane_display.py:15-29` | Geometry assertions at 900 px and palette assertions are both testable without a screen |

## Decisions

### D1 — Progress runs on the UI thread, pumped from inside the enumeration

**Decision**: Keep every LCM read on the thread that owns the project handle.
Thread a Qt-free progress sink into the inventory builders; the Qt
implementation is a modal indicator whose `tick` both advances the bar and
pumps the event loop.

**Rationale**: The builders walk LCM objects through pythonnet. LCM's cache is
not documented as thread-safe and the handle is opened by the host on the UI
thread, so moving the walk to a worker `QThread` would trade a cosmetic defect
for a correctness risk on the one path FR-045 forbids disturbing. Pumping from a
`QTimer` cannot work either: while a synchronous walk holds the thread, no timer
ever fires — which is exactly why the window greys out today. The only place
that *can* yield is inside the walk, so that is where the tick belongs.

**Alternatives considered**:
- *Worker thread + signals*: correct-looking, and the standard Qt answer, but it
  puts LCM reads on a second thread. Rejected on Principle I risk.
- *`processEvents()` on a timer*: cannot fire during the blocking call.
- *Indeterminate spinner painted from a separate thread*: paints, but Windows
  still marks the window "Not Responding" (FR-018, SC-002) because the main
  thread's message queue is not being drained.

### D2 — One threshold, two triggers, prediction from a count the caller already has

**Decision**: Declare `PROGRESS_THRESHOLD_MS = 500` in exactly one place
(`Lib/progress.py`) and use it twice: as `QProgressDialog.setMinimumDuration`
for the elapsed-time fallback (FR-014b), and as the bar an *anticipated* wait
must clear before the indicator is shown up front (FR-014a). Prediction is
`total_units / units_per_second >= 0.5 s`, where the rate is a declared
per-operation calibration constant.

**Rationale**: FR-019a forbids per-operation tuning of the threshold, and
`setMinimumDuration` is the exact behaviour FR-019 asks for (no dialog at all
for work that finishes first — no flash, no flicker). Making the *rate* the only
per-operation number keeps the threshold single and the prediction auditable: a
maintainer can see why an operation was predicted slow and re-measure the rate
without touching the threshold.

**Alternatives considered**:
- *Elapsed-time only*: simpler, and it is what the 500 ms clarification first
  suggested, but the clarification then chose predictive-first — an operator
  wants "how long will I wait", which needs the total on the first frame.
- *Per-operation delays*: rejected by FR-019a.
- *Remaining-time estimate*: explicitly out of scope; a throughput model is not
  built here.

### D3 — Totals only where they are already O(1)

**Decision**: Take determinate totals from calls the project already answers
cheaply — `LexiconNumberOfEntries()` for the entry-driven pages (affixes, stems,
skeleton, dependencies), `TextsNumberOfTexts()` for the texts page, and the
`.Count` of a possibility list for the list-driven blocks (phonology, rules,
entry types, custom fields). Everything else stays indeterminate.

**Rationale**: FR-014d and the matching assumption forbid buying a nicer bar
with a slower operation. Verified through the FLExToolsMCP that
`FLExProject.LexiconNumberOfEntries()` and `FLExProject.TextsNumberOfTexts()`
exist and are count reads, not enumerations; `ObjectCountFor(repository)` is the
generic form if a further count is needed.

**Alternatives considered**:
- *Pre-count pass per page*: doubles the walk to describe it. Rejected by
  FR-014d and by the "determinate progress is opportunistic" assumption.
- *Progress by page rather than by unit*: an 11-step bar that sits still for 40
  seconds answers nothing.

### D4 — One indicator, ever

**Decision**: The Qt sink keeps a single module-level current indicator. A
`begin` while one is already up **re-labels** the existing indicator and
restores the outer label on `end` (a small stack of labels, one dialog).

**Rationale**: FR-021 wants one indicator describing current work. Nested waits
are real here — a page's `initializePage` can build two inventories.

### D5 — Numbering is walked, not counted, and no total is displayed

*Revised 2026-08-17 after review-gate pushback: the first version of this
decision computed `Step {i} of {N}` statically from the declaration's length.
That presumed the flow length is knowable up front. It is not.*

**Decision**: Replace the twelve `setTitle("Step N of 10: ...")` literals with
one ordered declaration in `SelectionWizard` that fixes **order and skip
eligibility only**. A page's number is assigned on entry as "pages shown before
me, plus one". **No total is displayed anywhere.** Skipping is
`QWizardPage.nextId()`, which resolves the next page to show before navigating to
it, so a page's number is always one more than the number the operator was just
looking at.

**Rationale**: A page with nothing to decide should not be shown, and once pages
can drop out, a total becomes a claim the wizard cannot honour. Two things make it
unknowable: emptiness for the Custom Fields / Phonology / Rules / Entry Types /
Texts pages is a *source* property not known until a source is bound (which
happens *on* step 1 in the standalone), and for Morphology Skeleton / Grammatical
Dependencies it depends on picks the operator has not made yet. Any total shown
before those facts land would have to be corrected afterwards — which is exactly
the stale-total defect ("of 5", "of 10" across 11 pages) this story exists to
remove. Dropping the total does not weaken the guarantee, it strengthens it: a
stale total becomes unrepresentable rather than merely fixed, and consecutiveness
follows from how the operator moves rather than from a promise made in advance.

FR-010 still gets its single declared source — order and skip eligibility live in
one table, so adding or reordering a page cannot leave a stale number behind or
silently change which pages may vanish.

**Alternatives considered**:
- *Static `of N` from the declaration's length*: the original plan. Correct only
  if no page is ever skipped. Rejected on the pushback.
- *Skip pages and let the total drop mid-run*: honest but visibly wrong — a page
  painted before a skip was discovered claims a larger total than the pages after
  it, and going Back to change a pick moves it again.
- *Skip pages and keep `of 12`, leaving gaps in the numbering*: reads as a bug.
- *Never skip; show every page with an empty state*: predictable, and it is what
  the spec first said, but it makes the operator click Next through pages that ask
  them nothing.

### D5a — Skip only what a count already knows; never skip the Affix or Stem picker

**Decision**: A page is skipped only where its emptiness is established at
negligible cost — the same O(1) reads D3 uses for progress totals. The predicate
is deliberately **conservative**: unsure means show. Selection-dependent pages
(Skeleton, Grammatical Dependencies) use the cheap proxy "nothing was picked at
all" rather than "the inventory would be empty". The Affix and Stem pickers are
exempt and always shown.

**Rationale**: Determining emptiness precisely for Affixes or Stems means walking
every entry and inspecting its MorphType — the 40-second walk US1 exists to
cover. Buying a shorter click-path with a longer wait is the trade FR-014d already
refuses for progress, and the same economy applies here. Conservatism matters for
a different reason: the only failure mode left is showing a page that turns out
empty, which costs a click, whereas wrongly skipping a page silently removes a
decision the operator was entitled to make. The Affix/Stem exemption is the
requester's call and a sound one — an operator never offered the wizard's central
decision concludes the tool is broken, not that the project is empty.

**Alternatives considered**:
- *Enumerate eagerly at bind to decide every page precisely*: front-loads every
  expensive walk into one long wait at step 1, which is the opposite of US1's
  intent.
- *Skip Skeleton / Gram Deps on the real inventory result, discovered on arrival*:
  possible, but it means entering a page and immediately leaving it, and it makes
  the number the operator sees depend on a walk that has already happened.

### D5b — `nextId()` must stay cheap, because Qt calls it often

**Decision**: Cache the source-derived counts once when a source binds; keep the
selection-dependent predicates to a `len(picks)` test.

**Rationale**: `QWizard` calls `nextId()` to decide whether Next is enabled, so it
can fire on every `completeChanged` — potentially on every checkbox click in a
tree. A predicate that re-reads a possibility list there would turn US1's fixed
waits into a stutter on every interaction. Caching at bind is safe because the
counts are source properties and the source cannot change mid-run.

### D6 — The split keeps the accessor name, so 23 call sites do not move

**Decision**: `_PageProjectWS` becomes two pages. The **projects** page keeps
ownership of binding and of `context()`, and keeps the existing
`page_project_ws()` accessor. A new `_PageWritingSystems` owns the two WS
tables and `ws_mapping()` / `selected_ws_ids()`, reachable through a new
`page_writing_systems()` accessor; it reads the bound handles from the projects
page.

**Rationale**: `page_project_ws()` is called 23 times, and every one of those
calls wants `context()` — which stays where it is. Renaming the accessor would
be a large diff with no behavioural payoff, and the P-1 rule (no literal page
indices) already protects the insertion. `_compute_wizard_plan`'s single
`ws_mapping()` read moves to the new accessor.

**Consequence to accept**: two feature-034 tests assert the *exact* current
subtitle of the combined page (`test_034_flextools_contract.py:185`,
`test_034_step1_source_picker.py:172-179`). That literal describes the one-page
design FR-006 removes, so those assertions are updated as part of this work —
the host-difference they guard (source picked vs host-supplied) is preserved and
still asserted on the projects page.

### D7 — Own the header; keep `subTitle()` as the string of record

**Decision**: Each page grows a laid-out header row at the top of its own
layout: the description in a word-wrapping `QLabel` plus a slot on the right for
the view controls. Turn on `QWizard.WizardOption.IgnoreSubTitles` so Qt stops
drawing the subtitle, but keep calling `setSubTitle(...)` — it stays the API and
test surface for the description text. `QWizard` keeps rendering the numbered
title above our header.

**Rationale**: This is the only shape that satisfies FR-004's "reserve separate
space" claim as a *layout* fact rather than a positioning guess, and it makes
FR-012/FR-013a testable headlessly (`label.wordWrap()`, and geometry
non-intersection at 900 px). Keeping `setSubTitle` avoids a pointless rename and
keeps the pages' descriptions in one obvious place.

**Alternatives considered**:
- *Widgets in the native Windows title bar*: rejected in the spec's assumptions
  — it costs a custom frame plus re-implemented drag/snap/maximise.
- *Keep the floating bar, add top padding to every page*: still not laid out, so
  the next long description re-creates the bug.
- *`QWizard.setSideWidget()`*: supported and laid out, but it is a vertical side
  panel, not the header row FR-004 names.
- *Insert a row into `QWizard`'s own grid layout*: undocumented internal
  structure; two widgets would share a cell and overlap — the defect again.

### D8 — One control strip, reparented on page change

**Decision**: Keep a single `ThemeCornerBar` instance and move it into the
current page's header slot on `currentIdChanged`.

**Rationale**: FR-005 requires every existing capability to survive, including
the keyboard shortcuts. Twelve live bars would register `Ctrl+0`, `ZoomIn` and
`ZoomOut` twelve times and Qt would resolve them as ambiguous — a shortcut that
silently stops working is exactly the regression FR-005 forbids.

### D9 — Remove the *added* quoting at its two sources, not at the renderer

**Decision**: Three changes, each at the place that adds punctuation:
1. Sequence members render with `str(item)`, not `repr(item)`
   (`_added_segments`, `_segments_for_sequence`, and the LINK-only sibling).
2. `_affix_msa_label` separates form from gloss with a wide gap instead of
   `'...'`.
3. `FieldDiff` gains `multiline: bool = False`; a list-valued field sets it, and
   the renderer emits one entry per line for such a field.
Plus: an empty list-valued field renders an explicit `(none)` note, and a capped
list states the true total.

**Rationale**: FR-034 is the constraint that decides this. Stripping quotes at
render time would also strip the apostrophes and quote marks that *are* the
linguistic data — glottal stops, ejectives, orthographic apostrophes. Removing
the quoting where it is added cannot touch data. `multiline` as a defaulted
field keeps every existing `FieldDiff` construction and every scalar field
byte-identical.

**Alternatives considered**:
- *Strip quotes in `_value_span`*: destroys real data (FR-034). Rejected.
- *Infer "is a list" from segment count*: a two-segment scalar replacement
  (`old → new`) is indistinguishable from a two-entry list. Rejected.
- *Render lists as `<ul>`*: `QTextBrowser`'s HTML subset handles it, but bullets
  add the punctuation FR-033 is trying to remove.

### D10 — Green is chosen against measurements, not by eye

**Decision**: In the dark palette, `alternate_base`, the `button` family and
`focus` become green; `highlight` stays `#2F6FD0`. Candidate values are in
`data-model.md`. Extend the automated palette checks with:
- new contrast pairs: `button_text`/`button`, `focus`/`window`,
  `text`/`alternate_base`;
- three colour-distance floors, measured as CIE-Lab ΔE76 (computed in the test
  helper from sRGB, no new dependency): accent green vs `diff_added`,
  `highlight` vs `alternate_base`, and `alternate_base` vs `base`.

**Rationale**: The spec's assumption puts the exact hue in the plan and the
*checkability* in the tests. ΔE76 in Lab is enough to separate two hues that a
reader must not confuse, and it is a dozen lines of arithmetic — ΔE2000 buys
precision this question does not need. The `alternate_base` vs `base` floor is
what turns FR-025's "distinguishable at a glance" into a number.

### D11 — 900 px is one declared constant, and the pages bend to it

**Decision**: One `MIN_WINDOW_WIDTH = 900` constant. Tree-and-preview pages keep
both panes (FR-029a) by making the shared splitter non-collapsible with pane
minimums that sum below the floor. Views elide with `Qt.TextElideMode.ElideRight`
and carry the full value in a tooltip (FR-029b); no page acquires a horizontal
scrollbar.

**Rationale**: `_make_tree_pane_splitter` is already the single place every such
page builds its splitter, so FR-029a lands in one function. Verifying at the
floor *and* the largest text scale together (SC-005, FR-032) is the hard case,
and it is reachable in the offscreen harness by resizing and comparing widget
geometries.

### D12 — The Finish guard is verified, and two gaps are closed

**Decision**: Keep the existing guard. Add (a) an explanation on the disabled
Execute control — a dry run is required, or the run is read-only (FR-039,
FR-044); (b) clearing of the previously shown dry-run report in
`initializePage`, so a stale result is never presented as current (FR-041).

**Rationale**: Verification against the code confirms FR-038, FR-040, FR-042,
FR-043 and the read-only half of FR-044 are already met. Two things are not:
nothing tells the operator *why* Execute is dead, and `initializePage` clears
the cached plan and the button but leaves the old `StatsPanel` report on screen.

## Open questions

None. The three items the spec deliberately left to the plan — the exact green,
the prediction rule, and the minimum-width layout technique — are decided above
(D10, D2, D11), each with the test that makes the choice checkable.
