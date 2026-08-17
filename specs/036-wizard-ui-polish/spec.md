# Feature Specification: Wizard UI Polish Pass

**Feature Branch**: `036-wizard-ui-polish`

**Created**: 2026-08-17

**Status**: Draft

**Input**: User description: "UI tweaks to the standalone Windows app GUI: (1) Remove 'Phase 3c' from the title bar. (2) Move Project selection into its own dedicated Step 1 (renumbering all later steps). (3) Whenever the app is waiting on liblcm, show a progress meter (if the total is cheap to compute) or at minimum an indeterminate progress indicator, so users on large projects can tell it hasn't crashed. (4) Bring back the green accents (alternating row striping, buttons, etc.) that dark mode had before light mode was added. (5) Allow the window to be gracefully resized below the current minimum width limit. (6) Wrap Step descriptions to 2 lines when appropriate. (7) Move Zoom and Color-mode controls into the title bar if the framework allows. Label the zoom control 'Zoom:' and remove the A glyphs from the + and - buttons. (8) In the Morphology Skeleton slot preview, the affixes list shows a lot of quote characters, making entries hard to tell apart -- make affixes visually distinguishable. (9) On the Finish page, disable Execute until a Dry run has been run."

## Overview

Nine independent presentation-layer corrections to the GramTrans selection wizard.
None of them changes what GramTrans transfers, what it plans, or what it writes:
every requirement here is about what the operator can see, read, and trust while
driving the wizard. The wizard is used by field linguists — frequently on laptop
screens, frequently against projects large enough that a single grammar
enumeration takes tens of seconds — and each item below is a place where the
current presentation either withholds information the operator needs (progress,
step position, affix identity) or actively works against them (unreadable quote
soup, a window that refuses to shrink, a version-phase label that means nothing
to them).

Because the items are independent, they are specified as independent stories.
Shipping any single one is a real improvement; shipping none of the others does
not block it.

## Clarifications

### Session 2026-08-17

- Q: How long may an operation run before a progress indicator must appear? → A: 500 ms — as a fallback trigger only; see the next bullet
- Q: Should the indicator be triggered by elapsed time, or by how long the operation is expected to take? → A: Expected duration decides. Where the cost is knowable up front, the indicator appears before the work starts and states the scale of the work; the 500 ms elapsed-time rule is the fallback for operations whose cost cannot be predicted
- Q: During a wait that shows an indicator, what must the operator be able to do? → A: The window keeps repainting and stays movable; wizard input is blocked until the operation ends
- Q: At what window width and text scale is the two-line budget for step descriptions measured? → A: At the default width and text scale. Narrower or larger-text windows may wrap to a third line, which the layout must absorb without clipping
- Q: Which dark-mode surfaces get the green accent? → A: Alternating row striping, buttons, and the focus indicator. The selection highlight stays blue, so a selected row remains readable against green striping
- Q: How should the affixes in a slot preview be presented? → A: One affix per line, with form and gloss separated by whitespace or alignment rather than punctuation

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Know the wizard is working, not hung (Priority: P1)

A linguist opens the wizard against a large project and advances to a page that
must enumerate grammar from the lexical database. The window greys out and stops
repainting for 40 seconds. Nothing tells them whether the tool is working or has
died, so they kill it — and lose the selections they had already made. With this
story, every wait shows a visible, moving indicator naming what is being loaded
and — wherever the size of the job is knowable before it starts — how much of it
there is. The operator's real question is not "how long has this been going?" but
"how long will I be waiting?", and the indicator is there to answer that one.

**Why this priority**: This is the only item on the list that causes users to
lose work. An unreadable label is an annoyance; an apparently-hung window is a
correctness problem for the operator's session, because the rational response to
a frozen app is to kill it. It is also the item that gets *worse* as projects get
bigger, which is the direction real usage runs.

**Independent Test**: Drive the wizard against a project large enough for a
perceptible wait on a page that enumerates grammar. Confirm the indicator appears
at the start of the work rather than half a second into it, that it states how much
work there is, that it advances for the whole wait, that it names the operation,
and that it disappears when the page is ready. No other story needs to be
implemented for this to be testable.

**Acceptance Scenarios**:

1. **Given** a project whose grammar enumeration is known in advance to be large
   enough to take longer than 500 milliseconds, **When** the operator advances to
   the page that enumerates it, **Then** the indicator is already on screen when
   the work begins — the operator never sees a still window first.
1a. **Given** an operation whose size cannot be established in advance, **When**
   it runs past 500 milliseconds, **Then** the indicator appears at that point,
   names the operation, and stays until the operation ends.
2. **Given** an operation whose total unit count can be established without
   itself being slow, **When** that operation runs, **Then** the indicator shows
   determinate progress — units completed out of the total — so the operator can
   judge how much longer it will take.
3. **Given** an operation whose total cannot be established cheaply, **When**
   that operation runs, **Then** the indicator is indeterminate but still
   visibly animating, and still names the operation.
3a. **Given** any operation covered by this story, **When** the indicator is up,
   **Then** the window continues to repaint and can be moved, and no wizard
   control accepts input until the operation ends.
