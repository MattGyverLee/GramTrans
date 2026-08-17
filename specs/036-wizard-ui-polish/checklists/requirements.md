# Specification Quality Checklist: Wizard UI Polish Pass

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-17
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Validation history

**Iteration 1** — three issues found and fixed:

1. *Untestable minimum width.* FR-029 originally said only "lower than the
   current floor", which no test can pass or fail. Resolved by pinning a
   concrete floor (see FR-029) after confirming the target working posture with
   the requester.
2. *Framework capability presumed.* The request said "move Zoom and Color mode
   to the Title bar **if possible in the framework**", which is a conditional the
   spec must not silently resolve into a promise. Rewritten as an
   outcome — the controls live in window chrome and never overlap page content
   (FR-004) — with the placement decision recorded in Assumptions after
   confirming it with the requester, so the plan phase inherits a decision rather
   than a guess.
3. *Item 9 framed as new construction.* The Finish-page guard is already largely
   implemented. Specifying it as new work would have produced duplicate
   implementation tasks. Reframed as verification-plus-gap-closure and recorded
   in Assumptions, with the acceptance scenarios kept intact so the guard is
   actually proven rather than assumed.

**Iteration 2** — all items pass. No [NEEDS CLARIFICATION] markers remain.

**Iteration 3 (post-`/speckit-clarify`, same day)** — checkbox states unchanged at
16/16, but three items were passing on weaker evidence than the marks implied, and
clarification is what actually earned them:

- *Requirements are testable and unambiguous* — FR-014 and FR-019 turned on a
  "responsiveness threshold" that was never given a value, so neither could be
  passed or failed as written. Now 500 ms (FR-019a), and reframed: the trigger is
  **anticipated** duration first (FR-014a, FR-014c), with elapsed time as the
  fallback for work whose size cannot be known in advance (FR-014b). The
  requester's own framing drove this — the operator's question is "how long will I
  wait?", not "how long has it been?".
- *Success criteria are measurable* — SC-009 required "no description exceeds two
  lines" without saying at what width or text scale, which at the 900 px floor
  with maximum text would have silently mandated gutting the copy. Now budgeted at
  the default width and scale (FR-013), with FR-013a absorbing extra lines
  elsewhere.
- *All functional requirements have clear acceptance criteria* — FR-033's
  "separated structurally" and FR-024's green scope were both open enough to
  build two different things from. Now one entry per line (FR-033, FR-035) and
  green on striping/buttons/focus with the selection highlight staying blue
  (FR-024a).

Two contradictions introduced by the new answers were found and removed rather
than left to be discovered during planning:

- The "colour-mode switch mid-wait" edge case became unreachable once wizard input
  is blocked during a wait (FR-018). Rewritten to say so, and to require the
  indicator be drawn from the active palette rather than hard-coded.
- One-affix-per-line makes any cap on the list costlier in vertical space, so
  FR-037 now requires a truncated list to disclose its true total. A silently
  truncated list would let an operator judge a slot on a fraction of its contents
  — a worse failure than the quote soup US4 exists to fix.

## Notes

- **Eight decisions in this spec were confirmed with the requester rather than
  assumed**, all recorded in the spec's Assumptions section and, for the six from
  the clarify session, in `## Clarifications`: the minimum-width floor and
  side-by-side retention; the placement of the zoom/colour-mode controls; the
  500 ms threshold; predictive-before-elapsed triggering; input blocked during a
  wait; the two-line copy budget's measurement basis; the green accent's surface
  scope; and one-affix-per-line.
- **What is deliberately left to the plan**: the exact green hex values, and which
  specific operations qualify for up-front (determinate) progress. Both are bounded
  by tests the spec already requires — the contrast floors and colour-distance
  checks (FR-026, FR-027, SC-008a) for the first, and FR-014d's prohibition on
  paying for prediction with a slower operation for the second. These are design
  and discovery work, not open questions.
- One assumption is worth re-reading before planning: **the green accents have no
  prior state to restore.** The repository's history contains no green accent
  palette — the current theme was the first the application owned and was
  blue-accented from the outset. US7 is therefore fresh design work held to the
  existing contrast floors, not a revert. If the requester expected a revert,
  that expectation cannot be met literally.
- **Item 9 (Finish-page guard) is expected to be largely already satisfied.**
  Planning should budget verification and regression coverage, not
  reimplementation.
- FR-045 and SC-011 are the feature's guard rail: this is a presentation-only
  change, and nothing about what GramTrans transfers may move.