4. **Given** an operation that is neither predicted to be slow nor runs past 500
   milliseconds, **When** it runs, **Then** no indicator flashes on screen.
5. **Given** a wait in progress, **When** the operator moves or resizes the
   window, **Then** the window repaints — it is never reported as "Not
   Responding" by the operating system.
6. **Given** an operation that fails partway, **When** it fails, **Then** the
   indicator is dismissed and the failure is surfaced as a message — the
   indicator never remains on screen after the operation has stopped.

---

### User Story 2 - Pick the projects as a step of their own (Priority: P1)

Today the first page asks for two unrelated decisions at once: which projects to
transfer between, and how their writing systems correspond. The first is a
prerequisite for everything (nothing can be enumerated until both projects are
bound); the second is a detailed mapping exercise that only makes sense once
both projects are open. Splitting them gives the operator one decision per step
and makes the writing-system step able to show real, populated data on arrival
rather than empty tables.

**Why this priority**: It is the structural change on the list — it renumbers
every subsequent step, so it should land before anyone memorises the current
numbers, and it is the change most likely to conflict with other work if
deferred. It also fixes a live defect: one page in the current flow carries no
step number at all, and another carries a stale "of 5" count.

**Independent Test**: Walk the wizard end to end. Confirm step 1 asks only for
projects, step 2 asks only for writing systems, every page in the flow shows a
step number, the numbers ascend by one with no gaps or repeats, and the "of N"
total on every page equals the number of pages actually in the flow.

**Acceptance Scenarios**:

1. **Given** the wizard has just opened, **When** the operator reads step 1,
   **Then** it presents only the source and target project selection, and its
   title identifies it as step 1.
2. **Given** both projects are bound on step 1, **When** the operator advances,
   **Then** step 2 presents the writing-system correspondence with its tables
   already populated from the two bound projects.
3. **Given** the source and target are not both bound, **When** the operator
   tries to advance past step 1, **Then** advancing is refused and the reason is
   visible on the page.
4. **Given** any page in the flow, **When** the operator reads its title,
   **Then** it carries a step number and a total, the total is identical on
   every page, and it equals the count of pages in the flow.
5. **Given** the full flow, **When** the step numbers are read in order, **Then**
   they form a consecutive run from 1 to the total with no gaps, duplicates, or
   unnumbered pages.
6. **Given** a page that is retained in the codebase but not part of the flow,
   **When** the flow is walked, **Then** that page is never shown and its stale
   numbering can never be seen by the operator.

---

### User Story 3 - Fit the wizard on the screen you actually have (Priority: P2)

A linguist working on a small laptop, or side by side with FieldWorks on half a
screen, cannot narrow the wizard past its current floor. The window simply
refuses, so it either overhangs the screen edge or forces them to close the other
window they were comparing against. With this story the window narrows further
and the content adapts instead of being clipped.

**Why this priority**: It blocks a real working posture (wizard beside FLEx) but
costs the operator nothing except inconvenience when unmet — no data is lost and
nothing is misread.

**Independent Test**: Shrink the window horizontally to the new floor. Confirm it
resizes smoothly, that no control is clipped or overlapped at any width down to
the floor, and that every control remains reachable.

**Acceptance Scenarios**:

1. **Given** the wizard is open, **When** the operator drags its edge inward,
   **Then** the window narrows continuously to 900 pixels without snapping back
   or refusing.
2. **Given** the window is at its narrowest supported width, **When** the
   operator inspects any page, **Then** no label, button, or column is clipped,
   truncated without an ellipsis, or drawn over another control.
3. **Given** the window is at 900 pixels, **When** the operator inspects a page
   with a side-by-side tree and preview, **Then** both are still side by side,
   both remain usable, and every control on the page remains reachable.
3a. **Given** the window is at 900 pixels, **When** a column is too narrow for
   its content, **Then** the content is elided with a visible ellipsis and its
   full value stays available on demand — and the page acquires no horizontal
   scrollbar.
4. **Given** the window is at its narrowest supported width, **When** the
   operator looks for the navigation buttons, **Then** they are fully visible
   and clickable.

---

### User Story 4 - Read the affix list in a slot preview (Priority: P2)

An operator selecting inflectional slots on the Morphology Skeleton page clicks a
slot to see which affixes occupy it. The preview shows the list, but each entry
is wrapped in quote characters and each entry's own gloss carries a second pair
inside those, so a list of six affixes reads as a wall of punctuation and the
operator cannot tell one affix from the next. With this story each affix is a
distinct, scannable line.

**Why this priority**: It degrades a decision the operator is actively making —
whether a slot is worth transferring depends on what is in it — but it degrades
legibility rather than causing a wrong outcome, and only on one page.

**Independent Test**: Open the Morphology Skeleton page against a project with a
populated slot, select that slot, and read the affix list in the preview pane.
Confirm each affix is individually distinguishable and that no punctuation is
present that does not belong to the linguistic data itself.

**Acceptance Scenarios**:

1. **Given** a slot occupied by several affixes, **When** the operator selects
   it, **Then** each affix occupies its own line.
2. **Given** that affix list, **When** the operator reads it, **Then** no
   programmatic quoting has been added around the entries — the only quote
   characters shown are ones present in the linguistic data itself.
3. **Given** an affix whose display label combines a form and a gloss, **When**
   it is shown, **Then** form and gloss are separated by whitespace or alignment,
   with no added punctuation between them.
4. **Given** an empty slot, **When** the operator selects it, **Then** the
   preview says so plainly rather than showing an empty punctuation artifact.
4a. **Given** a slot with more affixes than the preview will list, **When** the
   operator selects it, **Then** the preview states that the list is truncated and
   how many affixes the slot actually holds.
5. **Given** any other list-valued field shown anywhere in the preview, **When**
   it is rendered, **Then** it follows the same rule — one entry per line, no
   added quote characters.

---

### User Story 5 - Trust the Finish page's guard rail (Priority: P2)

The Finish page offers a Dry run and an Execute. Execute must be unavailable
until the operator has actually seen a dry run of the plan they are about to
write, and must become unavailable again the moment that dry run stops describing
their current selections. This is the operator's last checkpoint before an
irreversible write.

**Why this priority**: The consequence of getting this wrong is a write the
operator did not preview, which is the one thing the wizard exists to prevent —
but the guard is believed to be substantially in place already, so the work is
verification and closing residual gaps rather than building from nothing.

**Independent Test**: Reach the Finish page and confirm Execute is unavailable.
Run a dry run and confirm it becomes available. Go back, change a selection,
return, and confirm it is unavailable again.

**Acceptance Scenarios**:

1. **Given** the operator has just arrived on the Finish page, **When** they look
   at Execute, **Then** it is visibly disabled and its disabled state explains
   that a dry run is required first.
2. **Given** no dry run has been run, **When** the operator attempts to trigger
   Execute by any means available on the page, **Then** no write occurs.
3. **Given** a dry run has completed successfully, **When** the operator looks at
   Execute, **Then** it is enabled.
4. **Given** a dry run has completed, **When** the operator navigates back,
   changes any selection, and returns to the Finish page, **Then** Execute is
   disabled again and the previously shown dry-run result is no longer presented
   as current.
5. **Given** a dry run that failed to produce a plan, **When** it finishes,
   **Then** Execute remains disabled and the failure is stated.
6. **Given** an Execute that has completed, **When** the operator remains on the
   page, **Then** Execute is disabled again so the same plan cannot be written
   twice.
7. **Given** the application is running without write permission, **When** the
   operator reaches the Finish page, **Then** Execute is disabled regardless of
   any dry run and the read-only condition is stated.

---

### User Story 6 - A title bar and chrome that speak to the operator (Priority: P3)

The title bar announces "Phase 3c" — an internal development milestone that means
nothing to a linguist and dates the tool. The zoom and colour-mode controls float
in the top-right corner over the page content, where they compete with the page
title. With this story the title names the tool and its purpose, and the
view controls sit in window chrome, clearly labelled, out of the content's way.

**Why this priority**: Pure polish. It costs the operator nothing but credibility
and a little clutter, and it is the item most constrained by what the UI
framework will actually allow.

**Independent Test**: Open the wizard and read the title bar. Confirm no internal
phase or milestone label appears, and confirm the zoom and colour-mode controls
are present, labelled, and do not overlap page content at any supported window
width.

**Acceptance Scenarios**:

1. **Given** the wizard is open, **When** the operator reads the window title,
   **Then** it identifies the application and its purpose and contains no
   internal development phase or milestone designation.
2. **Given** the wizard is open, **When** the operator looks for the zoom
   control, **Then** it is preceded by a visible "Zoom:" label.
3. **Given** the zoom control, **When** the operator reads its increase and
   decrease buttons, **Then** they are marked only as increase and decrease —
   the letter-A glyphs are gone.
4. **Given** the zoom and colour-mode controls, **When** the operator resizes the
   window to any supported width, **Then** the controls remain fully visible and
   never overlap the step title, the step description, or any page content.
4a. **Given** the window at its narrowest width, the largest supported text
   scale, and a step whose description fills both allowed lines, **When** the page
   is drawn, **Then** the controls and the description occupy separate space and
   neither is drawn over the other.
5. **Given** the zoom and colour-mode controls in their new position, **When** the
   operator uses them, **Then** every capability they had before still works:
   increase, decrease, reset to 100%, the current-percentage readout, the
   light/dark toggle, and the existing keyboard shortcuts.
6. **Given** the operator has set a text size above the default, **When** the
   controls are drawn, **Then** they remain reachable and do not grow to obscure
   page content.

---

### User Story 7 - Green accents in dark mode (Priority: P3)

Before light mode was introduced, dark mode carried green accents — alternating
row striping, button and focus colouring — that made lists easy to track
across and gave the tool its own identity. The current dark palette is
blue-accented with barely-visible row striping. With this story dark mode gets
its green accent family back, without giving up the contrast floors the current
palette established.

**Why this priority**: Preference and identity, plus a genuine legibility gain
from stronger row striping. Nothing is wrong or unreadable today.

**Independent Test**: Switch to dark mode and inspect a populated tree, a set of
buttons, and a selected row. Confirm striping, buttons and focus read as green,
that the selection stays blue and remains readable over the striping, that
alternating rows are clearly distinguishable from each other, and that measured
contrast still meets the palette's existing floors.

**Acceptance Scenarios**:

1. **Given** dark mode is active, **When** the operator views a populated list or
   tree, **Then** alternating rows are distinguishable from one another at a
   glance and the striping reads as a green tint.
2. **Given** dark mode is active, **When** the operator views buttons and the
   focus indicator, **Then** their accent colouring reads as green.
2a. **Given** dark mode is active and a row is selected in a striped tree,
   **When** the operator looks at it, **Then** the selection is blue, is plainly
   distinguishable from the green striping beneath it, and its text is readable.
3. **Given** the dark palette after this change, **When** its contrast is
   measured, **Then** every text-on-background pair still meets the contrast
   floor the palette already enforces, and the enforcement remains automated.
4. **Given** dark mode is active, **When** the operator views semantic colours
   that already carry meaning — warnings, added, removed — **Then** they remain
   distinguishable from the green accent and from each other, so accent green is
   never confusable with "added" green.
5. **Given** the operator switches between light and dark mode, **When** each is
   shown, **Then** both remain internally consistent and no control is left
   coloured for the other mode.

---

### User Story 8 - Step descriptions that finish their sentence (Priority: P3)

Several step descriptions are longer than one line at the window widths people
actually use, and are cut off. With this story a description that does not fit
wraps to a second line instead of being truncated.

**Why this priority**: A truncated description withholds guidance, but the
guidance is supplementary — the page's controls are still usable without it.

**Independent Test**: Narrow the window and visit each step. Confirm that any
description too long for one line occupies two, and that no description is cut
off.

**Acceptance Scenarios**:

1. **Given** a step whose description exceeds the available width, **When** the
   page is shown, **Then** the description wraps to a second line rather than
   being truncated.
2. **Given** a step whose description fits on one line, **When** the page is
   shown, **Then** it stays on one line and no blank second line is reserved.
3. **Given** a description that wraps, **When** the page is shown, **Then** no
   page content is pushed off screen or overlapped by the extra line.
4. **Given** the operator changes the text size or the window width, **When**
   descriptions are redrawn, **Then** they wrap or unwrap to suit, and remain
   fully readable at every supported combination.
5. **Given** a description longer than two lines at the default width and text
   scale, **When** the copy is reviewed, **Then** it is shortened to fit two lines
   there — two lines at the default is the budget, not a starting point.
6. **Given** a description that fits two lines at the default, **When** the window
   is narrowed to 900 pixels or the text scale is raised, **Then** it may wrap to a
   third line, and that extra line is absorbed without clipping the description,
   overlapping the zoom and colour-mode controls, or pushing page content off
   screen.

---

### Edge Cases

- **A wait that finishes instantly.** An operation that completes below the
  500-millisecond threshold must not flash an indicator on and off; a visible
  flicker is worse than no indicator.
- **A wait that never finishes.** If an operation hangs indefinitely, the
  indicator keeps animating and the window keeps repainting. Because wizard input
  is blocked (FR-018), the operator's only remaining exit is the operating
  system's own — closing or killing the window. That path must not leave a project
  handle open. Making a hung operation gracefully abandonable from inside the
  application requires cancellation, which is explicitly out of scope.
- **A predicted wait that turns out to be fast.** If a job's size predicted a long
  wait but it finishes almost immediately, the indicator will have been shown for a
  very short time. That is accepted: an indicator that appears and resolves quickly
  is honest about what was attempted, and is not the flicker FR-019 prohibits —
  FR-019 governs operations that were never predicted slow in the first place.
- **A fast operation that turns out to be slow.** The converse — a job whose size
  predicted speed but which runs long anyway — must still be caught by the
  elapsed-time fallback (FR-014b). The two triggers are not exclusive; whichever
  fires first governs.
- **Nested waits.** If one operation triggers another, the operator sees one
  indicator describing the current work, not a stack of competing dialogs.
- **A determinate total that turns out to be wrong.** If the counted total is
  exceeded, the indicator must not display more than 100% or a negative
  remainder; it degrades to indeterminate rather than displaying nonsense.
- **Renumbering with a conditionally-shown page.** If any page can be skipped for
  a given run, the step numbers the operator sees must still read consecutively
  — the numbering describes the flow shown, not the superset of pages that exist.
- **Releasing a bound project on the new step 1.** Unbinding a project after
  writing-system choices have been made on step 2 must not leave stale mappings
  attached to a project that is no longer bound.
- **Narrowest width with the largest text.** The minimum window width and the
  maximum text scale are independently reachable; the layout must survive both at
  once, which is the genuinely hardest case for clipping and overlap.
- **Affix labels containing real quote characters.** Linguistic data legitimately
  contains apostrophes and quote marks — glottal stops, ejectives, orthographic
  apostrophes. Removing *added* quoting must not remove or alter quoting that is
  part of the data.
- **A very long affix list in a slot.** A slot occupied by many affixes must
  remain scannable and must not make the preview pane grow without bound. Because
  each affix now takes a whole line, any cap reached must be stated along with the
  true total — a silently truncated list would let the operator judge a slot on a
  fraction of its contents, which is a worse failure than the quote soup this story
  set out to fix.
- **Dry run, then a change that does not alter the plan.** Any selection change
  after a dry run re-disables Execute. Re-enabling requires a fresh dry run even
  if the operator believes nothing material changed — the guard errs toward
  requiring another look.
- **Colour-mode switch mid-wait.** Not reachable: the colour-mode control is a
  wizard control, and wizard input is blocked while an indicator is up (FR-018).
  The indicator therefore only ever needs to render in the palette that was active
  when it appeared. It must still be drawn from the active palette rather than
  hard-coded, so that a wait entered in dark mode shows a dark indicator.

## Requirements *(mandatory)*

### Functional Requirements

**Title bar and window chrome (items 1, 7)**

- **FR-001**: The wizard's window title MUST identify the application and its
  purpose and MUST NOT contain any internal development phase, milestone, or
  iteration designation.
- **FR-002**: The zoom control MUST be preceded by a visible label reading
  "Zoom:".
- **FR-003**: The zoom increase and decrease controls MUST be marked as increase
  and decrease only, with no letter-A glyph.
- **FR-004**: The zoom and colour-mode controls MUST occupy a laid-out row in the
  wizard's own header rather than floating over page content, and MUST NEVER
  overlap the step title, the step description, or any page control — at any
  supported window width and any supported text scale. Overlap of the step
  description is the specific failure this requirement exists to prevent: the
  controls and the description MUST reserve separate space, so that a description
  grown to its full wrapped height — however many lines that takes at the current
  width and text scale (FR-013a) — cannot run underneath them.
- **FR-005**: Relocating those controls MUST preserve every existing capability:
  increase, decrease, reset to the default size, the current-percentage readout,
  the light/dark toggle, and all existing keyboard shortcuts.

**Step structure (items 2, 6)**

- **FR-006**: Source and target project selection MUST occupy a step of their
  own, presented first, containing no other decision.
- **FR-007**: Writing-system correspondence MUST occupy the step immediately
  after project selection, and MUST present its data already populated from the
  two bound projects on arrival.
- **FR-008**: Advancing past the project-selection step MUST be refused until
  both a source and a target project are bound, with the reason visible on the
  page.
- **FR-009**: Every page in the wizard flow MUST display a step number and a
  total; the numbers MUST be consecutive from 1 with no gaps or duplicates, and
  the total MUST be identical on every page and equal to the number of pages in
  the flow.
- **FR-010**: Step numbering and the total MUST derive from a single declared
  source, so that adding, removing, or reordering a page cannot leave a stale
  number or total behind.
- **FR-011**: A page retained in the codebase but excluded from the flow MUST NOT
  be reachable by the operator, and its numbering MUST NOT be displayed.
- **FR-012**: A step description too long for one line MUST wrap to a second
  line rather than being truncated; a description that fits MUST remain on one
  line without reserving a blank second line.
- **FR-013**: Step descriptions MUST fit within two lines **at the default window
  width and default text scale**; any description exceeding that budget MUST be
  shortened. This is a copy-length budget, measured once at the default, not a
  guarantee at every size.
- **FR-013a**: At narrower widths or larger text scales a description MAY wrap
  beyond two lines. The layout MUST absorb the extra line or lines without
  clipping the description, overlapping the zoom and colour-mode controls
  (FR-004), or pushing page content off screen.

**Progress feedback (item 3)**

- **FR-014**: Any operation that reads or writes the lexical database MUST present
  a visible progress indicator when either trigger fires, whichever comes first:
  - **FR-014a — anticipated cost (primary).** Where the size of the work can be
    established before it begins, and that size predicts a wait longer than 500
    milliseconds, the indicator MUST appear *before* the work starts. The operator
    is told what is coming rather than being made to wait to find out.
  - **FR-014b — elapsed time (fallback).** Where the size of the work cannot be
    established in advance, the indicator MUST appear once the operation has run
    for 500 milliseconds.
- **FR-014c**: For any operation whose size is knowable in advance, the indicator
  MUST state the scale of the work — how much there is to do — not merely that
  work is happening. "How long we will wait" is the question the indicator exists
  to answer; "how long it has been" is not a sufficient answer to it.
- **FR-014d**: The prediction MUST NOT cost more than it saves. An operation
  qualifies for FR-014a only where its size is already known or obtainable at
  negligible cost; establishing size MUST NOT itself introduce a perceptible
  wait (see FR-016 and the matching assumption).
- **FR-015**: The indicator MUST name the operation in terms the operator can
  recognise, not in internal or technical vocabulary.
- **FR-016**: When the total unit count for an operation can be established
  without itself incurring a perceptible cost, the indicator MUST show
  determinate progress — units completed against that total.
- **FR-017**: When the total cannot be established cheaply, the indicator MUST be
  indeterminate but MUST still animate visibly, so that "working" is
  distinguishable from "stopped".
- **FR-018**: The application window MUST continue to repaint, and MUST NOT be
  reported as unresponsive by the operating system, for the duration of any such
  wait. Wizard input MUST be blocked while an indicator is up: the window remains
  movable, resizable, and repainting, but no wizard control accepts input until
  the operation ends. This is what keeps a wait from becoming a re-entrant read of
  the lexical database.
- **FR-019**: An operation that neither predicts a long wait (FR-014a) nor runs
  past 500 milliseconds (FR-014b) MUST NOT display an indicator at all — no flash,
  no flicker.
- **FR-019a**: The 500-millisecond threshold MUST be one project-wide value
  declared in a single place, used both as the elapsed-time fallback and as the
  bar an anticipated wait must clear, and not tuned per operation.
- **FR-020**: When an operation ends — successfully, by failure, or by the
  operator abandoning the wizard — the indicator MUST be dismissed, and a failure
  MUST be surfaced to the operator as a message.
- **FR-021**: Concurrent or nested operations MUST present at most one indicator
  at a time, describing the work currently in progress.
- **FR-022**: Progress feedback MUST NOT alter what any operation reads, plans,
  or writes; it is observation only.
- **FR-023**: The set of operations covered MUST be enumerated explicitly and
  MUST include, at minimum: binding a source project, binding a target project,
  each per-page grammar or lexical enumeration, dry-run plan assembly, and the
  execute-move write.

**Dark-mode accents (item 4)**

- **FR-024**: Dark mode MUST use a green accent family for alternating row
  striping, buttons, and the focus indicator.
- **FR-024a**: The dark-mode selection highlight MUST remain blue. Selection and
  row striping are drawn on top of one another in a tree, so they MUST stay
  different hues, and a selected row MUST remain clearly readable against a
  green-striped one.
- **FR-025**: Dark-mode alternating row striping MUST be distinguishable at a
  glance on populated lists and trees and MUST read as a green tint.
- **FR-026**: The dark palette MUST continue to meet the contrast floors the
  existing palette enforces, and that enforcement MUST remain automated rather
  than asserted by review.
- **FR-027**: The accent green MUST remain visually distinguishable from every
  semantic colour that already carries meaning — in particular the "added" green
  of the difference display — so that accent colouring is never mistaken for
  meaning.
- **FR-028**: Light mode MUST remain internally consistent; no control may be
  left coloured for the other mode after a switch in either direction.

**Window resizing (item 5)**

- **FR-029**: The window's minimum width MUST be 900 pixels, down from 1100, and
  the window MUST narrow continuously to that floor without refusing or snapping
  back. The minimum height is unchanged.
- **FR-029a**: Pages presenting a tree beside a preview MUST keep both side by
  side at every width down to the 900-pixel floor; the layout MUST NOT reflow,
  stack, or hide either one.
- **FR-029b**: Where a column or label cannot fit at a narrow width, it MUST be
  shortened with a visible ellipsis and its full value MUST remain available to
  the operator on demand; content MUST NOT be cut off without indication, and the
  page MUST NOT acquire a horizontal scrollbar.
- **FR-030**: At every width from the new floor upward, no label, button, or
  column may be clipped, truncated without an ellipsis, or drawn over another
  control.
- **FR-031**: At the narrowest supported width, every control on every page MUST
  remain reachable, and the wizard's navigation controls MUST remain fully
  visible and operable.
- **FR-032**: The layout MUST hold at the narrowest supported width combined with
  the largest supported text scale.

**Slot affix legibility (item 8)**

- **FR-033**: List-valued fields in the preview display MUST place each entry on
  its own line, and MUST NOT add quote characters around entries.
- **FR-034**: Quote and apostrophe characters that are part of the linguistic
  data MUST be preserved exactly; only added programmatic quoting may be
  removed.
- **FR-035**: An affix label combining a form with a gloss MUST distinguish the
  two by whitespace or alignment, not by quote characters or other punctuation
  added for the purpose.
- **FR-036**: An empty list-valued field MUST be presented as explicitly empty
  rather than as an empty punctuation artifact.
- **FR-037**: A slot occupied by many affixes MUST remain scannable and MUST NOT
  cause the preview pane to grow without bound. One-entry-per-line trades vertical
  space for legibility, so where the list is capped the cap MUST be disclosed to
  the operator — a truncated list MUST say that it is truncated and how many
  entries exist, never silently show the first few as though they were all.

**Finish-page guard (item 9)**

- **FR-038**: Execute MUST be disabled on arrival at the Finish page and MUST
  remain disabled until a dry run has completed successfully.
- **FR-039**: While Execute is disabled for want of a dry run, its state MUST
  explain that a dry run is required.
- **FR-040**: No write MUST occur through any affordance on the Finish page while
  Execute is disabled.
- **FR-041**: Any change to any selection after a successful dry run MUST
  re-disable Execute, and the prior dry-run result MUST cease to be presented as
  current.
- **FR-042**: A dry run that fails to produce a plan MUST leave Execute disabled
  and MUST state the failure.
- **FR-043**: A completed Execute MUST leave Execute disabled, so that the same
  plan cannot be written twice.
- **FR-044**: When the application is running without write permission, Execute
  MUST be disabled irrespective of any dry run, and the read-only condition MUST
  be stated.

**Scope guard, applying to every requirement above**

- **FR-045**: No requirement in this feature may change what GramTrans
  enumerates, plans, or writes. The set of transferred objects and their content
  MUST be byte-identical before and after this feature for any given set of
  selections.

### Key Entities

- **Step**: One page of the wizard flow, carrying a position, a total, a title,
  and a description. Position and total are derived from the declared flow, never
  written per page.
- **Progress report**: What the operator is shown during a wait — an operation
  name, and either a completed-against-total pair or an indeterminate marker. Its
  purpose is to answer "how much longer?", so where a total is known it is part of
  the report from the first frame, not filled in as work proceeds.
- **Anticipated size**: A count, known or cheaply obtainable before an operation
  begins, that both predicts whether the wait warrants an indicator (FR-014a) and
  supplies the total the report displays (FR-014c, FR-016). Where no such count
  exists, the operation falls back to elapsed-time triggering and an indeterminate
  report.
- **Palette accent set**: The colours a mode uses for row striping, buttons and
  focus — distinct both from the selection highlight, which is tracked separately
  because it is drawn over striping, and from the semantic colours that carry
  meaning.
- **Preview list field**: A field whose value is a sequence of labels shown in the
  preview display, rendered one entry per line rather than as a quoted
  collection.
- **Dry-run result**: The previewed plan the operator has seen, valid only for the
  selection state that produced it and invalidated by any change to it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No wait longer than 500 milliseconds anywhere in the wizard leaves
  the operator without a visible, active indicator — verified against the largest
  available test project across every operation enumerated in FR-023.
- **SC-001a**: No operation that is neither predicted slow nor exceeds 500
  milliseconds displays an indicator, verified by driving each FR-023 operation
  against a project small enough to finish under the threshold and confirming
  nothing appears.
- **SC-001b**: For every FR-023 operation whose size is knowable in advance, the
  indicator is on screen before the work starts and states the total amount of
  work — measured by confirming the operator never observes a still window ahead
  of the indicator, and that the total shown matches the work actually performed.
- **SC-002**: The operating system never reports the wizard as unresponsive
  during any operation, measured across a full end-to-end run on the largest
  available test project.
- **SC-003**: Every page in the flow shows a step number; the numbers read
  consecutively from 1 to the stated total, and the total matches the flow's page
  count — verified by walking the flow and by an automated check that fails if a
  page is added or reordered without the numbering following.
- **SC-004**: Zero pages present an unnumbered or stale-total step title, down
  from two in the current flow.
- **SC-005**: The window can be narrowed to 900 pixels with no clipped or
  overlapping control on any page and no horizontal scrollbar, verified at both
  the default and the largest supported text scale, with tree-and-preview pages
  still side by side at the floor.
- **SC-005a**: The zoom and colour-mode controls never overlap the step title or
  the step description, verified at 900 pixels and the largest supported text
  scale using the longest description in the wizard — the worst case for both.
- **SC-006**: An operator asked to identify which affixes occupy a given slot can
  read them off the preview correctly on first attempt — one affix per line, with
  no quote characters present other than those in the data.
- **SC-007**: No sequence of actions on the Finish page can reach a write without
  a successful dry run of the current selection state having been shown first.
- **SC-008**: Dark-mode alternating rows, buttons and focus read as green while
  the selection highlight remains blue, and every measured contrast pair still
  meets the palette's existing floors, with the measurement automated.
- **SC-008a**: A selected row in a striped tree is distinguishable from the
  striping under it in dark mode, and the accent green is distinguishable from the
  diff display's "added" green — both verified as explicit colour-distance checks
  rather than by eye.
- **SC-009**: No step description exceeds two lines at the default window width
  and text scale, and no step description is truncated at any supported
  combination of width and text scale — including the 900-pixel floor at the
  largest scale, where extra wrapped lines are permitted but clipping is not.
- **SC-010**: The window title contains no internal phase or milestone label.
- **SC-011**: For an identical set of selections, the objects transferred and
  their content are unchanged from before this feature — the whole feature is
  observably presentation-only.

## Assumptions

- **The nine items are independent.** Each is specified and can be delivered on
  its own; none depends on another's completion. They are grouped into one
  feature because they share a surface, not because they share a mechanism.
- **The green accents are a design decision, not an archaeological one.** No
  green accent palette exists in this repository's history to restore — the
  current theme was the first the application owned, and it was blue-accented
  from the start. What the operator remembers predates the application having any
  palette of its own. FR-024 through FR-028 therefore specify green as a fresh
  design intent, held to the contrast floors the existing palette established,
  rather than as a revert to a prior state.
- **Green applies to dark mode only.** The request named dark mode specifically.
  Light mode keeps its current accent family, and the two modes are allowed to
  differ in accent hue.
- **Green covers striping, buttons and focus — not selection, confirmed with the
  requester.** The selection highlight stays blue (FR-024a) because selection is
  drawn over striping in a tree; making both green would put the two most
  frequently co-occurring surfaces in the same hue. It also sidesteps the tightest
  contrast target in the palette, which is highlighted text on the highlight
  colour.
- **The exact green is left to the plan.** The spec fixes which surfaces are green
  and the constraints the hue must satisfy — the existing contrast floors (FR-026)
  and measurable distance from the diff display's "added" green (FR-027, SC-008a)
  — but not the hex values. Choosing them is design work bounded by those tests,
  and the tests are what make the choice checkable.
- **The threshold is 500 milliseconds, and it is predictive first, confirmed with
  the requester.** The operator's question is "how long will I be waiting?", not
  "how long has this been going?" — so where the size of a job is knowable before
  it starts, the indicator appears up front and states the scale of the work
  (FR-014a, FR-014c). Elapsed time is only the fallback for jobs whose size cannot
  be known in advance (FR-014b). 500 ms is one project-wide value (FR-019a) that
  serves as both the fallback delay and the bar an anticipated wait must clear.
- **Prediction is free or it does not happen.** FR-014d forbids buying a better
  progress display with a slower operation. In practice this means an operation
  qualifies for up-front display only where a count it already has — or can get at
  negligible cost — predicts the wait. Where no such count exists, the elapsed-time
  fallback is the correct and sufficient answer, and no extra pass may be added to
  manufacture one.
- **Determinate progress is opportunistic.** An operation gets a real meter only
  where the total is already known or trivially countable. Nowhere does this
  feature justify an extra enumeration pass purely to populate a progress bar —
  that would make the wait longer to describe it better.
- **The Finish-page guard is substantially implemented already.** Execute is
  already disabled on construction and on every page entry, and is enabled only
  by a successful dry run. FR-038 through FR-044 are therefore expected to
  resolve mostly to verification and regression coverage, plus closing any gap
  that verification exposes. If verification finds the guard complete, saying so
  with evidence satisfies the story — this is deliberately not scoped as new
  construction.
- **The unnumbered and stale-numbered pages are in scope.** One page in the
  current flow carries no step number and one retained-but-unreachable page
  carries a stale "of 5". Renumbering fixes both; they are not tracked
  separately.
- **The quote problem is a rendering choice, not a data problem.** The preview
  renders sequence entries through a representation that quotes strings, and
  affix labels separately wrap their gloss in quotes. Both are display concerns.
  No stored data is affected, and FR-034 exists to keep it that way.
- **Affixes go one per line, confirmed with the requester**, with form and gloss
  separated by whitespace or alignment rather than punctuation (FR-033, FR-035).
  This costs vertical space in the preview pane, which is why FR-037 requires any
  cap on the list to be disclosed rather than silent — trading legibility for a
  quietly truncated list would replace one misreading with a worse one.
- **The minimum-width floor is 900 pixels, confirmed with the requester**, and is
  a single project-wide value applying to the wizard window as a whole rather than
  being negotiated per page. 900 was chosen so the wizard occupies half of a
  1920-pixel monitor beside FieldWorks. The requester also chose to keep
  tree-and-preview pages side by side all the way down rather than reflowing them
  (FR-029a), accepting tighter columns and ellipsis truncation (FR-029b) as the
  cost. Minimum height stays where it is; only width was at issue.
- **The zoom and colour-mode controls go in the wizard's own header, not a custom
  window frame.** The UI framework cannot place widgets in the native Windows
  title bar without the application replacing the entire window frame and
  reimplementing dragging, snapping, maximising, and the minimise/maximise/close
  buttons. The requester chose the header strip over that cost, with the explicit
  condition that the controls must never overlap the step description — which is
  what FR-004 and SC-005a enforce. The native title bar is therefore retained,
  and item 1 (FR-001) is the only change to the title bar itself.
- **Existing keyboard shortcuts and accessibility behaviour are preserved
  throughout.** Nothing in this feature may remove a shortcut, a focus stop, or a
  tab order that works today.
- **Testing follows the project's existing UI test approach.** This feature
  introduces no new testing technology; where a requirement needs automated
  verification, it uses whatever the repository already uses for the wizard.
- **The standalone application and the FlexTools-hosted path share this
  surface.** Every requirement applies to both hosts. Where a host difference
  already exists — notably whether a source project is picked or supplied by the
  host — this feature preserves it and does not unify the two.

## Dependencies

- The wizard, its theme, and its preview display as they exist today. This
  feature modifies presentation within that structure and introduces no new
  external dependency.
- The lexical-database access layer, unchanged: progress feedback observes the
  operations it already performs and does not alter them.

## Out of Scope

- Any change to what is enumerated, planned, or written — see FR-045.
- Cancelling a long-running operation mid-flight. This feature makes waits
  *visible*; making them *interruptible* is a separate concern with its own
  consistency questions and is not specified here. FR-018's input blocking is the
  direct consequence: with no cancellation, there is nothing useful for a wizard
  control to do during a wait, and allowing input would only invite re-entrant
  database access.
- Estimating and displaying a remaining *time* ("about 30 seconds left"). FR-014c
  requires the indicator to state the scale of the *work*, which is knowable;
  converting that into a duration requires a throughput model this feature does
  not build.
- Persisting window size or position between sessions.
- Reworking the content of any step beyond the project/writing-system split and
  the two-line description budget.
- Restyling light mode's accent family.
- Any change to the difference display's semantic colours.
